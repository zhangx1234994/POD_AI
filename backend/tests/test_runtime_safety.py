from __future__ import annotations

from app.core.config import get_settings
from app.services import runtime_safety


def test_background_workers_auto_disabled_on_macos_remote_db(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://user:pass@example.mysql.rds.aliyuncs.com:3306/podi")
    monkeypatch.setenv("BACKGROUND_WORKERS_ENABLED", "auto")
    monkeypatch.setattr(runtime_safety.platform, "system", lambda: "Darwin")
    try:
        decision = runtime_safety.get_background_worker_decision()
    finally:
        get_settings.cache_clear()

    assert decision.enabled is False
    assert "macOS" in decision.reason


def test_background_workers_auto_enabled_on_linux_remote_db(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://user:pass@example.mysql.rds.aliyuncs.com:3306/podi")
    monkeypatch.setenv("BACKGROUND_WORKERS_ENABLED", "auto")
    monkeypatch.setattr(runtime_safety.platform, "system", lambda: "Linux")
    try:
        decision = runtime_safety.get_background_worker_decision()
    finally:
        get_settings.cache_clear()

    assert decision.enabled is True


def test_background_workers_explicit_flag_overrides_auto(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://user:pass@example.mysql.rds.aliyuncs.com:3306/podi")
    monkeypatch.setenv("BACKGROUND_WORKERS_ENABLED", "true")
    monkeypatch.setattr(runtime_safety.platform, "system", lambda: "Darwin")
    try:
        decision = runtime_safety.get_background_worker_decision()
    finally:
        get_settings.cache_clear()

    assert decision.enabled is True
    assert "BACKGROUND_WORKERS_ENABLED=true" in decision.reason
