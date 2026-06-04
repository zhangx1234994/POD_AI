"""add business agent message request id

Revision ID: 20260604_add_business_agent_message_request_id
Revises: 20260602_add_business_agent_runtime
Create Date: 2026-06-04 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260604_add_business_agent_message_request_id"
down_revision: Union[str, Sequence[str], None] = "20260602_add_business_agent_runtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(item["name"] == column_name for item in inspector.get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return index_name in {item["name"] for item in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _table_exists("business_agent_messages"):
        return
    if not _column_exists("business_agent_messages", "request_id"):
        op.add_column("business_agent_messages", sa.Column("request_id", sa.String(length=128), nullable=True))
    if not _index_exists("business_agent_messages", "ix_business_agent_messages_request_id"):
        op.create_index("ix_business_agent_messages_request_id", "business_agent_messages", ["request_id"], unique=False)
    if not _index_exists("business_agent_messages", "uq_business_agent_messages_session_request"):
        op.create_index(
            "uq_business_agent_messages_session_request",
            "business_agent_messages",
            ["session_id", "request_id"],
            unique=True,
        )


def downgrade() -> None:
    if not _table_exists("business_agent_messages"):
        return
    if _index_exists("business_agent_messages", "uq_business_agent_messages_session_request"):
        op.drop_index("uq_business_agent_messages_session_request", table_name="business_agent_messages")
    if _index_exists("business_agent_messages", "ix_business_agent_messages_request_id"):
        op.drop_index("ix_business_agent_messages_request_id", table_name="business_agent_messages")
    if _column_exists("business_agent_messages", "request_id"):
        op.drop_column("business_agent_messages", "request_id")
