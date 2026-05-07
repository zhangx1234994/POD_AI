"""Wallet and billing domain models."""

from __future__ import annotations

from datetime import datetime

from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WalletAccount(Base):
    __tablename__ = "wallet_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    frozen_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class WalletHold(Base):
    __tablename__ = "wallet_holds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    wallet_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("wallet_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(String(64))
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="frozen")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class WalletLedger(Base):
    __tablename__ = "wallet_ledger"
    __table_args__ = (
        Index("ix_wallet_ledger_user_created_at", "user_id", "created_at"),
        Index("ix_wallet_ledger_related_task", "related_task_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    wallet_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("wallet_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    related_task_id: Mapped[str | None] = mapped_column(String(64))
    trace_id: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(64))
    model_key: Mapped[str | None] = mapped_column(String(128))
    remark: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class RechargeOrder(Base):
    __tablename__ = "recharge_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    transaction_id: Mapped[str | None] = mapped_column(String(128))
    fail_reason: Mapped[str | None] = mapped_column(Text)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class TaskCostSnapshot(Base):
    __tablename__ = "task_cost_snapshots"
    __table_args__ = (
        Index("ix_task_cost_snapshots_user_created", "user_id", "created_at"),
        Index("ix_task_cost_snapshots_provider_model", "provider", "model_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    input_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    pricing_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PackageCatalog(Base):
    __tablename__ = "package_catalogs"
    __table_args__ = (
        Index("ix_package_catalogs_business_key", "business_key"),
        Index("ix_package_catalogs_status", "status"),
        Index("ix_package_catalogs_sort_order", "sort_order"),
    )

    package_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    package_name: Mapped[str] = mapped_column(String(128), nullable=False)
    business_key: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_name: Mapped[str] = mapped_column(String(32), nullable=False, default="次")
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="CNY")
    validity_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PackageBalance(Base):
    __tablename__ = "package_balances"
    __table_args__ = (
        Index("ix_package_balances_user_id", "user_id"),
        Index("ix_package_balances_package_key", "package_key"),
        Index("ix_package_balances_business_key", "business_key"),
        Index("ix_package_balances_expires_at", "expires_at"),
        Index("ix_package_balances_user_package", "user_id", "package_key"),
        Index("ix_package_balances_user_business", "user_id", "business_key"),
        Index("ix_package_balances_status_expires", "status", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    package_key: Mapped[str] = mapped_column(String(64), nullable=False)
    package_name: Mapped[str | None] = mapped_column(String(128))
    business_key: Mapped[str | None] = mapped_column(String(64))
    total_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frozen_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_name: Mapped[str] = mapped_column(String(32), nullable=False, default="次")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PackageLedger(Base):
    __tablename__ = "package_ledger"
    __table_args__ = (
        Index("ix_package_ledger_package_balance_id", "package_balance_id"),
        Index("ix_package_ledger_user_id", "user_id"),
        Index("ix_package_ledger_package_key", "package_key"),
        Index("ix_package_ledger_business_key", "business_key"),
        Index("ix_package_ledger_user_created_at", "user_id", "created_at"),
        Index("ix_package_ledger_trace_id", "trace_id"),
        Index("ix_package_ledger_task_id", "related_task_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_balance_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("package_balances.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    package_key: Mapped[str] = mapped_column(String(64), nullable=False)
    business_key: Mapped[str | None] = mapped_column(String(64))
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    related_task_id: Mapped[str | None] = mapped_column(String(64))
    trace_id: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    remark: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PackagePurchaseOrder(Base):
    __tablename__ = "package_purchase_orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    package_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    package_name: Mapped[str | None] = mapped_column(String(128))
    business_key: Mapped[str | None] = mapped_column(String(64), index=True)
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_name: Mapped[str] = mapped_column(String(32), nullable=False, default="次")
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="CNY")
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="offline")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    payment_reference: Mapped[str | None] = mapped_column(String(128))
    transaction_id: Mapped[str | None] = mapped_column(String(128))
    fail_reason: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str | None] = mapped_column(String(64))
    created_by_username: Mapped[str | None] = mapped_column(String(128))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BillingInvoiceRequest(Base):
    __tablename__ = "billing_invoice_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    invoice_no: Mapped[str | None] = mapped_column(String(128), unique=True)
    related_order_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    related_order_id: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64))
    client_id: Mapped[str | None] = mapped_column(String(64))
    business_key: Mapped[str | None] = mapped_column(String(64), index=True)
    invoice_title: Mapped[str] = mapped_column(String(256), nullable=False)
    tax_no: Mapped[str | None] = mapped_column(String(64))
    invoice_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ordinary")
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="CNY")
    delivery_email: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="requested", index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str | None] = mapped_column(String(64))
    created_by_username: Mapped[str | None] = mapped_column(String(128))
    issued_by_user_id: Mapped[str | None] = mapped_column(String(64))
    issued_by_username: Mapped[str | None] = mapped_column(String(128))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class MonthlySettlement(Base):
    __tablename__ = "monthly_settlements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(192), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True)
    business_key: Mapped[str | None] = mapped_column(String(64), index=True)
    user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_frozen_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_income: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_expense: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_net: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_package_remaining_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    package_alert_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="issued", index=True)
    payment_reference: Mapped[str | None] = mapped_column(String(128))
    note: Mapped[str | None] = mapped_column(Text)
    issued_by_user_id: Mapped[str | None] = mapped_column(String(64))
    issued_by_username: Mapped[str | None] = mapped_column(String(128))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BillingNotificationLog(Base):
    __tablename__ = "billing_notification_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False, default="package_alert", index=True)
    send_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_sent", index=True)
    send_detail: Mapped[str | None] = mapped_column(Text)
    webhook_format: Mapped[str] = mapped_column(String(32), nullable=False, default="generic")
    webhook_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alert_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expiring_soon_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_balance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_payload: Mapped[dict | None] = mapped_column(JSON)
    response_payload: Mapped[dict | None] = mapped_column(JSON)
    created_by_user_id: Mapped[str | None] = mapped_column(String(64))
    created_by_username: Mapped[str | None] = mapped_column(String(128))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
