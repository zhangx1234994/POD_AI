"""add comfyui lora catalog table

Revision ID: 20260204_add_comfyui_lora_catalog
Revises: d1b7f6a8c3e1
Create Date: 2026-02-04 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260204_add_comfyui_lora_catalog"
down_revision: Union[str, Sequence[str], None] = "d1b7f6a8c3e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comfyui_lora_catalog",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("file_name", sa.String(length=256), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_model", sa.String(length=256), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("trigger_words", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("file_name", name="uq_comfyui_lora_file_name"),
    )


def downgrade() -> None:
    op.drop_table("comfyui_lora_catalog")
