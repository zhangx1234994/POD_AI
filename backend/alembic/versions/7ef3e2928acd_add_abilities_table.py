"""add abilities table

Revision ID: 7ef3e2928acd
Revises: dc175558f682
Create Date: 2026-01-08 00:27:35.576678

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = '7ef3e2928acd'
down_revision: Union[str, Sequence[str], None] = 'dc175558f682'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "abilities",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("capability_key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="inactive"),
        sa.Column("executor_id", sa.String(length=64), sa.ForeignKey("executors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("default_params", sa.JSON(), nullable=True),
        sa.Column("input_schema", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=func.now()),
    )
    op.create_index("ix_abilities_provider_capability", "abilities", ["provider", "capability_key"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_abilities_provider_capability", table_name="abilities")
    op.drop_table("abilities")
