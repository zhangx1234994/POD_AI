"""repair missing task cost snapshots table

Revision ID: 20260429_repair_missing_task_cost_snapshots
Revises: 20260429_add_billing_notification_logs
Create Date: 2026-04-29 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260429_repair_missing_task_cost_snapshots"
down_revision: Union[str, Sequence[str], None] = "20260429_add_billing_notification_logs"
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

    if "task_cost_snapshots" not in tables:
        op.create_table(
            "task_cost_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("task_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("model_key", sa.String(length=128), nullable=False),
            sa.Column("input_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unit_cost", sa.Numeric(precision=18, scale=6), nullable=True),
            sa.Column("total_cost", sa.Numeric(precision=18, scale=4), nullable=True),
            sa.Column("pricing_version", sa.String(length=32), nullable=False, server_default="v1"),
            sa.Column("currency", sa.String(length=16), nullable=False, server_default="USD"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_id", name="uq_task_cost_snapshots_task_id"),
        )

    for index_name, columns, unique in (
        ("ix_task_cost_snapshots_task_id", ["task_id"], True),
        ("ix_task_cost_snapshots_user_id", ["user_id"], False),
        ("ix_task_cost_snapshots_provider", ["provider"], False),
        ("ix_task_cost_snapshots_model_key", ["model_key"], False),
        ("ix_task_cost_snapshots_user_created", ["user_id", "created_at"], False),
        ("ix_task_cost_snapshots_provider_model", ["provider", "model_key"], False),
    ):
        _create_index_if_missing("task_cost_snapshots", index_name, columns, unique=unique)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "task_cost_snapshots" in set(inspector.get_table_names()):
        op.drop_table("task_cost_snapshots")
