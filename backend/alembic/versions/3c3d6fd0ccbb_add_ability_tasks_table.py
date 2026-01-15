"""add ability tasks table"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3c3d6fd0ccbb"
down_revision = "1a5aa64aae5e"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "ability_tasks",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("ability_id", sa.String(length=64), nullable=False),
        sa.Column("ability_name", sa.String(length=128), nullable=True),
        sa.Column("ability_provider", sa.String(length=64), nullable=False),
        sa.Column("capability_key", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("user_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("log_id", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("callback_url", sa.String(length=512), nullable=True),
        sa.Column("callback_headers", sa.JSON(), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["ability_id"], ["abilities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ability_tasks_ability_id", "ability_tasks", ["ability_id"])
    op.create_index("ix_ability_tasks_user_id", "ability_tasks", ["user_id"])
    op.create_index("ix_ability_tasks_status", "ability_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ability_tasks_status", table_name="ability_tasks")
    op.drop_index("ix_ability_tasks_user_id", table_name="ability_tasks")
    op.drop_index("ix_ability_tasks_ability_id", table_name="ability_tasks")
    op.drop_table("ability_tasks")
