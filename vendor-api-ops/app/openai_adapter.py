"""OpenAI and OpenAI-compatible image adapter."""

from __future__ import annotations

import json
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

    def submit_batch(
        self,
        *,
        settings: Settings,
        provider: str,
        api_key: str,
        request: Any,
    ) -> tuple[str | None, InvocationResult, InvocationError | None, dict[str, Any]]:
        """Submit an OpenAI Batch job for image generation/editing.

        Batch is intentionally a separate execution mode. It has lower cost but
        is not suitable for realtime user editing because OpenAI completes it
        asynchronously within the configured completion window.
        """

        api_type = str(request.apiType or "").strip().lower()
        base_url = _base_url(settings, provider)
        endpoint = _endpoint(api_type, request.inputs or {})
        timeout = _request_timeout(settings, request)
        batch_lines = _batch_lines(request=request, endpoint=endpoint)
        if not batch_lines:
            return None, InvocationResult(), InvocationError(
                code="OPENAI_BATCH_EMPTY",
                message="OpenAI batch requires at least one request item.",
                retryable=False,
            ), {"request": {"endpoint": endpoint, "itemCount": 0}}

        file_content = "\n".join(json.dumps(line, ensure_ascii=False, separators=(",", ":")) for line in batch_lines) + "\n"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            file_response = httpx.post(
                f"{base_url}/v1/files",
                headers=headers,
                data={"purpose": "batch"},
                files={"file": ("openai_batch_input.jsonl", file_content.encode("utf-8"), "application/jsonl")},
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            return None, InvocationResult(), InvocationError(
                code="VENDOR_API_TIMEOUT",
                message=str(exc) or "OpenAI batch file upload timed out",
                retryable=True,
            ), {"request": {"endpoint": endpoint, "itemCount": len(batch_lines)}}
        except httpx.HTTPError as exc:
            return None, InvocationResult(), InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(exc),
                retryable=True,
            ), {"request": {"endpoint": endpoint, "itemCount": len(batch_lines)}}

        file_data = _safe_json(file_response)
        if file_response.status_code >= 400:
            return None, InvocationResult(), InvocationError(
                code=_error_code(file_response.status_code, file_data),
                message=_error_message(file_data) or file_response.text[:500] or "OpenAI batch file upload failed",
                retryable=file_response.status_code in {408, 409, 429, 500, 502, 503, 504},
            ), {"request": {"endpoint": endpoint, "itemCount": len(batch_lines)}, "fileResponse": file_data}

        input_file_id = _first_str(file_data.get("id") if isinstance(file_data, dict) else None)
        if not input_file_id:
            return None, InvocationResult(), InvocationError(
                code="OPENAI_BATCH_FILE_ID_MISSING",
                message="OpenAI batch file upload did not return a file id.",
                retryable=True,
            ), {"request": {"endpoint": endpoint, "itemCount": len(batch_lines)}, "fileResponse": file_data}

        batch_payload = {
            "input_file_id": input_file_id,
            "endpoint": endpoint,
            "completion_window": str((request.taskPolicy or {}).get("completionWindow") or "24h"),
            "metadata": _batch_metadata(request, item_count=len(batch_lines)),
        }
        try:
            batch_response = httpx.post(
                f"{base_url}/v1/batches",
                headers={**headers, "Content-Type": "application/json"},
                json=batch_payload,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            return None, InvocationResult(), InvocationError(
                code="VENDOR_API_TIMEOUT",
                message=str(exc) or "OpenAI batch submit timed out",
                retryable=True,
            ), {"request": {"endpoint": endpoint, "itemCount": len(batch_lines), "inputFileId": input_file_id}}
        except httpx.HTTPError as exc:
            return None, InvocationResult(), InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(exc),
                retryable=True,
            ), {"request": {"endpoint": endpoint, "itemCount": len(batch_lines), "inputFileId": input_file_id}}

        batch_data = _safe_json(batch_response)
        if batch_response.status_code >= 400:
            return None, InvocationResult(), InvocationError(
                code=_error_code(batch_response.status_code, batch_data),
                message=_error_message(batch_data) or batch_response.text[:500] or "OpenAI batch submit failed",
                retryable=batch_response.status_code in {408, 409, 429, 500, 502, 503, 504},
            ), {
                "request": {"endpoint": endpoint, "itemCount": len(batch_lines), "inputFileId": input_file_id},
                "batchResponse": batch_data,
            }

        batch_id = _first_str(batch_data.get("id") if isinstance(batch_data, dict) else None)
        if not batch_id:
            return None, InvocationResult(), InvocationError(
                code="OPENAI_BATCH_ID_MISSING",
                message="OpenAI batch submit did not return a batch id.",
                retryable=True,
            ), {
                "request": {"endpoint": endpoint, "itemCount": len(batch_lines), "inputFileId": input_file_id},
                "batchResponse": batch_data,
            }

        result = InvocationResult(
            json={
                "batch": {
                    "id": batch_id,
                    "status": _first_str(batch_data.get("status") if isinstance(batch_data, dict) else None) or "validating",
                    "inputFileId": input_file_id,
                    "itemCount": len(batch_lines),
                    "completionWindow": batch_payload["completion_window"],
                }
            }
        )
        return batch_id, result, None, {
            "request": {"endpoint": endpoint, "itemCount": len(batch_lines), "inputFileId": input_file_id},
            "batch": _safe_batch_summary(batch_data),
        }

    def fetch_batch(
        self,
        *,
        settings: Settings,
        provider: str,
        api_key: str,
        batch_id: str,
    ) -> tuple[str, InvocationResult, InvocationError | None, dict[str, Any]]:
        base_url = _base_url(settings, provider)
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            batch_response = httpx.get(
                f"{base_url}/v1/batches/{batch_id}",
                headers=headers,
                timeout=float(settings.request_timeout_seconds),
            )
        except httpx.TimeoutException as exc:
            return "running", InvocationResult(), InvocationError(
                code="VENDOR_API_TIMEOUT",
                message=str(exc) or "OpenAI batch fetch timed out",
                retryable=True,
            ), {"batchId": batch_id}
        except httpx.HTTPError as exc:
            return "running", InvocationResult(), InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(exc),
                retryable=True,
            ), {"batchId": batch_id}

        batch_data = _safe_json(batch_response)
        if batch_response.status_code >= 400:
            return "running", InvocationResult(), InvocationError(
                code=_error_code(batch_response.status_code, batch_data),
                message=_error_message(batch_data) or batch_response.text[:500] or "OpenAI batch fetch failed",
                retryable=batch_response.status_code in {408, 409, 429, 500, 502, 503, 504},
            ), {"batchId": batch_id, "batchResponse": batch_data}

        upstream_status = _first_str(batch_data.get("status") if isinstance(batch_data, dict) else None) or "unknown"
        if upstream_status in {"validating", "in_progress", "finalizing", "cancelling"}:
            return "running", InvocationResult(json={"batch": _safe_batch_summary(batch_data)}), None, {
                "batch": _safe_batch_summary(batch_data)
            }
        if upstream_status != "completed":
            return "failed", InvocationResult(json={"batch": _safe_batch_summary(batch_data)}), InvocationError(
                code="OPENAI_BATCH_FAILED",
                message=f"OpenAI batch finished with status: {upstream_status}",
                retryable=upstream_status in {"expired"},
            ), {"batch": _safe_batch_summary(batch_data)}

        output_file_id = _first_str(batch_data.get("output_file_id") if isinstance(batch_data, dict) else None)
        if not output_file_id:
            return "failed", InvocationResult(json={"batch": _safe_batch_summary(batch_data)}), InvocationError(
                code="OPENAI_BATCH_OUTPUT_MISSING",
                message="OpenAI batch completed but did not expose output_file_id.",
                retryable=True,
            ), {"batch": _safe_batch_summary(batch_data)}

        try:
            output_response = httpx.get(
                f"{base_url}/v1/files/{output_file_id}/content",
                headers=headers,
                timeout=float(settings.request_timeout_seconds),
            )
        except httpx.TimeoutException as exc:
            return "running", InvocationResult(json={"batch": _safe_batch_summary(batch_data)}), InvocationError(
                code="VENDOR_API_TIMEOUT",
                message=str(exc) or "OpenAI batch output download timed out",
                retryable=True,
            ), {"batch": _safe_batch_summary(batch_data), "outputFileId": output_file_id}
        except httpx.HTTPError as exc:
            return "running", InvocationResult(json={"batch": _safe_batch_summary(batch_data)}), InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(exc),
                retryable=True,
            ), {"batch": _safe_batch_summary(batch_data), "outputFileId": output_file_id}

        if output_response.status_code >= 400:
            output_data = _safe_json(output_response)
            return "running", InvocationResult(json={"batch": _safe_batch_summary(batch_data)}), InvocationError(
                code=_error_code(output_response.status_code, output_data),
                message=_error_message(output_data) or output_response.text[:500] or "OpenAI batch output download failed",
                retryable=output_response.status_code in {408, 409, 429, 500, 502, 503, 504},
            ), {"batch": _safe_batch_summary(batch_data), "outputFileId": output_file_id, "outputResponse": output_data}

        result, output_summary = _parse_batch_output(output_response.text)
        result.json_["batch"] = _safe_batch_summary(batch_data)
        result.json_["batchOutput"] = output_summary
        return "succeeded", result, None, {
            "batch": _safe_batch_summary(batch_data),
            "outputFileId": output_file_id,
            "output": output_summary,
        }


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
    passthrough_keys = [
        "size",
        "quality",
        "background",
        "n",
        "output_format",
        "output_compression",
        "response_format",
    ]
    if api_type != "image_edit":
        passthrough_keys.append("input_fidelity")
    for key in passthrough_keys:
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


def _batch_lines(*, request: Any, endpoint: str) -> list[dict[str, Any]]:
    inputs = dict(request.inputs or {})
    raw_items = _batch_request_items(inputs.get("batch_requests") or inputs.get("batchRequests"))
    if not isinstance(raw_items, list) or not raw_items:
        payload = _build_payload(request)
        custom_id = _first_str(inputs.get("custom_id") or inputs.get("customId") or request.requestId) or "request-1"
        return [{"custom_id": custom_id, "method": "POST", "url": endpoint, "body": payload}]

    lines: list[dict[str, Any]] = []
    base_inputs = dict(inputs)
    base_inputs.pop("batch_requests", None)
    base_inputs.pop("batchRequests", None)
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        item_inputs = item.get("inputs") if isinstance(item.get("inputs"), dict) else item
        custom_id = _first_str(item.get("custom_id") or item.get("customId")) or f"request-{index}"
        payload_request = _RequestView(
            model=item.get("model") or request.model,
            apiType=item.get("apiType") or request.apiType,
            inputs={**base_inputs, **dict(item_inputs or {})},
            assets=request.assets,
            taskPolicy=request.taskPolicy,
            requestId=custom_id,
        )
        lines.append({"custom_id": custom_id, "method": "POST", "url": endpoint, "body": _build_payload(payload_request)})
    return lines


def _batch_request_items(value: Any) -> list[Any] | None:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, list) else None
    return None


class _RequestView:
    def __init__(
        self,
        *,
        model: Any,
        apiType: Any,
        inputs: dict[str, Any],
        assets: list[Any],
        taskPolicy: dict[str, Any],
        requestId: str | None,
    ) -> None:
        self.model = model
        self.apiType = apiType
        self.inputs = inputs
        self.assets = assets
        self.taskPolicy = taskPolicy
        self.requestId = requestId


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


def _parse_batch_output(text: str) -> tuple[InvocationResult, dict[str, Any]]:
    images: list[InvocationAsset] = []
    texts: list[str] = []
    success_count = 0
    error_count = 0
    output_items: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            error_count += 1
            continue
        custom_id = _first_str(item.get("custom_id") or item.get("customId"))
        response = item.get("response") if isinstance(item.get("response"), dict) else {}
        body = response.get("body") if isinstance(response.get("body"), dict) else {}
        error = item.get("error")
        if error:
            error_count += 1
            output_items.append({"customId": custom_id, "status": "failed", "error": _safe_error_summary(error)})
            continue
        parsed = _parse_result(body)
        for image in parsed.images:
            metadata = dict(image.metadata or {})
            if custom_id:
                metadata["customId"] = custom_id
            image.metadata = metadata
            images.append(image)
        texts.extend(parsed.texts)
        success_count += 1
        output_items.append(
            {
                "customId": custom_id,
                "status": "succeeded",
                "imageCount": len(parsed.images),
                "textCount": len(parsed.texts),
            }
        )
    return InvocationResult(images=images, texts=texts), {
        "successCount": success_count,
        "errorCount": error_count,
        "items": output_items[:200],
        "truncated": len(output_items) > 200,
    }


def _safe_error_summary(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: value.get(key) for key in ("code", "message", "param") if value.get(key) is not None}
    return str(value)[:300]


def _batch_metadata(request: Any, *, item_count: int) -> dict[str, str]:
    metadata: dict[str, str] = {
        "service": "podi-vendor-api-ops",
        "capabilityKey": str(request.capabilityKey or ""),
        "itemCount": str(item_count),
    }
    if request.requestId:
        metadata["requestId"] = str(request.requestId)
    if request.traceId:
        metadata["traceId"] = str(request.traceId)
    return metadata


def _safe_batch_summary(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    keys = (
        "id",
        "status",
        "endpoint",
        "input_file_id",
        "output_file_id",
        "error_file_id",
        "completion_window",
        "request_counts",
        "created_at",
        "completed_at",
        "expires_at",
    )
    return {key: data.get(key) for key in keys if data.get(key) is not None}


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
