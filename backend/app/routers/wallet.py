"""Wallet Service 路由，占位实现。"""

from fastapi import APIRouter

from app.schemas import wallet as schemas
from app.services.wallet import wallet_service

router = APIRouter()

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
async def list_transactions(query: schemas.TransactionsQuery = schemas.TransactionsQuery(userId="")) -> schemas.TransactionsResponse:
    # TODO: 查询数据库
    _ = query
    item = schemas.TransactionItem(
        id="txn_demo",
        changeType="DECREASE",
        points=-50,
        beforeBalance=550,
        afterBalance=500,
        taskId="tsk_demo",
        description="demo deduction",
    )
    return schemas.TransactionsResponse(total=1, items=[item])


@router.get("/v1/statistics", response_model=schemas.StatisticsResponse)
async def statistics(userId: str) -> schemas.StatisticsResponse:
    stats = wallet_service.stats(userId)
    return schemas.StatisticsResponse(**stats)
