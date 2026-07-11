"""Schemas for the product client-facing API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClientUserRead(BaseModel):
    id: str
    username: str
    email: str
    displayName: str | None = None
    role: str
    status: str
    tenantId: str | None = None
    clientId: str | None = None


class ClientWorkspaceRead(BaseModel):
    id: str
    name: str
    scenario: str
    status: str
    assetCount: int = 0
    runCount: int = 0
    latestRunStatus: str | None = None
    createdAt: datetime
    updatedAt: datetime


class ClientMeResponse(BaseModel):
    user: ClientUserRead
    workspace: ClientWorkspaceRead


class ClientAssetCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assetType: str = Field(alias="asset_type")
    url: str
    contentType: str | None = Field(default=None, alias="content_type")
    fileName: str | None = Field(default=None, alias="file_name")
    flowStepKey: str | None = Field(default=None, alias="flow_step_key")
    inputTags: list[str] = Field(default_factory=list, alias="input_tags")
    issueTags: list[str] = Field(default_factory=list, alias="issue_tags")
    metadata: dict[str, Any] | None = None


class ClientAssetRead(BaseModel):
    id: str
    assetType: str
    url: str
    contentType: str | None = None
    fileName: str | None = None
    title: str | None = None
    sourceRunId: str | None = None
    sourceBusinessKey: str | None = None
    sourceFlowStepKey: str | None = None
    qualityGrade: str | None = None
    inputTags: list[str] = Field(default_factory=list)
    issueTags: list[str] = Field(default_factory=list)
    selected: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime
    updatedAt: datetime


class ClientAssetListResponse(BaseModel):
    total: int
    items: list[ClientAssetRead]


class ClientWalletLedgerItem(BaseModel):
    id: str
    points: int
    description: str | None = None
    createdAt: str | None = None
    traceId: str | None = None
    taskId: str | None = None


class ClientProductCouponRead(BaseModel):
    id: str
    packageKey: str
    name: str
    businessKey: str | None = None
    totalUnits: int
    usedUnits: int
    frozenUnits: int
    remainingUnits: int
    unitName: str
    status: str
    source: str | None = None
    expiresAt: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClientWalletResponse(BaseModel):
    pointBalance: int
    frozenPoints: int
    currency: str = "CNY"
    productCouponCount: int
    productCoupons: list[ClientProductCouponRead] = Field(default_factory=list)
    ledger: list[ClientWalletLedgerItem] = Field(default_factory=list)
