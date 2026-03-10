from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_comfyui_duotu_ronghe_openapi_contains_only_tool_and_tasks_get():
    resp = client.get("/api/coze/podi/comfyui/execute/duotu-ronghe/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    paths = data.get("paths") or {}
    assert "/api/coze/podi/tools/comfyui/duotu_ronghe" in paths
    assert "/api/coze/podi/tasks/get" in paths
    assert "/api/coze/podi/comfyui/queue-summary" not in paths
    tool_schema = (
        paths["/api/coze/podi/tools/comfyui/duotu_ronghe"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
    )
    props = tool_schema.get("properties") or {}
    required = tool_schema.get("required") or []
    assert "url" in props
    assert "image_urls" in props
    assert "prompt" in props
    assert "url" in required
    assert "image_url" not in props
