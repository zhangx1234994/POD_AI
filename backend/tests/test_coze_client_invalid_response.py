import pytest


class _FakeResponse:
    def __init__(self, *, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text

    def json(self):
        raise ValueError("not json")


def test_coze_client_invalid_response_includes_status_and_body_snippet(monkeypatch):
    from app.services.coze_client import CozeWorkflowClient

    def _fake_post(*args, **kwargs):
        return _FakeResponse(status_code=502, text="<html>Bad Gateway</html>")

    monkeypatch.setattr("app.services.coze_client.httpx.post", _fake_post)

    c = CozeWorkflowClient()
    # Force config in-memory so the client doesn't read env in this test.
    c._settings.coze_base_url = "http://coze.local"
    c._settings.coze_api_token = "token"

    with pytest.raises(Exception) as excinfo:
        c.run_workflow(workflow_id="1", parameters={}, is_async=False)
    assert "COZE_INVALID_RESPONSE" in str(excinfo.value)
    assert "status=502" in str(excinfo.value)
    assert "Bad Gateway" in str(excinfo.value)

