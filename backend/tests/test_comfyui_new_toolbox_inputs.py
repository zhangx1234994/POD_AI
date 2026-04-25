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
    assert overrides == {"5": {"url": "https://example.com/input.png"}}
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


def test_qwen2512_print_shape_text_enhance_maps_url_prompt_and_bili_to_denoise():
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
        "27": {"seed": 424242, "steps": 8, "cfg": 1.0, "denoise": 0.75},
    }
    assert context.workflow.definition["output_node_ids"] == ["29"]
    assert context.workflow.definition["_max_output_images"] == 1


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
    assert overrides["12"] == {"width": 1800, "height": 1800}
    assert overrides["13"] == {
        "text1": "new pattern fission prompt",
        "text2": "dense repeating floral pattern with restrained fillers",
    }
    assert overrides["20"] == {"weight": 0.25}
    assert overrides["21"] == {"cfg": 1.0}
    assert isinstance(overrides["22"]["noise_seed"], int)
    assert overrides["22"]["noise_seed"] > 0
    assert overrides["24"] == {"steps": 8, "denoise": 0.59}
    assert overrides["27"] == {"batch_size": 1}
    assert overrides["30"] == {"method": "mkl", "strength": 0.2}
    assert context.workflow.definition["output_node_ids"] == ["31"]
    assert context.workflow.definition["_max_output_images"] == 1
