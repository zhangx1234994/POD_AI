from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_comfyui_flux2_klein_outpaint_standalone_openapi_available():
    resp = client.get("/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    paths = data.get("paths") or {}

    assert "/api/coze/podi/tools/comfyui/flux2_klein_9b_outpaint" in paths
    assert "/api/coze/podi/tasks/get" in paths

    tool_schema = (
        paths["/api/coze/podi/tools/comfyui/flux2_klein_9b_outpaint"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
    )
    assert set(tool_schema.get("properties") or {}) == {
        "url",
        "expand_left",
        "expand_right",
        "expand_top",
        "expand_bottom",
    }
    assert (tool_schema.get("required") or []) == ["url"]
