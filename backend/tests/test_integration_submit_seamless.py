from types import SimpleNamespace

from app.services.integration_test import IntegrationTestService


class _DummyAdapter:
    def _prepare_graph_inputs(self, context, workflow_definition):
        return (
            {
                "114": {"value": "https://example.com/input.png"},
                "96": {"url": "https://example.com/input.png"},
            },
            None,
        )

    def _ensure_sampler_seed(self, graph_payload, payload):
        return None


class _DummyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"prompt_id": "pid", "number": 1, "node_errors": {}}


def test_submit_comfyui_seamless_keeps_node_104(monkeypatch):
    svc = IntegrationTestService()
    captured = {}

    monkeypatch.setattr(
        svc,
        "_get_executor",
        lambda executor_id: SimpleNamespace(
            id=executor_id,
            type="comfyui",
            base_url="http://127.0.0.1:8079",
            config={},
        ),
    )
    monkeypatch.setattr(
        svc,
        "_get_comfyui_workflow_graph",
        lambda workflow_key: {
            "64": {"class_type": "ImageToMask", "inputs": {"image": ["104", 0]}},
            "96": {"class_type": "LoadImagesFromURL", "inputs": {"url": ""}},
            "102": {"class_type": "ImageResize+", "inputs": {"image": ["96", 0]}},
            "104": {"class_type": "easy loadImageBase64", "inputs": {"base64_data": "xxx"}},
            "114": {"class_type": "easy string", "inputs": {"value": ""}},
        },
    )
    monkeypatch.setattr(svc, "_get_comfyui_workflow_metadata", lambda workflow_key: {})

    from app.services import integration_test as mod

    monkeypatch.setattr(mod.registry, "get", lambda executor_type: _DummyAdapter())

    def _fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _DummyResponse()

    monkeypatch.setattr(mod.httpx, "post", _fake_post)

    svc.submit_comfyui_workflow(
        executor_id="executor_comfyui_seamless_117",
        workflow_key="sifang_lianxu",
        workflow_params={"url": "https://example.com/input.png"},
    )

    prompt = captured["json"]["prompt"]
    assert "104" in prompt
    assert prompt["64"]["inputs"]["image"] == ["104", 0]
