"""Client for the standalone vendor-api-ops service."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import get_settings
from app.models.integration import Ability, Executor


class VendorApiClient:
    def invoke(
        self,
        *,
        executor: Executor,
        ability: Ability,
        inputs: dict[str, Any],
        assets: list[dict[str, Any]] | None,
        request_id: str,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        base_url = self._base_url(executor, settings.vendor_api_base_url)
        metadata = ability.extra_metadata if isinstance(ability.extra_metadata, dict) else {}
        vendor_inputs = dict(inputs or {})
        for key in ("request_endpoint", "input_array_target"):
            value = metadata.get(key)
            if value not in (None, "", []):
                vendor_inputs.setdefault(key, value)
        payload = {
            "provider": ability.provider,
            "capabilityKey": ability.capability_key,
            "model": vendor_inputs.get("model") or metadata.get("model_id"),
            "apiType": metadata.get("api_type"),
            "executionMode": metadata.get("execution_mode") or metadata.get("executionMode"),
            "inputs": vendor_inputs,
            "assets": assets or [],
            "taskPolicy": {
                "maxConcurrency": int(getattr(executor, "max_concurrency", 1) or 1),
                "timeoutSeconds": settings.vendor_api_timeout_seconds,
            },
            "requestId": request_id,
            "traceId": trace_id,
        }
        headers = self._headers(settings.vendor_api_token)
        try:
            with httpx.Client(timeout=settings.vendor_api_timeout_seconds) as client:
                response = client.post(f"{base_url}/v1/invocations", json=payload, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="VENDOR_API_TIMEOUT") from exc
        except httpx.HTTPStatusError as exc:
            detail = self._safe_error(exc.response)
            raise HTTPException(status_code=502, detail=detail or "VENDOR_API_UPSTREAM_ERROR") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"VENDOR_API_UNAVAILABLE:{exc}") from exc

        data = response.json()
        return self.normalize_invocation_response(data=data, executor=executor)

    def fetch(self, *, executor: Executor, vendor_invocation_id: str) -> dict[str, Any]:
        settings = get_settings()
        base_url = self._base_url(executor, settings.vendor_api_base_url)
        try:
            with httpx.Client(timeout=settings.vendor_api_timeout_seconds) as client:
                response = client.get(
                    f"{base_url}/v1/invocations/{vendor_invocation_id}",
                    headers=self._headers(settings.vendor_api_token),
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="VENDOR_API_TIMEOUT") from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=self._safe_error(exc.response) or "VENDOR_API_UPSTREAM_ERROR") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"VENDOR_API_UNAVAILABLE:{exc}") from exc
        return self.normalize_invocation_response(data=response.json(), executor=executor)

    @staticmethod
    def normalize_invocation_response(*, data: dict[str, Any], executor: Executor | None = None) -> dict[str, Any]:
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        error = data.get("error") if isinstance(data.get("error"), dict) else None
        images = _assets_from_vendor(result.get("images"))
        videos = _assets_from_vendor(result.get("videos"))
        texts = result.get("texts") if isinstance(result.get("texts"), list) else []
        raw = data.get("raw") if isinstance(data.get("raw"), dict) else {}
        metadata = {
            "vendorInvocationId": data.get("vendorInvocationId"),
            "vendorTaskId": data.get("vendorTaskId"),
            "taskId": data.get("vendorTaskId"),
            "executorId": getattr(executor, "id", None),
            "baseUrl": getattr(executor, "base_url", None),
        }
        if error:
            metadata["vendorError"] = error
        return {
            "provider": data.get("provider"),
            "model": data.get("model"),
            "status": data.get("status"),
            "state": data.get("status"),
            "success": data.get("success"),
            "taskId": data.get("vendorTaskId") or data.get("vendorInvocationId"),
            "vendorInvocationId": data.get("vendorInvocationId"),
            "vendorTaskId": data.get("vendorTaskId"),
            "images": images,
            "videos": videos,
            "assets": images + videos,
            "texts": texts,
            "resultUrls": [item["url"] for item in images if isinstance(item.get("url"), str)],
            "jsonOutput": result.get("json") if isinstance(result.get("json"), dict) else {},
            "usage": result.get("usage") if isinstance(result.get("usage"), dict) else {},
            "cost": result.get("cost") if isinstance(result.get("cost"), dict) else {},
            "error": error,
            "metadata": metadata,
            "raw": {"vendorApi": raw},
        }

    @staticmethod
    def _base_url(executor: Executor, default: str) -> str:
        cfg = executor.config if isinstance(executor.config, dict) else {}
        base_url = executor.base_url or cfg.get("baseUrl") or cfg.get("base_url") or default
        return str(base_url).rstrip("/")

    @staticmethod
    def _headers(token: str | None) -> dict[str, str]:
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _safe_error(response: httpx.Response) -> Any:
        try:
            return response.json()
        except Exception:
            return response.text[:500]


def _assets_from_vendor(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        b64 = item.get("b64")
        if not url and not b64:
            continue
        out.append(
            {
                "url": url,
                "sourceUrl": url,
                "base64": b64,
                "type": item.get("mimeType"),
                "tag": item.get("role") or "output",
                "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else None,
            }
        )
    return out


vendor_api_client = VendorApiClient()
