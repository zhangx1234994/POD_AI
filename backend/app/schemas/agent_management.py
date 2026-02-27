"""Schemas for ComfyUI agent management."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class AgentBase(BaseModel):
    name: str | None = None
    role: str | None = None
    host: str | None = None
    base_url: str | None = Field(default=None, alias="baseUrl")
    status: str | None = None
    allowed: bool | None = None
    config: dict[str, Any] | None = None


class AgentCreate(AgentBase):
    id: str = Field(..., description="Agent ID (unique)")


class AgentUpdate(AgentBase):
    id: str | None = None


class AgentRead(AgentBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    last_seen_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_manifest_version: str | None = None
    metrics: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class AgentManifestBase(BaseModel):
    role: str
    version: str
    status: str | None = None
    download_url: str | None = Field(default=None, alias="downloadUrl")
    content: dict[str, Any] | None = None
    notes: str | None = None


class AgentManifestCreate(AgentManifestBase):
    pass


class AgentManifestUpdate(BaseModel):
    role: str | None = None
    version: str | None = None
    status: str | None = None
    download_url: str | None = Field(default=None, alias="downloadUrl")
    content: dict[str, Any] | None = None
    notes: str | None = None


class AgentManifestRead(AgentManifestBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    created_at: datetime
    updated_at: datetime


class AgentTaskBase(BaseModel):
    agent_id: str = Field(..., alias="agentId")
    manifest_id: int | None = Field(default=None, alias="manifestId")
    manifest_url: str | None = Field(default=None, alias="manifestUrl")
    actions: list[str] | None = None
    expires_at: datetime | None = Field(default=None, alias="expiresAt")


class AgentTaskCreate(AgentTaskBase):
    task_id: str | None = Field(default=None, alias="taskId")


class AgentTaskUpdate(BaseModel):
    status: str | None = None
    result_payload: dict[str, Any] | None = Field(default=None, alias="resultPayload")
    error_message: str | None = Field(default=None, alias="errorMessage")


class AgentTaskRead(AgentTaskBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    status: str = Field(description="任务状态：pending/running/success/failed/rejected")
    submit_status: str | None = Field(default=None, alias="submitStatus")
    callback_status: str | None = Field(default=None, alias="callbackStatus")
    final_status: str | None = Field(default=None, alias="finalStatus")
    error_code: str | None = Field(default=None, alias="errorCode")
    token_nonce: str | None = Field(default=None, alias="tokenNonce")
    pushed_at: datetime | None = Field(default=None, alias="pushedAt")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    request_payload: dict[str, Any] | None = Field(default=None, alias="requestPayload")
    result_payload: dict[str, Any] | None = Field(default=None, alias="resultPayload")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: datetime
    updated_at: datetime


class AgentTaskEventCreate(BaseModel):
    level: str = Field(default="info")
    step: str | None = None
    stage: str | None = None
    provider: str | None = None
    node_id: str | None = Field(default=None, alias="nodeId")
    retry_count: int | None = Field(default=None, alias="retryCount")
    trace_id: str | None = Field(default=None, alias="traceId")
    message: str
    progress: float | None = None
    payload: dict[str, Any] | None = None
    event_time: datetime | None = Field(default=None, alias="eventTime")


class AgentTaskEventRead(AgentTaskEventCreate):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    task_id: str = Field(..., alias="taskId")
    created_at: datetime


class AgentAlertCreate(BaseModel):
    alert_type: str = Field(..., alias="alertType", validation_alias=AliasChoices("alertType", "type"))
    message: str
    payload: dict[str, Any] | None = None


class AgentAlertRead(AgentAlertCreate):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    agent_id: str = Field(..., alias="agentId")
    created_at: datetime


class AgentHeartbeatRequest(BaseModel):
    status: str | None = Field(default=None, description="agent 状态（建议 active/inactive）")
    metrics: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None
    cpu: float | None = None
    mem: float | None = None
    disk_free_gb: float | None = Field(default=None, validation_alias=AliasChoices("diskFreeGb", "disk_free_gb"))
    gpu: dict[str, Any] | None = None
    agent_version: str | None = Field(default=None, alias="agentVersion")
    comfyui_version: str | None = Field(default=None, alias="comfyuiVersion")


class AgentHeartbeatResponse(BaseModel):
    status: str
    agent_id: str = Field(..., alias="agentId")
    received_at: datetime = Field(..., alias="receivedAt")


class AgentAuthVerifyRequest(BaseModel):
    token: str
    agent_id: str | None = Field(default=None, alias="agentId")
    task_id: str | None = Field(default=None, alias="taskId")
    nonce: str | None = None


class AgentTaskCompleteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    task_id: str | None = Field(default=None, alias="taskId")
    agent_id: str | None = Field(default=None, alias="agentId")
    summary: str | None = None


class AgentTaskFailedRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    task_id: str | None = Field(default=None, alias="taskId")
    agent_id: str | None = Field(default=None, alias="agentId")
    error_code: str | None = Field(default=None, alias="errorCode")
    message: str | None = None
    failed_items: dict[str, Any] | None = Field(default=None, alias="failedItems")


class AgentAuthVerifyResponse(BaseModel):
    ok: bool
    agent_id: str = Field(..., alias="agentId")
    task_id: str | None = Field(default=None, alias="taskId")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    scope: str | None = None
    policy: dict[str, bool] | None = None


class AgentTokenIssueRequest(BaseModel):
    ttl_seconds: int | None = Field(default=None, alias="ttlSeconds")


class AgentTokenIssueResponse(BaseModel):
    token: str
    expires_at: datetime = Field(..., alias="expiresAt")
    scope: str
    agent_id: str = Field(..., alias="agentId")


class AgentManifestPublishRequest(BaseModel):
    notes: str | None = None
    status: str | None = Field(default="published")


class AgentManifestRollbackRequest(BaseModel):
    target_manifest_id: int | None = Field(default=None, alias="targetManifestId")
    notes: str | None = None


class AgentRolePrimaryUpdateRequest(BaseModel):
    agent_id: str = Field(..., alias="agentId")


class AgentRolePrimaryRead(BaseModel):
    role: str
    agent_id: str | None = Field(default=None, alias="agentId")
    base_url: str | None = Field(default=None, alias="baseUrl")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class AgentManifestDriftCollection(BaseModel):
    expected: list[str] = Field(default_factory=list)
    reported: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    extra: list[str] = Field(default_factory=list)


class AgentManifestDriftResponse(BaseModel):
    manifest_id: int = Field(..., alias="manifestId")
    manifest_version: str = Field(..., alias="manifestVersion")
    agent_id: str = Field(..., alias="agentId")
    agent_last_manifest_version: str | None = Field(default=None, alias="agentLastManifestVersion")
    same_version: bool = Field(default=False, alias="sameVersion")
    has_snapshot: bool = Field(default=False, alias="hasSnapshot")
    comfyui: dict[str, Any] = Field(default_factory=dict)
    models: AgentManifestDriftCollection
    plugins: AgentManifestDriftCollection
    workflows: AgentManifestDriftCollection


class AgentRepairPlanRequest(BaseModel):
    agent_ids: list[str] = Field(default_factory=list, alias="agentIds")
    mode: str = Field(default="additive")


class AgentRepairPlanItem(BaseModel):
    agent_id: str = Field(alias="agentId")
    role: str | None = None
    actions: list[str] = Field(default_factory=list)
    missing_items: dict[str, list[str]] = Field(default_factory=dict, alias="missingItems")
    reason: str | None = None


class AgentRepairPlanSummary(BaseModel):
    total_agents: int = Field(alias="totalAgents")
    executable_agents: int = Field(alias="executableAgents")
    skipped_agents: int = Field(alias="skippedAgents")
    total_actions: int = Field(alias="totalActions")


class AgentRepairPlanResponse(BaseModel):
    manifest_id: int = Field(alias="manifestId")
    manifest_version: str = Field(alias="manifestVersion")
    mode: str
    generated_at: datetime = Field(alias="generatedAt")
    items: list[AgentRepairPlanItem] = Field(default_factory=list)
    summary: AgentRepairPlanSummary


class AgentRepairJobCreateItem(BaseModel):
    agent_id: str = Field(alias="agentId")
    actions: list[str] = Field(default_factory=list)
    missing_items: dict[str, list[str]] = Field(default_factory=dict, alias="missingItems")


class AgentRepairJobCreateRequest(BaseModel):
    manifest_id: int = Field(alias="manifestId")
    mode: str = Field(default="additive")
    items: list[AgentRepairJobCreateItem] = Field(default_factory=list)
    push: bool = True


class AgentRepairJobItemRead(BaseModel):
    id: int
    agent_id: str | None = Field(default=None, alias="agentId")
    task_id: str | None = Field(default=None, alias="taskId")
    status: str
    submit_status: str | None = Field(default=None, alias="submitStatus")
    callback_status: str | None = Field(default=None, alias="callbackStatus")
    final_status: str | None = Field(default=None, alias="finalStatus")
    actions: list[str] = Field(default_factory=list)
    missing_items: dict[str, Any] = Field(default_factory=dict, alias="missingItems")
    failed_items: dict[str, Any] | None = Field(default=None, alias="failedItems")
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")
    updated_at: datetime = Field(alias="updatedAt")


class AgentRepairJobRead(BaseModel):
    id: str
    manifest_id: int = Field(alias="manifestId")
    mode: str
    status: str
    requested_agent_count: int = Field(alias="requestedAgentCount")
    submitted_task_count: int = Field(alias="submittedTaskCount")
    succeeded_task_count: int = Field(alias="succeededTaskCount")
    failed_task_count: int = Field(alias="failedTaskCount")
    skipped_task_count: int = Field(alias="skippedTaskCount")
    created_by: str | None = Field(default=None, alias="createdBy")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    items: list[AgentRepairJobItemRead] = Field(default_factory=list)
    result_payload: dict[str, Any] | None = Field(default=None, alias="resultPayload")


class AgentMonitoringLane(BaseModel):
    lane: str
    total: int
    queued: int
    running: int
    succeeded: int
    failed: int
    avg_wait_seconds: float = Field(default=0, alias="avgWaitSeconds")
    failure_rate: float = Field(default=0, alias="failureRate")
    retry_count: int = Field(default=0, alias="retryCount")


class AgentMonitoringSummaryResponse(BaseModel):
    generated_at: datetime = Field(..., alias="generatedAt")
    window_hours: int = Field(..., alias="windowHours")
    lanes: list[AgentMonitoringLane]


class AgentMonitoringQueueItem(BaseModel):
    lane: str
    provider: str
    queued: int
    running: int
    total: int
    avg_wait_seconds: float = Field(default=0, alias="avgWaitSeconds")


class AgentMonitoringQueuesResponse(BaseModel):
    generated_at: datetime = Field(alias="generatedAt")
    window_hours: int = Field(alias="windowHours")
    items: list[AgentMonitoringQueueItem]


class AgentMonitoringErrorItem(BaseModel):
    provider: str
    stage: str
    error_code: str = Field(alias="errorCode")
    count: int
    last_occurred_at: datetime | None = Field(default=None, alias="lastOccurredAt")
    sample_message: str | None = Field(default=None, alias="sampleMessage")


class AgentMonitoringErrorsResponse(BaseModel):
    generated_at: datetime = Field(alias="generatedAt")
    window_hours: int = Field(alias="windowHours")
    items: list[AgentMonitoringErrorItem]


class AgentRuntimePolicyRequest(BaseModel):
    default_policy: dict[str, Any] = Field(default_factory=dict, alias="defaultPolicy")
    lane_overrides: dict[str, Any] = Field(default_factory=dict, alias="laneOverrides")
    node_overrides: dict[str, Any] = Field(default_factory=dict, alias="nodeOverrides")
    notes: str | None = None


class AgentRuntimePolicyRead(AgentRuntimePolicyRequest):
    policy_type: str = Field(alias="policyType")
    updated_at: datetime = Field(alias="updatedAt")


class AgentEnrollCodeCreateRequest(BaseModel):
    role: str = Field(default="full")
    ttl_seconds: int | None = Field(default=None, alias="ttlSeconds")
    note: str | None = None
    max_uses: int = Field(default=1, alias="maxUses")


class AgentEnrollCodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    code: str
    role: str
    status: str
    note: str | None = None
    max_uses: int = Field(alias="maxUses")
    used_count: int = Field(alias="usedCount")
    expires_at: datetime = Field(alias="expiresAt")
    used_at: datetime | None = Field(default=None, alias="usedAt")
    used_by_agent_id: str | None = Field(default=None, alias="usedByAgentId")
    created_by: str | None = Field(default=None, alias="createdBy")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AgentBootstrapExchangeRequest(BaseModel):
    enroll_code: str = Field(..., alias="enrollCode")
    machine_name: str | None = Field(default=None, alias="machineName")
    host: str | None = None
    role: str | None = None
    base_url: str | None = Field(default=None, alias="baseUrl")
    preferred_agent_id: str | None = Field(default=None, alias="preferredAgentId")
    agent_version: str | None = Field(default=None, alias="agentVersion")
    comfyui_version: str | None = Field(default=None, alias="comfyuiVersion")
    payload: dict[str, Any] | None = None


class AgentBootstrapAutoExchangeRequest(BaseModel):
    install_key: str = Field(..., alias="installKey")
    machine_name: str | None = Field(default=None, alias="machineName")
    host: str | None = None
    role: str = "full"
    base_url: str | None = Field(default=None, alias="baseUrl")
    preferred_agent_id: str | None = Field(default=None, alias="preferredAgentId")
    agent_version: str | None = Field(default=None, alias="agentVersion")
    comfyui_version: str | None = Field(default=None, alias="comfyuiVersion")
    payload: dict[str, Any] | None = None


class AgentBootstrapKeyEntry(BaseModel):
    kid: str
    secret: str
    status: str = "active"


class AgentBootstrapExchangeResponse(BaseModel):
    agent_id: str = Field(alias="agentId")
    role: str
    center_url: str = Field(alias="centerUrl")
    agent_token: str = Field(alias="agentToken")
    agent_token_expires_at: datetime = Field(alias="agentTokenExpiresAt")
    heartbeat_interval_sec: int = Field(default=60, alias="heartbeatIntervalSec")
    jwt_keys: list[AgentBootstrapKeyEntry] = Field(default_factory=list, alias="jwtKeys")


class AgentBootstrapRefreshKeysResponse(BaseModel):
    center_url: str = Field(alias="centerUrl")
    jwt_keys: list[AgentBootstrapKeyEntry] = Field(default_factory=list, alias="jwtKeys")
    refreshed_at: datetime = Field(alias="refreshedAt")


class AgentDesktopReleaseBase(BaseModel):
    channel: str = "stable"
    version: str
    os_type: str = Field(default="windows", alias="osType")
    arch: str = "x64"
    status: str = "active"
    download_url: str = Field(alias="downloadUrl")
    sha256: str
    min_agent_version: str | None = Field(default=None, alias="minAgentVersion")
    notes: str | None = None
    payload: dict[str, Any] | None = None
    published_at: datetime | None = Field(default=None, alias="publishedAt")


class AgentDesktopReleaseCreate(AgentDesktopReleaseBase):
    pass


class AgentDesktopReleaseUpdate(BaseModel):
    channel: str | None = None
    version: str | None = None
    os_type: str | None = Field(default=None, alias="osType")
    arch: str | None = None
    status: str | None = None
    download_url: str | None = Field(default=None, alias="downloadUrl")
    sha256: str | None = None
    min_agent_version: str | None = Field(default=None, alias="minAgentVersion")
    notes: str | None = None
    payload: dict[str, Any] | None = None
    published_at: datetime | None = Field(default=None, alias="publishedAt")


class AgentDesktopReleaseRead(AgentDesktopReleaseBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AgentDesktopReleaseUploadResponse(BaseModel):
    file_name: str = Field(alias="fileName")
    file_size: int = Field(alias="fileSize")
    sha256: str
    download_url: str = Field(alias="downloadUrl")
