"""add ability version field

Revision ID: 20260204_add_ability_version
Revises: 20260204_add_comfyui_model_plugin_catalog
Create Date: 2026-02-04 23:55:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260204_add_ability_version"
down_revision: Union[str, Sequence[str], None] = "20260204_add_comfyui_model_plugin_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "abilities",
        sa.Column("version", sa.String(length=32), nullable=False, server_default="v1"),
    )
    op.alter_column("abilities", "version", server_default=None)


def downgrade() -> None:
    op.drop_column("abilities", "version")
