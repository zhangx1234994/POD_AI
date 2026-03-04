from fastapi.testclient import TestClient

from app.main import app
from app.services.wallet import wallet_service


client = TestClient(app)


def setup_function() -> None:
    wallet_service.reset()


def test_freeze_confirm_then_ledger_and_statistics() -> None:
    freeze_resp = client.post(
        "/api/wallet/v1/freeze",
        json={"userId": "u_demo", "taskId": "task_001", "points": 120},
    )
    assert freeze_resp.status_code == 200
    hold_id = freeze_resp.json()["holdId"]
    assert freeze_resp.json()["balance"] == 380
    frozen_balance_resp = client.get("/api/wallet/v1/balance", params={"userId": "u_demo"})
    assert frozen_balance_resp.status_code == 200
    assert frozen_balance_resp.json()["frozenBalance"] == 120

    confirm_resp = client.post("/api/wallet/v1/confirm", json={"holdId": hold_id})
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["deducted"] == 120

    ledger_resp = client.get("/api/wallet/v1/ledger", params={"userId": "u_demo"})
    assert ledger_resp.status_code == 200
    ledger = ledger_resp.json()
    assert ledger["total"] == 1
    assert ledger["items"][0]["points"] == -120
    assert ledger["items"][0]["taskId"] == "task_001"

    stats_resp = client.get("/api/wallet/v1/statistics", params={"userId": "u_demo"})
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["totalPoints"] == 380
    assert stats["frozenPoints"] == 0


def test_recharge_order_balance_and_transactions_compat() -> None:
    create_resp = client.post(
        "/api/wallet/v1/recharge-orders",
        json={"userId": "u_recharge", "amount": 200, "channel": "manual"},
    )
    assert create_resp.status_code == 200
    order = create_resp.json()
    assert order["status"] == "paid"

    get_resp = client.get(f"/api/wallet/v1/recharge-orders/{order['orderNo']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["orderNo"] == order["orderNo"]

    balance_resp = client.get("/api/wallet/v1/balance", params={"userId": "u_recharge"})
    assert balance_resp.status_code == 200
    assert balance_resp.json()["balance"] == 700

    tx_resp = client.get("/api/wallet/v1/transactions", params={"userId": "u_recharge", "page": 1, "pageSize": 20})
    assert tx_resp.status_code == 200
    tx = tx_resp.json()
    assert tx["total"] == 1
    assert tx["items"][0]["description"].startswith("recharge:")


def test_wallet_error_codes() -> None:
    recharge_invalid = client.post(
        "/api/wallet/v1/recharge-orders",
        json={"userId": "u_invalid", "amount": 0, "channel": "manual"},
    )
    assert recharge_invalid.status_code == 400
    assert recharge_invalid.json().get("detail") == "RECHARGE_AMOUNT_INVALID"

    order_not_found = client.get("/api/wallet/v1/recharge-orders/rc_not_exists")
    assert order_not_found.status_code == 404
    assert order_not_found.json().get("detail") == "RECHARGE_ORDER_NOT_FOUND"

    release_not_found = client.post("/api/wallet/v1/release", json={"holdId": "hold_missing"})
    assert release_not_found.status_code == 404
    assert release_not_found.json().get("detail") == "WALLET_HOLD_NOT_FOUND"


def test_cost_snapshots_and_bill_summary() -> None:
    freeze_resp = client.post(
        "/api/wallet/v1/freeze",
        json={"userId": "u_cost", "taskId": "task_cost_1", "points": 50},
    )
    hold_id = freeze_resp.json()["holdId"]
    client.post("/api/wallet/v1/confirm", json={"holdId": hold_id})

    snapshot_resp = client.get("/api/wallet/v1/cost-snapshots", params={"userId": "u_cost"})
    assert snapshot_resp.status_code == 200
    snapshot = snapshot_resp.json()
    assert snapshot["count"] == 1
    assert snapshot["totalPoints"] == 50
    assert snapshot["items"][0]["taskId"] == "task_cost_1"

    bill_resp = client.get("/api/wallet/v1/bills", params={"userId": "u_cost"})
    assert bill_resp.status_code == 200
    bill = bill_resp.json()
    assert bill["expense"] == 50
    assert bill["net"] <= 0
