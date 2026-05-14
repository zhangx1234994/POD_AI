"""Persist third-party media outputs into our OSS bucket."""

from __future__ import annotations

import logging
from copy import deepcopy
from io import BytesIO
from typing import Any

import httpx
from PIL import Image

from app.services.media_ingest import media_ingest_service
from app.services.oss import oss_service


logger = logging.getLogger(__name__)


def persist_vendor_media_payload(
    payload: dict[str, Any],
    *,
    user_id: str,
    tag_prefix: str = "vendor-api",
    desired_image_size: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Return a copy of a vendor response with image/video assets stored in OSS."""

    if not isinstance(payload, dict):
        return payload
    updated = deepcopy(payload)
    images = _persist_asset_list(
        updated.get("images"),
        user_id=user_id,
        media_type="image",
        tag_prefix=tag_prefix,
        desired_size=desired_image_size,
    )
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


def _persist_asset_list(
    value: Any,
    *,
    user_id: str,
    media_type: str,
    tag_prefix: str,
    desired_size: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    results: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        persisted = _persist_one(
            item,
            user_id=user_id,
            media_type=media_type,
            tag=f"{tag_prefix}-{media_type}-{index}",
            desired_size=desired_size,
        )
        if persisted:
            results.append(persisted)
    return results


def _persist_one(
    item: dict[str, Any],
    *,
    user_id: str,
    media_type: str,
    tag: str,
    desired_size: tuple[int, int] | None = None,
) -> dict[str, Any] | None:
    if isinstance(item.get("ossUrl"), str) and item["ossUrl"]:
        normalized = _normalize_existing(item, media_type=media_type)
        return _enforce_image_size(normalized, user_id=user_id, tag=tag, desired_size=desired_size)
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

    persisted = {
        "ossUrl": stored.get("ossUrl"),
        "url": stored.get("ossUrl"),
        "sourceUrl": stored.get("sourceUrl") or source_url,
        "ossKey": stored.get("ossKey"),
        "contentType": stored.get("contentType") or mime_type,
        "size": stored.get("size"),
        "tag": stored.get("tag") or tag,
        "type": media_type,
    }
    return _enforce_image_size(persisted, user_id=user_id, tag=tag, desired_size=desired_size)


def _enforce_image_size(
    item: dict[str, Any],
    *,
    user_id: str,
    tag: str,
    desired_size: tuple[int, int] | None,
) -> dict[str, Any]:
    if not desired_size or item.get("type") != "image":
        return item
    try:
        target_w, target_h = int(desired_size[0]), int(desired_size[1])
    except Exception:
        return item
    if target_w <= 0 or target_h <= 0:
        return item
    url = _first_string(item.get("ossUrl"), item.get("url"))
    if not url:
        return item
    try:
        response = httpx.get(url, timeout=60)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        if image.size == (target_w, target_h):
            item["width"] = target_w
            item["height"] = target_h
            return item
        resized = _resize_with_pad(image, target_w=target_w, target_h=target_h)
        output = BytesIO()
        resized.save(output, format="PNG")
        upload = oss_service.upload_bytes(
            user_id=user_id or "system",
            filename=f"{tag}-target-{target_w}x{target_h}.png",
            data=output.getvalue(),
            content_type="image/png",
        )
        next_item = dict(item)
        previous_url = url
        next_item.update(
            {
                "ossUrl": upload.get("url"),
                "url": upload.get("url"),
                "sourceUrl": previous_url,
                "ossKey": upload.get("objectKey"),
                "contentType": "image/png",
                "size": len(output.getvalue()),
                "width": target_w,
                "height": target_h,
                "postprocess": {
                    "strategy": "fit_pad_keep_original_size",
                    "targetWidth": target_w,
                    "targetHeight": target_h,
                },
            }
        )
        return next_item
    except Exception as exc:
        logger.warning("Failed to enforce vendor image size %sx%s: %s", target_w, target_h, exc)
        fallback = dict(item)
        fallback["postprocessError"] = str(exc)[:240]
        return fallback


def _resize_with_pad(image: Image.Image, *, target_w: int, target_h: int) -> Image.Image:
    image = image.convert("RGBA")
    src_w, src_h = image.size
    if src_w <= 0 or src_h <= 0:
        return image
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))
    resized = image.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    canvas.paste(resized, (max(0, (target_w - new_w) // 2), max(0, (target_h - new_h) // 2)), resized)
    return canvas


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
