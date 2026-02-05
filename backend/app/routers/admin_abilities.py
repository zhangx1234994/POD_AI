"""Admin endpoints for ability catalog management."""

from __future__ import annotations

import csv
import io
import json
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
from app.models.integration import Ability, AbilityInvocationLog, Executor, Workflow
from app.schemas import admin_abilities as schemas
from app.schemas import admin_ability_logs as log_schemas
from app.services.ability_seed import ensure_default_abilities
from app.services.ability_logs import ability_log_service
from app.services.executors.base import ExecutionContext
from app.services.executors.registry import registry

router = APIRouter(prefix="/admin/abilities", dependencies=[Depends(require_admin)])


def _generate_id(existing_id: str | None) -> str:
    return existing_id or uuid4().hex


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
            )
            for ability in abilities
        ]
        return schemas.AbilityOptionListResponse(items=items)


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


@router.get("/{ability_id}/logs", response_model=log_schemas.AbilityInvocationLogListResponse)
def list_ability_logs(
    ability_id: str,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    total = ability_log_service.count_logs(ability_id=ability_id)
    entries = ability_log_service.list_logs(ability_id=ability_id, limit=limit, offset=offset)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [log_schemas.AbilityInvocationLogRead.model_validate(entry) for entry in entries],
    }


@router.get("/logs", response_model=log_schemas.AbilityInvocationLogListResponse)
def list_all_ability_logs(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ability_id: str | None = Query(default=None, alias="abilityId"),
    provider: str | None = Query(default=None),
    capability_key: str | None = Query(default=None, alias="capabilityKey"),
):
    total = ability_log_service.count_logs(
        ability_id=ability_id,
        provider=provider,
        capability_key=capability_key,
    )
    entries = ability_log_service.list_logs(
        ability_id=ability_id,
        provider=provider,
        capability_key=capability_key,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [log_schemas.AbilityInvocationLogRead.model_validate(entry) for entry in entries],
    }


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
        return log_schemas.AbilityInvocationLogRead.model_validate(refreshed)


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
    executor_id: str | None = Query(default=None, alias="executorId"),
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
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
        stmt = select(AbilityInvocationLog).where(
            AbilityInvocationLog.created_at >= start_dt,
            AbilityInvocationLog.created_at <= end_dt,
        )
        if provider:
            stmt = stmt.where(AbilityInvocationLog.ability_provider == provider)
        if capability_key:
            stmt = stmt.where(AbilityInvocationLog.capability_key == capability_key)
        if ability_id:
            stmt = stmt.where(AbilityInvocationLog.ability_id == ability_id)
        if executor_id:
            stmt = stmt.where(AbilityInvocationLog.executor_id == executor_id)
        if status:
            stmt = stmt.where(AbilityInvocationLog.status == status)
        if source:
            stmt = stmt.where(AbilityInvocationLog.source == source)

        stmt = stmt.order_by(AbilityInvocationLog.created_at.desc()).limit(limit)
        rows = session.execute(stmt).scalars().all()

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
                "ability_provider",
                "capability_key",
                "ability_id",
                "ability_name",
                "executor_id",
                "executor_name",
                "executor_type",
                "source",
                "duration_ms",
                "stored_url",
                "error_message",
                "task_id",
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
            w.writerow(
                [
                    r.id,
                    r.created_at.isoformat() + "Z" if r.created_at else "",
                    r.status,
                    r.ability_provider,
                    r.capability_key,
                    r.ability_id or "",
                    r.ability_name or "",
                    r.executor_id or "",
                    r.executor_name or "",
                    r.executor_type or "",
                    r.source,
                    r.duration_ms if r.duration_ms is not None else "",
                    r.stored_url or "",
                    (r.error_message or "").replace("\n", " ").strip(),
                    r.task_id or "",
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
            func.max(last_success_expr).label("last_ok_at"),
            func.max(last_failed_expr).label("last_fail_at"),
        ).where(AbilityInvocationLog.created_at >= since)
        if provider:
            stmt = stmt.where(AbilityInvocationLog.ability_provider == provider)
        if capability_key:
            stmt = stmt.where(AbilityInvocationLog.capability_key == capability_key)
        stmt = stmt.group_by(*group_cols).order_by(func.count(AbilityInvocationLog.id).desc()).limit(200)
        base_rows = session.execute(stmt).all()

        # Percentiles: fetch a bounded sample of durations per bucket, only for success.
        buckets: list[log_schemas.AbilityInvocationLogMetricBucket] = []
        for row in base_rows:
            # Row shape depends on group_by_executor
            if group_by_executor:
                ability_provider, cap_key, exec_id, cnt, ok_cnt, fail_cnt, avg_ms, last_ok_at, last_fail_at = row
            else:
                ability_provider, cap_key, cnt, ok_cnt, fail_cnt, avg_ms, last_ok_at, last_fail_at = row
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
                    last_success_at=last_ok_at,
                    last_failed_at=last_fail_at,
                )
            )

    return log_schemas.AbilityInvocationLogMetricsResponse(window_hours=window_hours, buckets=buckets)
