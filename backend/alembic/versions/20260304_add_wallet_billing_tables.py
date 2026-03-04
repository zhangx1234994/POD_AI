"""add wallet billing tables

Revision ID: 20260304_add_wallet_billing_tables
Revises: 20260218_add_eval_public_fields, 20260204_add_ability_version, 20260227_add_comfyui_repair_and_policy_tables, 20260126_add_eval_run_output_json
Create Date: 2026-03-04 20:10:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260304_add_wallet_billing_tables"
down_revision: Union[str, Sequence[str], None] = (
    "20260218_add_eval_public_fields",
    "20260204_add_ability_version",
    "20260227_add_comfyui_repair_and_policy_tables",
    "20260126_add_eval_run_output_json",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("frozen_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_wallet_accounts_user_id"),
    )
    op.create_index("ix_wallet_accounts_user_id", "wallet_accounts", ["user_id"], unique=True)

    op.create_table(
        "wallet_holds",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="frozen"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallet_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_holds_wallet_id", "wallet_holds", ["wallet_id"])
    op.create_index("ix_wallet_holds_user_id", "wallet_holds", ["user_id"])

    op.create_table(
        "wallet_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("biz_type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("related_task_id", sa.String(length=64), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model_key", sa.String(length=128), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallet_accounts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_wallet_ledger_user_id", "wallet_ledger", ["user_id"])
    op.create_index("ix_wallet_ledger_wallet_id", "wallet_ledger", ["wallet_id"])
    op.create_index("ix_wallet_ledger_related_task_id", "wallet_ledger", ["related_task_id"])
    op.create_index(
        "ix_wallet_ledger_user_created_at",
        "wallet_ledger",
        ["user_id", "created_at"],
    )

    op.create_table(
        "recharge_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_no", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("transaction_id", sa.String(length=128), nullable=True),
        sa.Column("fail_reason", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("order_no", name="uq_recharge_orders_order_no"),
    )
    op.create_index("ix_recharge_orders_order_no", "recharge_orders", ["order_no"], unique=True)
    op.create_index("ix_recharge_orders_user_id", "recharge_orders", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_recharge_orders_user_id", table_name="recharge_orders")
    op.drop_index("ix_recharge_orders_order_no", table_name="recharge_orders")
    op.drop_table("recharge_orders")

    op.drop_index("ix_wallet_ledger_user_created_at", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_related_task_id", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_wallet_id", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_user_id", table_name="wallet_ledger")
    op.drop_table("wallet_ledger")

    op.drop_index("ix_wallet_holds_user_id", table_name="wallet_holds")
    op.drop_index("ix_wallet_holds_wallet_id", table_name="wallet_holds")
    op.drop_table("wallet_holds")

    op.drop_index("ix_wallet_accounts_user_id", table_name="wallet_accounts")
    op.drop_table("wallet_accounts")
