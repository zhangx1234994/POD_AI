"""Helpers for trusted internal service calls."""

from __future__ import annotations

import ipaddress
from typing import Iterable

from fastapi import Request

from app.core.config import get_settings


def _csv_values(value: str | None) -> set[str]:
    return {item.strip() for item in (value or "").split(",") if item.strip()}


def _normalize_ip(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if text.startswith("[") and "]" in text:
        return text[1 : text.index("]")]
    if text.count(":") == 1 and "." in text:
        return text.split(":", 1)[0].strip()
    return text


def _is_loopback_or_private(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(_normalize_ip(host))
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def _is_trusted(host: str, trusted_hosts: Iterable[str]) -> bool:
    normalized = _normalize_ip(host)
    normalized_trusted = {_normalize_ip(item) for item in trusted_hosts}
    return bool(normalized and normalized in normalized_trusted)


def is_internal_request(request: Request) -> bool:
    """Return whether a request should be treated as a trusted service call.

    Proxy headers are only honored when the direct peer is already trusted.
    Otherwise a public caller could spoof X-Forwarded-For and bypass internal
    API protection.
    """

    settings = get_settings()
    trusted_hosts = _csv_values(settings.coze_trusted_ips)
    direct_host = _normalize_ip(request.client.host if request.client else "")
    if _is_loopback_or_private(direct_host) or _is_trusted(direct_host, trusted_hosts):
        forwarded_for = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        real_ip = (request.headers.get("x-real-ip") or "").strip()
        proxy_host = _normalize_ip(forwarded_for or real_ip)
        if proxy_host:
            return _is_loopback_or_private(proxy_host) or _is_trusted(proxy_host, trusted_hosts)
        return True
    return False
