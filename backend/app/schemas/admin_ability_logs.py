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
