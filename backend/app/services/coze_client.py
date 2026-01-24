"""Lightweight HTTP client for Coze Studio workflow APIs."""

from __future__ import annotations

from typing import Any, Mapping

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings


class CozeWorkflowClient:
    """Encapsulates HTTP logic for calling Coze Studio's /v1/workflow APIs."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def _get_config(self) -> tuple[str, str, float]:
        base_url = (self._settings.coze_base_url or "").rstrip("/")
        token = self._settings.coze_api_token or self._settings.service_api_token
        if not base_url or not token:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="COZE_NOT_CONFIGURED")
        timeout = max(5, int(self._settings.coze_default_timeout or 180))
        return base_url, token, float(timeout)

    def _stringify_ext(self, payload: Mapping[str, Any] | None) -> dict[str, str]:
        if not payload:
            return {}
        entries: dict[str, str] = {}
        for key, value in payload.items():
            if value is None:
                continue
            key_str = str(key)
            if isinstance(value, (str, int, float, bool)):
                entries[key_str] = str(value)
            else:
                entries[key_str] = str(value)
        return entries

    def run_workflow(
        self,
        *,
        workflow_id: str,
        parameters: dict[str, Any] | None,
        ext: Mapping[str, Any] | None = None,
        is_async: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        base_url, token, timeout = self._get_config()
        url = f"{base_url}/v1/workflow/run"
        body: dict[str, Any] = {
            "workflow_id": workflow_id,
            "parameters": parameters or {},
            "ext": self._stringify_ext(ext),
        }
        if is_async:
            body["is_async"] = True
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if request_id:
            headers["X-Request-ID"] = request_id
        try:
            response = httpx.post(url, json=body, headers=headers, timeout=timeout)
        except httpx.HTTPError as exc:  # pragma: no cover - network errors
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"COZE_REQUEST_FAILED:{exc}",
            ) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            # Coze (or an upstream proxy) may return HTML/text error pages (502, 504, etc).
            # Include a small snippet to make debugging possible from our UI logs.
            snippet = ""
            try:
                snippet = (response.text or "")[:300]
            except Exception:
                snippet = ""
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"COZE_INVALID_RESPONSE status={response.status_code} body={snippet!r}",
            ) from exc
        if response.status_code >= 400:
            detail = payload.get("msg") if isinstance(payload, dict) else payload
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"COZE_HTTP_{response.status_code}:{detail}",
            )
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="COZE_RESPONSE_NOT_JSON",
            )
        return payload

    def get_workflow_run_history(
        self,
        *, 
        execute_id: str,
        workflow_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Get workflow run history by execute_id."""
        base_url, token, timeout = self._get_config()
        url = f"{base_url}/v1/workflow/get_run_history"
        params = {
            "execute_id": execute_id,
            "workflow_id": workflow_id
        }
        headers = {
            "Authorization": f"Bearer {token}",
        }
        if request_id:
            headers["X-Request-ID"] = request_id
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=timeout)
        except httpx.HTTPError as exc:  # pragma: no cover - network errors
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"COZE_REQUEST_FAILED:{exc}",
            ) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            snippet = ""
            try:
                snippet = (response.text or "")[:300]
            except Exception:
                snippet = ""
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"COZE_INVALID_RESPONSE status={response.status_code} body={snippet!r}",
            ) from exc
        if response.status_code >= 400:
            detail = payload.get("msg") if isinstance(payload, dict) else payload
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"COZE_HTTP_{response.status_code}:{detail}",
            )
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="COZE_RESPONSE_NOT_JSON",
            )
        return payload


coze_client = CozeWorkflowClient()
