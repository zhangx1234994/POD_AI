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


def test_recharge_order_status_flow_and_transactions_compat() -> None:
    create_resp = client.post(
        "/api/wallet/v1/recharge-orders",
        json={"userId": "u_recharge", "amount": 200, "channel": "manual"},
    )
    assert create_resp.status_code == 200
    order = create_resp.json()
    assert order["status"] == "pending"
    assert order["paidAt"] is None

    get_resp = client.get(f"/api/wallet/v1/recharge-orders/{order['orderNo']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["orderNo"] == order["orderNo"]

    balance_resp = client.get("/api/wallet/v1/balance", params={"userId": "u_recharge"})
    assert balance_resp.status_code == 200
    assert balance_resp.json()["balance"] == 500

    paid_resp = client.post(
        f"/api/wallet/v1/recharge-orders/{order['orderNo']}/status",
        json={"status": "paid", "transactionId": "txn_mock_001"},
    )
    assert paid_resp.status_code == 200
    paid_order = paid_resp.json()
    assert paid_order["status"] == "paid"
    assert paid_order["transactionId"] == "txn_mock_001"
    assert paid_order["paidAt"]

    paid_retry_resp = client.post(
        f"/api/wallet/v1/recharge-orders/{order['orderNo']}/status",
        json={"status": "paid", "transactionId": "txn_mock_001"},
    )
    assert paid_retry_resp.status_code == 200

    tx_resp = client.get("/api/wallet/v1/transactions", params={"userId": "u_recharge", "page": 1, "pageSize": 20})
    assert tx_resp.status_code == 200
    tx = tx_resp.json()
    assert tx["total"] == 1
    assert tx["items"][0]["description"].startswith("recharge:")

    balance_after_paid = client.get("/api/wallet/v1/balance", params={"userId": "u_recharge"})
    assert balance_after_paid.status_code == 200
    assert balance_after_paid.json()["balance"] == 700


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

    recharge_status_not_found = client.post(
        "/api/wallet/v1/recharge-orders/rc_not_exists/status",
        json={"status": "paid"},
    )
    assert recharge_status_not_found.status_code == 404
    assert recharge_status_not_found.json().get("detail") == "RECHARGE_ORDER_NOT_FOUND"

    recharge_status_invalid = client.post(
        "/api/wallet/v1/recharge-orders/rc_not_exists/status",
        json={"status": "done"},
    )
    assert recharge_status_invalid.status_code == 400
    assert recharge_status_invalid.json().get("detail") == "RECHARGE_STATUS_INVALID"

    release_not_found = client.post("/api/wallet/v1/release", json={"holdId": "hold_missing"})
    assert release_not_found.status_code == 404
    assert release_not_found.json().get("detail") == "WALLET_HOLD_NOT_FOUND"


def test_recharge_order_status_conflict() -> None:
    create_resp = client.post(
        "/api/wallet/v1/recharge-orders",
        json={"userId": "u_recharge_conflict", "amount": 80, "channel": "manual"},
    )
    assert create_resp.status_code == 200
    order_no = create_resp.json()["orderNo"]

    fail_resp = client.post(
        f"/api/wallet/v1/recharge-orders/{order_no}/status",
        json={"status": "failed", "failReason": "pay_timeout"},
    )
    assert fail_resp.status_code == 200
    assert fail_resp.json()["status"] == "failed"

    paid_after_fail = client.post(
        f"/api/wallet/v1/recharge-orders/{order_no}/status",
        json={"status": "paid"},
    )
    assert paid_after_fail.status_code == 409
    assert paid_after_fail.json().get("detail") == "RECHARGE_ORDER_STATUS_CONFLICT"


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


def test_bill_month_invalid() -> None:
    resp = client.get("/api/wallet/v1/bills", params={"userId": "u_cost_invalid_month", "month": "202603"})
    assert resp.status_code == 400
    assert resp.json().get("detail") == "BILL_MONTH_INVALID"
