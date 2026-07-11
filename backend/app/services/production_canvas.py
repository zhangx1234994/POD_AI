"""Deterministic production-canvas composition and print preflight checks."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import httpx
from PIL import Image, ImageOps

from app.services.media_ingest import media_ingest_service


class ProductionCanvasError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


@dataclass(slots=True)
class ProductionCanvasResult:
    url: str
    object_key: str | None
    width: int
    height: int
    dpi: int
    mode: str
    source_width: int
    source_height: int


class ProductionCanvasService:
    """Build an exact print file; preview images are never accepted as a substitute."""

    SUPPORTED_MODES = {"cover", "tile", "seamless"}

    def compose(
        self,
        *,
        source_url: str,
        target_width: int,
        target_height: int,
        target_dpi: int,
        mode: str,
        user_id: str,
        filename: str,
        tiled_review_confirmed: bool = False,
    ) -> ProductionCanvasResult:
        if not source_url.startswith(("http://", "https://")):
            raise ProductionCanvasError("PRODUCTION_CANVAS_SOURCE_INVALID", "生产图源文件必须是可访问的图片 URL。")
        if not (64 <= target_width <= 12000 and 64 <= target_height <= 12000):
            raise ProductionCanvasError("PRODUCTION_CANVAS_SIZE_INVALID", "生产尺寸超出允许范围。")
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode not in self.SUPPORTED_MODES:
            raise ProductionCanvasError("PRODUCTION_CANVAS_MODE_INVALID", "生产贴图模式不受支持。")
        if normalized_mode == "seamless" and not tiled_review_confirmed:
            raise ProductionCanvasError("PRODUCTION_CANVAS_TILED_REVIEW_REQUIRED", "连续图必须先完成平铺复核，才能生成生产文件。")
        try:
            response = httpx.get(source_url, timeout=60)
            response.raise_for_status()
            source = Image.open(BytesIO(response.content)).convert("RGBA")
        except Exception as exc:  # noqa: BLE001
            raise ProductionCanvasError("PRODUCTION_CANVAS_SOURCE_LOAD_FAILED", "无法读取生产图源文件。") from exc

        source_width, source_height = source.size
        if normalized_mode == "cover":
            output = ImageOps.fit(source, (target_width, target_height), method=Image.Resampling.LANCZOS)
        else:
            output = Image.new("RGBA", (target_width, target_height))
            for y in range(0, target_height, source_height):
                for x in range(0, target_width, source_width):
                    output.alpha_composite(source, (x, y))

        binary = BytesIO()
        output.save(binary, format="PNG", dpi=(target_dpi, target_dpi))
        upload = media_ingest_service.upload_generated_image_bytes(
            data=binary.getvalue(),
            user_id=user_id,
            filename=filename,
            content_type="image/png",
            tag="production-canvas",
        )
        return ProductionCanvasResult(
            url=str(upload["ossUrl"]),
            object_key=upload.get("ossKey"),
            width=target_width,
            height=target_height,
            dpi=target_dpi,
            mode=normalized_mode,
            source_width=source_width,
            source_height=source_height,
        )

    def preflight(
        self,
        *,
        image_url: str,
        target_width: int,
        target_height: int,
        target_dpi: int,
    ) -> dict[str, Any]:
        try:
            response = httpx.get(image_url, timeout=60)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            width, height = image.size
            dpi_value = image.info.get("dpi") or (0, 0)
            actual_dpi = round(float(dpi_value[0] or 0)) if isinstance(dpi_value, tuple) else 0
            fmt = image.format or "unknown"
        except Exception as exc:  # noqa: BLE001
            raise ProductionCanvasError("PRODUCTION_PREFLIGHT_SOURCE_LOAD_FAILED", "无法读取待检生产文件。") from exc
        if (width, height) != (target_width, target_height):
            raise ProductionCanvasError(
                "PRODUCTION_PREFLIGHT_DIMENSION_MISMATCH",
                f"生产文件尺寸为 {width}x{height}，要求 {target_width}x{target_height}。",
            )
        if actual_dpi and actual_dpi < target_dpi:
            raise ProductionCanvasError(
                "PRODUCTION_PREFLIGHT_DPI_TOO_LOW",
                f"生产文件 DPI 为 {actual_dpi}，低于要求 {target_dpi}。",
            )
        return {
            "passed": True,
            "width": width,
            "height": height,
            "dpi": actual_dpi or target_dpi,
            "format": fmt,
            "expectedWidth": target_width,
            "expectedHeight": target_height,
            "expectedDpi": target_dpi,
        }


production_canvas_service = ProductionCanvasService()
