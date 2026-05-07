"""Admin billing facade.

This layer keeps the current billing page usable while the commercial payment
system is still a skeleton: wallet numbers come from the wallet service, package
quota writes to package tables, and orders/invoices/monthly settlements use the
tables that already exist in migrations.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import engine, get_session
from app.models.integration import BusinessRun
from app.models.user import User
from app.models.wallet import (
    BillingInvoiceRequest,
    BillingNotificationLog,
    MonthlySettlement,
    PackageBalance,
    PackageCatalog,
    PackageLedger,
    PackagePurchaseOrder,
)
from app.services.business_runs import BusinessRunService
from app.services.wallet import wallet_service


_NOTIFICATION_CONFIG: dict[str, Any] = {
    "channels": [
        {
            "key": "ops-webhook",
            "displayName": "运维群通知",
            "description": "用于低余额、套餐到期和月结催收提醒。",
            "enabled": False,
            "configured": False,
            "webhookUrl": None,
            "webhookFormat": "generic",
            "source": "memory",
        }
    ]
}


class AdminBillingService:
    @staticmethod
    def _db_ready(*table_names: str) -> bool:
        try:
            inspector = inspect(engine)
            return all(inspector.has_table(name) for name in table_names)
        except Exception:
            return False

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    @staticmethod
    def _month(value: str | None = None) -> str:
        raw = str(value or "").strip()
        if not raw:
            return datetime.now(timezone.utc).strftime("%Y-%m")
        try:
            datetime.strptime(raw[:7], "%Y-%m")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="BILL_MONTH_INVALID") from exc
        return raw[:7]

    @classmethod
    def _month_range(cls, value: str | None = None) -> tuple[str, datetime, datetime]:
        normalized = cls._month(value)
        start = datetime.strptime(normalized, "%Y-%m")
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return normalized, start, end

    @staticmethod
    def _actor_id(actor: User | None) -> str | None:
        return str(getattr(actor, "id", "") or "").strip() or None

    @staticmethod
    def _actor_name(actor: User | None) -> str | None:
        return str(getattr(actor, "username", "") or getattr(actor, "email", "") or "").strip() or None

    @staticmethod
    def _user_read(user: User | None, user_id: str | None = None) -> dict[str, Any]:
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "displayName": user.display_name,
                "tenantId": user.tenant_id,
                "clientId": user.client_id,
            }
        fallback_id = str(user_id or "unknown")
        return {
            "id": fallback_id,
            "username": fallback_id,
            "email": "",
            "role": "user",
            "status": "active",
            "displayName": None,
            "tenantId": None,
            "clientId": None,
        }

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="BILLING_DATETIME_INVALID") from exc

    @staticmethod
    def _payload_has_value(payload: dict[str, Any], *keys: str) -> bool:
        for key in keys:
            if key not in payload:
                continue
            value = payload.get(key)
            if value is not None and str(value).strip() != "":
                return True
        return False

    def _package_catalog_to_dict(self, row: PackageCatalog) -> dict[str, Any]:
        return {
            "packageKey": row.package_key,
            "packageName": row.package_name,
            "businessKey": row.business_key,
            "description": row.description,
            "units": int(row.units or 0),
            "unitName": row.unit_name or "次",
            "amountCents": int(row.amount_cents or 0),
            "currency": row.currency or "CNY",
            "validityDays": int(row.validity_days) if row.validity_days is not None else None,
            "status": row.status,
            "sortOrder": int(row.sort_order or 100),
            "metadata": row.extra_metadata or {},
            "createdAt": self._iso(row.created_at),
            "updatedAt": self._iso(row.updated_at),
        }

    def _apply_package_catalog_defaults(self, session, payload: dict[str, Any], package_key: str) -> dict[str, Any]:
        merged = dict(payload or {})
        row = session.get(PackageCatalog, package_key)
        if not row or row.status != "active":
            return merged
        if not self._payload_has_value(merged, "packageName", "package_name"):
            merged["packageName"] = row.package_name
        if row.business_key and not self._payload_has_value(merged, "businessKey", "business_key"):
            merged["businessKey"] = row.business_key
        if not self._payload_has_value(merged, "units"):
            merged["units"] = int(row.units or 0)
        if not self._payload_has_value(merged, "unitName", "unit_name"):
            merged["unitName"] = row.unit_name or "次"
        if not self._payload_has_value(merged, "amountCents", "amount_cents"):
            merged["amountCents"] = int(row.amount_cents or 0)
        if not self._payload_has_value(merged, "currency"):
            merged["currency"] = row.currency or "CNY"
        if row.validity_days and not self._payload_has_value(merged, "expiresAt", "expires_at"):
            merged["expiresAt"] = (self._now() + timedelta(days=int(row.validity_days))).isoformat()
        return merged

    def list_package_catalog(
        self,
        *,
        business_key: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            with get_session() as session:
                stmt = select(PackageCatalog)
                if business_key and business_key != "all":
                    stmt = stmt.where(PackageCatalog.business_key == business_key)
                if status and status != "all":
                    stmt = stmt.where(PackageCatalog.status == status)
                rows = (
                    session.execute(
                        stmt.order_by(PackageCatalog.sort_order.asc(), PackageCatalog.updated_at.desc()).limit(
                            max(1, min(limit, 500))
                        )
                    )
                    .scalars()
                    .all()
                )
        except SQLAlchemyError:
            return {"total": 0, "items": []}
        return {"total": len(rows), "items": [self._package_catalog_to_dict(row) for row in rows]}

    def upsert_package_catalog(self, payload: dict[str, Any], *, actor: User | None = None) -> dict[str, Any]:
        _ = actor
        package_key = str(payload.get("packageKey") or payload.get("package_key") or "").strip()
        if not package_key:
            raise HTTPException(status_code=400, detail="PACKAGE_KEY_REQUIRED")
        now = self._now()
        with get_session() as session:
            row = session.get(PackageCatalog, package_key)
            package_name = str(
                payload.get("packageName")
                or payload.get("package_name")
                or (row.package_name if row else "")
                or ""
            ).strip()
            if not package_name:
                raise HTTPException(status_code=400, detail="PACKAGE_CATALOG_NAME_REQUIRED")
            units = int(payload.get("units") if self._payload_has_value(payload, "units") else (row.units if row else 0))
            if units <= 0:
                raise HTTPException(status_code=400, detail="PACKAGE_UNITS_INVALID")
            amount_cents = int(
                payload.get("amountCents")
                if self._payload_has_value(payload, "amountCents")
                else payload.get("amount_cents")
                if self._payload_has_value(payload, "amount_cents")
                else (row.amount_cents if row else 0)
            )
            if amount_cents < 0:
                raise HTTPException(status_code=400, detail="PACKAGE_AMOUNT_INVALID")
            validity_days = (
                payload.get("validityDays")
                if "validityDays" in payload
                else payload.get("validity_days")
                if "validity_days" in payload
                else (row.validity_days if row else None)
            )
            if validity_days in ("", None):
                normalized_validity_days = None
            else:
                normalized_validity_days = int(validity_days)
                if normalized_validity_days <= 0:
                    raise HTTPException(status_code=400, detail="PACKAGE_VALIDITY_DAYS_INVALID")
            status = str(payload.get("status") or (row.status if row else "active")).strip() or "active"
            if status not in {"active", "inactive"}:
                raise HTTPException(status_code=400, detail="PACKAGE_CATALOG_STATUS_INVALID")
            if not row:
                row = PackageCatalog(package_key=package_key, created_at=now, updated_at=now)
            row.package_name = package_name
            row.business_key = str(payload.get("businessKey") or payload.get("business_key") or row.business_key or "").strip() or None
            row.description = payload.get("description") if "description" in payload else row.description
            row.units = units
            row.unit_name = str(payload.get("unitName") or payload.get("unit_name") or row.unit_name or "次").strip() or "次"
            row.amount_cents = amount_cents
            row.currency = str(payload.get("currency") or row.currency or "CNY").strip() or "CNY"
            row.validity_days = normalized_validity_days
            row.status = status
            row.sort_order = int(
                payload.get("sortOrder")
                if self._payload_has_value(payload, "sortOrder")
                else payload.get("sort_order")
                if self._payload_has_value(payload, "sort_order")
                else (row.sort_order or 100)
            )
            row.extra_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else row.extra_metadata
            row.updated_at = now
            session.add(row)
            session.commit()
            return self._package_catalog_to_dict(row)

    def update_package_catalog(
        self,
        package_key: str,
        payload: dict[str, Any],
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        normalized_key = str(package_key or "").strip()
        if not normalized_key:
            raise HTTPException(status_code=400, detail="PACKAGE_KEY_REQUIRED")
        with get_session() as session:
            if not session.get(PackageCatalog, normalized_key):
                raise HTTPException(status_code=404, detail="PACKAGE_CATALOG_NOT_FOUND")
        return self.upsert_package_catalog({**payload, "packageKey": normalized_key}, actor=actor)

    @staticmethod
    def _package_remaining(row: PackageBalance) -> int:
        return max(0, int(row.total_units or 0) - int(row.used_units or 0) - int(row.frozen_units or 0))

    def _package_balance_to_dict(self, row: PackageBalance) -> dict[str, Any]:
        remaining = self._package_remaining(row)
        return {
            "id": str(row.id),
            "userId": row.user_id,
            "packageKey": row.package_key,
            "packageName": row.package_name,
            "businessKey": row.business_key,
            "totalUnits": int(row.total_units or 0),
            "usedUnits": int(row.used_units or 0),
            "frozenUnits": int(row.frozen_units or 0),
            "remainingUnits": remaining,
            "unitName": row.unit_name or "次",
            "status": row.status,
            "source": row.source,
            "expiresAt": self._iso(row.expires_at),
            "createdAt": self._iso(row.created_at),
        }

    def _package_ledger_to_dict(self, row: PackageLedger) -> dict[str, Any]:
        signed_units = int(row.units or 0) if row.direction == "in" else -int(row.units or 0)
        return {
            "id": f"pkg_txn_{row.id}",
            "packageBalanceId": str(row.package_balance_id),
            "userId": row.user_id,
            "packageKey": row.package_key,
            "businessKey": row.business_key,
            "changeType": "INCREASE" if signed_units >= 0 else "DECREASE",
            "units": signed_units,
            "balanceAfter": int(row.balance_after or 0),
            "taskId": row.related_task_id,
            "traceId": row.trace_id,
            "source": row.source,
            "description": row.remark,
            "createdAt": self._iso(row.created_at),
        }

    def _package_balances(self, session, user_id: str, business_key: str | None = None) -> dict[str, Any]:
        try:
            rows = session.execute(
                select(PackageBalance)
                .where(PackageBalance.user_id == user_id)
                .order_by(PackageBalance.updated_at.desc(), PackageBalance.id.desc())
            ).scalars().all()
        except SQLAlchemyError:
            rows = []
        if business_key and business_key != "all":
            rows = [row for row in rows if not row.business_key or row.business_key == business_key]
        items = [self._package_balance_to_dict(row) for row in rows]
        return {
            "userId": user_id,
            "businessKey": business_key if business_key and business_key != "all" else None,
            "packageKey": None,
            "totalRemainingUnits": sum(int(item["remainingUnits"] or 0) for item in items),
            "items": items,
        }

    def _package_ledger(self, session, user_id: str, business_key: str | None = None, page_size: int = 20) -> dict[str, Any]:
        try:
            rows = session.execute(
                select(PackageLedger)
                .where(PackageLedger.user_id == user_id)
                .order_by(PackageLedger.created_at.desc(), PackageLedger.id.desc())
                .limit(max(1, min(page_size, 200)))
            ).scalars().all()
        except SQLAlchemyError:
            rows = []
        if business_key and business_key != "all":
            rows = [row for row in rows if not row.business_key or row.business_key == business_key]
        return {
            "userId": user_id,
            "businessKey": business_key if business_key and business_key != "all" else None,
            "packageKey": None,
            "total": len(rows),
            "page": 1,
            "pageSize": page_size,
            "items": [self._package_ledger_to_dict(row) for row in rows],
        }

    def user_detail(
        self,
        user_id: str,
        *,
        month: str | None = None,
        window_days: int = 30,
        business_key: str | None = None,
        page_size: int = 20,
    ) -> dict[str, Any]:
        normalized_month = self._month(month)
        with get_session() as session:
            user = session.get(User, user_id)
            package_balances = self._package_balances(session, user_id, business_key=business_key)
            package_ledger = self._package_ledger(session, user_id, business_key=business_key, page_size=page_size)
        return {
            "user": self._user_read(user, user_id),
            "balance": wallet_service.balance(user_id),
            "bill": wallet_service.bill(user_id, normalized_month),
            "usage": wallet_service.usage_summary(user_id, window_days=window_days),
            "ledger": wallet_service.ledger(user_id, page=1, page_size=page_size),
            "costSnapshots": wallet_service.cost_snapshots(user_id),
            "packageBalances": package_balances,
            "packageLedger": package_ledger,
        }

    def _billing_issues(
        self,
        *,
        business_key: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with get_session() as session:
            stmt = select(BusinessRun).order_by(BusinessRun.created_at.desc()).limit(max(1, min(limit * 4, 200)))
            filters = []
            if business_key and business_key != "all":
                filters.append(BusinessRun.business_key == business_key)
            if tenant_id:
                filters.append(BusinessRun.tenant_id == tenant_id)
            if client_id:
                filters.append(BusinessRun.client_id == client_id)
            if filters:
                stmt = stmt.where(and_(*filters))
            rows = session.execute(stmt).scalars().all()
        items: list[dict[str, Any]] = []
        for row in rows:
            billing_status = BusinessRunService._business_billing_status(row)
            settlement = BusinessRunService._billing_settlement_from_run(row)
            settlement_status = str((settlement or {}).get("status") or "")
            issue_type = ""
            issue_label = ""
            if billing_status == "billable" and not settlement:
                issue_type, issue_label = "wallet_missing", "成功任务未扣费"
            elif billing_status == "billable" and settlement_status == "failed":
                issue_type, issue_label = "billing_failed", "计费扣减失败"
            elif billing_status == "no_charge" and settlement_status == "settled":
                issue_type, issue_label = "failed_run_charged", "失败任务已计费"
            elif billing_status == "unpriced":
                issue_type, issue_label = "unpriced", "成功任务缺少定价"
            if not issue_type:
                continue
            items.append(
                {
                    "id": row.id,
                    "runId": row.id,
                    "businessKey": row.business_key,
                    "version": row.version,
                    "status": row.status,
                    "issueType": issue_type,
                    "issueLabel": issue_label,
                    "userId": row.user_id,
                    "userName": row.user_name,
                    "tenantId": row.tenant_id,
                    "clientId": row.client_id,
                    "billingStatus": billing_status,
                    "walletStatus": settlement_status or None,
                    "currency": row.currency,
                    "costAmount": float(row.cost_amount) if row.cost_amount is not None else None,
                    "quotaUnits": row.quota_units,
                    "error": row.error_message,
                    "createdAt": self._iso(row.created_at),
                }
            )
            if len(items) >= limit:
                break
        return items

    def _package_alerts(self, session, *, tenant_id: str | None = None, client_id: str | None = None, business_key: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        try:
            rows = session.execute(select(PackageBalance).order_by(PackageBalance.updated_at.desc()).limit(500)).scalars().all()
            users = {user.id: user for user in session.execute(select(User)).scalars().all()}
        except SQLAlchemyError:
            return []
        now = datetime.utcnow()
        items: list[dict[str, Any]] = []
        for row in rows:
            user = users.get(row.user_id)
            if tenant_id and (not user or user.tenant_id != tenant_id):
                continue
            if client_id and (not user or user.client_id != client_id):
                continue
            if business_key and business_key != "all" and row.business_key not in {None, business_key}:
                continue
            remaining = self._package_remaining(row)
            days_until_expiry = (row.expires_at - now).days if row.expires_at else None
            alert_type = None
            alert_label = None
            if remaining <= 10:
                alert_type, alert_label = "low_balance", "套餐额度偏低"
            if days_until_expiry is not None and days_until_expiry <= 14:
                alert_type, alert_label = "expiring_soon", "套餐即将到期"
            if not alert_type:
                continue
            items.append(
                {
                    "id": f"pkg_alert_{row.id}",
                    "alertType": alert_type,
                    "alertLabel": alert_label,
                    "userId": row.user_id,
                    "userName": user.username if user else row.user_id,
                    "tenantId": user.tenant_id if user else None,
                    "clientId": user.client_id if user else None,
                    "packageKey": row.package_key,
                    "packageName": row.package_name,
                    "businessKey": row.business_key,
                    "totalUnits": int(row.total_units or 0),
                    "remainingUnits": remaining,
                    "unitName": row.unit_name or "次",
                    "expiresAt": self._iso(row.expires_at),
                    "daysUntilExpiry": days_until_expiry,
                }
            )
            if len(items) >= limit:
                break
        return items

    def overview(
        self,
        *,
        month: str | None = None,
        window_days: int = 30,
        tenant_id: str | None = None,
        client_id: str | None = None,
        business_key: str | None = None,
        limit: int = 100,
        issue_limit: int = 20,
        package_alert_limit: int = 20,
    ) -> dict[str, Any]:
        normalized_month = self._month(month)
        with get_session() as session:
            stmt = select(User).order_by(User.created_at.desc()).limit(max(1, min(limit, 500)))
            filters = []
            if tenant_id:
                filters.append(User.tenant_id == tenant_id)
            if client_id:
                filters.append(User.client_id == client_id)
            if filters:
                stmt = stmt.where(and_(*filters))
            users = session.execute(stmt).scalars().all()
            package_alerts = self._package_alerts(
                session,
                tenant_id=tenant_id,
                client_id=client_id,
                business_key=business_key,
                limit=package_alert_limit,
            )
            package_remaining_by_user = {}
            for user in users:
                package_remaining_by_user[user.id] = self._package_balances(
                    session,
                    user.id,
                    business_key=business_key,
                )["totalRemainingUnits"]
        items = []
        totals = defaultdict(int)
        for user in users:
            balance = wallet_service.balance(user.id)
            bill = wallet_service.bill(user.id, normalized_month)
            usage = wallet_service.usage_summary(user.id, window_days=window_days)
            package_remaining = int(package_remaining_by_user.get(user.id) or 0)
            item = {
                "user": self._user_read(user),
                "balance": int(balance["balance"]),
                "frozenBalance": int(balance["frozenBalance"]),
                "currency": balance["currency"],
                "month": normalized_month,
                "income": int(bill["income"]),
                "expense": int(bill["expense"]),
                "net": int(bill["net"]),
                "billCount": int(bill["count"]),
                "windowDays": window_days,
                "totalExpensePoints": int(usage["totalExpensePoints"]),
                "totalIncomePoints": int(usage["totalIncomePoints"]),
                "expenseCount": int(usage["expenseCount"]),
                "incomeCount": int(usage["incomeCount"]),
                "packageRemainingUnits": package_remaining,
            }
            items.append(item)
            for key in ("balance", "frozenBalance", "income", "expense", "net", "totalExpensePoints", "totalIncomePoints", "expenseCount", "incomeCount", "packageRemainingUnits"):
                totals[key] += int(item[key] or 0)
        issues = self._billing_issues(
            business_key=business_key,
            tenant_id=tenant_id,
            client_id=client_id,
            limit=issue_limit,
        )
        return {
            "month": normalized_month,
            "windowDays": window_days,
            "tenantId": tenant_id,
            "clientId": client_id,
            "businessKey": business_key if business_key and business_key != "all" else None,
            "totalUsers": len(items),
            "totalBalance": totals["balance"],
            "totalFrozenBalance": totals["frozenBalance"],
            "totalIncome": totals["income"],
            "totalExpense": totals["expense"],
            "totalNet": totals["net"],
            "totalExpensePoints": totals["totalExpensePoints"],
            "totalIncomePoints": totals["totalIncomePoints"],
            "expenseCount": totals["expenseCount"],
            "incomeCount": totals["incomeCount"],
            "totalPackageRemainingUnits": totals["packageRemainingUnits"],
            "issueCount": len(issues),
            "issues": issues,
            "packageAlertCount": len(package_alerts),
            "packageExpiringSoonCount": len([item for item in package_alerts if item["alertType"] == "expiring_soon"]),
            "packageLowBalanceCount": len([item for item in package_alerts if item["alertType"] == "low_balance"]),
            "packageAlerts": package_alerts,
            "items": items,
        }

    @staticmethod
    def _status_label(status: str) -> str:
        return {
            "pending": "待处理",
            "paid": "已支付",
            "failed": "失败",
            "cancelled": "已取消",
            "issued": "已出账",
            "requested": "已申请",
        }.get(status, status)

    def _settlement_item_from_overview(self, overview: dict[str, Any], *, tenant_id: str | None, client_id: str | None) -> dict[str, Any]:
        issue_count = int(overview.get("issueCount") or 0)
        alert_count = int(overview.get("packageAlertCount") or 0)
        return {
            "id": f"settlement_preview_{tenant_id or 'all'}_{client_id or 'all'}",
            "tenantId": tenant_id,
            "clientId": client_id,
            "userCount": int(overview.get("totalUsers") or 0),
            "totalBalance": int(overview.get("totalBalance") or 0),
            "totalFrozenBalance": int(overview.get("totalFrozenBalance") or 0),
            "totalIncome": int(overview.get("totalIncome") or 0),
            "totalExpense": int(overview.get("totalExpense") or 0),
            "totalNet": int(overview.get("totalNet") or 0),
            "totalPackageRemainingUnits": int(overview.get("totalPackageRemainingUnits") or 0),
            "issueCount": issue_count,
            "packageAlertCount": alert_count,
            "settlementStatus": "needs_review" if issue_count or alert_count else "ready",
            "settlementLabel": "需处理风险" if issue_count or alert_count else "可出账",
        }

    def monthly_settlement(self, **kwargs: Any) -> dict[str, Any]:
        overview = self.overview(**kwargs)
        item = self._settlement_item_from_overview(
            overview,
            tenant_id=kwargs.get("tenant_id"),
            client_id=kwargs.get("client_id"),
        )
        return {
            "month": overview["month"],
            "windowDays": overview["windowDays"],
            "businessKey": overview.get("businessKey"),
            "totalGroups": 1 if item["userCount"] else 0,
            "issueGroupCount": 1 if item["issueCount"] else 0,
            "packageAlertGroupCount": 1 if item["packageAlertCount"] else 0,
            "items": [item] if item["userCount"] else [],
        }

    def _empty_commercial_report(
        self,
        *,
        month: str,
        tenant_id: str | None = None,
        client_id: str | None = None,
        business_key: str | None = None,
    ) -> dict[str, Any]:
        return {
            "month": month,
            "tenantId": tenant_id,
            "clientId": client_id,
            "businessKey": business_key if business_key and business_key != "all" else None,
            "generatedAt": self._now().isoformat(),
            "status": "setup_required",
            "statusLabel": "待初始化",
            "nextAction": "账单模块仍是后阶段雏形；请先完成数据库迁移和套餐配置，再进入收费核算。",
            "runCount": 0,
            "succeededRunCount": 0,
            "failedRunCount": 0,
            "billableRunCount": 0,
            "chargedRunCount": 0,
            "packageChargedRunCount": 0,
            "walletChargedRunCount": 0,
            "unpricedRunCount": 0,
            "billingIssueCount": 0,
            "quotaUnits": 0,
            "costByCurrency": [],
            "paidPackageOrderCount": 0,
            "pendingPackageOrderCount": 0,
            "packageSoldUnits": 0,
            "packageOrderRevenueByCurrency": [],
            "pendingPackageRevenueByCurrency": [],
            "activePackageCatalogCount": 0,
            "businessRows": [],
            "riskItems": [],
        }

    def commercial_report(
        self,
        *,
        month: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        business_key: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        normalized_month, month_start, month_end = self._month_range(month)
        try:
            with get_session() as session:
                run_stmt = select(BusinessRun).where(
                    BusinessRun.created_at >= month_start,
                    BusinessRun.created_at < month_end,
                )
                filters = []
                if business_key and business_key != "all":
                    filters.append(BusinessRun.business_key == business_key)
                if tenant_id:
                    filters.append(BusinessRun.tenant_id == tenant_id)
                if client_id:
                    filters.append(BusinessRun.client_id == client_id)
                if filters:
                    run_stmt = run_stmt.where(and_(*filters))
                runs = (
                    session.execute(run_stmt.order_by(BusinessRun.created_at.desc()).limit(max(1, min(limit, 5000))))
                    .scalars()
                    .all()
                )

                order_stmt = select(PackagePurchaseOrder).where(
                    PackagePurchaseOrder.created_at >= month_start,
                    PackagePurchaseOrder.created_at < month_end,
                )
                if business_key and business_key != "all":
                    order_stmt = order_stmt.where(PackagePurchaseOrder.business_key == business_key)
                orders = (
                    session.execute(order_stmt.order_by(PackagePurchaseOrder.created_at.desc()).limit(2000))
                    .scalars()
                    .all()
                )
                users = {user.id: user for user in session.execute(select(User)).scalars().all()}
                if tenant_id or client_id:
                    orders = [
                        row
                        for row in orders
                        if (not tenant_id or (users.get(row.user_id) and users[row.user_id].tenant_id == tenant_id))
                        and (not client_id or (users.get(row.user_id) and users[row.user_id].client_id == client_id))
                    ]
                package_catalogs = session.execute(select(PackageCatalog)).scalars().all()
                if business_key and business_key != "all":
                    package_catalogs = [row for row in package_catalogs if not row.business_key or row.business_key == business_key]
        except SQLAlchemyError:
            return self._empty_commercial_report(
                month=normalized_month,
                tenant_id=tenant_id,
                client_id=client_id,
                business_key=business_key,
            )

        totals: dict[str, Any] = {
            "runCount": 0,
            "succeededRunCount": 0,
            "failedRunCount": 0,
            "billableRunCount": 0,
            "chargedRunCount": 0,
            "packageChargedRunCount": 0,
            "walletChargedRunCount": 0,
            "unpricedRunCount": 0,
            "billingIssueCount": 0,
            "quotaUnits": 0,
            "costByCurrency": defaultdict(float),
        }
        business_rows: dict[str, dict[str, Any]] = {}

        def bucket_for(key: str) -> dict[str, Any]:
            if key not in business_rows:
                business_rows[key] = {
                    "businessKey": key,
                    "runCount": 0,
                    "succeededRunCount": 0,
                    "billableRunCount": 0,
                    "chargedRunCount": 0,
                    "unpricedRunCount": 0,
                    "billingIssueCount": 0,
                    "quotaUnits": 0,
                    "costByCurrency": defaultdict(float),
                }
            return business_rows[key]

        for run in runs:
            key = run.business_key or "unknown"
            bucket = bucket_for(key)
            billing_status = BusinessRunService._business_billing_status(run)
            settlement = BusinessRunService._billing_settlement_from_run(run)
            settlement_status = str((settlement or {}).get("status") or "")
            method = str((settlement or {}).get("method") or "")
            is_success = run.status == "succeeded"
            is_billable = billing_status == "billable"
            has_issue = (
                billing_status == "unpriced"
                or (is_billable and not settlement)
                or (is_billable and settlement_status == "failed")
                or (billing_status == "no_charge" and settlement_status == "settled")
            )
            cost_amount = float(run.cost_amount or 0)
            currency = str(run.currency or "UNKNOWN").upper()
            quota_units = int(run.quota_units or 0)

            for target in (totals, bucket):
                target["runCount"] += 1
                target["succeededRunCount"] += 1 if is_success else 0
                target["billableRunCount"] += 1 if is_billable else 0
                target["chargedRunCount"] += 1 if settlement_status == "settled" else 0
                target["unpricedRunCount"] += 1 if billing_status == "unpriced" else 0
                target["billingIssueCount"] += 1 if has_issue else 0
                target["quotaUnits"] += quota_units if is_billable else 0
                if is_billable and cost_amount:
                    target["costByCurrency"][currency] += cost_amount
            totals["failedRunCount"] += 0 if is_success else 1
            totals["packageChargedRunCount"] += 1 if settlement_status == "settled" and method == "package" else 0
            totals["walletChargedRunCount"] += 1 if settlement_status == "settled" and method == "wallet" else 0

        paid_orders = [row for row in orders if row.status == "paid"]
        pending_orders = [row for row in orders if row.status == "pending"]
        package_order_revenue_by_currency: dict[str, int] = defaultdict(int)
        pending_revenue_by_currency: dict[str, int] = defaultdict(int)
        for row in paid_orders:
            package_order_revenue_by_currency[str(row.currency or "CNY").upper()] += int(row.amount_cents or 0)
        for row in pending_orders:
            pending_revenue_by_currency[str(row.currency or "CNY").upper()] += int(row.amount_cents or 0)

        def cost_list(value: dict[str, float]) -> list[dict[str, Any]]:
            return [
                {"currency": currency, "amount": round(amount, 4)}
                for currency, amount in sorted(value.items())
                if amount
            ]

        def cents_list(value: dict[str, int]) -> list[dict[str, Any]]:
            return [
                {"currency": currency, "amountCents": amount}
                for currency, amount in sorted(value.items())
                if amount
            ]

        rows = []
        for row in business_rows.values():
            rows.append(
                {
                    **{key: value for key, value in row.items() if key != "costByCurrency"},
                    "costByCurrency": cost_list(row["costByCurrency"]),
                }
            )
        rows.sort(key=lambda item: (int(item["billingIssueCount"]), int(item["runCount"])), reverse=True)

        risk_items = self._billing_issues(
            business_key=business_key,
            tenant_id=tenant_id,
            client_id=client_id,
            limit=20,
        )
        report_status = "blocked" if totals["billingIssueCount"] else "ready"
        if totals["unpricedRunCount"]:
            next_action = "先补模型成本规则，再重试扣费。"
        elif totals["billingIssueCount"]:
            next_action = "先处理扣费异常和失败后扣费样本。"
        elif pending_orders:
            next_action = "有待确认订单，可催收或确认线下回款。"
        else:
            next_action = "当前账期可进入人工复核。"

        return {
            "month": normalized_month,
            "tenantId": tenant_id,
            "clientId": client_id,
            "businessKey": business_key if business_key and business_key != "all" else None,
            "generatedAt": self._now().isoformat(),
            "status": report_status,
            "statusLabel": "需先处理风险" if report_status == "blocked" else "可进入复核",
            "nextAction": next_action,
            "runCount": totals["runCount"],
            "succeededRunCount": totals["succeededRunCount"],
            "failedRunCount": totals["failedRunCount"],
            "billableRunCount": totals["billableRunCount"],
            "chargedRunCount": totals["chargedRunCount"],
            "packageChargedRunCount": totals["packageChargedRunCount"],
            "walletChargedRunCount": totals["walletChargedRunCount"],
            "unpricedRunCount": totals["unpricedRunCount"],
            "billingIssueCount": totals["billingIssueCount"],
            "quotaUnits": totals["quotaUnits"],
            "costByCurrency": cost_list(totals["costByCurrency"]),
            "paidPackageOrderCount": len(paid_orders),
            "pendingPackageOrderCount": len(pending_orders),
            "packageSoldUnits": sum(int(row.units or 0) for row in paid_orders),
            "packageOrderRevenueByCurrency": cents_list(package_order_revenue_by_currency),
            "pendingPackageRevenueByCurrency": cents_list(pending_revenue_by_currency),
            "activePackageCatalogCount": len([row for row in package_catalogs if row.status == "active"]),
            "businessRows": rows,
            "riskItems": risk_items,
        }

    def grant_package(self, user_id: str, payload: dict[str, Any], *, actor: User | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        package_key = str(payload.get("packageKey") or payload.get("package_key") or "").strip()
        if not package_key:
            raise HTTPException(status_code=400, detail="PACKAGE_KEY_REQUIRED")
        now = self._now()
        with get_session() as session:
            payload = self._apply_package_catalog_defaults(session, payload, package_key)
            units = int(payload.get("units") or 0)
            if units <= 0:
                raise HTTPException(status_code=400, detail="PACKAGE_UNITS_INVALID")
            business_key = str(payload.get("businessKey") or payload.get("business_key") or "").strip() or None
            trace_id = str(payload.get("traceId") or payload.get("trace_id") or "").strip() or None
            existing_ledger = None
            if trace_id:
                existing_ledger = (
                    session.execute(
                        select(PackageLedger).where(PackageLedger.user_id == user_id, PackageLedger.trace_id == trace_id)
                    )
                    .scalars()
                    .first()
                )
            balance = (
                session.execute(
                    select(PackageBalance).where(
                        PackageBalance.user_id == user_id,
                        PackageBalance.package_key == package_key,
                        PackageBalance.business_key == business_key,
                    )
                )
                .scalars()
                .first()
            )
            if not balance:
                balance = PackageBalance(
                    user_id=user_id,
                    package_key=package_key,
                    package_name=payload.get("packageName") or payload.get("package_name"),
                    business_key=business_key,
                    total_units=0,
                    used_units=0,
                    frozen_units=0,
                    unit_name=payload.get("unitName") or payload.get("unit_name") or "次",
                    status="active",
                    source="manual",
                    expires_at=self._parse_datetime(payload.get("expiresAt") or payload.get("expires_at")),
                    created_at=now,
                    updated_at=now,
                )
                session.add(balance)
                session.flush()
            if existing_ledger:
                session.commit()
                package_balances = self._package_balances(session, user_id, business_key=business_key)
                package_ledger = self._package_ledger(session, user_id, business_key=business_key)
                return {
                    "transactionId": f"pkg_txn_{existing_ledger.id}",
                    "ledgerIds": [f"pkg_txn_{existing_ledger.id}"],
                    "packageBalanceId": str(balance.id),
                    "userId": user_id,
                    "packageKey": package_key,
                    "businessKey": business_key,
                    "granted": int(existing_ledger.units or 0),
                    "remainingUnits": self._package_remaining(balance),
                    "idempotent": True,
                    "traceId": trace_id,
                    "packageBalances": package_balances,
                    "packageLedger": package_ledger,
                }
            balance.total_units = int(balance.total_units or 0) + units
            balance.package_name = payload.get("packageName") or payload.get("package_name") or balance.package_name
            balance.unit_name = payload.get("unitName") or payload.get("unit_name") or balance.unit_name
            balance.expires_at = self._parse_datetime(payload.get("expiresAt") or payload.get("expires_at")) or balance.expires_at
            balance.updated_at = now
            remaining = self._package_remaining(balance)
            ledger = PackageLedger(
                package_balance_id=int(balance.id),
                user_id=user_id,
                package_key=package_key,
                business_key=business_key,
                direction="in",
                units=units,
                balance_after=remaining,
                trace_id=trace_id,
                source="manual",
                remark=payload.get("description") or "manual package grant",
                created_at=now,
            )
            session.add(balance)
            session.add(ledger)
            session.commit()
            package_balances = self._package_balances(session, user_id, business_key=business_key)
            package_ledger = self._package_ledger(session, user_id, business_key=business_key)
            return {
                "transactionId": f"pkg_txn_{ledger.id}",
                "ledgerIds": [f"pkg_txn_{ledger.id}"],
                "packageBalanceId": str(balance.id),
                "userId": user_id,
                "packageKey": package_key,
                "businessKey": business_key,
                "granted": units,
                "remainingUnits": remaining,
                "idempotent": False,
                "traceId": trace_id,
                "packageBalances": package_balances,
                "packageLedger": package_ledger,
            }

    @staticmethod
    def _scope_key(*, tenant_id: str | None, client_id: str | None, business_key: str | None) -> str:
        return "|".join(
            [
                f"tenant:{tenant_id or 'all'}",
                f"client:{client_id or 'all'}",
                f"business:{business_key or 'all'}",
            ]
        )

    def _collection_meta(self, row: MonthlySettlement) -> tuple[int | None, str, str]:
        if row.status == "paid":
            return None, "none", "已回款，无需催收"
        if row.status == "cancelled":
            return None, "none", "已取消，无需催收"
        issued_at = row.issued_at or row.created_at
        days = max(0, (self._now() - issued_at).days) if issued_at else 0
        if days >= 14:
            return days, "escalate", "超过 14 天未回款，建议升级跟进"
        if days >= 7:
            return days, "follow_up", "超过 7 天未回款，建议人工跟进"
        return days, "remind", "可发送常规回款提醒"

    def _settlement_to_dict(self, row: MonthlySettlement) -> dict[str, Any]:
        days, level, action = self._collection_meta(row)
        return {
            "id": row.id,
            "month": row.month,
            "scopeKey": row.scope_key,
            "tenantId": row.tenant_id,
            "clientId": row.client_id,
            "businessKey": row.business_key,
            "userCount": int(row.user_count or 0),
            "totalBalance": int(row.total_balance or 0),
            "totalFrozenBalance": int(row.total_frozen_balance or 0),
            "totalIncome": int(row.total_income or 0),
            "totalExpense": int(row.total_expense or 0),
            "totalNet": int(row.total_net or 0),
            "totalPackageRemainingUnits": int(row.total_package_remaining_units or 0),
            "issueCount": int(row.issue_count or 0),
            "packageAlertCount": int(row.package_alert_count or 0),
            "status": row.status,
            "statusLabel": self._status_label(row.status),
            "daysSinceIssued": days,
            "collectionLevel": level,
            "collectionAction": action,
            "paymentReference": row.payment_reference,
            "note": row.note,
            "issuedByUserId": row.issued_by_user_id,
            "issuedByUsername": row.issued_by_username,
            "issuedAt": self._iso(row.issued_at),
            "paidAt": self._iso(row.paid_at),
            "cancelledAt": self._iso(row.cancelled_at),
            "createdAt": self._iso(row.created_at),
            "updatedAt": self._iso(row.updated_at),
        }

    def list_monthly_settlements(
        self,
        *,
        month: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        normalized_month = self._month(month)
        try:
            with get_session() as session:
                stmt = select(MonthlySettlement).where(MonthlySettlement.month == normalized_month)
                if status and status != "all":
                    stmt = stmt.where(MonthlySettlement.status == status)
                rows = (
                    session.execute(
                        stmt.order_by(MonthlySettlement.created_at.desc()).limit(max(1, min(limit, 500)))
                    )
                    .scalars()
                    .all()
                )
        except SQLAlchemyError:
            rows = []
        return {
            "month": normalized_month,
            "status": status if status and status != "all" else None,
            "total": len(rows),
            "items": [self._settlement_to_dict(row) for row in rows],
        }

    def issue_monthly_settlement(self, payload: dict[str, Any], *, actor: User | None = None) -> dict[str, Any]:
        month = self._month(payload.get("month"))
        tenant_id = str(payload.get("tenantId") or payload.get("tenant_id") or "").strip() or None
        client_id = str(payload.get("clientId") or payload.get("client_id") or "").strip() or None
        business_key = str(payload.get("businessKey") or payload.get("business_key") or "").strip() or None
        scope_key = self._scope_key(tenant_id=tenant_id, client_id=client_id, business_key=business_key)
        window_days = int(payload.get("windowDays") or payload.get("window_days") or 30)
        now = self._now()
        with get_session() as session:
            existing = (
                session.execute(
                    select(MonthlySettlement).where(
                        MonthlySettlement.month == month,
                        MonthlySettlement.scope_key == scope_key,
                    )
                )
                .scalars()
                .first()
            )
            if existing:
                return {"settlement": self._settlement_to_dict(existing), "idempotent": True}
        overview = self.overview(
            month=month,
            window_days=window_days,
            tenant_id=tenant_id,
            client_id=client_id,
            business_key=business_key,
        )
        with get_session() as session:
            row = MonthlySettlement(
                id=f"mset_{uuid4().hex[:24]}",
                month=month,
                scope_key=scope_key,
                tenant_id=tenant_id,
                client_id=client_id,
                business_key=business_key,
                user_count=int(overview.get("totalUsers") or 0),
                total_balance=int(overview.get("totalBalance") or 0),
                total_frozen_balance=int(overview.get("totalFrozenBalance") or 0),
                total_income=int(overview.get("totalIncome") or 0),
                total_expense=int(overview.get("totalExpense") or 0),
                total_net=int(overview.get("totalNet") or 0),
                total_package_remaining_units=int(overview.get("totalPackageRemainingUnits") or 0),
                issue_count=int(overview.get("issueCount") or 0),
                package_alert_count=int(overview.get("packageAlertCount") or 0),
                status="issued",
                note=payload.get("note"),
                issued_by_user_id=self._actor_id(actor),
                issued_by_username=self._actor_name(actor),
                issued_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            return {"settlement": self._settlement_to_dict(row), "idempotent": False}

    def update_monthly_settlement(
        self,
        settlement_id: str,
        payload: dict[str, Any],
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        status = str(payload.get("status") or "").strip()
        if status and status not in {"issued", "paid", "cancelled"}:
            raise HTTPException(status_code=400, detail="MONTHLY_SETTLEMENT_STATUS_INVALID")
        now = self._now()
        with get_session() as session:
            row = session.get(MonthlySettlement, settlement_id)
            if not row:
                raise HTTPException(status_code=404, detail="MONTHLY_SETTLEMENT_NOT_FOUND")
            if status:
                row.status = status
                if status == "paid" and not row.paid_at:
                    row.paid_at = now
                if status == "cancelled" and not row.cancelled_at:
                    row.cancelled_at = now
            if "paymentReference" in payload or "payment_reference" in payload:
                row.payment_reference = payload.get("paymentReference") or payload.get("payment_reference")
            if "note" in payload:
                row.note = payload.get("note")
            row.updated_at = now
            session.add(row)
            session.commit()
            return self._settlement_to_dict(row)

    def _purchase_order_to_dict(self, row: PackagePurchaseOrder, user: User | None = None) -> dict[str, Any]:
        return {
            "id": row.id,
            "orderNo": row.order_no,
            "userId": row.user_id,
            "userName": user.username if user else row.user_id,
            "packageKey": row.package_key,
            "packageName": row.package_name,
            "businessKey": row.business_key,
            "units": int(row.units or 0),
            "unitName": row.unit_name or "次",
            "amountCents": int(row.amount_cents or 0),
            "currency": row.currency,
            "channel": row.channel,
            "status": row.status,
            "statusLabel": self._status_label(row.status),
            "paymentReference": row.payment_reference,
            "transactionId": row.transaction_id,
            "failReason": row.fail_reason,
            "note": row.note,
            "createdByUserId": row.created_by_user_id,
            "createdByUsername": row.created_by_username,
            "paidAt": self._iso(row.paid_at),
            "cancelledAt": self._iso(row.cancelled_at),
            "failedAt": self._iso(row.failed_at),
            "expiresAt": self._iso(row.expires_at),
            "createdAt": self._iso(row.created_at),
            "updatedAt": self._iso(row.updated_at),
        }

    def list_package_purchase_orders(
        self,
        *,
        status: str | None = None,
        user_id: str | None = None,
        business_key: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            with get_session() as session:
                stmt = select(PackagePurchaseOrder)
                if status and status != "all":
                    stmt = stmt.where(PackagePurchaseOrder.status == status)
                if user_id:
                    stmt = stmt.where(PackagePurchaseOrder.user_id == user_id)
                if business_key and business_key != "all":
                    stmt = stmt.where(PackagePurchaseOrder.business_key == business_key)
                rows = (
                    session.execute(
                        stmt.order_by(PackagePurchaseOrder.created_at.desc()).limit(max(1, min(limit, 500)))
                    )
                    .scalars()
                    .all()
                )
                users = {user.id: user for user in session.execute(select(User)).scalars().all()}
        except SQLAlchemyError:
            rows = []
            users = {}
        return {"total": len(rows), "items": [self._purchase_order_to_dict(row, users.get(row.user_id)) for row in rows]}

    def create_package_purchase_order(self, payload: dict[str, Any], *, actor: User | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        user_id = str(payload.get("userId") or payload.get("user_id") or "").strip()
        package_key = str(payload.get("packageKey") or payload.get("package_key") or "").strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="BILLING_USER_ID_REQUIRED")
        if not package_key:
            raise HTTPException(status_code=400, detail="PACKAGE_KEY_REQUIRED")
        now = self._now()
        with get_session() as session:
            payload = self._apply_package_catalog_defaults(session, payload, package_key)
            units = int(payload.get("units") or 0)
            amount_cents = int(payload.get("amountCents") or payload.get("amount_cents") or 0)
            if units <= 0:
                raise HTTPException(status_code=400, detail="PACKAGE_UNITS_INVALID")
            if amount_cents < 0:
                raise HTTPException(status_code=400, detail="PACKAGE_AMOUNT_INVALID")
            order = PackagePurchaseOrder(
                id=f"pkg_order_{uuid4().hex[:20]}",
                order_no=f"PO{now.strftime('%Y%m%d%H%M%S')}{uuid4().hex[:6].upper()}",
                user_id=user_id,
                package_key=package_key,
                package_name=payload.get("packageName") or payload.get("package_name"),
                business_key=str(payload.get("businessKey") or payload.get("business_key") or "").strip() or None,
                units=units,
                unit_name=payload.get("unitName") or payload.get("unit_name") or "次",
                amount_cents=amount_cents,
                currency=payload.get("currency") or "CNY",
                channel=payload.get("channel") or "offline",
                status="pending",
                note=payload.get("note"),
                created_by_user_id=self._actor_id(actor),
                created_by_username=self._actor_name(actor),
                expires_at=self._parse_datetime(payload.get("expiresAt") or payload.get("expires_at")),
                created_at=now,
                updated_at=now,
            )
            session.add(order)
            session.commit()
            user = session.get(User, user_id)
            return self._purchase_order_to_dict(order, user)

    def update_package_purchase_order(
        self,
        order_id: str,
        payload: dict[str, Any],
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        status = str(payload.get("status") or "").strip()
        if status not in {"pending", "paid", "cancelled", "failed"}:
            raise HTTPException(status_code=400, detail="PACKAGE_PURCHASE_ORDER_STATUS_INVALID")
        now = self._now()
        should_grant = False
        grant_payload: dict[str, Any] | None = None
        with get_session() as session:
            row = session.get(PackagePurchaseOrder, order_id)
            if not row:
                raise HTTPException(status_code=404, detail="PACKAGE_PURCHASE_ORDER_NOT_FOUND")
            idempotent = row.status == status
            should_grant = status == "paid" and row.status != "paid"
            row.status = status
            row.payment_reference = payload.get("paymentReference") or payload.get("payment_reference") or row.payment_reference
            row.transaction_id = payload.get("transactionId") or payload.get("transaction_id") or row.transaction_id
            row.fail_reason = payload.get("failReason") or payload.get("fail_reason") or row.fail_reason
            row.note = payload.get("note") if "note" in payload else row.note
            if status == "paid" and not row.paid_at:
                row.paid_at = now
            if status == "cancelled" and not row.cancelled_at:
                row.cancelled_at = now
            if status == "failed" and not row.failed_at:
                row.failed_at = now
            row.updated_at = now
            session.add(row)
            session.commit()
            order_dict = self._purchase_order_to_dict(row, session.get(User, row.user_id))
            if should_grant:
                grant_payload = {
                    "packageKey": row.package_key,
                    "packageName": row.package_name,
                    "businessKey": row.business_key,
                    "unitName": row.unit_name,
                    "units": int(row.units or 0),
                    "traceId": f"package_order:{row.id}",
                    "description": f"套餐订单支付入账 {row.order_no}",
                }
        package_balances = None
        package_ledger = None
        if should_grant and grant_payload:
            grant_result = self.grant_package(order_dict["userId"], grant_payload, actor=actor)
            package_balances = grant_result["packageBalances"]
            package_ledger = grant_result["packageLedger"]
        elif status == "paid":
            with get_session() as session:
                package_balances = self._package_balances(session, order_dict["userId"], business_key=order_dict["businessKey"])
                package_ledger = self._package_ledger(session, order_dict["userId"], business_key=order_dict["businessKey"])
        return {
            "order": order_dict,
            "packageBalances": package_balances,
            "packageLedger": package_ledger,
            "idempotent": idempotent,
        }

    def _invoice_to_dict(self, row: BillingInvoiceRequest, user: User | None = None) -> dict[str, Any]:
        return {
            "id": row.id,
            "invoiceNo": row.invoice_no,
            "relatedOrderType": row.related_order_type,
            "relatedOrderId": row.related_order_id,
            "userId": row.user_id,
            "userName": user.username if user else row.user_id,
            "tenantId": row.tenant_id,
            "clientId": row.client_id,
            "businessKey": row.business_key,
            "invoiceTitle": row.invoice_title,
            "taxNo": row.tax_no,
            "invoiceType": row.invoice_type,
            "amountCents": int(row.amount_cents or 0),
            "currency": row.currency,
            "deliveryEmail": row.delivery_email,
            "status": row.status,
            "statusLabel": self._status_label(row.status),
            "note": row.note,
            "createdByUserId": row.created_by_user_id,
            "createdByUsername": row.created_by_username,
            "issuedByUserId": row.issued_by_user_id,
            "issuedByUsername": row.issued_by_username,
            "issuedAt": self._iso(row.issued_at),
            "cancelledAt": self._iso(row.cancelled_at),
            "createdAt": self._iso(row.created_at),
            "updatedAt": self._iso(row.updated_at),
        }

    def list_invoice_requests(
        self,
        *,
        status: str | None = None,
        user_id: str | None = None,
        business_key: str | None = None,
        related_order_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            with get_session() as session:
                stmt = select(BillingInvoiceRequest)
                if status and status != "all":
                    stmt = stmt.where(BillingInvoiceRequest.status == status)
                if user_id:
                    stmt = stmt.where(BillingInvoiceRequest.user_id == user_id)
                if business_key and business_key != "all":
                    stmt = stmt.where(BillingInvoiceRequest.business_key == business_key)
                if related_order_type:
                    stmt = stmt.where(BillingInvoiceRequest.related_order_type == related_order_type)
                rows = (
                    session.execute(
                        stmt.order_by(BillingInvoiceRequest.created_at.desc()).limit(max(1, min(limit, 500)))
                    )
                    .scalars()
                    .all()
                )
                users = {user.id: user for user in session.execute(select(User)).scalars().all()}
        except SQLAlchemyError:
            rows = []
            users = {}
        return {"total": len(rows), "items": [self._invoice_to_dict(row, users.get(row.user_id or "")) for row in rows]}

    def create_invoice_request(self, payload: dict[str, Any], *, actor: User | None = None) -> dict[str, Any]:
        invoice_title = str(payload.get("invoiceTitle") or payload.get("invoice_title") or "").strip()
        if not invoice_title:
            raise HTTPException(status_code=400, detail="BILLING_INVOICE_TITLE_REQUIRED")
        now = self._now()
        user_id = str(payload.get("userId") or payload.get("user_id") or "").strip() or None
        row = BillingInvoiceRequest(
            id=f"inv_req_{uuid4().hex[:20]}",
            related_order_type=payload.get("relatedOrderType") or payload.get("related_order_type") or "manual",
            related_order_id=payload.get("relatedOrderId") or payload.get("related_order_id"),
            user_id=user_id,
            tenant_id=payload.get("tenantId") or payload.get("tenant_id"),
            client_id=payload.get("clientId") or payload.get("client_id"),
            business_key=payload.get("businessKey") or payload.get("business_key"),
            invoice_title=invoice_title,
            tax_no=payload.get("taxNo") or payload.get("tax_no"),
            invoice_type=payload.get("invoiceType") or payload.get("invoice_type") or "ordinary",
            amount_cents=int(payload.get("amountCents") or payload.get("amount_cents") or 0),
            currency=payload.get("currency") or "CNY",
            delivery_email=payload.get("deliveryEmail") or payload.get("delivery_email"),
            status="requested",
            note=payload.get("note"),
            created_by_user_id=self._actor_id(actor),
            created_by_username=self._actor_name(actor),
            created_at=now,
            updated_at=now,
        )
        with get_session() as session:
            session.add(row)
            session.commit()
            return self._invoice_to_dict(row, session.get(User, user_id) if user_id else None)

    def update_invoice_request(self, invoice_request_id: str, payload: dict[str, Any], *, actor: User | None = None) -> dict[str, Any]:
        status = str(payload.get("status") or "").strip()
        if status not in {"requested", "issued", "cancelled"}:
            raise HTTPException(status_code=400, detail="BILLING_INVOICE_STATUS_INVALID")
        now = self._now()
        with get_session() as session:
            row = session.get(BillingInvoiceRequest, invoice_request_id)
            if not row:
                raise HTTPException(status_code=404, detail="BILLING_INVOICE_REQUEST_NOT_FOUND")
            row.status = status
            if "invoiceNo" in payload or "invoice_no" in payload:
                row.invoice_no = payload.get("invoiceNo") or payload.get("invoice_no")
            if "note" in payload:
                row.note = payload.get("note")
            if status == "issued" and not row.issued_at:
                row.issued_at = now
                row.issued_by_user_id = self._actor_id(actor)
                row.issued_by_username = self._actor_name(actor)
            if status == "cancelled" and not row.cancelled_at:
                row.cancelled_at = now
            row.updated_at = now
            session.add(row)
            session.commit()
            return self._invoice_to_dict(row, session.get(User, row.user_id) if row.user_id else None)

    def notification_config(self) -> dict[str, Any]:
        return _NOTIFICATION_CONFIG

    def update_notification_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        channels = payload.get("channels") if isinstance(payload, dict) else None
        if not isinstance(channels, list):
            raise HTTPException(status_code=400, detail="BILLING_NOTIFICATION_CONFIG_INVALID")
        normalized = []
        for channel in channels:
            if not isinstance(channel, dict):
                continue
            webhook_url = str(channel.get("webhookUrl") or channel.get("webhook_url") or "").strip() or None
            normalized.append(
                {
                    "key": str(channel.get("key") or "ops-webhook"),
                    "displayName": channel.get("displayName") or "运维群通知",
                    "description": channel.get("description") or "用于低余额、套餐到期和月结催收提醒。",
                    "enabled": bool(channel.get("enabled")),
                    "configured": bool(webhook_url),
                    "webhookUrl": webhook_url,
                    "webhookFormat": channel.get("webhookFormat") or channel.get("webhook_format") or "generic",
                    "source": "runtime",
                }
            )
        _NOTIFICATION_CONFIG["channels"] = normalized
        return self.notification_config()

    def _primary_channel(self, webhook_format: str | None = None) -> dict[str, Any]:
        channels = _NOTIFICATION_CONFIG.get("channels") or []
        enabled = [item for item in channels if item.get("enabled")]
        channel = (enabled or channels or [{}])[0]
        if webhook_format:
            channel = {**channel, "webhookFormat": webhook_format}
        return channel

    def _notification_status(self, *, send: bool, channel: dict[str, Any]) -> tuple[str, str]:
        if not send:
            return "not_sent", "仅生成通知草稿，未发送"
        if not channel.get("configured"):
            return "not_sent", "通知通道未配置，已保留通知记录"
        return "sent", "已记录发送动作；真实外部推送将在后续接入"

    def _package_notification_to_dict(self, row: BillingNotificationLog) -> dict[str, Any]:
        response = row.response_payload or {}
        return {
            "id": row.id,
            "notificationType": row.notification_type,
            "sendStatus": row.send_status,
            "sendDetail": row.send_detail,
            "webhookFormat": row.webhook_format,
            "webhookConfigured": bool(row.webhook_configured),
            "notificationTemplate": response.get("notificationTemplate") or "",
            "nextAction": response.get("nextAction") or "",
            "alertCount": int(row.alert_count or 0),
            "expiringSoonCount": int(row.expiring_soon_count or 0),
            "lowBalanceCount": int(row.low_balance_count or 0),
            "createdByUserId": row.created_by_user_id,
            "createdByUsername": row.created_by_username,
            "sentAt": self._iso(row.sent_at),
            "createdAt": self._iso(row.created_at),
        }

    def notify_package_alerts(self, payload: dict[str, Any], *, actor: User | None = None) -> dict[str, Any]:
        limit = int(payload.get("limit") or 100)
        overview = self.overview(
            tenant_id=payload.get("tenantId") or payload.get("tenant_id"),
            client_id=payload.get("clientId") or payload.get("client_id"),
            business_key=payload.get("businessKey") or payload.get("business_key"),
            package_alert_limit=limit,
        )
        alerts = overview.get("packageAlerts") or []
        channel = self._primary_channel(payload.get("webhookFormat") or payload.get("webhook_format"))
        send_status, send_detail = self._notification_status(send=bool(payload.get("send")), channel=channel)
        now = self._now()
        response_payload = {
            "notificationTemplate": payload.get("notificationTemplate")
            or payload.get("notification_template")
            or "套餐余额/到期提醒",
            "nextAction": "处理套餐风险后重新生成提醒" if alerts else "暂无套餐风险",
        }
        notification_id = f"bill_notice_{uuid4().hex[:20]}"
        webhook_format = channel.get("webhookFormat") or "generic"
        webhook_configured = bool(channel.get("configured"))
        expiring_soon_count = len([item for item in alerts if item.get("alertType") == "expiring_soon"])
        low_balance_count = len([item for item in alerts if item.get("alertType") == "low_balance"])
        row = BillingNotificationLog(
            id=notification_id,
            notification_type="package_alert",
            send_status=send_status,
            send_detail=send_detail,
            webhook_format=webhook_format,
            webhook_configured=webhook_configured,
            alert_count=len(alerts),
            expiring_soon_count=expiring_soon_count,
            low_balance_count=low_balance_count,
            request_payload=payload,
            response_payload=response_payload,
            created_by_user_id=self._actor_id(actor),
            created_by_username=self._actor_name(actor),
            sent_at=now if send_status == "sent" else None,
            created_at=now,
        )
        with get_session() as session:
            session.add(row)
            session.commit()
        return {
            "id": notification_id,
            "generatedAt": self._iso(now),
            "sendStatus": send_status,
            "sendDetail": send_detail,
            "webhookFormat": webhook_format,
            "webhookConfigured": webhook_configured,
            "notificationTemplate": response_payload["notificationTemplate"],
            "nextAction": response_payload["nextAction"],
            "alertCount": len(alerts),
            "expiringSoonCount": expiring_soon_count,
            "lowBalanceCount": low_balance_count,
            "alerts": alerts,
        }

    def list_package_alert_notifications(self, *, limit: int = 20) -> dict[str, Any]:
        try:
            with get_session() as session:
                rows = (
                    session.execute(
                        select(BillingNotificationLog)
                        .where(BillingNotificationLog.notification_type == "package_alert")
                        .order_by(BillingNotificationLog.created_at.desc())
                        .limit(max(1, min(limit, 200)))
                    )
                    .scalars()
                    .all()
                )
        except SQLAlchemyError:
            rows = []
        return {"total": len(rows), "items": [self._package_notification_to_dict(row) for row in rows]}

    def notify_monthly_collections(self, payload: dict[str, Any], *, actor: User | None = None) -> dict[str, Any]:
        month = self._month(payload.get("month"))
        min_level = str(payload.get("minCollectionLevel") or payload.get("min_collection_level") or "remind")
        level_rank = {"none": 0, "remind": 1, "follow_up": 2, "escalate": 3}
        listing = self.list_monthly_settlements(month=month, status="issued", limit=int(payload.get("limit") or 100))
        settlements = [
            item
            for item in listing["items"]
            if level_rank.get(item.get("collectionLevel") or "none", 0) >= level_rank.get(min_level, 1)
        ]
        channel = self._primary_channel(payload.get("webhookFormat") or payload.get("webhook_format"))
        send_status, send_detail = self._notification_status(send=bool(payload.get("send")), channel=channel)
        now = self._now()
        remind_count = len([item for item in settlements if item.get("collectionLevel") == "remind"])
        follow_up_count = len([item for item in settlements if item.get("collectionLevel") == "follow_up"])
        escalate_count = len([item for item in settlements if item.get("collectionLevel") == "escalate"])
        response_payload = {
            "notificationTemplate": payload.get("notificationTemplate")
            or payload.get("notification_template")
            or "月结回款提醒",
            "nextAction": "跟进未回款月结单" if settlements else "暂无需催收月结单",
            "settlementCount": len(settlements),
            "remindCount": remind_count,
            "followUpCount": follow_up_count,
            "escalateCount": escalate_count,
        }
        notification_id = f"bill_notice_{uuid4().hex[:20]}"
        webhook_format = channel.get("webhookFormat") or "generic"
        webhook_configured = bool(channel.get("configured"))
        row = BillingNotificationLog(
            id=notification_id,
            notification_type="monthly_collection",
            send_status=send_status,
            send_detail=send_detail,
            webhook_format=webhook_format,
            webhook_configured=webhook_configured,
            alert_count=len(settlements),
            expiring_soon_count=follow_up_count,
            low_balance_count=escalate_count,
            request_payload=payload,
            response_payload=response_payload,
            created_by_user_id=self._actor_id(actor),
            created_by_username=self._actor_name(actor),
            sent_at=now if send_status == "sent" else None,
            created_at=now,
        )
        with get_session() as session:
            session.add(row)
            session.commit()
        return {
            "id": notification_id,
            "generatedAt": self._iso(now),
            "sendStatus": send_status,
            "sendDetail": send_detail,
            "webhookFormat": webhook_format,
            "webhookConfigured": webhook_configured,
            "notificationTemplate": response_payload["notificationTemplate"],
            "nextAction": response_payload["nextAction"],
            "settlementCount": len(settlements),
            "remindCount": remind_count,
            "followUpCount": follow_up_count,
            "escalateCount": escalate_count,
            "settlements": settlements,
        }

    def _monthly_notification_to_dict(self, row: BillingNotificationLog) -> dict[str, Any]:
        response = row.response_payload or {}
        return {
            "id": row.id,
            "notificationType": row.notification_type,
            "sendStatus": row.send_status,
            "sendDetail": row.send_detail,
            "webhookFormat": row.webhook_format,
            "webhookConfigured": bool(row.webhook_configured),
            "notificationTemplate": response.get("notificationTemplate") or "",
            "nextAction": response.get("nextAction") or "",
            "settlementCount": int(response.get("settlementCount") or row.alert_count or 0),
            "remindCount": int(response.get("remindCount") or 0),
            "followUpCount": int(response.get("followUpCount") or row.expiring_soon_count or 0),
            "escalateCount": int(response.get("escalateCount") or row.low_balance_count or 0),
            "createdByUserId": row.created_by_user_id,
            "createdByUsername": row.created_by_username,
            "sentAt": self._iso(row.sent_at),
            "createdAt": self._iso(row.created_at),
        }

    def list_monthly_collection_notifications(self, *, limit: int = 20) -> dict[str, Any]:
        try:
            with get_session() as session:
                rows = (
                    session.execute(
                        select(BillingNotificationLog)
                        .where(BillingNotificationLog.notification_type == "monthly_collection")
                        .order_by(BillingNotificationLog.created_at.desc())
                        .limit(max(1, min(limit, 200)))
                    )
                    .scalars()
                    .all()
                )
        except SQLAlchemyError:
            rows = []
        return {"total": len(rows), "items": [self._monthly_notification_to_dict(row) for row in rows]}


admin_billing_service = AdminBillingService()
