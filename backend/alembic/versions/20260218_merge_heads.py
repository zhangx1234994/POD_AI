"""merge heads after eval tables

Revision ID: 20260218_merge_heads
Revises: 3c3d6fd0ccbb, 20260218_add_eval_tables
Create Date: 2026-02-18 00:10:00.000000

"""

from collections.abc import Sequence
from typing import Union

# Alembic operations are intentionally empty for merge revisions.
from alembic import op  # noqa: F401


revision: str = "20260218_merge_heads"
down_revision: Union[str, Sequence[str], None] = ("3c3d6fd0ccbb", "20260218_add_eval_tables")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

