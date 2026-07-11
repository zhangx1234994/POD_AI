"""External contracts for client production orders and operations fulfillment."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ShippingAddressInput(BaseModel):
    recipientName: str = Field(min_length=1, max_length=128)
    phoneNumber: str = Field(min_length=5, max_length=32)
    country: str = Field(min_length=2, max_length=8)
    state: str = Field(min_length=1, max_length=128)
    city: str = Field(min_length=1, max_length=128)
    district: str | None = Field(default=None, max_length=128)
    address: str = Field(min_length=3, max_length=500)
    postalCode: str = Field(min_length=3, max_length=32)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.strip().upper()


class ProductionOrderItemInput(BaseModel):
    productName: str = Field(min_length=1, max_length=180)
    templateNo: str = Field(min_length=1, max_length=64)
    bodyCode: str | None = Field(default=None, max_length=64)
    sizeCode: str = Field(min_length=1, max_length=64)
    colorCode: str = Field(min_length=1, max_length=64)
    firstCraft: str = Field(default="17", min_length=1, max_length=64)
    secondCraft: str | None = Field(default="2", max_length=64)
    viewId: str = Field(default="1", min_length=1, max_length=32)
    surfaceName: str = Field(default="front", min_length=1, max_length=64)
    targetWidth: int = Field(ge=64, le=12000)
    targetHeight: int = Field(ge=64, le=12000)
    targetDpi: int = Field(default=150, ge=72, le=600)
    quantity: int = Field(default=1, ge=1, le=10000)
    sourceAssetUrl: str
    compositionMode: Literal["cover", "tile", "seamless"] = "cover"
    tiledReviewConfirmed: bool = False


class ProductionOrderCreateInput(BaseModel):
    clientRequestId: str | None = Field(default=None, max_length=128)
    shippingAddress: ShippingAddressInput
    items: list[ProductionOrderItemInput] = Field(min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)


class ProductionOrderPayInput(BaseModel):
    paymentReference: str | None = Field(default=None, max_length=128)


class ProductionOrderOpsSubmitInput(BaseModel):
    confirmProduction: bool = False


class ProductionOrderItemOut(BaseModel):
    id: str
    productName: str
    templateNo: str
    sizeCode: str
    colorCode: str
    firstCraft: str
    secondCraft: str | None = None
    viewId: str
    targetWidth: int
    targetHeight: int
    targetDpi: int
    quantity: int
    sourceAssetUrl: str
    productionAssetUrl: str
    supplierEffectImageUrl: str | None = None
    preflight: dict[str, Any]


class ProductionOrderEventOut(BaseModel):
    eventType: str
    actorUserId: str | None = None
    payload: dict[str, Any] | None = None
    createdAt: datetime


class ProductionOrderOut(BaseModel):
    id: str
    orderNo: str
    status: str
    paymentStatus: str
    totalAmountCents: int
    totalPoints: int
    shippingAddress: dict[str, Any]
    supplierOrderId: str | None = None
    supplierPlatformOrderId: str | None = None
    supplierStatus: str | None = None
    supplierEffectImageUrls: list[str] = Field(default_factory=list)
    items: list[ProductionOrderItemOut]
    events: list[ProductionOrderEventOut] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime
