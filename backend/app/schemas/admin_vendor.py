"""Schemas for vendor-api-ops administration proxy endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class VendorProviderRead(BaseModel):
    provider: str
    displayName: str
    status: str
    requiresGlobalEgress: bool = False
    envKeyConfigured: bool = False
    supportedChecks: list[str] = Field(default_factory=list)
    supportedApiTypes: list[str] = Field(default_factory=list)
    executionModes: list[str] = Field(default_factory=list)


class VendorProviderListResponse(BaseModel):
    service: str
    baseUrl: str
    providers: list[VendorProviderRead]


class VendorEgressCheckRequest(BaseModel):
    check: str = "models"
    includeAuth: bool = False


class VendorEgressCheckResponse(BaseModel):
    success: bool
    provider: str
    check: str
    url: str
    httpStatus: int | None = None
    latencyMs: int | None = None
    errorCode: str | None = None
    message: str | None = None
    suggestion: str | None = None


class VendorKeyCreateRequest(BaseModel):
    provider: str
    alias: str
    key: str
    secret: str | None = None
    model: str | None = None
    status: str = "active"
    dailyQuota: int | None = None
    monthlyQuota: int | None = None
    maxConcurrency: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class VendorKeyUpdateRequest(BaseModel):
    status: str | None = None
    cooldownUntil: datetime | None = None
    lastError: str | None = None
    metadata: dict[str, Any] | None = None


class VendorKeyRead(BaseModel):
    id: str
    provider: str
    alias: str
    model: str | None = None
    status: str
    keyPreview: str
    dailyQuota: int | None = None
    monthlyQuota: int | None = None
    usageCount: int = 0
    maxConcurrency: int = 1
    cooldownUntil: datetime | None = None
    lastError: str | None = None
    lastUsedAt: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VendorKeyListResponse(BaseModel):
    baseUrl: str
    items: list[VendorKeyRead]


class VendorUsageSummaryItem(BaseModel):
    provider: str
    model: str | None = None
    status: str
    count: int = 0
    errorCode: str | None = None
    avgLatencyMs: int | None = None
    lastSeenAt: datetime | None = None


class VendorUsageSummaryResponse(BaseModel):
    baseUrl: str
    windowHours: int
    items: list[VendorUsageSummaryItem]


class VendorGovernanceTotals(BaseModel):
    providerCount: int = 0
    modelCount: int = 0
    activeModelCount: int = 0
    abilityCount: int = 0
    activeAbilityCount: int = 0
    keyCount: int = 0
    activeStoredKeyCount: int = 0
    envKeyProviderCount: int = 0
    issueCount: int = 0


class VendorGovernanceProviderItem(BaseModel):
    provider: str
    displayName: str
    providerStatus: str = "unknown"
    requiresGlobalEgress: bool = False
    envKeyConfigured: bool = False
    runtimeKeyConfigured: bool = False
    keyCount: int = 0
    activeStoredKeyCount: int = 0
    disabledKeyCount: int = 0
    cooldownKeyCount: int = 0
    exhaustedKeyCount: int = 0
    errorKeyCount: int = 0
    modelCount: int = 0
    activeModelCount: int = 0
    abilityCount: int = 0
    activeAbilityCount: int = 0
    succeededCalls: int = 0
    failedCalls: int = 0
    avgLatencyMs: int | None = None
    lastSeenAt: datetime | None = None
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class VendorGovernanceSummaryResponse(BaseModel):
    baseUrl: str
    windowHours: int
    generatedAt: datetime
    totals: VendorGovernanceTotals
    providers: list[VendorGovernanceProviderItem]
    issues: list[str] = Field(default_factory=list)


class VendorModelBase(BaseModel):
    provider: str
    model: str
    displayName: str
    status: str = "active"
    apiTypes: list[str] = Field(default_factory=list)
    executionModes: list[str] = Field(default_factory=list)
    supportsMask: bool = False
    supportsMultipleImages: bool = False
    supportsVideo: bool = False
    supportsText: bool = False
    requiresGlobalEgress: bool = False
    source: str = "provider"
    routePolicy: dict[str, Any] | None = Field(default_factory=dict)
    defaultTaskPolicy: dict[str, Any] | None = Field(default_factory=dict)
    inputSchema: dict[str, Any] | None = Field(default_factory=dict)
    costPolicy: dict[str, Any] | None = Field(default_factory=dict)
    metadata: dict[str, Any] | None = Field(default_factory=dict)


class VendorModelCreateRequest(VendorModelBase):
    pass


class VendorModelUpdateRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    displayName: str | None = None
    status: str | None = None
    apiTypes: list[str] | None = None
    executionModes: list[str] | None = None
    supportsMask: bool | None = None
    supportsMultipleImages: bool | None = None
    supportsVideo: bool | None = None
    supportsText: bool | None = None
    requiresGlobalEgress: bool | None = None
    source: str | None = None
    routePolicy: dict[str, Any] | None = None
    defaultTaskPolicy: dict[str, Any] | None = None
    inputSchema: dict[str, Any] | None = None
    costPolicy: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class VendorModelRead(VendorModelBase):
    id: int | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class VendorModelListResponse(BaseModel):
    baseUrl: str
    items: list[VendorModelRead]
