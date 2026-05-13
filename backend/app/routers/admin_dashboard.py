"""Admin dashboard endpoints for system overview, monitoring, and logs."""

from __future__ import annotations

from datetime import datetime, timedelta, time, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
from time import perf_counter
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

try:  # Python <3.11 compatibility
    from datetime import UTC  # type: ignore
except ImportError:  # pragma: no cover - py310 fallback
    UTC = timezone.utc

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.db import get_session
from app.deps.auth import require_admin
from app.models.eval import EvalRun, EvalWorkflowVersion
from app.models.integration import (
    Ability,
    AbilityInvocationLog,
    AbilityTask,
    ApiKey,
    BusinessCapability,
    BusinessRun,
    Executor,
    VendorModelCatalog,
)
from app.models.task import Task, TaskBatch, TaskEvent
from app.models.user import InviteCode, User, UserSession
from app.schemas import admin_dashboard as schemas
from app.services.ability_seed import ensure_default_abilities
from app.services.api_key_selector import is_usable
from app.services.business_runs import BusinessRunService, RECIPE_EXECUTABLE_STEP_TYPES
from app.services.business_seed import ensure_default_business_capabilities
from app.services.eval_operations_health import build_eval_operations_health
from app.services.integration_test import integration_test_service

router = APIRouter(prefix="/admin/dashboard", dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_RUNTIME_DIR = BACKEND_ROOT / "runtime" / "admin_dashboard"
DASHBOARD_REPORT_DIR = BACKEND_ROOT / "reports"
HEALTH_WATCH_UNITS = (
    {
        "unit": "podi-business-health-watch.timer",
        "title": "业务轻量自检定时器",
        "kind": "timer",
        "description": "每 15 分钟检查发布 smoke、三大业务路由、ComfyUI 队列和最近评测健康。",
    },
    {
        "unit": "podi-business-health-watch.service",
        "title": "业务轻量自检最近执行",
        "kind": "service",
        "description": "最近一次轻量自检执行结果。",
    },
    {
        "unit": "podi-business-live-patrol.timer",
        "title": "业务真实巡检定时器",
        "kind": "timer",
        "description": "每天单并发真实跑花纹提取、图裂变、扩图和 production 测评工作流。",
    },
    {
        "unit": "podi-business-live-patrol.service",
        "title": "业务真实巡检最近执行",
        "kind": "service",
        "description": "最近一次真实巡检执行结果。",
    },
    {
        "unit": "podi-eval-health-watch.timer",
        "title": "评测运行健康定时器",
        "kind": "timer",
        "description": "每 15 分钟检查评测运行是否卡住、是否无回填、是否有近期失败。",
    },
    {
        "unit": "podi-eval-health-watch.service",
        "title": "评测运行健康最近执行",
        "kind": "service",
        "description": "最近一次评测运行健康检查结果。",
    },
)
CORE_BUSINESS_KEYS = ("pattern_extract", "fission", "outpaint")
CORE_BUSINESS_LABELS = {
    "pattern_extract": "花纹提取",
    "fission": "图裂变",
    "outpaint": "扩图",
}
VENDOR_PROVIDERS = {"openai", "openai_compatible", "volcengine", "baidu", "kie"}


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _record_path(name: str) -> Path:
    DASHBOARD_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return DASHBOARD_RUNTIME_DIR / name


def _read_records(name: str) -> list[dict[str, Any]]:
    path = _record_path(name)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("dashboard record read failed: %s", path)
        return []
    return data if isinstance(data, list) else []


def _write_records(name: str, records: list[dict[str, Any]], *, keep: int = 50) -> None:
    path = _record_path(name)
    payload = records[: max(1, keep)]
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _append_record(name: str, record: dict[str, Any], *, keep: int = 50) -> None:
    current = _read_records(name)
    current = [record, *[item for item in current if item.get("id") != record.get("id")]]
    _write_records(name, current, keep=keep)


def _run_system_command(args: list[str], *, timeout: float = 3.0) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return 127, "", f"{args[0]} not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"{args[0]} timed out"
    return completed.returncode, completed.stdout or "", completed.stderr or ""


def _parse_systemctl_show(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in output.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            result[key] = value.strip()
    return result


def _clean_systemd_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower() == "n/a":
        return None
    return cleaned


def _format_systemd_time(value: str | None) -> str | None:
    cleaned = _clean_systemd_text(value)
    if not cleaned:
        return None
    parts = cleaned.split()
    if len(parts) >= 4 and len(parts[1]) == 10 and parts[1][4] == "-":
        suffix = f" {parts[3]}" if len(parts) >= 4 else ""
        return f"{parts[1]} {parts[2]}{suffix}".strip()
    return cleaned


def _safe_optional_int(value: str | None) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _classify_health_watch_unit(kind: str, props: dict[str, str], command_code: int) -> tuple[str, str]:
    if command_code == 127:
        return "unavailable", "当前运行环境没有 systemctl，无法读取定时器状态。"
    if command_code == 124:
        return "failed", "读取 systemd 状态超时。"

    load_state = _clean_systemd_text(props.get("LoadState")) or "unknown"
    active_state = _clean_systemd_text(props.get("ActiveState")) or "unknown"
    unit_file_state = _clean_systemd_text(props.get("UnitFileState"))
    result = _clean_systemd_text(props.get("Result"))
    exec_status = _safe_optional_int(props.get("ExecMainStatus"))

    if load_state in {"not-found", "masked", "bad-setting", "error"}:
        return "unavailable", "没有安装或无法加载该 systemd 单元。"

    if kind == "timer":
        if unit_file_state and unit_file_state not in {"enabled", "static", "linked", "generated"}:
            return "disabled", "定时器已安装但没有启用。"
        if active_state == "active":
            next_elapse = _format_systemd_time(props.get("NextElapseUSecRealtime"))
            return "healthy", f"定时器运行中，下次触发：{next_elapse or '等待 systemd 调度'}。"
        if active_state in {"activating", "reloading"}:
            return "running", "定时器正在启动。"
        return "failed", f"定时器未处于 active 状态：{active_state}。"

    if active_state in {"active", "activating"}:
        return "running", "检查任务正在执行。"
    if result in {None, "success"} and (exec_status is None or exec_status == 0):
        return "healthy", "最近一次执行成功。"
    if result in {"exit-code", "timeout", "signal", "core-dump", "watchdog", "resources"} or (exec_status or 0) != 0:
        return "failed", f"最近一次执行失败：result={result or 'unknown'}，exit={exec_status if exec_status is not None else 'unknown'}。"
    return "unknown", f"当前状态：active={active_state}，result={result or 'unknown'}。"


def _journal_tail(unit: str, *, lines: int = 8) -> list[str]:
    code, stdout, _stderr = _run_system_command(
        ["journalctl", "-u", unit, "-n", str(max(1, min(lines, 40))), "--no-pager", "-o", "short-iso"],
        timeout=3,
    )
    if code != 0:
        return []
    return [line for line in stdout.splitlines() if line.strip()][-lines:]


def _health_watch_unit_status(definition: dict[str, str]) -> schemas.HealthWatchUnitStatus:
    unit = definition["unit"]
    kind = definition["kind"]
    code, stdout, stderr = _run_system_command(
        [
            "systemctl",
            "show",
            unit,
            "--property=LoadState,ActiveState,SubState,UnitFileState,Result,ExecMainStatus,LastTriggerUSec,NextElapseUSecRealtime",
            "--no-pager",
        ],
        timeout=3,
    )
    props = _parse_systemctl_show(stdout)
    status, summary = _classify_health_watch_unit(kind, props, code)
    if code not in {0, 127, 124} and not props:
        status = "failed"
        summary = (stderr or stdout or "读取 systemd 状态失败。").strip().splitlines()[0][:240]

    logs = _journal_tail(unit, lines=8) if code == 0 and props.get("LoadState") != "not-found" else []
    return schemas.HealthWatchUnitStatus(
        unit=unit,
        title=definition["title"],
        kind=kind,
        status=status,
        summary=summary,
        loadState=_clean_systemd_text(props.get("LoadState")),
        activeState=_clean_systemd_text(props.get("ActiveState")),
        subState=_clean_systemd_text(props.get("SubState")),
        unitFileState=_clean_systemd_text(props.get("UnitFileState")),
        result=_clean_systemd_text(props.get("Result")),
        execMainStatus=_safe_optional_int(props.get("ExecMainStatus")),
        lastTrigger=_format_systemd_time(props.get("LastTriggerUSec")),
        nextElapse=_format_systemd_time(props.get("NextElapseUSecRealtime")),
        recentLogs=logs,
    )


def _relative_backend_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(BACKEND_ROOT.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _safe_backend_file(raw_path: str) -> Path:
    value = str(raw_path or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="REPORT_PATH_REQUIRED")
    path = Path(value)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    resolved = path.resolve()
    backend_root = BACKEND_ROOT.resolve()
    if resolved != backend_root and backend_root not in resolved.parents:
        raise HTTPException(status_code=400, detail="REPORT_PATH_OUTSIDE_BACKEND")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="REPORT_NOT_FOUND")
    return resolved


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _patrol_items(summary: dict[str, Any]) -> list[dict[str, Any]]:
    raw = summary.get("items")
    if not isinstance(raw, list):
        raw = summary.get("workflowItems")
    if not isinstance(raw, list):
        raw = summary.get("results")
    return [dict(item) for item in raw or [] if isinstance(item, dict)]


def _patrol_item_has_output(item: dict[str, Any]) -> bool:
    explicit = item.get("hasOutput")
    if isinstance(explicit, bool):
        return explicit
    if _safe_int(item.get("imageCount")) > 0:
        return True
    for key in ("imageUrls", "image_urls", "resultImageUrls", "result_image_urls"):
        value = item.get(key)
        if isinstance(value, list) and any(_safe_text(url) for url in value):
            return True
    return False


def _patrol_item_issue_code(item: dict[str, Any]) -> str:
    issue_code = _safe_text(item.get("issueCode") or item.get("errorCode")).upper()
    if issue_code and issue_code != "OK":
        return issue_code
    status = _safe_text(item.get("status")).lower()
    if status not in {"succeeded", "success", "passed", "pass"}:
        return "RUN_NOT_SUCCEEDED"
    if not _patrol_item_has_output(item):
        return "EVAL_SUCCEEDED_WITHOUT_OUTPUT"
    return "OK"


def _normalize_patrol_item(item: dict[str, Any]) -> dict[str, Any]:
    issue_code = _patrol_item_issue_code(item)
    has_output = _patrol_item_has_output(item)
    status = _safe_text(item.get("status"))
    health_status = "healthy" if issue_code == "OK" else "failed"
    return {
        "name": _safe_text(item.get("name")),
        "workflowId": _safe_text(item.get("workflowId") or item.get("workflow_id")),
        "runId": _safe_text(item.get("runId") or item.get("run_id")),
        "status": status or "unknown",
        "finalStatus": _safe_text(item.get("finalStatus") or item.get("final_status")),
        "callbackStatus": _safe_text(item.get("callbackStatus") or item.get("callback_status")),
        "cozeExecuteId": _safe_text(item.get("cozeExecuteId") or item.get("coze_execute_id")),
        "podiTaskId": _safe_text(item.get("podiTaskId") or item.get("podi_task_id")),
        "imageCount": _safe_int(item.get("imageCount") or item.get("image_count")),
        "hasOutput": has_output,
        "issueCode": issue_code,
        "healthStatus": health_status,
        "errorCode": _safe_text(item.get("errorCode") or item.get("error_code")),
        "error": _safe_text(item.get("error") or item.get("errorMessage") or item.get("error_message")),
    }


def _normalize_release_patrol_summary(summary: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = dict(summary)
    items = [_normalize_patrol_item(item) for item in _patrol_items(summary)]
    if not items:
        failed_count = _safe_int(summary.get("failedOrUnfinished"), _safe_int(summary.get("failed")))
        normalized.setdefault("failedOrUnfinished", failed_count)
        normalized.setdefault("failedItems", summary.get("failedItems") if isinstance(summary.get("failedItems"), list) else [])
        normalized.setdefault("abilityHealthEvidence", [])
        return normalized

    failed_items = [item for item in items if item.get("issueCode") != "OK"]
    passed_items = [item for item in items if item.get("issueCode") == "OK"]
    no_output_items = [item for item in items if not item.get("hasOutput")]
    issue_summary: dict[str, int] = {}
    for item in items:
        issue_code = _safe_text(item.get("issueCode")) or "UNKNOWN"
        issue_summary[issue_code] = issue_summary.get(issue_code, 0) + 1

    normalized["total"] = _safe_int(summary.get("total"), len(items)) or len(items)
    normalized["succeeded"] = len(passed_items)
    normalized["failedOrUnfinished"] = len(failed_items)
    normalized["unfinished"] = len([item for item in items if _safe_text(item.get("status")).lower() not in {"succeeded", "success", "failed"}])
    normalized["outputReady"] = len([item for item in items if item.get("hasOutput")])
    normalized["noOutput"] = len(no_output_items)
    normalized["issueSummary"] = issue_summary
    normalized["failedItems"] = failed_items
    normalized["passedItems"] = passed_items
    normalized["abilityHealthEvidence"] = items
    return normalized


def _strategy_indicator(
    *,
    key: str,
    title: str,
    value: str,
    target: str,
    status: str,
    detail: str,
    action: str,
) -> schemas.DashboardStrategyIndicator:
    return schemas.DashboardStrategyIndicator(
        key=key,
        title=title,
        value=value,
        target=target,
        status=status,
        detail=detail,
        action=action,
    )


def _format_strategy_rate(value: float | None) -> str:
    if value is None:
        return "暂无数据"
    return f"{round(value * 100)}%"


def _build_strategy_indicators(
    *,
    business_total: int,
    business_succeeded: int,
    business_failed: int,
    success_rate: float | None,
    billable: int,
    unpriced: int,
    callback_failed: int,
    callback_missing: int,
    wallet_settled: int,
    wallet_failed: int,
    risk_count: int,
) -> tuple[schemas.DashboardStrategyIndicator, list[schemas.DashboardStrategyIndicator]]:
    north_star_status = "healthy"
    north_star_detail = "业务成功交付正常，继续关注增长和质量。"
    north_star_action = "保持三大主业务巡检，持续提高稳定成功调用。"
    if business_total <= 0:
        north_star_status = "warning"
        north_star_detail = "统计窗口内没有业务调用，无法判断真实业务活跃度。"
        north_star_action = "先跑三大主业务真实巡检，确认业务链路有成功样本。"
    elif business_succeeded <= 0:
        north_star_status = "critical"
        north_star_detail = "统计窗口内没有成功业务交付。"
        north_star_action = "优先排查业务 API、Coze 工具箱和 ComfyUI 回填链路。"
    elif risk_count > 0:
        north_star_status = "warning"
        north_star_detail = f"有 {business_succeeded} 次成功交付，但仍存在 {risk_count} 个风险信号。"
        north_star_action = "先处理失败、回调和计费风险，再扩大发版或接入流量。"

    north_star = _strategy_indicator(
        key="north_star",
        title="北极星：成功业务交付",
        value=f"{business_succeeded} 次",
        target="持续增长，且不能靠失败或无回填堆量",
        status=north_star_status,
        detail=north_star_detail,
        action=north_star_action,
    )

    success_status = "healthy"
    if success_rate is None:
        success_status = "warning"
    elif success_rate < 0.8:
        success_status = "critical"
    elif success_rate < 0.9:
        success_status = "warning"

    billing_total = billable + unpriced
    billing_rate = (billable / billing_total) if billing_total > 0 else None
    billing_status = "healthy"
    if billing_total <= 0:
        billing_status = "warning"
    elif unpriced > 0:
        billing_status = "critical"

    callback_status = "healthy"
    if callback_failed > 0:
        callback_status = "critical"
    elif callback_missing > 0:
        callback_status = "warning"

    wallet_status = "healthy"
    if wallet_failed > 0:
        wallet_status = "critical"
    elif billable > 0 and wallet_settled < billable:
        wallet_status = "warning"
    elif billable <= 0:
        wallet_status = "warning"

    risk_status = "healthy"
    if risk_count > 0 and (business_failed > 0 or callback_failed > 0):
        risk_status = "critical"
    elif risk_count > 0:
        risk_status = "warning"

    indicators = [
        _strategy_indicator(
            key="business_success_rate",
            title="业务成功率",
            value=_format_strategy_rate(success_rate),
            target=">= 90%",
            status=success_status,
            detail=f"统计窗口内业务调用 {business_total} 次，失败 {business_failed} 次。",
            action="成功率低于目标时，先看业务调用详情里的五段链路判定。",
        ),
        _strategy_indicator(
            key="billing_coverage",
            title="计费完整度",
            value=_format_strategy_rate(billing_rate),
            target="100% 可计费成功任务已定价",
            status=billing_status,
            detail=f"可计费 {billable} 次，待定价 {unpriced} 次。",
            action="待定价不为 0 时，先补模型或业务版本的计价规则。",
        ),
        _strategy_indicator(
            key="callback_health",
            title="回调健康",
            value=f"{callback_failed} 失败 / {callback_missing} 未配置",
            target="失败 0，核心业务必须有回调口径",
            status=callback_status,
            detail="回调决定业务方能否拿到最终结果，不能只看中台任务成功。",
            action="出现回调失败时，先查业务运行详情和回调响应，再联系业务方确认接口。",
        ),
        _strategy_indicator(
            key="wallet_settlement",
            title="扣费闭环",
            value=f"{wallet_settled} 已结算 / {wallet_failed} 失败",
            target="可计费任务应完成扣费或明确不扣费",
            status=wallet_status,
            detail=f"当前可计费任务 {billable} 次，钱包结算 {wallet_settled} 次。",
            action="扣费失败或结算不足时，先进入账单页查看修复动作。",
        ),
        _strategy_indicator(
            key="risk_closure",
            title="风险闭环",
            value=f"{risk_count} 个风险",
            target="发版前风险为 0，或人工登记暂缓/豁免原因",
            status=risk_status,
            detail=f"风险由失败 {business_failed}、回调失败 {callback_failed}、待定价 {unpriced} 共同构成。",
            action="风险不为 0 时，不要直接发版；先处理或登记上线结论。",
        ),
    ]
    return north_star, indicators


def _strategy_summary(window_hours: int = 24) -> schemas.DashboardStrategySummary:
    window_hours = max(1, min(int(window_hours or 24), 2160))
    since = datetime.utcnow() - timedelta(hours=window_hours)
    zero_north_star, zero_indicators = _build_strategy_indicators(
        business_total=0,
        business_succeeded=0,
        business_failed=0,
        success_rate=None,
        billable=0,
        unpriced=0,
        callback_failed=0,
        callback_missing=0,
        wallet_settled=0,
        wallet_failed=0,
        risk_count=0,
    )

    zero = schemas.DashboardStrategySummary(
        window_hours=window_hours,
        north_star=zero_north_star,
        indicators=zero_indicators,
        business_total=0,
        business_succeeded=0,
        business_failed=0,
        success_rate=None,
        billable=0,
        unpriced=0,
        no_charge=0,
        billing_pending=0,
        callback_failed=0,
        callback_missing=0,
        wallet_settled=0,
        wallet_failed=0,
        cost_by_currency={},
        quota_units=0,
        risk_count=0,
    )

    try:
        with get_session() as session:
            rows = (
                session.execute(select(BusinessRun).where(BusinessRun.created_at >= since).order_by(BusinessRun.created_at.desc()))
                .scalars()
                .all()
            )
    except SQLAlchemyError:
        logger.exception("dashboard.strategy_summary query failed")
        return zero
    except Exception:
        logger.exception("dashboard.strategy_summary unavailable")
        return zero

    total = len(rows)
    succeeded = sum(1 for row in rows if row.status == "succeeded")
    failed = sum(1 for row in rows if row.status in {"failed", "cancelled"})
    billable = sum(
        1
        for row in rows
        if row.status == "succeeded" and ((float(row.cost_amount or 0) > 0) or int(row.quota_units or 0) > 0)
    )
    unpriced = sum(
        1
        for row in rows
        if row.status == "succeeded" and not row.cost_amount and not row.quota_units
    )
    callback_failed = sum(1 for row in rows if row.callback_status == "failed" or bool(row.callback_error))
    callback_missing = 0
    cost_by_currency: dict[str, float] = {}
    quota_units = 0
    for row in rows:
        quota_units += int(row.quota_units or 0)
        if row.cost_amount is None:
            continue
        currency = (row.currency or "CNY").upper()
        cost_by_currency[currency] = round(cost_by_currency.get(currency, 0.0) + float(row.cost_amount or 0), 4)

    billing_pending = unpriced
    no_charge = failed
    risk_count = failed + callback_failed + billing_pending
    north_star, indicators = _build_strategy_indicators(
        business_total=total,
        business_succeeded=succeeded,
        business_failed=failed,
        success_rate=round(succeeded / total, 4) if total else None,
        billable=billable,
        unpriced=unpriced,
        callback_failed=callback_failed,
        callback_missing=callback_missing,
        wallet_settled=0,
        wallet_failed=0,
        risk_count=risk_count,
    )
    return schemas.DashboardStrategySummary(
        window_hours=window_hours,
        north_star=north_star,
        indicators=indicators,
        business_total=total,
        business_succeeded=succeeded,
        business_failed=failed,
        success_rate=(succeeded / total if total else None),
        billable=billable,
        unpriced=unpriced,
        no_charge=no_charge,
        billing_pending=billing_pending,
        callback_failed=callback_failed,
        callback_missing=callback_missing,
        wallet_settled=0,
        wallet_failed=0,
        cost_by_currency=cost_by_currency,
        quota_units=quota_units,
        risk_count=risk_count,
    )


def _today_start() -> datetime:
    """Return start of today in Asia/Shanghai, converted to naive UTC for DB comparisons.

    Most of our timestamps are stored/treated as UTC in DB. The dashboard, however, should
    reflect China business day boundaries.
    """
    now_cn = datetime.now(ZoneInfo("Asia/Shanghai"))
    start_cn = datetime.combine(now_cn.date(), time.min, tzinfo=ZoneInfo("Asia/Shanghai"))
    return start_cn.astimezone(UTC).replace(tzinfo=None)


@router.get("/metrics", response_model=schemas.DashboardMetricsResponse)
def get_dashboard_metrics() -> schemas.DashboardMetricsResponse:
    today_start = _today_start()
    with get_session() as session:
        def safe_scalar(stmt, default: int = 0) -> int:
            try:
                return int(session.scalar(stmt) or default)
            except SQLAlchemyError:
                logger.exception("dashboard.metrics query failed: %s", stmt)
                return default

        def safe_group_count(col, id_col, filters: list | None = None) -> list[tuple[str, int]]:
            try:
                stmt = select(col, func.count(id_col))
                if filters:
                    stmt = stmt.where(*filters)
                rows = session.execute(stmt.group_by(col)).all()
                out: list[tuple[str, int]] = []
                for status, count in rows:
                    if status is None:
                        continue
                    out.append((str(status), int(count or 0)))
                return out
            except SQLAlchemyError:
                logger.exception("dashboard.metrics group_by failed: %s", col)
                return []

        # NOTE: The legacy task pipeline uses `tasks`/`task_events`.
        # The evaluation platform and Coze plugin primarily create `eval_run` and `ability_tasks`.
        # For a useful dashboard in the current product stage, we aggregate across all three.
        task_filter = Task.is_deleted.is_(False)
        task_total = safe_scalar(select(func.count(Task.id)).where(task_filter))
        ability_total = safe_scalar(select(func.count(AbilityTask.id)))
        eval_total = safe_scalar(select(func.count(EvalRun.id)))
        total_tasks = task_total + ability_total + eval_total

        task_pending = safe_scalar(select(func.count(Task.id)).where(task_filter, Task.status.in_(["created", "pending", "queued"])))
        task_running = safe_scalar(select(func.count(Task.id)).where(task_filter, Task.status == "running"))
        ability_pending = safe_scalar(select(func.count(AbilityTask.id)).where(AbilityTask.status == "queued"))
        ability_running = safe_scalar(select(func.count(AbilityTask.id)).where(AbilityTask.status == "running"))
        eval_pending = safe_scalar(select(func.count(EvalRun.id)).where(EvalRun.status == "queued"))
        eval_running = safe_scalar(select(func.count(EvalRun.id)).where(EvalRun.status == "running"))

        queue_depth = task_pending + ability_pending + eval_pending
        running_total = task_running + ability_running + eval_running

        pending_batch_filter = TaskBatch.completed_count < TaskBatch.total_count
        pending_batches = safe_scalar(select(func.count(TaskBatch.id)).where(pending_batch_filter))
        pending_batch_tasks = safe_scalar(
            select(func.sum(TaskBatch.total_count - TaskBatch.completed_count)).where(pending_batch_filter)
        )

        failed_tasks = (
            safe_scalar(select(func.count(Task.id)).where(task_filter, Task.status == "failed"))
            + safe_scalar(select(func.count(AbilityTask.id)).where(AbilityTask.status == "failed"))
            + safe_scalar(select(func.count(EvalRun.id)).where(EvalRun.status == "failed"))
        )

        # Status buckets aggregated across the three pipelines.
        buckets: dict[str, int] = {}
        for status, count in safe_group_count(Task.status, Task.id, [task_filter]):
            buckets[status] = buckets.get(status, 0) + count
        for status, count in safe_group_count(AbilityTask.status, AbilityTask.id):
            buckets[status] = buckets.get(status, 0) + count
        for status, count in safe_group_count(EvalRun.status, EvalRun.id):
            buckets[status] = buckets.get(status, 0) + count
        status_buckets = [schemas.TaskStatusBucket(status=k, count=v) for k, v in sorted(buckets.items(), key=lambda kv: (-kv[1], kv[0]))]

        today_map: dict[str, int] = {}
        try:
            for status, count in session.execute(
                select(Task.status, func.count(Task.id))
                .where(Task.created_at >= today_start, task_filter)
                .group_by(Task.status)
            ).all():
                if status is None:
                    continue
                today_map[str(status)] = today_map.get(str(status), 0) + int(count or 0)
        except SQLAlchemyError:
            logger.exception("dashboard.metrics today task query failed")
        try:
            for status, count in session.execute(
                select(AbilityTask.status, func.count(AbilityTask.id)).where(AbilityTask.created_at >= today_start).group_by(AbilityTask.status)
            ).all():
                if status is None:
                    continue
                today_map[str(status)] = today_map.get(str(status), 0) + int(count or 0)
        except SQLAlchemyError:
            logger.exception("dashboard.metrics today ability_task query failed")
        try:
            for status, count in session.execute(
                select(EvalRun.status, func.count(EvalRun.id)).where(EvalRun.created_at >= today_start).group_by(EvalRun.status)
            ).all():
                if status is None:
                    continue
                today_map[str(status)] = today_map.get(str(status), 0) + int(count or 0)
        except SQLAlchemyError:
            logger.exception("dashboard.metrics today eval_run query failed")

        # Merge recent "tasks" from all pipelines.
        try:
            legacy_tasks = (
                session.execute(
                    select(Task).where(task_filter).order_by(Task.created_at.desc()).limit(8)
                )
                .scalars()
                .all()
            )
        except SQLAlchemyError:
            logger.exception("dashboard.metrics recent legacy tasks failed")
            legacy_tasks = []
        try:
            ability_tasks = session.execute(select(AbilityTask).order_by(AbilityTask.created_at.desc()).limit(8)).scalars().all()
        except SQLAlchemyError:
            logger.exception("dashboard.metrics recent ability tasks failed")
            ability_tasks = []
        try:
            eval_rows = (
                session.execute(
                    select(EvalRun, EvalWorkflowVersion)
                    .join(EvalWorkflowVersion, EvalWorkflowVersion.id == EvalRun.workflow_version_id, isouter=True)
                    .order_by(EvalRun.created_at.desc())
                    .limit(8)
                )
                .all()
            )
        except SQLAlchemyError:
            logger.exception("dashboard.metrics recent eval runs failed")
            eval_rows = []
        recent: list[schemas.RecentTask] = []
        for task in legacy_tasks:
            recent.append(
                schemas.RecentTask(
                    id=task.id,
                    user_id=task.user_id,
                    tool_action=task.tool_action,
                    channel=task.channel,
                    status=task.status,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    error_message=task.error_message,
                )
            )
        for t in ability_tasks:
            recent.append(
                schemas.RecentTask(
                    id=t.id,
                    user_id=str(t.user_id or ""),
                    tool_action=f"{t.ability_provider}:{t.capability_key or ''}",
                    channel="ability-task",
                    status=t.status,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                    error_message=t.error_message,
                )
            )
        for run, wf in eval_rows:
            name = wf.name if wf else (run.workflow_version_id or "eval")
            recent.append(
                schemas.RecentTask(
                    id=run.id,
                    user_id=run.created_by,
                    tool_action=f"eval:{name}",
                    channel="eval",
                    status=run.status,
                    created_at=run.created_at,
                    updated_at=run.updated_at,
                    error_message=run.error_message,
                )
            )
        recent.sort(key=lambda x: x.created_at, reverse=True)
        recent_tasks = recent[:8]

        try:
            executor_health = session.execute(select(Executor).order_by(Executor.updated_at.desc())).scalars().all()
        except SQLAlchemyError:
            logger.exception("dashboard.metrics executor health query failed")
            executor_health = []

    return schemas.DashboardMetricsResponse(
        totals=schemas.DashboardTotals(
            total_tasks=total_tasks,
            queue_depth=queue_depth,
            pending_batches=pending_batches,
            failed_tasks=failed_tasks,
        ),
        queue_overview=schemas.QueueOverview(
            total_pending=queue_depth,
            total_running=running_total,
            task_pending=task_pending,
            task_running=task_running,
            ability_pending=ability_pending,
            ability_running=ability_running,
            eval_pending=eval_pending,
            eval_running=eval_running,
            pending_batches=pending_batches,
            pending_batch_tasks=pending_batch_tasks,
        ),
        status_buckets=status_buckets,
        today=schemas.TodaySummary(
            created=int(today_map.get("created", 0) + today_map.get("pending", 0) + today_map.get("queued", 0)),
            completed=int(today_map.get("completed", 0) + today_map.get("succeeded", 0)),
            failed=int(today_map.get("failed", 0)),
        ),
        recent_tasks=recent_tasks,
        executor_health=[
            schemas.ExecutorHealth(
                id=executor.id,
                name=executor.name,
                status=executor.status,
                health_status=executor.health_status,
                max_concurrency=executor.max_concurrency,
                weight=executor.weight,
                last_heartbeat_at=executor.last_heartbeat_at,
            )
            for executor in executor_health
        ],
        strategy_summary=_strategy_summary(window_hours=24),
    )


@router.get("/logs", response_model=schemas.DispatchLogResponse)
def get_dispatch_logs(limit: int = Query(25, ge=1, le=100)) -> schemas.DispatchLogResponse:
    with get_session() as session:
        try:
            rows = (
                session.execute(
                    select(TaskEvent, Task)
                    .join(Task, Task.id == TaskEvent.task_id)
                    .order_by(TaskEvent.created_at.desc())
                    .limit(limit)
                )
                .all()
            )
        except SQLAlchemyError:
            logger.exception("dashboard.logs legacy task events query failed")
            rows = []

    entries: list[schemas.DispatchLogEntry] = []
    for event, task in rows:
        entries.append(
            schemas.DispatchLogEntry(
                id=event.id,
                task_id=task.id,
                tool_action=task.tool_action,
                task_status=task.status,
                event_type=event.event_type,
                payload=event.payload,
                created_at=event.created_at,
            )
        )

    # If the legacy pipeline has no events, fall back to ability invocation logs
    # so the dashboard isn't a "whiteboard" during eval/testing stage.
    if not entries:
        with get_session() as session:
            logs = (
                session.execute(select(AbilityInvocationLog).order_by(AbilityInvocationLog.created_at.desc()).limit(limit))
                .scalars()
                .all()
            )
        for log in logs:
            payload = {
                "source": log.source,
                "executor": log.executor_name or log.executor_id or log.executor_type,
                "stored_url": log.stored_url,
                "error": log.error_message,
                "trace_id": log.trace_id,
                "workflow_run_id": log.workflow_run_id,
            }
            entries.append(
                schemas.DispatchLogEntry(
                    id=int(log.id),
                    task_id=str(log.task_id or ""),
                    tool_action=f"{log.ability_provider}:{log.capability_key}",
                    task_status=log.status,
                    event_type="ability_invocation",
                    payload={k: v for k, v in payload.items() if v},
                    created_at=log.created_at,
                )
            )
    return schemas.DispatchLogResponse(entries=entries)


@router.get("/system-config", response_model=schemas.SystemConfigResponse)
def get_system_config() -> schemas.SystemConfigResponse:
    settings = get_settings()
    db_url = make_url(settings.database_url)
    backend = getattr(db_url, "get_backend_name", None)
    driver = getattr(db_url, "get_driver_name", None)
    backend_name = backend() if callable(backend) else db_url.drivername.split("+")[0]
    driver_name = driver() if callable(driver) else (db_url.drivername.split("+")[1] if "+" in db_url.drivername else None)
    sanitized_dsn = f"{backend_name}{'+' + driver_name if driver_name else ''}://{db_url.host or 'local'}:{db_url.port or '-'}"
    if db_url.database:
        sanitized_dsn += f"/{db_url.database}"

    todo_items = [
        schemas.TodoItem(
            title="RAM 角色信任策略待收紧",
            description="CLTZ 角色目前允许 root AssumeRole，需要限定来源账号并考虑 MFA；这是云账号侧安全治理项，需要在阿里云 RAM 策略中处理。",
            severity="high",
        ),
        schemas.TodoItem(
            title="积分服务独立实现",
            description="当前仅有临时积分接口，后续需替换为正式服务并补充扣费审计。",
            severity="medium",
        ),
        schemas.TodoItem(
            title="ComfyUI 工作流管理",
            description="需要在管理端实现工作流上传与版本比对，避免直接修改代码。",
            severity="medium",
        ),
    ]

    feature_flags = {
        "baidu_quality_upgrade": True,
        "oss_direct_upload": True,
        "comfyui_pipeline": False,
        "componentized_ai": False,
    }
    coze_token_hint = None
    if settings.coze_api_token:
        coze_token_hint = "COZE_API_TOKEN"
    elif settings.service_api_token:
        coze_token_hint = "SERVICE_API_TOKEN"
    coze_config = schemas.CozeConfig(
        base_url=settings.coze_base_url,
        loop_base_url=settings.coze_loop_base_url,
        default_timeout=settings.coze_default_timeout,
        token_present=bool(settings.coze_api_token or settings.service_api_token),
        token_hint=coze_token_hint,
    )
    return schemas.SystemConfigResponse(
        app_name=settings.app_name,
        database=schemas.DatabaseConfig(
            backend=backend_name,
            driver=driver_name,
            host=db_url.host,
            port=db_url.port,
            database=db_url.database,
            dsn=sanitized_dsn,
        ),
        oss=schemas.OssConfig(
            bucket=settings.oss_bucket,
            endpoint=settings.oss_endpoint,
            internal_endpoint=settings.oss_internal_endpoint,
            public_domain=settings.oss_public_domain,
            root_prefix=settings.oss_root_prefix,
            sts_duration=settings.oss_sts_duration,
            role_arn=settings.oss_role_arn,
        ),
        security=schemas.SecurityConfig(
            jwt_access_ttl=settings.jwt_access_token_expires,
            jwt_refresh_ttl=settings.jwt_refresh_token_expires,
            upload_token_ttl=settings.upload_token_ttl,
        ),
        coze=coze_config,
        feature_flags=feature_flags,
        todo_items=todo_items,
    )


def _make_release_check(
    *,
    name: str,
    title: str,
    status: str,
    detail: str,
    blocking: bool | None = None,
    suggestion: str | None = None,
    duration_ms: int | None = None,
) -> schemas.ReleasePreflightCheck:
    return schemas.ReleasePreflightCheck(
        name=name,
        title=title,
        status=status,
        blocking=(status == "fail") if blocking is None else blocking,
        detail=detail,
        suggestion=suggestion,
        durationMs=duration_ms,
    )


def _timed_http_check(
    *,
    client: httpx.Client,
    method: str,
    path: str,
    json_payload: dict[str, Any] | None = None,
) -> tuple[int, Any, int]:
    started = perf_counter()
    response = client.request(method, path, json=json_payload)
    duration_ms = int((perf_counter() - started) * 1000)
    try:
        body: Any = response.json()
    except Exception:
        body = {"text": response.text[:500]}
    return response.status_code, body, duration_ms


def _business_label(key: str) -> str:
    return CORE_BUSINESS_LABELS.get(key, key)


def _vendor_model_has_cost_policy(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    for key in ("unitPrice", "unit_price", "discountPrice", "discount_price", "listPrice", "list_price", "price"):
        raw = value.get(key)
        if raw in (None, ""):
            continue
        try:
            if float(raw) > 0:
                return True
        except (TypeError, ValueError):
            return False
    return False


def _provider_runtime_key_configured(session, provider: str) -> bool:
    normalized = str(provider or "").strip().lower()
    if normalized == "baidu":
        settings = get_settings()
        if settings.baidu_api_key and settings.baidu_secret_key:
            return True
    if normalized == "volcengine" and get_settings().volcengine_api_key:
        return True
    rows = session.execute(select(ApiKey).where(ApiKey.provider == normalized)).scalars().all()
    return any(is_usable(row) for row in rows)


def _business_governance_for_preflight(session, row: BusinessCapability) -> dict[str, Any]:
    recipe = row.recipe if isinstance(row.recipe, dict) else {}
    issues: list[str] = []
    warnings: list[str] = []
    primary_ability_id: str | None = None
    ability: Ability | None = None
    vendor_model_id: int | None = None
    vendor_model: VendorModelCatalog | None = None

    try:
        primary_ability_id = BusinessRunService._extract_primary_ability_id(recipe)
    except Exception:
        primary_ability_id = None
    if not primary_ability_id:
        issues.append("未绑定主能力")
    else:
        ability = session.get(Ability, primary_ability_id)
        if not ability:
            issues.append("主能力不存在")
        elif ability.status != "active":
            issues.append("主能力未启用")

    try:
        steps = BusinessRunService._normalized_recipe_steps(recipe)
    except Exception:
        steps = []
    executable_steps = [
        step
        for step in steps
        if step.get("enabled") is not False and str(step.get("type") or "").strip() in RECIPE_EXECUTABLE_STEP_TYPES
    ]
    if not executable_steps:
        issues.append("配方没有可执行步骤")

    try:
        vendor_model_id = BusinessRunService._extract_recipe_vendor_model_id(recipe)
    except Exception:
        vendor_model_id = None
    if vendor_model_id is None and ability is not None:
        vendor_model_id = ability.vendor_model_id
    if vendor_model_id is not None:
        vendor_model = session.get(VendorModelCatalog, vendor_model_id)
        if not vendor_model:
            issues.append("绑定的模型不存在")
        elif vendor_model.status != "active":
            issues.append("绑定的模型未启用")

    provider = str(
        (vendor_model.provider if vendor_model else None)
        or (ability.provider if ability else None)
        or ""
    ).strip().lower()
    if provider in VENDOR_PROVIDERS:
        if vendor_model and not _vendor_model_has_cost_policy(vendor_model.cost_policy):
            warnings.append("第三方模型未配置成本口径")
        if not _provider_runtime_key_configured(session, provider):
            issues.append("第三方模型没有可用密钥")

    if issues:
        status = "blocker" if row.status == "active" or row.is_default else "warning"
    elif warnings:
        status = "warning"
    else:
        status = "ready"
    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "primaryAbilityId": primary_ability_id,
    }


def _run_business_capability_governance_preflight() -> schemas.ReleasePreflightCheck:
    started = perf_counter()
    try:
        with get_session() as session:
            ensure_default_abilities(session)
            ensure_default_business_capabilities(session)
            rows = (
                session.execute(
                    select(BusinessCapability)
                    .where(BusinessCapability.business_key.in_(CORE_BUSINESS_KEYS))
                    .order_by(
                        BusinessCapability.business_key.asc(),
                        BusinessCapability.is_default.desc(),
                        BusinessCapability.release_time.desc(),
                        BusinessCapability.created_at.desc(),
                    )
                )
                .scalars()
                .all()
            )
            default_by_key: dict[str, BusinessCapability] = {}
            for row in rows:
                if row.is_default and row.business_key in CORE_BUSINESS_KEYS:
                    default_by_key[row.business_key] = row

            blockers: list[str] = []
            warnings: list[str] = []
            missing = [key for key in CORE_BUSINESS_KEYS if key not in default_by_key]
            for key in missing:
                blockers.append(f"{_business_label(key)}缺少默认版本")
            for key in CORE_BUSINESS_KEYS:
                row = default_by_key.get(key)
                if not row:
                    continue
                governance = _business_governance_for_preflight(session, row)
                label = f"{_business_label(key)} {row.version}"
                if row.status != "active":
                    blockers.append(f"{label}未启用")
                if not governance.get("primaryAbilityId"):
                    blockers.append(f"{label}未绑定主能力")
                if governance["status"] == "blocker":
                    blockers.append(f"{label}：{'、'.join(governance['issues'][:3]) or '底层阻塞'}")
                elif governance["status"] == "warning":
                    warnings.append(f"{label}：{'、'.join((governance['warnings'] or governance['issues'])[:3]) or '需要补齐'}")

        duration_ms = int((perf_counter() - started) * 1000)
        if blockers:
            return _make_release_check(
                name="business_capability_governance",
                title="业务能力底层治理",
                status="fail",
                detail=f"阻塞={len(blockers)}；{'; '.join(blockers[:5])}",
                suggestion="先到业务能力页修复默认版本、主能力、模型密钥或可执行步骤，再进入线上闭环。",
                duration_ms=duration_ms,
            )
        if warnings:
            return _make_release_check(
                name="business_capability_governance",
                title="业务能力底层治理",
                status="warn",
                blocking=False,
                detail=f"提醒={len(warnings)}；{'; '.join(warnings[:5])}",
                suggestion="非阻塞提醒需要登记原因；正式收费前必须补齐成本口径。",
                duration_ms=duration_ms,
            )
        return _make_release_check(
            name="business_capability_governance",
            title="业务能力底层治理",
            status="pass",
            detail="花纹提取、图裂变、扩图均存在 active 默认版本，且底层主能力可用。",
            suggestion="后续版本切换前继续先跑本检查。",
            duration_ms=duration_ms,
        )
    except Exception as exc:
        logger.exception("business capability governance preflight failed")
        return _make_release_check(
            name="business_capability_governance",
            title="业务能力底层治理",
            status="fail",
            detail=str(exc),
            suggestion="检查失败时按阻塞处理，先确认数据库迁移、能力种子和业务版本数据。",
        )


def _run_auth_scope_preflight() -> schemas.ReleasePreflightCheck:
    started = perf_counter()
    try:
        now = datetime.utcnow()
        with get_session() as session:
            users = list(session.execute(select(User)).scalars().all())
            sessions = list(session.execute(select(UserSession)).scalars().all())
            invites = list(session.execute(select(InviteCode)).scalars().all())
        active_admin_count = len([user for user in users if user.role == "admin" and user.status == "active"])
        unscoped_client_count = len([user for user in users if user.role == "client" and user.status == "active" and not user.tenant_id])
        active_invites = [row for row in invites if row.status == "active"]
        unscoped_invite_count = len([row for row in active_invites if not row.tenant_id])
        expired_invite_count = len([row for row in active_invites if row.expires_at and row.expires_at <= now])
        active_session_count = len([row for row in sessions if row.status == "active" and row.expires_at > now])

        warnings: list[str] = []
        if unscoped_client_count:
            warnings.append(f"业务方账号未绑定范围 {unscoped_client_count} 个")
        if unscoped_invite_count:
            warnings.append(f"可用邀请码未绑定业务方 {unscoped_invite_count} 个")
        if expired_invite_count:
            warnings.append(f"过期邀请码仍激活 {expired_invite_count} 个")
        duration_ms = int((perf_counter() - started) * 1000)

        if active_admin_count <= 0:
            return _make_release_check(
                name="auth_scope_summary",
                title="账号权限上线检查",
                status="fail",
                detail="没有 active 管理员账号。",
                suggestion="先恢复或创建管理员账号，否则管理端上线后无法维护。",
                duration_ms=duration_ms,
            )
        if warnings:
            return _make_release_check(
                name="auth_scope_summary",
                title="账号权限上线检查",
                status="fail",
                detail="；".join(warnings),
                suggestion="先到账号权限页补齐业务方范围或失效过期邀请码；账号范围不清晰会影响后续限额、账单和隔离。",
                duration_ms=duration_ms,
            )
        return _make_release_check(
            name="auth_scope_summary",
            title="账号权限上线检查",
            status="pass",
            detail=f"active 管理员 {active_admin_count} 个，活跃会话 {active_session_count} 个，业务方账号和邀请码范围清晰。",
            suggestion="上线后继续保留至少一个可登录管理员。",
            duration_ms=duration_ms,
        )
    except Exception as exc:
        logger.exception("auth scope preflight failed")
        return _make_release_check(
            name="auth_scope_summary",
            title="账号权限上线检查",
            status="fail",
            detail=str(exc),
            suggestion="检查失败时按阻塞处理，先确认账号表、会话表和邀请码表迁移完整。",
        )


def _run_release_preflight_checks(
    *,
    base_url: str,
    expect_server_url: str | None = None,
) -> list[schemas.ReleasePreflightCheck]:
    checks: list[schemas.ReleasePreflightCheck] = []
    timeout = httpx.Timeout(20.0, connect=5.0)
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout) as client:
        try:
            status, body, duration_ms = _timed_http_check(client=client, method="GET", path="/health")
            checks.append(
                _make_release_check(
                    name="backend_health",
                    title="后端存活",
                    status="pass" if status == 200 and isinstance(body, dict) and body.get("status") == "ok" else "fail",
                    detail=f"HTTP {status}",
                    suggestion="如果失败，先确认 8099 是否为正式 backend 进程。",
                    duration_ms=duration_ms,
                )
            )
        except Exception as exc:
            checks.append(
                _make_release_check(
                    name="backend_health",
                    title="后端存活",
                    status="fail",
                    detail=str(exc),
                    suggestion="先恢复 backend，再继续检查工具箱和评测链路。",
                )
            )

        try:
            status, body, duration_ms = _timed_http_check(client=client, method="GET", path="/api/coze/podi/openapi.json")
            server_url = ""
            if isinstance(body, dict):
                servers = body.get("servers")
                if isinstance(servers, list) and servers and isinstance(servers[0], dict):
                    server_url = str(servers[0].get("url") or "")
            ok = status == 200 and bool(server_url) and (not expect_server_url or server_url == expect_server_url)
            detail = f"HTTP {status}；工具箱地址={server_url or '-'}"
            if expect_server_url:
                detail += f"；期望={expect_server_url}"
            checks.append(
                _make_release_check(
                    name="coze_openapi",
                    title="Coze 工具箱文档",
                    status="pass" if ok else "fail",
                    detail=detail,
                    suggestion="如果地址不对，先修正 PODI_INTERNAL_BASE_URL/反代配置后重新导入工具箱。",
                    duration_ms=duration_ms,
                )
            )
        except Exception as exc:
            checks.append(
                _make_release_check(
                    name="coze_openapi",
                    title="Coze 工具箱文档",
                    status="fail",
                    detail=str(exc),
                    suggestion="工具箱文档不可用时不要发版。",
                )
            )

        try:
            status, body, duration_ms = _timed_http_check(
                client=client,
                method="POST",
                path="/api/coze/podi/tasks/get",
                json_payload={"taskId": "__release_preflight_not_found__"},
            )
            detail = body.get("detail") if isinstance(body, dict) else body
            checks.append(
                _make_release_check(
                    name="internal_tasks_get",
                    title="Coze 内部查询入口",
                    status="pass" if status == 404 and detail == "TASK_NOT_FOUND" else "fail",
                    detail=f"HTTP {status}；返回={detail}",
                    suggestion="如果返回 INTERNAL_ONLY，说明 Coze/backend 内网访问边界仍未打通。",
                    duration_ms=duration_ms,
                )
            )
        except Exception as exc:
            checks.append(
                _make_release_check(
                    name="internal_tasks_get",
                    title="Coze 内部查询入口",
                    status="fail",
                    detail=str(exc),
                    suggestion="这是 2026-04-27 事故的核心检查项，失败必须阻断发版。",
                )
            )

        try:
            status, body, duration_ms = _timed_http_check(
                client=client,
                method="POST",
                path="/api/coze/podi/comfyui/queue-summary",
                json_payload={},
            )
            servers = body.get("servers") if isinstance(body, dict) else None
            server_count = len(servers) if isinstance(servers, list) else 0
            diagnostics = body.get("diagnostics") if isinstance(body, dict) else None
            error = body.get("error") if isinstance(body, dict) else None
            ok = status == 200 and server_count > 0 and not error
            checks.append(
                _make_release_check(
                    name="comfyui_queue_summary",
                    title="ComfyUI 队列可见",
                    status="pass" if ok else "fail",
                    detail=f"HTTP {status}；节点数={server_count}；诊断={diagnostics or error or '-'}",
                    suggestion="如果某台能力机不可达，要先标记离线或恢复服务，不能让任务静默卡住。",
                    duration_ms=duration_ms,
                )
            )
        except Exception as exc:
            checks.append(
                _make_release_check(
                    name="comfyui_queue_summary",
                    title="ComfyUI 队列可见",
                    status="fail",
                    detail=str(exc),
                    suggestion="队列不可见时无法判断 GPU 是否被喂满，必须先处理。",
                )
            )

        try:
            status, body, duration_ms = _timed_http_check(client=client, method="GET", path="/api/evals/workflow-versions")
            items = body.get("items") if isinstance(body, dict) else body
            count = len(items) if isinstance(items, list) else 0
            checks.append(
                _make_release_check(
                    name="eval_workflow_catalog",
                    title="测评目录可读",
                    status="pass" if status == 200 and count > 0 else "fail",
                    detail=f"HTTP {status}；工作流数={count}",
                    suggestion="如果目录为空，先确认 EVAL_PUBLIC_ENABLED 和工作流治理数据。",
                    duration_ms=duration_ms,
                )
            )
        except Exception as exc:
            checks.append(
                _make_release_check(
                    name="eval_workflow_catalog",
                    title="测评目录可读",
                    status="fail",
                    detail=str(exc),
                    suggestion="测评目录不可读时，不要进入人工验收。",
                )
            )

    try:
        queue_summary = integration_test_service.get_comfyui_queue_summary()
        with get_session() as session:
            report = build_eval_operations_health(
                session,
                stale_minutes=30,
                submit_grace_minutes=5,
                recent_hours=24,
                limit=20,
                comfyui_queue_summary=queue_summary,
            )
        health_status = str(report.get("status") or "critical")
        issue_count = len(report.get("issues") or [])
        checks.append(
            _make_release_check(
                name="eval_operations_health",
                title="评测运行健康",
                status="pass" if health_status == "healthy" else ("warn" if health_status == "warning" else "fail"),
                blocking=health_status == "critical",
                detail=f"状态={health_status}；问题数={issue_count}；近期成功={report.get('recentSuccessCount', 0)}",
                suggestion="critical 必须阻断发版；warning 需要人工确认是否为已知余额/外部模型问题。",
            )
        )
    except Exception as exc:
        checks.append(
            _make_release_check(
                name="eval_operations_health",
                title="评测运行健康",
                status="fail",
                detail=str(exc),
                suggestion="健康检查自身不可用时，按发版阻断处理。",
            )
        )

    checks.append(_run_business_capability_governance_preflight())
    checks.append(_run_auth_scope_preflight())
    checks.append(
        _make_release_check(
            name="weekly_report_cron",
            title="周报守护",
            status="warn",
            blocking=False,
            detail="当前版本只支持人工生成/归档周报，尚未接入正式定时任务。",
            suggestion="上线前至少手动生成一次周报或策略快照。",
        )
    )
    checks.append(
        _make_release_check(
            name="billing_collection_cron",
            title="账单守护",
            status="warn",
            blocking=False,
            detail="充值和账单仍处于框架阶段，暂未接入正式催收/对账定时任务。",
            suggestion="当前阶段只看框架可用性，不作为业务发版阻断项。",
        )
    )
    return checks


def _release_preflight_response(
    *,
    mode: str,
    base_url: str,
    checks: list[schemas.ReleasePreflightCheck],
) -> schemas.ReleasePreflightResponse:
    blocking_count = sum(1 for check in checks if check.blocking)
    warning_count = sum(1 for check in checks if check.status == "warn")
    status = "blocked" if blocking_count else ("warning" if warning_count else "passed")
    return schemas.ReleasePreflightResponse(
        id=f"preflight_{uuid4().hex[:12]}",
        mode=mode,
        status=status,
        canRelease=blocking_count == 0,
        generatedAt=_now_utc(),
        baseUrl=base_url,
        blockingCount=blocking_count,
        warningCount=warning_count,
        checks=checks,
    )


def _create_strategy_snapshot(window_hours: int, note: str | None = None) -> schemas.StrategySnapshotResponse:
    summary = _strategy_summary(window_hours=window_hours)
    return schemas.StrategySnapshotResponse(
        id=f"strategy_{uuid4().hex[:12]}",
        generatedAt=_now_utc(),
        windowHours=summary.window_hours,
        note=note,
        summary=summary,
    )


@router.post(
    "/strategy-summary/snapshots",
    response_model=schemas.StrategySnapshotResponse,
    response_model_by_alias=True,
)
def create_strategy_snapshot(
    payload: schemas.StrategySnapshotCreateRequest | None = None,
) -> schemas.StrategySnapshotResponse:
    req = payload or schemas.StrategySnapshotCreateRequest()
    snapshot = _create_strategy_snapshot(window_hours=req.window_hours, note=req.note)
    _append_record("strategy_snapshots.json", snapshot.model_dump(by_alias=True, mode="json"), keep=100)
    return snapshot


@router.get(
    "/strategy-summary/snapshots",
    response_model=schemas.StrategySnapshotListResponse,
    response_model_by_alias=True,
)
def list_strategy_snapshots(limit: int = Query(default=8, ge=1, le=50)) -> schemas.StrategySnapshotListResponse:
    items = [
        schemas.StrategySnapshotResponse.model_validate(item)
        for item in _read_records("strategy_snapshots.json")[:limit]
    ]
    return schemas.StrategySnapshotListResponse(items=items)


@router.post("/weekly-report/run", response_model=schemas.WeeklyReportResponse, response_model_by_alias=True)
def run_weekly_report(payload: schemas.WeeklyReportRunRequest | None = None) -> schemas.WeeklyReportResponse:
    req = payload or schemas.WeeklyReportRunRequest()
    snapshot = _create_strategy_snapshot(window_hours=req.window_hours, note=req.note or "weekly-report")
    DASHBOARD_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_name = f"weekly_report_{_now_utc().strftime('%Y%m%d_%H%M%S')}.md"
    report_path = DASHBOARD_REPORT_DIR / report_name
    summary = snapshot.summary
    report_path.write_text(
        "\n".join(
            [
                f"# PODI 周报快照 {snapshot.generated_at.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "",
                f"- 统计窗口：近 {summary.window_hours} 小时",
                f"- 业务调用：{summary.business_total}",
                f"- 成功：{summary.business_succeeded}",
                f"- 失败：{summary.business_failed}",
                f"- 可计费：{summary.billable}",
                f"- 待定价：{summary.unpriced}",
                f"- 回调失败：{summary.callback_failed}",
                f"- 风险数：{summary.risk_count}",
                f"- 成本：{summary.cost_by_currency}",
                f"- 额度：{summary.quota_units}",
                "",
                "## 北极星与 KPI",
                "",
                f"- {summary.north_star.title}：{summary.north_star.value}，状态={summary.north_star.status}，动作={summary.north_star.action}",
                *[
                    f"- {item.title}：{item.value}，目标={item.target}，状态={item.status}，动作={item.action}"
                    for item in summary.indicators
                ],
                "",
                "说明：当前为管理端轻量周报，后续可接入正式定时任务和外部通知。",
            ]
        ),
        encoding="utf-8",
    )
    webhook_configured = bool(os.getenv("PODI_WEEKLY_REPORT_WEBHOOK_URL"))
    send_status = "not_sent"
    send_detail = "未请求发送，只保存本地报告。"
    if req.send:
        send_status = "sent" if webhook_configured else "failed"
        send_detail = "已配置 webhook，发送逻辑待接入。" if webhook_configured else "未配置 webhook，本次仅保存本地报告。"

    response = schemas.WeeklyReportResponse(
        id=f"weekly_{uuid4().hex[:12]}",
        generatedAt=_now_utc(),
        windowHours=summary.window_hours,
        reportPath=_relative_backend_path(report_path),
        snapshotId=snapshot.id,
        sendStatus=send_status,
        sendDetail=send_detail,
        webhookFormat=req.webhook_format or "generic",
        webhookConfigured=webhook_configured,
        summary=summary,
    )
    _append_record("weekly_reports.json", response.model_dump(by_alias=True, mode="json"), keep=100)
    _append_record("strategy_snapshots.json", snapshot.model_dump(by_alias=True, mode="json"), keep=100)
    return response


@router.get("/weekly-report/records", response_model=schemas.WeeklyReportListResponse, response_model_by_alias=True)
def list_weekly_reports(limit: int = Query(default=5, ge=1, le=50)) -> schemas.WeeklyReportListResponse:
    items = [schemas.WeeklyReportResponse.model_validate(item) for item in _read_records("weekly_reports.json")[:limit]]
    return schemas.WeeklyReportListResponse(items=items)


@router.post("/release-preflight/run", response_model=schemas.ReleasePreflightResponse, response_model_by_alias=True)
def run_release_preflight(
    payload: schemas.ReleasePreflightRunRequest | None = None,
) -> schemas.ReleasePreflightResponse:
    req = payload or schemas.ReleasePreflightRunRequest()
    base_url = (req.base_url or "http://127.0.0.1:8099").rstrip("/")
    explicit_internal_base_url = (os.getenv("PODI_INTERNAL_BASE_URL") or "").strip()
    expected = req.expect_server_url or explicit_internal_base_url
    checks = _run_release_preflight_checks(base_url=base_url, expect_server_url=expected)
    response = _release_preflight_response(mode=req.mode or "light", base_url=base_url, checks=checks)
    _append_record("release_preflight_snapshots.json", response.model_dump(by_alias=True, mode="json"), keep=100)
    return response


@router.get(
    "/release-preflight/snapshots",
    response_model=schemas.ReleasePreflightSnapshotListResponse,
    response_model_by_alias=True,
)
def list_release_preflight_snapshots(limit: int = Query(default=5, ge=1, le=50)) -> schemas.ReleasePreflightSnapshotListResponse:
    items = [
        schemas.ReleasePreflightResponse.model_validate(item)
        for item in _read_records("release_preflight_snapshots.json")[:limit]
    ]
    return schemas.ReleasePreflightSnapshotListResponse(items=items)


@router.post("/release-patrol/records", response_model=schemas.ReleasePatrolRecordResponse, response_model_by_alias=True)
def create_release_patrol_record(
    payload: schemas.ReleasePatrolRecordCreateRequest,
) -> schemas.ReleasePatrolRecordResponse:
    summary = _normalize_release_patrol_summary(payload.summary or {})
    response = schemas.ReleasePatrolRecordResponse(
        id=f"patrol_{uuid4().hex[:12]}",
        status=payload.status,
        generatedAt=_now_utc(),
        command=payload.command,
        reportPath=payload.report_path,
        note=payload.note,
        summary=summary,
    )
    _append_record("release_patrol_records.json", response.model_dump(by_alias=True, mode="json"), keep=100)
    return response


@router.post("/release-patrol/import-report", response_model=schemas.ReleasePatrolRecordResponse, response_model_by_alias=True)
def import_release_patrol_report(
    payload: schemas.ReleasePatrolImportRequest,
) -> schemas.ReleasePatrolRecordResponse:
    path = _safe_backend_file(payload.report_path)
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="REPORT_JSON_INVALID") from exc
    if not isinstance(summary, dict):
        raise HTTPException(status_code=400, detail="REPORT_JSON_NOT_OBJECT")
    summary = _normalize_release_patrol_summary(summary)
    failed = _safe_int(summary.get("failedOrUnfinished"), _safe_int(summary.get("failed")))
    unfinished = _safe_int(summary.get("unfinished"))
    status = "passed" if failed == 0 and unfinished == 0 else "failed"
    response = schemas.ReleasePatrolRecordResponse(
        id=f"patrol_{uuid4().hex[:12]}",
        status=status,
        generatedAt=_now_utc(),
        command=payload.command,
        reportPath=_relative_backend_path(path),
        note="从巡检报告导入",
        summary=summary,
    )
    _append_record("release_patrol_records.json", response.model_dump(by_alias=True, mode="json"), keep=100)
    return response


@router.get("/release-patrol/records", response_model=schemas.ReleasePatrolRecordListResponse, response_model_by_alias=True)
def list_release_patrol_records(limit: int = Query(default=5, ge=1, le=50)) -> schemas.ReleasePatrolRecordListResponse:
    items = [schemas.ReleasePatrolRecordResponse.model_validate(item) for item in _read_records("release_patrol_records.json")[:limit]]
    return schemas.ReleasePatrolRecordListResponse(items=items)


@router.get("/health-watch/status", response_model=schemas.HealthWatchStatusResponse, response_model_by_alias=True)
def get_health_watch_status() -> schemas.HealthWatchStatusResponse:
    items = [_health_watch_unit_status(definition) for definition in HEALTH_WATCH_UNITS]
    issues = [
        f"{item.title}：{item.summary}"
        for item in items
        if item.status in {"failed", "unavailable", "disabled"}
    ]
    supported = any(item.status != "unavailable" for item in items)
    return schemas.HealthWatchStatusResponse(
        generatedAt=_now_utc(),
        supported=supported,
        items=items,
        issues=issues,
    )


_RELEASE_DECISION_TITLES = {
    "approved": "确认可上线",
    "deferred": "暂缓上线",
    "blocked": "阻塞上线",
}


@router.post(
    "/release-decisions/records",
    response_model=schemas.ReleaseDecisionRecordResponse,
    response_model_by_alias=True,
)
def create_release_decision_record(
    payload: schemas.ReleaseDecisionRecordCreateRequest,
) -> schemas.ReleaseDecisionRecordResponse:
    status = str(payload.status or "").strip().lower()
    if status not in _RELEASE_DECISION_TITLES:
        raise HTTPException(status_code=400, detail="RELEASE_DECISION_STATUS_INVALID")
    response = schemas.ReleaseDecisionRecordResponse(
        id=f"decision_{uuid4().hex[:12]}",
        status=status,
        title=(payload.title or _RELEASE_DECISION_TITLES[status]).strip() or _RELEASE_DECISION_TITLES[status],
        generatedAt=_now_utc(),
        preflightId=payload.preflight_id,
        patrolId=payload.patrol_id,
        note=payload.note,
        summary=payload.summary or {},
    )
    _append_record("release_decision_records.json", response.model_dump(by_alias=True, mode="json"), keep=100)
    return response


@router.get(
    "/release-decisions/records",
    response_model=schemas.ReleaseDecisionRecordListResponse,
    response_model_by_alias=True,
)
def list_release_decision_records(limit: int = Query(default=5, ge=1, le=50)) -> schemas.ReleaseDecisionRecordListResponse:
    items = [
        schemas.ReleaseDecisionRecordResponse.model_validate(item)
        for item in _read_records("release_decision_records.json")[:limit]
    ]
    return schemas.ReleaseDecisionRecordListResponse(items=items)
