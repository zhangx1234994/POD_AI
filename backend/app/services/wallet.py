"""Wallet domain service with DB-first storage and in-memory fallback."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import engine, get_session
from app.models.wallet import RechargeOrder, WalletAccount, WalletHold, WalletLedger


class WalletService:
    def __init__(self) -> None:
        self._db_ready_cache: bool | None = None
        self._memory_balance: dict[str, int] = {}
        self._memory_holds: dict[str, dict[str, Any]] = {}
        self._memory_ledger: list[dict[str, Any]] = []
        self._memory_orders: dict[str, dict] = {}

    def reset(self) -> None:
        self._db_ready_cache = None
        self._memory_balance = {}
        self._memory_holds = {}
        self._memory_ledger = []
        self._memory_orders = {}

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
        }

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
    ) -> None:
        session.add(
            WalletLedger(
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
        )

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
            account = self._ensure_wallet_account_db(session, user_id)
            order_no = f"rc_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"
            now = datetime.utcnow()
            account.balance = int(account.balance) + amount
            order = RechargeOrder(
                order_no=order_no,
                user_id=user_id,
                amount=amount,
                channel=channel or "manual",
                status="paid",
                paid_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(order)
            self._append_ledger_db(
                session=session,
                account=account,
                user_id=user_id,
                points_delta=amount,
                after_balance=int(account.balance),
                biz_type="recharge",
                task_id=None,
                remark=f"recharge:{order_no}",
            )
            session.add(account)
            session.commit()
            session.refresh(order)
            return self._serialize_order(order)

    def _get_recharge_order_db(self, order_no: str) -> dict:
        with get_session() as session:
            order = session.execute(select(RechargeOrder).where(RechargeOrder.order_no == order_no)).scalars().first()
            if not order:
                raise HTTPException(status_code=404, detail="RECHARGE_ORDER_NOT_FOUND")
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
        before = self._memory_balance[user_id]
        self._memory_balance[user_id] += amount
        now = self._now_iso()
        order = {
            "orderNo": order_no,
            "userId": user_id,
            "amount": amount,
            "channel": channel,
            "status": "paid",
            "createdAt": now,
            "paidAt": now,
        }
        self._memory_orders[order_no] = order
        self._record_ledger_memory(
            user_id=user_id,
            change_type="INCREASE",
            points=amount,
            before_balance=before,
            after_balance=self._memory_balance[user_id],
            task_id=None,
            description=f"recharge:{order_no}",
        )
        return order

    def _get_recharge_order_memory(self, order_no: str) -> dict:
        order = self._memory_orders.get(order_no)
        if not order:
            raise HTTPException(status_code=404, detail="RECHARGE_ORDER_NOT_FOUND")
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


wallet_service = WalletService()
