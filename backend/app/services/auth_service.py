"""Authentication service for login, sessions, and invite-based registration."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from threading import Lock
from typing import Any

import jwt
from fastapi import HTTPException, Request
from passlib.context import CryptContext
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_session
from app.models.user import InviteCode, User, UserSession


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 600


class AuthService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._login_failures: dict[str, list[datetime]] = {}
        self._login_failure_lock = Lock()

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def authenticate(
        self,
        *,
        username: str | None,
        email: str | None,
        password: str,
        request: Request | None = None,
    ) -> User:
        query = select(User)
        normalized_username = username.strip() if username else None
        normalized_email = email.strip().lower() if email else None
        if normalized_username:
            identifier = normalized_username
            query = query.where(User.username == identifier)
        elif normalized_email:
            identifier = normalized_email
            query = query.where(User.email == identifier)
        else:
            raise HTTPException(status_code=400, detail="LOGIN_IDENTIFIER_REQUIRED")
        rate_key = self._login_rate_key(identifier=identifier, request=request)
        self._check_login_rate_limit(rate_key)
        with get_session() as session:
            user = session.execute(query).scalars().first()
            if not user or not self.verify_password(password, user.password_hash):
                self._record_login_failure(rate_key)
                raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
            if user.status != "active":
                raise HTTPException(status_code=403, detail="USER_INACTIVE")
            user.last_login_at = datetime.utcnow()
            session.add(user)
            session.commit()
            session.refresh(user)
            self._clear_login_failures(rate_key)
            return user

    def register_with_invite(
        self,
        *,
        email: str,
        username: str,
        password: str,
        invite_code: str,
        display_name: str | None = None,
    ) -> User:
        normalized_email = email.strip().lower()
        normalized_username = username.strip()
        code = invite_code.strip()
        if not normalized_username:
            raise HTTPException(status_code=400, detail="USERNAME_REQUIRED")
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="PASSWORD_TOO_SHORT")
        with get_session() as session:
            invite = session.execute(select(InviteCode).where(InviteCode.code == code)).scalars().first()
            self._validate_invite(invite)
            existing = (
                session.execute(
                    select(User).where((User.email == normalized_email) | (User.username == normalized_username))
                )
                .scalars()
                .first()
            )
            if existing:
                raise HTTPException(status_code=409, detail="USER_ALREADY_EXISTS")
            user = User(
                id=uuid.uuid4().hex,
                email=normalized_email,
                username=normalized_username,
                display_name=display_name.strip() if display_name and display_name.strip() else None,
                password_hash=self.hash_password(password),
                role=invite.role,
                status="active",
                tenant_id=invite.tenant_id,
                client_id=invite.client_id,
                extra_metadata={"registered_by_invite": invite.id},
            )
            invite.used_count += 1
            if invite.used_count >= invite.max_uses:
                invite.status = "used"
            session.add(user)
            session.add(invite)
            session.commit()
            session.refresh(user)
            return user

    def create_invite_code(
        self,
        *,
        role: str = "user",
        tenant_id: str | None = None,
        client_id: str | None = None,
        max_uses: int = 1,
        expires_at: datetime | None = None,
        note: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_by: str | None = None,
    ) -> InviteCode:
        normalized_role = self._normalize_role(role)
        with get_session() as session:
            code = self._generate_unique_invite_code(session)
            row = InviteCode(
                id=uuid.uuid4().hex,
                code=code,
                role=normalized_role,
                tenant_id=self._clean_text(tenant_id, max_len=64),
                client_id=self._clean_text(client_id, max_len=64),
                max_uses=max(1, min(int(max_uses or 1), 100)),
                used_count=0,
                status="active",
                expires_at=expires_at,
                created_by=created_by,
                note=self._clean_text(note, max_len=500),
                extra_metadata=metadata,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_invite_codes(self, *, limit: int = 100) -> list[InviteCode]:
        with get_session() as session:
            rows = (
                session.execute(
                    select(InviteCode).order_by(InviteCode.created_at.desc()).limit(max(1, min(limit, 200)))
                )
                .scalars()
                .all()
            )
            return list(rows)

    def disable_invite_code(self, *, invite_id: str) -> InviteCode:
        normalized = invite_id.strip()
        with get_session() as session:
            row = session.get(InviteCode, normalized)
            if not row:
                row = session.execute(select(InviteCode).where(InviteCode.code == normalized)).scalars().first()
            if not row:
                raise HTTPException(status_code=404, detail="INVITE_CODE_NOT_FOUND")
            if row.status == "active":
                row.status = "disabled"
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_users(self, *, limit: int = 100) -> list[User]:
        with get_session() as session:
            rows = (
                session.execute(select(User).order_by(User.created_at.desc()).limit(max(1, min(limit, 200))))
                .scalars()
                .all()
            )
            return list(rows)

    def create_access_token(self, *, user: User, expires_delta: int | None = None) -> str:
        expire = datetime.utcnow() + timedelta(seconds=expires_delta or self.settings.jwt_access_token_expires)
        to_encode = {
            "sub": user.id,
            "role": user.role,
            "tenantId": getattr(user, "tenant_id", None),
            "clientId": getattr(user, "client_id", None),
            "exp": expire,
        }
        return jwt.encode(to_encode, self.settings.jwt_secret_key, algorithm="HS256")

    def create_refresh_token(self, *, user: User, expires_delta: int | None = None) -> str:
        token, _, _ = self._create_refresh_token_payload(user=user, expires_delta=expires_delta)
        return token

    def issue_token_pair(self, *, user: User, request: Request | None = None) -> dict[str, Any]:
        session_id = uuid.uuid4().hex
        access_token = self.create_access_token(user=user)
        refresh_token, refresh_jti, refresh_expire = self._create_refresh_token_payload(
            user=user,
            session_id=session_id,
        )
        with get_session() as db:
            db.add(
                UserSession(
                    id=session_id,
                    user_id=user.id,
                    refresh_jti=refresh_jti,
                    refresh_token_hash=self._hash_token(refresh_token),
                    status="active",
                    ip_address=self._request_ip(request),
                    user_agent=self._request_user_agent(request),
                    expires_at=refresh_expire,
                    last_seen_at=datetime.utcnow(),
                )
            )
            db.commit()
        return {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresIn": self.settings.jwt_access_token_expires,
            "role": user.role,
            "user": user,
        }

    def refresh_token_pair(self, *, refresh_token: str, request: Request | None = None) -> dict[str, Any]:
        try:
            payload = self.decode_token(refresh_token)
        except HTTPException as exc:
            if exc.detail in {"INVALID_TOKEN", "INVALID_TOKEN_PAYLOAD"}:
                raise HTTPException(status_code=401, detail="INVALID_REFRESH_TOKEN") from exc
            raise
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="INVALID_REFRESH_TOKEN")
        refresh_jti = str(payload.get("jti") or "")
        session_id = str(payload.get("sid") or "")
        if not refresh_jti:
            raise HTTPException(status_code=401, detail="INVALID_TOKEN_PAYLOAD")
        with get_session() as db:
            stmt = select(UserSession).where(UserSession.refresh_jti == refresh_jti)
            if session_id:
                stmt = stmt.where(UserSession.id == session_id)
            session_row = db.execute(stmt).scalars().first()
            if not session_row:
                raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
            now = datetime.utcnow()
            if session_row.status != "active":
                raise HTTPException(status_code=401, detail="SESSION_REVOKED")
            if session_row.expires_at <= now:
                session_row.status = "expired"
                db.add(session_row)
                db.commit()
                raise HTTPException(status_code=401, detail="SESSION_EXPIRED")
            user = db.get(User, session_row.user_id)
            if not user:
                raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
            if user.status != "active":
                raise HTTPException(status_code=403, detail="USER_INACTIVE")
            token_user = self._clone_user(user)
            session_row.status = "rotated"
            session_row.revoked_at = now
            db.add(session_row)
            db.commit()
        return self.issue_token_pair(user=token_user, request=request)

    def revoke_refresh_session(self, *, refresh_token: str) -> None:
        try:
            payload = self.decode_token(refresh_token)
        except HTTPException as exc:
            if exc.detail in {"INVALID_TOKEN", "INVALID_TOKEN_PAYLOAD"}:
                raise HTTPException(status_code=401, detail="INVALID_REFRESH_TOKEN") from exc
            raise
        refresh_jti = str(payload.get("jti") or "")
        if not refresh_jti:
            raise HTTPException(status_code=401, detail="INVALID_TOKEN_PAYLOAD")
        with get_session() as session:
            row = session.execute(select(UserSession).where(UserSession.refresh_jti == refresh_jti)).scalars().first()
            if not row:
                raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
            row.status = "revoked"
            row.revoked_at = datetime.utcnow()
            session.add(row)
            session.commit()

    def revoke_user_sessions(self, *, user_id: str) -> None:
        with get_session() as session:
            rows = session.execute(
                select(UserSession).where(UserSession.user_id == user_id, UserSession.status == "active")
            ).scalars().all()
            now = datetime.utcnow()
            for row in rows:
                row.status = "revoked"
                row.revoked_at = now
                session.add(row)
            session.commit()

    def list_sessions(self, *, user_id: str) -> list[UserSession]:
        with get_session() as session:
            rows = (
                session.execute(
                    select(UserSession).where(UserSession.user_id == user_id).order_by(UserSession.created_at.desc())
                )
                .scalars()
                .all()
            )
            return list(rows)

    def list_all_sessions(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with get_session() as session:
            rows = session.execute(
                select(UserSession, User)
                .join(User, UserSession.user_id == User.id)
                .order_by(UserSession.created_at.desc())
                .limit(max(1, min(limit, 500)))
            ).all()
            return [self._session_to_dict(session_row, user) for session_row, user in rows]

    def revoke_session_by_id(self, *, session_id: str) -> UserSession:
        with get_session() as session:
            row = session.get(UserSession, session_id.strip())
            if not row:
                raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
            if row.status != "revoked":
                row.status = "revoked"
                row.revoked_at = datetime.utcnow()
                session.add(row)
                session.commit()
                session.refresh(row)
            return row

    def decode_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, self.settings.jwt_secret_key, algorithms=["HS256"])
        except jwt.PyJWTError as exc:  # type: ignore[attr-defined]
            raise HTTPException(status_code=401, detail="INVALID_TOKEN") from exc

    def build_service_user(self) -> User:
        return User(
            id="service",
            email="service@podi.internal",
            username="service",
            password_hash="",
            role="admin",
            status="active",
        )

    def _create_refresh_token_payload(
        self,
        *,
        user: User,
        expires_delta: int | None = None,
        session_id: str | None = None,
    ) -> tuple[str, str, datetime]:
        expire = datetime.utcnow() + timedelta(seconds=expires_delta or self.settings.jwt_refresh_token_expires)
        token_id = uuid.uuid4().hex
        to_encode: dict[str, Any] = {"sub": user.id, "jti": token_id, "type": "refresh", "exp": expire}
        if session_id:
            to_encode["sid"] = session_id
        return jwt.encode(to_encode, self.settings.jwt_secret_key, algorithm="HS256"), token_id, expire

    def _validate_invite(self, invite: InviteCode | None) -> None:
        if not invite:
            raise HTTPException(status_code=400, detail="INVITE_CODE_INVALID")
        if invite.status == "used":
            raise HTTPException(status_code=409, detail="INVITE_CODE_USED")
        if invite.status == "expired":
            raise HTTPException(status_code=409, detail="INVITE_CODE_EXPIRED")
        if invite.status != "active":
            raise HTTPException(status_code=409, detail="INVITE_CODE_INACTIVE")
        if invite.expires_at and invite.expires_at <= datetime.utcnow():
            invite.status = "expired"
            raise HTTPException(status_code=409, detail="INVITE_CODE_EXPIRED")
        if invite.used_count >= invite.max_uses:
            invite.status = "used"
            raise HTTPException(status_code=409, detail="INVITE_CODE_USED")

    def _generate_unique_invite_code(self, session: Any) -> str:
        for _ in range(10):
            code = secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:16]
            exists = session.execute(select(InviteCode.id).where(InviteCode.code == code)).scalar()
            if not exists:
                return code
        raise HTTPException(status_code=500, detail="INVITE_CODE_GENERATE_FAILED")

    def _normalize_role(self, role: str) -> str:
        normalized = str(role or "user").strip().lower()
        if normalized not in {"user", "admin", "client"}:
            raise HTTPException(status_code=400, detail="ROLE_INVALID")
        return normalized

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _clone_user(self, user: User) -> User:
        return User(
            id=user.id,
            email=user.email,
            username=user.username,
            display_name=user.display_name,
            password_hash=user.password_hash,
            role=user.role,
            status=user.status,
            tenant_id=user.tenant_id,
            client_id=user.client_id,
            last_login_at=user.last_login_at,
            extra_metadata=user.extra_metadata,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def _session_to_dict(self, session_row: UserSession, user: User) -> dict[str, Any]:
        return {
            "id": session_row.id,
            "userId": session_row.user_id,
            "username": user.username,
            "email": user.email,
            "displayName": user.display_name,
            "status": session_row.status,
            "ipAddress": session_row.ip_address,
            "userAgent": session_row.user_agent,
            "expiresAt": session_row.expires_at,
            "revokedAt": session_row.revoked_at,
            "lastSeenAt": session_row.last_seen_at,
            "createdAt": session_row.created_at,
        }

    def _login_rate_key(self, *, identifier: str, request: Request | None) -> str:
        ip = self._request_ip(request) or "-"
        return f"{identifier.strip().lower()}|{ip}"

    def _check_login_rate_limit(self, rate_key: str) -> None:
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=LOGIN_FAILURE_WINDOW_SECONDS)
        with self._login_failure_lock:
            failures = [item for item in self._login_failures.get(rate_key, []) if item > cutoff]
            self._login_failures[rate_key] = failures
            if len(failures) >= LOGIN_FAILURE_LIMIT:
                raise HTTPException(status_code=429, detail="LOGIN_RATE_LIMITED")

    def _record_login_failure(self, rate_key: str) -> None:
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=LOGIN_FAILURE_WINDOW_SECONDS)
        with self._login_failure_lock:
            failures = [item for item in self._login_failures.get(rate_key, []) if item > cutoff]
            failures.append(now)
            self._login_failures[rate_key] = failures

    def _clear_login_failures(self, rate_key: str) -> None:
        with self._login_failure_lock:
            self._login_failures.pop(rate_key, None)

    def _request_ip(self, request: Request | None) -> str | None:
        if not request:
            return None
        for header in ("x-forwarded-for", "x-real-ip"):
            value = request.headers.get(header)
            if value:
                return value.split(",")[0].strip()[:64]
        return request.client.host[:64] if request.client else None

    def _request_user_agent(self, request: Request | None) -> str | None:
        if not request:
            return None
        return self._clean_text(request.headers.get("user-agent"), max_len=255)

    def _clean_text(self, value: str | None, *, max_len: int) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned[:max_len] if cleaned else None


auth_service = AuthService()
