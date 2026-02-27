"""Agent management endpoints (ComfyUI server sync)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_session
from app.deps.auth import require_admin
from app.models.agent_management import (
    Agent,
    AgentAlert,
    AgentDesktopRelease,
    AgentEnrollCode,
    AgentManifest,
    AgentTask,
    AgentTaskEvent,
    ComfyuiRepairJob,
    ComfyuiRepairJobItem,
    ComfyuiRuntimePolicy,
)
from app.models.integration import AbilityTask
from app.schemas import agent_management as schemas
from app.services.agent_management import (
    auto_exchange_install_key,
    agent_token_service,
    create_agent_task,
    ensure_agent_allowed,
    exchange_enroll_code,
    get_agent_or_404,
    issue_enroll_code,
    list_desktop_releases,
    push_task_to_agent,
    record_agent_alert,
    record_task_event,
    update_task_status,
)
from app.services.task_status_contract import derive_agent_task_status


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


def _desktop_release_storage_dir() -> Path:
    settings = get_settings()
    raw = (settings.desktop_release_storage_dir or "runtime/desktop_releases").strip()
    base = Path(raw)
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[2] / raw
    base.mkdir(parents=True, exist_ok=True)
    return base


def _sanitize_desktop_release_filename(file_name: str) -> str:
    cleaned = "".join(ch for ch in file_name.strip() if ch.isalnum() or ch in ("-", "_", "."))
    if not cleaned:
        cleaned = f"podi-desktop-{uuid4().hex[:12]}.exe"
    if not cleaned.lower().endswith(".exe"):
        cleaned = f"{cleaned}.exe"
    return cleaned


def _resolve_desktop_release_base_url(request: Request) -> str:
    settings = get_settings()
    preferred = (settings.agent_manifest_base_url or "").strip().rstrip("/")
    if preferred:
        return preferred
    return str(request.base_url).rstrip("/")


@agent_router.get("/bootstrap/releases/files/{file_name}")
def download_desktop_release_file(file_name: str) -> FileResponse:
    safe_name = _sanitize_desktop_release_filename(file_name)
    if safe_name != file_name:
        raise HTTPException(status_code=404, detail="AGENT_DESKTOP_RELEASE_FILE_NOT_FOUND")
    file_path = _desktop_release_storage_dir() / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="AGENT_DESKTOP_RELEASE_FILE_NOT_FOUND")
    return FileResponse(path=file_path, filename=file_path.name, media_type="application/octet-stream")


@agent_router.post("/bootstrap/exchange", response_model=schemas.AgentBootstrapExchangeResponse)
def bootstrap_exchange(payload: schemas.AgentBootstrapExchangeRequest) -> schemas.AgentBootstrapExchangeResponse:
    settings = get_settings()
    ttl_seconds = int(settings.agent_heartbeat_token_ttl)
    agent, _code = exchange_enroll_code(
        enroll_code=payload.enroll_code,
        machine_name=payload.machine_name,
        base_url=payload.base_url,
        host=payload.host,
        preferred_agent_id=payload.preferred_agent_id,
        payload={
            "role": payload.role,
            "agentVersion": payload.agent_version,
            "comfyuiVersion": payload.comfyui_version,
            "extra": payload.payload or {},
        },
    )
    token = agent_token_service.issue_token(
        agent_id=agent.id,
        task_id=None,
        scope="agent",
        ttl_seconds=ttl_seconds,
    )
    return schemas.AgentBootstrapExchangeResponse(
        agentId=agent.id,
        role=agent.role or "full",
        centerUrl=_resolve_center_url(),
        agentToken=token.token,
        agentTokenExpiresAt=token.expires_at,
        heartbeatIntervalSec=max(10, int(settings.agent_bootstrap_heartbeat_interval)),
        jwtKeys=[schemas.AgentBootstrapKeyEntry.model_validate(item) for item in agent_token_service.get_keyset()],
    )


@agent_router.post("/bootstrap/auto-exchange", response_model=schemas.AgentBootstrapExchangeResponse)
def bootstrap_auto_exchange(payload: schemas.AgentBootstrapAutoExchangeRequest) -> schemas.AgentBootstrapExchangeResponse:
    settings = get_settings()
    expected = (settings.agent_bootstrap_install_key or "").strip()
    install_key = (payload.install_key or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="AGENT_BOOTSTRAP_INSTALL_KEY_NOT_CONFIGURED")
    if not install_key:
        raise HTTPException(status_code=400, detail="AGENT_BOOTSTRAP_INSTALL_KEY_REQUIRED")
    if install_key != expected:
        raise HTTPException(status_code=403, detail="AGENT_BOOTSTRAP_INSTALL_KEY_INVALID")

    agent = auto_exchange_install_key(
        role=payload.role,
        machine_name=payload.machine_name,
        base_url=payload.base_url,
        host=payload.host,
        preferred_agent_id=payload.preferred_agent_id,
        payload={
            "agentVersion": payload.agent_version,
            "comfyuiVersion": payload.comfyui_version,
            "payload": payload.payload or {},
            "auto": True,
        },
    )
    token = agent_token_service.issue_token(
        agent_id=agent.id,
        task_id=None,
        scope="agent",
        ttl_seconds=int(settings.agent_heartbeat_token_ttl),
    )
    return schemas.AgentBootstrapExchangeResponse(
        agentId=agent.id,
        role=agent.role or "full",
        centerUrl=_resolve_center_url(),
        agentToken=token.token,
        agentTokenExpiresAt=token.expires_at,
        heartbeatIntervalSec=max(10, int(settings.agent_bootstrap_heartbeat_interval)),
        jwtKeys=[schemas.AgentBootstrapKeyEntry.model_validate(item) for item in agent_token_service.get_keyset()],
    )


@agent_router.post("/bootstrap/refresh-keys", response_model=schemas.AgentBootstrapRefreshKeysResponse)
def bootstrap_refresh_keys(
    request: Request,
    _: None = Depends(_document_bearer),
) -> schemas.AgentBootstrapRefreshKeysResponse:
    _require_agent_token(request, allowed_scopes={"agent", "task"})
    return schemas.AgentBootstrapRefreshKeysResponse(
        centerUrl=_resolve_center_url(),
        jwtKeys=[schemas.AgentBootstrapKeyEntry.model_validate(item) for item in agent_token_service.get_keyset()],
        refreshedAt=datetime.utcnow(),
    )


@agent_router.get("/bootstrap/releases", response_model=list[schemas.AgentDesktopReleaseRead])
def bootstrap_list_desktop_releases(
    request: Request,
    channel: str | None = "stable",
    os_type: str = "windows",
    arch: str = "x64",
    status: str = "active",
    limit: int = 20,
    _: None = Depends(_document_bearer),
) -> list[schemas.AgentDesktopReleaseRead]:
    _require_agent_token(request, allowed_scopes={"agent", "task"})
    items = list_desktop_releases(
        channel=channel,
        os_type=os_type,
        arch=arch,
        status=status,
        limit=limit,
    )
    return [schemas.AgentDesktopReleaseRead.model_validate(item) for item in items]


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
        if token:
            return token
    raise HTTPException(status_code=401, detail="AGENT_TOKEN_REQUIRED")


def _is_debug_token(token: str) -> bool:
    raw = (get_settings().agent_debug_tokens or "").strip()
    if not raw or not token:
        return False
    for entry in raw.split(","):
        if token == entry.strip():
            return True
    return False


def _require_agent_token(request: Request, allowed_scopes: set[str] | None = None) -> dict[str, Any]:
    token = _extract_bearer_token(request)
    if _is_debug_token(token):
        return {"scope": "debug", "agent_id": None, "task_id": None, "debug": True}
    payload = agent_token_service.decode_token(token)
    if allowed_scopes:
        scope = payload.get("scope")
        if scope not in allowed_scopes:
            raise HTTPException(status_code=403, detail="AGENT_TOKEN_SCOPE_INVALID")
    return payload


def _with_agent_task_stage(task: AgentTask) -> AgentTask:
    stage = derive_agent_task_status(
        status=task.status,
        pushed_at=task.pushed_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        error_message=task.error_message,
    )
    setattr(task, "submit_status", stage.submit_status)
    setattr(task, "callback_status", stage.callback_status)
    setattr(task, "final_status", stage.final_status)
    setattr(task, "error_code", stage.error_code)
    return task


def _resolve_center_url() -> str:
    settings = get_settings()
    return (settings.agent_manifest_base_url or settings.podi_internal_base_url or "").rstrip("/")


def _normalize_manifest_collection(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    normalized: list[str] = []
    for item in items:
        if isinstance(item, dict):
            key = item.get("name") or item.get("file_name") or item.get("fileName") or item.get("repo")
            if key:
                normalized.append(str(key).strip())
                continue
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
    return sorted({v for v in normalized if v})


def _extract_agent_snapshot(agent: Agent) -> dict[str, Any]:
    config = agent.config if isinstance(agent.config, dict) else {}
    snapshot_keys = ("manifest_snapshot", "snapshot", "inventory")
    for key in snapshot_keys:
        value = config.get(key)
        if isinstance(value, dict):
            return value
    heartbeat_payload = config.get("heartbeat")
    if isinstance(heartbeat_payload, dict):
        for key in snapshot_keys:
            value = heartbeat_payload.get(key)
            if isinstance(value, dict):
                return value
    return {}


def _build_collection_drift(expected: list[str], reported: list[str]) -> schemas.AgentManifestDriftCollection:
    expected_set = {item for item in expected if item}
    reported_set = {item for item in reported if item}
    return schemas.AgentManifestDriftCollection(
        expected=sorted(expected_set),
        reported=sorted(reported_set),
        missing=sorted(expected_set - reported_set),
        extra=sorted(reported_set - expected_set),
    )


def _build_manifest_drift_response(manifest: AgentManifest, agent: Agent) -> schemas.AgentManifestDriftResponse:
    content = manifest.content if isinstance(manifest.content, dict) else {}
    snapshot = _extract_agent_snapshot(agent)
    expected_models = _normalize_manifest_collection(content.get("models"))
    expected_plugins = _normalize_manifest_collection(content.get("plugins"))
    expected_workflows = _normalize_manifest_collection(content.get("workflows"))

    reported_models = _normalize_manifest_collection(snapshot.get("models"))
    reported_plugins = _normalize_manifest_collection(snapshot.get("plugins"))
    reported_workflows = _normalize_manifest_collection(snapshot.get("workflows"))

    expected_comfyui = content.get("comfyui") if isinstance(content.get("comfyui"), dict) else {}
    reported_comfyui = snapshot.get("comfyui") if isinstance(snapshot.get("comfyui"), dict) else {}
    expected_commit = str(expected_comfyui.get("commit") or "").strip() or None
    reported_commit = str(
        reported_comfyui.get("commit")
        or (agent.config or {}).get("comfyui_version")
        or ""
    ).strip() or None
    return schemas.AgentManifestDriftResponse(
        manifest_id=manifest.id,
        manifest_version=manifest.version,
        agent_id=agent.id,
        agent_last_manifest_version=agent.last_manifest_version,
        same_version=bool(agent.last_manifest_version and agent.last_manifest_version == manifest.version),
        has_snapshot=bool(snapshot),
        comfyui={
            "expected_commit": expected_commit,
            "reported_commit": reported_commit,
            "matched": bool(expected_commit and reported_commit and expected_commit == reported_commit),
        },
        models=_build_collection_drift(expected_models, reported_models),
        plugins=_build_collection_drift(expected_plugins, reported_plugins),
        workflows=_build_collection_drift(expected_workflows, reported_workflows),
    )


def _compute_repair_actions(drift: schemas.AgentManifestDriftResponse) -> tuple[list[str], dict[str, list[str]]]:
    actions: list[str] = []
    missing_items = {
        "models": drift.models.missing,
        "plugins": drift.plugins.missing,
        "workflows": drift.workflows.missing,
    }
    if drift.models.missing:
        actions.append("sync_models")
    if drift.plugins.missing:
        actions.append("sync_plugins")
    if drift.workflows.missing:
        actions.append("sync_workflows")
    comfyui = drift.comfyui if isinstance(drift.comfyui, dict) else {}
    expected_commit = str(comfyui.get("expected_commit") or "").strip()
    reported_commit = str(comfyui.get("reported_commit") or "").strip()
    if expected_commit and reported_commit and expected_commit != reported_commit:
        actions.append("sync_comfyui")
    return sorted({item for item in actions if item}), missing_items


def _sync_repair_job_item_from_task(item: ComfyuiRepairJobItem, task: AgentTask | None) -> None:
    if not task:
        item.status = "failed"
        item.submit_status = "submit_failed"
        item.callback_status = "failed"
        item.final_status = "failed"
        item.error_code = item.error_code or "AGENT_TASK_NOT_FOUND"
        item.error_message = item.error_message or "关联任务不存在或已被删除"
        return
    stage = derive_agent_task_status(
        status=task.status,
        pushed_at=task.pushed_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        error_message=task.error_message,
    )
    item.submit_status = stage.submit_status
    item.callback_status = stage.callback_status
    item.final_status = stage.final_status
    item.error_code = stage.error_code
    item.error_message = task.error_message
    result_payload = task.result_payload if isinstance(task.result_payload, dict) else {}
    failed_items = result_payload.get("failedItems") or result_payload.get("failed_items")
    if isinstance(failed_items, dict):
        item.failed_items = failed_items
    if stage.final_status in {"success", "failed", "rejected", "canceled"}:
        item.status = stage.final_status
    elif stage.callback_status in {"running"}:
        item.status = "running"
    else:
        item.status = "pending"


def _refresh_repair_job_state(session, job: ComfyuiRepairJob) -> ComfyuiRepairJob:
    items = (
        session.execute(
            select(ComfyuiRepairJobItem)
            .where(ComfyuiRepairJobItem.repair_job_id == job.id)
            .order_by(ComfyuiRepairJobItem.id.asc())
        )
        .scalars()
        .all()
    )
    submitted = 0
    succeeded = 0
    failed = 0
    skipped = 0
    for item in items:
        if not item.task_id:
            if item.status == "failed" or item.final_status in {"failed", "rejected", "canceled"}:
                failed += 1
            else:
                item.status = "skipped"
                item.final_status = item.final_status or "success"
                skipped += 1
            session.add(item)
            continue
        submitted += 1
        task = session.get(AgentTask, item.task_id)
        _sync_repair_job_item_from_task(item, task)
        if item.final_status in {"success"}:
            succeeded += 1
        elif item.final_status in {"failed", "rejected", "canceled"}:
            failed += 1
        session.add(item)

    job.requested_agent_count = len(items)
    job.submitted_task_count = submitted
    job.succeeded_task_count = succeeded
    job.failed_task_count = failed
    job.skipped_task_count = skipped

    if submitted == 0 and skipped == len(items):
        job.status = "succeeded"
    elif submitted > 0 and succeeded + failed >= submitted:
        if failed and succeeded:
            job.status = "partial"
        elif failed:
            job.status = "failed"
        else:
            job.status = "succeeded"
    elif failed > 0 and submitted == 0:
        job.status = "failed"
    else:
        job.status = "running"
    job.result_payload = {
        "submitted": submitted,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
    }
    session.add(job)
    return job


def _serialize_repair_job(session, job: ComfyuiRepairJob) -> schemas.AgentRepairJobRead:
    job = _refresh_repair_job_state(session, job)
    session.commit()
    items = (
        session.execute(
            select(ComfyuiRepairJobItem)
            .where(ComfyuiRepairJobItem.repair_job_id == job.id)
            .order_by(ComfyuiRepairJobItem.id.asc())
        )
        .scalars()
        .all()
    )
    return schemas.AgentRepairJobRead(
        id=job.id,
        manifestId=job.manifest_id,
        mode=job.mode,
        status=job.status,
        requestedAgentCount=job.requested_agent_count,
        submittedTaskCount=job.submitted_task_count,
        succeededTaskCount=job.succeeded_task_count,
        failedTaskCount=job.failed_task_count,
        skippedTaskCount=job.skipped_task_count,
        createdBy=job.created_by,
        errorMessage=job.error_message,
        createdAt=job.created_at,
        updatedAt=job.updated_at,
        resultPayload=job.result_payload if isinstance(job.result_payload, dict) else None,
        items=[
            schemas.AgentRepairJobItemRead(
                id=item.id,
                agentId=item.agent_id,
                taskId=item.task_id,
                status=item.status,
                submitStatus=item.submit_status,
                callbackStatus=item.callback_status,
                finalStatus=item.final_status,
                actions=list(item.actions or []),
                missingItems=item.missing_items if isinstance(item.missing_items, dict) else {},
                failedItems=item.failed_items if isinstance(item.failed_items, dict) else None,
                errorCode=item.error_code,
                errorMessage=item.error_message,
                updatedAt=item.updated_at,
            )
            for item in items
        ],
    )


@agent_router.post("/auth/verify", response_model=schemas.AgentAuthVerifyResponse)
def verify_agent_token(payload: schemas.AgentAuthVerifyRequest) -> schemas.AgentAuthVerifyResponse:
    if _is_debug_token(payload.token):
        return schemas.AgentAuthVerifyResponse(
            ok=True,
            agentId=str(payload.agent_id or "debug"),
            taskId=str(payload.task_id) if payload.task_id else None,
            expiresAt=None,
            scope="debug",
            policy={"allow": True},
        )
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
    if payload.get("debug"):
        with get_session() as session:
            manifest = session.get(AgentManifest, manifest_id)
            if not manifest:
                raise HTTPException(status_code=404, detail="AGENT_MANIFEST_NOT_FOUND")
            return schemas.AgentManifestRead.model_validate(manifest)
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
    if not decoded.get("debug") and str(decoded.get("task_id")) != task_id:
        raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
    with get_session() as session:
        task = session.get(AgentTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
        if not decoded.get("debug") and str(decoded.get("agent_id")) != task.agent_id:
            raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
        if task.expires_at and datetime.utcnow() > task.expires_at:
            raise HTTPException(status_code=409, detail="AGENT_TASK_EXPIRED")
    task = update_task_status(task_id=task_id, status="running")
    event_payload = payload.payload or {}
    if payload.step:
        event_payload["step"] = payload.step
    if payload.stage:
        event_payload["stage"] = payload.stage
    if payload.provider:
        event_payload["provider"] = payload.provider
    if payload.node_id:
        event_payload["nodeId"] = payload.node_id
    if payload.retry_count is not None:
        event_payload["retryCount"] = payload.retry_count
    if payload.trace_id:
        event_payload["traceId"] = payload.trace_id
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
    if not decoded.get("debug") and str(decoded.get("task_id")) != task_id:
        raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
    with get_session() as session:
        task = session.get(AgentTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
        if not decoded.get("debug") and str(decoded.get("agent_id")) != task.agent_id:
            raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
        if task.expires_at and datetime.utcnow() > task.expires_at:
            raise HTTPException(status_code=409, detail="AGENT_TASK_EXPIRED")
    payload = body.model_dump(by_alias=True, exclude_none=True) if body else {}
    task = update_task_status(task_id=task_id, status="success", result_payload=payload)
    return schemas.AgentTaskRead.model_validate(_with_agent_task_stage(task))


@agent_router.post("/tasks/{task_id}/failed", response_model=schemas.AgentTaskRead)
def fail_task(
    task_id: str,
    body: schemas.AgentTaskFailedRequest | None,
    request: Request,
    _: None = Depends(_document_bearer),
) -> schemas.AgentTaskRead:
    decoded = _require_agent_token(request, allowed_scopes={"task"})
    if not decoded.get("debug") and str(decoded.get("task_id")) != task_id:
        raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
    with get_session() as session:
        task = session.get(AgentTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
        if not decoded.get("debug") and str(decoded.get("agent_id")) != task.agent_id:
            raise HTTPException(status_code=403, detail="AGENT_TASK_FORBIDDEN")
        if task.expires_at and datetime.utcnow() > task.expires_at:
            raise HTTPException(status_code=409, detail="AGENT_TASK_EXPIRED")
    payload = body.model_dump(by_alias=True, exclude_none=True) if body else {}
    error_message = ""
    if payload:
        error_message = str(payload.get("errorCode") or payload.get("message") or payload.get("error") or "")
    task = update_task_status(task_id=task_id, status="failed", result_payload=payload, error_message=error_message)
    return schemas.AgentTaskRead.model_validate(_with_agent_task_stage(task))


@agent_router.post("/agents/{agent_id}/heartbeat", response_model=schemas.AgentHeartbeatResponse)
def heartbeat(
    agent_id: str,
    payload: schemas.AgentHeartbeatRequest,
    request: Request,
    _: None = Depends(_document_bearer),
) -> schemas.AgentHeartbeatResponse:
    decoded = _require_agent_token(request, allowed_scopes={"agent", "task"})
    token_agent = decoded.get("agent_id")
    if not decoded.get("debug") and token_agent and str(token_agent) != agent_id:
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
        config = agent.config or {}
        if payload.payload is not None:
            config["heartbeat"] = payload.payload
        if payload.agent_version:
            config["agent_version"] = payload.agent_version
        if payload.comfyui_version:
            config["comfyui_version"] = payload.comfyui_version
        if config:
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
    if not decoded.get("debug") and token_agent and str(token_agent) != agent_id:
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


@admin_router.post("/agents/enroll-codes", response_model=schemas.AgentEnrollCodeRead)
def create_enroll_code(payload: schemas.AgentEnrollCodeCreateRequest) -> schemas.AgentEnrollCodeRead:
    ttl_seconds = payload.ttl_seconds if payload.ttl_seconds else int(get_settings().agent_enroll_code_ttl_seconds)
    code = issue_enroll_code(
        role=payload.role,
        ttl_seconds=ttl_seconds,
        note=payload.note,
        max_uses=payload.max_uses,
        created_by="admin",
    )
    return schemas.AgentEnrollCodeRead.model_validate(code)


@admin_router.get("/agents/enroll-codes", response_model=list[schemas.AgentEnrollCodeRead])
def list_enroll_codes(
    status: str | None = None,
    role: str | None = None,
    limit: int = 50,
) -> list[schemas.AgentEnrollCodeRead]:
    with get_session() as session:
        stmt = select(AgentEnrollCode)
        if status:
            stmt = stmt.where(AgentEnrollCode.status == status)
        if role:
            stmt = stmt.where(AgentEnrollCode.role == role)
        items = session.execute(stmt.order_by(AgentEnrollCode.created_at.desc()).limit(min(200, limit))).scalars().all()
    return [schemas.AgentEnrollCodeRead.model_validate(item) for item in items]


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


@admin_router.get("/desktop/releases", response_model=list[schemas.AgentDesktopReleaseRead])
def get_desktop_releases(
    channel: str | None = None,
    os_type: str | None = None,
    arch: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[schemas.AgentDesktopReleaseRead]:
    items = list_desktop_releases(
        channel=channel,
        os_type=os_type,
        arch=arch,
        status=status,
        limit=limit,
    )
    return [schemas.AgentDesktopReleaseRead.model_validate(item) for item in items]


@admin_router.post("/desktop/releases/upload", response_model=schemas.AgentDesktopReleaseUploadResponse)
async def upload_desktop_release_file(request: Request, filename: str | None = None) -> schemas.AgentDesktopReleaseUploadResponse:
    storage_dir = _desktop_release_storage_dir()
    raw_name = filename or request.headers.get("X-File-Name") or f"podi-desktop-{uuid4().hex[:12]}.exe"
    safe_name = _sanitize_desktop_release_filename(raw_name)
    target_path = storage_dir / safe_name
    if target_path.exists():
        target_path = storage_dir / f"{target_path.stem}-{uuid4().hex[:8]}{target_path.suffix}"
    tmp_path = storage_dir / f".upload-{uuid4().hex}.tmp"

    digest = hashlib.sha256()
    total_size = 0
    max_size = 1024 * 1024 * 1024 * 2  # 2 GB
    with tmp_path.open("wb") as handle:
        async for chunk in request.stream():
            if not chunk:
                continue
            total_size += len(chunk)
            if total_size > max_size:
                handle.close()
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="AGENT_DESKTOP_RELEASE_FILE_TOO_LARGE")
            digest.update(chunk)
            handle.write(chunk)
    if total_size <= 0:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="AGENT_DESKTOP_RELEASE_FILE_EMPTY")

    tmp_path.replace(target_path)
    download_url = f"{_resolve_desktop_release_base_url(request)}/api/agent/bootstrap/releases/files/{target_path.name}"
    return schemas.AgentDesktopReleaseUploadResponse(
        fileName=target_path.name,
        fileSize=total_size,
        sha256=digest.hexdigest().lower(),
        downloadUrl=download_url,
    )


@admin_router.post("/desktop/releases", response_model=schemas.AgentDesktopReleaseRead)
def create_desktop_release(payload: schemas.AgentDesktopReleaseCreate) -> schemas.AgentDesktopReleaseRead:
    data = payload.model_dump(by_alias=False)
    now = datetime.utcnow()
    with get_session() as session:
        release = AgentDesktopRelease(
            **data,
            published_at=data.get("published_at") or (now if data.get("status") == "active" else None),
            created_at=now,
            updated_at=now,
        )
        session.add(release)
        session.commit()
        session.refresh(release)
        return schemas.AgentDesktopReleaseRead.model_validate(release)


@admin_router.put("/desktop/releases/{release_id}", response_model=schemas.AgentDesktopReleaseRead)
def update_desktop_release(
    release_id: int,
    payload: schemas.AgentDesktopReleaseUpdate,
) -> schemas.AgentDesktopReleaseRead:
    data = payload.model_dump(exclude_unset=True, by_alias=False)
    with get_session() as session:
        release = session.get(AgentDesktopRelease, release_id)
        if not release:
            raise HTTPException(status_code=404, detail="AGENT_DESKTOP_RELEASE_NOT_FOUND")
        for key, value in data.items():
            setattr(release, key, value)
        if release.status == "active" and not release.published_at:
            release.published_at = datetime.utcnow()
        session.add(release)
        session.commit()
        session.refresh(release)
        return schemas.AgentDesktopReleaseRead.model_validate(release)


@admin_router.get("/desktop/releases/{release_id}/download")
def download_desktop_release(release_id: int) -> RedirectResponse:
    with get_session() as session:
        release = session.get(AgentDesktopRelease, release_id)
        if not release:
            raise HTTPException(status_code=404, detail="AGENT_DESKTOP_RELEASE_NOT_FOUND")
        return RedirectResponse(url=release.download_url, status_code=307)


@admin_router.get("/desktop/releases/latest/download")
def download_latest_desktop_release(
    os: str = "windows",
    arch: str = "x64",
    channel: str = "stable",
    status: str = "active",
) -> RedirectResponse:
    with get_session() as session:
        stmt = (
            select(AgentDesktopRelease)
            .where(AgentDesktopRelease.os_type == os)
            .where(AgentDesktopRelease.arch == arch)
            .where(AgentDesktopRelease.channel == channel)
            .where(AgentDesktopRelease.status == status)
            .order_by(AgentDesktopRelease.published_at.desc(), AgentDesktopRelease.id.desc())
        )
        release = session.execute(stmt.limit(1)).scalar_one_or_none()
        if not release:
            raise HTTPException(status_code=404, detail="AGENT_DESKTOP_RELEASE_NOT_FOUND")
        return RedirectResponse(url=release.download_url, status_code=307)


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
    if not data.get("status"):
        data["status"] = "draft"
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


def _publish_manifest(session, manifest: AgentManifest, *, rolled_back_status: str = "rolled_back") -> None:
    current = (
        session.execute(
            select(AgentManifest).where(
                AgentManifest.role == manifest.role,
                AgentManifest.status == "published",
                AgentManifest.id != manifest.id,
            )
        )
        .scalars()
        .all()
    )
    for row in current:
        row.status = rolled_back_status
        session.add(row)
    manifest.status = "published"
    session.add(manifest)


@admin_router.post("/manifests/{manifest_id}/publish", response_model=schemas.AgentManifestRead)
def publish_manifest(
    manifest_id: int,
    payload: schemas.AgentManifestPublishRequest | None = None,
) -> schemas.AgentManifestRead:
    with get_session() as session:
        manifest = session.get(AgentManifest, manifest_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="AGENT_MANIFEST_NOT_FOUND")
        _publish_manifest(session, manifest)
        if payload and payload.notes:
            notes = (manifest.notes or "").strip()
            suffix = payload.notes.strip()
            if suffix:
                manifest.notes = f"{notes}\n{suffix}".strip() if notes else suffix
        session.commit()
        session.refresh(manifest)
        return schemas.AgentManifestRead.model_validate(manifest)


@admin_router.post("/manifests/{manifest_id}/rollback", response_model=schemas.AgentManifestRead)
def rollback_manifest(
    manifest_id: int,
    payload: schemas.AgentManifestRollbackRequest | None = None,
) -> schemas.AgentManifestRead:
    with get_session() as session:
        base = session.get(AgentManifest, manifest_id)
        if not base:
            raise HTTPException(status_code=404, detail="AGENT_MANIFEST_NOT_FOUND")
        target = base
        if payload and payload.target_manifest_id:
            target = session.get(AgentManifest, payload.target_manifest_id)
            if not target:
                raise HTTPException(status_code=404, detail="AGENT_MANIFEST_NOT_FOUND")
            if target.role != base.role:
                raise HTTPException(status_code=400, detail="AGENT_MANIFEST_ROLE_MISMATCH")
        _publish_manifest(session, target)
        if payload and payload.notes:
            notes = (target.notes or "").strip()
            suffix = payload.notes.strip()
            if suffix:
                target.notes = f"{notes}\n[rollback] {suffix}".strip() if notes else f"[rollback] {suffix}"
        session.commit()
        session.refresh(target)
        return schemas.AgentManifestRead.model_validate(target)


@admin_router.get("/manifests/{manifest_id}/drift", response_model=schemas.AgentManifestDriftResponse)
def get_manifest_drift(manifest_id: int, agent_id: str) -> schemas.AgentManifestDriftResponse:
    with get_session() as session:
        manifest = session.get(AgentManifest, manifest_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="AGENT_MANIFEST_NOT_FOUND")
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="AGENT_NOT_FOUND")
        return _build_manifest_drift_response(manifest, agent)


@admin_router.post("/manifests/{manifest_id}/repair-plan", response_model=schemas.AgentRepairPlanResponse)
def create_manifest_repair_plan(
    manifest_id: int,
    payload: schemas.AgentRepairPlanRequest | None = None,
) -> schemas.AgentRepairPlanResponse:
    request_payload = payload or schemas.AgentRepairPlanRequest()
    mode = (request_payload.mode or "additive").strip().lower() or "additive"
    if mode != "additive":
        raise HTTPException(status_code=400, detail="COMFYUI_REPAIR_MODE_NOT_SUPPORTED")
    with get_session() as session:
        manifest = session.get(AgentManifest, manifest_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="AGENT_MANIFEST_NOT_FOUND")
        stmt = select(Agent)
        if request_payload.agent_ids:
            stmt = stmt.where(Agent.id.in_(request_payload.agent_ids))
        else:
            stmt = stmt.where(Agent.allowed == True)  # noqa: E712
            if manifest.role:
                stmt = stmt.where(Agent.role == manifest.role)
        agents = session.execute(stmt.order_by(Agent.updated_at.desc())).scalars().all()
        if not agents:
            raise HTTPException(status_code=404, detail="AGENT_NOT_FOUND")
        items: list[schemas.AgentRepairPlanItem] = []
        executable = 0
        skipped = 0
        total_actions = 0
        for agent in agents:
            if not agent.allowed:
                skipped += 1
                items.append(
                    schemas.AgentRepairPlanItem(
                        agentId=agent.id,
                        role=agent.role,
                        actions=[],
                        missingItems={},
                        reason="代理服务已禁用",
                    )
                )
                continue
            drift = _build_manifest_drift_response(manifest, agent)
            actions, missing_items = _compute_repair_actions(drift)
            if actions:
                executable += 1
                total_actions += len(actions)
            else:
                skipped += 1
            items.append(
                schemas.AgentRepairPlanItem(
                    agentId=agent.id,
                    role=agent.role,
                    actions=actions,
                    missingItems=missing_items,
                    reason=None if actions else "当前节点与清单一致，无需修复",
                )
            )
        return schemas.AgentRepairPlanResponse(
            manifestId=manifest.id,
            manifestVersion=manifest.version,
            mode=mode,
            generatedAt=datetime.utcnow(),
            items=items,
            summary=schemas.AgentRepairPlanSummary(
                totalAgents=len(items),
                executableAgents=executable,
                skippedAgents=skipped,
                totalActions=total_actions,
            ),
        )


@admin_router.post("/repair-jobs", response_model=schemas.AgentRepairJobRead)
def create_repair_job(payload: schemas.AgentRepairJobCreateRequest) -> schemas.AgentRepairJobRead:
    mode = (payload.mode or "additive").strip().lower() or "additive"
    if mode != "additive":
        raise HTTPException(status_code=400, detail="COMFYUI_REPAIR_MODE_NOT_SUPPORTED")
    now = datetime.utcnow()
    with get_session() as session:
        manifest = session.get(AgentManifest, payload.manifest_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="AGENT_MANIFEST_NOT_FOUND")
        if not payload.items:
            raise HTTPException(status_code=400, detail="COMFYUI_REPAIR_ITEMS_REQUIRED")
        job = ComfyuiRepairJob(
            id=f"rjob_{now:%Y%m%d_%H%M%S}_{uuid4().hex[:8]}",
            manifest_id=manifest.id,
            mode=mode,
            status="pending",
            requested_agent_count=len(payload.items),
            created_by="admin",
            request_payload={
                "manifestId": manifest.id,
                "manifestVersion": manifest.version,
                "mode": mode,
                "items": [item.model_dump(by_alias=True) for item in payload.items],
            },
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        session.flush()
        created_task_ids: list[str] = []
        for item in payload.items:
            actions = sorted({str(v).strip() for v in item.actions if str(v).strip()})
            missing_items = item.missing_items if isinstance(item.missing_items, dict) else {}
            row = ComfyuiRepairJobItem(
                repair_job_id=job.id,
                manifest_id=manifest.id,
                agent_id=item.agent_id,
                actions=actions,
                missing_items=missing_items,
                status="pending",
                created_at=now,
                updated_at=now,
            )
            try:
                agent = session.get(Agent, item.agent_id)
                if not agent:
                    raise HTTPException(status_code=404, detail="AGENT_NOT_FOUND")
                ensure_agent_allowed(agent)
                if not actions:
                    row.status = "skipped"
                    row.final_status = "success"
                    row.error_code = "COMFYUI_REPAIR_NOTHING_TO_DO"
                    row.error_message = "该节点无需修复"
                    job.skipped_task_count += 1
                else:
                    task = create_agent_task(
                        agent_id=agent.id,
                        manifest=manifest,
                        actions=actions,
                        expires_at=None,
                    )
                    db_task = session.get(AgentTask, task.id)
                    if db_task:
                        request_payload = db_task.request_payload if isinstance(db_task.request_payload, dict) else {}
                        request_payload["repairJobId"] = job.id
                        request_payload["repairMissingItems"] = missing_items
                        db_task.request_payload = request_payload
                        session.add(db_task)
                    row.task_id = task.id
                    row.status = "running"
                    created_task_ids.append(task.id)
                    if payload.push:
                        try:
                            push_task_to_agent(task)
                        except HTTPException as exc:
                            row.status = "failed"
                            row.submit_status = "submit_failed"
                            row.callback_status = "failed"
                            row.final_status = "failed"
                            row.error_code = str(exc.detail)
                            row.error_message = str(exc.detail)
                            job.failed_task_count += 1
            except HTTPException as exc:
                row.status = "failed"
                row.submit_status = "submit_failed"
                row.callback_status = "failed"
                row.final_status = "failed"
                row.error_code = str(exc.detail)
                row.error_message = str(exc.detail)
                job.failed_task_count += 1
            session.add(row)
        job.submitted_task_count = len(created_task_ids)
        if job.failed_task_count > 0 and job.submitted_task_count == 0:
            job.status = "failed"
        elif job.submitted_task_count > 0:
            job.status = "running"
        elif job.skipped_task_count == job.requested_agent_count:
            job.status = "succeeded"
        job.result_payload = {"taskIds": created_task_ids}
        session.add(job)
        session.commit()
        session.refresh(job)
        return _serialize_repair_job(session, job)


@admin_router.get("/repair-jobs", response_model=list[schemas.AgentRepairJobRead])
def list_repair_jobs(manifest_id: int | None = None, limit: int = 20) -> list[schemas.AgentRepairJobRead]:
    with get_session() as session:
        stmt = select(ComfyuiRepairJob)
        if manifest_id is not None:
            stmt = stmt.where(ComfyuiRepairJob.manifest_id == manifest_id)
        jobs = session.execute(stmt.order_by(ComfyuiRepairJob.created_at.desc()).limit(min(100, limit))).scalars().all()
        return [_serialize_repair_job(session, job) for job in jobs]


@admin_router.get("/repair-jobs/{job_id}", response_model=schemas.AgentRepairJobRead)
def get_repair_job(job_id: str) -> schemas.AgentRepairJobRead:
    with get_session() as session:
        job = session.get(ComfyuiRepairJob, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="COMFYUI_REPAIR_JOB_NOT_FOUND")
        return _serialize_repair_job(session, job)


@admin_router.get("/roles/{role}/primary-agent", response_model=schemas.AgentRolePrimaryRead)
def get_role_primary_agent(role: str) -> schemas.AgentRolePrimaryRead:
    with get_session() as session:
        agents = (
            session.execute(
                select(Agent)
                .where(Agent.role == role)
                .order_by(Agent.updated_at.desc(), Agent.created_at.desc())
            )
            .scalars()
            .all()
        )
        primary = None
        for item in agents:
            config = item.config if isinstance(item.config, dict) else {}
            if bool(config.get("rolePrimary")):
                primary = item
                break
        if not primary and agents:
            primary = agents[0]
        return schemas.AgentRolePrimaryRead(
            role=role,
            agent_id=primary.id if primary else None,
            base_url=primary.base_url if primary else None,
            updated_at=primary.updated_at if primary else None,
        )


@admin_router.post("/roles/{role}/primary-agent", response_model=schemas.AgentRolePrimaryRead)
def set_role_primary_agent(role: str, payload: schemas.AgentRolePrimaryUpdateRequest) -> schemas.AgentRolePrimaryRead:
    with get_session() as session:
        rows = session.execute(select(Agent).where(Agent.role == role)).scalars().all()
        if not rows:
            raise HTTPException(status_code=404, detail="AGENT_NOT_FOUND")
        target = None
        for row in rows:
            config = row.config if isinstance(row.config, dict) else {}
            is_primary = row.id == payload.agent_id
            config["rolePrimary"] = is_primary
            row.config = config
            session.add(row)
            if is_primary:
                target = row
        if not target:
            raise HTTPException(status_code=404, detail="AGENT_NOT_FOUND")
        session.commit()
        session.refresh(target)
        return schemas.AgentRolePrimaryRead(
            role=role,
            agent_id=target.id,
            base_url=target.base_url,
            updated_at=target.updated_at,
        )


@admin_router.get("/monitoring/summary", response_model=schemas.AgentMonitoringSummaryResponse)
def get_monitoring_summary(window_hours: int = 24) -> schemas.AgentMonitoringSummaryResponse:
    window_hours = max(1, min(int(window_hours), 24 * 30))
    since = datetime.utcnow() - timedelta(hours=window_hours)
    with get_session() as session:
        ability_rows = (
            session.execute(select(AbilityTask).where(AbilityTask.created_at >= since))
            .scalars()
            .all()
        )
        agent_rows = (
            session.execute(select(AgentTask).where(AgentTask.created_at >= since))
            .scalars()
            .all()
        )
        event_rows = (
            session.execute(select(AgentTaskEvent).where(AgentTaskEvent.created_at >= since))
            .scalars()
            .all()
        )

    def _lane_stats(name: str, rows: list[Any], status_getter) -> schemas.AgentMonitoringLane:
        total = len(rows)
        queued = 0
        running = 0
        succeeded = 0
        failed = 0
        waits: list[float] = []
        for row in rows:
            status = status_getter(row)
            if status in {"queued", "pending", "submitting"}:
                queued += 1
            elif status in {"running", "submitted"}:
                running += 1
            elif status in {"succeeded", "success"}:
                succeeded += 1
            elif status in {"failed", "rejected", "canceled", "cancelled"}:
                failed += 1
            started = getattr(row, "started_at", None)
            created = getattr(row, "created_at", None)
            if started and created:
                waits.append(max(0.0, (started - created).total_seconds()))
        avg_wait = round(sum(waits) / len(waits), 3) if waits else 0.0
        failure_rate = round((failed / total), 4) if total else 0.0
        return schemas.AgentMonitoringLane(
            lane=name,
            total=total,
            queued=queued,
            running=running,
            succeeded=succeeded,
            failed=failed,
            avg_wait_seconds=avg_wait,
            failure_rate=failure_rate,
            retry_count=0,
        )

    lanes: list[schemas.AgentMonitoringLane] = []
    provider_groups: dict[str, list[AbilityTask]] = {}
    for row in ability_rows:
        provider = str(row.ability_provider or "unknown").lower()
        provider_groups.setdefault(provider, []).append(row)
    for provider, rows in sorted(provider_groups.items(), key=lambda item: item[0]):
        lanes.append(_lane_stats(provider, rows, lambda row: str(row.status or "").lower()))
    agent_lane = _lane_stats("agent", agent_rows, lambda row: str(row.status or "").lower())
    agent_lane.retry_count = sum(
        1
        for event in event_rows
        if isinstance(event.payload, dict) and event.payload.get("retryCount") is not None
    )
    lanes.append(agent_lane)
    return schemas.AgentMonitoringSummaryResponse(
        generated_at=datetime.utcnow(),
        window_hours=window_hours,
        lanes=lanes,
    )


@admin_router.get("/monitoring/queues", response_model=schemas.AgentMonitoringQueuesResponse)
def get_monitoring_queues(window_hours: int = 24) -> schemas.AgentMonitoringQueuesResponse:
    summary = get_monitoring_summary(window_hours=window_hours)
    items = [
        schemas.AgentMonitoringQueueItem(
            lane=lane.lane,
            provider=lane.lane,
            queued=lane.queued,
            running=lane.running,
            total=lane.total,
            avgWaitSeconds=lane.avg_wait_seconds,
        )
        for lane in summary.lanes
    ]
    return schemas.AgentMonitoringQueuesResponse(
        generatedAt=summary.generated_at,
        windowHours=summary.window_hours,
        items=items,
    )


@admin_router.get("/monitoring/errors", response_model=schemas.AgentMonitoringErrorsResponse)
def get_monitoring_errors(window_hours: int = 24, limit: int = 100) -> schemas.AgentMonitoringErrorsResponse:
    window_hours = max(1, min(int(window_hours), 24 * 30))
    since = datetime.utcnow() - timedelta(hours=window_hours)
    with get_session() as session:
        ability_rows = (
            session.execute(select(AbilityTask).where(AbilityTask.created_at >= since))
            .scalars()
            .all()
        )
        agent_rows = (
            session.execute(select(AgentTask).where(AgentTask.created_at >= since))
            .scalars()
            .all()
        )

    buckets: dict[tuple[str, str, str], schemas.AgentMonitoringErrorItem] = {}
    for row in ability_rows:
        status = str(row.status or "").lower()
        if status not in {"failed", "rejected", "timeout", "canceled", "cancelled"}:
            continue
        provider = str(row.ability_provider or "unknown").lower()
        error_code = str(row.error_code or "ABILITY_FAILED").strip() or "ABILITY_FAILED"
        key = (provider, "callback", error_code)
        item = buckets.get(key)
        if not item:
            item = schemas.AgentMonitoringErrorItem(
                provider=provider,
                stage="callback",
                errorCode=error_code,
                count=0,
                lastOccurredAt=None,
                sampleMessage=row.error_message,
            )
            buckets[key] = item
        item.count += 1
        if not item.last_occurred_at or (row.updated_at and row.updated_at > item.last_occurred_at):
            item.last_occurred_at = row.updated_at
        if not item.sample_message and row.error_message:
            item.sample_message = row.error_message

    for row in agent_rows:
        stage = derive_agent_task_status(
            status=row.status,
            pushed_at=row.pushed_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
            error_message=row.error_message,
        )
        if stage.final_status not in {"failed", "rejected", "canceled"}:
            continue
        error_code = str(stage.error_code or "AGENT_TASK_FAILED")
        key = ("agent", "callback", error_code)
        item = buckets.get(key)
        if not item:
            item = schemas.AgentMonitoringErrorItem(
                provider="agent",
                stage="callback",
                errorCode=error_code,
                count=0,
                lastOccurredAt=None,
                sampleMessage=row.error_message,
            )
            buckets[key] = item
        item.count += 1
        if not item.last_occurred_at or (row.updated_at and row.updated_at > item.last_occurred_at):
            item.last_occurred_at = row.updated_at
        if not item.sample_message and row.error_message:
            item.sample_message = row.error_message

    items = sorted(buckets.values(), key=lambda item: (item.count, item.last_occurred_at or datetime.min), reverse=True)
    return schemas.AgentMonitoringErrorsResponse(
        generatedAt=datetime.utcnow(),
        windowHours=window_hours,
        items=items[: max(1, min(limit, 200))],
    )


def _upsert_runtime_policy(policy_type: str, payload: dict[str, Any]) -> schemas.AgentRuntimePolicyRead:
    now = datetime.utcnow()
    with get_session() as session:
        row = session.execute(
            select(ComfyuiRuntimePolicy).where(ComfyuiRuntimePolicy.policy_type == policy_type)
        ).scalar_one_or_none()
        if not row:
            row = ComfyuiRuntimePolicy(
                policy_type=policy_type,
                payload=payload,
                created_at=now,
                updated_at=now,
            )
        else:
            row.payload = payload
            row.updated_at = now
        session.add(row)
        session.commit()
        session.refresh(row)
        data = row.payload if isinstance(row.payload, dict) else {}
        return schemas.AgentRuntimePolicyRead(
            policyType=row.policy_type,
            defaultPolicy=data.get("defaultPolicy") if isinstance(data.get("defaultPolicy"), dict) else {},
            laneOverrides=data.get("laneOverrides") if isinstance(data.get("laneOverrides"), dict) else {},
            nodeOverrides=data.get("nodeOverrides") if isinstance(data.get("nodeOverrides"), dict) else {},
            notes=str(data.get("notes") or "") or None,
            updatedAt=row.updated_at,
        )


def _read_runtime_policy(policy_type: str) -> schemas.AgentRuntimePolicyRead:
    with get_session() as session:
        row = session.execute(
            select(ComfyuiRuntimePolicy).where(ComfyuiRuntimePolicy.policy_type == policy_type)
        ).scalar_one_or_none()
        if not row:
            return schemas.AgentRuntimePolicyRead(
                policyType=policy_type,
                defaultPolicy={},
                laneOverrides={},
                nodeOverrides={},
                notes=None,
                updatedAt=datetime.utcnow(),
            )
        data = row.payload if isinstance(row.payload, dict) else {}
        return schemas.AgentRuntimePolicyRead(
            policyType=row.policy_type,
            defaultPolicy=data.get("defaultPolicy") if isinstance(data.get("defaultPolicy"), dict) else {},
            laneOverrides=data.get("laneOverrides") if isinstance(data.get("laneOverrides"), dict) else {},
            nodeOverrides=data.get("nodeOverrides") if isinstance(data.get("nodeOverrides"), dict) else {},
            notes=str(data.get("notes") or "") or None,
            updatedAt=row.updated_at,
        )


@admin_router.put("/policies/concurrency", response_model=schemas.AgentRuntimePolicyRead)
def put_concurrency_policy(payload: schemas.AgentRuntimePolicyRequest) -> schemas.AgentRuntimePolicyRead:
    data = payload.model_dump(by_alias=True)
    return _upsert_runtime_policy("concurrency", data)


@admin_router.get("/policies/concurrency", response_model=schemas.AgentRuntimePolicyRead)
def get_concurrency_policy() -> schemas.AgentRuntimePolicyRead:
    return _read_runtime_policy("concurrency")


@admin_router.put("/policies/retry", response_model=schemas.AgentRuntimePolicyRead)
def put_retry_policy(payload: schemas.AgentRuntimePolicyRequest) -> schemas.AgentRuntimePolicyRead:
    data = payload.model_dump(by_alias=True)
    return _upsert_runtime_policy("retry", data)


@admin_router.get("/policies/retry", response_model=schemas.AgentRuntimePolicyRead)
def get_retry_policy() -> schemas.AgentRuntimePolicyRead:
    return _read_runtime_policy("retry")


@admin_router.get("/tasks", response_model=list[schemas.AgentTaskRead])
def list_tasks(agent_id: str | None = None, status: str | None = None, limit: int = 50) -> list[schemas.AgentTaskRead]:
    with get_session() as session:
        stmt = select(AgentTask)
        if agent_id:
            stmt = stmt.where(AgentTask.agent_id == agent_id)
        if status:
            stmt = stmt.where(AgentTask.status == status)
        items = session.execute(stmt.order_by(AgentTask.created_at.desc()).limit(min(limit, 200))).scalars().all()
        return [schemas.AgentTaskRead.model_validate(_with_agent_task_stage(item)) for item in items]


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
    return schemas.AgentTaskRead.model_validate(_with_agent_task_stage(task))


@admin_router.get("/tasks/{task_id}", response_model=schemas.AgentTaskRead)
def get_task(task_id: str) -> schemas.AgentTaskRead:
    with get_session() as session:
        task = session.get(AgentTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="AGENT_TASK_NOT_FOUND")
        return schemas.AgentTaskRead.model_validate(_with_agent_task_stage(task))


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
