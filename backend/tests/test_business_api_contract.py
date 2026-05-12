from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_business_openapi_exposes_flat_business_tools() -> None:
    resp = client.get("/api/business/openapi.json", headers={"x-real-ip": "127.0.0.1"})
    assert resp.status_code == 200
    data = resp.json()
    paths = data.get("paths") or {}

    assert "/api/business/pattern-extract/runs" in paths
    assert "/api/business/fission/runs" in paths
    assert "/api/business/outpaint/runs" in paths
    assert "/api/business/pattern-extract/route-preview" in paths
    assert "/api/business/fission/route-preview" in paths
    assert "/api/business/outpaint/route-preview" in paths
    assert "/api/business/runs/get" in paths

    pattern_schema = paths["/api/business/pattern-extract/runs"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    assert pattern_schema["required"] == ["imageUrl"]
    assert {"imageUrl", "prompt", "negative_prompt", "width", "height", "batch", "lora", "timeout"}.issubset(
        pattern_schema["properties"]
    )
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
        "profile",
        "mode",
        "vl_result",
        "image_desc",
        "traceId",
        "requestId",
        "tenantId",
        "clientId",
        "channel",
        "source",
        "variation_strength",
        "quality",
        "count",
        "size",
        "maskUrl",
    }.issubset(submit_schema["properties"])
    assert "重绘幅度" in submit_schema["properties"]["bili"]["description"]
    assert "denoise" in submit_schema["properties"]["bili"]["description"]
    assert submit_schema["properties"]["size"]["enum"] == [
        "auto",
        "1024x1024",
        "1536x1024",
        "1024x1536",
        "2048x2048",
        "2048x1152",
        "3840x2160",
        "2160x3840",
    ]
    outpaint_schema = paths["/api/business/outpaint/runs"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    assert {"expand_left", "expand_right", "expand_top", "expand_bottom", "width", "height"}.issubset(
        outpaint_schema["properties"]
    )
    preview_schema = paths["/api/business/fission/route-preview"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    assert preview_schema["required"] == []
    assert {"tenantId", "clientId", "version", "metadata"}.issubset(preview_schema["properties"])
    pattern_preview_schema = paths["/api/business/pattern-extract/route-preview"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert pattern_preview_schema["required"] == []
    preview_response = paths["/api/business/fission/route-preview"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert {"selectedVersion", "selectedBy", "routeInfo", "activeVersions"}.issubset(
        preview_response["properties"]
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
        "billingStatus",
        "chargeable",
        "noChargeReason",
        "callbackStatus",
    }.issubset(run_schema["properties"])
    step_props = run_schema["properties"]["steps"]["items"]["properties"]
    assert "resultSummary" in step_props
    assert {"durationMs", "costAmount", "quotaUnits"}.issubset(step_props)
    submit_responses = paths["/api/business/fission/runs"]["post"]["responses"]
    assert "400" in submit_responses
    assert "500" in submit_responses
    assert "BUSINESS_IMAGE_URL_REQUIRED" in submit_responses["400"]["x-podi-errors"]
    assert "BUSINESS_API_KEY_INACTIVE" in submit_responses["401"]["x-podi-errors"]
    assert "BUSINESS_API_KEY_EXPIRED" in submit_responses["401"]["x-podi-errors"]
    assert "BUSINESS_USER_SCOPE_FORBIDDEN" in submit_responses["403"]["x-podi-errors"]
    assert "BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED" in submit_responses["403"]["x-podi-errors"]
    assert "COMFYUI_TIMEOUT" in submit_responses["500"]["x-podi-errors"]
    assert data["components"]["securitySchemes"]["BusinessApiKey"]["name"] == "X-PODI-API-Key"
    assert {"BusinessApiKey": []} in data["security"]
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


def test_business_pattern_extract_requires_image_url() -> None:
    resp = client.post(
        "/api/business/pattern-extract/runs",
        json={"inputs": {"prompt": "test"}},
        headers={"x-real-ip": "127.0.0.1"},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "BUSINESS_IMAGE_URL_REQUIRED"


def test_business_run_get_requires_run_id() -> None:
    resp = client.post("/api/business/runs/get", json={}, headers={"x-real-ip": "127.0.0.1"})

    assert resp.status_code == 400
    assert resp.json()["detail"] == "BUSINESS_RUN_ID_REQUIRED"


def test_business_admin_api_keys_require_admin_token() -> None:
    resp = client.get("/api/admin/business/api-keys", headers={"x-real-ip": "127.0.0.1"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "AUTHORIZATION_REQUIRED"


def test_business_api_submit_and_query_do_not_require_coze_workflow(monkeypatch) -> None:
    created: dict[str, object] = {}

    def _run_payload(*, business_key: str, payload) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "id": f"run_direct_{business_key}",
            "business_key": business_key,
            "business_version_id": f"biz_{business_key}_v1",
            "version": "v1",
            "status": "queued",
            "source": payload.source or "business-api",
            "channel": payload.channel,
            "trace_id": payload.traceId,
            "request_id": payload.requestId,
            "tenant_id": payload.tenantId,
            "client_id": payload.clientId,
            "ability_id": f"ability_{business_key}",
            "ability_name": f"{business_key} ability",
            "ability_task_id": f"task_direct_{business_key}",
            "image_urls": [],
            "video_urls": [],
            "texts": [],
            "debug_url": f"/api/business/runs/run_direct_{business_key}",
            "route_info": {"entry": "business-api", "selectedBy": "default"},
            "steps": [],
            "created_at": now,
            "updated_at": now,
        }

    class FakeBusinessRunService:
        def create_run(self, *, business_key, payload, user):
            assert user is not None
            assert payload.imageUrl == "https://example.com/input.png"
            assert not (payload.inputs or {}).get("coze_workflow_id")
            created["business_key"] = business_key
            created["payload_source"] = payload.source
            return _run_payload(business_key=business_key, payload=payload)

        def get_run(self, *, run_id, user):
            assert user is not None
            assert run_id == "run_direct_fission"
            return _run_payload(
                business_key="fission",
                payload=type(
                    "Payload",
                    (),
                    {
                        "source": "partner-api",
                        "channel": "open-api",
                        "traceId": "trace-direct-001",
                        "requestId": "req-direct-001",
                        "tenantId": "tenant-direct",
                        "clientId": "client-direct",
                    },
                )(),
            )

    monkeypatch.setattr("app.routers.business.get_business_run_service", lambda: FakeBusinessRunService())

    submit = client.post(
        "/api/business/fission/runs",
        json={
            "imageUrl": "https://example.com/input.png",
            "prompt": "直接业务 API 提交",
            "source": "partner-api",
            "channel": "open-api",
            "traceId": "trace-direct-001",
            "requestId": "req-direct-001",
            "tenantId": "tenant-direct",
            "clientId": "client-direct",
        },
        headers={"x-real-ip": "127.0.0.1"},
    )

    assert submit.status_code == 200
    submit_body = submit.json()
    assert created == {"business_key": "fission", "payload_source": "partner-api"}
    assert submit_body["runId"] == "run_direct_fission"
    assert submit_body["taskId"] == "task_direct_fission"
    assert submit_body["source"] == "partner-api"
    assert submit_body["channel"] == "open-api"
    assert submit_body["routeInfo"]["entry"] == "business-api"
    assert "cozeWorkflowId" not in submit_body

    query = client.post(
        "/api/business/runs/get",
        json={"runId": "run_direct_fission"},
        headers={"x-real-ip": "127.0.0.1"},
    )

    assert query.status_code == 200
    query_body = query.json()
    assert query_body["runId"] == "run_direct_fission"
    assert query_body["taskId"] == "task_direct_fission"


def test_coze_task_get_accepts_business_run_id_for_polling_compatibility(monkeypatch) -> None:
    now = datetime.now(timezone.utc)

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, model, row_id):
            return None

    class FakeBusinessRunService:
        def get_run(self, *, run_id, user):
            assert user is None
            assert run_id == "run_direct_fission"
            return {
                "id": "run_direct_fission",
                "business_key": "fission",
                "version": "gpt-image2-vl-v1",
                "status": "succeeded",
                "source": "business-api",
                "request_id": "req-direct-001",
                "ability_log_id": 123,
                "image_urls": ["https://example.com/out.png"],
                "video_urls": [],
                "texts": [],
                "created_at": now,
                "updated_at": now,
            }

    monkeypatch.setattr("app.routers.coze_podi_plugin.get_session", lambda: FakeSession())
    monkeypatch.setattr("app.routers.coze_podi_plugin.get_business_run_service", lambda: FakeBusinessRunService())

    resp = client.post(
        "/api/coze/podi/tasks/get",
        json={"taskId": "run_direct_fission"},
        headers={"x-real-ip": "127.0.0.1"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["taskId"] == "run_direct_fission"
    assert body["taskStatus"] == "succeeded"
    assert body["imageUrl"] == "https://example.com/out.png"
    assert body["imageUrls"] == ["https://example.com/out.png"]
    assert body["requestId"] == "req-direct-001"
