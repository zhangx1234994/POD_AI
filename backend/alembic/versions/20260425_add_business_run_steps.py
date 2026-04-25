"""add business run step table

Revision ID: 20260425_add_business_run_steps
Revises: 20260425_add_ability_vendor_model_link
Create Date: 2026-04-25 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260425_add_business_run_steps"
down_revision: Union[str, Sequence[str], None] = "20260425_add_ability_vendor_model_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "business_run_steps" not in tables:
        op.create_table(
            "business_run_steps",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("step_order", sa.Integer(), nullable=False),
            sa.Column("step_id", sa.String(length=64), nullable=True),
            sa.Column("step_type", sa.String(length=64), nullable=False, server_default="ability_task"),
            sa.Column("role", sa.String(length=64), nullable=True),
            sa.Column("display_name", sa.String(length=128), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
            sa.Column("ability_id", sa.String(length=64), nullable=True),
            sa.Column("ability_name", sa.String(length=128), nullable=True),
            sa.Column("ability_provider", sa.String(length=64), nullable=True),
            sa.Column("ability_task_id", sa.String(length=64), nullable=True),
            sa.Column("ability_log_id", sa.Integer(), nullable=True),
            sa.Column("request_payload", sa.JSON(), nullable=True),
            sa.Column("result_payload", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["ability_id"], ["abilities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["ability_task_id"], ["ability_tasks.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["run_id"], ["business_runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_business_run_steps_run_id", "business_run_steps", ["run_id"])
        op.create_index("ix_business_run_steps_status", "business_run_steps", ["status"])
        op.create_index("ix_business_run_steps_created_at", "business_run_steps", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "business_run_steps" in tables:
        op.drop_index("ix_business_run_steps_created_at", table_name="business_run_steps")
        op.drop_index("ix_business_run_steps_status", table_name="business_run_steps")
        op.drop_index("ix_business_run_steps_run_id", table_name="business_run_steps")
        op.drop_table("business_run_steps")
