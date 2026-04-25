"""Business capability orchestration service."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.db import get_session
from app.models.integration import (
    Ability,
    AbilityInvocationLog,
    AbilityTask,
    BusinessCapability,
    BusinessRun,
    BusinessRunStep,
    VendorModelCatalog,
)
from app.models.user import User
from app.schemas.abilities import AbilityInvokeRequest
from app.schemas.business import BusinessCapabilityCreateRequest, BusinessCapabilityUpdateRequest, BusinessRunCreateRequest
from app.services.ability_seed import ensure_default_abilities
from app.services.ability_task_service import get_ability_task_service
from app.services.business_seed import ensure_default_business_capabilities
from app.services.task_id_codec import encode_task_id


logger = logging.getLogger(__name__)
FINALIZE_INTERVAL_SECONDS = 6
FINALIZE_BATCH_SIZE = 30
RECIPE_EXECUTABLE_STEP_TYPES = {"ability_task", "comfyui_workflow", "vendor_api", "vl_analyze", "vl_analyze_image"}
RECIPE_PASSIVE_STEP_TYPES = {"input_mapping", "output_mapping", "prompt_template", "note"}


class BusinessRunService:
    def __init__(self) -> None:
        self._thread_started = False
        self._start_finalize_thread()

    def list_capabilities(self) -> list[BusinessCapability]:
        with get_session() as session:
            ensure_default_abilities(session)
            ensure_default_business_capabilities(session)
            rows = (
                session.execute(
                    select(BusinessCapability)
                    .order_by(
                        BusinessCapability.business_key.asc(),
                        BusinessCapability.is_default.desc(),
                        BusinessCapability.release_time.desc(),
                    )
                )
                .scalars()
                .all()
            )
            return [self._capability_to_dict(row, session=session) for row in rows]

    def create_capability(self, payload: BusinessCapabilityCreateRequest) -> dict[str, Any]:
        business_key = self._required_text(payload.businessKey, "BUSINESS_KEY_REQUIRED")
        version = self._required_text(payload.version, "BUSINESS_VERSION_REQUIRED")
        display_name = self._required_text(payload.displayName, "BUSINESS_DISPLAY_NAME_REQUIRED")
        with get_session() as session:
            existing = (
                session.execute(
                    select(BusinessCapability).where(
                        BusinessCapability.business_key == business_key,
                        BusinessCapability.version == version,
                    )
                )
                .scalars()
                .first()
            )
            if existing:
                raise HTTPException(status_code=409, detail="BUSINESS_CAPABILITY_VERSION_DUPLICATED")
            recipe = self._build_recipe(
                base_recipe=payload.recipe,
                primary_ability_id=payload.primaryAbilityId,
            )
            self._validate_recipe(session=session, recipe=recipe)
            status = self._normalize_status(payload.status)
            self._validate_default_status(is_default=payload.isDefault, status=status)
            row = BusinessCapability(
                id=self._required_text(payload.id, "BUSINESS_CAPABILITY_ID_REQUIRED")
                if payload.id
                else f"biz_{business_key}_{version}_{uuid4().hex[:8]}",
                business_key=business_key,
                version=version,
                display_name=display_name,
                description=payload.description,
                status=status,
                is_default=bool(payload.isDefault),
                release_time=payload.releaseTime,
                recipe=recipe,
                input_schema=payload.inputSchema,
                output_schema=payload.outputSchema,
                extra_metadata=payload.metadata,
            )
            if row.is_default:
                session.execute(
                    update(BusinessCapability)
                    .where(BusinessCapability.business_key == row.business_key)
                    .values(is_default=False)
                )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._capability_to_dict(row, session=session)

    def update_capability(self, capability_id: str, payload: BusinessCapabilityUpdateRequest) -> dict[str, Any]:
        with get_session() as session:
            row = session.get(BusinessCapability, capability_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
            next_business_key = self._required_text(payload.businessKey, "BUSINESS_KEY_REQUIRED") if payload.businessKey is not None else row.business_key
            next_version = self._required_text(payload.version, "BUSINESS_VERSION_REQUIRED") if payload.version is not None else row.version
            duplicate = (
                session.execute(
                    select(BusinessCapability).where(
                        BusinessCapability.business_key == next_business_key,
                        BusinessCapability.version == next_version,
                        BusinessCapability.id != row.id,
                    )
                )
                .scalars()
                .first()
            )
            if duplicate:
                raise HTTPException(status_code=409, detail="BUSINESS_CAPABILITY_VERSION_DUPLICATED")
            if payload.recipe is not None or payload.primaryAbilityId is not None:
                row.recipe = self._build_recipe(
                    base_recipe=payload.recipe if payload.recipe is not None else row.recipe,
                    primary_ability_id=payload.primaryAbilityId,
                )
                self._validate_recipe(session=session, recipe=row.recipe)
            next_status = self._normalize_status(payload.status) if payload.status is not None else row.status
            next_is_default = bool(payload.isDefault) if payload.isDefault is not None else row.is_default
            self._validate_default_status(is_default=next_is_default, status=next_status)
            row.business_key = next_business_key
            row.version = next_version
            if payload.displayName is not None:
                row.display_name = self._required_text(payload.displayName, "BUSINESS_DISPLAY_NAME_REQUIRED")
            if payload.description is not None:
                row.description = payload.description
            row.status = next_status
            row.is_default = next_is_default
            if "releaseTime" in payload.model_fields_set or "release_time" in payload.model_fields_set:
                row.release_time = payload.releaseTime
            if "inputSchema" in payload.model_fields_set or "input_schema" in payload.model_fields_set:
                row.input_schema = payload.inputSchema
            if "outputSchema" in payload.model_fields_set or "output_schema" in payload.model_fields_set:
                row.output_schema = payload.outputSchema
            if "metadata" in payload.model_fields_set or "extra_metadata" in payload.model_fields_set:
                row.extra_metadata = payload.metadata
            if row.is_default:
                session.execute(
                    update(BusinessCapability)
                    .where(
                        BusinessCapability.business_key == row.business_key,
                        BusinessCapability.id != row.id,
                    )
                    .values(is_default=False)
                )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._capability_to_dict(row, session=session)

    def list_runs(
        self,
        *,
        limit: int = 50,
        business_key: str | None = None,
        status: str | None = None,
        version: str | None = None,
        source: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        trace_id: str | None = None,
    ) -> tuple[int, list[BusinessRun]]:
        with get_session() as session:
            stmt = select(BusinessRun)
            count_stmt = select(func.count(BusinessRun.id))
            filters = []
            if business_key:
                filters.append(BusinessRun.business_key == business_key)
            if status:
                filters.append(BusinessRun.status == status)
            if version:
                filters.append(BusinessRun.version == version)
            if source:
                filters.append(BusinessRun.source == source)
            if tenant_id:
                filters.append(BusinessRun.tenant_id == tenant_id)
            if client_id:
                filters.append(BusinessRun.client_id == client_id)
            if trace_id:
                filters.append(BusinessRun.trace_id == trace_id)
            if filters:
                stmt = stmt.where(*filters)
                count_stmt = count_stmt.where(*filters)
            total = int(session.scalar(count_stmt) or 0)
            rows = (
                session.execute(stmt.order_by(BusinessRun.created_at.desc()).limit(max(1, min(limit, 200))))
                .scalars()
                .all()
            )
            return total, [self._run_to_dict(row, session=session) for row in rows]

    def usage_summary(
        self,
        *,
        window_hours: int = 24,
        business_key: str | None = None,
        status: str | None = None,
        version: str | None = None,
        source: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_window_hours = max(1, min(int(window_hours or 24), 24 * 90))
        since = datetime.utcnow() - timedelta(hours=normalized_window_hours)
        with get_session() as session:
            stmt = select(BusinessRun).where(BusinessRun.created_at >= since)
            filters = []
            if business_key:
                filters.append(BusinessRun.business_key == business_key)
            if status:
                filters.append(BusinessRun.status == status)
            if version:
                filters.append(BusinessRun.version == version)
            if source:
                filters.append(BusinessRun.source == source)
            if tenant_id:
                filters.append(BusinessRun.tenant_id == tenant_id)
            if client_id:
                filters.append(BusinessRun.client_id == client_id)
            if trace_id:
                filters.append(BusinessRun.trace_id == trace_id)
            if filters:
                stmt = stmt.where(*filters)
            rows = session.execute(stmt.order_by(BusinessRun.created_at.desc())).scalars().all()

        summary = self._summarize_usage_bucket("all", "全部业务", rows)
        recent_failures = [
            {
                "id": row.id,
                "business_key": row.business_key,
                "version": row.version,
                "status": row.status,
                "source": row.source,
                "channel": row.channel,
                "tenant_id": row.tenant_id,
                "client_id": row.client_id,
                "trace_id": row.trace_id,
                "error_message": row.error_message,
                "created_at": row.created_at,
            }
            for row in rows
            if str(row.status or "").lower() == "failed" or row.error_message
        ][:10]
        return {
            "window_hours": normalized_window_hours,
            "filters": {
                "business_key": business_key,
                "status": status,
                "version": version,
                "source": source,
                "tenant_id": tenant_id,
                "client_id": client_id,
                "trace_id": trace_id,
            },
            **{key: value for key, value in summary.items() if key not in {"key", "label", "latest_at"}},
            "by_business": self._usage_buckets(rows, lambda row: row.business_key or "unknown"),
            "by_source": self._usage_buckets(rows, lambda row: row.source or "business-api"),
            "by_tenant": self._usage_buckets(rows, lambda row: row.tenant_id or "未标记业务方"),
            "by_client": self._usage_buckets(rows, lambda row: row.client_id or "未标记客户端"),
            "by_version": self._usage_buckets(
                rows,
                lambda row: f"{row.business_key or 'unknown'}:{row.version or '未标记版本'}",
                label_func=lambda key: key.replace(":", " · ", 1),
            ),
            "recent_failures": recent_failures,
        }

    def _usage_buckets(self, rows: list[BusinessRun], key_func, label_func=None) -> list[dict[str, Any]]:
        groups: dict[str, list[BusinessRun]] = {}
        for row in rows:
            key = str(key_func(row) or "unknown").strip() or "unknown"
            groups.setdefault(key, []).append(row)
        buckets = [
            self._summarize_usage_bucket(
                key,
                str(label_func(key) if label_func else key),
                group,
            )
            for key, group in groups.items()
        ]
        return sorted(
            buckets,
            key=lambda item: (int(item.get("total") or 0), item.get("latest_at") or datetime.min),
            reverse=True,
        )[:50]

    def _summarize_usage_bucket(self, key: str, label: str, rows: list[BusinessRun]) -> dict[str, Any]:
        statuses = {
            "succeeded": 0,
            "failed": 0,
            "running": 0,
            "queued": 0,
            "cancelled": 0,
        }
        durations: list[int] = []
        cost_by_currency: dict[str, float] = {}
        quota_units = 0
        latest_at: datetime | None = None
        for row in rows:
            status = str(row.status or "").strip().lower()
            if status in statuses:
                statuses[status] += 1
            if isinstance(row.duration_ms, int):
                durations.append(row.duration_ms)
            cost_amount = self._first_number(row.cost_amount)
            if cost_amount is not None:
                currency = str(row.currency or "UNKNOWN").strip() or "UNKNOWN"
                cost_by_currency[currency] = round(cost_by_currency.get(currency, 0.0) + cost_amount, 4)
            quota_units += int(row.quota_units or 0)
            if row.created_at and (latest_at is None or row.created_at > latest_at):
                latest_at = row.created_at
        total = len(rows)
        success_rate = round(statuses["succeeded"] / total, 4) if total else None
        avg_duration_ms = int(sum(durations) / len(durations)) if durations else None
        return {
            "key": key,
            "label": label,
            "total": total,
            **statuses,
            "success_rate": success_rate,
            "avg_duration_ms": avg_duration_ms,
            "cost_by_currency": cost_by_currency,
            "quota_units": quota_units,
            "latest_at": latest_at,
        }

    def create_run(
        self,
        *,
        business_key: str,
        payload: BusinessRunCreateRequest,
        user: User | None,
        source: str = "business-api",
    ) -> BusinessRun:
        image_url = self._first_string(payload.imageUrl, payload.url, (payload.inputs or {}).get("imageUrl"), (payload.inputs or {}).get("url"))
        if not image_url:
            raise HTTPException(status_code=400, detail="BUSINESS_IMAGE_URL_REQUIRED")

        with get_session() as session:
            ensure_default_abilities(session)
            ensure_default_business_capabilities(session)
            capability, route_info = self._select_capability(
                session,
                business_key=business_key,
                version=payload.version,
                payload=payload,
                user=user,
                image_url=image_url,
            )
            recipe = capability.recipe if isinstance(capability.recipe, dict) else {}
            ability_id = self._extract_primary_ability_id(recipe)
            ability = session.get(Ability, ability_id)
            if not ability or ability.status != "active":
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE")
            request_payload = self._omit_large_fields(payload.model_dump(exclude_none=True))
            if isinstance(request_payload, dict):
                request_payload["_route"] = route_info
            run_id = uuid4().hex
            trace_context = self._resolve_trace_context(
                run_id=run_id,
                business_key=business_key,
                payload=payload,
                source=source,
            )
            request_payload["_trace"] = trace_context

            run = BusinessRun(
                id=run_id,
                business_key=capability.business_key,
                business_version_id=capability.id,
                version=capability.version,
                status="queued",
                source=trace_context["source"],
                channel=trace_context.get("channel"),
                trace_id=trace_context["traceId"],
                request_id=trace_context["requestId"],
                tenant_id=trace_context.get("tenantId"),
                client_id=trace_context.get("clientId"),
                user_id=self._safe_user_id(user),
                user_name=getattr(user, "username", None) if user else None,
                ability_id=ability.id,
                request_payload=request_payload,
                callback_url=payload.callbackUrl,
                callback_headers=payload.callbackHeaders,
            )
            session.add(run)
            self._create_run_steps(session=session, run=run, recipe=recipe)
            session.commit()
            session.refresh(run)
            run_id = run.id

        ability_payload = self._build_ability_payload(
            capability_key=business_key,
            payload=payload,
            image_url=image_url,
            route_info=route_info,
            trace_context=trace_context,
        )
        try:
            task = get_ability_task_service().enqueue(ability_id=ability_id, payload=ability_payload, user=user)
        except HTTPException as exc:
            self._mark_run_submit_failed(run_id, exc.detail)
            raise
        except Exception as exc:
            self._mark_run_submit_failed(run_id, f"RUN_CREATE_FAILED:{exc}")
            raise HTTPException(status_code=500, detail="RUN_CREATE_FAILED") from exc
        with get_session() as session:
            db_run = session.get(BusinessRun, run_id)
            if not db_run:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            db_run.ability_task_id = str(task.get("id") or "")
            db_run.status = str(task.get("status") or "queued")
            db_run.started_at = datetime.utcnow()
            self._mark_primary_step_submitted(
                session=session,
                run=db_run,
                task=task,
                request_payload=ability_payload.model_dump(exclude_none=True),
            )
            session.add(db_run)
            session.commit()

        self._enqueue_sidecar_steps(
            run_id=run_id,
            recipe=recipe,
            business_key=business_key,
            payload=payload,
            user=user,
            image_url=image_url,
            route_info=route_info,
            trace_context=trace_context,
        )
        with get_session() as session:
            db_run = session.get(BusinessRun, run_id)
            if not db_run:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            self._sync_run_steps(session=session, run=db_run)
            return self._run_to_dict(db_run, session=session)

    def _create_run_steps(self, *, session, run: BusinessRun, recipe: dict[str, Any]) -> None:
        for order, step in enumerate(self._normalized_recipe_steps(recipe), start=1):
            ability_id = step.get("abilityId")
            ability = session.get(Ability, ability_id) if isinstance(ability_id, str) and ability_id else None
            enabled = step.get("enabled") is not False
            row = BusinessRunStep(
                id=uuid4().hex,
                run_id=run.id,
                step_order=order,
                step_id=self._first_string(step.get("id")),
                step_type=self._first_string(step.get("type")) or "ability_task",
                role=self._first_string(step.get("role")),
                display_name=self._first_string(step.get("displayName")),
                enabled=enabled,
                status="planned" if enabled else "skipped",
                ability_id=ability_id if isinstance(ability_id, str) else None,
                ability_name=ability.display_name if ability else None,
                ability_provider=ability.provider if ability else None,
            )
            session.add(row)

    def _mark_primary_step_submitted(
        self,
        *,
        session,
        run: BusinessRun,
        task: dict[str, Any],
        request_payload: dict[str, Any],
    ) -> None:
        step = self._find_primary_step(session=session, run=run, task_id=None)
        if not step:
            return
        step.status = str(task.get("status") or "queued")
        step.ability_task_id = str(task.get("id") or "") or None
        step.request_payload = self._omit_large_fields(request_payload)
        step.started_at = run.started_at or datetime.utcnow()
        session.add(step)

    def _enqueue_sidecar_steps(
        self,
        *,
        run_id: str,
        recipe: dict[str, Any],
        business_key: str,
        payload: BusinessRunCreateRequest,
        user: User | None,
        image_url: str,
        route_info: dict[str, Any],
        trace_context: dict[str, Any],
    ) -> None:
        snapshots: list[dict[str, Any]] = []
        normalized_steps = self._normalized_recipe_steps(recipe)
        with get_session() as session:
            run = session.get(BusinessRun, run_id)
            if not run:
                return
            for order, step_config in enumerate(normalized_steps, start=1):
                if not self._is_sidecar_step(step_config):
                    continue
                row = (
                    session.execute(
                        select(BusinessRunStep).where(
                            BusinessRunStep.run_id == run.id,
                            BusinessRunStep.step_order == order,
                            BusinessRunStep.status == "planned",
                            BusinessRunStep.enabled.is_(True),
                        )
                    )
                    .scalars()
                    .first()
                )
                if not row or not row.ability_id:
                    continue
                snapshots.append(
                    {
                        "row_id": row.id,
                        "ability_id": row.ability_id,
                        "step_id": row.step_id,
                        "step_type": row.step_type,
                        "role": row.role,
                        "config": step_config,
                    }
                )

        for step in snapshots:
            step_payload = self._build_step_ability_payload(
                step=step,
                business_key=business_key,
                payload=payload,
                image_url=image_url,
                route_info=route_info,
                run_id=run_id,
                trace_context=trace_context,
            )
            try:
                task = get_ability_task_service().enqueue(
                    ability_id=str(step["ability_id"]),
                    payload=step_payload,
                    user=user,
                )
            except Exception as exc:
                self._mark_step_submit_failed(row_id=str(step["row_id"]), detail=self._extract_error_message(exc))
                continue
            self._mark_step_submitted(
                row_id=str(step["row_id"]),
                task=task,
                request_payload=step_payload.model_dump(exclude_none=True),
            )

    @staticmethod
    def _is_sidecar_step(step: dict[str, Any]) -> bool:
        if step.get("enabled") is False:
            return False
        role = str(step.get("role") or "").strip().lower()
        if role == "primary":
            return False
        step_type = str(step.get("type") or "").strip().lower()
        return step_type in {"vl_analyze", "vl_analyze_image"}

    def _mark_step_submitted(self, *, row_id: str, task: dict[str, Any], request_payload: dict[str, Any]) -> None:
        with get_session() as session:
            step = session.get(BusinessRunStep, row_id)
            if not step:
                return
            step.status = str(task.get("status") or "queued")
            step.ability_task_id = str(task.get("id") or "") or None
            step.request_payload = self._omit_large_fields(request_payload)
            step.started_at = datetime.utcnow()
            session.add(step)
            session.commit()

    def _mark_step_submit_failed(self, *, row_id: str, detail: Any) -> None:
        with get_session() as session:
            step = session.get(BusinessRunStep, row_id)
            if not step:
                return
            step.status = "failed"
            step.error_message = str(detail)[:500]
            step.finished_at = datetime.utcnow()
            session.add(step)
            session.commit()

    def _find_primary_step(self, *, session, run: BusinessRun, task_id: str | None) -> BusinessRunStep | None:
        if task_id:
            row = (
                session.execute(
                    select(BusinessRunStep).where(
                        BusinessRunStep.run_id == run.id,
                        BusinessRunStep.ability_task_id == task_id,
                    )
                )
                .scalars()
                .first()
            )
            if row:
                return row
        if run.ability_id:
            row = (
                session.execute(
                    select(BusinessRunStep)
                    .where(
                        BusinessRunStep.run_id == run.id,
                        BusinessRunStep.ability_id == run.ability_id,
                        BusinessRunStep.enabled.is_(True),
                    )
                    .order_by(
                        BusinessRunStep.role.desc(),
                        BusinessRunStep.step_order.asc(),
                    )
                )
                .scalars()
                .first()
            )
            if row:
                return row
        return (
            session.execute(
                select(BusinessRunStep)
                .where(
                    BusinessRunStep.run_id == run.id,
                    BusinessRunStep.enabled.is_(True),
                    BusinessRunStep.step_type.in_(["ability_task", "comfyui_workflow", "vendor_api"]),
                )
                .order_by(BusinessRunStep.step_order.asc())
            )
            .scalars()
            .first()
        )

    def _mark_run_submit_failed(self, run_id: str, detail: Any) -> None:
        with get_session() as session:
            db_run = session.get(BusinessRun, run_id)
            if not db_run:
                return
            db_run.status = "failed"
            db_run.error_message = str(detail)[:500]
            db_run.finished_at = datetime.utcnow()
            step = self._find_primary_step(session=session, run=db_run, task_id=None)
            if step:
                step.status = "failed"
                step.error_message = str(detail)[:500]
                step.finished_at = db_run.finished_at
                session.add(step)
            session.add(db_run)
            session.commit()

    def get_run(self, *, run_id: str, user: User | None = None) -> BusinessRun:
        self.finalize_run(run_id)
        with get_session() as session:
            row = session.get(BusinessRun, run_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            if user and getattr(user, "role", "") != "admin":
                uid = self._safe_user_id(user)
                if row.user_id and uid and row.user_id != uid:
                    raise HTTPException(status_code=403, detail="BUSINESS_RUN_FORBIDDEN")
            return self._run_to_dict(row, session=session)

    def finalize_run(self, run_id: str) -> None:
        with get_session() as session:
            run = session.get(BusinessRun, run_id)
            if not run:
                return
            self._sync_run_steps(session=session, run=run)
            if run.ability_task_id and run.status not in {"succeeded", "failed", "cancelled"}:
                task = session.get(AbilityTask, run.ability_task_id)
                if task:
                    self._copy_task_to_run(session=session, run=run, task=task)
            session.commit()
            if run.status in {"succeeded", "failed", "cancelled"}:
                self._deliver_callback(run.id)

    def _start_finalize_thread(self) -> None:
        if self._thread_started:
            return
        self._thread_started = True

        def _loop() -> None:
            while True:
                try:
                    self._finalize_pending_runs()
                except Exception as exc:  # pragma: no cover - background best effort
                    logger.warning("business run finalize loop failed: %s", exc)
                time.sleep(FINALIZE_INTERVAL_SECONDS)

        threading.Thread(target=_loop, daemon=True).start()

    def _finalize_pending_runs(self) -> None:
        with get_session() as session:
            rows = (
                session.execute(
                    select(BusinessRun)
                    .where(BusinessRun.status.in_(["queued", "running"]))
                    .order_by(BusinessRun.updated_at.asc())
                    .limit(FINALIZE_BATCH_SIZE)
                )
                .scalars()
                .all()
            )
            for run in rows:
                if not run.ability_task_id:
                    continue
                task = session.get(AbilityTask, run.ability_task_id)
                if not task:
                    continue
                self._sync_run_steps(session=session, run=run)
                self._copy_task_to_run(session=session, run=run, task=task)
            session.commit()
            terminal_ids = [row.id for row in rows if row.status in {"succeeded", "failed", "cancelled"}]
        self._finalize_pending_steps()
        for run_id in terminal_ids:
            self._deliver_callback(run_id)

    def _finalize_pending_steps(self) -> None:
        with get_session() as session:
            rows = (
                session.execute(
                    select(BusinessRunStep)
                    .where(
                        BusinessRunStep.status.in_(["queued", "running"]),
                        BusinessRunStep.ability_task_id.is_not(None),
                    )
                    .order_by(BusinessRunStep.updated_at.asc())
                    .limit(FINALIZE_BATCH_SIZE)
                )
                .scalars()
                .all()
            )
            for step in rows:
                if not step.ability_task_id:
                    continue
                task = session.get(AbilityTask, step.ability_task_id)
                if task:
                    self._copy_task_to_step(session=session, step=step, task=task)
            session.commit()

    def _sync_run_steps(self, *, session, run: BusinessRun) -> None:
        rows = (
            session.execute(
                select(BusinessRunStep)
                .where(
                    BusinessRunStep.run_id == run.id,
                    BusinessRunStep.status.in_(["queued", "running"]),
                    BusinessRunStep.ability_task_id.is_not(None),
                )
                .order_by(BusinessRunStep.step_order.asc())
            )
            .scalars()
            .all()
        )
        for step in rows:
            if not step.ability_task_id:
                continue
            task = session.get(AbilityTask, step.ability_task_id)
            if task:
                self._copy_task_to_step(session=session, step=step, task=task)

    def _copy_task_to_step(self, *, session, step: BusinessRunStep, task: AbilityTask) -> None:
        status = str(task.status or "running")
        step.status = status
        step.ability_task_id = task.id
        step.ability_log_id = task.log_id
        step.result_payload = self._omit_large_fields(task.result_payload if isinstance(task.result_payload, dict) else {})
        step.error_message = task.error_message
        step.started_at = task.started_at or step.started_at
        step.duration_ms = task.duration_ms or self._calculate_duration_ms(step.started_at, task.finished_at or step.finished_at)
        self._copy_cost_fields_from_task(session=session, target=step, task=task)
        if status in {"succeeded", "failed", "cancelled"}:
            step.finished_at = task.finished_at or datetime.utcnow()

    def _copy_task_to_run(self, *, session, run: BusinessRun, task: AbilityTask) -> None:
        payload = task.result_payload if isinstance(task.result_payload, dict) else {}
        status = str(task.status or "running")
        run.status = status
        run.ability_log_id = task.log_id
        run.result_payload = self._omit_large_fields(payload)
        run.image_urls = self._extract_urls(payload, keys=("images", "assets", "resultUrls", "imageUrls"))
        run.video_urls = self._extract_urls(payload, keys=("videos", "videoUrls"))
        texts = payload.get("texts") if isinstance(payload, dict) else None
        run.texts = [str(x) for x in texts if isinstance(x, (str, int, float))] if isinstance(texts, list) else None
        run.error_message = task.error_message
        run.duration_ms = task.duration_ms or self._calculate_duration_ms(run.started_at or task.started_at, task.finished_at or run.finished_at)
        self._copy_cost_fields_from_task(session=session, target=run, task=task)
        if task.started_at and not run.started_at:
            run.started_at = task.started_at
        if status in {"succeeded", "failed", "cancelled"}:
            run.finished_at = task.finished_at or datetime.utcnow()
        step = self._find_primary_step(session=session, run=run, task_id=task.id)
        if step:
            self._copy_task_to_step(session=session, step=step, task=task)
            session.add(step)
        session.add(run)

    def _deliver_callback(self, run_id: str) -> None:
        with get_session() as session:
            run = session.get(BusinessRun, run_id)
            if not run or not run.callback_url:
                return
            if run.callback_status in {"success", "failed"}:
                return
            payload = self._callback_payload(run)
            run.callback_status = "running"
            run.callback_payload = payload
            session.add(run)
            session.commit()

        try:
            response = httpx.post(
                str(run.callback_url),
                json=payload,
                headers=run.callback_headers or {},
                timeout=15,
            )
            body: dict[str, Any] = {}
            try:
                parsed = response.json()
                if isinstance(parsed, dict):
                    body = parsed
                else:
                    body = {"body": str(parsed)[:1000]}
            except Exception:
                body = {"body": response.text[:1000]}
            with get_session() as session:
                db_run = session.get(BusinessRun, run_id)
                if db_run:
                    db_run.callback_http_status = response.status_code
                    db_run.callback_response = body
                    db_run.callback_status = "success" if response.status_code < 400 else "failed"
                    db_run.callback_error = None if response.status_code < 400 else f"HTTP_{response.status_code}"
                    session.add(db_run)
                    session.commit()
        except Exception as exc:
            with get_session() as session:
                db_run = session.get(BusinessRun, run_id)
                if db_run:
                    db_run.callback_status = "failed"
                    db_run.callback_error = str(exc)[:500]
                    session.add(db_run)
                    session.commit()

    def _callback_payload(self, run: BusinessRun) -> dict[str, Any]:
        return {
            "runId": run.id,
            "businessKey": run.business_key,
            "version": run.version,
            "status": run.status,
            "traceId": run.trace_id,
            "requestId": run.request_id,
            "tenantId": run.tenant_id,
            "clientId": run.client_id,
            "channel": run.channel,
            "taskId": run.ability_task_id,
            "imageUrls": run.image_urls or [],
            "videoUrls": run.video_urls or [],
            "texts": run.texts or [],
            "error": run.error_message,
            "durationMs": run.duration_ms,
            "costAmount": float(run.cost_amount) if run.cost_amount is not None else None,
            "currency": run.currency,
            "debugUrl": run.debug_url,
        }

    def _resolve_trace_context(
        self,
        *,
        run_id: str,
        business_key: str,
        payload: BusinessRunCreateRequest,
        source: str | None,
    ) -> dict[str, Any]:
        metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
        inputs = payload.inputs if isinstance(payload.inputs, dict) else {}
        source_value = self._short_text(
            self._first_string(
                payload.source,
                metadata.get("source"),
                metadata.get("entry"),
                source,
                "business-api",
            ),
            64,
        )
        channel = self._short_text(
            self._first_string(
                payload.channel,
                metadata.get("channel"),
                metadata.get("scene"),
                inputs.get("channel"),
            ),
            64,
        )
        trace_id = self._short_text(
            self._first_string(
                payload.traceId,
                metadata.get("traceId"),
                metadata.get("trace_id"),
                inputs.get("traceId"),
                inputs.get("trace_id"),
                run_id,
            ),
            64,
        )
        request_id = self._short_text(
            self._first_string(
                payload.requestId,
                metadata.get("requestId"),
                metadata.get("request_id"),
                inputs.get("requestId"),
                inputs.get("request_id"),
                run_id,
            ),
            64,
        )
        tenant_id = self._short_text(
            self._first_string(
                payload.tenantId,
                metadata.get("tenantId"),
                metadata.get("tenant_id"),
                metadata.get("grayKey"),
                metadata.get("gray_key"),
                inputs.get("tenantId"),
                inputs.get("tenant_id"),
            ),
            64,
        )
        client_id = self._short_text(
            self._first_string(
                payload.clientId,
                metadata.get("clientId"),
                metadata.get("client_id"),
                inputs.get("clientId"),
                inputs.get("client_id"),
                payload.profile_id,
            ),
            64,
        )
        return {
            "businessKey": business_key,
            "source": source_value or "business-api",
            "channel": channel,
            "traceId": trace_id or run_id,
            "requestId": request_id or run_id,
            "tenantId": tenant_id,
            "clientId": client_id,
        }

    @staticmethod
    def _short_text(value: Any, max_length: int) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        return text[:max_length]

    @staticmethod
    def _calculate_duration_ms(started_at: datetime | None, finished_at: datetime | None) -> int | None:
        if not started_at or not finished_at:
            return None
        try:
            return max(0, int((finished_at - started_at).total_seconds() * 1000))
        except Exception:
            return None

    def _copy_cost_fields_from_task(self, *, session, target: BusinessRun | BusinessRunStep, task: AbilityTask) -> None:
        payload = task.result_payload if isinstance(task.result_payload, dict) else {}
        log = session.get(AbilityInvocationLog, int(task.log_id)) if task.log_id else None
        cost_payload = payload.get("cost") if isinstance(payload.get("cost"), dict) else {}
        usage_payload = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        billing_unit = self._first_string(
            getattr(log, "billing_unit", None),
            cost_payload.get("billingUnit"),
            cost_payload.get("billing_unit"),
            usage_payload.get("unit"),
        )
        unit_price = self._first_number(
            getattr(log, "unit_price", None),
            cost_payload.get("unitPrice"),
            cost_payload.get("unit_price"),
        )
        cost_amount = self._first_number(
            getattr(log, "cost_amount", None),
            cost_payload.get("costAmount"),
            cost_payload.get("cost_amount"),
            cost_payload.get("total"),
            cost_payload.get("amount"),
        )
        currency = self._first_string(
            getattr(log, "currency", None),
            cost_payload.get("currency"),
            usage_payload.get("currency"),
        )
        quota_units = self._first_int(
            cost_payload.get("quotaUnits"),
            cost_payload.get("quota_units"),
            usage_payload.get("total_tokens"),
            usage_payload.get("totalTokens"),
            usage_payload.get("output_count"),
        )
        target.billing_unit = billing_unit
        target.unit_price = unit_price
        target.cost_amount = cost_amount
        target.currency = currency
        target.quota_units = quota_units
        target.cost_breakdown = self._omit_large_fields(
            {
                "abilityTaskId": task.id,
                "abilityLogId": task.log_id,
                "provider": task.ability_provider,
                "capabilityKey": task.capability_key,
                "cost": cost_payload or None,
                "usage": usage_payload or None,
            }
        )

    @staticmethod
    def _first_number(*values: Any) -> float | None:
        for value in values:
            if value in (None, ""):
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _first_int(*values: Any) -> int | None:
        for value in values:
            if value in (None, ""):
                continue
            try:
                return int(float(value))
            except (TypeError, ValueError):
                continue
        return None

    def _select_capability(
        self,
        session,
        *,
        business_key: str,
        version: str | None,
        payload: BusinessRunCreateRequest | None = None,
        user: User | None = None,
        image_url: str | None = None,
    ) -> tuple[BusinessCapability, dict[str, Any]]:
        stmt = select(BusinessCapability).where(
            BusinessCapability.business_key == business_key,
            BusinessCapability.status == "active",
        )
        if version:
            row = session.execute(stmt.where(BusinessCapability.version == version)).scalars().first()
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
            return row, self._route_info(row, selected_by="explicit")

        rows = (
            session.execute(
                stmt.order_by(
                    BusinessCapability.is_default.desc(),
                    BusinessCapability.release_time.desc(),
                    BusinessCapability.created_at.desc(),
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
        default = next((row for row in rows if row.is_default), rows[0])
        route_key = self._resolve_route_key(payload=payload, user=user, image_url=image_url)
        for row in rows:
            if row.id == default.id:
                continue
            decision = self._rollout_decision(row=row, business_key=business_key, route_key=route_key)
            if decision.get("matched"):
                return row, self._route_info(row, route_key=route_key, **decision)
        return default, self._route_info(default, selected_by="default", route_key=route_key)

    def _rollout_decision(self, *, row: BusinessCapability, business_key: str, route_key: str | None) -> dict[str, Any]:
        rollout = self._extract_rollout_config(row)
        if not rollout:
            return {"matched": False}
        enabled = bool(rollout.get("enabled"))
        if not enabled:
            return {"matched": False}
        if not route_key:
            return {"matched": False, "selected_by": "rollout_no_key"}
        blocklist = set(self._string_list(rollout.get("blocklist") or rollout.get("excludeKeys") or rollout.get("exclude_keys")))
        if route_key in blocklist:
            return {"matched": False, "selected_by": "rollout_blocklist"}
        allowlist = set(
            self._string_list(
                rollout.get("allowlist")
                or rollout.get("includeKeys")
                or rollout.get("include_keys")
                or rollout.get("whitelist")
            )
        )
        if route_key in allowlist:
            return {
                "matched": True,
                "selected_by": "rollout_allowlist",
                "rollout_percent": self._safe_percent(rollout.get("percent")),
            }
        percent = self._safe_percent(rollout.get("percent"))
        if percent <= 0:
            return {"matched": False, "selected_by": "rollout_zero_percent", "rollout_percent": percent}
        bucket = self._rollout_bucket(
            business_key=business_key,
            capability_id=row.id,
            route_key=route_key,
            salt=str(rollout.get("salt") or ""),
        )
        if bucket < percent:
            return {
                "matched": True,
                "selected_by": "rollout_percent",
                "rollout_percent": percent,
                "rollout_bucket": bucket,
            }
        return {
            "matched": False,
            "selected_by": "rollout_percent_miss",
            "rollout_percent": percent,
            "rollout_bucket": bucket,
        }

    @staticmethod
    def _extract_rollout_config(row: BusinessCapability) -> dict[str, Any]:
        for source in (row.extra_metadata, row.recipe):
            if not isinstance(source, dict):
                continue
            rollout = source.get("rollout")
            if isinstance(rollout, dict):
                return rollout
        return {}

    @staticmethod
    def _resolve_route_key(
        *,
        payload: BusinessRunCreateRequest | None,
        user: User | None,
        image_url: str | None,
    ) -> str | None:
        metadata = payload.metadata if payload and isinstance(payload.metadata, dict) else {}
        inputs = payload.inputs if payload and isinstance(payload.inputs, dict) else {}
        for source in (metadata, inputs):
            for key in ("grayKey", "gray_key", "routeKey", "route_key", "tenantId", "tenant_id", "userId", "user_id", "traceId", "trace_id"):
                value = source.get(key)
                if isinstance(value, (str, int, float)) and str(value).strip():
                    return str(value).strip()
        user_id = BusinessRunService._safe_user_id(user)
        if user_id:
            return user_id
        if image_url and image_url.strip():
            return image_url.strip()
        return None

    @staticmethod
    def _rollout_bucket(*, business_key: str, capability_id: str, route_key: str, salt: str) -> float:
        raw = f"{business_key}:{capability_id}:{salt}:{route_key}".encode("utf-8")
        value = int(hashlib.sha256(raw).hexdigest()[:8], 16)
        return round((value / 0xFFFFFFFF) * 100, 4)

    @staticmethod
    def _route_key_hash(route_key: str | None) -> str | None:
        if not route_key:
            return None
        return hashlib.sha256(route_key.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _safe_percent(value: Any) -> float:
        try:
            percent = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(100.0, percent))

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if isinstance(item, (str, int, float)) and str(item).strip()]

    def _route_info(
        self,
        row: BusinessCapability,
        *,
        selected_by: str,
        route_key: str | None = None,
        rollout_percent: float | None = None,
        rollout_bucket: float | None = None,
        matched: bool | None = None,
    ) -> dict[str, Any]:
        _ = matched
        info: dict[str, Any] = {
            "businessVersionId": row.id,
            "version": row.version,
            "selectedBy": selected_by,
            "routeKeyHash": self._route_key_hash(route_key),
        }
        if rollout_percent is not None:
            info["rolloutPercent"] = rollout_percent
        if rollout_bucket is not None:
            info["rolloutBucket"] = rollout_bucket
        return info

    @staticmethod
    def _build_recipe(*, base_recipe: dict[str, Any] | None, primary_ability_id: str | None) -> dict[str, Any]:
        recipe = dict(base_recipe or {})
        normalized_primary = str(primary_ability_id or "").strip()
        raw_steps = recipe.get("steps")
        steps = [dict(step) if isinstance(step, dict) else step for step in raw_steps] if isinstance(raw_steps, list) else raw_steps
        if normalized_primary:
            recipe["primaryAbilityId"] = normalized_primary
            if not isinstance(steps, list):
                recipe["steps"] = [
                    {
                        "id": "primary",
                        "type": "ability_task",
                        "role": "primary",
                        "abilityId": normalized_primary,
                    }
                ]
            else:
                target_index: int | None = None
                for index, step in enumerate(steps):
                    if not isinstance(step, dict):
                        continue
                    step_id = str(step.get("id") or "").strip()
                    role = str(step.get("role") or "").strip()
                    if step_id == "primary" or role == "primary":
                        target_index = index
                        break
                if target_index is None:
                    for index, step in enumerate(steps):
                        if not isinstance(step, dict):
                            continue
                        step_type = str(step.get("type") or "ability_task").strip()
                        if step_type in {"ability_task", "comfyui_workflow", "vendor_api"}:
                            target_index = index
                            break
                primary_step = {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "abilityId": normalized_primary,
                }
                if target_index is None:
                    steps.append(primary_step)
                else:
                    existing = steps[target_index]
                    if isinstance(existing, dict):
                        steps[target_index] = {
                            **existing,
                            "id": existing.get("id") or "primary",
                            "type": existing.get("type") or "ability_task",
                            "role": existing.get("role") or "primary",
                            "abilityId": normalized_primary,
                        }
                recipe["steps"] = steps
        elif isinstance(steps, list):
            recipe["steps"] = steps
        if "mode" not in recipe:
            recipe["mode"] = "single_ability_task"
        return recipe

    def _validate_recipe(self, *, session, recipe: dict[str, Any]) -> None:
        primary_ability_id = self._extract_primary_ability_id(recipe)
        ability_ids = [primary_ability_id]
        raw_steps = recipe.get("steps")
        if raw_steps is not None and not isinstance(raw_steps, list):
            raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
        for raw_step in raw_steps or []:
            if not isinstance(raw_step, dict):
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
            if raw_step.get("enabled") is False:
                continue
            step_type = str(raw_step.get("type") or "ability_task").strip()
            if not step_type:
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
            ability_id = self._extract_step_ability_id(raw_step)
            if step_type in RECIPE_EXECUTABLE_STEP_TYPES or ability_id:
                if not ability_id:
                    raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
                ability_ids.append(ability_id)
            elif step_type not in RECIPE_PASSIVE_STEP_TYPES:
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
        vl_assist = recipe.get("vlAssist") or recipe.get("vl_assist")
        if vl_assist is not None and not isinstance(vl_assist, dict):
            raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
        if isinstance(vl_assist, dict) and vl_assist.get("enabled"):
            vl_ability_id = self._first_string(vl_assist.get("abilityId"), vl_assist.get("ability_id"), "vl_analyze_image")
            if not vl_ability_id:
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
            ability_ids.append(vl_ability_id)
        for ability_id in dict.fromkeys(ability_ids):
            ability = session.get(Ability, ability_id)
            if not ability:
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE")
        vendor_model_id = self._extract_recipe_vendor_model_id(recipe)
        if vendor_model_id is not None and not session.get(VendorModelCatalog, vendor_model_id):
            raise HTTPException(status_code=400, detail="VENDOR_MODEL_NOT_FOUND")

    @staticmethod
    def _extract_recipe_vendor_model_id(recipe: dict[str, Any]) -> int | None:
        raw = recipe.get("vendorModelId") or recipe.get("vendor_model_id")
        if raw in (None, ""):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="VENDOR_MODEL_NOT_FOUND")

    @staticmethod
    def _normalize_status(value: str | None) -> str:
        status = str(value or "inactive").strip().lower()
        allowed = {"active", "inactive", "draft", "disabled", "deprecated"}
        if status not in allowed:
            raise HTTPException(status_code=400, detail="BUSINESS_STATUS_INVALID")
        return status

    @staticmethod
    def _validate_default_status(*, is_default: bool, status: str) -> None:
        if is_default and status != "active":
            raise HTTPException(status_code=400, detail="BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE")

    @staticmethod
    def _required_text(value: str | None, error_code: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail=error_code)
        return text

    @staticmethod
    def _extract_primary_ability_id(recipe: dict[str, Any]) -> str:
        candidate = recipe.get("primaryAbilityId")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        steps = recipe.get("steps")
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict) or step.get("enabled") is False:
                    continue
                role = str(step.get("role") or "").strip()
                step_id = str(step.get("id") or "").strip()
                if role == "primary" or step_id == "primary":
                    ability_id = BusinessRunService._extract_step_ability_id(step)
                    if ability_id:
                        return ability_id
            for step in steps:
                if not isinstance(step, dict) or step.get("enabled") is False:
                    continue
                step_type = str(step.get("type") or "ability_task").strip()
                if step_type in {"ability_task", "comfyui_workflow", "vendor_api"}:
                    ability_id = BusinessRunService._extract_step_ability_id(step)
                    if ability_id:
                        return ability_id
        raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")

    @staticmethod
    def _extract_step_ability_id(step: dict[str, Any]) -> str | None:
        for key in ("abilityId", "ability_id"):
            value = step.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _build_ability_payload(
        self,
        *,
        capability_key: str,
        payload: BusinessRunCreateRequest,
        image_url: str,
        route_info: dict[str, Any] | None = None,
        trace_context: dict[str, Any] | None = None,
    ) -> AbilityInvokeRequest:
        inputs: dict[str, Any] = dict(payload.inputs or {})
        if capability_key == "fission":
            pass_keys = {
                "prompt",
                "bili",
                "width",
                "height",
                "batch_size",
                "steps",
                "cfg",
                "profile_id",
                "ipadapter_weight",
                "colormatch_method",
                "colormatch_strength",
                "image_desc",
            }
        elif capability_key == "outpaint":
            pass_keys = {
                "prompt",
                "expand_left",
                "expand_right",
                "expand_top",
                "expand_bottom",
                "width",
                "height",
                "seed",
                "timeout",
            }
        else:
            pass_keys = set(inputs)
        flat_payload = payload.model_dump(exclude_none=True, by_alias=True)
        for key in pass_keys:
            if key not in inputs and key in flat_payload:
                inputs[key] = flat_payload[key]
        if payload.prompt and "prompt" not in inputs:
            inputs["prompt"] = payload.prompt
        ability_inputs = {key: value for key, value in inputs.items() if key in pass_keys and value not in (None, "", [])}
        return AbilityInvokeRequest(
            inputs=ability_inputs,
            imageUrl=image_url,
            metadata={
                **(payload.metadata or {}),
                "businessKey": capability_key,
                "businessVersion": (route_info or {}).get("version"),
                "businessRoute": route_info or {},
                "businessTrace": trace_context or {},
                "traceId": (trace_context or {}).get("traceId"),
                "requestId": (trace_context or {}).get("requestId"),
                "tenantId": (trace_context or {}).get("tenantId"),
                "clientId": (trace_context or {}).get("clientId"),
                "channel": (trace_context or {}).get("channel"),
                "source": (trace_context or {}).get("source"),
            },
        )

    def _build_step_ability_payload(
        self,
        *,
        step: dict[str, Any],
        business_key: str,
        payload: BusinessRunCreateRequest,
        image_url: str,
        route_info: dict[str, Any],
        run_id: str,
        trace_context: dict[str, Any],
    ) -> AbilityInvokeRequest:
        step_config = step.get("config") if isinstance(step.get("config"), dict) else {}
        step_inputs = self._extract_step_inputs(step_config)
        request_inputs = payload.inputs if isinstance(payload.inputs, dict) else {}
        step_type = str(step.get("step_type") or step_config.get("type") or "").strip().lower()
        inputs: dict[str, Any] = dict(step_inputs)
        if step_type in {"vl_analyze", "vl_analyze_image"}:
            prompt = self._first_string(
                request_inputs.get("vl_prompt"),
                request_inputs.get("analysis_prompt"),
                request_inputs.get("analysisPrompt"),
                step_inputs.get("prompt"),
            )
            if not prompt and step_config.get("useBusinessPrompt") is True:
                prompt = payload.prompt
            provider = self._first_string(
                request_inputs.get("vl_provider"),
                request_inputs.get("vlProvider"),
                step_inputs.get("provider"),
            )
            coze_workflow_id = self._first_string(
                request_inputs.get("coze_vl_workflow_id"),
                request_inputs.get("cozeWorkflowId"),
                request_inputs.get("coze_workflow_id"),
                step_inputs.get("coze_workflow_id"),
                step_inputs.get("cozeWorkflowId"),
            )
            inputs = {"image_url": image_url, **inputs}
            if prompt:
                inputs["prompt"] = prompt
            if provider:
                inputs["provider"] = provider
            if coze_workflow_id:
                inputs["coze_workflow_id"] = coze_workflow_id
        else:
            inputs.setdefault("image_url", image_url)
        metadata = {
            **(payload.metadata or {}),
            "businessKey": business_key,
            "businessVersion": route_info.get("version"),
            "businessRoute": route_info,
            "businessRunId": run_id,
            "businessStepId": step.get("step_id"),
            "businessStepRole": step.get("role"),
            "businessStepType": step_type,
            "businessTrace": trace_context,
            "traceId": trace_context.get("traceId"),
            "requestId": trace_context.get("requestId"),
            "tenantId": trace_context.get("tenantId"),
            "clientId": trace_context.get("clientId"),
            "channel": trace_context.get("channel"),
            "source": trace_context.get("source"),
        }
        return AbilityInvokeRequest(
            inputs={key: value for key, value in inputs.items() if value not in (None, "", [])},
            imageUrl=image_url,
            metadata=metadata,
        )

    @staticmethod
    def _extract_step_inputs(step_config: dict[str, Any]) -> dict[str, Any]:
        inputs: dict[str, Any] = {}
        for key in ("defaultInputs", "default_inputs", "inputs", "params"):
            value = step_config.get(key)
            if isinstance(value, dict):
                inputs.update(value)
        return inputs

    @staticmethod
    def _extract_error_message(exc: Exception) -> str:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict):
            for key in ("message", "detail", "error", "code"):
                value = detail.get(key)
                if isinstance(value, (str, int, float)) and str(value).strip():
                    return str(value).strip()
            return str(detail)[:500]
        if isinstance(detail, (str, int, float)) and str(detail).strip():
            return str(detail).strip()
        return str(exc)[:500]

    @staticmethod
    def _extract_urls(payload: dict[str, Any] | None, *, keys: tuple[str, ...]) -> list[str]:
        if not isinstance(payload, dict):
            return []
        urls: list[str] = []

        def add(value: Any) -> None:
            if isinstance(value, str) and value.strip().startswith(("http://", "https://")):
                urls.append(value.strip())
            elif isinstance(value, dict):
                for key in ("ossUrl", "url", "sourceUrl"):
                    candidate = value.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        urls.append(candidate.strip())
                        break
            elif isinstance(value, list):
                for item in value:
                    add(item)

        for key in keys:
            add(payload.get(key))
        seen: set[str] = set()
        out: list[str] = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            out.append(url)
        return out

    @staticmethod
    def _normalized_recipe_steps(recipe: dict[str, Any]) -> list[dict[str, Any]]:
        raw_steps = recipe.get("steps")
        normalized: list[dict[str, Any]] = []
        if isinstance(raw_steps, list):
            for index, raw_step in enumerate(raw_steps):
                if not isinstance(raw_step, dict):
                    continue
                ability_id = BusinessRunService._extract_step_ability_id(raw_step)
                step_type = str(raw_step.get("type") or "ability_task").strip() or "ability_task"
                step: dict[str, Any] = {
                    "id": BusinessRunService._first_string(raw_step.get("id")) or f"step_{index + 1}",
                    "type": step_type,
                    "enabled": raw_step.get("enabled") is not False,
                }
                role = BusinessRunService._first_string(raw_step.get("role"))
                name = BusinessRunService._first_string(raw_step.get("displayName"), raw_step.get("name"), raw_step.get("title"))
                if role:
                    step["role"] = role
                if name:
                    step["displayName"] = name
                if ability_id:
                    step["abilityId"] = ability_id
                normalized.append(step)

        vl_assist = recipe.get("vlAssist") or recipe.get("vl_assist")
        if isinstance(vl_assist, dict) and vl_assist.get("enabled"):
            vl_ability_id = BusinessRunService._first_string(
                vl_assist.get("abilityId"),
                vl_assist.get("ability_id"),
                "vl_analyze_image",
            )
            has_vl_step = any(
                step.get("type") in {"vl_analyze", "vl_analyze_image"} or step.get("abilityId") == vl_ability_id
                for step in normalized
            )
            if vl_ability_id and not has_vl_step:
                normalized.insert(
                    0,
                    {
                        "id": "vl_analyze",
                        "type": "vl_analyze",
                        "role": "preprocess",
                        "displayName": "VL 图像理解",
                        "abilityId": vl_ability_id,
                        "enabled": True,
                    },
                )

        try:
            primary_ability_id = BusinessRunService._extract_primary_ability_id(recipe)
        except HTTPException:
            primary_ability_id = None
        if primary_ability_id:
            has_primary = False
            for step in normalized:
                if step.get("abilityId") == primary_ability_id and step.get("enabled") is not False:
                    has_primary = True
                    step.setdefault("role", "primary")
            if not has_primary:
                normalized.append(
                    {
                        "id": "primary",
                        "type": "ability_task",
                        "role": "primary",
                        "displayName": "主执行能力",
                        "abilityId": primary_ability_id,
                        "enabled": True,
                    }
                )
        return normalized

    def _recipe_steps_to_dict(self, recipe: dict[str, Any], *, session=None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for order, step in enumerate(self._normalized_recipe_steps(recipe), start=1):
            ability_id = step.get("abilityId")
            ability = session.get(Ability, ability_id) if session is not None and isinstance(ability_id, str) else None
            item = {
                "order": order,
                "id": step.get("id"),
                "type": step.get("type"),
                "role": step.get("role"),
                "displayName": step.get("displayName"),
                "enabled": step.get("enabled") is not False,
                "abilityId": ability_id,
                "abilityName": ability.display_name if ability else None,
                "abilityProvider": ability.provider if ability else None,
            }
            rows.append({key: value for key, value in item.items() if value is not None})
        return rows

    @staticmethod
    def _first_string(*values: Any) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _safe_user_id(user: User | None) -> str | None:
        if not user:
            return None
        user_id = str(getattr(user, "id", "") or "").strip()
        return None if user_id == "service" else user_id or None

    def _capability_to_dict(self, row: BusinessCapability, *, session=None) -> dict[str, Any]:
        recipe = row.recipe if isinstance(row.recipe, dict) else {}
        primary_ability_id: str | None = None
        primary_ability_name: str | None = None
        primary_ability_provider: str | None = None
        vendor_model_id: int | None = None
        vendor_model_name: str | None = None
        vendor_model_provider: str | None = None
        latest_run = self._latest_run_summary(row, session=session)
        run_metrics = self._run_metrics_summary(row, session=session)
        try:
            primary_ability_id = self._extract_primary_ability_id(recipe)
        except HTTPException:
            primary_ability_id = None
        ability = session.get(Ability, primary_ability_id) if session is not None and primary_ability_id else None
        if ability:
            primary_ability_name = ability.display_name
            primary_ability_provider = ability.provider
            try:
                vendor_model_id = self._extract_recipe_vendor_model_id(recipe) or ability.vendor_model_id
            except HTTPException:
                vendor_model_id = ability.vendor_model_id
        else:
            try:
                vendor_model_id = self._extract_recipe_vendor_model_id(recipe)
            except HTTPException:
                vendor_model_id = None
        vendor_model = session.get(VendorModelCatalog, vendor_model_id) if session is not None and vendor_model_id else None
        if vendor_model:
            vendor_model_name = vendor_model.display_name
            vendor_model_provider = vendor_model.provider
        return {
            "id": row.id,
            "business_key": row.business_key,
            "version": row.version,
            "display_name": row.display_name,
            "description": row.description,
            "status": row.status,
            "is_default": row.is_default,
            "release_time": row.release_time,
            "recipe": self._omit_large_fields(row.recipe),
            "input_schema": row.input_schema,
            "output_schema": row.output_schema,
            "extra_metadata": row.extra_metadata,
            "primary_ability_id": primary_ability_id,
            "primary_ability_name": primary_ability_name,
            "primary_ability_provider": primary_ability_provider,
            "vendor_model_id": vendor_model_id,
            "vendor_model_name": vendor_model_name,
            "vendor_model_provider": vendor_model_provider,
            "recipe_steps": self._recipe_steps_to_dict(recipe, session=session),
            "latest_run": latest_run,
            "run_metrics": run_metrics,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _latest_run_summary(row: BusinessCapability, *, session=None) -> dict[str, Any] | None:
        if session is None:
            return None
        latest = (
            session.execute(
                select(BusinessRun)
                .where(BusinessRun.business_version_id == row.id)
                .order_by(BusinessRun.created_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if not latest:
            return None
        return {
            "id": latest.id,
            "status": latest.status,
            "created_at": latest.created_at,
            "finished_at": latest.finished_at,
            "image_count": len(latest.image_urls or []),
            "video_count": len(latest.video_urls or []),
            "error": latest.error_message,
        }

    @staticmethod
    def _run_metrics_summary(row: BusinessCapability, *, session=None) -> dict[str, Any]:
        since = datetime.utcnow() - timedelta(hours=24)
        metrics = {
            "window_hours": 24,
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "running": 0,
            "queued": 0,
            "cancelled": 0,
            "success_rate": None,
        }
        if session is None:
            return metrics
        rows = (
            session.execute(
                select(BusinessRun.status, func.count(BusinessRun.id))
                .where(
                    BusinessRun.business_version_id == row.id,
                    BusinessRun.created_at >= since,
                )
                .group_by(BusinessRun.status)
            )
            .all()
        )
        for status, count in rows:
            key = str(status or "").strip().lower()
            value = int(count or 0)
            if key in metrics:
                metrics[key] = value
            metrics["total"] = int(metrics["total"] or 0) + value
        total = int(metrics["total"] or 0)
        if total > 0:
            metrics["success_rate"] = round(int(metrics["succeeded"] or 0) / total, 4)
        return metrics

    def _run_to_dict(self, row: BusinessRun, *, session=None) -> dict[str, Any]:
        ability_name: str | None = None
        ability_provider: str | None = None
        vendor_model_id: int | None = None
        vendor_model_name: str | None = None
        vendor_model_provider: str | None = None
        ability = session.get(Ability, row.ability_id) if session is not None and row.ability_id else None
        if ability:
            ability_name = ability.display_name
            ability_provider = ability.provider
            vendor_model_id = ability.vendor_model_id
        vendor_model = session.get(VendorModelCatalog, vendor_model_id) if session is not None and vendor_model_id else None
        if vendor_model:
            vendor_model_name = vendor_model.display_name
            vendor_model_provider = vendor_model.provider
        return {
            "id": row.id,
            "business_key": row.business_key,
            "business_version_id": row.business_version_id,
            "version": row.version,
            "status": row.status,
            "source": row.source,
            "channel": row.channel,
            "trace_id": row.trace_id,
            "request_id": row.request_id,
            "tenant_id": row.tenant_id,
            "client_id": row.client_id,
            "user_id": row.user_id,
            "user_name": row.user_name,
            "ability_id": row.ability_id,
            "ability_name": ability_name,
            "ability_provider": ability_provider,
            "vendor_model_id": vendor_model_id,
            "vendor_model_name": vendor_model_name,
            "vendor_model_provider": vendor_model_provider,
            "ability_task_id": (
                encode_task_id(task_id=row.ability_task_id, provider=row.business_key, executor_id=None)
                if row.ability_task_id
                else None
            ),
            "ability_log_id": row.ability_log_id,
            "request_payload": self._omit_large_fields(row.request_payload),
            "result_payload": self._omit_large_fields(row.result_payload),
            "image_urls": row.image_urls,
            "video_urls": row.video_urls,
            "texts": row.texts,
            "error_message": row.error_message,
            "duration_ms": row.duration_ms,
            "billing_unit": row.billing_unit,
            "unit_price": float(row.unit_price) if row.unit_price is not None else None,
            "cost_amount": float(row.cost_amount) if row.cost_amount is not None else None,
            "currency": row.currency,
            "quota_units": row.quota_units,
            "cost_breakdown": row.cost_breakdown,
            "callback_status": row.callback_status,
            "debug_url": row.debug_url,
            "route_info": (row.request_payload or {}).get("_route") if isinstance(row.request_payload, dict) else None,
            "steps": self._run_steps_to_dict(row, session=session),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }

    def _run_steps_to_dict(self, row: BusinessRun, *, session=None) -> list[dict[str, Any]]:
        if session is None:
            return []
        steps = (
            session.execute(
                select(BusinessRunStep)
                .where(BusinessRunStep.run_id == row.id)
                .order_by(BusinessRunStep.step_order.asc(), BusinessRunStep.created_at.asc())
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": step.id,
                "run_id": step.run_id,
                "step_order": step.step_order,
                "step_id": step.step_id,
                "step_type": step.step_type,
                "role": step.role,
                "display_name": step.display_name,
                "enabled": step.enabled,
                "status": step.status,
                "ability_id": step.ability_id,
                "ability_name": step.ability_name,
                "ability_provider": step.ability_provider,
                "ability_task_id": (
                    encode_task_id(task_id=step.ability_task_id, provider=row.business_key, executor_id=None)
                    if step.ability_task_id
                    else None
                ),
                "ability_log_id": step.ability_log_id,
                "result_summary": self._build_step_result_summary(step),
                "error_message": step.error_message,
                "duration_ms": step.duration_ms,
                "billing_unit": step.billing_unit,
                "unit_price": float(step.unit_price) if step.unit_price is not None else None,
                "cost_amount": float(step.cost_amount) if step.cost_amount is not None else None,
                "currency": step.currency,
                "quota_units": step.quota_units,
                "cost_breakdown": step.cost_breakdown,
                "started_at": step.started_at,
                "finished_at": step.finished_at,
                "created_at": step.created_at,
                "updated_at": step.updated_at,
            }
            for step in steps
        ]

    def _build_step_result_summary(self, step: BusinessRunStep) -> dict[str, Any] | None:
        payload = step.result_payload if isinstance(step.result_payload, dict) else {}
        if not payload:
            return None
        summary: dict[str, Any] = {}
        image_urls = self._extract_urls(payload, keys=("images", "assets", "resultUrls", "imageUrls"))
        video_urls = self._extract_urls(payload, keys=("videos", "videoUrls"))
        if image_urls:
            summary["imageCount"] = len(image_urls)
            summary["firstImageUrl"] = image_urls[0]
        if video_urls:
            summary["videoCount"] = len(video_urls)
            summary["firstVideoUrl"] = video_urls[0]

        texts = payload.get("texts")
        first_text = None
        if isinstance(texts, list):
            for item in texts:
                if isinstance(item, (str, int, float)) and str(item).strip():
                    first_text = str(item).strip()
                    break
        if first_text:
            parsed = self._try_parse_json(first_text)
            if isinstance(parsed, dict):
                if isinstance(parsed.get("summary"), (str, int, float)):
                    summary["summary"] = str(parsed.get("summary"))[:500]
                if isinstance(parsed.get("style"), (str, int, float)):
                    summary["style"] = str(parsed.get("style"))[:160]
                if isinstance(parsed.get("composition"), (str, int, float)):
                    summary["composition"] = str(parsed.get("composition"))[:200]
                for key in ("subjects", "colors", "riskFlags"):
                    value = parsed.get(key)
                    if isinstance(value, list):
                        summary[key] = [str(item)[:80] for item in value[:8]]
                prompt_card = parsed.get("promptCard")
                if isinstance(prompt_card, dict):
                    for source_key, target_key in (
                        ("imageDesc", "imageDesc"),
                        ("positivePrompt", "positivePrompt"),
                        ("negativePrompt", "negativePrompt"),
                    ):
                        value = prompt_card.get(source_key)
                        if isinstance(value, (str, int, float)) and str(value).strip():
                            summary[target_key] = str(value).strip()[:800]
            else:
                summary["textPreview"] = first_text[:800]

        return summary or None

    @staticmethod
    def _try_parse_json(value: str) -> Any:
        text = str(value or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").strip()
            if text.endswith("```"):
                text = text[:-3].strip()
        try:
            return json.loads(text)
        except Exception:
            return None

    def _omit_large_fields(self, payload: Any, depth: int = 0) -> Any:
        if depth > 6:
            return "[truncated]"
        if isinstance(payload, dict):
            out: dict[str, Any] = {}
            for key, value in payload.items():
                key_lower = str(key).lower()
                if key_lower in {"imagebase64", "image_base64"} or key_lower.endswith("base64"):
                    out[key] = "[omitted]"
                else:
                    out[key] = self._omit_large_fields(value, depth + 1)
            return out
        if isinstance(payload, list):
            return [self._omit_large_fields(item, depth + 1) for item in payload[:50]]
        return payload


@lru_cache
def get_business_run_service() -> BusinessRunService:
    return BusinessRunService()
