"""Persist third-party media outputs into our OSS bucket."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.media_ingest import media_ingest_service


def persist_vendor_media_payload(
    payload: dict[str, Any],
    *,
    user_id: str,
    tag_prefix: str = "vendor-api",
) -> dict[str, Any]:
    """Return a copy of a vendor response with image/video assets stored in OSS."""

    if not isinstance(payload, dict):
        return payload
    updated = deepcopy(payload)
    images = _persist_asset_list(updated.get("images"), user_id=user_id, media_type="image", tag_prefix=tag_prefix)
    videos = _persist_asset_list(updated.get("videos"), user_id=user_id, media_type="video", tag_prefix=tag_prefix)
    stored_assets = images + videos
    if images:
        updated["images"] = images
        updated["resultUrls"] = [item["ossUrl"] for item in images if isinstance(item.get("ossUrl"), str)]
        updated["imageUrls"] = list(updated["resultUrls"])
    if videos:
        updated["videos"] = videos
        updated["videoUrls"] = [item["ossUrl"] for item in videos if isinstance(item.get("ossUrl"), str)]
    if stored_assets:
        updated["assets"] = stored_assets
        updated["storedAssets"] = stored_assets
    return updated


def _persist_asset_list(value: Any, *, user_id: str, media_type: str, tag_prefix: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    results: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        persisted = _persist_one(item, user_id=user_id, media_type=media_type, tag=f"{tag_prefix}-{media_type}-{index}")
        if persisted:
            results.append(persisted)
    return results


def _persist_one(item: dict[str, Any], *, user_id: str, media_type: str, tag: str) -> dict[str, Any] | None:
    if isinstance(item.get("ossUrl"), str) and item["ossUrl"]:
        return _normalize_existing(item, media_type=media_type)
    source_url = _first_string(item.get("url"), item.get("sourceUrl"))
    base64_payload = _first_string(item.get("base64"), item.get("b64"))
    mime_type = _first_string(item.get("contentType"), item.get("mimeType"), item.get("type"))
    try:
        if source_url:
            stored = media_ingest_service.ingest_from_remote_url(source_url, user_id=user_id, tag=tag)
        elif base64_payload:
            stored = media_ingest_service.ingest_from_base64(
                base64_payload,
                user_id=user_id,
                mime_type=mime_type or ("image/png" if media_type == "image" else "video/mp4"),
                tag=tag,
            )
        else:
            return None
    except Exception as exc:  # best effort: keep original vendor output visible
        fallback = _normalize_existing(item, media_type=media_type)
        fallback["persistError"] = str(exc)[:240]
        return fallback

    return {
        "ossUrl": stored.get("ossUrl"),
        "url": stored.get("ossUrl"),
        "sourceUrl": stored.get("sourceUrl") or source_url,
        "ossKey": stored.get("ossKey"),
        "contentType": stored.get("contentType") or mime_type,
        "size": stored.get("size"),
        "tag": stored.get("tag") or tag,
        "type": media_type,
    }


def _normalize_existing(item: dict[str, Any], *, media_type: str) -> dict[str, Any]:
    content_type = _first_string(item.get("contentType"), item.get("mimeType"), item.get("type"))
    url = _first_string(item.get("ossUrl"), item.get("url"), item.get("sourceUrl"))
    return {
        "ossUrl": item.get("ossUrl"),
        "url": url,
        "sourceUrl": item.get("sourceUrl") or item.get("url"),
        "contentType": content_type,
        "size": item.get("size"),
        "tag": item.get("tag"),
        "type": media_type,
        "base64": item.get("base64") or item.get("b64"),
    }


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
