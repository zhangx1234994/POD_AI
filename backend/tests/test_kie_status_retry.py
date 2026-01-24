import pytest


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

