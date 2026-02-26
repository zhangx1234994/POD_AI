"""add eval_batch_output_review table

Revision ID: 20260226_add_eval_batch_output_reviews
Revises: 20260223_add_eval_batch_tables
Create Date: 2026-02-26 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260226_add_eval_batch_output_reviews"
down_revision: Union[str, Sequence[str], None] = "20260223_add_eval_batch_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eval_batch_output_review",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("batch_session_id", sa.String(length=64), nullable=False),
        sa.Column("run_item_id", sa.String(length=64), nullable=False),
        sa.Column("eval_run_id", sa.String(length=64), nullable=True),
        sa.Column("output_index", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_session_id"], ["eval_batch_session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_item_id"], ["eval_batch_run_item.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["eval_run_id"], ["eval_run.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_item_id", "output_index", name="uq_eval_batch_output_review_item_index"),
    )
    op.create_index(
        "ix_eval_batch_output_review_batch",
        "eval_batch_output_review",
        ["batch_session_id"],
    )
    op.create_index(
        "ix_eval_batch_output_review_eval_run_id",
        "eval_batch_output_review",
        ["eval_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_eval_batch_output_review_eval_run_id", table_name="eval_batch_output_review")
    op.drop_index("ix_eval_batch_output_review_batch", table_name="eval_batch_output_review")
    op.drop_table("eval_batch_output_review")

