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

    def list_users(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with get_session() as session:
            rows = (
                session.execute(select(User).order_by(User.created_at.desc()).limit(max(1, min(limit, 200))))
                .scalars()
                .all()
            )
            return [self._user_to_dict(row) for row in rows]

    def update_user(
        self,
        *,
        user_id: str,
        display_name: str | None = None,
        role: str | None = None,
        status: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        note: str | None = None,
        actor: User | None = None,
    ) -> dict[str, Any]:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            raise HTTPException(status_code=400, detail="USER_ID_REQUIRED")
        with get_session() as session:
            user = session.get(User, normalized_user_id)
            if not user:
                raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
            before = self._user_to_dict(user)
            next_role = self._normalize_role(role) if role is not None else user.role
            next_status = self._normalize_status(status) if status is not None else user.status
            actor_id = str(getattr(actor, "id", "") or "").strip()
            if actor_id and actor_id == user.id and (next_role != "admin" or next_status != "active"):
                raise HTTPException(status_code=409, detail="AUTH_SELF_LOCKOUT_FORBIDDEN")

            user.display_name = self._clean_text(display_name, max_len=128) if display_name is not None else user.display_name
            user.role = next_role
            user.status = next_status
            user.tenant_id = self._clean_text(tenant_id, max_len=64) if tenant_id is not None else user.tenant_id
            user.client_id = self._clean_text(client_id, max_len=64) if client_id is not None else user.client_id

            changed_fields = [
                field
                for field in ("displayName", "role", "status", "tenantId", "clientId")
                if before.get(field) != self._user_to_dict(user).get(field)
            ]
            if next_status != "active":
                now = datetime.utcnow()
                sessions = session.execute(
                    select(UserSession).where(UserSession.user_id == user.id, UserSession.status == "active")
                ).scalars().all()
                for row in sessions:
                    row.status = "revoked"
                    row.revoked_at = now
                    session.add(row)
                if sessions and "sessions" not in changed_fields:
                    changed_fields.append("sessions")

            after = self._user_to_dict(user)
            user.extra_metadata = self._with_admin_audit(
                user.extra_metadata,
                {
                    "action": "update_auth_user",
                    "actorUserId": actor_id or None,
                    "actorUsername": self._actor_username(actor),
                    "actorRole": str(getattr(actor, "role", "") or "").strip() or None if actor else None,
                    "note": self._clean_text(note, max_len=500),
                    "changedFields": changed_fields,
                    "before": {key: before.get(key) for key in ("displayName", "role", "status", "tenantId", "clientId")},
                    "after": {key: after.get(key) for key in ("displayName", "role", "status", "tenantId", "clientId")},
                    "createdAt": datetime.utcnow().isoformat(),
                },
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return self._user_to_dict(user)

    def scope_summary(self) -> dict[str, Any]:
        now = datetime.utcnow()
        with get_session() as session:
            users = list(session.execute(select(User)).scalars().all())
            sessions = list(session.execute(select(UserSession)).scalars().all())
            invites = list(session.execute(select(InviteCode)).scalars().all())

        active_users = [user for user in users if user.status == "active"]
        active_sessions = [row for row in sessions if row.status == "active" and row.expires_at > now]
        active_invites = [row for row in invites if row.status == "active"]
        expired_active_invites = [row for row in active_invites if row.expires_at and row.expires_at <= now]
        unscoped_active_invites = [row for row in active_invites if not row.tenant_id]
        client_users = [user for user in users if user.role == "client"]
        unscoped_client_users = [user for user in client_users if not user.tenant_id]

        role_groups: dict[str, list[User]] = {}
        for user in users:
            role_groups.setdefault(user.role or "user", []).append(user)

        tenant_groups: dict[tuple[str | None, str | None], list[User]] = {}
        for user in users:
            key = (user.tenant_id or None, user.client_id or None)
            tenant_groups.setdefault(key, []).append(user)
        active_session_user_ids = {row.user_id for row in active_sessions}

        risks = [
            {
                "key": "no_admin_user",
                "title": "没有管理员账号",
                "severity": "danger" if not any(user.role == "admin" and user.status == "active" for user in users) else "success",
                "count": 0 if any(user.role == "admin" and user.status == "active" for user in users) else 1,
                "detail": "至少保留一个可登录管理员，避免管理端无法维护账号。",
            },
            {
                "key": "unscoped_client_users",
                "title": "业务方账号未绑定",
                "severity": "warning" if unscoped_client_users else "success",
                "count": len(unscoped_client_users),
                "detail": "业务方账号应绑定业务方标识，便于后续隔离、限额和账单统计。",
            },
            {
                "key": "unscoped_active_invites",
                "title": "邀请码未绑定业务方",
                "severity": "warning" if unscoped_active_invites else "success",
                "count": len(unscoped_active_invites),
                "detail": "给业务方使用的邀请码建议提前绑定业务方和客户端，减少注册后再调整。",
            },
            {
                "key": "expired_active_invites",
                "title": "邀请码已过期但仍激活",
                "severity": "warning" if expired_active_invites else "success",
                "count": len(expired_active_invites),
                "detail": "过期的邀请码需要失效，避免页面状态和实际注册结果不一致。",
            },
        ]
        blocking_risks = [item for item in risks if item["severity"] == "danger" and item["count"] > 0]
        warning_risks = [item for item in risks if item["severity"] == "warning" and item["count"] > 0]
        checklist = [
            {
                "key": "admin_login_available",
                "title": "管理员可登录",
                "passed": not any(item["key"] == "no_admin_user" and item["count"] > 0 for item in risks),
                "detail": "至少保留一个 active 管理员账号。",
                "action": "如失败，先恢复或创建管理员账号。",
            },
            {
                "key": "client_users_scoped",
                "title": "业务方账号已绑定范围",
                "passed": len(unscoped_client_users) == 0,
                "detail": "业务方账号需要绑定业务方标识，后续才能做隔离、额度和账单统计。",
                "action": "到账号权限页给业务方账号补 tenantId/clientId。",
            },
            {
                "key": "active_invites_scoped",
                "title": "可用邀请码已绑定范围",
                "passed": len(unscoped_active_invites) == 0,
                "detail": "给业务方发的邀请码建议提前绑定业务方和客户端。",
                "action": "失效未绑定的邀请码，重新生成带范围的邀请码。",
            },
            {
                "key": "expired_invites_disabled",
                "title": "过期邀请码已失效",
                "passed": len(expired_active_invites) == 0,
                "detail": "页面显示可用的邀请码必须和实际注册结果一致。",
                "action": "失效过期邀请码，避免业务方拿到后注册失败。",
            },
            {
                "key": "sessions_auditable",
                "title": "登录会话可追踪",
                "passed": True,
                "detail": "当前管理端可查看活跃会话，并可踢出异常会话。",
                "action": "发现离职或异常登录时，直接踢出会话并停用账号。",
            },
        ]
        business_api_policy = [
            {
                "key": "client_user_bound_scope",
                "title": "业务方账号只能使用绑定范围",
                "detail": "业务方账号调用业务 API 时，系统会忽略外部伪造的业务方标识，强制使用账号绑定的 tenantId/clientId。",
                "enforced": True,
            },
            {
                "key": "unscoped_client_user_blocked",
                "title": "未绑定业务方的账号不能调用业务 API",
                "detail": "role=client 且缺少 tenantId 的账号会被拒绝，避免调用记录、额度和账单归属不清。",
                "enforced": True,
            },
            {
                "key": "admin_service_can_act_as_tenant",
                "title": "管理员和服务 Token 可代业务方发起任务",
                "detail": "Coze、巡检和后台任务仍可显式传入 tenantId/clientId，用于灰度、回归和代业务方排障。",
                "enforced": True,
            },
            {
                "key": "inactive_user_sessions_revoked",
                "title": "停用账号会同步踢出会话",
                "detail": "账号停用后原有刷新 Token 不再可用，避免停用账号继续访问业务接口。",
                "enforced": True,
            },
        ]
        role_boundary = [
            {
                "key": "admin_user",
                "title": "管理员账号",
                "principal": "管理端管理员",
                "allowed": "维护用户、会话、邀请码、业务版本、发布门禁，并可在巡检或排障时显式代业务方发起任务。",
                "blocked": "不能把自己降权或停用；不应作为业务方长期接入凭证。",
                "enforced": True,
            },
            {
                "key": "client_user",
                "title": "业务方账号",
                "principal": "业务接入方",
                "allowed": "只能在账号绑定的 tenantId/clientId 范围内提交业务 API 任务和查询结果。",
                "blocked": "不能伪造或越权传入其他业务方范围；未绑定 tenantId 时不能调用业务 API。",
                "enforced": True,
            },
            {
                "key": "service_token",
                "title": "服务 Token",
                "principal": "Coze、巡检脚本、后台任务",
                "allowed": "用于系统级调用、发布前巡检和代业务方排障，可显式携带 tenantId/clientId。",
                "blocked": "不能发给业务方当登录账号使用；不能绕过业务运行日志、结算和结果回填链路。",
                "enforced": True,
            },
            {
                "key": "coze_toolbox",
                "title": "Coze 工具箱",
                "principal": "Coze 工作流",
                "allowed": "只调用中台 toolbox 和业务 API，由中台统一路由、调度、回填和查询任务。",
                "blocked": "不能直连 ComfyUI、vendor-api-ops 或历史测试地址。",
                "enforced": True,
            },
        ]

        return {
            "generatedAt": now,
            "releaseReady": len(blocking_risks) == 0 and len(warning_risks) == 0,
            "blockingRiskCount": len(blocking_risks),
            "warningRiskCount": len(warning_risks),
            "totals": {
                "users": len(users),
                "activeUsers": len(active_users),
                "adminUsers": len([user for user in users if user.role == "admin"]),
                "clientUsers": len(client_users),
                "unscopedClientUsers": len(unscoped_client_users),
                "activeSessions": len(active_sessions),
                "activeInvites": len(active_invites),
                "unscopedActiveInvites": len(unscoped_active_invites),
                "expiredActiveInvites": len(expired_active_invites),
            },
            "roles": [
                {
                    "role": role,
                    "count": len(group),
                    "activeCount": len([user for user in group if user.status == "active"]),
                }
                for role, group in sorted(role_groups.items())
            ],
            "tenants": [
                {
                    "tenantId": tenant_id,
                    "clientId": client_id,
                    "userCount": len(group),
                    "activeUserCount": len([user for user in group if user.status == "active"]),
                    "clientUserCount": len([user for user in group if user.role == "client"]),
                    "activeSessionCount": len([user for user in group if user.id in active_session_user_ids]),
                }
                for (tenant_id, client_id), group in sorted(
                    tenant_groups.items(),
                    key=lambda item: ((item[0][0] or ""), (item[0][1] or "")),
                )
            ][:50],
            "risks": risks,
            "checklist": checklist,
            "businessApiPolicy": business_api_policy,
            "roleBoundary": role_boundary,
        }

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

    def _normalize_status(self, status: str | None) -> str:
        normalized = str(status or "active").strip().lower()
        if normalized not in {"active", "inactive", "disabled"}:
            raise HTTPException(status_code=400, detail="USER_STATUS_INVALID")
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

    def _user_to_dict(self, user: User) -> dict[str, Any]:
        metadata = user.extra_metadata if isinstance(user.extra_metadata, dict) else {}
        admin_audit = metadata.get("admin_audit", [])
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "status": user.status,
            "displayName": user.display_name,
            "tenantId": user.tenant_id,
            "clientId": user.client_id,
            "createdAt": user.created_at,
            "lastLoginAt": user.last_login_at,
            "adminAudit": admin_audit if isinstance(admin_audit, list) else [],
        }

    def _with_admin_audit(self, metadata: dict[str, Any] | None, entry: dict[str, Any]) -> dict[str, Any]:
        next_metadata = dict(metadata or {}) if isinstance(metadata, dict) else {}
        audit = next_metadata.get("admin_audit", [])
        if not isinstance(audit, list):
            audit = []
        audit.insert(0, entry)
        next_metadata["admin_audit"] = audit[:20]
        return next_metadata

    def _actor_username(self, user: User | None) -> str | None:
        if not user:
            return None
        return (
            getattr(user, "username", None)
            or getattr(user, "display_name", None)
            or getattr(user, "email", None)
            or getattr(user, "id", None)
        )

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
