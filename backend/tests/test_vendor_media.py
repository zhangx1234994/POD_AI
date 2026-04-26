from __future__ import annotations

from app.services import vendor_media


def test_persist_vendor_media_payload_uploads_remote_images(monkeypatch) -> None:
    def fake_ingest(url: str, *, user_id: str, tag: str | None = None) -> dict:
        return {
            "sourceUrl": url,
            "ossUrl": "https://oss.example.com/stored.png",
            "ossKey": "stored.png",
            "contentType": "image/png",
            "size": 123,
            "tag": tag,
        }

    monkeypatch.setattr(vendor_media.media_ingest_service, "ingest_from_remote_url", fake_ingest)

    result = vendor_media.persist_vendor_media_payload(
        {"images": [{"url": "https://vendor.example.com/out.png", "mimeType": "image/png"}]},
        user_id="tester",
        tag_prefix="vendor-api-test",
    )

    assert result["images"][0]["ossUrl"] == "https://oss.example.com/stored.png"
    assert result["images"][0]["sourceUrl"] == "https://vendor.example.com/out.png"
    assert result["resultUrls"] == ["https://oss.example.com/stored.png"]
    assert result["storedAssets"][0]["tag"] == "vendor-api-test-image-0"


def test_persist_vendor_media_payload_uploads_base64_images(monkeypatch) -> None:
    def fake_ingest(payload: str, *, user_id: str, filename_hint=None, mime_type=None, tag: str | None = None) -> dict:
        return {
            "sourceUrl": None,
            "ossUrl": "https://oss.example.com/generated.png",
            "ossKey": "generated.png",
            "contentType": mime_type,
            "size": len(payload),
            "tag": tag,
        }

    monkeypatch.setattr(vendor_media.media_ingest_service, "ingest_from_base64", fake_ingest)

    result = vendor_media.persist_vendor_media_payload(
        {"images": [{"base64": "abc123", "contentType": "image/png"}]},
        user_id="tester",
    )

    assert result["images"][0]["ossUrl"] == "https://oss.example.com/generated.png"
    assert result["images"][0]["contentType"] == "image/png"
    assert result["assets"][0]["type"] == "image"
