"""Service for AI ability evaluation runs (Coze workflow -> optional PODI task polling)."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.models.eval import EvalRun, EvalWorkflowVersion
from app.models.integration import AbilityTask
from app.services.ability_task_service import ability_task_service
from app.services.coze_client import coze_client


_HEX_TASK_ID = re.compile(r"^[0-9a-f]{24,64}$")


class EvalService:
    """Persisted evaluation runs with background execution in a bounded thread pool."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        settings = get_settings()
        max_workers = max(1, int(getattr(settings, "eval_run_max_workers", 6)))
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        # Best-effort: never block API startup on evaluation bookkeeping.
        # (In reload mode, mapper initialization can be sensitive to import order.)
        try:
            self._resume_pending_runs()
        except Exception as exc:  # pragma: no cover - defensive startup guard
            self._logger.warning("EvalService resume skipped: %s", exc)

    def create_eval_run(
        self,
        *,
        workflow_version_id: str,
        dataset_item_id: str | None,
        input_oss_urls: list[str] | None,
        parameters: dict[str, Any] | None,
        created_by: str,
        db: Session,
    ) -> EvalRun:
        workflow_version = db.get(EvalWorkflowVersion, workflow_version_id)
        if not workflow_version:
            raise ValueError(f"Workflow version {workflow_version_id} not found")

        normalized_params = (parameters or {}).copy()
        urls = [u for u in (input_oss_urls or []) if isinstance(u, str) and u.strip()]
        if urls:
            # Keep the convention: single image input uses `url` (string).
            normalized_params.setdefault("url", urls[0])
            if len(urls) > 1:
                normalized_params.setdefault("urls", urls)
            # Compat for some Coze workflows that use different casing.
            for alias in ("Url", "URL"):
                normalized_params.setdefault(alias, urls[0])

        run = EvalRun(
            id=uuid4().hex,
            workflow_version_id=workflow_version_id,
            dataset_item_id=dataset_item_id,
            input_oss_urls_json=urls or None,
            parameters_json=normalized_params or None,
            status="queued",
            created_by=created_by,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        self._executor.submit(self._execute_run, run.id)
        return run

    def list_eval_runs(
        self,
        *,
        db: Session,
        workflow_version_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[int, list[EvalRun]]:
        stmt = select(EvalRun)
        count_stmt = select(func.count()).select_from(EvalRun)
        if workflow_version_id:
            stmt = stmt.where(EvalRun.workflow_version_id == workflow_version_id)
            count_stmt = count_stmt.where(EvalRun.workflow_version_id == workflow_version_id)
        if status:
            stmt = stmt.where(EvalRun.status == status)
            count_stmt = count_stmt.where(EvalRun.status == status)

        total = int(db.execute(count_stmt).scalar_one())
        items = (
            db.execute(stmt.order_by(EvalRun.created_at.desc()).offset(offset).limit(limit))
            .scalars()
            .all()
        )
        return total, items

    def _resume_pending_runs(self) -> None:
        """On process boot, re-queue runs left in queued/running."""
        with get_session() as session:
            pending_ids = (
                session.execute(select(EvalRun.id).where(EvalRun.status.in_(["queued", "running"])))
                .scalars()
                .all()
            )
            if pending_ids:
                session.execute(
                    EvalRun.__table__.update()
                    .where(EvalRun.id.in_(pending_ids))
                    .values(status="queued")
                )
                session.commit()
        for run_id in pending_ids:
            self._executor.submit(self._execute_run, run_id)

    def _execute_run(self, run_id: str) -> None:
        started = time.monotonic()
        settings = get_settings()
        # Avoid using ORM instances outside the session scope (commit expires attrs by default).
        workflow_id: str | None = None
        run_parameters: dict[str, Any] = {}
        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if not run:
                return
            if isinstance(run.parameters_json, dict):
                run_parameters = run.parameters_json.copy()
            workflow_version = session.get(EvalWorkflowVersion, run.workflow_version_id)
            if not workflow_version:
                run.status = "failed"
                run.error_message = "WORKFLOW_VERSION_NOT_FOUND"
                session.add(run)
                session.commit()
                return
            workflow_id = str(workflow_version.workflow_id)
            run.status = "running"
            session.add(run)
            session.commit()

        try:
            # Execute the workflow (non-streaming). OpenAPI tokens are handled by coze_client.
            if not workflow_id:
                raise RuntimeError("WORKFLOW_ID_MISSING")
            response = coze_client.run_workflow(
                workflow_id=workflow_id,
                parameters=run_parameters,
                is_async=False,
            )

            execute_id = response.get("execute_id")
            debug_url = response.get("debug_url")
            with get_session() as session:
                run = session.get(EvalRun, run_id)
                if not run:
                    return
                run.coze_execute_id = str(execute_id) if execute_id else None
                run.coze_debug_url = str(debug_url) if debug_url else None
                session.add(run)
                session.commit()

            parsed = self._parse_coze_payload(response)
            output = parsed.get("output")
            podi_task_id = self._guess_podi_task_id(parsed, output)
            if podi_task_id:
                # Prefer PODI ability_tasks.
                with get_session() as session:
                    task_row = session.get(AbilityTask, podi_task_id)
                if task_row:
                    self._poll_ability_task(run_id=run_id, task_id=podi_task_id, started=started)
                    return
                # Fallback: if output is a raw ComfyUI id, resolve via a callback workflow.
                callback_wf = settings.coze_comfyui_callback_workflow_id
                if callback_wf:
                    with get_session() as session:
                        run = session.get(EvalRun, run_id)
                        if run:
                            run.podi_task_id = podi_task_id
                            session.add(run)
                            session.commit()
                    image_urls = self._poll_callback_images(
                        callback_workflow_id=callback_wf,
                        taskid=podi_task_id,
                    )
                    if image_urls:
                        self._mark_succeeded(run_id, image_urls=image_urls, started=started)
                        return
                    self._mark_failed(run_id, message="CALLBACK_IMAGES_EMPTY", started=started)
                    return

            image_urls = self._extract_image_urls(parsed)
            self._mark_succeeded(run_id, image_urls=image_urls, started=started)
        except HTTPException as exc:
            self._mark_failed(run_id, message=str(exc.detail), started=started)
        except Exception as exc:  # pragma: no cover - defensive
            self._mark_failed(run_id, message=str(exc), started=started)

    @staticmethod
    def _parse_coze_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize Coze response to a dict with parsed `data`."""
        data = payload.get("data")
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                # Some workflows return plain strings.
                return {"output": data}
        if isinstance(data, dict):
            return data
        # Fallback to the top-level payload (best-effort).
        if isinstance(payload, dict):
            return payload
        return {}

    @staticmethod
    def _guess_podi_task_id(parsed: dict[str, Any], output: Any) -> str | None:
        for key in ("podi_task_id", "task_id", "taskId"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(output, str) and _HEX_TASK_ID.match(output.strip()):
            return output.strip()
        return None

    @staticmethod
    def _extract_image_urls(payload: dict[str, Any]) -> list[str]:
        """Extract image URLs from common workflow outputs."""
        candidates: list[str] = []

        def _push(value: Any) -> None:
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                candidates.append(value)

        for key in ("imageUrl", "image_url", "url"):
            _push(payload.get(key))
        for key in ("imageUrls", "image_urls", "urls"):
            val = payload.get(key)
            if isinstance(val, list):
                for item in val:
                    _push(item)

        assets = payload.get("assets")
        if isinstance(assets, list):
            for item in assets:
                if isinstance(item, dict):
                    _push(item.get("storedUrl") or item.get("ossUrl") or item.get("url"))

        # Legacy: some workflows use output for a single URL.
        _push(payload.get("output"))

        # Preserve order, de-dup.
        seen: set[str] = set()
        out: list[str] = []
        for u in candidates:
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
        return out

    def _poll_callback_images(self, *, callback_workflow_id: str, taskid: str) -> list[str]:
        """Resolve images for workflows that output a raw ComfyUI task id.

        The callback workflow may return empty images while the underlying job is still running,
        so we poll for a bounded period.
        """
        deadline = time.monotonic() + 180.0
        interval = 2.0
        last_images: list[str] = []
        attempts = 0
        while time.monotonic() < deadline:
            attempts += 1
            resolved = coze_client.run_workflow(
                workflow_id=callback_workflow_id,
                parameters={"taskid": taskid},
                is_async=False,
            )
            parsed = self._parse_coze_payload(resolved)
            images = self._extract_image_urls(parsed)
            last_images = images
            if images:
                break
            time.sleep(interval)
            interval = min(interval * 1.4, 8.0)
        return last_images

    def _poll_ability_task(self, *, run_id: str, task_id: str, started: float) -> None:
        deadline = time.monotonic() + 60 * 20  # 20 minutes max
        interval = 1.5
        last_status: str | None = None

        while time.monotonic() < deadline:
            with get_session() as session:
                task_row = session.get(AbilityTask, task_id)
                if not task_row:
                    self._mark_failed(run_id, message="TASK_NOT_FOUND", started=started)
                    return
                task = ability_task_service.to_dict(task_row)
            status = task.get("status")
            if status != last_status:
                last_status = status
                with get_session() as session:
                    run = session.get(EvalRun, run_id)
                    if run:
                        run.podi_task_id = task_id
                        session.add(run)
                        session.commit()

            if status == "succeeded":
                result_payload = task.get("result_payload") or {}
                image_urls: list[str] = []
                if isinstance(result_payload, dict):
                    images = result_payload.get("images") or []
                    if isinstance(images, list):
                        for it in images:
                            if not isinstance(it, dict):
                                continue
                            for k in ("ossUrl", "sourceUrl", "url"):
                                v = it.get(k)
                                if isinstance(v, str) and v.strip():
                                    image_urls.append(v.strip())
                                    break
                self._mark_succeeded(run_id, image_urls=image_urls, started=started)
                return

            if status == "failed":
                self._mark_failed(run_id, message=task.get("error_message") or "TASK_FAILED", started=started)
                return

            time.sleep(interval)
            interval = min(interval * 1.3, 10.0)

        self._mark_failed(run_id, message="TASK_TIMEOUT", started=started)

    @staticmethod
    def _mark_succeeded(run_id: str, *, image_urls: list[str], started: float) -> None:
        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if not run:
                return
            run.status = "succeeded"
            run.error_message = None
            run.result_image_urls_json = image_urls or []
            run.duration_ms = int((time.monotonic() - started) * 1000)
            session.add(run)
            session.commit()

    @staticmethod
    def _mark_failed(run_id: str, *, message: str, started: float) -> None:
        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if not run:
                return
            run.status = "failed"
            run.error_message = message
            run.duration_ms = int((time.monotonic() - started) * 1000)
            session.add(run)
            session.commit()


@lru_cache
def get_eval_service() -> EvalService:
    """Lazy singleton to avoid import-time side effects (important under uvicorn reload)."""

    return EvalService()
