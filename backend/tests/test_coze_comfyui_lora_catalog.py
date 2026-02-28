from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers.coze_podi_plugin import _match_lora_base_model


client = TestClient(app)


def test_match_lora_base_model_accepts_single_and_list_values():
    row = SimpleNamespace(base_model="qwen_image_edit", base_models=["sdxl", "flux"])  # noqa: N806
    assert _match_lora_base_model(row, "qwen-image-edit")
    assert _match_lora_base_model(row, "flux")
    assert _match_lora_base_model(row, "SDXL")


def test_match_lora_base_model_rejects_when_not_matched():
    row = SimpleNamespace(base_model="qwen_image_edit", base_models=["sdxl"])  # noqa: N806
    assert not _match_lora_base_model(row, "wan2.2")


def test_lora_openapi_exposes_zero_param_tool():
    resp = client.get("/api/coze/podi/comfyui/lora/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths") or {}
    assert "/api/coze/podi/comfyui/lora-catalog/default" in paths
    op = paths["/api/coze/podi/comfyui/lora-catalog/default"].get("post") or {}
    assert "requestBody" in op
    schema = ((op["requestBody"]["content"]["application/json"]).get("schema") or {})
    props = schema.get("properties") or {}
    assert props["status"]["description"]
    assert props["baseModel"]["description"]
    assert props["limit"]["description"]


def test_lora_default_supports_empty_json_payload():
    resp = client.post("/api/coze/podi/comfyui/lora-catalog/default", json={})
    assert resp.status_code == 200
    data = resp.json()
    # Coze validator is strict; optional string fields should be omitted instead of null.
    assert "executorId" not in data or data["executorId"] is not None
    assert "baseUrl" not in data or data["baseUrl"] is not None
