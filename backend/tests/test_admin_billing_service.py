from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.admin_billing as admin_billing_module
from app.core.db import Base
from app.models.integration import BusinessRun
from app.models.user import User
from app.models.wallet import PackageBalance
from app.routers.admin_billing import commercial_report_to_csv
from app.services.admin_billing import AdminBillingService
from app.services.wallet import wallet_service


def install_admin_billing_db(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def fake_get_session():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(admin_billing_module, "get_session", fake_get_session)
    wallet_service.reset()
    with testing_session() as session:
        now = datetime.utcnow()
        session.add_all(
            [
                User(
                    id="user_bill_1",
                    email="bill1@example.com",
                    username="bill1",
                    password_hash="x",
                    role="client",
                    status="active",
                    tenant_id="tenant-a",
                    client_id="client-a",
                    created_at=now,
                    updated_at=now,
                ),
                User(
                    id="admin_bill",
                    email="admin-bill@example.com",
                    username="admin_bill",
                    password_hash="x",
                    role="admin",
                    status="active",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.add(
            BusinessRun(
                id="run_bill_unsettled",
                business_key="fission",
                version="v1",
                status="succeeded",
                tenant_id="tenant-a",
                client_id="client-a",
                user_id="user_bill_1",
                user_name="bill1",
                cost_amount=0.12,
                currency="USD",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    return testing_session


def test_admin_billing_overview_package_grant_and_user_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    install_admin_billing_db(monkeypatch)
    service = AdminBillingService()

    granted = service.grant_package(
        "user_bill_1",
        {
            "packageKey": "fission-basic",
            "packageName": "图裂变基础包",
            "businessKey": "fission",
            "units": 30,
            "traceId": "trace_pkg_001",
            "expiresAt": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        },
    )

    assert granted["remainingUnits"] == 30
    assert granted["idempotent"] is False

    repeated = service.grant_package(
        "user_bill_1",
        {
            "packageKey": "fission-basic",
            "businessKey": "fission",
            "units": 30,
            "traceId": "trace_pkg_001",
        },
    )
    assert repeated["idempotent"] is True
    assert repeated["packageBalances"]["totalRemainingUnits"] == 30

    detail = service.user_detail("user_bill_1", business_key="fission")
    assert detail["user"]["username"] == "bill1"
    assert detail["packageBalances"]["totalRemainingUnits"] == 30
    assert detail["packageLedger"]["total"] == 1

    overview = service.overview(tenant_id="tenant-a", client_id="client-a", business_key="fission")
    assert overview["totalUsers"] == 1
    assert overview["totalPackageRemainingUnits"] == 30
    assert overview["issueCount"] == 1
    assert overview["issues"][0]["issueType"] == "wallet_missing"
    assert overview["packageAlertCount"] == 1


def test_admin_billing_monthly_settlement_and_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    install_admin_billing_db(monkeypatch)
    service = AdminBillingService()

    issued = service.issue_monthly_settlement(
        {"month": "2026-05", "tenantId": "tenant-a", "clientId": "client-a", "businessKey": "fission"}
    )
    assert issued["idempotent"] is False
    assert issued["settlement"]["status"] == "issued"

    repeated = service.issue_monthly_settlement(
        {"month": "2026-05", "tenantId": "tenant-a", "clientId": "client-a", "businessKey": "fission"}
    )
    assert repeated["idempotent"] is True

    collection = service.notify_monthly_collections({"month": "2026-05", "send": False})
    assert collection["settlementCount"] == 1
    assert collection["sendStatus"] == "not_sent"

    listing = service.list_monthly_collection_notifications()
    assert listing["total"] == 1
    assert listing["items"][0]["settlementCount"] == 1

    paid = service.update_monthly_settlement(issued["settlement"]["id"], {"status": "paid", "paymentReference": "bank-001"})
    assert paid["status"] == "paid"
    assert paid["collectionLevel"] == "none"


def test_admin_billing_order_paid_grants_package_and_invoice_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    install_admin_billing_db(monkeypatch)
    service = AdminBillingService()

    order = service.create_package_purchase_order(
        {
            "userId": "user_bill_1",
            "packageKey": "outpaint-basic",
            "packageName": "扩图基础包",
            "businessKey": "outpaint",
            "units": 10,
            "amountCents": 9900,
        }
    )
    assert order["status"] == "pending"

    paid = service.update_package_purchase_order(order["id"], {"status": "paid", "paymentReference": "bank-002"})
    assert paid["order"]["status"] == "paid"
    assert paid["packageBalances"]["totalRemainingUnits"] == 10

    repeated = service.update_package_purchase_order(order["id"], {"status": "paid", "paymentReference": "bank-002"})
    assert repeated["idempotent"] is True
    assert repeated["packageLedger"]["total"] == 1

    invoice = service.create_invoice_request(
        {
            "relatedOrderType": "package_purchase_order",
            "relatedOrderId": order["id"],
            "userId": "user_bill_1",
            "invoiceTitle": "上海测试公司",
            "amountCents": 9900,
        }
    )
    assert invoice["status"] == "requested"

    issued_invoice = service.update_invoice_request(invoice["id"], {"status": "issued", "invoiceNo": "INV-001"})
    assert issued_invoice["invoiceNo"] == "INV-001"
    assert issued_invoice["status"] == "issued"


def test_admin_billing_package_catalog_applies_order_and_grant_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    install_admin_billing_db(monkeypatch)
    service = AdminBillingService()

    catalog = service.upsert_package_catalog(
        {
            "packageKey": "fission-pro",
            "packageName": "图裂变正式套餐",
            "businessKey": "fission",
            "description": "主线图裂变业务套餐",
            "units": 300,
            "unitName": "张",
            "amountCents": 19900,
            "validityDays": 30,
            "sortOrder": 10,
        }
    )
    assert catalog["packageKey"] == "fission-pro"
    assert catalog["units"] == 300

    catalog_list = service.list_package_catalog(business_key="fission")
    assert catalog_list["total"] == 1
    assert catalog_list["items"][0]["packageName"] == "图裂变正式套餐"

    order = service.create_package_purchase_order({"userId": "user_bill_1", "packageKey": "fission-pro"})
    assert order["packageName"] == "图裂变正式套餐"
    assert order["businessKey"] == "fission"
    assert order["units"] == 300
    assert order["amountCents"] == 19900
    assert order["expiresAt"]

    paid = service.update_package_purchase_order(order["id"], {"status": "paid", "paymentReference": "bank-003"})
    assert paid["packageBalances"]["totalRemainingUnits"] == 300

    granted = service.grant_package("user_bill_1", {"packageKey": "fission-pro", "traceId": "catalog-grant-1"})
    assert granted["businessKey"] == "fission"
    assert granted["granted"] == 300
    assert granted["packageBalances"]["totalRemainingUnits"] == 600


def test_admin_billing_commercial_report_summarizes_orders_cost_and_risks(monkeypatch: pytest.MonkeyPatch) -> None:
    testing_session = install_admin_billing_db(monkeypatch)
    service = AdminBillingService()
    with testing_session() as session:
        now = datetime.utcnow()
        session.add(
            BusinessRun(
                id="run_bill_unpriced",
                business_key="fission",
                version="v1",
                status="succeeded",
                tenant_id="tenant-a",
                client_id="client-a",
                user_id="user_bill_1",
                user_name="bill1",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    service.upsert_package_catalog(
        {
            "packageKey": "fission-pro",
            "packageName": "图裂变正式套餐",
            "businessKey": "fission",
            "units": 300,
            "amountCents": 19900,
        }
    )
    order = service.create_package_purchase_order({"userId": "user_bill_1", "packageKey": "fission-pro"})
    service.update_package_purchase_order(order["id"], {"status": "paid", "paymentReference": "bank-004"})

    report = service.commercial_report(month=datetime.utcnow().strftime("%Y-%m"), business_key="fission")

    assert report["status"] == "blocked"
    assert report["runCount"] == 2
    assert report["succeededRunCount"] == 2
    assert report["unpricedRunCount"] == 1
    assert report["billingIssueCount"] == 2
    assert report["paidPackageOrderCount"] == 1
    assert report["packageSoldUnits"] == 300
    assert report["activePackageCatalogCount"] == 1
    assert report["costByCurrency"] == [{"currency": "USD", "amount": 0.12}]
    assert report["packageOrderRevenueByCurrency"] == [{"currency": "CNY", "amountCents": 19900}]
    assert report["businessRows"][0]["businessKey"] == "fission"
    csv_text = commercial_report_to_csv(report)
    assert "商业化报表" in csv_text
    assert "已确认收入,CNY 199.00" in csv_text
    assert "fission,2,2,1,0,1,2,0,USD 0.1200" in csv_text


def test_admin_billing_read_endpoints_degrade_when_tables_are_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise SQLAlchemyError("billing tables unavailable")

    @contextmanager
    def broken_get_session():
        yield BrokenSession()

    monkeypatch.setattr(admin_billing_module, "get_session", broken_get_session)
    service = AdminBillingService()

    catalog = service.list_package_catalog()
    report = service.commercial_report(month="2026-05", business_key="fission")
    settlements = service.list_monthly_settlements(month="2026-05")
    orders = service.list_package_purchase_orders()
    invoices = service.list_invoice_requests()
    package_notifications = service.list_package_alert_notifications()
    monthly_notifications = service.list_monthly_collection_notifications()

    assert catalog == {"total": 0, "items": []}
    assert report["status"] == "setup_required"
    assert report["statusLabel"] == "待初始化"
    assert report["businessKey"] == "fission"
    assert report["businessRows"] == []
    assert settlements["items"] == []
    assert orders == {"total": 0, "items": []}
    assert invoices == {"total": 0, "items": []}
    assert package_notifications == {"total": 0, "items": []}
    assert monthly_notifications == {"total": 0, "items": []}


def test_admin_billing_validation_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    install_admin_billing_db(monkeypatch)
    service = AdminBillingService()

    with pytest.raises(HTTPException) as package_exc:
        service.grant_package("user_bill_1", {"packageKey": "", "units": 1})
    assert package_exc.value.detail == "PACKAGE_KEY_REQUIRED"

    with pytest.raises(HTTPException) as month_exc:
        service.list_monthly_settlements(month="2026/05")
    assert month_exc.value.detail == "BILL_MONTH_INVALID"

    with pytest.raises(HTTPException) as report_month_exc:
        service.commercial_report(month="2026/05")
    assert report_month_exc.value.detail == "BILL_MONTH_INVALID"

    with pytest.raises(HTTPException) as order_exc:
        service.update_package_purchase_order("missing", {"status": "paid"})
    assert order_exc.value.detail == "PACKAGE_PURCHASE_ORDER_NOT_FOUND"

    with pytest.raises(HTTPException) as invoice_exc:
        service.create_invoice_request({"invoiceTitle": ""})
    assert invoice_exc.value.detail == "BILLING_INVOICE_TITLE_REQUIRED"

    with pytest.raises(HTTPException) as catalog_exc:
        service.upsert_package_catalog({"packageKey": "bad", "units": 0})
    assert catalog_exc.value.detail == "PACKAGE_CATALOG_NAME_REQUIRED"
