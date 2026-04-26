from __future__ import annotations

import httpx

from app.models.integration import Ability, Executor
from app.services.vendor_api_client import vendor_api_client


class _FakeClient:
    def __init__(self, captured: dict, *, response_payload: dict):
        self._captured = captured
        self._response_payload = response_payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, json: dict | None = None, headers: dict | None = None):
        self._captured["method"] = "POST"
        self._captured["url"] = url
        self._captured["json"] = json or {}
        self._captured["headers"] = headers or {}
        return httpx.Response(
            200,
            json=self._response_payload,
            request=httpx.Request("POST", url),
        )


def test_vendor_api_client_sends_backend_credentials_on_invoke(monkeypatch) -> None:
    captured: dict = {}
    payload = {
        "success": True,
        "status": "succeeded",
        "provider": "openai",
        "model": "gpt-image-2",
        "vendorInvocationId": "vinv_1",
        "vendorTaskId": None,
        "result": {"images": [{"url": "https://example.com/out.png"}], "videos": [], "texts": []},
        "error": None,
        "raw": {},
    }
    monkeypatch.setattr(
        "app.services.vendor_api_client.httpx.Client",
        lambda timeout: _FakeClient(captured, response_payload=payload),
    )

    executor = Executor(id="executor_vendor", type="vendor_api", base_url="http://vendor.local", max_concurrency=2)
    ability = Ability(provider="openai", capability_key="gpt_image_2_generate")

    result = vendor_api_client.invoke(
        executor=executor,
        ability=ability,
        inputs={"prompt": "test"},
        assets=[],
        request_id="req_1",
        trace_id="trace_1",
        credentials={"keyId": "apikey_1", "key": "sk-secret"},
    )

    assert captured["url"] == "http://vendor.local/v1/invocations"
    assert captured["json"]["credentials"] == {"keyId": "apikey_1", "key": "sk-secret"}
    assert result["metadata"]["vendorInvocationId"] == "vinv_1"
    assert result["resultUrls"] == ["https://example.com/out.png"]


def test_vendor_api_client_uses_refresh_endpoint_when_fetching_with_credentials(monkeypatch) -> None:
    captured: dict = {}
    payload = {
        "success": False,
        "status": "running",
        "provider": "kie",
        "model": "kie-market",
        "vendorInvocationId": "vinv_2",
        "vendorTaskId": "upstream_1",
        "result": {"images": [], "videos": [], "texts": []},
        "error": None,
        "raw": {},
    }
    monkeypatch.setattr(
        "app.services.vendor_api_client.httpx.Client",
        lambda timeout: _FakeClient(captured, response_payload=payload),
    )

    executor = Executor(id="executor_vendor", type="vendor_api", base_url="http://vendor.local")

    result = vendor_api_client.fetch(
        executor=executor,
        vendor_invocation_id="vinv_2",
        credentials={"keyId": "apikey_2", "key": "kie-secret"},
    )

    assert captured["url"] == "http://vendor.local/v1/invocations/vinv_2/refresh"
    assert captured["json"] == {"credentials": {"keyId": "apikey_2", "key": "kie-secret"}}
    assert result["metadata"]["vendorTaskId"] == "upstream_1"
