"""Authenticated client and operations endpoints for physical production orders."""

from fastapi import APIRouter, Depends, Query

from app.deps.auth import get_current_user, require_admin
from app.models.user import User
from app.schemas import production_order as schemas
from app.services.production_orders import production_order_service


client_router = APIRouter(prefix="/api/client/production-orders", tags=["client-production-orders"])
admin_router = APIRouter(prefix="/admin/production-orders", tags=["admin-production-orders"])


@client_router.post("", response_model=schemas.ProductionOrderOut)
def create_order(payload: schemas.ProductionOrderCreateInput, user: User = Depends(get_current_user)) -> dict:
    return production_order_service.create(user=user, payload=payload)


@client_router.get("", response_model=list[schemas.ProductionOrderOut])
def list_orders(limit: int = Query(default=100, ge=1, le=200), user: User = Depends(get_current_user)) -> list[dict]:
    return production_order_service.list_for_user(user=user, limit=limit)


@client_router.get("/{order_id}", response_model=schemas.ProductionOrderOut)
def get_order(order_id: str, user: User = Depends(get_current_user)) -> dict:
    return production_order_service.get_for_user(user=user, order_id=order_id)


@admin_router.get("", response_model=list[schemas.ProductionOrderOut])
def list_ops_orders(
    status: str | None = Query(default=None), limit: int = Query(default=200, ge=1, le=500), user: User = Depends(require_admin)
) -> list[dict]:
    return production_order_service.list_for_ops(status=status, limit=limit)


@admin_router.post("/{order_id}/mark-paid", response_model=schemas.ProductionOrderOut)
def mark_paid_for_controlled_test(
    order_id: str, payload: schemas.ProductionOrderPayInput, user: User = Depends(require_admin)
) -> dict:
    """Temporary controlled test action. Replace its caller with the payment callback once WeChat Pay is enabled."""
    return production_order_service.mark_paid_for_gateway(
        order_id=order_id, actor=user, payment_reference=payload.paymentReference, test_mode=True
    )


@admin_router.post("/{order_id}/submit-fengniao", response_model=schemas.ProductionOrderOut)
def submit_to_fengniao(
    order_id: str, payload: schemas.ProductionOrderOpsSubmitInput, user: User = Depends(require_admin)
) -> dict:
    return production_order_service.submit_to_fengniao(
        order_id=order_id, actor=user, confirm_production=payload.confirmProduction
    )


@admin_router.post("/{order_id}/sync-fengniao", response_model=schemas.ProductionOrderOut)
def sync_fengniao(order_id: str, user: User = Depends(require_admin)) -> dict:
    return production_order_service.sync_fengniao(order_id=order_id, actor=user)
