"""Auth schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


def _attr_or_key(data: Any, key: str, default: Any = None) -> Any:
    if isinstance(data, dict):
        return data.get(key, default)
    return getattr(data, key, default)


def _normalize_aliases(data: Any, aliases: dict[str, str]) -> Any:
    if not isinstance(data, dict):
        return data
    normalized = dict(data)
    for old_key, new_key in aliases.items():
        if old_key in normalized and new_key not in normalized:
            normalized[new_key] = normalized[old_key]
    return normalized


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    role: str
    status: str
    displayName: str | None = None
    tenantId: str | None = None
    clientId: str | None = None
    createdAt: datetime | None = None
    lastLoginAt: datetime | None = None
    adminAudit: list["AuthUserAuditItem"] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_source(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return _normalize_aliases(
                data,
                {
                    "display_name": "displayName",
                    "tenant_id": "tenantId",
                    "client_id": "clientId",
                    "created_at": "createdAt",
                    "last_login_at": "lastLoginAt",
                    "admin_audit": "adminAudit",
                },
            )
        metadata = _attr_or_key(data, "extra_metadata") or {}
        admin_audit = metadata.get("admin_audit", []) if isinstance(metadata, dict) else []
        return {
            "id": _attr_or_key(data, "id"),
            "username": _attr_or_key(data, "username"),
            "email": _attr_or_key(data, "email"),
            "role": _attr_or_key(data, "role"),
            "status": _attr_or_key(data, "status"),
            "displayName": _attr_or_key(data, "display_name"),
            "tenantId": _attr_or_key(data, "tenant_id"),
            "clientId": _attr_or_key(data, "client_id"),
            "createdAt": _attr_or_key(data, "created_at"),
            "lastLoginAt": _attr_or_key(data, "last_login_at"),
            "adminAudit": admin_audit if isinstance(admin_audit, list) else [],
        }


class AuthUserAuditItem(BaseModel):
    action: str | None = None
    actorUserId: str | None = None
    actorUsername: str | None = None
    actorRole: str | None = None
    note: str | None = None
    changedFields: list[str] = Field(default_factory=list)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    createdAt: datetime | str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_source(cls, data: Any) -> Any:
        return _normalize_aliases(
            data,
            {
                "actor_user_id": "actorUserId",
                "actor_username": "actorUsername",
                "actor_role": "actorRole",
                "changed_fields": "changedFields",
                "created_at": "createdAt",
            },
        )


class UserUpdateRequest(BaseModel):
    displayName: str | None = None
    role: str | None = None
    status: str | None = None
    tenantId: str | None = None
    clientId: str | None = None
    note: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_source(cls, data: Any) -> Any:
        return _normalize_aliases(
            data,
            {
                "display_name": "displayName",
                "tenant_id": "tenantId",
                "client_id": "clientId",
            },
        )


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    expiresIn: int
    refreshToken: str | None = None
    role: str
    user: UserRead | None = None


class LoginRequest(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    password: str


class RefreshRequest(BaseModel):
    refreshToken: str


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    inviteCode: str
    displayName: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_source(cls, data: Any) -> Any:
        return _normalize_aliases(data, {"invite_code": "inviteCode", "display_name": "displayName"})


class LogoutRequest(BaseModel):
    refreshToken: str | None = None
    allSessions: bool = False


class UserSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    userId: str | None = None
    username: str | None = None
    email: str | None = None
    displayName: str | None = None
    status: str
    ipAddress: str | None = None
    userAgent: str | None = None
    expiresAt: datetime | None
    revokedAt: datetime | None = None
    lastSeenAt: datetime | None = None
    createdAt: datetime | None

    @model_validator(mode="before")
    @classmethod
    def normalize_source(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return _normalize_aliases(
                data,
                {
                    "user_id": "userId",
                    "display_name": "displayName",
                    "ip_address": "ipAddress",
                    "user_agent": "userAgent",
                    "expires_at": "expiresAt",
                    "revoked_at": "revokedAt",
                    "last_seen_at": "lastSeenAt",
                    "created_at": "createdAt",
                },
            )
        return {
            "id": _attr_or_key(data, "id"),
            "userId": _attr_or_key(data, "user_id"),
            "username": _attr_or_key(data, "username"),
            "email": _attr_or_key(data, "email"),
            "displayName": _attr_or_key(data, "display_name"),
            "status": _attr_or_key(data, "status"),
            "ipAddress": _attr_or_key(data, "ip_address"),
            "userAgent": _attr_or_key(data, "user_agent"),
            "expiresAt": _attr_or_key(data, "expires_at"),
            "revokedAt": _attr_or_key(data, "revoked_at"),
            "lastSeenAt": _attr_or_key(data, "last_seen_at"),
            "createdAt": _attr_or_key(data, "created_at"),
        }


class UserSessionListResponse(BaseModel):
    items: list[UserSessionRead]


class InviteCodeCreateRequest(BaseModel):
    role: str = "user"
    tenantId: str | None = None
    clientId: str | None = None
    maxUses: int = Field(default=1, ge=1, le=100)
    expiresAt: datetime | None = None
    note: str | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_source(cls, data: Any) -> Any:
        return _normalize_aliases(
            data,
            {
                "tenant_id": "tenantId",
                "client_id": "clientId",
                "max_uses": "maxUses",
                "expires_at": "expiresAt",
            },
        )


class InviteCodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    role: str
    tenantId: str | None = None
    clientId: str | None = None
    maxUses: int
    usedCount: int
    status: str
    expiresAt: datetime | None = None
    createdBy: str | None = None
    note: str | None = None
    metadata: dict[str, Any] | None = None
    createdAt: datetime | None
    updatedAt: datetime | None

    @model_validator(mode="before")
    @classmethod
    def normalize_source(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return _normalize_aliases(
                data,
                {
                    "tenant_id": "tenantId",
                    "client_id": "clientId",
                    "max_uses": "maxUses",
                    "used_count": "usedCount",
                    "expires_at": "expiresAt",
                    "created_by": "createdBy",
                    "extra_metadata": "metadata",
                    "created_at": "createdAt",
                    "updated_at": "updatedAt",
                },
            )
        return {
            "id": _attr_or_key(data, "id"),
            "code": _attr_or_key(data, "code"),
            "role": _attr_or_key(data, "role"),
            "tenantId": _attr_or_key(data, "tenant_id"),
            "clientId": _attr_or_key(data, "client_id"),
            "maxUses": _attr_or_key(data, "max_uses"),
            "usedCount": _attr_or_key(data, "used_count"),
            "status": _attr_or_key(data, "status"),
            "expiresAt": _attr_or_key(data, "expires_at"),
            "createdBy": _attr_or_key(data, "created_by"),
            "note": _attr_or_key(data, "note"),
            "metadata": _attr_or_key(data, "extra_metadata"),
            "createdAt": _attr_or_key(data, "created_at"),
            "updatedAt": _attr_or_key(data, "updated_at"),
        }


class InviteCodeListResponse(BaseModel):
    items: list[InviteCodeRead]


class UserListResponse(BaseModel):
    items: list[UserRead]


class AuthScopeTotals(BaseModel):
    users: int
    activeUsers: int
    adminUsers: int
    clientUsers: int
    unscopedClientUsers: int
    activeSessions: int
    activeInvites: int
    unscopedActiveInvites: int
    expiredActiveInvites: int


class AuthScopeRoleItem(BaseModel):
    role: str
    count: int
    activeCount: int


class AuthScopeTenantItem(BaseModel):
    tenantId: str | None = None
    clientId: str | None = None
    userCount: int
    activeUserCount: int
    clientUserCount: int
    activeSessionCount: int


class AuthScopeRiskItem(BaseModel):
    key: str
    title: str
    severity: str
    count: int
    detail: str


class AuthScopeChecklistItem(BaseModel):
    key: str
    title: str
    passed: bool
    detail: str
    action: str


class AuthScopeBusinessApiPolicyItem(BaseModel):
    key: str
    title: str
    detail: str
    enforced: bool


class AuthScopeRoleBoundaryItem(BaseModel):
    key: str
    title: str
    principal: str
    allowed: str
    blocked: str
    enforced: bool


class AuthScopeSummaryResponse(BaseModel):
    generatedAt: datetime
    releaseReady: bool = False
    blockingRiskCount: int = 0
    warningRiskCount: int = 0
    totals: AuthScopeTotals
    roles: list[AuthScopeRoleItem]
    tenants: list[AuthScopeTenantItem]
    risks: list[AuthScopeRiskItem]
    checklist: list[AuthScopeChecklistItem] = Field(default_factory=list)
    businessApiPolicy: list[AuthScopeBusinessApiPolicyItem] = Field(default_factory=list)
    roleBoundary: list[AuthScopeRoleBoundaryItem] = Field(default_factory=list)
