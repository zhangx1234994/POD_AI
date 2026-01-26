"""add eval_run.result_output_json

Revision ID: 20260126_add_eval_run_output_json
Revises: 20260218_merge_heads
Create Date: 2026-01-26 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260126_add_eval_run_output_json"
down_revision: Union[str, Sequence[str], None] = "20260218_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("eval_run", sa.Column("result_output_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("eval_run", "result_output_json")

