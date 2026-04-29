"""add billing invoice requests

Revision ID: 20260429_add_billing_invoice_requests
Revises: 20260429_add_package_purchase_orders
Create Date: 2026-04-29 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260429_add_billing_invoice_requests"
down_revision: Union[str, Sequence[str], None] = "20260429_add_package_purchase_orders"
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

    if "billing_invoice_requests" not in tables:
        op.create_table(
            "billing_invoice_requests",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("invoice_no", sa.String(length=128), nullable=True),
            sa.Column("related_order_type", sa.String(length=64), nullable=False, server_default="manual"),
            sa.Column("related_order_id", sa.String(length=64), nullable=True),
            sa.Column("user_id", sa.String(length=64), nullable=True),
            sa.Column("tenant_id", sa.String(length=64), nullable=True),
            sa.Column("client_id", sa.String(length=64), nullable=True),
            sa.Column("business_key", sa.String(length=64), nullable=True),
            sa.Column("invoice_title", sa.String(length=256), nullable=False),
            sa.Column("tax_no", sa.String(length=64), nullable=True),
            sa.Column("invoice_type", sa.String(length=32), nullable=False, server_default="ordinary"),
            sa.Column("amount_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=16), nullable=False, server_default="CNY"),
            sa.Column("delivery_email", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="requested"),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.String(length=64), nullable=True),
            sa.Column("created_by_username", sa.String(length=128), nullable=True),
            sa.Column("issued_by_user_id", sa.String(length=64), nullable=True),
            sa.Column("issued_by_username", sa.String(length=128), nullable=True),
            sa.Column("issued_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("invoice_no", name="uq_billing_invoice_requests_invoice_no"),
        )

    for index_name, columns in (
        ("ix_billing_invoice_requests_status_created", ["status", "created_at"]),
        ("ix_billing_invoice_requests_user_created", ["user_id", "created_at"]),
        ("ix_billing_invoice_requests_related", ["related_order_type", "related_order_id"]),
        ("ix_billing_invoice_requests_business_key", ["business_key"]),
    ):
        _create_index_if_missing("billing_invoice_requests", index_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "billing_invoice_requests" in tables:
        op.drop_table("billing_invoice_requests")
