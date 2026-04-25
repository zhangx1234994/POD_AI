"""add business run observability and cost fields

Revision ID: 20260425_add_business_run_observability
Revises: 20260425_add_business_run_steps
Create Date: 2026-04-25 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260425_add_business_run_observability"
down_revision: Union[str, Sequence[str], None] = "20260425_add_business_run_steps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table_name: str, column_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column_name not in columns:
        op.add_column(table_name, column)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "business_runs" in tables:
        _add_column_if_missing("business_runs", "channel", sa.Column("channel", sa.String(length=64), nullable=True))
        _add_column_if_missing("business_runs", "trace_id", sa.Column("trace_id", sa.String(length=64), nullable=True))
        _add_column_if_missing("business_runs", "request_id", sa.Column("request_id", sa.String(length=64), nullable=True))
        _add_column_if_missing("business_runs", "tenant_id", sa.Column("tenant_id", sa.String(length=64), nullable=True))
        _add_column_if_missing("business_runs", "client_id", sa.Column("client_id", sa.String(length=64), nullable=True))
        _add_column_if_missing("business_runs", "duration_ms", sa.Column("duration_ms", sa.Integer(), nullable=True))
        _add_column_if_missing("business_runs", "billing_unit", sa.Column("billing_unit", sa.String(length=32), nullable=True))
        _add_column_if_missing("business_runs", "unit_price", sa.Column("unit_price", sa.Numeric(precision=14, scale=6), nullable=True))
        _add_column_if_missing("business_runs", "currency", sa.Column("currency", sa.String(length=16), nullable=True))
        _add_column_if_missing("business_runs", "cost_amount", sa.Column("cost_amount", sa.Numeric(precision=14, scale=4), nullable=True))
        _add_column_if_missing("business_runs", "quota_units", sa.Column("quota_units", sa.Integer(), nullable=True))
        _add_column_if_missing("business_runs", "cost_breakdown", sa.Column("cost_breakdown", sa.JSON(), nullable=True))
        _create_index_if_missing("business_runs", "ix_business_runs_trace_id", ["trace_id"])
        _create_index_if_missing("business_runs", "ix_business_runs_request_id", ["request_id"])
        _create_index_if_missing("business_runs", "ix_business_runs_tenant_id", ["tenant_id"])
        _create_index_if_missing("business_runs", "ix_business_runs_client_id", ["client_id"])

    if "business_run_steps" in tables:
        _add_column_if_missing("business_run_steps", "duration_ms", sa.Column("duration_ms", sa.Integer(), nullable=True))
        _add_column_if_missing("business_run_steps", "billing_unit", sa.Column("billing_unit", sa.String(length=32), nullable=True))
        _add_column_if_missing(
            "business_run_steps",
            "unit_price",
            sa.Column("unit_price", sa.Numeric(precision=14, scale=6), nullable=True),
        )
        _add_column_if_missing("business_run_steps", "currency", sa.Column("currency", sa.String(length=16), nullable=True))
        _add_column_if_missing(
            "business_run_steps",
            "cost_amount",
            sa.Column("cost_amount", sa.Numeric(precision=14, scale=4), nullable=True),
        )
        _add_column_if_missing("business_run_steps", "quota_units", sa.Column("quota_units", sa.Integer(), nullable=True))
        _add_column_if_missing("business_run_steps", "cost_breakdown", sa.Column("cost_breakdown", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "business_runs" in tables:
        indexes = {item["name"] for item in inspector.get_indexes("business_runs")}
        for index_name in (
            "ix_business_runs_client_id",
            "ix_business_runs_tenant_id",
            "ix_business_runs_request_id",
            "ix_business_runs_trace_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="business_runs")
        columns = {item["name"] for item in inspector.get_columns("business_runs")}
        for column_name in (
            "cost_breakdown",
            "quota_units",
            "cost_amount",
            "currency",
            "unit_price",
            "billing_unit",
            "duration_ms",
            "client_id",
            "tenant_id",
            "request_id",
            "trace_id",
            "channel",
        ):
            if column_name in columns:
                op.drop_column("business_runs", column_name)

    if "business_run_steps" in tables:
        columns = {item["name"] for item in inspector.get_columns("business_run_steps")}
        for column_name in (
            "cost_breakdown",
            "quota_units",
            "cost_amount",
            "currency",
            "unit_price",
            "billing_unit",
            "duration_ms",
        ):
            if column_name in columns:
                op.drop_column("business_run_steps", column_name)
