"""Prompt compiler for GPT Image 2 pattern fission business versions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TEMPLATE_ID = "pattern_fission_controlled_v2"
LEGACY_TEMPLATE_ID = "pattern_fission_prompt_template_v21"
TEMPLATE_ALIASES = {TEMPLATE_ID, "gpt_image2_pattern_fission_controlled_v2"}
LEGACY_TEMPLATE_ALIASES = {LEGACY_TEMPLATE_ID, "pattern_fission_v21", "gpt_image2_pattern_fission_v21"}

ROUTE_ID = "OPENAI_GPT_IMAGE2_PATTERN_CONTROLLED_V2"
LEGACY_ROUTE_ID = "OPENAI_GPT_IMAGE2_PATTERN_V21"
ROUTE_VERSION = "pattern_fission_controlled_v2.0"
MODEL_ID = "gpt-image-2"
DEFAULT_SIZE = "auto"
DEFAULT_OUTPUT_FORMAT = "png"

QUALITY_MAP = {
    "preview": "low",
    "smoke": "low",
    "batch_eval": "low",
    "candidate": "medium",
    "production": "medium",
    "final": "medium",
    "premium": "high",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "auto": "auto",
}

STRENGTH_ALIASES = {
    "low": "conservative",
    "medium": "same_series",
    "high": "creative_same_series",
    "conservative": "conservative",
    "same_series": "same_series",
    "creative_same_series": "creative_same_series",
}

QUANT_PROFILES: dict[str, dict[str, float | list[float]]] = {
    "conservative": {
        "variation_band": [0.20, 0.40],
        "motif_count_delta_max": 0.10,
        "density_delta_max": 0.12,
        "avg_motif_scale_delta_max": 0.12,
        "palette_delta_max": 0.10,
        "background_delta_max": 0.08,
        "layout_retention_min": 0.86,
    },
    "same_series": {
        "variation_band": [0.35, 0.60],
        "motif_count_delta_max": 0.15,
        "density_delta_max": 0.18,
        "avg_motif_scale_delta_max": 0.18,
        "palette_delta_max": 0.15,
        "background_delta_max": 0.12,
        "layout_retention_min": 0.78,
    },
    "creative_same_series": {
        "variation_band": [0.55, 0.75],
        "motif_count_delta_max": 0.22,
        "density_delta_max": 0.25,
        "avg_motif_scale_delta_max": 0.22,
        "palette_delta_max": 0.22,
        "background_delta_max": 0.18,
        "layout_retention_min": 0.70,
    },
}

ROUTE_LOCKS = {
    "complex_tapestry_bordered": [
        "Keep the visible border hierarchy and inner field relationship.",
        "Keep bilateral or radial balance if present.",
        "If birds or animals exist, redraw them with clear head, eye, beak, neck, wing and body connections.",
    ],
    "seamless_dense_allover": [
        "Keep the all-over repeat feeling with no large empty gaps.",
        "Keep dense filler motifs and spacing rhythm.",
        "Do not simplify the pattern into a sparse wallpaper.",
    ],
    "seamless_scatter_fruit": [
        "Keep the same motif category by default: fruit remains fruit of the same commercial family unless semantic_swap=true.",
        "Keep fruit-to-leaf ratio close to the source.",
        "Do not replace the product category unless the user explicitly selected semantic theme swap.",
    ],
    "seamless_scatter_floral": [
        "Keep flower-to-leaf ratio close to the source.",
        "Keep scatter rhythm and negative-space proportion.",
        "Do not enlarge flowers enough to reduce the perceived motif count.",
    ],
    "seamless_four_way": [
        "Keep tile-like continuity and edge rhythm.",
        "Keep repeat direction, spacing rhythm and motif scale relationships.",
        "Do not turn it into a one-off centered illustration.",
    ],
}

LEGACY_STRENGTHS = {
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

LEGACY_CATEGORY_BRIEFS = {
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
    template_id: str | None = None,
) -> PatternFissionPrompt:
    """Compile VL output and business inputs into GPT Image 2 edit parameters."""

    selected_template = str(template_id or TEMPLATE_ID).strip()
    if selected_template in LEGACY_TEMPLATE_ALIASES:
        return _compile_legacy_pattern_fission_prompt(vl_summary=vl_summary, user_inputs=user_inputs)
    return _compile_controlled_v2_prompt(vl_summary=vl_summary, user_inputs=user_inputs)


def _compile_controlled_v2_prompt(
    *,
    vl_summary: dict[str, Any] | None,
    user_inputs: dict[str, Any] | None,
) -> PatternFissionPrompt:
    raw_inputs = dict(user_inputs or {})
    vl_card = extract_vl_card(vl_summary or {})
    user_params = normalize_pattern_fission_user_params(raw_inputs)
    route = normalize_pattern_type(vl_card)
    profile = QUANT_PROFILES[user_params["variation_strength"]]
    motifs = _extract_motifs(vl_card)
    comp = _extract_composition(vl_card)
    material = vl_card.get("material_style") if isinstance(vl_card.get("material_style"), dict) else {}
    palette = vl_card.get("color_palette") if isinstance(vl_card.get("color_palette"), dict) else {}
    route_locks = ROUTE_LOCKS.get(route) or ["Keep flat decorative pattern format and repeat logic."]
    variation_band = profile["variation_band"]
    assert isinstance(variation_band, list)

    semantic_rule = (
        "Semantic swap is enabled: motif category may change, but layout, density, palette, and commercial use limits still apply."
        if user_params["semantic_swap"]
        else "Semantic swap is disabled: keep the same commercial motif category; vary shapes and details, not the subject class."
    )

    sections = [
        "Use the uploaded image as a strict pattern reference, not as a loose style reference.",
        "",
        "Task:",
        "Create one same-series commercial fission variant of the source pattern.",
        "",
        "Source understanding:",
        f"- Pattern route: {route}",
        f"- Style family: {_first_text(vl_card.get('style_family'), '')}",
        f"- Layout: {comp['layout']}",
        f"- Symmetry: {comp['symmetry']}",
        f"- Density: {comp['density']}",
        f"- Border logic: {comp['border_logic']}",
        f"- Primary motifs: {motifs['primary']}",
        f"- Secondary motifs: {motifs['secondary']}",
        f"- Filler motifs: {motifs['fillers']}",
        f"- Border motifs: {motifs['border']}",
        f"- Rendering and texture: {_first_text(material.get('rendering'), '')}; {_first_text(material.get('linework'), '')}; {_first_text(material.get('texture'), '')}",
        f"- Color relationship: {_first_text(palette.get('color_relationship'), '')}",
        "",
        "Hard quantitative locks:",
        f"- Motif count delta must be <= {profile['motif_count_delta_max']:.0%}.",
        f"- Overall density delta must be <= {profile['density_delta_max']:.0%}.",
        f"- Average motif scale delta must be <= {profile['avg_motif_scale_delta_max']:.0%}.",
        f"- Main palette delta must be <= {profile['palette_delta_max']:.0%}.",
        f"- Background hue/value delta must be <= {profile['background_delta_max']:.0%}.",
        f"- Layout retention target must be >= {profile['layout_retention_min']:.0%}.",
        f"- Required visual variation band: {variation_band[0]:.0%}-{variation_band[1]:.0%}.",
        "",
        "Route locks:",
        *[f"- {item}" for item in route_locks],
        "",
        "Allowed changes:",
        "- Redraw petal, leaf, fruit, vine, bird, filler or ornament silhouettes within the same motif category.",
        "- Change internal linework, vein detail, small decoration and local color accents.",
        "- Add small arrangement jitter while preserving spacing rhythm and edge continuity.",
        "- Keep hand-drawn or printed material feeling from the source.",
        "",
        "Semantic rule:",
        f"- {semantic_rule}",
        "",
        "Forbidden:",
        "- Do not introduce readable text, logo, watermark, label, signature or pseudo-letters.",
        "- Do not reduce density, remove filler motifs, create large empty gaps or enlarge motifs beyond the scale limit.",
        "- Do not change the background color family unless the user explicitly selected palette shift.",
        "- Do not turn the image into a scene, product mockup, poster, photorealistic rendering, glossy 3D image or modern vector icon.",
        "- Do not copy the original motifs exactly; variation must come from new shapes and internal details.",
    ]
    if user_params["extra_prompt"]:
        sections.extend(["", "Additional user requirement:", f"- {user_params['extra_prompt']}"])
    sections.extend(["", "Output:", "Flat decorative pattern image, same aspect ratio and same practical use case as the source."])

    compiled_prompt = "\n".join(_trim_empty_tail(sections)).strip()
    audit = _audit_compilation(prompt=compiled_prompt, route=route)
    openai_params = {
        "model": MODEL_ID,
        "quality": user_params["quality"],
        "size": user_params["size"],
        "output_format": user_params["output_format"],
        "n": 1,
        "background": "auto",
    }
    if user_params["output_compression"] is not None:
        openai_params["output_compression"] = user_params["output_compression"]
    return PatternFissionPrompt(
        compiled_prompt=compiled_prompt,
        openai_params=openai_params,
        route_id=ROUTE_ID,
        template_id=TEMPLATE_ID,
        pattern_type=route,
        user_params={
            **user_params,
            "route_version": ROUTE_VERSION,
            "quant_profile": profile,
            "audit": audit,
        },
        vl_card=vl_card,
    )


def _compile_legacy_pattern_fission_prompt(
    *,
    vl_summary: dict[str, Any] | None,
    user_inputs: dict[str, Any] | None,
) -> PatternFissionPrompt:
    raw_inputs = dict(user_inputs or {})
    vl_card = extract_vl_card(vl_summary or {})
    user_params = _normalize_legacy_pattern_fission_user_params(raw_inputs)
    pattern_type = _first_text(
        vl_card.get("pattern_type"),
        vl_card.get("image_type"),
        (vl_summary or {}).get("patternType"),
        "unknown_pattern",
    )
    pattern_key = _legacy_category_key(pattern_type)
    sections: list[str] = [
        "Task: create a new commercial same-series pattern variant from the reference image.",
        "",
        "Reference analysis:",
        _format_vl_card(vl_card),
        "",
        "Preserve:",
        "- Preserve the reference image's composition logic, motif count, layout density, spacing rhythm, scale relationships, border logic, background simplicity, style family, material feeling, and color relationship.",
        "",
        "Redraw:",
        "- Redraw the motifs so the image becomes a new commercial variant in the same series.",
        "- The changed elements must have visibly different shapes, silhouettes, details, and internal patterns, not only different colors.",
        "",
        "Strength:",
        f"- {LEGACY_STRENGTHS[user_params['variation_strength']]}",
        "",
        "Category guidance:",
        *[f"- {item}" for item in LEGACY_CATEGORY_BRIEFS.get(pattern_key, LEGACY_CATEGORY_BRIEFS["unknown_pattern"])],
        "",
        "Type lock:",
        "- Keep the result as a flat decorative pattern, ornament, template image, or design asset matching the reference type.",
        "- Do not turn it into a realistic scene, product mockup, poster, photo, or 3D render.",
        "",
        "Negative constraints:",
        "- Do not only recolor.",
        "- Do not copy the original motifs exactly.",
        "- Do not simplify or remove elements.",
        "- Do not reduce motif count or leave empty gaps.",
        "- Do not add unrelated objects, text, logos, frames, watermarks, or mockup context.",
    ]
    if user_params.get("extra_prompt"):
        sections.extend(["", "Additional user requirement:", f"- {user_params['extra_prompt']}"])
    sections.extend(["", "Output:", "- Return only the edited image.", "- Keep a clean commercial design-asset appearance."])
    return PatternFissionPrompt(
        compiled_prompt="\n".join(sections).strip(),
        openai_params={
            "model": MODEL_ID,
            "quality": user_params["quality"],
            "size": user_params["size"],
            "output_format": user_params["output_format"],
            "n": 1,
            "background": "auto",
        },
        route_id=LEGACY_ROUTE_ID,
        template_id=LEGACY_TEMPLATE_ID,
        pattern_type=pattern_key,
        user_params=user_params,
        vl_card=vl_card,
    )


def extract_vl_card(vl_summary: dict[str, Any]) -> dict[str, Any]:
    if isinstance(vl_summary.get("vlCard"), dict):
        return dict(vl_summary["vlCard"])
    if isinstance(vl_summary.get("vl_card"), dict):
        return dict(vl_summary["vl_card"])
    if _looks_like_vl_card(vl_summary):
        return dict(vl_summary)
    prompt_card = vl_summary.get("promptCard") if isinstance(vl_summary.get("promptCard"), dict) else {}
    return {
        "image_type": _first_text(vl_summary.get("image_type"), vl_summary.get("imageType"), vl_summary.get("summary"), "unknown_pattern"),
        "pattern_type": _first_text(vl_summary.get("pattern_type"), vl_summary.get("patternType"), "unknown_pattern"),
        "style_family": _first_text(vl_summary.get("style_family"), vl_summary.get("styleFamily"), vl_summary.get("style"), ""),
        "composition": {
            "layout": _first_text(vl_summary.get("composition"), ""),
            "symmetry": "",
            "border_logic": "",
            "density": "",
        },
        "motifs": {
            "primary": _string_list(vl_summary.get("subjects")),
            "secondary": [],
            "fillers": [],
            "border": [],
        },
        "material_style": {},
        "color_palette": {
            "background": "",
            "primary_colors": _string_list(vl_summary.get("colors")),
            "color_relationship": "",
        },
        "risk_flags": {},
        "text_policy": "",
        "fission_brief": _first_text(prompt_card.get("positivePrompt"), prompt_card.get("imageDesc"), vl_summary.get("summary"), ""),
    }


def normalize_pattern_type(vl_card: dict[str, Any]) -> str:
    pattern_type = str(vl_card.get("pattern_type") or "")
    image_type = str(vl_card.get("image_type") or "")
    style_family = str(vl_card.get("style_family") or "")
    motifs = vl_card.get("motifs") if isinstance(vl_card.get("motifs"), dict) else {}
    motif_blob = " ".join(
        _compact_list(motifs.get(key, []), 8)
        for key in ("primary", "secondary", "fillers", "border")
    )
    route_blob = " ".join([pattern_type, image_type, style_family, motif_blob])

    has_bird_or_animal = any(key in motif_blob for key in ["鸟", "雀", "鹤", "鹿", "动物", "bird", "animal"])
    has_border_or_tapestry = any(key in route_blob for key in ["边框", "挂毯", "织物", "tapestry", "border"])
    if has_bird_or_animal and has_border_or_tapestry:
        return "complex_tapestry_bordered"

    primary_blob = _compact_list(motifs.get("primary", []), 8)
    fruit_keywords = ["水果", "果实", "柑橘", "橙子", "橘子", "柠檬", "苹果", "梨子", "桃子", "柿子", "草莓", "浆果", "葡萄柚"]
    if any(key in " ".join([pattern_type, primary_blob]) for key in fruit_keywords):
        return "seamless_scatter_fruit"
    if any(key in route_blob for key in ["花卉", "花朵", "花枝", "花型", "floral"]):
        if any(key in route_blob for key in ["满印", "满版", "高密度", "all-over", "allover"]):
            return "seamless_dense_allover"
        return "seamless_scatter_floral"
    if any(key in route_blob for key in ["满印", "满版", "高密度", "家纺", "面料印花"]):
        return "seamless_dense_allover"
    if "连续" in route_blob or "repeat" in route_blob.lower():
        return "seamless_four_way"
    return "generic_flat_pattern"


def normalize_pattern_fission_user_params(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "variation_strength": _normalize_strength(inputs.get("variation_strength") or inputs.get("strength") or inputs.get("bili")),
        "semantic_swap": _as_bool(inputs.get("semantic_swap") or inputs.get("semanticSwap"), default=False),
        "quality": _quality(inputs.get("quality")),
        "count": 1,
        "size": _first_text(inputs.get("size"), DEFAULT_SIZE),
        "output_format": _first_text(inputs.get("output_format"), inputs.get("outputFormat"), DEFAULT_OUTPUT_FORMAT),
        "output_compression": _as_int(inputs.get("output_compression") or inputs.get("outputCompression")),
        "extra_prompt": _first_text(inputs.get("prompt"), inputs.get("extra_prompt"), inputs.get("user_prompt"), ""),
    }


def _normalize_legacy_pattern_fission_user_params(inputs: dict[str, Any]) -> dict[str, Any]:
    strength = _choice(inputs.get("variation_strength") or inputs.get("strength") or inputs.get("bili"), {"low", "medium", "high"}, "high")
    return {
        "variation_strength": strength,
        "quality": _quality(inputs.get("quality")),
        "count": 1,
        "preserve_layout": True,
        "preserve_border": "auto",
        "preserve_count_density": True,
        "style_shift": "standard",
        "size": _first_text(inputs.get("size"), DEFAULT_SIZE),
        "output_format": _first_text(inputs.get("output_format"), inputs.get("outputFormat"), DEFAULT_OUTPUT_FORMAT),
        "extra_prompt": _first_text(inputs.get("prompt"), inputs.get("extra_prompt"), inputs.get("user_prompt"), ""),
    }


def _audit_compilation(*, prompt: str, route: str) -> dict[str, Any]:
    required_terms = [
        "Motif count delta",
        "Overall density delta",
        "Average motif scale delta",
        "Main palette delta",
        "Background hue/value delta",
        "Semantic swap is disabled",
        "Do not introduce readable text",
    ]
    return {
        "ok": route != "generic_flat_pattern" and len(prompt) <= 2600 and all(term in prompt for term in required_terms),
        "pattern_route": route,
        "prompt_chars": len(prompt),
        "has_all_quant_terms": all(term in prompt for term in required_terms),
        "uses_raw_vl_fission_brief": "fission_brief" in prompt or "VL fission brief" in prompt,
    }


def _extract_motifs(vl_card: dict[str, Any]) -> dict[str, str]:
    motifs = vl_card.get("motifs") if isinstance(vl_card.get("motifs"), dict) else {}
    return {
        "primary": _compact_list(motifs.get("primary", []), 5),
        "secondary": _compact_list(motifs.get("secondary", []), 5),
        "fillers": _compact_list(motifs.get("fillers", []), 5),
        "border": _compact_list(motifs.get("border", []), 4),
    }


def _extract_composition(vl_card: dict[str, Any]) -> dict[str, str]:
    composition = vl_card.get("composition") if isinstance(vl_card.get("composition"), dict) else {}
    return {
        "layout": str(composition.get("layout") or "")[:160],
        "symmetry": str(composition.get("symmetry") or "")[:120],
        "density": str(composition.get("density") or "")[:120],
        "border_logic": str(composition.get("border_logic") or "")[:160],
    }


def _format_vl_card(vl_card: dict[str, Any]) -> str:
    parts = [
        f"- Image type: {_first_text(vl_card.get('image_type'), 'unknown')}",
        f"- Pattern type: {_first_text(vl_card.get('pattern_type'), 'unknown')}",
        f"- Style family: {_first_text(vl_card.get('style_family'), 'unknown')}",
    ]
    for key, label in (("composition", "Composition"), ("motifs", "Motifs"), ("material_style", "Material style"), ("color_palette", "Color palette")):
        block = vl_card.get(key) if isinstance(vl_card.get(key), dict) else {}
        if block:
            parts.append(f"- {label}: {_compact_dict(block)}")
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


def _compact_list(values: Any, limit: int = 6) -> str:
    if not values:
        return ""
    if isinstance(values, str):
        return values[:180]
    if isinstance(values, (int, float)):
        return str(values)
    if isinstance(values, list):
        return ", ".join(str(value)[:80] for value in values[:limit] if str(value).strip())
    return str(values)[:180]


def _looks_like_vl_card(value: dict[str, Any]) -> bool:
    keys = {"image_type", "pattern_type", "composition", "motifs", "material_style", "color_palette"}
    return len(keys.intersection(value)) >= 3


def _legacy_category_key(pattern_type: str) -> str:
    normalized = str(pattern_type or "").strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in LEGACY_CATEGORY_BRIEFS:
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


def _normalize_strength(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized.isdigit():
        number = int(normalized)
        if number <= 40:
            normalized = "conservative"
        elif number <= 75:
            normalized = "same_series"
        else:
            normalized = "creative_same_series"
    return STRENGTH_ALIASES.get(normalized, "same_series")


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


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _trim_empty_tail(values: list[str]) -> list[str]:
    out = list(values)
    while out and not str(out[-1]).strip():
        out.pop()
    return out
