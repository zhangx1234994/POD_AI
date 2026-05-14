from __future__ import annotations

import json

from app.services.ability_invocation import AbilityInvocationService
from app.models.integration import BusinessRunStep
from app.services.business_runs import BusinessRunService
from app.services.fission_image_evaluation import normalize_generated_image_eval_result


def test_generated_image_eval_normalizes_refission_decision() -> None:
    payload = {
        "output": json.dumps(
            {
                "eval_json": {
                    "final_verdict": "needs_repair",
                    "overall_score": 72,
                    "scores": {"shape": 4, "material": 3, "scale": 3, "logic": 4},
                    "problem_tags": ["motif_density_shift"],
                },
                "route_json": {
                    "route_action": "regenerate",
                    "problem_tags": ["color_ratio_shift"],
                    "reason_summary": "元素密度和颜色比例有漂移，需要重新裂变。",
                },
            },
            ensure_ascii=False,
        )
    }

    result = normalize_generated_image_eval_result(payload)

    assert result["decision"] == "needs_refission"
    assert result["score"] == 72
    assert result["scores"] == {"shape": 4, "material": 3, "scale": 3, "logic": 4}
    assert result["problem_tags"] == ["color_ratio_shift", "motif_density_shift"]
    assert result["next_action"]["type"] == "refission_repeat"


def test_generated_image_eval_hard_fail_rejects() -> None:
    result = normalize_generated_image_eval_result(
        {
            "eval_json": {"sanity_eval": {"hard_fail": True}, "final_verdict": "pass"},
            "route_json": {"route_action": "pass"},
        }
    )

    assert result["decision"] == "reject"
    assert result["next_action"] == {"type": "reject"}


def test_vl_control_card_is_preserved_for_business_compilers() -> None:
    service = AbilityInvocationService()
    structured = service._coerce_vl_structured_json(
        {
            "route_mode": "fission_general",
            "pattern_type": "multi_element_pattern",
            "profile_hint": "pattern_default_v1",
            "prompt_main": "保留主体花纹结构，做多元素裂变。",
            "prompt_control": "保持疏密、边框和颜色比例，不要只换色。",
            "control_cards": {"shape_card": {}, "material_card": {}, "scale_card": {}, "noise_card": {}},
        },
        provider="volcengine_vl",
        image_url="https://example.com/source.png",
    )

    assert structured["fissionControlCard"]["prompt_main"] == "保留主体花纹结构，做多元素裂变。"
    assert structured["promptMain"] == "保留主体花纹结构，做多元素裂变。"
    assert structured["promptControl"] == "保持疏密、边框和颜色比例，不要只换色。"
    assert structured["promptCard"]["positivePrompt"] == "保留主体花纹结构，做多元素裂变。"


def test_v4_vl_control_card_uses_image_desc_as_prompt_control() -> None:
    service = AbilityInvocationService()
    structured = service._coerce_vl_structured_json(
        {
            "prompt_main": "保留原图对象类别，做对象级裂变。",
            "image_desc": "保持重复布局、元素数量级、间距节奏和原图配色。",
            "pattern_risk_type": "separable_cartoon_icon_repeat",
            "density_risk_level": "medium",
            "palette_card": {"dominant_colors": ["cream", "pastel blue"]},
        },
        provider="volcengine_vl",
        image_url="https://example.com/source.png",
    )

    assert structured["fissionControlCard"]["prompt_main"] == "保留原图对象类别，做对象级裂变。"
    assert structured["promptMain"] == "保留原图对象类别，做对象级裂变。"
    assert structured["promptControl"] == "保持重复布局、元素数量级、间距节奏和原图配色。"
    assert structured["promptCard"]["imageDesc"] == "保持重复布局、元素数量级、间距节奏和原图配色。"


def test_v4_vl_control_card_is_extracted_from_prompt_card_image_desc() -> None:
    service = AbilityInvocationService()
    card = {
        "prompt_main": "童趣足球满版印花，保持布局和柔和配色。",
        "image_desc": "浅奶油底色，儿童、足球和爱心重复排列。",
        "pattern_risk_type": "separable_cartoon_icon_repeat",
        "density_risk_level": "medium",
        "palette_card": {"dominant_colors": ["cream", "pastel blue"]},
    }

    structured = service._coerce_vl_structured_json(
        {
            "summary": "",
            "promptCard": {
                "positivePrompt": "",
                "imageDesc": json.dumps(card, ensure_ascii=False),
                "rawText": json.dumps(card, ensure_ascii=False),
            },
        },
        provider="volcengine_vl",
        image_url="https://example.com/source.png",
    )

    assert structured["fissionControlCard"]["prompt_main"] == "童趣足球满版印花，保持布局和柔和配色。"
    assert structured["promptMain"] == "童趣足球满版印花，保持布局和柔和配色。"
    assert structured["promptControl"] == "浅奶油底色，儿童、足球和爱心重复排列。"


def test_direct_comfyui_v4_control_card_compiles_object_prompt_and_locks() -> None:
    service = AbilityInvocationService()
    params = {
        "prompt": "业务额外要求：保留童趣运动主题。",
        "bili": "80%",
        "reference_lock": 0.34,
        "color_lock": 0.9,
        "profile": "pattern_risk_routed_v4",
        "vl_result": {
            "prompt_main": "童趣足球满版印花，保持原图布局和配色。",
            "image_desc": "浅奶油底色，儿童、足球、爱心和圆点重复排列。",
            "pattern_risk_type": "separable_cartoon_icon_repeat",
            "object_variation_level": "high",
            "recommended_reference_lock": 0.42,
            "recommended_color_lock": 0.9,
            "palette_card": {"dominant_colors": ["cream", "pastel blue"]},
        },
    }

    service._apply_comfyui_fission_control_card(params)

    assert "High object-level fission" in params["prompt"]
    assert "业务额外要求" in params["prompt"]
    assert params["image_desc"].startswith("浅奶油底色")
    assert "Preserve palette, density, motif scale" in params["image_desc"]
    assert params["reference_lock"] == "0.34"
    assert params["ipadapter_weight"] == "0.34"
    assert params["color_lock"] == "0.9"
    assert params["colormatch_strength"] == "0.9"


def test_direct_comfyui_v4_control_card_reads_nested_image_desc_json() -> None:
    service = AbilityInvocationService()
    card = {
        "prompt_main": "童趣足球满版印花，保持原图布局和配色。",
        "image_desc": "浅奶油底色，儿童、足球、爱心和圆点重复排列。",
        "pattern_risk_type": "separable_cartoon_icon_repeat",
        "object_variation_level": "medium",
        "recommended_reference_lock": 0.42,
        "recommended_color_lock": 0.9,
        "palette_card": {"dominant_colors": ["cream", "pastel blue"]},
    }
    params = {
        "bili": "100",
        "reference_lock": 0.34,
        "color_lock": 0.9,
        "profile": "pattern_risk_routed_v4",
        "vl_result": {
            "style": "",
            "imageDesc": json.dumps(card, ensure_ascii=False) + "\nColor control priority: old suffix",
        },
    }

    service._apply_comfyui_fission_control_card(params)

    assert "High object-level fission" in params["prompt"]
    assert "童趣足球满版印花" in params["prompt"]
    assert not params["image_desc"].lstrip().startswith("{")
    assert params["reference_lock"] == "0.34"
    assert params["ipadapter_weight"] == "0.34"


def test_business_summary_preserves_v4_vl_control_card() -> None:
    card = {
        "prompt_main": "保留原图对象类别，做对象级裂变。",
        "image_desc": "保持重复布局、元素数量级、间距节奏和原图配色。",
        "pattern_risk_type": "separable_cartoon_icon_repeat",
        "density_risk_level": "medium",
        "palette_card": {"dominant_colors": ["cream", "pastel blue"]},
    }
    step = BusinessRunStep(result_payload={"texts": [json.dumps(card, ensure_ascii=False)]})
    service = object.__new__(BusinessRunService)

    summary = service._build_step_result_summary(step)

    assert summary is not None
    assert summary["fissionControlCard"]["prompt_main"] == "保留原图对象类别，做对象级裂变。"
    assert summary["positivePrompt"] == "保留原图对象类别，做对象级裂变。"
    assert summary["imageDesc"] == "保持重复布局、元素数量级、间距节奏和原图配色。"
    assert summary["patternRiskType"] == "separable_cartoon_icon_repeat"


def test_business_summary_extracts_v4_card_from_prompt_card_image_desc() -> None:
    card = {
        "prompt_main": "童趣足球满版印花，保持原图布局和配色。",
        "image_desc": "浅奶油底色，儿童、足球、爱心和圆点重复排列。",
        "pattern_risk_type": "separable_cartoon_icon_repeat",
        "density_risk_level": "medium",
        "palette_card": {"dominant_colors": ["cream", "pastel blue"]},
    }
    step = BusinessRunStep(
        result_payload={"texts": [json.dumps({"promptCard": {"imageDesc": json.dumps(card, ensure_ascii=False)}})]}
    )
    service = object.__new__(BusinessRunService)

    summary = service._build_step_result_summary(step)

    assert summary is not None
    assert summary["fissionControlCard"]["prompt_main"] == "童趣足球满版印花，保持原图布局和配色。"
    assert summary["positivePrompt"] == "童趣足球满版印花，保持原图布局和配色。"
    assert summary["imageDesc"] == "浅奶油底色，儿童、足球、爱心和圆点重复排列。"
