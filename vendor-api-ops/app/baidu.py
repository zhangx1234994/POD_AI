"""Baidu image processing adapter."""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from app.config import Settings
from app.schemas import InvocationAsset, InvocationError, InvocationResult


class BaiduAdapter:
    def __init__(self) -> None:
        self._token_cache: dict[str, tuple[str, float]] = {}

    def run(
        self,
        *,
        settings: Settings,
        api_key: str,
        secret_key: str | None,
        request: Any,
    ) -> tuple[InvocationResult, InvocationError | None, dict[str, Any]]:
        if not secret_key:
            return InvocationResult(), InvocationError(
                code="VENDOR_API_KEY_DISABLED",
                message="Baidu secret key is not configured",
                suggestion="Create a Baidu key with both key and secret in vendor-api-ops.",
            ), {}
        token, token_error, token_raw = self._get_access_token(settings=settings, api_key=api_key, secret_key=secret_key)
        if token_error:
            return InvocationResult(), token_error, token_raw

        endpoint = _endpoint(request.inputs or {})
        base_url = settings.baidu_base_url.rstrip("/")
        url = f"{base_url}{endpoint}?access_token={token}"
        params, image_error = _build_form_payload(request)
        if image_error:
            return InvocationResult(), image_error, {"request": _safe_request(params)}

        try:
            response = httpx.post(
                url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=params,
                timeout=settings.request_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            return InvocationResult(), InvocationError(
                code="VENDOR_API_TIMEOUT",
                message=str(exc) or "Baidu request timed out",
                retryable=True,
            ), {"request": _safe_request(params)}
        except httpx.HTTPError as exc:
            return InvocationResult(), InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(exc),
                retryable=True,
            ), {"request": _safe_request(params)}

        data = _safe_json(response)
        image_value = _extract_image_value(data)
        if response.status_code >= 400 or not image_value:
            return InvocationResult(), InvocationError(
                code=_error_code(response.status_code, data),
                message=_error_message(data) or response.text[:500] or "Baidu request failed",
                retryable=response.status_code in {408, 409, 429, 500, 502, 503, 504},
            ), {"request": _safe_request(params), "response": data}

        result = InvocationResult(
            images=[
                InvocationAsset(
                    b64=image_value,
                    role="output",
                    mimeType="image/png",
                    metadata={"logId": data.get("log_id")},
                )
            ],
            json={"providerPayloadAccepted": True, "logId": data.get("log_id")},
        )
        return result, None, {"request": _safe_request(params), "response": data}

    def _get_access_token(
        self,
        *,
        settings: Settings,
        api_key: str,
        secret_key: str,
    ) -> tuple[str | None, InvocationError | None, dict[str, Any]]:
        cache_key = f"{api_key}:{secret_key}"
        now = time.time()
        cached = self._token_cache.get(cache_key)
        if cached and cached[1] - now > 60:
            return cached[0], None, {}

        url = f"{settings.baidu_base_url.rstrip('/')}/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key,
        }
        try:
            response = httpx.post(url, params=params, timeout=min(settings.request_timeout_seconds, 10.0))
        except httpx.TimeoutException as exc:
            return None, InvocationError(
                code="VENDOR_API_TIMEOUT",
                message=str(exc) or "Baidu token request timed out",
                retryable=True,
            ), {}
        except httpx.HTTPError as exc:
            return None, InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(exc),
                retryable=True,
            ), {}

        data = _safe_json(response)
        access_token = data.get("access_token") if isinstance(data, dict) else None
        if response.status_code >= 400 or not isinstance(access_token, str) or not access_token:
            return None, InvocationError(
                code=_error_code(response.status_code, data),
                message=_error_message(data) or response.text[:500] or "Baidu token request failed",
                retryable=response.status_code in {408, 409, 429, 500, 502, 503, 504},
            ), {"response": data}
        expires_in = data.get("expires_in") if isinstance(data, dict) else None
        try:
            ttl = int(expires_in or 0)
        except Exception:
            ttl = 0
        self._token_cache[cache_key] = (access_token, now + max(ttl, 300))
        return access_token, None, {"response": {"expires_in": expires_in}}


def _endpoint(inputs: dict[str, Any]) -> str:
    endpoint = inputs.get("request_endpoint") or inputs.get("endpoint") or "/rest/2.0/image-process/v1/image_quality_enhance"
    endpoint = str(endpoint).strip()
    return endpoint if endpoint.startswith("/") else f"/{endpoint}"


def _build_form_payload(request: Any) -> tuple[dict[str, Any], InvocationError | None]:
    inputs = dict(request.inputs or {})
    payload: dict[str, Any] = {}
    for key, value in inputs.items():
        if key in {
            "endpoint",
            "request_endpoint",
            "image_url",
            "imageUrl",
            "url",
            "imageBase64",
            "image_base64",
        }:
            continue
        if value in (None, "", []):
            continue
        payload[key] = value
    image = _resolve_image(inputs, request.assets)
    if not image:
        return payload, InvocationError(
            code="VENDOR_API_INPUT_INVALID",
            message="Baidu image processing requires image_base64/imageBase64/image_url or an input asset URL.",
            suggestion="Upload the source image to OSS first, then pass image_url.",
        )
    payload["image"] = image
    return payload, None


def _resolve_image(inputs: dict[str, Any], assets: list[Any]) -> str | None:
    for key in ("image_base64", "imageBase64", "image"):
        value = inputs.get(key)
        if isinstance(value, str) and value.strip() and not value.strip().startswith("http"):
            return _strip_data_url(value.strip())
    for key in ("image_url", "imageUrl", "url", "image"):
        value = inputs.get(key)
        if isinstance(value, str) and value.strip().startswith("http"):
            return _download_as_base64(value.strip())
    for asset in assets or []:
        value = getattr(asset, "url", None) if hasattr(asset, "url") else None
        if not value and isinstance(asset, dict):
            value = asset.get("url") or asset.get("ossUrl") or asset.get("sourceUrl")
        if isinstance(value, str) and value.strip():
            return _download_as_base64(value.strip())
    return None


def _download_as_base64(url: str) -> str | None:
    try:
        response = httpx.get(url, timeout=20)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    return base64.b64encode(response.content).decode("utf-8")


def _strip_data_url(value: str) -> str:
    if "," in value and value.lower().startswith("data:"):
        return value.split(",", 1)[1]
    return value


def _safe_request(payload: dict[str, Any]) -> dict[str, Any]:
    safe = dict(payload)
    if isinstance(safe.get("image"), str):
        safe["image"] = f"<base64:{len(safe['image'])}>"
    return safe


def _error_code(status_code: int, data: Any) -> str:
    if status_code == 401:
        return "VENDOR_API_KEY_DISABLED"
    if status_code == 429:
        return "VENDOR_API_RATE_LIMITED"
    if isinstance(data, dict):
        for key in ("error_code", "error"):
            value = data.get(key)
            if value:
                return str(value)
    return "VENDOR_API_UPSTREAM_ERROR"


def _error_message(data: Any) -> str | None:
    if isinstance(data, dict):
        for key in ("error_msg", "error_description", "message", "msg"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return {"raw": response.text[:500]}


def _extract_image_value(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("image", "image_processed"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


baidu_adapter = BaiduAdapter()
