"""add package catalogs

Revision ID: 20260504_add_package_catalogs
Revises: 20260429_add_billing_invoice_requests
Create Date: 2026-05-04 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260504_add_package_catalogs"
down_revision: Union[str, Sequence[str], None] = "20260429_add_billing_invoice_requests"
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

    if "package_catalogs" not in tables:
        op.create_table(
            "package_catalogs",
            sa.Column("package_key", sa.String(length=64), nullable=False),
            sa.Column("package_name", sa.String(length=128), nullable=False),
            sa.Column("business_key", sa.String(length=64), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("units", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unit_name", sa.String(length=32), nullable=False, server_default="次"),
            sa.Column("amount_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=16), nullable=False, server_default="CNY"),
            sa.Column("validity_days", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("package_key"),
        )

    for index_name, columns in (
        ("ix_package_catalogs_business_key", ["business_key"]),
        ("ix_package_catalogs_status", ["status"]),
        ("ix_package_catalogs_sort_order", ["sort_order"]),
    ):
        _create_index_if_missing("package_catalogs", index_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "package_catalogs" in tables:
        op.drop_table("package_catalogs")
