"""Shared models for desktop agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class JwtKey:
    kid: str
    secret: str
    status: str = "active"


@dataclass
class DesktopConfig:
    center_url: str = ""
    install_key: str = ""
    auto_bootstrap: bool = True
    agent_id: str = ""
    agent_token: str = ""
    jwt_keys: list[JwtKey] = field(default_factory=list)
    comfyui_path: str = ""
    comfyui_port: int = 8079
    agent_port: int = 18079
    heartbeat_interval_sec: int = 60
    auto_update: bool = True
    log_level: str = "INFO"


@dataclass
class RuntimeTaskResult:
    task_id: str
    status: str
    started_at: datetime
    finished_at: datetime
    message: str | None = None
    payload: dict[str, Any] | None = None
