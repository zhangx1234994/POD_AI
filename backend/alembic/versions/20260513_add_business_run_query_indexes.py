"""add business run list query indexes

Revision ID: 20260513_add_business_run_query_indexes
Revises: 20260512_add_business_run_version_indexes
Create Date: 2026-05-13 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260513_add_business_run_query_indexes"
down_revision: Union[str, Sequence[str], None] = "20260512_add_business_run_version_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)


def _drop_index_if_present(table_name: str, index_name: str) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name in indexes:
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    _create_index_if_missing("business_runs", "ix_business_runs_key_created", ["business_key", "created_at"])
    _create_index_if_missing(
        "business_runs",
        "ix_business_runs_key_status_created",
        ["business_key", "status", "created_at"],
    )
    _create_index_if_missing(
        "business_run_steps",
        "ix_business_run_steps_run_order_id",
        ["run_id", "step_order", "id"],
    )


def downgrade() -> None:
    _drop_index_if_present("business_run_steps", "ix_business_run_steps_run_order_id")
    _drop_index_if_present("business_runs", "ix_business_runs_key_status_created")
    _drop_index_if_present("business_runs", "ix_business_runs_key_created")
