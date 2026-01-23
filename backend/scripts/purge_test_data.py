"""Purge test data for a clean evaluation run.

This only touches DB rows (does not delete OSS objects).

Usage:
  cd backend
  python3 scripts/purge_test_data.py --dry-run
  python3 scripts/purge_test_data.py --yes
  python3 scripts/purge_test_data.py --yes --include-datasets
  python3 scripts/purge_test_data.py --yes --include-ability-logs --include-ability-tasks
"""

from __future__ import annotations

import argparse

from sqlalchemy import func, select

from app.core.db import get_session
from app.models.eval import EvalAnnotation, EvalDatasetItem, EvalRun, EvalWorkflowVersion


def _count(session, model) -> int:
    return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge PODI test/eval data from DB.")
    parser.add_argument("--yes", action="store_true", help="Actually delete rows (required).")
    parser.add_argument("--dry-run", action="store_true", help="Print counts only; do not delete.")
    parser.add_argument(
        "--include-datasets",
        action="store_true",
        help="Also delete eval dataset items (keeps workflow versions).",
    )
    parser.add_argument(
        "--include-workflows",
        action="store_true",
        help="Also delete eval workflow versions (DANGEROUS; usually you want to keep these).",
    )
    parser.add_argument(
        "--include-ability-logs",
        action="store_true",
        help="Also delete ability invocation logs (admin/tests + unified invoke logs).",
    )
    parser.add_argument(
        "--include-ability-tasks",
        action="store_true",
        help="Also delete ability task rows (will remove async task history).",
    )
    args = parser.parse_args()

    with get_session() as session:
        counts = {
            "eval_workflow_version": _count(session, EvalWorkflowVersion),
            "eval_dataset_item": _count(session, EvalDatasetItem),
            "eval_run": _count(session, EvalRun),
            "eval_annotation": _count(session, EvalAnnotation),
        }

        # Optional tables live in other modules; import lazily to avoid side effects.
        AbilityInvocationLog = None
        AbilityTask = None
        if args.include_ability_logs:
            from app.models.integration import AbilityInvocationLog  # type: ignore
            counts["ability_invocation_logs"] = _count(session, AbilityInvocationLog)
        if args.include_ability_tasks:
            from app.models.integration import AbilityTask  # type: ignore
            counts["ability_tasks"] = _count(session, AbilityTask)

        print("Current row counts:")
        for k, v in counts.items():
            print(f"- {k}: {v}")

        if args.dry_run:
            return 0

        if not args.yes:
            print("\nRefusing to delete without --yes.")
            return 2

        deleted = {}

        # Delete children first.
        deleted["eval_annotation"] = session.query(EvalAnnotation).delete(synchronize_session=False)
        deleted["eval_run"] = session.query(EvalRun).delete(synchronize_session=False)

        if args.include_datasets:
            deleted["eval_dataset_item"] = session.query(EvalDatasetItem).delete(synchronize_session=False)

        if args.include_workflows:
            deleted["eval_workflow_version"] = session.query(EvalWorkflowVersion).delete(synchronize_session=False)

        if args.include_ability_logs:
            # Imported above if requested.
            deleted["ability_invocation_logs"] = session.query(AbilityInvocationLog).delete(synchronize_session=False)  # type: ignore

        if args.include_ability_tasks:
            deleted["ability_tasks"] = session.query(AbilityTask).delete(synchronize_session=False)  # type: ignore

        session.commit()

        print("\nDeleted rows:")
        for k, v in deleted.items():
            print(f"- {k}: {int(v)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
