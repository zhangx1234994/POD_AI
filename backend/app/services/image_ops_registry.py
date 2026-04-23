"""Registry for self-built image atomic abilities handled by image-ops."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


IMAGE_OPS_CAPABILITIES: dict[str, dict[str, Any]] = {
    "expand_mask_color": {
        "operation": "expand-mask-color",
        "heavy": False,
        "local_fallback_allowed": True,
        "filename_prefix": "expand_mask",
        "result_tag": "podi-expand-mask",
    },
    "set_dpi": {
        "operation": "set-dpi",
        "heavy": False,
        "local_fallback_allowed": True,
        "filename_prefix": "set_dpi",
        "result_tag": "podi-set-dpi",
    },
    "upscale_resize": {
        "operation": "upscale-resize",
        "heavy": True,
        "local_fallback_allowed": False,
        "filename_prefix": "upscale",
        "result_tag": "podi-upscale-resize",
    },
}


def image_ops_managed_capabilities() -> list[str]:
    return list(IMAGE_OPS_CAPABILITIES.keys())


def is_image_ops_capability(*, provider: str | None, capability_key: str | None) -> bool:
    return (provider or "").strip().lower() == "podi" and (capability_key or "").strip() in IMAGE_OPS_CAPABILITIES


def get_image_ops_capability(capability_key: str | None) -> dict[str, Any] | None:
    key = (capability_key or "").strip()
    spec = IMAGE_OPS_CAPABILITIES.get(key)
    return deepcopy(spec) if isinstance(spec, dict) else None


def is_heavy_image_ops_capability(capability_key: str | None) -> bool:
    spec = IMAGE_OPS_CAPABILITIES.get((capability_key or "").strip()) or {}
    return bool(spec.get("heavy", False))
