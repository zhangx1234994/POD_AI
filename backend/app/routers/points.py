"""临时积分接口，占位实现供前端联调。"""

from datetime import datetime
from fastapi import APIRouter, Query
from pydantic import BaseModel


class PointsCostRequest(BaseModel):
    userId: str
    action: str
    imagesCount: int = 1


router = APIRouter()


@router.post("/img/points-cost")
async def calculate_points(payload: PointsCostRequest) -> dict:
    points_per_image = 5
    total = max(1, payload.imagesCount) * points_per_image
    current_temp_points = 800
    current_recharge_points = 200
    body = {
        "pointsPerImage": points_per_image,
        "totalPointsCost": total,
        "currentTempPoints": current_temp_points,
        "currentRechargePoints": current_recharge_points,
        "currentTotalPoints": current_temp_points + current_recharge_points,
        "isSufficient": True,
    }
    return {"data": body, "code": 0}


@router.get("/points/statistics")
async def points_statistics(userId: str = Query(...)) -> dict:
    return {
        "data": {
            "userId": userId,
            "totalPoints": 1000,
            "tempPoints": 800,
            "rechargePoints": 200,
            "updatedAt": datetime.utcnow().isoformat(),
        },
        "code": 0,
    }


@router.get("/points/transactions")
async def points_transactions(
    userId: str = Query(...),
    current: int = 1,
    page: int | None = None,
    size: int = 20,
) -> dict:
    return {
        "data": [],
        "total": 0,
        "page": page or current,
        "size": size,
        "userId": userId,
    }
