"""KIE Market adapter."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.schemas import InvocationAsset, InvocationError, InvocationResult

_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_TRANSIENT_ATTEMPTS = 2


class KieAdapter:
    def submit(
        self,
        *,
        settings: Settings,
        api_key: str,
        request: Any,
    ) -> tuple[str | None, InvocationResult, InvocationError | None, dict[str, Any]]:
        endpoint = _request_endpoint(request)
        base_url = _base_url(settings)
        url = f"{base_url}{endpoint}"
        inputs = dict(request.inputs or {})
        input_payload = _build_input_payload(inputs, request.assets)
        payload: dict[str, Any] = {
            "model": request.model or inputs.get("model"),
            "input": input_payload,
        }
        callback_url = request.callbackUrl or inputs.get("callBackUrl") or inputs.get("callback_url")
        if callback_url:
            payload["callBackUrl"] = callback_url
        extra = inputs.get("extra")
        if isinstance(extra, dict):
            payload.update(extra)

        headers = _headers(api_key)
        try:
            response, data, attempts = _post_with_retry(
                url,
                headers=headers,
                payload=payload,
                timeout=settings.request_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            return None, InvocationResult(), InvocationError(
                code="VENDOR_API_TIMEOUT",
                message=str(exc) or "KIE request timed out",
                retryable=True,
            ), {"request": payload}
        except httpx.HTTPError as exc:
            return None, InvocationResult(), InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(exc),
                retryable=True,
            ), {"request": payload}

        code = data.get("code") if isinstance(data, dict) else None
        if response.status_code >= 400 or code not in (None, 200, "200"):
            message = data.get("msg") if isinstance(data, dict) else response.text[:500]
            return None, InvocationResult(), InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(message or "KIE_TASK_CREATE_FAILED"),
                retryable=response.status_code in {429, 500, 502, 503, 504},
            ), {"request": payload, "response": data, "attempts": attempts}

        task_id = ((data.get("data") or {}) if isinstance(data, dict) else {}).get("taskId")
        if not task_id:
            return None, InvocationResult(), InvocationError(
                code="VENDOR_API_RESPONSE_INVALID",
                message="KIE response did not include taskId",
            ), {"request": payload, "response": data}

        return str(task_id), InvocationResult(json={"submitted": True}), None, {"request": payload, "response": data, "attempts": attempts}

    def fetch(
        self,
        *,
        settings: Settings,
        api_key: str,
        task_id: str,
    ) -> tuple[str, InvocationResult, InvocationError | None, dict[str, Any]]:
        base_url = _base_url(settings)
        url = f"{base_url}/api/v1/jobs/recordInfo"
        try:
            response, data, attempts = _get_with_retry(
                url,
                headers=_headers(api_key),
                params={"taskId": task_id},
                timeout=settings.request_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            return "running", InvocationResult(), InvocationError(
                code="VENDOR_API_TIMEOUT",
                message=str(exc) or "KIE status request timed out",
                retryable=True,
            ), {}
        except httpx.HTTPError as exc:
            return "running", InvocationResult(), InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(exc),
                retryable=True,
            ), {}

        if response.status_code >= 400:
            return "running", InvocationResult(), InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(data.get("msg") if isinstance(data, dict) else response.text[:500]),
                retryable=response.status_code in {429, 500, 502, 503, 504},
            ), {"response": data, "attempts": attempts}

        state = _extract_state(data)
        result_urls, result_json = _parse_result(data)
        result = InvocationResult(
            images=[InvocationAsset(url=url, role="output") for url in result_urls],
            json=result_json,
        )
        if state == "success":
            return "succeeded", result, None, {"response": data, "attempts": attempts}
        if state == "fail":
            return "failed", result, InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=_extract_error_message(data) or "KIE task failed",
                retryable=False,
            ), {"response": data, "attempts": attempts}
        return "running", result, None, {"response": data, "attempts": attempts}


def _base_url(settings: Settings) -> str:
    return settings.kie_base_url.rstrip("/")


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _request_endpoint(request: Any) -> str:
    inputs = request.inputs or {}
    endpoint = inputs.get("request_endpoint") or inputs.get("endpoint") or "/api/v1/jobs/createTask"
    endpoint = str(endpoint).strip()
    return endpoint if endpoint.startswith("/") else f"/{endpoint}"


def _build_input_payload(inputs: dict[str, Any], assets: list[Any]) -> dict[str, Any]:
    input_payload = inputs.get("input")
    if not isinstance(input_payload, dict):
        input_payload = {}
    for key, value in inputs.items():
        if key in {"model", "input", "endpoint", "request_endpoint", "extra"}:
            continue
        if value in (None, "", []):
            continue
        input_payload.setdefault(key, value)
    urls = _asset_urls(assets)
    if urls:
        target = inputs.get("input_array_target")
        if not isinstance(target, str) or not target.strip():
            target = "image_input" if "image_input" in input_payload else "input_urls"
        existing = input_payload.get(target)
        merged = _url_list(existing)
        for url in urls:
            if url not in merged:
                merged.append(url)
        input_payload[target] = merged
    return input_payload


def _asset_urls(assets: list[Any]) -> list[str]:
    out: list[str] = []
    for item in assets or []:
        value = None
        if hasattr(item, "url"):
            value = getattr(item, "url")
        elif isinstance(item, dict):
            value = item.get("url") or item.get("ossUrl") or item.get("sourceUrl")
        if isinstance(value, str) and value.strip():
            out.append(value.strip())
    return out


def _url_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_url_list(item))
        return out
    if isinstance(value, dict):
        for key in ("url", "ossUrl", "sourceUrl"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return [raw.strip()]
    return []


def _extract_state(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    record = data.get("data") if isinstance(data.get("data"), dict) else data
    for key in ("state", "status", "taskStatus"):
        value = record.get(key) if isinstance(record, dict) else None
        if value is not None:
            return str(value).strip().lower()
    return ""


def _parse_result(data: Any) -> tuple[list[str], dict[str, Any]]:
    if not isinstance(data, dict):
        return [], {}
    record = data.get("data") if isinstance(data.get("data"), dict) else data
    result = record.get("result") if isinstance(record, dict) else None
    if isinstance(result, str):
        try:
            import json

            parsed = json.loads(result)
        except Exception:
            parsed = {"raw": result}
    elif isinstance(result, dict):
        parsed = result
    else:
        parsed = {}
    urls: list[str] = []
    for key in ("resultUrls", "result_urls", "urls", "images"):
        value = parsed.get(key) if isinstance(parsed, dict) else None
        urls.extend(_url_list(value))
    if isinstance(record, dict):
        urls.extend(_url_list(record.get("resultUrls")))
    dedup: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        dedup.append(url)
    return dedup, parsed if isinstance(parsed, dict) else {}


def _extract_error_message(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    record = data.get("data") if isinstance(data.get("data"), dict) else data
    for key in ("failMsg", "errorMessage", "message", "msg"):
        value = record.get(key) if isinstance(record, dict) else data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _post_with_retry(url: str, *, headers: dict[str, str], payload: dict[str, Any], timeout: int) -> tuple[httpx.Response, Any, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, _MAX_TRANSIENT_ATTEMPTS + 1):
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            attempts.append({"attempt": attempt, "error": exc.__class__.__name__, "message": str(exc)})
            if attempt < _MAX_TRANSIENT_ATTEMPTS:
                continue
            raise
        data = _safe_json(response)
        attempts.append(_attempt_summary(attempt=attempt, response=response, data=data))
        if attempt < _MAX_TRANSIENT_ATTEMPTS and _is_transient_response(response, data):
            continue
        return response, data, attempts
    return response, data, attempts


def _get_with_retry(
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any],
    timeout: int,
) -> tuple[httpx.Response, Any, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, _MAX_TRANSIENT_ATTEMPTS + 1):
        try:
            response = httpx.get(url, headers=headers, params=params, timeout=timeout)
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            attempts.append({"attempt": attempt, "error": exc.__class__.__name__, "message": str(exc)})
            if attempt < _MAX_TRANSIENT_ATTEMPTS:
                continue
            raise
        data = _safe_json(response)
        attempts.append(_attempt_summary(attempt=attempt, response=response, data=data))
        if attempt < _MAX_TRANSIENT_ATTEMPTS and _is_transient_response(response, data):
            continue
        return response, data, attempts
    return response, data, attempts


def _attempt_summary(*, attempt: int, response: httpx.Response, data: Any) -> dict[str, Any]:
    code = data.get("code") if isinstance(data, dict) else None
    return {
        "attempt": attempt,
        "httpStatus": response.status_code,
        "code": code,
    }


def _is_transient_response(response: httpx.Response, data: Any) -> bool:
    if response.status_code in _TRANSIENT_STATUS_CODES:
        return True
    code = data.get("code") if isinstance(data, dict) else None
    try:
        return int(code) in _TRANSIENT_STATUS_CODES
    except Exception:
        return False


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return {"raw": response.text[:500]}


kie_adapter = KieAdapter()
