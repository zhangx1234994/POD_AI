"""Provider registry and network checks."""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.schemas import EgressCheckResponse, ProviderInfo


ERR_PROVIDER_NOT_SUPPORTED = "VENDOR_API_PROVIDER_NOT_SUPPORTED"
ERR_PROXY_UNAVAILABLE = "VENDOR_API_PROXY_UNAVAILABLE"
ERR_TIMEOUT = "VENDOR_API_TIMEOUT"
ERR_UPSTREAM_ERROR = "VENDOR_API_UPSTREAM_ERROR"


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
        execution_modes=("sync", "sync_then_store"),
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


def list_providers() -> list[ProviderInfo]:
    return [
        ProviderInfo(
            provider=item.provider,
            displayName=item.display_name,
            status="active",
            requiresGlobalEgress=item.requires_global_egress,
            supportedChecks=list(item.supported_checks),
            supportedApiTypes=list(item.supported_api_types),
            executionModes=list(item.execution_modes),
        )
        for item in PROVIDERS.values()
    ]


def _openai_check_url(settings: Settings, check: str) -> str:
    base = settings.openai_base_url.rstrip("/")
    if check == "models":
        return f"{base}/v1/models"
    raise ValueError(check)


def _check_url(settings: Settings, provider: str, check: str) -> str:
    if provider in {"openai", "openai_compatible"}:
        return _openai_check_url(settings, check)
    if provider == "volcengine":
        return "https://ark.cn-beijing.volces.com/api/v3/models"
    if provider == "baidu":
        return "https://aip.baidubce.com/oauth/2.0/token"
    if provider == "kie":
        return "https://api.kie.ai/api/v1/jobs/recordInfo"
    return ""


async def check_provider_egress(
    *,
    settings: Settings,
    provider: str,
    check: str,
    include_auth: bool,
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
    if include_auth and normalized == "openai" and settings.openai_api_key:
        headers["Authorization"] = f"Bearer {settings.openai_api_key}"

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
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
    reachable = response.status_code < 500
    return EgressCheckResponse(
        success=reachable,
        provider=normalized,
        check=check,
        url=url,
        httpStatus=response.status_code,
        latencyMs=latency,
        errorCode=None if reachable else ERR_UPSTREAM_ERROR,
        message="reachable" if reachable else response.text[:300],
        suggestion=None if reachable else "Upstream returned a server error; retry or check provider status.",
    )


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
