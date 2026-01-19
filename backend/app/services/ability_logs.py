"""Ability invocation logging helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import uuid4
from typing import Any

from sqlalchemy import desc, select

from app.core.db import get_session
from app.models.integration import Ability, AbilityInvocationLog, Executor


@dataclass
class AbilityLogStartParams:
    ability_id: str | None = None
    ability_name: str | None = None
    provider: str | None = None
    capability_key: str | None = None
    executor_id: str | None = None
    executor_name: str | None = None
    executor_type: str | None = None
    source: str = "admin-test"
    task_id: str | None = None
    request_payload: dict[str, Any] | None = None
    trace_id: str | None = None
    workflow_run_id: str | None = None
    billing_unit: str | None = None
    unit_price: float | None = None
    currency: str | None = None
    cost_amount: float | None = None


class AbilityLogService:
    """Stores ability/test invocation traces so the admin console can show history."""

    _sensitive_keys = {
        "imagebase64",
        "image_base64",
        "resultimage",
        "result_image",
        "mask_base64",
        "payload",
        "file_content",
    }

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def start_log(self, params: AbilityLogStartParams) -> int | None:
        """Create a log stub and return its ID."""
        try:
            with get_session() as session:
                ability = session.get(Ability, params.ability_id) if params.ability_id else None
                executor = session.get(Executor, params.executor_id) if params.executor_id else None
                ability_provider = params.provider or (ability.provider if ability else "unknown")
                capability_key = params.capability_key or (ability.capability_key if ability else "unknown")
                ability_name = params.ability_name or (ability.display_name if ability else None)
                executor_name = params.executor_name or (executor.name if executor else None)
                executor_type = params.executor_type or (executor.type if executor else None)
                trace_id = params.trace_id or uuid4().hex
                currency = params.currency
                billing_unit = params.billing_unit
                unit_price = params.unit_price
                cost_amount = params.cost_amount
                if ability and not currency:
                    metadata = ability.extra_metadata or {}
                    pricing = metadata.get("pricing") if isinstance(metadata, dict) else None
                    if isinstance(pricing, dict):
                        currency = currency or pricing.get("currency")
                        billing_unit = billing_unit or pricing.get("unit")
                        unit_price = unit_price or pricing.get("discount_price") or pricing.get("list_price")
                if cost_amount is None and unit_price is not None:
                    try:
                        cost_amount = float(unit_price)
                    except (TypeError, ValueError):
                        cost_amount = None
                log = AbilityInvocationLog(
                    ability_id=params.ability_id,
                    ability_provider=ability_provider,
                    capability_key=capability_key,
                    ability_name=ability_name,
                    executor_id=params.executor_id,
                    executor_name=executor_name,
                    executor_type=executor_type,
                    source=params.source or "admin-test",
                    task_id=params.task_id,
                    status="pending",
                    request_payload=self._sanitize_payload(params.request_payload),
                    trace_id=trace_id,
                    workflow_run_id=params.workflow_run_id,
                    billing_unit=billing_unit,
                    unit_price=unit_price,
                    currency=currency,
                    cost_amount=cost_amount,
                )
                session.add(log)
                session.commit()
                session.refresh(log)
                return log.id
        except Exception as exc:  # pragma: no cover - best effort logging
            self._logger.warning("Failed to create ability log: %s", exc)
            return None

    def finish_success(
        self,
        log_id: int | None,
        *,
        response_payload: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Mark a log as successful."""
        self._finalize_log(
            log_id,
            status="success",
            response_payload=response_payload,
            duration_ms=duration_ms,
            error_message=None,
        )

    def finish_failure(
        self,
        log_id: int | None,
        *,
        error_message: str | None,
        response_payload: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Mark a log as failed."""
        self._finalize_log(
            log_id,
            status="failed",
            response_payload=response_payload,
            duration_ms=duration_ms,
            error_message=error_message or "unknown error",
        )

    def list_logs(
        self,
        *,
        ability_id: str | None = None,
        provider: str | None = None,
        capability_key: str | None = None,
        limit: int = 20,
    ) -> list[AbilityInvocationLog]:
        """Return the most recent logs for an ability or provider/key pair."""
        with get_session() as session:
            stmt = select(AbilityInvocationLog)
            if ability_id:
                stmt = stmt.where(AbilityInvocationLog.ability_id == ability_id)
            elif provider and capability_key:
                stmt = stmt.where(
                    AbilityInvocationLog.ability_provider == provider,
                    AbilityInvocationLog.capability_key == capability_key,
                )
            stmt = stmt.order_by(desc(AbilityInvocationLog.created_at)).limit(max(1, min(limit, 100)))
            return session.execute(stmt).scalars().all()

    def get_log_by_workflow_run_id(self, workflow_run_id: str) -> AbilityInvocationLog | None:
        """Return the latest log that matches a workflow_run_id."""
        if not workflow_run_id:
            return None
        with get_session() as session:
            stmt = (
                select(AbilityInvocationLog)
                .where(AbilityInvocationLog.workflow_run_id == workflow_run_id)
                .order_by(desc(AbilityInvocationLog.created_at))
                .limit(1)
            )
            return session.execute(stmt).scalars().first()

    def _finalize_log(
        self,
        log_id: int | None,
        *,
        status: str,
        response_payload: dict[str, Any] | None,
        duration_ms: int | None,
        error_message: str | None,
    ) -> None:
        if not log_id:
            return
        try:
            with get_session() as session:
                log = session.get(AbilityInvocationLog, log_id)
                if not log:
                    return
                log.status = status
                if duration_ms is not None:
                    log.duration_ms = duration_ms
                sanitized_response = self._sanitize_payload(response_payload)
                if sanitized_response is not None:
                    log.response_payload = sanitized_response
                stored_url = self._extract_stored_url(response_payload)
                if stored_url:
                    log.stored_url = stored_url
                assets = self._extract_assets(response_payload)
                if assets is not None:
                    log.result_assets = assets
                if error_message:
                    log.error_message = error_message
                session.add(log)
                session.commit()
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.warning("Failed to finalize ability log %s: %s", log_id, exc)

    def _sanitize_payload(self, payload: dict[str, Any] | None, *, depth: int = 0) -> dict[str, Any] | None:
        if payload is None:
            return None
        if depth > 6:
            return {"detail": "truncated"}

        def _sanitize_value(value: Any, key: str | None = None, level: int = 0) -> Any:
            if isinstance(value, dict):
                return {
                    str(k): _sanitize_value(v, str(k).lower(), level + 1)
                    for k, v in value.items()
                    if level < 6
                }
            if isinstance(value, list):
                return [_sanitize_value(item, key, level + 1) for item in value[:50]]
            if isinstance(value, str):
                lowered = key or ""
                if lowered in self._sensitive_keys or lowered.endswith("base64"):
                    return "[omitted]"
                if len(value) > 2000:
                    return f"{value[:2000]}…"
                return value
            return value

        return _sanitize_value(payload, level=depth)  # type: ignore[arg-type]

    def _extract_stored_url(self, payload: dict[str, Any] | None) -> str | None:
        if not isinstance(payload, dict):
            return None
        for key in ("storedUrl", "stored_url"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        assets = payload.get("assets")
        asset_url = None
        if isinstance(assets, list):
            for item in assets:
                if isinstance(item, dict):
                    value = item.get("ossUrl") or item.get("url")
                    if isinstance(value, str) and value:
                        asset_url = value
                        break
        if asset_url:
            return asset_url
        result_urls = payload.get("resultUrls")
        if isinstance(result_urls, list) and result_urls:
            first = result_urls[0]
            if isinstance(first, str):
                return first
        image_url = payload.get("imageUrl")
        if isinstance(image_url, str) and image_url:
            return image_url
        return None

    def _extract_assets(self, payload: dict[str, Any] | None) -> list[dict[str, Any]] | None:
        if not isinstance(payload, dict):
            return None
        assets = payload.get("assets") or payload.get("storedAssets")
        if not isinstance(assets, list) or not assets:
            return None
        sanitized: list[dict[str, Any]] = []
        for entry in assets[:20]:
            if isinstance(entry, dict):
                record: dict[str, Any] = {}
                for key in ("ossUrl", "ossKey", "sourceUrl", "contentType", "size", "tag", "url"):
                    value = entry.get(key)
                    if value is not None:
                        record[key] = value
                if record:
                    sanitized.append(record)
        return sanitized or None


ability_log_service = AbilityLogService()
