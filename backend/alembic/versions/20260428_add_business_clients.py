"""add business client policy table

Revision ID: 20260428_add_business_clients
Revises: 20260425_add_auth_sessions_invites
Create Date: 2026-04-28 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260428_add_business_clients"
down_revision: Union[str, Sequence[str], None] = "20260425_add_auth_sessions_invites"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "business_clients" not in tables:
        op.create_table(
            "business_clients",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("client_id", sa.String(length=64), nullable=True),
            sa.Column("display_name", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("allowed_business_keys", sa.JSON(), nullable=True),
            sa.Column("daily_run_limit", sa.Integer(), nullable=True),
            sa.Column("daily_quota_units", sa.Integer(), nullable=True),
            sa.Column("concurrent_run_limit", sa.Integer(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_business_clients_tenant_id", "business_clients", ["tenant_id"])
        op.create_index("ix_business_clients_client_id", "business_clients", ["client_id"])
        op.create_index("ix_business_clients_status", "business_clients", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "business_clients" in tables:
        indexes = {item["name"] for item in inspector.get_indexes("business_clients")}
        for index_name in (
            "ix_business_clients_status",
            "ix_business_clients_client_id",
            "ix_business_clients_tenant_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="business_clients")
        op.drop_table("business_clients")
