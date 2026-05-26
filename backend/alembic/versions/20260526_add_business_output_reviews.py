"""add business output reviews

Revision ID: 20260526_add_business_output_reviews
Revises: 20260518_add_ability_log_query_indexes
Create Date: 2026-05-26 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260526_add_business_output_reviews"
down_revision: Union[str, Sequence[str], None] = "20260518_add_ability_log_query_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return column_name in {item["name"] for item in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_present(table_name: str, column_name: str) -> None:
    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def _drop_index_if_present(table_name: str, index_name: str) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name in indexes:
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    if not _table_exists("business_output_reviews"):
        op.create_table(
            "business_output_reviews",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("business_key", sa.String(length=64), nullable=False),
            sa.Column("business_version_id", sa.String(length=64), nullable=True),
            sa.Column("version", sa.String(length=32), nullable=True),
            sa.Column("output_index", sa.Integer(), nullable=False),
            sa.Column("output_url", sa.String(length=1024), nullable=True),
            sa.Column("sample_key", sa.String(length=64), nullable=True),
            sa.Column("sample_label", sa.String(length=128), nullable=True),
            sa.Column("batch_id", sa.String(length=64), nullable=True),
            sa.Column("quality_grade", sa.String(length=32), nullable=False),
            sa.Column("input_tags", sa.JSON(), nullable=True),
            sa.Column("issue_tags", sa.JSON(), nullable=True),
            sa.Column("next_action", sa.String(length=64), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("reviewer_user_id", sa.String(length=64), nullable=True),
            sa.Column("reviewer_username", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["business_version_id"], ["business_capabilities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["run_id"], ["business_runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("run_id", "output_index", name="uq_business_output_review_run_output"),
        )
    else:
        _add_column_if_missing("business_output_reviews", sa.Column("sample_key", sa.String(length=64), nullable=True))
        _add_column_if_missing("business_output_reviews", sa.Column("sample_label", sa.String(length=128), nullable=True))
        _add_column_if_missing("business_output_reviews", sa.Column("batch_id", sa.String(length=64), nullable=True))
    _create_index_if_missing("business_output_reviews", "ix_business_output_reviews_business_created", ["business_key", "created_at"])
    _create_index_if_missing("business_output_reviews", "ix_business_output_reviews_batch_created", ["batch_id", "created_at"])
    _create_index_if_missing("business_output_reviews", "ix_business_output_reviews_created_at", ["created_at"])
    _create_index_if_missing("business_output_reviews", "ix_business_output_reviews_grade_created", ["quality_grade", "created_at"])
    _create_index_if_missing("business_output_reviews", "ix_business_output_reviews_quality_grade", ["quality_grade"])
    _create_index_if_missing("business_output_reviews", "ix_business_output_reviews_run_id", ["run_id"])
    _create_index_if_missing("business_output_reviews", "ix_business_output_reviews_business_key", ["business_key"])
    _create_index_if_missing("business_output_reviews", "ix_business_output_reviews_version_created", ["business_version_id", "created_at"])
    if not _table_exists("business_quality_samples"):
        op.create_table(
            "business_quality_samples",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("business_key", sa.String(length=64), nullable=False),
            sa.Column("sample_key", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("image_url", sa.String(length=1024), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=True),
            sa.Column("generated_image_url", sa.String(length=1024), nullable=True),
            sa.Column("input_tags", sa.JSON(), nullable=True),
            sa.Column("default_params", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("created_by_user_id", sa.String(length=64), nullable=True),
            sa.Column("created_by_username", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("business_key", "sample_key", name="uq_business_quality_sample_business_key"),
        )
    _create_index_if_missing("business_quality_samples", "ix_business_quality_samples_business_key", ["business_key"])
    _create_index_if_missing("business_quality_samples", "ix_business_quality_samples_sample_key", ["sample_key"])
    _create_index_if_missing("business_quality_samples", "ix_business_quality_samples_status", ["status"])
    _create_index_if_missing("business_quality_samples", "ix_business_quality_samples_created_at", ["created_at"])
    _create_index_if_missing("business_quality_samples", "ix_business_quality_samples_business_status", ["business_key", "status"])
    _create_index_if_missing("business_quality_samples", "ix_business_quality_samples_business_sort", ["business_key", "sort_order", "created_at"])
    if not _table_exists("business_quality_sample_versions"):
        op.create_table(
            "business_quality_sample_versions",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("sample_id", sa.String(length=64), nullable=False),
            sa.Column("business_key", sa.String(length=64), nullable=False),
            sa.Column("sample_key", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("image_url", sa.String(length=1024), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=True),
            sa.Column("generated_image_url", sa.String(length=1024), nullable=True),
            sa.Column("input_tags", sa.JSON(), nullable=True),
            sa.Column("default_params", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("change_type", sa.String(length=32), nullable=False),
            sa.Column("change_note", sa.Text(), nullable=True),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", sa.String(length=64), nullable=True),
            sa.Column("actor_username", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["sample_id"], ["business_quality_samples.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("business_quality_sample_versions", "ix_business_quality_sample_versions_sample_id", ["sample_id"])
    _create_index_if_missing("business_quality_sample_versions", "ix_business_quality_sample_versions_business_key", ["business_key", "sample_key"])
    _create_index_if_missing("business_quality_sample_versions", "ix_business_quality_sample_versions_change_type", ["change_type"])
    _create_index_if_missing("business_quality_sample_versions", "ix_business_quality_sample_versions_created_at", ["created_at"])
    _create_index_if_missing("business_quality_sample_versions", "ix_business_quality_sample_versions_sample_created", ["sample_id", "created_at"])
    if not _table_exists("business_quality_action_rules"):
        op.create_table(
            "business_quality_action_rules",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("business_key", sa.String(length=64), nullable=False),
            sa.Column("rule_key", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("issue_tags", sa.JSON(), nullable=True),
            sa.Column("input_tags", sa.JSON(), nullable=True),
            sa.Column("action_type", sa.String(length=64), nullable=False),
            sa.Column("target_business_version_id", sa.String(length=64), nullable=True),
            sa.Column("target_version", sa.String(length=32), nullable=True),
            sa.Column("target_label", sa.String(length=128), nullable=True),
            sa.Column("target_ref", sa.String(length=128), nullable=True),
            sa.Column("target_params", sa.JSON(), nullable=True),
            sa.Column("sample_batch_id", sa.String(length=64), nullable=True),
            sa.Column("evidence_review_ids", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False),
            sa.Column("owner_user_id", sa.String(length=64), nullable=True),
            sa.Column("owner_username", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["target_business_version_id"], ["business_capabilities.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("business_key", "rule_key", name="uq_business_quality_action_business_key"),
        )
    _create_index_if_missing("business_quality_action_rules", "ix_business_quality_action_rules_action_type", ["action_type"])
    _create_index_if_missing("business_quality_action_rules", "ix_business_quality_action_rules_business_key", ["business_key"])
    _create_index_if_missing("business_quality_action_rules", "ix_business_quality_action_rules_created_at", ["created_at"])
    _create_index_if_missing("business_quality_action_rules", "ix_business_quality_action_rules_rule_key", ["rule_key"])
    _create_index_if_missing("business_quality_action_rules", "ix_business_quality_action_rules_sample_batch_id", ["sample_batch_id"])
    _create_index_if_missing("business_quality_action_rules", "ix_business_quality_action_rules_status", ["status"])
    _create_index_if_missing("business_quality_action_rules", "ix_business_quality_action_business_priority", ["business_key", "priority", "created_at"])
    _create_index_if_missing("business_quality_action_rules", "ix_business_quality_action_business_status", ["business_key", "status"])
    _create_index_if_missing("business_quality_action_rules", "ix_business_quality_action_business_type", ["business_key", "action_type"])


def downgrade() -> None:
    if _table_exists("business_quality_action_rules"):
        _drop_index_if_present("business_quality_action_rules", "ix_business_quality_action_business_type")
        _drop_index_if_present("business_quality_action_rules", "ix_business_quality_action_business_status")
        _drop_index_if_present("business_quality_action_rules", "ix_business_quality_action_business_priority")
        _drop_index_if_present("business_quality_action_rules", "ix_business_quality_action_rules_status")
        _drop_index_if_present("business_quality_action_rules", "ix_business_quality_action_rules_sample_batch_id")
        _drop_index_if_present("business_quality_action_rules", "ix_business_quality_action_rules_rule_key")
        _drop_index_if_present("business_quality_action_rules", "ix_business_quality_action_rules_created_at")
        _drop_index_if_present("business_quality_action_rules", "ix_business_quality_action_rules_business_key")
        _drop_index_if_present("business_quality_action_rules", "ix_business_quality_action_rules_action_type")
        op.drop_table("business_quality_action_rules")
    if _table_exists("business_quality_sample_versions"):
        _drop_index_if_present("business_quality_sample_versions", "ix_business_quality_sample_versions_sample_created")
        _drop_index_if_present("business_quality_sample_versions", "ix_business_quality_sample_versions_created_at")
        _drop_index_if_present("business_quality_sample_versions", "ix_business_quality_sample_versions_change_type")
        _drop_index_if_present("business_quality_sample_versions", "ix_business_quality_sample_versions_business_key")
        _drop_index_if_present("business_quality_sample_versions", "ix_business_quality_sample_versions_sample_id")
        op.drop_table("business_quality_sample_versions")
    if _table_exists("business_quality_samples"):
        _drop_index_if_present("business_quality_samples", "ix_business_quality_samples_business_sort")
        _drop_index_if_present("business_quality_samples", "ix_business_quality_samples_business_status")
        _drop_index_if_present("business_quality_samples", "ix_business_quality_samples_created_at")
        _drop_index_if_present("business_quality_samples", "ix_business_quality_samples_status")
        _drop_index_if_present("business_quality_samples", "ix_business_quality_samples_sample_key")
        _drop_index_if_present("business_quality_samples", "ix_business_quality_samples_business_key")
        op.drop_table("business_quality_samples")
    if _table_exists("business_output_reviews"):
        _drop_index_if_present("business_output_reviews", "ix_business_output_reviews_version_created")
        _drop_index_if_present("business_output_reviews", "ix_business_output_reviews_business_key")
        _drop_index_if_present("business_output_reviews", "ix_business_output_reviews_run_id")
        _drop_index_if_present("business_output_reviews", "ix_business_output_reviews_quality_grade")
        _drop_index_if_present("business_output_reviews", "ix_business_output_reviews_grade_created")
        _drop_index_if_present("business_output_reviews", "ix_business_output_reviews_created_at")
        _drop_index_if_present("business_output_reviews", "ix_business_output_reviews_batch_created")
        _drop_index_if_present("business_output_reviews", "ix_business_output_reviews_business_created")
        _drop_column_if_present("business_output_reviews", "batch_id")
        _drop_column_if_present("business_output_reviews", "sample_label")
        _drop_column_if_present("business_output_reviews", "sample_key")
        op.drop_table("business_output_reviews")
