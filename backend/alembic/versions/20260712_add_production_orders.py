"""add production orders

Revision ID: 20260712_add_production_orders
Revises: 20260604_add_business_agent_message_request_id
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260712_add_production_orders"
down_revision: Union[str, Sequence[str], None] = "20260604_add_business_agent_message_request_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "production_orders" not in inspector.get_table_names():
        op.create_table(
            "production_orders",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("order_no", sa.String(64), nullable=False, unique=True),
            sa.Column("idempotency_key", sa.String(128), unique=True),
            sa.Column("user_id", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("payment_status", sa.String(32), nullable=False),
            sa.Column("total_amount_cents", sa.Integer(), nullable=False),
            sa.Column("total_points", sa.Integer(), nullable=False),
            sa.Column("payment_reference", sa.String(128)),
            sa.Column("shipping_address", sa.JSON(), nullable=False),
            sa.Column("supplier_order_id", sa.String(128)),
            sa.Column("supplier_platform_order_id", sa.String(128)),
            sa.Column("supplier_status", sa.String(128)),
            sa.Column("supplier_response", sa.JSON()),
            sa.Column("notes", sa.Text()),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("submitted_to_supplier_at", sa.DateTime()),
            sa.Column("paid_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        for name, columns, unique in (
            ("ix_production_orders_order_no", ["order_no"], True),
            ("ix_production_orders_idempotency_key", ["idempotency_key"], True),
            ("ix_production_orders_user_id", ["user_id"], False),
            ("ix_production_orders_user_created", ["user_id", "created_at"], False),
            ("ix_production_orders_status_created", ["status", "created_at"], False),
            ("ix_production_orders_supplier_order", ["supplier_order_id"], False),
        ):
            op.create_index(name, "production_orders", columns, unique=unique)
    if "production_order_items" not in inspector.get_table_names():
        op.create_table(
            "production_order_items",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("order_id", sa.String(64), sa.ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("product_name", sa.String(180), nullable=False),
            sa.Column("template_no", sa.String(64), nullable=False),
            sa.Column("body_code", sa.String(64)),
            sa.Column("size_code", sa.String(64), nullable=False),
            sa.Column("color_code", sa.String(64), nullable=False),
            sa.Column("first_craft", sa.String(64), nullable=False),
            sa.Column("second_craft", sa.String(64)),
            sa.Column("view_id", sa.String(32), nullable=False),
            sa.Column("surface_name", sa.String(64), nullable=False),
            sa.Column("target_width", sa.Integer(), nullable=False),
            sa.Column("target_height", sa.Integer(), nullable=False),
            sa.Column("target_dpi", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("source_asset_url", sa.String(1024), nullable=False),
            sa.Column("production_asset_url", sa.String(1024), nullable=False),
            sa.Column("production_asset_key", sa.String(512)),
            sa.Column("supplier_effect_image_url", sa.String(1024)),
            sa.Column("supplier_effect_image_key", sa.String(512)),
            sa.Column("preflight", sa.JSON(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_production_order_items_order", "production_order_items", ["order_id"])
        op.create_index("ix_production_order_items_template", "production_order_items", ["template_no"])
    if "production_order_events" not in inspector.get_table_names():
        op.create_table(
            "production_order_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("order_id", sa.String(64), sa.ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("actor_user_id", sa.String(64)),
            sa.Column("payload", sa.JSON()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_production_order_events_order_created", "production_order_events", ["order_id", "created_at"])


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "production_order_events" in inspector.get_table_names():
        op.drop_table("production_order_events")
    if "production_order_items" in inspector.get_table_names():
        op.drop_table("production_order_items")
    if "production_orders" in inspector.get_table_names():
        op.drop_table("production_orders")
