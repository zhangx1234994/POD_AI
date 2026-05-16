"""Public evaluation APIs (no login) for internal testers.

This router is intended for internal usage on a trusted network. You can:
- enable it with `EVAL_PUBLIC_ENABLED=true`
- optionally protect it with `EVAL_PUBLIC_TOKEN`
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, File
from sqlalchemy import Integer, case, delete, exists, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, load_only

from app.core.config import get_settings
from app.core.db import get_db
from app.models.eval import (
    EvalAnnotation,
    EvalBatchAsset,
    EvalBatchOutputReview,
    EvalBatchRunItem,
    EvalBatchSession,
    EvalRun,
    EvalWorkflowVersion,
)
from app.models.integration import (
    AbilityInvocationLog,
    AbilityTask,
    ComfyuiLora,
    ComfyuiModelCatalog,
    ComfyuiPluginCatalog,
)
from app.schemas import admin_integrations as admin_schemas
from app.schemas import admin_tests
from app.schemas.eval import (
    EvalAnnotationCreate,
    EvalAnnotationResponse,
    EvalBatchAssetListResponse,
    EvalBatchAssetResponse,
    EvalBatchAssetUpsertRequest,
    EvalBatchCreate,
    EvalBatchReviewGroupItem,
    EvalBatchReviewGroupListResponse,
    EvalBatchReviewOutputItem,
    EvalBatchReviewProgress,
    EvalBatchReviewProgressRequest,
    EvalBatchReviewProgressResponse,
    EvalBatchOutputReviewListResponse,
    EvalBatchOutputReviewResponse,
    EvalBatchOutputReviewUpsertRequest,
    EvalBatchRunItemListResponse,
    EvalBatchRunItemResponse,
    EvalBatchSessionListResponse,
    EvalBatchSessionResponse,
    EvalBatchStopResponse,
    EvalBatchSubmitRequest,
    EvalBatchSubmitResponse,
    EvalOperationsHealthResponse,
    EvalRunWithLatestAnnotationListResponse,
    EvalRunWithLatestAnnotationResponse,
    EvalRunCreate,
    EvalRunListResponse,
    EvalRunResponse,
    EvalWorkflowResourceBinding,
    EvalWorkflowVersionResponse,
)
from app.services.comfyui_lora_catalog_service import ensure_default_lora_catalog_entries
from app.services.eval_seed import FISSION_WORKFLOW_IDS, ensure_default_eval_workflow_versions
from app.services.eval_operations_health import build_eval_operations_health
from app.services.eval_workflow_response import (
    EVAL_WORKFLOW_METADATA_UPDATE_KEYS,
    build_eval_workflow_response_metadata,
    is_eval_workflow_visible_for_eval_catalog,
    merge_eval_workflow_metadata_update,
)
from app.services.eval_workflow_routing_governance import resolve_eval_workflow_routing_governance
from app.services.eval_service import get_eval_service
from app.services.integration_test import integration_test_service
from app.services.oss import oss_service
from app.services.task_status_contract import derive_eval_run_status


router = APIRouter(prefix="/api/evals", tags=["evals-public"])
_BATCH_REVIEW_PAGE_SIZE = 20
logger = logging.getLogger(__name__)


def _require_public_enabled(request: Request) -> None:
    settings = get_settings()
    if not settings.eval_public_enabled:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if settings.eval_public_token:
        token = request.headers.get("X-Eval-Token") or request.query_params.get("token")
        if token != settings.eval_public_token:
            raise HTTPException(status_code=401, detail="UNAUTHORIZED")


def _require_eval_admin(request: Request) -> None:
    settings = get_settings()
    token = request.headers.get("X-Eval-Admin-Token") or request.query_params.get("admin_token")
    if not settings.eval_admin_token or token != settings.eval_admin_token:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")


def _get_or_set_rater_id(request: Request, response: Response) -> str:
    rid = request.cookies.get("podi_eval_rater")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    rid = uuid4().hex
    response.set_cookie(
        "podi_eval_rater",
        rid,
        max_age=3600 * 24 * 365,
        httponly=False,
        samesite="lax",
    )
    return rid


def _ensure_eval_workflow_versions_nonfatal(db: Session) -> None:
    """Best-effort seed sync.

    Production data should still be readable even when seed normalization fails
    because of a lagging migration or dirty historical rows.
    """
    try:
        ensure_default_eval_workflow_versions(db)
    except Exception:
        db.rollback()
        logger.exception("Failed to sync default eval workflow versions; falling back to existing rows")


def _batch_session_expr():
    return func.json_unquote(func.json_extract(EvalRun.parameters_json, "$.__batch_session_id"))


def _batch_mode_expr():
    return func.json_unquote(func.json_extract(EvalRun.parameters_json, "$.__eval_batch_mode"))


def _extract_workflow_resource_bindings(schema: dict[str, Any] | None) -> list[EvalWorkflowResourceBinding]:
    if not isinstance(schema, dict):
        return []
    raw_fields = schema.get("fields")
    if not isinstance(raw_fields, list):
        return []
    bindings: list[EvalWorkflowResourceBinding] = []
    for field in raw_fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip()
        if not name:
            continue
        lower_name = name.lower()
        explicit_type = str(field.get("resourceType") or field.get("resource_type") or "").strip().lower()
        resource_type = ""
        if explicit_type in {"lora", "model", "plugin"}:
            resource_type = explicit_type
        elif "lora" in lower_name:
            resource_type = "lora"
        elif any(token in lower_name for token in ("model", "checkpoint", "unet", "clip", "vae")):
            resource_type = "model"
        elif any(token in lower_name for token in ("plugin", "node")):
            resource_type = "plugin"
        if not resource_type:
            continue
        source = f"/api/evals/resources/options?type={resource_type}&status=active"
        bindings.append(
            EvalWorkflowResourceBinding(
                field=name,
                resourceType=resource_type,
                source=source,
            )
        )
    dedup: dict[str, EvalWorkflowResourceBinding] = {}
    for item in bindings:
        dedup[item.field] = item
    return list(dedup.values())


def _serialize_workflow_version(version: EvalWorkflowVersion) -> EvalWorkflowVersionResponse:
    response_metadata = build_eval_workflow_response_metadata(version)
    return EvalWorkflowVersionResponse(
        id=version.id,
        category=version.category,
        name=version.name,
        version=version.version,
        coze_base_url=version.coze_base_url,
        workflow_id=version.workflow_id,
        parameters_schema=version.parameters_schema,
        output_schema=version.output_schema,
        notes=version.notes,
        status=version.status,
        **response_metadata,
        resourceBindings=_extract_workflow_resource_bindings(version.parameters_schema),
        routingGovernance=resolve_eval_workflow_routing_governance(
            workflow_id=version.workflow_id,
            name=version.name,
            category=version.category,
            output_schema=version.output_schema,
        ),
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def _dedupe_workflow_versions(rows: list[EvalWorkflowVersion]) -> list[EvalWorkflowVersion]:
    dedup: dict[str, EvalWorkflowVersion] = {}
    for row in rows:
        key = str(row.workflow_id or "").strip() or str(row.id)
        if key not in dedup:
            dedup[key] = row
    return list(dedup.values())


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _serialize_eval_billing(log: AbilityInvocationLog | None) -> dict[str, Any]:
    if not log:
        return {}
    return {
        "billing_unit": log.billing_unit,
        "unit_price": _safe_float(log.unit_price),
        "currency": log.currency,
        "cost_amount": _safe_float(log.cost_amount),
    }


def _non_empty_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    results: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            results.append(item.strip())
            continue
        if isinstance(item, dict):
            for key in ("url", "storedUrl", "stored_url", "outputUrl", "output_url", "imageUrl", "videoUrl"):
                nested = item.get(key)
                if isinstance(nested, str) and nested.strip():
                    results.append(nested.strip())
                    break
    return results


def _output_payload(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return text
    return value


def _compact_eval_output_for_list(value: Any) -> Any:
    """Keep eval list rows lightweight; detail/result image fields remain intact."""

    output = _output_payload(value)
    if not isinstance(output, dict):
        if isinstance(output, str) and len(output) > 1200:
            return f"{output[:1200]}..."
        return output
    keep_keys = (
        "id",
        "runId",
        "businessRunId",
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
        "video_urls",
        "videoUrls",
        "texts",
        "error_message",
        "error",
        "route_info",
        "routeInfo",
    )
    compact = {key: _truncate_eval_output_value(output.get(key)) for key in keep_keys if key in output}
    steps = output.get("steps")
    if isinstance(steps, list):
        compact["steps"] = [_compact_eval_step_for_list(step) for step in steps[:8] if isinstance(step, dict)]
        compact["stepCount"] = len(steps)
    return compact


def _compact_eval_step_for_list(step: dict[str, Any]) -> dict[str, Any]:
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
    return {key: _truncate_eval_output_value(step.get(key)) for key in keys if key in step}


def _truncate_eval_output_value(value: Any) -> Any:
    if isinstance(value, str):
        return f"{value[:1200]}..." if len(value) > 1200 else value
    if isinstance(value, list):
        return [_truncate_eval_output_value(item) for item in value[:20]]
    if isinstance(value, dict):
        return {str(key): _truncate_eval_output_value(item) for key, item in list(value.items())[:30]}
    return value


def _collect_output_list(output: Any, keys: tuple[str, ...]) -> list[Any]:
    if not isinstance(output, dict):
        return []
    for key in keys:
        value = output.get(key)
        if isinstance(value, list):
            return value
        if value not in (None, "", [], {}):
            return [value]
    return []


def _eval_run_output_kind(run: EvalRun) -> tuple[str, bool]:
    images = run.result_image_urls_json if isinstance(run.result_image_urls_json, list) else []
    if _non_empty_strings(images):
        return "image", True
    output = _output_payload(run.result_output_json)
    if output in (None, "", [], {}):
        return "none", False
    if isinstance(output, dict):
        nested_images = _collect_output_list(output, ("imageUrls", "image_urls", "images", "resultUrls", "result_urls"))
        if _non_empty_strings(nested_images):
            return "image", True
        nested_videos = _collect_output_list(output, ("videoUrls", "video_urls", "videos"))
        if _non_empty_strings(nested_videos):
            return "video", True
        nested_texts = _collect_output_list(output, ("texts", "resultTexts", "result_texts", "text", "content", "message"))
        if _non_empty_strings(nested_texts):
            return "text", True
        return "structured", True
    if isinstance(output, list):
        if _non_empty_strings(output):
            return "text", True
        return ("structured", True) if any(item not in (None, "", [], {}) for item in output) else ("none", False)
    if isinstance(output, str):
        return ("text", True) if output.strip() else ("none", False)
    return "structured", True


def _build_eval_billing_map(db: Session, runs: list[EvalRun]) -> dict[str, dict[str, Any]]:
    task_ids = [str(run.podi_task_id).strip() for run in runs if isinstance(run.podi_task_id, str) and run.podi_task_id.strip()]
    if not task_ids:
        return {}
    try:
        task_rows = db.execute(
            select(AbilityTask.id, AbilityTask.log_id).where(AbilityTask.id.in_(task_ids))
        ).all()
        task_log_ids = {
            str(row.id): int(row.log_id)
            for row in task_rows
            if row.log_id is not None
        }
        log_ids = list(set(task_log_ids.values()))
        if not log_ids:
            return {}
        log_rows = db.execute(
            select(
                AbilityInvocationLog.id,
                AbilityInvocationLog.billing_unit,
                AbilityInvocationLog.unit_price,
                AbilityInvocationLog.currency,
                AbilityInvocationLog.cost_amount,
            ).where(AbilityInvocationLog.id.in_(log_ids))
        ).all()
    except SQLAlchemyError as exc:
        logger.warning("load eval billing summary failed: %s", exc)
        return {}
    log_by_id = {
        int(row.id): {
            "billing_unit": row.billing_unit,
            "unit_price": _safe_float(row.unit_price),
            "currency": row.currency,
            "cost_amount": _safe_float(row.cost_amount),
        }
        for row in log_rows
    }
    return {
        task_id: log_by_id[log_id]
        for task_id, log_id in task_log_ids.items()
        if log_id in log_by_id
    }


def _serialize_eval_run(run: EvalRun, billing: dict[str, Any] | None = None, *, compact_output: bool = False) -> EvalRunResponse:
    if compact_output:
        return _serialize_eval_run_for_list(run, billing)

    output_kind, has_result = _eval_run_output_kind(run)
    stage = derive_eval_run_status(
        status=run.status,
        podi_task_id=run.podi_task_id,
        error_message=run.error_message,
        has_result=has_result,
    )
    payload = EvalRunResponse.model_validate(run).model_dump()
    payload.update(
        {
            "submit_status": stage.submit_status,
            "callback_status": stage.callback_status,
            "final_status": stage.final_status,
            "error_code": stage.error_code,
            "result_output_kind": output_kind,
            "result_has_output": has_result,
            **(billing or {}),
        }
    )
    return EvalRunResponse.model_validate(payload)


def _serialize_eval_run_for_list(run: EvalRun, billing: dict[str, Any] | None = None) -> EvalRunResponse:
    image_urls = run.result_image_urls_json if isinstance(run.result_image_urls_json, list) else None
    output_kind, has_result = _eval_run_output_kind(run)
    stage = derive_eval_run_status(
        status=run.status,
        podi_task_id=run.podi_task_id,
        error_message=run.error_message,
        has_result=has_result,
    )
    payload = {
        "id": run.id,
        "workflow_version_id": run.workflow_version_id,
        "dataset_item_id": run.dataset_item_id,
        "input_oss_urls_json": run.input_oss_urls_json,
        "parameters_json": run.parameters_json,
        "status": run.status,
        "coze_execute_id": run.coze_execute_id,
        "coze_debug_url": run.coze_debug_url,
        "podi_task_id": run.podi_task_id,
        "result_image_urls_json": image_urls,
        # 列表页不加载大体积结构化正文，只返回结果类型摘要。
        "result_output_json": None,
        "result_output_kind": output_kind,
        "result_has_output": has_result,
        "error_message": run.error_message,
        "duration_ms": run.duration_ms,
        "created_by": run.created_by,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "submit_status": stage.submit_status,
        "callback_status": stage.callback_status,
        "final_status": stage.final_status,
        "error_code": stage.error_code,
        **(billing or {}),
    }
    return EvalRunResponse.model_validate(payload)


_RECOVERABLE_BUSINESS_EVAL_ERROR_CODES = (
    "BUSINESS_RUN_TIMEOUT",
    "BUSINESS_RUN_GET_FAILED",
    "BUSINESS_RUN_TEMPORARY_UNAVAILABLE",
)
_RECOVERABLE_BUSINESS_EVAL_ERROR_PREFIXES = tuple(f"{code}:" for code in _RECOVERABLE_BUSINESS_EVAL_ERROR_CODES)


def _is_recoverable_business_eval_row(run: EvalRun) -> bool:
    error = str(run.error_message or "").strip()
    return str(run.status or "").lower() == "failed" and (
        error in _RECOVERABLE_BUSINESS_EVAL_ERROR_CODES
        or error.startswith(_RECOVERABLE_BUSINESS_EVAL_ERROR_PREFIXES)
    )


def _is_recoverable_business_timeout_row(run: EvalRun) -> bool:
    return _is_recoverable_business_eval_row(run)


def _recover_business_timeout_rows_for_display(
    db: Session,
    rows: list[EvalRun],
    *,
    status_filter: str | None = None,
) -> tuple[list[EvalRun], bool]:
    """Recover stale business eval rows before the UI renders a failed card."""

    run_ids = [str(row.id) for row in rows if _is_recoverable_business_eval_row(row)]
    if not run_ids:
        return rows, False

    recovered = False
    service = get_eval_service()
    for run_id in run_ids:
        recovered = service.reconcile_business_run_for_eval(run_id) or recovered
    if not recovered:
        return rows, False

    try:
        db.expire_all()
    except Exception:
        pass

    refreshed: list[EvalRun] = []
    normalized_status = str(status_filter or "").strip().lower()
    for row in rows:
        latest = db.get(EvalRun, row.id) or row
        if normalized_status and str(latest.status or "").lower() != normalized_status:
            continue
        refreshed.append(latest)
    return refreshed, True


def _is_missing_output_review_table(exc: Exception) -> bool:
    text = str(exc).lower()
    return "eval_batch_output_review" in text and (
        "doesn't exist" in text
        or "no such table" in text
        or "undefined table" in text
    )


def _load_output_reviews_by_run_items(
    db: Session,
    *,
    run_item_ids: list[str],
    batch_id: str | None = None,
) -> list[EvalBatchOutputReview]:
    if not run_item_ids:
        return []
    stmt = select(EvalBatchOutputReview).where(EvalBatchOutputReview.run_item_id.in_(run_item_ids))
    if batch_id:
        stmt = stmt.where(EvalBatchOutputReview.batch_session_id == batch_id)
    stmt = stmt.order_by(EvalBatchOutputReview.output_index.asc(), EvalBatchOutputReview.updated_at.desc())
    try:
        return db.execute(stmt).scalars().all()
    except SQLAlchemyError as exc:  # pragma: no cover - defensive downgrade path.
        if _is_missing_output_review_table(exc):
            db.rollback()
            return []
        raise


def _ensure_batch_owner(batch: EvalBatchSession | None, rater_id: str) -> EvalBatchSession:
    if not batch:
        raise HTTPException(status_code=404, detail="BATCH_NOT_FOUND")
    if batch.created_by != rater_id:
        raise HTTPException(status_code=403, detail="BATCH_FORBIDDEN")
    return batch


def _require_batch_exists(batch: EvalBatchSession | None) -> EvalBatchSession:
    if not batch:
        raise HTTPException(status_code=404, detail="BATCH_NOT_FOUND")
    return batch


def _normalize_batch_review_progress(
    review_state: dict[str, Any] | None,
    *,
    total_pages: int,
) -> dict[str, Any]:
    raw = review_state if isinstance(review_state, dict) else {}
    def _as_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    page_size = _BATCH_REVIEW_PAGE_SIZE
    current_page = _as_int(raw.get("current_page"), 1)
    completed_page = _as_int(raw.get("completed_page"), 0)
    if current_page < 1:
        current_page = 1
    if completed_page < 0:
        completed_page = 0
    if total_pages > 0 and current_page > total_pages:
        current_page = total_pages
    if completed_page > current_page:
        completed_page = current_page
    if total_pages > 0 and completed_page > total_pages:
        completed_page = total_pages
    updated_raw = raw.get("updated_at")
    updated_at = None
    if isinstance(updated_raw, str) and updated_raw.strip():
        updated_at = updated_raw.strip()
    return {
        "page_size": page_size,
        "current_page": current_page,
        "completed_page": completed_page,
        "updated_at": updated_at,
    }


def _get_batch_review_progress(batch: EvalBatchSession, *, total_pages: int) -> dict[str, Any]:
    metadata = batch.extra_metadata if isinstance(batch.extra_metadata, dict) else {}
    review_state = metadata.get("review_state") if isinstance(metadata, dict) else None
    return _normalize_batch_review_progress(review_state if isinstance(review_state, dict) else None, total_pages=total_pages)


def _set_batch_review_progress(
    batch: EvalBatchSession,
    *,
    current_page: int,
    completed_page: int,
    total_pages: int,
) -> dict[str, Any]:
    normalized = _normalize_batch_review_progress(
        {
            "page_size": _BATCH_REVIEW_PAGE_SIZE,
            "current_page": current_page,
            "completed_page": completed_page,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        },
        total_pages=total_pages,
    )
    metadata = batch.extra_metadata.copy() if isinstance(batch.extra_metadata, dict) else {}
    metadata["review_state"] = normalized
    batch.extra_metadata = metadata
    batch.updated_at = datetime.utcnow()
    return normalized


def _parse_review_progress_updated_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _derive_batch_status(
    *,
    current_status: str,
    planned_image_count: int,
    uploaded_count: int,
    upload_failed_count: int,
    upload_in_progress_count: int,
    repeat_count: int,
    submitted_count: int,
    running_count: int,
    succeeded_count: int,
    failed_count: int,
    canceled_count: int,
) -> str:
    """Derive batch status from counters using runnable assets as source of truth."""
    if current_status == "stopped":
        return "stopped"

    repeat = max(1, int(repeat_count or 1))
    expected_run_count = max(0, int(uploaded_count or 0)) * repeat
    terminal_run_count = (
        max(0, int(succeeded_count or 0))
        + max(0, int(failed_count or 0))
        + max(0, int(canceled_count or 0))
    )

    if running_count > 0:
        return "running"
    if expected_run_count > 0 and terminal_run_count >= expected_run_count:
        if failed_count > 0 or upload_failed_count > 0:
            return "failed"
        return "succeeded"
    if submitted_count > 0:
        return "running"
    if upload_in_progress_count > 0:
        return "uploading"
    if uploaded_count > 0:
        return "ready"
    if upload_failed_count > 0 and planned_image_count > 0:
        # All assets failed upload (or no runnable asset remains).
        return "failed"
    if planned_image_count > 0:
        return "uploading"
    return "draft"


def _touch_batch_counters(db: Session, batch_id: str) -> EvalBatchSession:
    batch = db.get(EvalBatchSession, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="BATCH_NOT_FOUND")

    run_item_touched = False
    if batch.status not in {"succeeded", "failed", "stopped"}:
        run_items = db.execute(
            select(EvalBatchRunItem).where(
                EvalBatchRunItem.batch_session_id == batch_id,
                EvalBatchRunItem.eval_run_id.is_not(None),
                EvalBatchRunItem.status != "canceled",
            )
        ).scalars().all()
        run_ids = [
            str(item.eval_run_id).strip()
            for item in run_items
            if isinstance(item.eval_run_id, str) and str(item.eval_run_id).strip()
        ]
        if run_ids:
            runs = db.execute(select(EvalRun).where(EvalRun.id.in_(run_ids))).scalars().all()
            run_map = {str(run.id): run for run in runs}
            for item in run_items:
                run = run_map.get(str(item.eval_run_id or ""))
                if not run:
                    continue
                mapped = item.status
                if run.status == "queued":
                    mapped = "submitted"
                elif run.status == "running":
                    mapped = "running"
                elif run.status == "succeeded":
                    mapped = "succeeded"
                elif run.status == "failed":
                    mapped = "failed"
                if mapped != item.status:
                    item.status = mapped
                    item.updated_at = datetime.utcnow()
                    run_item_touched = True
                if run.status == "failed":
                    err = str(run.error_message or item.error_message or "")
                    if err != str(item.error_message or ""):
                        item.error_message = err
                        run_item_touched = True
                    if not item.error_code:
                        item.error_code = "RUN_FAILED"
                        run_item_touched = True

    uploaded_count = int(
        db.execute(
            select(func.count(EvalBatchAsset.id)).where(
                EvalBatchAsset.batch_session_id == batch_id,
                EvalBatchAsset.upload_status == "uploaded",
            )
        ).scalar_one()
        or 0
    )
    upload_failed_count = int(
        db.execute(
            select(func.count(EvalBatchAsset.id)).where(
                EvalBatchAsset.batch_session_id == batch_id,
                EvalBatchAsset.upload_status == "failed",
            )
        ).scalar_one()
        or 0
    )
    planned_image_count = int(
        db.execute(
            select(func.count(EvalBatchAsset.id)).where(EvalBatchAsset.batch_session_id == batch_id)
        ).scalar_one()
        or 0
    )
    upload_in_progress_count = int(
        db.execute(
            select(func.count(EvalBatchAsset.id)).where(
                EvalBatchAsset.batch_session_id == batch_id,
                EvalBatchAsset.upload_status.in_(["pending", "uploading"]),
            )
        ).scalar_one()
        or 0
    )

    submitted_count = int(
        db.execute(
            select(func.count(EvalBatchRunItem.id)).where(
                EvalBatchRunItem.batch_session_id == batch_id,
                EvalBatchRunItem.status.in_(["submitted", "running", "succeeded", "failed"]),
            )
        ).scalar_one()
        or 0
    )
    running_count = int(
        db.execute(
            select(func.count(EvalBatchRunItem.id)).where(
                EvalBatchRunItem.batch_session_id == batch_id,
                EvalBatchRunItem.status.in_(["submitting", "submitted", "running"]),
            )
        ).scalar_one()
        or 0
    )
    succeeded_count = int(
        db.execute(
            select(func.count(EvalBatchRunItem.id)).where(
                EvalBatchRunItem.batch_session_id == batch_id,
                EvalBatchRunItem.status == "succeeded",
            )
        ).scalar_one()
        or 0
    )
    failed_count = int(
        db.execute(
            select(func.count(EvalBatchRunItem.id)).where(
                EvalBatchRunItem.batch_session_id == batch_id,
                EvalBatchRunItem.status == "failed",
            )
        ).scalar_one()
        or 0
    )
    canceled_count = int(
        db.execute(
            select(func.count(EvalBatchRunItem.id)).where(
                EvalBatchRunItem.batch_session_id == batch_id,
                EvalBatchRunItem.status == "canceled",
            )
        ).scalar_one()
        or 0
    )

    planned_run_count = uploaded_count * max(1, int(batch.repeat_count or 1))
    next_status = _derive_batch_status(
        current_status=str(batch.status or ""),
        planned_image_count=planned_image_count,
        uploaded_count=uploaded_count,
        upload_failed_count=upload_failed_count,
        upload_in_progress_count=upload_in_progress_count,
        repeat_count=int(batch.repeat_count or 1),
        submitted_count=submitted_count,
        running_count=running_count,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        canceled_count=canceled_count,
    )
    if next_status in {"succeeded", "failed", "stopped"}:
        next_finished_at = batch.finished_at or datetime.utcnow()
    else:
        next_finished_at = None

    before_snapshot = (
        batch.status,
        batch.finished_at,
        batch.planned_image_count,
        batch.planned_run_count,
        batch.uploaded_count,
        batch.upload_failed_count,
        batch.submitted_count,
        batch.running_count,
        batch.succeeded_count,
        batch.failed_count,
        batch.canceled_count,
    )
    after_snapshot = (
        next_status,
        next_finished_at,
        planned_image_count,
        planned_run_count,
        uploaded_count,
        upload_failed_count,
        submitted_count,
        running_count,
        succeeded_count,
        failed_count,
        canceled_count,
    )
    if before_snapshot != after_snapshot:
        batch.status = next_status
        batch.finished_at = next_finished_at
        batch.planned_image_count = planned_image_count
        batch.planned_run_count = planned_run_count
        batch.uploaded_count = uploaded_count
        batch.upload_failed_count = upload_failed_count
        batch.submitted_count = submitted_count
        batch.running_count = running_count
        batch.succeeded_count = succeeded_count
        batch.failed_count = failed_count
        batch.canceled_count = canceled_count
        batch.updated_at = datetime.utcnow()
        db.add(batch)
        run_item_touched = True
    if run_item_touched:
        db.flush()
    return batch


def _cleanup_empty_draft_batches(db: Session, *, keep_recent_minutes: int = 10) -> int:
    """Remove invalid draft batches that never uploaded any asset nor created any run item."""
    threshold = datetime.utcnow() - timedelta(minutes=max(1, int(keep_recent_minutes or 1)))
    candidates = (
        db.execute(
            select(EvalBatchSession.id)
            .where(
                EvalBatchSession.status == "draft",
                EvalBatchSession.created_at < threshold,
            )
            .order_by(EvalBatchSession.created_at.asc())
            .limit(200)
        )
        .scalars()
        .all()
    )
    if not candidates:
        return 0
    deleted = 0
    for batch_id in candidates:
        asset_exists = db.execute(
            select(exists().where(EvalBatchAsset.batch_session_id == batch_id))
        ).scalar_one()
        if asset_exists:
            continue
        run_exists = db.execute(
            select(exists().where(EvalBatchRunItem.batch_session_id == batch_id))
        ).scalar_one()
        if run_exists:
            continue
        db.execute(delete(EvalBatchSession).where(EvalBatchSession.id == batch_id))
        deleted += 1
    if deleted > 0:
        db.flush()
    return deleted


def _to_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        iv = int(value)
        return iv if iv > 0 else None
    text = str(value).strip()
    if not text:
        return None
    digits = ""
    for ch in text:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    if not digits:
        return None
    iv = int(digits)
    return iv if iv > 0 else None


def _fit_longest_edge(width: int | None, height: int | None, longest: int = 1024) -> tuple[int, int] | None:
    w = _to_positive_int(width)
    h = _to_positive_int(height)
    if not w or not h:
        return None
    max_side = max(w, h)
    if max_side <= 0:
        return None
    scale = float(longest) / float(max_side)
    out_w = max(1, int(round(float(w) * scale)))
    out_h = max(1, int(round(float(h) * scale)))
    return out_w, out_h


def _coerce_batch_base_params(params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split batch control params from workflow params."""

    controls = {
        "size_mode": str(params.get("__batch_size_mode") or "").strip().lower() or "preset_1k",
        "aspect_ratio": str(params.get("__batch_aspect_ratio") or "").strip(),
        "resolution": str(params.get("__batch_resolution") or "").strip(),
        "custom_width": _to_positive_int(params.get("__batch_custom_width")),
        "custom_height": _to_positive_int(params.get("__batch_custom_height")),
        "aspect_field": str(params.get("__batch_aspect_field") or "").strip(),
        "resolution_field": str(params.get("__batch_resolution_field") or "").strip(),
        "width_field": str(params.get("__batch_width_field") or "").strip(),
        "height_field": str(params.get("__batch_height_field") or "").strip(),
    }
    workflow_params = {k: v for k, v in params.items() if not str(k).startswith("__batch_")}
    return workflow_params, controls


def _resolve_size_field_names(workflow_params: dict[str, Any], controls: dict[str, Any]) -> dict[str, str]:
    def _fallback(*candidates: str) -> str:
        for name in candidates:
            if name and name in workflow_params:
                return name
        return ""

    aspect_field = str(controls.get("aspect_field") or "").strip() or _fallback("aspect_ratio", "aspectRatio")
    resolution_field = str(controls.get("resolution_field") or "").strip() or _fallback("resolution")
    width_field = str(controls.get("width_field") or "").strip() or _fallback("width")
    height_field = str(controls.get("height_field") or "").strip() or _fallback("height")
    return {
        "aspect_field": aspect_field,
        "resolution_field": resolution_field,
        "width_field": width_field,
        "height_field": height_field,
    }


def _apply_batch_size_params(
    *,
    workflow_params: dict[str, Any],
    controls: dict[str, Any],
    asset: EvalBatchAsset,
) -> dict[str, Any]:
    """Build per-asset params according to size strategy."""

    params = workflow_params.copy()
    field_names = _resolve_size_field_names(workflow_params, controls)
    aspect_field = field_names["aspect_field"]
    resolution_field = field_names["resolution_field"]
    width_field = field_names["width_field"]
    height_field = field_names["height_field"]
    size_mode = str(controls.get("size_mode") or "preset_1k").strip().lower()
    if size_mode not in {"original", "preset_1k", "custom"}:
        size_mode = "preset_1k"

    known_size_fields = {
        "aspect_ratio",
        "aspectRatio",
        "resolution",
        "width",
        "height",
    }
    known_size_fields.update(
        name for name in [aspect_field, resolution_field, width_field, height_field] if name
    )

    def _clear_size_fields() -> None:
        for name in known_size_fields:
            params.pop(name, None)

    if size_mode == "original":
        _clear_size_fields()
        return params

    if size_mode == "preset_1k":
        if resolution_field:
            if aspect_field:
                aspect_value = str(controls.get("aspect_ratio") or "").strip()
                if aspect_value:
                    params[aspect_field] = aspect_value
                else:
                    params.pop(aspect_field, None)
            params[resolution_field] = str(controls.get("resolution") or "1K").strip() or "1K"
            if width_field:
                params.pop(width_field, None)
            if height_field:
                params.pop(height_field, None)
        else:
            # Width/height mode workflow: map to longest edge = 1K.
            params.pop(aspect_field, None)
            if resolution_field:
                params.pop(resolution_field, None)
            fitted = _fit_longest_edge(asset.width, asset.height, 1024)
            if fitted:
                out_w, out_h = fitted
                if width_field:
                    params[width_field] = str(out_w)
                if height_field:
                    params[height_field] = str(out_h)
        return params

    # custom
    if resolution_field:
        resolution_value = str(controls.get("resolution") or "").strip()
        if resolution_value:
            params[resolution_field] = resolution_value
        else:
            params.pop(resolution_field, None)
        if aspect_field:
            aspect_value = str(controls.get("aspect_ratio") or "").strip()
            if aspect_value:
                params[aspect_field] = aspect_value
            else:
                params.pop(aspect_field, None)
        if width_field:
            params.pop(width_field, None)
        if height_field:
            params.pop(height_field, None)
        return params

    custom_w = _to_positive_int(controls.get("custom_width"))
    custom_h = _to_positive_int(controls.get("custom_height"))
    if width_field:
        if custom_w:
            params[width_field] = str(custom_w)
        else:
            params.pop(width_field, None)
    if height_field:
        if custom_h:
            params[height_field] = str(custom_h)
        else:
            params.pop(height_field, None)
    if aspect_field:
        params.pop(aspect_field, None)
    if resolution_field:
        params.pop(resolution_field, None)
    return params


@router.get("/me")
def get_me(request: Request, response: Response) -> dict[str, Any]:
    _require_public_enabled(request)
    rid = _get_or_set_rater_id(request, response)
    return {"raterId": rid}


@router.get("/workflow-versions", response_model=list[EvalWorkflowVersionResponse])
def list_workflow_versions(
    request: Request,
    response: Response,
    category: str | None = Query(None),
    status: str | None = Query("active"),
    include_auxiliary: bool = Query(False, alias="includeAuxiliary"),
    db: Session = Depends(get_db),
) -> list[EvalWorkflowVersionResponse]:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    _ensure_eval_workflow_versions_nonfatal(db)
    stmt = select(EvalWorkflowVersion)
    if category:
        stmt = stmt.where(EvalWorkflowVersion.category == category)
    if status:
        stmt = stmt.where(EvalWorkflowVersion.status == status)
    rows = db.execute(stmt.order_by(EvalWorkflowVersion.category.asc(), EvalWorkflowVersion.created_at.desc())).scalars().all()
    rows = [
        row
        for row in rows
        if is_eval_workflow_visible_for_eval_catalog(row, include_auxiliary=include_auxiliary)
    ]
    rows = _dedupe_workflow_versions(rows)
    return [_serialize_workflow_version(row) for row in rows]


@router.get("/resources/options", response_model=admin_schemas.ComfyuiResourceOptionsResponse)
def list_eval_resource_options(
    request: Request,
    response: Response,
    resource_type: str = Query(..., alias="type"),
    status: str | None = Query("active"),
    query: str | None = Query(None, alias="q"),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    normalized_type = (resource_type or "").strip().lower()
    if normalized_type not in {"lora", "model", "plugin"}:
        raise HTTPException(status_code=400, detail="COMFYUI_RESOURCE_TYPE_INVALID")

    keyword = f"%{(query or '').strip()}%" if (query or "").strip() else None
    items: list[admin_schemas.ComfyuiResourceOptionItem] = []

    if normalized_type == "lora":
        ensure_default_lora_catalog_entries(db)
        stmt = select(ComfyuiLora)
        if status:
            stmt = stmt.where(ComfyuiLora.status == status)
        if keyword:
            stmt = stmt.where(or_(ComfyuiLora.file_name.like(keyword), ComfyuiLora.display_name.like(keyword)))
        rows = db.execute(stmt.order_by(ComfyuiLora.updated_at.desc()).limit(limit)).scalars().all()
        items = [
            admin_schemas.ComfyuiResourceOptionItem(
                id=f"lora:{row.id}",
                key=row.file_name,
                label=row.display_name or row.file_name,
                resourceType="lora",
                status=row.status,
                description=row.description,
                metadata={
                    "baseModel": row.base_model,
                    "baseModels": row.base_models or [],
                    "tags": row.tags or [],
                },
            )
            for row in rows
        ]
    elif normalized_type == "model":
        stmt = select(ComfyuiModelCatalog)
        if status:
            stmt = stmt.where(ComfyuiModelCatalog.status == status)
        if keyword:
            stmt = stmt.where(
                or_(ComfyuiModelCatalog.file_name.like(keyword), ComfyuiModelCatalog.display_name.like(keyword))
            )
        rows = db.execute(stmt.order_by(ComfyuiModelCatalog.updated_at.desc()).limit(limit)).scalars().all()
        items = [
            admin_schemas.ComfyuiResourceOptionItem(
                id=f"model:{row.id}",
                key=row.file_name,
                label=row.display_name or row.file_name,
                resourceType="model",
                status=row.status,
                description=row.description,
                downloadUrl=row.download_url,
                metadata={"modelType": row.model_type, "tags": row.tags or []},
            )
            for row in rows
        ]
    else:
        stmt = select(ComfyuiPluginCatalog)
        if status:
            stmt = stmt.where(ComfyuiPluginCatalog.status == status)
        if keyword:
            stmt = stmt.where(
                or_(
                    ComfyuiPluginCatalog.node_key.like(keyword),
                    ComfyuiPluginCatalog.display_name.like(keyword),
                    ComfyuiPluginCatalog.package_name.like(keyword),
                )
            )
        rows = db.execute(stmt.order_by(ComfyuiPluginCatalog.updated_at.desc()).limit(limit)).scalars().all()
        items = [
            admin_schemas.ComfyuiResourceOptionItem(
                id=f"plugin:{row.id}",
                key=row.node_key,
                label=row.display_name or row.node_key,
                resourceType="plugin",
                status=row.status,
                description=row.description,
                downloadUrl=row.download_url,
                metadata={"packageName": row.package_name, "tags": row.tags or [], "version": row.version},
            )
            for row in rows
        ]

    return admin_schemas.ComfyuiResourceOptionsResponse(
        resourceType=normalized_type,
        status=status,
        total=len(items),
        items=items,
    )


@router.get("/docs/workflows")
def get_workflow_docs(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Developer doc: how to call Coze workflows + full IO schema list (active)."""
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    _ensure_eval_workflow_versions_nonfatal(db)

    rows = (
        db.execute(
            select(EvalWorkflowVersion)
            .where(EvalWorkflowVersion.status == "active")
            .order_by(EvalWorkflowVersion.category.asc(), EvalWorkflowVersion.name.asc())
        )
        .scalars()
        .all()
    )

    def _md_escape(text: str) -> str:
        return (text or "").replace("|", "\\|").replace("\n", " ").strip()

    def _infer_output_kind(wf: EvalWorkflowVersion) -> str:
        schema = wf.output_schema or {}
        fields = schema.get("fields") if isinstance(schema, dict) else None
        if isinstance(fields, list):
            has_json_field = False
            for f in fields:
                if not isinstance(f, dict):
                    continue
                name = str(f.get("name") or "").strip().lower()
                f_type = str(f.get("type") or "").strip().lower()
                if name == "output":
                    desc = str(f.get("description") or "")
                    if "task" in desc.lower() or "回调" in desc:
                        return "callback_task_id"
                if f_type in {"json", "array", "object"} or name in {"items", "lora_names", "loraNames"}:
                    has_json_field = True
            if has_json_field:
                return "json_output"
        return "image_url"

    def _coerce_schema(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            return {"fields": value}
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"fields": parsed}
        return {}

    def _normalize_options(options: Any) -> list[dict[str, str]]:
        if isinstance(options, str):
            raw = options.strip()
            if not raw:
                return []
            # Allow comma-separated strings as a fallback.
            return [{"label": item.strip(), "value": item.strip()} for item in raw.split(",") if item.strip()]
        if not isinstance(options, list):
            return []
        normalized: list[dict[str, str]] = []
        for opt in options:
            if isinstance(opt, dict):
                label = opt.get("label")
                value = opt.get("value")
                if value is None:
                    value = label
                if label is None:
                    label = value
                if value is None and label is None:
                    continue
                normalized.append({"label": str(label or ""), "value": str(value or "")})
            else:
                normalized.append({"label": str(opt), "value": str(opt)})
        return [x for x in normalized if x.get("label") or x.get("value")]

    def _normalize_fields(schema: Any) -> list[dict[str, Any]]:
        schema = _coerce_schema(schema)
        fields = schema.get("fields") if isinstance(schema, dict) else None
        if not isinstance(fields, list):
            return []
        normalized: list[dict[str, Any]] = []
        for f in fields:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            normalized.append(
                {
                    "name": str(f.get("name") or "").strip(),
                    "label": str(f.get("label") or "").strip() or None,
                    "type": str(f.get("type") or "text").strip(),
                    "required": bool(f.get("required")),
                    "defaultValue": f.get("defaultValue") if f.get("defaultValue") is not None else "",
                    "description": str(f.get("description") or "").strip(),
                    "options": _normalize_options(f.get("options")),
                }
            )
        return normalized

    def _filter_doc_fields(wf: EvalWorkflowVersion, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
        is_fission = wf.category == "图裂变" or str(wf.workflow_id) in FISSION_WORKFLOW_IDS
        if is_fission:
            internal_keys = {"count", "generateCount", "variantCount", "n"}
            return [f for f in fields if str(f.get("name") or "") not in internal_keys]
        return fields

    def _example_parameters(fields: list[dict[str, Any]]) -> dict[str, str]:
        example: dict[str, str] = {}
        for f in fields:
            name = str(f.get("name") or "")
            if not name:
                continue
            example[name] = "<required>" if f.get("required") else "<optional>"
        return example

    def _render_schema_table(fields: list[dict[str, Any]], *, empty_hint: str) -> list[str]:
        if not fields:
            return [empty_hint, ""]
        lines: list[str] = []
        lines.append("| 字段 | 必填 | 类型 | 默认值 | 可选项 | 描述 |")
        lines.append("|---|---:|---|---|---|---|")
        for f in fields:
            name = str(f.get("name") or "")
            required = "Y" if f.get("required") else ""
            ftype = str(f.get("type") or "text")
            default = str(f.get("defaultValue") or "")
            opts = ""
            options = f.get("options")
            if isinstance(options, list) and options:
                rendered = []
                for o in options:
                    if isinstance(o, dict):
                        rendered.append(str(o.get("value") or o.get("label") or ""))
                    else:
                        rendered.append(str(o))
                opts = " / ".join([x for x in rendered if x])
            desc = str(f.get("description") or "")
            lines.append(
                f"| `{_md_escape(name)}` | {required} | `{_md_escape(ftype)}` | `{_md_escape(default)}` | {_md_escape(opts)} | {_md_escape(desc)} |"
            )
        lines.append("")
        return lines

    def _workflow_error_hints(output_kind: str) -> list[str]:
        hints = [
            "`INTERNAL_ONLY`：非内网访问或缺少 SERVICE_API_TOKEN。",
            "`COZE_FAILED` / `COZE_EXECUTION_FAILED`：Coze 返回 code!=0 或执行失败。",
            "`COZE_RUN_*`：Coze run_status=failed/canceled/timeout 等。",
            "`COZE_ASYNC_TIMEOUT` / `COZE_ASYNC_EMPTY`：异步轮询超时/无响应。",
            "`COZE_WORKFLOW_ERROR`：工作流 output 内含错误字段。",
            "`COZE_SUBMIT_FAILED` / `COZE_SUBMIT_MISSING_EXECUTE_ID`：提交失败或缺少 execute_id。",
            "`COZE_HISTORY_FAILED`：Coze history 查询失败。",
            "`WORKFLOW_VERSION_NOT_FOUND`：评测平台未找到对应 workflow 版本。",
            "`PROMPT_REQUIRED`：缺少提示词，通常是人工测试入参不完整。",
            "`VENDOR_CREDITS_INSUFFICIENT`：第三方账号余额不足。",
            "`FANOUT_EMPTY` / `FANOUT_PARTIAL_FAILED`：批量子任务全部失败或部分失败。",
        ]
        if output_kind == "callback_task_id":
            hints.extend(
                [
                    "`TASK_ID_REQUIRED`：缺少 taskId。",
                    "`TASK_NOT_FOUND`：任务不存在或已过期。",
                    "`TASK_FAILED`：任务执行失败。",
                    "`TASK_TIMEOUT`：任务超时。",
                    "`TASK_IMAGES_EMPTY`：任务结果无图片。",
                    "`CALLBACK_OUTPUT_EMPTY`：回调 task id 为空。",
                    "`CALLBACK_IMAGES_EMPTY`：回调解析不到图片。",
                    "`CALLBACK_TASK_NOT_RESOLVED`：task id 无法解析/失效。",
                    "`COMFYUI_*`：ComfyUI 相关错误（如 `COMFYUI_SUBMIT_ERROR`、`COMFYUI_HISTORY_INVALID`）。",
                    "`ERR|Q1001|...` / `ERR|Q2001|...`：并发/队列超限。",
                ]
            )
        return hints

    def _strip_backticks(values: list[str]) -> list[str]:
        return [value.replace("`", "") for value in values]

    lines: list[str] = []
    lines.append("# PODI 评测平台 · Coze 工作流调用文档")
    lines.append("")
    lines.append("用于开发人员直接通过 Coze OpenAPI 调用工作流，确认入参/出参与 workflow_id。")
    lines.append("")
    lines.append("## 调用方式")
    lines.append("")
    lines.append("环境变量：")
    lines.append("- `COZE_BASE_URL`：例如 `https://api.coze.cn`（以实际为准）")
    lines.append("- `COZE_API_TOKEN`：Coze 平台生成的 token")
    lines.append("")
    lines.append("网络/鉴权注意：")
    lines.append("- PODI 的 Coze 插件接口默认仅允许内网访问（返回 `401 {\"detail\":\"INTERNAL_ONLY\"}`）。")
    lines.append("- 若 Coze 与 PODI 不在同一内网：在 PODI 后端配置 `COZE_TRUSTED_IPS=<coze_source_ip,...>` 放行 Coze 源 IP。")
    lines.append("- 也可在请求头携带 `Authorization: Bearer $SERVICE_API_TOKEN`（若后端已配置该 token）。")
    lines.append("")
    lines.append("示例：")
    lines.append("```bash")
    lines.append("curl -X POST \"$COZE_BASE_URL/v1/workflow/run\" \\")
    lines.append("  -H \"Authorization: Bearer $COZE_API_TOKEN\" \\")
    lines.append("  -H \"Content-Type: application/json\" \\")
    lines.append("  -d '{\"workflow_id\":\"<WORKFLOW_ID>\",\"parameters\":{}}'")
    lines.append("```")
    lines.append("")
    lines.append("## ComfyUI 回调（重要）")
    lines.append("")
    lines.append("部分工作流的 `output` 返回的是回调 task id（例如 ComfyUI 类工作流）。评测平台会：")
    lines.append("1) 先运行 Coze 工作流拿到 `data.output`（task id）")
    lines.append("2) 再轮询 task 结果，拿到最终图片 URL 列表并展示")
    lines.append("")
    lines.append("回调工作流（通用类）：")
    lines.append("- `ComfyUI 回调 · comfyui_huidiao` 输入 `taskid`，输出 `images` 数组。")
    lines.append("")
    lines.append("task id 兼容格式：")
    lines.append("- 旧格式：`<raw_id>`（数据库/历史返回）")
    lines.append("- 新格式：`t1.<provider>.<executorId>.<raw_id>`（可解析，便于路由与排障）")
    lines.append("")
    lines.append("如需在 Coze 侧自行解析回调图片：")
    lines.append("- 推荐：调用 PODI `/api/coze/podi/tasks/get`（入参 `taskId`）直接获取 `images`。")
    lines.append("- 备选：配置 `COZE_COMFYUI_CALLBACK_WORKFLOW_ID`，由一个专门的回调工作流负责将 task id 解析为 images。")
    lines.append("")
    lines.append("## debug_url 是什么？")
    lines.append("")
    lines.append("当 Coze 执行失败或需要排查时，后端会透出 `debug_url`，可在 Coze Studio/Loop 中打开对应 run 的节点级日志。")
    lines.append("")
    lines.append("## 注意事项（统一规则）")
    lines.append("")
    lines.append("- 图片类参数统一使用 URL（纯字符串），像素类参数仅传数字（不要带 `px`）。")
    lines.append("- 回调类工作流的 `output` 为 task id，需轮询 `/api/coze/podi/tasks/get` 获取最终图片。")
    lines.append("- ComfyUI 类工作流会额外返回 `ip`（执行节点），用于排障与路由判断。")
    lines.append("- ComfyUI 队列汇总工具无需入参，直接返回各节点队列状态。")
    lines.append("")
    lines.append("## 状态与异常统一准则（开发联调必读）")
    lines.append("")
    lines.append("### 状态词口径")
    lines.append("- Coze `/api/coze/podi/tasks/get`：`taskStatus` 仅使用 `queued/running/succeeded/failed`。")
    lines.append("- 能力异步任务 `/api/ability-tasks`：`queued/running/succeeded/failed/cancelled`。")
    lines.append("- 能力调用日志 `/api/admin/abilities/logs`：`pending/success/failed`（日志维度，不等同任务状态）。")
    lines.append("- 评测 run 列表 `/api/evals/runs`：")
    lines.append("  - `submit_status`：提交阶段（`pending/submitting/submit_failed/submitted`）")
    lines.append("  - `callback_status`：回调阶段（`waiting/running/success/failed/not_configured`）")
    lines.append("  - `final_status`：最终阶段（`pending/running/success/failed/canceled`）")
    lines.append("")
    lines.append("### 失败处理约定")
    lines.append("- 队列/并发限制：`taskId=ERR|Qxxxx|...` 且 `taskStatus=failed`。")
    lines.append("- 其余错误按错误关键字透传（如 `TASK_NOT_FOUND`、`COMFYUI_SUBMIT_ERROR`）。")
    lines.append("- 建议业务端先判 `taskStatus`，再根据 `debugResponse/errorMessage` 做重试与告警。")
    lines.append("")
    lines.append("### 结果显示约定")
    lines.append("- `taskStatus=succeeded` 但暂未拿到图片 URL 时，前端应显示“结果回填中”，不要直接判定无结果。")
    lines.append("")
    lines.append("## 常见错误速查（报错编号体系）")
    lines.append("")
    lines.append("### 错误码格式")
    lines.append("- `ERR|<CODE>|<message>`：用于队列/并发等强约束错误（回调 id 字段会直接返回该值）。")
    lines.append("- 其余错误多为**错误关键字**（如 `TASK_NOT_FOUND`），在 error_message 或 debugResponse 中出现。")
    lines.append("")
    lines.append("### 错误码一览（完整）")
    lines.append("| 编号 | 含义 | 典型场景 |")
    lines.append("|---|---|---|")
    lines.append("| Q1001 | ComfyUI 队列已满（单机 >= 10） | ComfyUI 并发超限 |")
    lines.append("| Q2001 | 商业模型队列已满（单机 >= 10） | 商业模型并发超限 |")
    lines.append("| INTERNAL_ONLY | 仅内网可访问 | IP 未放行 |")
    lines.append("| WORKFLOW_ID_MISSING | 缺少 workflow_id | 请求体缺字段 |")
    lines.append("| WORKFLOW_VERSION_NOT_FOUND | workflow 版本不存在 | workflow_id 不在评测库 |")
    lines.append("| PROMPT_REQUIRED | 缺少提示词 | 人工测试/模型调用入参不完整 |")
    lines.append("| VENDOR_CREDITS_INSUFFICIENT | 第三方账号余额不足 | KIE/OpenAI-compatible/中转站余额不足 |")
    lines.append("| FANOUT_EMPTY | 批量子任务全部失败 | fanout 模式 |")
    lines.append("| FANOUT_PARTIAL_FAILED | 批量部分失败 | fanout 模式 |")
    lines.append("| COZE_SUBMIT_FAILED | 提交 Coze 失败 | /v1/workflow/run 返回错误 |")
    lines.append("| COZE_SUBMIT_MISSING_EXECUTE_ID | 缺少 execute_id | Coze 返回体异常 |")
    lines.append("| COZE_HISTORY_FAILED | Coze history 失败 | /v1/workflow/history 异常 |")
    lines.append("| COZE_EXECUTION_FAILED | Coze 执行失败 | run_status=failed |")
    lines.append("| COZE_FAILED | Coze 执行失败 | code!=0 |")
    lines.append("| COZE_RUN_* | Coze 状态异常 | run_status=failed/canceled/timeout |")
    lines.append("| COZE_ASYNC_EMPTY | Coze 异步空响应 | async poll 返回空 |")
    lines.append("| COZE_ASYNC_TIMEOUT | Coze 轮询超时 | async 超时 |")
    lines.append("| COZE_WORKFLOW_ERROR | workflow error | output 内 error 字段 |")
    lines.append("| TASK_ID_REQUIRED | 缺少 taskId | /api/coze/podi/tasks/get |")
    lines.append("| TASK_NOT_FOUND | 任务不存在 | taskId 错误或被清理 |")
    lines.append("| TASK_FAILED | 任务执行失败 | 上游执行失败 |")
    lines.append("| TASK_TIMEOUT | 任务超时 | 超过轮询期限 |")
    lines.append("| TASK_IMAGES_EMPTY | 任务无图片 | task 结果无 images |")
    lines.append("| CALLBACK_OUTPUT_EMPTY | 回调 task id 为空 | 工作流未返回 output |")
    lines.append("| CALLBACK_IMAGES_EMPTY | 回调解析不到图片 | 回调未产出 images |")
    lines.append("| CALLBACK_TASK_NOT_RESOLVED | task id 无法解析/失效 | 回调任务无法完成 |")
    lines.append("| COMFYUI_QUEUE_STATUS_ERROR | ComfyUI 队列查询失败 | /queue/status 异常 |")
    lines.append("| COMFYUI_QUEUE_STATUS_INVALID | ComfyUI 队列响应异常 | queue JSON 不合法 |")
    lines.append("| COMFYUI_SUBMIT_ERROR | 提交 ComfyUI 失败 | /prompt 失败 |")
    lines.append("| COMFYUI_SUBMIT_NODE_ERROR | ComfyUI 节点错误 | 节点报错/缺模型 |")
    lines.append("| COMFYUI_HISTORY_HTTP_* | ComfyUI history 非 200 | /history/<id> 失败 |")
    lines.append("| COMFYUI_HISTORY_INVALID | ComfyUI history JSON 异常 | history 解析失败 |")
    lines.append("| COMFYUI_STATUS_* | ComfyUI 状态异常 | status=error/unknown |")
    lines.append("| COMFYUI_IMAGES_EMPTY | ComfyUI 无输出图 | history 没有 images |")
    lines.append("| COMFYUI_ASSETS_EMPTY | OSS 入库为空 | 图片落盘失败 |")
    lines.append("| COMFYUI_TIMEOUT | ComfyUI 轮询超时 | /history 超时 |")
    lines.append("| COMFYUI_WORKFLOW_EMPTY | ComfyUI workflow 为空 | 工作流配置缺失 |")
    lines.append("| COMFYUI_BASE_URL_MISSING | 缺少 ComfyUI Base URL | 执行节点未配置 |")
    lines.append("| COMFYUI_IMAGE_REQUIRED | 缺少图片 | 需要图片输入 |")
    lines.append("")
    lines.append("### 补充说明")
    lines.append("- `Q1001/Q2001` 触发时，**回调 id 字段会返回 `ERR|Qxxxx|...`**，便于业务侧统一处理。")
    lines.append("- 其余错误关键字由后端直接透传，评测平台可直接显示在失败详情。")
    lines.append("")
    lines.append("## 功能列表（active）")
    lines.append("")
    lines.append("| 分类 | 功能 | workflow_id | 输出类型 | 备注 |")
    lines.append("|---|---|---:|---|---|")
    workflows: list[dict[str, Any]] = []
    grouped: dict[str, list[EvalWorkflowVersion]] = {}

    for wf in rows:
        parameters = _filter_doc_fields(wf, _normalize_fields(wf.parameters_schema or {}))
        outputs = _normalize_fields(wf.output_schema or {})
        output_kind = _infer_output_kind(wf)
        workflows.append(
            {
                "category": wf.category,
                "name": wf.name,
                "workflow_id": wf.workflow_id,
                "notes": wf.notes,
                "output_kind": output_kind,
                "parameters": parameters,
                "outputs": outputs,
                "errors": _strip_backticks(_workflow_error_hints(output_kind)),
                "request": {
                    "method": "POST",
                    "path": "/v1/workflow/run",
                    "body": {"workflow_id": wf.workflow_id, "parameters": _example_parameters(parameters)},
                },
            }
        )
        grouped.setdefault(wf.category, []).append(wf)
        lines.append(
            f"| {_md_escape(wf.category)} | {_md_escape(wf.name)} | `{_md_escape(wf.workflow_id)}` | `{output_kind}` | {_md_escape(wf.notes or '')} |"
        )
    lines.append("")

    lines.append("## 目录")
    lines.append("")
    for category, items in grouped.items():
        lines.append(f"- {category}（{len(items)}）")
    lines.append("")

    lines.append("## 分类明细")
    lines.append("")

    for category, items in grouped.items():
        lines.append(f"## {category}")
        lines.append("")
        for wf in items:
            lines.append(f"### {wf.name}")
            lines.append("")
            lines.append(f"- workflow_id：`{wf.workflow_id}`")
            lines.append(f"- 输出类型：`{_infer_output_kind(wf)}`（主字段为 `output`，额外字段见出参说明）")
            if wf.notes:
                lines.append(f"- 备注：{wf.notes}")
            lines.append("")
            lines.append("#### 调用方法")
            lines.append("")
            lines.append("```json")
            example_params = _example_parameters(
                _filter_doc_fields(wf, _normalize_fields(wf.parameters_schema or {}))
            )
            lines.append(
                json.dumps(
                    {"workflow_id": wf.workflow_id, "parameters": example_params},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            lines.append("```")
            lines.append("")
            lines.append("#### 入参 parameters")
            lines.append("")
            fields = _filter_doc_fields(wf, _normalize_fields(wf.parameters_schema or {}))
            lines.extend(_render_schema_table(fields, empty_hint="_无 schema（请在后台补齐 parameters_schema 以生成动态表单）。_"))
            if wf.category == "图裂变" or str(wf.workflow_id) in FISSION_WORKFLOW_IDS:
                lines.append(
                    "> 说明：`count` 为评测平台内部“裂变数量”控制参数，不属于 Coze workflow 入参，调用 Coze OpenAPI 请勿传递。"
                )
                lines.append("")

            lines.append("#### 出参 data")
            lines.append("")
            output_fields = _normalize_fields(wf.output_schema or {})
            lines.extend(_render_schema_table(output_fields, empty_hint="_无 schema（请在后台补齐 output_schema 以生成文档）。_"))
            lines.append("> Coze 返回结构中 `data` 可能是 JSON 字符串或对象。建议直接查看 `data` 的字段（以上表格）。")
            lines.append("")

            lines.append("#### 错误码")
            lines.append("")
            lines.append("可能出现以下错误（详见本文档「错误码一览」）：")
            for hint in _workflow_error_hints(_infer_output_kind(wf)):
                lines.append(f"- {hint}")
            lines.append("")

    return {
        "markdown": "\n".join(lines),
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "workflows": workflows,
    }


@router.post("/uploads")
async def upload_image(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Upload an image to OSS and return its public URL."""
    _require_public_enabled(request)
    user_id = _get_or_set_rater_id(request, response)
    data = await file.read()
    uploaded = oss_service.upload_bytes(user_id=user_id, filename=file.filename or "upload.png", data=data, content_type=file.content_type)
    return {"url": uploaded.get("url"), "objectKey": uploaded.get("objectKey")}


@router.get("/admin/workflow-versions", response_model=list[EvalWorkflowVersionResponse])
def admin_list_workflow_versions(
    request: Request,
    category: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[EvalWorkflowVersionResponse]:
    _require_eval_admin(request)
    _ensure_eval_workflow_versions_nonfatal(db)
    stmt = select(EvalWorkflowVersion)
    if category:
        stmt = stmt.where(EvalWorkflowVersion.category == category)
    rows = db.execute(stmt.order_by(EvalWorkflowVersion.category.asc(), EvalWorkflowVersion.created_at.desc())).scalars().all()
    return [_serialize_workflow_version(row) for row in rows]


@router.get("/admin/operations-health", response_model=EvalOperationsHealthResponse)
def admin_get_operations_health(
    request: Request,
    stale_minutes: int = Query(30, alias="staleMinutes", ge=5, le=24 * 60),
    submit_grace_minutes: int = Query(5, alias="submitGraceMinutes", ge=1, le=120),
    recent_hours: int = Query(24, alias="recentHours", ge=1, le=24 * 14),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> EvalOperationsHealthResponse:
    _require_eval_admin(request)
    try:
        comfyui_queue_summary = integration_test_service.get_comfyui_queue_summary()
    except Exception:
        logger.exception("Failed to load ComfyUI queue summary for eval operations health")
        comfyui_queue_summary = {"error": "COMFYUI_QUEUE_HEALTH_UNAVAILABLE"}
    report = build_eval_operations_health(
        db,
        stale_minutes=stale_minutes,
        submit_grace_minutes=submit_grace_minutes,
        recent_hours=recent_hours,
        limit=limit,
        comfyui_queue_summary=comfyui_queue_summary,
    )
    return EvalOperationsHealthResponse.model_validate(report)


@router.get("/admin/comfyui-queue-summary", response_model=admin_tests.ComfyuiQueueSummaryResponse)
def admin_get_comfyui_queue_summary(
    request: Request,
    executor_ids: list[str] | None = Query(None, alias="executorIds"),
) -> admin_tests.ComfyuiQueueSummaryResponse:
    _require_eval_admin(request)
    result = integration_test_service.get_comfyui_queue_summary(executor_ids=executor_ids)
    result["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return admin_tests.ComfyuiQueueSummaryResponse.model_validate(result)


@router.put("/admin/workflow-versions/{workflow_version_id}", response_model=EvalWorkflowVersionResponse)
def admin_update_workflow_version(
    workflow_version_id: str,
    request: Request,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> EvalWorkflowVersionResponse:
    _require_eval_admin(request)
    row = db.get(EvalWorkflowVersion, workflow_version_id)
    if not row:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    metadata_update = {
        key: body.pop(key)
        for key in list(body.keys())
        if key in EVAL_WORKFLOW_METADATA_UPDATE_KEYS
    }
    for key in ("name", "notes", "category", "status", "version"):
        if key in body and isinstance(body[key], str):
            setattr(row, key, body[key].strip())
    if metadata_update:
        row.extra_metadata = merge_eval_workflow_metadata_update(row.extra_metadata, metadata_update)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_workflow_version(row)


@router.post("/batches", response_model=EvalBatchSessionResponse)
def create_batch(
    request: Request,
    response: Response,
    payload: EvalBatchCreate,
    db: Session = Depends(get_db),
) -> EvalBatchSession:
    _require_public_enabled(request)
    created_by = _get_or_set_rater_id(request, response)
    workflow = db.get(EvalWorkflowVersion, payload.workflow_version_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="WORKFLOW_VERSION_NOT_FOUND")

    # Enforce single active batch per creator to prevent accidental duplicate submissions.
    active_batch = db.execute(
        select(EvalBatchSession)
        .where(
            EvalBatchSession.created_by == created_by,
            EvalBatchSession.status.in_(["uploading", "ready", "submitting", "running"]),
        )
        .order_by(EvalBatchSession.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if active_batch:
        raise HTTPException(
            status_code=409,
            detail=f"BATCH_ACTIVE_EXISTS:{active_batch.id}",
        )

    meta = payload.metadata.copy() if isinstance(payload.metadata, dict) else {}
    if payload.parameters_json is not None:
        meta["parameters_json"] = payload.parameters_json
    batch = EvalBatchSession(
        id=f"batch_{int(datetime.utcnow().timestamp() * 1000)}_{uuid4().hex[:8]}",
        workflow_version_id=payload.workflow_version_id,
        created_by=created_by,
        status="draft",
        repeat_count=payload.repeat_count,
        extra_metadata=meta or None,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/batches", response_model=EvalBatchSessionListResponse)
def list_batches(
    request: Request,
    response: Response,
    workflow_version_id: str | None = Query(None),
    mine_only: bool = Query(False),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> EvalBatchSessionListResponse:
    _require_public_enabled(request)
    rater_id = _get_or_set_rater_id(request, response)
    purged = _cleanup_empty_draft_batches(db)
    if purged > 0:
        db.commit()
    stmt = select(EvalBatchSession)
    count_stmt = select(func.count()).select_from(EvalBatchSession)
    if workflow_version_id:
        stmt = stmt.where(EvalBatchSession.workflow_version_id == workflow_version_id)
        count_stmt = count_stmt.where(EvalBatchSession.workflow_version_id == workflow_version_id)
    if mine_only:
        stmt = stmt.where(EvalBatchSession.created_by == rater_id)
        count_stmt = count_stmt.where(EvalBatchSession.created_by == rater_id)
    if status:
        stmt = stmt.where(EvalBatchSession.status == status)
        count_stmt = count_stmt.where(EvalBatchSession.status == status)
    total = int(db.execute(count_stmt).scalar_one())
    items = db.execute(
        stmt.order_by(EvalBatchSession.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    touched = False
    active_checked = False
    for item in items:
        if item.status in {"succeeded", "failed", "stopped"}:
            continue
        active_checked = True
        before = (
            item.status,
            item.planned_image_count,
            item.planned_run_count,
            item.uploaded_count,
            item.upload_failed_count,
            item.submitted_count,
            item.running_count,
            item.succeeded_count,
            item.failed_count,
            item.canceled_count,
        )
        refreshed = _touch_batch_counters(db, item.id)
        after = (
            refreshed.status,
            refreshed.planned_image_count,
            refreshed.planned_run_count,
            refreshed.uploaded_count,
            refreshed.upload_failed_count,
            refreshed.submitted_count,
            refreshed.running_count,
            refreshed.succeeded_count,
            refreshed.failed_count,
            refreshed.canceled_count,
        )
        if before != after:
            touched = True
    if touched or active_checked:
        db.commit()
        for item in items:
            db.refresh(item)
    return EvalBatchSessionListResponse(total=total, items=items)


@router.get("/batches/{batch_id}", response_model=EvalBatchSessionResponse)
def get_batch(
    batch_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> EvalBatchSession:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    batch = _require_batch_exists(db.get(EvalBatchSession, batch_id))
    batch = _touch_batch_counters(db, batch.id)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/batches/{batch_id}/assets", response_model=EvalBatchAssetListResponse)
def upsert_batch_assets(
    batch_id: str,
    payload: EvalBatchAssetUpsertRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> EvalBatchAssetListResponse:
    _require_public_enabled(request)
    rater_id = _get_or_set_rater_id(request, response)
    batch = _ensure_batch_owner(db.get(EvalBatchSession, batch_id), rater_id)
    if batch.status == "stopped":
        raise HTTPException(status_code=409, detail="BATCH_STOPPED")
    if not payload.items:
        raise HTTPException(status_code=400, detail="BATCH_ASSETS_EMPTY")
    if len(payload.items) > 5000:
        raise HTTPException(status_code=400, detail="BATCH_ASSET_LIMIT_EXCEEDED")

    allowed_status = {"pending", "uploading", "uploaded", "failed", "skipped"}
    upserted_ids: list[str] = []
    for item in payload.items:
        status_value = str(item.upload_status or "uploaded").strip().lower()
        if status_value not in allowed_status:
            raise HTTPException(status_code=400, detail="BATCH_ASSET_UPLOAD_STATUS_INVALID")

        row = db.execute(
            select(EvalBatchAsset).where(
                EvalBatchAsset.batch_session_id == batch.id,
                EvalBatchAsset.source_key == item.source_key,
            )
        ).scalar_one_or_none()
        if status_value == "uploaded":
            incoming_url = str(item.oss_url or "").strip()
            existing_url = str(row.oss_url or "").strip() if row else ""
            if not incoming_url and not existing_url:
                raise HTTPException(status_code=400, detail="BATCH_ASSET_URL_REQUIRED")
        if row is None:
            row = EvalBatchAsset(
                id=uuid4().hex,
                batch_session_id=batch.id,
                source_key=item.source_key.strip(),
                file_name=item.file_name.strip() or "unnamed",
            )
        row.file_name = item.file_name.strip() or row.file_name
        row.oss_url = str(item.oss_url or "").strip() or None
        row.object_key = str(item.object_key or "").strip() or None
        row.size_bytes = item.size_bytes
        row.width = item.width
        row.height = item.height
        row.upload_status = status_value
        row.upload_error_code = str(item.upload_error_code or "").strip() or None
        row.upload_error_message = str(item.upload_error_message or "").strip() or None
        row.updated_at = datetime.utcnow()
        db.add(row)
        db.flush()
        upserted_ids.append(row.id)

    batch.status = "uploading"
    batch.updated_at = datetime.utcnow()
    _touch_batch_counters(db, batch.id)
    db.commit()

    items = db.execute(
        select(EvalBatchAsset)
        .where(EvalBatchAsset.id.in_(upserted_ids))
        .order_by(EvalBatchAsset.created_at.desc())
    ).scalars().all()
    return EvalBatchAssetListResponse(total=len(items), items=items)


@router.get("/batches/{batch_id}/assets", response_model=EvalBatchAssetListResponse)
def list_batch_assets(
    batch_id: str,
    request: Request,
    response: Response,
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> EvalBatchAssetListResponse:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    batch = _require_batch_exists(db.get(EvalBatchSession, batch_id))
    stmt = select(EvalBatchAsset).where(EvalBatchAsset.batch_session_id == batch.id)
    count_stmt = select(func.count()).select_from(EvalBatchAsset).where(
        EvalBatchAsset.batch_session_id == batch.id
    )
    if status:
        stmt = stmt.where(EvalBatchAsset.upload_status == status)
        count_stmt = count_stmt.where(EvalBatchAsset.upload_status == status)
    total = int(db.execute(count_stmt).scalar_one())
    items = db.execute(
        stmt.order_by(EvalBatchAsset.created_at.asc()).offset(offset).limit(limit)
    ).scalars().all()
    return EvalBatchAssetListResponse(total=total, items=items)


@router.post("/batches/{batch_id}/submit", response_model=EvalBatchSubmitResponse)
def submit_batch(
    batch_id: str,
    payload: EvalBatchSubmitRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> EvalBatchSubmitResponse:
    _require_public_enabled(request)
    rater_id = _get_or_set_rater_id(request, response)
    batch = _ensure_batch_owner(db.get(EvalBatchSession, batch_id), rater_id)
    if batch.status == "stopped":
        raise HTTPException(status_code=409, detail="BATCH_STOPPED")

    assets = db.execute(
        select(EvalBatchAsset)
        .where(EvalBatchAsset.batch_session_id == batch.id)
        .where(EvalBatchAsset.upload_status == "uploaded")
        .order_by(EvalBatchAsset.created_at.asc())
    ).scalars().all()
    if not assets:
        raise HTTPException(status_code=400, detail="BATCH_NOT_READY")
    if not batch.workflow_version_id:
        raise HTTPException(status_code=400, detail="WORKFLOW_VERSION_NOT_FOUND")

    base_params: dict[str, Any] = {}
    if isinstance(batch.extra_metadata, dict):
        maybe_params = batch.extra_metadata.get("parameters_json")
        if isinstance(maybe_params, dict):
            base_params = maybe_params.copy()
    if isinstance(payload.parameters_json, dict):
        base_params.update(payload.parameters_json)
    workflow_base_params, batch_controls = _coerce_batch_base_params(base_params)

    existing_items = db.execute(
        select(EvalBatchRunItem).where(EvalBatchRunItem.batch_session_id == batch.id)
    ).scalars().all()
    item_map: dict[tuple[str, int], EvalBatchRunItem] = {
        (str(item.asset_id), int(item.repeat_index)): item for item in existing_items
    }

    created_items = 0
    submitted_items = 0
    failed_items = 0
    batch.status = "submitting"
    batch.updated_at = datetime.utcnow()
    db.add(batch)
    db.flush()

    for asset in assets:
        for repeat_index in range(1, max(1, int(batch.repeat_count or 1)) + 1):
            key = (asset.id, repeat_index)
            item = item_map.get(key)
            if item is None:
                item = EvalBatchRunItem(
                    id=uuid4().hex,
                    batch_session_id=batch.id,
                    asset_id=asset.id,
                    repeat_index=repeat_index,
                    status="pending",
                )
                db.add(item)
                db.flush()
                item_map[key] = item
                created_items += 1
            if payload.only_pending and item.eval_run_id:
                continue
            if batch.status == "stopped":
                raise HTTPException(status_code=409, detail="BATCH_STOPPED")
            params = _apply_batch_size_params(
                workflow_params=workflow_base_params,
                controls=batch_controls,
                asset=asset,
            )
            params["__eval_batch_mode"] = "1"
            params["__batch_session_id"] = batch.id
            params["__batch_expected_total"] = str(len(assets) * max(1, int(batch.repeat_count or 1)))
            params["__batch_expected_images"] = str(batch.planned_image_count or len(assets))
            params["__batch_expected_repeat"] = str(batch.repeat_count)
            params["__batch_file_name"] = asset.file_name
            params["__batch_source_key"] = asset.source_key
            params["__batch_repeat_index"] = str(repeat_index)
            params["__batch_request_key"] = f"{batch.id}::{asset.source_key}::{repeat_index}"
            params.setdefault("url", asset.oss_url)
            item.status = "submitting"
            item.updated_at = datetime.utcnow()
            db.add(item)
            db.flush()
            try:
                run = get_eval_service().create_eval_run(
                    workflow_version_id=batch.workflow_version_id,
                    dataset_item_id=None,
                    input_oss_urls=[str(asset.oss_url or "")] if asset.oss_url else None,
                    parameters=params,
                    created_by=rater_id,
                    db=db,
                )
                item.eval_run_id = run.id
                if run.status in {"failed"}:
                    item.status = "failed"
                    item.error_code = "BATCH_ITEM_SUBMIT_FAILED"
                    item.error_message = str(run.error_message or "RUN_CREATE_FAILED")
                    failed_items += 1
                else:
                    item.status = "submitted"
                    item.error_code = None
                    item.error_message = None
                    submitted_items += 1
            except Exception as exc:
                item.status = "failed"
                item.error_code = "BATCH_ITEM_SUBMIT_FAILED"
                item.error_message = str(exc)
                failed_items += 1
            item.updated_at = datetime.utcnow()
            db.add(item)

    _touch_batch_counters(db, batch.id)
    db.commit()
    return EvalBatchSubmitResponse(
        batch_id=batch.id,
        created_items=created_items,
        submitted_items=submitted_items,
        failed_items=failed_items,
    )


@router.get("/batches/{batch_id}/items", response_model=EvalBatchRunItemListResponse)
def list_batch_items(
    batch_id: str,
    request: Request,
    response: Response,
    status: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> EvalBatchRunItemListResponse:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    batch = _require_batch_exists(db.get(EvalBatchSession, batch_id))
    stmt = select(EvalBatchRunItem).where(EvalBatchRunItem.batch_session_id == batch.id)
    count_stmt = select(func.count()).select_from(EvalBatchRunItem).where(
        EvalBatchRunItem.batch_session_id == batch.id
    )
    if status:
        stmt = stmt.where(EvalBatchRunItem.status == status)
        count_stmt = count_stmt.where(EvalBatchRunItem.status == status)
    total = int(db.execute(count_stmt).scalar_one())
    items = db.execute(
        stmt.order_by(EvalBatchRunItem.created_at.asc()).offset(offset).limit(limit)
    ).scalars().all()

    asset_ids = [str(item.asset_id) for item in items if item.asset_id]
    asset_map: dict[str, EvalBatchAsset] = {}
    if asset_ids:
        assets = db.execute(select(EvalBatchAsset).where(EvalBatchAsset.id.in_(asset_ids))).scalars().all()
        asset_map = {str(asset.id): asset for asset in assets}

    run_ids = [item.eval_run_id for item in items if item.eval_run_id]
    run_map: dict[str, EvalRun] = {}
    if run_ids:
        runs = db.execute(select(EvalRun).where(EvalRun.id.in_(run_ids))).scalars().all()
        run_map = {str(run.id): run for run in runs}
    review_map: dict[str, list[EvalBatchOutputReview]] = {}
    run_item_ids = [str(item.id) for item in items if item.id]
    for review in _load_output_reviews_by_run_items(db, run_item_ids=run_item_ids):
        key = str(review.run_item_id)
        review_map.setdefault(key, []).append(review)
    touched = False
    for item in items:
        if item.status == "canceled":
            continue
        if not item.eval_run_id:
            continue
        run = run_map.get(str(item.eval_run_id))
        if not run:
            continue
        mapped = item.status
        if run.status == "queued":
            mapped = "submitted"
        elif run.status == "running":
            mapped = "running"
        elif run.status == "succeeded":
            mapped = "succeeded"
        elif run.status == "failed":
            mapped = "failed"
        if mapped != item.status:
            item.status = mapped
            item.updated_at = datetime.utcnow()
            touched = True
        if run.status == "failed":
            item.error_code = item.error_code or "RUN_FAILED"
            item.error_message = str(run.error_message or item.error_message or "")
            touched = True
    for item in items:
        asset = asset_map.get(str(item.asset_id or ""))
        run = run_map.get(str(item.eval_run_id or ""))
        run_params = run.parameters_json if run and isinstance(run.parameters_json, dict) else {}
        setattr(item, "asset_source_key", str(asset.source_key) if asset else None)
        setattr(item, "asset_file_name", str(asset.file_name) if asset else None)
        setattr(item, "asset_oss_url", str(asset.oss_url) if asset and asset.oss_url else None)
        setattr(item, "run_status", str(run.status) if run and run.status else None)
        setattr(item, "run_prompt", str(run_params.get("prompt") or "") if run else None)
        setattr(
            item,
            "run_output_urls_json",
            (
                [str(url) for url in (run.result_image_urls_json or []) if isinstance(url, str) and str(url).strip()]
                if run
                else None
            ),
        )
        setattr(
            item,
            "run_output_reviews_json",
            [
                EvalBatchOutputReviewResponse.model_validate(review).model_dump()
                for review in review_map.get(str(item.id), [])
            ],
        )
        setattr(item, "run_error_message", str(run.error_message or "") if run and run.error_message else None)
    if touched:
        _touch_batch_counters(db, batch.id)
        db.commit()
    return EvalBatchRunItemListResponse(total=total, items=items)


@router.get("/batches/{batch_id}/review-groups", response_model=EvalBatchReviewGroupListResponse)
def list_batch_review_groups(
    batch_id: str,
    request: Request,
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(_BATCH_REVIEW_PAGE_SIZE, ge=1, le=200),
    db: Session = Depends(get_db),
) -> EvalBatchReviewGroupListResponse:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    batch = _require_batch_exists(db.get(EvalBatchSession, batch_id))
    batch = _touch_batch_counters(db, batch.id)
    db.commit()
    db.refresh(batch)
    if str(batch.status or "").lower() not in {"succeeded", "failed", "stopped"}:
        raise HTTPException(status_code=409, detail="BATCH_REVIEW_NOT_READY")

    normalized_page_size = _BATCH_REVIEW_PAGE_SIZE if page_size != _BATCH_REVIEW_PAGE_SIZE else page_size
    total_groups = int(
        db.execute(
            select(func.count(EvalBatchAsset.id)).where(EvalBatchAsset.batch_session_id == batch.id)
        ).scalar_one()
        or 0
    )
    total_pages = max(1, (total_groups + normalized_page_size - 1) // normalized_page_size) if total_groups > 0 else 0
    if total_pages > 0 and page > total_pages:
        raise HTTPException(status_code=400, detail="BATCH_REVIEW_PAGE_INVALID")
    offset = (page - 1) * normalized_page_size

    assets = (
        db.execute(
            select(EvalBatchAsset)
            .where(EvalBatchAsset.batch_session_id == batch.id)
            .order_by(EvalBatchAsset.created_at.asc(), EvalBatchAsset.id.asc())
            .offset(offset)
            .limit(normalized_page_size)
        )
        .scalars()
        .all()
    )
    asset_ids = [str(asset.id) for asset in assets]

    run_items: list[EvalBatchRunItem] = []
    if asset_ids:
        run_items = (
            db.execute(
                select(EvalBatchRunItem)
                .where(
                    EvalBatchRunItem.batch_session_id == batch.id,
                    EvalBatchRunItem.asset_id.in_(asset_ids),
                )
                .order_by(EvalBatchRunItem.repeat_index.asc(), EvalBatchRunItem.created_at.asc())
            )
            .scalars()
            .all()
        )

    run_ids = [
        str(item.eval_run_id).strip()
        for item in run_items
        if isinstance(item.eval_run_id, str) and str(item.eval_run_id).strip()
    ]
    run_map: dict[str, EvalRun] = {}
    if run_ids:
        runs = db.execute(select(EvalRun).where(EvalRun.id.in_(run_ids))).scalars().all()
        run_map = {str(run.id): run for run in runs}

    run_item_ids = [str(item.id) for item in run_items if item.id]
    review_rows = _load_output_reviews_by_run_items(
        db,
        run_item_ids=run_item_ids,
        batch_id=batch.id,
    )
    review_map: dict[tuple[str, int], EvalBatchOutputReview] = {
        (str(row.run_item_id), int(row.output_index)): row for row in review_rows
    }

    run_items_by_asset: dict[str, list[EvalBatchRunItem]] = {}
    for item in run_items:
        key = str(item.asset_id)
        run_items_by_asset.setdefault(key, []).append(item)

    group_items: list[EvalBatchReviewGroupItem] = []
    for asset in assets:
        asset_run_items = run_items_by_asset.get(str(asset.id), [])
        outputs: list[EvalBatchReviewOutputItem] = []
        run_total = len(asset_run_items)
        completed = 0
        failed = 0
        waiting = 0
        last_error = ""

        for run_item in asset_run_items:
            run = run_map.get(str(run_item.eval_run_id or ""))
            run_status = str(run.status or run_item.status or "").lower() if run else str(run_item.status or "").lower()
            if run_status in {"succeeded", "failed"}:
                completed += 1
            else:
                waiting += 1
            if run_status == "failed":
                failed += 1
            if not last_error:
                err = str(run.error_message or run_item.error_message or "").strip() if run else str(run_item.error_message or "").strip()
                if err:
                    last_error = err

            output_urls = (
                [str(url).strip() for url in (run.result_image_urls_json or []) if isinstance(url, str) and str(url).strip()]
                if run
                else []
            )
            for idx, url in enumerate(output_urls):
                output_index = idx + 1
                review = review_map.get((str(run_item.id), output_index))
                outputs.append(
                    EvalBatchReviewOutputItem(
                        run_item_id=str(run_item.id),
                        run_id=str(run_item.eval_run_id) if run_item.eval_run_id else None,
                        output_index=output_index,
                        url=url,
                        run_status=run_status or None,
                        review=EvalBatchOutputReviewResponse.model_validate(review) if review else None,
                    )
                )

        if outputs:
            group_status = "has_output"
        elif failed > 0:
            group_status = "failed"
        else:
            group_status = "no_output"

        group_items.append(
            EvalBatchReviewGroupItem(
                asset_id=str(asset.id),
                source_key=str(asset.source_key or ""),
                file_name=str(asset.file_name or ""),
                input_url=str(asset.oss_url or "") or None,
                group_status=group_status,
                run_total=run_total,
                completed=completed,
                failed=failed,
                waiting=waiting,
                outputs=outputs,
                last_error=last_error or None,
            )
        )

    review_progress_raw = _get_batch_review_progress(batch, total_pages=total_pages)
    review_progress = EvalBatchReviewProgress(
        page_size=_BATCH_REVIEW_PAGE_SIZE,
        current_page=int(review_progress_raw["current_page"]),
        completed_page=int(review_progress_raw["completed_page"]),
        updated_at=_parse_review_progress_updated_at(review_progress_raw.get("updated_at")),
    )
    return EvalBatchReviewGroupListResponse(
        batch_id=batch.id,
        page=page,
        page_size=_BATCH_REVIEW_PAGE_SIZE,
        total_groups=total_groups,
        total_pages=total_pages,
        review_progress=review_progress,
        items=group_items,
    )


@router.post("/batches/{batch_id}/review-progress", response_model=EvalBatchReviewProgressResponse)
def save_batch_review_progress(
    batch_id: str,
    payload: EvalBatchReviewProgressRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> EvalBatchReviewProgressResponse:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    batch = _require_batch_exists(db.get(EvalBatchSession, batch_id))
    batch = _touch_batch_counters(db, batch.id)
    if str(batch.status or "").lower() not in {"succeeded", "failed", "stopped"}:
        raise HTTPException(status_code=409, detail="BATCH_REVIEW_NOT_READY")

    total_groups = int(
        db.execute(
            select(func.count(EvalBatchAsset.id)).where(EvalBatchAsset.batch_session_id == batch.id)
        ).scalar_one()
        or 0
    )
    total_pages = max(1, (total_groups + _BATCH_REVIEW_PAGE_SIZE - 1) // _BATCH_REVIEW_PAGE_SIZE) if total_groups > 0 else 0
    if payload.completed_page > payload.current_page:
        raise HTTPException(status_code=400, detail="BATCH_REVIEW_PAGE_INVALID")
    if total_pages > 0 and payload.current_page > total_pages:
        raise HTTPException(status_code=400, detail="BATCH_REVIEW_PAGE_INVALID")

    normalized = _set_batch_review_progress(
        batch,
        current_page=int(payload.current_page),
        completed_page=int(payload.completed_page),
        total_pages=total_pages,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return EvalBatchReviewProgressResponse(
        batch_id=batch.id,
        review_progress=EvalBatchReviewProgress(
            page_size=_BATCH_REVIEW_PAGE_SIZE,
            current_page=int(normalized["current_page"]),
            completed_page=int(normalized["completed_page"]),
            updated_at=_parse_review_progress_updated_at(normalized.get("updated_at")),
        ),
    )


@router.post("/batches/{batch_id}/reviews", response_model=EvalBatchOutputReviewListResponse)
def upsert_batch_output_reviews(
    batch_id: str,
    payload: EvalBatchOutputReviewUpsertRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> EvalBatchOutputReviewListResponse:
    _require_public_enabled(request)
    rater_id = _get_or_set_rater_id(request, response)
    batch = _require_batch_exists(db.get(EvalBatchSession, batch_id))
    if not payload.items:
        raise HTTPException(status_code=400, detail="BATCH_REVIEWS_EMPTY")
    if len(payload.items) > 2000:
        raise HTTPException(status_code=400, detail="BATCH_REVIEWS_LIMIT_EXCEEDED")

    run_item_ids = list(
        {
            str(item.run_item_id or "").strip()
            for item in payload.items
            if str(item.run_item_id or "").strip()
        }
    )
    if not run_item_ids:
        raise HTTPException(status_code=400, detail="BATCH_REVIEW_RUN_ITEM_REQUIRED")

    run_items = (
        db.execute(
            select(EvalBatchRunItem).where(
                EvalBatchRunItem.batch_session_id == batch.id,
                EvalBatchRunItem.id.in_(run_item_ids),
            )
        )
        .scalars()
        .all()
    )
    run_item_map = {str(item.id): item for item in run_items}
    if len(run_item_map) != len(run_item_ids):
        raise HTTPException(status_code=400, detail="BATCH_REVIEW_RUN_ITEM_INVALID")

    existing_rows = (
        db.execute(
            select(EvalBatchOutputReview).where(
                EvalBatchOutputReview.batch_session_id == batch.id,
                EvalBatchOutputReview.run_item_id.in_(run_item_ids),
            )
        )
        .scalars()
        .all()
    )
    row_map: dict[tuple[str, int], EvalBatchOutputReview] = {
        (str(row.run_item_id), int(row.output_index)): row for row in existing_rows
    }

    allowed_verdicts = {"pending", "satisfied", "unsatisfied"}
    touched_keys: set[tuple[str, int]] = set()
    now = datetime.utcnow()

    for item in payload.items:
        run_item_id = str(item.run_item_id or "").strip()
        if not run_item_id:
            raise HTTPException(status_code=400, detail="BATCH_REVIEW_RUN_ITEM_REQUIRED")
        run_item = run_item_map.get(run_item_id)
        if run_item is None:
            raise HTTPException(status_code=400, detail="BATCH_REVIEW_RUN_ITEM_INVALID")

        output_index = int(item.output_index)
        verdict = str(item.verdict or "pending").strip().lower()
        if verdict not in allowed_verdicts:
            raise HTTPException(status_code=400, detail="BATCH_REVIEW_VERDICT_INVALID")
        reason = str(item.reason or "").strip() or None
        note = str(item.note or "").strip() or None

        key = (run_item_id, output_index)
        row = row_map.get(key)
        should_clear = verdict == "pending" and not reason and not note
        if should_clear:
            if row is not None:
                db.delete(row)
                touched_keys.add(key)
                row_map.pop(key, None)
            continue

        if row is None:
            row = EvalBatchOutputReview(
                id=uuid4().hex,
                batch_session_id=batch.id,
                run_item_id=run_item_id,
                eval_run_id=run_item.eval_run_id,
                output_index=output_index,
                verdict=verdict,
                reason=reason,
                note=note,
                created_by=rater_id,
                updated_by=rater_id,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            row_map[key] = row
        else:
            row.eval_run_id = run_item.eval_run_id
            row.verdict = verdict
            row.reason = reason
            row.note = note
            row.updated_by = rater_id
            row.updated_at = now
            db.add(row)
        touched_keys.add(key)

    db.commit()

    rows: list[EvalBatchOutputReview] = []
    if touched_keys:
        touched_run_item_ids = list({run_item_id for run_item_id, _ in touched_keys})
        touched_output_indexes = list({output_index for _, output_index in touched_keys})
        rows = (
            db.execute(
                select(EvalBatchOutputReview)
                .where(EvalBatchOutputReview.batch_session_id == batch.id)
                .where(EvalBatchOutputReview.run_item_id.in_(touched_run_item_ids))
                .where(EvalBatchOutputReview.output_index.in_(touched_output_indexes))
                .order_by(EvalBatchOutputReview.updated_at.desc())
            )
            .scalars()
            .all()
        )
        rows = [row for row in rows if (str(row.run_item_id), int(row.output_index)) in touched_keys]
    return EvalBatchOutputReviewListResponse(total=len(rows), items=rows)


@router.post("/batches/{batch_id}/stop", response_model=EvalBatchStopResponse)
def stop_batch(
    batch_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> EvalBatchStopResponse:
    _require_public_enabled(request)
    rater_id = _get_or_set_rater_id(request, response)
    batch = _ensure_batch_owner(db.get(EvalBatchSession, batch_id), rater_id)
    if batch.status == "stopped":
        return EvalBatchStopResponse(
            batch_id=batch.id,
            stopped_run_items=0,
            stopped_eval_runs=0,
            stopped_ability_tasks=0,
        )

    now = datetime.utcnow()
    batch.status = "stopped"
    batch.finished_at = now
    batch.updated_at = now
    db.add(batch)
    stopped_run_items = (
        db.execute(
            update(EvalBatchRunItem)
            .where(EvalBatchRunItem.batch_session_id == batch.id)
            .where(EvalBatchRunItem.status.in_(["pending", "submitting", "submitted", "running"]))
            .values(status="canceled", error_code="BATCH_STOPPED", error_message="MANUAL_STOP_BY_OPERATOR", updated_at=now)
        ).rowcount
        or 0
    )

    run_ids = db.execute(
        select(EvalBatchRunItem.eval_run_id).where(
            EvalBatchRunItem.batch_session_id == batch.id,
            EvalBatchRunItem.eval_run_id.is_not(None),
        )
    ).scalars().all()
    run_ids = [str(run_id) for run_id in run_ids if isinstance(run_id, str) and run_id.strip()]

    stopped_eval_runs = 0
    stopped_ability_tasks = 0
    if run_ids:
        stopped_eval_runs = (
            db.execute(
                update(EvalRun)
                .where(EvalRun.id.in_(run_ids))
                .where(EvalRun.status.in_(["queued", "running"]))
                .values(status="failed", error_message="MANUAL_STOP_BY_OPERATOR", updated_at=now)
            ).rowcount
            or 0
        )
        task_rows = db.execute(
            select(EvalRun.podi_task_id).where(EvalRun.id.in_(run_ids), EvalRun.podi_task_id.is_not(None))
        ).scalars().all()
        task_ids = [str(task_id).strip() for task_id in task_rows if isinstance(task_id, str) and str(task_id).strip()]
        if task_ids:
            stopped_ability_tasks = (
                db.execute(
                    update(AbilityTask)
                    .where(AbilityTask.id.in_(task_ids))
                    .where(AbilityTask.status.in_(["queued", "running"]))
                    .values(
                        status="failed",
                        error_message="MANUAL_STOP_BY_OPERATOR",
                        finished_at=now,
                        updated_at=now,
                    )
                ).rowcount
                or 0
            )

    _touch_batch_counters(db, batch.id)
    db.commit()
    return EvalBatchStopResponse(
        batch_id=batch.id,
        stopped_run_items=int(stopped_run_items),
        stopped_eval_runs=int(stopped_eval_runs),
        stopped_ability_tasks=int(stopped_ability_tasks),
    )


@router.post("/runs", response_model=EvalRunResponse)
def create_run(
    request: Request,
    response: Response,
    payload: EvalRunCreate,
    db: Session = Depends(get_db),
) -> EvalRunResponse:
    _require_public_enabled(request)
    created_by = _get_or_set_rater_id(request, response)
    run = get_eval_service().create_eval_run(
        workflow_version_id=payload.workflow_version_id,
        dataset_item_id=payload.dataset_item_id,
        input_oss_urls=payload.input_oss_urls_json,
        parameters=payload.parameters_json,
        created_by=created_by,
        db=db,
    )
    return _serialize_eval_run(run)


@router.get("/runs", response_model=EvalRunListResponse)
def list_runs(
    request: Request,
    response: Response,
    workflow_version_id: str | None = Query(None),
    batch_session_id: str | None = Query(None),
    batch_mode: bool | None = Query(None),
    mine_only: bool = Query(False),
    status: str | None = Query(None),
    unrated: bool | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> EvalRunListResponse:
    _require_public_enabled(request)
    rater_id = _get_or_set_rater_id(request, response)

    stmt = select(EvalRun)
    count_stmt = select(func.count()).select_from(EvalRun)
    if workflow_version_id:
        stmt = stmt.where(EvalRun.workflow_version_id == workflow_version_id)
        count_stmt = count_stmt.where(EvalRun.workflow_version_id == workflow_version_id)
    if mine_only:
        stmt = stmt.where(EvalRun.created_by == rater_id)
        count_stmt = count_stmt.where(EvalRun.created_by == rater_id)
    if batch_mode is True:
        batch_mode_expr = _batch_mode_expr()
        stmt = stmt.where(batch_mode_expr.in_(["1", "true", "True"]))
        count_stmt = count_stmt.where(batch_mode_expr.in_(["1", "true", "True"]))
    if batch_session_id:
        batch_expr = _batch_session_expr()
        stmt = stmt.where(batch_expr == batch_session_id.strip())
        count_stmt = count_stmt.where(batch_expr == batch_session_id.strip())
    if status:
        stmt = stmt.where(EvalRun.status == status)
        count_stmt = count_stmt.where(EvalRun.status == status)
    if unrated:
        subq = select(EvalAnnotation.id).where(EvalAnnotation.run_id == EvalRun.id)
        stmt = stmt.where(~exists(subq))
        count_stmt = count_stmt.where(~exists(subq))

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(stmt.order_by(EvalRun.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    rows, recovered = _recover_business_timeout_rows_for_display(db, rows, status_filter=status)
    if recovered and status:
        total = int(db.execute(count_stmt).scalar_one())
    billing_map = _build_eval_billing_map(db, rows)
    items = [_serialize_eval_run(row, billing_map.get(str(row.podi_task_id or ""))) for row in rows]
    return EvalRunListResponse(total=total, items=items)


@router.get("/runs/batches")
def list_run_batches(
    request: Request,
    response: Response,
    workflow_version_id: str | None = Query(None),
    mine_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List LoRA batch sessions grouped by `__batch_session_id`."""
    _require_public_enabled(request)
    rater_id = _get_or_set_rater_id(request, response)
    batch_expr = _batch_session_expr()
    expected_total_expr = func.cast(
        func.json_unquote(func.json_extract(EvalRun.parameters_json, "$.__batch_expected_total")),
        Integer,
    )
    expected_images_expr = func.cast(
        func.json_unquote(func.json_extract(EvalRun.parameters_json, "$.__batch_expected_images")),
        Integer,
    )
    expected_repeat_expr = func.cast(
        func.json_unquote(func.json_extract(EvalRun.parameters_json, "$.__batch_expected_repeat")),
        Integer,
    )
    completed_expr = case((EvalRun.status.in_(["succeeded", "failed"]), 1), else_=0)
    queued_expr = case((EvalRun.status == "queued", 1), else_=0)
    running_expr = case((EvalRun.status == "running", 1), else_=0)
    succeeded_expr = case((EvalRun.status == "succeeded", 1), else_=0)
    failed_expr = case((EvalRun.status == "failed", 1), else_=0)

    base_stmt = (
        select(
            batch_expr.label("batch_id"),
            func.min(EvalRun.workflow_version_id).label("workflow_version_id"),
            func.min(EvalWorkflowVersion.name).label("workflow_name"),
            func.count(EvalRun.id).label("total"),
            func.sum(completed_expr).label("completed"),
            func.sum(queued_expr).label("queued"),
            func.sum(running_expr).label("running"),
            func.sum(succeeded_expr).label("succeeded"),
            func.sum(failed_expr).label("failed"),
            func.max(expected_total_expr).label("expected_total"),
            func.max(expected_images_expr).label("expected_images"),
            func.max(expected_repeat_expr).label("expected_repeat"),
            func.max(EvalRun.created_at).label("latest_created_at"),
            func.max(EvalRun.updated_at).label("latest_updated_at"),
        )
        .select_from(EvalRun)
        .join(EvalWorkflowVersion, EvalWorkflowVersion.id == EvalRun.workflow_version_id, isouter=True)
        .where(batch_expr.is_not(None), batch_expr != "")
        .group_by(batch_expr)
    )
    if workflow_version_id:
        base_stmt = base_stmt.where(EvalRun.workflow_version_id == workflow_version_id)
    if mine_only:
        base_stmt = base_stmt.where(EvalRun.created_by == rater_id)
    total = int(db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar_one())
    rows = db.execute(base_stmt.order_by(func.max(EvalRun.created_at).desc()).offset(offset).limit(limit)).all()
    items: list[dict[str, Any]] = []
    for row in rows:
        latest_created = row.latest_created_at.isoformat() if row.latest_created_at else None
        latest_updated = row.latest_updated_at.isoformat() if row.latest_updated_at else None
        items.append(
            {
                "batchId": str(row.batch_id or ""),
                "workflowVersionId": str(row.workflow_version_id or "") if row.workflow_version_id else None,
                "workflowName": str(row.workflow_name or "") if row.workflow_name else None,
                "total": int(row.total or 0),
                "completed": int(row.completed or 0),
                "queued": int(row.queued or 0),
                "running": int(row.running or 0),
                "succeeded": int(row.succeeded or 0),
                "failed": int(row.failed or 0),
                "expectedTotal": int(row.expected_total or 0),
                "expectedImages": int(row.expected_images or 0),
                "expectedRepeat": int(row.expected_repeat or 0),
                "latestCreatedAt": latest_created,
                "latestUpdatedAt": latest_updated,
            }
        )
    return {"total": total, "items": items}


@router.post("/runs/batches/{batch_id}/stop")
def stop_run_batch(
    batch_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Stop queued/running runs in a batch and mark them failed."""
    _require_public_enabled(request)
    rater_id = _get_or_set_rater_id(request, response)
    batch_key = str(batch_id or "").strip()
    if not batch_key:
        raise HTTPException(status_code=400, detail="BATCH_ID_REQUIRED")

    batch_expr = _batch_session_expr()
    rows = db.execute(
        select(EvalRun.id, EvalRun.podi_task_id)
        .where(batch_expr == batch_key)
        .where(EvalRun.created_by == rater_id)
        .where(EvalRun.status.in_(["queued", "running"]))
    ).all()
    if not rows:
        return {"batchId": batch_key, "stoppedRuns": 0, "stoppedTasks": 0}

    run_ids = [str(row.id) for row in rows]
    task_ids = [
        str(row.podi_task_id)
        for row in rows
        if isinstance(row.podi_task_id, str) and row.podi_task_id.strip()
    ]
    now = datetime.utcnow()
    stopped_tasks = 0
    if task_ids:
        stopped_tasks = (
            db.execute(
                update(AbilityTask)
                .where(AbilityTask.id.in_(task_ids))
                .where(AbilityTask.status.in_(["queued", "running"]))
                .values(
                    status="failed",
                    error_message="MANUAL_STOP_BY_OPERATOR",
                    finished_at=now,
                    updated_at=now,
                )
            ).rowcount
            or 0
        )
    stopped_runs = (
        db.execute(
            update(EvalRun)
            .where(EvalRun.id.in_(run_ids))
            .where(EvalRun.status.in_(["queued", "running"]))
            .values(
                status="failed",
                error_message="MANUAL_STOP_BY_OPERATOR",
                updated_at=now,
            )
        ).rowcount
        or 0
    )
    db.commit()
    return {
        "batchId": batch_key,
        "stoppedRuns": int(stopped_runs),
        "stoppedTasks": int(stopped_tasks),
    }

@router.get("/runs/with-latest-annotation", response_model=EvalRunWithLatestAnnotationListResponse)
def list_runs_with_latest_annotation(
    request: Request,
    response: Response,
    workflow_version_id: str | None = Query(None),
    status: str | None = Query(None),
    unrated: bool | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> Any:
    """List runs and attach each run's latest annotation.

    This endpoint is optimized for the evaluation UI: filtering by rating/comment is easier
    when annotation info is present on each row.
    """
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)

    stmt = select(EvalRun)
    count_stmt = select(func.count()).select_from(EvalRun)
    if workflow_version_id:
        stmt = stmt.where(EvalRun.workflow_version_id == workflow_version_id)
        count_stmt = count_stmt.where(EvalRun.workflow_version_id == workflow_version_id)
    if status:
        stmt = stmt.where(EvalRun.status == status)
        count_stmt = count_stmt.where(EvalRun.status == status)
    if unrated:
        subq = select(EvalAnnotation.id).where(EvalAnnotation.run_id == EvalRun.id)
        stmt = stmt.where(~exists(subq))
        count_stmt = count_stmt.where(~exists(subq))

    total = int(db.execute(count_stmt).scalar_one())
    runs = (
        db.execute(
            stmt.options(
                load_only(
                    EvalRun.id,
                    EvalRun.workflow_version_id,
                    EvalRun.dataset_item_id,
                    EvalRun.input_oss_urls_json,
                    EvalRun.parameters_json,
                    EvalRun.status,
                    EvalRun.coze_execute_id,
                    EvalRun.coze_debug_url,
                    EvalRun.podi_task_id,
                    EvalRun.result_image_urls_json,
                    EvalRun.error_message,
                    EvalRun.duration_ms,
                    EvalRun.created_by,
                    EvalRun.created_at,
                    EvalRun.updated_at,
                )
            )
            .order_by(EvalRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    runs, recovered = _recover_business_timeout_rows_for_display(db, runs, status_filter=status)
    if recovered and status:
        total = int(db.execute(count_stmt).scalar_one())

    run_ids = [r.id for r in runs]
    latest_map: dict[str, EvalAnnotation] = {}
    if run_ids:
        ann_rows = (
            db.execute(
                select(EvalAnnotation)
                .where(EvalAnnotation.run_id.in_(run_ids))
                .order_by(EvalAnnotation.run_id.asc(), EvalAnnotation.created_at.desc())
            )
            .scalars()
            .all()
        )
        for ann in ann_rows:
            if ann.run_id not in latest_map:
                latest_map[ann.run_id] = ann

    billing_map = _build_eval_billing_map(db, runs)
    items: list[EvalRunWithLatestAnnotationResponse] = []
    for r in runs:
        items.append(
            EvalRunWithLatestAnnotationResponse.model_validate(
                {
                    **_serialize_eval_run(
                        r,
                        billing_map.get(str(r.podi_task_id or "")),
                        compact_output=True,
                    ).model_dump(),
                    "latest_annotation": EvalAnnotationResponse.model_validate(latest_map.get(r.id)).model_dump()
                    if latest_map.get(r.id)
                    else None,
                }
            )
        )
    return EvalRunWithLatestAnnotationListResponse(total=total, items=items)


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
def get_run(
    run_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> EvalRunResponse:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    get_eval_service().reconcile_business_run_for_eval(run_id)
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    billing_map = _build_eval_billing_map(db, [run])
    return _serialize_eval_run(run, billing_map.get(str(run.podi_task_id or "")))


@router.post("/runs/{run_id}/annotations", response_model=EvalAnnotationResponse)
def create_annotation(
    run_id: str,
    request: Request,
    response: Response,
    payload: EvalAnnotationCreate,
    db: Session = Depends(get_db),
) -> EvalAnnotation:
    _require_public_enabled(request)
    created_by = _get_or_set_rater_id(request, response)
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="RUN_NOT_FOUND")
    ann = EvalAnnotation(
        id=uuid4().hex,
        run_id=run_id,
        rating=payload.rating,
        tags_json=payload.tags_json,
        comment=payload.comment,
        created_by=created_by,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


@router.get("/runs/{run_id}/annotations", response_model=list[EvalAnnotationResponse])
def list_run_annotations(
    run_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> list[EvalAnnotation]:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    stmt = select(EvalAnnotation).where(EvalAnnotation.run_id == run_id).order_by(EvalAnnotation.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.get("/metrics/workflows")
def workflow_metrics(
    request: Request,
    response: Response,
    recent_hours: int = Query(72, ge=1, le=720),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return per-workflow aggregate rating metrics for business comparison."""
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    # avg rating + count per workflow_version_id
    rows = db.execute(
        select(
            EvalRun.workflow_version_id,
            func.count(func.distinct(EvalRun.id)).label("run_count"),
            func.count(EvalAnnotation.id).label("rating_count"),
            func.avg(EvalAnnotation.rating).label("avg_rating"),
        )
        .select_from(EvalRun)
        .join(EvalAnnotation, EvalAnnotation.run_id == EvalRun.id, isouter=True)
        .group_by(EvalRun.workflow_version_id)
    ).all()
    metrics: dict[str, Any] = {}
    for workflow_version_id, run_count, rating_count, avg_rating in rows:
        if not workflow_version_id:
            continue
        metrics[str(workflow_version_id)] = {
            "ratingCount": int(rating_count or 0),
            "avgRating": float(avg_rating) if avg_rating is not None else None,
            "runCount": int(run_count or 0),
            "recentRunCount": 0,
            "recentSuccessCount": 0,
            "recentFailureCount": 0,
            "recentRunningCount": 0,
            "recentNoOutputCount": 0,
            "recentOutputKindCounts": {"image": 0, "video": 0, "text": 0, "structured": 0, "none": 0},
            "recentHours": recent_hours,
        }
    recent_since = datetime.utcnow() - timedelta(hours=recent_hours)
    run_rows = db.execute(select(EvalRun).where(EvalRun.created_at >= recent_since)).scalars().all()
    for run in run_rows:
        workflow_version_id = str(run.workflow_version_id or "").strip()
        if not workflow_version_id:
            continue
        bucket = metrics.setdefault(
            workflow_version_id,
            {
                "ratingCount": 0,
                "avgRating": None,
                "runCount": 0,
                "recentRunCount": 0,
                "recentSuccessCount": 0,
                "recentFailureCount": 0,
                "recentRunningCount": 0,
                "recentNoOutputCount": 0,
                "recentOutputKindCounts": {"image": 0, "video": 0, "text": 0, "structured": 0, "none": 0},
                "recentHours": recent_hours,
            },
        )
        output_kind, has_result = _eval_run_output_kind(run)
        stage = derive_eval_run_status(
            status=run.status,
            podi_task_id=run.podi_task_id,
            error_message=run.error_message,
            has_result=has_result,
        )
        final_status = stage.final_status
        bucket["recentRunCount"] = int(bucket.get("recentRunCount") or 0) + 1
        if final_status == "success":
            bucket["recentSuccessCount"] = int(bucket.get("recentSuccessCount") or 0) + 1
        elif final_status in {"failed", "canceled"}:
            bucket["recentFailureCount"] = int(bucket.get("recentFailureCount") or 0) + 1
        else:
            bucket["recentRunningCount"] = int(bucket.get("recentRunningCount") or 0) + 1
        if str(run.status or "").lower() in {"succeeded", "success", "completed"} and not has_result:
            bucket["recentNoOutputCount"] = int(bucket.get("recentNoOutputCount") or 0) + 1
        kind_counts = bucket.setdefault(
            "recentOutputKindCounts",
            {"image": 0, "video": 0, "text": 0, "structured": 0, "none": 0},
        )
        if isinstance(kind_counts, dict):
            kind_counts[output_kind] = int(kind_counts.get(output_kind) or 0) + 1
        run_sort_at = run.updated_at or run.created_at
        last_sort_at = bucket.get("_lastRunSortAt")
        if last_sort_at is None or (run_sort_at is not None and run_sort_at > last_sort_at):
            bucket.update(
                {
                    "lastRunStatus": final_status,
                    "lastRunAt": run.updated_at.isoformat() if run.updated_at else None,
                    "lastRunHasOutput": has_result,
                    "lastRunOutputKind": output_kind,
                    "lastErrorCode": stage.error_code,
                    "lastErrorMessage": run.error_message,
                    "_lastRunSortAt": run_sort_at,
                }
            )
    for bucket in metrics.values():
        if isinstance(bucket, dict):
            bucket.pop("_lastRunSortAt", None)
    return {"metrics": metrics, "recentHours": recent_hours}
