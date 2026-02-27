"""HTTP client for center APIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from urllib.parse import urlencode


@dataclass
class CenterClient:
    center_url: str
    timeout: int = 20

    def _url(self, path: str) -> str:
        return f"{self.center_url.rstrip('/')}{path}"

    def bootstrap_exchange(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(self._url("/api/agent/bootstrap/exchange"), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def bootstrap_auto_exchange(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(self._url("/api/agent/bootstrap/auto-exchange"), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def bootstrap_refresh_keys(self, agent_token: str) -> dict[str, Any]:
        resp = httpx.post(
            self._url("/api/agent/bootstrap/refresh-keys"),
            headers={"Authorization": f"Bearer {agent_token}"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def list_desktop_releases(
        self,
        agent_token: str,
        *,
        channel: str = "stable",
        os_type: str = "windows",
        arch: str = "x64",
        status: str = "active",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query = urlencode(
            {
                "channel": channel,
                "os_type": os_type,
                "arch": arch,
                "status": status,
                "limit": max(1, min(100, int(limit))),
            }
        )
        resp = httpx.get(
            self._url(f"/api/agent/bootstrap/releases?{query}"),
            headers={"Authorization": f"Bearer {agent_token}"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def verify_task_token(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(self._url("/api/agent/auth/verify"), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def fetch_manifest(self, manifest_url: str, token: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {token}",
            "x-task-token": token,
        }
        resp = httpx.get(manifest_url, headers=headers, timeout=max(self.timeout, 60))
        resp.raise_for_status()
        return resp.json()

    def report_event(self, task_id: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(
            self._url(f"/api/agent/tasks/{task_id}/events"),
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def report_complete(self, task_id: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(
            self._url(f"/api/agent/tasks/{task_id}/complete"),
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def report_failed(self, task_id: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(
            self._url(f"/api/agent/tasks/{task_id}/failed"),
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def heartbeat(self, agent_id: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(
            self._url(f"/api/agent/agents/{agent_id}/heartbeat"),
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def alert(self, agent_id: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(
            self._url(f"/api/agent/agents/{agent_id}/alerts"),
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()
