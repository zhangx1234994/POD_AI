from types import SimpleNamespace

from app.services.executors.base import ExecutionContext
from app.services.executors.comfyui import ComfyUIExecutorAdapter


def _make_context(graph: dict):
    workflow = SimpleNamespace(definition={"graph": graph}, extra_metadata={"workflow_key": "duotu_ronghe"})
    executor = SimpleNamespace(base_url="", config={})
    task = SimpleNamespace(user_id="tester")
    return ExecutionContext(task=task, workflow=workflow, executor=executor, payload={})


def test_duotu_ronghe_maps_primary_and_extra_urls_to_three_nodes():
    graph = {
        "422": {"inputs": {"url": ""}},
        "421": {"inputs": {"url": ""}},
        "416": {"inputs": {"url": ""}},
        "379": {"inputs": {"prompt": ""}},
        "372": {"inputs": {"prompt": ""}},
        "89": {"inputs": {"lora_name": "default.safetensors"}},
    }
    context = _make_context(graph)
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_duotu_ronghe_inputs(
        {
            "image_url": "https://example.com/a.png",
            "image_urls": "https://example.com/b.png\nhttps://example.com/c.png",
            "prompt": "fusion prompt",
            "negative_prompt": "no seams",
            "lora": "fusion.safetensors",
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["422"]["url"] == "https://example.com/a.png"
    assert overrides["421"]["url"] == "https://example.com/b.png"
    assert overrides["416"]["url"] == "https://example.com/c.png"
    assert overrides["379"]["prompt"] == "fusion prompt"
    assert overrides["372"]["prompt"] == "no seams"
    assert overrides["89"]["lora_name"] == "fusion.safetensors"


def test_duotu_ronghe_reuses_last_url_when_only_one_extra_image_is_provided():
    graph = {
        "422": {"inputs": {"url": ""}},
        "421": {"inputs": {"url": ""}},
        "416": {"inputs": {"url": ""}},
    }
    context = _make_context(graph)
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_duotu_ronghe_inputs(
        {
            "image_url": "https://example.com/a.png",
            "image_urls": "https://example.com/b.png",
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["422"]["url"] == "https://example.com/a.png"
    assert overrides["421"]["url"] == "https://example.com/b.png"
    assert overrides["416"]["url"] == "https://example.com/b.png"


def test_duotu_ronghe_reuses_primary_when_only_one_image_is_provided():
    graph = {
        "422": {"inputs": {"url": ""}},
        "421": {"inputs": {"url": ""}},
        "416": {"inputs": {"url": ""}},
    }
    context = _make_context(graph)
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_duotu_ronghe_inputs(
        {
            "image_url": "https://example.com/a.png",
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["422"]["url"] == "https://example.com/a.png"
    assert overrides["421"]["url"] == "https://example.com/a.png"
    assert overrides["416"]["url"] == "https://example.com/a.png"
