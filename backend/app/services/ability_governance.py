"""Helpers for normalized ability governance and business-facing status."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_VALID_SCOPES = ("internal", "admin", "eval", "coze", "client")
_SCOPE_LABELS = {
    "internal": "内部",
    "admin": "管理端",
    "eval": "测评端",
    "coze": "Coze",
    "client": "客户端",
}
_VALID_RELEASE_STATUSES = ("draft", "internal_ready", "eval_ready", "published", "deprecated")
_VALID_ROUTE_POLICIES = ("fixed", "queue_aware", "fallback_allowed")
_VALID_QUALITY_STATUSES = ("untested", "usable", "needs_optimization")


def _normalize_scope_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: list[str] = []
    for item in value:
        text = str(item or "").strip().lower()
        if text in _VALID_SCOPES and text not in seen:
            seen.append(text)
    return seen


def _extract_surface_scopes(metadata: dict[str, Any] | None) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    presentation = metadata.get("presentation")
    surfaces = presentation.get("surfaces") if isinstance(presentation, dict) else None
    if not isinstance(surfaces, dict):
        return []
    selected = []
    for scope in _VALID_SCOPES:
        if scope == "internal":
            continue
        if bool(surfaces.get(scope)):
            selected.append(scope)
    return selected


def _resolve_scopes(*, status: str | None, metadata: dict[str, Any] | None) -> list[str]:
    governance = metadata.get("governance") if isinstance(metadata, dict) and isinstance(metadata.get("governance"), dict) else {}
    scopes = _normalize_scope_list(governance.get("scopes"))
    if scopes:
        return scopes
    scopes = _extract_surface_scopes(metadata)
    if scopes:
        return scopes
    if (status or "").strip().lower() == "active":
        return ["admin"]
    return ["internal"]


def _resolve_release_status(*, status: str | None, metadata: dict[str, Any] | None, scopes: list[str]) -> str:
    governance = metadata.get("governance") if isinstance(metadata, dict) and isinstance(metadata.get("governance"), dict) else {}
    explicit = str(governance.get("release_status") or "").strip().lower()
    if explicit in _VALID_RELEASE_STATUSES:
        return explicit
    if (status or "").strip().lower() != "active":
        return "draft"
    if "client" in scopes or "coze" in scopes:
        return "published"
    if "eval" in scopes:
        return "eval_ready"
    return "internal_ready"


def _resolve_route_policy(*, metadata: dict[str, Any] | None) -> str:
    governance = metadata.get("governance") if isinstance(metadata, dict) and isinstance(metadata.get("governance"), dict) else {}
    explicit = str(governance.get("route_policy") or "").strip().lower()
    if explicit in _VALID_ROUTE_POLICIES:
        return explicit

    raw_policy = str((metadata or {}).get("routing_policy") or "").strip().lower()
    if raw_policy in {"queue", "queue_aware"}:
        return "queue_aware"
    if raw_policy in {"fallback", "fallback_allowed"}:
        return "fallback_allowed"

    allowed_executor_ids = (metadata or {}).get("allowed_executor_ids")
    if isinstance(allowed_executor_ids, list) and len([item for item in allowed_executor_ids if item]) > 1:
        return "fallback_allowed"
    return "fixed"


def _resolve_quality_status(*, status: str | None, metadata: dict[str, Any] | None) -> str:
    governance = metadata.get("governance") if isinstance(metadata, dict) and isinstance(metadata.get("governance"), dict) else {}
    explicit = str(governance.get("quality_status") or "").strip().lower()
    if explicit in _VALID_QUALITY_STATUSES:
        return explicit
    if (status or "").strip().lower() != "active":
        return "untested"
    return "usable"


def resolve_ability_governance(*, status: str | None, metadata: dict[str, Any] | None) -> dict[str, Any]:
    scopes = _resolve_scopes(status=status, metadata=metadata)
    return {
        "scopes": scopes,
        "release_status": _resolve_release_status(status=status, metadata=metadata, scopes=scopes),
        "route_policy": _resolve_route_policy(metadata=metadata),
        "quality_status": _resolve_quality_status(status=status, metadata=metadata),
    }


def build_business_status(governance: dict[str, Any] | None) -> dict[str, Any]:
    payload = governance if isinstance(governance, dict) else {}
    release_status = str(payload.get("release_status") or "").strip().lower()
    quality_status = str(payload.get("quality_status") or "").strip().lower()
    scopes = _normalize_scope_list(payload.get("scopes"))

    if release_status == "published":
        availability_code, availability_label = "available", "可用"
    elif release_status in {"internal_ready", "eval_ready"}:
        availability_code, availability_label = "testing", "测试中"
    else:
        availability_code, availability_label = "unavailable", "暂不可用"

    if quality_status == "usable":
        stability_code, stability_label = "stable", "稳定"
    elif quality_status == "needs_optimization":
        stability_code, stability_label = "optimizing", "优化中"
    else:
        stability_code, stability_label = "experimental", "实验性"

    return {
        "availability_code": availability_code,
        "availability_label": availability_label,
        "stability_code": stability_code,
        "stability_label": stability_label,
        "surface_labels": [_SCOPE_LABELS.get(scope, scope) for scope in scopes],
    }


def enrich_metadata_with_governance(
    metadata: dict[str, Any] | None,
    *,
    status: str | None,
    governance_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = deepcopy(metadata) if isinstance(metadata, dict) else {}
    if governance_override is not None:
        governance_payload = {
            "scopes": _normalize_scope_list(governance_override.get("scopes")),
            "release_status": str(governance_override.get("release_status") or "").strip().lower() or None,
            "route_policy": str(governance_override.get("route_policy") or "").strip().lower() or None,
            "quality_status": str(governance_override.get("quality_status") or "").strip().lower() or None,
        }
        governance_payload = {key: value for key, value in governance_payload.items() if value not in (None, [], "")}
        if governance_payload:
            base["governance"] = governance_payload
        else:
            base.pop("governance", None)
    base["governance"] = resolve_ability_governance(status=status, metadata=base)
    return base
