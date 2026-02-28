"""Schemas for ability invocation logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AbilityInvocationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ability_id: str | None = None
    ability_provider: str
    capability_key: str
    ability_name: str | None = None
    ability_current_template_id: str | None = Field(default=None, description="能力当前模板版本ID")
    ability_template_history_count: int = Field(default=0, description="能力模板历史快照数量")
    ability_template_published: bool = Field(default=False, description="能力是否已发布模板")
    executor_id: str | None = None
    executor_name: str | None = None
    executor_type: str | None = None
    source: str
    task_id: str | None = None
    callback_id: str | None = None
    trace_id: str | None = None
    workflow_run_id: str | None = None
    status: str = Field(description="日志状态：pending/success/failed（日志维度）")
    submit_status: str | None = Field(
        default=None,
        description="提交阶段状态：pending/submitting/submit_failed/submitted",
    )
    final_status: str | None = Field(
        default=None,
        description="最终状态：pending/running/success/failed/canceled",
    )
    error_code: str | None = Field(default=None, description="标准错误码（可为空）")
    duration_ms: int | None = None
    stored_url: str | None = None
    request_payload: dict[str, Any] | None = None
    response_payload: dict[str, Any] | None = None
    result_assets: list[dict[str, Any]] | None = None
    error_message: str | None = Field(default=None, description="失败错误码或可读信息")
    callback_status: str | None = Field(
        default=None,
        description="回调状态：success/failed（可为空，表示未配置或未触发）",
    )
    callback_http_status: int | None = None
    callback_payload: dict[str, Any] | None = None
    callback_response: dict[str, Any] | None = None
    callback_error: str | None = None
    callback_started_at: datetime | None = None
    callback_finished_at: datetime | None = None
    billing_unit: str | None = None
    unit_price: float | None = None
    currency: str | None = None
    cost_amount: float | None = None
    created_at: datetime


class AbilityInvocationLogListResponse(BaseModel):
    total: int | None = None
    limit: int | None = None
    offset: int | None = None
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
    total_cost: float | None = None
    avg_cost: float | None = None

    last_success_at: datetime | None = None
    last_failed_at: datetime | None = None


class AbilityLogCostSummary(BaseModel):
    key: str
    count: int
    total_cost: float | None = None
    avg_cost: float | None = None


class AbilityInvocationLogMetricsResponse(BaseModel):
    window_hours: int
    total_count: int | None = None
    total_success_count: int | None = None
    total_failed_count: int | None = None
    uncosted_count: int | None = None
    total_cost: float | None = None
    avg_cost_per_call: float | None = None
    provider_totals: list[AbilityLogCostSummary] = Field(default_factory=list)
    currency_totals: list[AbilityLogCostSummary] = Field(default_factory=list)
    buckets: list[AbilityInvocationLogMetricBucket]
