"""add ability vendor model link

Revision ID: 20260425_add_ability_vendor_model_link
Revises: 20260425_add_vendor_model_catalog
Create Date: 2026-04-25 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260425_add_ability_vendor_model_link"
down_revision: Union[str, Sequence[str], None] = "20260425_add_vendor_model_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("abilities")}
    if "vendor_model_id" not in columns:
        op.add_column("abilities", sa.Column("vendor_model_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_abilities_vendor_model_id",
            "abilities",
            "vendor_model_catalog",
            ["vendor_model_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("abilities")}
    if "vendor_model_id" in columns:
        op.drop_constraint("fk_abilities_vendor_model_id", "abilities", type_="foreignkey")
        op.drop_column("abilities", "vendor_model_id")
