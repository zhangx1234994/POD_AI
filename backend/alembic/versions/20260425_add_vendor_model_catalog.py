"""add vendor model catalog

Revision ID: 20260425_add_vendor_model_catalog
Revises: 20260424_add_business_capabilities
Create Date: 2026-04-25 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260425_add_vendor_model_catalog"
down_revision: Union[str, Sequence[str], None] = "20260424_add_business_capabilities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "vendor_model_catalog" not in tables:
        op.create_table(
            "vendor_model_catalog",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("display_name", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("api_types", sa.JSON(), nullable=True),
            sa.Column("execution_modes", sa.JSON(), nullable=True),
            sa.Column("supports_mask", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("supports_multiple_images", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("supports_video", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("supports_text", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("requires_global_egress", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("source", sa.String(length=64), nullable=False, server_default="backend-admin"),
            sa.Column("route_policy", sa.JSON(), nullable=True),
            sa.Column("default_task_policy", sa.JSON(), nullable=True),
            sa.Column("input_schema", sa.JSON(), nullable=True),
            sa.Column("cost_policy", sa.JSON(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "model", name="uq_vendor_model_catalog_provider_model"),
        )
        op.create_index("ix_vendor_model_catalog_provider", "vendor_model_catalog", ["provider"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "vendor_model_catalog" in tables:
        op.drop_index("ix_vendor_model_catalog_provider", table_name="vendor_model_catalog")
        op.drop_table("vendor_model_catalog")
