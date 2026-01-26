"""Async ability task queue service."""

from __future__ import annotations

from functools import lru_cache
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_session
from app.models.integration import Ability, AbilityTask
from app.models.user import User
from app.schemas.abilities import AbilityInvokeRequest
from app.services.ability_invocation import ability_invocation_service
from app.services.task_id_codec import decode_task_id


class AbilityTaskService:
    def __init__(self) -> None:
        settings = get_settings()
        max_workers = max(1, settings.ability_task_max_workers)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._resume_pending_tasks()

    def enqueue(self, *, ability_id: str, payload: AbilityInvokeRequest, user: User | None) -> AbilityTask:
        with get_session() as session:
            ability = session.get(Ability, ability_id)
            if not ability or ability.status != "active":
                raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND_OR_INACTIVE")
            task = AbilityTask(
                id=uuid4().hex,
                ability_id=ability.id,
                ability_name=ability.display_name,
                ability_provider=ability.provider,
                capability_key=ability.capability_key,
                user_id=user.id if user else None,
                user_name=user.username if user else None,
                status="queued",
                request_payload=payload.model_dump(),
                callback_url=payload.callbackUrl,
                callback_headers=payload.callbackHeaders,
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            task_data = self.to_dict(task)
        self._executor.submit(self._run_task, task.id)
        return task_data

    def list_tasks(self, *, user: User, limit: int = 50) -> list[AbilityTask]:
        with get_session() as session:
            stmt = select(AbilityTask).order_by(AbilityTask.created_at.desc()).limit(max(1, min(limit, 200)))
            if user.role != "admin":
                stmt = stmt.where(AbilityTask.user_id == user.id)
            tasks = session.execute(stmt).scalars().all()
            return [self.to_dict(task) for task in tasks]

    def get_task(self, *, task_id: str, user: User) -> AbilityTask:
        decoded = decode_task_id(task_id) or task_id
        with get_session() as session:
            stmt = select(AbilityTask).where(AbilityTask.id == decoded)
            if user.role != "admin":
                stmt = stmt.where(AbilityTask.user_id == user.id)
            task = session.execute(stmt).scalar_one_or_none()
            if not task:
                raise HTTPException(status_code=404, detail="TASK_NOT_FOUND")
            return self.to_dict(task)

    def _resume_pending_tasks(self) -> None:
        pending_ids: list[str] = []
        with get_session() as session:
            pending = (
                session.execute(select(AbilityTask).where(AbilityTask.status.in_(["queued", "running"])))
                .scalars()
                .all()
            )

            # Avoid duplicate submissions on process restart:
            # - Some ComfyUI abilities are "submit-only" (we return immediately and finalize later via polling).
            # - Those tasks stay in `running` with a stored promptId/baseUrl in result_payload.metadata.
            # If we blindly reset `running` -> `queued` and re-enqueue, we'll submit the same job again,
            # creating "mysterious extra jobs" on the ComfyUI server after each backend restart.
            to_requeue: list[str] = []
            for task in pending:
                if task.status == "queued":
                    to_requeue.append(task.id)
                    continue
                if task.status == "running":
                    if self._is_comfyui_submitted_only(task):
                        continue
                    to_requeue.append(task.id)

            pending_ids = to_requeue
            if pending_ids:
                session.execute(
                    AbilityTask.__table__.update()
                    .where(AbilityTask.id.in_(pending_ids))
                    .values(status="queued", started_at=None)
                )
                session.commit()
        for task_id in pending_ids:
            self._executor.submit(self._run_task, task_id)

    @staticmethod
    def _is_comfyui_submitted_only(task: AbilityTask) -> bool:
        if (task.ability_provider or "").lower() != "comfyui":
            return False
        payload = task.result_payload or {}
        if not isinstance(payload, dict):
            return False
        meta = payload.get("metadata")
        if not isinstance(meta, dict):
            return False
        prompt_id = meta.get("promptId") or meta.get("taskId")
        base_url = meta.get("baseUrl")
        return isinstance(prompt_id, str) and bool(prompt_id.strip()) and isinstance(base_url, str) and bool(base_url.strip())

    def _run_task(self, task_id: str) -> None:
        started_at = datetime.utcnow()
        request_payload: dict[str, Any] | None = None
        task_user_id: str | None = None
        task_ability_id: str | None = None
        with get_session() as session:
            task = session.get(AbilityTask, task_id)
            if not task:
                return
            request_payload = (task.request_payload or {}).copy()
            task_user_id = task.user_id
            task_ability_id = task.ability_id
            task.status = "running"
            task.started_at = started_at
            session.add(task)
            session.commit()
        try:
            request_model = AbilityInvokeRequest.model_validate(request_payload or {})
            user = None
            if task_user_id:
                with get_session() as session:
                    user = session.get(User, task_user_id)
            response = ability_invocation_service.invoke(
                ability_id=task_ability_id or "",
                payload=request_model,
                user=user,
                source="ability-task",
            )
            finished_at = datetime.utcnow()
            duration = response.durationMs
            if duration is None:
                duration = int((finished_at - started_at).total_seconds() * 1000)
            with get_session() as session:
                db_task = session.get(AbilityTask, task_id)
                if not db_task:
                    return
                # Some abilities (e.g. long-running ComfyUI graphs) return status=running,
                # meaning we only submitted the job and will finalize later via polling.
                if (response.status or "").lower() in {"queued", "running"}:
                    db_task.status = "running"
                    db_task.finished_at = None
                    db_task.duration_ms = None
                    db_task.result_payload = response.model_dump()
                    db_task.log_id = response.logId
                    db_task.error_message = None
                else:
                    db_task.status = "succeeded"
                    db_task.finished_at = finished_at
                    db_task.duration_ms = duration
                    db_task.result_payload = response.model_dump()
                    db_task.log_id = response.logId
                    db_task.error_message = None
                session.add(db_task)
                session.commit()
        except Exception as exc:  # pragma: no cover - defensive
            finished_at = datetime.utcnow()
            error_detail = self._format_error(exc)
            with get_session() as session:
                db_task = session.get(AbilityTask, task_id)
                if not db_task:
                    return
                db_task.status = "failed"
                db_task.finished_at = finished_at
                db_task.error_message = error_detail.get("message")
                db_task.result_payload = None
                session.add(db_task)
                session.commit()

    @staticmethod
    def _format_error(exc: Exception) -> dict[str, Any]:
        if isinstance(exc, HTTPException):
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            return {"message": detail, "status_code": exc.status_code}
        return {"message": str(exc)}

    def to_dict(self, task: AbilityTask) -> dict[str, Any]:
        return {
            "id": task.id,
            "ability_id": task.ability_id,
            "ability_name": task.ability_name,
            "ability_provider": task.ability_provider,
            "capability_key": task.capability_key,
            "status": task.status,
            "log_id": task.log_id,
            "duration_ms": task.duration_ms,
            "request_payload": self._sanitize_payload(task.request_payload),
            "result_payload": self._sanitize_payload(task.result_payload),
            "error_message": task.error_message,
            "callback_url": task.callback_url,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
        }

    def _sanitize_payload(self, payload: dict[str, Any] | None, depth: int = 0) -> dict[str, Any] | None:
        if payload is None:
            return None

        def _sanitize(value: Any, level: int = 0) -> Any:
            if level > 6:
                return "[truncated]"
            if isinstance(value, dict):
                sanitized = {}
                for key, val in value.items():
                    key_lower = str(key).lower()
                    if key_lower in {"imagebase64", "image_base64"} or key_lower.endswith("base64"):
                        sanitized[key] = "[omitted]"
                    else:
                        sanitized[key] = _sanitize(val, level + 1)
                return sanitized
            if isinstance(value, list):
                return [_sanitize(item, level + 1) for item in value[:50]]
            return value

        return _sanitize(payload, depth)


@lru_cache
def get_ability_task_service() -> AbilityTaskService:
    """Lazy singleton to avoid import-time side effects (important under uvicorn reload/tests)."""

    return AbilityTaskService()
