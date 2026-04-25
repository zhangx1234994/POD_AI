"""add auth sessions, invite codes, and tenant fields

Revision ID: 20260425_add_auth_sessions_invites
Revises: 20260425_add_business_run_observability
Create Date: 2026-04-25 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260425_add_auth_sessions_invites"
down_revision: Union[str, Sequence[str], None] = "20260425_add_business_run_observability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table_name: str, column_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column_name not in columns:
        op.add_column(table_name, column)


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

    if "users" in tables:
        _add_column_if_missing("users", "display_name", sa.Column("display_name", sa.String(length=128), nullable=True))
        _add_column_if_missing("users", "tenant_id", sa.Column("tenant_id", sa.String(length=64), nullable=True))
        _add_column_if_missing("users", "client_id", sa.Column("client_id", sa.String(length=64), nullable=True))
        _create_index_if_missing("users", "ix_users_tenant_id", ["tenant_id"])
        _create_index_if_missing("users", "ix_users_client_id", ["client_id"])

    if "user_sessions" not in tables:
        op.create_table(
            "user_sessions",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("refresh_jti", sa.String(length=64), nullable=False),
            sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("user_sessions", "ix_user_sessions_user_id", ["user_id"])
    _create_index_if_missing("user_sessions", "ix_user_sessions_refresh_jti", ["refresh_jti"], unique=True)
    _create_index_if_missing("user_sessions", "ix_user_sessions_status", ["status"])
    _create_index_if_missing("user_sessions", "ix_user_sessions_expires_at", ["expires_at"])

    if "invite_codes" not in tables:
        op.create_table(
            "invite_codes",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
            sa.Column("tenant_id", sa.String(length=64), nullable=True),
            sa.Column("client_id", sa.String(length=64), nullable=True),
            sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.String(length=64), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("invite_codes", "ix_invite_codes_code", ["code"], unique=True)
    _create_index_if_missing("invite_codes", "ix_invite_codes_tenant_id", ["tenant_id"])
    _create_index_if_missing("invite_codes", "ix_invite_codes_client_id", ["client_id"])
    _create_index_if_missing("invite_codes", "ix_invite_codes_status", ["status"])
    _create_index_if_missing("invite_codes", "ix_invite_codes_expires_at", ["expires_at"])
    _create_index_if_missing("invite_codes", "ix_invite_codes_created_by", ["created_by"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "invite_codes" in tables:
        for index_name in (
            "ix_invite_codes_created_by",
            "ix_invite_codes_expires_at",
            "ix_invite_codes_status",
            "ix_invite_codes_client_id",
            "ix_invite_codes_tenant_id",
            "ix_invite_codes_code",
        ):
            try:
                op.drop_index(index_name, table_name="invite_codes")
            except Exception:
                pass
        op.drop_table("invite_codes")

    if "user_sessions" in tables:
        for index_name in (
            "ix_user_sessions_expires_at",
            "ix_user_sessions_status",
            "ix_user_sessions_refresh_jti",
            "ix_user_sessions_user_id",
        ):
            try:
                op.drop_index(index_name, table_name="user_sessions")
            except Exception:
                pass
        op.drop_table("user_sessions")

    if "users" in tables:
        columns = {item["name"] for item in inspector.get_columns("users")}
        indexes = {item["name"] for item in inspector.get_indexes("users")}
        if "ix_users_client_id" in indexes:
            op.drop_index("ix_users_client_id", table_name="users")
        if "ix_users_tenant_id" in indexes:
            op.drop_index("ix_users_tenant_id", table_name="users")
        if "client_id" in columns:
            op.drop_column("users", "client_id")
        if "tenant_id" in columns:
            op.drop_column("users", "tenant_id")
        if "display_name" in columns:
            op.drop_column("users", "display_name")
