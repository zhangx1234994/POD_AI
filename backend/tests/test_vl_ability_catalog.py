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


def test_vl_fission_components_are_seeded_as_atomic_capabilities() -> None:
    control_card = VL_ABILITIES["fission_control_card"]
    evaluation = VL_ABILITIES["fission_generated_image_evaluate"]
    seeds = {item.id: item for item in DEFAULT_ABILITY_SEEDS}

    assert control_card["defaults"]["provider"] == "volcengine_vl"
    assert control_card["metadata"]["component_key"] == "fission_control_card"
    assert control_card["metadata"]["output_schema"] == "fission_control_card_v1"
    assert "prompt_main" in control_card["defaults"]["prompt"]
    assert seeds["vl_fission_control_card"].provider == "vl"

    eval_fields = {item["name"]: item for item in evaluation["input_schema"]["fields"]}
    assert evaluation["metadata"]["api_type"] == "generated_image_evaluation"
    assert evaluation["metadata"]["coze_workflow_id"] == "7632187670952673280"
    assert eval_fields["original_image"]["required"] is True
    assert eval_fields["generated_image"]["required"] is True
    assert seeds["vl_fission_generated_image_evaluate"].category == "image_quality_evaluation"
