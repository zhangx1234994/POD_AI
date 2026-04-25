"""Schemas for business-facing capability orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BusinessCapabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    businessKey: str = Field(alias="business_key")
    version: str
    displayName: str = Field(alias="display_name")
    description: str | None = None
    status: str
    isDefault: bool = Field(alias="is_default")
    releaseTime: datetime | None = Field(default=None, alias="release_time")
    recipe: dict[str, Any]
    inputSchema: dict[str, Any] | None = Field(default=None, alias="input_schema")
    outputSchema: dict[str, Any] | None = Field(default=None, alias="output_schema")
    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")
    primaryAbilityId: str | None = Field(default=None, alias="primary_ability_id")
    primaryAbilityName: str | None = Field(default=None, alias="primary_ability_name")
    primaryAbilityProvider: str | None = Field(default=None, alias="primary_ability_provider")
    vendorModelId: int | None = Field(default=None, alias="vendor_model_id")
    vendorModelName: str | None = Field(default=None, alias="vendor_model_name")
    vendorModelProvider: str | None = Field(default=None, alias="vendor_model_provider")
    recipeSteps: list[dict[str, Any]] = Field(default_factory=list, alias="recipe_steps")
    latestRun: dict[str, Any] | None = Field(default=None, alias="latest_run")
    runMetrics: dict[str, Any] | None = Field(default=None, alias="run_metrics")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessCapabilityListResponse(BaseModel):
    items: list[BusinessCapabilityRead]


class BusinessCapabilityCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    businessKey: str = Field(alias="business_key")
    version: str
    displayName: str = Field(alias="display_name")
    description: str | None = None
    status: str = "inactive"
    isDefault: bool = Field(default=False, alias="is_default")
    releaseTime: datetime | None = Field(default=None, alias="release_time")
    primaryAbilityId: str | None = Field(default=None, alias="primary_ability_id")
    recipe: dict[str, Any] | None = None
    inputSchema: dict[str, Any] | None = Field(default=None, alias="input_schema")
    outputSchema: dict[str, Any] | None = Field(default=None, alias="output_schema")
    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")


class BusinessCapabilityUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    businessKey: str | None = Field(default=None, alias="business_key")
    version: str | None = None
    displayName: str | None = Field(default=None, alias="display_name")
    description: str | None = None
    status: str | None = None
    isDefault: bool | None = Field(default=None, alias="is_default")
    releaseTime: datetime | None = Field(default=None, alias="release_time")
    primaryAbilityId: str | None = Field(default=None, alias="primary_ability_id")
    recipe: dict[str, Any] | None = None
    inputSchema: dict[str, Any] | None = Field(default=None, alias="input_schema")
    outputSchema: dict[str, Any] | None = Field(default=None, alias="output_schema")
    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")


class BusinessRunCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: str | None = Field(default=None, description="指定业务版本；为空则使用默认启用版本")
    imageUrl: str | None = Field(default=None, description="主图 URL")
    url: str | None = Field(default=None, description="主图 URL 兼容字段")
    prompt: str | None = Field(default=None, description="业务提示词")
    inputs: dict[str, Any] | None = Field(default=None, description="业务参数；不同业务能力字段不同")
    bili: float | None = Field(default=None, description="图裂变幅度/噪声强度，数值越大变化越明显")
    width: int | None = Field(default=None, description="输出宽度")
    height: int | None = Field(default=None, description="输出高度")
    batch_size: int | None = Field(default=None, description="输出张数")
    steps: int | None = Field(default=None, description="采样步数")
    cfg: float | None = Field(default=None, description="提示词控制强度")
    profile_id: str | None = Field(default=None, description="业务侧配置 ID")
    ipadapter_weight: float | None = Field(default=None, description="参考图约束权重")
    colormatch_method: str | None = Field(default=None, description="颜色匹配方式")
    colormatch_strength: float | None = Field(default=None, description="颜色匹配强度")
    image_desc: str | None = Field(default=None, description="图片描述，可由 VL 分析结果填入")
    expand_left: int | None = Field(default=None, description="向左扩展像素")
    expand_right: int | None = Field(default=None, description="向右扩展像素")
    expand_top: int | None = Field(default=None, description="向上扩展像素")
    expand_bottom: int | None = Field(default=None, description="向下扩展像素")
    seed: int | None = Field(default=None, description="随机种子；为空时由底层能力随机")
    timeout: int | None = Field(default=None, description="任务超时时间，单位秒")
    source: str | None = Field(default=None, description="调用来源，例如 coze、client、partner-api")
    channel: str | None = Field(default=None, description="业务渠道，例如 coze-workflow、open-api、eval")
    traceId: str | None = Field(default=None, description="调用链路 ID，用于跨系统排查")
    requestId: str | None = Field(default=None, description="业务方请求 ID，用于幂等和日志关联")
    tenantId: str | None = Field(default=None, description="租户/业务方 ID")
    clientId: str | None = Field(default=None, description="客户端/应用 ID")
    callbackUrl: str | None = Field(default=None, description="业务任务终态回调地址")
    callbackHeaders: dict[str, str] | None = Field(default=None, description="业务任务回调请求头")
    metadata: dict[str, Any] | None = Field(default=None, description="调用来源、灰度标识等业务上下文")


class BusinessRunStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    runId: str = Field(alias="run_id")
    order: int = Field(alias="step_order")
    stepId: str | None = Field(default=None, alias="step_id")
    stepType: str = Field(alias="step_type")
    role: str | None = None
    displayName: str | None = Field(default=None, alias="display_name")
    enabled: bool
    status: str
    abilityId: str | None = Field(default=None, alias="ability_id")
    abilityName: str | None = Field(default=None, alias="ability_name")
    abilityProvider: str | None = Field(default=None, alias="ability_provider")
    abilityTaskId: str | None = Field(default=None, alias="ability_task_id")
    abilityLogId: int | None = Field(default=None, alias="ability_log_id")
    resultSummary: dict[str, Any] | None = Field(default=None, alias="result_summary")
    error: str | None = Field(default=None, alias="error_message")
    durationMs: int | None = Field(default=None, alias="duration_ms")
    billingUnit: str | None = Field(default=None, alias="billing_unit")
    unitPrice: float | None = Field(default=None, alias="unit_price")
    costAmount: float | None = Field(default=None, alias="cost_amount")
    currency: str | None = None
    quotaUnits: int | None = Field(default=None, alias="quota_units")
    costBreakdown: dict[str, Any] | None = Field(default=None, alias="cost_breakdown")
    startedAt: datetime | None = Field(default=None, alias="started_at")
    finishedAt: datetime | None = Field(default=None, alias="finished_at")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    runId: str = Field(alias="id")
    businessKey: str = Field(alias="business_key")
    businessVersionId: str | None = Field(default=None, alias="business_version_id")
    version: str | None = None
    status: str
    source: str
    channel: str | None = None
    traceId: str | None = Field(default=None, alias="trace_id")
    requestId: str | None = Field(default=None, alias="request_id")
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    userId: str | None = Field(default=None, alias="user_id")
    userName: str | None = Field(default=None, alias="user_name")
    abilityId: str | None = Field(default=None, alias="ability_id")
    abilityName: str | None = Field(default=None, alias="ability_name")
    abilityProvider: str | None = Field(default=None, alias="ability_provider")
    vendorModelId: int | None = Field(default=None, alias="vendor_model_id")
    vendorModelName: str | None = Field(default=None, alias="vendor_model_name")
    vendorModelProvider: str | None = Field(default=None, alias="vendor_model_provider")
    abilityTaskId: str | None = Field(default=None, alias="ability_task_id")
    taskId: str | None = Field(default=None, alias="ability_task_id")
    abilityLogId: int | None = Field(default=None, alias="ability_log_id")
    requestPayload: dict[str, Any] | None = Field(default=None, alias="request_payload")
    resultPayload: dict[str, Any] | None = Field(default=None, alias="result_payload")
    imageUrls: list[str] | None = Field(default=None, alias="image_urls")
    videoUrls: list[str] | None = Field(default=None, alias="video_urls")
    texts: list[str] | None = None
    error: str | None = Field(default=None, alias="error_message")
    errorMessage: str | None = Field(default=None, alias="error_message")
    durationMs: int | None = Field(default=None, alias="duration_ms")
    billingUnit: str | None = Field(default=None, alias="billing_unit")
    unitPrice: float | None = Field(default=None, alias="unit_price")
    costAmount: float | None = Field(default=None, alias="cost_amount")
    currency: str | None = None
    quotaUnits: int | None = Field(default=None, alias="quota_units")
    costBreakdown: dict[str, Any] | None = Field(default=None, alias="cost_breakdown")
    callbackStatus: str | None = Field(default=None, alias="callback_status")
    debugUrl: str | None = Field(default=None, alias="debug_url")
    routeInfo: dict[str, Any] | None = Field(default=None, alias="route_info")
    steps: list[BusinessRunStepRead] = Field(default_factory=list)
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")
    startedAt: datetime | None = Field(default=None, alias="started_at")
    finishedAt: datetime | None = Field(default=None, alias="finished_at")


class BusinessRunListResponse(BaseModel):
    items: list[BusinessRunRead]
    total: int


class BusinessUsageBucket(BaseModel):
    key: str
    label: str
    total: int
    succeeded: int
    failed: int
    running: int
    queued: int
    cancelled: int
    successRate: float | None = Field(default=None, alias="success_rate")
    avgDurationMs: int | None = Field(default=None, alias="avg_duration_ms")
    costByCurrency: dict[str, float] = Field(default_factory=dict, alias="cost_by_currency")
    quotaUnits: int = Field(default=0, alias="quota_units")
    latestAt: datetime | None = Field(default=None, alias="latest_at")


class BusinessUsageFailure(BaseModel):
    id: str
    runId: str = Field(alias="id")
    businessKey: str = Field(alias="business_key")
    version: str | None = None
    status: str
    source: str
    channel: str | None = None
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    traceId: str | None = Field(default=None, alias="trace_id")
    error: str | None = Field(default=None, alias="error_message")
    createdAt: datetime = Field(alias="created_at")


class BusinessUsageSummaryResponse(BaseModel):
    windowHours: int = Field(alias="window_hours")
    filters: dict[str, Any]
    total: int
    succeeded: int
    failed: int
    running: int
    queued: int
    cancelled: int
    successRate: float | None = Field(default=None, alias="success_rate")
    avgDurationMs: int | None = Field(default=None, alias="avg_duration_ms")
    costByCurrency: dict[str, float] = Field(default_factory=dict, alias="cost_by_currency")
    quotaUnits: int = Field(default=0, alias="quota_units")
    byBusiness: list[BusinessUsageBucket] = Field(default_factory=list, alias="by_business")
    bySource: list[BusinessUsageBucket] = Field(default_factory=list, alias="by_source")
    byTenant: list[BusinessUsageBucket] = Field(default_factory=list, alias="by_tenant")
    byClient: list[BusinessUsageBucket] = Field(default_factory=list, alias="by_client")
    byVersion: list[BusinessUsageBucket] = Field(default_factory=list, alias="by_version")
    recentFailures: list[BusinessUsageFailure] = Field(default_factory=list, alias="recent_failures")
