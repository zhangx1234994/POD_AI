"""add business api key usage logs and run step indexes

Revision ID: 20260512_add_business_api_key_usage
Revises: 20260512_add_eval_run_query_indexes
Create Date: 2026-05-12 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260512_add_business_api_key_usage"
down_revision: Union[str, Sequence[str], None] = "20260512_add_eval_run_query_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)


def _drop_index_if_present(table_name: str, index_name: str) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name in indexes:
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    _create_index_if_missing(
        "business_run_steps",
        "ix_business_run_steps_run_order_created",
        ["run_id", "step_order", "created_at"],
    )
    _create_index_if_missing(
        "business_run_steps",
        "ix_business_run_steps_run_status_order",
        ["run_id", "status", "step_order"],
    )
    _create_index_if_missing(
        "business_run_steps",
        "ix_business_run_steps_status_updated",
        ["status", "updated_at"],
    )
    _create_index_if_missing("api_keys", "ix_api_keys_provider_key", ["provider", "key"])

    if "business_api_key_usage_logs" not in tables:
        op.create_table(
            "business_api_key_usage_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("api_key_id", sa.String(length=64), nullable=True),
            sa.Column("api_key_name", sa.String(length=128), nullable=True),
            sa.Column("api_key_preview", sa.String(length=32), nullable=True),
            sa.Column("method", sa.String(length=16), nullable=False),
            sa.Column("path", sa.String(length=256), nullable=False),
            sa.Column("status_code", sa.Integer(), nullable=True),
            sa.Column("business_key", sa.String(length=64), nullable=True),
            sa.Column("run_id", sa.String(length=64), nullable=True),
            sa.Column("request_id", sa.String(length=64), nullable=True),
            sa.Column("trace_id", sa.String(length=64), nullable=True),
            sa.Column("tenant_id", sa.String(length=64), nullable=True),
            sa.Column("client_id", sa.String(length=64), nullable=True),
            sa.Column("error_code", sa.String(length=128), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    for index_name, columns in (
        ("ix_business_api_key_usage_logs_api_key_id", ["api_key_id"]),
        ("ix_business_api_key_usage_logs_business_key", ["business_key"]),
        ("ix_business_api_key_usage_logs_run_id", ["run_id"]),
        ("ix_business_api_key_usage_logs_request_id", ["request_id"]),
        ("ix_business_api_key_usage_logs_trace_id", ["trace_id"]),
        ("ix_business_api_key_usage_logs_tenant_id", ["tenant_id"]),
        ("ix_business_api_key_usage_logs_client_id", ["client_id"]),
        ("ix_business_api_key_usage_logs_created_at", ["created_at"]),
    ):
        _create_index_if_missing("business_api_key_usage_logs", index_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "business_api_key_usage_logs" in tables:
        op.drop_table("business_api_key_usage_logs")

    _drop_index_if_present("business_run_steps", "ix_business_run_steps_status_updated")
    _drop_index_if_present("business_run_steps", "ix_business_run_steps_run_status_order")
    _drop_index_if_present("business_run_steps", "ix_business_run_steps_run_order_created")
    _drop_index_if_present("api_keys", "ix_api_keys_provider_key")
