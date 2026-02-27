"""add comfyui repair jobs and runtime policies

Revision ID: 20260227_add_comfyui_repair_and_policy_tables
Revises: 20260226_add_agent_bootstrap_tables
Create Date: 2026-02-27 10:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260227_add_comfyui_repair_and_policy_tables"
down_revision: Union[str, Sequence[str], None] = "20260226_add_agent_bootstrap_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comfyui_repair_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("manifest_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="additive"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("requested_agent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["manifest_id"], ["agent_manifests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comfyui_repair_jobs_manifest_id", "comfyui_repair_jobs", ["manifest_id"])
    op.create_index("ix_comfyui_repair_jobs_status", "comfyui_repair_jobs", ["status"])
    op.create_index("ix_comfyui_repair_jobs_created_at", "comfyui_repair_jobs", ["created_at"])

    op.create_table(
        "comfyui_repair_job_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("repair_job_id", sa.String(length=64), nullable=False),
        sa.Column("manifest_id", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.String(length=64), nullable=True),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("submit_status", sa.String(length=32), nullable=True),
        sa.Column("callback_status", sa.String(length=32), nullable=True),
        sa.Column("final_status", sa.String(length=32), nullable=True),
        sa.Column("actions", sa.JSON(), nullable=True),
        sa.Column("missing_items", sa.JSON(), nullable=True),
        sa.Column("failed_items", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["repair_job_id"], ["comfyui_repair_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["manifest_id"], ["agent_manifests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_comfyui_repair_job_items_job", "comfyui_repair_job_items", ["repair_job_id"])
    op.create_index("ix_comfyui_repair_job_items_status", "comfyui_repair_job_items", ["status"])
    op.create_index("ix_comfyui_repair_job_items_agent", "comfyui_repair_job_items", ["agent_id"])

    op.create_table(
        "comfyui_runtime_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_type", sa.String(length=32), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_comfyui_runtime_policies_type", "comfyui_runtime_policies", ["policy_type"])


def downgrade() -> None:
    op.drop_index("ix_comfyui_runtime_policies_type", table_name="comfyui_runtime_policies")
    op.drop_table("comfyui_runtime_policies")

    op.drop_index("ix_comfyui_repair_job_items_agent", table_name="comfyui_repair_job_items")
    op.drop_index("ix_comfyui_repair_job_items_status", table_name="comfyui_repair_job_items")
    op.drop_index("ix_comfyui_repair_job_items_job", table_name="comfyui_repair_job_items")
    op.drop_table("comfyui_repair_job_items")

    op.drop_index("ix_comfyui_repair_jobs_created_at", table_name="comfyui_repair_jobs")
    op.drop_index("ix_comfyui_repair_jobs_status", table_name="comfyui_repair_jobs")
    op.drop_index("ix_comfyui_repair_jobs_manifest_id", table_name="comfyui_repair_jobs")
    op.drop_table("comfyui_repair_jobs")
