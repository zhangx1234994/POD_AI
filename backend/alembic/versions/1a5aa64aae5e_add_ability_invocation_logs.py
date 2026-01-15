"""add ability invocation logs table

Revision ID: 1a5aa64aae5e
Revises: 7ef3e2928acd
Create Date: 2026-01-12 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "1a5aa64aae5e"
down_revision: Union[str, Sequence[str], None] = "7ef3e2928acd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ability_invocation_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ability_id", sa.String(length=64), sa.ForeignKey("abilities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ability_provider", sa.String(length=64), nullable=False),
        sa.Column("capability_key", sa.String(length=64), nullable=False),
        sa.Column("ability_name", sa.String(length=128), nullable=True),
        sa.Column("executor_id", sa.String(length=64), sa.ForeignKey("executors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("executor_name", sa.String(length=128), nullable=True),
        sa.Column("executor_type", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="admin-test"),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("stored_url", sa.String(length=512), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("result_assets", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=func.now()),
    )
    op.create_index(
        "ix_ability_invocation_logs_ability_id",
        "ability_invocation_logs",
        ["ability_id", "created_at"],
    )
    op.create_index(
        "ix_ability_invocation_logs_provider_capability",
        "ability_invocation_logs",
        ["ability_provider", "capability_key", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ability_invocation_logs_provider_capability", table_name="ability_invocation_logs")
    op.drop_index("ix_ability_invocation_logs_ability_id", table_name="ability_invocation_logs")
    op.drop_table("ability_invocation_logs")
