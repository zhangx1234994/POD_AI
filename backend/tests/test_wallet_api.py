import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.wallet import wallet_service


client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_wallet(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WALLET_CALLBACK_TOKEN", raising=False)
    monkeypatch.delenv("WALLET_CALLBACK_SIGNING_SECRET", raising=False)
    get_settings.cache_clear()
    wallet_service.reset()
    yield
    monkeypatch.delenv("WALLET_CALLBACK_TOKEN", raising=False)
    monkeypatch.delenv("WALLET_CALLBACK_SIGNING_SECRET", raising=False)
    get_settings.cache_clear()


def _build_signature_payload(order_no: str, payload: dict, ts: int) -> str:
    return "\n".join(
        [
            order_no,
            str(ts),
            str(payload.get("status") or ""),
            str(payload.get("transactionId") or ""),
            str(payload.get("failReason") or ""),
            str(payload.get("taskId") or ""),
            str(payload.get("traceId") or ""),
            str(payload.get("provider") or ""),
            str(payload.get("modelKey") or ""),
        ]
    )


def _sign_payload(secret: str, order_no: str, payload: dict, ts: int) -> str:
    content = _build_signature_payload(order_no, payload, ts)
    return hmac.new(secret.encode("utf-8"), content.encode("utf-8"), hashlib.sha256).hexdigest()


def test_recharge_status_requires_callback_token_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WALLET_CALLBACK_TOKEN", "wallet_cb_123")
    get_settings.cache_clear()
    create_resp = client.post(
        "/api/wallet/v1/recharge-orders",
        json={"userId": "u_cb", "amount": 60, "channel": "manual"},
    )
    assert create_resp.status_code == 200
    order_no = create_resp.json()["orderNo"]

    missing_token_resp = client.post(
        f"/api/wallet/v1/recharge-orders/{order_no}/status",
        json={"status": "paid"},
    )
    assert missing_token_resp.status_code == 401
    assert missing_token_resp.json().get("detail") == "RECHARGE_CALLBACK_UNAUTHORIZED"

    ok_resp = client.post(
        f"/api/wallet/v1/recharge-orders/{order_no}/status",
        json={"status": "paid", "transactionId": "txn_cb_001"},
        headers={"X-Wallet-Callback-Token": "wallet_cb_123"},
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["status"] == "paid"


def test_recharge_status_requires_callback_signature_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    signing_secret = "wallet_sign_123"
    monkeypatch.setenv("WALLET_CALLBACK_SIGNING_SECRET", signing_secret)
    get_settings.cache_clear()
    create_resp = client.post(
        "/api/wallet/v1/recharge-orders",
        json={"userId": "u_sign", "amount": 90, "channel": "manual"},
    )
    assert create_resp.status_code == 200
    order_no = create_resp.json()["orderNo"]

    payload = {
        "status": "paid",
        "transactionId": "txn_sign_001",
        "taskId": "task_sign_001",
        "traceId": "trace_sign_001",
        "provider": "kie",
        "modelKey": "nano-banana-2",
    }

    missing_sig_resp = client.post(
        f"/api/wallet/v1/recharge-orders/{order_no}/status",
        json=payload,
    )
    assert missing_sig_resp.status_code == 401
    assert missing_sig_resp.json().get("detail") == "RECHARGE_CALLBACK_SIGNATURE_INVALID"

    expired_ts = int(time.time()) - 999
    expired_sig = _sign_payload(signing_secret, order_no, payload, expired_ts)
    expired_resp = client.post(
        f"/api/wallet/v1/recharge-orders/{order_no}/status",
        json=payload,
        headers={
            "X-Wallet-Callback-Timestamp": str(expired_ts),
            "X-Wallet-Callback-Signature": expired_sig,
        },
    )
    assert expired_resp.status_code == 401
    assert expired_resp.json().get("detail") == "RECHARGE_CALLBACK_SIGNATURE_EXPIRED"

    ts = int(time.time())
    sig = _sign_payload(signing_secret, order_no, payload, ts)
    ok_resp = client.post(
        f"/api/wallet/v1/recharge-orders/{order_no}/status",
        json=payload,
        headers={
            "X-Wallet-Callback-Timestamp": str(ts),
            "X-Wallet-Callback-Signature": sig,
        },
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["status"] == "paid"

    ledger_resp = client.get("/api/wallet/v1/ledger", params={"userId": "u_sign"})
    assert ledger_resp.status_code == 200
    item = ledger_resp.json()["items"][0]
    assert item["taskId"] == "task_sign_001"
    assert item["traceId"] == "trace_sign_001"
    assert item["provider"] == "kie"
    assert item["modelKey"] == "nano-banana-2"


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
        json={
            "status": "paid",
            "transactionId": "txn_mock_001",
            "taskId": "task_rc_001",
            "traceId": "trace_rc_001",
            "provider": "kie",
            "modelKey": "nano-banana-pro",
        },
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
    assert tx["items"][0]["taskId"] == "task_rc_001"
    assert tx["items"][0]["traceId"] == "trace_rc_001"
    assert tx["items"][0]["provider"] == "kie"
    assert tx["items"][0]["modelKey"] == "nano-banana-pro"

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


def test_record_expense_and_idempotent_by_trace_id() -> None:
    create_resp = client.post(
        "/api/wallet/v1/expenses",
        json={
            "userId": "u_expense",
            "points": 120,
            "taskId": "task_exp_001",
            "traceId": "trace_exp_001",
            "provider": "kie",
            "modelKey": "nano-banana-2",
            "description": "manual settle",
        },
    )
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["deducted"] == 120
    assert data["balance"] == 380
    assert data["idempotent"] is False

    dup_resp = client.post(
        "/api/wallet/v1/expenses",
        json={
            "userId": "u_expense",
            "points": 120,
            "taskId": "task_exp_001",
            "traceId": "trace_exp_001",
            "provider": "kie",
            "modelKey": "nano-banana-2",
        },
    )
    assert dup_resp.status_code == 200
    dup = dup_resp.json()
    assert dup["idempotent"] is True
    assert dup["balance"] == 380

    ledger_resp = client.get("/api/wallet/v1/ledger", params={"userId": "u_expense"})
    assert ledger_resp.status_code == 200
    ledger = ledger_resp.json()
    assert ledger["total"] == 1
    assert ledger["items"][0]["points"] == -120
    assert ledger["items"][0]["traceId"] == "trace_exp_001"


def test_record_expense_insufficient() -> None:
    resp = client.post(
        "/api/wallet/v1/expenses",
        json={"userId": "u_expense_insufficient", "points": 9999},
    )
    assert resp.status_code == 402
    assert resp.json().get("detail") == "WALLET_INSUFFICIENT"


def test_usage_summary_with_expense_and_income() -> None:
    expense_a = client.post(
        "/api/wallet/v1/expenses",
        json={
            "userId": "u_usage",
            "points": 40,
            "taskId": "task_usage_1",
            "traceId": "trace_usage_1",
            "provider": "kie",
            "modelKey": "nano-banana-2",
        },
    )
    assert expense_a.status_code == 200
    expense_b = client.post(
        "/api/wallet/v1/expenses",
        json={
            "userId": "u_usage",
            "points": 20,
            "taskId": "task_usage_2",
            "traceId": "trace_usage_2",
            "provider": "comfyui",
            "modelKey": "yinhua_tiqu",
        },
    )
    assert expense_b.status_code == 200

    order = client.post(
        "/api/wallet/v1/recharge-orders",
        json={"userId": "u_usage", "amount": 100, "channel": "manual"},
    ).json()
    paid = client.post(
        f"/api/wallet/v1/recharge-orders/{order['orderNo']}/status",
        json={"status": "paid"},
    )
    assert paid.status_code == 200

    summary_resp = client.get("/api/wallet/v1/usage-summary", params={"userId": "u_usage", "windowDays": 30})
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["totalExpensePoints"] == 60
    assert summary["totalIncomePoints"] == 100
    assert summary["expenseCount"] == 2
    assert summary["incomeCount"] == 1
    assert summary["providers"][0]["key"] == "kie"
    assert summary["models"][0]["key"] == "nano-banana-2"
    assert len(summary["daily"]) >= 1


def test_record_task_cost_snapshot_idempotent() -> None:
    first = wallet_service.record_task_cost_snapshot(
        task_id="ability_task_001",
        user_id="u_cost_snapshot",
        provider="kie",
        model_key="nano-banana-2",
        input_count=1,
        output_count=2,
        unit_cost=0.04,
        total_cost=0.08,
        pricing_version="kie-20260304",
        currency="USD",
    )
    assert first["created"] is True
    assert first["taskId"] == "ability_task_001"
    assert first["totalCost"] == 0.08

    second = wallet_service.record_task_cost_snapshot(
        task_id="ability_task_001",
        user_id="u_cost_snapshot",
        provider="kie",
        model_key="nano-banana-2",
        input_count=1,
        output_count=2,
        unit_cost=0.04,
        total_cost=0.08,
        pricing_version="kie-20260304",
        currency="USD",
    )
    assert second["created"] is False
    assert second["taskId"] == "ability_task_001"
