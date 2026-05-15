import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import get_session
from app.main import app
from app.models.integration import BusinessApiKeyUsageLog, BusinessRun
from app.models.user import User
from app.schemas.business import BusinessRunCreateRequest
from app.services.business_runs import BusinessRunService


client = TestClient(app)


def test_business_openapi_exposes_flat_business_tools() -> None:
    resp = client.get("/api/business/openapi.json", headers={"x-real-ip": "127.0.0.1"})
    assert resp.status_code == 200
    data = resp.json()
    paths = data.get("paths") or {}

    assert "/api/business/pattern-extract/runs" in paths
    assert "/api/business/fission/runs" in paths
    assert "/api/business/fission-evaluate/runs" in paths
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
        "variation_preset",
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
        "size",
        "maskUrl",
    }.issubset(submit_schema["properties"])
    assert "count" not in submit_schema["properties"]
    assert "preserve_layout" not in submit_schema["properties"]
    assert "preserve_border" not in submit_schema["properties"]
    assert "preserve_count_density" not in submit_schema["properties"]
    assert "style_shift" not in submit_schema["properties"]
    assert "重绘幅度" in submit_schema["properties"]["bili"]["description"]
    assert "denoise" in submit_schema["properties"]["bili"]["description"]
    assert "通常不需要业务方传入" in submit_schema["properties"]["tenantId"]["description"]
    assert "业务 API Key" in submit_schema["properties"]["clientId"]["description"]
    assert "runId 轮询" in submit_schema["properties"]["callbackUrl"]["description"]
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
    assert submit_schema["properties"]["profile"]["enum"] == [
        "pattern_risk_routed_v4",
        "pattern_color_lock_v2",
        "pattern_color_lock_strict_v2",
        "pattern_default_v1",
    ]
    assert submit_schema["properties"]["mode"]["enum"] == ["fission"]
    assert submit_schema["properties"]["variation_preset"]["enum"] == ["default-high", "safe", "object-strong", "color-free"]
    assert submit_schema["properties"]["pattern_risk_type"]["enum"] == [
        "element_pattern",
        "object_variation",
        "text_or_logo",
        "border_or_layout",
        "unknown",
    ]
    outpaint_schema = paths["/api/business/outpaint/runs"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    assert {"expand_left", "expand_right", "expand_top", "expand_bottom", "width", "height"}.issubset(
        outpaint_schema["properties"]
    )
    fission_eval_schema = paths["/api/business/fission-evaluate/runs"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert fission_eval_schema["required"] == ["originalImageUrl", "generatedImageUrl"]
    assert {"originalImageUrl", "generatedImageUrl", "context", "callbackUrl", "traceId", "requestId"}.issubset(
        fission_eval_schema["properties"]
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
    assert preview_response["properties"]["selectedBy"]["enum"] == [
        "explicit",
        "default",
        "rollout_allowlist",
        "rollout_percent",
    ]
    assert preview_response["properties"]["selectedStatus"]["enum"] == ["active", "disabled", "archived"]

    run_schema = paths["/api/business/runs/get"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert {
        "runId",
        "taskId",
        "status",
        "taskStatus",
        "imageUrl",
        "imageUrls",
        "videoUrl",
        "videoUrls",
        "text",
        "texts",
        "error",
        "errorMessage",
        "errorCode",
        "debugResponse",
        "debugUrl",
        "retryAfterSeconds",
        "expectedImageCount",
        "traceId",
        "requestId",
        "durationMs",
        "createdAt",
        "finishedAt",
    }.issubset(run_schema["properties"])
    assert "routeInfo" not in run_schema["properties"]
    assert "steps" not in run_schema["properties"]
    assert "flowSummary" not in run_schema["properties"]
    assert "requestPayload" not in run_schema["properties"]
    assert "costBreakdown" not in run_schema["properties"]
    run_get_request_schema = paths["/api/business/runs/get"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    assert {"runId", "taskId", "detail", "includeDebug"}.issubset(run_get_request_schema["properties"])
    submit_responses = paths["/api/business/fission/runs"]["post"]["responses"]
    submit_response_schema = submit_responses["200"]["content"]["application/json"]["schema"]
    assert {
        "runId",
        "taskId",
        "businessKey",
        "version",
        "status",
        "taskStatus",
        "traceId",
        "requestId",
        "debugUrl",
        "retryAfterSeconds",
    }.issubset(submit_response_schema["properties"])
    assert "routeInfo" not in submit_response_schema["properties"]
    assert "steps" not in submit_response_schema["properties"]
    assert "requestPayload" not in submit_response_schema["properties"]
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


def test_business_fission_evaluate_requires_two_images() -> None:
    resp = client.post(
        "/api/business/fission-evaluate/runs",
        json={"originalImageUrl": "https://example.com/original.png"},
        headers={"x-real-ip": "127.0.0.1"},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "VL_EVAL_IMAGE_REQUIRED"


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


def test_business_run_get_hides_internal_database_errors(monkeypatch) -> None:
    class FakeBusinessRunService:
        def get_run(self, *, run_id, user):
            raise RuntimeError("pymysql.err.OperationalError: SELECT very large sql")

    monkeypatch.setattr("app.routers.business.get_business_run_service", lambda: FakeBusinessRunService())

    resp = client.post(
        "/api/business/runs/get",
        json={"runId": "run_sql_failed"},
        headers={"x-real-ip": "127.0.0.1"},
    )

    assert resp.status_code == 503
    assert resp.json()["detail"] == "BUSINESS_RUN_TEMPORARY_UNAVAILABLE"


def test_business_admin_api_keys_require_admin_token() -> None:
    resp = client.get("/api/admin/business/api-keys", headers={"x-real-ip": "127.0.0.1"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "AUTHORIZATION_REQUIRED"


def test_business_admin_api_usage_supports_filters_summary_and_run_groups() -> None:
    now = datetime.utcnow()
    run_id = "run_usage_contract_001"
    with get_session() as session:
        for row in session.execute(select(BusinessApiKeyUsageLog).where(BusinessApiKeyUsageLog.run_id == run_id)).scalars().all():
            session.delete(row)
        session.add_all(
            [
                BusinessApiKeyUsageLog(
                    api_key_id="api_key_usage_contract",
                    api_key_name="业务方测试 Key",
                    api_key_preview="podi...test",
                    method="POST",
                    path="/api/business/fission/runs",
                    status_code=200,
                    business_key="fission",
                    run_id=run_id,
                    request_id="req_usage_contract",
                    trace_id="trace_usage_contract",
                    tenant_id="tenant-usage",
                    client_id="client-usage",
                    duration_ms=120,
                    created_at=now,
                ),
                BusinessApiKeyUsageLog(
                    api_key_id="api_key_usage_contract",
                    api_key_name="业务方测试 Key",
                    api_key_preview="podi...test",
                    method="POST",
                    path="/api/business/runs/get",
                    status_code=200,
                    business_key="fission",
                    run_id=run_id,
                    request_id="req_usage_contract",
                    trace_id="trace_usage_contract",
                    tenant_id="tenant-usage",
                    client_id="client-usage",
                    duration_ms=60,
                    created_at=now,
                ),
                BusinessApiKeyUsageLog(
                    api_key_id="api_key_usage_contract",
                    api_key_name="业务方测试 Key",
                    api_key_preview="podi...test",
                    method="POST",
                    path="/api/business/runs/get",
                    status_code=400,
                    business_key="fission",
                    run_id=run_id,
                    request_id="req_usage_contract",
                    trace_id="trace_usage_contract",
                    tenant_id="tenant-usage",
                    client_id="client-usage",
                    error_code="BUSINESS_RUN_ID_REQUIRED",
                    duration_ms=50,
                    created_at=now,
                ),
            ]
        )
        session.commit()

    resp = client.get(
        "/api/admin/business/api-key-usage",
        params={"run_id": run_id, "window_hours": 0, "limit": 10},
        headers={"Authorization": "Bearer podi-test-service-token", "x-real-ip": "127.0.0.1"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["summary"]["submitCount"] == 1
    assert body["summary"]["pollCount"] == 2
    assert body["summary"]["errorCount"] == 1
    assert body["summary"]["uniqueRunCount"] == 1
    assert body["groups"][0]["runId"] == run_id
    assert body["groups"][0]["submitCount"] == 1
    assert body["groups"][0]["pollCount"] == 2
    assert body["groups"][0]["needsAttention"] is True
    assert body["groups"][0]["issueCode"] == "HAS_ERROR"

    poll_resp = client.get(
        "/api/admin/business/api-key-usage",
        params={"run_id": run_id, "endpoint_kind": "poll", "window_hours": 0, "limit": 10},
        headers={"Authorization": "Bearer podi-test-service-token", "x-real-ip": "127.0.0.1"},
    )

    assert poll_resp.status_code == 200
    assert poll_resp.json()["total"] == 2

    export_resp = client.get(
        "/api/admin/business/api-key-usage/export",
        params={"run_id": run_id, "window_hours": 0},
        headers={"Authorization": "Bearer podi-test-service-token", "x-real-ip": "127.0.0.1"},
    )
    assert export_resp.status_code == 200
    assert "text/csv" in export_resp.headers["content-type"]
    export_text = export_resp.text
    assert "接口动作" in export_text
    assert "submit" in export_text
    assert "poll" in export_text
    assert "BUSINESS_RUN_ID_REQUIRED" in export_text


def test_business_api_key_actor_does_not_write_fake_user_id() -> None:
    user = User(
        id="business-api-key:biz_key_fission_partner_20260512",
        email="biz_key_fission_partner_20260512@business-api.podi.internal",
        username="业务方图裂变测试 Key",
        password_hash="",
        role="client",
        status="active",
        tenant_id="partner",
        client_id="fission-api",
    )

    assert BusinessRunService._safe_user_id(user) is None


def test_business_callback_payload_uses_public_task_id() -> None:
    run = BusinessRun(
        id="run_callback_001",
        business_key="fission",
        version="comfyui-vl-control-v2",
        status="succeeded",
        trace_id="trace-callback-001",
        request_id="req-callback-001",
        tenant_id="tenant-a",
        client_id="client-a",
        channel="open-api",
        ability_task_id="f721a56e53a2471fa22bdcf2a2ae0e94",
        image_urls=["https://example.com/result.png"],
        video_urls=[],
        texts=[],
        duration_ms=58283,
        cost_amount=0.35,
        currency="CNY",
    )

    payload = BusinessRunService()._callback_payload(run)

    assert payload["runId"] == "run_callback_001"
    assert payload["taskId"] == "t1.fission.auto.f721a56e53a2471fa22bdcf2a2ae0e94"
    assert payload["imageUrls"] == ["https://example.com/result.png"]


def test_business_fission_evaluate_payload_maps_original_and_generated_images() -> None:
    payload = BusinessRunCreateRequest(
        originalImageUrl="https://example.com/original.png",
        generatedImageUrl="https://example.com/generated.png",
        context={"business": "fission", "version": "gpt-image2-vl-v2"},
        source="partner-api",
        channel="open-api",
        traceId="trace-eval-001",
        requestId="req-eval-001",
    )

    ability_payload = BusinessRunService()._build_ability_payload(
        capability_key="fission_evaluate",
        payload=payload,
        image_url="https://example.com/original.png",
        route_info={"version": "v1"},
        trace_context={
            "traceId": "trace-eval-001",
            "requestId": "req-eval-001",
            "source": "partner-api",
            "channel": "open-api",
        },
    )

    assert ability_payload.imageUrl == "https://example.com/original.png"
    assert ability_payload.inputs["original_image"] == "https://example.com/original.png"
    assert ability_payload.inputs["generated_image"] == "https://example.com/generated.png"
    assert ability_payload.inputs["context"] == {"business": "fission", "version": "gpt-image2-vl-v2"}
    assert ability_payload.metadata["businessKey"] == "fission_evaluate"


def test_business_fission_payload_forces_single_output_and_drops_legacy_fields() -> None:
    payload = BusinessRunCreateRequest.model_validate(
        {
            "imageUrl": "https://example.com/input.png",
            "version": "gpt-image2-vl-v2",
            "prompt": "保持同系列图案",
            "bili": "80%",
            "width": 1600,
            "height": 1200,
            "count": 3,
            "batch_size": 4,
            "preserve_layout": True,
            "preserve_border": "auto",
            "preserve_count_density": True,
            "style_shift": "standard",
            "inputs": {
                "n": 5,
                "batchSize": 6,
                "generateCount": 7,
                "variantCount": 8,
                "variation_strength": "same_series",
                "quality": "candidate",
                "size": "auto",
            },
        }
    )

    ability_payload = BusinessRunService()._build_ability_payload(
        capability_key="fission",
        payload=payload,
        image_url="https://example.com/input.png",
        route_info={"version": "gpt-image2-vl-v2"},
        trace_context={"traceId": "trace-single-001", "requestId": "req-single-001"},
    )

    assert ability_payload.inputs["prompt"] == "保持同系列图案"
    assert ability_payload.inputs["bili"] == "80%"
    assert ability_payload.inputs["variation_strength"] == "same_series"
    assert ability_payload.inputs["quality"] == "candidate"
    assert ability_payload.inputs["size"] == "auto"
    for key in (
        "count",
        "n",
        "batch_size",
        "batchSize",
        "generateCount",
        "variantCount",
        "preserve_layout",
        "preserve_border",
        "preserve_count_density",
        "style_shift",
    ):
        assert key not in ability_payload.inputs


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
    assert submit_body["businessKey"] == "fission"
    assert submit_body["status"] == "queued"
    assert submit_body["taskStatus"] == "queued"
    assert submit_body["traceId"] == "trace-direct-001"
    assert submit_body["requestId"] == "req-direct-001"
    assert submit_body["retryAfterSeconds"] == 10
    assert "source" not in submit_body
    assert "channel" not in submit_body
    assert "routeInfo" not in submit_body
    assert "steps" not in submit_body
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
    assert query_body["status"] == "queued"
    assert query_body["taskStatus"] == "queued"
    assert query_body["expectedImageCount"] == 1
    assert query_body["retryAfterSeconds"] == 10
    assert "routeInfo" not in query_body
    assert "steps" not in query_body

    full_query = client.post(
        "/api/business/runs/get",
        json={"runId": "run_direct_fission", "detail": "full"},
        headers={"x-real-ip": "127.0.0.1"},
    )

    assert full_query.status_code == 200
    full_body = full_query.json()
    assert full_body["runId"] == "run_direct_fission"
    assert full_body["routeInfo"]["entry"] == "business-api"
    assert full_body["steps"] == []


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


def test_business_run_light_response_exposes_structured_text_payload(monkeypatch) -> None:
    now = datetime.now(timezone.utc)

    class FakeBusinessRunService:
        def get_run(self, *, run_id, user):
            assert run_id == "run_score_001"
            return {
                "id": "run_score_001",
                "business_key": "fission_evaluate",
                "version": "v1",
                "status": "succeeded",
                "source": "partner-api",
                "channel": "open-api",
                "request_id": "req-score-001",
                "ability_task_id": "task_score_001",
                "image_urls": [],
                "video_urls": [],
                "texts": [
                    json.dumps(
                        {
                            "decision": "pass",
                            "score": 85,
                            "reason": "质量稳定，可进入业务验收。",
                        },
                        ensure_ascii=False,
                    )
                ],
                "created_at": now,
                "updated_at": now,
                "finished_at": now,
            }

    monkeypatch.setattr("app.routers.business.get_business_run_service", lambda: FakeBusinessRunService())

    resp = client.post(
        "/api/business/runs/get",
        json={"runId": "run_score_001"},
        headers={"x-real-ip": "127.0.0.1"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["text"].startswith('{"decision"')
    assert body["resultPayload"] == {
        "decision": "pass",
        "score": 85,
        "reason": "质量稳定，可进入业务验收。",
    }


def test_business_run_light_response_prefers_structured_payload_inside_texts(monkeypatch) -> None:
    now = datetime.now(timezone.utc)

    class FakeBusinessRunService:
        def get_run(self, *, run_id, user):
            assert run_id == "run_score_002"
            score_text = json.dumps(
                {
                    "decision": "needs_refission",
                    "score": 62,
                    "reason": "主体关系有偏移，建议二次裂变。",
                    "next_action": {"type": "refission"},
                },
                ensure_ascii=False,
            )
            return {
                "id": "run_score_002",
                "business_key": "fission_evaluate",
                "version": "v1",
                "status": "succeeded",
                "source": "partner-api",
                "channel": "open-api",
                "request_id": "req-score-002",
                "ability_task_id": "task_score_002",
                "image_urls": [],
                "video_urls": [],
                "texts": [score_text],
                "result_payload": {
                    "status": "succeeded",
                    "provider": "vl",
                    "texts": [score_text],
                    "durationMs": 12000,
                },
                "created_at": now,
                "updated_at": now,
                "finished_at": now,
            }

    monkeypatch.setattr("app.routers.business.get_business_run_service", lambda: FakeBusinessRunService())

    resp = client.post(
        "/api/business/runs/get",
        json={"runId": "run_score_002"},
        headers={"x-real-ip": "127.0.0.1"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["resultPayload"] == {
        "decision": "needs_refission",
        "score": 62,
        "reason": "主体关系有偏移，建议二次裂变。",
        "next_action": {"type": "refission"},
    }


def test_coze_task_get_keeps_task_not_found_for_unknown_ids(monkeypatch) -> None:
    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, model, row_id):
            return None

    class FakeBusinessRunService:
        def get_run(self, *, run_id, user):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")

    monkeypatch.setattr("app.routers.coze_podi_plugin.get_session", lambda: FakeSession())
    monkeypatch.setattr("app.routers.coze_podi_plugin.get_business_run_service", lambda: FakeBusinessRunService())

    resp = client.post(
        "/api/coze/podi/tasks/get",
        json={"taskId": "missing-id"},
        headers={"x-real-ip": "127.0.0.1"},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "TASK_NOT_FOUND"
