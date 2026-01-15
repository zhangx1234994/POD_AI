"""Utilities to persist third-party media assets into our OSS bucket."""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.services.oss import oss_service


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
        upload_result = oss_service.upload_bytes(
            user_id=user_id or "system",
            filename=filename,
            data=response.content,
            content_type=content_type,
        )
        return {
            "sourceUrl": url,
            "ossUrl": upload_result["url"],
            "ossKey": upload_result["objectKey"],
            "contentType": content_type,
            "size": len(response.content),
            "tag": tag,
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
        }


media_ingest_service = MediaIngestService()
