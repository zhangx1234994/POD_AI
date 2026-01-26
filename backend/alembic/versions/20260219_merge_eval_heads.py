"""merge eval heads (public fields + output json)

Revision ID: 20260219_merge_eval_heads
Revises: 20260126_add_eval_run_output_json, 20260218_add_eval_public_fields
Create Date: 2026-02-19 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

# Alembic operations are intentionally empty for merge revisions.
from alembic import op  # noqa: F401

revision: str = "20260219_merge_eval_heads"
down_revision: Union[str, Sequence[str], None] = (
    "20260126_add_eval_run_output_json",
    "20260218_add_eval_public_fields",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

