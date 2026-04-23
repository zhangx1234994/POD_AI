from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image


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
    return "PNG", ".png"


def expand_with_color(
    *,
    image_bytes: bytes,
    expand_left: int = 0,
    expand_right: int = 0,
    expand_top: int = 0,
    expand_bottom: int = 0,
    fill_rgb: tuple[int, int, int] = (0, 0, 0),
    fill_alpha: int = 0,
) -> tuple[bytes, str, str]:
    left = _coerce_nonneg_int(expand_left)
    right = _coerce_nonneg_int(expand_right)
    top = _coerce_nonneg_int(expand_top)
    bottom = _coerce_nonneg_int(expand_bottom)

    im = Image.open(BytesIO(image_bytes)).convert("RGBA")
    w, h = im.size
    new_w = w + left + right
    new_h = h + top + bottom
    try:
        a = int(fill_alpha)
    except Exception:
        a = 0
    a = 0 if a < 0 else (255 if a > 255 else a)
    fill = (*fill_rgb, a)

    canvas = Image.new("RGBA", (new_w, new_h), fill)
    canvas.paste(im, (left, top), im)
    out = BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue(), "image/png", ".png"


def set_dpi(*, image_bytes: bytes, dpi: int) -> tuple[bytes, str, str]:
    dpi_value = _coerce_nonneg_int(dpi) or 300
    im = Image.open(BytesIO(image_bytes))
    fmt, ext = _guess_image_format_and_ext(im)
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
    target = _coerce_nonneg_int(max_long_edge) or 2048
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
        out = BytesIO()
        resized.convert("RGB").save(out, format="JPEG", quality=95, subsampling=0)
        return out.getvalue(), "image/jpeg", ".jpg"

    out = BytesIO()
    resized.convert("RGBA").save(out, format="PNG")
    return out.getvalue(), "image/png", ".png"
