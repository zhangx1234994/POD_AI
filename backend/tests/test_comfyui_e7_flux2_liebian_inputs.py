from types import SimpleNamespace

from app.services.executors.base import ExecutionContext
from app.services.executors.comfyui import ComfyUIExecutorAdapter


def _make_context():
    workflow = SimpleNamespace(definition={"graph": {}}, extra_metadata={"workflow_key": "e7_flux2_liebian"})
    executor = SimpleNamespace(base_url="http://127.0.0.1:8188", config={})
    task = SimpleNamespace(user_id="tester")
    return ExecutionContext(task=task, workflow=workflow, executor=executor, payload={})


def test_e7_flux2_liebian_maps_similarity_and_core_inputs():
    context = _make_context()
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_e7_flux2_liebian_inputs(
        {
            "image_url": "https://example.com/input.png",
            "prompt": "保留系列感，重新绘制主花型",
            "image_desc": "主体为花卉装饰图案，中央主花簇明显",
            "similarity": 100,
            "steps": 8,
            "cfg": 1.0,
            "seed": 123456,
            "batch_size": 2,
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["10"]["url"] == "https://example.com/input.png"
    assert overrides["13"]["text1"] == "保留系列感，重新绘制主花型"
    assert overrides["13"]["text2"] == "主体为花卉装饰图案，中央主花簇明显"
    assert overrides["18"]["cfg"] == 1.0
    assert overrides["19"]["noise_seed"] == 123456
    assert overrides["21"]["steps"] == 8
    assert overrides["21"]["denoise"] == 0.3
    assert overrides["24"]["batch_size"] == 2
    assert context.workflow.definition["_expected_image_count"] == 2
    assert context.workflow.definition["output_node_ids"] == ["27"]


def test_e7_flux2_liebian_normalizes_custom_size_and_clamps_similarity():
    context = _make_context()
    adapter = ComfyUIExecutorAdapter()

    overrides, error = adapter._build_e7_flux2_liebian_inputs(
        {
            "image_url": "https://example.com/input.png",
            "prompt": "做一次明显裂变",
            "similarity": -10,
            "width": 1001,
            "height": 1503,
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["21"]["denoise"] == 0.7
    assert overrides["12"]["width"] == 1000
    assert overrides["12"]["height"] == 1496
