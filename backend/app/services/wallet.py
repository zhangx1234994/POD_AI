"""Wallet 领域服务，先用内存模拟，后续接数据库。"""

from typing import Dict

from fastapi import HTTPException


class WalletService:
    def __init__(self) -> None:
        self._balance: Dict[str, int] = {}
        self._holds: Dict[str, int] = {}

    def ensure_user(self, user_id: str) -> None:
        self._balance.setdefault(user_id, 500)

    def freeze(self, user_id: str, task_id: str, points: int) -> tuple[str, int]:
        self.ensure_user(user_id)
        balance = self._balance[user_id]
        if points > balance:
            raise HTTPException(status_code=402, detail="WALLET_INSUFFICIENT")
        hold_id = f"hold_{task_id}_{user_id}"
        self._holds[hold_id] = points
        self._balance[user_id] -= points
        return hold_id, self._balance[user_id]

    def confirm(self, hold_id: str) -> int:
        points = self._holds.pop(hold_id, None)
        if points is None:
            raise HTTPException(status_code=404, detail="WALLET_HOLD_NOT_FOUND")
        return points

    def release(self, hold_id: str) -> tuple[str, int]:
        points = self._holds.pop(hold_id, None)
        if points is None:
            raise HTTPException(status_code=404, detail="WALLET_HOLD_NOT_FOUND")
        user_id = hold_id.split("_")[-1]
        self.ensure_user(user_id)
        self._balance[user_id] += points
        return user_id, self._balance[user_id]

    def stats(self, user_id: str) -> dict:
        self.ensure_user(user_id)
        frozen = sum(v for k, v in self._holds.items() if k.endswith(user_id))
        return {
            "totalPoints": self._balance[user_id],
            "tempPoints": 0,
            "frozenPoints": frozen,
            "grantedToday": 0,
        }


wallet_service = WalletService()
