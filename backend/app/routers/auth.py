"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException

from app.schemas import auth as schemas
from app.services.auth_service import auth_service
from app.core.db import get_session
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest) -> schemas.TokenResponse:
    user = auth_service.authenticate(username=payload.username, email=payload.email, password=payload.password)
    access_token = auth_service.create_access_token(user=user)
    refresh_token = auth_service.create_refresh_token(user=user)
    return schemas.TokenResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        expiresIn=auth_service.settings.jwt_access_token_expires,
        role=user.role,
    )


@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh_token(payload: schemas.RefreshRequest) -> schemas.TokenResponse:
    data = auth_service.decode_token(payload.refreshToken)
    if data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="INVALID_REFRESH_TOKEN")
    with get_session() as session:
        user = session.get(User, data.get("sub"))
        if not user:
            raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    access_token = auth_service.create_access_token(user=user)
    refresh_token = auth_service.create_refresh_token(user=user)
    return schemas.TokenResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        expiresIn=auth_service.settings.jwt_access_token_expires,
        role=user.role,
    )
