"""Shared prompt helpers for VL-controlled image fission."""

from __future__ import annotations

import json
from typing import Any


OBJECT_LEVEL_FISSION_INSTRUCTION = (
    "High object-level fission: every repeated object should show visible local redesign. "
    "Vary poses, contour details, hair, clothing, expressions, accessory details, "
    "object decoration, ball panel patterns, heart silhouettes, and small shape details. "
    "Avoid keeping identical repeated objects. Preserve all-over repeat layout, motif count level, "
    "average motif size, spacing rhythm, background-to-motif area ratio, and source palette."
)

CONTROL_DESCRIPTION_SUFFIX = (
    "Preserve palette, density, motif scale, spacing rhythm, and print material."
)

CONTROL_CARD_MARKERS = {
    "route_mode",
    "pattern_type",
    "profile_hint",
    "prompt_main",
    "prompt_control",
    "image_desc",
    "pattern_risk_type",
    "density_risk_level",
    "palette_card",
    "recommended_reference_lock",
    "recommended_color_lock",
}


def append_unique(base: str | None, addition: str | None) -> str:
    base_text = str(base or "").strip()
    addition_text = str(addition or "").strip()
    if not addition_text:
        return base_text
    if addition_text in base_text:
        return base_text
    return "\n\n".join(part for part in (base_text, addition_text) if part)


def parse_variation_percent(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip().lower().replace("%", "")
    if text in {"low", "safe", "conservative"}:
        return 30.0
    if text in {"mid", "medium", "default"}:
        return 60.0
    if text in {"high", "strong", "object-strong"}:
        return 80.0
    if text in {"experimental", "max", "very_high", "very-high"}:
        return 100.0
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number * 100 if 0 < number <= 1 else number


def should_add_object_fission_instruction(
    *,
    pattern_risk_type: Any,
    object_variation_level: Any = None,
    bili: Any = None,
) -> bool:
    risk = str(pattern_risk_type or "").strip()
    if risk != "separable_cartoon_icon_repeat":
        return False
    object_level = str(object_variation_level or "").strip().lower()
    if object_level == "high":
        return True
    percent = parse_variation_percent(bili)
    return percent is not None and percent >= 80


def compile_comfyui_v4_prompt(
    *,
    prompt_main: str | None,
    business_extra_prompt: str | None = None,
    pattern_risk_type: Any = None,
    object_variation_level: Any = None,
    bili: Any = None,
) -> str:
    prompt = str(prompt_main or "").strip()
    if should_add_object_fission_instruction(
        pattern_risk_type=pattern_risk_type,
        object_variation_level=object_variation_level,
        bili=bili,
    ):
        prompt = append_unique(prompt, OBJECT_LEVEL_FISSION_INSTRUCTION)
    prompt = append_unique(prompt, business_extra_prompt)
    return prompt


def compile_comfyui_v4_image_desc(image_desc: str | None) -> str:
    return append_unique(image_desc, CONTROL_DESCRIPTION_SUFFIX)


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        pass

    # Some old traces stored a JSON object followed by color-control prose.
    start = text.find("{")
    if start < 0:
        return None
    try:
        parsed, _ = json.JSONDecoder().raw_decode(text[start:])
        return parsed
    except (TypeError, ValueError):
        return None


def is_fission_control_card(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    has_prompt = bool(value.get("prompt_main") or value.get("promptMain"))
    return has_prompt and len(CONTROL_CARD_MARKERS.intersection(value)) >= 3


def extract_fission_control_card(value: Any, *, _depth: int = 0) -> dict[str, Any] | None:
    if _depth > 4:
        return None
    parsed = parse_jsonish(value)
    if not isinstance(parsed, dict):
        return None

    for key in ("fissionControlCard", "fission_control_card"):
        candidate = parsed.get(key)
        if isinstance(candidate, dict):
            nested = extract_fission_control_card(candidate, _depth=_depth + 1)
            return nested or candidate

    if is_fission_control_card(parsed):
        return parsed

    for key in ("vl_result", "vlResult", "vlCard", "promptCard", "prompt_card"):
        candidate = parsed.get(key)
        if isinstance(candidate, dict):
            nested = extract_fission_control_card(candidate, _depth=_depth + 1)
            if nested:
                return nested

    for key in (
        "rawText",
        "raw_text",
        "imageDesc",
        "image_desc",
        "promptControl",
        "prompt_control",
        "text",
        "content",
    ):
        candidate = parsed.get(key)
        if isinstance(candidate, str) and candidate.strip():
            nested = extract_fission_control_card(candidate, _depth=_depth + 1)
            if nested:
                return nested
    return None
