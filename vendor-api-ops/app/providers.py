"""Provider registry and network checks."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.schemas import EgressCheckResponse, ProviderInfo
from app.storage import vendor_storage


ERR_PROVIDER_NOT_SUPPORTED = "VENDOR_API_PROVIDER_NOT_SUPPORTED"
ERR_PROXY_UNAVAILABLE = "VENDOR_API_PROXY_UNAVAILABLE"
ERR_TIMEOUT = "VENDOR_API_TIMEOUT"
ERR_UPSTREAM_ERROR = "VENDOR_API_UPSTREAM_ERROR"
ERR_KEY_MISSING = "VENDOR_API_KEY_MISSING"
ERR_AUTH_FAILED = "VENDOR_API_AUTH_FAILED"


@dataclass(frozen=True)
class ProviderDefinition:
    provider: str
    display_name: str
    requires_global_egress: bool
    supported_checks: tuple[str, ...]
    supported_api_types: tuple[str, ...]
    execution_modes: tuple[str, ...]


PROVIDERS: dict[str, ProviderDefinition] = {
    "openai": ProviderDefinition(
        provider="openai",
        display_name="OpenAI",
        requires_global_egress=True,
        supported_checks=("models",),
        supported_api_types=("image_generation", "image_edit", "chat_completions"),
        execution_modes=("sync", "sync_then_store", "batch_submit_poll"),
    ),
    "openai_compatible": ProviderDefinition(
        provider="openai_compatible",
        display_name="OpenAI Compatible Relay",
        requires_global_egress=True,
        supported_checks=("models",),
        supported_api_types=("image_generation", "image_edit", "chat_completions"),
        execution_modes=("sync", "sync_then_store", "async_submit_poll"),
    ),
    "volcengine": ProviderDefinition(
        provider="volcengine",
        display_name="Volcengine Ark",
        requires_global_egress=False,
        supported_checks=("models",),
        supported_api_types=("chat_completions", "image_generation", "video_generation"),
        execution_modes=("sync", "async_submit_poll"),
    ),
    "baidu": ProviderDefinition(
        provider="baidu",
        display_name="Baidu Image Processing",
        requires_global_egress=False,
        supported_checks=("oauth",),
        supported_api_types=("baidu_image_process",),
        execution_modes=("sync_then_store",),
    ),
    "kie": ProviderDefinition(
        provider="kie",
        display_name="KIE Market",
        requires_global_egress=False,
        supported_checks=("jobs",),
        supported_api_types=("market_image_to_image", "market_text_to_video"),
        execution_modes=("async_submit_poll", "callback"),
    ),
}


def list_providers(settings: Settings | None = None) -> list[ProviderInfo]:
    settings = settings or Settings()
    return [
        ProviderInfo(
            provider=item.provider,
            displayName=item.display_name,
            status="active",
            requiresGlobalEgress=item.requires_global_egress,
            envKeyConfigured=_has_env_key(settings, item.provider),
            supportedChecks=list(item.supported_checks),
            supportedApiTypes=list(item.supported_api_types),
            executionModes=list(item.execution_modes),
        )
        for item in PROVIDERS.values()
    ]


def _has_env_key(settings: Settings, provider: str) -> bool:
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "openai_compatible":
        return bool(settings.openai_compatible_api_key)
    if provider == "volcengine":
        return bool(settings.volcengine_api_key)
    if provider == "baidu":
        return bool(settings.baidu_api_key and settings.baidu_secret_key)
    if provider == "kie":
        return bool(settings.kie_api_key)
    return False


def _openai_check_url(settings: Settings, check: str, *, compatible: bool = False) -> str:
    base = (settings.openai_compatible_base_url if compatible and settings.openai_compatible_base_url else settings.openai_base_url).rstrip("/")
    if check == "models":
        return f"{base}/v1/models"
    raise ValueError(check)


def _check_url(settings: Settings, provider: str, check: str) -> str:
    if provider == "openai":
        return _openai_check_url(settings, check)
    if provider == "openai_compatible":
        return _openai_check_url(settings, check, compatible=True)
    if provider == "volcengine":
        return f"{settings.volcengine_base_url.rstrip('/')}/api/v3/models"
    if provider == "baidu":
        return f"{settings.baidu_base_url.rstrip('/')}/oauth/2.0/token"
    if provider == "kie":
        return f"{settings.kie_base_url.rstrip('/')}/api/v1/jobs/recordInfo"
    return ""


async def check_provider_egress(
    *,
    settings: Settings,
    provider: str,
    check: str,
    include_auth: bool,
    auth_material: dict[str, str | None] | None = None,
) -> EgressCheckResponse:
    normalized = provider.lower().strip()
    definition = PROVIDERS.get(normalized)
    if not definition:
        return EgressCheckResponse(
            success=False,
            provider=normalized,
            check=check,
            url="",
            errorCode=ERR_PROVIDER_NOT_SUPPORTED,
            message=f"Provider is not supported: {provider}",
            suggestion="Add the provider to vendor-api-ops before exposing it through backend.",
        )
    if check not in definition.supported_checks:
        return EgressCheckResponse(
            success=False,
            provider=normalized,
            check=check,
            url="",
            errorCode=ERR_PROVIDER_NOT_SUPPORTED,
            message=f"Check is not supported for provider {provider}: {check}",
            suggestion=f"Use one of: {', '.join(definition.supported_checks)}",
        )

    url = _check_url(settings, normalized, check)
    headers: dict[str, str] = {}
    method = "GET"
    params: dict[str, Any] | None = None
    if include_auth:
        auth = auth_material or _select_auth_material(settings, normalized)
        if not auth.get("key"):
            return EgressCheckResponse(
                success=False,
                provider=normalized,
                check=check,
                url=url,
                errorCode=ERR_KEY_MISSING,
                message=f"{normalized} has no active API Key.",
                suggestion="Create an active key in the admin model ammo page, then retry the key check.",
            )
        if normalized == "baidu":
            if not auth.get("secret"):
                return EgressCheckResponse(
                    success=False,
                    provider=normalized,
                    check=check,
                    url=url,
                    errorCode=ERR_KEY_MISSING,
                    message="Baidu requires both API Key and Secret Key.",
                    suggestion="Edit the Baidu key by adding a new key with both API Key and Secret Key, then disable the old one.",
                )
            method = "POST"
            params = {
                "grant_type": "client_credentials",
                "client_id": auth["key"],
                "client_secret": auth["secret"],
            }
        else:
            headers["Authorization"] = f"Bearer {auth['key']}"
            if normalized == "kie":
                params = {"taskId": "__podi_key_check__"}

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
            response = await client.request(method, url, headers=headers, params=params)
    except httpx.ProxyError as exc:
        return _failed_response(
            provider=normalized,
            check=check,
            url=url,
            started=started,
            error_code=ERR_PROXY_UNAVAILABLE,
            message=str(exc),
            suggestion="Check HTTP_PROXY/HTTPS_PROXY or deploy vendor-api-ops on a host with direct egress.",
        )
    except httpx.TimeoutException as exc:
        return _failed_response(
            provider=normalized,
            check=check,
            url=url,
            started=started,
            error_code=ERR_TIMEOUT,
            message=str(exc) or "Request timed out",
            suggestion="Use a reachable proxy/global-egress node or increase timeout after verifying network.",
        )
    except httpx.HTTPError as exc:
        return _failed_response(
            provider=normalized,
            check=check,
            url=url,
            started=started,
            error_code=ERR_UPSTREAM_ERROR,
            message=str(exc),
            suggestion="Check DNS, firewall, proxy, and upstream provider availability.",
        )

    latency = int((time.perf_counter() - started) * 1000)
    reachable = _is_check_success(provider=normalized, include_auth=include_auth, status_code=response.status_code)
    error_code = None if reachable else (ERR_AUTH_FAILED if include_auth else ERR_UPSTREAM_ERROR)
    return EgressCheckResponse(
        success=reachable,
        provider=normalized,
        check=check,
        url=url,
        httpStatus=response.status_code,
        latencyMs=latency,
        errorCode=error_code,
        message=("authenticated" if include_auth else "reachable") if reachable else response.text[:300],
        suggestion=None
        if reachable
        else (
            "Key check failed. Verify the key value, secret, quota, and provider account status."
            if include_auth
            else "Upstream returned a server error; retry or check provider status."
        ),
    )


def _select_auth_material(settings: Settings, provider: str) -> dict[str, str | None]:
    stored = vendor_storage.pick_key(provider=provider)
    if stored and stored.get("key"):
        return {"key": str(stored.get("key") or ""), "secret": stored.get("secret")}
    if provider == "openai":
        return {"key": settings.openai_api_key, "secret": None}
    if provider == "openai_compatible":
        return {"key": settings.openai_compatible_api_key, "secret": None}
    if provider == "volcengine":
        return {"key": settings.volcengine_api_key, "secret": None}
    if provider == "kie":
        return {"key": settings.kie_api_key, "secret": None}
    if provider == "baidu":
        return {"key": settings.baidu_api_key, "secret": settings.baidu_secret_key}
    return {"key": None, "secret": None}


def _is_check_success(*, provider: str, include_auth: bool, status_code: int) -> bool:
    if not include_auth:
        return status_code < 500
    if provider == "kie":
        # KIE recordInfo may return a business-level "task not found" for the
        # fake check task. That still proves auth reached the upstream service.
        return status_code < 500 and status_code not in {401, 403}
    return 200 <= status_code < 300


def _failed_response(
    *,
    provider: str,
    check: str,
    url: str,
    started: float,
    error_code: str,
    message: str,
    suggestion: str,
) -> EgressCheckResponse:
    return EgressCheckResponse(
        success=False,
        provider=provider,
        check=check,
        url=url,
        latencyMs=int((time.perf_counter() - started) * 1000),
        errorCode=error_code,
        message=message,
        suggestion=suggestion,
    )
