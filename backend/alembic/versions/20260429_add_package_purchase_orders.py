"""add package purchase orders

Revision ID: 20260429_add_package_purchase_orders
Revises: 20260429_repair_missing_business_operation_logs
Create Date: 2026-04-29 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260429_add_package_purchase_orders"
down_revision: Union[str, Sequence[str], None] = "20260429_repair_missing_business_operation_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], *, unique: bool = False) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "package_purchase_orders" not in tables:
        op.create_table(
            "package_purchase_orders",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("order_no", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("package_key", sa.String(length=64), nullable=False),
            sa.Column("package_name", sa.String(length=128), nullable=True),
            sa.Column("business_key", sa.String(length=64), nullable=True),
            sa.Column("units", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unit_name", sa.String(length=32), nullable=False, server_default="次"),
            sa.Column("amount_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=16), nullable=False, server_default="CNY"),
            sa.Column("channel", sa.String(length=32), nullable=False, server_default="offline"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("payment_reference", sa.String(length=128), nullable=True),
            sa.Column("transaction_id", sa.String(length=128), nullable=True),
            sa.Column("fail_reason", sa.Text(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.String(length=64), nullable=True),
            sa.Column("created_by_username", sa.String(length=128), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("failed_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("order_no", name="uq_package_purchase_orders_order_no"),
        )

    for index_name, columns in (
        ("ix_package_purchase_orders_order_no", ["order_no"]),
        ("ix_package_purchase_orders_user_id", ["user_id"]),
        ("ix_package_purchase_orders_package_key", ["package_key"]),
        ("ix_package_purchase_orders_business_key", ["business_key"]),
        ("ix_package_purchase_orders_user_created", ["user_id", "created_at"]),
        ("ix_package_purchase_orders_status_created", ["status", "created_at"]),
    ):
        _create_index_if_missing("package_purchase_orders", index_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "package_purchase_orders" in tables:
        op.drop_table("package_purchase_orders")
