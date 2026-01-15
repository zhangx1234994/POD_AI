"""Pydantic schemas for admin integration endpoints."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class ExecutorBase(BaseModel):
    name: str
    type: str
    base_url: str | None = None
    status: str = "inactive"
    weight: int = 1
    max_concurrency: int = 1
    config: dict[str, Any] | None = None
    api_key_ids: list[str] = Field(default_factory=list)


class ExecutorCreate(ExecutorBase):
    id: str | None = None


class ExecutorUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    base_url: str | None = None
    status: str | None = None
    weight: int | None = None
    max_concurrency: int | None = None
    config: dict[str, Any] | None = None
    api_key_ids: list[str] | None = None


class ExecutorRead(ExecutorBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    health_status: str | None = None
    last_heartbeat_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowBase(BaseModel):
    action: str
    name: str
    version: str = "v1"
    type: str = "generic"
    status: str = "inactive"
    definition: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] | None = None


class WorkflowCreate(WorkflowBase):
    id: str | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    status: str | None = None
    type: str | None = None
    definition: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class WorkflowRead(WorkflowBase):
    model_config = ConfigDict(from_attributes=True)

    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")

    id: str
    created_at: datetime
    updated_at: datetime


class WorkflowBindingBase(BaseModel):
    action: str
    workflow_id: str
    executor_id: str
    priority: int = 0
    enabled: bool = True
    metadata: dict[str, Any] | None = None


class WorkflowBindingCreate(WorkflowBindingBase):
    id: str | None = None


class WorkflowBindingUpdate(BaseModel):
    workflow_id: str | None = None
    executor_id: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    metadata: dict[str, Any] | None = None


class WorkflowBindingRead(WorkflowBindingBase):
    model_config = ConfigDict(from_attributes=True)

    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")

    id: str
    created_at: datetime
    updated_at: datetime


class ApiKeyBase(BaseModel):
    provider: str
    name: str
    key: str
    status: str = "active"
    daily_quota: int | None = None
    expire_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class ApiKeyCreate(ApiKeyBase):
    id: str | None = None


class ApiKeyUpdate(BaseModel):
    provider: str | None = None
    name: str | None = None
    key: str | None = None
    status: str | None = None
    daily_quota: int | None = None
    expire_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class ApiKeyRead(ApiKeyBase):
    model_config = ConfigDict(from_attributes=True)

    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")

    id: str
    usage_count: int
    created_at: datetime
    updated_at: datetime
