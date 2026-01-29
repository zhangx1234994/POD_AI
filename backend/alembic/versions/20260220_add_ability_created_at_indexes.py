"""add created_at indexes for ability logs/tasks

Revision ID: 20260220_add_ability_created_at_indexes
Revises: 20260219_merge_eval_heads
Create Date: 2026-02-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260220_add_ability_created_at_indexes"
down_revision: Union[str, Sequence[str], None] = "20260219_merge_eval_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_ability_invocation_logs_created_at",
        "ability_invocation_logs",
        ["created_at"],
    )
    op.create_index(
        "ix_ability_tasks_created_at",
        "ability_tasks",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ability_tasks_created_at", table_name="ability_tasks")
    op.drop_index("ix_ability_invocation_logs_created_at", table_name="ability_invocation_logs")
