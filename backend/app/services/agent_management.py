"""Agent management utilities for ComfyUI server sync."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import httpx
import jwt
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_session
from app.models.agent_management import (
    Agent,
    AgentAlert,
    AgentDesktopRelease,
    AgentEnrollCode,
    AgentManifest,
    AgentTask,
    AgentTaskEvent,
)


MAX_EVENT_MESSAGE_LENGTH = 4096


@dataclass(frozen=True)
class AgentToken:
    token: str
    expires_at: datetime
    nonce: str
    kid: str


class AgentTokenService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._secrets = self._parse_secrets(self.settings.agent_jwt_secrets)
        if not self._secrets:
            self._secrets = {self.settings.agent_jwt_default_kid: self.settings.jwt_secret_key}

    @staticmethod
    def _parse_secrets(raw: str) -> dict[str, str]:
        secrets: dict[str, str] = {}
        for item in (raw or "").split(","):
            entry = item.strip()
            if not entry:
                continue
            if ":" in entry:
                kid, secret = entry.split(":", 1)
                secrets[kid.strip()] = secret.strip()
            else:
                secrets["default"] = entry
        return secrets

    def _pick_secret(self, kid: str | None) -> tuple[str, str]:
        if kid and kid in self._secrets:
            return kid, self._secrets[kid]
        if kid and len(self._secrets) == 1:
            sole_kid = next(iter(self._secrets))
            return sole_kid, self._secrets[sole_kid]
        if kid:
            raise HTTPException(status_code=401, detail="AGENT_TOKEN_KID_INVALID")
        if len(self._secrets) == 1:
            sole_kid = next(iter(self._secrets))
            return sole_kid, self._secrets[sole_kid]
        raise HTTPException(status_code=401, detail="AGENT_TOKEN_KID_REQUIRED")

    def issue_token(self, *, agent_id: str, task_id: str | None, scope: str, ttl_seconds: int) -> AgentToken:
        kid, secret = self._pick_secret(self.settings.agent_jwt_default_kid)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        nonce = uuid4().hex
        payload = {
            "agent_id": agent_id,
            "task_id": task_id,
            "scope": scope,
            "nonce": nonce,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(payload, secret, algorithm="HS256", headers={"kid": kid})
        return AgentToken(token=token, expires_at=expires_at, nonce=nonce, kid=kid)

    def get_keyset(self) -> list[dict[str, str]]:
        return [
            {"kid": kid, "secret": secret, "status": "active"}
            for kid, secret in self._secrets.items()
            if kid and secret
        ]

    def decode_token(self, token: str, *, expected_scope: str | None = None) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:  # type: ignore[attr-defined]
            raise HTTPException(status_code=401, detail="AGENT_TOKEN_INVALID") from exc
        kid = header.get("kid")
        _, secret = self._pick_secret(kid)
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(status_code=401, detail="AGENT_TOKEN_EXPIRED") from exc
        except jwt.PyJWTError as exc:  # type: ignore[attr-defined]
            raise HTTPException(status_code=401, detail="AGENT_TOKEN_INVALID") from exc
        scope = payload.get("scope")
        if expected_scope and scope != expected_scope:
            raise HTTPException(status_code=403, detail="AGENT_TOKEN_SCOPE_INVALID")
        return payload


agent_token_service = AgentTokenService()


def _normalize_base_url(agent: Agent) -> str:
    raw = (agent.base_url or (agent.config or {}).get("baseUrl") or (agent.config or {}).get("base_url") or "").strip()
    return raw.rstrip("/")


def get_agent_or_404(agent_id: str) -> Agent:
    with get_session() as session:
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="AGENT_NOT_FOUND")
        return agent


def ensure_agent_allowed(agent: Agent) -> None:
    if not agent.allowed or (agent.status or "").lower() == "disabled":
        raise HTTPException(status_code=403, detail="AGENT_NOT_ALLOWED")


def resolve_manifest_url(manifest: AgentManifest | None) -> str | None:
    if not manifest:
        return None
    if manifest.download_url:
        return manifest.download_url
    settings = get_settings()
    base_url = (settings.agent_manifest_base_url or settings.podi_internal_base_url).rstrip("/")
    return f"{base_url}/api/agent/manifests/{manifest.id}"


def create_agent_task(
    *,
    agent_id: str,
    manifest: AgentManifest | None,
    manifest_url_override: str | None = None,
    actions: list[str] | None,
    expires_at: datetime | None,
    task_id: str | None = None,
) -> AgentTask:
    now = datetime.utcnow()
    task_id = task_id or f"agt_{now:%Y%m%d_%H%M%S}_{uuid4().hex[:8]}"
    settings = get_settings()
    if not expires_at:
        expires_at = now + timedelta(seconds=settings.agent_task_timeout_seconds)
    ttl_seconds = int(settings.agent_task_token_ttl)
    remaining = int((expires_at - now).total_seconds())
    if remaining > 0:
        ttl_seconds = min(ttl_seconds, remaining)
    token = agent_token_service.issue_token(
        agent_id=agent_id,
        task_id=task_id,
        scope="task",
        ttl_seconds=ttl_seconds,
    )
    manifest_url = manifest_url_override or resolve_manifest_url(manifest)
    task = AgentTask(
        id=task_id,
        agent_id=agent_id,
        manifest_id=manifest.id if manifest else None,
        manifest_url=manifest_url,
        actions=actions or [],
        status="pending",
        token_nonce=token.nonce,
        expires_at=expires_at,
        request_payload={
            "agent_id": agent_id,
            "manifest_url": manifest_url,
            "actions": actions or [],
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
        created_at=now,
        updated_at=now,
    )
    with get_session() as session:
        session.add(task)
        session.commit()
        session.refresh(task)
    return task


def _format_actions_payload(actions: list[str] | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(actions, dict):
        return actions
    if isinstance(actions, list):
        return {str(item).strip(): True for item in actions if str(item).strip()}
    return {}


def push_task_to_agent(task: AgentTask) -> dict[str, Any]:
    agent = get_agent_or_404(task.agent_id)
    ensure_agent_allowed(agent)
    base_url = _normalize_base_url(agent)
    if not base_url:
        raise HTTPException(status_code=400, detail="AGENT_BASE_URL_MISSING")
    settings = get_settings()
    ttl_seconds = int(settings.agent_task_token_ttl)
    if task.expires_at:
        remaining = int((task.expires_at - datetime.utcnow()).total_seconds())
        if remaining > 0:
            ttl_seconds = min(ttl_seconds, remaining)
    token = agent_token_service.issue_token(
        agent_id=task.agent_id,
        task_id=task.id,
        scope="task",
        ttl_seconds=ttl_seconds,
    )
    actions_payload = _format_actions_payload(task.actions)
    payload = {
        "task_id": task.id,
        "agent_id": task.agent_id,
        "manifest_url": task.manifest_url,
        "actions": actions_payload,
        "expires_at": task.expires_at.isoformat() if task.expires_at else None,
        "token": token.token,
        "nonce": token.nonce,
    }
    url = f"{base_url}/tasks"
    try:
        response = httpx.post(url, json=payload, timeout=15)
    except httpx.HTTPError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail="AGENT_PUSH_FAILED") from exc

    with get_session() as session:
        db_task = session.get(AgentTask, task.id)
        if db_task:
            db_task.pushed_at = datetime.utcnow()
            if response.status_code == 409:
                db_task.status = "pending"
                db_task.error_message = "AGENT_BUSY"
            elif response.status_code >= 400:
                db_task.status = "pending"
                db_task.error_message = f"AGENT_HTTP_{response.status_code}"
            else:
                db_task.status = "running"
                db_task.error_message = None
            session.add(db_task)
            session.commit()
            session.refresh(db_task)
            task = db_task

    return {
        "taskId": task.id,
        "agentId": task.agent_id,
        "status": task.status,
        "pushStatus": response.status_code,
        "tokenExpiresAt": token.expires_at.isoformat(),
    }


def record_task_event(task: AgentTask, *, level: str, message: str, payload: dict[str, Any] | None) -> AgentTaskEvent:
    clean_message = (message or "").strip()
    if len(clean_message) > MAX_EVENT_MESSAGE_LENGTH:
        clean_message = clean_message[:MAX_EVENT_MESSAGE_LENGTH]
    event = AgentTaskEvent(
        task_id=task.id,
        level=level or "info",
        message=clean_message,
        payload=payload or None,
        created_at=datetime.utcnow(),
    )
    with get_session() as session:
        session.add(event)
        session.commit()
        session.refresh(event)
    return event


def update_task_status(
    *,
    task_id: str,
    status: str,
    result_payload: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> AgentTask:
    with get_session() as session:
        task = session.get(AgentTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
        task.status = status
        now = datetime.utcnow()
        if status in {"running"} and not task.started_at:
            task.started_at = now
        if status in {"success", "failed", "rejected"}:
            task.finished_at = now
        if result_payload is not None:
            task.result_payload = result_payload
        if error_message is not None:
            task.error_message = error_message
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def record_agent_alert(agent_id: str, *, alert_type: str, message: str, payload: dict[str, Any] | None) -> AgentAlert:
    alert = AgentAlert(
        agent_id=agent_id,
        alert_type=alert_type,
        message=message,
        payload=payload or None,
        created_at=datetime.utcnow(),
    )
    with get_session() as session:
        session.add(alert)
        session.commit()
        session.refresh(alert)
    return alert


def list_recent_tasks(agent_id: str | None = None, limit: int = 20) -> list[AgentTask]:
    with get_session() as session:
        stmt = select(AgentTask).order_by(AgentTask.created_at.desc()).limit(limit)
        if agent_id:
            stmt = stmt.where(AgentTask.agent_id == agent_id)
        return session.execute(stmt).scalars().all()


def issue_enroll_code(
    *,
    role: str,
    ttl_seconds: int,
    note: str | None = None,
    max_uses: int = 1,
    created_by: str | None = None,
) -> AgentEnrollCode:
    now = datetime.utcnow()
    expire_at = now + timedelta(seconds=max(60, int(ttl_seconds)))
    token = f"enroll_{uuid4().hex}{uuid4().hex[:8]}"
    code = AgentEnrollCode(
        code=token,
        role=(role or "full").strip() or "full",
        status="active",
        note=(note or "").strip() or None,
        max_uses=max(1, int(max_uses or 1)),
        used_count=0,
        expires_at=expire_at,
        created_by=(created_by or "").strip() or None,
        created_at=now,
        updated_at=now,
    )
    with get_session() as session:
        session.add(code)
        session.commit()
        session.refresh(code)
        return code


def exchange_enroll_code(
    *,
    enroll_code: str,
    machine_name: str | None = None,
    base_url: str | None = None,
    host: str | None = None,
    preferred_agent_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[Agent, AgentEnrollCode]:
    code_text = (enroll_code or "").strip()
    if not code_text:
        raise HTTPException(status_code=400, detail="AGENT_ENROLL_CODE_REQUIRED")
    with get_session() as session:
        code = session.execute(select(AgentEnrollCode).where(AgentEnrollCode.code == code_text)).scalar_one_or_none()
        if not code:
            raise HTTPException(status_code=404, detail="AGENT_ENROLL_CODE_NOT_FOUND")
        if code.status != "active":
            raise HTTPException(status_code=409, detail="AGENT_ENROLL_CODE_INACTIVE")
        now = datetime.utcnow()
        if code.expires_at and now > code.expires_at:
            code.status = "expired"
            session.add(code)
            session.commit()
            raise HTTPException(status_code=409, detail="AGENT_ENROLL_CODE_EXPIRED")
        if code.used_count >= max(1, int(code.max_uses or 1)):
            code.status = "used"
            session.add(code)
            session.commit()
            raise HTTPException(status_code=409, detail="AGENT_ENROLL_CODE_USED")

        role = (code.role or "full").strip() or "full"
        agent = _upsert_agent_registration(
            session=session,
            role=role,
            machine_name=machine_name,
            base_url=base_url,
            host=host,
            preferred_agent_id=preferred_agent_id,
            payload={
                "enrollCode": code.code,
                "payload": payload or {},
            },
            now=now,
        )

        code.used_count = int(code.used_count or 0) + 1
        code.used_at = now
        code.used_by_agent_id = agent.id
        if code.used_count >= max(1, int(code.max_uses or 1)):
            code.status = "used"
        session.add(agent)
        session.add(code)
        session.commit()
        session.refresh(agent)
        session.refresh(code)
        return agent, code


def _upsert_agent_registration(
    *,
    session,
    role: str,
    machine_name: str | None,
    base_url: str | None,
    host: str | None,
    preferred_agent_id: str | None,
    payload: dict[str, Any] | None,
    now: datetime,
) -> Agent:
    target_agent_id = (preferred_agent_id or "").strip()
    agent = session.get(Agent, target_agent_id) if target_agent_id else None
    if agent is None:
        suffix = uuid4().hex[:10]
        target_agent_id = target_agent_id or f"desktop_{role}_{suffix}"
        agent = Agent(
            id=target_agent_id,
            name=(machine_name or target_agent_id).strip()[:128],
            role=role,
            host=(host or machine_name or "").strip()[:128] or None,
            base_url=(base_url or "").strip() or None,
            status="active",
            allowed=True,
            config={},
            created_at=now,
            updated_at=now,
        )
    else:
        if not agent.role:
            agent.role = role
        if base_url:
            agent.base_url = base_url.strip()
        if host:
            agent.host = host.strip()[:128]
        if machine_name and not agent.name:
            agent.name = machine_name.strip()[:128]
        agent.allowed = True if agent.allowed is None else agent.allowed
        agent.status = agent.status or "active"
        agent.updated_at = now

    cfg = agent.config if isinstance(agent.config, dict) else {}
    cfg["bootstrap"] = {
        "last_enrolled_at": now.isoformat() + "Z",
        "machine_name": (machine_name or "").strip() or None,
        "payload": payload or None,
    }
    agent.config = cfg
    return agent


def auto_exchange_install_key(
    *,
    role: str,
    machine_name: str | None,
    base_url: str | None,
    host: str | None,
    preferred_agent_id: str | None,
    payload: dict[str, Any] | None,
) -> Agent:
    now = datetime.utcnow()
    normalized_role = (role or "full").strip() or "full"
    with get_session() as session:
        agent = _upsert_agent_registration(
            session=session,
            role=normalized_role,
            machine_name=machine_name,
            base_url=base_url,
            host=host,
            preferred_agent_id=preferred_agent_id,
            payload=payload,
            now=now,
        )
        session.add(agent)
        session.commit()
        session.refresh(agent)
        return agent


def list_desktop_releases(
    *,
    channel: str | None = None,
    os_type: str | None = None,
    arch: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[AgentDesktopRelease]:
    with get_session() as session:
        stmt = select(AgentDesktopRelease)
        if channel:
            stmt = stmt.where(AgentDesktopRelease.channel == channel)
        if os_type:
            stmt = stmt.where(AgentDesktopRelease.os_type == os_type)
        if arch:
            stmt = stmt.where(AgentDesktopRelease.arch == arch)
        if status:
            stmt = stmt.where(AgentDesktopRelease.status == status)
        stmt = stmt.order_by(AgentDesktopRelease.updated_at.desc()).limit(min(200, max(1, limit)))
        return session.execute(stmt).scalars().all()
