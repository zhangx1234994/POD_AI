from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_comfyui_beijing_koutu_openapi_contains_only_tool_and_tasks_get():
    resp = client.get("/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    paths = data.get("paths") or {}
    assert "/api/coze/podi/tools/comfyui/beijing_koutu" in paths
    assert "/api/coze/podi/tasks/get" in paths
    assert "/api/coze/podi/comfyui/queue-summary" not in paths

    tool_schema = (
        paths["/api/coze/podi/tools/comfyui/beijing_koutu"]["post"]["requestBody"]["content"]["application/json"][
            "schema"
        ]
    )
    props = tool_schema.get("properties") or {}
    required = tool_schema.get("required") or []
    assert set(props) == {"url"}
    assert required == ["url"]


def test_comfyui_toubu_kouxiang_openapi_contains_only_tool_and_tasks_get():
    resp = client.get("/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    paths = data.get("paths") or {}
    assert "/api/coze/podi/tools/comfyui/toubu_kouxiang" in paths
    assert "/api/coze/podi/tasks/get" in paths

    tool_schema = (
        paths["/api/coze/podi/tools/comfyui/toubu_kouxiang"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
    )
    props = tool_schema.get("properties") or {}
    required = tool_schema.get("required") or []
    assert set(props) == {"url"}
    assert required == ["url"]


def test_comfyui_flux2_9b_liebian_sifang_openapi_contains_expected_fields():
    resp = client.get("/api/coze/podi/comfyui/execute/flux2-9b-liebian-sifang/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    paths = data.get("paths") or {}
    assert "/api/coze/podi/tools/comfyui/flux2_9b_liebian_sifang" in paths
    assert "/api/coze/podi/tasks/get" in paths

    tool_schema = (
        paths["/api/coze/podi/tools/comfyui/flux2_9b_liebian_sifang"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
    )
    props = tool_schema.get("properties") or {}
    required = tool_schema.get("required") or []
    assert set(props) == {"url", "prompt"}
    assert "url" in required
    assert "prompt" in required
