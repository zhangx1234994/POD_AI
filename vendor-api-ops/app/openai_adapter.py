"""OpenAI and OpenAI-compatible image adapter."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.schemas import InvocationAsset, InvocationError, InvocationResult


class OpenAIAdapter:
    def run(
        self,
        *,
        settings: Settings,
        provider: str,
        api_key: str,
        request: Any,
    ) -> tuple[InvocationResult, InvocationError | None, dict[str, Any]]:
        api_type = str(request.apiType or "").strip().lower()
        base_url = _base_url(settings, provider)
        endpoint = _endpoint(api_type, request.inputs or {})
        url = f"{base_url}{endpoint}"
        payload = _build_payload(request)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            if api_type == "image_edit":
                response, raw_request = _post_image_edit(
                    url=url,
                    api_key=api_key,
                    request=request,
                    payload=payload,
                    timeout=_request_timeout(settings, request),
                )
            else:
                response = httpx.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=_request_timeout(settings, request),
                )
                raw_request = _safe_request(payload)
        except httpx.TimeoutException as exc:
            return InvocationResult(), InvocationError(
                code="VENDOR_API_TIMEOUT",
                message=str(exc) or "OpenAI request timed out",
                retryable=True,
            ), {"request": _safe_request(payload)}
        except httpx.HTTPError as exc:
            return InvocationResult(), InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(exc),
                retryable=True,
            ), {"request": _safe_request(payload)}

        data = _safe_json(response)
        if response.status_code >= 400:
            return InvocationResult(), InvocationError(
                code=_error_code(response.status_code, data),
                message=_error_message(data) or response.text[:500] or "OpenAI request failed",
                retryable=response.status_code in {408, 409, 429, 500, 502, 503, 504},
            ), {"request": raw_request, "response": data}

        result = _parse_result(data)
        return result, None, {"request": raw_request, "response": data}


def _base_url(settings: Settings, provider: str) -> str:
    if provider == "openai_compatible" and settings.openai_compatible_base_url:
        return settings.openai_compatible_base_url.rstrip("/")
    return settings.openai_base_url.rstrip("/")


def _endpoint(api_type: str, inputs: dict[str, Any]) -> str:
    endpoint = inputs.get("request_endpoint") or inputs.get("endpoint")
    if isinstance(endpoint, str) and endpoint.strip():
        endpoint = endpoint.strip()
        return endpoint if endpoint.startswith("/") else f"/{endpoint}"
    if api_type == "image_edit":
        return "/v1/images/edits"
    return "/v1/images/generations"


def _build_payload(request: Any) -> dict[str, Any]:
    inputs = dict(request.inputs or {})
    api_type = str(request.apiType or "").strip().lower()
    payload: dict[str, Any] = {
        "model": request.model or inputs.get("model"),
        "prompt": inputs.get("prompt"),
    }
    for key in (
        "size",
        "quality",
        "background",
        "n",
        "output_format",
        "output_compression",
        "input_fidelity",
        "response_format",
    ):
        value = inputs.get(key)
        if value not in (None, "", []):
            payload[key] = value
    if api_type == "image_edit":
        image_urls = _input_urls(inputs, request.assets)
        if image_urls:
            payload["images"] = [{"image_url": url} for url in image_urls]
        mask_url = _first_str(inputs.get("mask_url") or inputs.get("maskUrl"))
        if mask_url:
            payload["mask"] = {"image_url": mask_url}
    return {key: value for key, value in payload.items() if value not in (None, "", [])}


def _post_image_edit(
    *,
    url: str,
    api_key: str,
    request: Any,
    payload: dict[str, Any],
    timeout: float,
) -> tuple[httpx.Response, dict[str, Any]]:
    inputs = dict(request.inputs or {})
    files: list[tuple[str, tuple[str, bytes, str]]] = []
    raw_request = _safe_request(payload)
    image_urls = _input_urls(inputs, request.assets)
    for index, image_url in enumerate(image_urls):
        file_payload = _download_file(image_url, fallback_name=f"image_{index}.png")
        if file_payload is None:
            raise httpx.RequestError(f"Failed to download OpenAI edit image: {image_url}")
        files.append(("image[]", file_payload))
    mask_url = _first_str(inputs.get("mask_url") or inputs.get("maskUrl"))
    if mask_url:
        file_payload = _download_file(mask_url, fallback_name="mask.png")
        if file_payload is None:
            raise httpx.RequestError(f"Failed to download OpenAI edit mask: {mask_url}")
        files.append(("mask", file_payload))
    if not files:
        raise httpx.RequestError("OpenAI image edit requires at least one input image")

    data = _multipart_fields(payload)
    raw_request["image_count"] = len(image_urls)
    raw_request["mask_present"] = bool(mask_url)
    headers = {"Authorization": f"Bearer {api_key}"}
    response = httpx.post(url, headers=headers, data=data, files=files, timeout=timeout)
    return response, raw_request


def _multipart_fields(payload: dict[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key, value in payload.items():
        if key in {"images", "mask"} or value in (None, "", []):
            continue
        if isinstance(value, bool):
            fields[key] = "true" if value else "false"
        else:
            fields[key] = str(value)
    return fields


def _download_file(url: str, *, fallback_name: str) -> tuple[str, bytes, str] | None:
    try:
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    content_type = response.headers.get("content-type") or _content_type_from_name(url) or "image/png"
    return fallback_name, response.content, content_type.split(";", 1)[0].strip() or "image/png"


def _content_type_from_name(value: str) -> str | None:
    path = value.split("?", 1)[0].lower()
    if path.endswith(".jpg") or path.endswith(".jpeg"):
        return "image/jpeg"
    if path.endswith(".webp"):
        return "image/webp"
    if path.endswith(".png"):
        return "image/png"
    return None


def _request_timeout(settings: Settings, request: Any) -> float:
    policy = getattr(request, "taskPolicy", None)
    if isinstance(policy, dict):
        value = policy.get("timeoutSeconds") or policy.get("timeout_seconds")
        try:
            if value:
                return float(value)
        except (TypeError, ValueError):
            pass
    return float(settings.request_timeout_seconds)


def _input_urls(inputs: dict[str, Any], assets: list[Any]) -> list[str]:
    urls: list[str] = []
    for key in ("image_url", "imageUrl", "url", "input_url", "inputUrl"):
        value = _first_str(inputs.get(key))
        if value:
            urls.append(value)
    urls.extend(_url_list(inputs.get("image_urls") or inputs.get("imageUrls") or inputs.get("input_urls")))
    for item in assets or []:
        value = None
        if hasattr(item, "url"):
            value = getattr(item, "url")
        elif isinstance(item, dict):
            value = item.get("url") or item.get("ossUrl") or item.get("sourceUrl")
        value = _first_str(value)
        if value:
            urls.append(value)
    dedup: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        dedup.append(url)
    return dedup


def _url_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.replace(",", "\n").splitlines() if line.strip()]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_url_list(item))
        return out
    if isinstance(value, dict):
        return [_first_str(value.get("url") or value.get("ossUrl") or value.get("sourceUrl"))] if _first_str(value.get("url") or value.get("ossUrl") or value.get("sourceUrl")) else []
    return []


def _parse_result(data: Any) -> InvocationResult:
    images: list[InvocationAsset] = []
    texts: list[str] = []
    if isinstance(data, dict):
        for item in data.get("data") or []:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("url"), str) and item["url"].strip():
                images.append(InvocationAsset(url=item["url"].strip(), role="output"))
            elif isinstance(item.get("b64_json"), str) and item["b64_json"].strip():
                images.append(InvocationAsset(b64=item["b64_json"].strip(), role="output", mimeType="image/png"))
            if isinstance(item.get("revised_prompt"), str) and item["revised_prompt"].strip():
                texts.append(item["revised_prompt"].strip())
    return InvocationResult(images=images, texts=texts, json={"providerPayloadAccepted": True})


def _error_code(status_code: int, data: Any) -> str:
    if status_code == 401:
        return "VENDOR_API_KEY_DISABLED"
    if status_code == 429:
        return "VENDOR_API_RATE_LIMITED"
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict) and isinstance(err.get("code"), str) and err.get("code"):
            return str(err["code"])
    return "VENDOR_API_UPSTREAM_ERROR"


def _error_message(data: Any) -> str | None:
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict) and isinstance(err.get("message"), str):
            return err["message"]
        if isinstance(data.get("message"), str):
            return data["message"]
    return None


def _safe_request(payload: dict[str, Any]) -> dict[str, Any]:
    safe = dict(payload)
    for item in safe.get("images") or []:
        if isinstance(item, dict) and isinstance(item.get("image"), str):
            item["image"] = "<binary>"
    if isinstance(safe.get("mask"), dict) and isinstance(safe["mask"].get("image"), str):
        safe["mask"]["image"] = "<binary>"
    return safe


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return {"raw": response.text[:500]}


def _first_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


openai_adapter = OpenAIAdapter()
