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


def _guess_image_format_and_ext(im: Image.Image) -> tuple[str, str]:
    fmt = (getattr(im, "format", None) or "").upper()
    if fmt in {"JPEG", "JPG"}:
        return "JPEG", ".jpg"
    if fmt == "PNG":
        return "PNG", ".png"
    if fmt == "WEBP":
        return "WEBP", ".webp"
    # Safe default: PNG
    return "PNG", ".png"


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


def set_dpi(
    *,
    image_bytes: bytes,
    dpi: int,
) -> tuple[bytes, str, str]:
    """Set DPI metadata without changing pixel dimensions.

    Returns (bytes, content_type, filename_ext).
    """
    dpi_value = _coerce_nonneg_int(dpi) or 300
    im = Image.open(BytesIO(image_bytes))
    fmt, ext = _guess_image_format_and_ext(im)
    # For JPEG/PNG, Pillow supports `dpi=(x,y)` on save. For other formats we fallback to PNG.
    if fmt not in {"JPEG", "PNG"}:
        fmt, ext = "PNG", ".png"
        im = im.convert("RGBA")
    out = BytesIO()
    save_kwargs: dict[str, Any] = {"dpi": (dpi_value, dpi_value)}
    if fmt == "JPEG":
        im = im.convert("RGB")
        save_kwargs.setdefault("quality", 95)
        save_kwargs.setdefault("subsampling", 0)
        content_type = "image/jpeg"
    else:
        content_type = "image/png"
    im.save(out, format=fmt, **save_kwargs)
    return out.getvalue(), content_type, ext


def upscale_resize(
    *,
    image_bytes: bytes,
    max_long_edge: int,
    output_format: str | None = None,
) -> tuple[bytes, str, str]:
    """Resize image so that its long edge equals max_long_edge (no AI; high-quality resample).

    Returns (bytes, content_type, filename_ext).
    """
    target = _coerce_nonneg_int(max_long_edge) or 2048
    # Hard guardrails to prevent OOM / huge uploads.
    if target > 8192:
        target = 8192

    im = Image.open(BytesIO(image_bytes))
    fmt_in, _ = _guess_image_format_and_ext(im)
    w, h = im.size
    if w <= 0 or h <= 0:
        raise ValueError("invalid image size")
    long_edge = max(w, h)
    if long_edge == target:
        resized = im
    else:
        scale = target / float(long_edge)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        resized = im.resize((new_w, new_h), Image.LANCZOS)

    out_fmt = (output_format or fmt_in or "PNG").upper()
    if out_fmt in {"JPG", "JPEG"}:
        out_fmt = "JPEG"
        resized = resized.convert("RGB")
        out = BytesIO()
        resized.save(out, format="JPEG", quality=95, subsampling=0)
        return out.getvalue(), "image/jpeg", ".jpg"

    # Default to PNG (lossless).
    resized = resized.convert("RGBA")
    out = BytesIO()
    resized.save(out, format="PNG")
    return out.getvalue(), "image/png", ".png"
