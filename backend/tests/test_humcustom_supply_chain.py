from types import SimpleNamespace

from app.services.humcustom_supply_chain import HumcustomSupplyChainClient


def test_query_order_reads_order_level_status_and_waybill(monkeypatch) -> None:
    client = HumcustomSupplyChainClient()
    monkeypatch.setattr(
        "app.services.humcustom_supply_chain.get_settings",
        lambda: SimpleNamespace(humcustom_access_token="test-token"),
    )
    monkeypatch.setattr(
        client,
        "_request_json",
        lambda **_: {
            "code": 0,
            "success": True,
            "data": {
                "orderStatusName": "待付款",
                "waybillNo": "YT123456",
                "orderDetailList": [{"platOrderId": "ACP-1", "productName": "12oz杯"}],
            },
        },
    )

    snapshot = client.query_order("ACP-1")

    assert snapshot.plat_order_id == "ACP-1"
    assert snapshot.order_status_name == "待付款"
    assert snapshot.waybill_no == "YT123456"
