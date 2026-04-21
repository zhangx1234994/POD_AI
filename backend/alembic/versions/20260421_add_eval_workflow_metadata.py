"""add metadata column to eval workflow version

Revision ID: 20260421_add_eval_workflow_metadata
Revises: 20260416_dedupe_eval_workflow_versions
Create Date: 2026-04-21 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260421_add_eval_workflow_metadata"
down_revision: Union[str, Sequence[str], None] = "20260416_dedupe_eval_workflow_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("eval_workflow_version")}
    if "metadata" not in columns:
        op.add_column("eval_workflow_version", sa.Column("metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("eval_workflow_version")}
    if "metadata" in columns:
        op.drop_column("eval_workflow_version", "metadata")
