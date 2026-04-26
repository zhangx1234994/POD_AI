from __future__ import annotations

from types import SimpleNamespace

import httpx

import app.services.vendor_api_client as vendor_api_client_module
from app.services.vendor_api_client import VendorApiClient


def test_vendor_api_response_normalizes_assets_and_metadata() -> None:
    executor = SimpleNamespace(id="executor_vendor_api_global_default", base_url="http://vendor.local", config={})

    normalized = VendorApiClient.normalize_invocation_response(
        executor=executor,  # type: ignore[arg-type]
        data={
            "success": True,
            "status": "succeeded",
            "provider": "openai",
            "model": "gpt-image-2",
            "vendorInvocationId": "vinv_1",
            "vendorTaskId": None,
            "result": {
                "images": [{"url": "https://example.com/out.png", "role": "output", "mimeType": "image/png"}],
                "videos": [],
                "texts": ["ok"],
                "json": {"x": 1},
                "usage": {"images": 1},
                "cost": {"amount": 0.08},
            },
            "raw": {"adapter": "contract-v1"},
        },
    )

    assert normalized["provider"] == "openai"
    assert normalized["status"] == "succeeded"
    assert normalized["vendorInvocationId"] == "vinv_1"
    assert normalized["resultUrls"] == ["https://example.com/out.png"]
    assert normalized["images"][0]["contentType"] == "image/png"
    assert normalized["metadata"]["vendorInvocationId"] == "vinv_1"
    assert normalized["metadata"]["executorId"] == "executor_vendor_api_global_default"
    assert normalized["texts"] == ["ok"]


def test_vendor_api_invoke_forwards_metadata_request_endpoint(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, timeout: int) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, json: dict, headers: dict) -> httpx.Response:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "status": "succeeded",
                    "provider": "baidu",
                    "model": "quality_upgrade",
                    "vendorInvocationId": "vinv_1",
                    "result": {"images": [{"b64": "out-b64"}]},
                },
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(vendor_api_client_module.httpx, "Client", FakeClient)
    executor = SimpleNamespace(id="executor_vendor_api_domestic_default", base_url="http://vendor.local", config={}, max_concurrency=2)
    ability = SimpleNamespace(
        provider="baidu",
        capability_key="quality_upgrade",
        extra_metadata={
            "api_type": "baidu_image_process",
            "model_id": "quality_upgrade",
            "request_endpoint": "/rest/2.0/image-process/v1/image_quality_enhance",
        },
    )

    result = VendorApiClient().invoke(
        executor=executor,  # type: ignore[arg-type]
        ability=ability,  # type: ignore[arg-type]
        inputs={"image_base64": "in-b64"},
        assets=None,
        request_id="req_1",
    )

    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["inputs"]["request_endpoint"] == "/rest/2.0/image-process/v1/image_quality_enhance"
    assert result["assets"][0]["base64"] == "out-b64"
    assert result["assets"][0]["contentType"] is None
