"""Cleanup/deprecation overrides for redundant or non-business-facing abilities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_OVERRIDES: dict[tuple[str, str], dict[str, Any]] = {
    ("comfyui", "huawen_kuotu"): {
        "governance": {
            "release_status": "deprecated",
            "quality_status": "needs_optimization",
        },
        "deprecation": {
            "replacement_capability_key": "flux2_klein_9b_outpaint",
            "replacement_display_name": "ComfyUI · FLUX2-Klein 扩图",
            "reason": "统一扩图入口，避免业务侧同时理解两套扩图工作流。",
            "retirement_mode": "hide_public",
        },
        "presentation": {
            "visible": False,
            "usage_hint": "已由统一扩图入口替代，不再建议直接使用。",
            "operation_label": "旧版扩图",
        },
    },
    ("podi", "expand_mask_color"): {
        "governance": {
            "scopes": ["internal", "admin"],
            "release_status": "internal_ready",
            "quality_status": "usable",
        },
        "presentation": {
            "visible": False,
            "category_label": "平台工具",
            "usage_hint": "内部中间步骤能力，不建议业务直接使用。",
            "operation_label": "内部扩边占位",
        },
    },
    ("podi", "set_dpi"): {
        "execution_target": "image_ops",
        "image_ops": {
            "operation": "set-dpi",
            "heavy": False,
        },
        "governance": {
            "scopes": ["internal", "admin"],
            "release_status": "internal_ready",
            "quality_status": "usable",
        },
        "presentation": {
            "visible": False,
            "category_label": "平台工具",
            "usage_hint": "内部后处理能力，用于印刷输出规范化，不建议业务直接使用。",
            "operation_label": "内部 DPI 处理",
        },
    },
    ("podi", "upscale_resize"): {
        "execution_target": "image_ops",
        "image_ops": {
            "operation": "upscale-resize",
            "heavy": True,
        },
        "governance": {
            "scopes": ["internal", "admin"],
            "release_status": "internal_ready",
            "quality_status": "usable",
        },
        "presentation": {
            "visible": False,
            "category_label": "平台工具",
            "usage_hint": "内部后处理能力，用于尺寸放大与格式规范化，不建议业务直接使用。",
            "operation_label": "内部尺寸处理",
        },
    },
}


def get_cleanup_overrides(*, provider: str | None, capability_key: str | None) -> dict[str, Any]:
    key = (str(provider or "").strip().lower(), str(capability_key or "").strip().lower())
    payload = _OVERRIDES.get(key)
    return deepcopy(payload) if isinstance(payload, dict) else {}
