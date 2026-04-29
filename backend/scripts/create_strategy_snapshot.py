#!/usr/bin/env python3
"""Create a strategy metrics snapshot or weekly report.

Run on the backend host:

    backend/.venv/bin/python backend/scripts/create_strategy_snapshot.py
    backend/.venv/bin/python backend/scripts/create_strategy_snapshot.py --weekly-report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _dump(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create PODI strategy snapshot / weekly report.")
    parser.add_argument("--window-hours", type=int, default=168, help="Metrics window. Default: 168 hours.")
    parser.add_argument("--note", default="", help="Optional note stored with the snapshot/report.")
    parser.add_argument("--weekly-report", action="store_true", help="Create weekly report markdown and records.")
    parser.add_argument("--send", action="store_true", help="Ask weekly report route to send webhook if configured.")
    parser.add_argument("--webhook-format", default="generic", help="Webhook format label.")
    args = parser.parse_args()

    from app.routers import admin_dashboard  # noqa: PLC0415
    from app.schemas import admin_dashboard as schemas  # noqa: PLC0415

    if args.weekly_report:
        response = admin_dashboard.run_weekly_report(
            schemas.WeeklyReportRunRequest(
                windowHours=args.window_hours,
                note=args.note or "weekly-auto",
                send=args.send,
                webhookFormat=args.webhook_format,
            )
        )
        _dump(response.model_dump(by_alias=True, mode="json"))
        return 0

    snapshot = admin_dashboard._create_strategy_snapshot(  # noqa: SLF001 - intentional script reuse.
        window_hours=args.window_hours,
        note=args.note or "manual",
    )
    admin_dashboard._append_record(  # noqa: SLF001 - intentional script reuse.
        "strategy_snapshots.json",
        snapshot.model_dump(by_alias=True, mode="json"),
        keep=100,
    )
    _dump(snapshot.model_dump(by_alias=True, mode="json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
