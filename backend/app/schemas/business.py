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
    governanceStatus: str = Field(default="unknown", alias="governance_status")
    governanceIssues: list[str] = Field(default_factory=list, alias="governance_issues")
    governanceSuggestions: list[str] = Field(default_factory=list, alias="governance_suggestions")
    runtimeKeyConfigured: bool | None = Field(default=None, alias="runtime_key_configured")
    modelCostConfigured: bool | None = Field(default=None, alias="model_cost_configured")
    egressVerified: bool | None = Field(default=None, alias="egress_verified")
    latestAcceptance: dict[str, Any] | None = Field(default=None, alias="latest_acceptance")
    acceptanceRecords: list[dict[str, Any]] = Field(default_factory=list, alias="acceptance_records")
    releaseGate: dict[str, Any] | None = Field(default=None, alias="release_gate")
    latestRun: dict[str, Any] | None = Field(default=None, alias="latest_run")
    runMetrics: dict[str, Any] | None = Field(default=None, alias="run_metrics")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessCapabilityListResponse(BaseModel):
    items: list[BusinessCapabilityRead]


class BusinessDefaultApprovalCreateRequest(BaseModel):
    note: str | None = None


class BusinessDefaultApprovalDecisionRequest(BaseModel):
    note: str | None = None


class BusinessDefaultApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    businessKey: str = Field(alias="business_key")
    sourceCapabilityId: str | None = Field(default=None, alias="source_capability_id")
    targetCapabilityId: str = Field(alias="target_capability_id")
    status: str
    requesterUserId: str | None = Field(default=None, alias="requester_user_id")
    requesterUsername: str | None = Field(default=None, alias="requester_username")
    approverUserId: str | None = Field(default=None, alias="approver_user_id")
    approverUsername: str | None = Field(default=None, alias="approver_username")
    requestNote: str | None = Field(default=None, alias="request_note")
    decisionNote: str | None = Field(default=None, alias="decision_note")
    beforePayload: dict[str, Any] | None = Field(default=None, alias="before_payload")
    afterPayload: dict[str, Any] | None = Field(default=None, alias="after_payload")
    sourceCapability: BusinessCapabilityRead | None = Field(default=None, alias="source_capability")
    targetCapability: BusinessCapabilityRead | None = Field(default=None, alias="target_capability")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")
    decidedAt: datetime | None = Field(default=None, alias="decided_at")
    appliedAt: datetime | None = Field(default=None, alias="applied_at")


class BusinessDefaultApprovalListResponse(BaseModel):
    items: list[BusinessDefaultApprovalRead]


class BusinessAcceptanceRecordRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(default="passed", description="passed / failed / warning / waived")
    note: str | None = Field(default=None, description="验收说明")
    evidenceRunId: str | None = Field(default=None, alias="evidence_run_id", description="关联业务运行 ID")
    evidenceUrl: str | None = Field(default=None, alias="evidence_url", description="证据链接，例如测评报告或截图")
    checklist: dict[str, Any] | None = Field(default=None, description="人工验收勾选项")
    metadata: dict[str, Any] | None = Field(default=None, description="补充信息")


class BusinessOperationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    action: str
    targetType: str = Field(alias="target_type")
    targetId: str | None = Field(default=None, alias="target_id")
    businessKey: str | None = Field(default=None, alias="business_key")
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    actorUserId: str | None = Field(default=None, alias="actor_user_id")
    actorUsername: str | None = Field(default=None, alias="actor_username")
    actorRole: str | None = Field(default=None, alias="actor_role")
    note: str | None = None
    beforePayload: dict[str, Any] | None = Field(default=None, alias="before_payload")
    afterPayload: dict[str, Any] | None = Field(default=None, alias="after_payload")
    createdAt: datetime = Field(alias="created_at")


class BusinessOperationLogListResponse(BaseModel):
    items: list[BusinessOperationLogRead]


class BusinessClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    tenantId: str = Field(alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    displayName: str = Field(alias="display_name")
    status: str
    allowedBusinessKeys: list[str] = Field(default_factory=list, alias="allowed_business_keys")
    dailyRunLimit: int | None = Field(default=None, alias="daily_run_limit")
    dailyQuotaUnits: int | None = Field(default=None, alias="daily_quota_units")
    concurrentRunLimit: int | None = Field(default=None, alias="concurrent_run_limit")
    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessClientListResponse(BaseModel):
    items: list[BusinessClientRead]


class BusinessClientCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    tenantId: str = Field(alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    displayName: str | None = Field(default=None, alias="display_name")
    status: str = "active"
    allowedBusinessKeys: list[str] | None = Field(default=None, alias="allowed_business_keys")
    dailyRunLimit: int | None = Field(default=None, ge=1, alias="daily_run_limit")
    dailyQuotaUnits: int | None = Field(default=None, ge=1, alias="daily_quota_units")
    concurrentRunLimit: int | None = Field(default=None, ge=1, alias="concurrent_run_limit")
    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")


class BusinessClientUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    displayName: str | None = Field(default=None, alias="display_name")
    status: str | None = None
    allowedBusinessKeys: list[str] | None = Field(default=None, alias="allowed_business_keys")
    dailyRunLimit: int | None = Field(default=None, ge=1, alias="daily_run_limit")
    dailyQuotaUnits: int | None = Field(default=None, ge=1, alias="daily_quota_units")
    concurrentRunLimit: int | None = Field(default=None, ge=1, alias="concurrent_run_limit")
    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")


class BusinessApiKeyCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    name: str
    key: str
    status: str = "active"
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    allowedBusinessKeys: list[str] = Field(default_factory=list, alias="allowed_business_keys")
    expireAt: datetime | None = Field(default=None, alias="expire_at")
    metadata: dict[str, Any] | None = None


class BusinessApiKeyUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    key: str | None = None
    status: str | None = None
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    allowedBusinessKeys: list[str] | None = Field(default=None, alias="allowed_business_keys")
    expireAt: datetime | None = Field(default=None, alias="expire_at")
    metadata: dict[str, Any] | None = None


class BusinessApiKeyRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    status: str
    keyPreview: str = Field(alias="key_preview")
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    allowedBusinessKeys: list[str] = Field(default_factory=list, alias="allowed_business_keys")
    usageCount: int = Field(alias="usage_count")
    expireAt: datetime | None = Field(default=None, alias="expire_at")
    metadata: dict[str, Any] | None = None
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessApiKeyListResponse(BaseModel):
    items: list[BusinessApiKeyRead]


class BusinessApiKeyUsageLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    apiKeyId: str | None = Field(default=None, alias="api_key_id")
    apiKeyName: str | None = Field(default=None, alias="api_key_name")
    apiKeyPreview: str | None = Field(default=None, alias="api_key_preview")
    method: str
    path: str
    statusCode: int | None = Field(default=None, alias="status_code")
    businessKey: str | None = Field(default=None, alias="business_key")
    runId: str | None = Field(default=None, alias="run_id")
    requestId: str | None = Field(default=None, alias="request_id")
    traceId: str | None = Field(default=None, alias="trace_id")
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    errorCode: str | None = Field(default=None, alias="error_code")
    durationMs: int | None = Field(default=None, alias="duration_ms")
    ipAddress: str | None = Field(default=None, alias="ip_address")
    userAgent: str | None = Field(default=None, alias="user_agent")
    createdAt: datetime = Field(alias="created_at")


class BusinessApiKeyUsageLogListResponse(BaseModel):
    items: list[BusinessApiKeyUsageLogRead]
    total: int


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


class BusinessCapabilityPromoteRequest(BaseModel):
    activate: bool = Field(default=True, description="如果版本未启用，是否先启用再设为默认")
    note: str | None = Field(default=None, description="切换原因，写入版本事件")


class BusinessCapabilityRollbackRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    targetCapabilityId: str | None = Field(default=None, alias="target_capability_id", description="指定回滚目标；为空则自动使用上一默认版")
    activate: bool = Field(default=True, description="如果回滚目标未启用，是否先启用再设为默认")
    note: str | None = Field(default=None, description="回滚原因，写入版本事件")


class BusinessRoutePreviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    businessKey: str = Field(alias="business_key")
    requestedVersion: str | None = Field(default=None, alias="requested_version")
    selectedCapabilityId: str = Field(alias="selected_capability_id")
    selectedVersion: str = Field(alias="selected_version")
    selectedDisplayName: str = Field(alias="selected_display_name")
    selectedStatus: str = Field(alias="selected_status")
    selectedIsDefault: bool = Field(alias="selected_is_default")
    selectedBy: str = Field(alias="selected_by")
    routeInfo: dict[str, Any] = Field(alias="route_info")
    defaultCapabilityId: str | None = Field(default=None, alias="default_capability_id")
    defaultVersion: str | None = Field(default=None, alias="default_version")
    activeVersions: list[dict[str, Any]] = Field(default_factory=list, alias="active_versions")


class BusinessRunCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: str | None = Field(default=None, description="指定业务版本；为空则使用默认启用版本")
    imageUrl: str | None = Field(default=None, description="主图 URL")
    url: str | None = Field(default=None, description="主图 URL 兼容字段")
    prompt: str | None = Field(default=None, description="业务提示词")
    inputs: dict[str, Any] | None = Field(default=None, description="业务参数；不同业务能力字段不同")
    bili: float | str | None = Field(default=None, description="图裂变相似度，0-100；值越大越接近原图。底层 ComfyUI denoise 由后端反向换算，兼容 50% 这类百分比口径")
    width: int | None = Field(default=None, description="输出宽度")
    height: int | None = Field(default=None, description="输出高度")
    batch_size: int | None = Field(default=None, description="输出张数")
    batch: int | None = Field(default=None, description="输出张数；花纹提取使用该字段")
    steps: int | None = Field(default=None, description="采样步数")
    cfg: float | None = Field(default=None, description="提示词控制强度")
    profile_id: str | None = Field(default=None, description="业务侧配置 ID")
    profile: str | None = Field(default=None, description="业务侧配置 ID；兼容 AI 团队接口包字段")
    mode: str | None = Field(default=None, description="业务执行模式；例如 fission")
    vl_result: dict[str, Any] | str | None = Field(default=None, description="上游 VL 控制卡 JSON；可由中台 VL 组件自动生成")
    ipadapter_weight: float | None = Field(default=None, description="参考图约束权重")
    colormatch_method: str | None = Field(default=None, description="颜色匹配方式")
    colormatch_strength: float | None = Field(default=None, description="颜色匹配强度")
    image_desc: str | None = Field(default=None, description="图片描述，可由 VL 分析结果填入")
    variation_strength: str | None = Field(default=None, description="GPT Image 2 裂变幅度：low / medium / high")
    quality: str | None = Field(default=None, description="商业模型质量档位：preview / production / premium")
    count: int | None = Field(default=None, description="商业模型输出张数；当前建议 1-3")
    preserve_layout: bool | None = Field(default=None, description="是否尽量保留原图版式")
    preserve_border: str | None = Field(default=None, description="边框保留策略：auto / true / false")
    preserve_count_density: bool | None = Field(default=None, description="是否保留元素数量感和密度")
    style_shift: str | None = Field(default=None, description="风格迁移幅度：standard / conservative / creative")
    size: str | None = Field(default=None, description="商业模型输出尺寸；GPT Image 2 默认 auto")
    output_format: str | None = Field(default=None, description="商业模型输出格式；默认 png")
    mask_url: str | None = Field(default=None, alias="maskUrl", description="可选蒙版 URL；用于 OpenAI 图片编辑")
    negative_prompt: str | None = Field(default=None, description="反向提示词；花纹提取使用该字段")
    lora: str | None = Field(default=None, description="LoRA 方案；花纹提取使用该字段")
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
    userId: str | None = Field(default=None, description="业务方用户 ID；仅作为外部上下文保留，不直接写入平台用户外键")
    userName: str | None = Field(default=None, description="业务用户展示名，用于管理端排查")
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
    executorId: str | None = Field(default=None, alias="executor_id")
    executorName: str | None = Field(default=None, alias="executor_name")
    executorType: str | None = Field(default=None, alias="executor_type")
    executionEvidence: dict[str, Any] | None = Field(default=None, alias="execution_evidence")
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
    billingStatus: str | None = Field(default=None, alias="billing_status")
    chargeable: bool | None = None
    noChargeReason: str | None = Field(default=None, alias="no_charge_reason")
    callbackStatus: str | None = Field(default=None, alias="callback_status")
    callbackHttpStatus: int | None = Field(default=None, alias="callback_http_status")
    callbackError: str | None = Field(default=None, alias="callback_error")
    debugUrl: str | None = Field(default=None, alias="debug_url")
    routeInfo: dict[str, Any] | None = Field(default=None, alias="route_info")
    issueCategory: str | None = Field(default=None, alias="issue_category")
    issueLabel: str | None = Field(default=None, alias="issue_label")
    issueSeverity: str | None = Field(default=None, alias="issue_severity")
    issueAction: str | None = Field(default=None, alias="issue_action")
    issueEvidence: str | None = Field(default=None, alias="issue_evidence")
    retestSourceRunId: str | None = Field(default=None, alias="retest_source_run_id")
    retestLatestRunId: str | None = Field(default=None, alias="retest_latest_run_id")
    retestLatestStatus: str | None = Field(default=None, alias="retest_latest_status")
    retestAttempts: int = Field(default=0, alias="retest_attempts")
    retestRecovered: bool = Field(default=False, alias="retest_recovered")
    retestSummary: dict[str, Any] | None = Field(default=None, alias="retest_summary")
    flowSummary: dict[str, Any] | None = Field(default=None, alias="flow_summary")
    steps: list[BusinessRunStepRead] = Field(default_factory=list)
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")
    startedAt: datetime | None = Field(default=None, alias="started_at")
    finishedAt: datetime | None = Field(default=None, alias="finished_at")


class BusinessRunListResponse(BaseModel):
    items: list[BusinessRunRead]
    total: int


class BusinessRunBulkActionRequest(BaseModel):
    runIds: list[str] = Field(default_factory=list)
    note: str | None = None
    onlyFailed: bool = True


class BusinessRunBulkActionItem(BaseModel):
    runId: str = Field(alias="run_id")
    newRunId: str | None = Field(default=None, alias="new_run_id")
    ok: bool
    status: str
    message: str | None = None


class BusinessRunBulkActionResponse(BaseModel):
    action: str
    total: int
    succeeded: int
    failed: int
    items: list[BusinessRunBulkActionItem]


class BusinessRunIssueChecklistRequest(BaseModel):
    runIds: list[str] = Field(default_factory=list)
    onlyFailed: bool = True


class BusinessRunIssueChecklistItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    runId: str = Field(alias="run_id")
    businessKey: str | None = Field(default=None, alias="business_key")
    version: str | None = None
    status: str
    issueCategory: str = Field(alias="issue_category")
    issueLabel: str = Field(alias="issue_label")
    issueSeverity: str = Field(alias="issue_severity")
    issueAction: str | None = Field(default=None, alias="issue_action")
    issueEvidence: str | None = Field(default=None, alias="issue_evidence")
    recommendedActions: list[str] = Field(default_factory=list, alias="recommended_actions")
    diagnostics: list[str] = Field(default_factory=list)
    abilityId: str | None = Field(default=None, alias="ability_id")
    abilityName: str | None = Field(default=None, alias="ability_name")
    executorId: str | None = Field(default=None, alias="executor_id")
    executorName: str | None = Field(default=None, alias="executor_name")
    callbackStatus: str | None = Field(default=None, alias="callback_status")
    retestLatestRunId: str | None = Field(default=None, alias="retest_latest_run_id")
    retestLatestStatus: str | None = Field(default=None, alias="retest_latest_status")
    createdAt: datetime | None = Field(default=None, alias="created_at")


class BusinessRunIssueChecklistResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    generatedAt: str = Field(alias="generated_at")
    total: int
    issueCount: int = Field(alias="issue_count")
    skippedCount: int = Field(default=0, alias="skipped_count")
    byCategory: dict[str, int] = Field(default_factory=dict, alias="by_category")
    bySeverity: dict[str, int] = Field(default_factory=dict, alias="by_severity")
    markdown: str
    items: list[BusinessRunIssueChecklistItem]


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
    actualCostByCurrency: dict[str, float] = Field(default_factory=dict, alias="actual_cost_by_currency")
    quotaUnits: int = Field(default=0, alias="quota_units")
    actualQuotaUnits: int = Field(default=0, alias="actual_quota_units")
    billable: int = 0
    unpriced: int = 0
    noCharge: int = Field(default=0, alias="no_charge")
    billingPending: int = Field(default=0, alias="billing_pending")
    callbackSuccess: int = Field(default=0, alias="callback_success")
    callbackFailed: int = Field(default=0, alias="callback_failed")
    callbackRunning: int = Field(default=0, alias="callback_running")
    callbackMissing: int = Field(default=0, alias="callback_missing")
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


class BusinessIssueBucket(BusinessUsageBucket):
    severity: str | None = None
    action: str | None = None


class BusinessUnresolvedIssueBucket(BusinessIssueBucket):
    retested: int = 0
    retestAttempts: int = Field(default=0, alias="retest_attempts")


class BusinessUnresolvedIssueItem(BaseModel):
    id: str
    runId: str = Field(alias="id")
    businessKey: str = Field(alias="business_key")
    version: str | None = None
    status: str
    source: str
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    traceId: str | None = Field(default=None, alias="trace_id")
    issueCategory: str = Field(alias="issue_category")
    issueLabel: str = Field(alias="issue_label")
    issueAction: str | None = Field(default=None, alias="issue_action")
    retestAttempts: int = Field(default=0, alias="retest_attempts")
    retestLatestRunId: str | None = Field(default=None, alias="retest_latest_run_id")
    retestLatestStatus: str | None = Field(default=None, alias="retest_latest_status")
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
    actualCostByCurrency: dict[str, float] = Field(default_factory=dict, alias="actual_cost_by_currency")
    quotaUnits: int = Field(default=0, alias="quota_units")
    actualQuotaUnits: int = Field(default=0, alias="actual_quota_units")
    billable: int = 0
    unpriced: int = 0
    noCharge: int = Field(default=0, alias="no_charge")
    billingPending: int = Field(default=0, alias="billing_pending")
    callbackSuccess: int = Field(default=0, alias="callback_success")
    callbackFailed: int = Field(default=0, alias="callback_failed")
    callbackRunning: int = Field(default=0, alias="callback_running")
    callbackMissing: int = Field(default=0, alias="callback_missing")
    byBusiness: list[BusinessUsageBucket] = Field(default_factory=list, alias="by_business")
    bySource: list[BusinessUsageBucket] = Field(default_factory=list, alias="by_source")
    byTenant: list[BusinessUsageBucket] = Field(default_factory=list, alias="by_tenant")
    byClient: list[BusinessUsageBucket] = Field(default_factory=list, alias="by_client")
    byVersion: list[BusinessUsageBucket] = Field(default_factory=list, alias="by_version")
    byIssue: list[BusinessIssueBucket] = Field(default_factory=list, alias="by_issue")
    unresolvedIssues: list[BusinessUnresolvedIssueBucket] = Field(default_factory=list, alias="unresolved_issues")
    recentUnresolvedIssues: list[BusinessUnresolvedIssueItem] = Field(default_factory=list, alias="recent_unresolved_issues")
    recentFailures: list[BusinessUsageFailure] = Field(default_factory=list, alias="recent_failures")
