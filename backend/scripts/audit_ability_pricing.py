#!/usr/bin/env python3
"""Audit ability pricing completeness for release checks.

Usage:
  python3 backend/scripts/audit_ability_pricing.py
  python3 backend/scripts/audit_ability_pricing.py --provider kie --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, "backend")

from sqlalchemy import select

from app.core.db import get_session
from app.models.integration import Ability
from app.services.ability_seed import ensure_default_abilities


@dataclass
class PricingIssue:
    ability_id: str
    provider: str
    capability_key: str
    display_name: str
    issue: str


def _validate_pricing(metadata: dict[str, Any] | None) -> list[str]:
    if not isinstance(metadata, dict):
        return ["metadata_missing"]
    pricing = metadata.get("pricing")
    if not isinstance(pricing, dict):
        return ["pricing_missing"]
    issues: list[str] = []
    currency = pricing.get("currency")
    unit = pricing.get("unit")
    list_price = pricing.get("list_price")
    discount_price = pricing.get("discount_price")
    if not isinstance(currency, str) or not currency.strip():
        issues.append("currency_missing")
    if not isinstance(unit, str) or not unit.strip():
        issues.append("unit_missing")
    if list_price is None and discount_price is None:
        issues.append("price_missing")
    return issues


def run(provider: str | None) -> tuple[list[PricingIssue], int]:
    issues: list[PricingIssue] = []
    total = 0
    with get_session() as session:
        # Keep seed in sync before auditing to avoid false positives from stale rows.
        ensure_default_abilities(session)
        stmt = select(Ability).where(Ability.status == "active")
        if provider:
            stmt = stmt.where(Ability.provider == provider)
        rows = session.execute(stmt.order_by(Ability.provider.asc(), Ability.capability_key.asc())).scalars().all()
        total = len(rows)
        for row in rows:
            found = _validate_pricing(row.extra_metadata if isinstance(row.extra_metadata, dict) else None)
            for item in found:
                issues.append(
                    PricingIssue(
                        ability_id=row.id,
                        provider=row.provider,
                        capability_key=row.capability_key,
                        display_name=row.display_name or row.capability_key,
                        issue=item,
                    )
                )
    return issues, total


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ability pricing completeness.")
    parser.add_argument("--provider", default=None, help="Filter by provider, e.g. kie/comfyui/volcengine.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    issues, total = run(args.provider)
    summary = {
        "provider": args.provider or "all",
        "total_active_abilities": total,
        "issue_count": len(issues),
        "ok": len(issues) == 0,
    }

    if args.json:
        print(json.dumps({"summary": summary, "issues": [asdict(x) for x in issues]}, ensure_ascii=False, indent=2))
        return 0 if not issues else 2

    print("[ability-pricing-audit]")
    print(f"- provider: {summary['provider']}")
    print(f"- total_active_abilities: {summary['total_active_abilities']}")
    print(f"- issue_count: {summary['issue_count']}")
    if not issues:
        print("- result: OK")
        return 0

    print("- result: HAS_ISSUES")
    for item in issues:
        print(
            f"  - {item.provider}:{item.capability_key} "
            f"({item.ability_id}, {item.display_name}) -> {item.issue}"
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

