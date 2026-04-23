"""Client abstraction for self-built image atomic tools.

This keeps PODI ability contracts stable while allowing execution to move from
local in-process functions to a dedicated image-ops service later.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from app.core.config import get_settings
from app.services import podi_image_tools


class ImageOpsLocalExecutionDisabled(RuntimeError):
    """Raised when caller explicitly forbids local execution and no remote service is available."""


class ImageOpsRemoteError(RuntimeError):
    """Raised when remote image-ops service is configured but returns an invalid response."""


class ImageOpsClient:
    def _settings(self):
        return get_settings()

    @property
    def remote_enabled(self) -> bool:
        return bool((self._settings().image_ops_base_url or "").strip())

    def _resolve_allow_local_fallback(self, explicit: bool | None) -> bool:
        if explicit is not None:
            return bool(explicit)
        return bool(self._settings().image_ops_local_fallback_enabled)

    def expand_with_color(
        self,
        *,
        image_bytes: bytes,
        expand_left: int,
        expand_right: int,
        expand_top: int,
        expand_bottom: int,
        allow_local_fallback: bool | None = None,
    ) -> tuple[bytes, str, str]:
        params = {
            "expand_left": expand_left,
            "expand_right": expand_right,
            "expand_top": expand_top,
            "expand_bottom": expand_bottom,
        }
        return self._execute(
            operation="expand-mask-color",
            image_bytes=image_bytes,
            params=params,
            local_runner=lambda: (
                podi_image_tools.expand_with_color(
                    image_bytes=image_bytes,
                    expand_left=expand_left,
                    expand_right=expand_right,
                    expand_top=expand_top,
                    expand_bottom=expand_bottom,
                ),
                "image/png",
                ".png",
            ),
            allow_local_fallback=self._resolve_allow_local_fallback(allow_local_fallback),
        )

    def set_dpi(
        self,
        *,
        image_bytes: bytes,
        dpi: int,
        allow_local_fallback: bool | None = None,
    ) -> tuple[bytes, str, str]:
        return self._execute(
            operation="set-dpi",
            image_bytes=image_bytes,
            params={"dpi": dpi},
            local_runner=lambda: podi_image_tools.set_dpi(image_bytes=image_bytes, dpi=dpi),
            allow_local_fallback=self._resolve_allow_local_fallback(allow_local_fallback),
        )

    def upscale_resize(
        self,
        *,
        image_bytes: bytes,
        max_long_edge: int,
        output_format: str | None,
        allow_local_fallback: bool | None = None,
    ) -> tuple[bytes, str, str]:
        return self._execute(
            operation="upscale-resize",
            image_bytes=image_bytes,
            params={"max_long_edge": max_long_edge, "output_format": output_format},
            local_runner=lambda: podi_image_tools.upscale_resize(
                image_bytes=image_bytes,
                max_long_edge=max_long_edge,
                output_format=output_format,
            ),
            allow_local_fallback=self._resolve_allow_local_fallback(allow_local_fallback),
        )

    def _execute(
        self,
        *,
        operation: str,
        image_bytes: bytes,
        params: dict[str, Any],
        local_runner,
        allow_local_fallback: bool,
    ) -> tuple[bytes, str, str]:
        if self.remote_enabled:
            try:
                return self._call_remote(operation=operation, image_bytes=image_bytes, params=params)
            except Exception as exc:
                if not allow_local_fallback:
                    raise ImageOpsRemoteError(str(exc)) from exc
        else:
            if not allow_local_fallback:
                raise ImageOpsLocalExecutionDisabled(operation)
        return local_runner()

    def _call_remote(
        self,
        *,
        operation: str,
        image_bytes: bytes,
        params: dict[str, Any],
    ) -> tuple[bytes, str, str]:
        settings = self._settings()
        base_url = (settings.image_ops_base_url or "").rstrip("/")
        if not base_url:
            raise ImageOpsRemoteError("IMAGE_OPS_BASE_URL_NOT_CONFIGURED")
        headers = {"Content-Type": "application/json"}
        token = (settings.image_ops_service_token or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload = {
            "imageBase64": base64.b64encode(image_bytes).decode("utf-8"),
            "params": params,
        }
        response = httpx.post(
            f"{base_url}/internal/image-ops/{operation}",
            json=payload,
            headers=headers,
            timeout=max(5, int(settings.image_ops_timeout_seconds or 120)),
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ImageOpsRemoteError("IMAGE_OPS_INVALID_RESPONSE")
        content_base64 = data.get("contentBase64")
        content_type = str(data.get("contentType") or "").strip()
        file_ext = str(data.get("fileExt") or "").strip()
        if not isinstance(content_base64, str) or not content_base64.strip():
            raise ImageOpsRemoteError("IMAGE_OPS_CONTENT_MISSING")
        try:
            content = base64.b64decode(content_base64)
        except Exception as exc:  # noqa: BLE001 - returned content is invalid
            raise ImageOpsRemoteError("IMAGE_OPS_CONTENT_INVALID") from exc
        if not content_type:
            raise ImageOpsRemoteError("IMAGE_OPS_CONTENT_TYPE_MISSING")
        if not file_ext.startswith("."):
            raise ImageOpsRemoteError("IMAGE_OPS_FILE_EXT_INVALID")
        return content, content_type, file_ext


image_ops_client = ImageOpsClient()
