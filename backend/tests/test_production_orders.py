from __future__ import annotations

from datetime import datetime

import pytest

from app.core.db import Base, engine, get_session
from app.models.production_order import ProductionOrder
from app.models.user import User
from app.schemas.production_order import ProductionOrderCreateInput, ShippingAddressInput
from app.services.humcustom_supply_chain import HumcustomOrderSnapshot, HumcustomPlaceOrderResult
from app.services.production_canvas import ProductionCanvasResult
from app.services.production_orders import production_order_service


@pytest.fixture(autouse=True)
def _tables() -> None:
    Base.metadata.create_all(engine)


def _user() -> User:
    return User(
        id="production-test-user",
        username="production-test-user",
        email="production-test@example.com",
        password_hash="unused",
        role="admin",
        status="active",
    )


def _payload(*, template_no: str = "10167", color_code: str = "white") -> ProductionOrderCreateInput:
    return ProductionOrderCreateInput(
        clientRequestId=f"production-test-{template_no}-{color_code}-{datetime.utcnow().timestamp()}",
        shippingAddress=ShippingAddressInput(
            recipientName="PODI Test", phoneNumber="13800138000", country="CN", state="江苏省", city="南京市",
            district="浦口区", address="天润城十六街区北区", postalCode="210000",
        ),
        items=[
            {
                "productName": "12oz啤酒保温杯",
                "templateNo": template_no,
                "bodyCode": "1631",
                "sizeCode": "OneSize",
                "colorCode": color_code,
                "firstCraft": "17",
                "secondCraft": "2",
                "targetWidth": 2717,
                "targetHeight": 1772,
                "targetDpi": 150,
                "sourceAssetUrl": "https://assets.example.test/source.png",
                "compositionMode": "tile",
            }
        ],
    )


def _patch_canvas(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        "app.services.production_orders.production_canvas_service.compose",
        lambda **_: ProductionCanvasResult(
            url="https://oss.example.test/production.png", object_key="production/test.png", width=2717, height=1772,
            dpi=150, mode="tile", source_width=512, source_height=512,
        ),
    )
    monkeypatch.setattr(
        "app.services.production_orders.production_canvas_service.preflight",
        lambda **_: {"passed": True, "width": 2717, "height": 1772, "dpi": 150, "format": "PNG"},
    )


def test_production_order_requires_verified_supplier_template(monkeypatch) -> None:
    _patch_canvas(monkeypatch)
    order = production_order_service.create(user=_user(), payload=_payload(template_no="10241"))
    paid = production_order_service.mark_paid_for_gateway(
        order_id=order["id"], actor=_user(), payment_reference="test-paid", test_mode=True
    )
    assert paid["paymentStatus"] == "paid"
    assert paid["status"] == "supplier_retry"
    assert paid["supplierStatus"] == "retry_required"
    with pytest.raises(Exception) as exc_info:
        production_order_service.submit_to_fengniao(order_id=order["id"], actor=_user(), confirm_production=True)
    assert exc_info.value.detail["errorCode"] == "FENGNIAO_TEMPLATE_NOT_VERIFIED"


def test_production_order_payment_auto_submits_supplier_and_archives_effect(monkeypatch) -> None:
    _patch_canvas(monkeypatch)
    captured: dict = {}

    class FakeSupplier:
        def place_order(self, payload: dict) -> HumcustomPlaceOrderResult:
            captured.update(payload)
            return HumcustomPlaceOrderResult(
                plat_order_id=payload["platOrderId"], order_id="FN-ORDER-100", platform_order_id=payload["platOrderId"],
                raw={"code": 0, "success": True, "data": {"effectImageUrl": "https://supplier.example.test/effect.png"}},
            )

        def query_order(self, plat_order_id: str) -> HumcustomOrderSnapshot:
            return HumcustomOrderSnapshot(
                plat_order_id=plat_order_id,
                order_status_name="待付款",
                waybill_no=None,
                raw={"code": 0, "success": True, "data": {"orderDetailList": [{"previewImageUrl": "https://supplier.example.test/query-effect.png"}]}},
            )

    monkeypatch.setattr("app.services.production_orders.humcustom_supply_chain_client", FakeSupplier())
    monkeypatch.setattr(
        "app.services.production_orders.media_ingest_service.ingest_from_remote_url",
        lambda *_, **__: {"ossUrl": "https://oss.example.test/effect.png", "ossKey": "supplier/effect.png"},
    )
    order = production_order_service.create(user=_user(), payload=_payload())
    submitted = production_order_service.mark_paid_for_gateway(
        order_id=order["id"], actor=_user(), payment_reference="test-paid", test_mode=True
    )
    assert submitted["status"] == "submitted_to_supplier"
    assert submitted["paymentStatus"] == "paid"
    assert submitted["supplierOrderId"] == "FN-ORDER-100"
    assert submitted["supplierEffectImageUrls"] == ["https://oss.example.test/effect.png"]
    assert captured["shipCountry"] == "CN"
    assert captured["goodsList"][0]["templateNo"] == "10167"
    assert captured["goodsList"][0]["imageList"][0]["imageUrl"] == "https://oss.example.test/production.png"
    synced = production_order_service.sync_fengniao(order_id=order["id"], actor=_user())
    assert synced["supplierStatus"] == "待付款"
    with get_session() as session:
        row = session.get(ProductionOrder, order["id"])
        assert row is not None
        assert row.supplier_response == {
            "code": 0,
            "success": True,
            "message": None,
            "data": {"orderDetailList": [{"previewImageUrl": "https://supplier.example.test/query-effect.png"}]},
            "orderStatusName": "待付款",
            "waybillNo": None,
        }


def test_unexpected_supplier_failure_preserves_paid_order_for_retry(monkeypatch) -> None:
    _patch_canvas(monkeypatch)

    class BrokenSupplier:
        def place_order(self, _payload: dict) -> HumcustomPlaceOrderResult:
            raise RuntimeError("temporary supplier adapter failure")

    monkeypatch.setattr("app.services.production_orders.humcustom_supply_chain_client", BrokenSupplier())
    order = production_order_service.create(user=_user(), payload=_payload())

    paid = production_order_service.mark_paid_for_gateway(
        order_id=order["id"], actor=_user(), payment_reference="test-paid-unexpected", test_mode=True
    )

    assert paid["paymentStatus"] == "paid"
    assert paid["status"] == "supplier_retry"
    assert paid["supplierStatus"] == "retry_required"
    with get_session() as session:
        row = session.get(ProductionOrder, order["id"])
        assert row is not None
        assert row.payment_reference == "test-paid-unexpected"
