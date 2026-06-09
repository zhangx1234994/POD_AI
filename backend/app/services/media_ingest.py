"""Utilities to persist third-party media assets into our OSS bucket."""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.services import podi_image_tools
from app.services.oss import oss_service


_RASTER_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


class MediaIngestService:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def _normalize_filename(self, *, source_url: str | None, hint: str | None, content_type: str | None, fallback_ext: str) -> str:
        if hint:
            suffix = Path(hint).suffix
            if suffix:
                return hint
        if content_type:
            ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
            if ext:
                return f"media{ext}"
        if source_url:
            path = urlparse(source_url).path
            suffix = Path(path).suffix
            if suffix:
                return f"media{suffix}"
        return f"media{fallback_ext}"

    def _looks_like_raster_image(self, *, filename: str, content_type: str | None) -> bool:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        if normalized_type.startswith("image/") and normalized_type not in {"image/svg+xml"}:
            return True
        return Path(filename).suffix.lower() in _RASTER_IMAGE_EXTENSIONS

    def _replace_filename_suffix(self, filename: str, suffix: str) -> str:
        if not suffix.startswith("."):
            return filename
        path = Path(filename)
        if path.suffix.lower() == suffix.lower():
            return filename
        return str(path.with_suffix(suffix))

    def _apply_default_image_dpi(
        self,
        *,
        data: bytes,
        filename: str,
        content_type: str | None,
    ) -> tuple[bytes, str | None, str, int | None]:
        dpi = int(get_settings().output_image_default_dpi or 0)
        if dpi <= 0 or not self._looks_like_raster_image(filename=filename, content_type=content_type):
            return data, content_type, filename, None
        try:
            normalized, normalized_type, normalized_ext = podi_image_tools.set_dpi(image_bytes=data, dpi=dpi)
        except Exception as exc:  # noqa: BLE001 - media ingest should not fail only because metadata normalization failed
            self._logger.warning("Failed to write default image DPI metadata before OSS upload: %s", exc)
            return data, content_type, filename, None
        return normalized, normalized_type, self._replace_filename_suffix(filename, normalized_ext), dpi

    def ingest_from_remote_url(
        self,
        url: str,
        *,
        user_id: str,
        filename_hint: str | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        try:
            response = httpx.get(url, timeout=60)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - defensive
            self._logger.warning("Failed to download remote asset: %s", exc)
            raise
        content_type = response.headers.get("Content-Type")
        filename = self._normalize_filename(
            source_url=url,
            hint=filename_hint,
            content_type=content_type,
            fallback_ext=".bin",
        )
        data, content_type, filename, applied_dpi = self._apply_default_image_dpi(
            data=response.content,
            filename=filename,
            content_type=content_type,
        )
        upload_result = oss_service.upload_bytes(
            user_id=user_id or "system",
            filename=filename,
            data=data,
            content_type=content_type,
        )
        return {
            "sourceUrl": url,
            "ossUrl": upload_result["url"],
            "ossKey": upload_result["objectKey"],
            "contentType": content_type,
            "size": len(data),
            "tag": tag,
            "dpi": applied_dpi,
        }

    def ingest_from_base64(
        self,
        payload: str,
        *,
        user_id: str,
        filename_hint: str | None = None,
        mime_type: str | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        prefix = ""
        data_part = payload
        if payload.startswith("data:"):
            prefix, data_part = payload.split(",", 1)
            if not mime_type and prefix.startswith("data:"):
                mime_type = prefix.split(";")[0].replace("data:", "", 1)
        raw = base64.b64decode(data_part)
        filename = self._normalize_filename(
            source_url=None,
            hint=filename_hint,
            content_type=mime_type,
            fallback_ext=".png",
        )
        raw, mime_type, filename, applied_dpi = self._apply_default_image_dpi(
            data=raw,
            filename=filename,
            content_type=mime_type,
        )
        upload_result = oss_service.upload_bytes(
            user_id=user_id or "system",
            filename=filename,
            data=raw,
            content_type=mime_type,
        )
        return {
            "sourceUrl": None,
            "ossUrl": upload_result["url"],
            "ossKey": upload_result["objectKey"],
            "contentType": mime_type,
            "size": len(raw),
            "tag": tag,
            "dpi": applied_dpi,
        }

    def upload_generated_image_bytes(
        self,
        *,
        data: bytes,
        user_id: str,
        filename: str,
        content_type: str | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        """Upload a generated result image after applying default delivery metadata."""

        return self.upload_generated_media_bytes(
            data=data,
            user_id=user_id,
            filename=filename,
            content_type=content_type,
            tag=tag,
        )

    def upload_generated_media_bytes(
        self,
        *,
        data: bytes,
        user_id: str,
        filename: str,
        content_type: str | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        """Upload generated media, applying image-only delivery metadata when relevant."""

        data, content_type, filename, applied_dpi = self._apply_default_image_dpi(
            data=data,
            filename=filename,
            content_type=content_type,
        )
        upload_result = oss_service.upload_bytes(
            user_id=user_id or "system",
            filename=filename,
            data=data,
            content_type=content_type,
        )
        object_key = upload_result["objectKey"]
        return {
            "ossUrl": upload_result["url"],
            "url": upload_result["url"],
            "ossKey": object_key,
            "objectKey": object_key,
            "contentType": content_type,
            "size": len(data),
            "tag": tag,
            "dpi": applied_dpi,
        }


media_ingest_service = MediaIngestService()
