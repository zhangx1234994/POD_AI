from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

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


def test_unsupported_provider_returns_normalized_error() -> None:
    client = TestClient(app)

    response = client.post("/v1/providers/unknown/egress-check", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "VENDOR_API_PROVIDER_NOT_SUPPORTED"


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
