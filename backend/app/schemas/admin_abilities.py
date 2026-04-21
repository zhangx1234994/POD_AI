"""Schemas for ability catalog management."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class AbilityGovernance(BaseModel):
    scopes: list[str] = Field(default_factory=list)
    release_status: str = Field(default="draft")
    route_policy: str = Field(default="fixed")
    quality_status: str = Field(default="untested")


class AbilityBusinessStatus(BaseModel):
    availability_code: str = Field(default="unavailable")
    availability_label: str = Field(default="暂不可用")
    stability_code: str = Field(default="experimental")
    stability_label: str = Field(default="实验性")
    surface_labels: list[str] = Field(default_factory=list)


class AbilityBase(BaseModel):
    provider: str
    category: str
    capability_key: str
    version: str = Field(default="v1")
    display_name: str
    description: str | None = None
    status: str = Field(default="inactive")
    ability_type: str = Field(default="api")
    executor_id: str | None = None
    workflow_id: str | None = None
    coze_workflow_id: str | None = None
    default_params: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    governance: AbilityGovernance | None = None


class AbilityCreate(AbilityBase):
    id: str | None = None


class AbilityUpdate(BaseModel):
    provider: str | None = None
    category: str | None = None
    capability_key: str | None = None
    version: str | None = None
    display_name: str | None = None
    description: str | None = None
    status: str | None = None
    ability_type: str | None = None
    executor_id: str | None = None
    workflow_id: str | None = None
    coze_workflow_id: str | None = None
    default_params: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    governance: AbilityGovernance | None = None


class AbilityRead(AbilityBase):
    model_config = ConfigDict(from_attributes=True)

    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")

    ability_type: str = Field(default="api")
    workflow_id: str | None = None
    coze_workflow_id: str | None = None
    last_health_check_at: datetime | None = None
    last_health_status: str | None = None
    success_rate: float | None = None
    business_status: AbilityBusinessStatus | None = None

    id: str
    created_at: datetime
    updated_at: datetime


class AbilityOption(BaseModel):
    id: str
    provider: str
    category: str | None = None
    capability_key: str
    version: str | None = None
    display_name: str
    description: str | None = None
    default_params: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    coze_workflow_id: str | None = None
    governance: AbilityGovernance | None = None
    business_status: AbilityBusinessStatus | None = None


class AbilityOptionListResponse(BaseModel):
    items: list[AbilityOption]


class AbilityTemplateSnapshot(BaseModel):
    id: str
    version_label: str | None = None
    action: str = "publish"
    created_at: datetime
    notes: str | None = None
    default_params: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class AbilityTemplateStateResponse(BaseModel):
    ability_id: str
    current_template_id: str | None = None
    history: list[AbilityTemplateSnapshot]


class AbilityTemplatePublishRequest(BaseModel):
    version_label: str | None = None
    notes: str | None = None


class AbilityTemplateRollbackRequest(BaseModel):
    template_id: str = Field(..., alias="templateId")
    notes: str | None = None


class AbilityTemplateValidateRequest(BaseModel):
    default_params: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class AbilityTemplateValidateResponse(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]
