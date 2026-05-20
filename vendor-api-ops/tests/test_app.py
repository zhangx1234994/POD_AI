from __future__ import annotations

import json
import sqlite3

import httpx
from fastapi.testclient import TestClient

from app import providers as provider_module
from app.config import get_settings
from app.invocations import invocation_store
from app.main import app
from app.storage import vendor_storage


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "vendor-api-ops"}


def test_provider_list_includes_expected_providers() -> None:
    client = TestClient(app)

    response = client.get("/v1/providers")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "vendor-api-ops"
    providers = {item["provider"]: item for item in body["providers"]}
    assert providers["openai"]["requiresGlobalEgress"] is True
    assert "batch_submit_poll" in providers["openai"]["executionModes"]
    assert providers["openai_compatible"]["requiresGlobalEgress"] is True
    assert providers["volcengine"]["supportedApiTypes"]
    assert providers["baidu"]["executionModes"] == ["sync_then_store"]
    assert "async_submit_poll" in providers["kie"]["executionModes"]
    assert providers["openai"]["envKeyConfigured"] is False


def test_provider_list_reports_env_key_presence(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-env")
    try:
        client = TestClient(app)

        response = client.get("/v1/providers")

        assert response.status_code == 200
        providers = {item["provider"]: item for item in response.json()["providers"]}
        assert providers["openai"]["envKeyConfigured"] is True
    finally:
        get_settings.cache_clear()


def test_service_token_required_for_sensitive_routes_when_configured(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("VENDOR_API_OPS_ADMIN_TOKEN", "test-token")
    try:
        client = TestClient(app)

        assert client.get("/v1/providers").status_code == 200
        assert client.get("/v1/keys").status_code == 401

        response = client.get("/v1/keys", headers={"Authorization": "Bearer test-token"})

        assert response.status_code == 200
        assert "items" in response.json()
    finally:
        get_settings.cache_clear()


def test_forbidden_client_returns_source_audit(monkeypatch, caplog) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("VENDOR_API_ALLOWED_CLIENTS", "127.0.0.1")
    try:
        client = TestClient(app)

        with caplog.at_level("WARNING"):
            response = client.get(
                "/v1/keys",
                headers={"user-agent": "pytest-agent", "x-forwarded-for": "203.0.113.10"},
            )

        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["errorCode"] == "VENDOR_API_CLIENT_FORBIDDEN"
        assert detail["source"]["clientHost"] == "testclient"
        assert detail["source"]["path"] == "/v1/keys"
        assert detail["source"]["xForwardedFor"] == "203.0.113.10"
        assert "vendor-api-ops rejected non-allowlisted client" in caplog.text
    finally:
        get_settings.cache_clear()


def test_unsupported_provider_returns_normalized_error() -> None:
    client = TestClient(app)

    response = client.post("/v1/providers/unknown/egress-check", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "VENDOR_API_PROVIDER_NOT_SUPPORTED"


def test_provider_auth_check_uses_stored_openai_key(monkeypatch) -> None:
    client = TestClient(app)
    captured = {}

    monkeypatch.setattr(
        provider_module.vendor_storage,
        "pick_key",
        lambda *, provider, model=None: {"id": "vkey_test", "provider": provider, "key": "sk-stored-key", "status": "active"},
    )

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def request(self, method, url, headers=None, params=None):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = headers or {}
            captured["params"] = params
            return httpx.Response(200, json={"data": []}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/v1/providers/openai/egress-check", json={"check": "models", "includeAuth": True})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "authenticated"
    assert captured["headers"]["Authorization"] == "Bearer sk-stored-key"
    assert captured["url"].endswith("/v1/models")


def test_provider_auth_check_reports_missing_key(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(provider_module.vendor_storage, "pick_key", lambda *, provider, model=None: None)
    try:
        client = TestClient(app)

        response = client.post("/v1/providers/openai/egress-check", json={"check": "models", "includeAuth": True})

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["errorCode"] == "VENDOR_API_KEY_MISSING"
    finally:
        get_settings.cache_clear()


def test_key_check_persists_last_check_metadata(monkeypatch) -> None:
    client = TestClient(app)
    created = client.post("/v1/keys", json={"provider": "openai", "alias": "check-key", "key": "sk-check-key"})
    key_id = created.json()["id"]
    captured = {}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def request(self, method, url, headers=None, params=None):
            captured["headers"] = headers or {}
            return httpx.Response(200, json={"data": []}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(f"/v1/keys/{key_id}/check", json={})

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert captured["headers"]["Authorization"] == "Bearer sk-check-key"

    keys = client.get("/v1/keys").json()["items"]
    checked = next(item for item in keys if item["id"] == key_id)
    assert checked["metadata"]["lastCheck"]["success"] is True
    assert checked["metadata"]["lastCheck"]["checkedAt"]
    assert checked["lastError"] is None


def test_baidu_image_process_returns_base64_asset(monkeypatch) -> None:
    client = TestClient(app)
    client.post(
        "/v1/keys",
        json={"provider": "baidu", "alias": "baidu-test", "key": "baidu-api-key", "secret": "baidu-secret"},
    )
    captured = {}

    def fake_post(url, headers=None, params=None, data=None, timeout=None):
        if url.endswith("/oauth/2.0/token"):
            captured["tokenParams"] = params
            return httpx.Response(
                200,
                json={"access_token": "baidu-token", "expires_in": 3600},
                request=httpx.Request("POST", url),
            )
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        return httpx.Response(
            200,
            json={"image": "baidu-image-b64", "log_id": "log-1"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post(
        "/v1/invocations",
        json={
            "provider": "baidu",
            "capabilityKey": "quality_upgrade",
            "model": "quality_upgrade",
            "apiType": "baidu_image_process",
            "inputs": {
                "request_endpoint": "/rest/2.0/image-process/v1/image_quality_enhance",
                "image_base64": "source-b64",
                "resolution": "2k",
            },
            "requestId": "req_1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "succeeded"
    assert body["provider"] == "baidu"
    assert body["vendorInvocationId"].startswith("vinv_")
    assert body["result"]["images"][0]["b64"] == "baidu-image-b64"
    assert captured["url"].endswith("/rest/2.0/image-process/v1/image_quality_enhance?access_token=baidu-token")
    assert captured["data"]["image"] == "source-b64"
    assert captured["data"]["resolution"] == "2k"


def test_baidu_image_process_accepts_image_processed_field(monkeypatch) -> None:
    client = TestClient(app)
    client.post(
        "/v1/keys",
        json={"provider": "baidu", "alias": "baidu-processed-test", "key": "baidu-api-key", "secret": "baidu-secret"},
    )

    def fake_post(url, headers=None, params=None, data=None, timeout=None):
        if url.endswith("/oauth/2.0/token"):
            return httpx.Response(
                200,
                json={"access_token": "baidu-token", "expires_in": 3600},
                request=httpx.Request("POST", url),
            )
        return httpx.Response(
            200,
            json={"image_processed": "baidu-processed-b64", "log_id": "log-processed"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post(
        "/v1/invocations",
        json={
            "provider": "baidu",
            "capabilityKey": "remove_moire",
            "model": "remove_moire",
            "apiType": "baidu_image_process",
            "inputs": {
                "request_endpoint": "/rest/2.0/image-process/v1/remove_moire",
                "image_base64": "source-b64",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["result"]["images"][0]["b64"] == "baidu-processed-b64"


def test_volcengine_chat_completion_returns_text(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "volcengine", "alias": "volc-chat", "key": "volc-key"})
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(
            200,
            json={"model": "doubao-seed", "choices": [{"message": {"content": "ok text"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post(
        "/v1/invocations",
        json={
            "provider": "volcengine",
            "capabilityKey": "doubao_seed_1_8",
            "model": "doubao-seed",
            "apiType": "chat_completions",
            "inputs": {"prompt": "describe", "image_url": "https://example.com/in.png"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["result"]["texts"] == ["ok text"]
    assert captured["url"].endswith("/api/v3/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer volc-key"
    assert captured["json"]["messages"][0]["content"][0]["type"] == "image_url"


def test_volcengine_image_generation_returns_url(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "volcengine", "alias": "volc-image", "key": "volc-key"})

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(
            200,
            json={"data": [{"url": "https://example.com/volc-out.png"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post(
        "/v1/invocations",
        json={
            "provider": "volcengine",
            "capabilityKey": "doubao_seedream_4_5",
            "model": "doubao-seedream",
            "apiType": "image_generation",
            "inputs": {"prompt": "dress", "size": "2K", "response_format": "url"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["result"]["images"][0]["url"] == "https://example.com/volc-out.png"


def test_volcengine_video_generation_submits_async_task(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "volcengine", "alias": "volc-video", "key": "volc-key"})
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(
            200,
            json={"id": "video-task-1"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post(
        "/v1/invocations",
        json={
            "provider": "volcengine",
            "capabilityKey": "doubao_seedance_1_5_pro",
            "model": "doubao-seedance",
            "apiType": "video_generation",
            "inputs": {
                "prompt": "小猫对着镜头打哈欠",
                "image_url": "https://example.com/frame.png",
                "duration": 5,
                "ratio": "16:9",
                "resolution": "720p",
                "watermark": False,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["vendorTaskId"] == "video-task-1"
    assert captured["url"].endswith("/api/v3/contents/generations/tasks")
    assert captured["headers"]["Authorization"] == "Bearer volc-key"
    assert captured["json"]["content"] == [
        {"type": "text", "text": "小猫对着镜头打哈欠"},
        {"type": "image_url", "image_url": {"url": "https://example.com/frame.png"}, "role": "first_frame"},
    ]
    assert captured["json"]["duration"] == 5
    assert captured["json"]["watermark"] is False


def test_volcengine_video_generation_refresh_returns_video(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "volcengine", "alias": "volc-video-refresh", "key": "volc-key"})

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(200, json={"id": "video-task-2"}, request=httpx.Request("POST", url))

    def fake_get(url, headers=None, timeout=None):
        assert url.endswith("/api/v3/contents/generations/tasks/video-task-2")
        assert headers["Authorization"] == "Bearer volc-key"
        return httpx.Response(
            200,
            json={
                "id": "video-task-2",
                "status": "succeeded",
                "content": {
                    "video_url": "https://example.com/out.mp4",
                    "last_frame_url": "https://example.com/last.png",
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)

    created = client.post(
        "/v1/invocations",
        json={
            "provider": "volcengine",
            "capabilityKey": "doubao_seedance_1_5_pro",
            "model": "doubao-seedance",
            "apiType": "video_generation",
            "inputs": {"prompt": "video"},
        },
    ).json()

    response = client.get(f"/v1/invocations/{created['vendorInvocationId']}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["result"]["videos"][0]["url"] == "https://example.com/out.mp4"
    assert body["result"]["images"][0]["url"] == "https://example.com/last.png"


def test_openai_image_edit_calls_real_contract(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "openai", "alias": "image-edit", "key": "sk-test-image-edit"})
    captured = {}

    def fake_get(url, timeout=None):
        return httpx.Response(
            200,
            content=b"image-bytes",
            headers={"content-type": "image/png"},
            request=httpx.Request("GET", url),
        )

    def fake_post(url, headers=None, json=None, data=None, files=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["data"] = data
        captured["files"] = files
        captured["timeout"] = timeout
        return httpx.Response(
            200,
            json={"data": [{"b64_json": "abc123", "revised_prompt": "revised"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post(
        "/v1/invocations",
        json={
            "provider": "openai",
            "capabilityKey": "gpt_image_2_edit",
            "model": "gpt-image-2",
            "apiType": "image_edit",
            "inputs": {
                "prompt": "replace background",
                "image_url": "https://example.com/source.png",
                "mask_url": "https://example.com/mask.png",
                "size": "1024x1024",
                "quality": "auto",
                "input_fidelity": "high",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["result"]["images"][0]["b64"] == "abc123"
    assert body["result"]["texts"] == ["revised"]
    assert captured["url"].endswith("/v1/images/edits")
    assert captured["json"] is None
    assert captured["data"]["model"] == "gpt-image-2"
    assert captured["data"]["prompt"] == "replace background"
    assert captured["data"]["size"] == "1024x1024"
    assert "input_fidelity" not in captured["data"]
    assert [item[0] for item in captured["files"]] == ["image[]", "mask"]


def test_openai_image_generation_calls_real_contract(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "openai", "alias": "image-generate", "key": "sk-test-image-generate"})
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(
            200,
            json={"data": [{"url": "https://example.com/openai-generated.png"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post(
        "/v1/invocations",
        json={
            "provider": "openai",
            "capabilityKey": "gpt_image_2_generate",
            "model": "gpt-image-2",
            "apiType": "image_generation",
            "inputs": {
                "prompt": "a textile pattern for a summer dress",
                "size": "1024x1024",
                "quality": "auto",
                "background": "auto",
                "output_format": "png",
                "n": 1,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["result"]["images"][0]["url"] == "https://example.com/openai-generated.png"
    assert captured["url"].endswith("/v1/images/generations")
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert captured["json"] == {
        "model": "gpt-image-2",
        "prompt": "a textile pattern for a summer dress",
        "size": "1024x1024",
        "quality": "auto",
        "background": "auto",
        "n": 1,
        "output_format": "png",
    }
    assert "images" not in captured["json"]
    assert "mask" not in captured["json"]


def test_openai_image_generation_batch_submit_and_poll(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "openai", "alias": "image-generate-batch", "key": "sk-test-image-batch"})
    captured: dict[str, object] = {}

    def fake_post(url, headers=None, json=None, data=None, files=None, timeout=None):
        if url.endswith("/v1/files"):
            captured["file_data"] = data
            captured["file_tuple"] = files["file"]
            return httpx.Response(
                200,
                json={"id": "file_batch_input"},
                request=httpx.Request("POST", url),
            )
        if url.endswith("/v1/batches"):
            captured["batch_json"] = json
            return httpx.Response(
                200,
                json={
                    "id": "batch_123",
                    "status": "validating",
                    "endpoint": "/v1/images/generations",
                    "input_file_id": "file_batch_input",
                },
                request=httpx.Request("POST", url),
            )
        raise AssertionError(url)

    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/v1/batches/batch_123"):
            return httpx.Response(
                200,
                json={
                    "id": "batch_123",
                    "status": "completed",
                    "endpoint": "/v1/images/generations",
                    "input_file_id": "file_batch_input",
                    "output_file_id": "file_batch_output",
                    "request_counts": {"total": 1, "completed": 1, "failed": 0},
                },
                request=httpx.Request("GET", url),
            )
        if url.endswith("/v1/files/file_batch_output/content"):
            line = {
                "custom_id": "case-001",
                "response": {
                    "status_code": 200,
                    "body": {"data": [{"url": "https://example.com/batch-image.png", "revised_prompt": "batch revised"}]},
                },
                "error": None,
            }
            return httpx.Response(200, text=json.dumps(line), request=httpx.Request("GET", url))
        raise AssertionError(url)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)

    submitted = client.post(
        "/v1/invocations",
        json={
            "provider": "openai",
            "capabilityKey": "gpt_image_2_generate",
            "model": "gpt-image-2",
            "apiType": "image_generation",
            "executionMode": "batch_submit_poll",
            "inputs": {
                "prompt": "low cost textile batch",
                "size": "1024x1024",
                "quality": "low",
                "custom_id": "case-001",
            },
        },
    )

    assert submitted.status_code == 200
    body = submitted.json()
    assert body["status"] == "running"
    assert body["vendorTaskId"] == "batch_123"
    assert captured["file_data"] == {"purpose": "batch"}
    file_name, file_bytes, file_type = captured["file_tuple"]
    assert file_name == "openai_batch_input.jsonl"
    assert file_type == "application/jsonl"
    batch_line = json.loads(file_bytes.decode("utf-8").strip())
    assert batch_line == {
        "custom_id": "case-001",
        "method": "POST",
        "url": "/v1/images/generations",
        "body": {
            "model": "gpt-image-2",
            "prompt": "low cost textile batch",
            "size": "1024x1024",
            "quality": "low",
        },
    }
    assert captured["batch_json"]["input_file_id"] == "file_batch_input"
    assert captured["batch_json"]["endpoint"] == "/v1/images/generations"
    assert captured["batch_json"]["completion_window"] == "24h"

    fetched = client.get(f"/v1/invocations/{body['vendorInvocationId']}")

    assert fetched.status_code == 200
    done = fetched.json()
    assert done["status"] == "succeeded"
    assert done["result"]["images"][0]["url"] == "https://example.com/batch-image.png"
    assert done["result"]["images"][0]["metadata"]["customId"] == "case-001"
    assert done["result"]["texts"] == ["batch revised"]


def test_invocation_uses_request_credentials_without_persisting_secret(monkeypatch) -> None:
    client = TestClient(app)
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers or {}
        return httpx.Response(
            200,
            json={"data": [{"url": "https://example.com/request-key.png"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post(
        "/v1/invocations",
        json={
            "provider": "openai",
            "capabilityKey": "gpt_image_2_generate",
            "model": "gpt-image-2",
            "apiType": "image_generation",
            "credentials": {"keyId": "backend-key-1", "key": "sk-request-secret"},
            "inputs": {"prompt": "credential boundary check"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert captured["headers"]["Authorization"] == "Bearer sk-request-secret"

    record = vendor_storage.get_invocation(body["vendorInvocationId"])
    assert record is not None
    stored_request = record["request"]
    assert stored_request["credentials"] == {
        "present": True,
        "source": "backend-request",
        "keyId": "backend-key-1",
    }
    assert "sk-request-secret" not in json.dumps(stored_request)


def test_vendor_key_concurrency_limit_returns_retryable_error(monkeypatch) -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/keys",
        json={
            "provider": "openai",
            "alias": "image-generate-busy",
            "key": "sk-test-busy-key",
            "maxConcurrency": 1,
        },
    )
    assert created.status_code == 200

    active_backup = dict(invocation_store._active_by_key)  # noqa: SLF001 - targeted process-local guard test
    try:
        keys = client.get("/v1/keys?provider=openai").json()["items"]
        for key in keys:
            invocation_store._active_by_key[key["id"]] = int(key.get("maxConcurrency") or 1)  # noqa: SLF001

        def fail_if_called(*args, **kwargs):
            raise AssertionError("vendor API should not be called when all keys are busy")

        monkeypatch.setattr(httpx, "post", fail_if_called)
        response = client.post(
            "/v1/invocations",
            json={
                "provider": "openai",
                "capabilityKey": "gpt_image_2_generate",
                "model": "gpt-image-2",
                "apiType": "image_generation",
                "inputs": {"prompt": "busy"},
            },
        )
    finally:
        invocation_store._active_by_key.clear()  # noqa: SLF001
        invocation_store._active_by_key.update(active_backup)  # noqa: SLF001

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "VENDOR_API_KEY_CONCURRENCY_LIMITED"
    assert body["error"]["retryable"] is True


def test_usage_summary_returns_recent_vendor_logs(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "openai", "alias": "usage-summary", "key": "sk-test-usage-summary"})

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(
            200,
            json={"data": [{"url": "https://example.com/openai-usage.png"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client.post(
        "/v1/invocations",
        json={
            "provider": "openai",
            "capabilityKey": "gpt_image_2_generate",
            "model": "gpt-image-2",
            "apiType": "image_generation",
            "inputs": {"prompt": "usage summary"},
        },
    )

    response = client.get("/v1/usage/summary?windowHours=24")

    assert response.status_code == 200
    body = response.json()
    assert body["windowHours"] == 24
    assert any(item["provider"] == "openai" and item["status"] == "succeeded" for item in body["items"])


def test_async_kie_invocation_can_be_polled(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "kie", "alias": "test-kie", "key": "kie-test-key"})

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(
            200,
            json={"code": 200, "data": {"taskId": "kie_task_1"}},
            request=httpx.Request("POST", url),
        )

    def fake_get(url, headers=None, params=None, timeout=None):
        return httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "state": "success",
                    "result": "{\"resultUrls\":[\"https://example.com/kie-out.png\"]}",
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)

    submit = client.post(
        "/v1/invocations",
        json={
            "provider": "kie",
            "capabilityKey": "nano_banana_pro_image_to_image",
            "model": "nano-banana-pro",
            "apiType": "market_image_to_image",
            "inputs": {"prompt": "test"},
        },
    )

    assert submit.status_code == 200
    submitted = submit.json()
    assert submitted["status"] == "running"
    assert submitted["vendorTaskId"] == "kie_task_1"

    fetched = client.get(f"/v1/invocations/{submitted['vendorInvocationId']}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["vendorInvocationId"] == submitted["vendorInvocationId"]
    assert body["status"] == "succeeded"
    assert body["result"]["images"][0]["url"] == "https://example.com/kie-out.png"


def test_kie_poll_parses_result_json_field(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "kie", "alias": "test-kie-result-json", "key": "kie-test-key"})

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(
            200,
            json={"code": 200, "data": {"taskId": "kie_task_result_json"}},
            request=httpx.Request("POST", url),
        )

    def fake_get(url, headers=None, params=None, timeout=None):
        return httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "state": "success",
                    "resultJson": "{\"resultUrls\":[\"https://example.com/kie-result-json.png\"]}",
                },
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)

    submit = client.post(
        "/v1/invocations",
        json={
            "provider": "kie",
            "capabilityKey": "nano_banana_pro_image_to_image",
            "model": "nano-banana-pro",
            "apiType": "market_image_to_image",
            "inputs": {"prompt": "test"},
        },
    )
    fetched = client.get(f"/v1/invocations/{submit.json()['vendorInvocationId']}")

    assert fetched.status_code == 200
    assert fetched.json()["result"]["images"][0]["url"] == "https://example.com/kie-result-json.png"


def test_kie_submit_maps_image_urls_alias_to_configured_input_array(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "kie", "alias": "test-kie-input-alias", "key": "kie-test-key"})
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return httpx.Response(
            200,
            json={"code": 200, "data": {"taskId": "kie_task_alias"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post(
        "/v1/invocations",
        json={
            "provider": "kie",
            "capabilityKey": "flux2_pro_image_to_image",
            "model": "flux-2/pro-image-to-image",
            "apiType": "market_image_to_image",
            "inputs": {
                "prompt": "test",
                "image_urls": "https://example.com/input.png",
                "input_array_target": "input_urls",
            },
        },
    )

    assert response.status_code == 200
    assert captured["json"]["input"]["input_urls"] == ["https://example.com/input.png"]
    assert "image_urls" not in captured["json"]["input"]
    assert "input_array_target" not in captured["json"]["input"]


def test_kie_submit_retries_transient_create_failure(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "kie", "alias": "test-kie-retry", "key": "kie-test-retry-key"})
    calls = {"post": 0}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"] += 1
        if calls["post"] == 1:
            return httpx.Response(
                502,
                json={"code": 500, "msg": "bad gateway"},
                request=httpx.Request("POST", url),
            )
        return httpx.Response(
            200,
            json={"code": 200, "data": {"taskId": "kie_task_retry"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = client.post(
        "/v1/invocations",
        json={
            "provider": "kie",
            "capabilityKey": "nano_banana_pro_image_to_image",
            "model": "nano-banana-pro",
            "apiType": "market_image_to_image",
            "inputs": {"prompt": "retry create"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["vendorTaskId"] == "kie_task_retry"
    assert calls["post"] == 2
    assert [item["httpStatus"] for item in body["raw"]["attempts"]] == [502, 200]


def test_key_list_does_not_expose_secret() -> None:
    client = TestClient(app)

    created = client.post(
        "/v1/keys",
        json={"provider": "openai", "alias": "main", "key": "sk-test-1234567890"},
    )

    assert created.status_code == 200
    body = created.json()
    assert body["keyPreview"] == "sk-t...7890"
    assert "key" not in body

    listed = client.get("/v1/keys?provider=openai")
    assert listed.status_code == 200
    previews = {item["keyPreview"] for item in listed.json()["items"]}
    assert "sk-t...7890" in previews


def test_key_storage_encrypts_new_keys_when_secret_is_configured(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("VENDOR_API_KEY_ENCRYPTION_SECRET", "unit-test-encryption-secret")
    try:
        client = TestClient(app)

        created = client.post(
            "/v1/keys",
            json={"provider": "openai", "alias": "encrypted", "key": "sk-encrypted-123456", "secret": "secret-value"},
        )

        assert created.status_code == 200
        key_id = created.json()["id"]
        with sqlite3.connect(vendor_storage._db_path.as_posix()) as conn:  # noqa: SLF001
            row = conn.execute("select key_value, secret_value from vendor_api_keys where id = ?", (key_id,)).fetchone()
        assert row is not None
        assert row[0].startswith("enc:v1:")
        assert row[1].startswith("enc:v1:")
        assert "sk-encrypted-123456" not in row[0]
        assert "secret-value" not in row[1]

        listed = client.get(f"/v1/keys?provider=openai").json()["items"]
        item = next(item for item in listed if item["id"] == key_id)
        assert item["keyPreview"] == "sk-e...3456"
        assert item["metadata"]["security"]["keyEncrypted"] is True
        assert item["metadata"]["security"]["secretEncrypted"] is True
    finally:
        get_settings.cache_clear()
