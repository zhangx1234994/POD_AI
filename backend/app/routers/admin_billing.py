"""Admin billing endpoints.

The first version is intentionally operational rather than payment-complete:
it gives the admin page real package quota, wallet, monthly settlement, invoice,
and notification records without pretending a third-party payment gateway exists.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Response

from app.deps.auth import require_admin
from app.models.user import User
from app.services.admin_billing import admin_billing_service
from app.services.wallet import wallet_service


router = APIRouter(prefix="/admin/billing", dependencies=[Depends(require_admin)], tags=["admin-billing"])


def _format_report_amounts(items: list[dict[str, Any]] | None, *, cents: bool = False) -> str:
    values = []
    for item in items or []:
        currency = str(item.get("currency") or "").strip() or "-"
        amount = item.get("amountCents") if cents else item.get("amount")
        if amount is None:
            continue
        if cents:
            values.append(f"{currency} {int(amount) / 100:.2f}")
        else:
            values.append(f"{currency} {float(amount):.4f}")
    return " / ".join(values) if values else "-"


def commercial_report_to_csv(report: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["商业化报表"])
    writer.writerow(["账期", report.get("month") or ""])
    writer.writerow(["状态", report.get("statusLabel") or report.get("status") or ""])
    writer.writerow(["下一步", report.get("nextAction") or ""])
    writer.writerow(["生成时间", report.get("generatedAt") or ""])
    writer.writerow([])
    writer.writerow(["指标", "数值"])
    writer.writerow(["任务总数", report.get("runCount") or 0])
    writer.writerow(["成功任务", report.get("succeededRunCount") or 0])
    writer.writerow(["可计费任务", report.get("billableRunCount") or 0])
    writer.writerow(["已扣费任务", report.get("chargedRunCount") or 0])
    writer.writerow(["套餐扣费任务", report.get("packageChargedRunCount") or 0])
    writer.writerow(["钱包扣费任务", report.get("walletChargedRunCount") or 0])
    writer.writerow(["免计费任务", report.get("noChargeRunCount") or 0])
    writer.writerow(["未定价任务", report.get("unpricedRunCount") or 0])
    writer.writerow(["计费异常", report.get("billingIssueCount") or 0])
    writer.writerow(["套餐消耗", report.get("quotaUnits") or 0])
    writer.writerow(["售出套餐额度", report.get("packageSoldUnits") or 0])
    writer.writerow(["已确认订单数", report.get("paidPackageOrderCount") or 0])
    writer.writerow(["待确认订单数", report.get("pendingPackageOrderCount") or 0])
    writer.writerow(["已确认收入", _format_report_amounts(report.get("packageOrderRevenueByCurrency"), cents=True)])
    writer.writerow(["待确认金额", _format_report_amounts(report.get("pendingPackageRevenueByCurrency"), cents=True)])
    writer.writerow(["任务成本", _format_report_amounts(report.get("costByCurrency"))])
    writer.writerow([])
    writer.writerow(["业务", "任务数", "成功数", "可计费数", "已扣费数", "免计费数", "未定价数", "计费异常数", "套餐消耗", "成本"])
    for row in report.get("businessRows") or []:
        writer.writerow(
            [
                row.get("businessKey") or "-",
                row.get("runCount") or 0,
                row.get("succeededRunCount") or 0,
                row.get("billableRunCount") or 0,
                row.get("chargedRunCount") or 0,
                row.get("noChargeRunCount") or 0,
                row.get("unpricedRunCount") or 0,
                row.get("billingIssueCount") or 0,
                row.get("quotaUnits") or 0,
                _format_report_amounts(row.get("costByCurrency")),
            ]
        )
    risk_items = report.get("riskItems") or []
    if risk_items:
        writer.writerow([])
        writer.writerow(["风险任务", "业务", "问题", "用户", "状态", "成本", "时间"])
        for item in risk_items:
            writer.writerow(
                [
                    item.get("runId") or item.get("id") or "-",
                    item.get("businessKey") or "-",
                    item.get("issueLabel") or item.get("issueType") or "-",
                    item.get("userName") or item.get("userId") or "-",
                    item.get("billingStatus") or "-",
                    f"{item.get('currency') or '-'} {item.get('costAmount') or 0}",
                    item.get("createdAt") or "-",
                ]
            )
    return buffer.getvalue()


@router.get("/overview")
def get_billing_overview(
    month: str | None = Query(default=None),
    window_days: int = Query(default=30, ge=1, le=365),
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    issue_limit: int = Query(default=20, ge=1, le=200),
    package_alert_limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    return admin_billing_service.overview(
        month=month,
        window_days=window_days,
        tenant_id=tenant_id,
        client_id=client_id,
        business_key=business_key,
        limit=limit,
        issue_limit=issue_limit,
        package_alert_limit=package_alert_limit,
    )


@router.get("/monthly-settlement")
def get_monthly_settlement_preview(
    month: str | None = Query(default=None),
    window_days: int = Query(default=30, ge=1, le=365),
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    return admin_billing_service.monthly_settlement(
        month=month,
        window_days=window_days,
        tenant_id=tenant_id,
        client_id=client_id,
        business_key=business_key,
        limit=limit,
    )


@router.get("/commercial-report")
def get_commercial_report(
    month: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict[str, Any]:
    return admin_billing_service.commercial_report(
        month=month,
        tenant_id=tenant_id,
        client_id=client_id,
        business_key=business_key,
        limit=limit,
    )


@router.get("/commercial-report/export")
def export_commercial_report(
    month: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
) -> Response:
    report = admin_billing_service.commercial_report(
        month=month,
        tenant_id=tenant_id,
        client_id=client_id,
        business_key=business_key,
        limit=limit,
    )
    filename_parts = ["commercial-report", str(report.get("month") or "current")]
    if report.get("businessKey"):
        filename_parts.append(str(report["businessKey"]))
    filename = "-".join(filename_parts) + ".csv"
    return Response(
        "\ufeff" + commercial_report_to_csv(report),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/monthly-settlements")
def list_monthly_settlements(
    month: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    return admin_billing_service.list_monthly_settlements(month=month, status=status, limit=limit)


@router.post("/monthly-settlements/issue")
def issue_monthly_settlement(
    payload: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    return admin_billing_service.issue_monthly_settlement(payload, actor=user)


@router.patch("/monthly-settlements/{settlement_id}")
def update_monthly_settlement(
    settlement_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    return admin_billing_service.update_monthly_settlement(settlement_id, payload, actor=user)


@router.post("/package-alerts/notify")
def notify_package_alerts(
    payload: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    return admin_billing_service.notify_package_alerts(payload, actor=user)


@router.get("/package-alert-notifications")
def list_package_alert_notifications(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
    return admin_billing_service.list_package_alert_notifications(limit=limit)


@router.get("/notification-config")
def get_notification_config() -> dict[str, Any]:
    return admin_billing_service.notification_config()


@router.patch("/notification-config")
def update_notification_config(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return admin_billing_service.update_notification_config(payload)


@router.get("/package-catalog")
def list_package_catalog(
    business_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    return admin_billing_service.list_package_catalog(business_key=business_key, status=status, limit=limit)


@router.post("/package-catalog")
def upsert_package_catalog(
    payload: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    return admin_billing_service.upsert_package_catalog(payload, actor=user)


@router.patch("/package-catalog/{package_key}")
def update_package_catalog(
    package_key: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    return admin_billing_service.update_package_catalog(package_key, payload, actor=user)


@router.get("/package-purchase-orders")
def list_package_purchase_orders(
    status: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    return admin_billing_service.list_package_purchase_orders(
        status=status,
        user_id=user_id,
        business_key=business_key,
        limit=limit,
    )


@router.post("/package-purchase-orders")
def create_package_purchase_order(
    payload: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    return admin_billing_service.create_package_purchase_order(payload, actor=user)


@router.patch("/package-purchase-orders/{order_id}")
def update_package_purchase_order(
    order_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    return admin_billing_service.update_package_purchase_order(order_id, payload, actor=user)


@router.get("/invoice-requests")
def list_invoice_requests(
    status: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    related_order_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    return admin_billing_service.list_invoice_requests(
        status=status,
        user_id=user_id,
        business_key=business_key,
        related_order_type=related_order_type,
        limit=limit,
    )


@router.post("/invoice-requests")
def create_invoice_request(
    payload: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    return admin_billing_service.create_invoice_request(payload, actor=user)


@router.patch("/invoice-requests/{invoice_request_id}")
def update_invoice_request(
    invoice_request_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    return admin_billing_service.update_invoice_request(invoice_request_id, payload, actor=user)


@router.post("/monthly-settlements/collections/notify")
def notify_monthly_collections(
    payload: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    return admin_billing_service.notify_monthly_collections(payload, actor=user)


@router.get("/monthly-settlement-collection-notifications")
def list_monthly_collection_notifications(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
    return admin_billing_service.list_monthly_collection_notifications(limit=limit)


@router.get("/users/{user_id}")
def get_billing_user_detail(
    user_id: str,
    month: str | None = Query(default=None),
    window_days: int = Query(default=30, ge=1, le=365),
    business_key: str | None = Query(default=None),
    page_size: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    return admin_billing_service.user_detail(
        user_id,
        month=month,
        window_days=window_days,
        business_key=business_key,
        page_size=page_size,
    )


@router.post("/users/{user_id}/packages/grant")
def grant_user_package(
    user_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    return admin_billing_service.grant_package(user_id, payload, actor=user)


@router.get("/users/{user_id}/ledger/export")
def export_user_ledger(
    user_id: str,
    month: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
) -> Response:
    _ = business_key
    ledger = wallet_service.ledger(user_id, page=1, page_size=1000)
    rows = ledger.get("items") or []
    if month:
        rows = [row for row in rows if str(row.get("createdAt") or "").startswith(month)]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["流水ID", "类型", "点数", "扣费前", "扣费后", "任务ID", "幂等键", "说明", "时间"])
    for row in rows:
        writer.writerow(
            [
                row.get("id"),
                row.get("changeType"),
                row.get("points"),
                row.get("beforeBalance"),
                row.get("afterBalance"),
                row.get("taskId"),
                row.get("traceId"),
                row.get("description"),
                row.get("createdAt"),
            ]
        )
    filename = f"billing-ledger-{user_id}.csv"
    return Response(
        "\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
