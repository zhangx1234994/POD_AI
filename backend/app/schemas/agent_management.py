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
    status: str
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
    status: str | None = None
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
