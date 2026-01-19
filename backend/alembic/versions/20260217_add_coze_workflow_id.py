"""add coze workflow id mapping to abilities

Revision ID: 20260217_add_coze_workflow_id
Revises: 20260114_ability_model_expansion
Create Date: 2026-02-17 03:30:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260217_add_coze_workflow_id"
down_revision: Union[str, Sequence[str], None] = "20260114_ability_model_expansion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    ability_columns = {column["name"] for column in inspector.get_columns("abilities")}

    if "coze_workflow_id" not in ability_columns:
        op.add_column("abilities", sa.Column("coze_workflow_id", sa.String(length=64), nullable=True))
        op.create_index(
            "ix_abilities_coze_workflow_id",
            "abilities",
            ["coze_workflow_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    ability_columns = {column["name"] for column in inspector.get_columns("abilities")}
    indexes = {index["name"] for index in inspector.get_indexes("abilities")}

    if "ix_abilities_coze_workflow_id" in indexes:
        op.drop_index("ix_abilities_coze_workflow_id", table_name="abilities")
    if "coze_workflow_id" in ability_columns:
        op.drop_column("abilities", "coze_workflow_id")
