"""Schemas for ability catalog management."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class AbilityBase(BaseModel):
    provider: str
    category: str
    capability_key: str
    display_name: str
    description: str | None = None
    status: str = Field(default="inactive")
    ability_type: str = Field(default="api")
    executor_id: str | None = None
    workflow_id: str | None = None
    default_params: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class AbilityCreate(AbilityBase):
    id: str | None = None


class AbilityUpdate(BaseModel):
    provider: str | None = None
    category: str | None = None
    capability_key: str | None = None
    display_name: str | None = None
    description: str | None = None
    status: str | None = None
    ability_type: str | None = None
    executor_id: str | None = None
    workflow_id: str | None = None
    default_params: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class AbilityRead(AbilityBase):
    model_config = ConfigDict(from_attributes=True)

    metadata: dict[str, Any] | None = Field(default=None, alias="extra_metadata")

    ability_type: str = Field(default="api")
    workflow_id: str | None = None
    last_health_check_at: datetime | None = None
    last_health_status: str | None = None
    success_rate: float | None = None

    id: str
    created_at: datetime
    updated_at: datetime
