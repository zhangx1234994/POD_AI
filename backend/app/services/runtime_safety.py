"""Runtime safety guards for background consumers."""

from __future__ import annotations

import logging
import os
import platform
from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackgroundWorkerDecision:
    enabled: bool
    reason: str


def _truthy_or_falsy(value: object) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return None


def suppress_background_threads_for_tests() -> bool:
    """Disable passive polling loops in pytest without changing runtime worker semantics."""
    return _truthy_or_falsy(os.getenv("PODI_TEST_DISABLE_BACKGROUND_THREADS")) is True


def _database_host(database_url: str) -> str:
    try:
        parsed = urlparse(database_url)
    except Exception:
        return ""
    return (parsed.hostname or "").strip().lower()


def _is_remote_database(database_url: str) -> bool:
    host = _database_host(database_url)
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    if host.endswith(".local"):
        return False
    return True


def get_background_worker_decision() -> BackgroundWorkerDecision:
    settings = get_settings()
    configured = _truthy_or_falsy(settings.background_workers_enabled)
    if configured is not None:
        return BackgroundWorkerDecision(
            enabled=configured,
            reason=f"BACKGROUND_WORKERS_ENABLED={str(settings.background_workers_enabled).strip()}",
        )

    if platform.system().lower() == "darwin" and _is_remote_database(settings.database_url):
        return BackgroundWorkerDecision(
            enabled=False,
            reason="auto disabled on macOS with a remote database; prevents local dev from consuming production queues",
        )

    return BackgroundWorkerDecision(enabled=True, reason="auto enabled for server/runtime host")


def log_background_worker_decision(service_name: str) -> BackgroundWorkerDecision:
    decision = get_background_worker_decision()
    if decision.enabled:
        logger.info("%s background workers enabled: %s", service_name, decision.reason)
    else:
        logger.warning("%s background workers disabled: %s", service_name, decision.reason)
    return decision
