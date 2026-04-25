"""Admin-facing client for vendor-api-ops."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import get_settings


class VendorAdminClient:
    def _base_url(self) -> str:
        return get_settings().vendor_api_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        token = get_settings().vendor_api_token
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._base_url()}{path}"
        try:
            with httpx.Client(timeout=get_settings().vendor_api_timeout_seconds) as client:
                response = client.request(method, url, json=json, params=params, headers=self._headers())
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="VENDOR_API_TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="VENDOR_API_EXECUTOR_UNAVAILABLE") from exc
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=_error_detail(response))
        try:
            return response.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="VENDOR_API_RESPONSE_INVALID") from exc

    def list_providers(self) -> dict[str, Any]:
        payload = self._request("GET", "/v1/providers")
        return {**payload, "baseUrl": self._base_url()}

    def check_egress(self, provider: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/v1/providers/{provider}/egress-check", json=payload)

    def list_keys(self, provider: str | None = None) -> dict[str, Any]:
        payload = self._request("GET", "/v1/keys", params={"provider": provider} if provider else None)
        items = payload.get("items") if isinstance(payload, dict) else []
        return {"baseUrl": self._base_url(), "items": items if isinstance(items, list) else []}

    def usage_summary(self, *, window_hours: int = 24) -> dict[str, Any]:
        payload = self._request("GET", "/v1/usage/summary", params={"windowHours": window_hours})
        items = payload.get("items") if isinstance(payload, dict) else []
        return {
            "baseUrl": self._base_url(),
            "windowHours": int(payload.get("windowHours") or window_hours) if isinstance(payload, dict) else window_hours,
            "items": items if isinstance(items, list) else [],
        }

    def create_key(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/keys", json=payload)

    def update_key(self, key_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/v1/keys/{key_id}", json=payload)


def _error_detail(response: httpx.Response) -> Any:
    try:
        data = response.json()
    except ValueError:
        return response.text[:500] or "VENDOR_API_UPSTREAM_ERROR"
    if isinstance(data, dict):
        return data.get("detail") or data.get("errorCode") or data.get("message") or data
    return data


vendor_admin_client = VendorAdminClient()
