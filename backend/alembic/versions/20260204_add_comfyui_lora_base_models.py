"""add comfyui lora base_models

Revision ID: 20260204_add_comfyui_lora_base_models
Revises: 20260204_add_comfyui_lora_catalog
Create Date: 2026-02-04 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260204_add_comfyui_lora_base_models"
down_revision: Union[str, Sequence[str], None] = "20260204_add_comfyui_lora_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("comfyui_lora_catalog", sa.Column("base_models", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("comfyui_lora_catalog", "base_models")
