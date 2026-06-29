from types import SimpleNamespace

from app.services.executors.base import ExecutionContext
from app.services.executors.comfyui import ComfyUIExecutorAdapter, SEAMLESS_STABLE_SEED


def _make_context(graph: dict):
    workflow = SimpleNamespace(definition={"graph": graph}, extra_metadata={"workflow_key": "sifang_lianxu"})
    executor = SimpleNamespace(base_url="", config={})
    task = SimpleNamespace(user_id="tester")
    return ExecutionContext(task=task, workflow=workflow, executor=executor, payload={})


def test_seamless_overrides_keep_mask_node_104_and_only_replace_source_url():
    graph = {
        "114": {"inputs": {"value": ""}},
        "96": {"inputs": {"url": ""}},
        "64": {"inputs": {"image": ["104", 0]}},
        "102": {"inputs": {"image": ["104", 0]}},
    }
    context = _make_context(graph)
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_seamless_inputs({"image_url": "https://example.com/input.png"}, context)

    assert error is None
    assert overrides is not None
    assert overrides["114"]["value"] == "https://example.com/input.png"
    assert overrides["96"]["url"].startswith("https://example.com/input.png#podi_cb=")
    assert overrides["102"]["image"] == ["96", 0]
    assert "64" not in overrides
    assert context.workflow.definition["_max_output_images"] == 1


def test_seamless_pattern_type_aliases_map_to_expected_boolean():
    context = _make_context({"97": {"inputs": {"boolean": True}}})
    adapter = ComfyUIExecutorAdapter()

    twoway, err1 = adapter._build_seamless_inputs(
        {"image_url": "https://example.com/input.png", "patternType": "二方连续"},
        context,
    )
    seamless, err2 = adapter._build_seamless_inputs(
        {"image_url": "https://example.com/input.png", "patternType": "four-way"},
        context,
    )

    assert err1 is None and err2 is None
    assert twoway is not None and seamless is not None
    assert twoway["97"]["boolean"] is False
    assert seamless["97"]["boolean"] is True


def test_seamless_uses_stable_seed_when_caller_does_not_provide_seed():
    adapter = ComfyUIExecutorAdapter()
    graph = {
        "4": {"class_type": "KSampler", "inputs": {"seed": 1}},
        "22": {"class_type": "RandomNoise", "inputs": {"noise_seed": 2}},
    }

    adapter._ensure_sampler_seed(graph, {}, workflow_key="sifang_lianxu")

    assert graph["4"]["inputs"]["seed"] == SEAMLESS_STABLE_SEED
    assert graph["22"]["inputs"]["noise_seed"] == SEAMLESS_STABLE_SEED


def test_seamless_respects_explicit_seed():
    adapter = ComfyUIExecutorAdapter()
    graph = {"4": {"class_type": "KSampler", "inputs": {"seed": 1}}}

    adapter._ensure_sampler_seed(graph, {"seed": 12345}, workflow_key="sifang_lianxu")

    assert graph["4"]["inputs"]["seed"] == 12345


def test_non_seamless_keeps_random_seed_behavior(monkeypatch):
    adapter = ComfyUIExecutorAdapter()
    graph = {"4": {"class_type": "KSampler", "inputs": {"seed": 1}}}
    monkeypatch.setattr("app.services.executors.comfyui.secrets.randbits", lambda _bits: 98765)

    adapter._ensure_sampler_seed(graph, {}, workflow_key="yinhua_tiqu")

    assert graph["4"]["inputs"]["seed"] == 98765


def test_seamless_explicit_custom_size_keeps_tile_boundary_and_resizes_on_store(monkeypatch):
    context = _make_context({"102": {"inputs": {"width": 1024, "height": 1024}}})
    adapter = ComfyUIExecutorAdapter()
    monkeypatch.setattr(adapter, "_load_remote_image_size", lambda _url: (1560, 1880))

    overrides, error = adapter._build_seamless_inputs(
        {"image_url": "https://example.com/input.png", "width": 1566, "height": 1885},
        context,
    )

    assert error is None
    assert overrides is not None
    assert overrides["102"]["width"] == 1560
    assert overrides["102"]["height"] == 1880
    assert context.workflow.definition["_expected_output_width"] == 1566
    assert context.workflow.definition["_expected_output_height"] == 1885
    assert context.workflow.definition["_expected_output_adjust_mode"] == "resize"


def test_pattern_extract_explicit_custom_size_resizes_on_store():
    context = _make_context({"400": {"inputs": {"width": 1024, "height": 1024}}})
    context.workflow.extra_metadata = {"workflow_key": "yinhua_tiqu"}
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_pattern_extract_inputs(
        {"image_url": "https://example.com/input.png", "width": 1566, "height": 1885},
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["400"]["width"] == 1560
    assert overrides["400"]["height"] == 1880
    assert context.workflow.definition["_expected_output_width"] == 1566
    assert context.workflow.definition["_expected_output_height"] == 1885
    assert context.workflow.definition["_expected_output_adjust_mode"] == "resize"


def test_e7_fission_explicit_custom_size_uses_source_ratio_generation_and_cover_crop(monkeypatch):
    context = _make_context({"12": {"inputs": {"width": 1024, "height": 1024}}})
    adapter = ComfyUIExecutorAdapter()
    monkeypatch.setattr(adapter, "_load_remote_image_size", lambda _url: (1560, 1880))

    overrides, error = adapter._build_e7_flux2_liebian_inputs(
        {"image_url": "https://example.com/input.png", "width": 1566, "height": 1885},
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["12"]["width"] == 1568
    assert overrides["12"]["height"] == 1888
    assert overrides["12"]["method"] == "fill / crop"
    assert context.workflow.definition["_expected_output_width"] == 1566
    assert context.workflow.definition["_expected_output_height"] == 1885
    assert context.workflow.definition["_expected_output_adjust_mode"] == "cover_crop"


def test_flux_strong_fission_explicit_custom_size_uses_source_ratio_generation_and_cover_crop(monkeypatch):
    context = _make_context({"12": {"inputs": {"width": 1024, "height": 1024}}})
    context.executor.base_url = "http://comfyui.local"
    adapter = ComfyUIExecutorAdapter()
    monkeypatch.setattr(adapter, "_load_remote_image_size", lambda _url: (1560, 1880))
    monkeypatch.setattr(adapter, "_upload_image_for_comfyui_loadimage", lambda **_kwargs: "input.png")

    overrides, error = adapter._build_flux_strong_hq_softstyle_fission_inputs(
        {"image_url": "https://example.com/input.png", "width": 1566, "height": 1885},
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["12"]["width"] == 1568
    assert overrides["12"]["height"] == 1888
    assert overrides["12"]["method"] == "fill / crop"
    assert context.workflow.definition["_expected_output_width"] == 1566
    assert context.workflow.definition["_expected_output_height"] == 1885
    assert context.workflow.definition["_expected_output_adjust_mode"] == "cover_crop"
