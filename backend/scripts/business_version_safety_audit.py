#!/usr/bin/env python3
"""Check that core business entries have an active rollback target."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_rollback_drill import _build_drill_report  # noqa: E402


DEFAULT_BUSINESS_KEYS = ("fission", "outpaint")


def _parse_business_keys(raw: str | None) -> list[str]:
    values = [item.strip() for item in str(raw or "").split(",")]
    return [item for item in values if item]


def _is_report_safe(report: dict[str, Any]) -> bool:
    return bool(report.get("currentDefault") and report.get("rollbackTarget") and report.get("ok"))


def _build_safety_report(business_keys: list[str]) -> dict[str, Any]:
    items = [
        _build_drill_report(business_key=business_key, target_capability_id=None)
        for business_key in business_keys
    ]
    return {
        "ok": all(_is_report_safe(item) for item in items),
        "businessKeys": business_keys,
        "items": items,
    }


def _print_report(report: dict[str, Any]) -> None:
    print(f"业务版本安全垫检查：{'通过' if report.get('ok') else '失败'}")
    for item in report.get("items") or []:
        current = item.get("currentDefault") or {}
        target = item.get("rollbackTarget") or {}
        safe = _is_report_safe(item)
        print(f"- {item.get('businessKey')}：{'可回滚' if safe else '不可回滚'}")
        print(f"  当前默认：{current.get('displayName') or '-'} / {current.get('version') or '-'} / {current.get('id') or '-'}")
        print(f"  保底目标：{target.get('displayName') or '-'} / {target.get('version') or '-'} / {target.get('id') or '-'}")
    if not report.get("ok"):
        print("结论：上线前必须为每个核心业务保留 active 默认版本和至少一个 active 非默认版本。")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit business version rollback safety.")
    parser.add_argument(
        "--business-keys",
        default=",".join(DEFAULT_BUSINESS_KEYS),
        help="Comma-separated business keys. Default: fission,outpaint.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON.")
    args = parser.parse_args()

    business_keys = _parse_business_keys(args.business_keys)
    if not business_keys:
        print("business keys are required", file=sys.stderr)
        return 2

    report = _build_safety_report(business_keys)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        _print_report(report)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
