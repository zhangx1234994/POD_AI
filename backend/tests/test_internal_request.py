from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.deps.internal import is_internal_request


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _request(client_host: str, headers: dict[str, str] | None = None):
    return SimpleNamespace(client=SimpleNamespace(host=client_host), headers=headers or {})


def test_public_request_cannot_spoof_forwarded_for(monkeypatch):
    monkeypatch.setenv("COZE_TRUSTED_IPS", "")
    get_settings.cache_clear()

    request = _request("8.8.8.8", {"x-forwarded-for": "127.0.0.1"})

    assert is_internal_request(request) is False


def test_private_direct_request_is_internal(monkeypatch):
    monkeypatch.setenv("COZE_TRUSTED_IPS", "")
    get_settings.cache_clear()

    assert is_internal_request(_request("172.18.0.5")) is True


def test_trusted_public_host_is_internal(monkeypatch):
    monkeypatch.setenv("COZE_TRUSTED_IPS", "114.55.0.56")
    get_settings.cache_clear()

    assert is_internal_request(_request("114.55.0.56")) is True


def test_trusted_proxy_does_not_hide_external_caller(monkeypatch):
    monkeypatch.setenv("COZE_TRUSTED_IPS", "114.55.0.56")
    get_settings.cache_clear()

    request = _request("114.55.0.56", {"x-forwarded-for": "8.8.8.8"})

    assert is_internal_request(request) is False
