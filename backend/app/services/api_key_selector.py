"""API key selection + rotation helpers.

Design goals (internal platform):
- API keys are stored in DB (`api_keys`) and linked to executors via `executor_api_keys`.
- For internal integrations (Coze/workflows), callers should not need to provide keys.
- When a key is rate-limited, we can temporarily cool it down and fail over to another.

We keep vendor-specific key structures in `ApiKey.key` + `ApiKey.metadata`:
- volcengine/kie: `key` holds the API Key
- baidu: `key` holds apiKey, `metadata.secretKey` holds secretKey
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration import ApiKey, ExecutorApiKey


def _now_ts() -> int:
    return int(time.time())


def _parse_cooldown_until(metadata: dict[str, Any] | None) -> int | None:
    if not metadata:
        return None
    v = metadata.get("cooldown_until")
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    # Best-effort ISO8601 parsing (store as epoch to keep it simple).
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except Exception:
            return None
    return None


def is_usable(api_key: ApiKey) -> bool:
    if api_key.status != "active":
        return False
    if api_key.expire_at and api_key.expire_at <= datetime.now(timezone.utc).replace(tzinfo=None):
        return False
    cd = _parse_cooldown_until(api_key.extra_metadata)
    if cd and cd > _now_ts():
        return False
    return True


def pick_executor_api_key(
    session: Session,
    *,
    executor_id: str,
    provider: str,
    exclude_ids: set[str] | None = None,
) -> ApiKey | None:
    """Pick an API key bound to an executor, ordered by binding priority then usage.

    Returns None if no usable key is found.
    """

    exclude_ids = exclude_ids or set()
    stmt = (
        select(ApiKey, ExecutorApiKey)
        .join(ExecutorApiKey, ExecutorApiKey.api_key_id == ApiKey.id)
        .where(
            ExecutorApiKey.executor_id == executor_id,
            ApiKey.provider == provider,
        )
        .order_by(ExecutorApiKey.priority.asc(), ApiKey.usage_count.asc(), ApiKey.id.asc())
    )
    rows = session.execute(stmt).all()
    for api_key, _link in rows:
        if api_key.id in exclude_ids:
            continue
        if is_usable(api_key):
            return api_key
    return None


def pick_provider_api_key(
    session: Session,
    *,
    provider: str,
    exclude_ids: set[str] | None = None,
) -> ApiKey | None:
    """Pick any usable API key for a provider (global pool).

    This is the internal "it should just work" fallback when a key hasn't been
    explicitly bound to an executor yet.
    """

    exclude_ids = exclude_ids or set()
    stmt = (
        select(ApiKey)
        .where(ApiKey.provider == provider)
        .order_by(ApiKey.usage_count.asc(), ApiKey.id.asc())
    )
    for api_key in session.execute(stmt).scalars().all():
        if api_key.id in exclude_ids:
            continue
        if is_usable(api_key):
            return api_key
    return None


def mark_cooldown(
    session: Session,
    *,
    api_key: ApiKey,
    seconds: int,
    reason: str | None = None,
) -> None:
    meta = dict(api_key.extra_metadata or {})
    meta["cooldown_until"] = _now_ts() + max(1, int(seconds))
    if reason:
        meta["cooldown_reason"] = reason
    api_key.extra_metadata = meta
    session.add(api_key)
    session.commit()


def bump_usage(session: Session, *, api_key: ApiKey) -> None:
    api_key.usage_count = (api_key.usage_count or 0) + 1
    meta = dict(api_key.extra_metadata or {})
    meta["last_used_at"] = _now_ts()
    api_key.extra_metadata = meta
    session.add(api_key)
    session.commit()
