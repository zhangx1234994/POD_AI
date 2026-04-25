"""add business capability and run tables

Revision ID: 20260424_add_business_capabilities
Revises: 20260421_add_eval_workflow_metadata
Create Date: 2026-04-24 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260424_add_business_capabilities"
down_revision: Union[str, Sequence[str], None] = "20260421_add_eval_workflow_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "business_capabilities" not in tables:
        op.create_table(
            "business_capabilities",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("business_key", sa.String(length=64), nullable=False),
            sa.Column("version", sa.String(length=32), nullable=False),
            sa.Column("display_name", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="inactive"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("release_time", sa.DateTime(), nullable=True),
            sa.Column("recipe", sa.JSON(), nullable=False),
            sa.Column("input_schema", sa.JSON(), nullable=True),
            sa.Column("output_schema", sa.JSON(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("business_key", "version", name="uq_business_capability_key_version"),
        )
        op.create_index("ix_business_capabilities_business_key", "business_capabilities", ["business_key"])

    if "business_runs" not in tables:
        op.create_table(
            "business_runs",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("business_key", sa.String(length=64), nullable=False),
            sa.Column("business_version_id", sa.String(length=64), nullable=True),
            sa.Column("version", sa.String(length=32), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("source", sa.String(length=64), nullable=False, server_default="business-api"),
            sa.Column("user_id", sa.String(length=64), nullable=True),
            sa.Column("user_name", sa.String(length=128), nullable=True),
            sa.Column("ability_id", sa.String(length=64), nullable=True),
            sa.Column("ability_task_id", sa.String(length=64), nullable=True),
            sa.Column("ability_log_id", sa.Integer(), nullable=True),
            sa.Column("request_payload", sa.JSON(), nullable=True),
            sa.Column("result_payload", sa.JSON(), nullable=True),
            sa.Column("image_urls", sa.JSON(), nullable=True),
            sa.Column("video_urls", sa.JSON(), nullable=True),
            sa.Column("texts", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("callback_url", sa.String(length=512), nullable=True),
            sa.Column("callback_headers", sa.JSON(), nullable=True),
            sa.Column("callback_status", sa.String(length=32), nullable=True),
            sa.Column("callback_http_status", sa.Integer(), nullable=True),
            sa.Column("callback_payload", sa.JSON(), nullable=True),
            sa.Column("callback_response", sa.JSON(), nullable=True),
            sa.Column("callback_error", sa.Text(), nullable=True),
            sa.Column("debug_url", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["ability_id"], ["abilities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["ability_task_id"], ["ability_tasks.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["business_version_id"], ["business_capabilities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_business_runs_business_key", "business_runs", ["business_key"])
        op.create_index("ix_business_runs_status", "business_runs", ["status"])
        op.create_index("ix_business_runs_created_at", "business_runs", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "business_runs" in tables:
        op.drop_index("ix_business_runs_created_at", table_name="business_runs")
        op.drop_index("ix_business_runs_status", table_name="business_runs")
        op.drop_index("ix_business_runs_business_key", table_name="business_runs")
        op.drop_table("business_runs")
    if "business_capabilities" in tables:
        op.drop_index("ix_business_capabilities_business_key", table_name="business_capabilities")
        op.drop_table("business_capabilities")
