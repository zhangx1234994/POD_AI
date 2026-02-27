"""Health check helpers for desktop agent."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import httpx


def run_health_check(*, comfyui_path: str, comfyui_port: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    path = Path(comfyui_path).expanduser()
    checks.append(
        {
            "name": "comfyui_path_exists",
            "ok": path.exists(),
            "detail": str(path),
        }
    )
    checks.append(
        {
            "name": "git_installed",
            "ok": shutil.which("git") is not None,
            "detail": shutil.which("git") or "missing",
        }
    )
    checks.append(
        {
            "name": "python_installed",
            "ok": shutil.which("python") is not None or shutil.which("python3") is not None,
            "detail": shutil.which("python") or shutil.which("python3") or "missing",
        }
    )
    url = f"http://127.0.0.1:{int(comfyui_port)}/"
    try:
        resp = httpx.get(url, timeout=5)
        checks.append(
            {
                "name": "comfyui_http",
                "ok": resp.status_code < 500,
                "detail": f"status={resp.status_code}",
            }
        )
    except Exception as exc:
        checks.append(
            {
                "name": "comfyui_http",
                "ok": False,
                "detail": str(exc),
            }
        )
    ok = all(bool(item.get("ok")) for item in checks)
    return {"ok": ok, "checks": checks}
