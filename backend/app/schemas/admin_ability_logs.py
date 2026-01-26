"""Schemas for ability invocation logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AbilityInvocationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ability_id: str | None = None
    ability_provider: str
    capability_key: str
    ability_name: str | None = None
    executor_id: str | None = None
    executor_name: str | None = None
    executor_type: str | None = None
    source: str
    task_id: str | None = None
    trace_id: str | None = None
    workflow_run_id: str | None = None
    status: str
    duration_ms: int | None = None
    stored_url: str | None = None
    request_payload: dict[str, Any] | None = None
    response_payload: dict[str, Any] | None = None
    result_assets: list[dict[str, Any]] | None = None
    error_message: str | None = None
    billing_unit: str | None = None
    unit_price: float | None = None
    currency: str | None = None
    cost_amount: float | None = None
    created_at: datetime


class AbilityInvocationLogListResponse(BaseModel):
    items: list[AbilityInvocationLogRead]


class AbilityInvocationLogMetricBucket(BaseModel):
    """Aggregated metrics for ability invocations (best-effort)."""

    ability_provider: str
    capability_key: str
    executor_id: str | None = None

    count: int
    success_count: int
    failed_count: int
    success_rate: float | None = None

    avg_duration_ms: float | None = None
    p50_duration_ms: int | None = None
    p95_duration_ms: int | None = None

    last_success_at: datetime | None = None
    last_failed_at: datetime | None = None


class AbilityInvocationLogMetricsResponse(BaseModel):
    window_hours: int
    buckets: list[AbilityInvocationLogMetricBucket]
