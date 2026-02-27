from types import SimpleNamespace

from app.services.executors.base import ExecutionContext
from app.services.executors.comfyui import ComfyUIExecutorAdapter


def _make_context(graph: dict):
    workflow = SimpleNamespace(definition={"graph": graph}, extra_metadata={"workflow_key": "sifang_lianxu"})
    executor = SimpleNamespace(base_url="", config={})
    task = SimpleNamespace(user_id="tester")
    return ExecutionContext(task=task, workflow=workflow, executor=executor, payload={})


def test_seamless_overrides_use_url_branch_only_when_graph_has_legacy_node():
    graph = {
        "114": {"inputs": {"value": ""}},
        "96": {"inputs": {"url": ""}},
        "64": {"inputs": {"image": ["104", 0]}},
        "94": {"inputs": {"image": ["104", 0]}},
        "102": {"inputs": {"image": ["104", 0]}},
        "106": {"inputs": {"image": "legacy.png"}},
    }
    context = _make_context(graph)
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_seamless_inputs({"image_url": "https://example.com/input.png"}, context)

    assert error is None
    assert overrides is not None
    assert overrides["114"]["value"] == "https://example.com/input.png"
    assert overrides["96"]["url"] == "https://example.com/input.png"
    assert overrides["64"]["image"] == ["96", 0]
    assert overrides["94"]["image"] == ["96", 0]
    assert overrides["102"]["image"] == ["96", 0]
    assert "106" not in overrides
    assert context.workflow.definition["_max_output_images"] == 1
