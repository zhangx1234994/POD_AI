#!/usr/bin/env python3
"""Dry-run or execute business default-version rollback.

Default mode is read-only. Use --apply --yes only when an actual rollback is
intended.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_backend() -> SimpleNamespace:
    from fastapi import HTTPException
    from sqlalchemy import select

    from app.core.db import get_session
    from app.models.integration import BusinessCapability
    from app.schemas.business import BusinessCapabilityRollbackRequest
    from app.services.ability_seed import ensure_default_abilities
    from app.services.business_runs import get_business_run_service
    from app.services.business_seed import ensure_default_business_capabilities

    return SimpleNamespace(
        HTTPException=HTTPException,
        BusinessCapability=BusinessCapability,
        BusinessCapabilityRollbackRequest=BusinessCapabilityRollbackRequest,
        ensure_default_abilities=ensure_default_abilities,
        ensure_default_business_capabilities=ensure_default_business_capabilities,
        get_business_run_service=get_business_run_service,
        get_session=get_session,
        select=select,
    )


def _release_events(metadata: Any) -> list[dict[str, Any]]:
    if not isinstance(metadata, dict):
        return []
    events = metadata.get("releaseEvents")
    if not isinstance(events, list):
        return []
    return [event for event in events if isinstance(event, dict)]


def _previous_default_ids(current_default: Any | None) -> list[str]:
    ids: list[str] = []
    if not current_default:
        return ids
    for event in reversed(_release_events(current_default.extra_metadata)):
        previous_id = str(event.get("previousDefaultCapabilityId") or "").strip()
        if previous_id and previous_id != current_default.id and previous_id not in ids:
            ids.append(previous_id)
    return ids


def _capability_summary(row: Any | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": row.id,
        "businessKey": row.business_key,
        "version": row.version,
        "displayName": row.display_name,
        "status": row.status,
        "isDefault": row.is_default,
        "releaseTime": row.release_time.isoformat() if row.release_time else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _resolve_rollback_target(
    session,
    *,
    business_key: str,
    current_default: Any | None,
    target_capability_id: str | None,
    backend: SimpleNamespace,
) -> tuple[Any | None, str]:
    explicit_id = str(target_capability_id or "").strip()
    if explicit_id:
        target = session.get(backend.BusinessCapability, explicit_id)
        if target and target.business_key == business_key:
            return target, "explicit"
        return None, "explicit_not_found"

    for previous_id in _previous_default_ids(current_default):
        previous = session.get(backend.BusinessCapability, previous_id)
        if previous and previous.business_key == business_key:
            return previous, "release_event"

    fallback = (
        session.execute(
            backend.select(backend.BusinessCapability)
            .where(
                backend.BusinessCapability.business_key == business_key,
                backend.BusinessCapability.status == "active",
                backend.BusinessCapability.is_default.is_(False),
            )
            .order_by(
                backend.BusinessCapability.release_time.desc(),
                backend.BusinessCapability.updated_at.desc(),
                backend.BusinessCapability.created_at.desc(),
            )
        )
        .scalars()
        .first()
    )
    return fallback, "active_fallback" if fallback else "not_found"


def _build_drill_report(
    *,
    business_key: str,
    target_capability_id: str | None,
) -> dict[str, Any]:
    backend = _load_backend()
    with backend.get_session() as session:
        backend.ensure_default_abilities(session)
        backend.ensure_default_business_capabilities(session)
        rows = (
            session.execute(
                backend.select(backend.BusinessCapability)
                .where(backend.BusinessCapability.business_key == business_key)
                .order_by(
                    backend.BusinessCapability.is_default.desc(),
                    backend.BusinessCapability.release_time.desc(),
                    backend.BusinessCapability.updated_at.desc(),
                    backend.BusinessCapability.created_at.desc(),
                )
            )
            .scalars()
            .all()
        )
        current_default = next((row for row in rows if row.is_default), None)
        target, selected_by = _resolve_rollback_target(
            session,
            business_key=business_key,
            current_default=current_default,
            target_capability_id=target_capability_id,
            backend=backend,
        )
        return {
            "checkedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "businessKey": business_key,
            "ok": target is not None,
            "mode": "dry_run",
            "selectedBy": selected_by,
            "currentDefault": _capability_summary(current_default),
            "rollbackTarget": _capability_summary(target),
            "versions": [_capability_summary(row) for row in rows],
            "releaseEvents": _release_events(current_default.extra_metadata if current_default else None)[-5:],
        }


def _print_report(report: dict[str, Any]) -> None:
    print(f"业务回滚演练：{report['businessKey']} | {'可回滚' if report['ok'] else '不可回滚'}")
    current = report.get("currentDefault") or {}
    target = report.get("rollbackTarget") or {}
    print(f"- 当前默认：{current.get('displayName') or '-'} / {current.get('version') or '-'} / {current.get('id') or '-'}")
    print(f"- 回滚目标：{target.get('displayName') or '-'} / {target.get('version') or '-'} / {target.get('id') or '-'}")
    print(f"- 目标来源：{report.get('selectedBy')}")
    print(f"- 版本数量：{len(report.get('versions') or [])}")
    if not report.get("ok"):
        print("- 结论：没有找到可回滚目标；上线前需要至少保留一个 active 非默认版本，或先做一次默认版本切换记录。")


def main() -> int:
    parser = argparse.ArgumentParser(description="Drill business default-version rollback.")
    parser.add_argument("--business-key", default="fission", help="Business key, for example fission or outpaint.")
    parser.add_argument("--target-capability-id", default="", help="Optional explicit rollback target capability id.")
    parser.add_argument("--apply", action="store_true", help="Actually perform rollback.")
    parser.add_argument("--yes", action="store_true", help="Required with --apply.")
    parser.add_argument("--note", default="rollback drill", help="Release event note when --apply is used.")
    parser.add_argument("--json", action="store_true", help="Print JSON.")
    args = parser.parse_args()

    business_key = str(args.business_key or "").strip()
    if not business_key:
        print("business key is required", file=sys.stderr)
        return 2

    if args.apply:
        if not args.yes:
            print("Refusing to apply rollback without --yes.", file=sys.stderr)
            return 2
        try:
            backend = _load_backend()
            result = backend.get_business_run_service().rollback_default(
                business_key,
                backend.BusinessCapabilityRollbackRequest(
                    targetCapabilityId=str(args.target_capability_id or "").strip() or None,
                    note=args.note,
                ),
            )
        except Exception as exc:
            detail = getattr(exc, "detail", repr(exc))
            payload = {"ok": False, "mode": "apply", "businessKey": business_key, "error": detail}
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"业务回滚执行失败：{detail}")
            return 2
        payload = {"ok": True, "mode": "apply", "businessKey": business_key, "result": result}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        else:
            print(f"业务回滚已执行：{result.get('display_name')} / {result.get('version')} / {result.get('id')}")
        return 0

    report = _build_drill_report(
        business_key=business_key,
        target_capability_id=str(args.target_capability_id or "").strip() or None,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        _print_report(report)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
