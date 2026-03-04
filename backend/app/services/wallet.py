"""Wallet 领域服务，先用内存模拟，后续接数据库。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from fastapi import HTTPException


class WalletService:
    def __init__(self) -> None:
        self._balance: Dict[str, int] = {}
        self._holds: Dict[str, dict[str, Any]] = {}
        self._ledger: list[dict[str, Any]] = []
        self._orders: Dict[str, dict] = {}

    def reset(self) -> None:
        self._balance = {}
        self._holds = {}
        self._ledger = []
        self._orders = {}

    def ensure_user(self, user_id: str) -> None:
        self._balance.setdefault(user_id, 500)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _record_ledger(
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
        self._ledger.append(row)
        return row

    @staticmethod
    def _normalize_page(page: int, page_size: int) -> tuple[int, int]:
        normalized_page = max(1, int(page or 1))
        normalized_page_size = max(1, min(200, int(page_size or 20)))
        return normalized_page, normalized_page_size

    def _list_user_ledger(self, user_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self._ledger if row.get("userId") == user_id]
        rows.sort(key=lambda row: row.get("createdAt", ""), reverse=True)
        return rows

    def freeze(self, user_id: str, task_id: str, points: int) -> tuple[str, int]:
        self.ensure_user(user_id)
        balance = self._balance[user_id]
        if points > balance:
            raise HTTPException(status_code=402, detail="WALLET_INSUFFICIENT")
        hold_id = f"hold_{uuid4().hex[:14]}"
        self._holds[hold_id] = {
            "userId": user_id,
            "taskId": task_id,
            "points": points,
            "createdAt": self._now_iso(),
        }
        self._balance[user_id] -= points
        return hold_id, self._balance[user_id]

    def confirm(self, hold_id: str) -> int:
        hold = self._holds.pop(hold_id, None)
        if hold is None:
            raise HTTPException(status_code=404, detail="WALLET_HOLD_NOT_FOUND")
        user_id = str(hold.get("userId") or "")
        points = int(hold.get("points") or 0)
        before = self._balance.get(user_id, 0) + points
        after = self._balance.get(user_id, 0)
        self._record_ledger(
            user_id=user_id,
            change_type="DECREASE",
            points=-points,
            before_balance=before,
            after_balance=after,
            task_id=hold.get("taskId"),
            description="task consume",
        )
        return points

    def release(self, hold_id: str) -> tuple[str, int]:
        hold = self._holds.pop(hold_id, None)
        if hold is None:
            raise HTTPException(status_code=404, detail="WALLET_HOLD_NOT_FOUND")
        user_id = str(hold.get("userId") or "")
        points = int(hold.get("points") or 0)
        self.ensure_user(user_id)
        before = self._balance[user_id]
        self._balance[user_id] += points
        self._record_ledger(
            user_id=user_id,
            change_type="INCREASE",
            points=points,
            before_balance=before,
            after_balance=self._balance[user_id],
            task_id=hold.get("taskId"),
            description="task release",
        )
        return user_id, self._balance[user_id]

    def stats(self, user_id: str) -> dict:
        self.ensure_user(user_id)
        frozen = sum(int(v.get("points") or 0) for v in self._holds.values() if v.get("userId") == user_id)
        return {
            "totalPoints": self._balance[user_id],
            "tempPoints": 0,
            "frozenPoints": frozen,
            "grantedToday": 0,
        }

    def balance(self, user_id: str) -> dict:
        self.ensure_user(user_id)
        frozen = sum(int(v.get("points") or 0) for v in self._holds.values() if v.get("userId") == user_id)
        return {
            "userId": user_id,
            "balance": self._balance[user_id],
            "frozenBalance": frozen,
            "currency": "CNY",
        }

    def create_recharge_order(self, user_id: str, amount: int, channel: str) -> dict:
        self.ensure_user(user_id)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="RECHARGE_AMOUNT_INVALID")
        order_no = f"rc_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"
        before = self._balance[user_id]
        self._balance[user_id] += amount
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
        self._orders[order_no] = order
        self._record_ledger(
            user_id=user_id,
            change_type="INCREASE",
            points=amount,
            before_balance=before,
            after_balance=self._balance[user_id],
            task_id=None,
            description=f"recharge:{order_no}",
        )
        return order

    def get_recharge_order(self, order_no: str) -> dict:
        order = self._orders.get(order_no)
        if not order:
            raise HTTPException(status_code=404, detail="RECHARGE_ORDER_NOT_FOUND")
        return order

    def ledger(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        self.ensure_user(user_id)
        rows = self._list_user_ledger(user_id)
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

    def bill(self, user_id: str, month: str) -> dict:
        self.ensure_user(user_id)
        prefix = f"{month}-" if len(month) == 7 else month
        rows = [row for row in self._ledger if row.get("userId") == user_id and str(row.get("createdAt", "")).startswith(prefix)]
        total_in = sum(int(row.get("points", 0)) for row in rows if int(row.get("points", 0)) > 0)
        total_out = -sum(int(row.get("points", 0)) for row in rows if int(row.get("points", 0)) < 0)
        return {
            "userId": user_id,
            "month": month,
            "income": total_in,
            "expense": total_out,
            "net": total_in - total_out,
            "count": len(rows),
        }

    def cost_snapshots(self, user_id: str, provider: str | None = None, model_key: str | None = None) -> dict:
        self.ensure_user(user_id)
        rows = self._list_user_ledger(user_id)
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


wallet_service = WalletService()
