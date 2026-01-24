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
import sys
from pathlib import Path

from sqlalchemy import func, select

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.db import get_session
from app.models.eval import EvalAnnotation, EvalDatasetItem, EvalRun, EvalWorkflowVersion


def _count(session, model) -> int:
    return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge PODI test/eval data from DB.")
    parser.add_argument("--yes", action="store_true", help="Actually delete rows (required).")
    parser.add_argument("--dry-run", action="store_true", help="Print counts only; do not delete.")
    parser.add_argument(
        "--workflow-id",
        dest="workflow_id",
        default=None,
        help="Only delete eval runs/annotations for this Coze workflow_id (keeps other runs).",
    )
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
        target_workflow_version_ids: list[str] = []
        if args.workflow_id:
            wf_id = str(args.workflow_id).strip()
            target_workflow_version_ids = (
                session.execute(select(EvalWorkflowVersion.id).where(EvalWorkflowVersion.workflow_id == wf_id))
                .scalars()
                .all()
            )
            if not target_workflow_version_ids:
                print(f"No eval_workflow_version rows found for workflow_id={wf_id}")
                return 0

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
        if args.workflow_id:
            run_count = int(
                session.execute(
                    select(func.count()).select_from(EvalRun).where(EvalRun.workflow_version_id.in_(target_workflow_version_ids))
                ).scalar_one()
            )
            ann_count = int(
                session.execute(
                    select(func.count())
                    .select_from(EvalAnnotation)
                    .where(EvalAnnotation.run_id.in_(select(EvalRun.id).where(EvalRun.workflow_version_id.in_(target_workflow_version_ids))))
                ).scalar_one()
            )
            print(f"\nTarget (workflow_id={args.workflow_id}) counts:")
            print(f"- eval_run: {run_count}")
            print(f"- eval_annotation: {ann_count}")

        if args.dry_run:
            return 0

        if not args.yes:
            print("\nRefusing to delete without --yes.")
            return 2

        deleted = {}

        # Delete children first.
        if args.workflow_id:
            # Restrict to the selected workflow's runs.
            run_ids = (
                session.execute(
                    select(EvalRun.id).where(EvalRun.workflow_version_id.in_(target_workflow_version_ids))
                )
                .scalars()
                .all()
            )
            if run_ids:
                deleted["eval_annotation"] = (
                    session.query(EvalAnnotation).filter(EvalAnnotation.run_id.in_(run_ids)).delete(synchronize_session=False)
                )
            else:
                deleted["eval_annotation"] = 0
            deleted["eval_run"] = (
                session.query(EvalRun).filter(EvalRun.workflow_version_id.in_(target_workflow_version_ids)).delete(synchronize_session=False)
            )
        else:
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
