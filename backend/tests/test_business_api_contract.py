from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_business_openapi_exposes_flat_business_tools() -> None:
    resp = client.get("/api/business/openapi.json", headers={"x-real-ip": "127.0.0.1"})
    assert resp.status_code == 200
    data = resp.json()
    paths = data.get("paths") or {}

    assert "/api/business/fission/runs" in paths
    assert "/api/business/outpaint/runs" in paths
    assert "/api/business/runs/get" in paths

    submit_schema = paths["/api/business/fission/runs"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    assert submit_schema["required"] == ["imageUrl"]
    assert {
        "imageUrl",
        "prompt",
        "version",
        "inputs",
        "callbackUrl",
        "bili",
        "width",
        "height",
        "image_desc",
        "traceId",
        "requestId",
        "tenantId",
        "clientId",
        "channel",
        "source",
    }.issubset(submit_schema["properties"])
    outpaint_schema = paths["/api/business/outpaint/runs"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    assert {"expand_left", "expand_right", "expand_top", "expand_bottom", "width", "height"}.issubset(
        outpaint_schema["properties"]
    )

    run_schema = paths["/api/business/runs/get"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert {
        "runId",
        "taskId",
        "status",
        "imageUrls",
        "error",
        "debugUrl",
        "abilityName",
        "vendorModelName",
        "routeInfo",
        "steps",
        "traceId",
        "requestId",
        "durationMs",
        "costAmount",
        "currency",
    }.issubset(run_schema["properties"])
    step_props = run_schema["properties"]["steps"]["items"]["properties"]
    assert "resultSummary" in step_props
    assert {"durationMs", "costAmount", "quotaUnits"}.issubset(step_props)
    submit_responses = paths["/api/business/fission/runs"]["post"]["responses"]
    assert "400" in submit_responses
    assert "500" in submit_responses
    assert "BUSINESS_IMAGE_URL_REQUIRED" in submit_responses["400"]["x-podi-errors"]
    assert "COMFYUI_TIMEOUT" in submit_responses["500"]["x-podi-errors"]
    get_responses = paths["/api/business/runs/get"]["post"]["responses"]
    assert "BUSINESS_RUN_ID_REQUIRED" in get_responses["400"]["x-podi-errors"]


def test_business_capabilities_response_uses_public_camel_case(monkeypatch) -> None:
    class FakeBusinessRunService:
        def list_capabilities(self):
            return [
                {
                    "id": "biz_fission_v1_test",
                    "business_key": "fission",
                    "version": "v1",
                    "display_name": "图裂变",
                    "description": "test",
                    "status": "active",
                    "is_default": True,
                    "release_time": None,
                    "recipe": {"primaryAbilityId": "comfyui_test"},
                    "input_schema": {"fields": []},
                    "output_schema": None,
                    "extra_metadata": {"seed_version": 1},
                    "created_at": "2026-04-24T00:00:00",
                    "updated_at": "2026-04-24T00:00:00",
                }
            ]

    monkeypatch.setattr("app.routers.business.get_business_run_service", lambda: FakeBusinessRunService())

    resp = client.get("/api/business/capabilities", headers={"x-real-ip": "127.0.0.1"})

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["businessKey"] == "fission"
    assert item["displayName"] == "图裂变"
    assert item["isDefault"] is True
    assert "business_key" not in item


def test_business_fission_requires_image_url() -> None:
    resp = client.post("/api/business/fission/runs", json={"inputs": {"prompt": "test"}}, headers={"x-real-ip": "127.0.0.1"})

    assert resp.status_code == 400
    assert resp.json()["detail"] == "BUSINESS_IMAGE_URL_REQUIRED"


def test_business_run_get_requires_run_id() -> None:
    resp = client.post("/api/business/runs/get", json={}, headers={"x-real-ip": "127.0.0.1"})

    assert resp.status_code == 400
    assert resp.json()["detail"] == "BUSINESS_RUN_ID_REQUIRED"
