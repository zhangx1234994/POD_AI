"""add eval batch tables

Revision ID: 20260223_add_eval_batch_tables
Revises: 20260222_add_comfyui_version_catalog
Create Date: 2026-02-23 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260223_add_eval_batch_tables"
down_revision: Union[str, Sequence[str], None] = "20260222_add_comfyui_version_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eval_batch_session",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("workflow_version_id", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("planned_image_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repeat_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("planned_run_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("upload_failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("running_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("canceled_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["workflow_version_id"], ["eval_workflow_version.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_eval_batch_session_created_by", "eval_batch_session", ["created_by"])
    op.create_index("ix_eval_batch_session_status", "eval_batch_session", ["status"])
    op.create_index("ix_eval_batch_session_created_at", "eval_batch_session", ["created_at"])

    op.create_table(
        "eval_batch_asset",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("batch_session_id", sa.String(length=64), nullable=False),
        sa.Column("source_key", sa.String(length=191), nullable=False),
        sa.Column("file_name", sa.String(length=256), nullable=False),
        sa.Column("oss_url", sa.String(length=1024), nullable=True),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("upload_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("upload_error_code", sa.String(length=64), nullable=True),
        sa.Column("upload_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_session_id"], ["eval_batch_session.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("batch_session_id", "source_key", name="uq_eval_batch_asset_source"),
    )
    op.create_index("ix_eval_batch_asset_upload_status", "eval_batch_asset", ["upload_status"])
    op.create_index(
        "ix_eval_batch_asset_batch_upload_status",
        "eval_batch_asset",
        ["batch_session_id", "upload_status"],
    )

    op.create_table(
        "eval_batch_run_item",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("batch_session_id", sa.String(length=64), nullable=False),
        sa.Column("asset_id", sa.String(length=64), nullable=False),
        sa.Column("repeat_index", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("eval_run_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_session_id"], ["eval_batch_session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["eval_batch_asset.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["eval_run_id"], ["eval_run.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "batch_session_id",
            "asset_id",
            "repeat_index",
            name="uq_eval_batch_run_item_repeat",
        ),
    )
    op.create_index("ix_eval_batch_run_item_status", "eval_batch_run_item", ["status"])
    op.create_index(
        "ix_eval_batch_run_item_batch_status",
        "eval_batch_run_item",
        ["batch_session_id", "status"],
    )
    op.create_index("ix_eval_batch_run_item_eval_run_id", "eval_batch_run_item", ["eval_run_id"])


def downgrade() -> None:
    op.drop_index("ix_eval_batch_run_item_eval_run_id", table_name="eval_batch_run_item")
    op.drop_index("ix_eval_batch_run_item_batch_status", table_name="eval_batch_run_item")
    op.drop_index("ix_eval_batch_run_item_status", table_name="eval_batch_run_item")
    op.drop_table("eval_batch_run_item")

    op.drop_index("ix_eval_batch_asset_batch_upload_status", table_name="eval_batch_asset")
    op.drop_index("ix_eval_batch_asset_upload_status", table_name="eval_batch_asset")
    op.drop_table("eval_batch_asset")

    op.drop_index("ix_eval_batch_session_created_at", table_name="eval_batch_session")
    op.drop_index("ix_eval_batch_session_status", table_name="eval_batch_session")
    op.drop_index("ix_eval_batch_session_created_by", table_name="eval_batch_session")
    op.drop_table("eval_batch_session")
