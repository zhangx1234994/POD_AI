"""Compatibility-safe helpers for user-facing ability presentation."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


_TRAILING_ENGLISH_RE = re.compile(r"\s+[A-Za-z][A-Za-z0-9 /().,_:+-]*$")
_NODE_HINT_RE = re.compile(r"^节点\s*\d+\s*[·:：.-]\s*.*$")
_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
_PROVIDER_SEPARATOR_RE = re.compile(r"\s*[·:：]\s*")
_ADVANCED_FIELD_KEYS = {
    "aspect_ratio",
    "batch",
    "batch_size",
    "cfg",
    "custom_height",
    "custom_width",
    "denoise",
    "dpi",
    "duration",
    "expand_bottom",
    "expand_left",
    "expand_right",
    "expand_top",
    "height",
    "max_images",
    "max_long_edge",
    "negative_prompt",
    "output",
    "output_format",
    "patternType",
    "pattern_type",
    "resolution",
    "response_format",
    "seed",
    "sequential_image_generation",
    "size",
    "steps",
    "type",
    "width",
}


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().split())
    return text or None


def _prefer_user_text(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if _NODE_HINT_RE.match(text):
        return None
    if _CHINESE_RE.search(text):
        text = _TRAILING_ENGLISH_RE.sub("", text).strip()
    return text or None


def get_public_display_name(display_name: str | None) -> str | None:
    text = _clean_text(display_name)
    if not text:
        return None
    parts = _PROVIDER_SEPARATOR_RE.split(text, maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        text = parts[1].strip()
    if _CHINESE_RE.search(text):
        text = _TRAILING_ENGLISH_RE.sub("", text).strip()
    return text or None


def get_public_summary(description: str | None) -> str | None:
    return _prefer_user_text(description)


def get_public_field_schema(
    schema: dict[str, Any] | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(schema, dict):
        return schema
    result = deepcopy(schema)
    raw_fields = result.get("fields")
    if not isinstance(raw_fields, list):
        return result
    presentation = metadata.get("presentation") if isinstance(metadata, dict) else {}
    field_overrides = presentation.get("fields") if isinstance(presentation, dict) else {}
    overrides_by_name = field_overrides if isinstance(field_overrides, dict) else {}

    normalized_fields: list[dict[str, Any]] = []
    for raw in raw_fields:
        if not isinstance(raw, dict):
            continue
        field = deepcopy(raw)
        name = str(field.get("name") or "")
        override = overrides_by_name.get(name) if isinstance(overrides_by_name.get(name), dict) else {}

        label = _clean_text(override.get("label")) or _prefer_user_text(field.get("label")) or _clean_text(field.get("label"))
        description = _clean_text(override.get("description")) or _prefer_user_text(field.get("description"))
        placeholder = _clean_text(override.get("placeholder")) or _prefer_user_text(field.get("placeholder"))

        if label:
            field["label"] = label
        if description:
            field["description"] = description
        elif "description" in field:
            field.pop("description", None)
        if placeholder:
            field["placeholder"] = placeholder
        elif "placeholder" in field:
            field.pop("placeholder", None)

        advanced_override = override.get("advanced")
        if isinstance(advanced_override, bool):
            field["advanced"] = advanced_override
        elif name in _ADVANCED_FIELD_KEYS:
            field["advanced"] = True

        normalized_fields.append(field)

    result["fields"] = normalized_fields
    return result


def get_public_presentation(
    *,
    display_name: str | None,
    description: str | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    presentation = metadata.get("presentation") if isinstance(metadata, dict) else {}
    public_name = _clean_text((presentation or {}).get("name")) or get_public_display_name(display_name)
    public_summary = _clean_text((presentation or {}).get("summary")) or get_public_summary(description)
    public_form_intro = _clean_text((presentation or {}).get("formIntro"))
    public_expected_output = _clean_text((presentation or {}).get("expectedOutput"))
    public_surfaces = (presentation or {}).get("surfaces") if isinstance((presentation or {}).get("surfaces"), dict) else None

    payload: dict[str, Any] = {}
    if public_name:
        payload["name"] = public_name
    if public_summary:
        payload["summary"] = public_summary
    if public_form_intro:
        payload["formIntro"] = public_form_intro
    if public_expected_output:
        payload["expectedOutput"] = public_expected_output
    if public_surfaces:
        payload["surfaces"] = public_surfaces
    return payload or None
