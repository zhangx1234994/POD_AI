from __future__ import annotations

import base64

import httpx
import pytest

from app.core.config import get_settings
from app.services import podi_image_tools
from app.services.image_ops_client import (
    ImageOpsClient,
    ImageOpsLocalExecutionDisabled,
    ImageOpsRemoteError,
    image_ops_client,
)


_MINIMAL_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8B9l8AAAAASUVORK5CYII="
)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_image_ops_client_uses_remote_service_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_OPS_BASE_URL", "http://image-ops.internal")
    monkeypatch.setenv("IMAGE_OPS_SERVICE_TOKEN", "secret-token")
    get_settings.cache_clear()

    calls: dict[str, object] = {}

    def _fake_post(url: str, json=None, headers=None, timeout=None):  # noqa: A002 - mirror httpx API
        calls["url"] = url
        calls["json"] = json
        calls["headers"] = headers
        calls["timeout"] = timeout
        payload = {
            "contentBase64": base64.b64encode(_MINIMAL_PNG_BYTES).decode("utf-8"),
            "contentType": "image/png",
            "fileExt": ".png",
        }
        return _FakeResponse(payload)

    monkeypatch.setattr(httpx, "post", _fake_post)
    try:
        client = ImageOpsClient()
        content, content_type, file_ext = client.upscale_resize(
            image_bytes=_MINIMAL_PNG_BYTES,
            max_long_edge=2048,
            output_format="png",
            allow_local_fallback=False,
        )
        assert content == _MINIMAL_PNG_BYTES
        assert content_type == "image/png"
        assert file_ext == ".png"
        assert calls["url"] == "http://image-ops.internal/internal/image-ops/upscale-resize"
        assert calls["headers"] == {
            "Content-Type": "application/json",
            "Authorization": "Bearer secret-token",
        }
        assert calls["json"]["params"]["max_long_edge"] == 2048
    finally:
        get_settings.cache_clear()


def test_image_ops_client_raises_remote_error_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IMAGE_OPS_BASE_URL", "http://image-ops.internal")
    get_settings.cache_clear()

    def _fake_post(url: str, json=None, headers=None, timeout=None):  # noqa: A002 - mirror httpx API
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "post", _fake_post)
    try:
        client = ImageOpsClient()
        with pytest.raises(ImageOpsRemoteError):
            client.set_dpi(
                image_bytes=_MINIMAL_PNG_BYTES,
                dpi=300,
                allow_local_fallback=False,
            )
    finally:
        get_settings.cache_clear()


def test_image_ops_client_falls_back_to_local_when_remote_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IMAGE_OPS_BASE_URL", "http://image-ops.internal")
    monkeypatch.setenv("IMAGE_OPS_LOCAL_FALLBACK_ENABLED", "true")
    get_settings.cache_clear()

    def _fake_post(url: str, json=None, headers=None, timeout=None):  # noqa: A002 - mirror httpx API
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "post", _fake_post)
    monkeypatch.setattr(
        podi_image_tools,
        "set_dpi",
        lambda *, image_bytes, dpi: (b"fallback", "image/png", ".png"),
    )
    try:
        client = ImageOpsClient()
        content, content_type, file_ext = client.set_dpi(
            image_bytes=_MINIMAL_PNG_BYTES,
            dpi=300,
        )
        assert content == b"fallback"
        assert content_type == "image/png"
        assert file_ext == ".png"
    finally:
        get_settings.cache_clear()


def test_image_ops_client_blocks_local_when_remote_missing_and_fallback_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IMAGE_OPS_BASE_URL", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(ImageOpsLocalExecutionDisabled):
            image_ops_client.upscale_resize(
                image_bytes=_MINIMAL_PNG_BYTES,
                max_long_edge=2048,
                output_format="png",
                allow_local_fallback=False,
            )
    finally:
        get_settings.cache_clear()
