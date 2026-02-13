"""Backfill KIE failure reasons into ability logs / tasks.

Usage:
  python3 backend/scripts/backfill_kie_error_messages.py --apply
  python3 backend/scripts/backfill_kie_error_messages.py --limit 200 --apply

Defaults to dry-run (no DB writes) unless --apply is provided.
"""

from __future__ import annotations

import argparse
from typing import Any

from sqlalchemy import or_, select

from app.core.db import get_session
from app.models.integration import AbilityInvocationLog, AbilityTask
from app.services.ability_task_service import AbilityTaskService


def _should_backfill_error(message: str | None) -> bool:
    if message is None:
        return True
    normalized = str(message).strip().lower()
    if normalized in {"", "kie_task_failed", "200 success", "200"}:
        return True
    if normalized.startswith("200 ") and "success" in normalized:
        return True
    return False


def _extract_message(payload: dict[str, Any] | None) -> str | None:
    return AbilityTaskService._extract_kie_error_message(payload)


def backfill(*, apply: bool, limit: int | None) -> None:
    updated_logs = 0
    updated_tasks = 0
    scanned_logs = 0
    scanned_tasks = 0

    with get_session() as session:
        log_stmt = select(AbilityInvocationLog).where(
            AbilityInvocationLog.ability_provider == "kie",
            AbilityInvocationLog.status == "failed",
            or_(
                AbilityInvocationLog.error_message.is_(None),
                AbilityInvocationLog.error_message == "",
                AbilityInvocationLog.error_message == "KIE_TASK_FAILED",
                AbilityInvocationLog.error_message == "200 success",
                AbilityInvocationLog.error_message == "200",
            ),
        )
        if limit:
            log_stmt = log_stmt.limit(limit)
        logs = session.execute(log_stmt).scalars().all()

        for log in logs:
            scanned_logs += 1
            payload = log.response_payload or {}
            if not isinstance(payload, dict):
                continue
            message = _extract_message(payload)
            if not message or not _should_backfill_error(log.error_message):
                continue
            if apply:
                log.error_message = message
                session.add(log)
                updated_logs += 1

        task_stmt = select(AbilityTask).where(
            AbilityTask.ability_provider == "kie",
            AbilityTask.status == "failed",
            or_(
                AbilityTask.error_message.is_(None),
                AbilityTask.error_message == "",
                AbilityTask.error_message == "KIE_TASK_FAILED",
                AbilityTask.error_message == "200 success",
                AbilityTask.error_message == "200",
            ),
        )
        if limit:
            task_stmt = task_stmt.limit(limit)
        tasks = session.execute(task_stmt).scalars().all()

        for task in tasks:
            scanned_tasks += 1
            payload = task.result_payload or {}
            if not isinstance(payload, dict):
                continue
            message = _extract_message(payload)
            if not message or not _should_backfill_error(task.error_message):
                continue
            if apply:
                task.error_message = message
                session.add(task)
                updated_tasks += 1

        if apply and (updated_logs or updated_tasks):
            session.commit()

    print(
        f"scanned_logs={scanned_logs} updated_logs={updated_logs} "
        f"scanned_tasks={scanned_tasks} updated_tasks={updated_tasks} apply={apply}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill KIE error messages.")
    parser.add_argument("--apply", action="store_true", help="Write updates to DB.")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows per table.")
    args = parser.parse_args()
    backfill(apply=bool(args.apply), limit=args.limit)


if __name__ == "__main__":
    main()
