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
    versionLine: dict[str, Any] | None = Field(default=None, alias="version_line")
    versionLineage: dict[str, Any] | None = Field(default=None, alias="version_lineage")
    versionFamily: dict[str, Any] | None = Field(default=None, alias="version_family")
    recipeSteps: list[dict[str, Any]] = Field(default_factory=list, alias="recipe_steps")
    orchestrationGraph: dict[str, Any] | None = Field(default=None, alias="orchestration_graph")
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


class BusinessApiKeyUsageRunGroup(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    runId: str | None = Field(default=None, alias="run_id")
    businessKey: str | None = Field(default=None, alias="business_key")
    runStatus: str | None = Field(default=None, alias="run_status")
    runVersion: str | None = Field(default=None, alias="run_version")
    businessVersionId: str | None = Field(default=None, alias="business_version_id")
    resultImageCount: int = Field(default=0, alias="result_image_count")
    resultVideoCount: int = Field(default=0, alias="result_video_count")
    resultTextCount: int = Field(default=0, alias="result_text_count")
    runError: str | None = Field(default=None, alias="run_error")
    runFinishedAt: datetime | None = Field(default=None, alias="run_finished_at")
    apiKeyName: str | None = Field(default=None, alias="api_key_name")
    apiKeyPreview: str | None = Field(default=None, alias="api_key_preview")
    requestId: str | None = Field(default=None, alias="request_id")
    traceId: str | None = Field(default=None, alias="trace_id")
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    totalCount: int = Field(default=0, alias="total_count")
    submitCount: int = Field(default=0, alias="submit_count")
    pollCount: int = Field(default=0, alias="poll_count")
    callbackCount: int = Field(default=0, alias="callback_count")
    errorCount: int = Field(default=0, alias="error_count")
    needsAttention: bool = Field(default=False, alias="needs_attention")
    issueCode: str | None = Field(default=None, alias="issue_code")
    issueHint: str | None = Field(default=None, alias="issue_hint")
    lastStatusCode: int | None = Field(default=None, alias="last_status_code")
    lastErrorCode: str | None = Field(default=None, alias="last_error_code")
    firstSeenAt: datetime | None = Field(default=None, alias="first_seen_at")
    lastSeenAt: datetime | None = Field(default=None, alias="last_seen_at")


class BusinessApiKeyUsageSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total: int = 0
    successCount: int = Field(default=0, alias="success_count")
    errorCount: int = Field(default=0, alias="error_count")
    submitCount: int = Field(default=0, alias="submit_count")
    pollCount: int = Field(default=0, alias="poll_count")
    callbackCount: int = Field(default=0, alias="callback_count")
    uniqueRunCount: int = Field(default=0, alias="unique_run_count")
    averageDurationMs: float | None = Field(default=None, alias="average_duration_ms")


class BusinessApiKeyUsagePagination(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total: int = 0
    offset: int = 0
    limit: int = 50
    hasMore: bool = Field(default=False, alias="has_more")
    nextOffset: int | None = Field(default=None, alias="next_offset")


class BusinessApiKeyUsageLogListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[BusinessApiKeyUsageLogRead]
    total: int
    offset: int = 0
    limit: int = 50
    pagination: BusinessApiKeyUsagePagination | None = None
    summary: BusinessApiKeyUsageSummary = Field(default_factory=BusinessApiKeyUsageSummary)
    groups: list[BusinessApiKeyUsageRunGroup] = Field(default_factory=list)


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


class BusinessCapabilityDraftCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: str | None = None
    displayName: str | None = Field(default=None, alias="display_name")
    note: str | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")


class BusinessCapabilityDraftRecipeUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recipe: dict[str, Any]
    primaryAbilityId: str | None = Field(default=None, alias="primary_ability_id")
    note: str | None = None


class BusinessCapabilityDraftPublishRequest(BaseModel):
    note: str | None = None


class BusinessCapabilityDraftValidateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    draft: BusinessCapabilityRead
    defaultCapability: BusinessCapabilityRead | None = Field(default=None, alias="default_capability")
    canPublish: bool = Field(alias="can_publish")
    checks: list[dict[str, Any]]
    diffSummary: list[str] = Field(default_factory=list, alias="diff_summary")
    releaseGate: dict[str, Any] = Field(default_factory=dict, alias="release_gate")
    nextAction: str | None = Field(default=None, alias="next_action")


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


class ProductCommercializationImage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    url: str = Field(description="产品图 URL。")
    role: str | None = Field(
        default=None,
        description="图片角色：primary/front/back/side/detail/texture/lifestyle/reference 等。",
    )
    label: str | None = Field(default=None, description="给运营人员看的图片标签。")
    isPrimary: bool = Field(default=False, alias="is_primary", description="是否作为本次视频执行的主参考图。")
    source: str | None = Field(default=None, description="图片来源，例如 upload/exported/manual。")
    weight: float | None = Field(default=None, ge=0, le=1, description="可选权重，用于后续路由或排序。")


class ProductCommercializationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action: str | None = Field(
        default=None,
        description="业务动作：copy_preview、video_preview、video_keyframes、video_generate（默认执行视频）、compose_video、visual_generate（配图）。",
    )

    productImageUrl: str | None = Field(
        default=None,
        alias="product_image_url",
        description="产品设计完成后的商品图 URL；预览可为空，视频生成必填",
    )
    productImages: list[ProductCommercializationImage] | None = Field(
        default=None,
        alias="product_images",
        description="可选产品图组；主图、正面、背面、侧面、细节、场景图等。旧字段 productImageUrl 仍作为主图兼容入口。",
    )
    designImageUrl: str | None = Field(
        default=None,
        alias="design_image_url",
        description="可选设计稿/印花图 URL，用于辅助理解商品来源",
    )
    productFields: dict[str, Any] = Field(
        default_factory=dict,
        alias="product_fields",
        description="可选产品导出字段 JSON；有则作为说明材料使用，没有则继续执行，图片事实优先",
    )
    extraPrompt: str | None = Field(default=None, alias="extra_prompt", description="业务方补充要求")
    outputLanguage: str = Field(
        default="en-US",
        alias="output_language",
        description="输出语言：en-US / zh-CN / bilingual",
    )
    marketRegion: str = Field(default="US", alias="market_region", description="目标市场：US / UK / EU / global")
    commercePlatform: str | None = Field(
        default=None,
        alias="commerce_platform",
        description="目标电商平台/渠道，例如 Amazon、Shopify、Etsy、TikTok Shop、独立站等",
    )
    copyTone: str | None = Field(
        default=None,
        alias="copy_tone",
        description="文案语气，例如 natural_professional / warm_gift / premium / playful / concise",
    )
    targetAudience: str | None = Field(default=None, alias="target_audience", description="目标人群")
    sellingAngle: str | None = Field(default=None, alias="selling_angle", description="本轮主打卖点或营销角度")
    forbiddenClaims: list[str] | str | None = Field(
        default=None,
        alias="forbidden_claims",
        description="禁止或谨慎使用的宣传点，例如环保、医疗、认证、品牌词等",
    )
    copyScenarios: list[str] | None = Field(
        default=None,
        alias="copy_scenarios",
        description="文案场景：listing_title / bullet_points / detail_description / ad_short_copy / keyword_pack",
    )
    visualSupportMode: str = Field(
        default="recommendation",
        alias="visual_support_mode",
        description="配图模式：none / recommendation / generate；generate 仍需显式执行动作",
    )
    videoScenario: str = Field(
        default="product_showcase_short",
        alias="video_scenario",
        description="视频类型/资产类型；兼容字段名仍为 videoScenario。当前允许 product_showcase_short / social_ad_short / detail_explainer。",
    )
    durationSeconds: int | None = Field(
        default=None,
        ge=1,
        le=60,
        alias="duration_seconds",
        description="期望单段视频执行时长。实际合法值由所选视频模型决定，例如 KIE Veo3.1 Fast 当前为 8 秒，Vidu 可按模型画像选择 3/5/8 秒。",
    )
    targetDurationSeconds: int | None = Field(
        default=None,
        ge=1,
        le=60,
        alias="target_duration_seconds",
        description="用户目标成片时长。后端按所选模型的片段时长画像规划分镜，必要时多段生成并合成。",
    )
    aspectRatio: str | None = Field(default="16:9", alias="aspect_ratio")
    strategyProfile: str | None = Field(default="default_pod_profile", alias="strategy_profile")
    executorId: str | None = Field(default=None, alias="executor_id", description="视频生成使用的 executor，可选 KIE/Vidu；不传使用默认 KIE")
    pollTimeout: float | None = Field(default=None, alias="poll_timeout", description="视频生成轮询超时秒数")
    videoPromptOverride: str | None = Field(
        default=None,
        alias="video_prompt_override",
        description="用户编辑后的最终视频执行脚本。仅影响显式视频生成动作，预览规划仍由模型生成。",
    )
    videoPlanningContext: dict[str, Any] | None = Field(
        default=None,
        alias="video_planning_context",
        description="视频规划结构化上下文，例如核心信息、目标人群、使用场景、镜头偏好、禁止内容和用户自由要求。",
        json_schema_extra={
            "properties": {
                "coreMessage": {"type": "string", "description": "核心信息或主打卖点"},
                "targetAudience": {"type": "string", "description": "目标人群"},
                "usageScene": {"type": "string", "description": "使用场景或投放场景"},
                "shotPreference": {"type": "string", "description": "镜头偏好"},
                "avoid": {"type": "string", "description": "禁止内容或规避项"},
                "userRequirement": {"type": "string", "description": "用户自由视频要求，会进入规划模型上下文"},
                "fields": {
                    "type": "array",
                    "description": "测评端或业务方结构化补充字段",
                    "items": {"type": "object", "additionalProperties": True},
                },
            },
            "additionalProperties": True,
        },
    )
    keyframeShotScope: str | int | None = Field(
        default=None,
        alias="keyframe_shot_scope",
        description="可选首尾帧生成范围；传镜头序号时只重生成该镜头的首帧/尾帧/关键帧，不传则生成全部计划关键帧。",
    )
    confirmedVideoKeyframes: list[dict[str, Any]] | None = Field(
        default=None,
        alias="confirmed_video_keyframes",
        description="用户已确认的视频首尾帧/关键帧资产。video_generate 会按 shot/segmentIndex 匹配并优先作为对应镜头参考图。",
    )
    visualScenes: list[str] | None = Field(
        default=None,
        alias="visual_scenes",
        description="配图任务的场景ID清单，例如 listing-main / social-ad-cover / detail-closeup。",
    )
    requestId: str | None = Field(default=None, alias="request_id")
    traceId: str | None = Field(default=None, alias="trace_id")
    source: str | None = None


class ProductCommercializationPreviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    requestId: str = Field(alias="request_id")
    businessKey: str = Field(alias="business_key")
    underlyingBusinessKey: str | None = Field(default=None, alias="underlying_business_key")
    version: str
    status: str
    generatedAt: str = Field(alias="generated_at")
    strategyProfile: str = Field(alias="strategy_profile")
    outputLanguage: str = Field(alias="output_language")
    marketRegion: str = Field(alias="market_region")
    copyScenarios: list[str] = Field(alias="copy_scenarios")
    productCard: dict[str, Any] = Field(alias="product_card")
    resolvedProductFacts: dict[str, Any] | None = Field(default=None, alias="resolved_product_facts")
    copyPackage: dict[str, Any] = Field(alias="copy_package")
    contentPackage: dict[str, Any] | None = Field(default=None, alias="content_package")
    copyGeneration: dict[str, Any] | None = Field(default=None, alias="copy_generation")
    visualAssetPlan: dict[str, Any] = Field(alias="visual_asset_plan")
    videoPlan: dict[str, Any] = Field(alias="video_plan")
    videoAssetPackagePlan: dict[str, Any] | None = Field(default=None, alias="video_asset_package_plan")
    review: dict[str, Any]
    execution: dict[str, Any]
    audit: dict[str, Any] | None = None


class ProductCommercializationVideoResponse(ProductCommercializationPreviewResponse):
    videoResult: dict[str, Any] | None = Field(default=None, alias="video_result")
    videoAssetPackage: dict[str, Any] | None = Field(default=None, alias="video_asset_package")


class Product3DRenderVideoRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    modelKey: str = Field(
        default="cup_1660",
        alias="model_key",
        description="3D 模型 key：cup_1660 / backpack_2551。",
    )
    textureImageUrl: str | None = Field(
        default=None,
        alias="texture_image_url",
        description="要贴到模型上的主图或花纹图 URL。预览可为空，但会降低可执行度。",
    )
    textureImageUrls: list[str] | None = Field(
        default=None,
        alias="texture_image_urls",
        description="可选多贴图 URL，后续用于多材质/多面贴图。",
    )
    textureSlots: list[dict[str, Any]] | None = Field(
        default=None,
        alias="texture_slots",
        description="按材质槽绑定的贴图清单：materialSlot/imageUrl/label。",
    )
    materialSlot: str | None = Field(default=None, alias="material_slot", description="目标材质槽；为空使用推荐槽。")
    cameraPreset: str = Field(default="orbit_360", alias="camera_preset", description="镜头预设。")
    cameraDistance: str = Field(default="wide", alias="camera_distance", description="镜头远近：wide/standard/close。")
    scenePreset: str = Field(default="clean_studio", alias="scene_preset", description="场景预设。")
    motionPath: list[dict[str, float]] | None = Field(
        default=None,
        alias="motion_path",
        description="兼容字段：镜头轨迹归一化坐标点列表，x/y 均为 0-1；至少 2 点，最多取前 12 点。商品保持固定，不表示商品位移。",
    )
    cameraPlan: dict[str, Any] | None = Field(
        default=None,
        alias="camera_plan",
        description="镜头方案。描述相机轨迹、焦点、是否已播放确认和商品固定约束；新接入优先使用该字段。",
    )
    durationSeconds: int = Field(default=6, ge=1, le=30, alias="duration_seconds", description="目标渲染视频秒数。")
    aspectRatio: str = Field(default="16:9", alias="aspect_ratio", description="目标画幅比例。")
    outputMode: str = Field(
        default="plan_only",
        alias="output_mode",
        description="输出模式。/preview 使用 plan_only；/runs 会强制使用 render_video 并返回统一业务 runId。",
    )
    extraPrompt: str | None = Field(
        default=None,
        alias="extra_prompt",
        description="内部渲染备注；不作为大模型提示词，不决定贴图槽或视频内容。",
    )
    requestId: str | None = Field(default=None, alias="request_id")
    traceId: str | None = Field(default=None, alias="trace_id")
    source: str | None = None


class Product3DRenderVideoPreviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    requestId: str = Field(alias="request_id")
    businessKey: str = Field(alias="business_key")
    version: str
    status: str
    generatedAt: str = Field(alias="generated_at")
    model: dict[str, Any]
    assetReadiness: dict[str, Any] = Field(alias="asset_readiness")
    renderPlan: dict[str, Any] = Field(alias="render_plan")
    review: dict[str, Any]
    execution: dict[str, Any]
    audit: dict[str, Any] | None = None


class Product3DRenderVideoCatalogResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    businessKey: str = Field(alias="business_key")
    version: str
    status: str
    generatedAt: str = Field(alias="generated_at")
    defaults: dict[str, Any]
    models: list[dict[str, Any]]
    scenePresets: list[dict[str, Any]] = Field(alias="scene_presets")
    sceneAssetSources: list[dict[str, Any]] = Field(alias="scene_asset_sources")
    cameraPresets: list[dict[str, Any]] = Field(alias="camera_presets")
    cameraDistances: list[dict[str, Any]] = Field(alias="camera_distances")
    durationOptions: list[int] = Field(alias="duration_options")
    aspectRatioOptions: list[str] = Field(alias="aspect_ratio_options")
    renderers: dict[str, Any]
    endpoints: dict[str, str]
    audit: dict[str, Any] | None = None


class BusinessProjectCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    scenario: str = "general"
    flowTemplateId: str | None = Field(default=None, alias="flow_template_id")
    currentFlowStepKey: str | None = Field(default=None, alias="current_flow_step_key")
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    metadata: dict[str, Any] | None = None


class BusinessProjectUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    scenario: str | None = None
    status: str | None = None
    flowTemplateId: str | None = Field(default=None, alias="flow_template_id")
    currentFlowStepKey: str | None = Field(default=None, alias="current_flow_step_key")
    metadata: dict[str, Any] | None = None


class BusinessProjectAssetCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assetType: str = Field(alias="asset_type")
    url: str | None = None
    contentType: str | None = Field(default=None, alias="content_type")
    fileName: str | None = Field(default=None, alias="file_name")
    flowStepKey: str | None = Field(default=None, alias="flow_step_key")
    inputTags: list[str] = Field(default_factory=list, alias="input_tags")
    issueTags: list[str] = Field(default_factory=list, alias="issue_tags")
    metadata: dict[str, Any] | None = None


class BusinessProjectAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    assetId: str = Field(alias="id")
    projectId: str = Field(alias="project_id")
    assetType: str = Field(alias="asset_type")
    url: str | None = None
    contentType: str | None = Field(default=None, alias="content_type")
    fileName: str | None = Field(default=None, alias="file_name")
    sourceRunId: str | None = Field(default=None, alias="source_run_id")
    sourceBusinessKey: str | None = Field(default=None, alias="source_business_key")
    sourceFlowStepKey: str | None = Field(default=None, alias="source_flow_step_key")
    sourceOutputIndex: int | None = Field(default=None, alias="source_output_index")
    qualityGrade: str | None = Field(default=None, alias="quality_grade")
    inputTags: list[str] = Field(default_factory=list, alias="input_tags")
    issueTags: list[str] = Field(default_factory=list, alias="issue_tags")
    selected: bool
    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessProjectRunLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    projectId: str = Field(alias="project_id")
    runId: str = Field(alias="run_id")
    businessKey: str = Field(alias="business_key")
    status: str | None = None
    flowStepKey: str | None = Field(default=None, alias="flow_step_key")
    flowStepName: str | None = Field(default=None, alias="flow_step_name")
    flowTemplateId: str | None = Field(default=None, alias="flow_template_id")
    inputAssetIds: list[str] = Field(default_factory=list, alias="input_asset_ids")
    outputAssetIds: list[str] = Field(default_factory=list, alias="output_asset_ids")
    clientRequestId: str | None = Field(default=None, alias="client_request_id")
    assetSyncStatus: str = Field(alias="asset_sync_status")
    assetSyncError: str | None = Field(default=None, alias="asset_sync_error")
    errorCode: str | None = Field(default=None, alias="error_code")
    errorMessage: str | None = Field(default=None, alias="error_message")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessProjectSelectionCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assetIds: list[str] = Field(default_factory=list, alias="asset_ids")
    assetId: str | None = Field(default=None, alias="asset_id")
    sourceFlowStepKey: str | None = Field(default=None, alias="source_flow_step_key")
    targetFlowStepKey: str | None = Field(default=None, alias="target_flow_step_key")
    note: str | None = None
    metadata: dict[str, Any] | None = None


class BusinessProjectSelectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    projectId: str = Field(alias="project_id")
    assetId: str = Field(alias="asset_id")
    sourceRunId: str | None = Field(default=None, alias="source_run_id")
    sourceFlowStepKey: str | None = Field(default=None, alias="source_flow_step_key")
    targetFlowStepKey: str | None = Field(default=None, alias="target_flow_step_key")
    selectedByUserId: str | None = Field(default=None, alias="selected_by_user_id")
    selectedByUserName: str | None = Field(default=None, alias="selected_by_user_name")
    note: str | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")
    createdAt: datetime = Field(alias="created_at")


class BusinessExportPackageCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assetIds: list[str] = Field(default_factory=list, alias="asset_ids")
    includeRunEvidence: bool = Field(default=True, alias="include_run_evidence")
    includeQualitySummary: bool = Field(default=True, alias="include_quality_summary")
    metadata: dict[str, Any] | None = None


class BusinessExportPackageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    packageId: str = Field(alias="id")
    projectId: str = Field(alias="project_id")
    status: str
    assetIds: list[str] = Field(default_factory=list, alias="asset_ids")
    runIds: list[str] = Field(default_factory=list, alias="run_ids")
    downloadUrl: str | None = Field(default=None, alias="download_url")
    manifest: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    errorCode: str | None = Field(default=None, alias="error_code")
    errorMessage: str | None = Field(default=None, alias="error_message")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    projectId: str = Field(alias="id")
    name: str
    scenario: str
    status: str
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    ownerUserId: str | None = Field(default=None, alias="owner_user_id")
    ownerUserName: str | None = Field(default=None, alias="owner_user_name")
    currentFlowStepKey: str | None = Field(default=None, alias="current_flow_step_key")
    flowTemplateId: str | None = Field(default=None, alias="flow_template_id")
    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")
    assetCount: int = Field(default=0, alias="asset_count")
    runCount: int = Field(default=0, alias="run_count")
    selectionCount: int = Field(default=0, alias="selection_count")
    exportPackageCount: int = Field(default=0, alias="export_package_count")
    latestRunStatus: str | None = Field(default=None, alias="latest_run_status")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessProjectListResponse(BaseModel):
    items: list[BusinessProjectRead]
    total: int


class BusinessProjectDetailResponse(BaseModel):
    project: BusinessProjectRead
    assets: list[BusinessProjectAssetRead] = Field(default_factory=list)
    runs: list[BusinessProjectRunLinkRead] = Field(default_factory=list)
    selections: list[BusinessProjectSelectionRead] = Field(default_factory=list)
    exportPackages: list[BusinessExportPackageRead] = Field(default_factory=list, alias="export_packages")


class BusinessProjectAssetListResponse(BaseModel):
    items: list[BusinessProjectAssetRead]
    total: int


class BusinessProjectRunLinkListResponse(BaseModel):
    items: list[BusinessProjectRunLinkRead]
    total: int


class BusinessRunCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: str | None = Field(default=None, description="指定业务版本；为空则使用默认启用版本")
    imageUrl: str | None = Field(default=None, description="主图 URL")
    url: str | None = Field(default=None, description="主图 URL 兼容字段")
    originalImageUrl: str | None = Field(default=None, description="原图 URL；裂变评分业务使用")
    generatedImageUrl: str | None = Field(default=None, description="生成图 URL；裂变评分业务使用")
    prompt: str | None = Field(default=None, description="业务提示词")
    editable_prompt: str | None = Field(default=None, description="文字强化文生图最终提示词；由用户确认后提交")
    editablePrompt: str | None = Field(default=None, description="文字强化文生图最终提示词；camelCase 兼容字段")
    editable_negative_prompt: str | None = Field(default=None, description="文字强化文生图反向提示词")
    editableNegativePrompt: str | None = Field(default=None, description="文字强化文生图反向提示词；camelCase 兼容字段")
    promptDraftId: str | None = Field(default=None, description="第一步 VL 提示词草稿 ID，用于链路追踪")
    prompt_draft_id: str | None = Field(default=None, description="第一步 VL 提示词草稿 ID；snake_case 兼容字段")
    route_decision: str | None = Field(default=None, description="文字强化裂变第一步返回的内部路线判断；可选兼容字段")
    routeDecision: str | None = Field(default=None, description="文字强化裂变第一步返回的内部路线判断；camelCase 兼容字段")
    text_items: list[dict[str, Any]] | None = Field(default=None, description="用户确认后的识别文字列表；可选")
    textItems: list[dict[str, Any]] | None = Field(default=None, description="用户确认后的识别文字列表；camelCase 兼容字段")
    context: dict[str, Any] | str | None = Field(default=None, description="业务上下文；裂变评分业务可传版本、提示词等信息")
    inputs: dict[str, Any] | None = Field(default=None, description="业务参数；不同业务能力字段不同")
    bili: float | str | None = Field(default=None, description="图裂变重绘幅度，0-100；值越大重绘越强、变化越明显。兼容 50% 这类百分比口径")
    width: int | None = Field(default=None, description="输出宽度")
    height: int | None = Field(default=None, description="输出高度")
    batch_size: int | None = Field(default=None, description="兼容旧字段；业务裂变接口固定单张输出，不按该字段扩图。")
    batch: int | None = Field(default=None, description="输出张数；花纹提取使用该字段")
    steps: int | None = Field(default=None, description="采样步数")
    cfg: float | None = Field(default=None, description="提示词控制强度")
    profile_id: str | None = Field(default=None, description="业务侧配置 ID")
    profile: str | None = Field(default=None, description="业务侧配置 ID；兼容 AI 团队接口包字段")
    mode: str | None = Field(default=None, description="业务执行模式；例如 fission")
    vl_result: dict[str, Any] | str | None = Field(default=None, description="上游 VL 控制卡 JSON；可由中台 VL 组件自动生成")
    variation_preset: str | None = Field(default=None, description="测评/业务侧参数预设名称；用于日志和排查")
    reference_lock: float | None = Field(default=None, description="原图结构保留度；映射到 IPAdapter 权重")
    color_lock: float | None = Field(default=None, description="颜色锁定强度；映射到 ColorMatch 强度")
    pattern_risk_type: str | None = Field(default=None, description="VL 识别出的图案风险类型；通常由中台自动生成")
    ipadapter_weight: float | None = Field(default=None, description="参考图约束权重")
    colormatch_method: str | None = Field(default=None, description="颜色匹配方式")
    colormatch_strength: float | None = Field(default=None, description="颜色匹配强度")
    image_desc: str | None = Field(default=None, description="图片描述，可由 VL 分析结果填入")
    variation_strength: str | None = Field(default=None, description="GPT Image 2 裂变幅度：conservative / same_series / creative_same_series")
    quality: str | None = Field(default=None, description="商业模型质量档位：preview / candidate / premium")
    count: int | None = Field(default=None, description="兼容旧字段；GPT Image 2 业务版固定单次输出 1 张")
    preserve_layout: bool | None = Field(default=None, description="兼容旧字段；当前由中台内部默认策略控制")
    preserve_border: str | None = Field(default=None, description="兼容旧字段；当前由中台内部默认策略控制")
    preserve_count_density: bool | None = Field(default=None, description="兼容旧字段；当前由中台内部默认策略控制")
    style_shift: str | None = Field(default=None, description="兼容旧字段；当前由中台内部默认策略控制")
    size: str | None = Field(default=None, description="商业模型输出尺寸；GPT Image 2 默认 auto")
    output_format: str | None = Field(default=None, description="商业模型输出格式；默认 png")
    outputFormat: str | None = Field(default=None, description="商业模型输出格式；camelCase 兼容字段")
    productType: str | None = Field(default=None, description="产品设计品类；camelCase 字段")
    product_type: str | None = Field(default=None, description="产品设计品类；snake_case 字段")
    designBrief: str | None = Field(default=None, description="产品设计要求；camelCase 字段")
    design_brief: str | None = Field(default=None, description="产品设计要求；snake_case 字段")
    scene: str | None = Field(default=None, description="产品设计展示场景")
    clientContextId: str | None = Field(default=None, description="客户端调用上下文 ID；用于跨能力链路回溯和排查", alias="client_context_id")
    maskUrl: str | None = Field(default=None, description="可选蒙版 URL；用于 OpenAI 图片编辑")
    mask_url: str | None = Field(default=None, description="可选蒙版 URL；snake_case 兼容字段")
    editSkill: str | None = Field(default=None, description="图编辑技能：局部修改、参考图替换、删除修补、补色校正、扩展画布")
    edit_skill: str | None = Field(default=None, description="图编辑技能；snake_case 兼容字段")
    instruction: str | None = Field(default=None, description="图编辑用户编辑指令")
    selectionHints: list[dict[str, Any]] | dict[str, Any] | str | None = Field(default=None, description="点选/框选/圆选/手绘区域提示")
    selection_hints: list[dict[str, Any]] | dict[str, Any] | str | None = Field(default=None, description="点选/框选/圆选/手绘区域提示；snake_case 兼容字段")
    referenceImages: list[dict[str, Any]] | list[str] | dict[str, Any] | str | None = Field(default=None, description="图编辑参考图列表")
    reference_images: list[dict[str, Any]] | list[str] | dict[str, Any] | str | None = Field(default=None, description="图编辑参考图列表；snake_case 兼容字段")
    maskMeta: dict[str, Any] | None = Field(default=None, description="蒙版元信息，如画布尺寸、羽化、来源")
    mask_meta: dict[str, Any] | None = Field(default=None, description="蒙版元信息；snake_case 兼容字段")
    targetWidth: int | None = Field(default=None, description="图编辑扩展画布目标宽度；camelCase 字段")
    target_width: int | None = Field(default=None, description="图编辑扩展画布目标宽度；snake_case 字段")
    targetHeight: int | None = Field(default=None, description="图编辑扩展画布目标高度；camelCase 字段")
    target_height: int | None = Field(default=None, description="图编辑扩展画布目标高度；snake_case 字段")
    placementX: int | None = Field(default=None, description="原图放入扩展画布的左上角 X 坐标；camelCase 字段")
    placement_x: int | None = Field(default=None, description="原图放入扩展画布的左上角 X 坐标；snake_case 字段")
    placementY: int | None = Field(default=None, description="原图放入扩展画布的左上角 Y 坐标；camelCase 字段")
    placement_y: int | None = Field(default=None, description="原图放入扩展画布的左上角 Y 坐标；snake_case 字段")
    anchor: str | None = Field(default=None, description="扩展画布锚点：center/left/right/top/bottom/top_left/top_right/bottom_left/bottom_right/custom")
    preserveOriginal: bool | None = Field(default=None, description="扩展画布时是否尽量保持原图区域不变；camelCase 字段")
    preserve_original: bool | None = Field(default=None, description="扩展画布时是否尽量保持原图区域不变；snake_case 字段")
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
    projectId: str | None = Field(default=None, description="兼容调用上下文 ID；历史字段 projectId，仅用于旧链路回溯", alias="project_id")
    flowStepKey: str | None = Field(default=None, description="客户端声明的业务步骤 key", alias="flow_step_key")
    flowStepName: str | None = Field(default=None, description="客户端声明的业务步骤名称", alias="flow_step_name")
    flowTemplateId: str | None = Field(default=None, description="客户端业务模板 ID", alias="flow_template_id")
    inputAssetIds: list[str] | None = Field(default=None, description="输入资产证据 ID 列表；兼容旧链路使用", alias="input_asset_ids")
    clientRequestId: str | None = Field(default=None, description="客户端请求 ID，用于幂等排查和日志关联", alias="client_request_id")


class BusinessAgentSessionCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    agentKey: str = Field(default="agent.image_edit_assistant", alias="agent_key")
    imageUrl: str | None = Field(default=None, alias="image_url", description="会话主图 URL")
    message: str | None = Field(default=None, description="可选首轮用户消息；传入后会直接生成方案卡片")
    editSkill: str | None = Field(default=None, alias="edit_skill")
    quality: str | None = None
    size: str | None = None
    outputFormat: str | None = Field(default=None, alias="output_format")
    maskUrl: str | None = Field(default=None, alias="mask_url")
    referenceImages: list[dict[str, Any]] | list[str] | None = Field(default=None, alias="reference_images")
    selectionHints: list[dict[str, Any]] | None = Field(default=None, alias="selection_hints")
    title: str | None = None
    context: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    source: str | None = Field(default=None, description="调用来源，例如 eval / client")
    channel: str | None = None
    traceId: str | None = Field(default=None, alias="trace_id")
    requestId: str | None = Field(default=None, alias="request_id")
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    projectId: str | None = Field(default=None, alias="project_id")


class BusinessAgentMessageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str
    imageUrl: str | None = Field(default=None, alias="image_url")
    editSkill: str | None = Field(default=None, alias="edit_skill")
    quality: str | None = None
    size: str | None = None
    outputFormat: str | None = Field(default=None, alias="output_format")
    maskUrl: str | None = Field(default=None, alias="mask_url")
    referenceImages: list[dict[str, Any]] | list[str] | None = Field(default=None, alias="reference_images")
    selectionHints: list[dict[str, Any]] | None = Field(default=None, alias="selection_hints")
    context: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    requestId: str | None = Field(default=None, alias="request_id")


class BusinessAgentConfirmRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    planId: str | None = Field(default=None, alias="plan_id")
    overrides: dict[str, Any] | None = None
    callbackUrl: str | None = Field(default=None, alias="callback_url")
    callbackHeaders: dict[str, str] | None = Field(default=None, alias="callback_headers")
    requestId: str | None = Field(default=None, alias="request_id")


class BusinessAgentMessageRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    sessionId: str = Field(alias="session_id")
    role: str
    content: str | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    planId: str | None = Field(default=None, alias="plan_id")
    runId: str | None = Field(default=None, alias="run_id")
    requestId: str | None = Field(default=None, alias="request_id")
    metadata: dict[str, Any] | None = None
    createdAt: datetime = Field(alias="created_at")


class BusinessAgentPlanRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    sessionId: str = Field(alias="session_id")
    agentKey: str = Field(alias="agent_key")
    status: str
    intent: str
    title: str | None = None
    summary: str | None = None
    editPlan: list[dict[str, Any]] = Field(default_factory=list, alias="edit_plan")
    toolName: str = Field(alias="tool_name")
    toolPayload: dict[str, Any] = Field(default_factory=dict, alias="tool_payload")
    estimatedCostLevel: str | None = Field(default=None, alias="estimated_cost_level")
    riskLevel: str | None = Field(default=None, alias="risk_level")
    confirmationRequired: bool = Field(alias="confirmation_required")
    plannerModel: str | None = Field(default=None, alias="planner_model")
    plannerMode: str | None = Field(default=None, alias="planner_mode")
    warnings: list[str] = Field(default_factory=list)
    routeEvidence: dict[str, Any] = Field(default_factory=dict, alias="route_evidence")
    workingMemory: dict[str, Any] = Field(default_factory=dict, alias="working_memory")
    assetState: dict[str, Any] = Field(default_factory=dict, alias="asset_state")
    methodology: dict[str, Any] = Field(default_factory=dict)
    baseImageRole: str | None = Field(default=None, alias="base_image_role")
    parentRunId: str | None = Field(default=None, alias="parent_run_id")
    errorCode: str | None = Field(default=None, alias="error_code")
    errorMessage: str | None = Field(default=None, alias="error_message")
    confirmedAt: datetime | None = Field(default=None, alias="confirmed_at")
    executedAt: datetime | None = Field(default=None, alias="executed_at")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessAgentToolCallRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    sessionId: str = Field(alias="session_id")
    planId: str = Field(alias="plan_id")
    toolName: str = Field(alias="tool_name")
    businessKey: str | None = Field(default=None, alias="business_key")
    runId: str | None = Field(default=None, alias="run_id")
    status: str
    requestPayload: dict[str, Any] | None = Field(default=None, alias="request_payload")
    responsePayload: dict[str, Any] | None = Field(default=None, alias="response_payload")
    errorCode: str | None = Field(default=None, alias="error_code")
    errorMessage: str | None = Field(default=None, alias="error_message")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessAgentSessionRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    agentKey: str = Field(alias="agent_key")
    status: str
    title: str | None = None
    imageUrl: str | None = Field(default=None, alias="image_url")
    latestPlanId: str | None = Field(default=None, alias="latest_plan_id")
    latestRunId: str | None = Field(default=None, alias="latest_run_id")
    traceId: str | None = Field(default=None, alias="trace_id")
    requestId: str | None = Field(default=None, alias="request_id")
    tenantId: str | None = Field(default=None, alias="tenant_id")
    clientId: str | None = Field(default=None, alias="client_id")
    userId: str | None = Field(default=None, alias="user_id")
    userName: str | None = Field(default=None, alias="user_name")
    context: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    messages: list[BusinessAgentMessageRead] = Field(default_factory=list)
    plans: list[BusinessAgentPlanRead] = Field(default_factory=list)
    toolCalls: list[BusinessAgentToolCallRead] = Field(default_factory=list, alias="tool_calls")
    latestPlan: BusinessAgentPlanRead | None = Field(default=None, alias="latest_plan")
    latestToolCall: BusinessAgentToolCallRead | None = Field(default=None, alias="latest_tool_call")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessAgentSessionResponse(BaseModel):
    session: BusinessAgentSessionRead


class BusinessAgentPlanResponse(BaseModel):
    session: BusinessAgentSessionRead
    plan: BusinessAgentPlanRead


class BusinessAgentConfirmResponse(BaseModel):
    session: BusinessAgentSessionRead
    plan: BusinessAgentPlanRead
    toolCall: BusinessAgentToolCallRead = Field(alias="tool_call")
    run: dict[str, Any]


class TextFissionPromptRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    imageUrl: str | None = Field(default=None, description="原图 URL")
    url: str | None = Field(default=None, description="原图 URL 兼容字段")
    provider: str | None = Field(default=None, description="VL 模型来源，默认使用中台配置的 Doubao VL")
    prompt: str | None = Field(default=None, description="可选补充说明；默认按系统提示词生成可编辑提示词")
    source: str | None = Field(default=None, description="调用来源，例如 eval、partner-api")
    channel: str | None = Field(default=None, description="业务渠道")
    traceId: str | None = Field(default=None, description="调用链路 ID")
    requestId: str | None = Field(default=None, description="业务方请求 ID")
    tenantId: str | None = Field(default=None, description="租户/业务方 ID")
    clientId: str | None = Field(default=None, description="客户端/应用 ID")
    metadata: dict[str, Any] | None = Field(default=None, description="调用上下文")


class TextFissionPromptResponse(BaseModel):
    promptDraftId: str
    status: str
    imageUrl: str
    editablePrompt: str
    editablePromptCn: str | None = None
    editableNegativePrompt: str | None = None
    editableNegativePromptCn: str | None = None
    textContent: str | None = None
    textItems: list[dict[str, Any]] = Field(default_factory=list)
    routeDecision: str | None = None
    routeReason: str | None = None
    canUseText2Img: bool | None = None
    textCount: int | None = None
    promptProfile: str | None = None
    layoutCard: dict[str, Any] | str | None = None
    paletteCard: dict[str, Any] | str | None = None
    riskNotes: list[Any] | str | None = None
    vlResult: dict[str, Any]
    traceId: str | None = None


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
    traceSummary: dict[str, Any] | None = Field(default=None, alias="trace_summary")
    agentTrace: dict[str, Any] | None = Field(default=None, alias="agent_trace")
    apiUsage: dict[str, Any] | None = Field(default=None, alias="api_usage")
    orchestrationGraph: dict[str, Any] | None = Field(default=None, alias="orchestration_graph")
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


class BusinessOutputReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    runId: str = Field(alias="run_id")
    businessKey: str = Field(alias="business_key")
    businessVersionId: str | None = Field(default=None, alias="business_version_id")
    version: str | None = None
    outputIndex: int = Field(alias="output_index")
    outputUrl: str | None = Field(default=None, alias="output_url")
    sampleKey: str | None = Field(default=None, alias="sample_key")
    sampleLabel: str | None = Field(default=None, alias="sample_label")
    batchId: str | None = Field(default=None, alias="batch_id")
    qualityGrade: str = Field(alias="quality_grade")
    inputTags: list[str] = Field(default_factory=list, alias="input_tags")
    issueTags: list[str] = Field(default_factory=list, alias="issue_tags")
    nextAction: str | None = Field(default=None, alias="next_action")
    note: str | None = None
    reviewerUserId: str | None = Field(default=None, alias="reviewer_user_id")
    reviewerUsername: str | None = Field(default=None, alias="reviewer_username")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessOutputReviewUpsertItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    outputIndex: int = Field(ge=0, alias="output_index")
    outputUrl: str | None = Field(default=None, alias="output_url")
    sampleKey: str | None = Field(default=None, alias="sample_key")
    sampleLabel: str | None = Field(default=None, alias="sample_label")
    batchId: str | None = Field(default=None, alias="batch_id")
    qualityGrade: str = Field(default="pending", alias="quality_grade")
    inputTags: list[str] = Field(default_factory=list, alias="input_tags")
    issueTags: list[str] = Field(default_factory=list, alias="issue_tags")
    nextAction: str | None = Field(default=None, alias="next_action")
    note: str | None = None


class BusinessOutputReviewUpsertRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[BusinessOutputReviewUpsertItem] = Field(default_factory=list)


class BusinessOutputReviewListResponse(BaseModel):
    total: int
    items: list[BusinessOutputReviewRead]


class BusinessOutputReviewBucket(BaseModel):
    key: str
    label: str
    total: int
    sampleReviews: list[BusinessOutputReviewRead] = Field(default_factory=list, alias="sample_reviews")


class BusinessOutputReviewBusinessSummary(BaseModel):
    businessKey: str = Field(alias="business_key")
    label: str
    total: int
    reviewed: int
    excellent: int = 0
    usable: int = 0
    borderline: int = 0
    bad: int = 0
    blocked: int = 0
    pending: int = 0
    latestAt: datetime | None = Field(default=None, alias="latest_at")
    topIssueTags: list[BusinessOutputReviewBucket] = Field(default_factory=list, alias="top_issue_tags")
    topInputTags: list[BusinessOutputReviewBucket] = Field(default_factory=list, alias="top_input_tags")


class BusinessOutputReviewVersionSummary(BaseModel):
    businessKey: str = Field(alias="business_key")
    businessVersionId: str | None = Field(default=None, alias="business_version_id")
    version: str | None = None
    label: str
    total: int
    reviewed: int
    excellent: int = 0
    usable: int = 0
    borderline: int = 0
    bad: int = 0
    blocked: int = 0
    pending: int = 0
    latestAt: datetime | None = Field(default=None, alias="latest_at")
    topIssueTags: list[BusinessOutputReviewBucket] = Field(default_factory=list, alias="top_issue_tags")
    topInputTags: list[BusinessOutputReviewBucket] = Field(default_factory=list, alias="top_input_tags")


class BusinessOutputReviewBatchVersionSummary(BaseModel):
    businessVersionId: str | None = Field(default=None, alias="business_version_id")
    version: str | None = None
    label: str
    total: int
    reviewed: int
    good: int = 0
    risk: int = 0
    latestAt: datetime | None = Field(default=None, alias="latest_at")
    sampleReviews: list[BusinessOutputReviewRead] = Field(default_factory=list, alias="sample_reviews")


class BusinessOutputReviewBatchSummary(BaseModel):
    batchId: str = Field(alias="batch_id")
    businessKey: str = Field(alias="business_key")
    sampleKey: str | None = Field(default=None, alias="sample_key")
    sampleLabel: str | None = Field(default=None, alias="sample_label")
    label: str
    total: int
    reviewed: int
    good: int = 0
    risk: int = 0
    latestAt: datetime | None = Field(default=None, alias="latest_at")
    versions: list[BusinessOutputReviewBatchVersionSummary] = Field(default_factory=list)
    topIssueTags: list[BusinessOutputReviewBucket] = Field(default_factory=list, alias="top_issue_tags")
    topInputTags: list[BusinessOutputReviewBucket] = Field(default_factory=list, alias="top_input_tags")
    sampleReviews: list[BusinessOutputReviewRead] = Field(default_factory=list, alias="sample_reviews")


class BusinessOutputReviewSummaryResponse(BaseModel):
    windowHours: int = Field(alias="window_hours")
    filters: dict[str, Any]
    total: int
    byGrade: list[BusinessOutputReviewBucket] = Field(default_factory=list, alias="by_grade")
    byBusiness: list[BusinessOutputReviewBusinessSummary] = Field(default_factory=list, alias="by_business")
    byVersion: list[BusinessOutputReviewVersionSummary] = Field(default_factory=list, alias="by_version")
    byBatch: list[BusinessOutputReviewBatchSummary] = Field(default_factory=list, alias="by_batch")
    topIssueTags: list[BusinessOutputReviewBucket] = Field(default_factory=list, alias="top_issue_tags")
    topInputTags: list[BusinessOutputReviewBucket] = Field(default_factory=list, alias="top_input_tags")
    recentReviews: list[BusinessOutputReviewRead] = Field(default_factory=list, alias="recent_reviews")


class BusinessQualitySampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    businessKey: str = Field(alias="business_key")
    sampleKey: str = Field(alias="sample_key")
    label: str | None = None
    description: str | None = None
    imageUrl: str | None = Field(default=None, alias="image_url")
    prompt: str | None = None
    generatedImageUrl: str | None = Field(default=None, alias="generated_image_url")
    inputTags: list[str] = Field(default_factory=list, alias="input_tags")
    defaultParams: dict[str, Any] = Field(default_factory=dict, alias="default_params")
    status: str
    sortOrder: int = Field(alias="sort_order")
    createdByUserId: str | None = Field(default=None, alias="created_by_user_id")
    createdByUsername: str | None = Field(default=None, alias="created_by_username")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessQualitySampleCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    businessKey: str = Field(alias="business_key")
    sampleKey: str | None = Field(default=None, alias="sample_key")
    label: str
    description: str | None = None
    imageUrl: str = Field(alias="image_url")
    prompt: str | None = None
    generatedImageUrl: str | None = Field(default=None, alias="generated_image_url")
    inputTags: list[str] = Field(default_factory=list, alias="input_tags")
    defaultParams: dict[str, Any] = Field(default_factory=dict, alias="default_params")
    status: str = "active"
    sortOrder: int = Field(default=0, alias="sort_order")
    changeNote: str | None = Field(default=None, alias="change_note")


class BusinessQualitySampleUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sampleKey: str | None = Field(default=None, alias="sample_key")
    label: str | None = None
    description: str | None = None
    imageUrl: str | None = Field(default=None, alias="image_url")
    prompt: str | None = None
    generatedImageUrl: str | None = Field(default=None, alias="generated_image_url")
    inputTags: list[str] | None = Field(default=None, alias="input_tags")
    defaultParams: dict[str, Any] | None = Field(default=None, alias="default_params")
    status: str | None = None
    sortOrder: int | None = Field(default=None, alias="sort_order")
    changeNote: str | None = Field(default=None, alias="change_note")


class BusinessQualitySampleListResponse(BaseModel):
    total: int
    items: list[BusinessQualitySampleRead]


class BusinessQualitySampleImportItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    businessKey: str | None = Field(default=None, alias="business_key")
    sampleKey: str | None = Field(default=None, alias="sample_key")
    label: str
    description: str | None = None
    imageUrl: str = Field(alias="image_url")
    prompt: str | None = None
    generatedImageUrl: str | None = Field(default=None, alias="generated_image_url")
    inputTags: list[str] = Field(default_factory=list, alias="input_tags")
    defaultParams: dict[str, Any] = Field(default_factory=dict, alias="default_params")
    status: str = "active"
    sortOrder: int = Field(default=0, alias="sort_order")
    changeNote: str | None = Field(default=None, alias="change_note")


class BusinessQualitySampleImportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    businessKey: str | None = Field(default=None, alias="business_key")
    items: list[BusinessQualitySampleImportItem] = Field(default_factory=list)
    dryRun: bool = Field(default=False, alias="dry_run")
    changeNote: str | None = Field(default=None, alias="change_note")


class BusinessQualitySampleImportResult(BaseModel):
    index: int
    action: str
    sampleId: str | None = Field(default=None, alias="sample_id")
    businessKey: str | None = Field(default=None, alias="business_key")
    sampleKey: str | None = Field(default=None, alias="sample_key")
    label: str | None = None
    errorCode: str | None = Field(default=None, alias="error_code")
    message: str | None = None


class BusinessQualitySampleImportResponse(BaseModel):
    total: int
    created: int
    updated: int
    skipped: int
    failed: int
    dryRun: bool = Field(alias="dry_run")
    items: list[BusinessQualitySampleImportResult]


class BusinessQualitySampleVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    sampleId: str = Field(alias="sample_id")
    businessKey: str = Field(alias="business_key")
    sampleKey: str = Field(alias="sample_key")
    label: str
    description: str | None = None
    imageUrl: str = Field(alias="image_url")
    prompt: str | None = None
    generatedImageUrl: str | None = Field(default=None, alias="generated_image_url")
    inputTags: list[str] = Field(default_factory=list, alias="input_tags")
    defaultParams: dict[str, Any] = Field(default_factory=dict, alias="default_params")
    status: str
    sortOrder: int = Field(alias="sort_order")
    changeType: str = Field(alias="change_type")
    changeNote: str | None = Field(default=None, alias="change_note")
    versionNo: int = Field(alias="version_no")
    actorUserId: str | None = Field(default=None, alias="actor_user_id")
    actorUsername: str | None = Field(default=None, alias="actor_username")
    createdAt: datetime = Field(alias="created_at")


class BusinessQualitySampleVersionListResponse(BaseModel):
    total: int
    items: list[BusinessQualitySampleVersionRead]


class BusinessQualityActionRuleTarget(BaseModel):
    id: str
    version: str | None = None
    displayName: str | None = Field(default=None, alias="display_name")
    status: str | None = None
    isDefault: bool | None = Field(default=None, alias="is_default")


class BusinessQualityActionRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    businessKey: str = Field(alias="business_key")
    ruleKey: str = Field(alias="rule_key")
    title: str
    description: str | None = None
    issueTags: list[str] = Field(default_factory=list, alias="issue_tags")
    inputTags: list[str] = Field(default_factory=list, alias="input_tags")
    actionType: str = Field(alias="action_type")
    targetBusinessVersionId: str | None = Field(default=None, alias="target_business_version_id")
    targetVersion: str | None = Field(default=None, alias="target_version")
    targetLabel: str | None = Field(default=None, alias="target_label")
    targetRef: str | None = Field(default=None, alias="target_ref")
    targetParams: dict[str, Any] = Field(default_factory=dict, alias="target_params")
    targetCapability: BusinessQualityActionRuleTarget | None = Field(default=None, alias="target_capability")
    sampleBatchId: str | None = Field(default=None, alias="sample_batch_id")
    evidenceReviewIds: list[str] = Field(default_factory=list, alias="evidence_review_ids")
    status: str
    priority: int
    ownerUserId: str | None = Field(default=None, alias="owner_user_id")
    ownerUsername: str | None = Field(default=None, alias="owner_username")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")


class BusinessQualityActionRuleCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    businessKey: str = Field(alias="business_key")
    ruleKey: str | None = Field(default=None, alias="rule_key")
    title: str
    description: str | None = None
    issueTags: list[str] = Field(default_factory=list, alias="issue_tags")
    inputTags: list[str] = Field(default_factory=list, alias="input_tags")
    actionType: str = Field(default="watch_only", alias="action_type")
    targetBusinessVersionId: str | None = Field(default=None, alias="target_business_version_id")
    targetRef: str | None = Field(default=None, alias="target_ref")
    targetParams: dict[str, Any] = Field(default_factory=dict, alias="target_params")
    sampleBatchId: str | None = Field(default=None, alias="sample_batch_id")
    evidenceReviewIds: list[str] = Field(default_factory=list, alias="evidence_review_ids")
    status: str = "candidate"
    priority: int = 0


class BusinessQualityActionRuleUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ruleKey: str | None = Field(default=None, alias="rule_key")
    title: str | None = None
    description: str | None = None
    issueTags: list[str] | None = Field(default=None, alias="issue_tags")
    inputTags: list[str] | None = Field(default=None, alias="input_tags")
    actionType: str | None = Field(default=None, alias="action_type")
    targetBusinessVersionId: str | None = Field(default=None, alias="target_business_version_id")
    targetRef: str | None = Field(default=None, alias="target_ref")
    targetParams: dict[str, Any] | None = Field(default=None, alias="target_params")
    sampleBatchId: str | None = Field(default=None, alias="sample_batch_id")
    evidenceReviewIds: list[str] | None = Field(default=None, alias="evidence_review_ids")
    status: str | None = None
    priority: int | None = None


class BusinessQualityActionRuleListResponse(BaseModel):
    total: int
    items: list[BusinessQualityActionRuleRead]


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


class BusinessFlowEvidenceBucket(BaseModel):
    key: str
    label: str
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    running: int = 0
    queued: int = 0
    cancelled: int = 0
    successRate: float | None = Field(default=None, alias="success_rate")
    avgDurationMs: int | None = Field(default=None, alias="avg_duration_ms")
    p95DurationMs: int | None = Field(default=None, alias="p95_duration_ms")
    latestAt: datetime | None = Field(default=None, alias="latest_at")
    evidence: dict[str, Any] = Field(default_factory=dict)


class BusinessFlowEvidenceResponse(BaseModel):
    stageEvidence: list[BusinessFlowEvidenceBucket] = Field(default_factory=list, alias="stage_evidence")
    routeHits: list[BusinessFlowEvidenceBucket] = Field(default_factory=list, alias="route_hits")
    candidateHits: list[BusinessFlowEvidenceBucket] = Field(default_factory=list, alias="candidate_hits")
    loraHits: list[BusinessFlowEvidenceBucket] = Field(default_factory=list, alias="lora_hits")
    workflowHits: list[BusinessFlowEvidenceBucket] = Field(default_factory=list, alias="workflow_hits")


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
    unresolvedByBusiness: list[BusinessIssueBucket] = Field(default_factory=list, alias="unresolved_by_business")
    recentUnresolvedIssues: list[BusinessUnresolvedIssueItem] = Field(default_factory=list, alias="recent_unresolved_issues")
    recentFailures: list[BusinessUsageFailure] = Field(default_factory=list, alias="recent_failures")
    flowEvidence: BusinessFlowEvidenceResponse | None = Field(default=None, alias="flow_evidence")
