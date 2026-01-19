"""Auth dependencies for FastAPI routes."""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.auth_service import auth_service
from app.core.db import get_session
from app.models.user import User
from app.core.config import get_settings


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    settings = get_settings()
    token: str | None = None
    if settings.service_api_token and credentials and credentials.scheme.lower() == "bearer" and credentials.credentials == settings.service_api_token:
        return auth_service.build_service_user()
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    else:
        token = request.query_params.get("access_token") or request.query_params.get("token")
        if not token:
            token = request.cookies.get("access_token") or request.cookies.get("token")
        if not token:
            referer = request.headers.get("referer")
            if referer:
                from urllib.parse import urlparse, parse_qs

                parsed = urlparse(referer)
                query = parse_qs(parsed.query)
                token = query.get("access_token", [None])[0] or query.get("token", [None])[0]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTHORIZATION_REQUIRED")
    if settings.service_api_token and token == settings.service_api_token:
        return auth_service.build_service_user()
    payload = auth_service.decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_TOKEN_PAYLOAD")
    with get_session() as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="USER_NOT_FOUND")
        if user.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="USER_INACTIVE")
        return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ADMIN_ONLY")
    return user
