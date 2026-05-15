"""Admin endpoints for ability catalog management."""

from __future__ import annotations

import csv
import io
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from types import SimpleNamespace

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import and_, case, func, select

from app.core.db import get_session
from app.deps.auth import require_admin
from app.models.integration import Ability, AbilityInvocationLog, AbilityTask, Executor, VendorModelCatalog, Workflow
from app.schemas import admin_abilities as schemas
from app.schemas import admin_ability_logs as log_schemas
from app.services.ability_seed import ensure_default_abilities
from app.services.ability_logs import ability_log_service
from app.services.executors.base import ExecutionContext
from app.services.executors.registry import registry
from app.services.task_status_contract import derive_ability_log_status
from app.services.task_id_codec import encode_task_id

router = APIRouter(prefix="/admin/abilities", dependencies=[Depends(require_admin)])
_TEMPLATE_REGISTRY_KEY = "__template_registry"
_TEMPLATE_HISTORY_LIMIT = 100


def _generate_id(existing_id: str | None) -> str:
    return existing_id or uuid4().hex


def _sanitize_template_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    cleaned = dict(metadata)
    cleaned.pop(_TEMPLATE_REGISTRY_KEY, None)
    return cleaned


def _get_template_registry(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {"current_template_id": None, "history": []}
    registry = metadata.get(_TEMPLATE_REGISTRY_KEY)
    if isinstance(registry, dict):
        current = registry.get("current_template_id")
        history = registry.get("history")
        return {
            "current_template_id": str(current).strip() if isinstance(current, str) and current.strip() else None,
            "history": history if isinstance(history, list) else [],
        }
    return {"current_template_id": None, "history": []}


def _set_template_registry(metadata: dict[str, Any] | None, registry: dict[str, Any]) -> dict[str, Any]:
    target = dict(metadata) if isinstance(metadata, dict) else {}
    target[_TEMPLATE_REGISTRY_KEY] = registry
    return target


def _snapshot_ability_template(
    ability: Ability,
    *,
    action: str,
    version_label: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    return {
        "id": f"tpl_{datetime.utcnow():%Y%m%d%H%M%S}_{uuid4().hex[:8]}",
        "version_label": (version_label or "").strip() or None,
        "action": action,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "notes": (notes or "").strip() or None,
        "default_params": deepcopy(ability.default_params) if isinstance(ability.default_params, dict) else {},
        "input_schema": deepcopy(ability.input_schema) if isinstance(ability.input_schema, dict) else {},
        "metadata": deepcopy(_sanitize_template_metadata(ability.extra_metadata)),
    }


def _normalize_template_history(history: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        template_id = str(item.get("id") or "").strip()
        if not template_id:
            continue
        normalized.append(item)
    normalized.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return normalized[:_TEMPLATE_HISTORY_LIMIT]


def _validate_template_payload(
    *,
    default_params: dict[str, Any] | None,
    input_schema: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if default_params is not None and not isinstance(default_params, dict):
        errors.append("default_params 必须是对象")
    if input_schema is not None and not isinstance(input_schema, dict):
        errors.append("input_schema 必须是对象")
    if metadata is not None and not isinstance(metadata, dict):
        errors.append("metadata 必须是对象")

    schema = input_schema if isinstance(input_schema, dict) else {}
    fields = schema.get("fields")
    if fields is not None and not isinstance(fields, list):
        errors.append("input_schema.fields 必须是数组")
    if isinstance(fields, list):
        for idx, field in enumerate(fields, start=1):
            if not isinstance(field, dict):
                errors.append(f"input_schema.fields[{idx}] 必须是对象")
                continue
            key = str(field.get("key") or "").strip()
            if not key:
                errors.append(f"input_schema.fields[{idx}] 缺少 key")
            field_type = str(field.get("type") or "").strip().lower()
            if not field_type:
                warnings.append(f"input_schema.fields[{idx}] 未设置 type，前端将按 text 处理")

    metadata_dict = metadata if isinstance(metadata, dict) else {}
    api_type = str(metadata_dict.get("api_type") or "").strip()
    if not api_type:
        warnings.append("metadata.api_type 为空，路由分支可能无法自动识别")
    model_id = str(metadata_dict.get("model_id") or "").strip()
    if not model_id:
        warnings.append("metadata.model_id 为空，后续排障定位成本较高")
    return errors, warnings


def _template_state_response(ability: Ability) -> schemas.AbilityTemplateStateResponse:
    metadata = ability.extra_metadata if isinstance(ability.extra_metadata, dict) else {}
    registry = _get_template_registry(metadata)
    history = _normalize_template_history(registry.get("history") if isinstance(registry, dict) else [])
    return schemas.AbilityTemplateStateResponse(
        ability_id=ability.id,
        current_template_id=registry.get("current_template_id"),
        history=[schemas.AbilityTemplateSnapshot.model_validate(item) for item in history],
    )


def _resolve_template_snapshot(metadata: dict[str, Any] | None) -> tuple[str | None, int]:
    registry = _get_template_registry(metadata)
    current_template_id = registry.get("current_template_id")
    history = _normalize_template_history(registry.get("history") if isinstance(registry, dict) else [])
    return current_template_id, len(history)


def _resolve_template_filtered_ability_ids(
    *,
    template_id: str | None,
    template_published: bool | None,
) -> list[str] | None:
    normalized_template_id = (template_id or "").strip() or None
    if normalized_template_id is None and template_published is None:
        return None
    with get_session() as session:
        rows = session.execute(select(Ability.id, Ability.extra_metadata)).all()
    matched_ids: list[str] = []
    for ability_id, metadata in rows:
        current_template_id, _history_count = _resolve_template_snapshot(metadata if isinstance(metadata, dict) else None)
        if normalized_template_id and current_template_id != normalized_template_id:
            continue
        if template_published is True and not current_template_id:
            continue
        if template_published is False and current_template_id:
            continue
        matched_ids.append(str(ability_id))
    return matched_ids


def _extract_callback_id(response_payload: dict[str, Any] | None) -> str | None:
    if not isinstance(response_payload, dict):
        return None
    candidates = ("callbackId", "callback_id", "taskId", "task_id", "promptId", "prompt_id")
    containers = [response_payload]
    data = response_payload.get("data")
    if isinstance(data, dict):
        containers.append(data)
    metadata = response_payload.get("metadata")
    if isinstance(metadata, dict):
        containers.append(metadata)
    result = response_payload.get("result")
    if isinstance(result, dict):
        containers.append(result)
    raw = response_payload.get("raw")
    if isinstance(raw, dict):
        containers.append(raw)
    for container in containers:
        for key in candidates:
            value = container.get(key)
            if isinstance(value, (str, int)):
                text = str(value).strip()
                if text:
                    return text
    return None


def _normalize_task_id(value: str | int | None, *, provider: str | None, executor_id: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("t1.") or text.startswith("ERR|"):
        return text
    return encode_task_id(task_id=text, provider=provider, executor_id=executor_id)


def _load_callback_task_map(log_ids: list[int]) -> dict[int, str]:
    if not log_ids:
        return {}
    with get_session() as session:
        rows = session.execute(
            select(AbilityTask.log_id, AbilityTask.id).where(AbilityTask.log_id.in_(log_ids))
        ).all()
    mapping: dict[int, str] = {}
    for log_id, task_id in rows:
        if log_id is None or not task_id:
            continue
        mapping[int(log_id)] = str(task_id)
    return mapping


def _attach_callback_ids(entries: list[AbilityInvocationLog]) -> list[AbilityInvocationLog]:
    if not entries:
        return entries
    log_ids = [entry.id for entry in entries if entry and entry.id]
    task_map = _load_callback_task_map(log_ids)
    for entry in entries:
        payload = entry.response_payload if isinstance(entry.response_payload, dict) else {}
        executor_hint = entry.executor_id
        if not executor_hint and isinstance(payload, dict):
            for key in ("executorId", "executor", "executor_id"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    executor_hint = value.strip()
                    break
                if isinstance(value, (int, float)):
                    executor_hint = str(value)
                    break
        raw_callback_id = task_map.get(entry.id) or _extract_callback_id(entry.response_payload)
        callback_id = _normalize_task_id(
            raw_callback_id,
            provider=entry.ability_provider,
            executor_id=executor_hint,
        )
        setattr(entry, "callback_id", callback_id)
    return entries


def _attach_stage_status(entries: list[AbilityInvocationLog]) -> list[AbilityInvocationLog]:
    if not entries:
        return entries
    for entry in entries:
        request_payload = entry.request_payload if isinstance(entry.request_payload, dict) else {}
        callback_configured = request_payload.get("callbackConfigured")
        if isinstance(callback_configured, str):
            callback_configured = callback_configured.strip().lower() in {"1", "true", "yes", "y"}
        elif not isinstance(callback_configured, bool):
            callback_configured = None
        stage = derive_ability_log_status(
            log_status=entry.status,
            callback_status=entry.callback_status,
            callback_http_status=entry.callback_http_status,
            callback_error=entry.callback_error,
            callback_configured=callback_configured,
            error_message=entry.error_message,
        )
        setattr(entry, "submit_status", stage.submit_status)
        setattr(entry, "final_status", stage.final_status)
        setattr(entry, "error_code", stage.error_code)
    return entries


def _load_template_summary_map(ability_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not ability_ids:
        return {}
    with get_session() as session:
        rows = session.execute(
            select(Ability.id, Ability.extra_metadata).where(Ability.id.in_(ability_ids))
        ).all()
    mapping: dict[str, dict[str, Any]] = {}
    for ability_id, metadata in rows:
        current_template_id, history_count = _resolve_template_snapshot(metadata if isinstance(metadata, dict) else None)
        mapping[str(ability_id)] = {
            "current_template_id": current_template_id,
            "history_count": history_count,
            "published": bool(current_template_id),
        }
    return mapping


def _attach_template_summary(entries: list[AbilityInvocationLog]) -> list[AbilityInvocationLog]:
    if not entries:
        return entries
    ability_ids = sorted({str(entry.ability_id) for entry in entries if entry and entry.ability_id})
    summary_map = _load_template_summary_map(ability_ids)
    for entry in entries:
        ability_id = str(entry.ability_id) if entry and entry.ability_id else ""
        summary = summary_map.get(ability_id) or {}
        setattr(entry, "ability_current_template_id", summary.get("current_template_id"))
        setattr(entry, "ability_template_history_count", int(summary.get("history_count") or 0))
        setattr(entry, "ability_template_published", bool(summary.get("published")))
    return entries


def _enrich_log_entries(entries: list[AbilityInvocationLog]) -> list[AbilityInvocationLog]:
    return _attach_template_summary(_attach_stage_status(_attach_callback_ids(entries)))


def _serialize_ability_log(
    entry: AbilityInvocationLog,
    *,
    include_payloads: bool,
) -> log_schemas.AbilityInvocationLogRead:
    item = log_schemas.AbilityInvocationLogRead.model_validate(entry)
    if include_payloads:
        return item
    item.request_payload = None
    item.response_payload = None
    item.result_assets = None
    item.callback_payload = None
    item.callback_response = None
    return item


@router.get("", response_model=list[schemas.AbilityRead])
def list_abilities() -> list[Ability]:
    with get_session() as session:
        ensure_default_abilities(session)
        stmt = select(Ability).order_by(Ability.provider.asc(), Ability.capability_key.asc())
        return session.execute(stmt).scalars().all()


@router.get("/options", response_model=schemas.AbilityOptionListResponse)
def list_ability_options(
    status: str | None = Query(default="active"),
    provider: str | None = Query(default=None),
) -> schemas.AbilityOptionListResponse:
    with get_session() as session:
        ensure_default_abilities(session)
        stmt = select(Ability)
        if status:
            stmt = stmt.where(Ability.status == status)
        if provider:
            stmt = stmt.where(Ability.provider == provider)
        stmt = stmt.order_by(Ability.provider.asc(), Ability.capability_key.asc())
        abilities = session.execute(stmt).scalars().all()
        items = [
            schemas.AbilityOption(
                id=ability.id,
                provider=ability.provider,
                category=ability.category,
                capability_key=ability.capability_key,
                version=ability.version,
                display_name=ability.display_name,
                description=ability.description,
                default_params=ability.default_params,
                input_schema=ability.input_schema,
                metadata=ability.extra_metadata,
                coze_workflow_id=ability.coze_workflow_id,
                vendor_model_id=ability.vendor_model_id,
            )
            for ability in abilities
        ]
        return schemas.AbilityOptionListResponse(items=items)


@router.get("/health/summary", response_model=schemas.AbilityHealthSummaryResponse)
def get_ability_health_summary(
    stale_hours: int = Query(default=24, alias="staleHours", ge=1, le=24 * 30),
    limit: int = Query(default=20, ge=1, le=100),
    provider: str | None = Query(default=None),
    status: str | None = Query(default=None),
    health_status: str | None = Query(default=None, alias="healthStatus"),
    needs_test: bool | None = Query(default=None, alias="needsTest"),
    stale_only: bool = Query(default=False, alias="staleOnly"),
) -> schemas.AbilityHealthSummaryResponse:
    """Return a lightweight health summary derived from recent ability logs."""

    return schemas.AbilityHealthSummaryResponse.model_validate(
        ability_log_service.refresh_health_summaries(
            provider=provider,
            status=status,
            health_status=health_status,
            needs_test=needs_test,
            stale_only=stale_only,
            stale_hours=stale_hours,
            limit=limit,
        )
    )


@router.post("/health/refresh", response_model=schemas.AbilityHealthSummaryResponse)
def refresh_ability_health_summary(
    stale_hours: int = Query(default=24, alias="staleHours", ge=1, le=24 * 30),
    limit: int = Query(default=20, ge=1, le=100),
    provider: str | None = Query(default=None),
    status: str | None = Query(default=None),
    health_status: str | None = Query(default=None, alias="healthStatus"),
    needs_test: bool | None = Query(default=None, alias="needsTest"),
    stale_only: bool = Query(default=False, alias="staleOnly"),
) -> schemas.AbilityHealthSummaryResponse:
    """Recompute health fields without calling upstream providers."""

    return schemas.AbilityHealthSummaryResponse.model_validate(
        ability_log_service.refresh_health_summaries(
            provider=provider,
            status=status,
            health_status=health_status,
            needs_test=needs_test,
            stale_only=stale_only,
            stale_hours=stale_hours,
            limit=limit,
        )
    )


@router.get("/health/export")
def export_ability_health_summary(
    stale_hours: int = Query(default=24, alias="staleHours", ge=1, le=24 * 30),
    limit: int = Query(default=500, ge=1, le=500),
    provider: str | None = Query(default=None),
    status: str | None = Query(default=None),
    health_status: str | None = Query(default=None, alias="healthStatus"),
    needs_test: bool | None = Query(default=None, alias="needsTest"),
    stale_only: bool = Query(default=False, alias="staleOnly"),
) -> Response:
    """Export the current ability retest list as CSV."""

    payload = ability_log_service.refresh_health_summaries(
        provider=provider,
        status=status,
        health_status=health_status,
        needs_test=needs_test,
        stale_only=stale_only,
        stale_hours=stale_hours,
        limit=limit,
    )
    output = io.StringIO()
    fieldnames = [
        "abilityId",
        "displayName",
        "provider",
        "capabilityKey",
        "status",
        "healthStatus",
        "lastHealthCheckAt",
        "successRate",
        "finishedLogCount",
        "latestLogStatus",
        "latestLogAt",
        "stale",
        "needsTest",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        writer.writerow({key: item.get(key) for key in fieldnames})
    filename = f"ability-health-{datetime.utcnow():%Y%m%d%H%M%S}.csv"
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", response_model=schemas.AbilityRead)
def create_ability(payload: schemas.AbilityCreate) -> Ability:
    with get_session() as session:
        ability = Ability(
            id=_generate_id(payload.id),
            provider=payload.provider,
            category=payload.category,
            capability_key=payload.capability_key,
            version=payload.version,
            display_name=payload.display_name,
            description=payload.description,
            status=payload.status,
            ability_type=payload.ability_type or "api",
            executor_id=payload.executor_id,
            workflow_id=payload.workflow_id,
            vendor_model_id=payload.vendor_model_id,
            coze_workflow_id=payload.coze_workflow_id,
            default_params=payload.default_params,
            input_schema=payload.input_schema,
            extra_metadata=payload.metadata,
        )
        if ability.executor_id:
            executor = session.get(Executor, ability.executor_id)
            if not executor:
                raise HTTPException(status_code=400, detail="EXECUTOR_NOT_FOUND")
        if ability.workflow_id:
            workflow = session.get(Workflow, ability.workflow_id)
            if not workflow:
                raise HTTPException(status_code=400, detail="WORKFLOW_NOT_FOUND")
        if ability.vendor_model_id:
            vendor_model = session.get(VendorModelCatalog, ability.vendor_model_id)
            if not vendor_model:
                raise HTTPException(status_code=400, detail="VENDOR_MODEL_NOT_FOUND")
        session.add(ability)
        session.commit()
        session.refresh(ability)
        return ability


@router.put("/{ability_id}", response_model=schemas.AbilityRead)
def update_ability(ability_id: str, payload: schemas.AbilityUpdate) -> Ability:
    with get_session() as session:
        ability = session.get(Ability, ability_id)
        if not ability:
            raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND")
        data = payload.model_dump(exclude_unset=True)
        if "metadata" in data:
            data["extra_metadata"] = data.pop("metadata")
        if "executor_id" in data and data["executor_id"]:
            executor = session.get(Executor, data["executor_id"])
            if not executor:
                raise HTTPException(status_code=400, detail="EXECUTOR_NOT_FOUND")
        if "workflow_id" in data and data["workflow_id"]:
            workflow = session.get(Workflow, data["workflow_id"])
            if not workflow:
                raise HTTPException(status_code=400, detail="WORKFLOW_NOT_FOUND")
        if "vendor_model_id" in data and data["vendor_model_id"]:
            vendor_model = session.get(VendorModelCatalog, data["vendor_model_id"])
            if not vendor_model:
                raise HTTPException(status_code=400, detail="VENDOR_MODEL_NOT_FOUND")
        for key, value in data.items():
            setattr(ability, key, value)
        session.add(ability)
        session.commit()
        session.refresh(ability)
        return ability


@router.delete("/{ability_id}")
def delete_ability(ability_id: str) -> dict[str, str]:
    with get_session() as session:
        ability = session.get(Ability, ability_id)
        if not ability:
            raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND")
        session.delete(ability)
        session.commit()
        return {"status": "deleted"}


@router.get("/{ability_id}/template", response_model=schemas.AbilityTemplateStateResponse)
def get_ability_template_state(ability_id: str) -> schemas.AbilityTemplateStateResponse:
    with get_session() as session:
        ability = session.get(Ability, ability_id)
        if not ability:
            raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND")
        return _template_state_response(ability)


@router.post("/{ability_id}/template/validate", response_model=schemas.AbilityTemplateValidateResponse)
def validate_ability_template(
    ability_id: str,
    payload: schemas.AbilityTemplateValidateRequest | None = None,
) -> schemas.AbilityTemplateValidateResponse:
    with get_session() as session:
        ability = session.get(Ability, ability_id)
        if not ability:
            raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND")
        has_override = payload is not None and payload.model_dump(exclude_none=True) != {}
        default_params = payload.default_params if has_override and payload else ability.default_params
        input_schema = payload.input_schema if has_override and payload else ability.input_schema
        metadata = payload.metadata if has_override and payload else _sanitize_template_metadata(ability.extra_metadata)
        errors, warnings = _validate_template_payload(
            default_params=default_params if isinstance(default_params, dict) else None,
            input_schema=input_schema if isinstance(input_schema, dict) else None,
            metadata=metadata if isinstance(metadata, dict) else None,
        )
        return schemas.AbilityTemplateValidateResponse(ok=len(errors) == 0, errors=errors, warnings=warnings)


@router.post("/{ability_id}/template/publish", response_model=schemas.AbilityTemplateStateResponse)
def publish_ability_template(
    ability_id: str,
    payload: schemas.AbilityTemplatePublishRequest | None = None,
) -> schemas.AbilityTemplateStateResponse:
    with get_session() as session:
        ability = session.get(Ability, ability_id)
        if not ability:
            raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND")
        errors, _warnings = _validate_template_payload(
            default_params=ability.default_params if isinstance(ability.default_params, dict) else {},
            input_schema=ability.input_schema if isinstance(ability.input_schema, dict) else {},
            metadata=_sanitize_template_metadata(ability.extra_metadata),
        )
        if errors:
            raise HTTPException(status_code=400, detail="ABILITY_TEMPLATE_INVALID")
        metadata = ability.extra_metadata if isinstance(ability.extra_metadata, dict) else {}
        registry = _get_template_registry(metadata)
        history = _normalize_template_history(registry.get("history") if isinstance(registry, dict) else [])
        snapshot = _snapshot_ability_template(
            ability,
            action="publish",
            version_label=payload.version_label if payload else None,
            notes=payload.notes if payload else None,
        )
        history = _normalize_template_history([snapshot] + history)
        registry = {"current_template_id": snapshot["id"], "history": history}
        ability.extra_metadata = _set_template_registry(metadata, registry)
        session.add(ability)
        session.commit()
        session.refresh(ability)
        return _template_state_response(ability)


@router.post("/{ability_id}/template/rollback", response_model=schemas.AbilityTemplateStateResponse)
def rollback_ability_template(
    ability_id: str,
    payload: schemas.AbilityTemplateRollbackRequest,
) -> schemas.AbilityTemplateStateResponse:
    with get_session() as session:
        ability = session.get(Ability, ability_id)
        if not ability:
            raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND")
        metadata = ability.extra_metadata if isinstance(ability.extra_metadata, dict) else {}
        registry = _get_template_registry(metadata)
        history = _normalize_template_history(registry.get("history") if isinstance(registry, dict) else [])
        target = None
        for item in history:
            if str(item.get("id")) == payload.template_id:
                target = item
                break
        if not target:
            raise HTTPException(status_code=404, detail="ABILITY_TEMPLATE_NOT_FOUND")
        backup = _snapshot_ability_template(
            ability,
            action="rollback_backup",
            version_label=None,
            notes=(payload.notes or "").strip() or f"rollback->{payload.template_id}",
        )
        restored_default_params = target.get("default_params")
        restored_input_schema = target.get("input_schema")
        restored_metadata = target.get("metadata")
        ability.default_params = restored_default_params if isinstance(restored_default_params, dict) else {}
        ability.input_schema = restored_input_schema if isinstance(restored_input_schema, dict) else {}
        base_metadata = restored_metadata if isinstance(restored_metadata, dict) else {}
        next_history = _normalize_template_history([backup] + history)
        next_registry = {"current_template_id": payload.template_id, "history": next_history}
        ability.extra_metadata = _set_template_registry(base_metadata, next_registry)
        session.add(ability)
        session.commit()
        session.refresh(ability)
        return _template_state_response(ability)


@router.get("/{ability_id}/logs", response_model=log_schemas.AbilityInvocationLogListResponse)
def list_ability_logs(
    ability_id: str,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    since_hours: int = Query(default=6, ge=0, le=24 * 30, alias="sinceHours"),
    include_payloads: bool = Query(default=False, alias="includePayloads"),
    search: str | None = Query(default=None, max_length=128),
    callback_failed: bool = Query(default=False, alias="callbackFailed"),
):
    total = ability_log_service.count_logs(
        ability_id=ability_id,
        search=search,
        callback_failed=callback_failed,
        since_hours=since_hours,
    )
    entries = ability_log_service.list_logs(
        ability_id=ability_id,
        search=search,
        callback_failed=callback_failed,
        since_hours=since_hours,
        limit=limit,
        offset=offset,
    )
    entries = _enrich_log_entries(entries)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_serialize_ability_log(entry, include_payloads=include_payloads) for entry in entries],
    }


@router.get("/logs", response_model=log_schemas.AbilityInvocationLogListResponse)
def list_all_ability_logs(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    since_hours: int = Query(default=6, ge=0, le=24 * 30, alias="sinceHours"),
    include_payloads: bool = Query(default=False, alias="includePayloads"),
    ability_id: str | None = Query(default=None, alias="abilityId"),
    provider: str | None = Query(default=None),
    capability_key: str | None = Query(default=None, alias="capabilityKey"),
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    template_id: str | None = Query(default=None, alias="templateId"),
    template_published: bool | None = Query(default=None, alias="templatePublished"),
    search: str | None = Query(default=None, max_length=128),
    callback_failed: bool = Query(default=False, alias="callbackFailed"),
):
    template_ability_ids = _resolve_template_filtered_ability_ids(
        template_id=template_id,
        template_published=template_published,
    )
    total = ability_log_service.count_logs(
        ability_id=ability_id,
        ability_ids=template_ability_ids,
        provider=provider,
        capability_key=capability_key,
        status=status,
        source=source,
        search=search,
        callback_failed=callback_failed,
        since_hours=since_hours,
    )
    entries = ability_log_service.list_logs(
        ability_id=ability_id,
        ability_ids=template_ability_ids,
        provider=provider,
        capability_key=capability_key,
        status=status,
        source=source,
        search=search,
        callback_failed=callback_failed,
        since_hours=since_hours,
        limit=limit,
        offset=offset,
    )
    entries = _enrich_log_entries(entries)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_serialize_ability_log(entry, include_payloads=include_payloads) for entry in entries],
    }


@router.get("/logs/{log_id:int}", response_model=log_schemas.AbilityInvocationLogRead)
def get_ability_log(log_id: int):
    with get_session() as session:
        log = session.get(AbilityInvocationLog, log_id)
        if not log:
            raise HTTPException(status_code=404, detail="ABILITY_LOG_NOT_FOUND")
        enriched = _enrich_log_entries([log])[0]
        return _serialize_ability_log(enriched, include_payloads=True)


@router.post("/logs/{log_id}/resolve", response_model=log_schemas.AbilityInvocationLogRead)
def resolve_comfyui_log(log_id: int):
    with get_session() as session:
        log = session.get(AbilityInvocationLog, log_id)
        if not log:
            raise HTTPException(status_code=404, detail="ABILITY_LOG_NOT_FOUND")
        if (log.ability_provider or "").lower() != "comfyui":
            raise HTTPException(status_code=400, detail="ABILITY_LOG_NOT_COMFYUI")
        if log.result_assets:
            return log_schemas.AbilityInvocationLogRead.model_validate(log)
        payload = log.response_payload or {}
        prompt_id = payload.get("promptId") or payload.get("taskId")
        base_url = payload.get("baseUrl")
        executor_id = payload.get("executorId") or payload.get("executor") or log.executor_id
        output_node_ids = payload.get("outputNodeIds") or payload.get("output_node_ids")
        if (not base_url or not prompt_id) and executor_id:
            executor = session.get(Executor, str(executor_id))
            if executor:
                cfg = executor.config or {}
                ex_base = (executor.base_url or cfg.get("baseUrl") or cfg.get("base_url") or "").strip()
                if ex_base:
                    base_url = ex_base
        if not (isinstance(prompt_id, str) and prompt_id.strip()):
            raise HTTPException(status_code=400, detail="COMFYUI_PROMPT_ID_REQUIRED")
        if not (isinstance(base_url, str) and base_url.strip()):
            raise HTTPException(status_code=400, detail="COMFYUI_BASE_URL_REQUIRED")

    adapter = registry.get("comfyui")
    if adapter is None:
        raise HTTPException(status_code=500, detail="COMFYUI_ADAPTER_MISSING")

    history_url = f"{base_url.rstrip('/')}/history/{prompt_id}"
    resp = httpx.get(history_url, timeout=15)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"COMFYUI_HISTORY_HTTP_{resp.status_code}")
    data = resp.json()
    entry = data.get(prompt_id) if isinstance(data, dict) else None
    if not isinstance(entry, dict):
        raise HTTPException(status_code=502, detail="COMFYUI_HISTORY_INVALID")

    output_nodes = None
    if isinstance(output_node_ids, list):
        output_nodes = {str(x) for x in output_node_ids if str(x).strip()}

    outputs = adapter._extract_outputs(entry, output_node_ids=output_nodes)  # type: ignore[attr-defined]
    hist = outputs.get("history") if isinstance(outputs, dict) else None
    status_dict = hist.get("status") if isinstance(hist, dict) else None
    status_str = str((status_dict or {}).get("status_str") or "").lower()
    if status_str and status_str != "success":
        raise HTTPException(status_code=409, detail=f"COMFYUI_STATUS_{status_str}")

    images = outputs.get("images") if isinstance(outputs, dict) else None
    if not isinstance(images, list) or not images:
        raise HTTPException(status_code=409, detail="COMFYUI_IMAGES_EMPTY")

    ctx = ExecutionContext(
        task=SimpleNamespace(id=f"log-{log_id}", user_id="admin", assets=[]),
        workflow=SimpleNamespace(id="admin_log_resolve", definition={}, extra_metadata={}),
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
        raise HTTPException(status_code=409, detail="COMFYUI_ASSETS_EMPTY")

    resolved_payload = dict(payload)
    resolved_payload["assets"] = assets
    resolved_payload["images"] = assets
    resolved_payload["status"] = "succeeded"
    ability_log_service.finish_success(log_id, response_payload=resolved_payload, duration_ms=log.duration_ms)

    with get_session() as session:
        refreshed = session.get(AbilityInvocationLog, log_id)
        if not refreshed:
            raise HTTPException(status_code=404, detail="ABILITY_LOG_NOT_FOUND")
        enriched = _enrich_log_entries([refreshed])[0]
        return log_schemas.AbilityInvocationLogRead.model_validate(enriched)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    # Support unix seconds / millis.
    if v.isdigit():
        try:
            ts = int(v)
            if ts > 10_000_000_000:
                ts = ts // 1000
            return datetime.utcfromtimestamp(ts)
        except (ValueError, OSError):
            return None
    try:
        # Accept ISO 8601 (UTC recommended).
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return None


@router.get("/logs/export")
def export_ability_logs(
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    limit: int = Query(default=2000, ge=1, le=20000),
    provider: str | None = Query(default=None),
    capability_key: str | None = Query(default=None, alias="capabilityKey"),
    ability_id: str | None = Query(default=None, alias="abilityId"),
    template_id: str | None = Query(default=None, alias="templateId"),
    template_published: bool | None = Query(default=None, alias="templatePublished"),
    executor_id: str | None = Query(default=None, alias="executorId"),
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=128),
    callback_failed: bool = Query(default=False, alias="callbackFailed"),
    since_hours: int = Query(default=24, ge=1, le=24 * 30, alias="sinceHours"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
) -> Response:
    """Export ability invocation logs for auditing/debug.

    Note: payload fields are already sanitized when being written to DB.
    """
    start_dt = _parse_dt(start) or (datetime.utcnow() - timedelta(hours=since_hours))
    end_dt = _parse_dt(end) or datetime.utcnow()

    with get_session() as session:
        template_ability_ids = _resolve_template_filtered_ability_ids(
            template_id=template_id,
            template_published=template_published,
        )
        stmt = select(AbilityInvocationLog).where(
            AbilityInvocationLog.created_at >= start_dt,
            AbilityInvocationLog.created_at <= end_dt,
        )
        if template_ability_ids is not None:
            if not template_ability_ids:
                rows: list[AbilityInvocationLog] = []
                stmt = None
            else:
                stmt = stmt.where(AbilityInvocationLog.ability_id.in_(template_ability_ids))

        if stmt is not None:
            stmt = ability_log_service._apply_log_filters(
                stmt,
                ability_id=ability_id,
                provider=provider,
                capability_key=capability_key,
                status=status,
                source=source,
                search=search,
                callback_failed=callback_failed,
            )
        if stmt is not None and executor_id:
            stmt = stmt.where(AbilityInvocationLog.executor_id == executor_id)

        if stmt is not None:
            stmt = stmt.order_by(AbilityInvocationLog.created_at.desc()).limit(limit)
            rows = session.execute(stmt).scalars().all()

    rows = _enrich_log_entries(rows)

    if format == "json":
        data = [log_schemas.AbilityInvocationLogRead.model_validate(r).model_dump() for r in rows]
        filename = f"ability_logs_{start_dt.date().isoformat()}_{end_dt.date().isoformat()}.json"
        payload = json.dumps(
            jsonable_encoder(
                {
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "window": {"start": start_dt.isoformat() + "Z", "end": end_dt.isoformat() + "Z"},
                    "count": len(data),
                    "items": data,
                }
            ),
            ensure_ascii=True,
        ).encode("utf-8")
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # CSV export
    filename = f"ability_logs_{start_dt.date().isoformat()}_{end_dt.date().isoformat()}.csv"

    def _gen():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "id",
                "created_at",
                "status",
                "submit_status",
                "final_status",
                "ability_provider",
                "capability_key",
                "ability_id",
                "ability_name",
                "ability_current_template_id",
                "ability_template_history_count",
                "ability_template_published",
                "executor_id",
                "executor_name",
                "executor_type",
                "source",
                "duration_ms",
                "stored_url",
                "output_kind",
                "output_image_count",
                "output_video_count",
                "output_text_count",
                "output_structured_count",
                "output_asset_count",
                "output_primary_url",
                "output_text_preview",
                "error_message",
                "error_code",
                "task_id",
                "callback_id",
                "trace_id",
                "workflow_run_id",
                "request_payload",
                "response_payload",
                "result_assets",
            ]
        )
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        for r in rows:
            read = log_schemas.AbilityInvocationLogRead.model_validate(r)
            summary = read.output_summary
            w.writerow(
                [
                    r.id,
                    r.created_at.isoformat() + "Z" if r.created_at else "",
                    r.status,
                    getattr(r, "submit_status", "") or "",
                    getattr(r, "final_status", "") or "",
                    r.ability_provider,
                    r.capability_key,
                    r.ability_id or "",
                    r.ability_name or "",
                    getattr(r, "ability_current_template_id", None) or "",
                    getattr(r, "ability_template_history_count", None) or 0,
                    "true" if bool(getattr(r, "ability_template_published", False)) else "false",
                    r.executor_id or "",
                    r.executor_name or "",
                    r.executor_type or "",
                    r.source,
                    r.duration_ms if r.duration_ms is not None else "",
                    r.stored_url or "",
                    summary.primary_kind or "",
                    summary.image_count,
                    summary.video_count,
                    summary.text_count,
                    summary.structured_count,
                    summary.asset_count,
                    summary.primary_url or "",
                    summary.text_preview or "",
                    (r.error_message or "").replace("\n", " ").strip(),
                    getattr(r, "error_code", None) or "",
                    r.task_id or "",
                    getattr(r, "callback_id", None) or "",
                    r.trace_id or "",
                    r.workflow_run_id or "",
                    json.dumps(r.request_payload, ensure_ascii=True) if r.request_payload is not None else "",
                    json.dumps(r.response_payload, ensure_ascii=True) if r.response_payload is not None else "",
                    json.dumps(r.result_assets, ensure_ascii=True) if r.result_assets is not None else "",
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        _gen(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/logs/metrics", response_model=log_schemas.AbilityInvocationLogMetricsResponse)
def get_ability_log_metrics(
    window_hours: int = Query(default=24, ge=1, le=24 * 30, alias="windowHours"),
    provider: str | None = Query(default=None),
    capability_key: str | None = Query(default=None, alias="capabilityKey"),
    group_by_executor: bool = Query(default=False, alias="groupByExecutor"),
) -> log_schemas.AbilityInvocationLogMetricsResponse:
    """Lightweight monitoring buckets for the admin console.

    Percentiles are computed best-effort from a capped sample (per bucket).
    """
    since = datetime.utcnow() - timedelta(hours=window_hours)

    with get_session() as session:
        group_cols = [AbilityInvocationLog.ability_provider, AbilityInvocationLog.capability_key]
        if group_by_executor:
            group_cols.append(AbilityInvocationLog.executor_id)

        success_expr = case((AbilityInvocationLog.status == "success", 1), else_=0)
        failed_expr = case((AbilityInvocationLog.status == "failed", 1), else_=0)
        last_success_expr = case((AbilityInvocationLog.status == "success", AbilityInvocationLog.created_at), else_=None)
        last_failed_expr = case((AbilityInvocationLog.status == "failed", AbilityInvocationLog.created_at), else_=None)

        stmt = select(
            *group_cols,
            func.count(AbilityInvocationLog.id).label("cnt"),
            func.sum(success_expr).label("ok_cnt"),
            func.sum(failed_expr).label("fail_cnt"),
            func.avg(AbilityInvocationLog.duration_ms).label("avg_ms"),
            func.sum(AbilityInvocationLog.cost_amount).label("total_cost"),
            func.avg(AbilityInvocationLog.cost_amount).label("avg_cost"),
            func.max(last_success_expr).label("last_ok_at"),
            func.max(last_failed_expr).label("last_fail_at"),
        ).where(AbilityInvocationLog.created_at >= since)
        if provider:
            stmt = stmt.where(AbilityInvocationLog.ability_provider == provider)
        if capability_key:
            stmt = stmt.where(AbilityInvocationLog.capability_key == capability_key)
        stmt = stmt.group_by(*group_cols).order_by(func.count(AbilityInvocationLog.id).desc()).limit(200)
        base_rows = session.execute(stmt).all()

        total_stmt = select(
            func.count(AbilityInvocationLog.id).label("total_cnt"),
            func.sum(success_expr).label("total_ok_cnt"),
            func.sum(failed_expr).label("total_fail_cnt"),
            func.sum(case((AbilityInvocationLog.cost_amount.is_(None), 1), else_=0)).label("uncosted_cnt"),
            func.sum(AbilityInvocationLog.cost_amount).label("total_cost"),
            func.avg(AbilityInvocationLog.cost_amount).label("avg_cost"),
        ).where(AbilityInvocationLog.created_at >= since)
        if provider:
            total_stmt = total_stmt.where(AbilityInvocationLog.ability_provider == provider)
        if capability_key:
            total_stmt = total_stmt.where(AbilityInvocationLog.capability_key == capability_key)
        total_row = session.execute(total_stmt).one()

        provider_cost_stmt = (
            select(
                AbilityInvocationLog.ability_provider.label("k"),
                func.count(AbilityInvocationLog.id).label("cnt"),
                func.sum(AbilityInvocationLog.cost_amount).label("total_cost"),
                func.avg(AbilityInvocationLog.cost_amount).label("avg_cost"),
            )
            .where(AbilityInvocationLog.created_at >= since)
            .group_by(AbilityInvocationLog.ability_provider)
            .order_by(func.sum(AbilityInvocationLog.cost_amount).desc())
            .limit(20)
        )
        if provider:
            provider_cost_stmt = provider_cost_stmt.where(AbilityInvocationLog.ability_provider == provider)
        if capability_key:
            provider_cost_stmt = provider_cost_stmt.where(AbilityInvocationLog.capability_key == capability_key)
        provider_cost_rows = session.execute(provider_cost_stmt).all()

        currency_cost_stmt = (
            select(
                func.coalesce(AbilityInvocationLog.currency, "UNKNOWN").label("k"),
                func.count(AbilityInvocationLog.id).label("cnt"),
                func.sum(AbilityInvocationLog.cost_amount).label("total_cost"),
                func.avg(AbilityInvocationLog.cost_amount).label("avg_cost"),
            )
            .where(AbilityInvocationLog.created_at >= since)
            .group_by(func.coalesce(AbilityInvocationLog.currency, "UNKNOWN"))
            .order_by(func.sum(AbilityInvocationLog.cost_amount).desc())
            .limit(20)
        )
        if provider:
            currency_cost_stmt = currency_cost_stmt.where(AbilityInvocationLog.ability_provider == provider)
        if capability_key:
            currency_cost_stmt = currency_cost_stmt.where(AbilityInvocationLog.capability_key == capability_key)
        currency_cost_rows = session.execute(currency_cost_stmt).all()

        # Percentiles: fetch a bounded sample of durations per bucket, only for success.
        buckets: list[log_schemas.AbilityInvocationLogMetricBucket] = []
        for row in base_rows:
            # Row shape depends on group_by_executor
            if group_by_executor:
                ability_provider, cap_key, exec_id, cnt, ok_cnt, fail_cnt, avg_ms, total_cost, avg_cost, last_ok_at, last_fail_at = row
            else:
                ability_provider, cap_key, cnt, ok_cnt, fail_cnt, avg_ms, total_cost, avg_cost, last_ok_at, last_fail_at = row
                exec_id = None

            # Load sample durations (capped) to compute p50/p95.
            dur_stmt = (
                select(AbilityInvocationLog.duration_ms)
                .where(
                    and_(
                        AbilityInvocationLog.created_at >= since,
                        AbilityInvocationLog.ability_provider == ability_provider,
                        AbilityInvocationLog.capability_key == cap_key,
                        AbilityInvocationLog.status == "success",
                        AbilityInvocationLog.duration_ms.is_not(None),
                    )
                )
                .order_by(AbilityInvocationLog.created_at.desc())
                .limit(800)
            )
            if group_by_executor:
                dur_stmt = dur_stmt.where(AbilityInvocationLog.executor_id == exec_id)
            durations = [int(x) for (x,) in session.execute(dur_stmt).all() if x is not None]
            durations.sort()
            p50 = None
            p95 = None
            if durations:
                p50 = durations[int((len(durations) - 1) * 0.5)]
                p95 = durations[int((len(durations) - 1) * 0.95)]

            total = int(cnt or 0)
            ok = int(ok_cnt or 0)
            fail = int(fail_cnt or 0)
            rate = (ok / total) if total > 0 else None
            buckets.append(
                log_schemas.AbilityInvocationLogMetricBucket(
                    ability_provider=str(ability_provider),
                    capability_key=str(cap_key),
                    executor_id=str(exec_id) if exec_id else None,
                    count=total,
                    success_count=ok,
                    failed_count=fail,
                    success_rate=rate,
                    avg_duration_ms=float(avg_ms) if avg_ms is not None else None,
                    p50_duration_ms=p50,
                    p95_duration_ms=p95,
                    total_cost=float(total_cost) if total_cost is not None else None,
                    avg_cost=float(avg_cost) if avg_cost is not None else None,
                    last_success_at=last_ok_at,
                    last_failed_at=last_fail_at,
                )
            )

    return log_schemas.AbilityInvocationLogMetricsResponse(
        window_hours=window_hours,
        total_count=int(total_row.total_cnt or 0),
        total_success_count=int(total_row.total_ok_cnt or 0),
        total_failed_count=int(total_row.total_fail_cnt or 0),
        uncosted_count=int(total_row.uncosted_cnt or 0),
        total_cost=float(total_row.total_cost) if total_row.total_cost is not None else None,
        avg_cost_per_call=float(total_row.avg_cost) if total_row.avg_cost is not None else None,
        provider_totals=[
            log_schemas.AbilityLogCostSummary(
                key=str(row.k),
                count=int(row.cnt or 0),
                total_cost=float(row.total_cost) if row.total_cost is not None else None,
                avg_cost=float(row.avg_cost) if row.avg_cost is not None else None,
            )
            for row in provider_cost_rows
            if row.k
        ],
        currency_totals=[
            log_schemas.AbilityLogCostSummary(
                key=str(row.k),
                count=int(row.cnt or 0),
                total_cost=float(row.total_cost) if row.total_cost is not None else None,
                avg_cost=float(row.avg_cost) if row.avg_cost is not None else None,
            )
            for row in currency_cost_rows
            if row.k
        ],
        buckets=buckets,
    )
