from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.constants.abilities import DEFAULT_VOLCENGINE_VL_ABILITY_ID, DEFAULT_VOLCENGINE_VL_MODEL_ID, VL_ABILITIES
from app.models.integration import Ability
from app.schemas import abilities as ability_schemas
from app.services.ability_invocation import AbilityInvocationService, _ImageBundle, _InvocationContext
from app.services.ability_seed import DEFAULT_ABILITY_SEEDS


def test_vl_analyze_image_ability_is_seeded_as_atomic_capability() -> None:
    ability = VL_ABILITIES["analyze_image"]
    fields = {item["name"]: item for item in ability["input_schema"]["fields"]}
    provider_options = {item["value"] for item in fields["provider"]["options"]}
    seed = next(item for item in DEFAULT_ABILITY_SEEDS if item.id == "vl_analyze_image")

    assert ability["metadata"]["api_type"] == "vl_analyze_image"
    assert ability["metadata"]["structured_output"] is True
    assert ability["metadata"]["provider_ability_map"]["volcengine_vl"] == DEFAULT_VOLCENGINE_VL_ABILITY_ID
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
    assert control_card["metadata"]["output_schema"] == "fission_control_card_v2"
    assert control_card["metadata"]["provider_ability_map"]["volcengine_vl"] == DEFAULT_VOLCENGINE_VL_ABILITY_ID
    assert "prompt_main" in control_card["defaults"]["prompt"]
    assert "palette_card" in control_card["defaults"]["prompt"]
    assert seeds["vl_fission_control_card"].provider == "vl"

    eval_fields = {item["name"]: item for item in evaluation["input_schema"]["fields"]}
    assert evaluation["metadata"]["api_type"] == "generated_image_evaluation"
    assert evaluation["metadata"]["coze_workflow_id"] == "7632187670952673280"
    assert eval_fields["original_image"]["required"] is True
    assert eval_fields["generated_image"]["required"] is True
    assert seeds["vl_fission_generated_image_evaluate"].category == "image_quality_evaluation"


def test_default_volcengine_vl_ability_uses_seed_2_lite_model() -> None:
    seed = next(item for item in DEFAULT_ABILITY_SEEDS if item.id == DEFAULT_VOLCENGINE_VL_ABILITY_ID)

    assert seed.display_name == "火山 · Doubao-Seed-2.0-lite VL"
    assert seed.default_params["model"] == DEFAULT_VOLCENGINE_VL_MODEL_ID
    assert seed.metadata["model_id"] == DEFAULT_VOLCENGINE_VL_MODEL_ID
    assert seed.metadata["supports_vision"] is True


def test_vl_provider_ability_resolution_is_metadata_driven() -> None:
    service = AbilityInvocationService()

    assert (
        service._resolve_vl_provider_ability_id(
            {"provider_ability_map": {"volcengine_vl": "volcengine_custom_vl"}},
            "volcengine_vl",
        )
        == "volcengine_custom_vl"
    )
    assert service._resolve_vl_provider_ability_id({}, "volcengine_vl") == DEFAULT_VOLCENGINE_VL_ABILITY_ID


def test_vendor_api_rate_limit_result_is_retryable() -> None:
    service = AbilityInvocationService()
    result = {
        "status": "failed",
        "metadata": {
            "vendorError": {
                "code": "VENDOR_API_RATE_LIMITED",
                "message": "System protection triggered by request burst. Request id: xxx",
                "retryable": True,
            }
        },
    }

    assert service._is_retryable_vendor_api_result(result) is True
    assert service._is_retryable_vendor_api_result({"status": "running"}) is False


def test_vl_provider_image_download_failure_surfaces_as_400(monkeypatch) -> None:
    service = AbilityInvocationService()
    ability = Ability(
        id="vl_text2img_prompt_draft",
        provider="vl",
        capability_key="text2img_prompt_draft",
        display_name="VL draft",
        status="active",
        category="vision_language",
        default_params={},
        input_schema={},
        extra_metadata={
            "provider_ability_map": {"volcengine_vl": DEFAULT_VOLCENGINE_VL_ABILITY_ID},
            "default_provider": "volcengine_vl",
        },
    )

    def fake_invoke(**_kwargs):
        return ability_schemas.AbilityInvokeResponse(
            abilityId=DEFAULT_VOLCENGINE_VL_ABILITY_ID,
            provider="volcengine",
            status="failed",
            requestId="provider_failed",
            metadata={
                "vendorError": {
                    "message": "Error while downloading: https://example.com/missing.png, status code: 404"
                }
            },
        )

    monkeypatch.setattr(service, "invoke", fake_invoke)

    with pytest.raises(HTTPException) as exc_info:
        service._invoke_vl(
            ability,
            {"provider": "volcengine_vl"},
            _ImageBundle(image_url="https://example.com/missing.png", image_base64=None, image_list=[]),
            _InvocationContext(
                request_id="parent_request",
                source="business:text_fission_prompt",
                user=None,
                payload=ability_schemas.AbilityInvokeRequest(),
            ),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "VL_IMAGE_UNREACHABLE"
