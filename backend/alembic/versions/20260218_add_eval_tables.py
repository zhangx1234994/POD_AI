"""add evaluation tables

Revision ID: 20260218_add_eval_tables
Revises: 20260217_add_coze_workflow_id
Create Date: 2026-02-18 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260218_add_eval_tables"
down_revision: Union[str, Sequence[str], None] = "20260217_add_coze_workflow_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "eval_workflow_version" not in tables:
        op.create_table(
            "eval_workflow_version",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("version", sa.String(length=32), nullable=True, server_default="v1"),
            sa.Column("coze_base_url", sa.String(length=512), nullable=True),
            sa.Column("workflow_id", sa.String(length=64), nullable=False),
            sa.Column("parameters_schema", sa.JSON(), nullable=True),
            sa.Column("output_schema", sa.JSON(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("ix_eval_workflow_version_category", "eval_workflow_version", ["category"])
        op.create_index("ix_eval_workflow_version_status", "eval_workflow_version", ["status"])

    if "eval_dataset_item" not in tables:
        op.create_table(
            "eval_dataset_item",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("oss_url", sa.String(length=512), nullable=False),
            sa.Column("meta_json", sa.JSON(), nullable=True),
            sa.Column("created_by", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_eval_dataset_item_category", "eval_dataset_item", ["category"])

    if "eval_run" not in tables:
        op.create_table(
            "eval_run",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("workflow_version_id", sa.String(length=64), nullable=True),
            sa.Column("dataset_item_id", sa.String(length=64), nullable=True),
            sa.Column("input_oss_urls_json", sa.JSON(), nullable=True),
            sa.Column("parameters_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("coze_execute_id", sa.String(length=64), nullable=True),
            sa.Column("coze_debug_url", sa.String(length=512), nullable=True),
            sa.Column("podi_task_id", sa.String(length=64), nullable=True),
            sa.Column("result_image_urls_json", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(
                ["workflow_version_id"],
                ["eval_workflow_version.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["dataset_item_id"],
                ["eval_dataset_item.id"],
                ondelete="SET NULL",
            ),
        )
        op.create_index("ix_eval_run_status", "eval_run", ["status"])
        op.create_index("ix_eval_run_created_at", "eval_run", ["created_at"])
        op.create_index("ix_eval_run_workflow_version_id", "eval_run", ["workflow_version_id"])

    if "eval_annotation" not in tables:
        op.create_table(
            "eval_annotation",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("tags_json", sa.JSON(), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["run_id"], ["eval_run.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_eval_annotation_run_id", "eval_annotation", ["run_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "eval_annotation" in tables:
        op.drop_index("ix_eval_annotation_run_id", table_name="eval_annotation")
        op.drop_table("eval_annotation")

    if "eval_run" in tables:
        op.drop_index("ix_eval_run_workflow_version_id", table_name="eval_run")
        op.drop_index("ix_eval_run_created_at", table_name="eval_run")
        op.drop_index("ix_eval_run_status", table_name="eval_run")
        op.drop_table("eval_run")

    if "eval_dataset_item" in tables:
        op.drop_index("ix_eval_dataset_item_category", table_name="eval_dataset_item")
        op.drop_table("eval_dataset_item")

    if "eval_workflow_version" in tables:
        op.drop_index("ix_eval_workflow_version_status", table_name="eval_workflow_version")
        op.drop_index("ix_eval_workflow_version_category", table_name="eval_workflow_version")
        op.drop_table("eval_workflow_version")

