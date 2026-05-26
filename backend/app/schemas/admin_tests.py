"""Schemas for admin-side integration tests."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BaiduImageOperation(str, Enum):
    quality_upgrade = "quality_upgrade"
    colourize = "colourize"
    remove_moire = "remove_moire"
    stretch_restore = "stretch_restore"
    dehaze = "dehaze"
    contrast_enhance = "contrast_enhance"
    denoise = "denoise"


class AbilityTestContext(BaseModel):
    abilityId: str | None = Field(default=None, description="Optional ability ID for logging/tracing")
    abilityName: str | None = Field(default=None, description="Friendly name of the ability")
    abilityProvider: str | None = Field(default=None, description="Provider hint for logging fallback")
    capabilityKey: str | None = Field(default=None, description="Capability key for logging fallback")


class BaiduImageProcessTestRequest(AbilityTestContext):
    executorId: str = Field(..., description="Executor ID configured with type=baidu")
    operation: BaiduImageOperation = Field(default=BaiduImageOperation.quality_upgrade)
    imageBase64: str | None = Field(None, description="Base64 encoded image data")
    imageUrl: str | None = Field(None, description="Fallback image URL if base64 not provided")
    params: dict[str, Any] | None = Field(default=None, description="Extra parameters that override defaults")


class BaiduImageProcessTestResponse(BaseModel):
    provider: str
    logId: int | None = None
    resultImage: str
    raw: dict[str, Any] | None = None


class BaiduQualityUpgradeTestRequest(AbilityTestContext):
    executorId: str = Field(..., description="Executor ID configured with type=baidu")
    imageBase64: str | None = Field(None, description="Base64 encoded image data")
    imageUrl: str | None = Field(None, description="Fallback image URL if base64 not provided")
    resolution: str = Field("2k", description="Target resolution, e.g., 2k/4k")
    upscaleType: str | None = Field("auto", description="Baidu quality_upgrade type parameter")


class BaiduQualityUpgradeTestResponse(BaiduImageProcessTestResponse):
    """Backward compatible alias of BaiduImageProcessTestResponse."""


class VolcengineChatTestRequest(AbilityTestContext):
    executorId: str = Field(..., description="Executor ID configured with type=volcengine")
    model: str
    prompt: str
    imageUrl: str | None = Field(
        default=None, description="Optional image URL when the chat model supports visual input"
    )
    params: dict[str, Any] | None = None


class VolcengineChatTestResponse(BaseModel):
    provider: str
    model: str
    text: str
    logId: int | None = None
    raw: dict[str, Any] | None = None


class VolcengineImageTestRequest(AbilityTestContext):
    executorId: str = Field(..., description="Executor ID configured with type=volcengine")
    model: str
    prompt: str
    negativePrompt: str | None = None
    size: str | None = None
    responseFormat: str | None = None
    params: dict[str, Any] | None = None


class VolcengineImageTestResponse(BaseModel):
    provider: str
    model: str
    logId: int | None = None
    imageUrl: str | None = None
    imageBase64: str | None = None
    storedUrl: str | None = None
    assets: list["StoredAsset"] | None = None
    raw: dict[str, Any] | None = None


class StoredAsset(BaseModel):
    ossUrl: str
    ossKey: str
    sourceUrl: str | None = None
    contentType: str | None = None
    size: int | None = None
    tag: str | None = None


class KieMarketTestRequest(AbilityTestContext):
    executorId: str = Field(..., description="Executor ID configured with type=kie")
    model: str = Field(..., description="模型 ID，例如 nano-banana-pro")
    endpoint: str | None = Field("/api/v1/jobs/createTask", description="KIE API 路径")
    callBackUrl: str | None = Field(default=None, description="可选回调 URL")
    input: dict[str, Any] = Field(..., description="input 对象，包含 prompt/参数/URL 等")
    extra: dict[str, Any] | None = Field(default=None, description="附加顶层字段，如扩展参数")
    pollTimeout: float | None = Field(default=75.0, description="最长轮询秒数，默认 75s")


class KieMarketTestResponse(BaseModel):
    provider: str
    model: str
    logId: int | None = None
    taskId: str
    state: str | None = None
    resultUrls: list[str] | None = None
    resultObject: dict[str, Any] | None = None
    storedAssets: list[StoredAsset] | None = None
    raw: dict[str, Any] | None = None


class ComfyuiWorkflowTestRequest(AbilityTestContext):
    executorId: str = Field(..., description="Executor ID configured with type=comfyui")
    workflowKey: str = Field(..., description="内置 workflow key，例如 sifang_lianxu")
    workflowParams: dict[str, Any] = Field(default_factory=dict, description="与任务提交时 workflowParams 一致")
    submitOnly: bool | None = Field(default=False, description="仅提交任务进入队列，不等待结果")


class ComfyuiWorkflowTestResponse(BaseModel):
    provider: str
    workflowKey: str
    promptId: str
    state: str | None = None
    logId: int | None = None
    storedUrl: str | None = None
    assets: list[StoredAsset] | None = None
    raw: dict[str, Any] | None = None


class ComfyuiModelCatalogResponse(BaseModel):
    executorId: str
    baseUrl: str
    models: dict[str, list[str]]
    nodeKeys: list[str] | None = None
    nodeCount: int | None = None


class ComfyuiRouteEvidence(BaseModel):
    recentTotal: int | None = None
    recentQueued: int | None = None
    recentRunning: int | None = None
    recentSucceeded: int | None = None
    recentFailed: int | None = None
    recentCancelled: int | None = None
    recentOther: int | None = None
    latestTaskId: str | None = None
    latestStatus: str | None = None
    latestTaskAt: str | None = None


class ComfyuiQueueStatusResponse(BaseModel):
    executorId: str
    baseUrl: str
    executorName: str | None = None
    executorStatus: str | None = None
    maxConcurrency: int | None = None
    tags: list[str] | None = None
    runningCount: int
    pendingCount: int
    totalCount: int | None = None
    queueMaxSize: int | None = None
    capacityTarget: int | None = None
    idleSlots: int | None = None
    utilization: float | None = None
    saturation: str | None = None
    diagnosisLevel: str | None = None
    diagnosis: str | None = None
    backendQueued: int | None = None
    backendRunning: int | None = None
    backendActive: int | None = None
    backendOldestQueuedAt: str | None = None
    backendOldestRunningAt: str | None = None
    backendOldestRunningAgeSeconds: int | None = None
    feedCode: str | None = None
    feedDiagnosisLevel: str | None = None
    feedDiagnosis: str | None = None
    feedAction: str | None = None
    routeEvidence: ComfyuiRouteEvidence | None = None
    routeDiagnosisLevel: str | None = None
    routeDiagnosis: str | None = None
    supported: bool = True
    message: str | None = None
    raw: dict[str, Any] | None = None


class ComfyuiQueueDiagnostic(BaseModel):
    level: str
    code: str
    message: str


class ComfyuiQueueSummaryResponse(BaseModel):
    totalRunning: int
    totalPending: int
    totalCount: int
    totalCapacity: int | None = None
    totalIdleSlots: int | None = None
    utilization: float | None = None
    backendQueuedTotal: int | None = None
    backendRunningTotal: int | None = None
    backendActiveTotal: int | None = None
    supportedServers: int | None = None
    unsupportedServers: int | None = None
    saturatedServers: int | None = None
    idleServers: int | None = None
    feedGapServers: int | None = None
    backendBlockedServers: int | None = None
    backendRunningInvisibleServers: int | None = None
    backendRunningSettlingServers: int | None = None
    backendRunningStaleGraceSeconds: int | None = None
    routeEvidenceWindowHours: int | None = None
    routeEvidenceTotal: int | None = None
    routeEvidenceCoveredServers: int | None = None
    recentRouteMissingServers: int | None = None
    diagnostics: list[ComfyuiQueueDiagnostic] | None = None
    timestamp: str | None = None
    servers: list[ComfyuiQueueStatusResponse]


class ComfyuiWorkflowCompatibilityDiagnostic(BaseModel):
    level: str
    code: str
    message: str


class ComfyuiWorkflowMissingNode(BaseModel):
    nodeId: str
    classType: str


class ComfyuiWorkflowMissingModel(BaseModel):
    nodeId: str
    classType: str
    inputName: str
    value: str


class ComfyuiWorkflowCompatibilityServer(BaseModel):
    executorId: str
    compatible: bool
    reachable: bool
    missingNodes: list[ComfyuiWorkflowMissingNode] = Field(default_factory=list)
    missingModels: list[ComfyuiWorkflowMissingModel] = Field(default_factory=list)
    message: str | None = None


class ComfyuiWorkflowCompatibilityItem(BaseModel):
    abilityId: str
    displayName: str
    capabilityKey: str
    workflowKey: str
    workflowId: str | None = None
    action: str | None = None
    allowedExecutorIds: list[str] = Field(default_factory=list)
    bindingExecutorIds: list[str] = Field(default_factory=list)
    expectedExecutorIds: list[str] = Field(default_factory=list)
    compatibleExecutorIds: list[str] = Field(default_factory=list)
    incompatibleExecutorIds: list[str] = Field(default_factory=list)
    requiredNodeKeys: list[str] = Field(default_factory=list)
    requiredNodeCount: int = 0
    status: str
    diagnostics: list[ComfyuiWorkflowCompatibilityDiagnostic] = Field(default_factory=list)
    servers: list[ComfyuiWorkflowCompatibilityServer] = Field(default_factory=list)


class ComfyuiWorkflowCompatibilityExecutor(BaseModel):
    executorId: str
    executorName: str | None = None
    baseUrl: str | None = None
    status: str | None = None
    reachable: bool
    nodeCount: int | None = None
    message: str | None = None


class ComfyuiWorkflowCompatibilityResponse(BaseModel):
    checkedAt: str
    totalWorkflows: int
    okCount: int
    warningCount: int
    failedCount: int
    servers: list[ComfyuiWorkflowCompatibilityExecutor]
    workflows: list[ComfyuiWorkflowCompatibilityItem]


class ComfyuiSystemStatsResponse(BaseModel):
    executorId: str
    baseUrl: str
    system: dict[str, Any] | None = None
    devices: list[dict[str, Any]] | None = None
    raw: dict[str, Any] | None = None
