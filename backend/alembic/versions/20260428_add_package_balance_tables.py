"""add package balance tables

Revision ID: 20260428_add_package_balance_tables
Revises: 20260428_add_business_clients
Create Date: 2026-04-28 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260428_add_package_balance_tables"
down_revision: Union[str, Sequence[str], None] = "20260428_add_business_clients"
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

    if "package_balances" not in tables:
        op.create_table(
            "package_balances",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("package_key", sa.String(length=64), nullable=False),
            sa.Column("package_name", sa.String(length=128), nullable=True),
            sa.Column("business_key", sa.String(length=64), nullable=True),
            sa.Column("total_units", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("used_units", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("frozen_units", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unit_name", sa.String(length=32), nullable=False, server_default="次"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("source", sa.String(length=64), nullable=False, server_default="manual"),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    for index_name, columns in (
        ("ix_package_balances_user_id", ["user_id"]),
        ("ix_package_balances_package_key", ["package_key"]),
        ("ix_package_balances_business_key", ["business_key"]),
        ("ix_package_balances_expires_at", ["expires_at"]),
        ("ix_package_balances_user_package", ["user_id", "package_key"]),
        ("ix_package_balances_user_business", ["user_id", "business_key"]),
        ("ix_package_balances_status_expires", ["status", "expires_at"]),
    ):
        _create_index_if_missing("package_balances", index_name, columns)

    if "package_ledger" not in tables:
        op.create_table(
            "package_ledger",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("package_balance_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("package_key", sa.String(length=64), nullable=False),
            sa.Column("business_key", sa.String(length=64), nullable=True),
            sa.Column("direction", sa.String(length=16), nullable=False),
            sa.Column("units", sa.Integer(), nullable=False),
            sa.Column("balance_after", sa.Integer(), nullable=False),
            sa.Column("related_task_id", sa.String(length=64), nullable=True),
            sa.Column("trace_id", sa.String(length=64), nullable=True),
            sa.Column("source", sa.String(length=64), nullable=False, server_default="manual"),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["package_balance_id"], ["package_balances.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    for index_name, columns in (
        ("ix_package_ledger_package_balance_id", ["package_balance_id"]),
        ("ix_package_ledger_user_id", ["user_id"]),
        ("ix_package_ledger_package_key", ["package_key"]),
        ("ix_package_ledger_business_key", ["business_key"]),
        ("ix_package_ledger_user_created_at", ["user_id", "created_at"]),
        ("ix_package_ledger_trace_id", ["trace_id"]),
        ("ix_package_ledger_task_id", ["related_task_id"]),
    ):
        _create_index_if_missing("package_ledger", index_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "package_ledger" in tables:
        op.drop_table("package_ledger")
    if "package_balances" in tables:
        op.drop_table("package_balances")
