"""Production-order orchestration: exact artwork -> payment -> Fengniao."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.production_order import ProductionOrder, ProductionOrderEvent, ProductionOrderItem
from app.models.user import User
from app.schemas import production_order as schemas
from app.services.humcustom_supply_chain import HumcustomSupplyChainError, humcustom_supply_chain_client
from app.services.media_ingest import media_ingest_service
from app.services.production_canvas import ProductionCanvasError, production_canvas_service


# This table is deliberately small. A template only becomes pushable after its
# supplier parameters have been verified; it is safer than guessing from a UI catalog.
VERIFIED_FENGNIAO_TEMPLATES: dict[tuple[str, str], dict[str, Any]] = {
    ("10167", "OneSize"): {
        "platformSku": "",
        "firstCraft": "17",  # default gloss; 5D is intentionally not enabled.
        "secondCraft": "2",
        "colors": {"white"},
        "viewId": "1",
    },
}


class ProductionOrderService:
    def create(self, *, user: User, payload: schemas.ProductionOrderCreateInput) -> dict[str, Any]:
        if payload.clientRequestId:
            with self._session() as session:
                existing = session.execute(
                    self._order_query().where(ProductionOrder.idempotency_key == payload.clientRequestId)
                ).scalars().first()
                if existing:
                    if existing.user_id != user.id:
                        raise self._error(409, "PRODUCTION_ORDER_IDEMPOTENCY_CONFLICT", "请求编号已被其他账户使用。")
                    return self._serialize(existing)

        now = datetime.utcnow()
        order_id = f"pord_{uuid4().hex[:18]}"
        order = ProductionOrder(
            id=order_id,
            order_no=f"ACP{now:%Y%m%d}{uuid4().hex[:8].upper()}",
            idempotency_key=payload.clientRequestId,
            user_id=user.id,
            status="awaiting_payment",
            payment_status="pending",
            shipping_address=payload.shippingAddress.model_dump(),
            notes=payload.notes,
            extra_metadata={"source": "client-production-order", "version": "v1"},
            created_at=now,
            updated_at=now,
        )
        try:
            for index, item_input in enumerate(payload.items, start=1):
                filename = f"production-{order.order_no}-{index}-{item_input.targetWidth}x{item_input.targetHeight}.png"
                composed = production_canvas_service.compose(
                    source_url=item_input.sourceAssetUrl,
                    target_width=item_input.targetWidth,
                    target_height=item_input.targetHeight,
                    target_dpi=item_input.targetDpi,
                    mode=item_input.compositionMode,
                    user_id=user.id,
                    filename=filename,
                    tiled_review_confirmed=item_input.tiledReviewConfirmed,
                )
                preflight = production_canvas_service.preflight(
                    image_url=composed.url,
                    target_width=item_input.targetWidth,
                    target_height=item_input.targetHeight,
                    target_dpi=item_input.targetDpi,
                )
                order.items.append(
                    ProductionOrderItem(
                        id=f"pitem_{uuid4().hex[:18]}",
                        product_name=item_input.productName,
                        template_no=item_input.templateNo,
                        body_code=item_input.bodyCode,
                        size_code=item_input.sizeCode,
                        color_code=item_input.colorCode,
                        first_craft=item_input.firstCraft,
                        second_craft=item_input.secondCraft,
                        view_id=item_input.viewId,
                        surface_name=item_input.surfaceName,
                        target_width=item_input.targetWidth,
                        target_height=item_input.targetHeight,
                        target_dpi=item_input.targetDpi,
                        quantity=item_input.quantity,
                        source_asset_url=item_input.sourceAssetUrl,
                        production_asset_url=composed.url,
                        production_asset_key=composed.object_key,
                        preflight={**preflight, "compositionMode": composed.mode, "sourceWidth": composed.source_width, "sourceHeight": composed.source_height},
                        extra_metadata={"supplierConfigVerified": self._is_supplier_config_verified(item_input)},
                        created_at=now,
                        updated_at=now,
                    )
                )
        except ProductionCanvasError as exc:
            raise self._error(400, exc.error_code, exc.message) from exc

        self._add_event(order, "production_file_preflight_passed", user.id, {"itemCount": len(order.items)})
        self._add_event(order, "order_created", user.id, {"paymentStatus": "pending"})
        with self._session() as session:
            session.add(order)
            session.commit()
            persisted = session.execute(self._order_query().where(ProductionOrder.id == order.id)).scalars().one()
            return self._serialize(persisted)

    def list_for_user(self, *, user: User, limit: int = 100) -> list[dict[str, Any]]:
        with self._session() as session:
            rows = session.execute(
                self._order_query()
                .where(ProductionOrder.user_id == user.id)
                .order_by(ProductionOrder.created_at.desc())
                .limit(max(1, min(limit, 200)))
            ).scalars().all()
            return [self._serialize(row) for row in rows]

    def get_for_user(self, *, user: User, order_id: str) -> dict[str, Any]:
        with self._session() as session:
            row = session.execute(self._order_query().where(ProductionOrder.id == order_id)).scalars().first()
            if not row:
                raise self._error(404, "PRODUCTION_ORDER_NOT_FOUND", "生产订单不存在。")
            if row.user_id != user.id:
                raise self._error(403, "PRODUCTION_ORDER_FORBIDDEN", "无权访问该生产订单。")
            return self._serialize(row)

    def list_for_ops(self, *, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        with self._session() as session:
            query = self._order_query().order_by(ProductionOrder.created_at.desc()).limit(max(1, min(limit, 500)))
            if status:
                query = query.where(ProductionOrder.status == status)
            return [self._serialize(row) for row in session.execute(query).scalars().all()]

    def mark_paid_for_gateway(self, *, order_id: str, actor: User, payment_reference: str | None, test_mode: bool) -> dict[str, Any]:
        with self._session() as session:
            order = self._find_order(session, order_id)
            if order.payment_status == "paid" and order.status not in {"supplier_pending", "supplier_retry", "ops_review"}:
                return self._serialize(order)
            if order.payment_status != "paid" and order.status != "awaiting_payment":
                raise self._error(409, "PRODUCTION_ORDER_PAYMENT_STATUS_INVALID", "当前订单不能确认支付。")
            if order.payment_status != "paid":
                order.payment_status = "paid"
                order.payment_reference = payment_reference
                order.paid_at = datetime.utcnow()
                self._add_event(order, "payment_confirmed", actor.id, {"testMode": test_mode, "reference": payment_reference or None})
            order.status = "supplier_pending"
            self._add_event(order, "supplier_auto_submit_queued", actor.id, {"reason": "payment_confirmed"})
            session.add(order)
            session.commit()

        try:
            return self.submit_to_fengniao(order_id=order_id, actor=actor, confirm_production=True)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            return self._defer_supplier_submission(
                order_id=order_id,
                actor=actor,
                error_code=detail.get("errorCode", "PRODUCTION_ORDER_SUPPLIER_SUBMIT_FAILED"),
                message=detail.get("message", "供应链自动提交失败，等待平台重试。"),
            )
        except Exception as exc:  # noqa: BLE001 - payment success must survive supplier failures
            return self._defer_supplier_submission(
                order_id=order_id,
                actor=actor,
                error_code="PRODUCTION_ORDER_SUPPLIER_SUBMIT_UNEXPECTED",
                message=str(exc)[:300] or "供应链自动提交异常，等待平台重试。",
            )

    def _defer_supplier_submission(
        self,
        *,
        order_id: str,
        actor: User,
        error_code: str,
        message: str,
    ) -> dict[str, Any]:
        with self._session() as session:
            order = self._find_order(session, order_id)
            if order.status != "submitted_to_supplier":
                order.status = "supplier_retry"
                order.supplier_status = "retry_required"
                self._add_event(
                    order,
                    "supplier_auto_submit_deferred",
                    actor.id,
                    {
                        "errorCode": error_code,
                        "message": message,
                    },
                )
                session.add(order)
                session.commit()
            return self._serialize(order)

    def submit_to_fengniao(self, *, order_id: str, actor: User, confirm_production: bool) -> dict[str, Any]:
        if not confirm_production:
            raise self._error(409, "PRODUCTION_ORDER_SUPPLIER_CONFIRMATION_REQUIRED", "供应链重试必须明确确认。")
        with self._session() as session:
            order = self._find_order(session, order_id)
            if order.status == "submitted_to_supplier":
                return self._serialize(order)
            if order.payment_status != "paid" or order.status not in {"supplier_pending", "supplier_retry", "ops_review"}:
                raise self._error(409, "PRODUCTION_ORDER_NOT_READY_FOR_SUPPLIER", "订单尚未支付或不在供应链提交队列。")
            self._validate_supplier_ready(order)
            supplier_payload = self._supplier_payload(order)
            try:
                result = humcustom_supply_chain_client.place_order(supplier_payload)
            except HumcustomSupplyChainError as exc:
                order.status = "supplier_retry"
                order.supplier_status = "retry_required"
                self._add_event(order, "supplier_submit_failed", actor.id, {"errorCode": exc.error_code, "message": exc.message})
                session.add(order)
                session.commit()
                raise self._error(exc.status_code, exc.error_code, exc.message) from exc

            effect_assets = self._persist_supplier_effect_images(result.raw, order=order)
            order.supplier_order_id = result.order_id
            order.supplier_platform_order_id = result.platform_order_id or result.plat_order_id
            order.supplier_status = "submitted"
            order.supplier_response = self._safe_supplier_response(result.raw)
            order.status = "submitted_to_supplier"
            order.submitted_to_supplier_at = datetime.utcnow()
            self._add_event(
                order,
                "supplier_submitted",
                actor.id,
                {"supplierOrderId": result.order_id, "platformOrderId": result.platform_order_id, "effectImageCount": len(effect_assets)},
            )
            session.add(order)
            session.commit()
            return self._serialize(order)

    def sync_fengniao(self, *, order_id: str, actor: User) -> dict[str, Any]:
        with self._session() as session:
            order = self._find_order(session, order_id)
            platform_order_id = order.supplier_platform_order_id or order.order_no
            if not order.submitted_to_supplier_at:
                raise self._error(409, "FENGNIAO_ORDER_NOT_SUBMITTED", "订单尚未推送蜂鸟，不能同步。")
            try:
                snapshot = humcustom_supply_chain_client.query_order(platform_order_id)
            except HumcustomSupplyChainError as exc:
                self._add_event(order, "supplier_sync_failed", actor.id, {"errorCode": exc.error_code, "message": exc.message})
                session.add(order)
                session.commit()
                raise self._error(exc.status_code, exc.error_code, exc.message) from exc
            effects = self._persist_supplier_effect_images(snapshot.raw, order=order)
            order.supplier_status = snapshot.order_status_name or order.supplier_status
            response = self._safe_supplier_response(snapshot.raw)
            response["orderStatusName"] = snapshot.order_status_name
            response["waybillNo"] = snapshot.waybill_no
            order.supplier_response = response
            self._add_event(
                order,
                "supplier_synced",
                actor.id,
                {"supplierStatus": snapshot.order_status_name, "waybillNo": snapshot.waybill_no, "effectImageCount": len(effects)},
            )
            session.add(order)
            session.commit()
            return self._serialize(order)

    @staticmethod
    def _is_supplier_config_verified(item: schemas.ProductionOrderItemInput) -> bool:
        config = VERIFIED_FENGNIAO_TEMPLATES.get((item.templateNo, item.sizeCode))
        return bool(
            config
            and item.colorCode in config["colors"]
            and item.firstCraft == config["firstCraft"]
            and item.secondCraft == config["secondCraft"]
            and item.viewId == config["viewId"]
        )

    def _validate_supplier_ready(self, order: ProductionOrder) -> None:
        for item in order.items:
            verified = (item.extra_metadata or {}).get("supplierConfigVerified") is True
            if not verified:
                raise self._error(
                    409,
                    "FENGNIAO_TEMPLATE_NOT_VERIFIED",
                    f"模板 {item.template_no}/{item.size_code} 的蜂鸟工艺或颜色尚未验证，不能推单。",
                )
            if not (item.preflight or {}).get("passed"):
                raise self._error(409, "PRODUCTION_PREFLIGHT_REQUIRED", "存在未通过印刷预检的生产文件。")

    def _supplier_payload(self, order: ProductionOrder) -> dict[str, Any]:
        address = order.shipping_address or {}
        goods = []
        for item in order.items:
            supplier_config = VERIFIED_FENGNIAO_TEMPLATES[(item.template_no, item.size_code)]
            goods.append(
                {
                    "templateNo": item.template_no,
                    "platformSku": supplier_config["platformSku"],
                    "firstCraft": item.first_craft,
                    "secondCraft": item.second_craft or "",
                    "num": item.quantity,
                    "platItemId": item.id,
                    "sizeCode": item.size_code,
                    "colorCode": item.color_code,
                    "imageList": [{"imageUrl": item.production_asset_url, "viewId": item.view_id}],
                }
            )
        return {
            "apiVersion": "1",
            "goodsList": goods,
            "orgOrderId": order.order_no,
            "platOrderId": order.order_no,
            "recipientName": address.get("recipientName"),
            "shipPhoneNumber": address.get("phoneNumber"),
            "shipEmail": address.get("email") or "",
            "shipCountry": address.get("country"),
            "shipState": address.get("state"),
            "shipCity": address.get("city"),
            "shipDistrict": address.get("district") or "",
            "shipAddress": address.get("address"),
            "shipPostaCode": address.get("postalCode"),
            "addressId": "",
            "waybillType": "0",
            "selfSuppliedCarrier": "",
            "selfSuppliedPdfUrl": "",
            "selfSuppliedWaybill": "",
        }

    def _persist_supplier_effect_images(self, raw: dict[str, Any], *, order: ProductionOrder) -> list[str]:
        persisted: list[str] = []
        urls = list(self._image_urls(raw))
        for item, url in zip(order.items, urls, strict=False):
            try:
                stored = media_ingest_service.ingest_from_remote_url(
                    url, user_id=order.user_id, filename_hint=f"supplier-effect-{order.order_no}-{item.id}.png", tag="fengniao-effect"
                )
            except Exception:  # noqa: BLE001 - an unavailable effect image must not erase a valid supplier order
                continue
            item.supplier_effect_image_url = str(stored["ossUrl"])
            item.supplier_effect_image_key = stored.get("ossKey")
            persisted.append(item.supplier_effect_image_url)
        return persisted

    def _image_urls(self, value: Any, *, key_hint: str = "") -> Iterable[str]:
        if isinstance(value, dict):
            for key, child in value.items():
                yield from self._image_urls(child, key_hint=str(key).lower())
        elif isinstance(value, list):
            for child in value:
                yield from self._image_urls(child, key_hint=key_hint)
        elif isinstance(value, str) and value.startswith(("http://", "https://")):
            if any(token in key_hint for token in ("effect", "render", "preview", "mockup", "image", "picture", "photo")):
                yield value

    @staticmethod
    def _safe_supplier_response(raw: dict[str, Any]) -> dict[str, Any]:
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        return {"code": raw.get("code"), "success": raw.get("success"), "message": raw.get("message"), "data": data}

    @staticmethod
    def _add_event(order: ProductionOrder, event_type: str, actor_user_id: str | None, payload: dict[str, Any]) -> None:
        order.events.append(ProductionOrderEvent(event_type=event_type, actor_user_id=actor_user_id, payload=payload))

    @staticmethod
    def _order_query():
        return select(ProductionOrder).options(
            selectinload(ProductionOrder.items), selectinload(ProductionOrder.events)
        )

    @staticmethod
    def _find_order(session: Session, order_id: str) -> ProductionOrder:
        order = session.execute(
            ProductionOrderService._order_query().where(ProductionOrder.id == order_id)
        ).scalars().first()
        if not order:
            raise ProductionOrderService._error(404, "PRODUCTION_ORDER_NOT_FOUND", "生产订单不存在。")
        return order

    @staticmethod
    def _serialize(order: ProductionOrder) -> dict[str, Any]:
        return {
            "id": order.id,
            "orderNo": order.order_no,
            "status": order.status,
            "paymentStatus": order.payment_status,
            "totalAmountCents": order.total_amount_cents,
            "totalPoints": order.total_points,
            "shippingAddress": dict(order.shipping_address or {}),
            "supplierOrderId": order.supplier_order_id,
            "supplierPlatformOrderId": order.supplier_platform_order_id,
            "supplierStatus": order.supplier_status,
            "supplierEffectImageUrls": [item.supplier_effect_image_url for item in order.items if item.supplier_effect_image_url],
            "items": [
                {
                    "id": item.id, "productName": item.product_name, "templateNo": item.template_no,
                    "sizeCode": item.size_code, "colorCode": item.color_code, "firstCraft": item.first_craft,
                    "secondCraft": item.second_craft, "viewId": item.view_id, "targetWidth": item.target_width,
                    "targetHeight": item.target_height, "targetDpi": item.target_dpi, "quantity": item.quantity,
                    "sourceAssetUrl": item.source_asset_url, "productionAssetUrl": item.production_asset_url,
                    "supplierEffectImageUrl": item.supplier_effect_image_url, "preflight": dict(item.preflight or {}),
                }
                for item in order.items
            ],
            "events": [
                {"eventType": event.event_type, "actorUserId": event.actor_user_id, "payload": event.payload, "createdAt": event.created_at}
                for event in order.events
            ],
            "createdAt": order.created_at,
            "updatedAt": order.updated_at,
        }

    @staticmethod
    def _session():
        from app.core.db import get_session
        return get_session()

    @staticmethod
    def _error(status_code: int, error_code: str, message: str) -> HTTPException:
        return HTTPException(status_code=status_code, detail={"errorCode": error_code, "message": message})


production_order_service = ProductionOrderService()
