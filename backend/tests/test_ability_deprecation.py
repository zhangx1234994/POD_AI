from __future__ import annotations

from app.services.ability_deprecation import enrich_metadata_with_deprecation, resolve_ability_deprecation
from app.services.ability_presentation import is_ability_visible_for_surface


def test_resolve_deprecation_defaults_for_deprecated_release_status() -> None:
    payload = resolve_ability_deprecation(
        status="active",
        metadata={
            "governance": {"release_status": "deprecated"},
            "deprecation": {"replacement_capability_key": "flux2_klein_9b_outpaint", "reason": "统一扩图入口"},
        },
    )

    assert payload == {
        "is_deprecated": True,
        "replacement_ability_id": None,
        "replacement_capability_key": "flux2_klein_9b_outpaint",
        "replacement_display_name": None,
        "reason": "统一扩图入口",
        "retirement_mode": "hide_public",
    }


def test_enrich_deprecation_preserves_clean_payload() -> None:
    enriched = enrich_metadata_with_deprecation(
        {"model_id": "seedream-4.5"},
        status="active",
        deprecation_override={
            "replacement_display_name": "统一扩图",
            "retirement_mode": "internal_only",
            "reason": "业务侧统一从新版扩图进入",
        },
    )

    assert enriched["model_id"] == "seedream-4.5"
    assert enriched["deprecation"] == {
        "replacement_display_name": "统一扩图",
        "reason": "业务侧统一从新版扩图进入",
        "retirement_mode": "internal_only",
    }


def test_deprecated_ability_is_hidden_even_if_presentation_visible() -> None:
    metadata = {
        "governance": {"scopes": ["coze", "client"], "release_status": "deprecated"},
        "presentation": {"visible": True, "sort_order": 10},
        "deprecation": {"retirement_mode": "hide_public", "replacement_capability_key": "new_outpaint"},
    }

    assert not is_ability_visible_for_surface(
        status="active",
        provider="comfyui",
        category="image_generation",
        capability_key="old_outpaint",
        ability_type="comfyui",
        metadata=metadata,
        surface="coze",
    )
