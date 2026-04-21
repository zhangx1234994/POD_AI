"""Helpers for deprecated/replacement ability metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.ability_governance import resolve_ability_governance

_VALID_RETIREMENT_MODES = ("hide_public", "internal_only", "delete_candidate")


def resolve_ability_deprecation(*, status: str | None, metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    base = metadata if isinstance(metadata, dict) else {}
    payload = base.get("deprecation") if isinstance(base.get("deprecation"), dict) else {}
    governance = resolve_ability_governance(status=status, metadata=base)
    is_deprecated = str(governance.get("release_status") or "").strip().lower() == "deprecated"

    replacement_ability_id = str(payload.get("replacement_ability_id") or "").strip() or None
    replacement_capability_key = str(payload.get("replacement_capability_key") or "").strip() or None
    replacement_display_name = str(payload.get("replacement_display_name") or "").strip() or None
    reason = str(payload.get("reason") or "").strip() or None
    retirement_mode = str(payload.get("retirement_mode") or "").strip().lower() or None
    if retirement_mode not in _VALID_RETIREMENT_MODES:
        retirement_mode = "hide_public" if is_deprecated else None

    if not is_deprecated and not any([replacement_ability_id, replacement_capability_key, replacement_display_name, reason, retirement_mode]):
        return None

    return {
        "is_deprecated": is_deprecated,
        "replacement_ability_id": replacement_ability_id,
        "replacement_capability_key": replacement_capability_key,
        "replacement_display_name": replacement_display_name,
        "reason": reason,
        "retirement_mode": retirement_mode,
    }


def enrich_metadata_with_deprecation(
    metadata: dict[str, Any] | None,
    *,
    status: str | None,
    deprecation_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = deepcopy(metadata) if isinstance(metadata, dict) else {}
    if deprecation_override is not None:
        payload = {
            "replacement_ability_id": str(deprecation_override.get("replacement_ability_id") or "").strip() or None,
            "replacement_capability_key": str(deprecation_override.get("replacement_capability_key") or "").strip() or None,
            "replacement_display_name": str(deprecation_override.get("replacement_display_name") or "").strip() or None,
            "reason": str(deprecation_override.get("reason") or "").strip() or None,
            "retirement_mode": str(deprecation_override.get("retirement_mode") or "").strip().lower() or None,
        }
        payload = {key: value for key, value in payload.items() if value not in (None, "")}
        if payload:
            base["deprecation"] = payload
        else:
            base.pop("deprecation", None)
    resolved = resolve_ability_deprecation(status=status, metadata=base)
    if resolved:
        base["deprecation"] = {key: value for key, value in resolved.items() if key != "is_deprecated" and value not in (None, "")}
    else:
        base.pop("deprecation", None)
    return base
