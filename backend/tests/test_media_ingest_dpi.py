from __future__ import annotations

import base64
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

import app.services.media_ingest as media_ingest_module
from app.services.media_ingest import MediaIngestService


def _png_bytes(size: tuple[int, int] = (32, 32)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (40, 120, 200)).save(output, format="PNG")
    return output.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes, content_type: str = "image/png") -> None:
        self.content = content
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self) -> None:
        return None


def _capture_upload(monkeypatch):
    uploads: list[dict[str, object]] = []

    def fake_upload_bytes(**kwargs):
        uploads.append(kwargs)
        return {"url": "https://oss.example.com/stored.png", "objectKey": "stored-key"}

    monkeypatch.setattr(media_ingest_module.oss_service, "upload_bytes", fake_upload_bytes)
    return uploads


def test_ingest_from_remote_url_writes_default_dpi_before_upload(monkeypatch) -> None:
    source = _png_bytes()
    uploads = _capture_upload(monkeypatch)

    def fake_get(url: str, timeout: int = 60) -> _FakeResponse:
        assert url == "https://vendor.example.com/generated.png"
        return _FakeResponse(source)

    monkeypatch.setattr(media_ingest_module.httpx, "get", fake_get)
    monkeypatch.setattr(media_ingest_module, "get_settings", lambda: SimpleNamespace(output_image_default_dpi=150))

    result = MediaIngestService().ingest_from_remote_url(
        "https://vendor.example.com/generated.png",
        user_id="tester",
        tag="generated",
    )

    assert result["dpi"] == 150
    assert uploads[0]["content_type"] == "image/png"
    stored = Image.open(BytesIO(uploads[0]["data"]))
    assert stored.info.get("dpi") == (150.01239999999999, 150.01239999999999)


def test_ingest_from_base64_writes_default_dpi_before_upload(monkeypatch) -> None:
    uploads = _capture_upload(monkeypatch)
    monkeypatch.setattr(media_ingest_module, "get_settings", lambda: SimpleNamespace(output_image_default_dpi=150))

    result = MediaIngestService().ingest_from_base64(
        base64.b64encode(_png_bytes()).decode("utf-8"),
        user_id="tester",
        mime_type="image/png",
        tag="generated",
    )

    assert result["dpi"] == 150
    stored = Image.open(BytesIO(uploads[0]["data"]))
    assert stored.info.get("dpi") == (150.01239999999999, 150.01239999999999)


def test_ingest_keeps_original_bytes_when_default_dpi_disabled(monkeypatch) -> None:
    source = _png_bytes()
    uploads = _capture_upload(monkeypatch)
    monkeypatch.setattr(media_ingest_module, "get_settings", lambda: SimpleNamespace(output_image_default_dpi=0))

    result = MediaIngestService().ingest_from_base64(
        base64.b64encode(source).decode("utf-8"),
        user_id="tester",
        mime_type="image/png",
        tag="generated",
    )

    assert result["dpi"] is None
    assert uploads[0]["data"] == source


def test_upload_generated_image_bytes_writes_default_dpi(monkeypatch) -> None:
    uploads = _capture_upload(monkeypatch)
    monkeypatch.setattr(media_ingest_module, "get_settings", lambda: SimpleNamespace(output_image_default_dpi=150))

    result = MediaIngestService().upload_generated_image_bytes(
        data=_png_bytes(),
        user_id="tester",
        filename="generated.png",
        content_type="image/png",
        tag="generated-result",
    )

    assert result["dpi"] == 150
    assert result["url"] == "https://oss.example.com/stored.png"
    assert result["objectKey"] == "stored-key"
    assert result["tag"] == "generated-result"
    stored = Image.open(BytesIO(uploads[0]["data"]))
    assert stored.info.get("dpi") == (150.01239999999999, 150.01239999999999)
