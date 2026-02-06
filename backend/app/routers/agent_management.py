"""Agent management endpoints (ComfyUI server sync)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.db import get_session
from app.deps.auth import require_admin
from app.models.agent_management import Agent, AgentAlert, AgentManifest, AgentTask, AgentTaskEvent
from app.schemas import agent_management as schemas
from app.services.agent_management import (
    agent_token_service,
    create_agent_task,
    ensure_agent_allowed,
    get_agent_or_404,
    push_task_to_agent,
    record_agent_alert,
    record_task_event,
    update_task_status,
)


agent_router = APIRouter(prefix="/api/agent", tags=["agent"])
admin_router = APIRouter(prefix="/api/admin/comfyui", dependencies=[Depends(require_admin)], tags=["admin-agent"])
bearer_scheme = HTTPBearer(auto_error=False)


def _document_bearer(_: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> None:
    """Attach bearer auth to OpenAPI without enforcing it here."""
    return None


@agent_router.get("/docs/agent-protocol", response_class=PlainTextResponse)
def get_agent_protocol() -> PlainTextResponse:
    """Return the current agent protocol markdown (auto-refreshes from repo)."""
    repo_root = Path(__file__).resolve().parents[3]
    doc_path = repo_root / "docs" / "comfyui" / "agent-management.md"
    try:
        content = doc_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        content = "# Agent protocol\n\nDocument not found in repository.\n"
    return PlainTextResponse(content, media_type="text/markdown; charset=utf-8")


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
        if token:
            return token
    raise HTTPException(status_code=401, detail="AGENT_TOKEN_REQUIRED")


def _require_agent_token(request: Request, allowed_scopes: set[str] | None = None) -> dict[str, Any]:
    token = _extract_bearer_token(request)
    payload = agent_token_service.decode_token(token)
    if allowed_scopes:
        scope = payload.get("scope")
        if scope not in allowed_scopes:
            raise HTTPException(status_code=403, detail="AGENT_TOKEN_SCOPE_INVALID")
    return payload


@agent_router.post("/auth/verify", response_model=schemas.AgentAuthVerifyResponse)
def verify_agent_token(payload: schemas.AgentAuthVerifyRequest) -> schemas.AgentAuthVerifyResponse:
    decoded = agent_token_service.decode_token(payload.token)
    agent_id = decoded.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=401, detail="AGENT_TOKEN_PAYLOAD_INVALID")
    if payload.agent_id and str(payload.agent_id) != str(agent_id):
        raise HTTPException(status_code=403, detail="AGENT_TOKEN_PAYLOAD_MISMATCH")
    token_task_id = decoded.get("task_id")
    if payload.task_id:
        if not token_task_id or str(payload.task_id) != str(token_task_id):
            raise HTTPException(status_code=403, detail="AGENT_TOKEN_PAYLOAD_MISMATCH")
    if payload.nonce:
        if str(payload.nonce) != str(decoded.get("nonce") or ""):
            raise HTTPException(status_code=403, detail="AGENT_TOKEN_PAYLOAD_MISMATCH")
    agent = get_agent_or_404(str(agent_id))
    ensure_agent_allowed(agent)
    task_id = token_task_id
    expires_at = None
    if task_id:
        with get_session() as session:
            task = session.get(AgentTask, str(task_id))
            if not task:
                raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
            if task.agent_id != agent.id:
                raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
            if task.expires_at and datetime.utcnow() > task.expires_at:
                raise HTTPException(status_code=409, detail="AGENT_TASK_EXPIRED")
            expires_at = task.expires_at
    return schemas.AgentAuthVerifyResponse(
        ok=True,
        agentId=agent.id,
        taskId=str(task_id) if task_id else None,
        expiresAt=expires_at,
        scope=decoded.get("scope"),
        policy={"allow": True},
    )


@agent_router.get("/manifests/{manifest_id}", response_model=schemas.AgentManifestRead)
def get_manifest(
    manifest_id: int, request: Request, _: None = Depends(_document_bearer)
) -> schemas.AgentManifestRead:
    payload = _require_agent_token(request, allowed_scopes={"task"})
    task_id = payload.get("task_id")
    if not task_id:
        raise HTTPException(status_code=401, detail="AGENT_TOKEN_PAYLOAD_INVALID")
    with get_session() as session:
        task = session.get(AgentTask, str(task_id))
        if not task:
            raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
        if task.expires_at and datetime.utcnow() > task.expires_at:
            raise HTTPException(status_code=409, detail="AGENT_TASK_EXPIRED")
        if task.manifest_id != manifest_id:
            raise HTTPException(status_code=403, detail="AGENT_MANIFEST_FORBIDDEN")
        manifest = session.get(AgentManifest, manifest_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="AGENT_MANIFEST_NOT_FOUND")
        return schemas.AgentManifestRead.model_validate(manifest)


@agent_router.post("/tasks/{task_id}/events", response_model=schemas.AgentTaskEventRead)
def report_task_event(
    task_id: str,
    payload: schemas.AgentTaskEventCreate,
    request: Request,
    _: None = Depends(_document_bearer),
) -> schemas.AgentTaskEventRead:
    decoded = _require_agent_token(request, allowed_scopes={"task"})
    if str(decoded.get("task_id")) != task_id:
        raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
    with get_session() as session:
        task = session.get(AgentTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
        if str(decoded.get("agent_id")) != task.agent_id:
            raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
        if task.expires_at and datetime.utcnow() > task.expires_at:
            raise HTTPException(status_code=409, detail="AGENT_TASK_EXPIRED")
    task = update_task_status(task_id=task_id, status="running")
    event_payload = payload.payload or {}
    if payload.step:
        event_payload["step"] = payload.step
    if payload.progress is not None:
        event_payload["progress"] = payload.progress
    event = record_task_event(task, level=payload.level, message=payload.message, payload=event_payload or None)
    return schemas.AgentTaskEventRead.model_validate(event)


@agent_router.post("/tasks/{task_id}/complete", response_model=schemas.AgentTaskRead)
def complete_task(
    task_id: str,
    body: schemas.AgentTaskCompleteRequest | None,
    request: Request,
    _: None = Depends(_document_bearer),
) -> schemas.AgentTaskRead:
    decoded = _require_agent_token(request, allowed_scopes={"task"})
    if str(decoded.get("task_id")) != task_id:
        raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
    with get_session() as session:
        task = session.get(AgentTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
        if str(decoded.get("agent_id")) != task.agent_id:
            raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
        if task.expires_at and datetime.utcnow() > task.expires_at:
            raise HTTPException(status_code=409, detail="AGENT_TASK_EXPIRED")
    payload = body.model_dump(by_alias=True, exclude_none=True) if body else {}
    task = update_task_status(task_id=task_id, status="success", result_payload=payload)
    return schemas.AgentTaskRead.model_validate(task)


@agent_router.post("/tasks/{task_id}/failed", response_model=schemas.AgentTaskRead)
def fail_task(
    task_id: str,
    body: schemas.AgentTaskFailedRequest | None,
    request: Request,
    _: None = Depends(_document_bearer),
) -> schemas.AgentTaskRead:
    decoded = _require_agent_token(request, allowed_scopes={"task"})
    if str(decoded.get("task_id")) != task_id:
        raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
    with get_session() as session:
        task = session.get(AgentTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
        if str(decoded.get("agent_id")) != task.agent_id:
            raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
        if task.expires_at and datetime.utcnow() > task.expires_at:
            raise HTTPException(status_code=409, detail="AGENT_TASK_EXPIRED")
    payload = body.model_dump(by_alias=True, exclude_none=True) if body else {}
    error_message = ""
    if payload:
        error_message = str(payload.get("errorCode") or payload.get("message") or payload.get("error") or "")
    task = update_task_status(task_id=task_id, status="failed", result_payload=payload, error_message=error_message)
    return schemas.AgentTaskRead.model_validate(task)


@agent_router.post("/agents/{agent_id}/heartbeat", response_model=schemas.AgentHeartbeatResponse)
def heartbeat(
    agent_id: str,
    payload: schemas.AgentHeartbeatRequest,
    request: Request,
    _: None = Depends(_document_bearer),
) -> schemas.AgentHeartbeatResponse:
    decoded = _require_agent_token(request, allowed_scopes={"agent", "task"})
    token_agent = decoded.get("agent_id")
    if token_agent and str(token_agent) != agent_id:
        raise HTTPException(status_code=403, detail="AGENT_NOT_ALLOWED")
    with get_session() as session:
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="AGENT_NOT_FOUND")
        ensure_agent_allowed(agent)
        now = datetime.utcnow()
        agent.last_seen_at = now
        agent.last_heartbeat_at = now
        metrics = payload.metrics or {}
        if payload.cpu is not None:
            metrics["cpu"] = payload.cpu
        if payload.mem is not None:
            metrics["mem"] = payload.mem
        if payload.disk_free_gb is not None:
            metrics["disk_free_gb"] = payload.disk_free_gb
        if payload.gpu is not None:
            metrics["gpu"] = payload.gpu
        if metrics:
            agent.metrics = metrics
        if payload.payload is not None:
            config = agent.config or {}
            config["heartbeat"] = payload.payload
            if payload.agent_version:
                config["agent_version"] = payload.agent_version
            if payload.comfyui_version:
                config["comfyui_version"] = payload.comfyui_version
            agent.config = config
        if payload.status:
            agent.status = payload.status
        session.add(agent)
        session.commit()
    return schemas.AgentHeartbeatResponse(status="ok", agentId=agent_id, receivedAt=now)


@agent_router.post("/agents/{agent_id}/alerts", response_model=schemas.AgentAlertRead)
def alert(
    agent_id: str,
    payload: schemas.AgentAlertCreate,
    request: Request,
    _: None = Depends(_document_bearer),
) -> schemas.AgentAlertRead:
    decoded = _require_agent_token(request, allowed_scopes={"agent", "task"})
    token_agent = decoded.get("agent_id")
    if token_agent and str(token_agent) != agent_id:
        raise HTTPException(status_code=403, detail="AGENT_NOT_ALLOWED")
    agent = get_agent_or_404(agent_id)
    ensure_agent_allowed(agent)
    record = record_agent_alert(
        agent_id=agent_id, alert_type=payload.alert_type, message=payload.message, payload=payload.payload
    )
    return schemas.AgentAlertRead.model_validate(record)


@admin_router.get("/agents", response_model=list[schemas.AgentRead])
def list_agents(status: str | None = None, role: str | None = None, limit: int = 50) -> list[schemas.AgentRead]:
    with get_session() as session:
        stmt = select(Agent)
        if status:
            stmt = stmt.where(Agent.status == status)
        if role:
            stmt = stmt.where(Agent.role == role)
        agents = session.execute(stmt.order_by(Agent.updated_at.desc()).limit(min(limit, 200))).scalars().all()
        return [schemas.AgentRead.model_validate(item) for item in agents]


@admin_router.post("/agents", response_model=schemas.AgentRead)
def create_agent(payload: schemas.AgentCreate) -> schemas.AgentRead:
    data = payload.model_dump(by_alias=False)
    with get_session() as session:
        if session.get(Agent, payload.id):
            raise HTTPException(status_code=409, detail="AGENT_ALREADY_EXISTS")
        agent = Agent(**data)
        session.add(agent)
        session.commit()
        session.refresh(agent)
        return schemas.AgentRead.model_validate(agent)


@admin_router.put("/agents/{agent_id}", response_model=schemas.AgentRead)
def update_agent(agent_id: str, payload: schemas.AgentUpdate) -> schemas.AgentRead:
    data = payload.model_dump(exclude_unset=True, by_alias=False)
    with get_session() as session:
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="AGENT_NOT_FOUND")
        for key, value in data.items():
            setattr(agent, key, value)
        session.add(agent)
        session.commit()
        session.refresh(agent)
        return schemas.AgentRead.model_validate(agent)


@admin_router.post("/agents/{agent_id}/token", response_model=schemas.AgentTokenIssueResponse)
def issue_agent_token(
    agent_id: str, payload: schemas.AgentTokenIssueRequest | None = None
) -> schemas.AgentTokenIssueResponse:
    agent = get_agent_or_404(agent_id)
    ensure_agent_allowed(agent)
    ttl_seconds = payload.ttl_seconds if payload and payload.ttl_seconds else None
    if ttl_seconds is None:
        ttl_seconds = int(agent_token_service.settings.agent_heartbeat_token_ttl)
    token = agent_token_service.issue_token(agent_id=agent_id, task_id=None, scope="agent", ttl_seconds=ttl_seconds)
    return schemas.AgentTokenIssueResponse(
        token=token.token,
        expiresAt=token.expires_at,
        scope="agent",
        agentId=agent_id,
    )


@admin_router.get("/alerts", response_model=list[schemas.AgentAlertRead])
def list_alerts(
    agent_id: str | None = None, alert_type: str | None = None, limit: int = 50
) -> list[schemas.AgentAlertRead]:
    with get_session() as session:
        stmt = select(AgentAlert)
        if agent_id:
            stmt = stmt.where(AgentAlert.agent_id == agent_id)
        if alert_type:
            stmt = stmt.where(AgentAlert.alert_type == alert_type)
        items = session.execute(stmt.order_by(AgentAlert.created_at.desc()).limit(min(limit, 200))).scalars().all()
        return [schemas.AgentAlertRead.model_validate(item) for item in items]


@admin_router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str) -> dict[str, str]:
    with get_session() as session:
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="AGENT_NOT_FOUND")
        session.delete(agent)
        session.commit()
        return {"status": "deleted"}


@admin_router.get("/manifests", response_model=list[schemas.AgentManifestRead])
def list_manifests(role: str | None = None, status: str | None = None, limit: int = 50) -> list[schemas.AgentManifestRead]:
    with get_session() as session:
        stmt = select(AgentManifest)
        if role:
            stmt = stmt.where(AgentManifest.role == role)
        if status:
            stmt = stmt.where(AgentManifest.status == status)
        items = session.execute(stmt.order_by(AgentManifest.updated_at.desc()).limit(min(limit, 200))).scalars().all()
        return [schemas.AgentManifestRead.model_validate(item) for item in items]


@admin_router.post("/manifests", response_model=schemas.AgentManifestRead)
def create_manifest(payload: schemas.AgentManifestCreate) -> schemas.AgentManifestRead:
    data = payload.model_dump(by_alias=False)
    with get_session() as session:
        manifest = AgentManifest(**data)
        session.add(manifest)
        session.commit()
        session.refresh(manifest)
        return schemas.AgentManifestRead.model_validate(manifest)


@admin_router.get("/manifests/{manifest_id}", response_model=schemas.AgentManifestRead)
def get_manifest_admin(manifest_id: int) -> schemas.AgentManifestRead:
    with get_session() as session:
        manifest = session.get(AgentManifest, manifest_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="AGENT_MANIFEST_NOT_FOUND")
        return schemas.AgentManifestRead.model_validate(manifest)


@admin_router.put("/manifests/{manifest_id}", response_model=schemas.AgentManifestRead)
def update_manifest(manifest_id: int, payload: schemas.AgentManifestUpdate) -> schemas.AgentManifestRead:
    data = payload.model_dump(exclude_unset=True, by_alias=False)
    with get_session() as session:
        manifest = session.get(AgentManifest, manifest_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="AGENT_MANIFEST_NOT_FOUND")
        for key, value in data.items():
            setattr(manifest, key, value)
        session.add(manifest)
        session.commit()
        session.refresh(manifest)
        return schemas.AgentManifestRead.model_validate(manifest)


@admin_router.get("/tasks", response_model=list[schemas.AgentTaskRead])
def list_tasks(agent_id: str | None = None, status: str | None = None, limit: int = 50) -> list[schemas.AgentTaskRead]:
    with get_session() as session:
        stmt = select(AgentTask)
        if agent_id:
            stmt = stmt.where(AgentTask.agent_id == agent_id)
        if status:
            stmt = stmt.where(AgentTask.status == status)
        items = session.execute(stmt.order_by(AgentTask.created_at.desc()).limit(min(limit, 200))).scalars().all()
        return [schemas.AgentTaskRead.model_validate(item) for item in items]


@admin_router.post("/tasks", response_model=schemas.AgentTaskRead)
def create_task(payload: schemas.AgentTaskCreate, push: bool = True) -> schemas.AgentTaskRead:
    with get_session() as session:
        agent = session.get(Agent, payload.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="AGENT_NOT_FOUND")
        ensure_agent_allowed(agent)
        manifest = session.get(AgentManifest, payload.manifest_id) if payload.manifest_id else None
        if payload.manifest_id and not manifest:
            raise HTTPException(status_code=404, detail="AGENT_MANIFEST_NOT_FOUND")
    task = create_agent_task(
        agent_id=payload.agent_id,
        manifest=manifest,
        manifest_url_override=payload.manifest_url,
        actions=payload.actions,
        expires_at=payload.expires_at,
        task_id=payload.task_id,
    )
    if push:
        push_task_to_agent(task)
        with get_session() as session:
            task = session.get(AgentTask, task.id) or task
    return schemas.AgentTaskRead.model_validate(task)


@admin_router.get("/tasks/{task_id}", response_model=schemas.AgentTaskRead)
def get_task(task_id: str) -> schemas.AgentTaskRead:
    with get_session() as session:
        task = session.get(AgentTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
        return schemas.AgentTaskRead.model_validate(task)


@admin_router.post("/tasks/{task_id}/push")
def push_task(task_id: str) -> dict[str, Any]:
    with get_session() as session:
        task = session.get(AgentTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
    return push_task_to_agent(task)


@admin_router.get("/tasks/{task_id}/events", response_model=list[schemas.AgentTaskEventRead])
def list_task_events(task_id: str, limit: int = 50) -> list[schemas.AgentTaskEventRead]:
    with get_session() as session:
        stmt = select(AgentTaskEvent).where(AgentTaskEvent.task_id == task_id).order_by(AgentTaskEvent.id.desc())
        items = session.execute(stmt.limit(min(limit, 200))).scalars().all()
        return [schemas.AgentTaskEventRead.model_validate(item) for item in items]
