"""add business run version query indexes

Revision ID: 20260512_add_business_run_version_indexes
Revises: 20260512_add_business_api_key_usage
Create Date: 2026-05-12 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260512_add_business_run_version_indexes"
down_revision: Union[str, Sequence[str], None] = "20260512_add_business_api_key_usage"
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
    _create_index_if_missing("business_runs", "ix_business_runs_version_created", ["business_version_id", "created_at"])
    _create_index_if_missing(
        "business_runs",
        "ix_business_runs_version_status_created",
        ["business_version_id", "status", "created_at"],
    )


def downgrade() -> None:
    _drop_index_if_present("business_runs", "ix_business_runs_version_status_created")
    _drop_index_if_present("business_runs", "ix_business_runs_version_created")
