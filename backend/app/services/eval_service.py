"""Service for AI ability evaluation runs (Coze workflow -> optional PODI task polling)."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from functools import lru_cache
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.models.eval import EvalRun, EvalWorkflowVersion
from app.models.integration import AbilityTask
from app.schemas.abilities import AbilityImageInput, AbilityInvokeRequest
from app.schemas.business import BusinessRunCreateRequest
from app.services.auth_service import auth_service
from app.services.ability_task_service import get_ability_task_service
from app.services.business_runs import get_business_run_service
from app.services.coze_client import coze_client
from app.services.integration_test import integration_test_service
from app.services.task_id_codec import decode_task_id


_HEX_TASK_ID = re.compile(r"^[0-9a-f]{24,64}$")
EVAL_FINALIZE_INTERVAL_SECONDS = 3
EVAL_FINALIZE_BATCH_SIZE = 50
EVAL_RUN_TIMEOUT_SECONDS = 60 * 30
RECOVERABLE_BUSINESS_EVAL_ERROR_PREFIXES = (
    "BUSINESS_RUN_TIMEOUT:",
    "BUSINESS_RUN_GET_FAILED:",
    "BUSINESS_RUN_TEMPORARY_UNAVAILABLE:",
)


class EvalService:
    """Persisted evaluation runs with background execution in a bounded thread pool."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        settings = get_settings()
        total_workers = max(1, int(getattr(settings, "eval_run_max_workers", 6)))
        comfyui_workers = max(1, int(getattr(settings, "eval_comfyui_run_max_workers", 2)))
        commercial_workers = max(1, int(getattr(settings, "eval_commercial_run_max_workers", 4)))
        default_workers = max(1, int(getattr(settings, "eval_default_run_max_workers", 2)))
        # Keep each lane bounded; avoid accidental oversubscription when env is set too large.
        comfyui_workers = min(comfyui_workers, total_workers)
        commercial_workers = min(commercial_workers, total_workers)
        default_workers = min(default_workers, total_workers)
        self._lane_executors: dict[str, ThreadPoolExecutor] = {
            "comfyui": ThreadPoolExecutor(max_workers=comfyui_workers),
            "commercial": ThreadPoolExecutor(max_workers=commercial_workers),
            "default": ThreadPoolExecutor(max_workers=default_workers),
        }
        self._lock = threading.Lock()
        self._thread_started = False
        # Best-effort: never block API startup on evaluation bookkeeping.
        # (In reload mode, mapper initialization can be sensitive to import order.)
        try:
            self._resume_pending_runs()
            self._start_finalize_thread()
        except Exception as exc:  # pragma: no cover - defensive startup guard
            self._logger.warning("EvalService resume skipped: %s", exc)

    @staticmethod
    def _infer_provider_lane(
        workflow_version: EvalWorkflowVersion | None,
        parameters: dict[str, Any] | None,
    ) -> str:
        if isinstance(parameters, dict):
            explicit = str(
                parameters.get("__eval_provider_lane")
                or parameters.get("__provider_lane")
                or ""
            ).strip().lower()
            if explicit in {"comfyui", "commercial", "default"}:
                return explicit
            provider_hint = str(parameters.get("provider") or "").strip().lower()
            if provider_hint in {"comfyui", "commercial", "kie", "volcengine"}:
                return "comfyui" if provider_hint == "comfyui" else "commercial"
            if "moxing" in parameters:
                return "commercial"

        name_text = ""
        if workflow_version:
            name_text = f"{workflow_version.name or ''} {workflow_version.notes or ''}".lower()
        if "comfyui" in name_text:
            return "comfyui"
        commercial_keywords = (
            "商业模型",
            "commercial",
            "kie",
            "volc",
            "火山",
            "banana",
            "flux",
            "doubao",
            "seedream",
            "seedance",
        )
        if any(key in name_text for key in commercial_keywords):
            return "commercial"
        return "default"

    @staticmethod
    def _lane_from_parameters(parameters: dict[str, Any] | None) -> str:
        if not isinstance(parameters, dict):
            return "default"
        lane = str(parameters.get("__eval_provider_lane") or "").strip().lower()
        if lane in {"comfyui", "commercial", "default"}:
            return lane
        return "default"

    @staticmethod
    def _classify_eval_error(error: str | None) -> str:
        text = str(error or "").strip()
        lowered = text.lower()
        if not lowered:
            return "UNKNOWN"
        if "eof" in lowered or "connection reset" in lowered or "broken pipe" in lowered:
            return "NETWORK_EOF"
        if "timed out" in lowered or "timeout" in lowered:
            return "TIMEOUT"
        if "status=502" in lowered or "bad gateway" in lowered:
            return "HTTP_502"
        if "status=503" in lowered:
            return "HTTP_503"
        if "status=504" in lowered:
            return "HTTP_504"
        if "image_download_failed" in lowered:
            return "IMAGE_DOWNLOAD_FAILED"
        if "coze_workflow_error" in lowered:
            return "COZE_WORKFLOW_ERROR"
        if "coze_history_failed" in lowered:
            return "COZE_HISTORY_FAILED"
        if "coze_submit_failed" in lowered:
            return "COZE_SUBMIT_FAILED"
        if "task_timeout" in lowered:
            return "TASK_TIMEOUT"
        if "task_images_empty" in lowered:
            return "TASK_IMAGES_EMPTY"
        if "callback_images_empty" in lowered:
            return "CALLBACK_IMAGES_EMPTY"
        if "output_no_images" in lowered or "output_empty" in lowered:
            return "OUTPUT_EMPTY"
        return "UNKNOWN"

    @classmethod
    def _is_retryable_eval_error(cls, error: str | None) -> bool:
        kind = cls._classify_eval_error(error)
        return kind in {"NETWORK_EOF", "TIMEOUT", "HTTP_502", "HTTP_503", "HTTP_504", "COZE_HISTORY_FAILED"}

    @classmethod
    def _format_eval_error(cls, error: str | None) -> str:
        text = str(error or "").strip() or "UNKNOWN"
        return f"{cls._classify_eval_error(text)}:{text}"

    @classmethod
    def _summarize_fanout_errors(cls, errors: list[str]) -> str | None:
        if not errors:
            return None
        counts: dict[str, int] = {}
        normalized: list[str] = []
        for err in errors:
            formatted = cls._format_eval_error(err)
            normalized.append(formatted)
            kind = formatted.split(":", 1)[0]
            counts[kind] = counts.get(kind, 0) + 1
        summary = ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items()))
        details = " | ".join(normalized[:5]) + (" ..." if len(normalized) > 5 else "")
        return f"FANOUT_PARTIAL_FAILED[{summary}]: {details}"

    @staticmethod
    def _describe_ability_task_state(task_row: AbilityTask | None) -> str:
        if not task_row:
            return "TASK_NOT_FOUND"
        result_payload = task_row.result_payload or {}
        meta = result_payload.get("metadata") if isinstance(result_payload, dict) else {}
        parts = [
            f"status={task_row.status}",
            f"provider={task_row.ability_provider}",
            f"capability={task_row.capability_key}",
        ]
        if isinstance(meta, dict):
            executor_id = meta.get("executorId")
            prompt_id = meta.get("promptId") or meta.get("taskId")
            if executor_id:
                parts.append(f"executor={executor_id}")
            if prompt_id:
                parts.append(f"promptId={prompt_id}")
        if task_row.error_message:
            parts.append(f"error={str(task_row.error_message)[:240]}")
        if isinstance(result_payload, dict):
            images = result_payload.get("images")
            if isinstance(images, list):
                parts.append(f"imageCount={len(images)}")
        return ";".join(parts)

    @staticmethod
    def _extract_image_urls_from_task_payload(result_payload: Any) -> list[str]:
        image_urls: list[str] = []
        if not isinstance(result_payload, dict):
            return image_urls
        images = result_payload.get("images") or []
        if not isinstance(images, list):
            return image_urls
        for it in images:
            if not isinstance(it, dict):
                continue
            for key in ("storedUrl", "ossUrl", "sourceUrl", "url"):
                value = it.get(key)
                if isinstance(value, str) and value.strip():
                    image_urls.append(value.strip())
                    break
        return image_urls

    @staticmethod
    def _clean_eval_runtime_params(parameters: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(parameters, dict):
            return {}
        return {
            key: value
            for key, value in parameters.items()
            if not str(key).startswith("__") and value is not None
        }

    @staticmethod
    def _first_param_string(parameters: dict[str, Any], keys: list[str]) -> str:
        for key in keys:
            value = parameters.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if value is not None and not isinstance(value, (dict, list)):
                text = str(value).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _elapsed_ms_since(created_at: datetime | None) -> int:
        if not created_at:
            return 0
        return max(0, int((datetime.utcnow() - created_at).total_seconds() * 1000))

    def _submit_run(self, run_id: str, parameters: dict[str, Any] | None) -> None:
        lane = self._lane_from_parameters(parameters)
        executor = self._lane_executors.get(lane) or self._lane_executors["default"]
        executor.submit(self._execute_run, run_id)

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
        batch_request_key = str(normalized_params.get("__batch_request_key") or "").strip()
        if batch_request_key:
            req_key_expr = func.json_unquote(func.json_extract(EvalRun.parameters_json, "$.__batch_request_key"))
            existing = db.execute(
                select(EvalRun).where(req_key_expr == batch_request_key).limit(1)
            ).scalar_one_or_none()
            if existing:
                return existing
        urls = [u for u in (input_oss_urls or []) if isinstance(u, str) and u.strip()]
        if urls:
            # Keep the convention: single image input uses `url` (string).
            normalized_params.setdefault("url", urls[0])
            if len(urls) > 1:
                normalized_params.setdefault("urls", urls)
            # Compat for some Coze workflows that use different casing.
            for alias in ("Url", "URL"):
                normalized_params.setdefault(alias, urls[0])

        # Coze will hard-fail if a workflow declares required params but they're missing.
        # Some workflows require `prompt` even when we want "no prompt" behavior; use a
        # whitespace prompt to satisfy Coze validation while keeping semantics neutral.
        schema = workflow_version.parameters_schema or {}
        fields = schema.get("fields") if isinstance(schema, dict) else None
        if isinstance(fields, list):
            for f in fields:
                if not isinstance(f, dict):
                    continue
                if f.get("name") != "prompt" or not f.get("required"):
                    continue
                v = normalized_params.get("prompt")
                if v is None or (isinstance(v, str) and not v.strip()):
                    normalized_params["prompt"] = " "

        def _strip_px(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return str(int(value))
            if not isinstance(value, str):
                return None
            raw = value.strip()
            if not raw:
                return None
            # Accept "200", "200px", "200 px", "200PX"
            num = ""
            for ch in raw:
                if ch.isdigit():
                    num += ch
                elif num:
                    break
            return num or None

        # Normalize numeric pixel params (strip "px" suffixes if present).
        pixel_keys = {
            "width",
            "height",
            "expand_left",
            "expand_right",
            "expand_top",
            "expand_bottom",
            "expandLeft",
            "expandRight",
            "expandTop",
            "expandBottom",
            "left",
            "right",
            "top",
            "bottom",
            "bianchang",
        }
        for key in list(normalized_params.keys()):
            if key not in pixel_keys:
                continue
            stripped = _strip_px(normalized_params.get(key))
            if stripped is not None:
                normalized_params[key] = stripped
        normalized_params["__eval_provider_lane"] = self._infer_provider_lane(workflow_version, normalized_params)

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

        self._submit_run(run.id, normalized_params)
        return run

    @staticmethod
    def _workflow_expects_callback(output_schema: dict[str, Any] | list[Any] | str | None) -> bool:
        """Best-effort: infer whether a workflow returns a callback task id in `output`."""
        schema: dict[str, Any] | list[Any] | str = output_schema or {}
        if isinstance(schema, str):
            raw = schema.strip()
            if raw:
                try:
                    schema = json.loads(raw)
                except json.JSONDecodeError:
                    schema = {}
        if isinstance(schema, list):
            schema = {"fields": schema}
        fields = schema.get("fields") if isinstance(schema, dict) else None
        if not isinstance(fields, list):
            return False
        for f in fields:
            if not isinstance(f, dict) or f.get("name") != "output":
                continue
            desc = str(f.get("description") or "")
            if "task" in desc.lower() or "回调" in desc:
                return True
        return False

    @staticmethod
    def _pop_fanout_count(params: dict[str, Any]) -> int:
        """Extract internal fan-out count (裂变数量) from params.

        This is a PODI evaluation-only control parameter and should NOT be sent to Coze,
        because most workflows don't declare it in their schema.
        """

        for key in ("count", "generateCount", "variantCount", "n"):
            if key not in params:
                continue
            raw = params.pop(key, None)
            try:
                value = int(str(raw).strip())
            except Exception:
                value = 0
            if value > 0:
                return min(value, 20)  # safety cap
        return 1

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
        pending_rows: list[tuple[str, dict[str, Any] | None]] = []
        business_rows: list[tuple[str, str, dict[str, Any] | None]] = []
        with get_session() as session:
            rows = (
                session.execute(
                    select(
                        EvalRun.id,
                        EvalRun.parameters_json,
                        EvalRun.podi_task_id,
                        EvalRun.coze_execute_id,
                        EvalRun.result_output_json,
                        EvalWorkflowVersion.extra_metadata,
                    )
                    .join(EvalWorkflowVersion, EvalWorkflowVersion.id == EvalRun.workflow_version_id, isouter=True)
                    .where(EvalRun.status.in_(["queued", "running"]))
                )
                .all()
            )
            for row in rows:
                run_id = str(row[0])
                parameters = row[1] if isinstance(row[1], dict) else None
                podi_task_id = str(row[2] or "").strip()
                coze_execute_id = str(row[3] or "").strip()
                business_run_id = ""
                if self._is_business_eval_metadata(row[5]):
                    business_run_id = self._extract_business_run_id(row[4])
                if business_run_id:
                    business_rows.append((run_id, business_run_id, parameters))
                elif not podi_task_id and not coze_execute_id:
                    pending_rows.append((run_id, parameters))
            pending_ids = [run_id for run_id, _ in pending_rows]
            business_ids = [run_id for run_id, _, _ in business_rows]
            running_ids = [
                str(row[0])
                for row in rows
                if str(row[2] or "").strip() or str(row[3] or "").strip()
            ]
            if pending_ids:
                session.execute(
                    EvalRun.__table__.update()
                    .where(EvalRun.id.in_(pending_ids))
                    .values(status="queued")
                )
            if business_ids:
                session.execute(
                    EvalRun.__table__.update()
                    .where(EvalRun.id.in_(business_ids))
                    .values(status="running")
                )
            if running_ids:
                session.execute(
                    EvalRun.__table__.update()
                    .where(EvalRun.id.in_(running_ids))
                    .values(status="running")
                )
            if pending_ids or business_ids or running_ids:
                session.commit()
        for run_id, parameters in pending_rows:
            self._submit_run(str(run_id), parameters if isinstance(parameters, dict) else None)
        for run_id, business_run_id, parameters in business_rows:
            self._submit_business_resume(str(run_id), business_run_id, parameters if isinstance(parameters, dict) else None)

    def _start_finalize_thread(self) -> None:
        if self._thread_started:
            return
        self._thread_started = True

        def _loop() -> None:
            while True:
                try:
                    self._finalize_pending_runs()
                except Exception as exc:  # pragma: no cover - background best effort
                    self._logger.warning("eval finalize loop failed: %s", exc)
                time.sleep(EVAL_FINALIZE_INTERVAL_SECONDS)

        threading.Thread(target=_loop, daemon=True, name="podi-eval-finalizer").start()

    def _finalize_pending_runs(self) -> None:
        with get_session() as session:
            rows = (
                session.execute(
                    select(EvalRun, EvalWorkflowVersion.extra_metadata)
                    .join(EvalWorkflowVersion, EvalWorkflowVersion.id == EvalRun.workflow_version_id, isouter=True)
                    .where(EvalRun.status.in_(["queued", "running"]))
                    .order_by(EvalRun.updated_at.asc())
                    .limit(EVAL_FINALIZE_BATCH_SIZE)
                )
                .all()
            )
            snapshots = [
                {
                    "run_id": run.id,
                    "workflow_version_id": run.workflow_version_id,
                    "coze_execute_id": run.coze_execute_id,
                    "podi_task_id": run.podi_task_id,
                    "business_run_id": self._extract_business_run_id(run.result_output_json)
                    if self._is_business_eval_metadata(metadata)
                    else "",
                    "created_at": run.created_at,
                }
                for run, metadata in rows
            ]

        for item in snapshots:
            run_id = str(item["run_id"])
            business_run_id = str(item.get("business_run_id") or "").strip()
            podi_task_id = str(item.get("podi_task_id") or "").strip()
            coze_execute_id = str(item.get("coze_execute_id") or "").strip()
            if business_run_id:
                self._finalize_business_run_once(
                    run_id=run_id,
                    business_run_id=business_run_id,
                )
                continue
            if podi_task_id:
                self._finalize_ability_task_run_once(
                    run_id=run_id,
                    task_id=podi_task_id,
                    output_json=None,
                    created_at=item.get("created_at"),
                )
                continue
            if coze_execute_id:
                self._finalize_coze_async_run_once(
                    run_id=run_id,
                    workflow_version_id=str(item.get("workflow_version_id") or ""),
                    execute_id=coze_execute_id,
                    created_at=item.get("created_at"),
                )
        self._finalize_recoverable_business_eval_runs()

    def _finalize_recoverable_business_eval_runs(self) -> None:
        """Recover eval rows whose display status lagged behind the business run."""

        with get_session() as session:
            rows = (
                session.execute(
                    select(EvalRun.id, EvalRun.result_output_json, EvalRun.error_message)
                    .where(EvalRun.status == "failed")
                    .where(
                        or_(
                            *[
                                EvalRun.error_message.like(f"{prefix}%")
                                for prefix in RECOVERABLE_BUSINESS_EVAL_ERROR_PREFIXES
                            ]
                        )
                    )
                    .order_by(EvalRun.updated_at.asc())
                    .limit(20)
                )
                .all()
            )
        for row in rows:
            business_run_id = self._extract_business_run_id(row.result_output_json) or self._extract_business_run_id(
                row.error_message
            )
            if not business_run_id:
                continue
            self._finalize_business_run_once(run_id=str(row.id), business_run_id=business_run_id)

    def reconcile_business_run_for_eval(self, run_id: str) -> bool:
        """Synchronously recover one stale business eval row before returning it to the UI."""

        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            return False
        with get_session() as session:
            run = session.get(EvalRun, normalized_run_id)
            if not run or str(run.status or "").lower() != "failed":
                return False
            error = str(run.error_message or "")
            if not error.startswith(RECOVERABLE_BUSINESS_EVAL_ERROR_PREFIXES):
                return False
            business_run_id = self._extract_business_run_id(run.result_output_json) or self._extract_business_run_id(
                error
            )
        if not business_run_id:
            return False
        self._finalize_business_run_once(run_id=normalized_run_id, business_run_id=business_run_id)
        return True

    def reconcile_business_timeout_run(self, run_id: str) -> bool:
        return self.reconcile_business_run_for_eval(run_id)

    @staticmethod
    def _append_run_images(run_id: str, *, image_urls: list[str]) -> None:
        if not image_urls:
            return
        cleaned: list[str] = []
        for u in image_urls:
            if not isinstance(u, str):
                continue
            s = u.strip()
            if not s:
                continue
            cleaned.append(s)
        if not cleaned:
            return
        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if not run:
                return
            cur = run.result_image_urls_json or []
            seen = set(cur)
            for u in cleaned:
                if u in seen:
                    continue
                cur.append(u)
                seen.add(u)
            run.result_image_urls_json = cur
            session.add(run)
            session.commit()

    def _execute_native_eval_run(
        self,
        *,
        run_id: str,
        execution_config: dict[str, Any],
        parameters: dict[str, Any],
        started: float,
    ) -> bool:
        mode = str(execution_config.get("mode") or "").strip().lower()
        if mode == "business_run":
            self._execute_business_eval_run(
                run_id=run_id,
                execution_config=execution_config,
                parameters=parameters,
                started=started,
            )
            return True
        if mode == "ability_task":
            self._execute_ability_task_eval_run(
                run_id=run_id,
                execution_config=execution_config,
                parameters=parameters,
                started=started,
            )
            return True
        return False

    def _execute_business_eval_run(
        self,
        *,
        run_id: str,
        execution_config: dict[str, Any],
        parameters: dict[str, Any],
        started: float,
    ) -> None:
        clean_params = self._clean_eval_runtime_params(parameters)
        image_url = self._first_param_string(clean_params, ["imageUrl", "image_url", "url", "Url", "URL"])
        if not image_url:
            self._mark_failed(run_id, message="BUSINESS_IMAGE_URL_REQUIRED", started=started)
            return
        payload_data = {
            key: value
            for key, value in clean_params.items()
            if key not in {"Url", "URL", "image_url"}
        }
        payload_data["imageUrl"] = image_url
        payload_data["url"] = image_url
        version = str(execution_config.get("version") or "").strip()
        if version:
            payload_data["version"] = version
        payload_data.setdefault("source", "eval")
        payload_data.setdefault("channel", "eval-web")
        metadata = payload_data.get("metadata") if isinstance(payload_data.get("metadata"), dict) else {}
        metadata = {**metadata, "evalRunId": run_id, "evalExecutionMode": "business_run"}
        payload_data["metadata"] = metadata
        business_key = str(execution_config.get("business_key") or "").strip()
        if not business_key:
            self._mark_failed(run_id, message="BUSINESS_KEY_MISSING", started=started)
            return
        try:
            payload = BusinessRunCreateRequest.model_validate(payload_data)
            service_user = auth_service.build_service_user()
            business_run = get_business_run_service().create_run(
                business_key=business_key,
                payload=payload,
                user=service_user,
                source="eval",
            )
        except HTTPException as exc:
            self._mark_failed(run_id, message=str(exc.detail), started=started)
            return
        except Exception as exc:  # pragma: no cover - defensive
            self._mark_failed(run_id, message=f"BUSINESS_RUN_CREATE_FAILED:{exc}", started=started)
            return

        business_run_id = str(business_run.get("id") or business_run.get("runId") or "").strip()
        task_id = self._decode_business_task_id(business_run.get("ability_task_id") or business_run.get("taskId"))
        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if run:
                run.status = "running"
                run.podi_task_id = task_id or None
                run.result_output_json = {
                    "businessRunId": business_run_id,
                    "businessKey": business_key,
                    "version": version or business_run.get("version"),
                    "status": business_run.get("status"),
                }
                session.add(run)
                session.commit()
        if not business_run_id:
            self._mark_failed(run_id, message="BUSINESS_RUN_ID_MISSING", started=started)
            return
        self._poll_business_run(run_id=run_id, business_run_id=business_run_id, started=started)

    def _poll_business_run(self, *, run_id: str, business_run_id: str, started: float) -> None:
        deadline = time.monotonic() + 60 * 30
        interval = 2.0
        service_user = auth_service.build_service_user()
        last_payload: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            try:
                payload = get_business_run_service().get_run(run_id=business_run_id, user=service_user)
            except HTTPException as exc:
                self._mark_failed(run_id, message=str(exc.detail), started=started)
                return
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.exception(
                    "eval business run polling failed: eval_run_id=%s business_run_id=%s",
                    run_id,
                    business_run_id,
                )
                self._mark_failed(run_id, message="BUSINESS_RUN_GET_FAILED:业务任务结果查询失败，请稍后重试", started=started)
                return
            last_payload = payload if isinstance(payload, dict) else {}
            status = str(last_payload.get("status") or "").strip().lower()
            task_id = self._decode_business_task_id(last_payload.get("ability_task_id") or last_payload.get("taskId"))
            with get_session() as session:
                run = session.get(EvalRun, run_id)
                if run:
                    run.status = "running" if status in {"queued", "running", "pending", "planned"} else run.status
                    run.podi_task_id = task_id or run.podi_task_id
                    run.result_output_json = self._business_eval_output_summary(last_payload)
                    session.add(run)
                    session.commit()
            if status == "succeeded":
                self._mark_succeeded(
                    run_id,
                    image_urls=[str(x) for x in (last_payload.get("image_urls") or last_payload.get("imageUrls") or []) if str(x).strip()],
                    output_json=self._business_eval_output_summary(last_payload),
                    started=started,
                )
                return
            if status in {"failed", "cancelled"}:
                message = str(last_payload.get("error_message") or last_payload.get("error") or f"BUSINESS_RUN_{status.upper()}")
                if status == "failed" and self._is_transient_business_poll_error(message, started=started):
                    time.sleep(interval)
                    interval = min(interval * 1.25, 10.0)
                    continue
                self._mark_failed(
                    run_id,
                    message=message,
                    started=started,
                )
                return
            time.sleep(interval)
            interval = min(interval * 1.25, 10.0)
        detail = self._business_eval_output_summary(last_payload or {})
        self._mark_failed(run_id, message=f"BUSINESS_RUN_TIMEOUT:{detail}", started=started)

    def _finalize_business_run_once(self, *, run_id: str, business_run_id: str) -> None:
        service_user = auth_service.build_service_user()
        try:
            payload = get_business_run_service().get_run(run_id=business_run_id, user=service_user)
        except HTTPException as exc:
            detail = str(exc.detail)
            if self._is_retryable_eval_error(detail):
                return
            self._mark_failed(run_id, message=detail, started=None)
            return
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.warning(
                "eval business run finalize failed: eval_run_id=%s business_run_id=%s error=%s",
                run_id,
                business_run_id,
                exc,
            )
            return

        payload = payload if isinstance(payload, dict) else {}
        status = str(payload.get("status") or "").strip().lower()
        output_summary = self._business_eval_output_summary(payload)
        task_id = self._decode_business_task_id(payload.get("ability_task_id") or payload.get("taskId"))
        if status == "succeeded":
            self._mark_succeeded(
                run_id,
                image_urls=[str(x) for x in (payload.get("image_urls") or payload.get("imageUrls") or []) if str(x).strip()],
                output_json=output_summary,
                started=None,
            )
            return
        if status in {"failed", "cancelled"}:
            self._mark_failed(
                run_id,
                message=str(payload.get("error_message") or payload.get("error") or f"BUSINESS_RUN_{status.upper()}"),
                started=None,
            )
            return
        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if run:
                run.status = "running"
                run.podi_task_id = task_id or run.podi_task_id
                run.result_output_json = output_summary
                session.add(run)
                session.commit()

    @staticmethod
    def _business_eval_output_summary(payload: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "id",
            "runId",
            "business_key",
            "businessKey",
            "version",
            "status",
            "ability_task_id",
            "taskId",
            "ability_name",
            "abilityName",
            "image_urls",
            "imageUrls",
            "texts",
            "error_message",
            "error",
            "route_info",
            "routeInfo",
            "steps",
        )
        summary = {key: payload.get(key) for key in keys if key in payload and key != "steps"}
        steps = payload.get("steps")
        if isinstance(steps, list):
            summary["steps"] = [EvalService._business_run_step_list_summary(step) for step in steps[:8] if isinstance(step, dict)]
            summary["stepCount"] = len(steps)
        return EvalService._json_safe_payload(summary)

    @staticmethod
    def _business_run_step_list_summary(step: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "id",
            "stepId",
            "display_name",
            "displayName",
            "role",
            "status",
            "ability_id",
            "abilityId",
            "ability_name",
            "abilityName",
            "duration_ms",
            "durationMs",
            "error_message",
            "error",
        )
        return {key: step.get(key) for key in keys if key in step}

    @staticmethod
    def _decode_business_task_id(value: Any) -> str:
        return str(decode_task_id(value) or "").strip()

    @staticmethod
    def _is_transient_business_poll_error(message: str, *, started: float) -> bool:
        normalized = str(message or "").strip().upper()
        if normalized not in {"TASK_NOT_FOUND"}:
            return False
        # Business runs may create the primary task after a VL step; during that
        # short window, run finalization can briefly observe an unresolved task.
        return time.monotonic() - started < 180

    @staticmethod
    def _json_safe_payload(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): EvalService._json_safe_payload(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [EvalService._json_safe_payload(item) for item in value]
        return value

    @staticmethod
    def _is_business_eval_metadata(metadata: Any) -> bool:
        if not isinstance(metadata, dict):
            return False
        execution = metadata.get("eval_execution")
        return isinstance(execution, dict) and str(execution.get("mode") or "").strip().lower() == "business_run"

    @staticmethod
    def _extract_business_run_id(output: Any) -> str:
        if isinstance(output, str):
            raw = output.strip()
            if not raw:
                return ""
            if raw.startswith(RECOVERABLE_BUSINESS_EVAL_ERROR_PREFIXES):
                raw = raw.split(":", 1)[1].strip()
            try:
                output = json.loads(raw)
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(raw)
                    output = parsed if isinstance(parsed, dict) else raw
                except (SyntaxError, ValueError):
                    for key in ("businessRunId", "business_run_id", "runId", "run_id", "id"):
                        match = re.search(rf"['\"]{key}['\"]\s*:\s*['\"]([^'\"]+)['\"]", raw)
                        if match:
                            return match.group(1).strip()
                    return ""
        if not isinstance(output, dict):
            return ""
        for key in ("businessRunId", "business_run_id", "runId", "run_id", "id"):
            value = str(output.get(key) or "").strip()
            if value:
                return value
        nested = output.get("businessRun") or output.get("business_run")
        if isinstance(nested, dict):
            return EvalService._extract_business_run_id(nested)
        return ""

    def _submit_business_resume(
        self,
        run_id: str,
        business_run_id: str,
        parameters: dict[str, Any] | None,
    ) -> None:
        lane = self._lane_from_parameters(parameters)
        executor = self._lane_executors.get(lane) or self._lane_executors["default"]
        executor.submit(self._poll_business_run, run_id=run_id, business_run_id=business_run_id, started=time.monotonic())

    def _execute_ability_task_eval_run(
        self,
        *,
        run_id: str,
        execution_config: dict[str, Any],
        parameters: dict[str, Any],
        started: float,
    ) -> None:
        ability_id = str(execution_config.get("ability_id") or "").strip()
        if not ability_id:
            self._mark_failed(run_id, message="ABILITY_ID_MISSING", started=started)
            return
        clean_params = self._clean_eval_runtime_params(parameters)
        image_fields = [
            str(item).strip()
            for item in (execution_config.get("image_fields") or [])
            if str(item).strip()
        ]
        images: list[AbilityImageInput] = []
        for field in image_fields:
            value = self._first_param_string(clean_params, [field])
            if value:
                images.append(AbilityImageInput(name=field, url=value))
        image_url = self._first_param_string(clean_params, ["imageUrl", "image_url", "url", "Url", "URL"])
        inputs = {
            key: value
            for key, value in clean_params.items()
            if key not in {"imageUrl", "image_url", "url", "Url", "URL"}
        }
        metadata = {
            "source": "eval",
            "evalRunId": run_id,
            "evalExecutionMode": "ability_task",
        }
        try:
            task = get_ability_task_service().enqueue(
                ability_id=ability_id,
                payload=AbilityInvokeRequest(
                    imageUrl=image_url or None,
                    images=images or None,
                    inputs=inputs,
                    metadata=metadata,
                ),
                user=auth_service.build_service_user(),
            )
        except HTTPException as exc:
            self._mark_failed(run_id, message=str(exc.detail), started=started)
            return
        except Exception as exc:  # pragma: no cover - defensive
            self._mark_failed(run_id, message=f"ABILITY_TASK_CREATE_FAILED:{exc}", started=started)
            return
        task_id = str(task.get("id") or "").strip()
        if not task_id:
            self._mark_failed(run_id, message="ABILITY_TASK_ID_MISSING", started=started)
            return
        self._poll_ability_task(run_id=run_id, task_id=task_id, started=started)

    def _submit_coze_async_run(
        self,
        *,
        run_id: str,
        workflow_id: str,
        coze_params: dict[str, Any],
    ) -> tuple[bool, str | None]:
        params = coze_params.copy()
        last_error: str | None = None
        for _ in range(2):
            try:
                resp = coze_client.run_workflow(
                    workflow_id=workflow_id,
                    parameters=params,
                    is_async=True,
                    request_id=run_id,
                    max_retries=1,
                )
            except HTTPException as exc:
                return False, str(exc.detail)
            except Exception as exc:  # pragma: no cover - defensive
                return False, str(exc)

            base_resp = resp.get("BaseResp") or {}
            status_code = base_resp.get("StatusCode")
            code = resp.get("code")
            if (isinstance(code, int) and code != 0) or (isinstance(status_code, int) and status_code != 0):
                msg = resp.get("msg") or base_resp.get("StatusMessage") or "COZE_SUBMIT_FAILED"
                if (
                    isinstance(code, int)
                    and code == 4000
                    and isinstance(msg, str)
                    and "Missing required parameters" in msg
                ):
                    patched = self._patch_missing_required_params(params, msg)
                    if patched:
                        params = patched
                        continue
                return False, f"COZE_SUBMIT_FAILED code={code} statusCode={status_code} msg={msg}"

            execute_id = str(resp.get("execute_id") or "").strip()
            debug_url = str(resp.get("debug_url") or "").strip()
            if not execute_id:
                last_error = "COZE_SUBMIT_MISSING_EXECUTE_ID"
                continue
            with get_session() as session:
                run = session.get(EvalRun, run_id)
                if run:
                    run.status = "running"
                    run.coze_execute_id = execute_id
                    run.coze_debug_url = debug_url or run.coze_debug_url
                    session.add(run)
                    session.commit()
            return True, None
        return False, last_error or "COZE_SUBMIT_FAILED"

    def _attach_ability_task_run(self, *, run_id: str, task_id: str, output_json: Any | None) -> None:
        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if not run:
                return
            run.status = "running"
            run.podi_task_id = task_id
            if output_json is not None:
                run.result_output_json = output_json
            session.add(run)
            session.commit()

    def _finalize_coze_async_run_once(
        self,
        *,
        run_id: str,
        workflow_version_id: str,
        execute_id: str,
        created_at: datetime | None,
    ) -> None:
        if created_at and (datetime.utcnow() - created_at).total_seconds() > EVAL_RUN_TIMEOUT_SECONDS:
            self._mark_failed(run_id, message="COZE_ASYNC_TIMEOUT", started=None)
            return
        with get_session() as session:
            workflow_version = session.get(EvalWorkflowVersion, workflow_version_id)
            if not workflow_version:
                self._mark_failed(run_id, message="WORKFLOW_VERSION_NOT_FOUND", started=None)
                return
            workflow_id = str(workflow_version.workflow_id)
            expects_callback = self._workflow_expects_callback(workflow_version.output_schema)

        try:
            hist = coze_client.get_workflow_run_history(execute_id=execute_id, workflow_id=workflow_id)
        except HTTPException as exc:
            detail = str(exc.detail)
            if self._is_retryable_eval_error(detail):
                return
            self._mark_failed(run_id, message=detail, started=None)
            return
        except Exception as exc:  # pragma: no cover - defensive
            self._mark_failed(run_id, message=str(exc), started=None)
            return

        base_resp = hist.get("BaseResp") or {}
        status_code = base_resp.get("StatusCode")
        code = hist.get("code")
        if (isinstance(code, int) and code != 0) or (isinstance(status_code, int) and status_code != 0):
            msg = hist.get("msg") or base_resp.get("StatusMessage") or "COZE_HISTORY_FAILED"
            self._mark_failed(run_id, message=f"COZE_HISTORY_FAILED code={code} statusCode={status_code} msg={msg}", started=None)
            return

        parsed = self._parse_coze_payload(hist)
        if isinstance(parsed, dict):
            if isinstance(parsed.get("$error"), str) and parsed.get("$error"):
                self._mark_failed(run_id, message=f"COZE_WORKFLOW_ERROR: {parsed.get('$error')}", started=None)
                return
            if isinstance(parsed.get("error_msg"), str) and parsed.get("error_msg"):
                self._mark_failed(run_id, message=f"COZE_WORKFLOW_ERROR: {parsed.get('error_msg')}", started=None)
                return
            tool_error = self._extract_workflow_tool_error(parsed)
            if tool_error:
                self._mark_failed(run_id, message=tool_error, started=None)
                return

        image_urls = self._extract_image_urls(parsed)
        output = parsed.get("output")
        output_present = output is not None and not (isinstance(output, str) and not output.strip())
        if image_urls:
            self._mark_succeeded(run_id, image_urls=image_urls, output_json=self._extract_output_json(parsed), started=None)
            return
        if not output_present:
            status = parsed.get("status") or parsed.get("run_status") or parsed.get("state")
            if isinstance(status, str) and status.lower() in {"failed", "error", "canceled", "cancelled"}:
                self._mark_failed(run_id, message=f"COZE_RUN_{status}", started=None)
            return

        podi_task_id: str | None
        if expects_callback and isinstance(output, str) and output.strip():
            podi_task_id = decode_task_id(output.strip())
        else:
            podi_task_id = decode_task_id(self._guess_podi_task_id(parsed, output))
        if not podi_task_id:
            output_json = self._extract_output_json(parsed)
            if output_json is not None:
                self._mark_succeeded(run_id, image_urls=[], output_json=output_json, started=None)
                return
            self._mark_failed(run_id, message=f"OUTPUT_NO_IMAGES output={str(output)[:128]}", started=None)
            return

        with get_session() as session:
            task_row = session.get(AbilityTask, podi_task_id)
        if not task_row:
            # Coze may expose a task id before our DB transaction is visible.
            return
        output_json = self._extract_output_json(parsed)
        self._attach_ability_task_run(run_id=run_id, task_id=podi_task_id, output_json=output_json)
        self._finalize_ability_task_run_once(
            run_id=run_id,
            task_id=podi_task_id,
            output_json=output_json,
            created_at=created_at,
        )

    def _finalize_ability_task_run_once(
        self,
        *,
        run_id: str,
        task_id: str,
        output_json: Any | None,
        created_at: datetime | None,
    ) -> None:
        if created_at and (datetime.utcnow() - created_at).total_seconds() > EVAL_RUN_TIMEOUT_SECONDS:
            self._mark_failed(run_id, message="TASK_TIMEOUT", started=None)
            return
        with get_session() as session:
            task_row = session.get(AbilityTask, task_id)
            if not task_row:
                self._mark_failed(run_id, message="TASK_NOT_FOUND", started=None)
                return
            status = task_row.status
            result_payload = task_row.result_payload if isinstance(task_row.result_payload, dict) else {}
            error_message = task_row.error_message

        if status == "succeeded":
            if output_json is None:
                output_json = self._extract_output_json(result_payload) or result_payload
            self._mark_succeeded(
                run_id,
                image_urls=self._extract_image_urls_from_task_payload(result_payload),
                output_json=output_json,
                started=None,
            )
            return
        if status == "failed":
            self._mark_failed(run_id, message=error_message or "TASK_FAILED", started=None)
            return
        self._try_finalize_comfyui_task(task_id=task_id)
        self._try_finalize_kie_task(task_id=task_id)

    def _execute_run(self, run_id: str) -> None:
        started = time.monotonic()
        settings = get_settings()
        # Avoid using ORM instances outside the session scope (commit expires attrs by default).
        workflow_id: str | None = None
        expects_callback = False
        native_eval_execution: dict[str, Any] | None = None
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
            expects_callback = self._workflow_expects_callback(workflow_version.output_schema)
            metadata = workflow_version.extra_metadata if isinstance(workflow_version.extra_metadata, dict) else {}
            raw_execution = metadata.get("eval_execution") if isinstance(metadata.get("eval_execution"), dict) else None
            native_eval_execution = raw_execution.copy() if raw_execution else None
            run.status = "running"
            session.add(run)
            session.commit()

        try:
            if native_eval_execution and self._execute_native_eval_run(
                run_id=run_id,
                execution_config=native_eval_execution,
                parameters=run_parameters,
                started=started,
            ):
                return
            # Execute the workflow (non-streaming). OpenAPI tokens are handled by coze_client.
            if not workflow_id:
                raise RuntimeError("WORKFLOW_ID_MISSING")

            # Fan-out (裂变数量): run the same workflow multiple times and aggregate images.
            # Note: `count` is an internal eval control param and is not sent to Coze.
            coze_params = run_parameters.copy()
            # Internal scheduler flags for eval UI should never be sent to Coze.
            coze_params.pop("__eval_batch_mode", None)
            coze_params.pop("__batch_session_id", None)
            coze_params.pop("__batch_source_key", None)
            coze_params.pop("__batch_file_name", None)
            coze_params.pop("__batch_repeat_index", None)
            coze_params.pop("__batch_request_key", None)
            coze_params.pop("__batch_expected_total", None)
            coze_params.pop("__batch_expected_images", None)
            coze_params.pop("__batch_expected_repeat", None)
            coze_params.pop("__eval_provider_lane", None)
            # UI uses `similarity`; Coze workflows expect legacy `bili`.
            if "bili" not in coze_params and "similarity" in coze_params:
                coze_params["bili"] = coze_params.get("similarity")
            coze_params.pop("similarity", None)
            # Outpaint workflows now use lowercase `url`; keep a compatibility alias if needed.
            if workflow_id in {"7597723984687267840", "7598587935331450880"}:
                if "url" not in coze_params and "Url" in coze_params:
                    coze_params["url"] = coze_params.get("Url")
            fanout = self._pop_fanout_count(coze_params)
            if fanout > 1:
                # Stable default: allow forcing sequential fan-out (max_workers=1) to
                # reduce pressure on Coze/tools and avoid connection resets under load.
                max_workers = min(fanout, max(1, int(getattr(settings, "eval_fanout_max_workers", 1))))
                all_images: list[str] = []
                errors: list[str] = []
                last_debug_url: str | None = None
                last_execute_id: str | None = None

                if max_workers <= 1:
                    # Sequential fan-out (stable mode).
                    for _ in range(fanout):
                        imgs, err, execute_id, debug_url = self._run_coze_async_item_with_retry(
                            run_id,
                            workflow_id,
                            coze_params,
                            settings,
                            expects_callback,
                        )
                        if imgs:
                            all_images.extend(imgs)
                            self._append_run_images(run_id, image_urls=imgs)
                        if err:
                            errors.append(err)
                        if debug_url:
                            last_debug_url = debug_url
                        if execute_id:
                            last_execute_id = execute_id
                else:
                    with ThreadPoolExecutor(max_workers=max_workers) as pool:
                        futures = [
                            pool.submit(
                                self._run_coze_async_item_with_retry,
                                run_id,
                                workflow_id,
                                coze_params,
                                settings,
                                expects_callback,
                            )
                            for _ in range(fanout)
                        ]
                        for fut in as_completed(futures):
                            imgs, err, execute_id, debug_url = fut.result()
                            if imgs:
                                all_images.extend(imgs)
                                self._append_run_images(run_id, image_urls=imgs)
                            if err:
                                errors.append(err)
                            if debug_url:
                                last_debug_url = debug_url
                            if execute_id:
                                last_execute_id = execute_id

                # De-dup while preserving order.
                seen: set[str] = set()
                dedup: list[str] = []
                for u in all_images:
                    if u in seen:
                        continue
                    seen.add(u)
                    dedup.append(u)

                with get_session() as session:
                    run = session.get(EvalRun, run_id)
                    if run:
                        run.coze_execute_id = last_execute_id or run.coze_execute_id
                        run.coze_debug_url = last_debug_url or run.coze_debug_url
                        session.add(run)
                        session.commit()

                if dedup:
                    warn = self._summarize_fanout_errors(errors)
                    self._mark_succeeded(run_id, image_urls=dedup, output_json=None, started=started, error_message=warn)
                    return
                primary_error = self._summarize_fanout_errors(errors) or "FANOUT_EMPTY"
                self._mark_failed(run_id, message=primary_error, started=started)
                return

            submitted, submit_error = self._submit_coze_async_run(
                run_id=run_id,
                workflow_id=workflow_id,
                coze_params=coze_params,
            )
            if submitted:
                return
            self._mark_failed(run_id, message=submit_error or "COZE_SUBMIT_FAILED", started=started)
            return

            # Primary path: sync run (lower overhead).
            # Fallback: if Coze blocks longer than our HTTP timeout (common for long-running
            # generation workflows), switch to async submit + run_history polling.
            try:
                response = coze_client.run_workflow(
                    workflow_id=workflow_id,
                    parameters=coze_params,
                    is_async=False,
                    request_id=run_id,
                    max_retries=1,
                )
            except HTTPException as exc:
                detail = str(getattr(exc, "detail", "") or "")
                lowered = detail.lower()
                is_timeout = "coze_request_failed" in lowered and ("timed out" in lowered or "timeout" in lowered)
                if is_timeout:
                    imgs, err, execute_id, debug_url = self._run_coze_async_item_with_retry(
                        run_id,
                        workflow_id,
                        coze_params,
                        settings,
                        expects_callback,
                    )
                    with get_session() as session:
                        run = session.get(EvalRun, run_id)
                        if run:
                            run.coze_execute_id = execute_id or run.coze_execute_id
                            run.coze_debug_url = debug_url or run.coze_debug_url
                            session.add(run)
                            session.commit()
                    if imgs:
                        self._mark_succeeded(run_id, image_urls=imgs, output_json=None, started=started, error_message=None)
                    else:
                        self._mark_failed(run_id, message=err or "COZE_ASYNC_EMPTY", started=started)
                    return
                raise

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

            # Coze can return HTTP 200 with a non-zero `code` (or BaseResp.StatusCode) for failures.
            base_resp = response.get("BaseResp") or {}
            status_code = base_resp.get("StatusCode")
            code = response.get("code")
            if (isinstance(code, int) and code != 0) or (isinstance(status_code, int) and status_code != 0):
                msg = response.get("msg") or base_resp.get("StatusMessage") or "COZE_EXECUTION_FAILED"

                # Coze validates required parameters before running nodes. Some workflows
                # may mark common fields like height/width as required. If callers omit them
                # (or send empty), Coze returns code=4000 with a "Missing required parameters"
                # message. We apply a best-effort fallback and retry once so UI users don't
                # get stuck with a hard failure for "obvious defaults".
                if (
                    isinstance(code, int)
                    and code == 4000
                    and isinstance(msg, str)
                    and "Missing required parameters" in msg
                ):
                    patched = self._patch_missing_required_params(run_parameters, msg)
                    if patched:
                        response = coze_client.run_workflow(
                            workflow_id=workflow_id,
                            parameters=patched,
                            is_async=False,
                            request_id=run_id,
                            max_retries=1,
                        )
                        base_resp = response.get("BaseResp") or {}
                        status_code = base_resp.get("StatusCode")
                        code = response.get("code")
                        if (isinstance(code, int) and code != 0) or (
                            isinstance(status_code, int) and status_code != 0
                        ):
                            msg = response.get("msg") or base_resp.get("StatusMessage") or "COZE_EXECUTION_FAILED"
                        else:
                            # Continue normal success path below.
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

                # Still failed after optional patch+retry.
                self._mark_failed(
                    run_id,
                    message=f"COZE_FAILED code={code} statusCode={status_code} msg={msg} debugUrl={debug_url}",
                    started=started,
                )
                return

            parsed = self._parse_coze_payload(response)
            # Some Coze workflows return a structured error payload even with HTTP 200.
            if isinstance(parsed, dict):
                if isinstance(parsed.get("$error"), str) and parsed.get("$error"):
                    self._mark_failed(
                        run_id,
                        message=f"COZE_WORKFLOW_ERROR: {parsed.get('$error')}",
                        started=started,
                    )
                    return
                if isinstance(parsed.get("error_msg"), str) and parsed.get("error_msg"):
                    self._mark_failed(
                        run_id,
                        message=f"COZE_WORKFLOW_ERROR: {parsed.get('error_msg')}",
                        started=started,
                    )
                    return

            output = parsed.get("output")
            podi_task_id: str | None = None
            if expects_callback and isinstance(output, str) and output.strip():
                # Callback workflows are expected to return the task id in `output`,
                # which may not be a hex string (e.g. snowflake ids).
                podi_task_id = decode_task_id(output.strip())
            else:
                podi_task_id = decode_task_id(self._guess_podi_task_id(parsed, output))
            if podi_task_id:
                # Prefer PODI ability_tasks.
                with get_session() as session:
                    task_row = session.get(AbilityTask, podi_task_id)
                if task_row:
                    output_json = self._extract_output_json(parsed)
                    self._poll_ability_task(run_id=run_id, task_id=podi_task_id, started=started, output_json=output_json)
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
            output_json = self._extract_output_json(parsed)
            # Callback workflows must eventually return a task id (then we resolve it to images).
            # If Coze returns an empty string while the job is still processing, we should not
            # silently mark success with empty outputs.
            if expects_callback and not image_urls:
                if not (isinstance(output, str) and output.strip()):
                    self._mark_failed(run_id, message="CALLBACK_OUTPUT_EMPTY", started=started)
                    return
            if expects_callback and not image_urls and isinstance(output, str) and output.strip():
                self._mark_failed(
                    run_id,
                    message=f"CALLBACK_TASK_NOT_RESOLVED output={output.strip()[:128]}",
                    started=started,
                )
                return
            self._mark_succeeded(run_id, image_urls=image_urls, output_json=output_json, started=started)
        except HTTPException as exc:
            self._mark_failed(run_id, message=str(exc.detail), started=started)
        except Exception as exc:  # pragma: no cover - defensive
            self._mark_failed(run_id, message=str(exc), started=started)

    @staticmethod
    def _patch_missing_required_params(
        params: dict[str, Any],
        msg: str,
    ) -> dict[str, Any] | None:
        """Best-effort patch for Coze code=4000 missing required parameters.

        Coze error messages can look like:
          "Missing required parameters：'height'. ..."
        We parse the missing field name(s) and fill with safe defaults.
        """

        missing = set(re.findall(r"'([^']+)'", msg or ""))
        if not missing:
            return None

        patched = params.copy()
        changed = False
        for name in missing:
            if name in patched and patched[name] is not None and str(patched[name]).strip():
                continue
            key = str(name)
            # Common numeric-like fields: provide conservative defaults as strings.
            if key in {"height", "width"}:
                patched[key] = "1024"
                changed = True
                continue
            if key.startswith("expand_"):
                patched[key] = "0"
                changed = True
                continue
            if key in {"dpi", "pdi"}:
                patched[key] = "300"
                changed = True
                continue
            # Generic: provide a whitespace string so it is "present" and non-empty.
            patched[key] = " "
            changed = True

        return patched if changed else None

    def _run_coze_async_item(
        self,
        run_id: str,
        workflow_id: str,
        coze_params: dict[str, Any],
        settings: Any,
        expects_callback: bool,
    ) -> tuple[list[str], str | None, str | None, str | None]:
        """Submit+poll one Coze run via async mode; return resolved image URLs.

        Returns: (image_urls, error_message, execute_id, debug_url)
        """

        def _is_transient(msg: str) -> bool:
            lowered = (msg or "").lower()
            return any(
                key in lowered
                for key in (
                    "timeout",
                    "temporarily",
                    "rate",
                    "too many",
                    "bad gateway",
                    "gateway timeout",
                    "502",
                    "503",
                    "504",
                    "coze_invalid_response",
                )
            )

        params = coze_params.copy()
        execute_id: str | None = None
        debug_url: str | None = None

        # 1) Submit (async). Avoid aggressive retries to prevent duplicate jobs when
        # network is flaky (Coze may still accept the first request).
        last_err: str | None = None
        for attempt in range(2):
            try:
                resp = coze_client.run_workflow(
                    workflow_id=workflow_id,
                    parameters=params,
                    is_async=True,
                    request_id=run_id,
                    max_retries=1,
                )
                base_resp = resp.get("BaseResp") or {}
                status_code = base_resp.get("StatusCode")
                code = resp.get("code")
                if (isinstance(code, int) and code != 0) or (isinstance(status_code, int) and status_code != 0):
                    msg = resp.get("msg") or base_resp.get("StatusMessage") or "COZE_SUBMIT_FAILED"
                    if (
                        isinstance(code, int)
                        and code == 4000
                        and isinstance(msg, str)
                        and "Missing required parameters" in msg
                    ):
                        patched = self._patch_missing_required_params(params, msg)
                        if patched:
                            params = patched
                            continue
                    last_err = f"COZE_SUBMIT_FAILED code={code} statusCode={status_code} msg={msg}"
                    return [], last_err, None, None

                execute_id = str(resp.get("execute_id") or "").strip() or None
                debug_url = str(resp.get("debug_url") or "").strip() or None
                if execute_id:
                    break
                last_err = "COZE_SUBMIT_MISSING_EXECUTE_ID"
            except HTTPException as exc:
                last_err = str(exc.detail)
                return [], last_err, None, None
            except Exception as exc:  # pragma: no cover - defensive
                last_err = str(exc)
                return [], last_err, None, None

        if not execute_id:
            return [], last_err or "COZE_SUBMIT_FAILED", None, debug_url

        # 2) Poll run history until output appears or failure.
        deadline = time.monotonic() + 60 * 20  # 20 minutes max
        interval = 1.2
        while time.monotonic() < deadline:
            try:
                hist = coze_client.get_workflow_run_history(execute_id=execute_id, workflow_id=workflow_id)
            except HTTPException as exc:
                detail = str(exc.detail)
                if _is_transient(detail):
                    time.sleep(interval)
                    interval = min(interval * 1.4, 8.0)
                    continue
                return [], detail, execute_id, debug_url
            base_resp = hist.get("BaseResp") or {}
            status_code = base_resp.get("StatusCode")
            code = hist.get("code")
            if (isinstance(code, int) and code != 0) or (isinstance(status_code, int) and status_code != 0):
                msg = hist.get("msg") or base_resp.get("StatusMessage") or "COZE_HISTORY_FAILED"
                return [], f"COZE_HISTORY_FAILED code={code} statusCode={status_code} msg={msg}", execute_id, debug_url

            parsed = self._parse_coze_payload(hist)
            # Coze may surface node failures as a JSON `{ "$error": "..." }` output.
            if isinstance(parsed, dict):
                if isinstance(parsed.get("$error"), str) and parsed.get("$error"):
                    return [], f"COZE_WORKFLOW_ERROR: {parsed.get('$error')}", execute_id, debug_url
                if isinstance(parsed.get("error_msg"), str) and parsed.get("error_msg"):
                    return [], f"COZE_WORKFLOW_ERROR: {parsed.get('error_msg')}", execute_id, debug_url
                tool_error = self._extract_workflow_tool_error(parsed)
                if tool_error:
                    return [], tool_error, execute_id, debug_url
            images = self._extract_image_urls(parsed)
            output = parsed.get("output")
            # Treat empty-string output as "not ready yet" (common while tools are still running).
            output_present = output is not None and not (isinstance(output, str) and not output.strip())
            if images or output_present:
                podi_task_id: str | None = None
                if expects_callback and isinstance(output, str) and output.strip():
                    podi_task_id = decode_task_id(output.strip())
                else:
                    podi_task_id = decode_task_id(self._guess_podi_task_id(parsed, output))
                if podi_task_id:
                    with get_session() as session:
                        task_row = session.get(AbilityTask, podi_task_id)
                    if task_row:
                        imgs, task_diag = self._poll_ability_task_inline(task_id=podi_task_id)
                        if imgs:
                            return imgs, None, execute_id, debug_url
                        return [], f"TASK_IMAGES_EMPTY:{task_diag}", execute_id, debug_url
                    callback_wf = settings.coze_comfyui_callback_workflow_id
                    if callback_wf:
                        imgs = self._poll_callback_images(callback_workflow_id=callback_wf, taskid=podi_task_id)
                        if imgs:
                            return imgs, None, execute_id, debug_url
                        return [], "CALLBACK_IMAGES_EMPTY", execute_id, debug_url
                if images:
                    return images, None, execute_id, debug_url
                return [], f"OUTPUT_NO_IMAGES output={str(output)[:128]}", execute_id, debug_url

            status = parsed.get("status") or parsed.get("run_status") or parsed.get("state")
            if isinstance(status, str) and status.lower() in {"failed", "error", "canceled", "cancelled"}:
                return [], f"COZE_RUN_{status}", execute_id, debug_url

            time.sleep(interval)
            interval = min(interval * 1.4, 8.0)

        return [], "COZE_ASYNC_TIMEOUT", execute_id, debug_url

    def _run_coze_async_item_with_retry(
        self,
        run_id: str,
        workflow_id: str,
        coze_params: dict[str, Any],
        settings: Any,
        expects_callback: bool,
    ) -> tuple[list[str], str | None, str | None, str | None]:
        attempts = 0
        last_result: tuple[list[str], str | None, str | None, str | None] = ([], None, None, None)
        while attempts < 2:
            attempts += 1
            imgs, err, execute_id, debug_url = self._run_coze_async_item(
                run_id,
                workflow_id,
                coze_params,
                settings,
                expects_callback,
            )
            last_result = (imgs, err, execute_id, debug_url)
            if imgs or not self._is_retryable_eval_error(err) or attempts >= 2:
                return last_result
            self._logger.warning(
                "Eval fanout transient error, retrying workflow_id=%s attempt=%s err=%s",
                workflow_id,
                attempts,
                err,
            )
            time.sleep(1.2 * attempts)
        return last_result

    @staticmethod
    def _parse_coze_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize Coze response to a dict with parsed `data`.

        Coze `/v1/workflow/get_run_history` commonly returns:
        - data: [{..., input: "<json str>", output: "<json str>", execute_status: "...", ...}]
        We should parse the inner `output` JSON (not the entire record), otherwise we may
        mistakenly treat debug/input URLs as "image outputs".
        """
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
        if isinstance(data, list):
            # Run history: pick the latest record and parse its `output` JSON.
            if data:
                last = data[-1]
                if isinstance(last, dict):
                    out = last.get("output")
                    run_status = last.get("execute_status") or last.get("executeStatus") or last.get("status")
                    debug_url = last.get("debug_url") or last.get("debugUrl")
                    error_msg = last.get("error_msg") or last.get("errorMsg")

                    parsed_out: dict[str, Any] | None = None
                    if isinstance(out, str):
                        try:
                            maybe = json.loads(out)
                            if isinstance(maybe, dict):
                                parsed_out = maybe
                            else:
                                parsed_out = {"output": maybe}
                        except Exception:
                            parsed_out = {"output": out}
                    elif isinstance(out, dict):
                        parsed_out = out
                    elif out is not None:
                        parsed_out = {"output": out}

                    if isinstance(parsed_out, dict):
                        # Attach minimal metadata so callers can show status/debug links.
                        if run_status is not None and "run_status" not in parsed_out and "status" not in parsed_out:
                            parsed_out["run_status"] = run_status
                        if debug_url and "debug_url" not in parsed_out:
                            parsed_out["debug_url"] = debug_url
                        if error_msg and "error_msg" not in parsed_out:
                            parsed_out["error_msg"] = error_msg
                        return parsed_out

            # Fallback: keep the list under a predictable key; callers can recursively scan it.
            return {"output": data}
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
    def _format_tool_error(code: Any, message: Any) -> str:
        safe_code = str(code or "COZE_TOOL_FAILED").strip() or "COZE_TOOL_FAILED"
        safe_message = " ".join(str(message or safe_code).strip().split())
        safe_message = safe_message.replace("|", "/")
        return f"ERR|{safe_code}|{safe_message}"

    @classmethod
    def _extract_workflow_tool_error(cls, payload: dict[str, Any]) -> str | None:
        """Detect tool-level failures returned inside a successful Coze run.

        Coze can mark a workflow execution as Success even when a plugin tool
        returns `taskStatus=failed`, for example queue-full responses from PODI.
        Eval runs must fail immediately instead of waiting until async timeout.
        """

        def _scan(value: Any, *, depth: int = 0) -> str | None:
            if depth > 5:
                return None
            if isinstance(value, str):
                text = value.strip()
                if text.startswith("ERR|"):
                    return text
                return None
            if isinstance(value, list):
                for item in value:
                    found = _scan(item, depth=depth + 1)
                    if found:
                        return found
                return None
            if not isinstance(value, dict):
                return None

            task_id = value.get("taskId") or value.get("task_id") or value.get("output")
            if isinstance(task_id, str) and task_id.strip().startswith("ERR|"):
                return task_id.strip()

            status = str(value.get("taskStatus") or value.get("task_status") or "").strip().lower()
            code = value.get("errorCode") or value.get("error_code")
            message = (
                value.get("debugResponse")
                or value.get("debug_response")
                or value.get("error_message")
                or value.get("error")
                or value.get("text")
            )
            if status == "failed" and (code or message):
                return cls._format_tool_error(code, message)
            if isinstance(message, str) and any(
                marker in message
                for marker in ("COMFYUI_QUEUE_FULL", "COMMERCIAL_QUEUE_FULL", "PROMPT_REQUIRED")
            ):
                inferred_code = code
                if not inferred_code and "COMFYUI_QUEUE_FULL" in message:
                    inferred_code = "Q1001"
                if not inferred_code and "COMMERCIAL_QUEUE_FULL" in message:
                    inferred_code = "Q2001"
                return cls._format_tool_error(inferred_code, message)

            for item in value.values():
                found = _scan(item, depth=depth + 1)
                if found:
                    return found
            return None

        return _scan(payload)

    @staticmethod
    def _extract_image_urls(payload: dict[str, Any]) -> list[str]:
        """Extract image URLs from common workflow outputs."""
        candidates: list[str] = []

        def _looks_like_image_url(url: str) -> bool:
            u = url.strip()
            if not u.startswith(("http://", "https://")):
                return False
            lower = u.lower()
            # Exclude known non-image URLs that sometimes appear in debug payloads.
            if "/work_flow" in lower or "/workflow" in lower and "execute_id=" in lower:
                return False
            if "execute_mode=" in lower and "execute_id=" in lower:
                return False
            # Accept common image/video extensions.
            if re.search(r"\.(png|jpe?g|webp|gif|bmp|mp4)(\\?|$)", lower):
                return True
            # Accept ComfyUI /view?filename=xxx.png style URLs.
            if "filename=" in lower and re.search(r"filename=[^&]+\\.(png|jpe?g|webp|gif|bmp)", lower):
                return True
            return False

        def _push(value: Any) -> None:
            if isinstance(value, str) and _looks_like_image_url(value):
                candidates.append(value)

        def _scan_any(value: Any, *, depth: int = 0) -> None:
            # Coze workflows are not consistent: outputs may be nested under `output`,
            # `data`, arrays, or custom fields. We do a bounded recursive scan as a
            # last-resort so "success but empty output" becomes less common.
            if depth > 6:
                return
            if len(candidates) >= 50:
                return
            if isinstance(value, str):
                _push(value)
                return
            if isinstance(value, dict):
                for v in value.values():
                    _scan_any(v, depth=depth + 1)
                return
            if isinstance(value, list):
                for item in value:
                    _scan_any(item, depth=depth + 1)
                return

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
        # Fallback: recursively scan the payload for any http(s) string.
        if not candidates:
            _scan_any(payload)

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

    def _poll_ability_task_inline(self, *, task_id: str) -> tuple[list[str], str]:
        """Poll an ability_task and return image URLs + final diagnostic (for fan-out runs)."""
        deadline = time.monotonic() + 60 * 20  # 20 minutes max
        interval = 1.5
        attempts = 0
        last_diag = "TASK_POLL_NOT_STARTED"

        while time.monotonic() < deadline:
            with get_session() as session:
                task_row = session.get(AbilityTask, task_id)
                if not task_row:
                    return [], "TASK_NOT_FOUND"
                task = get_ability_task_service().to_dict(task_row)
                last_diag = self._describe_ability_task_state(task_row)

            status = task.get("status")
            if status == "succeeded":
                result_payload = task.get("result_payload") or {}
                image_urls: list[str] = []
                if isinstance(result_payload, dict):
                    images = result_payload.get("images") or []
                    if isinstance(images, list):
                        for it in images:
                            if not isinstance(it, dict):
                                continue
                            for k in ("storedUrl", "ossUrl", "sourceUrl", "url"):
                                v = it.get(k)
                                if isinstance(v, str) and v.strip():
                                    image_urls.append(v.strip())
                                    break
                return image_urls, self._describe_ability_task_state(task_row)

            if status == "failed":
                return [], self._describe_ability_task_state(task_row)

            # For long-running ComfyUI "submit only" tasks, the DB row stays running until we
            # finalize it by polling ComfyUI /history and ingesting outputs. Coze normally
            # triggers this via `/api/coze/podi/tasks/get`, but eval polling should be able
            # to finalize on its own (otherwise "generated but never refreshed" happens).
            attempts += 1
            if attempts % 3 == 0:
                self._try_finalize_comfyui_task(task_id=task_id)
                self._try_finalize_kie_task(task_id=task_id)

            time.sleep(interval)
            interval = min(interval * 1.3, 10.0)

        return [], f"TASK_TIMEOUT:{last_diag}"

    def _poll_ability_task(self, *, run_id: str, task_id: str, started: float, output_json: Any | None = None) -> None:
        deadline = time.monotonic() + 60 * 20  # 20 minutes max
        interval = 1.5
        last_status: str | None = None
        attempts = 0

        while time.monotonic() < deadline:
            with get_session() as session:
                task_row = session.get(AbilityTask, task_id)
                if not task_row:
                    self._mark_failed(run_id, message="TASK_NOT_FOUND", started=started)
                    return
                task = get_ability_task_service().to_dict(task_row)
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
                            for k in ("storedUrl", "ossUrl", "sourceUrl", "url"):
                                v = it.get(k)
                                if isinstance(v, str) and v.strip():
                                    image_urls.append(v.strip())
                                    break
                if output_json is None and isinstance(result_payload, dict):
                    output_json = self._extract_output_json(result_payload) or result_payload
                self._mark_succeeded(run_id, image_urls=image_urls, output_json=output_json, started=started)
                return

            if status == "failed":
                self._mark_failed(run_id, message=task.get("error_message") or "TASK_FAILED", started=started)
                return

            attempts += 1
            if attempts % 3 == 0:
                # Try to finalize ComfyUI submitted-only tasks.
                self._try_finalize_comfyui_task(task_id=task_id)
                self._try_finalize_kie_task(task_id=task_id)

            time.sleep(interval)
            interval = min(interval * 1.3, 10.0)

        self._mark_failed(run_id, message="TASK_TIMEOUT", started=started)

    def _try_finalize_comfyui_task(self, *, task_id: str) -> None:
        """Best-effort: finalize a ComfyUI submitted-only task by polling /history.

        This mirrors the behavior in `/api/coze/podi/tasks/get` so eval runs can refresh
        without relying on a separate Coze callback workflow.
        """

        with get_session() as session:
            task_row = session.get(AbilityTask, task_id)
            if not task_row:
                return
            if (task_row.ability_provider or "").lower() != "comfyui":
                return
            capability_key = str(task_row.capability_key or "").strip().lower()
            if task_row.status not in {"queued", "running"}:
                return
            result_payload = task_row.result_payload or {}
            if not isinstance(result_payload, dict):
                return
            meta = result_payload.get("metadata") if isinstance(result_payload.get("metadata"), dict) else {}
            prompt_id = meta.get("promptId") or meta.get("taskId")
            base_url = meta.get("baseUrl")
            executor_id = meta.get("executorId")
            output_node_ids = meta.get("outputNodeIds") or meta.get("output_node_ids")
            # Multi-ComfyUI support: prefer executor config if available.
            if isinstance(executor_id, str) and executor_id.strip():
                try:
                    from app.models.integration import Executor

                    ex = session.get(Executor, executor_id.strip())
                    if ex:
                        cfg = ex.config or {}
                        ex_base = (ex.base_url or cfg.get("baseUrl") or cfg.get("base_url") or "").strip()
                        if ex_base:
                            base_url = ex_base
                except Exception:
                    pass

            if not (isinstance(prompt_id, str) and prompt_id.strip() and isinstance(base_url, str) and base_url.strip()):
                return

        # Avoid importing heavy modules unless needed.
        try:
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
            resp = httpx.get(history_url, timeout=15)
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
                return

            output_node_set = None
            if isinstance(output_node_ids, list):
                output_node_set = {str(x) for x in output_node_ids if str(x).strip()}
            outputs = adapter._extract_outputs(entry, output_node_ids=output_node_set)  # type: ignore[attr-defined]
            hist = outputs.get("history") if isinstance(outputs, dict) else None
            status_dict = hist.get("status") if isinstance(hist, dict) else None
            status_str = str((status_dict or {}).get("status_str") or "").lower()

            if status_str == "error":
                with get_session() as session:
                    db_task = session.get(AbilityTask, task_id)
                    if db_task:
                        db_task.status = "failed"
                        db_task.error_message = "COMFYUI_ERROR"
                        session.add(db_task)
                        session.commit()
                return
            if status_str != "success":
                return

            images = outputs.get("images") if isinstance(outputs, dict) else None
            if not isinstance(images, list) or not images:
                return
            if capability_key == "sifang_lianxu":
                images = images[:1]
                if not images:
                    return

            ctx = ExecutionContext(
                task=SimpleNamespace(id=task_id, user_id="eval", assets=[]),
                workflow=SimpleNamespace(id="eval_finalize", definition={}, extra_metadata={}),
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
                return

            with get_session() as session:
                db_task = session.get(AbilityTask, task_id)
                if not db_task:
                    return
                next_payload = dict(db_task.result_payload or {})
                next_payload["images"] = assets
                next_payload["assets"] = assets
                next_payload["status"] = "succeeded"
                db_task.status = "succeeded"
                db_task.result_payload = next_payload
                db_task.error_message = None
                db_task.finished_at = datetime.utcnow()
                if not db_task.duration_ms and db_task.started_at:
                    try:
                        db_task.duration_ms = int((datetime.utcnow() - db_task.started_at).total_seconds() * 1000)
                    except Exception:
                        pass
                session.add(db_task)
                session.commit()
        except Exception as exc:
            # Best-effort; keep task running but record the last diagnostic hint for operators.
            with get_session() as session:
                db_task = session.get(AbilityTask, task_id)
                if db_task and db_task.status in {"queued", "running"}:
                    db_task.error_message = str(exc)[:240]
                    session.add(db_task)
                    session.commit()
            return

    def _try_finalize_kie_task(self, *, task_id: str) -> None:
        """Best-effort: finalize a KIE task by polling recordInfo and ingesting outputs."""

        with get_session() as session:
            task_row = session.get(AbilityTask, task_id)
            if not task_row:
                return
            if (task_row.ability_provider or "").lower() != "kie":
                return
            if task_row.status not in {"queued", "running"}:
                return
            result_payload = task_row.result_payload or {}
            if not isinstance(result_payload, dict):
                return
            meta = result_payload.get("metadata") if isinstance(result_payload.get("metadata"), dict) else {}
            kie_task_id = meta.get("taskId")
            executor_id = meta.get("executorId")
            settings = get_settings()
            timeout_seconds = int(getattr(settings, "kie_task_timeout_seconds", 0) or 0)
            started_at = task_row.started_at or task_row.created_at
            if timeout_seconds > 0 and started_at:
                elapsed = (datetime.utcnow() - started_at).total_seconds()
                if elapsed > timeout_seconds:
                    task_row.status = "failed"
                    task_row.error_message = "KIE_TIMEOUT"
                    task_row.finished_at = datetime.utcnow()
                    try:
                        task_row.duration_ms = int(elapsed * 1000)
                    except Exception:
                        pass
                    session.add(task_row)
                    session.commit()
                    return
            if not (isinstance(kie_task_id, str) and kie_task_id.strip()):
                return
            if not (isinstance(executor_id, str) and executor_id.strip()):
                return

        try:
            fetched = integration_test_service.fetch_kie_market_result(
                executor_id=executor_id.strip(),
                task_id=kie_task_id.strip(),
                timeout=18.0,
                max_retries=1,
            )
        except Exception as exc:
            self._logger.warning("eval finalize KIE task failed: %s", exc)
            return

        state = str(fetched.get("state") or "").lower()
        urls = fetched.get("resultUrls") if isinstance(fetched.get("resultUrls"), list) else []
        assets = fetched.get("storedAssets") if isinstance(fetched.get("storedAssets"), list) else []

        with get_session() as session:
            db_task = session.get(AbilityTask, task_id)
            if not db_task:
                return
            if state == "success" and (urls or assets):
                if not assets and urls:
                    assets = [{"url": u} for u in urls if isinstance(u, str) and u.strip()]
                next_payload = dict(db_task.result_payload or {})
                next_payload["images"] = assets
                next_payload["assets"] = assets
                next_payload["status"] = "succeeded"
                db_task.status = "succeeded"
                db_task.result_payload = next_payload
                db_task.finished_at = datetime.utcnow()
                if not db_task.duration_ms and db_task.started_at:
                    try:
                        db_task.duration_ms = int(
                            (datetime.utcnow() - db_task.started_at).total_seconds() * 1000
                        )
                    except Exception:
                        pass
                session.add(db_task)
                session.commit()
                return
            if state == "fail":
                db_task.status = "failed"
                db_task.error_message = "KIE_TASK_FAILED"
                db_task.finished_at = datetime.utcnow()
                session.add(db_task)
                session.commit()
                return

    @staticmethod
    def _extract_output_json(payload: dict[str, Any]) -> Any:
        """Best-effort extraction of `output` for non-image workflows.

        Coze often returns `output` as:
        - a JSON string (e.g. "{...}") for tagging/metadata flows
        - a primitive/string for text flows
        """

        if not isinstance(payload, dict):
            return None
        if any(
            key in payload
            for key in (
                "ip",
                "prompt",
                "servers",
                "totalPending",
                "totalRunning",
                "totalCount",
                "timestamp",
            )
        ):
            return payload
        output = payload.get("output")
        if output is None:
            if any(k in payload for k in ("servers", "totalPending", "totalRunning", "totalCount", "timestamp")):
                return payload
            # Some workflows return structured business data directly (without `output`),
            # e.g. LoRA catalog query: {"items":[...], "lora_names":[...]}.
            meta_keys = {
                "run_status",
                "debug_url",
                "error_msg",
                "status",
                "state",
                "taskId",
                "task_id",
                "podi_task_id",
                "imageUrl",
                "imageUrls",
                "image_url",
                "image_urls",
                "url",
                "urls",
                "assets",
                "videos",
                "videoUrl",
                "videoUrls",
                "servers",
                "totalPending",
                "totalRunning",
                "totalCount",
                "timestamp",
            }
            business_payload = {
                k: v
                for k, v in payload.items()
                if k not in meta_keys and not str(k).startswith("_")
            }
            if business_payload:
                return business_payload
            return None
        if isinstance(output, (dict, list, int, float, bool)):
            return output
        if isinstance(output, str):
            s = output.strip()
            if not s:
                return None
            # Try parsing JSON-like strings for nicer rendering in the UI.
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                try:
                    parsed = json.loads(s)
                    return parsed
                except Exception:
                    pass
            # Avoid persisting huge bodies.
            return s[:8000]
        return str(output)[:8000]

    @staticmethod
    def _mark_succeeded(
        run_id: str,
        *,
        image_urls: list[str],
        output_json: Any | None = None,
        started: float | None,
        error_message: str | None = None,
    ) -> None:
        # Last-line defense: avoid persisting obvious non-image debug URLs as "image outputs".
        cleaned: list[str] = []
        for u in image_urls or []:
            if not isinstance(u, str):
                continue
            s = u.strip()
            if not s:
                continue
            lower = s.lower()
            if "/work_flow" in lower or ("/workflow" in lower and "execute_id=" in lower):
                continue
            if "execute_mode=" in lower and "execute_id=" in lower:
                continue
            cleaned.append(s)

        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if not run:
                return
            workflow_id = None
            if run.workflow_version_id:
                wf = session.get(EvalWorkflowVersion, run.workflow_version_id)
                if wf and wf.workflow_id:
                    workflow_id = str(wf.workflow_id)
            # 连续图工作流只需要返回一张结果图；若有多个输出，取最后一个。
            if workflow_id == "7598563505054154752" and len(cleaned) > 1:
                cleaned = [cleaned[-1]]
            run.status = "succeeded"
            run.error_message = error_message
            run.result_image_urls_json = cleaned or []
            run.result_output_json = output_json
            if started is not None:
                run.duration_ms = int((time.monotonic() - started) * 1000)
            else:
                run.duration_ms = EvalService._elapsed_ms_since(run.created_at)
            session.add(run)
            session.commit()

    @staticmethod
    def _mark_failed(run_id: str, *, message: str, started: float | None) -> None:
        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if not run:
                return
            run.status = "failed"
            run.error_message = message
            if started is not None:
                run.duration_ms = int((time.monotonic() - started) * 1000)
            else:
                run.duration_ms = EvalService._elapsed_ms_since(run.created_at)
            session.add(run)
            session.commit()


@lru_cache
def get_eval_service() -> EvalService:
    """Lazy singleton to avoid import-time side effects (important under uvicorn reload)."""

    return EvalService()
