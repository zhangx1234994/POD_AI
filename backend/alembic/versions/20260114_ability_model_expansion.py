"""expand ability model, executor api keys, and cost fields

Revision ID: 20260114_ability_model_expansion
Revises: 1a5aa64aae5e
Create Date: 2026-01-14 03:30:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "20260114_ability_model_expansion"
down_revision: Union[str, Sequence[str], None] = "1a5aa64aae5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    ability_columns = {col["name"] for col in inspector.get_columns("abilities")}

    added_workflow_fk = False
    if "ability_type" not in ability_columns:
        op.add_column(
            "abilities",
            sa.Column("ability_type", sa.String(length=32), nullable=False, server_default="api"),
        )
        op.alter_column("abilities", "ability_type", server_default=None)
    if "workflow_id" not in ability_columns:
        op.add_column("abilities", sa.Column("workflow_id", sa.String(length=64), nullable=True))
        added_workflow_fk = True
    if "last_health_check_at" not in ability_columns:
        op.add_column("abilities", sa.Column("last_health_check_at", sa.DateTime(), nullable=True))
    if "last_health_status" not in ability_columns:
        op.add_column("abilities", sa.Column("last_health_status", sa.String(length=32), nullable=True))
    if "success_rate" not in ability_columns:
        op.add_column("abilities", sa.Column("success_rate", sa.Float(), nullable=True))

    if added_workflow_fk:
        op.create_foreign_key(
            "fk_abilities_workflow_id",
            "abilities",
            "workflows",
            ["workflow_id"],
            ["id"],
            ondelete="SET NULL",
        )

    log_columns = {col["name"] for col in inspector.get_columns("ability_invocation_logs")}
    if "trace_id" not in log_columns:
        op.add_column("ability_invocation_logs", sa.Column("trace_id", sa.String(length=64), nullable=True))
    if "workflow_run_id" not in log_columns:
        op.add_column("ability_invocation_logs", sa.Column("workflow_run_id", sa.String(length=64), nullable=True))
    if "billing_unit" not in log_columns:
        op.add_column("ability_invocation_logs", sa.Column("billing_unit", sa.String(length=32), nullable=True))
    if "unit_price" not in log_columns:
        op.add_column(
            "ability_invocation_logs",
            sa.Column("unit_price", sa.Numeric(precision=10, scale=4), nullable=True),
        )
    if "currency" not in log_columns:
        op.add_column("ability_invocation_logs", sa.Column("currency", sa.String(length=16), nullable=True))
    if "cost_amount" not in log_columns:
        op.add_column(
            "ability_invocation_logs",
            sa.Column("cost_amount", sa.Numeric(precision=14, scale=4), nullable=True),
        )
    op.create_index(
        "ix_ability_invocation_logs_trace",
        "ability_invocation_logs",
        ["trace_id"],
    )

    op.create_table(
        "executor_api_keys",
        sa.Column(
            "executor_id",
            sa.String(length=64),
            sa.ForeignKey("executors.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "api_key_id",
            sa.String(length=64),
            sa.ForeignKey("api_keys.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=func.now()),
    )

    op.create_table(
        "ability_cost_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "ability_id",
            sa.String(length=64),
            sa.ForeignKey("abilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "executor_id",
            sa.String(length=64),
            sa.ForeignKey("executors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_end", sa.DateTime(), nullable=False),
        sa.Column("invocation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=func.now()),
    )
    op.create_index(
        "ix_ability_cost_snapshots_ability_window",
        "ability_cost_snapshots",
        ["ability_id", "window_start", "window_end"],
    )


def downgrade() -> None:
    op.drop_index("ix_ability_cost_snapshots_ability_window", table_name="ability_cost_snapshots")
    op.drop_table("ability_cost_snapshots")

    op.drop_table("executor_api_keys")

    op.drop_index("ix_ability_invocation_logs_trace", table_name="ability_invocation_logs")
    bind = op.get_bind()
    inspector = inspect(bind)
    log_columns = {col["name"] for col in inspector.get_columns("ability_invocation_logs")}
    if "cost_amount" in log_columns:
        op.drop_column("ability_invocation_logs", "cost_amount")
    if "currency" in log_columns:
        op.drop_column("ability_invocation_logs", "currency")
    if "unit_price" in log_columns:
        op.drop_column("ability_invocation_logs", "unit_price")
    if "billing_unit" in log_columns:
        op.drop_column("ability_invocation_logs", "billing_unit")
    if "workflow_run_id" in log_columns:
        op.drop_column("ability_invocation_logs", "workflow_run_id")
    if "trace_id" in log_columns:
        op.drop_column("ability_invocation_logs", "trace_id")

    ability_columns = {col["name"] for col in inspector.get_columns("abilities")}
    fk_names = {fk["name"] for fk in inspector.get_foreign_keys("abilities")}
    if "fk_abilities_workflow_id" in fk_names:
        op.drop_constraint("fk_abilities_workflow_id", "abilities", type_="foreignkey")
    if "success_rate" in ability_columns:
        op.drop_column("abilities", "success_rate")
    if "last_health_status" in ability_columns:
        op.drop_column("abilities", "last_health_status")
    if "last_health_check_at" in ability_columns:
        op.drop_column("abilities", "last_health_check_at")
    if "workflow_id" in ability_columns:
        op.drop_column("abilities", "workflow_id")
    if "ability_type" in ability_columns:
        op.drop_column("abilities", "ability_type")
