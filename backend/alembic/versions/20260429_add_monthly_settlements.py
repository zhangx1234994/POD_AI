"""add monthly settlements

Revision ID: 20260429_add_monthly_settlements
Revises: 20260428_add_business_default_approvals
Create Date: 2026-04-29 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260429_add_monthly_settlements"
down_revision: Union[str, Sequence[str], None] = "20260428_add_business_default_approvals"
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

    if "monthly_settlements" not in tables:
        op.create_table(
            "monthly_settlements",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("month", sa.String(length=7), nullable=False),
            sa.Column("scope_key", sa.String(length=192), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=True),
            sa.Column("client_id", sa.String(length=64), nullable=True),
            sa.Column("business_key", sa.String(length=64), nullable=True),
            sa.Column("user_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_balance", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_frozen_balance", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_income", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_expense", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_net", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_package_remaining_units", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("issue_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("package_alert_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="issued"),
            sa.Column("payment_reference", sa.String(length=128), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("issued_by_user_id", sa.String(length=64), nullable=True),
            sa.Column("issued_by_username", sa.String(length=128), nullable=True),
            sa.Column("issued_at", sa.DateTime(), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("month", "scope_key", name="uq_monthly_settlements_month_scope"),
        )

    for index_name, columns in (
        ("ix_monthly_settlements_month_status", ["month", "status"]),
        ("ix_monthly_settlements_tenant_client", ["tenant_id", "client_id"]),
        ("ix_monthly_settlements_business_key", ["business_key"]),
    ):
        _create_index_if_missing("monthly_settlements", index_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "monthly_settlements" in tables:
        op.drop_table("monthly_settlements")
