"""add business project context tables

Revision ID: 20260602_add_business_project_context
Revises: 20260526_add_business_output_reviews
Create Date: 2026-06-02 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260602_add_business_project_context"
down_revision: Union[str, Sequence[str], None] = "20260526_add_business_output_reviews"
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
    if not _table_exists("business_projects"):
        op.create_table(
            "business_projects",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("scenario", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=True),
            sa.Column("client_id", sa.String(length=64), nullable=True),
            sa.Column("owner_user_id", sa.String(length=64), nullable=True),
            sa.Column("owner_user_name", sa.String(length=128), nullable=True),
            sa.Column("current_flow_step_key", sa.String(length=64), nullable=True),
            sa.Column("flow_template_id", sa.String(length=64), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("business_projects", "ix_business_projects_client_id", ["client_id"])
    _create_index_if_missing("business_projects", "ix_business_projects_created_at", ["created_at"])
    _create_index_if_missing("business_projects", "ix_business_projects_flow_template_id", ["flow_template_id"])
    _create_index_if_missing("business_projects", "ix_business_projects_owner_updated", ["owner_user_id", "updated_at"])
    _create_index_if_missing("business_projects", "ix_business_projects_owner_user_id", ["owner_user_id"])
    _create_index_if_missing("business_projects", "ix_business_projects_scenario", ["scenario"])
    _create_index_if_missing("business_projects", "ix_business_projects_scenario_status_updated", ["scenario", "status", "updated_at"])
    _create_index_if_missing("business_projects", "ix_business_projects_status", ["status"])
    _create_index_if_missing("business_projects", "ix_business_projects_tenant_client_updated", ["tenant_id", "client_id", "updated_at"])
    _create_index_if_missing("business_projects", "ix_business_projects_tenant_id", ["tenant_id"])

    if not _table_exists("business_project_assets"):
        op.create_table(
            "business_project_assets",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=False),
            sa.Column("asset_type", sa.String(length=32), nullable=False),
            sa.Column("url", sa.String(length=1024), nullable=True),
            sa.Column("content_type", sa.String(length=64), nullable=True),
            sa.Column("file_name", sa.String(length=255), nullable=True),
            sa.Column("source_run_id", sa.String(length=64), nullable=True),
            sa.Column("source_business_key", sa.String(length=64), nullable=True),
            sa.Column("source_flow_step_key", sa.String(length=64), nullable=True),
            sa.Column("source_output_index", sa.Integer(), nullable=True),
            sa.Column("quality_grade", sa.String(length=32), nullable=True),
            sa.Column("input_tags", sa.JSON(), nullable=True),
            sa.Column("issue_tags", sa.JSON(), nullable=True),
            sa.Column("selected", sa.Boolean(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["business_projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_run_id"], ["business_runs.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("business_project_assets", "ix_business_project_assets_asset_type", ["asset_type"])
    _create_index_if_missing("business_project_assets", "ix_business_project_assets_created_at", ["created_at"])
    _create_index_if_missing("business_project_assets", "ix_business_project_assets_project_id", ["project_id"])
    _create_index_if_missing("business_project_assets", "ix_business_project_assets_project_selected_updated", ["project_id", "selected", "updated_at"])
    _create_index_if_missing("business_project_assets", "ix_business_project_assets_project_type_created", ["project_id", "asset_type", "created_at"])
    _create_index_if_missing("business_project_assets", "ix_business_project_assets_quality_grade", ["quality_grade"])
    _create_index_if_missing("business_project_assets", "ix_business_project_assets_source_business_key", ["source_business_key"])
    _create_index_if_missing("business_project_assets", "ix_business_project_assets_source_flow_step_key", ["source_flow_step_key"])
    _create_index_if_missing("business_project_assets", "ix_business_project_assets_source_run_id", ["source_run_id"])
    _create_index_if_missing("business_project_assets", "ix_business_project_assets_source_run_output", ["source_run_id", "source_output_index"])

    if not _table_exists("business_project_run_links"):
        op.create_table(
            "business_project_run_links",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("business_key", sa.String(length=64), nullable=False),
            sa.Column("flow_step_key", sa.String(length=64), nullable=True),
            sa.Column("flow_step_name", sa.String(length=128), nullable=True),
            sa.Column("flow_template_id", sa.String(length=64), nullable=True),
            sa.Column("input_asset_ids", sa.JSON(), nullable=True),
            sa.Column("output_asset_ids", sa.JSON(), nullable=True),
            sa.Column("client_request_id", sa.String(length=128), nullable=True),
            sa.Column("asset_sync_status", sa.String(length=32), nullable=False),
            sa.Column("asset_sync_error", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["business_projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["run_id"], ["business_runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("run_id", name="uq_business_project_run_links_run_id"),
        )
    _create_index_if_missing("business_project_run_links", "ix_business_project_run_links_asset_sync_status", ["asset_sync_status"])
    _create_index_if_missing("business_project_run_links", "ix_business_project_run_links_business_created", ["business_key", "created_at"])
    _create_index_if_missing("business_project_run_links", "ix_business_project_run_links_business_key", ["business_key"])
    _create_index_if_missing("business_project_run_links", "ix_business_project_run_links_client_request_id", ["client_request_id"])
    _create_index_if_missing("business_project_run_links", "ix_business_project_run_links_created_at", ["created_at"])
    _create_index_if_missing("business_project_run_links", "ix_business_project_run_links_flow_step_key", ["flow_step_key"])
    _create_index_if_missing("business_project_run_links", "ix_business_project_run_links_flow_template_id", ["flow_template_id"])
    _create_index_if_missing("business_project_run_links", "ix_business_project_run_links_project_client_request", ["project_id", "client_request_id"])
    _create_index_if_missing("business_project_run_links", "ix_business_project_run_links_project_id", ["project_id"])
    _create_index_if_missing("business_project_run_links", "ix_business_project_run_links_project_step_created", ["project_id", "flow_step_key", "created_at"])
    _create_index_if_missing("business_project_run_links", "ix_business_project_run_links_run_id", ["run_id"], unique=True)

    if not _table_exists("business_project_selections"):
        op.create_table(
            "business_project_selections",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=False),
            sa.Column("asset_id", sa.String(length=64), nullable=False),
            sa.Column("source_run_id", sa.String(length=64), nullable=True),
            sa.Column("source_flow_step_key", sa.String(length=64), nullable=True),
            sa.Column("target_flow_step_key", sa.String(length=64), nullable=True),
            sa.Column("selected_by_user_id", sa.String(length=64), nullable=True),
            sa.Column("selected_by_user_name", sa.String(length=128), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["business_project_assets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["business_projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["selected_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["source_run_id"], ["business_runs.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("business_project_selections", "ix_business_project_selections_asset_created", ["asset_id", "created_at"])
    _create_index_if_missing("business_project_selections", "ix_business_project_selections_asset_id", ["asset_id"])
    _create_index_if_missing("business_project_selections", "ix_business_project_selections_created_at", ["created_at"])
    _create_index_if_missing("business_project_selections", "ix_business_project_selections_project_created", ["project_id", "created_at"])
    _create_index_if_missing("business_project_selections", "ix_business_project_selections_project_id", ["project_id"])
    _create_index_if_missing("business_project_selections", "ix_business_project_selections_source_flow_step_key", ["source_flow_step_key"])
    _create_index_if_missing("business_project_selections", "ix_business_project_selections_source_run_id", ["source_run_id"])
    _create_index_if_missing("business_project_selections", "ix_business_project_selections_target_flow_step_key", ["target_flow_step_key"])

    if not _table_exists("business_export_packages"):
        op.create_table(
            "business_export_packages",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("asset_ids", sa.JSON(), nullable=False),
            sa.Column("run_ids", sa.JSON(), nullable=True),
            sa.Column("download_url", sa.String(length=1024), nullable=True),
            sa.Column("manifest", sa.JSON(), nullable=True),
            sa.Column("summary", sa.JSON(), nullable=True),
            sa.Column("error_code", sa.String(length=128), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["business_projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("business_export_packages", "ix_business_export_packages_created_at", ["created_at"])
    _create_index_if_missing("business_export_packages", "ix_business_export_packages_project_created", ["project_id", "created_at"])
    _create_index_if_missing("business_export_packages", "ix_business_export_packages_project_id", ["project_id"])
    _create_index_if_missing("business_export_packages", "ix_business_export_packages_status", ["status"])
    _create_index_if_missing("business_export_packages", "ix_business_export_packages_status_updated", ["status", "updated_at"])


def downgrade() -> None:
    _drop_table_if_present("business_export_packages")
    _drop_table_if_present("business_project_selections")
    _drop_table_if_present("business_project_run_links")
    _drop_table_if_present("business_project_assets")
    _drop_table_if_present("business_projects")
