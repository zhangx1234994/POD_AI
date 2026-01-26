#!/usr/bin/env python3
"""Purge unfinished AbilityTask records (testing-only cleanup).

This removes AbilityTask rows that are stuck in non-terminal states (queued/running),
optionally filtered by provider. It also deletes matching AbilityInvocationLog rows
when they reference the purged task_id or are still `pending` for that provider.

Examples:
  python3 backend/scripts/purge_unfinished_ability_tasks.py --dry-run
  python3 backend/scripts/purge_unfinished_ability_tasks.py --provider comfyui --yes
  python3 backend/scripts/purge_unfinished_ability_tasks.py --yes
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections import Counter
from datetime import datetime

from sqlalchemy import delete, select

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import get_session  # noqa: E402
from app.models.integration import AbilityInvocationLog, AbilityTask  # noqa: E402


TERMINAL = {"succeeded", "failed", "completed", "cancelled", "canceled"}
UNFINISHED = {"queued", "running", "pending", "created"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=str, default=None, help="Only delete tasks for this provider (e.g. comfyui/kie).")
    ap.add_argument("--dry-run", action="store_true", help="Print counts only; do not delete.")
    ap.add_argument("--yes", action="store_true", help="Actually perform deletion.")
    args = ap.parse_args()

    if not args.dry_run and not args.yes:
        args.dry_run = True

    provider = (args.provider or "").strip().lower() or None

    with get_session() as session:
        stmt = select(AbilityTask).where(AbilityTask.status.in_(sorted(UNFINISHED)))
        if provider:
            stmt = stmt.where(AbilityTask.ability_provider == provider)
        tasks = session.execute(stmt).scalars().all()

        if not tasks:
            print("No unfinished ability_tasks matched. Nothing to do.")
            return 0

        by_provider = Counter((t.ability_provider or "unknown") for t in tasks)
        by_key = Counter(((t.ability_provider or "unknown"), (t.capability_key or "unknown")) for t in tasks)
        print(
            f"Matched ability_tasks={len(tasks)} (dry_run={args.dry_run}) @ {datetime.utcnow().isoformat()}Z"
        )
        print("By provider:")
        for k, v in by_provider.most_common():
            print(f"  {k}: {v}")
        print("Top capability keys:")
        for (prov, key), v in by_key.most_common(15):
            print(f"  {prov}:{key} {v}")

        if args.dry_run:
            print("Dry-run only. Re-run with --yes to delete.")
            return 0

        task_ids = [t.id for t in tasks if isinstance(t.id, str) and t.id]

        # Delete logs that point to these tasks.
        session.execute(delete(AbilityInvocationLog).where(AbilityInvocationLog.task_id.in_(task_ids)))

        # Also clear pending logs for this provider (optional; keeps admin UI clean in testing).
        if provider:
            session.execute(
                delete(AbilityInvocationLog).where(
                    AbilityInvocationLog.ability_provider == provider,
                    AbilityInvocationLog.status == "pending",
                )
            )

        session.execute(delete(AbilityTask).where(AbilityTask.id.in_(task_ids)))
        session.commit()
        print("Deleted.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

