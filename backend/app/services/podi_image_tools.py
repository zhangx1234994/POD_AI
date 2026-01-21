"""Local image utilities used as PODI abilities.

These utilities run inside our backend (no external executor) and return assets
stored in our OSS bucket so downstream workflow nodes can consume stable URLs.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

import httpx
from PIL import Image

from app.services.oss import oss_service


def _coerce_nonneg_int(value: Any) -> int:
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def expand_with_color(
    *,
    image_bytes: bytes,
    expand_left: int = 0,
    expand_right: int = 0,
    expand_top: int = 0,
    expand_bottom: int = 0,
    # Bright magenta is a good "special color" that is rare in natural images.
    fill_rgb: tuple[int, int, int] = (255, 0, 255),
) -> bytes:
    """Expand a canvas and fill new area with a solid color (PNG output)."""

    left = _coerce_nonneg_int(expand_left)
    right = _coerce_nonneg_int(expand_right)
    top = _coerce_nonneg_int(expand_top)
    bottom = _coerce_nonneg_int(expand_bottom)

    im = Image.open(BytesIO(image_bytes)).convert("RGBA")
    w, h = im.size
    new_w = w + left + right
    new_h = h + top + bottom
    fill = (*fill_rgb, 255)

    canvas = Image.new("RGBA", (new_w, new_h), fill)
    canvas.paste(im, (left, top), im)

    out = BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def expand_with_color_from_url(
    *,
    image_url: str,
    expand_left: int = 0,
    expand_right: int = 0,
    expand_top: int = 0,
    expand_bottom: int = 0,
    user_id: str,
    filename: str = "expand_mask.png",
) -> dict[str, Any]:
    """Download image, expand, upload to OSS, return a lightweight asset dict."""

    resp = httpx.get(image_url, timeout=60)
    resp.raise_for_status()
    content = resp.content
    out_bytes = expand_with_color(
        image_bytes=content,
        expand_left=expand_left,
        expand_right=expand_right,
        expand_top=expand_top,
        expand_bottom=expand_bottom,
    )
    upload = oss_service.upload_bytes(
        user_id=user_id or "system",
        filename=filename,
        data=out_bytes,
        content_type="image/png",
    )
    return {
        "sourceUrl": image_url,
        "ossUrl": upload.get("url"),
        "ossKey": upload.get("objectKey"),
        "contentType": "image/png",
        "tag": "podi-expand-mask",
    }

