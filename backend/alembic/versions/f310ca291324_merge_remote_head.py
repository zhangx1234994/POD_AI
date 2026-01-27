"""Compat: merge remote alembic head.

Revision ID: f310ca291324
Revises: 20260219_merge_eval_heads
Create Date: 2026-01-27

Why this exists:
- Some environments already have `alembic_version = f310ca291324`.
- If this repo is missing that revision file, `alembic upgrade head` fails with:
  "Can't locate revision identified by 'f310ca291324'".
- This no-op revision restores continuity so the current DB state can be managed
  by the migrations in this repository.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op  # noqa: F401

revision: str = "f310ca291324"
down_revision: Union[str, Sequence[str], None] = "20260219_merge_eval_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

