"""Public schemas for vendor-api-ops."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorPayload(BaseModel):
    success: bool = False
    errorCode: str
    message: str
    suggestion: str | None = None
    source: dict[str, str] | None = None


class ProviderInfo(BaseModel):
    provider: str
    displayName: str
    status: str
    requiresGlobalEgress: bool = False
    envKeyConfigured: bool = False
    supportedChecks: list[str] = Field(default_factory=list)
    supportedApiTypes: list[str] = Field(default_factory=list)
    executionModes: list[str] = Field(default_factory=list)


class ProvidersResponse(BaseModel):
    service: str
    providers: list[ProviderInfo]


class EgressCheckRequest(BaseModel):
    check: str = Field(default="models", description="Provider-specific connectivity check name.")
    includeAuth: bool = Field(default=False, description="Whether to include configured provider auth.")
    credentials: dict[str, Any] = Field(
        default_factory=dict,
        description="Request-scoped credentials provided by backend. Never returned or persisted in plaintext.",
    )


class EgressCheckResponse(BaseModel):
    success: bool
    provider: str
    check: str
    url: str
    httpStatus: int | None = None
    latencyMs: int | None = None
    errorCode: str | None = None
    message: str | None = None
    suggestion: str | None = None


class InvocationAsset(BaseModel):
    url: str | None = None
    b64: str | None = None
    role: str | None = Field(default="output")
    mimeType: str | None = None
    metadata: dict[str, Any] | None = None


class InvocationResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    images: list[InvocationAsset] = Field(default_factory=list)
    videos: list[InvocationAsset] = Field(default_factory=list)
    texts: list[str] = Field(default_factory=list)
    json_: dict[str, Any] = Field(default_factory=dict, alias="json")
    usage: dict[str, Any] = Field(default_factory=dict)
    cost: dict[str, Any] = Field(default_factory=dict)


class InvocationError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    suggestion: str | None = None


class InvocationRequest(BaseModel):
    provider: str
    capabilityKey: str
    model: str | None = None
    apiType: str | None = None
    executionMode: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    assets: list[InvocationAsset] = Field(default_factory=list)
    taskPolicy: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(
        default_factory=dict,
        description="Request-scoped vendor credentials provided by backend. Never returned or persisted in plaintext.",
    )
    requestId: str | None = None
    traceId: str | None = None
    callbackUrl: str | None = None


class InvocationFetchRequest(BaseModel):
    credentials: dict[str, Any] = Field(
        default_factory=dict,
        description="Request-scoped vendor credentials for polling async vendor tasks.",
    )


class InvocationResponse(BaseModel):
    success: bool
    status: str
    provider: str
    model: str | None = None
    vendorInvocationId: str
    vendorTaskId: str | None = None
    result: InvocationResult = Field(default_factory=InvocationResult)
    error: InvocationError | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


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
    items: list[VendorKeyRead]


class UsageSummaryItem(BaseModel):
    provider: str
    model: str | None = None
    status: str
    count: int = 0
    errorCode: str | None = None
    avgLatencyMs: int | None = None
    lastSeenAt: datetime | None = None


class UsageSummaryResponse(BaseModel):
    windowHours: int
    items: list[UsageSummaryItem]
