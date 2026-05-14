from __future__ import annotations

from app.schemas.business import BusinessRunCreateRequest
from app.services.business_runs import BusinessRunService
from app.services.pattern_fission_prompt import LEGACY_TEMPLATE_ID, TEMPLATE_ID, compile_pattern_fission_prompt


def _vl_summary() -> dict:
    return {
        "vlCard": {
            "image_type": "flat decorative pattern",
            "pattern_type": "complex_floral_bird_tapestry",
            "style_family": "antique textile",
            "composition": {"layout": "mirrored", "density": "dense"},
            "motifs": {"primary": ["bird", "flower"], "secondary": ["vine"]},
            "material_style": {"rendering": "hand painted", "texture": "aged pigment"},
            "color_palette": {"main_colors": ["muted blue", "cream"], "color_relationship": "low saturation"},
            "preserve_locks": ["preserve mirrored composition"],
            "change_targets": ["redesign birds and floral ornaments"],
            "forbidden_drifts": ["do not become a realistic scene"],
            "fission_brief": "保持古典织物系列感，重绘鸟和花叶。",
        }
    }


def test_pattern_fission_prompt_compiler_maps_business_params_to_openai_params() -> None:
    compiled = compile_pattern_fission_prompt(
        vl_summary=_vl_summary(),
        user_inputs={
            "variation_strength": "same_series",
            "quality": "premium",
            "count": 2,
            "prompt": "增加节庆感，但不要加入文字。",
        },
    )

    assert compiled.template_id == TEMPLATE_ID
    assert compiled.route_id == "OPENAI_GPT_IMAGE2_PATTERN_CONTROLLED_V2"
    assert compiled.pattern_type == "complex_tapestry_bordered"
    assert compiled.openai_params["model"] == "gpt-image-2"
    assert compiled.openai_params["quality"] == "high"
    assert compiled.openai_params["size"] == "auto"
    assert compiled.openai_params["output_format"] == "png"
    assert compiled.openai_params["n"] == 1
    assert "Motif count delta must be <= 15%" in compiled.compiled_prompt
    assert "Semantic swap is disabled" in compiled.compiled_prompt
    assert "fission_brief" not in compiled.compiled_prompt
    assert compiled.user_params["audit"]["ok"] is True
    assert "增加节庆感" in compiled.compiled_prompt


def test_business_fission_payload_uses_pattern_fission_compiler(monkeypatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()

    payload = BusinessRunCreateRequest(
        imageUrl="https://example.com/source.png",
        inputs={
            "variation_strength": "same_series",
            "quality": "production",
            "count": 3,
            "prompt": "保留系列感，元素要明显变化。",
        },
    )
    recipe = {
        "vlAssist": {
            "enabled": True,
            "applyToPrimary": {"compiler": TEMPLATE_ID, "overwrite": True},
        },
        "promptCompiler": {"id": TEMPLATE_ID},
    }
    ability_payload = service._build_ability_payload(
        capability_key="fission",
        payload=payload,
        image_url="https://example.com/source.png",
        route_info={"version": "gpt-image2-vl-v2"},
        trace_context={"traceId": "trace-test"},
        recipe=recipe,
        vl_summary=_vl_summary(),
    )

    assert ability_payload.inputs["model"] == "gpt-image-2"
    assert ability_payload.inputs["quality"] == "medium"
    assert ability_payload.inputs["size"] == "auto"
    assert ability_payload.inputs["n"] == 1
    assert "count" not in ability_payload.inputs
    assert "preserve_layout" not in ability_payload.inputs
    assert "preserve_border" not in ability_payload.inputs
    assert "preserve_count_density" not in ability_payload.inputs
    assert "style_shift" not in ability_payload.inputs
    assert ability_payload.inputs["prompt_template_id"] == TEMPLATE_ID
    assert ability_payload.inputs["route_id"] == "OPENAI_GPT_IMAGE2_PATTERN_CONTROLLED_V2"
    assert ability_payload.inputs["pattern_type"] == "complex_tapestry_bordered"
    assert ability_payload.inputs["vl_card"]["fission_brief"] == "保持古典织物系列感，重绘鸟和花叶。"
    assert ability_payload.inputs["pattern_fission_user_params"]["route_version"] == "pattern_fission_controlled_v2.0"
    assert ability_payload.inputs["pattern_fission_user_params"]["audit"]["ok"] is True
    assert "保留系列感" in ability_payload.inputs["prompt"]


def test_pattern_fission_prompt_keeps_legacy_template_available() -> None:
    compiled = compile_pattern_fission_prompt(
        vl_summary=_vl_summary(),
        user_inputs={"variation_strength": "high", "quality": "preview"},
        template_id=LEGACY_TEMPLATE_ID,
    )

    assert compiled.template_id == LEGACY_TEMPLATE_ID
    assert compiled.route_id == "OPENAI_GPT_IMAGE2_PATTERN_V21"
    assert compiled.pattern_type == "complex_floral_bird_tapestry"
    assert "Business fission brief" not in compiled.compiled_prompt


def test_recipe_step_inputs_read_nested_config_defaults(monkeypatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()

    assert service._extract_step_inputs({"config": {"defaultInputs": {"provider": "volcengine_vl", "prompt": "json only"}}}) == {
        "provider": "volcengine_vl",
        "prompt": "json only",
    }
