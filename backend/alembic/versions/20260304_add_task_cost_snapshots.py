"""add task cost snapshots

Revision ID: 20260304_add_task_cost_snapshots
Revises: 20260304_add_wallet_billing_tables
Create Date: 2026-03-04 23:40:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260304_add_task_cost_snapshots"
down_revision: Union[str, Sequence[str], None] = "20260304_add_wallet_billing_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
        sa.UniqueConstraint("task_id", name="uq_task_cost_snapshots_task_id"),
    )
    op.create_index("ix_task_cost_snapshots_task_id", "task_cost_snapshots", ["task_id"], unique=True)
    op.create_index("ix_task_cost_snapshots_user_id", "task_cost_snapshots", ["user_id"])
    op.create_index("ix_task_cost_snapshots_provider", "task_cost_snapshots", ["provider"])
    op.create_index("ix_task_cost_snapshots_model_key", "task_cost_snapshots", ["model_key"])
    op.create_index(
        "ix_task_cost_snapshots_user_created",
        "task_cost_snapshots",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_task_cost_snapshots_provider_model",
        "task_cost_snapshots",
        ["provider", "model_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_cost_snapshots_provider_model", table_name="task_cost_snapshots")
    op.drop_index("ix_task_cost_snapshots_user_created", table_name="task_cost_snapshots")
    op.drop_index("ix_task_cost_snapshots_model_key", table_name="task_cost_snapshots")
    op.drop_index("ix_task_cost_snapshots_provider", table_name="task_cost_snapshots")
    op.drop_index("ix_task_cost_snapshots_user_id", table_name="task_cost_snapshots")
    op.drop_index("ix_task_cost_snapshots_task_id", table_name="task_cost_snapshots")
    op.drop_table("task_cost_snapshots")
