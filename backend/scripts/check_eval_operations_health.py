#!/usr/bin/env python3
"""Check eval operational health from backend database.

Exit code:
- 0: healthy
- 1: warning
- 2: critical
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db import get_session  # noqa: E402
from app.services.eval_operations_health import build_eval_operations_health  # noqa: E402
from app.services.integration_test import integration_test_service  # noqa: E402


def _print_text(report: dict) -> None:
    print(f"评测运行健康：{report['status']}")
    print(
        "工作流："
        f"active={report['activeWorkflowCount']} / total={report['totalWorkflowCount']}；"
        f"总状态={report['statusCounts']}；"
        f"最近{report['recentHours']}小时={report['recentStatusCounts']}"
    )
    if not report["issues"]:
        print("未发现长期运行、提交卡住、成功无结果或近期失败。")
        return
    print("发现问题：")
    for issue in report["issues"]:
        print(f"- [{issue['severity']}] {issue['code']}：{issue['message']}")
    if report["staleRunning"]:
        print("长期未收口任务：")
        for item in report["staleRunning"][:10]:
            print(
                f"- {item['ageMinutes']}分钟 | {item.get('workflowName') or item.get('workflowId')} "
                f"| run={item['runId']} | task={item.get('podiTaskId') or '-'}"
            )
    if report["recentFailures"]:
        print(f"近期失败错误分布：{report['errorCounts']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check eval operational health.")
    parser.add_argument("--stale-minutes", type=int, default=30, help="queued/running over this age is stale.")
    parser.add_argument("--submit-grace-minutes", type=int, default=5, help="running without ids over this age is stalled.")
    parser.add_argument("--recent-hours", type=int, default=24, help="recent failure/output window.")
    parser.add_argument("--limit", type=int, default=20, help="max rows per issue group.")
    parser.add_argument("--json", action="store_true", help="print JSON.")
    args = parser.parse_args()

    try:
        comfyui_queue_summary = integration_test_service.get_comfyui_queue_summary()
    except Exception as exc:
        comfyui_queue_summary = {"error": "COMFYUI_QUEUE_HEALTH_UNAVAILABLE", "detail": str(exc)}

    with get_session() as session:
        report = build_eval_operations_health(
            session,
            stale_minutes=args.stale_minutes,
            submit_grace_minutes=args.submit_grace_minutes,
            recent_hours=args.recent_hours,
            limit=args.limit,
            comfyui_queue_summary=comfyui_queue_summary,
        )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, default=str, indent=2))
    else:
        _print_text(report)

    status = str(report.get("status") or "critical")
    if status == "healthy":
        return 0
    if status == "warning":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
