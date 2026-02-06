"""add agent management tables

Revision ID: 20260221_add_agent_management_tables
Revises: 20260220_add_ability_created_at_indexes
Create Date: 2026-02-21 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260221_add_agent_management_tables"
down_revision: Union[str, Sequence[str], None] = "20260220_add_ability_created_at_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=128)),
        sa.Column("role", sa.String(length=64)),
        sa.Column("host", sa.String(length=128)),
        sa.Column("base_url", sa.Text()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime()),
        sa.Column("last_heartbeat_at", sa.DateTime()),
        sa.Column("last_manifest_version", sa.String(length=64)),
        sa.Column("metrics", sa.JSON()),
        sa.Column("config", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agents_status", "agents", ["status"])
    op.create_index("ix_agents_role", "agents", ["role"])

    op.create_table(
        "agent_manifests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("download_url", sa.Text()),
        sa.Column("content", sa.JSON()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_manifests_role", "agent_manifests", ["role"])
    op.create_index("ix_agent_manifests_version", "agent_manifests", ["version"])

    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("manifest_id", sa.Integer()),
        sa.Column("manifest_url", sa.Text()),
        sa.Column("actions", sa.JSON()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("token_nonce", sa.String(length=64)),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("pushed_at", sa.DateTime()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("request_payload", sa.JSON()),
        sa.Column("result_payload", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["manifest_id"], ["agent_manifests.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_agent_tasks_agent_id", "agent_tasks", ["agent_id"])
    op.create_index("ix_agent_tasks_status", "agent_tasks", ["status"])

    op.create_table(
        "agent_task_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("message", sa.Text()),
        sa.Column("payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_agent_task_events_task_id", "agent_task_events", ["task_id"])

    op.create_table(
        "agent_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_agent_alerts_agent_id", "agent_alerts", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_alerts_agent_id", table_name="agent_alerts")
    op.drop_table("agent_alerts")
    op.drop_index("ix_agent_task_events_task_id", table_name="agent_task_events")
    op.drop_table("agent_task_events")
    op.drop_index("ix_agent_tasks_status", table_name="agent_tasks")
    op.drop_index("ix_agent_tasks_agent_id", table_name="agent_tasks")
    op.drop_table("agent_tasks")
    op.drop_index("ix_agent_manifests_version", table_name="agent_manifests")
    op.drop_index("ix_agent_manifests_role", table_name="agent_manifests")
    op.drop_table("agent_manifests")
    op.drop_index("ix_agents_role", table_name="agents")
    op.drop_index("ix_agents_status", table_name="agents")
    op.drop_table("agents")
