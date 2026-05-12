"""Prompt compiler for GPT Image 2 pattern fission business versions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TEMPLATE_ID = "pattern_fission_prompt_template_v21"
ROUTE_ID = "OPENAI_GPT_IMAGE2_PATTERN_V21"
MODEL_ID = "gpt-image-2"
DEFAULT_SIZE = "auto"
DEFAULT_OUTPUT_FORMAT = "png"

QUALITY_MAP = {
    "preview": "low",
    "production": "medium",
    "premium": "high",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "auto": "auto",
}

STRENGTHS = {
    "low": (
        "Create a conservative same-series variant. Keep the composition and motif placement close "
        "to the reference, while changing local shapes, surface details, and internal ornament."
    ),
    "medium": (
        "Create a clearly new same-series variant. Keep layout, density, subject count, color "
        "relationship, and style family, but redesign each major motif so it is visibly different."
    ),
    "high": (
        "Create a strongly redesigned same-series variant. Preserve only the layout logic, density, "
        "subject count, border relationship, style family, and palette relationship; make the main "
        "motifs clearly new."
    ),
}

CATEGORY_BRIEFS = {
    "template_object_collection": [
        "Keep the template-like object collection layout, row rhythm, object count feeling, white or simple background, and commercial asset clarity.",
        "Redesign every object with different silhouette, decorative pattern, color grouping, and internal detail while preserving the collection style.",
    ],
    "line_art_floral_branch": [
        "Keep the clean line-art botanical branch style, white or simple background, hand-drawn stroke quality, and blue-and-white decorative relationship if present.",
        "Redesign flower shapes, petal count, blossom angles, bud clusters, branch direction, and line details.",
    ],
    "abstract_background": [
        "Keep the abstract background type, flow rhythm, color relationship, and overall density.",
        "Redesign waves, layers, shapes, internal textures, and movement direction without adding concrete objects.",
    ],
    "central_badge_or_mandala": [
        "Keep the centered structure, radial balance, outer ring logic, and ornamental hierarchy.",
        "Redesign inner symbols, floral units, ring details, and decorative geometry without breaking the centered composition.",
    ],
    "complex_floral_bird_tapestry": [
        "Keep the antique textile feeling, mirrored or structured composition, dense botanical ornament, framed border hierarchy, faded pigment, hand-painted linework, and muted palette relationship.",
        "Redraw every bird, flower, vine, leaf, berry, seed pod, filler motif, and border ornament as a related but visibly different same-series design.",
        "Every bird must have one clean head, one beak, readable eye area, coherent neck-to-body connection, integrated wings, and connected tail. Keep birds visually separate from flowers and leaves.",
    ],
    "unknown_pattern": [
        "Preserve the visible design format, style family, color relationship, and main composition while creating a same-series commercial variant.",
        "Redesign the main visual elements with visible shape and detail changes.",
    ],
}

BASE_PRESERVE = (
    "Preserve the reference image's composition logic, motif count, layout density, spacing rhythm, "
    "scale relationships, border logic, background simplicity, style family, material feeling, and "
    "color relationship."
)
BASE_REDRAW = [
    "Redraw the motifs so the image becomes a new commercial variant in the same series.",
    "The changed elements must have visibly different shapes, silhouettes, details, and internal patterns, not only different colors.",
]
TYPE_LOCK = [
    "Keep the result as a flat decorative pattern, ornament, template image, or design asset matching the reference type.",
    "Do not turn it into a realistic scene, product mockup, poster, photo, or 3D render.",
]
NEGATIVE = [
    "Do not only recolor.",
    "Do not copy the original motifs exactly.",
    "Do not simplify or remove elements.",
    "Do not reduce motif count or leave empty gaps.",
    "Do not add unrelated objects, text, logos, frames, watermarks, or mockup context.",
]


@dataclass(frozen=True)
class PatternFissionPrompt:
    compiled_prompt: str
    openai_params: dict[str, Any]
    route_id: str
    template_id: str
    pattern_type: str
    user_params: dict[str, Any]
    vl_card: dict[str, Any]


def compile_pattern_fission_prompt(
    *,
    vl_summary: dict[str, Any] | None,
    user_inputs: dict[str, Any] | None,
) -> PatternFissionPrompt:
    """Compile VL output and business inputs into GPT Image 2 edit parameters."""

    raw_inputs = dict(user_inputs or {})
    vl_card = extract_vl_card(vl_summary or {})
    user_params = normalize_pattern_fission_user_params(raw_inputs)
    pattern_type = _first_text(
        vl_card.get("pattern_type"),
        vl_card.get("image_type"),
        (vl_summary or {}).get("patternType"),
        "unknown_pattern",
    )
    pattern_key = _category_key(pattern_type)

    sections: list[str] = [
        "Task: create a new commercial same-series pattern variant from the reference image.",
        "",
        "Reference analysis:",
        _format_vl_card(vl_card),
        "",
        "Preserve:",
        f"- {BASE_PRESERVE}",
    ]
    for item in _string_list(vl_card.get("preserve_locks")):
        sections.append(f"- {item}")
    sections.extend(["", "Redraw:"])
    sections.extend(f"- {item}" for item in BASE_REDRAW)
    for item in _string_list(vl_card.get("change_targets")):
        sections.append(f"- {item}")
    sections.extend(["", "Strength:", f"- {STRENGTHS[user_params['variation_strength']]}"])
    sections.extend(["", "Category guidance:"])
    sections.extend(f"- {item}" for item in CATEGORY_BRIEFS.get(pattern_key, CATEGORY_BRIEFS["unknown_pattern"]))
    sections.extend(["", "Type lock:"])
    sections.extend(f"- {item}" for item in TYPE_LOCK)
    sections.extend(["", "Negative constraints:"])
    sections.extend(f"- {item}" for item in NEGATIVE)
    for item in _string_list(vl_card.get("forbidden_drifts")):
        sections.append(f"- {item}")
    _append_business_controls(sections, user_params)
    fission_brief = _first_text(vl_card.get("fission_brief"), (vl_summary or {}).get("fissionBrief"))
    if fission_brief:
        sections.extend(["", "Business fission brief:", f"- {fission_brief}"])
    if user_params.get("extra_prompt"):
        sections.extend(["", "Additional user requirement:", f"- {user_params['extra_prompt']}"])
    sections.extend(
        [
            "",
            "Output:",
            "- Return only the edited image.",
            "- Keep a clean commercial design-asset appearance.",
        ]
    )

    openai_params = {
        "model": MODEL_ID,
        "quality": user_params["quality"],
        "size": user_params["size"],
        "output_format": user_params["output_format"],
        "n": user_params["count"],
        "background": "auto",
    }
    return PatternFissionPrompt(
        compiled_prompt="\n".join(sections).strip(),
        openai_params=openai_params,
        route_id=ROUTE_ID,
        template_id=TEMPLATE_ID,
        pattern_type=pattern_key,
        user_params=user_params,
        vl_card=vl_card,
    )


def extract_vl_card(vl_summary: dict[str, Any]) -> dict[str, Any]:
    if isinstance(vl_summary.get("vlCard"), dict):
        return dict(vl_summary["vlCard"])
    if _looks_like_vl_card(vl_summary):
        return dict(vl_summary)
    prompt_card = vl_summary.get("promptCard") if isinstance(vl_summary.get("promptCard"), dict) else {}
    return {
        "image_type": _first_text(vl_summary.get("image_type"), vl_summary.get("summary"), "unknown_pattern"),
        "pattern_type": _first_text(vl_summary.get("pattern_type"), vl_summary.get("patternType"), "unknown_pattern"),
        "style_family": _first_text(vl_summary.get("style_family"), vl_summary.get("style"), ""),
        "composition": {
            "layout": _first_text(vl_summary.get("composition"), ""),
            "symmetry": "",
            "border_logic": "",
            "density": "",
            "visual_hierarchy": "",
        },
        "motifs": {
            "primary": _string_list(vl_summary.get("subjects")),
            "secondary": [],
            "fillers": [],
            "border": [],
            "background": [],
        },
        "material_style": {},
        "color_palette": {
            "main_colors": _string_list(vl_summary.get("colors")),
            "accent_colors": [],
            "color_relationship": "",
        },
        "preserve_locks": [],
        "change_targets": _string_list(prompt_card.get("fissionHints")),
        "forbidden_drifts": [],
        "fission_brief": _first_text(prompt_card.get("positivePrompt"), prompt_card.get("imageDesc"), vl_summary.get("summary"), ""),
    }


def normalize_pattern_fission_user_params(inputs: dict[str, Any]) -> dict[str, Any]:
    strength = _choice(inputs.get("variation_strength") or inputs.get("strength") or inputs.get("bili"), {"low", "medium", "high"}, "high")
    quality = _quality(inputs.get("quality"))
    return {
        "variation_strength": strength,
        "quality": quality,
        "count": _bounded_int(inputs.get("count") or inputs.get("n") or inputs.get("batch_size"), default=1, minimum=1, maximum=3),
        "preserve_layout": _bool(inputs.get("preserve_layout"), default=True),
        "preserve_border": _choice(inputs.get("preserve_border"), {"auto", "true", "false"}, "auto"),
        "preserve_count_density": _bool(inputs.get("preserve_count_density"), default=True),
        "style_shift": _choice(inputs.get("style_shift"), {"standard", "conservative", "creative"}, "standard"),
        "size": _first_text(inputs.get("size"), DEFAULT_SIZE),
        "output_format": _first_text(inputs.get("output_format"), inputs.get("outputFormat"), DEFAULT_OUTPUT_FORMAT),
        "extra_prompt": _first_text(inputs.get("prompt"), inputs.get("extra_prompt"), inputs.get("user_prompt"), ""),
    }


def _append_business_controls(sections: list[str], user_params: dict[str, Any]) -> None:
    controls: list[str] = []
    if user_params["preserve_layout"]:
        controls.append("Keep the original layout logic and visual hierarchy.")
    if user_params["preserve_count_density"]:
        controls.append("Keep the motif count feeling and density close to the reference.")
    if user_params["preserve_border"] == "true":
        controls.append("Keep the border logic and border-to-center relationship.")
    elif user_params["preserve_border"] == "false":
        controls.append("Border details may change, but do not add unrelated frames.")
    if user_params["style_shift"] == "conservative":
        controls.append("Keep style shift subtle and close to the source series.")
    elif user_params["style_shift"] == "creative":
        controls.append("Allow stronger motif redesign while staying in the same commercial series.")
    if controls:
        sections.extend(["", "Business controls:"])
        sections.extend(f"- {item}" for item in controls)


def _format_vl_card(vl_card: dict[str, Any]) -> str:
    parts = [
        f"- Image type: {_first_text(vl_card.get('image_type'), 'unknown')}",
        f"- Pattern type: {_first_text(vl_card.get('pattern_type'), 'unknown')}",
        f"- Style family: {_first_text(vl_card.get('style_family'), 'unknown')}",
    ]
    composition = vl_card.get("composition") if isinstance(vl_card.get("composition"), dict) else {}
    if composition:
        parts.append(f"- Composition: {_compact_dict(composition)}")
    motifs = vl_card.get("motifs") if isinstance(vl_card.get("motifs"), dict) else {}
    if motifs:
        parts.append(f"- Motifs: {_compact_dict(motifs)}")
    material = vl_card.get("material_style") if isinstance(vl_card.get("material_style"), dict) else {}
    if material:
        parts.append(f"- Material style: {_compact_dict(material)}")
    palette = vl_card.get("color_palette") if isinstance(vl_card.get("color_palette"), dict) else {}
    if palette:
        parts.append(f"- Color palette: {_compact_dict(palette)}")
    return "\n".join(parts)


def _compact_dict(value: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key, item in value.items():
        if isinstance(item, list):
            text = ", ".join(str(part) for part in item[:8] if str(part).strip())
        elif isinstance(item, dict):
            text = _compact_dict(item)
        else:
            text = str(item or "").strip()
        if text:
            chunks.append(f"{key}: {text}")
    return "; ".join(chunks)[:800]


def _looks_like_vl_card(value: dict[str, Any]) -> bool:
    keys = {"image_type", "composition", "motifs", "preserve_locks", "change_targets", "fission_brief"}
    return len(keys.intersection(value)) >= 3


def _category_key(pattern_type: str) -> str:
    normalized = str(pattern_type or "").strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in CATEGORY_BRIEFS:
        return normalized
    if "bird" in normalized or "tapestry" in normalized:
        return "complex_floral_bird_tapestry"
    if "line" in normalized and ("floral" in normalized or "botanical" in normalized):
        return "line_art_floral_branch"
    if "mandala" in normalized or "badge" in normalized:
        return "central_badge_or_mandala"
    if "abstract" in normalized:
        return "abstract_background"
    if "template" in normalized or "collection" in normalized:
        return "template_object_collection"
    return "unknown_pattern"


def _quality(value: Any) -> str:
    normalized = str(value or "preview").strip().lower()
    return QUALITY_MAP.get(normalized, "low")


def _choice(value: Any, allowed: set[str], default: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized.isdigit():
        number = int(normalized)
        if number <= 40:
            normalized = "low"
        elif number <= 75:
            normalized = "medium"
        else:
            normalized = "high"
    return normalized if normalized in allowed else default


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
    return ""


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, (str, int, float)) and str(value).strip():
        return [str(value).strip()]
    return []
