"""Production-order records for the client-to-supplier fulfillment boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ProductionOrder(Base):
    __tablename__ = "production_orders"
    __table_args__ = (
        Index("ix_production_orders_user_created", "user_id", "created_at"),
        Index("ix_production_orders_status_created", "status", "created_at"),
        Index("ix_production_orders_supplier_order", "supplier_order_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payment_reference: Mapped[str | None] = mapped_column(String(128))
    shipping_address: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    supplier_order_id: Mapped[str | None] = mapped_column(String(128))
    supplier_platform_order_id: Mapped[str | None] = mapped_column(String(128))
    supplier_status: Mapped[str | None] = mapped_column(String(128))
    supplier_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    submitted_to_supplier_at: Mapped[datetime | None] = mapped_column(DateTime)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    items: Mapped[list["ProductionOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="ProductionOrderItem.id"
    )
    events: Mapped[list["ProductionOrderEvent"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="ProductionOrderEvent.id"
    )


class ProductionOrderItem(Base):
    __tablename__ = "production_order_items"
    __table_args__ = (Index("ix_production_order_items_order", "order_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False
    )
    product_name: Mapped[str] = mapped_column(String(180), nullable=False)
    template_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    body_code: Mapped[str | None] = mapped_column(String(64))
    size_code: Mapped[str] = mapped_column(String(64), nullable=False)
    color_code: Mapped[str] = mapped_column(String(64), nullable=False)
    first_craft: Mapped[str] = mapped_column(String(64), nullable=False)
    second_craft: Mapped[str | None] = mapped_column(String(64))
    view_id: Mapped[str] = mapped_column(String(32), nullable=False, default="1")
    surface_name: Mapped[str] = mapped_column(String(64), nullable=False)
    target_width: Mapped[int] = mapped_column(Integer, nullable=False)
    target_height: Mapped[int] = mapped_column(Integer, nullable=False)
    target_dpi: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    source_asset_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    production_asset_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    production_asset_key: Mapped[str | None] = mapped_column(String(512))
    supplier_effect_image_url: Mapped[str | None] = mapped_column(String(1024))
    supplier_effect_image_key: Mapped[str | None] = mapped_column(String(512))
    preflight: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    order: Mapped[ProductionOrder] = relationship(back_populates="items")


class ProductionOrderEvent(Base):
    __tablename__ = "production_order_events"
    __table_args__ = (Index("ix_production_order_events_order_created", "order_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    order: Mapped[ProductionOrder] = relationship(back_populates="events")
