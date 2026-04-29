"""repair missing business operation logs table

Revision ID: 20260429_repair_missing_business_operation_logs
Revises: 20260429_repair_missing_task_cost_snapshots
Create Date: 2026-04-29 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260429_repair_missing_business_operation_logs"
down_revision: Union[str, Sequence[str], None] = "20260429_repair_missing_task_cost_snapshots"
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

    if "business_operation_logs" not in tables:
        op.create_table(
            "business_operation_logs",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("target_type", sa.String(length=64), nullable=False),
            sa.Column("target_id", sa.String(length=64), nullable=True),
            sa.Column("business_key", sa.String(length=64), nullable=True),
            sa.Column("tenant_id", sa.String(length=64), nullable=True),
            sa.Column("client_id", sa.String(length=64), nullable=True),
            sa.Column("actor_user_id", sa.String(length=64), nullable=True),
            sa.Column("actor_username", sa.String(length=128), nullable=True),
            sa.Column("actor_role", sa.String(length=32), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("before_payload", sa.JSON(), nullable=True),
            sa.Column("after_payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    for index_name, columns in (
        ("ix_business_operation_logs_action", ["action"]),
        ("ix_business_operation_logs_target_type", ["target_type"]),
        ("ix_business_operation_logs_target_id", ["target_id"]),
        ("ix_business_operation_logs_business_key", ["business_key"]),
        ("ix_business_operation_logs_tenant_id", ["tenant_id"]),
        ("ix_business_operation_logs_client_id", ["client_id"]),
        ("ix_business_operation_logs_actor_user_id", ["actor_user_id"]),
        ("ix_business_operation_logs_created_at", ["created_at"]),
    ):
        _create_index_if_missing("business_operation_logs", index_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "business_operation_logs" in set(inspector.get_table_names()):
        op.drop_table("business_operation_logs")
