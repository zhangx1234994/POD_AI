"""Normalize eval workflow metadata for API responses."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.models.eval import EvalWorkflowVersion
from app.services.eval_workflow_catalog_cleanup import get_eval_workflow_cleanup_overrides
from app.services.eval_workflow_deprecation import enrich_metadata_with_eval_workflow_deprecation
from app.services.eval_workflow_governance import resolve_eval_workflow_governance
from app.services.eval_workflow_presentation import (
    enrich_metadata_with_eval_workflow_presentation,
    is_eval_workflow_visible,
)
from app.services.eval_workflow_usage import enrich_metadata_with_eval_workflow_usage


EVAL_WORKFLOW_METADATA_UPDATE_KEYS = frozenset({"metadata", "presentation", "usage", "deprecation", "governance"})
EVAL_WORKFLOW_PUBLIC_ROLES = frozenset({"production", "candidate"})
EVAL_WORKFLOW_EVAL_CATALOG_EXTRA_ROLES = frozenset({"auxiliary"})


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def merge_eval_workflow_metadata_update(
    current: dict[str, Any] | None,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    """Merge admin-editable metadata blocks without losing unrelated fields."""

    base = deepcopy(current) if isinstance(current, dict) else {}
    if "metadata" in updates:
        value = updates.get("metadata")
        if value is None:
            base = {}
        elif isinstance(value, dict):
            base = _deep_merge(base, value)

    for key in ("presentation", "usage", "deprecation", "governance"):
        if key not in updates:
            continue
        value = updates.get(key)
        if value is None:
            base.pop(key, None)
        elif isinstance(value, dict):
            existing = base.get(key) if isinstance(base.get(key), dict) else {}
            base[key] = _deep_merge(existing, value)

    return base or None


def _camelize_presentation(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    return {
        "visible": payload.get("visible"),
        "sortOrder": payload.get("sort_order"),
        "categoryLabel": payload.get("category_label"),
        "usageHint": payload.get("usage_hint"),
        "operationLabel": payload.get("operation_label"),
        "variantLabel": payload.get("variant_label"),
        "entryMode": payload.get("entry_mode"),
        "resultMode": payload.get("result_mode"),
        "supportsBatch": payload.get("supports_batch"),
        "recommendedRepeatCount": payload.get("recommended_repeat_count"),
        "badges": payload.get("badges") or [],
    }


def _camelize_usage(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    return {
        "singleRunEnabled": payload.get("single_run_enabled"),
        "batchEnabled": payload.get("batch_enabled"),
        "docsEnabled": payload.get("docs_enabled"),
        "recommendedEntry": payload.get("recommended_entry"),
        "supportsAnnotation": payload.get("supports_annotation"),
        "requiresResourceOptions": payload.get("requires_resource_options"),
        "resourceOptionTypes": payload.get("resource_option_types") or [],
    }


def _camelize_deprecation(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    return {
        "isDeprecated": payload.get("is_deprecated"),
        "replacementWorkflowId": payload.get("replacement_workflow_id"),
        "replacementDisplayName": payload.get("replacement_display_name"),
        "reason": payload.get("reason"),
        "retirementMode": payload.get("retirement_mode"),
    }


def _camelize_governance(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    return {
        "role": payload.get("role"),
        "roleLabel": payload.get("role_label"),
        "roleReason": payload.get("role_reason"),
        "rank": payload.get("rank"),
        "isPrimary": payload.get("is_primary"),
    }


def build_eval_workflow_response_metadata(row: EvalWorkflowVersion) -> dict[str, Any]:
    """Build metadata/presentation/usage/deprecation/governance for a workflow row."""

    metadata = deepcopy(row.extra_metadata) if isinstance(row.extra_metadata, dict) else {}
    metadata = _deep_merge(metadata, get_eval_workflow_cleanup_overrides(row.workflow_id))
    metadata = enrich_metadata_with_eval_workflow_deprecation(metadata, status=row.status)
    metadata = enrich_metadata_with_eval_workflow_presentation(
        metadata,
        status=row.status,
        category=row.category,
        workflow_id=row.workflow_id,
        name=row.name,
        parameters_schema=row.parameters_schema,
        output_schema=row.output_schema,
    )
    metadata = enrich_metadata_with_eval_workflow_usage(
        metadata,
        category=row.category,
        parameters_schema=row.parameters_schema,
    )
    governance = resolve_eval_workflow_governance(
        status=row.status,
        category=row.category,
        workflow_id=row.workflow_id,
        name=row.name,
        metadata=metadata,
        deprecation=metadata.get("deprecation") if isinstance(metadata.get("deprecation"), dict) else None,
    )
    metadata["governance"] = governance
    if governance.get("role") not in EVAL_WORKFLOW_PUBLIC_ROLES and isinstance(metadata.get("presentation"), dict):
        metadata["presentation"]["visible"] = False
    return {
        "metadata": metadata or None,
        "presentation": _camelize_presentation(metadata.get("presentation")),
        "usage": _camelize_usage(metadata.get("usage")),
        "deprecation": _camelize_deprecation(metadata.get("deprecation")),
        "governance": _camelize_governance(governance),
    }


def is_eval_workflow_publicly_visible(row: EvalWorkflowVersion) -> bool:
    metadata = build_eval_workflow_response_metadata(row).get("metadata")
    governance = metadata.get("governance") if isinstance(metadata, dict) else None
    role = str(governance.get("role") or "").strip().lower() if isinstance(governance, dict) else ""
    if role and role not in EVAL_WORKFLOW_PUBLIC_ROLES:
        return False
    return is_eval_workflow_visible(
        status=row.status,
        category=row.category,
        workflow_id=row.workflow_id,
        name=row.name,
        parameters_schema=row.parameters_schema,
        output_schema=row.output_schema,
        metadata=metadata if isinstance(metadata, dict) else None,
    )


def is_eval_workflow_visible_for_eval_catalog(
    row: EvalWorkflowVersion,
    *,
    include_auxiliary: bool = False,
) -> bool:
    """Return whether a workflow should appear in the internal eval toolbox.

    The default behavior stays identical to the public catalog. The eval UI can
    opt into auxiliary tools such as DPI, upscale, tagging, and queue probes
    without leaking legacy or disabled workflows.
    """

    if is_eval_workflow_publicly_visible(row):
        return True
    if not include_auxiliary:
        return False

    response = build_eval_workflow_response_metadata(row)
    metadata = response.get("metadata")
    governance = metadata.get("governance") if isinstance(metadata, dict) else None
    role = str(governance.get("role") or "").strip().lower() if isinstance(governance, dict) else ""
    if role not in EVAL_WORKFLOW_EVAL_CATALOG_EXTRA_ROLES:
        return False
    if str(row.status or "").strip().lower() != "active":
        return False

    deprecation = metadata.get("deprecation") if isinstance(metadata, dict) else None
    if isinstance(deprecation, dict) and deprecation.get("is_deprecated"):
        return False

    raw_metadata = row.extra_metadata if isinstance(row.extra_metadata, dict) else {}
    raw_presentation = raw_metadata.get("presentation") if isinstance(raw_metadata.get("presentation"), dict) else {}
    if raw_presentation.get("visible") is False:
        return False
    return True
