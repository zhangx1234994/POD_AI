"""Schemas for workflow trigger & orchestration APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ComfyuiWorkflowTriggerRequest(BaseModel):
    executorId: str
    workflowKey: str
    workflowParams: dict[str, Any] | None = None
    workflowRunId: str | None = None
    abilityId: str | None = None
    source: str | None = None


class ComfyuiWorkflowTriggerResponse(BaseModel):
    provider: str
    workflowKey: str
    promptId: str
    storedUrl: str | None = None
    assets: list[dict[str, Any]] | None = None
    raw: dict[str, Any] | None = None
    logId: int | None = None
    workflowRunId: str | None = None
