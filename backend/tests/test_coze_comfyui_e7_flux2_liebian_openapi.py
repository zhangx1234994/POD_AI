from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_comfyui_e7_flux2_liebian_openapi_contains_only_tool_and_tasks_get():
    resp = client.get("/api/coze/podi/comfyui/execute/e7-flux2-liebian/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    paths = data.get("paths") or {}
    assert "/api/coze/podi/tools/comfyui/e7_flux2_liebian" in paths
    assert "/api/coze/podi/tasks/get" in paths
    assert "/api/coze/podi/comfyui/queue-summary" not in paths

    tool_schema = (
        paths["/api/coze/podi/tools/comfyui/e7_flux2_liebian"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
    )
    props = tool_schema.get("properties") or {}
    required = tool_schema.get("required") or []
    assert "url" in props
    assert "prompt" in props
    assert "similarity" in props
    assert "batch_size" in props
    assert "image_desc" not in props
    assert "image_url" not in props
    assert "url" in required
    assert "prompt" in required
