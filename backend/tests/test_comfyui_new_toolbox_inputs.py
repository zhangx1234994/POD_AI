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
    assert overrides == {"141": {"url": "https://example.com/portrait.png"}}
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
