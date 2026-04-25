from __future__ import annotations

from app.constants.abilities import VL_ABILITIES
from app.services.ability_seed import DEFAULT_ABILITY_SEEDS


def test_vl_analyze_image_ability_is_seeded_as_atomic_capability() -> None:
    ability = VL_ABILITIES["analyze_image"]
    fields = {item["name"]: item for item in ability["input_schema"]["fields"]}
    provider_options = {item["value"] for item in fields["provider"]["options"]}
    seed = next(item for item in DEFAULT_ABILITY_SEEDS if item.id == "vl_analyze_image")

    assert ability["metadata"]["api_type"] == "vl_analyze_image"
    assert ability["metadata"]["structured_output"] is True
    assert provider_options == {"volcengine_vl", "coze_vl"}
    assert fields["image_url"]["required"] is True
    assert seed.provider == "vl"
    assert seed.status == "active"
    assert seed.category == "vision_language"
