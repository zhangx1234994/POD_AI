from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app import providers as provider_module
from app.config import get_settings
from app.invocations import invocation_store
from app.main import app


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


def test_openai_image_edit_calls_real_contract(monkeypatch) -> None:
    client = TestClient(app)
    client.post("/v1/keys", json={"provider": "openai", "alias": "image-edit", "key": "sk-test-image-edit"})
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(
            200,
            json={"data": [{"b64_json": "abc123", "revised_prompt": "revised"}]},
            request=httpx.Request("POST", url),
        )

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
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["result"]["images"][0]["b64"] == "abc123"
    assert body["result"]["texts"] == ["revised"]
    assert captured["url"].endswith("/v1/images/edits")
    assert captured["json"]["images"] == [{"image_url": "https://example.com/source.png"}]
    assert captured["json"]["mask"] == {"image_url": "https://example.com/mask.png"}


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
