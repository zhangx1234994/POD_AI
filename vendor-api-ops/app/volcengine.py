"""Volcengine Ark adapter."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.schemas import InvocationAsset, InvocationError, InvocationResult


class VolcengineAdapter:
    def run(
        self,
        *,
        settings: Settings,
        api_key: str,
        request: Any,
    ) -> tuple[InvocationResult, InvocationError | None, dict[str, Any]]:
        api_type = str(request.apiType or "").strip().lower()
        endpoint = _endpoint(api_type, request.inputs or {})
        url = f"{settings.volcengine_base_url.rstrip('/')}{endpoint}"
        payload = _build_payload(request)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=settings.request_timeout_seconds)
        except httpx.TimeoutException as exc:
            return InvocationResult(), InvocationError(
                code="VENDOR_API_TIMEOUT",
                message=str(exc) or "Volcengine request timed out",
                retryable=True,
            ), {"request": payload}
        except httpx.HTTPError as exc:
            return InvocationResult(), InvocationError(
                code="VENDOR_API_UPSTREAM_ERROR",
                message=str(exc),
                retryable=True,
            ), {"request": payload}

        data = _safe_json(response)
        if response.status_code >= 400:
            return InvocationResult(), InvocationError(
                code=_error_code(response.status_code, data),
                message=_error_message(data) or response.text[:500] or "Volcengine request failed",
                retryable=response.status_code in {408, 409, 429, 500, 502, 503, 504},
            ), {"request": payload, "response": data}

        if api_type == "chat_completions":
            result = _parse_chat_result(data)
        else:
            result = _parse_media_result(data, api_type=api_type)
        return result, None, {"request": payload, "response": data}


def _endpoint(api_type: str, inputs: dict[str, Any]) -> str:
    endpoint = inputs.get("request_endpoint") or inputs.get("endpoint")
    if isinstance(endpoint, str) and endpoint.strip():
        endpoint = endpoint.strip()
        return endpoint if endpoint.startswith("/") else f"/{endpoint}"
    if api_type == "chat_completions":
        return "/api/v3/chat/completions"
    if api_type == "video_generation":
        return "/api/v3/contents/generations/tasks"
    return "/api/v3/images/generations"


def _build_payload(request: Any) -> dict[str, Any]:
    inputs = dict(request.inputs or {})
    api_type = str(request.apiType or "").strip().lower()
    if api_type == "chat_completions":
        return _build_chat_payload(request, inputs)
    if api_type == "video_generation":
        return _build_video_payload(request, inputs)
    return _build_image_payload(request, inputs)


def _build_chat_payload(request: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    prompt = inputs.get("prompt") or inputs.get("text") or ""
    content: list[dict[str, Any]] = [{"type": "text", "text": str(prompt)}]
    image_url = _first_url(inputs.get("image_url") or inputs.get("imageUrl"))
    if image_url:
        content.insert(0, {"type": "image_url", "image_url": {"url": image_url}})
    payload: dict[str, Any] = {
        "model": request.model or inputs.get("model"),
        "messages": inputs.get("messages") if isinstance(inputs.get("messages"), list) else [{"role": "user", "content": content}],
        "stream": bool(inputs.get("stream", False)),
    }
    _merge_passthrough(payload, inputs, exclude={"prompt", "text", "image_url", "imageUrl", "messages"})
    return _strip_empty(payload)


def _build_image_payload(request: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": request.model or inputs.get("model"),
        "prompt": inputs.get("prompt"),
        "stream": bool(inputs.get("stream", False)),
    }
    for key in (
        "negative_prompt",
        "size",
        "response_format",
        "n",
        "sequential_image_generation",
        "max_images",
        "watermark",
        "width",
        "height",
    ):
        if inputs.get(key) not in (None, "", []):
            payload[key] = inputs[key]
    image_urls = _url_list(inputs.get("image_urls") or inputs.get("imageUrls") or inputs.get("input_urls"))
    if image_urls:
        payload["image_urls"] = image_urls
    _merge_passthrough(
        payload,
        inputs,
        exclude={
            "prompt",
            "negative_prompt",
            "size",
            "response_format",
            "n",
            "image_urls",
            "imageUrls",
            "input_urls",
            "sequential_image_generation",
            "max_images",
            "watermark",
            "width",
            "height",
        },
    )
    return _strip_empty(payload)


def _build_video_payload(request: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": request.model or inputs.get("model"),
        "content": inputs.get("content") or inputs.get("prompt"),
        "stream": bool(inputs.get("stream", False)),
    }
    for key in ("image_url", "image_urls", "duration", "ratio", "resolution", "fps", "watermark"):
        if inputs.get(key) not in (None, "", []):
            payload[key] = inputs[key]
    _merge_passthrough(payload, inputs, exclude=set(payload.keys()) | {"prompt"})
    return _strip_empty(payload)


def _merge_passthrough(payload: dict[str, Any], inputs: dict[str, Any], *, exclude: set[str]) -> None:
    for key, value in inputs.items():
        if key in exclude or key in {"endpoint", "request_endpoint"}:
            continue
        if value in (None, "", []):
            continue
        payload.setdefault(key, value)


def _parse_chat_result(data: Any) -> InvocationResult:
    texts: list[str] = []
    if isinstance(data, dict):
        for choice in data.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str) and content.strip():
                texts.append(content.strip())
            elif isinstance(content, list):
                joined = " ".join(
                    str(part.get("text") or "").strip() for part in content if isinstance(part, dict)
                ).strip()
                if joined:
                    texts.append(joined)
    return InvocationResult(texts=texts, json={"providerPayloadAccepted": True})


def _parse_media_result(data: Any, *, api_type: str) -> InvocationResult:
    images: list[InvocationAsset] = []
    videos: list[InvocationAsset] = []
    seen_video_urls: set[str] = set()
    if isinstance(data, dict):
        for item in data.get("data") or []:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("url"), str) and item["url"].strip():
                url = item["url"].strip()
                asset = InvocationAsset(url=url, role="output")
                if api_type == "video_generation" or _looks_like_video(item["url"]):
                    seen_video_urls.add(url)
                    videos.append(asset)
                else:
                    images.append(asset)
            if isinstance(item.get("b64_json"), str) and item["b64_json"].strip():
                images.append(InvocationAsset(b64=item["b64_json"].strip(), role="output", mimeType="image/png"))
            for key in ("video_url", "videoUrl", "url"):
                value = item.get(key)
                if isinstance(value, str) and value.strip() and (key != "url" or _looks_like_video(value)):
                    url = value.strip()
                    if url not in seen_video_urls:
                        seen_video_urls.add(url)
                        videos.append(InvocationAsset(url=url, role="output"))
                    break
    return InvocationResult(images=images, videos=videos, json={"providerPayloadAccepted": True})


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


def _first_url(value: Any) -> str | None:
    urls = _url_list(value)
    return urls[0] if urls else None


def _url_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.replace(",", "\n").splitlines() if line.strip()]
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


def _looks_like_video(value: str) -> bool:
    lower = value.lower()
    return any(lower.split("?", 1)[0].endswith(ext) for ext in (".mp4", ".mov", ".webm"))


def _strip_empty(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in (None, "", [])}


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return {"raw": response.text[:500]}


volcengine_adapter = VolcengineAdapter()
