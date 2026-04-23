from __future__ import annotations

import base64

from fastapi import Depends, FastAPI, Header, HTTPException

from app.config import get_settings
from app.schemas import ImageOpsRequest, ImageOpsResponse
from app.service import expand_with_color, set_dpi, upscale_resize

app = FastAPI(title="PODI Image Ops", version="0.1.0")


def _require_internal_token(authorization: str | None = Header(default=None)) -> None:
    token = (get_settings().image_ops_service_token or "").strip()
    if not token:
        return
    expected = f"Bearer {token}"
    if (authorization or "").strip() != expected:
        raise HTTPException(status_code=401, detail="IMAGE_OPS_UNAUTHORIZED")


def _decode_image(image_base64: str) -> bytes:
    try:
        return base64.b64decode(image_base64)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="IMAGE_OPS_IMAGE_INVALID") from exc


def _encode_response(content: bytes, content_type: str, file_ext: str) -> ImageOpsResponse:
    return ImageOpsResponse(
        contentBase64=base64.b64encode(content).decode("utf-8"),
        contentType=content_type,
        fileExt=file_ext,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/image-ops/expand-mask-color", response_model=ImageOpsResponse)
def expand_mask_color_endpoint(
    payload: ImageOpsRequest,
    _auth: None = Depends(_require_internal_token),
) -> ImageOpsResponse:
    image_bytes = _decode_image(payload.imageBase64)
    content, content_type, file_ext = expand_with_color(
        image_bytes=image_bytes,
        expand_left=payload.params.get("expand_left", 0),
        expand_right=payload.params.get("expand_right", 0),
        expand_top=payload.params.get("expand_top", 0),
        expand_bottom=payload.params.get("expand_bottom", 0),
    )
    return _encode_response(content, content_type, file_ext)


@app.post("/internal/image-ops/set-dpi", response_model=ImageOpsResponse)
def set_dpi_endpoint(
    payload: ImageOpsRequest,
    _auth: None = Depends(_require_internal_token),
) -> ImageOpsResponse:
    image_bytes = _decode_image(payload.imageBase64)
    content, content_type, file_ext = set_dpi(
        image_bytes=image_bytes,
        dpi=payload.params.get("dpi", 300),
    )
    return _encode_response(content, content_type, file_ext)


@app.post("/internal/image-ops/upscale-resize", response_model=ImageOpsResponse)
def upscale_resize_endpoint(
    payload: ImageOpsRequest,
    _auth: None = Depends(_require_internal_token),
) -> ImageOpsResponse:
    image_bytes = _decode_image(payload.imageBase64)
    content, content_type, file_ext = upscale_resize(
        image_bytes=image_bytes,
        max_long_edge=payload.params.get("max_long_edge", 2048),
        output_format=payload.params.get("output_format"),
    )
    return _encode_response(content, content_type, file_ext)
