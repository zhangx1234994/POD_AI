"""Helpers for business-facing ability presentation metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.ability_governance import resolve_ability_governance

_CATEGORY_LABELS = {
    "image_process": "图像处理",
    "image_generation": "图片生成",
    "video_generation": "视频生成",
    "text_generation": "文本理解",
    "utilities": "平台工具",
}

_CATEGORY_SORT_BUCKETS = {
    "image_process": 100,
    "image_generation": 200,
    "video_generation": 300,
    "text_generation": 400,
    "utilities": 900,
}


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


def _normalize_sort_order(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _guess_operation_label(*, category: str, capability_key: str, provider: str) -> str:
    key = capability_key.strip().lower()
    if any(token in key for token in ("outpaint", "extend", "kuotu", "kuozhan")):
        return "图像扩展"
    if any(token in key for token in ("remove_bg", "koutu", "kouxiang")):
        return "抠图"
    if any(token in key for token in ("liebian", "fission", "variation")):
        return "图像裂变"
    if any(token in key for token in ("tiqu", "extract")):
        return "图案提取"
    if category == "image_process":
        return "图像处理"
    if category == "image_generation":
        return "图片生成"
    if category == "video_generation":
        return "视频生成"
    if category == "text_generation":
        return "文本处理"
    if provider == "podi" or category == "utilities":
        return "辅助工具"
    return "能力调用"


def _guess_usage_hint(*, category: str, ability_type: str, provider: str, governance: dict[str, Any]) -> str:
    scopes = set(governance.get("scopes") or [])
    if provider == "podi" or category == "utilities":
        return "适合平台内部链路或管理端辅助操作"
    if "coze" in scopes and ability_type == "comfyui":
        return "适合在 Coze 工作流中作为图像节点使用"
    if "coze" in scopes:
        return "适合在 Coze 工作流中作为原子能力节点使用"
    if "client" in scopes:
        return "适合直接给业务侧前台或工作台使用"
    if "eval" in scopes:
        return "适合先在测评端完成单次验证后再决定发布"
    if category == "image_process":
        return "适合单图增强、抠图或结构化处理"
    if category == "image_generation":
        return "适合生成或改造图片结果"
    if category == "video_generation":
        return "适合生成短视频结果"
    if category == "text_generation":
        return "适合理解提示词、文案或多模态输入"
    return "适合直接发起单次能力验证"


def resolve_ability_presentation(
    *,
    status: str | None,
    provider: str | None,
    category: str | None,
    capability_key: str | None,
    ability_type: str | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    base = metadata if isinstance(metadata, dict) else {}
    presentation = base.get("presentation") if isinstance(base.get("presentation"), dict) else {}
    normalized_category = str(category or "").strip().lower()
    governance = resolve_ability_governance(status=status, metadata=base)
    default_visible = (status or "").strip().lower() == "active" and governance.get("release_status") != "deprecated"
    default_sort = _CATEGORY_SORT_BUCKETS.get(normalized_category, 9000)
    return {
        "visible": _normalize_bool(presentation.get("visible"), default=default_visible),
        "sort_order": _normalize_sort_order(presentation.get("sort_order"), default=default_sort),
        "category_label": str(
            presentation.get("category_label") or _CATEGORY_LABELS.get(normalized_category) or (category or "通用能力")
        ).strip(),
        "usage_hint": str(
            presentation.get("usage_hint")
            or _guess_usage_hint(
                category=normalized_category,
                ability_type=str(ability_type or "").strip().lower(),
                provider=str(provider or "").strip().lower(),
                governance=governance,
            )
        ).strip(),
        "operation_label": str(
            presentation.get("operation_label")
            or _guess_operation_label(
                category=normalized_category,
                capability_key=str(capability_key or ""),
                provider=str(provider or "").strip().lower(),
            )
        ).strip(),
    }


def enrich_metadata_with_presentation(
    metadata: dict[str, Any] | None,
    *,
    status: str | None,
    provider: str | None,
    category: str | None,
    capability_key: str | None,
    ability_type: str | None,
    presentation_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = deepcopy(metadata) if isinstance(metadata, dict) else {}
    if presentation_override is not None:
        payload = {
            "visible": presentation_override.get("visible"),
            "sort_order": presentation_override.get("sort_order"),
            "category_label": str(presentation_override.get("category_label") or "").strip() or None,
            "usage_hint": str(presentation_override.get("usage_hint") or "").strip() or None,
            "operation_label": str(presentation_override.get("operation_label") or "").strip() or None,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        if payload:
            base["presentation"] = payload
        else:
            base.pop("presentation", None)
    base["presentation"] = resolve_ability_presentation(
        status=status,
        provider=provider,
        category=category,
        capability_key=capability_key,
        ability_type=ability_type,
        metadata=base,
    )
    return base
