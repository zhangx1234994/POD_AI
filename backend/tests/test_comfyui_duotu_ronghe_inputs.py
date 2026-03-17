from types import SimpleNamespace

from app.services.executors.base import ExecutionContext
from app.services.executors.comfyui import ComfyUIExecutorAdapter


def _make_context(graph: dict):
    workflow = SimpleNamespace(definition={"graph": graph}, extra_metadata={"workflow_key": "duotu_ronghe"})
    executor = SimpleNamespace(base_url="http://127.0.0.1:8188", config={})
    task = SimpleNamespace(user_id="tester")
    return ExecutionContext(task=task, workflow=workflow, executor=executor, payload={})


def _patch_uploads(adapter: ComfyUIExecutorAdapter):
    uploaded: list[str] = []

    def fake_upload(*, image_url: str, base_url: str, prefix: str) -> str:
        uploaded.append(f"{prefix}:{image_url}:{base_url}")
        suffix = image_url.rsplit("/", 1)[-1]
        return f"{prefix}-{suffix}"

    adapter._upload_image_for_comfyui_loadimage = fake_upload  # type: ignore[attr-defined]
    return uploaded


def test_duotu_ronghe_maps_primary_and_split_aux_urls_to_new_nodes():
    graph = {
        "78": {"inputs": {"image": ""}},
        "106": {"inputs": {"image": ""}},
        "108": {"inputs": {"image": ""}},
        "110": {"inputs": {"prompt": "", "image1": ["390", 0], "image2": ["106", 0], "image3": ["108", 0]}},
        "111": {"inputs": {"prompt": "", "image1": ["390", 0], "image2": ["106", 0], "image3": ["108", 0]}},
        "112": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "151": {"inputs": {"seed": 1}},
    }
    context = _make_context(graph)
    adapter = ComfyUIExecutorAdapter()
    uploaded = _patch_uploads(adapter)

    overrides, error = adapter._build_duotu_ronghe_inputs(
        {
            "image_url": "https://example.com/main.png",
            "image_url_2": "https://example.com/aux-1.png",
            "image_url_3": "https://example.com/aux-2.png",
            "prompt": "fusion prompt",
            "negative_prompt": "no seams",
            "width": 2048,
            "height": 1536,
            "seed": 12345,
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["78"]["image"] == "duotu-primary-main.png"
    assert overrides["106"]["image"] == "duotu-aux1-aux-1.png"
    assert overrides["108"]["image"] == "duotu-aux2-aux-2.png"
    assert overrides["111"]["prompt"] == "fusion prompt"
    assert overrides["110"]["prompt"] == "no seams"
    assert overrides["112"]["width"] == 2048
    assert overrides["112"]["height"] == 1536
    assert overrides["151"]["seed"] == 12345
    assert context.workflow.definition["output_node_ids"] == ["60"]
    assert len(uploaded) == 3


def test_duotu_ronghe_omits_missing_aux_inputs_from_prompt_nodes():
    graph = {
        "78": {"inputs": {"image": ""}},
        "106": {"inputs": {"image": ""}},
        "108": {"inputs": {"image": ""}},
        "110": {"inputs": {"prompt": "", "image1": ["390", 0], "image2": ["106", 0], "image3": ["108", 0]}},
        "111": {"inputs": {"prompt": "", "image1": ["390", 0], "image2": ["106", 0], "image3": ["108", 0]}},
        "112": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "151": {"inputs": {"seed": 1}},
    }
    context = _make_context(graph)
    adapter = ComfyUIExecutorAdapter()
    _patch_uploads(adapter)

    overrides, error = adapter._build_duotu_ronghe_inputs(
        {
            "image_url": "https://example.com/main.png",
            "prompt": "fusion prompt",
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["78"]["image"] == "duotu-primary-main.png"
    assert "106" not in overrides
    assert "108" not in overrides
    assert "image2" not in context.workflow.definition["graph"]["110"]["inputs"]
    assert "image3" not in context.workflow.definition["graph"]["110"]["inputs"]
    assert "image2" not in context.workflow.definition["graph"]["111"]["inputs"]
    assert "image3" not in context.workflow.definition["graph"]["111"]["inputs"]


def test_duotu_ronghe_collapses_sparse_aux_inputs_without_gap():
    graph = {
        "78": {"inputs": {"image": ""}},
        "106": {"inputs": {"image": ""}},
        "108": {"inputs": {"image": ""}},
        "110": {"inputs": {"prompt": "", "image1": ["390", 0], "image2": ["106", 0], "image3": ["108", 0]}},
        "111": {"inputs": {"prompt": "", "image1": ["390", 0], "image2": ["106", 0], "image3": ["108", 0]}},
        "112": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "151": {"inputs": {"seed": 1}},
    }
    context = _make_context(graph)
    adapter = ComfyUIExecutorAdapter()
    _patch_uploads(adapter)

    overrides, error = adapter._build_duotu_ronghe_inputs(
        {
            "image_url": "https://example.com/main.png",
            "image_url_3": "https://example.com/aux-2.png",
        },
        context,
        context.workflow.definition,
    )

    assert error is None
    assert overrides is not None
    assert overrides["106"]["image"] == "duotu-aux1-aux-2.png"
    assert "108" not in overrides
    assert context.workflow.definition["graph"]["110"]["inputs"]["image2"] == ["106", 0]
    assert "image3" not in context.workflow.definition["graph"]["110"]["inputs"]
