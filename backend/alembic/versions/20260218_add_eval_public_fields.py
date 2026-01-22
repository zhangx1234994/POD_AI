"""add eval public settings fields (no-op placeholder)

Revision ID: 20260218_add_eval_public_fields
Revises: 20260218_merge_heads
Create Date: 2026-02-18 00:30:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op  # noqa: F401


revision: str = "20260218_add_eval_public_fields"
down_revision: Union[str, Sequence[str], None] = "20260218_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No schema changes: public eval endpoints are controlled by env vars.
    pass


def downgrade() -> None:
    pass

