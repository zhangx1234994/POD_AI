from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from PIL import Image

import app.services.media_ingest as media_ingest_module
import app.services.vendor_media as vendor_media_module
from app.services.vendor_media import persist_vendor_media_payload


def _png_bytes(size: tuple[int, int], color: tuple[int, int, int, int] = (255, 0, 0, 255)) -> bytes:
    output = BytesIO()
    Image.new("RGBA", size, color).save(output, format="PNG")
    return output.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def test_persist_vendor_media_can_enforce_desired_image_size(monkeypatch) -> None:
    uploads: list[dict[str, object]] = []

    def fake_get(url: str, timeout: int = 60) -> _FakeResponse:
        assert url == "https://oss.example.com/vendor-output.png"
        return _FakeResponse(_png_bytes((1024, 1024)))

    def fake_upload_bytes(**kwargs):
        uploads.append(kwargs)
        return {"url": "https://oss.example.com/resized.png", "objectKey": "resized-key"}

    monkeypatch.setattr(vendor_media_module.httpx, "get", fake_get)
    monkeypatch.setattr(media_ingest_module.oss_service, "upload_bytes", fake_upload_bytes)
    monkeypatch.setattr(media_ingest_module, "get_settings", lambda: SimpleNamespace(output_image_default_dpi=150))

    result = persist_vendor_media_payload(
        {
            "images": [
                {
                    "ossUrl": "https://oss.example.com/vendor-output.png",
                    "url": "https://oss.example.com/vendor-output.png",
                }
            ]
        },
        user_id="tester",
        desired_image_size=(640, 360),
    )

    assert result["imageUrls"] == ["https://oss.example.com/resized.png"]
    assert result["images"][0]["width"] == 640
    assert result["images"][0]["height"] == 360
    assert result["images"][0]["postprocess"]["strategy"] == "fit_pad_keep_original_size"
    assert uploads[0]["content_type"] == "image/png"
    stored = Image.open(BytesIO(uploads[0]["data"]))
    assert stored.info.get("dpi") == (150.01239999999999, 150.01239999999999)


def test_persist_vendor_media_keeps_existing_image_when_size_already_matches(monkeypatch) -> None:
    def fake_get(url: str, timeout: int = 60) -> _FakeResponse:
        return _FakeResponse(_png_bytes((640, 360)))

    def fail_upload_bytes(**kwargs):  # pragma: no cover - should not be called
        raise AssertionError("upload should not be called when size already matches")

    monkeypatch.setattr(vendor_media_module.httpx, "get", fake_get)
    monkeypatch.setattr(media_ingest_module.oss_service, "upload_bytes", fail_upload_bytes)

    result = persist_vendor_media_payload(
        {"images": [{"ossUrl": "https://oss.example.com/already-ok.png"}]},
        user_id="tester",
        desired_image_size=(640, 360),
    )

    assert result["imageUrls"] == ["https://oss.example.com/already-ok.png"]
    assert result["images"][0]["width"] == 640
    assert result["images"][0]["height"] == 360
