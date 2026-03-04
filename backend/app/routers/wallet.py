"""Wallet Service 路由，占位实现。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.config import get_settings
from app.schemas import wallet as schemas
from app.services.wallet import wallet_service

router = APIRouter()


def _require_recharge_callback_token(request: Request) -> None:
    expected = (get_settings().wallet_callback_token or "").strip()
    if not expected:
        return
    token = (
        request.headers.get("X-Wallet-Callback-Token")
        or request.query_params.get("callback_token")
        or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    )
    if token != expected:
        raise HTTPException(status_code=401, detail="RECHARGE_CALLBACK_UNAUTHORIZED")


@router.post("/v1/freeze", response_model=schemas.FreezeResponse)
async def freeze_points(payload: schemas.FreezeRequest) -> schemas.FreezeResponse:
    hold_id, balance = wallet_service.freeze(payload.userId, payload.taskId, payload.points)
    return schemas.FreezeResponse(holdId=hold_id, balance=balance)


@router.post("/v1/confirm")
async def confirm_points(payload: schemas.HoldActionRequest) -> dict:
    points = wallet_service.confirm(payload.holdId)
    return {"success": True, "deducted": points}


@router.post("/v1/release")
async def release_points(payload: schemas.HoldActionRequest) -> dict:
    user_id, balance = wallet_service.release(payload.holdId)
    return {"success": True, "released": payload.holdId, "userId": user_id, "balance": balance}


@router.get("/v1/transactions", response_model=schemas.TransactionsResponse)
async def list_transactions(query: schemas.TransactionsQuery = Depends()) -> schemas.TransactionsResponse:
    page_data = wallet_service.ledger(query.userId, query.page, query.pageSize)
    return schemas.TransactionsResponse(total=page_data["total"], items=page_data["items"])


@router.get("/v1/statistics", response_model=schemas.StatisticsResponse)
async def statistics(userId: str) -> schemas.StatisticsResponse:
    stats = wallet_service.stats(userId)
    return schemas.StatisticsResponse(**stats)


@router.get("/v1/balance", response_model=schemas.BalanceResponse)
async def balance(userId: str) -> schemas.BalanceResponse:
    data = wallet_service.balance(userId)
    return schemas.BalanceResponse(**data)


@router.post("/v1/recharge-orders", response_model=schemas.RechargeOrderResponse)
async def create_recharge_order(payload: schemas.RechargeOrderCreateRequest) -> schemas.RechargeOrderResponse:
    order = wallet_service.create_recharge_order(payload.userId, payload.amount, payload.channel)
    return schemas.RechargeOrderResponse(**order)


@router.get("/v1/recharge-orders/{order_no}", response_model=schemas.RechargeOrderResponse)
async def get_recharge_order(order_no: str) -> schemas.RechargeOrderResponse:
    order = wallet_service.get_recharge_order(order_no)
    return schemas.RechargeOrderResponse(**order)


@router.post("/v1/recharge-orders/{order_no}/status", response_model=schemas.RechargeOrderResponse)
async def update_recharge_order_status(
    request: Request,
    order_no: str,
    payload: schemas.RechargeOrderStatusUpdateRequest,
) -> schemas.RechargeOrderResponse:
    _require_recharge_callback_token(request)
    order = wallet_service.update_recharge_order_status(
        order_no=order_no,
        status=payload.status,
        fail_reason=payload.failReason,
        transaction_id=payload.transactionId,
    )
    return schemas.RechargeOrderResponse(**order)


@router.get("/v1/ledger", response_model=schemas.LedgerResponse)
async def list_ledger(
    userId: str,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=200),
) -> schemas.LedgerResponse:
    data = wallet_service.ledger(userId, page, pageSize)
    return schemas.LedgerResponse(**data)


@router.get("/v1/bills", response_model=schemas.BillResponse)
async def get_bill(
    userId: str,
    month: str | None = Query(default=None, description="YYYY-MM"),
) -> schemas.BillResponse:
    month_value = month or datetime.now(timezone.utc).strftime("%Y-%m")
    data = wallet_service.bill(userId, month_value)
    return schemas.BillResponse(**data)


@router.get("/v1/cost-snapshots", response_model=schemas.CostSnapshotResponse)
async def list_cost_snapshots(
    userId: str,
    provider: str | None = None,
    modelKey: str | None = None,
) -> schemas.CostSnapshotResponse:
    data = wallet_service.cost_snapshots(userId, provider=provider, model_key=modelKey)
    return schemas.CostSnapshotResponse(**data)
