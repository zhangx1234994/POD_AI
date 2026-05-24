from types import SimpleNamespace

from app.services.executors.base import ExecutionContext
from app.services.executors.comfyui import ComfyUIExecutorAdapter


def _make_context(workflow_key: str, graph: dict):
    workflow = SimpleNamespace(definition={"graph": graph}, extra_metadata={"workflow_key": workflow_key})
    executor = SimpleNamespace(base_url="http://127.0.0.1:8188", config={})
    task = SimpleNamespace(user_id="tester")
    return ExecutionContext(task=task, workflow=workflow, executor=executor, payload={})


def test_background_remove_maps_url_and_final_output_node():
    graph = {"5": {"inputs": {"url": "https://"}}, "4": {"inputs": {"filename_prefix": "bg_remove"}}}
    context = _make_context("beijing_koutu", graph)
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_background_remove_inputs(
        {"image_url": "https://example.com/input.png"},
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides["5"] == {"url": "https://example.com/input.png"}
    assert str(overrides["4"]["filename_prefix"]).startswith("bg_remove_")
    assert context.workflow.definition["output_node_ids"] == ["4"]
    assert context.workflow.definition["_max_output_images"] == 1


def test_head_extract_maps_url_and_final_output_node():
    graph = {"141": {"inputs": {"url": "https://"}}, "140": {"inputs": {"filename_prefix": "head_extraction"}}}
    context = _make_context("toubu_kouxiang", graph)
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_head_extract_inputs(
        {"image_url": "https://example.com/portrait.png"},
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides["141"] == {"url": "https://example.com/portrait.png"}
    assert isinstance(overrides.get("134", {}).get("seed"), int)
    assert overrides["134"]["seed"] > 0
    assert context.workflow.definition["output_node_ids"] == ["140"]
    assert context.workflow.definition["_max_output_images"] == 1


def test_flux2_9b_liebian_sifang_maps_only_url_and_prompt():
    graph = {
        "141": {"inputs": {"url": "https://"}},
        "132": {"inputs": {"inStr": "old prompt"}},
        "104": {"inputs": {"base64_data": "keep-me"}},
        "111": {"inputs": {"filename_prefix": "fission_4F"}},
    }
    context = _make_context("flux2_9b_liebian_sifang", graph)
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_flux2_9b_liebian_sifang_inputs(
        {
            "image_url": "https://example.com/pattern.png",
            "prompt": "new fusion prompt",
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides == {
        "141": {"url": "https://example.com/pattern.png"},
        "132": {"inStr": "new fusion prompt"},
    }
    assert context.workflow.definition["graph"]["104"]["inputs"]["base64_data"] == "keep-me"
    assert context.workflow.definition["output_node_ids"] == ["111"]
    assert context.workflow.definition["_max_output_images"] == 1


def test_flux2_klein_9b_outpaint_maps_uploaded_image_expand_and_random_seed():
    graph = {
        "76": {"inputs": {"image": "old.png"}},
        "99": {"inputs": {"seed": 1}},
        "102": {"inputs": {"left": 408, "top": 0, "right": 408, "bottom": 0}},
        "9": {"inputs": {"filename_prefix": "Flux2-Klein"}},
    }
    context = _make_context("flux2_klein_9b_outpaint", graph)
    adapter = ComfyUIExecutorAdapter()
    adapter._upload_image_for_comfyui_loadimage = lambda **_: "staged-input.png"  # type: ignore[method-assign]

    overrides, error = adapter._build_flux2_klein_9b_outpaint_inputs(
        {
            "image_url": "https://example.com/input.png",
            "expand_left": 256,
            "expand_right": 128,
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides == {
        "76": {"image": "staged-input.png"},
        "102": {"left": 256, "right": 128},
        "99": {"seed": overrides["99"]["seed"]},
    }
    assert isinstance(overrides["99"]["seed"], int)
    assert overrides["99"]["seed"] > 0
    assert context.workflow.definition["output_node_ids"] == ["9"]
    assert context.workflow.definition["_max_output_images"] == 1


def test_qwen2512_print_shape_text_enhance_maps_url_prompt_and_bili_to_repaint_denoise():
    graph = {
        "10": {"inputs": {"url": "https://"}},
        "13": {"inputs": {"text1": "old prompt", "text2": ""}},
        "27": {"inputs": {"seed": 1, "steps": 8, "cfg": 1.0, "denoise": 0.75}},
        "29": {"inputs": {"filename_prefix": "08_Qwen2512PrintShape"}},
    }
    context = _make_context("qwen2512_print_shape_text_enhance", graph)
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_qwen2512_print_shape_text_enhance_inputs(
        {
            "image_url": "https://example.com/pattern.png",
            "prompt": "new text enhance prompt",
            "bili": 50,
            "seed": 424242,
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides == {
        "10": {"url": "https://example.com/pattern.png"},
        "13": {"text1": "new text enhance prompt"},
        "27": {"seed": 424242, "steps": 8, "cfg": 1.0, "denoise": 0.625},
    }
    assert context.workflow.definition["output_node_ids"] == ["29"]
    assert context.workflow.definition["_max_output_images"] == 1


def test_qwen2512_text2img_text_allowed_maps_user_editable_prompt_to_text2img_nodes():
    graph = {
        "10": {"inputs": {"text": "__PROMPT__"}},
        "11": {"inputs": {"text": "__NEGATIVE__"}},
        "12": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "19": {"inputs": {"seed": 1, "steps": 8, "cfg": 2.0}},
        "21": {"inputs": {"filename_prefix": "09_qwen_text2img"}},
    }
    context = _make_context("qwen2512_text2img_text_allowed", graph)
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_qwen2512_text2img_text_allowed_inputs(
        {
            "editable_prompt": "flat textile pattern with readable HAPPY SUMMER letters",
            "editable_negative_prompt": "bad anatomy, watermark",
            "width": 1201,
            "height": 999,
            "seed": 12345,
            "steps": 9,
            "cfg": 2.5,
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["10"] == {"text": "flat textile pattern with readable HAPPY SUMMER letters"}
    assert "bad anatomy" in overrides["11"]["text"]
    assert "watermark" in overrides["11"]["text"]
    assert "text" not in overrides["11"]["text"].lower()
    assert "letters" not in overrides["11"]["text"].lower()
    assert overrides["12"] == {"width": 1200, "height": 992, "batch_size": 1}
    assert overrides["19"] == {"seed": 12345, "steps": 9, "cfg": 2.5}
    assert context.workflow.definition["output_node_ids"] == ["21"]
    assert context.workflow.definition["_max_output_images"] == 1
    assert context.workflow.definition["_expected_image_count"] == 1


def test_qwen2512_text2img_text_allowed_requires_prompt():
    context = _make_context("qwen2512_text2img_text_allowed", {})
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_qwen2512_text2img_text_allowed_inputs(
        {"width": 1024},
        context,
        context.workflow.definition,
    )

    assert overrides is None
    assert error == "COMFYUI_PROMPT_REQUIRED"


def test_flux_strong_hq_softstyle_fission_maps_uploaded_image_profile_and_bili():
    graph = {
        "10": {"inputs": {"image": "old.png"}},
        "12": {"inputs": {"width": ["11", 0], "height": ["11", 1]}},
        "13": {"inputs": {"text1": "__PROMPT__", "text2": "__IMAGE_DESC__"}},
        "20": {"inputs": {"weight": "__IPADAPTER_WEIGHT__"}},
        "21": {"inputs": {"cfg": "__CFG__"}},
        "22": {"inputs": {"noise_seed": "__SEED__"}},
        "24": {"inputs": {"steps": "__STEPS__", "denoise": "__DENOISE__"}},
        "27": {"inputs": {"batch_size": "__BATCH_SIZE__"}},
        "30": {"inputs": {"method": "__COLORMATCH_METHOD__", "strength": "__COLORMATCH_STRENGTH__"}},
        "31": {"inputs": {"filename_prefix": "05_FluxStrongHQSoftStyle"}},
    }
    context = _make_context("flux_strong_hq_softstyle_fission", graph)
    adapter = ComfyUIExecutorAdapter()
    adapter._upload_image_for_comfyui_loadimage = lambda **_: "staged-fission.png"  # type: ignore[method-assign]

    overrides, error = adapter._build_flux_strong_hq_softstyle_fission_inputs(
        {
            "image_url": "https://example.com/pattern.png",
            "prompt": "new pattern fission prompt",
            "image_desc": "dense repeating floral pattern with restrained fillers",
            "bili": 90,
            "width": 1800,
            "height": 1800,
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["10"] == {"image": "staged-fission.png"}
    assert overrides["12"] == {"width": 1792, "height": 1792, "method": "fill / crop"}
    assert overrides["13"] == {
        "text1": "new pattern fission prompt",
        "text2": "dense repeating floral pattern with restrained fillers",
    }
    assert overrides["20"] == {"weight": 0.25}
    assert overrides["21"] == {"cfg": 1.0}
    assert isinstance(overrides["22"]["noise_seed"], int)
    assert overrides["22"]["noise_seed"] > 0
    assert overrides["24"] == {"steps": 8, "denoise": 0.765}
    assert overrides["27"] == {"batch_size": 1}
    assert overrides["30"] == {"method": "mkl", "strength": 0.2}
    assert context.workflow.definition["output_node_ids"] == ["31"]


def test_flux_strong_hq_softstyle_fission_control_card_uses_ai_team_bili_mapping():
    graph = {
        "10": {"inputs": {"image": "old.png"}},
        "12": {"inputs": {"width": ["11", 0], "height": ["11", 1]}},
        "13": {"inputs": {"text1": "__PROMPT__", "text2": "__IMAGE_DESC__"}},
        "20": {"inputs": {"weight": "__IPADAPTER_WEIGHT__"}},
        "21": {"inputs": {"cfg": "__CFG__"}},
        "22": {"inputs": {"noise_seed": "__SEED__"}},
        "24": {"inputs": {"steps": "__STEPS__", "denoise": "__DENOISE__"}},
        "27": {"inputs": {"batch_size": "__BATCH_SIZE__"}},
        "30": {"inputs": {"method": "__COLORMATCH_METHOD__", "strength": "__COLORMATCH_STRENGTH__"}},
        "31": {"inputs": {"filename_prefix": "05_FluxStrongHQSoftStyle"}},
    }
    context = _make_context("flux_strong_hq_softstyle_fission", graph)
    adapter = ComfyUIExecutorAdapter()
    adapter._upload_image_for_comfyui_loadimage = lambda **_: "staged-fission.png"  # type: ignore[method-assign]

    overrides, error = adapter._build_flux_strong_hq_softstyle_fission_inputs(
        {
            "image_url": "https://example.com/pattern.png",
            "prompt": "keep pattern logic",
            "image_desc": "control density and material",
            "bili": "50%",
            "bili_mapping": "variation_percent_045_080",
            "width": 2000,
            "height": 2000,
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["12"] == {"width": 2000, "height": 2000, "method": "fill / crop"}
    assert overrides["24"] == {"steps": 8, "denoise": 0.625}
    assert context.workflow.definition["_max_output_images"] == 1


def test_flux_strong_hq_softstyle_fission_explicit_size_uses_target_canvas():
    graph = {
        "10": {"inputs": {"image": "old.png"}},
        "12": {"inputs": {"width": ["11", 0], "height": ["11", 1], "method": "keep proportion"}},
        "13": {"inputs": {"text1": "__PROMPT__", "text2": "__IMAGE_DESC__"}},
        "20": {"inputs": {"weight": "__IPADAPTER_WEIGHT__"}},
        "21": {"inputs": {"cfg": "__CFG__"}},
        "22": {"inputs": {"noise_seed": "__SEED__"}},
        "24": {"inputs": {"steps": "__STEPS__", "denoise": "__DENOISE__"}},
        "27": {"inputs": {"batch_size": "__BATCH_SIZE__"}},
        "30": {"inputs": {"method": "__COLORMATCH_METHOD__", "strength": "__COLORMATCH_STRENGTH__"}},
        "31": {"inputs": {"filename_prefix": "05_FluxStrongHQSoftStyle"}},
    }
    context = _make_context("flux_strong_hq_softstyle_fission", graph)
    adapter = ComfyUIExecutorAdapter()
    adapter._upload_image_for_comfyui_loadimage = lambda **_: "staged-fission.png"  # type: ignore[method-assign]

    overrides, error = adapter._build_flux_strong_hq_softstyle_fission_inputs(
        {
            "image_url": "https://example.com/pattern.png",
            "bili": "80",
            "width": 2925,
            "height": 2009,
            "profile": "pattern_risk_routed_v4",
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["12"] == {"width": 2912, "height": 2000, "method": "fill / crop"}


def test_flux_strong_hq_softstyle_fission_colorlock_uses_v4_risk_route_and_controls():
    graph = {
        "10": {"inputs": {"image": "old.png"}},
        "12": {"inputs": {"width": ["11", 0], "height": ["11", 1]}},
        "13": {"inputs": {"text1": "__PROMPT__", "text2": "__IMAGE_DESC__"}},
        "20": {"inputs": {"weight": "__IPADAPTER_WEIGHT__"}},
        "21": {"inputs": {"cfg": "__CFG__"}},
        "22": {"inputs": {"noise_seed": "__SEED__"}},
        "24": {"inputs": {"steps": "__STEPS__", "denoise": "__DENOISE__"}},
        "27": {"inputs": {"batch_size": "__BATCH_SIZE__"}},
        "30": {"inputs": {"method": "__COLORMATCH_METHOD__", "strength": "__COLORMATCH_STRENGTH__"}},
        "31": {"inputs": {"filename_prefix": "05_FluxStrongHQSoftStyle"}},
    }
    context = _make_context("flux_strong_hq_softstyle_fission", graph)
    adapter = ComfyUIExecutorAdapter()
    adapter._upload_image_for_comfyui_loadimage = lambda **_: "staged-fission.png"  # type: ignore[method-assign]

    overrides, error = adapter._build_flux_strong_hq_softstyle_fission_inputs(
        {
            "image_url": "https://example.com/pattern.png",
            "prompt": "keep palette and redesign motifs",
            "image_desc": "palette_card included",
            "bili": "80%",
            "bili_mapping": "pattern_risk_routed_v4",
            "profile": "pattern_risk_routed_v4",
            "pattern_risk_type": "separable_cartoon_icon_repeat",
            "reference_lock": 0.42,
            "color_lock": 0.90,
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["20"] == {"weight": 0.42}
    assert overrides["21"] == {"cfg": 1.0}
    assert overrides["24"] == {"steps": 8, "denoise": 0.68}
    assert overrides["27"] == {"batch_size": 1}
    assert overrides["30"] == {"method": "mkl", "strength": 0.9}

    overrides_high, error_high = adapter._build_flux_strong_hq_softstyle_fission_inputs(
        {
            "image_url": "https://example.com/pattern.png",
            "prompt": "keep palette and redesign motifs",
            "bili": "120%",
            "bili_mapping": "pattern_risk_routed_v4",
            "profile": "pattern_risk_routed_v4",
            "vl_result": {"pattern_risk_type": "separable_cartoon_icon_repeat"},
        },
        context,
        context.workflow.definition,
    )
    assert error_high is None
    assert overrides_high is not None
    assert overrides_high["24"] == {"steps": 8, "denoise": 0.72}

    overrides_reference_lock, error_reference_lock = adapter._build_flux_strong_hq_softstyle_fission_inputs(
        {
            "image_url": "https://example.com/pattern.png",
            "prompt": "keep palette and redesign motifs",
            "bili": "100%",
            "bili_mapping": "pattern_risk_routed_v4",
            "profile": "pattern_risk_routed_v4",
            "vl_result": {"pattern_risk_type": "separable_cartoon_icon_repeat"},
            "reference_lock": 0.34,
            "ipadapter_weight": 0.42,
        },
        context,
        context.workflow.definition,
    )
    assert error_reference_lock is None
    assert overrides_reference_lock is not None
    assert overrides_reference_lock["20"] == {"weight": 0.34}

    overrides_conservative, error_conservative = adapter._build_flux_strong_hq_softstyle_fission_inputs(
        {
            "image_url": "https://example.com/pattern.png",
            "prompt": "keep palette and redesign motifs",
            "bili": "100%",
            "bili_mapping": "pattern_risk_routed_v4",
            "profile": "pattern_risk_routed_v4",
            "vl_result": {"pattern_risk_type": "small_scatter_high_density"},
        },
        context,
        context.workflow.definition,
    )
    assert error_conservative is None
    assert overrides_conservative is not None
    assert overrides_conservative["24"] == {"steps": 8, "denoise": 0.52}


def test_flux_strong_hq_softstyle_fission_aspect_recompose_uses_fixed_controls():
    graph = {
        "10": {"inputs": {"image": "old.png"}},
        "12": {"inputs": {"width": ["11", 0], "height": ["11", 1]}},
        "13": {"inputs": {"text1": "__PROMPT__", "text2": "__IMAGE_DESC__"}},
        "20": {"inputs": {"weight": "__IPADAPTER_WEIGHT__"}},
        "21": {"inputs": {"cfg": "__CFG__"}},
        "22": {"inputs": {"noise_seed": "__SEED__"}},
        "24": {"inputs": {"steps": "__STEPS__", "denoise": "__DENOISE__"}},
        "27": {"inputs": {"batch_size": "__BATCH_SIZE__"}},
        "30": {"inputs": {"method": "__COLORMATCH_METHOD__", "strength": "__COLORMATCH_STRENGTH__"}},
        "31": {"inputs": {"filename_prefix": "05_FluxStrongHQSoftStyle"}},
    }
    context = _make_context("flux_strong_hq_softstyle_fission", graph)
    adapter = ComfyUIExecutorAdapter()
    adapter._upload_image_for_comfyui_loadimage = lambda **_: "staged-guide.png"  # type: ignore[method-assign]

    overrides, error = adapter._build_flux_strong_hq_softstyle_fission_inputs(
        {
            "image_url": "https://example.com/fission-aspect-guide.png",
            "prompt": "aspect recompose",
            "image_desc": "keep density",
            "width": 1600,
            "height": 896,
            "aspect_recompose_route": "pattern_recompose",
            "aspect_recompose_denoise": 0.68,
            "reference_lock": 0.34,
            "color_lock": 0.95,
            "colormatch_method": "mkl",
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["10"] == {"image": "staged-guide.png"}
    assert overrides["12"] == {"width": 1600, "height": 896, "method": "fill / crop"}
    assert overrides["20"] == {"weight": 0.34}
    assert overrides["24"] == {"steps": 8, "denoise": 0.68}
    assert overrides["30"] == {"method": "mkl", "strength": 0.95}
