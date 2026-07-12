from __future__ import annotations

from app.constants.abilities import OPENAI_IMAGE_ABILITIES, PACKY_IMAGE_ABILITIES


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


def test_openai_gpt_image_2_batch_abilities_are_separate_from_realtime() -> None:
    generation = OPENAI_IMAGE_ABILITIES["gpt_image_2_generate"]
    generation_batch = OPENAI_IMAGE_ABILITIES["gpt_image_2_generate_batch"]
    edit = OPENAI_IMAGE_ABILITIES["gpt_image_2_edit"]
    edit_batch = OPENAI_IMAGE_ABILITIES["gpt_image_2_edit_batch"]

    assert generation["metadata"]["execution_mode"] == "sync_then_store"
    assert edit["metadata"]["execution_mode"] == "sync_then_store"
    assert generation_batch["metadata"]["execution_mode"] == "batch_submit_poll"
    assert edit_batch["metadata"]["execution_mode"] == "batch_submit_poll"
    assert generation_batch["defaults"]["quality"] == "low"
    assert edit_batch["defaults"]["quality"] == "low"
    assert "batch_requests" in {item["name"] for item in generation_batch["input_schema"]["fields"]}
    assert "batch_requests" in {item["name"] for item in edit_batch["input_schema"]["fields"]}


def test_openai_gpt_image_2_edit_ability_keeps_mask_without_unsupported_fidelity() -> None:
    ability = OPENAI_IMAGE_ABILITIES["gpt_image_2_edit"]
    fields = {item["name"]: item for item in ability["input_schema"]["fields"]}

    assert ability["endpoint"] == "/v1/images/edits"
    assert ability["defaults"]["size"] == "auto"
    assert ability["metadata"]["api_type"] == "image_edit"
    assert ability["metadata"]["seed_version"] == 4
    assert ability["metadata"]["timeoutSeconds"] == 420
    assert ability["metadata"]["supports_mask"] is True
    assert "mask_url" in fields
    assert "image_urls" in fields
    assert fields["size"]["default"] == "auto"
    assert "input_fidelity" not in fields
    assert "transparent" not in {option["value"] for option in fields["background"]["options"]}


def test_packy_gpt_image_2_edit_is_single_image_openai_compatible() -> None:
    ability = PACKY_IMAGE_ABILITIES["gpt_image_2_edit"]
    fields = {item["name"]: item for item in ability["input_schema"]["fields"]}

    assert ability["endpoint"] == "/v1/images/edits"
    assert ability["defaults"]["multipart_image_field"] == "image"
    assert ability["defaults"]["max_input_images"] == 1
    assert ability["metadata"]["provider_family"] == "openai_compatible"
    assert ability["metadata"]["supports_multiple_images"] is False
    assert ability["metadata"]["max_input_images"] == 1
    assert ability["metadata"]["multipart_image_field"] == "image"
    assert "image_url" in fields
    assert "image_urls" not in fields
