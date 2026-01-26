"""Encode/decode external taskId strings.

We keep DB primary keys as the original hex id (uuid4().hex), but we can expose a
more "parseable" taskId to clients without breaking existing integrations:

  t1.<provider>.<executorId>.<hexTaskId>

Rules:
- decode_task_id() accepts both old hex ids and the new format and always returns the DB id.
- encode_task_id() is best-effort and falls back to the raw id if inputs are missing.
"""

from __future__ import annotations

import re
from typing import Any


_HEX32_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


def decode_task_id(value: Any) -> str | None:
    """Return DB task id (hex) from either old/new external taskId strings."""

    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if _HEX32_RE.match(s):
        return s.lower()

    # t1.<provider>.<executorId>.<hex>
    if s.startswith("t1."):
        parts = s.split(".")
        if len(parts) >= 4:
            tail = parts[-1].strip()
            if _HEX32_RE.match(tail):
                return tail.lower()
    return s


def encode_task_id(*, task_id: str, provider: str | None, executor_id: str | None) -> str:
    """Build an external parseable taskId.

    If task_id isn't a uuid hex, still return a tagged string so downstream can route.
    """

    raw = (task_id or "").strip()
    if not raw:
        return ""
    prov = (provider or "unknown").strip().lower() or "unknown"
    ex = (executor_id or "auto").strip() or "auto"
    # Keep format dot-safe; executor ids are usually underscore-based.
    prov = prov.replace(".", "_")
    ex = ex.replace(".", "_")
    return f"t1.{prov}.{ex}.{raw}"

