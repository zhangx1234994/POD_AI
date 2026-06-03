"""add business agent runtime tables

Revision ID: 20260602_add_business_agent_runtime
Revises: 20260602_add_business_project_context
Create Date: 2026-06-02 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260602_add_business_agent_runtime"
down_revision: Union[str, Sequence[str], None] = "20260602_add_business_project_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], *, unique: bool = False) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def _drop_table_if_present(table_name: str) -> None:
    if _table_exists(table_name):
        op.drop_table(table_name)


def upgrade() -> None:
    if not _table_exists("business_agent_sessions"):
        op.create_table(
            "business_agent_sessions",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("agent_key", sa.String(length=96), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=128), nullable=True),
            sa.Column("image_url", sa.String(length=1024), nullable=True),
            sa.Column("latest_plan_id", sa.String(length=64), nullable=True),
            sa.Column("latest_run_id", sa.String(length=64), nullable=True),
            sa.Column("trace_id", sa.String(length=64), nullable=True),
            sa.Column("request_id", sa.String(length=64), nullable=True),
            sa.Column("tenant_id", sa.String(length=64), nullable=True),
            sa.Column("client_id", sa.String(length=64), nullable=True),
            sa.Column("user_id", sa.String(length=64), nullable=True),
            sa.Column("user_name", sa.String(length=128), nullable=True),
            sa.Column("context", sa.JSON(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["latest_run_id"], ["business_runs.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_agent_key", ["agent_key"])
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_agent_status_updated", ["agent_key", "status", "updated_at"])
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_client_id", ["client_id"])
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_created_at", ["created_at"])
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_latest_plan_id", ["latest_plan_id"])
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_request_id", ["request_id"])
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_status", ["status"])
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_tenant_client_updated", ["tenant_id", "client_id", "updated_at"])
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_tenant_id", ["tenant_id"])
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_trace_id", ["trace_id"])
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_user_id", ["user_id"])
    _create_index_if_missing("business_agent_sessions", "ix_business_agent_sessions_user_updated", ["user_id", "updated_at"])

    if not _table_exists("business_agent_messages"):
        op.create_table(
            "business_agent_messages",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("attachments", sa.JSON(), nullable=True),
            sa.Column("plan_id", sa.String(length=64), nullable=True),
            sa.Column("run_id", sa.String(length=64), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["business_runs.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["session_id"], ["business_agent_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("business_agent_messages", "ix_business_agent_messages_created_at", ["created_at"])
    _create_index_if_missing("business_agent_messages", "ix_business_agent_messages_plan_id", ["plan_id"])
    _create_index_if_missing("business_agent_messages", "ix_business_agent_messages_role", ["role"])
    _create_index_if_missing("business_agent_messages", "ix_business_agent_messages_role_created", ["role", "created_at"])
    _create_index_if_missing("business_agent_messages", "ix_business_agent_messages_run_id", ["run_id"])
    _create_index_if_missing("business_agent_messages", "ix_business_agent_messages_session_created", ["session_id", "created_at"])
    _create_index_if_missing("business_agent_messages", "ix_business_agent_messages_session_id", ["session_id"])

    if not _table_exists("business_agent_plans"):
        op.create_table(
            "business_agent_plans",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("agent_key", sa.String(length=96), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("intent", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=128), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("edit_plan", sa.JSON(), nullable=True),
            sa.Column("tool_name", sa.String(length=96), nullable=False),
            sa.Column("tool_payload", sa.JSON(), nullable=False),
            sa.Column("estimated_cost_level", sa.String(length=32), nullable=True),
            sa.Column("risk_level", sa.String(length=32), nullable=True),
            sa.Column("confirmation_required", sa.Boolean(), nullable=False),
            sa.Column("planner_model", sa.String(length=128), nullable=True),
            sa.Column("planner_mode", sa.String(length=64), nullable=True),
            sa.Column("warnings", sa.JSON(), nullable=True),
            sa.Column("raw_response", sa.JSON(), nullable=True),
            sa.Column("error_code", sa.String(length=128), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("executed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["business_agent_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("business_agent_plans", "ix_business_agent_plans_agent_key", ["agent_key"])
    _create_index_if_missing("business_agent_plans", "ix_business_agent_plans_created_at", ["created_at"])
    _create_index_if_missing("business_agent_plans", "ix_business_agent_plans_intent", ["intent"])
    _create_index_if_missing("business_agent_plans", "ix_business_agent_plans_session_created", ["session_id", "created_at"])
    _create_index_if_missing("business_agent_plans", "ix_business_agent_plans_session_id", ["session_id"])
    _create_index_if_missing("business_agent_plans", "ix_business_agent_plans_status", ["status"])
    _create_index_if_missing("business_agent_plans", "ix_business_agent_plans_status_updated", ["status", "updated_at"])
    _create_index_if_missing("business_agent_plans", "ix_business_agent_plans_tool_created", ["tool_name", "created_at"])
    _create_index_if_missing("business_agent_plans", "ix_business_agent_plans_tool_name", ["tool_name"])

    if not _table_exists("business_agent_tool_calls"):
        op.create_table(
            "business_agent_tool_calls",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("plan_id", sa.String(length=64), nullable=False),
            sa.Column("tool_name", sa.String(length=96), nullable=False),
            sa.Column("business_key", sa.String(length=64), nullable=True),
            sa.Column("run_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("request_payload", sa.JSON(), nullable=True),
            sa.Column("response_payload", sa.JSON(), nullable=True),
            sa.Column("error_code", sa.String(length=128), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["plan_id"], ["business_agent_plans.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["run_id"], ["business_runs.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["session_id"], ["business_agent_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("business_agent_tool_calls", "ix_business_agent_tool_calls_business_created", ["business_key", "created_at"])
    _create_index_if_missing("business_agent_tool_calls", "ix_business_agent_tool_calls_business_key", ["business_key"])
    _create_index_if_missing("business_agent_tool_calls", "ix_business_agent_tool_calls_created_at", ["created_at"])
    _create_index_if_missing("business_agent_tool_calls", "ix_business_agent_tool_calls_plan_created", ["plan_id", "created_at"])
    _create_index_if_missing("business_agent_tool_calls", "ix_business_agent_tool_calls_plan_id", ["plan_id"])
    _create_index_if_missing("business_agent_tool_calls", "ix_business_agent_tool_calls_run_id", ["run_id"])
    _create_index_if_missing("business_agent_tool_calls", "ix_business_agent_tool_calls_session_created", ["session_id", "created_at"])
    _create_index_if_missing("business_agent_tool_calls", "ix_business_agent_tool_calls_session_id", ["session_id"])
    _create_index_if_missing("business_agent_tool_calls", "ix_business_agent_tool_calls_status", ["status"])
    _create_index_if_missing("business_agent_tool_calls", "ix_business_agent_tool_calls_tool_name", ["tool_name"])


def downgrade() -> None:
    _drop_table_if_present("business_agent_tool_calls")
    _drop_table_if_present("business_agent_plans")
    _drop_table_if_present("business_agent_messages")
    _drop_table_if_present("business_agent_sessions")
