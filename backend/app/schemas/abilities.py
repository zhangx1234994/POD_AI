"""Schemas for public ability catalogue and invocation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AbilityPublicInfo(BaseModel):
    id: str
    provider: str
    category: str
    capabilityKey: str
    displayName: str
    description: str | None = None
    status: str
    abilityType: str = Field(default="api")
    workflowId: str | None = None
    executorId: str | None = None
    cozeWorkflowId: str | None = None
    defaultParams: dict[str, Any] | None = None
    inputSchema: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    requiresImage: bool = False
    supportsMultipleImages: bool = False
    maxOutputImages: int | None = None
    lastHealthCheckAt: datetime | None = None
    lastHealthStatus: str | None = None
    successRate: float | None = None


class AbilityListResponse(BaseModel):
    items: list[AbilityPublicInfo]


class AbilityImageInput(BaseModel):
    name: str | None = Field(default=None, description="Optional filename or tag")
    url: str | None = Field(default=None, description="External HTTP URL")
    ossUrl: str | None = Field(default=None, description="OSS URL from prior uploads")
    base64: str | None = Field(default=None, description="Data URL/Base64 payload")


class AbilityInvokeRequest(BaseModel):
    executorId: str | None = Field(default=None, description="Override executor ID when多个节点可用")
    inputs: dict[str, Any] | None = Field(default=None, description="能力自定义参数映射")
    imageUrl: str | None = Field(default=None, description="单图入口：HTTP/OSS 地址")
    imageBase64: str | None = Field(default=None, description="单图入口：Base64 字符串")
    images: list[AbilityImageInput] | None = Field(
        default=None, description="多图入口，按顺序传入；ComfyUI/KIE 流程自动转换为 imageList"
    )
    metadata: dict[str, Any] | None = Field(default=None, description="客户端上下文信息，可选")
    callbackUrl: str | None = Field(
        default=None,
        description="可选，HTTP(s) 地址；若填写则在执行完成或失败后推送结果",
    )
    callbackHeaders: dict[str, str] | None = Field(
        default=None,
        description="可选，自定义回调请求头，例如鉴权 token",
    )


class AbilityOutputAsset(BaseModel):
    ossUrl: str | None = None
    sourceUrl: str | None = None
    base64: str | None = None
    type: str | None = None
    description: str | None = None
    tag: str | None = None


class AbilityInvokeResponse(BaseModel):
    abilityId: str
    provider: str
    status: str = "succeeded"
    requestId: str
    logId: int | None = None
    durationMs: int | None = Field(default=None, description="执行耗时，毫秒")
    images: list[AbilityOutputAsset] | None = None
    videos: list[AbilityOutputAsset] | None = None
    texts: list[str] | None = None
    assets: list[AbilityOutputAsset] | None = None
    metadata: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None
