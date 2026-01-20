"""Baidu Image Processing adapter."""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

import httpx

from app.models.task import Task
from app.core.config import get_settings

from .base import ExecutionContext, ExecutionResult, ExecutorAdapter


class BaiduImageExecutorAdapter(ExecutorAdapter):
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._token_cache: dict[str, tuple[str, float]] = {}

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        definition = context.workflow.definition or {}
        endpoint = definition.get("endpoint") or "/rest/2.0/image-process/v1/quality_upgrade"
        if not endpoint:
            return ExecutionResult(
                success=False,
                status="failed",
                error_message="BAIDU_ENDPOINT_MISSING",
            )
        params = {**(definition.get("defaults") or {}), **(context.payload or {})}
        image_payload = self._resolve_image(params, context.task)
        if not image_payload:
            return ExecutionResult(success=False, status="failed", error_message="IMAGE_REQUIRED")
        params["image"] = image_payload

        try:
            token = self._get_access_token(context.executor.config or {})
        except ValueError as exc:
            return ExecutionResult(success=False, status="failed", error_message=str(exc))

        base_url = (context.executor.base_url or "https://aip.baidubce.com").rstrip("/")
        url = f"{base_url}{endpoint}?access_token={token}"
        timeout = definition.get("timeout", 30)

        try:
            response = httpx.post(
                url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=params,
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            self._logger.exception("Baidu API request failed: %s", exc)
            return ExecutionResult(success=False, status="failed", error_message="HTTP_ERROR")

        data = response.json()
        if "image" not in data:
            error_msg = data.get("error_msg") or data.get("error_code") or "BAIDU_API_ERROR"
            return ExecutionResult(success=False, status="failed", error_message=str(error_msg))

        output = data["image"]
        data_url = f"data:image/png;base64,{output}"
        payload = {
            "provider": "baidu_image",
            "logId": data.get("log_id"),
            "resultImage": data_url,
            "raw": data,
        }
        return ExecutionResult(success=True, status="completed", progress=100, result_payload=payload)

    def _get_access_token(self, config: dict[str, Any]) -> str:
        api_key = config.get("apiKey") or config.get("api_key")
        secret_key = config.get("secretKey") or config.get("secret_key")
        if not api_key or not secret_key:
            settings = get_settings()
            api_key = api_key or settings.baidu_api_key
            secret_key = secret_key or settings.baidu_secret_key
        if not api_key or not secret_key:
            raise ValueError("BAIDU_API_KEY_MISSING")
        cache_key = f"{api_key}:{secret_key}"
        cached = self._token_cache.get(cache_key)
        now = time.time()
        if cached and cached[1] - now > 60:
            return cached[0]

        token_url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key,
        }
        response = httpx.post(token_url, params=params, timeout=10)
        token_data = response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 0)
        if not access_token:
            raise ValueError(token_data.get("error_description") or "BAIDU_TOKEN_ERROR")
        self._token_cache[cache_key] = (access_token, now + int(expires_in))
        return access_token

    def _resolve_image(self, params: dict[str, Any], task: Task) -> str | None:
        image_value = params.get("image") or params.get("imageBase64")
        if isinstance(image_value, str) and image_value and not image_value.startswith("http"):
            return image_value

        image_url = image_value if isinstance(image_value, str) else params.get("imageUrl")
        if not image_url:
            for asset in task.assets:
                if asset.asset_type == "input" and asset.url:
                    image_url = asset.url
                    break

        if not image_url:
            return None
        try:
            resp = httpx.get(image_url, timeout=20)
            resp.raise_for_status()
            return base64.b64encode(resp.content).decode("utf-8")
        except httpx.HTTPError as exc:
            self._logger.warning("Failed to fetch image for task %s: %s", task.id, exc)
            return None
