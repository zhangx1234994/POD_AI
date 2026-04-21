"""Helpers for business-facing eval workflow usage metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _normalize_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _field_names(schema: dict[str, Any] | None) -> list[str]:
    fields = schema.get("fields") if isinstance(schema, dict) else None
    if not isinstance(fields, list):
        return []
    result: list[str] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip()
        if name:
            result.append(name)
    return result


def _resource_option_types(parameters_schema: dict[str, Any] | None) -> list[str]:
    fields = parameters_schema.get("fields") if isinstance(parameters_schema, dict) else None
    if not isinstance(fields, list):
        return []
    types: list[str] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        explicit = str(field.get("resourceType") or field.get("resource_type") or "").strip().lower()
        name = str(field.get("name") or "").strip().lower()
        resource_type = ""
        if explicit in {"lora", "model", "plugin"}:
            resource_type = explicit
        elif "lora" in name:
            resource_type = "lora"
        elif any(token in name for token in ("model", "checkpoint", "unet", "clip", "vae")):
            resource_type = "model"
        elif any(token in name for token in ("plugin", "node")):
            resource_type = "plugin"
        if resource_type and resource_type not in types:
            types.append(resource_type)
    return types


def _guess_batch_enabled(
    *,
    category: str,
    parameters_schema: dict[str, Any] | None,
    presentation: dict[str, Any] | None,
) -> bool:
    if isinstance(presentation, dict) and bool(presentation.get("supports_batch")):
        return True
    names = {name.lower() for name in _field_names(parameters_schema)}
    if "count" in names:
        return True
    if "lora" in names:
        return True
    return category in {"图裂变", "花纹提取类", "四方/两方连续图类"}


def _guess_recommended_entry(
    *,
    parameters_schema: dict[str, Any] | None,
    batch_enabled: bool,
    requires_resource_options: bool,
) -> str:
    names = {name.lower() for name in _field_names(parameters_schema)}
    if batch_enabled and "lora" in names:
        return "lora_batch"
    if requires_resource_options:
        return "resource_form"
    if "url" in names:
        return "single_image"
    if names:
        return "parameter_form"
    return "direct_run"


def _guess_supports_annotation(
    *,
    presentation: dict[str, Any] | None,
) -> bool:
    result_mode = str((presentation or {}).get("result_mode") or "").strip().lower()
    return result_mode in {"image", "callback_image"}


def resolve_eval_workflow_usage(
    *,
    category: str | None,
    parameters_schema: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    base = metadata if isinstance(metadata, dict) else {}
    usage = base.get("usage") if isinstance(base.get("usage"), dict) else {}
    presentation = base.get("presentation") if isinstance(base.get("presentation"), dict) else {}
    category_text = str(category or "").strip() or "通用类"
    resource_types = _resource_option_types(parameters_schema)
    requires_resource_options = bool(resource_types)
    batch_enabled = _normalize_bool(
        usage.get("batch_enabled"),
        default=_guess_batch_enabled(
            category=category_text,
            parameters_schema=parameters_schema,
            presentation=presentation,
        ),
    )
    return {
        "single_run_enabled": _normalize_bool(usage.get("single_run_enabled"), default=True),
        "batch_enabled": batch_enabled,
        "docs_enabled": _normalize_bool(usage.get("docs_enabled"), default=True),
        "recommended_entry": str(
            usage.get("recommended_entry")
            or _guess_recommended_entry(
                parameters_schema=parameters_schema,
                batch_enabled=batch_enabled,
                requires_resource_options=requires_resource_options,
            )
        ).strip()
        or "parameter_form",
        "supports_annotation": _normalize_bool(
            usage.get("supports_annotation"),
            default=_guess_supports_annotation(presentation=presentation),
        ),
        "requires_resource_options": _normalize_bool(
            usage.get("requires_resource_options"),
            default=requires_resource_options,
        ),
        "resource_option_types": list(usage.get("resource_option_types") or resource_types or []),
    }


def enrich_metadata_with_eval_workflow_usage(
    metadata: dict[str, Any] | None,
    *,
    category: str | None,
    parameters_schema: dict[str, Any] | None,
    usage_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = deepcopy(metadata) if isinstance(metadata, dict) else {}
    if usage_override is not None:
        payload = {
            "single_run_enabled": usage_override.get("single_run_enabled"),
            "batch_enabled": usage_override.get("batch_enabled"),
            "docs_enabled": usage_override.get("docs_enabled"),
            "recommended_entry": str(usage_override.get("recommended_entry") or "").strip() or None,
            "supports_annotation": usage_override.get("supports_annotation"),
            "requires_resource_options": usage_override.get("requires_resource_options"),
            "resource_option_types": list(usage_override.get("resource_option_types") or []),
        }
        payload = {
            key: value
            for key, value in payload.items()
            if value is not None and value != []
        }
        if payload:
            base["usage"] = payload
        else:
            base.pop("usage", None)
    base["usage"] = resolve_eval_workflow_usage(
        category=category,
        parameters_schema=parameters_schema,
        metadata=base,
    )
    return base
