"""Unified status contract helpers for task/query APIs.

This module provides a compatibility layer so existing storage fields can expose
the new dual-stage status contract without schema-breaking migrations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TaskStageStatus:
    submit_status: str
    callback_status: str
    final_status: str
    error_code: str | None = None


def extract_error_code(error_message: str | None) -> str | None:
    text = (error_message or "").strip()
    if not text:
        return None
    if text.startswith("ERR|"):
        parts = text.split("|", 2)
        if len(parts) >= 2 and parts[1].strip():
            return parts[1].strip()
    for sep in (" ", ":", "|"):
        if sep in text:
            token = text.split(sep, 1)[0].strip()
            if token and token.replace("_", "").isalnum() and token.upper() == token:
                return token
    return None


def derive_ability_task_status(
    *,
    status: str | None,
    started_at: Any = None,
    finished_at: Any = None,
    error_message: str | None = None,
) -> TaskStageStatus:
    normalized = str(status or "").strip().lower()
    error_code = extract_error_code(error_message)
    if normalized in {"queued", "pending"}:
        return TaskStageStatus(
            submit_status="pending",
            callback_status="waiting",
            final_status="pending",
            error_code=error_code,
        )
    if normalized in {"running", "processing", "submitted"}:
        return TaskStageStatus(
            submit_status="submitted",
            callback_status="running",
            final_status="running",
            error_code=error_code,
        )
    if normalized in {"succeeded", "success", "completed"}:
        return TaskStageStatus(
            submit_status="submitted",
            callback_status="success",
            final_status="success",
            error_code=error_code,
        )
    if normalized in {"cancelled", "canceled", "stopped"}:
        return TaskStageStatus(
            submit_status="submitted" if started_at else "submit_failed",
            callback_status="failed",
            final_status="canceled",
            error_code=error_code,
        )
    if normalized in {"failed", "error", "rejected"}:
        submit_status = "submitted" if started_at or finished_at else "submit_failed"
        return TaskStageStatus(
            submit_status=submit_status,
            callback_status="failed",
            final_status="failed",
            error_code=error_code,
        )
    return TaskStageStatus(
        submit_status="pending",
        callback_status="waiting",
        final_status="pending",
        error_code=error_code,
    )


def derive_ability_log_status(
    *,
    log_status: str | None,
    callback_status: str | None,
    callback_http_status: int | None = None,
    callback_error: str | None = None,
    callback_configured: bool | None = None,
    error_message: str | None = None,
) -> TaskStageStatus:
    raw_log = str(log_status or "").strip().lower()
    raw_callback = str(callback_status or "").strip().lower()
    error_code = extract_error_code(error_message) or extract_error_code(callback_error)
    callback_failed = (
        raw_callback in {"failed", "error", "timeout", "rejected"}
        or bool(callback_error)
        or (isinstance(callback_http_status, int) and callback_http_status >= 400)
    )
    callback_success = raw_callback in {"success", "succeeded", "completed", "ok"} or (
        isinstance(callback_http_status, int) and callback_http_status < 400 and raw_callback in {"", "success"}
    )
    callback_running = raw_callback in {"running", "processing", "pending", "queued"}

    if raw_log in {"failed", "error"}:
        return TaskStageStatus(
            submit_status="submit_failed",
            callback_status="failed" if callback_failed else "waiting",
            final_status="failed",
            error_code=error_code,
        )

    submit_status = "submitted" if raw_log in {"success", "succeeded"} else "submitting"
    if callback_configured is False:
        callback_stage = "not_configured"
        final = "success" if raw_log in {"success", "succeeded"} else "running"
        return TaskStageStatus(
            submit_status=submit_status,
            callback_status=callback_stage,
            final_status=final,
            error_code=error_code,
        )

    if callback_failed:
        return TaskStageStatus(
            submit_status=submit_status,
            callback_status="failed",
            final_status="failed",
            error_code=error_code,
        )
    if callback_success:
        return TaskStageStatus(
            submit_status=submit_status,
            callback_status="success",
            final_status="success",
            error_code=error_code,
        )
    if callback_running:
        return TaskStageStatus(
            submit_status=submit_status,
            callback_status="running",
            final_status="running",
            error_code=error_code,
        )
    if callback_configured:
        return TaskStageStatus(
            submit_status=submit_status,
            callback_status="waiting",
            final_status="running" if raw_log in {"success", "succeeded"} else "pending",
            error_code=error_code,
        )
    return TaskStageStatus(
        submit_status=submit_status,
        callback_status="waiting",
        final_status="running" if raw_log in {"success", "succeeded"} else "pending",
        error_code=error_code,
    )


def derive_eval_run_status(
    *,
    status: str | None,
    podi_task_id: str | None = None,
    error_message: str | None = None,
    has_result: bool = False,
) -> TaskStageStatus:
    normalized = str(status or "").strip().lower()
    error_code = extract_error_code(error_message)
    submitted = bool(podi_task_id)

    if normalized in {"queued", "pending"}:
        return TaskStageStatus(
            submit_status="pending",
            callback_status="waiting",
            final_status="pending",
            error_code=error_code,
        )
    if normalized in {"running", "processing"}:
        return TaskStageStatus(
            submit_status="submitted" if submitted else "submitting",
            callback_status="running",
            final_status="running",
            error_code=error_code,
        )
    if normalized in {"succeeded", "success", "completed"}:
        return TaskStageStatus(
            submit_status="submitted" if submitted else "submitting",
            callback_status="success" if has_result else "running",
            final_status="success" if has_result else "running",
            error_code=error_code,
        )
    if normalized in {"failed", "error", "timeout"}:
        return TaskStageStatus(
            submit_status="submitted" if submitted else "submit_failed",
            callback_status="failed",
            final_status="failed",
            error_code=error_code,
        )
    return TaskStageStatus(
        submit_status="pending",
        callback_status="waiting",
        final_status="pending",
        error_code=error_code,
    )


def derive_agent_task_status(
    *,
    status: str | None,
    pushed_at: Any = None,
    started_at: Any = None,
    finished_at: Any = None,
    error_message: str | None = None,
) -> TaskStageStatus:
    normalized = str(status or "").strip().lower()
    error_code = extract_error_code(error_message)
    if normalized == "pending":
        if pushed_at:
            return TaskStageStatus(
                submit_status="submit_failed",
                callback_status="waiting",
                final_status="pending",
                error_code=error_code,
            )
        return TaskStageStatus(
            submit_status="pending",
            callback_status="waiting",
            final_status="pending",
            error_code=error_code,
        )
    if normalized == "running":
        return TaskStageStatus(
            submit_status="submitted",
            callback_status="running",
            final_status="running",
            error_code=error_code,
        )
    if normalized == "success":
        return TaskStageStatus(
            submit_status="submitted",
            callback_status="success",
            final_status="success",
            error_code=error_code,
        )
    if normalized in {"failed", "rejected"}:
        submit_status = "submitted" if started_at or finished_at else "submit_failed"
        final = "failed" if normalized == "failed" else "canceled"
        return TaskStageStatus(
            submit_status=submit_status,
            callback_status="failed",
            final_status=final,
            error_code=error_code,
        )
    return TaskStageStatus(
        submit_status="pending",
        callback_status="waiting",
        final_status="pending",
        error_code=error_code,
    )
