from __future__ import annotations

from app.constants.abilities import OPENAI_IMAGE_ABILITIES


def test_openai_gpt_image_2_generation_ability_is_seeded() -> None:
    ability = OPENAI_IMAGE_ABILITIES["gpt_image_2_generate"]
    fields = {item["name"]: item for item in ability["input_schema"]["fields"]}

    assert ability["endpoint"] == "/v1/images/generations"
    assert ability["defaults"]["model"] == "gpt-image-2"
    assert ability["metadata"]["executor_type"] == "vendor_api"
    assert ability["metadata"]["executor_tag"] == "global-egress"
    assert ability["metadata"]["api_type"] == "image_generation"
    assert fields["prompt"]["required"] is True
    assert "transparent" not in {option["value"] for option in fields["background"]["options"]}


def test_openai_gpt_image_2_edit_ability_keeps_mask_without_unsupported_fidelity() -> None:
    ability = OPENAI_IMAGE_ABILITIES["gpt_image_2_edit"]
    fields = {item["name"]: item for item in ability["input_schema"]["fields"]}

    assert ability["endpoint"] == "/v1/images/edits"
    assert ability["defaults"]["size"] == "auto"
    assert ability["metadata"]["api_type"] == "image_edit"
    assert ability["metadata"]["seed_version"] == 3
    assert ability["metadata"]["supports_mask"] is True
    assert "mask_url" in fields
    assert "image_urls" in fields
    assert fields["size"]["default"] == "auto"
    assert "input_fidelity" not in fields
    assert "transparent" not in {option["value"] for option in fields["background"]["options"]}
