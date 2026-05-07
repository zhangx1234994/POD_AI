"""Wallet domain service with DB-first storage and in-memory fallback."""

from __future__ import annotations

import os
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import engine, get_session
from app.models.wallet import RechargeOrder, TaskCostSnapshot, WalletAccount, WalletHold, WalletLedger


RECHARGE_TERMINAL_STATUSES = {"paid", "failed", "canceled"}
RECHARGE_ALLOWED_STATUSES = {"pending", *RECHARGE_TERMINAL_STATUSES}


class WalletService:
    def __init__(self) -> None:
        self._db_ready_cache: bool | None = None
        self._memory_balance: dict[str, int] = {}
        self._memory_holds: dict[str, dict[str, Any]] = {}
        self._memory_ledger: list[dict[str, Any]] = []
        self._memory_orders: dict[str, dict] = {}
        self._memory_task_cost_snapshots: dict[str, dict[str, Any]] = {}

    def reset(self) -> None:
        self._db_ready_cache = None
        self._memory_balance = {}
        self._memory_holds = {}
        self._memory_ledger = []
        self._memory_orders = {}
        self._memory_task_cost_snapshots = {}

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _db_ready(self) -> bool:
        if os.getenv("PYTEST_CURRENT_TEST"):
            return False
        if self._db_ready_cache is not None:
            return self._db_ready_cache
        try:
            inspector = inspect(engine)
            required_tables = (
                "wallet_accounts",
                "wallet_holds",
                "wallet_ledger",
                "recharge_orders",
            )
            self._db_ready_cache = all(inspector.has_table(name) for name in required_tables)
        except Exception:
            self._db_ready_cache = False
        return self._db_ready_cache

    @staticmethod
    def _task_cost_table_ready() -> bool:
        if os.getenv("PYTEST_CURRENT_TEST"):
            return False
        try:
            inspector = inspect(engine)
            return bool(inspector.has_table("task_cost_snapshots"))
        except Exception:
            return False

    @staticmethod
    def _normalize_page(page: int, page_size: int) -> tuple[int, int]:
        normalized_page = max(1, int(page or 1))
        normalized_page_size = max(1, min(200, int(page_size or 20)))
        return normalized_page, normalized_page_size

    @staticmethod
    def _month_bounds(month: str) -> tuple[datetime, datetime]:
        try:
            start = datetime.strptime(month, "%Y-%m")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="BILL_MONTH_INVALID") from exc
        if start.month == 12:
            end = datetime(start.year + 1, 1, 1)
        else:
            end = datetime(start.year, start.month + 1, 1)
        return start, end

    def _ensure_wallet_account_db(self, session: Session, user_id: str) -> WalletAccount:
        account = session.execute(select(WalletAccount).where(WalletAccount.user_id == user_id)).scalars().first()
        if account:
            return account
        account = WalletAccount(user_id=user_id, balance=500, frozen_balance=0, currency="CNY", status="active")
        session.add(account)
        session.flush()
        return account

    @staticmethod
    def _serialize_order(order: RechargeOrder) -> dict:
        return {
            "orderNo": order.order_no,
            "userId": order.user_id,
            "amount": int(order.amount),
            "channel": order.channel,
            "status": order.status,
            "createdAt": order.created_at.isoformat() if order.created_at else "",
            "paidAt": order.paid_at.isoformat() if order.paid_at else None,
            "failReason": order.fail_reason,
            "transactionId": order.transaction_id,
            "updatedAt": order.updated_at.isoformat() if order.updated_at else None,
        }

    @staticmethod
    def _to_decimal(value: float | int | str | Decimal | None, scale: str) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value)).quantize(Decimal(scale))
        except Exception:
            return None

    @staticmethod
    def _normalize_recharge_status(status: str) -> str:
        normalized = str(status or "").strip().lower()
        if normalized not in RECHARGE_ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="RECHARGE_STATUS_INVALID")
        return normalized

    @staticmethod
    def _normalize_idempotency_key(trace_id: str | None, task_id: str | None = None) -> str:
        normalized_trace_id = str(trace_id or "").strip()
        if normalized_trace_id:
            return normalized_trace_id[:64]
        normalized_task_id = str(task_id or "").strip()
        if normalized_task_id:
            return f"task:{normalized_task_id}"[:64]
        raise HTTPException(status_code=400, detail="WALLET_TRACE_ID_REQUIRED")

    @staticmethod
    def _normalize_adjustment_direction(direction: str) -> str:
        normalized = str(direction or "").strip().lower()
        if normalized in {"increase", "in", "credit", "refund"}:
            return "increase"
        if normalized in {"decrease", "out", "debit", "deduct"}:
            return "decrease"
        raise HTTPException(status_code=400, detail="WALLET_ADJUSTMENT_DIRECTION_INVALID")

    @staticmethod
    def _serialize_ledger_row(row: WalletLedger) -> dict:
        signed_points = int(row.points) if row.direction == "in" else -int(row.points)
        after_balance = int(row.balance_after)
        before_balance = after_balance - signed_points
        return {
            "id": f"txn_{row.id}",
            "changeType": "INCREASE" if signed_points >= 0 else "DECREASE",
            "points": signed_points,
            "beforeBalance": before_balance,
            "afterBalance": after_balance,
            "taskId": row.related_task_id,
            "traceId": row.trace_id,
            "description": row.remark,
            "provider": row.provider,
            "modelKey": row.model_key,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }

    def _append_ledger_db(
        self,
        *,
        session: Session,
        account: WalletAccount,
        user_id: str,
        points_delta: int,
        after_balance: int,
        biz_type: str,
        task_id: str | None,
        remark: str,
        provider: str | None = None,
        model_key: str | None = None,
        trace_id: str | None = None,
    ) -> WalletLedger:
        row = WalletLedger(
            user_id=user_id,
            wallet_id=account.id,
            biz_type=biz_type,
            direction="in" if points_delta >= 0 else "out",
            points=abs(points_delta),
            balance_after=after_balance,
            related_task_id=task_id,
            trace_id=trace_id,
            provider=provider,
            model_key=model_key,
            remark=remark,
        )
        session.add(row)
        session.flush()
        return row

    def _freeze_db(self, user_id: str, task_id: str, points: int) -> tuple[str, int]:
        with get_session() as session:
            account = self._ensure_wallet_account_db(session, user_id)
            if points > int(account.balance):
                raise HTTPException(status_code=402, detail="WALLET_INSUFFICIENT")
            hold_id = f"hold_{uuid4().hex[:14]}"
            account.balance = int(account.balance) - points
            account.frozen_balance = int(account.frozen_balance) + points
            session.add(
                WalletHold(
                    id=hold_id,
                    wallet_id=account.id,
                    user_id=user_id,
                    task_id=task_id,
                    points=points,
                    status="frozen",
                )
            )
            session.add(account)
            session.commit()
            return hold_id, int(account.balance)

    def _confirm_db(self, hold_id: str) -> int:
        with get_session() as session:
            hold = session.get(WalletHold, hold_id)
            if not hold:
                raise HTTPException(status_code=404, detail="WALLET_HOLD_NOT_FOUND")
            account = session.get(WalletAccount, hold.wallet_id)
            if not account:
                raise HTTPException(status_code=404, detail="WALLET_HOLD_NOT_FOUND")
            points = int(hold.points)
            account.frozen_balance = max(0, int(account.frozen_balance) - points)
            self._append_ledger_db(
                session=session,
                account=account,
                user_id=hold.user_id,
                points_delta=-points,
                after_balance=int(account.balance),
                biz_type="consume",
                task_id=hold.task_id,
                remark="task consume",
            )
            session.delete(hold)
            session.add(account)
            session.commit()
            return points

    def _release_db(self, hold_id: str) -> tuple[str, int]:
        with get_session() as session:
            hold = session.get(WalletHold, hold_id)
            if not hold:
                raise HTTPException(status_code=404, detail="WALLET_HOLD_NOT_FOUND")
            account = session.get(WalletAccount, hold.wallet_id)
            if not account:
                raise HTTPException(status_code=404, detail="WALLET_HOLD_NOT_FOUND")
            points = int(hold.points)
            account.balance = int(account.balance) + points
            account.frozen_balance = max(0, int(account.frozen_balance) - points)
            self._append_ledger_db(
                session=session,
                account=account,
                user_id=hold.user_id,
                points_delta=points,
                after_balance=int(account.balance),
                biz_type="refund",
                task_id=hold.task_id,
                remark="task release",
            )
            session.delete(hold)
            session.add(account)
            session.commit()
            return hold.user_id, int(account.balance)

    def _stats_db(self, user_id: str) -> dict:
        with get_session() as session:
            account = self._ensure_wallet_account_db(session, user_id)
            session.commit()
            return {
                "totalPoints": int(account.balance),
                "tempPoints": 0,
                "frozenPoints": int(account.frozen_balance),
                "grantedToday": 0,
            }

    def _balance_db(self, user_id: str) -> dict:
        with get_session() as session:
            account = self._ensure_wallet_account_db(session, user_id)
            session.commit()
            return {
                "userId": user_id,
                "balance": int(account.balance),
                "frozenBalance": int(account.frozen_balance),
                "currency": account.currency or "CNY",
            }

    def _create_recharge_order_db(self, user_id: str, amount: int, channel: str) -> dict:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="RECHARGE_AMOUNT_INVALID")
        with get_session() as session:
            self._ensure_wallet_account_db(session, user_id)
            order_no = f"rc_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"
            now = datetime.utcnow()
            order = RechargeOrder(
                order_no=order_no,
                user_id=user_id,
                amount=amount,
                channel=channel or "manual",
                status="pending",
                paid_at=None,
                created_at=now,
                updated_at=now,
            )
            session.add(order)
            session.commit()
            session.refresh(order)
            return self._serialize_order(order)

    def _get_recharge_order_db(self, order_no: str) -> dict:
        with get_session() as session:
            order = session.execute(select(RechargeOrder).where(RechargeOrder.order_no == order_no)).scalars().first()
            if not order:
                raise HTTPException(status_code=404, detail="RECHARGE_ORDER_NOT_FOUND")
            return self._serialize_order(order)

    def _update_recharge_order_status_db(
        self,
        order_no: str,
        status: str,
        fail_reason: str | None = None,
        transaction_id: str | None = None,
        task_id: str | None = None,
        trace_id: str | None = None,
        provider: str | None = None,
        model_key: str | None = None,
    ) -> dict:
        target_status = self._normalize_recharge_status(status)
        with get_session() as session:
            order = session.execute(select(RechargeOrder).where(RechargeOrder.order_no == order_no)).scalars().first()
            if not order:
                raise HTTPException(status_code=404, detail="RECHARGE_ORDER_NOT_FOUND")
            current_status = str(order.status or "").lower()
            if current_status in RECHARGE_TERMINAL_STATUSES and current_status != target_status:
                raise HTTPException(status_code=409, detail="RECHARGE_ORDER_STATUS_CONFLICT")
            if target_status == "pending":
                if current_status != "pending":
                    raise HTTPException(status_code=409, detail="RECHARGE_ORDER_STATUS_CONFLICT")
                return self._serialize_order(order)

            if target_status == "paid":
                account = self._ensure_wallet_account_db(session, order.user_id)
                if current_status != "paid":
                    account.balance = int(account.balance) + int(order.amount)
                    self._append_ledger_db(
                        session=session,
                        account=account,
                        user_id=order.user_id,
                        points_delta=int(order.amount),
                        after_balance=int(account.balance),
                        biz_type="recharge",
                        task_id=task_id,
                        trace_id=trace_id,
                        provider=provider,
                        model_key=model_key,
                        remark=f"recharge:{order.order_no}",
                    )
                    order.paid_at = datetime.utcnow()
                    session.add(account)
                order.status = "paid"
                order.fail_reason = None
                if transaction_id:
                    order.transaction_id = transaction_id
            elif target_status in {"failed", "canceled"}:
                if current_status == "paid":
                    raise HTTPException(status_code=409, detail="RECHARGE_ORDER_STATUS_CONFLICT")
                order.status = target_status
                order.fail_reason = fail_reason
                if transaction_id:
                    order.transaction_id = transaction_id
            order.updated_at = datetime.utcnow()
            session.add(order)
            session.commit()
            session.refresh(order)
            return self._serialize_order(order)

    def _ledger_db(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        page, page_size = self._normalize_page(page, page_size)
        with get_session() as session:
            self._ensure_wallet_account_db(session, user_id)
            base_query = select(WalletLedger).where(WalletLedger.user_id == user_id)
            total = int(session.scalar(select(func.count()).select_from(base_query.subquery())) or 0)
            rows = (
                session.execute(
                    base_query.order_by(WalletLedger.created_at.desc(), WalletLedger.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
                .scalars()
                .all()
            )
            session.commit()
        return {
            "userId": user_id,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "items": [self._serialize_ledger_row(row) for row in rows],
        }

    def _bill_db(self, user_id: str, month: str) -> dict:
        start, end = self._month_bounds(month if len(month) == 7 else month[:7])
        with get_session() as session:
            self._ensure_wallet_account_db(session, user_id)
            rows = (
                session.execute(
                    select(WalletLedger).where(
                        WalletLedger.user_id == user_id,
                        WalletLedger.created_at >= start,
                        WalletLedger.created_at < end,
                    )
                )
                .scalars()
                .all()
            )
            session.commit()
        income = sum(int(row.points) for row in rows if row.direction == "in")
        expense = sum(int(row.points) for row in rows if row.direction == "out")
        return {
            "userId": user_id,
            "month": start.strftime("%Y-%m"),
            "income": income,
            "expense": expense,
            "net": income - expense,
            "count": len(rows),
        }

    def _cost_snapshots_db(self, user_id: str, provider: str | None = None, model_key: str | None = None) -> dict:
        with get_session() as session:
            self._ensure_wallet_account_db(session, user_id)
            query = select(WalletLedger).where(
                WalletLedger.user_id == user_id,
                WalletLedger.direction == "out",
            )
            if provider:
                query = query.where(WalletLedger.provider == provider)
            if model_key:
                query = query.where(WalletLedger.model_key == model_key)
            rows = session.execute(query.order_by(WalletLedger.created_at.desc(), WalletLedger.id.desc())).scalars().all()
            session.commit()
        items = [
            {
                "date": row.created_at.date().isoformat() if row.created_at else "",
                "provider": row.provider or "unknown",
                "modelKey": row.model_key or "unknown",
                "points": int(row.points),
                "taskId": row.related_task_id,
            }
            for row in rows
        ]
        return {
            "userId": user_id,
            "provider": provider,
            "modelKey": model_key,
            "count": len(items),
            "totalPoints": sum(int(item.get("points") or 0) for item in items),
            "items": items,
        }

    def _record_task_cost_snapshot_db(
        self,
        *,
        task_id: str,
        user_id: str,
        provider: str,
        model_key: str,
        input_count: int,
        output_count: int,
        unit_cost: float | Decimal | None,
        total_cost: float | Decimal | None,
        pricing_version: str = "v1",
        currency: str = "USD",
    ) -> dict:
        with get_session() as session:
            existing = (
                session.execute(select(TaskCostSnapshot).where(TaskCostSnapshot.task_id == task_id)).scalars().first()
            )
            if existing:
                session.commit()
                return {
                    "taskId": existing.task_id,
                    "userId": existing.user_id,
                    "provider": existing.provider,
                    "modelKey": existing.model_key,
                    "inputCount": int(existing.input_count or 0),
                    "outputCount": int(existing.output_count or 0),
                    "unitCost": float(existing.unit_cost) if existing.unit_cost is not None else None,
                    "totalCost": float(existing.total_cost) if existing.total_cost is not None else None,
                    "pricingVersion": existing.pricing_version,
                    "currency": existing.currency,
                    "created": False,
                }
            row = TaskCostSnapshot(
                task_id=task_id,
                user_id=user_id,
                provider=provider,
                model_key=model_key,
                input_count=max(0, int(input_count or 0)),
                output_count=max(0, int(output_count or 0)),
                unit_cost=self._to_decimal(unit_cost, "0.000001"),
                total_cost=self._to_decimal(total_cost, "0.0001"),
                pricing_version=(pricing_version or "v1")[:32],
                currency=(currency or "USD")[:16],
            )
            session.add(row)
            session.commit()
            return {
                "taskId": task_id,
                "userId": user_id,
                "provider": provider,
                "modelKey": model_key,
                "inputCount": max(0, int(input_count or 0)),
                "outputCount": max(0, int(output_count or 0)),
                "unitCost": float(unit_cost) if unit_cost is not None else None,
                "totalCost": float(total_cost) if total_cost is not None else None,
                "pricingVersion": (pricing_version or "v1")[:32],
                "currency": (currency or "USD")[:16],
                "created": True,
            }

    def _usage_summary_db(self, user_id: str, window_days: int) -> dict:
        normalized_days = max(1, min(365, int(window_days or 30)))
        since = datetime.utcnow() - timedelta(days=normalized_days)
        with get_session() as session:
            self._ensure_wallet_account_db(session, user_id)
            rows = (
                session.execute(
                    select(WalletLedger).where(
                        WalletLedger.user_id == user_id,
                        WalletLedger.created_at >= since,
                    )
                )
                .scalars()
                .all()
            )
            session.commit()

        expense_total = 0
        income_total = 0
        expense_count = 0
        income_count = 0
        daily_map: dict[str, dict[str, int]] = {}
        provider_map: dict[str, dict[str, int]] = {}
        model_map: dict[str, dict[str, int]] = {}

        for row in rows:
            points = int(row.points or 0)
            date_key = row.created_at.date().isoformat() if row.created_at else ""
            daily_entry = daily_map.setdefault(date_key, {"expensePoints": 0, "incomePoints": 0, "count": 0})
            daily_entry["count"] += 1
            if row.direction == "out":
                expense_total += points
                expense_count += 1
                daily_entry["expensePoints"] += points
                provider_key = row.provider or "unknown"
                provider_entry = provider_map.setdefault(provider_key, {"count": 0, "points": 0})
                provider_entry["count"] += 1
                provider_entry["points"] += points
                model_key = row.model_key or "unknown"
                model_entry = model_map.setdefault(model_key, {"count": 0, "points": 0})
                model_entry["count"] += 1
                model_entry["points"] += points
            else:
                income_total += points
                income_count += 1
                daily_entry["incomePoints"] += points

        daily = [
            {
                "date": key,
                "expensePoints": value["expensePoints"],
                "incomePoints": value["incomePoints"],
                "count": value["count"],
            }
            for key, value in sorted(daily_map.items(), key=lambda kv: kv[0], reverse=True)
        ]
        providers = [
            {"key": key, "count": value["count"], "points": value["points"]}
            for key, value in sorted(provider_map.items(), key=lambda kv: (-kv[1]["points"], kv[0]))[:10]
        ]
        models = [
            {"key": key, "count": value["count"], "points": value["points"]}
            for key, value in sorted(model_map.items(), key=lambda kv: (-kv[1]["points"], kv[0]))[:10]
        ]
        return {
            "userId": user_id,
            "windowDays": normalized_days,
            "totalExpensePoints": expense_total,
            "totalIncomePoints": income_total,
            "expenseCount": expense_count,
            "incomeCount": income_count,
            "daily": daily,
            "providers": providers,
            "models": models,
        }

    def _record_expense_db(
        self,
        *,
        user_id: str,
        points: int,
        task_id: str | None = None,
        trace_id: str | None = None,
        provider: str | None = None,
        model_key: str | None = None,
        description: str | None = None,
    ) -> dict:
        with get_session() as session:
            account = self._ensure_wallet_account_db(session, user_id)
            existing_row = None
            normalized_trace_id = self._normalize_idempotency_key(trace_id, task_id)
            existing_row = (
                session.execute(
                    select(WalletLedger).where(
                        WalletLedger.user_id == user_id,
                        WalletLedger.biz_type == "consume",
                        WalletLedger.direction == "out",
                        WalletLedger.trace_id == normalized_trace_id,
                    )
                )
                .scalars()
                .first()
            )
            if existing_row:
                session.commit()
                return {
                    "transactionId": f"txn_{existing_row.id}",
                    "userId": user_id,
                    "deducted": int(existing_row.points),
                    "balance": int(account.balance),
                    "idempotent": True,
                    "taskId": existing_row.related_task_id,
                    "traceId": existing_row.trace_id,
                    "provider": existing_row.provider,
                    "modelKey": existing_row.model_key,
                }

            if points > int(account.balance):
                raise HTTPException(status_code=402, detail="WALLET_INSUFFICIENT")

            account.balance = int(account.balance) - points
            row = self._append_ledger_db(
                session=session,
                account=account,
                user_id=user_id,
                points_delta=-points,
                after_balance=int(account.balance),
                biz_type="consume",
                task_id=task_id,
                trace_id=normalized_trace_id,
                provider=provider,
                model_key=model_key,
                remark=description or "manual consume",
            )
            session.add(account)
            session.commit()
            return {
                "transactionId": f"txn_{row.id}",
                "userId": user_id,
                "deducted": points,
                "balance": int(account.balance),
                "idempotent": False,
                "taskId": task_id,
                "traceId": normalized_trace_id,
                "provider": provider,
                "modelKey": model_key,
            }

    def _record_adjustment_db(
        self,
        *,
        user_id: str,
        direction: str,
        points: int,
        task_id: str | None = None,
        trace_id: str | None = None,
        provider: str | None = None,
        model_key: str | None = None,
        description: str | None = None,
    ) -> dict:
        normalized_direction = self._normalize_adjustment_direction(direction)
        normalized_trace_id = self._normalize_idempotency_key(trace_id, task_id)
        with get_session() as session:
            account = self._ensure_wallet_account_db(session, user_id)
            existing_row = (
                session.execute(
                    select(WalletLedger).where(
                        WalletLedger.user_id == user_id,
                        WalletLedger.biz_type == "adjustment",
                        WalletLedger.trace_id == normalized_trace_id,
                    )
                )
                .scalars()
                .first()
            )
            if existing_row:
                session.commit()
                return {
                    "transactionId": f"txn_{existing_row.id}",
                    "userId": user_id,
                    "direction": "increase" if existing_row.direction == "in" else "decrease",
                    "adjusted": int(existing_row.points),
                    "balance": int(account.balance),
                    "idempotent": True,
                    "taskId": existing_row.related_task_id,
                    "traceId": existing_row.trace_id,
                    "provider": existing_row.provider,
                    "modelKey": existing_row.model_key,
                }

            points_delta = points if normalized_direction == "increase" else -points
            if points_delta < 0 and points > int(account.balance):
                raise HTTPException(status_code=402, detail="WALLET_INSUFFICIENT")

            account.balance = int(account.balance) + points_delta
            row = self._append_ledger_db(
                session=session,
                account=account,
                user_id=user_id,
                points_delta=points_delta,
                after_balance=int(account.balance),
                biz_type="adjustment",
                task_id=task_id,
                trace_id=normalized_trace_id,
                provider=provider,
                model_key=model_key,
                remark=description or "manual adjustment",
            )
            session.add(account)
            session.commit()
            return {
                "transactionId": f"txn_{row.id}",
                "userId": user_id,
                "direction": normalized_direction,
                "adjusted": points,
                "balance": int(account.balance),
                "idempotent": False,
                "taskId": task_id,
                "traceId": normalized_trace_id,
                "provider": provider,
                "modelKey": model_key,
            }

    def _ensure_user_memory(self, user_id: str) -> None:
        self._memory_balance.setdefault(user_id, 500)

    def _record_ledger_memory(
        self,
        *,
        user_id: str,
        change_type: str,
        points: int,
        before_balance: int,
        after_balance: int,
        task_id: str | None,
        trace_id: str | None = None,
        description: str,
        provider: str | None = None,
        model_key: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": f"txn_{uuid4().hex[:10]}",
            "userId": user_id,
            "changeType": change_type,
            "points": points,
            "beforeBalance": before_balance,
            "afterBalance": after_balance,
            "taskId": task_id,
            "traceId": trace_id,
            "description": description,
            "provider": provider,
            "modelKey": model_key,
            "createdAt": self._now_iso(),
        }
        self._memory_ledger.append(row)
        return row

    def _list_user_ledger_memory(self, user_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self._memory_ledger if row.get("userId") == user_id]
        rows.sort(key=lambda row: row.get("createdAt", ""), reverse=True)
        return rows

    def _freeze_memory(self, user_id: str, task_id: str, points: int) -> tuple[str, int]:
        self._ensure_user_memory(user_id)
        balance = self._memory_balance[user_id]
        if points > balance:
            raise HTTPException(status_code=402, detail="WALLET_INSUFFICIENT")
        hold_id = f"hold_{uuid4().hex[:14]}"
        self._memory_holds[hold_id] = {
            "userId": user_id,
            "taskId": task_id,
            "points": points,
            "createdAt": self._now_iso(),
        }
        self._memory_balance[user_id] -= points
        return hold_id, self._memory_balance[user_id]

    def _confirm_memory(self, hold_id: str) -> int:
        hold = self._memory_holds.pop(hold_id, None)
        if hold is None:
            raise HTTPException(status_code=404, detail="WALLET_HOLD_NOT_FOUND")
        user_id = str(hold.get("userId") or "")
        points = int(hold.get("points") or 0)
        before = self._memory_balance.get(user_id, 0) + points
        after = self._memory_balance.get(user_id, 0)
        self._record_ledger_memory(
            user_id=user_id,
            change_type="DECREASE",
            points=-points,
            before_balance=before,
            after_balance=after,
            task_id=hold.get("taskId"),
            description="task consume",
        )
        return points

    def _release_memory(self, hold_id: str) -> tuple[str, int]:
        hold = self._memory_holds.pop(hold_id, None)
        if hold is None:
            raise HTTPException(status_code=404, detail="WALLET_HOLD_NOT_FOUND")
        user_id = str(hold.get("userId") or "")
        points = int(hold.get("points") or 0)
        self._ensure_user_memory(user_id)
        before = self._memory_balance[user_id]
        self._memory_balance[user_id] += points
        self._record_ledger_memory(
            user_id=user_id,
            change_type="INCREASE",
            points=points,
            before_balance=before,
            after_balance=self._memory_balance[user_id],
            task_id=hold.get("taskId"),
            description="task release",
        )
        return user_id, self._memory_balance[user_id]

    def _stats_memory(self, user_id: str) -> dict:
        self._ensure_user_memory(user_id)
        frozen = sum(int(v.get("points") or 0) for v in self._memory_holds.values() if v.get("userId") == user_id)
        return {
            "totalPoints": self._memory_balance[user_id],
            "tempPoints": 0,
            "frozenPoints": frozen,
            "grantedToday": 0,
        }

    def _balance_memory(self, user_id: str) -> dict:
        self._ensure_user_memory(user_id)
        frozen = sum(int(v.get("points") or 0) for v in self._memory_holds.values() if v.get("userId") == user_id)
        return {
            "userId": user_id,
            "balance": self._memory_balance[user_id],
            "frozenBalance": frozen,
            "currency": "CNY",
        }

    def _create_recharge_order_memory(self, user_id: str, amount: int, channel: str) -> dict:
        self._ensure_user_memory(user_id)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="RECHARGE_AMOUNT_INVALID")
        order_no = f"rc_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"
        now = self._now_iso()
        order = {
            "orderNo": order_no,
            "userId": user_id,
            "amount": amount,
            "channel": channel,
            "status": "pending",
            "createdAt": now,
            "paidAt": None,
            "failReason": None,
            "transactionId": None,
            "updatedAt": now,
        }
        self._memory_orders[order_no] = order
        return order

    def _get_recharge_order_memory(self, order_no: str) -> dict:
        order = self._memory_orders.get(order_no)
        if not order:
            raise HTTPException(status_code=404, detail="RECHARGE_ORDER_NOT_FOUND")
        return order

    def _update_recharge_order_status_memory(
        self,
        order_no: str,
        status: str,
        fail_reason: str | None = None,
        transaction_id: str | None = None,
        task_id: str | None = None,
        trace_id: str | None = None,
        provider: str | None = None,
        model_key: str | None = None,
    ) -> dict:
        target_status = self._normalize_recharge_status(status)
        order = self._memory_orders.get(order_no)
        if not order:
            raise HTTPException(status_code=404, detail="RECHARGE_ORDER_NOT_FOUND")
        current_status = str(order.get("status") or "").lower()
        if current_status in RECHARGE_TERMINAL_STATUSES and current_status != target_status:
            raise HTTPException(status_code=409, detail="RECHARGE_ORDER_STATUS_CONFLICT")
        if target_status == "pending":
            if current_status != "pending":
                raise HTTPException(status_code=409, detail="RECHARGE_ORDER_STATUS_CONFLICT")
            return order
        if target_status == "paid":
            if current_status != "paid":
                user_id = str(order.get("userId") or "")
                amount = int(order.get("amount") or 0)
                self._ensure_user_memory(user_id)
                before = self._memory_balance[user_id]
                self._memory_balance[user_id] += amount
                self._record_ledger_memory(
                    user_id=user_id,
                    change_type="INCREASE",
                    points=amount,
                    before_balance=before,
                    after_balance=self._memory_balance[user_id],
                    task_id=task_id,
                    trace_id=trace_id,
                    description=f"recharge:{order_no}",
                    provider=provider,
                    model_key=model_key,
                )
                order["paidAt"] = self._now_iso()
            order["status"] = "paid"
            order["failReason"] = None
            if transaction_id:
                order["transactionId"] = transaction_id
        else:
            if current_status == "paid":
                raise HTTPException(status_code=409, detail="RECHARGE_ORDER_STATUS_CONFLICT")
            order["status"] = target_status
            order["failReason"] = fail_reason
            if transaction_id:
                order["transactionId"] = transaction_id
        order["updatedAt"] = self._now_iso()
        return order

    def _ledger_memory(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        self._ensure_user_memory(user_id)
        rows = self._list_user_ledger_memory(user_id)
        page, page_size = self._normalize_page(page, page_size)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "userId": user_id,
            "total": len(rows),
            "page": page,
            "pageSize": page_size,
            "items": rows[start:end],
        }

    def _bill_memory(self, user_id: str, month: str) -> dict:
        self._ensure_user_memory(user_id)
        prefix = f"{month[:7]}-"
        rows = [
            row
            for row in self._memory_ledger
            if row.get("userId") == user_id and str(row.get("createdAt", "")).startswith(prefix)
        ]
        total_in = sum(int(row.get("points", 0)) for row in rows if int(row.get("points", 0)) > 0)
        total_out = -sum(int(row.get("points", 0)) for row in rows if int(row.get("points", 0)) < 0)
        return {
            "userId": user_id,
            "month": month[:7],
            "income": total_in,
            "expense": total_out,
            "net": total_in - total_out,
            "count": len(rows),
        }

    def _cost_snapshots_memory(
        self, user_id: str, provider: str | None = None, model_key: str | None = None
    ) -> dict:
        self._ensure_user_memory(user_id)
        rows = self._list_user_ledger_memory(user_id)
        snapshots: list[dict[str, Any]] = []
        for row in rows:
            points = int(row.get("points", 0))
            if points >= 0:
                continue
            provider_value = row.get("provider") or "unknown"
            model_value = row.get("modelKey") or "unknown"
            if provider and provider != provider_value:
                continue
            if model_key and model_key != model_value:
                continue
            snapshots.append(
                {
                    "date": str(row.get("createdAt", ""))[:10],
                    "provider": provider_value,
                    "modelKey": model_value,
                    "points": abs(points),
                    "taskId": row.get("taskId"),
                }
            )
        return {
            "userId": user_id,
            "provider": provider,
            "modelKey": model_key,
            "count": len(snapshots),
            "totalPoints": sum(int(item.get("points") or 0) for item in snapshots),
            "items": snapshots,
        }

    def _usage_summary_memory(self, user_id: str, window_days: int) -> dict:
        self._ensure_user_memory(user_id)
        normalized_days = max(1, min(365, int(window_days or 30)))
        since = datetime.now(timezone.utc) - timedelta(days=normalized_days)
        rows = []
        for row in self._memory_ledger:
            if row.get("userId") != user_id:
                continue
            created_raw = str(row.get("createdAt") or "")
            try:
                created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            except ValueError:
                created_at = None
            if created_at and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at and created_at < since:
                continue
            rows.append(row)

        expense_total = 0
        income_total = 0
        expense_count = 0
        income_count = 0
        daily_map: dict[str, dict[str, int]] = {}
        provider_map: dict[str, dict[str, int]] = {}
        model_map: dict[str, dict[str, int]] = {}

        for row in rows:
            raw_points = int(row.get("points") or 0)
            date_key = str(row.get("createdAt") or "")[:10]
            daily_entry = daily_map.setdefault(date_key, {"expensePoints": 0, "incomePoints": 0, "count": 0})
            daily_entry["count"] += 1
            if raw_points < 0:
                points = abs(raw_points)
                expense_total += points
                expense_count += 1
                daily_entry["expensePoints"] += points
                provider_key = str(row.get("provider") or "unknown")
                provider_entry = provider_map.setdefault(provider_key, {"count": 0, "points": 0})
                provider_entry["count"] += 1
                provider_entry["points"] += points
                model_key = str(row.get("modelKey") or "unknown")
                model_entry = model_map.setdefault(model_key, {"count": 0, "points": 0})
                model_entry["count"] += 1
                model_entry["points"] += points
            elif raw_points > 0:
                income_total += raw_points
                income_count += 1
                daily_entry["incomePoints"] += raw_points

        daily = [
            {
                "date": key,
                "expensePoints": value["expensePoints"],
                "incomePoints": value["incomePoints"],
                "count": value["count"],
            }
            for key, value in sorted(daily_map.items(), key=lambda kv: kv[0], reverse=True)
        ]
        providers = [
            {"key": key, "count": value["count"], "points": value["points"]}
            for key, value in sorted(provider_map.items(), key=lambda kv: (-kv[1]["points"], kv[0]))[:10]
        ]
        models = [
            {"key": key, "count": value["count"], "points": value["points"]}
            for key, value in sorted(model_map.items(), key=lambda kv: (-kv[1]["points"], kv[0]))[:10]
        ]
        return {
            "userId": user_id,
            "windowDays": normalized_days,
            "totalExpensePoints": expense_total,
            "totalIncomePoints": income_total,
            "expenseCount": expense_count,
            "incomeCount": income_count,
            "daily": daily,
            "providers": providers,
            "models": models,
        }

    def _record_task_cost_snapshot_memory(
        self,
        *,
        task_id: str,
        user_id: str,
        provider: str,
        model_key: str,
        input_count: int,
        output_count: int,
        unit_cost: float | Decimal | None,
        total_cost: float | Decimal | None,
        pricing_version: str = "v1",
        currency: str = "USD",
    ) -> dict:
        existing = self._memory_task_cost_snapshots.get(task_id)
        if existing:
            return {**existing, "created": False}
        data = {
            "taskId": task_id,
            "userId": user_id,
            "provider": provider,
            "modelKey": model_key,
            "inputCount": max(0, int(input_count or 0)),
            "outputCount": max(0, int(output_count or 0)),
            "unitCost": float(unit_cost) if unit_cost is not None else None,
            "totalCost": float(total_cost) if total_cost is not None else None,
            "pricingVersion": (pricing_version or "v1")[:32],
            "currency": (currency or "USD")[:16],
        }
        self._memory_task_cost_snapshots[task_id] = data
        return {**data, "created": True}

    def _record_expense_memory(
        self,
        *,
        user_id: str,
        points: int,
        task_id: str | None = None,
        trace_id: str | None = None,
        provider: str | None = None,
        model_key: str | None = None,
        description: str | None = None,
    ) -> dict:
        self._ensure_user_memory(user_id)
        normalized_trace_id = self._normalize_idempotency_key(trace_id, task_id)
        for row in self._memory_ledger:
            if (
                row.get("userId") == user_id
                and row.get("changeType") == "DECREASE"
                and row.get("traceId") == normalized_trace_id
            ):
                return {
                    "transactionId": str(row.get("id")),
                    "userId": user_id,
                    "deducted": abs(int(row.get("points") or 0)),
                    "balance": int(self._memory_balance.get(user_id) or 0),
                    "idempotent": True,
                    "taskId": row.get("taskId"),
                    "traceId": row.get("traceId"),
                    "provider": row.get("provider"),
                    "modelKey": row.get("modelKey"),
                }

        if points > int(self._memory_balance.get(user_id) or 0):
            raise HTTPException(status_code=402, detail="WALLET_INSUFFICIENT")

        before = int(self._memory_balance[user_id])
        self._memory_balance[user_id] = before - points
        row = self._record_ledger_memory(
            user_id=user_id,
            change_type="DECREASE",
            points=-points,
            before_balance=before,
            after_balance=self._memory_balance[user_id],
            task_id=task_id,
            trace_id=normalized_trace_id,
            description=description or "manual consume",
            provider=provider,
            model_key=model_key,
        )
        return {
            "transactionId": str(row.get("id")),
            "userId": user_id,
            "deducted": points,
            "balance": int(self._memory_balance[user_id]),
            "idempotent": False,
            "taskId": task_id,
            "traceId": normalized_trace_id,
            "provider": provider,
            "modelKey": model_key,
        }

    def _record_adjustment_memory(
        self,
        *,
        user_id: str,
        direction: str,
        points: int,
        task_id: str | None = None,
        trace_id: str | None = None,
        provider: str | None = None,
        model_key: str | None = None,
        description: str | None = None,
    ) -> dict:
        self._ensure_user_memory(user_id)
        normalized_direction = self._normalize_adjustment_direction(direction)
        normalized_trace_id = self._normalize_idempotency_key(trace_id, task_id)
        for row in self._memory_ledger:
            if (
                row.get("userId") == user_id
                and row.get("traceId") == normalized_trace_id
                and str(row.get("description") or "").startswith("adjustment:")
            ):
                raw_points = int(row.get("points") or 0)
                return {
                    "transactionId": str(row.get("id")),
                    "userId": user_id,
                    "direction": "increase" if raw_points >= 0 else "decrease",
                    "adjusted": abs(raw_points),
                    "balance": int(self._memory_balance.get(user_id) or 0),
                    "idempotent": True,
                    "taskId": row.get("taskId"),
                    "traceId": row.get("traceId"),
                    "provider": row.get("provider"),
                    "modelKey": row.get("modelKey"),
                }

        points_delta = points if normalized_direction == "increase" else -points
        if points_delta < 0 and points > int(self._memory_balance.get(user_id) or 0):
            raise HTTPException(status_code=402, detail="WALLET_INSUFFICIENT")

        before = int(self._memory_balance[user_id])
        self._memory_balance[user_id] = before + points_delta
        row = self._record_ledger_memory(
            user_id=user_id,
            change_type="INCREASE" if points_delta >= 0 else "DECREASE",
            points=points_delta,
            before_balance=before,
            after_balance=self._memory_balance[user_id],
            task_id=task_id,
            trace_id=normalized_trace_id,
            description=f"adjustment:{description or 'manual adjustment'}",
            provider=provider,
            model_key=model_key,
        )
        return {
            "transactionId": str(row.get("id")),
            "userId": user_id,
            "direction": normalized_direction,
            "adjusted": points,
            "balance": int(self._memory_balance[user_id]),
            "idempotent": False,
            "taskId": task_id,
            "traceId": normalized_trace_id,
            "provider": provider,
            "modelKey": model_key,
        }

    def freeze(self, user_id: str, task_id: str, points: int) -> tuple[str, int]:
        if self._db_ready():
            try:
                return self._freeze_db(user_id, task_id, points)
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._freeze_memory(user_id, task_id, points)

    def confirm(self, hold_id: str) -> int:
        if self._db_ready():
            try:
                return self._confirm_db(hold_id)
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._confirm_memory(hold_id)

    def release(self, hold_id: str) -> tuple[str, int]:
        if self._db_ready():
            try:
                return self._release_db(hold_id)
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._release_memory(hold_id)

    def stats(self, user_id: str) -> dict:
        if self._db_ready():
            try:
                return self._stats_db(user_id)
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._stats_memory(user_id)

    def balance(self, user_id: str) -> dict:
        if self._db_ready():
            try:
                return self._balance_db(user_id)
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._balance_memory(user_id)

    def create_recharge_order(self, user_id: str, amount: int, channel: str) -> dict:
        if self._db_ready():
            try:
                return self._create_recharge_order_db(user_id, amount, channel)
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._create_recharge_order_memory(user_id, amount, channel)

    def get_recharge_order(self, order_no: str) -> dict:
        if self._db_ready():
            try:
                return self._get_recharge_order_db(order_no)
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._get_recharge_order_memory(order_no)

    def update_recharge_order_status(
        self,
        order_no: str,
        status: str,
        fail_reason: str | None = None,
        transaction_id: str | None = None,
        task_id: str | None = None,
        trace_id: str | None = None,
        provider: str | None = None,
        model_key: str | None = None,
    ) -> dict:
        if self._db_ready():
            try:
                return self._update_recharge_order_status_db(
                    order_no=order_no,
                    status=status,
                    fail_reason=fail_reason,
                    transaction_id=transaction_id,
                    task_id=task_id,
                    trace_id=trace_id,
                    provider=provider,
                    model_key=model_key,
                )
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._update_recharge_order_status_memory(
            order_no=order_no,
            status=status,
            fail_reason=fail_reason,
            transaction_id=transaction_id,
            task_id=task_id,
            trace_id=trace_id,
            provider=provider,
            model_key=model_key,
        )

    def ledger(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        if self._db_ready():
            try:
                return self._ledger_db(user_id, page=page, page_size=page_size)
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._ledger_memory(user_id, page=page, page_size=page_size)

    def bill(self, user_id: str, month: str) -> dict:
        month_value = month[:7]
        self._month_bounds(month_value)
        if self._db_ready():
            try:
                return self._bill_db(user_id, month_value)
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._bill_memory(user_id, month_value)

    def cost_snapshots(self, user_id: str, provider: str | None = None, model_key: str | None = None) -> dict:
        if self._db_ready():
            try:
                return self._cost_snapshots_db(user_id, provider=provider, model_key=model_key)
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._cost_snapshots_memory(user_id, provider=provider, model_key=model_key)

    def usage_summary(self, user_id: str, window_days: int = 30) -> dict:
        if self._db_ready():
            try:
                return self._usage_summary_db(user_id, window_days=window_days)
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._usage_summary_memory(user_id, window_days=window_days)

    def record_expense(
        self,
        *,
        user_id: str,
        points: int,
        task_id: str | None = None,
        trace_id: str | None = None,
        provider: str | None = None,
        model_key: str | None = None,
        description: str | None = None,
    ) -> dict:
        if self._db_ready():
            try:
                return self._record_expense_db(
                    user_id=user_id,
                    points=points,
                    task_id=task_id,
                    trace_id=trace_id,
                    provider=provider,
                    model_key=model_key,
                    description=description,
                )
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._record_expense_memory(
            user_id=user_id,
            points=points,
            task_id=task_id,
            trace_id=trace_id,
            provider=provider,
            model_key=model_key,
            description=description,
        )

    def record_adjustment(
        self,
        *,
        user_id: str,
        direction: str,
        points: int,
        task_id: str | None = None,
        trace_id: str | None = None,
        provider: str | None = None,
        model_key: str | None = None,
        description: str | None = None,
    ) -> dict:
        if self._db_ready():
            try:
                return self._record_adjustment_db(
                    user_id=user_id,
                    direction=direction,
                    points=points,
                    task_id=task_id,
                    trace_id=trace_id,
                    provider=provider,
                    model_key=model_key,
                    description=description,
                )
            except SQLAlchemyError:
                self._db_ready_cache = False
        return self._record_adjustment_memory(
            user_id=user_id,
            direction=direction,
            points=points,
            task_id=task_id,
            trace_id=trace_id,
            provider=provider,
            model_key=model_key,
            description=description,
        )

    def record_task_cost_snapshot(
        self,
        *,
        task_id: str,
        user_id: str,
        provider: str,
        model_key: str,
        input_count: int,
        output_count: int,
        unit_cost: float | Decimal | None,
        total_cost: float | Decimal | None,
        pricing_version: str = "v1",
        currency: str = "USD",
    ) -> dict:
        if self._task_cost_table_ready():
            try:
                return self._record_task_cost_snapshot_db(
                    task_id=task_id,
                    user_id=user_id,
                    provider=provider,
                    model_key=model_key,
                    input_count=input_count,
                    output_count=output_count,
                    unit_cost=unit_cost,
                    total_cost=total_cost,
                    pricing_version=pricing_version,
                    currency=currency,
                )
            except SQLAlchemyError:
                pass
        return self._record_task_cost_snapshot_memory(
            task_id=task_id,
            user_id=user_id,
            provider=provider,
            model_key=model_key,
            input_count=input_count,
            output_count=output_count,
            unit_cost=unit_cost,
            total_cost=total_cost,
            pricing_version=pricing_version,
            currency=currency,
        )


wallet_service = WalletService()
