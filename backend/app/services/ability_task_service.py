"""Async ability task queue service."""

from __future__ import annotations

from functools import lru_cache
import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.db import get_session
from app.models.integration import Ability, AbilityInvocationLog, AbilityTask
from app.models.user import User
from app.schemas.abilities import AbilityInvokeRequest
from app.services.ability_invocation import ability_invocation_service
from app.services.ability_logs import ability_log_service
from app.services.integration_test import integration_test_service
from app.services.task_id_codec import decode_task_id
from app.services.task_status_contract import derive_ability_task_status
from app.services.wallet import wallet_service

logger = logging.getLogger(__name__)

CLEANUP_TTL_HOURS = 24
CLEANUP_INTERVAL_SECONDS = 30 * 60
# 回填线程默认每 8 秒扫描一次，避免 ComfyUI 任务在“已完成但未回填”状态停留过久。
FINALIZE_INTERVAL_SECONDS = 8
FINALIZE_BATCH_SIZE = 20
COMFYUI_HISTORY_TIMEOUT_SECONDS = 6
MAX_QUEUE_PER_EXECUTOR = 10
ERR_CODE_COMFYUI_QUEUE_FULL = "Q1001"
ERR_CODE_COMMERCIAL_QUEUE_FULL = "Q2001"


def _format_task_error(code: str, message: str) -> str:
    safe_message = " ".join(str(message).strip().split())
    safe_message = safe_message.replace("|", "/")
    return f"ERR|{code}|{safe_message}"


class AbilityTaskService:
    def __init__(self) -> None:
        settings = get_settings()
        max_workers = max(1, settings.ability_task_max_workers)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._cleanup_stale_running_tasks()
        self._start_cleanup_thread()
        self._start_finalize_thread()
        self._resume_pending_tasks()

    def enqueue(self, *, ability_id: str, payload: AbilityInvokeRequest, user: User | None) -> AbilityTask:
        with get_session() as session:
            ability = session.get(Ability, ability_id)
            if not ability or ability.status != "active":
                raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND_OR_INACTIVE")
            provider_lower = (ability.provider or "").lower()
            executor_id = payload.executorId or ability.executor_id
            if executor_id:
                is_comfyui = provider_lower == "comfyui"
                is_commercial = provider_lower in {"volcengine", "kie"}
                is_async_flag = bool((ability.extra_metadata or {}).get("async_mode") or (ability.extra_metadata or {}).get("callback_mode"))
                if is_comfyui or is_commercial or is_async_flag:
                    pending_count = self.count_pending_by_executor(
                        executor_id=executor_id,
                        providers=[provider_lower] if provider_lower else None,
                        limit=MAX_QUEUE_PER_EXECUTOR,
                    )
                    if pending_count >= MAX_QUEUE_PER_EXECUTOR:
                        code = ERR_CODE_COMFYUI_QUEUE_FULL if is_comfyui else ERR_CODE_COMMERCIAL_QUEUE_FULL
                        queue_name = "COMFYUI_QUEUE_FULL" if is_comfyui else "COMMERCIAL_QUEUE_FULL"
                        message = f"{queue_name}(limit={MAX_QUEUE_PER_EXECUTOR}, current={pending_count})"
                        raise HTTPException(status_code=429, detail=_format_task_error(code, message))
            request_payload = payload.model_dump()
            if executor_id and not request_payload.get("executorId"):
                request_payload["executorId"] = executor_id
            task_user_id, task_user_name = self._serialize_task_owner(user)
            task = AbilityTask(
                id=uuid4().hex,
                ability_id=ability.id,
                ability_name=ability.display_name,
                ability_provider=ability.provider,
                capability_key=ability.capability_key,
                user_id=task_user_id,
                user_name=task_user_name,
                status="queued",
                request_payload=request_payload,
                callback_url=payload.callbackUrl,
                callback_headers=payload.callbackHeaders,
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            task_data = self.to_dict(task)
        self._executor.submit(self._run_task, task.id)
        return task_data

    @staticmethod
    def _serialize_task_owner(user: User | None) -> tuple[str | None, str | None]:
        if not user:
            return None, None
        user_id = str(getattr(user, "id", "") or "").strip()
        user_name = getattr(user, "username", None)
        if user_id == "service":
            return None, user_name
        return user_id or None, user_name

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

    def _cleanup_stale_running_tasks(self) -> None:
        cutoff = datetime.utcnow() - timedelta(hours=CLEANUP_TTL_HOURS)
        with get_session() as session:
            stmt = (
                delete(AbilityTask)
                .where(AbilityTask.status == "running")
                .where(func.coalesce(AbilityTask.started_at, AbilityTask.updated_at, AbilityTask.created_at) < cutoff)
            )
            result = session.execute(stmt)
            session.commit()
            deleted = result.rowcount or 0
            if deleted:
                logger.info("Cleaned %s stale running ability tasks (>%sh).", deleted, CLEANUP_TTL_HOURS)

    def _start_cleanup_thread(self) -> None:
        def _loop() -> None:
            while True:
                try:
                    self._cleanup_stale_running_tasks()
                except Exception as exc:  # pragma: no cover - best effort cleanup
                    logger.warning("Cleanup stale ability tasks failed: %s", exc)
                time.sleep(CLEANUP_INTERVAL_SECONDS)

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()

    def _start_finalize_thread(self) -> None:
        def _loop() -> None:
            while True:
                try:
                    self._finalize_running_comfyui_tasks()
                    self._finalize_running_kie_tasks()
                except Exception as exc:  # pragma: no cover - best effort
                    logger.warning("Finalize ability tasks failed: %s", exc)
                time.sleep(FINALIZE_INTERVAL_SECONDS)

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()

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

    @staticmethod
    def _limit_comfyui_output_images(capability_key: str | None, images: list[dict[str, Any]]) -> list[dict[str, Any]]:
        key = str(capability_key or "").strip().lower()
        # 四方连续当前只需要最终成品图，忽略 workflow 偶发产出的额外图片。
        if key == "sifang_lianxu":
            return images[:1]
        return images

    @staticmethod
    def _touch_running_task(task_id: str) -> None:
        """Rotate finalize queue fairly: touched tasks move to the back by updated_at."""
        if not task_id:
            return
        try:
            with get_session() as session:
                db_task = session.get(AbilityTask, task_id)
                if not db_task or db_task.status != "running":
                    return
                db_task.updated_at = datetime.utcnow()
                session.add(db_task)
                session.commit()
        except Exception:
            return

    def _finalize_running_comfyui_tasks(self) -> None:
        with get_session() as session:
            rows = (
                session.execute(
                    select(AbilityTask)
                    .where(AbilityTask.status == "running")
                    .where(AbilityTask.ability_provider == "comfyui")
                    .order_by(AbilityTask.updated_at.asc())
                    .limit(FINALIZE_BATCH_SIZE)
                )
                .scalars()
                .all()
            )

        for task in rows:
            result_payload = task.result_payload or {}
            if not isinstance(result_payload, dict):
                continue
            meta = result_payload.get("metadata") if isinstance(result_payload.get("metadata"), dict) else {}
            prompt_id = meta.get("promptId") or meta.get("taskId")
            base_url = meta.get("baseUrl")
            executor_id = meta.get("executorId") or meta.get("executor")
            output_node_ids = meta.get("outputNodeIds") or meta.get("output_node_ids")
            if not (isinstance(prompt_id, str) and prompt_id.strip()):
                continue
            if not (isinstance(base_url, str) and base_url.strip()):
                continue

            # Prefer executor config when available (multi-ComfyUI routing).
            if isinstance(executor_id, str) and executor_id.strip():
                try:
                    from app.models.integration import Executor

                    with get_session() as session:
                        ex = session.get(Executor, executor_id.strip())
                        if ex:
                            cfg = ex.config or {}
                            ex_base = (ex.base_url or cfg.get("baseUrl") or cfg.get("base_url") or "").strip()
                            if ex_base:
                                base_url = ex_base
                except Exception:
                    pass

            try:
                # Avoid importing heavy modules unless needed.
                import httpx
                from types import SimpleNamespace

                from app.services.executors.base import ExecutionContext
                from app.services.executors.registry import registry
            except Exception:
                return

            adapter = registry.get("comfyui")
            if adapter is None:
                return

            try:
                history_url = f"{base_url.rstrip('/')}/history/{prompt_id}"
                resp = httpx.get(history_url, timeout=COMFYUI_HISTORY_TIMEOUT_SECONDS)
                if resp.status_code != 200:
                    raise RuntimeError(f"COMFYUI_HISTORY_HTTP_{resp.status_code}")
                data = resp.json()
                entry = None
                if isinstance(data, dict):
                    prompt_entry = data.get(prompt_id)
                    if isinstance(prompt_entry, dict):
                        entry = prompt_entry
                    elif isinstance(data.get("outputs"), dict):
                        # Some ComfyUI deployments return the history entry directly.
                        entry = data
                if not isinstance(entry, dict):
                    # History not ready yet (ComfyUI may still be writing prompt entry).
                    self._touch_running_task(task.id)
                    continue

                output_node_set = None
                if isinstance(output_node_ids, list):
                    output_node_set = {str(x) for x in output_node_ids if str(x).strip()}
                outputs = adapter._extract_outputs(entry, output_node_ids=output_node_set)  # type: ignore[attr-defined]
                hist = outputs.get("history") if isinstance(outputs, dict) else None
                status_dict = hist.get("status") if isinstance(hist, dict) else None
                status_str = str((status_dict or {}).get("status_str") or "").lower()

                if status_str == "error":
                    comfy_error = self._extract_comfyui_error_detail(hist if isinstance(hist, dict) else entry)
                    with get_session() as session:
                        db_task = session.get(AbilityTask, task.id)
                        if db_task:
                            db_task.status = "failed"
                            db_task.error_message = comfy_error or "COMFYUI_ERROR"
                            db_task.finished_at = datetime.utcnow()
                            session.add(db_task)
                            session.commit()
                            try:
                                ability_log_service.finish_failure(
                                    db_task.log_id,
                                    error_message=comfy_error or "COMFYUI_ERROR",
                                    response_payload=result_payload,
                                    duration_ms=db_task.duration_ms,
                                )
                            except Exception:
                                pass
                    continue

                if status_str != "success":
                    self._touch_running_task(task.id)
                    continue

                images = outputs.get("images") if isinstance(outputs, dict) else None
                if not isinstance(images, list) or not images:
                    self._touch_running_task(task.id)
                    continue
                images = self._limit_comfyui_output_images(task.capability_key, images)
                if not images:
                    self._touch_running_task(task.id)
                    continue

                ctx = ExecutionContext(
                    task=SimpleNamespace(id=task.id, user_id=task.user_id or "system", assets=[]),
                    workflow=SimpleNamespace(id="ability_finalize", definition={}, extra_metadata={}),
                    executor=SimpleNamespace(id=executor_id or "comfyui", base_url=base_url, config={}),
                    payload={},
                    api_key=None,
                )

                assets: list[dict[str, Any]] = []
                for img in images:
                    if not isinstance(img, dict):
                        continue
                    source_url = img.get("url") or adapter._build_image_url(base_url.rstrip("/"), img)  # type: ignore[attr-defined]
                    base64_data = img.get("base64")
                    if source_url:
                        asset = adapter._store_remote_asset(source_url, ctx, tag="comfyui")  # type: ignore[attr-defined]
                    elif base64_data:
                        asset = adapter._store_base64_asset(base64_data, ctx, tag="comfyui")  # type: ignore[attr-defined]
                    else:
                        asset = None
                    if asset:
                        assets.append(asset)

                if not assets:
                    self._touch_running_task(task.id)
                    continue

                finished_at = datetime.utcnow()
                with get_session() as session:
                    db_task = session.get(AbilityTask, task.id)
                    if not db_task:
                        continue
                    next_payload = dict(db_task.result_payload or {})
                    next_payload["images"] = assets
                    next_payload["assets"] = assets
                    next_payload["status"] = "succeeded"
                    next_payload["state"] = "success"
                    db_task.status = "succeeded"
                    db_task.result_payload = next_payload
                    db_task.finished_at = finished_at
                    db_task.error_message = None
                    if not db_task.duration_ms and db_task.started_at:
                        try:
                            db_task.duration_ms = int((finished_at - db_task.started_at).total_seconds() * 1000)
                        except Exception:
                            pass
                    session.add(db_task)
                    session.commit()
                    try:
                        ability_log_service.finish_success(
                            db_task.log_id,
                            response_payload=next_payload,
                            duration_ms=db_task.duration_ms,
                        )
                    except Exception:
                        pass
                    self._settle_success_wallet(task_id=task.id, db_task=db_task)
            except Exception as exc:
                # Best-effort; keep task running but record last hint for operators.
                with get_session() as session:
                    db_task = session.get(AbilityTask, task.id)
                    if db_task and db_task.status in {"queued", "running"}:
                        db_task.error_message = str(exc)[:240]
                        session.add(db_task)
                        session.commit()
                continue

    def _finalize_running_kie_tasks(self) -> None:
        settings = get_settings()
        timeout_seconds = int(getattr(settings, "kie_task_timeout_seconds", 0) or 0)
        now = datetime.utcnow()
        with get_session() as session:
            rows = (
                session.execute(
                    select(AbilityTask)
                    .where(AbilityTask.status == "running")
                    .where(AbilityTask.ability_provider == "kie")
                    .order_by(AbilityTask.updated_at.asc())
                    .limit(FINALIZE_BATCH_SIZE)
                )
                .scalars()
                .all()
            )

        for task in rows:
            result_payload = task.result_payload or {}
            if not isinstance(result_payload, dict):
                continue
            meta = result_payload.get("metadata") if isinstance(result_payload.get("metadata"), dict) else {}
            kie_task_id = meta.get("taskId") or result_payload.get("taskId")
            executor_id = meta.get("executorId") or result_payload.get("executorId") or result_payload.get("executor")
            if not (isinstance(kie_task_id, str) and kie_task_id.strip()):
                continue
            if not (isinstance(executor_id, str) and executor_id.strip()):
                continue

            started_at = task.started_at or task.created_at
            if timeout_seconds > 0 and started_at:
                elapsed = (now - started_at).total_seconds()
                if elapsed > timeout_seconds:
                    with get_session() as session:
                        db_task = session.get(AbilityTask, task.id)
                        if db_task:
                            db_task.status = "failed"
                            db_task.error_message = "KIE_TIMEOUT"
                            db_task.finished_at = datetime.utcnow()
                            try:
                                db_task.duration_ms = int(elapsed * 1000)
                            except Exception:
                                pass
                            session.add(db_task)
                            session.commit()
                            try:
                                ability_log_service.finish_failure(
                                    db_task.log_id,
                                    error_message="KIE_TIMEOUT",
                                    response_payload=result_payload,
                                    duration_ms=db_task.duration_ms,
                                )
                            except Exception:
                                pass
                    continue

            try:
                fetched = integration_test_service.fetch_kie_market_result(
                    executor_id=str(executor_id).strip(),
                    task_id=str(kie_task_id).strip(),
                    timeout=18.0,
                    max_retries=1,
                )
            except Exception:
                continue

            state = str(fetched.get("state") or "").lower()
            urls = fetched.get("resultUrls") if isinstance(fetched.get("resultUrls"), list) else []
            assets = fetched.get("storedAssets") if isinstance(fetched.get("storedAssets"), list) else []

            if state == "success" and (urls or assets):
                if not assets and urls:
                    assets = [{"url": u} for u in urls if isinstance(u, str) and u.strip()]
                next_payload = dict(result_payload)
                next_payload["images"] = assets
                next_payload["assets"] = assets
                next_payload["status"] = "succeeded"
                next_payload["state"] = state
                finished_at = datetime.utcnow()
                with get_session() as session:
                    db_task = session.get(AbilityTask, task.id)
                    if not db_task:
                        continue
                    db_task.status = "succeeded"
                    db_task.result_payload = next_payload
                    db_task.finished_at = finished_at
                    if not db_task.duration_ms and db_task.started_at:
                        try:
                            db_task.duration_ms = int((finished_at - db_task.started_at).total_seconds() * 1000)
                        except Exception:
                            pass
                    session.add(db_task)
                    session.commit()
                    try:
                        ability_log_service.finish_success(
                            db_task.log_id,
                            response_payload=next_payload,
                            duration_ms=db_task.duration_ms,
                        )
                    except Exception:
                        pass
                    self._settle_success_wallet(task_id=task.id, db_task=db_task)
                continue

            if state == "fail":
                error_message = self._extract_kie_error_message(fetched) or "KIE_TASK_FAILED"
                with get_session() as session:
                    db_task = session.get(AbilityTask, task.id)
                    if db_task:
                        db_task.status = "failed"
                        db_task.error_message = error_message
                        db_task.finished_at = datetime.utcnow()
                        session.add(db_task)
                        session.commit()
                        try:
                            ability_log_service.finish_failure(
                                db_task.log_id,
                                error_message=error_message,
                                response_payload=result_payload,
                                duration_ms=db_task.duration_ms,
                            )
                        except Exception:
                            pass
                continue

    @staticmethod
    def _extract_kie_error_message(payload: dict[str, Any] | None) -> str | None:
        if not isinstance(payload, dict):
            return None
        # Prefer explicit error fields in the payload.
        for key in ("error_message", "errorMessage", "error", "msg", "message", "detail"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                code = payload.get("code")
                if code not in (None, ""):
                    return f"{code} {val}".strip()
                return val.strip()

        # Look into raw response from KIE.
        raw = payload.get("raw")
        if isinstance(raw, dict):
            response = raw.get("response")
            if isinstance(response, str) and response.strip():
                return response.strip()
            if isinstance(response, dict):
                code = response.get("code")
                record = response.get("data")
                if isinstance(record, dict):
                    fail_msg = record.get("failMsg") or record.get("failMessage")
                    if isinstance(fail_msg, str) and fail_msg.strip():
                        fail_code = record.get("failCode") or record.get("code")
                        if fail_code not in (None, ""):
                            return f"{fail_code} {fail_msg}".strip()
                        return fail_msg.strip()
                    for key in ("errorMsg", "errorMessage", "error", "msg", "message", "detail"):
                        val = record.get(key)
                        if isinstance(val, str) and val.strip():
                            return val.strip()
                    result_json = record.get("resultJson")
                    if isinstance(result_json, dict):
                        for key in ("failMsg", "failMessage", "errorMsg", "errorMessage", "error", "msg", "message", "detail"):
                            val = result_json.get(key)
                            if isinstance(val, str) and val.strip():
                                return val.strip()
                for key in ("msg", "message", "error_message", "error", "detail"):
                    val = response.get(key)
                    if isinstance(val, str) and val.strip():
                        if code not in (None, ""):
                            return f"{code} {val}".strip()
                        return val.strip()

        # Some paths include parsed resultObject.
        result_object = payload.get("resultObject")
        if isinstance(result_object, dict):
            for key in ("errorMsg", "errorMessage", "error", "msg", "message", "detail"):
                val = result_object.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()

        return None

    @staticmethod
    def _resolve_invoke_status(raw_status: str | None) -> str:
        normalized = str(raw_status or "").strip().lower()
        if normalized in {"queued", "running"}:
            return "running"
        if normalized in {"failed", "error", "timeout", "rejected"}:
            return "failed"
        if normalized in {"cancelled", "canceled", "stopped", "aborted"}:
            return "cancelled"
        return "succeeded"

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _count_inputs(request_payload: dict[str, Any] | None) -> int:
        payload = request_payload if isinstance(request_payload, dict) else {}
        images = payload.get("images")
        if isinstance(images, list) and images:
            return len(images)
        if payload.get("imageUrl") or payload.get("imageBase64"):
            return 1
        inputs = payload.get("inputs")
        if isinstance(inputs, dict):
            for key in ("image_input", "input_urls", "image_urls", "image_list"):
                val = inputs.get(key)
                if isinstance(val, list) and val:
                    return len(val)
            if inputs.get("url") or inputs.get("image_url"):
                return 1
        return 0

    @staticmethod
    def _count_outputs(result_payload: dict[str, Any] | None) -> int:
        payload = result_payload if isinstance(result_payload, dict) else {}
        count = 0
        for key in ("images", "videos", "assets"):
            val = payload.get(key)
            if isinstance(val, list):
                count += len(val)
        return count

    def _settle_success_wallet(self, *, task_id: str, db_task: AbilityTask) -> None:
        settings = get_settings()
        if not bool(getattr(settings, "wallet_auto_expense_enabled", True)):
            return
        user_id = str(db_task.user_id or "").strip()
        if not user_id:
            return

        provider = str(db_task.ability_provider or "unknown")
        model_key = str(db_task.capability_key or "unknown")
        request_payload = db_task.request_payload if isinstance(db_task.request_payload, dict) else {}
        result_payload = db_task.result_payload if isinstance(db_task.result_payload, dict) else {}
        input_count = self._count_inputs(request_payload)
        output_count = self._count_outputs(result_payload)

        pricing_version = "v1"
        currency = "USD"
        total_cost: float | None = None
        unit_cost: float | None = None

        try:
            with get_session() as session:
                ability = session.get(Ability, db_task.ability_id)
                metadata = ability.extra_metadata if ability and isinstance(ability.extra_metadata, dict) else {}
                pricing = metadata.get("pricing") if isinstance(metadata, dict) else None
                if isinstance(pricing, dict):
                    pricing_version = str(
                        pricing.get("version")
                        or metadata.get("pricing_version")
                        or metadata.get("seed_version")
                        or "v1"
                    )
                    currency = str(pricing.get("currency") or "USD")
                    fallback_cost = self._safe_float(pricing.get("discount_price"))
                    if fallback_cost is None:
                        fallback_cost = self._safe_float(pricing.get("list_price"))
                    total_cost = fallback_cost

                if db_task.log_id:
                    log = session.get(AbilityInvocationLog, int(db_task.log_id))
                    if log:
                        if log.ability_provider:
                            provider = str(log.ability_provider)
                        if log.capability_key:
                            model_key = str(log.capability_key)
                        log_total = self._safe_float(log.cost_amount)
                        if log_total is not None:
                            total_cost = log_total
                        log_unit = self._safe_float(log.unit_price)
                        if log_unit is not None:
                            unit_cost = log_unit
                        if log.currency:
                            currency = str(log.currency)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("settle wallet metadata lookup failed for ability task %s: %s", task_id, exc)

        if unit_cost is None and total_cost is not None:
            divisor = max(1, output_count)
            unit_cost = total_cost / divisor

        try:
            wallet_service.record_task_cost_snapshot(
                task_id=task_id,
                user_id=user_id,
                provider=provider,
                model_key=model_key,
                input_count=input_count,
                output_count=output_count,
                unit_cost=unit_cost,
                total_cost=total_cost,
                pricing_version=pricing_version,
                currency=currency,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("record task cost snapshot failed for ability task %s: %s", task_id, exc)

        points = 0
        if total_cost is not None and total_cost > 0:
            rate = max(1, int(getattr(settings, "wallet_points_per_usd", 100) or 100))
            points = max(1, int(math.ceil(float(total_cost) * rate)))
        if points <= 0:
            return

        trace_id = f"ability_task:{task_id}"
        try:
            wallet_service.record_expense(
                user_id=user_id,
                points=points,
                task_id=task_id,
                trace_id=trace_id,
                provider=provider,
                model_key=model_key,
                description=f"ability task settle:{task_id}",
            )
        except HTTPException as exc:
            logger.warning("wallet settle rejected for ability task %s: %s", task_id, exc.detail)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("wallet settle failed for ability task %s: %s", task_id, exc)

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
                task_id=task_id,
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
                should_settle = False
                resolved_status = self._resolve_invoke_status(response.status)
                # Some abilities (e.g. long-running ComfyUI graphs) return status=running,
                # meaning we only submitted the job and will finalize later via polling.
                if resolved_status == "running":
                    db_task.status = "running"
                    db_task.finished_at = None
                    db_task.duration_ms = None
                    db_task.result_payload = response.model_dump()
                    db_task.log_id = response.logId
                    db_task.error_message = None
                elif resolved_status == "failed":
                    db_task.status = "failed"
                    db_task.finished_at = finished_at
                    db_task.duration_ms = duration
                    db_task.result_payload = response.model_dump()
                    db_task.log_id = response.logId
                    db_task.error_message = self._extract_kie_error_message(response.model_dump()) or "ABILITY_TASK_FAILED"
                elif resolved_status == "cancelled":
                    db_task.status = "cancelled"
                    db_task.finished_at = finished_at
                    db_task.duration_ms = duration
                    db_task.result_payload = response.model_dump()
                    db_task.log_id = response.logId
                    db_task.error_message = "ABILITY_TASK_CANCELLED"
                else:
                    db_task.status = "succeeded"
                    db_task.finished_at = finished_at
                    db_task.duration_ms = duration
                    db_task.result_payload = response.model_dump()
                    db_task.log_id = response.logId
                    db_task.error_message = None
                    should_settle = True
                session.add(db_task)
                session.commit()
                if should_settle:
                    self._settle_success_wallet(task_id=task_id, db_task=db_task)
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
    def _extract_comfyui_error_detail(history_entry: dict[str, Any] | None) -> str | None:
        if not isinstance(history_entry, dict):
            return None
        status = history_entry.get("status")
        if not isinstance(status, dict):
            return None
        messages = status.get("messages")
        if not isinstance(messages, list):
            return None
        for item in reversed(messages):
            if not (isinstance(item, list) and len(item) >= 2):
                continue
            event = str(item[0] or "").strip().lower()
            payload = item[1]
            if event != "execution_error" or not isinstance(payload, dict):
                continue
            node_id = str(payload.get("node_id") or "").strip()
            node_type = str(payload.get("node_type") or "").strip()
            exc_type = str(payload.get("exception_type") or "").strip()
            exc_msg = " ".join(str(payload.get("exception_message") or "").split())
            details: list[str] = []
            if node_id:
                if node_type:
                    details.append(f"node={node_id}:{node_type}")
                else:
                    details.append(f"node={node_id}")
            elif node_type:
                details.append(f"node={node_type}")
            if exc_type:
                details.append(f"type={exc_type}")
            prefix = f"COMFYUI_ERROR({', '.join(details)})" if details else "COMFYUI_ERROR"
            if exc_msg:
                # Keep payload concise for task list/CSV readability.
                if len(exc_msg) > 220:
                    exc_msg = f"{exc_msg[:217]}..."
                return f"{prefix}: {exc_msg}"
            return prefix
        return None

    @staticmethod
    def _format_error(exc: Exception) -> dict[str, Any]:
        if isinstance(exc, HTTPException):
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            return {"message": detail, "status_code": exc.status_code}
        return {"message": str(exc)}

    def count_pending_by_executor(
        self,
        *,
        executor_id: str | None,
        providers: list[str] | None = None,
        limit: int | None = None,
    ) -> int:
        if not executor_id:
            return 0
        normalized_executor = str(executor_id).strip()
        if not normalized_executor:
            return 0
        with get_session() as session:
            stmt = select(AbilityTask).where(AbilityTask.status.in_(["queued", "running"]))
            if providers:
                stmt = stmt.where(AbilityTask.ability_provider.in_([p for p in providers if p]))
            tasks = session.execute(stmt).scalars().all()
        count = 0
        for task in tasks:
            payload = task.request_payload or {}
            if not isinstance(payload, dict):
                continue
            if str(payload.get("executorId") or "").strip() != normalized_executor:
                continue
            count += 1
            if limit is not None and count >= limit:
                return count
        return count

    def to_dict(self, task: AbilityTask) -> dict[str, Any]:
        stage = derive_ability_task_status(
            status=task.status,
            started_at=task.started_at,
            finished_at=task.finished_at,
            error_message=task.error_message,
        )
        return {
            "id": task.id,
            "ability_id": task.ability_id,
            "ability_name": task.ability_name,
            "ability_provider": task.ability_provider,
            "capability_key": task.capability_key,
            "status": task.status,
            "submit_status": stage.submit_status,
            "callback_status": stage.callback_status,
            "final_status": stage.final_status,
            "error_code": stage.error_code,
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
