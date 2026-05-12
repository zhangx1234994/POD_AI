"""Create or rotate a business API key.

Run from `backend/`:

    python scripts/create_business_api_key.py --name "业务方测试 Key" --tenant-id partner-a

The generated key is printed once. Do not commit the output.
"""

from __future__ import annotations

import argparse
import json
import secrets
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.core.db import get_session
from app.models.integration import ApiKey


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _metadata(*, tenant_id: str | None, client_id: str | None, allowed_business_keys: list[str]) -> dict[str, Any]:
    return {
        "tenantId": tenant_id,
        "clientId": client_id,
        "allowedBusinessKeys": allowed_business_keys,
        "createdBy": "backend/scripts/create_business_api_key.py",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or rotate a PODI business API key.")
    parser.add_argument("--id", default="", help="Stable key id. Defaults to a generated uuid.")
    parser.add_argument("--name", required=True, help="Display name shown in admin.")
    parser.add_argument("--tenant-id", default="", help="Business tenant id.")
    parser.add_argument("--client-id", default="", help="Business client id.")
    parser.add_argument(
        "--allowed-business-key",
        action="append",
        default=None,
        help="Allowed business key. Can be repeated. Defaults to fission.",
    )
    parser.add_argument("--expire-at", default="", help="Optional ISO datetime, e.g. 2026-06-30T23:59:59.")
    parser.add_argument("--key", default="", help="Optional explicit key. If omitted, a new key is generated.")
    parser.add_argument("--rotate", action="store_true", help="If id exists, replace its key and metadata.")
    args = parser.parse_args()

    key_id = args.id.strip() or uuid4().hex
    allowed = [item.strip() for item in (args.allowed_business_key or ["fission"]) if item and item.strip()]
    api_key_value = args.key.strip() or f"podi_biz_{secrets.token_urlsafe(32)}"
    now = datetime.utcnow()

    with get_session() as session:
        existing = session.get(ApiKey, key_id)
        if existing and existing.provider != "business_api":
            raise SystemExit(f"Key id exists with different provider: {existing.provider}")
        if existing and not args.rotate:
            output = {
                "created": False,
                "id": existing.id,
                "name": existing.name,
                "status": existing.status,
                "message": "key already exists; rerun with --rotate to replace and print a new key",
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0

        row = existing or ApiKey(id=key_id, provider="business_api", created_at=now)
        row.name = args.name
        row.key = api_key_value
        row.status = "active"
        row.expire_at = _parse_dt(args.expire_at)
        row.extra_metadata = _metadata(
            tenant_id=args.tenant_id.strip() or None,
            client_id=args.client_id.strip() or None,
            allowed_business_keys=allowed,
        )
        row.updated_at = now
        session.add(row)
        session.commit()

    output = {
        "created": existing is None,
        "rotated": bool(existing),
        "id": key_id,
        "name": args.name,
        "key": api_key_value,
        "allowedBusinessKeys": allowed,
        "tenantId": args.tenant_id.strip() or None,
        "clientId": args.client_id.strip() or None,
        "expireAt": args.expire_at.strip() or None,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
