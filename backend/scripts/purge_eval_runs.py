#!/usr/bin/env python3
"""Purge eval runs (and annotations) from the database.

Use this to reset the evaluation UI history when starting a fresh regression cycle.
This targets ONLY eval tables: `eval_run` and `eval_annotation`.

Examples:
  python3 backend/scripts/purge_eval_runs.py --dry-run
  python3 backend/scripts/purge_eval_runs.py --all --yes
  python3 backend/scripts/purge_eval_runs.py --category "四方/两方连续图类" --yes
  python3 backend/scripts/purge_eval_runs.py --workflow-id 7598563505054154752 --yes
"""

from __future__ import annotations

import argparse
from datetime import datetime
import pathlib
import sys

from sqlalchemy import delete, select

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import get_session
from app.models.eval import EvalAnnotation, EvalRun, EvalWorkflowVersion


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="Delete ALL eval runs (dangerous).")
    ap.add_argument("--category", type=str, default=None, help="Only delete runs under this category.")
    ap.add_argument("--workflow-id", type=str, default=None, help="Only delete runs for this Coze workflow_id.")
    ap.add_argument("--dry-run", action="store_true", help="Print counts only; do not delete.")
    ap.add_argument("--yes", action="store_true", help="Actually perform deletion.")
    args = ap.parse_args()

    if not args.all and not args.category and not args.workflow_id:
        args.dry_run = True

    if not args.dry_run and not args.yes:
        print("Refusing to delete without --yes. Use --dry-run to preview.")
        return 2

    with get_session() as session:
        wf_ids = None
        if args.workflow_id:
            rows = session.execute(
                select(EvalWorkflowVersion.id).where(EvalWorkflowVersion.workflow_id == args.workflow_id)
            ).all()
            wf_ids = [r[0] for r in rows]
            if not wf_ids:
                print(f"No eval workflow versions found for workflow_id={args.workflow_id}. Nothing to delete.")
                return 0

        if args.category:
            rows = session.execute(
                select(EvalWorkflowVersion.id).where(EvalWorkflowVersion.category == args.category)
            ).all()
            wf_ids = [r[0] for r in rows]
            if not wf_ids:
                print(f"No eval workflow versions found for category={args.category}. Nothing to delete.")
                return 0

        # Find target run ids.
        stmt = select(EvalRun.id)
        if not args.all and wf_ids is not None:
            stmt = stmt.where(EvalRun.workflow_version_id.in_(wf_ids))
        run_ids = [r[0] for r in session.execute(stmt).all()]

        if not run_ids:
            print("No eval runs matched. Nothing to delete.")
            return 0

        ann_count = session.execute(select(EvalAnnotation.id).where(EvalAnnotation.run_id.in_(run_ids))).all()
        print(
            f"Matched runs={len(run_ids)} annotations={len(ann_count)} (dry_run={args.dry_run}) @ {datetime.utcnow().isoformat()}Z"
        )

        if args.dry_run:
            print("Dry-run only. Re-run with --yes to delete.")
            return 0

        # Delete annotations first (for DBs without ON DELETE CASCADE / to be explicit).
        session.execute(delete(EvalAnnotation).where(EvalAnnotation.run_id.in_(run_ids)))
        session.execute(delete(EvalRun).where(EvalRun.id.in_(run_ids)))
        session.commit()
        print("Deleted.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
