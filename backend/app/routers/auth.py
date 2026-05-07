"""Authentication routes."""

from fastapi import APIRouter, Depends, Request

from app.deps.auth import get_current_user, require_admin
from app.models.user import User
from app.schemas import auth as schemas
from app.services.auth_service import auth_service


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenResponse, response_model_by_alias=False)
def login(payload: schemas.LoginRequest, request: Request) -> schemas.TokenResponse:
    user = auth_service.authenticate(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        request=request,
    )
    token_pair = auth_service.issue_token_pair(user=user, request=request)
    return schemas.TokenResponse(**token_pair)


@router.post("/refresh", response_model=schemas.TokenResponse, response_model_by_alias=False)
def refresh_token(payload: schemas.RefreshRequest, request: Request) -> schemas.TokenResponse:
    return schemas.TokenResponse(
        **auth_service.refresh_token_pair(refresh_token=payload.refreshToken, request=request)
    )


@router.post("/register", response_model=schemas.TokenResponse, response_model_by_alias=False)
def register(payload: schemas.RegisterRequest, request: Request) -> schemas.TokenResponse:
    user = auth_service.register_with_invite(
        email=str(payload.email),
        username=payload.username,
        password=payload.password,
        invite_code=payload.inviteCode,
        display_name=payload.displayName,
    )
    return schemas.TokenResponse(**auth_service.issue_token_pair(user=user, request=request))


@router.post("/logout")
def logout(payload: schemas.LogoutRequest, user: User = Depends(get_current_user)) -> dict[str, bool]:
    if payload.allSessions:
        auth_service.revoke_user_sessions(user_id=user.id)
    elif payload.refreshToken:
        auth_service.revoke_refresh_session(refresh_token=payload.refreshToken)
    return {"ok": True}


@router.get("/sessions", response_model=schemas.UserSessionListResponse, response_model_by_alias=False)
def list_sessions(user: User = Depends(get_current_user)) -> schemas.UserSessionListResponse:
    return schemas.UserSessionListResponse(items=auth_service.list_sessions(user_id=user.id))


@router.get("/sessions/all", response_model=schemas.UserSessionListResponse, response_model_by_alias=False)
def list_all_sessions(
    limit: int = 200,
    _: User = Depends(require_admin),
) -> schemas.UserSessionListResponse:
    return schemas.UserSessionListResponse(items=auth_service.list_all_sessions(limit=limit))


@router.post(
    "/sessions/{session_id}/revoke",
    response_model=schemas.UserSessionRead,
    response_model_by_alias=False,
)
def revoke_session(
    session_id: str,
    _: User = Depends(require_admin),
) -> schemas.UserSessionRead:
    return schemas.UserSessionRead.model_validate(
        auth_service.revoke_session_by_id(session_id=session_id),
        from_attributes=True,
    )


@router.post("/invite-codes", response_model=schemas.InviteCodeRead, response_model_by_alias=False)
def create_invite_code(
    payload: schemas.InviteCodeCreateRequest,
    user: User = Depends(require_admin),
) -> schemas.InviteCodeRead:
    row = auth_service.create_invite_code(
        role=payload.role,
        tenant_id=payload.tenantId,
        client_id=payload.clientId,
        max_uses=payload.maxUses,
        expires_at=payload.expiresAt,
        note=payload.note,
        metadata=payload.metadata,
        created_by=user.id,
    )
    return schemas.InviteCodeRead.model_validate(row, from_attributes=True)


@router.post(
    "/invite-codes/{invite_id}/disable",
    response_model=schemas.InviteCodeRead,
    response_model_by_alias=False,
)
def disable_invite_code(
    invite_id: str,
    _: User = Depends(require_admin),
) -> schemas.InviteCodeRead:
    return schemas.InviteCodeRead.model_validate(
        auth_service.disable_invite_code(invite_id=invite_id),
        from_attributes=True,
    )


@router.get("/invite-codes", response_model=schemas.InviteCodeListResponse, response_model_by_alias=False)
def list_invite_codes(
    limit: int = 100,
    _: User = Depends(require_admin),
) -> schemas.InviteCodeListResponse:
    return schemas.InviteCodeListResponse(items=auth_service.list_invite_codes(limit=limit))


@router.get("/users", response_model=schemas.UserListResponse, response_model_by_alias=False)
def list_users(
    limit: int = 100,
    _: User = Depends(require_admin),
) -> schemas.UserListResponse:
    return schemas.UserListResponse(items=auth_service.list_users(limit=limit))


@router.patch("/users/{user_id}", response_model=schemas.UserRead, response_model_by_alias=False)
def update_user(
    user_id: str,
    payload: schemas.UserUpdateRequest,
    user: User = Depends(require_admin),
) -> schemas.UserRead:
    return schemas.UserRead.model_validate(
        auth_service.update_user(
            user_id=user_id,
            display_name=payload.displayName,
            role=payload.role,
            status=payload.status,
            tenant_id=payload.tenantId,
            client_id=payload.clientId,
            note=payload.note,
            actor=user,
        )
    )


@router.get(
    "/scope-summary",
    response_model=schemas.AuthScopeSummaryResponse,
    response_model_by_alias=False,
)
def get_scope_summary(_: User = Depends(require_admin)) -> schemas.AuthScopeSummaryResponse:
    return schemas.AuthScopeSummaryResponse.model_validate(auth_service.scope_summary())
