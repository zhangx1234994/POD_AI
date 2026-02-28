from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _internal_headers() -> dict[str, str]:
    return {"x-forwarded-for": "127.0.0.1"}


def test_kie_catalog_openapi_public_and_contains_query_tools():
    resp = client.get("/api/coze/podi/kie/catalog/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    paths = data.get("paths") or {}
    assert "/api/coze/podi/kie/models/list" in paths
    assert "/api/coze/podi/kie/models/schema" in paths


def test_kie_single_model_openapi_contains_zero_param_schema_tool():
    resp = client.get("/api/coze/podi/kie/catalog/nano-banana-pro-image-to-image/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    paths = data.get("paths") or {}
    assert "/api/coze/podi/kie/models/nano_banana_pro_image_to_image/schema" in paths


def test_kie_models_list_filter_by_media_type():
    resp = client.post(
        "/api/coze/podi/kie/models/list",
        json={"mediaType": "video", "status": "all"},
        headers=_internal_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0
    assert all(item.get("mediaType") == "video" for item in data.get("items") or [])


def test_kie_models_schema_returns_coze_suggestion():
    resp = client.post(
        "/api/coze/podi/kie/models/schema",
        json={"modelKey": "nano_banana_pro_image_to_image"},
        headers=_internal_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"]["modelKey"] == "nano_banana_pro_image_to_image"
    suggestion = data.get("cozeSuggestion") or {}
    assert "requiredParams" in suggestion
    assert "payloadTemplate" in suggestion


def test_kie_models_schema_missing_model_key():
    resp = client.post(
        "/api/coze/podi/kie/models/schema",
        json={},
        headers=_internal_headers(),
    )
    assert resp.status_code == 400
    assert resp.json().get("detail") == "KIE_MODEL_KEY_REQUIRED"


def test_kie_models_schema_not_found():
    resp = client.post(
        "/api/coze/podi/kie/models/schema",
        json={"modelKey": "unknown_model"},
        headers=_internal_headers(),
    )
    assert resp.status_code == 404
    assert resp.json().get("detail") == "KIE_MODEL_NOT_FOUND"


def test_kie_models_schema_by_path_without_body():
    resp = client.post(
        "/api/coze/podi/kie/models/nano-banana-pro-image-to-image/schema",
        headers=_internal_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"]["modelKey"] == "nano_banana_pro_image_to_image"
