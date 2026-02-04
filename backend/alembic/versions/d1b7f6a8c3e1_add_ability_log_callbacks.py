"""add callback fields to ability invocation logs

Revision ID: d1b7f6a8c3e1
Revises: 20260220_add_ability_created_at_indexes
Create Date: 2026-02-04 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "d1b7f6a8c3e1"
down_revision: Union[str, Sequence[str], None] = "20260220_add_ability_created_at_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {col["name"] for col in inspector.get_columns("ability_invocation_logs")}

    if "callback_status" not in columns:
        op.add_column("ability_invocation_logs", sa.Column("callback_status", sa.String(length=32), nullable=True))
    if "callback_http_status" not in columns:
        op.add_column("ability_invocation_logs", sa.Column("callback_http_status", sa.Integer(), nullable=True))
    if "callback_payload" not in columns:
        op.add_column("ability_invocation_logs", sa.Column("callback_payload", sa.JSON(), nullable=True))
    if "callback_response" not in columns:
        op.add_column("ability_invocation_logs", sa.Column("callback_response", sa.JSON(), nullable=True))
    if "callback_error" not in columns:
        op.add_column("ability_invocation_logs", sa.Column("callback_error", sa.Text(), nullable=True))
    if "callback_started_at" not in columns:
        op.add_column("ability_invocation_logs", sa.Column("callback_started_at", sa.DateTime(), nullable=True))
    if "callback_finished_at" not in columns:
        op.add_column("ability_invocation_logs", sa.Column("callback_finished_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {col["name"] for col in inspector.get_columns("ability_invocation_logs")}

    if "callback_finished_at" in columns:
        op.drop_column("ability_invocation_logs", "callback_finished_at")
    if "callback_started_at" in columns:
        op.drop_column("ability_invocation_logs", "callback_started_at")
    if "callback_error" in columns:
        op.drop_column("ability_invocation_logs", "callback_error")
    if "callback_response" in columns:
        op.drop_column("ability_invocation_logs", "callback_response")
    if "callback_payload" in columns:
        op.drop_column("ability_invocation_logs", "callback_payload")
    if "callback_http_status" in columns:
        op.drop_column("ability_invocation_logs", "callback_http_status")
    if "callback_status" in columns:
        op.drop_column("ability_invocation_logs", "callback_status")
