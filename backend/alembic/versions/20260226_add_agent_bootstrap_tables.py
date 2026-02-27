"""add agent bootstrap and desktop release tables

Revision ID: 20260226_add_agent_bootstrap_tables
Revises: 20260226_add_eval_batch_output_reviews
Create Date: 2026-02-26 22:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260226_add_agent_bootstrap_tables"
down_revision: Union[str, Sequence[str], None] = "20260226_add_eval_batch_output_reviews"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_enroll_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=128), nullable=False, unique=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("note", sa.Text()),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime()),
        sa.Column("used_by_agent_id", sa.String(length=64)),
        sa.Column("created_by", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_enroll_codes_role", "agent_enroll_codes", ["role"])
    op.create_index("ix_agent_enroll_codes_status", "agent_enroll_codes", ["status"])
    op.create_index("ix_agent_enroll_codes_expires_at", "agent_enroll_codes", ["expires_at"])

    op.create_table(
        "agent_desktop_releases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="stable"),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("os_type", sa.String(length=32), nullable=False, server_default="windows"),
        sa.Column("arch", sa.String(length=32), nullable=False, server_default="x64"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("download_url", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=128), nullable=False),
        sa.Column("min_agent_version", sa.String(length=64)),
        sa.Column("notes", sa.Text()),
        sa.Column("payload", sa.JSON()),
        sa.Column("published_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_desktop_releases_channel", "agent_desktop_releases", ["channel"])
    op.create_index("ix_agent_desktop_releases_status", "agent_desktop_releases", ["status"])
    op.create_index("ix_agent_desktop_releases_platform", "agent_desktop_releases", ["os_type", "arch"])


def downgrade() -> None:
    op.drop_index("ix_agent_desktop_releases_platform", table_name="agent_desktop_releases")
    op.drop_index("ix_agent_desktop_releases_status", table_name="agent_desktop_releases")
    op.drop_index("ix_agent_desktop_releases_channel", table_name="agent_desktop_releases")
    op.drop_table("agent_desktop_releases")

    op.drop_index("ix_agent_enroll_codes_expires_at", table_name="agent_enroll_codes")
    op.drop_index("ix_agent_enroll_codes_status", table_name="agent_enroll_codes")
    op.drop_index("ix_agent_enroll_codes_role", table_name="agent_enroll_codes")
    op.drop_table("agent_enroll_codes")
