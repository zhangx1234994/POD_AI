"""Operational health checks for eval workflows and runs."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.eval import EvalRun, EvalWorkflowVersion
from app.services.task_status_contract import extract_error_code

_NON_ACTIONABLE_FAILURE_CODES = {
    # Manual patrol cancellation is an operator action, not a business chain failure.
    "EVAL_PATROL_ABORTED",
}


def _utcnow() -> datetime:
    return datetime.utcnow()


def _age_minutes(created_at: datetime | None, *, now: datetime) -> int:
    if not created_at:
        return 0
    return max(0, int((now - created_at).total_seconds() // 60))


def _image_count(run: EvalRun) -> int:
    images = run.result_image_urls_json
    return len(images) if isinstance(images, list) else 0


def _has_result(run: EvalRun) -> bool:
    return _image_count(run) > 0 or run.result_output_json is not None


def _run_item(
    run: EvalRun,
    workflow: EvalWorkflowVersion | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    return {
        "runId": run.id,
        "workflowId": workflow.workflow_id if workflow else None,
        "workflowName": workflow.name if workflow else None,
        "category": workflow.category if workflow else None,
        "status": run.status,
        "ageMinutes": _age_minutes(run.created_at, now=now),
        "cozeExecuteId": run.coze_execute_id,
        "podiTaskId": run.podi_task_id,
        "imageCount": _image_count(run),
        "hasOutput": _has_result(run),
        "errorCode": extract_error_code(run.error_message),
        "errorMessage": run.error_message,
        "createdAt": run.created_at,
        "updatedAt": run.updated_at,
    }


def _issue(severity: str, code: str, title: str, message: str, count: int) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "title": title,
        "message": message,
        "count": count,
    }


def build_eval_operations_health(
    session: Session,
    *,
    stale_minutes: int = 30,
    submit_grace_minutes: int = 5,
    recent_hours: int = 24,
    limit: int = 20,
) -> dict[str, Any]:
    """Build a lightweight health report for eval operations.

    This checks symptoms that `/health` cannot catch:
    - eval runs stuck in queued/running for too long
    - running runs that never received a Coze execute id or PODI task id
    - succeeded image workflows without any output
    - recent failures that should be visible before business users report them
    """

    now = _utcnow()
    stale_cutoff = now - timedelta(minutes=max(1, stale_minutes))
    submit_grace_cutoff = now - timedelta(minutes=max(1, submit_grace_minutes))
    recent_cutoff = now - timedelta(hours=max(1, recent_hours))
    limit = max(1, min(int(limit), 100))

    active_workflow_count = int(
        session.execute(
            select(func.count(EvalWorkflowVersion.id)).where(EvalWorkflowVersion.status == "active")
        ).scalar_one()
        or 0
    )
    total_workflow_count = int(
        session.execute(select(func.count(EvalWorkflowVersion.id))).scalar_one() or 0
    )

    status_rows = session.execute(
        select(EvalRun.status, func.count(EvalRun.id)).group_by(EvalRun.status)
    ).all()
    status_counts = {str(status or "unknown"): int(count or 0) for status, count in status_rows}

    recent_status_rows = session.execute(
        select(EvalRun.status, func.count(EvalRun.id))
        .where(EvalRun.created_at >= recent_cutoff)
        .group_by(EvalRun.status)
    ).all()
    recent_counts = {str(status or "unknown"): int(count or 0) for status, count in recent_status_rows}

    running_rows = (
        session.execute(
            select(EvalRun, EvalWorkflowVersion)
            .join(EvalWorkflowVersion, EvalWorkflowVersion.id == EvalRun.workflow_version_id, isouter=True)
            .where(EvalRun.status.in_(["queued", "running"]))
            .order_by(EvalRun.created_at.asc())
            .limit(500)
        )
        .all()
    )
    stale_running_all = [
        _run_item(run, workflow, now=now)
        for run, workflow in running_rows
        if run.created_at and run.created_at <= stale_cutoff
    ]
    submit_stalled_all = [
        _run_item(run, workflow, now=now)
        for run, workflow in running_rows
        if str(run.status or "").lower() == "running"
        and not str(run.coze_execute_id or "").strip()
        and not str(run.podi_task_id or "").strip()
        and run.created_at
        and run.created_at <= submit_grace_cutoff
    ]
    stale_running = stale_running_all[:limit]
    submit_stalled = submit_stalled_all[:limit]

    recent_failure_rows = (
        session.execute(
            select(EvalRun, EvalWorkflowVersion)
            .join(EvalWorkflowVersion, EvalWorkflowVersion.id == EvalRun.workflow_version_id, isouter=True)
            .where(EvalRun.status == "failed", EvalRun.created_at >= recent_cutoff)
            .order_by(EvalRun.created_at.desc())
            .limit(max(limit, 500))
        )
        .all()
    )
    recent_failures_raw = [_run_item(run, workflow, now=now) for run, workflow in recent_failure_rows]
    recent_failures_all = [
        item
        for item in recent_failures_raw
        if str(item.get("errorCode") or "UNKNOWN") not in _NON_ACTIONABLE_FAILURE_CODES
    ]
    recent_failures = recent_failures_all[:limit]
    error_counter = Counter(str(item.get("errorCode") or "UNKNOWN") for item in recent_failures_all)

    recent_success_rows = (
        session.execute(
            select(EvalRun, EvalWorkflowVersion)
            .join(EvalWorkflowVersion, EvalWorkflowVersion.id == EvalRun.workflow_version_id, isouter=True)
            .where(EvalRun.status == "succeeded", EvalRun.created_at >= recent_cutoff)
            .order_by(EvalRun.created_at.desc())
            .limit(500)
        )
        .all()
    )
    succeeded_without_output_all = [
        _run_item(run, workflow, now=now)
        for run, workflow in recent_success_rows
        if not _has_result(run)
    ]
    succeeded_without_output = succeeded_without_output_all[:limit]

    issues: list[dict[str, Any]] = []
    if active_workflow_count == 0:
        issues.append(
            _issue(
                "critical",
                "EVAL_NO_ACTIVE_WORKFLOW",
                "没有可用评测工作流",
                "active 工作流数量为 0，评测端无法覆盖真实业务链路。",
                1,
            )
        )
    if stale_running_all:
        issues.append(
            _issue(
                "critical",
                "EVAL_RUN_STALE",
                "存在长期未收口的评测任务",
                f"有 {len(stale_running_all)} 条任务运行超过 {stale_minutes} 分钟，需要检查 Coze/中台任务/回填链路。",
                len(stale_running_all),
            )
        )
    if submit_stalled_all:
        issues.append(
            _issue(
                "critical",
                "EVAL_SUBMIT_STALLED",
                "存在提交后没有执行标识的任务",
                f"有 {len(submit_stalled_all)} 条运行中任务没有 Coze 执行 ID 或中台任务 ID，可能卡在提交阶段。",
                len(submit_stalled_all),
            )
        )
    if succeeded_without_output_all:
        issues.append(
            _issue(
                "warning",
                "EVAL_SUCCESS_WITHOUT_OUTPUT",
                "存在成功但没有结果的评测记录",
                f"最近 {recent_hours} 小时内有 {len(succeeded_without_output_all)} 条成功记录没有图片或结构化结果。",
                len(succeeded_without_output_all),
            )
        )
    recent_failure_total = len(recent_failures_all)
    if recent_failure_total:
        issues.append(
            _issue(
                "warning",
                "EVAL_RECENT_FAILURES",
                "最近有评测失败",
                f"最近 {recent_hours} 小时内有 {recent_failure_total} 条失败记录，需看错误分布。",
                recent_failure_total,
            )
        )

    if any(item["severity"] == "critical" for item in issues):
        status = "critical"
    elif issues:
        status = "warning"
    else:
        status = "healthy"

    return {
        "generatedAt": now,
        "status": status,
        "staleMinutes": stale_minutes,
        "submitGraceMinutes": submit_grace_minutes,
        "recentHours": recent_hours,
        "activeWorkflowCount": active_workflow_count,
        "totalWorkflowCount": total_workflow_count,
        "statusCounts": status_counts,
        "recentStatusCounts": recent_counts,
        "staleRunning": stale_running,
        "submitStalled": submit_stalled,
        "succeededWithoutOutput": succeeded_without_output,
        "recentFailures": recent_failures,
        "errorCounts": dict(error_counter),
        "issues": issues,
    }
