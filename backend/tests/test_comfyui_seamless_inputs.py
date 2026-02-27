from types import SimpleNamespace

from app.services.executors.base import ExecutionContext
from app.services.executors.comfyui import ComfyUIExecutorAdapter


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
