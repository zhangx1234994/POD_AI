"""add comfyui version catalog

Revision ID: 20260222_add_comfyui_version_catalog
Revises: 20260221_add_agent_management_tables
Create Date: 2026-02-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260222_add_comfyui_version_catalog"
down_revision: Union[str, Sequence[str], None] = "20260221_add_agent_management_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comfyui_version_catalog",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("commit_sha", sa.String(length=64)),
        sa.Column("repo_url", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("download_url", sa.Text()),
        sa.Column("released_at", sa.DateTime()),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_comfyui_version_catalog_version", "comfyui_version_catalog", ["version"], unique=True)
    op.create_index("ix_comfyui_version_catalog_status", "comfyui_version_catalog", ["status"])


def downgrade() -> None:
    op.drop_index("ix_comfyui_version_catalog_status", table_name="comfyui_version_catalog")
    op.drop_index("ix_comfyui_version_catalog_version", table_name="comfyui_version_catalog")
    op.drop_table("comfyui_version_catalog")
