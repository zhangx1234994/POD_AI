"""add business default approvals

Revision ID: 20260428_add_business_default_approvals
Revises: 20260428_add_package_balance_tables
Create Date: 2026-04-28 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260428_add_business_default_approvals"
down_revision: Union[str, Sequence[str], None] = "20260428_add_package_balance_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], *, unique: bool = False) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "business_default_approvals" not in tables:
        op.create_table(
            "business_default_approvals",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("business_key", sa.String(length=64), nullable=False),
            sa.Column("source_capability_id", sa.String(length=64), nullable=True),
            sa.Column("target_capability_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("requester_user_id", sa.String(length=64), nullable=True),
            sa.Column("requester_username", sa.String(length=128), nullable=True),
            sa.Column("approver_user_id", sa.String(length=64), nullable=True),
            sa.Column("approver_username", sa.String(length=128), nullable=True),
            sa.Column("request_note", sa.Text(), nullable=True),
            sa.Column("decision_note", sa.Text(), nullable=True),
            sa.Column("before_payload", sa.JSON(), nullable=True),
            sa.Column("after_payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("applied_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["source_capability_id"], ["business_capabilities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["target_capability_id"], ["business_capabilities.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    for index_name, columns in (
        ("ix_business_default_approvals_business_key", ["business_key"]),
        ("ix_business_default_approvals_source_capability_id", ["source_capability_id"]),
        ("ix_business_default_approvals_target_capability_id", ["target_capability_id"]),
        ("ix_business_default_approvals_status", ["status"]),
        ("ix_business_default_approvals_requester_user_id", ["requester_user_id"]),
        ("ix_business_default_approvals_approver_user_id", ["approver_user_id"]),
        ("ix_business_default_approvals_created_at", ["created_at"]),
        ("ix_business_default_approvals_status_business", ["status", "business_key"]),
    ):
        _create_index_if_missing("business_default_approvals", index_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "business_default_approvals" in set(inspector.get_table_names()):
        op.drop_table("business_default_approvals")
