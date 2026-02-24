"""Schemas for asynchronous ability tasks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .abilities import AbilityInvokeRequest


class AbilityTaskCreateRequest(AbilityInvokeRequest):
    abilityId: str


class AbilityTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    abilityId: str = Field(alias="ability_id")
    abilityName: str | None = Field(default=None, alias="ability_name")
    provider: str = Field(alias="ability_provider")
    capabilityKey: str | None = Field(default=None, alias="capability_key")
    status: str = Field(
        description="任务状态：queued/running/succeeded/failed/cancelled（统一契约）",
    )
    logId: int | None = Field(default=None, alias="log_id")
    durationMs: int | None = Field(default=None, alias="duration_ms")
    requestPayload: dict[str, Any] | None = Field(default=None, alias="request_payload")
    resultPayload: dict[str, Any] | None = Field(default=None, alias="result_payload")
    errorMessage: str | None = Field(
        default=None,
        alias="error_message",
        description="失败原因错误码或可读信息（如 TASK_NOT_FOUND / KIE_TIMEOUT）",
    )
    callbackUrl: str | None = Field(default=None, alias="callback_url")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")
    startedAt: datetime | None = Field(default=None, alias="started_at")
    finishedAt: datetime | None = Field(default=None, alias="finished_at")


class AbilityTaskListResponse(BaseModel):
    items: list[AbilityTaskRead]
