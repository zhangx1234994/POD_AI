"""Authentication service for user login and token issuance."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import jwt
from fastapi import HTTPException
from passlib.context import CryptContext
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_session
from app.models.user import User


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class AuthService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def authenticate(self, *, username: str | None, email: str | None, password: str) -> User:
        with get_session() as session:
            query = select(User)
            if username:
                query = query.where(User.username == username)
            elif email:
                query = query.where(User.email == email)
            else:
                raise HTTPException(status_code=400, detail="LOGIN_IDENTIFIER_REQUIRED")
            user = session.execute(query).scalars().first()
            if not user or not self.verify_password(password, user.password_hash):
                raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
            if user.status != "active":
                raise HTTPException(status_code=403, detail="USER_INACTIVE")
            user.last_login_at = datetime.utcnow()
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def create_access_token(self, *, user: User, expires_delta: int | None = None) -> str:
        expire = datetime.utcnow() + timedelta(seconds=expires_delta or self.settings.jwt_access_token_expires)
        to_encode = {"sub": user.id, "role": user.role, "exp": expire}
        return jwt.encode(to_encode, self.settings.jwt_secret_key, algorithm="HS256")

    def create_refresh_token(self, *, user: User, expires_delta: int | None = None) -> str:
        expire = datetime.utcnow() + timedelta(seconds=expires_delta or self.settings.jwt_refresh_token_expires)
        token_id = uuid.uuid4().hex
        to_encode = {"sub": user.id, "jti": token_id, "type": "refresh", "exp": expire}
        return jwt.encode(to_encode, self.settings.jwt_secret_key, algorithm="HS256")

    def decode_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, self.settings.jwt_secret_key, algorithms=["HS256"])
        except jwt.PyJWTError as exc:  # type: ignore[attr-defined]
            raise HTTPException(status_code=401, detail="INVALID_TOKEN") from exc

    def build_service_user(self) -> User:
        user = User(id="service", email="service@podi.internal", role="admin", status="active")
        return user


auth_service = AuthService()
