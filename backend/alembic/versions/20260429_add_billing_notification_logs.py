"""add billing notification logs

Revision ID: 20260429_add_billing_notification_logs
Revises: 20260429_add_monthly_settlements
Create Date: 2026-04-29 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260429_add_billing_notification_logs"
down_revision: Union[str, Sequence[str], None] = "20260429_add_monthly_settlements"
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

    if "billing_notification_logs" not in tables:
        op.create_table(
            "billing_notification_logs",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("notification_type", sa.String(length=64), nullable=False, server_default="package_alert"),
            sa.Column("send_status", sa.String(length=32), nullable=False, server_default="not_sent"),
            sa.Column("send_detail", sa.Text(), nullable=True),
            sa.Column("webhook_format", sa.String(length=32), nullable=False, server_default="generic"),
            sa.Column("webhook_configured", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("alert_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("expiring_soon_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("low_balance_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("request_payload", sa.JSON(), nullable=True),
            sa.Column("response_payload", sa.JSON(), nullable=True),
            sa.Column("created_by_user_id", sa.String(length=64), nullable=True),
            sa.Column("created_by_username", sa.String(length=128), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    for index_name, columns in (
        ("ix_billing_notification_logs_type_created", ["notification_type", "created_at"]),
        ("ix_billing_notification_logs_status", ["send_status"]),
    ):
        _create_index_if_missing("billing_notification_logs", index_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "billing_notification_logs" in tables:
        op.drop_table("billing_notification_logs")
