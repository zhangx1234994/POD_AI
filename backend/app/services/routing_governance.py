"""Routing/concurrency normalization for executors and abilities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_ALLOWED_SELECTION_POLICIES = {"auto", "fixed", "queue", "weight", "round_robin"}


def _normalize_tags(value: Any) -> list[str]:
    tags: list[str] = []
    if value is None:
        return tags
    if isinstance(value, list):
        for item in value:
            text = str(item).strip().lower()
            if text:
                tags.append(text)
    elif isinstance(value, str):
        for part in value.replace(";", ",").split(","):
            text = part.strip().lower()
            if text:
                tags.append(text)
    else:
        text = str(value).strip().lower()
        if text:
            tags.append(text)
    return tags


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    text = str(value).strip()
    return [text] if text else []


def normalize_executor_routing(config: dict[str, Any] | None, *, max_concurrency: int) -> dict[str, Any]:
    cfg = deepcopy(config) if isinstance(config, dict) else {}
    routing_raw = cfg.get("routing") if isinstance(cfg.get("routing"), dict) else {}
    tags = _normalize_tags(
        routing_raw.get("tags")
        if "tags" in routing_raw
        else (cfg.get("tags") if "tags" in cfg else cfg.get("tag"))
    )
    selection_policy = str(routing_raw.get("selection_policy") or "auto").strip().lower()
    if selection_policy not in _ALLOWED_SELECTION_POLICIES:
        selection_policy = "auto"
    routing_enabled = bool(routing_raw.get("routing_enabled", True))
    fallback_only = bool(routing_raw.get("fallback_only", False))
    allowed_workflow_keys = _normalize_string_list(routing_raw.get("allowed_workflow_keys"))
    blocked_workflow_keys = _normalize_string_list(routing_raw.get("blocked_workflow_keys"))
    normalized = {
        "routing_enabled": routing_enabled,
        "fallback_only": fallback_only,
        "selection_policy": selection_policy,
        "tags": tags,
        "allowed_workflow_keys": allowed_workflow_keys,
        "blocked_workflow_keys": blocked_workflow_keys,
        "concurrency_limit": max(1, int(max_concurrency or 1)),
    }
    return normalized


def enrich_executor_config_with_routing(config: dict[str, Any] | None, *, max_concurrency: int) -> dict[str, Any]:
    base = deepcopy(config) if isinstance(config, dict) else {}
    base["routing"] = normalize_executor_routing(base, max_concurrency=max_concurrency)
    return base


def build_executor_business_status(routing: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(routing.get("routing_enabled", True))
    fallback_only = bool(routing.get("fallback_only", False))
    concurrency = max(1, int(routing.get("concurrency_limit") or 1))
    if not enabled:
        mode_code = "fixed_only"
        mode_label = "固定节点执行"
    elif fallback_only:
        mode_code = "fallback_only"
        mode_label = "仅兜底参与"
    else:
        mode_code = "routeable"
        mode_label = "可参与路由"
    return {
        "execution_mode_code": mode_code,
        "execution_mode_label": mode_label,
        "concurrency_label": f"并发上限 {concurrency}",
        "tags": routing.get("tags") or [],
    }


def normalize_ability_routing(metadata: dict[str, Any] | None) -> dict[str, Any]:
    source = deepcopy(metadata) if isinstance(metadata, dict) else {}
    routing_raw = source.get("routing") if isinstance(source.get("routing"), dict) else {}
    executor_type = str(source.get("executor_type") or "").strip().lower()

    policy = str(
        routing_raw.get("selection_policy")
        or routing_raw.get("policy")
        or source.get("routing_policy")
        or "auto"
    ).strip().lower()
    if policy not in _ALLOWED_SELECTION_POLICIES:
        policy = "auto"

    required_tags = _normalize_tags(
        routing_raw.get("required_executor_tags")
        if "required_executor_tags" in routing_raw
        else source.get("required_tags")
    )
    if not required_tags and executor_type == "comfyui":
        required_tags = ["comfyui-general"]
    allowed_executor_ids = _normalize_string_list(
        routing_raw.get("allowed_executor_ids")
        if "allowed_executor_ids" in routing_raw
        else source.get("allowed_executor_ids")
    )
    fallback_to_default = routing_raw.get("fallback_to_default")
    if fallback_to_default is None:
        fallback_to_default = source.get("fallback_to_default")
    if fallback_to_default is None:
        fallback_to_default = True

    action = str(routing_raw.get("action") or source.get("action") or "generic").strip() or "generic"
    workflow_key = str(routing_raw.get("workflow_key") or source.get("workflow_key") or "").strip() or None

    return {
        "selection_policy": policy,
        "required_executor_tags": required_tags,
        "allowed_executor_ids": allowed_executor_ids,
        "fallback_to_default": bool(fallback_to_default),
        "action": action,
        "workflow_key": workflow_key,
    }


def enrich_ability_metadata_with_routing(metadata: dict[str, Any] | None) -> dict[str, Any]:
    base = deepcopy(metadata) if isinstance(metadata, dict) else {}
    base["routing"] = normalize_ability_routing(base)
    return base
