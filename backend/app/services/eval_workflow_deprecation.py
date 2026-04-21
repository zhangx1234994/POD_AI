"""Helpers for eval workflow deprecation metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_VALID_RETIREMENT_MODES = {
    "hide_public",
    "admin_only",
    "delete_candidate",
}


def resolve_eval_workflow_deprecation(
    *,
    status: str | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    base = metadata if isinstance(metadata, dict) else {}
    payload = base.get("deprecation") if isinstance(base.get("deprecation"), dict) else {}
    if not payload:
        return None
    is_deprecated = str(status or "").strip().lower() == "inactive" or bool(payload.get("is_deprecated", True))
    if not is_deprecated:
        return None
    retirement_mode = str(payload.get("retirement_mode") or "hide_public").strip().lower()
    if retirement_mode not in _VALID_RETIREMENT_MODES:
        retirement_mode = "hide_public"
    return {
        "is_deprecated": True,
        "replacement_workflow_id": str(payload.get("replacement_workflow_id") or "").strip() or None,
        "replacement_display_name": str(payload.get("replacement_display_name") or "").strip() or None,
        "reason": str(payload.get("reason") or "").strip() or None,
        "retirement_mode": retirement_mode,
    }


def enrich_metadata_with_eval_workflow_deprecation(
    metadata: dict[str, Any] | None,
    *,
    status: str | None,
    deprecation_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = deepcopy(metadata) if isinstance(metadata, dict) else {}
    if deprecation_override is not None:
        payload = {
            "is_deprecated": bool(deprecation_override.get("is_deprecated", True)),
            "replacement_workflow_id": str(
                deprecation_override.get("replacement_workflow_id") or ""
            ).strip()
            or None,
            "replacement_display_name": str(
                deprecation_override.get("replacement_display_name") or ""
            ).strip()
            or None,
            "reason": str(deprecation_override.get("reason") or "").strip() or None,
            "retirement_mode": str(deprecation_override.get("retirement_mode") or "").strip() or None,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        if payload:
            base["deprecation"] = payload
        else:
            base.pop("deprecation", None)

    resolved = resolve_eval_workflow_deprecation(status=status, metadata=base)
    if resolved:
        base["deprecation"] = resolved
    else:
        base.pop("deprecation", None)
    return base
