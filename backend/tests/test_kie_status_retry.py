import pytest
from types import SimpleNamespace


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", json_payload=None):
        self.status_code = status_code
        self.text = text
        self._json_payload = json_payload

    def json(self):
        if self._json_payload is None:
            raise ValueError("not json")
        return self._json_payload


def test_kie_status_retry_retries_on_5xx_then_succeeds(monkeypatch):
    from app.services.integration_test import IntegrationTestService

    calls = {"n": 0}

    def _fake_get(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            return _FakeResponse(502, text="<html>bad gateway</html>", json_payload={"code": 500})
        return _FakeResponse(200, json_payload={"data": {"state": "success"}})

    monkeypatch.setattr("app.services.integration_test.httpx.get", _fake_get)

    svc = IntegrationTestService()
    out = svc._fetch_kie_task("https://api.kie.ai", {"Authorization": "Bearer x"}, "t1")
    assert out["data"]["state"] == "success"
    assert calls["n"] == 2


def test_kie_status_retry_eventually_raises_with_snippet(monkeypatch):
    from app.services.integration_test import IntegrationTestService

    def _fake_get(*args, **kwargs):
        return _FakeResponse(502, text="<html>bad gateway</html>", json_payload={"code": 500})

    monkeypatch.setattr("app.services.integration_test.httpx.get", _fake_get)

    svc = IntegrationTestService()
    with pytest.raises(Exception) as excinfo:
        svc._fetch_kie_task("https://api.kie.ai", {"Authorization": "Bearer x"}, "t1")
    assert "KIE_STATUS_HTTP_502" in str(excinfo.value)
    assert "bad gateway" in str(excinfo.value).lower()


def test_kie_status_fetch_supports_veo_endpoint(monkeypatch):
    from app.services.integration_test import IntegrationTestService

    captured = {}

    def _fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        return _FakeResponse(200, json_payload={"data": {"successFlag": 1, "response": {"videoUrls": ["https://x/out.mp4"]}}})

    monkeypatch.setattr("app.services.integration_test.httpx.get", _fake_get)

    svc = IntegrationTestService()
    out = svc._fetch_kie_task(
        "https://api.kie.ai",
        {"Authorization": "Bearer x"},
        "t1",
        status_endpoint="/api/v1/veo/record-info",
    )

    assert captured["url"] == "https://api.kie.ai/api/v1/veo/record-info"
    assert captured["params"] == {"taskId": "t1"}
    assert svc._extract_kie_state(out) == "success"
    urls, parsed = svc._parse_kie_result(out)
    assert urls == ["https://x/out.mp4"]
    assert parsed == {"videoUrls": ["https://x/out.mp4"]}


def test_kie_veo_run_forces_fast_model_and_direct_payload(monkeypatch):
    from app.services.integration_test import IntegrationTestService

    svc = IntegrationTestService()
    monkeypatch.setattr(
        svc,
        "_get_executor",
        lambda executor_id: SimpleNamespace(id=executor_id, type="kie", config={}, base_url="https://api.kie.ai"),
    )
    monkeypatch.setattr(
        svc,
        "_pick_kie_api_key",
        lambda executor, exclude_ids=None: SimpleNamespace(id="legacy", key="test-key"),
    )
    monkeypatch.setattr(
        svc,
        "_prepare_kie_client",
        lambda executor, api_key: ("https://api.kie.ai", {"Authorization": f"Bearer {api_key.key}"}),
    )

    captured = {}

    def _fake_post(url, **kwargs):
        captured["post_url"] = url
        captured["json"] = kwargs.get("json")
        return _FakeResponse(200, json_payload={"code": 200, "data": {"taskId": "veo_task_1"}})

    def _fake_get(url, **kwargs):
        captured["get_url"] = url
        return _FakeResponse(
            200,
            json_payload={
                "data": {
                    "successFlag": 1,
                    "response": {"videoUrls": ["https://kie.example/result.mp4"]},
                }
            },
        )

    def _fake_store_remote_asset(remote_url, *, user_id, filename, tag):
        if tag == "kie-input":
            return {"ossUrl": "https://podi.oss/input.png", "ossKey": "input.png", "contentType": "image/png", "tag": tag}
        return {
            "ossUrl": "https://podi.oss/result.mp4",
            "ossKey": "result.mp4",
            "sourceUrl": remote_url,
            "contentType": "video/mp4",
            "tag": tag,
        }

    monkeypatch.setattr("app.services.integration_test.httpx.post", _fake_post)
    monkeypatch.setattr("app.services.integration_test.httpx.get", _fake_get)
    monkeypatch.setattr(svc, "_store_remote_asset", _fake_store_remote_asset)

    result = svc.run_kie_market_task(
        executor_id="executor_kie",
        endpoint="/api/v1/veo/generate",
        status_endpoint="/api/v1/veo/record-info",
        model="veo3",
        input_payload={
            "prompt": "make a product video",
            "imageUrls": ["https://example.com/input.png"],
            "aspect_ratio": "9:16",
            "durationSeconds": 8,
            "enableFallback": True,
        },
        input_array_target="imageUrls",
        poll_timeout=10,
        poll_interval=0.1,
    )

    assert captured["post_url"] == "https://api.kie.ai/api/v1/veo/generate"
    assert captured["get_url"] == "https://api.kie.ai/api/v1/veo/record-info"
    assert "input" not in captured["json"]
    assert captured["json"]["model"] == "veo3_fast"
    assert captured["json"]["aspectRatio"] == "9:16"
    assert "aspect_ratio" not in captured["json"]
    assert captured["json"]["duration"] == 8
    assert "durationSeconds" not in captured["json"]
    assert captured["json"]["imageUrls"] == ["https://podi.oss/input.png"]
    assert captured["json"]["enableFallback"] is False
    assert result["status"] == "succeeded"
    assert result["videoUrls"] == ["https://podi.oss/result.mp4"]
    assert result["storedAssets"][0]["type"] == "video"
