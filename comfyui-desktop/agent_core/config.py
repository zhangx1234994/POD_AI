"""Local config persistence for desktop agent."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import DesktopConfig, JwtKey


def get_home_dir() -> Path:
    raw = os.environ.get("COMFYUI_DESKTOP_HOME", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".podi" / "comfyui-desktop").resolve()


def _default_center_url() -> str:
    return os.environ.get("PODI_DESKTOP_CENTER_URL", "").strip()


def _default_install_key() -> str:
    return os.environ.get("PODI_DESKTOP_INSTALL_KEY", "").strip()


def get_config_path() -> Path:
    return get_home_dir() / "config.json"


def get_state_db_path() -> Path:
    return get_home_dir() / "state.db"


def get_logs_dir() -> Path:
    return get_home_dir() / "logs"


def ensure_runtime_dirs() -> None:
    home = get_home_dir()
    logs = get_logs_dir()
    home.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)


def _decode_jwt_keys(raw: Any) -> list[JwtKey]:
    if not isinstance(raw, list):
        return []
    rows: list[JwtKey] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kid = str(item.get("kid") or "").strip()
        secret = str(item.get("secret") or "").strip()
        if not kid or not secret:
            continue
        rows.append(JwtKey(kid=kid, secret=secret, status=str(item.get("status") or "active")))
    return rows


def load_config() -> DesktopConfig:
    ensure_runtime_dirs()
    path = get_config_path()
    if not path.exists():
        return DesktopConfig(
            center_url=_default_center_url(),
            install_key=_default_install_key(),
            auto_bootstrap=True,
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    cfg = DesktopConfig(
        center_url=str(raw.get("center_url") or _default_center_url() or "").strip(),
        install_key=str(raw.get("install_key") or _default_install_key() or "").strip(),
        auto_bootstrap=bool(raw.get("auto_bootstrap", True)),
        agent_id=str(raw.get("agent_id") or "").strip(),
        agent_token=str(raw.get("agent_token") or "").strip(),
        jwt_keys=_decode_jwt_keys(raw.get("jwt_keys")),
        comfyui_path=str(raw.get("comfyui_path") or "").strip(),
        comfyui_port=int(raw.get("comfyui_port") or 8079),
        agent_port=int(raw.get("agent_port") or 18079),
        heartbeat_interval_sec=max(10, int(raw.get("heartbeat_interval_sec") or 60)),
        auto_update=bool(raw.get("auto_update", True)),
        log_level=str(raw.get("log_level") or "INFO").upper(),
    )
    return cfg


def save_config(config: DesktopConfig) -> None:
    ensure_runtime_dirs()
    path = get_config_path()
    payload = asdict(config)
    payload["jwt_keys"] = [asdict(item) for item in config.jwt_keys]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
