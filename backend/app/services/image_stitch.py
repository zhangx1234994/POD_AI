"""Deterministic image stitching utilities for PODI business runs."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import httpx
from fastapi import HTTPException
from PIL import Image


MAX_STITCH_COLUMNS = 10
MAX_STITCH_ROWS = 10
MAX_STITCH_SIDE = 8000
MAX_STITCH_TOTAL_PIXELS = 64_000_000
MIN_STITCH_TARGET_SIDE_EXCLUSIVE = 100


@dataclass(frozen=True)
class ImageStitchOptions:
    mode: str
    columns: int
    rows: int
    target_width: int | None = None
    target_height: int | None = None


@dataclass(frozen=True)
class ImageStitchResult:
    image: Image.Image
    width: int
    height: int
    intermediate_width: int
    intermediate_height: int


def normalize_image_stitch_options(payload: Any, inputs: dict[str, Any] | None = None) -> ImageStitchOptions:
    inputs = inputs if isinstance(inputs, dict) else {}
    mode = str(_first_value(getattr(payload, "mode", None), inputs.get("mode"), inputs.get("stitchMode"), "count")).strip()
    if mode not in {"count", "size"}:
        raise HTTPException(status_code=400, detail="IMAGE_STITCH_MODE_INVALID")

    columns = _coerce_int(_first_value(getattr(payload, "columns", None), inputs.get("columns")), "IMAGE_STITCH_COUNT_INVALID")
    rows = _coerce_int(_first_value(getattr(payload, "rows", None), inputs.get("rows")), "IMAGE_STITCH_COUNT_INVALID")
    if columns < 1 or columns > MAX_STITCH_COLUMNS or rows < 1 or rows > MAX_STITCH_ROWS:
        raise HTTPException(status_code=400, detail="IMAGE_STITCH_COUNT_INVALID")

    target_width = _optional_int(_first_value(getattr(payload, "targetWidth", None), getattr(payload, "target_width", None), inputs.get("targetWidth"), inputs.get("target_width")))
    target_height = _optional_int(_first_value(getattr(payload, "targetHeight", None), getattr(payload, "target_height", None), inputs.get("targetHeight"), inputs.get("target_height")))
    if mode == "size":
        if target_width is None or target_height is None:
            raise HTTPException(status_code=400, detail="IMAGE_STITCH_SIZE_INVALID")
        _assert_size_target(target_width, target_height)

    return ImageStitchOptions(
        mode=mode,
        columns=columns,
        rows=rows,
        target_width=target_width,
        target_height=target_height,
    )


def load_remote_rgba_image(url: str) -> Image.Image:
    target = str(url or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="BUSINESS_IMAGE_URL_REQUIRED")
    try:
        response = httpx.get(target, timeout=30, follow_redirects=True)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content)).convert("RGBA")
        image.load()
        return image
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="IMAGE_STITCH_SOURCE_LOAD_FAILED") from exc


def render_image_stitch(source_image: Image.Image, options: ImageStitchOptions) -> ImageStitchResult:
    try:
        source = source_image.convert("RGBA")
        source_width, source_height = source.size
        intermediate_width = source_width * options.columns
        intermediate_height = source_height * options.rows
        _assert_output_size(intermediate_width, intermediate_height)

        output_width = options.target_width if options.mode == "size" else intermediate_width
        output_height = options.target_height if options.mode == "size" else intermediate_height
        if output_width is None or output_height is None:
            raise HTTPException(status_code=400, detail="IMAGE_STITCH_SIZE_INVALID")
        _assert_output_size(output_width, output_height)

        # 与前端 Canvas 保持同一契约：先用整数坐标拼出中间整图，尺寸模式只在最后整体缩放一次。
        intermediate = Image.new("RGBA", (intermediate_width, intermediate_height), (0, 0, 0, 0))
        for row in range(options.rows):
            for column in range(options.columns):
                intermediate.alpha_composite(source, (column * source_width, row * source_height))

        if options.mode == "size":
            resized = intermediate.resize((output_width, output_height), Image.Resampling.LANCZOS)
            output = resized.convert("RGBA")
        else:
            output = intermediate

        return ImageStitchResult(
            image=output,
            width=output_width,
            height=output_height,
            intermediate_width=intermediate_width,
            intermediate_height=intermediate_height,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="IMAGE_STITCH_RENDER_FAILED") from exc


def encode_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    try:
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="IMAGE_STITCH_RENDER_FAILED") from exc


def _assert_size_target(width: int, height: int) -> None:
    if width <= MIN_STITCH_TARGET_SIDE_EXCLUSIVE or height <= MIN_STITCH_TARGET_SIDE_EXCLUSIVE:
        raise HTTPException(status_code=400, detail="IMAGE_STITCH_SIZE_INVALID")
    _assert_output_size(width, height)


def _assert_output_size(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise HTTPException(status_code=400, detail="IMAGE_STITCH_SIZE_INVALID")
    if width > MAX_STITCH_SIDE or height > MAX_STITCH_SIDE or width * height > MAX_STITCH_TOTAL_PIXELS:
        raise HTTPException(status_code=400, detail="IMAGE_STITCH_OUTPUT_TOO_LARGE")


def _coerce_int(value: Any, error_code: str) -> int:
    number = _optional_int(value)
    if number is None:
        raise HTTPException(status_code=400, detail=error_code)
    return number


def _optional_int(value: Any) -> int | None:
    if value in (None, "", []):
        return None
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return number


def _first_value(*values: Any) -> Any | None:
    for value in values:
        if value not in (None, "", []):
            return value
    return None
