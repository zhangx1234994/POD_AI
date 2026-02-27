"""Runtime container for agent server and GUI."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import socket
import subprocess
import threading
from dataclasses import dataclass
from typing import Any

import httpx

from .center_client import CenterClient
from .config import get_home_dir, get_state_db_path, load_config, save_config
from .health_check import run_health_check
from .models import DesktopConfig, JwtKey
from .state_store import StateStore
from .task_engine import TaskEngine


DESKTOP_AGENT_VERSION = os.environ.get("PODI_DESKTOP_VERSION", "0.1.0").strip() or "0.1.0"
AUTO_APPLY_UPDATES = os.environ.get("PODI_DESKTOP_AUTO_APPLY", "false").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class AgentRuntime:
    config: DesktopConfig
    store: StateStore
    client: CenterClient
    engine: TaskEngine
    _heartbeat_stop: threading.Event
    _heartbeat_thread: threading.Thread | None = None
    _heartbeat_tick: int = 0

    @classmethod
    def create(cls) -> "AgentRuntime":
        config = load_config()
        store = StateStore(get_state_db_path())
        client = CenterClient(center_url=config.center_url or "http://127.0.0.1:8099")
        engine = TaskEngine(config=config, store=store, client=client)
        return cls(
            config=config,
            store=store,
            client=client,
            engine=engine,
            _heartbeat_stop=threading.Event(),
        )

    def update_config(self, config: DesktopConfig) -> None:
        self.config = config
        self.client = CenterClient(center_url=config.center_url or "http://127.0.0.1:8099")
        self.engine = TaskEngine(config=config, store=self.store, client=self.client)
        save_config(config)

    def try_auto_bootstrap(self) -> dict[str, Any] | None:
        if self.config.agent_id and self.config.agent_token:
            return None
        if not self.config.auto_bootstrap:
            return None
        center = (self.config.center_url or "").strip()
        install_key = (self.config.install_key or "").strip()
        if not center or not install_key:
            return None
        payload = {
            "installKey": install_key,
            "machineName": socket.gethostname(),
            "host": self._detect_host_ip(),
            "baseUrl": self._detect_base_url(),
            "role": "full",
            "agentVersion": f"desktop-{DESKTOP_AGENT_VERSION}",
        }
        response = self.client.bootstrap_auto_exchange(payload)
        keys = []
        for item in response.get("jwtKeys") or []:
            if not isinstance(item, dict):
                continue
            kid = str(item.get("kid") or "").strip()
            secret = str(item.get("secret") or "").strip()
            if kid and secret:
                keys.append(JwtKey(kid=kid, secret=secret, status=str(item.get("status") or "active")))
        updated = DesktopConfig(
            center_url=str(response.get("centerUrl") or center),
            install_key=install_key,
            auto_bootstrap=self.config.auto_bootstrap,
            agent_id=str(response.get("agentId") or "").strip(),
            agent_token=str(response.get("agentToken") or "").strip(),
            jwt_keys=keys or self.config.jwt_keys,
            comfyui_path=self.config.comfyui_path,
            comfyui_port=self.config.comfyui_port,
            agent_port=self.config.agent_port,
            heartbeat_interval_sec=max(
                10,
                int(response.get("heartbeatIntervalSec") or self.config.heartbeat_interval_sec or 60),
            ),
            auto_update=self.config.auto_update,
            log_level=self.config.log_level,
        )
        self.update_config(updated)
        return response

    def bootstrap(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.bootstrap_exchange(payload)
        keys = []
        for item in response.get("jwtKeys") or []:
            if not isinstance(item, dict):
                continue
            kid = str(item.get("kid") or "").strip()
            secret = str(item.get("secret") or "").strip()
            if kid and secret:
                keys.append(JwtKey(kid=kid, secret=secret, status=str(item.get("status") or "active")))
        updated = DesktopConfig(
            center_url=str(response.get("centerUrl") or self.config.center_url or "").strip(),
            install_key=self.config.install_key,
            auto_bootstrap=self.config.auto_bootstrap,
            agent_id=str(response.get("agentId") or self.config.agent_id or "").strip(),
            agent_token=str(response.get("agentToken") or "").strip(),
            jwt_keys=keys or self.config.jwt_keys,
            comfyui_path=self.config.comfyui_path,
            comfyui_port=self.config.comfyui_port,
            agent_port=self.config.agent_port,
            heartbeat_interval_sec=max(
                10,
                int(response.get("heartbeatIntervalSec") or self.config.heartbeat_interval_sec or 60),
            ),
            auto_update=self.config.auto_update,
            log_level=self.config.log_level,
        )
        self.update_config(updated)
        return response

    def refresh_keys(self) -> dict[str, Any]:
        response = self.client.bootstrap_refresh_keys(self.config.agent_token)
        keys = []
        for item in response.get("jwtKeys") or []:
            if not isinstance(item, dict):
                continue
            kid = str(item.get("kid") or "").strip()
            secret = str(item.get("secret") or "").strip()
            if kid and secret:
                keys.append(JwtKey(kid=kid, secret=secret, status=str(item.get("status") or "active")))
        if keys:
            self.config.jwt_keys = keys
            save_config(self.config)
        return response

    def check_health(self) -> dict[str, Any]:
        return run_health_check(comfyui_path=self.config.comfyui_path, comfyui_port=self.config.comfyui_port)

    def start_heartbeat(self) -> None:
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_tick = 0
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=3)

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.is_set():
            self._heartbeat_tick += 1
            if self.config.agent_id and self.config.agent_token and self.config.center_url:
                payload = {
                    "status": "active",
                    "metrics": {
                        "host": socket.gethostname(),
                    },
                    "agentVersion": f"desktop-{DESKTOP_AGENT_VERSION}",
                    "payload": self._build_heartbeat_payload(),
                }
                try:
                    self.client.heartbeat(self.config.agent_id, self.config.agent_token, payload)
                except Exception:
                    pass
                if self.config.auto_update and (self._heartbeat_tick == 1 or self._heartbeat_tick % 10 == 0):
                    try:
                        checked = self.check_desktop_update(force=False)
                        if AUTO_APPLY_UPDATES and checked.get("status") == "update_available":
                            current_state = self.store.get_update_state() or {}
                            if current_state.get("status") not in {"apply_started", "applying"}:
                                self.apply_desktop_update(force=False)
                    except Exception:
                        pass
            self._heartbeat_stop.wait(timeout=max(10, int(self.config.heartbeat_interval_sec or 60)))

    def execute_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.engine.execute(payload)

    def get_status(self) -> dict[str, Any]:
        health = self.check_health()
        update_state = self.store.get_update_state()
        return {
            "agentId": self.config.agent_id,
            "centerUrl": self.config.center_url,
            "agentPort": self.config.agent_port,
            "heartbeatIntervalSec": self.config.heartbeat_interval_sec,
            "agentVersion": DESKTOP_AGENT_VERSION,
            "health": health,
            "updateState": update_state,
            "taskCount": len(self.store.list_tasks(limit=500)),
        }

    def check_desktop_update(self, *, force: bool = True) -> dict[str, Any]:
        current = DESKTOP_AGENT_VERSION
        if not self.config.auto_update and not force:
            state = {
                "current_version": current,
                "target_version": None,
                "status": "disabled",
                "payload": {"reason": "auto_update_disabled"},
            }
            self.store.set_update_state(**state)
            return state
        if not self.config.agent_token or not self.config.center_url:
            state = {
                "current_version": current,
                "target_version": None,
                "status": "not_ready",
                "payload": {"reason": "agent_not_bootstrapped"},
            }
            self.store.set_update_state(**state)
            return state
        try:
            releases = self.client.list_desktop_releases(
                self.config.agent_token,
                channel="stable",
                os_type="windows",
                arch="x64",
                status="active",
                limit=20,
            )
        except Exception as exc:
            state = {
                "current_version": current,
                "target_version": None,
                "status": "check_failed",
                "payload": {"error": str(exc)},
            }
            self.store.set_update_state(**state)
            return state
        if not releases:
            state = {
                "current_version": current,
                "target_version": None,
                "status": "no_release",
                "payload": {"count": 0},
            }
            self.store.set_update_state(**state)
            return state

        latest = self._pick_latest_release(releases)
        target = str(latest.get("version") or "").strip() or None
        previous = self.store.get_update_state() or {}
        cmp = self._compare_versions(target or "", current)
        status = "update_available" if cmp > 0 else "up_to_date"
        if cmp <= 0 and previous.get("status") in {"apply_started", "applying"} and target:
            if self._compare_versions(current, target) >= 0:
                status = "applied"
        state = {
            "current_version": current,
            "target_version": target,
            "status": status,
            "payload": {
                "release": latest,
                "count": len(releases),
            },
        }
        self.store.set_update_state(**state)
        return state

    def apply_desktop_update(self, *, force: bool = True) -> dict[str, Any]:
        checked = self.check_desktop_update(force=force)
        status = str(checked.get("status") or "")
        if status != "update_available":
            return checked
        if self._is_task_running():
            blocked = {
                "current_version": checked.get("current_version") or DESKTOP_AGENT_VERSION,
                "target_version": checked.get("target_version"),
                "status": "apply_blocked_running_task",
                "payload": {"reason": "task_running"},
            }
            self.store.set_update_state(**blocked)
            return blocked
        if not self._is_windows():
            unsupported = {
                "current_version": checked.get("current_version") or DESKTOP_AGENT_VERSION,
                "target_version": checked.get("target_version"),
                "status": "apply_not_supported",
                "payload": {"reason": "windows_only"},
            }
            self.store.set_update_state(**unsupported)
            return unsupported

        payload = checked.get("payload") if isinstance(checked.get("payload"), dict) else {}
        release = payload.get("release") if isinstance(payload, dict) else None
        if not isinstance(release, dict):
            invalid = {
                "current_version": checked.get("current_version") or DESKTOP_AGENT_VERSION,
                "target_version": checked.get("target_version"),
                "status": "apply_failed",
                "payload": {"reason": "release_missing"},
            }
            self.store.set_update_state(**invalid)
            return invalid

        download_url = str(release.get("downloadUrl") or "").strip()
        sha256 = str(release.get("sha256") or "").strip().lower()
        target_version = str(release.get("version") or checked.get("target_version") or "").strip()
        if not download_url or not sha256:
            invalid = {
                "current_version": checked.get("current_version") or DESKTOP_AGENT_VERSION,
                "target_version": target_version or None,
                "status": "apply_failed",
                "payload": {"reason": "release_fields_missing", "required": ["downloadUrl", "sha256"]},
            }
            self.store.set_update_state(**invalid)
            return invalid

        try:
            installer_path = self._download_update_installer(download_url, target_version)
            actual = self._sha256(installer_path)
            if actual != sha256:
                raise RuntimeError(f"sha256 mismatch: expected {sha256}, got {actual}")
            launch = self._launch_installer(installer_path)
            started = {
                "current_version": checked.get("current_version") or DESKTOP_AGENT_VERSION,
                "target_version": target_version or None,
                "status": "apply_started",
                "payload": {
                    "release": release,
                    "installer_path": str(installer_path),
                    "launcher": launch,
                },
            }
            self.store.set_update_state(**started)
            return started
        except Exception as exc:
            failed = {
                "current_version": checked.get("current_version") or DESKTOP_AGENT_VERSION,
                "target_version": target_version or None,
                "status": "apply_failed",
                "payload": {"error": str(exc), "release": release},
            }
            self.store.set_update_state(**failed)
            return failed

    @staticmethod
    def _pick_latest_release(releases: list[dict[str, Any]]) -> dict[str, Any]:
        def _release_sort_key(item: dict[str, Any]) -> tuple[str, tuple[int, ...], int]:
            published = str(item.get("publishedAt") or item.get("updatedAt") or item.get("createdAt") or "")
            version = str(item.get("version") or "")
            rid = int(item.get("id") or 0)
            return (published, AgentRuntime._version_key(version), rid)

        ranked = sorted(releases, key=_release_sort_key, reverse=True)
        return ranked[0]

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        numbers = [int(part) for part in re.findall(r"\d+", version or "")]
        if not numbers:
            return (0,)
        return tuple(numbers)

    @staticmethod
    def _compare_versions(left: str, right: str) -> int:
        l_key = AgentRuntime._version_key(left)
        r_key = AgentRuntime._version_key(right)
        length = max(len(l_key), len(r_key))
        for idx in range(length):
            lv = l_key[idx] if idx < len(l_key) else 0
            rv = r_key[idx] if idx < len(r_key) else 0
            if lv > rv:
                return 1
            if lv < rv:
                return -1
        if (left or "") > (right or ""):
            return 1
        if (left or "") < (right or ""):
            return -1
        return 0

    def _download_update_installer(self, download_url: str, target_version: str) -> Path:
        updates_dir = get_home_dir() / "updates"
        updates_dir.mkdir(parents=True, exist_ok=True)
        normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", target_version or "latest")
        installer_path = updates_dir / f"podi-agent-{normalized}.exe"
        temp_path = installer_path.with_suffix(".download")
        with httpx.stream("GET", download_url, timeout=600) as response:
            response.raise_for_status()
            with temp_path.open("wb") as handle:
                for chunk in response.iter_bytes():
                    if chunk:
                        handle.write(chunk)
        temp_path.replace(installer_path)
        return installer_path

    def _launch_installer(self, installer_path: Path) -> dict[str, Any]:
        script_path = installer_path.with_suffix(".apply.ps1")
        escaped_installer = str(installer_path).replace("'", "''")
        script_body = "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$installer = '{escaped_installer}'",
                "if (-not (Test-Path $installer)) { throw 'installer_not_found' }",
                "Start-Process -FilePath $installer -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' -Verb RunAs -Wait",
                "exit 0",
            ]
        )
        script_path.write_text(script_body + "\n", encoding="utf-8")
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ]
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603,S607
        return {
            "script_path": str(script_path),
            "command": command,
        }

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest().lower()

    def _is_task_running(self) -> bool:
        return bool(getattr(self.engine, "_running_task_id", None))

    def _build_heartbeat_payload(self) -> dict[str, Any]:
        update_state = self.store.get_update_state() or {}
        payload = update_state.get("payload") if isinstance(update_state.get("payload"), dict) else {}
        error_message = (
            payload.get("error")
            or payload.get("message")
            or payload.get("reason")
            or update_state.get("error")
            or update_state.get("message")
        )
        update_summary = {
            "status": update_state.get("status"),
            "currentVersion": update_state.get("current_version"),
            "targetVersion": update_state.get("target_version"),
            "updatedAt": update_state.get("updated_at"),
            "error": str(error_message).strip() if error_message else None,
        }
        return {
            "runtime": {
                "desktopVersion": DESKTOP_AGENT_VERSION,
                "autoApplyEnabled": AUTO_APPLY_UPDATES,
            },
            "updateState": update_summary,
        }

    @staticmethod
    def _is_windows() -> bool:
        return os.name == "nt"

    def _detect_host_ip(self) -> str:
        try:
            host = socket.gethostbyname(socket.gethostname())
            if host and host != "127.0.0.1":
                return host
        except Exception:
            pass
        return "127.0.0.1"

    def _detect_base_url(self) -> str:
        host_ip = self._detect_host_ip()
        return f"http://{host_ip}:{int(self.config.agent_port)}"
