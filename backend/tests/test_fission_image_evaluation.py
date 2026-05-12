from __future__ import annotations

import json

from app.services.ability_invocation import AbilityInvocationService
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
