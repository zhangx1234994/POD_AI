#!/usr/bin/env python3
"""Small release smoke check for the backend business chain.

Run this on the backend/Coze host after restart. It intentionally calls
internal Coze toolbox endpoints, so running it from an untrusted external host
should fail with INTERNAL_ONLY.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import httpx


def _short(value: Any, limit: int = 500) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split())[:limit]


def _result(name: str, ok: bool, detail: str) -> dict[str, Any]:
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {name}: {detail}")
    return {"name": name, "ok": ok, "detail": detail}


def _get_json(client: httpx.Client, path: str) -> tuple[int, Any]:
    response = client.get(path)
    try:
        data = response.json()
    except Exception:
        data = {"text": response.text}
    return response.status_code, data


def _post_json(client: httpx.Client, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
    response = client.post(path, json=payload)
    try:
        data = response.json()
    except Exception:
        data = {"text": response.text}
    return response.status_code, data


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PODI backend release smoke checks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8099")
    parser.add_argument("--expect-server-url", default="", help="Optional OpenAPI servers[0].url expectation.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary at the end.")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    timeout = httpx.Timeout(20.0, connect=5.0)
    checks: list[dict[str, Any]] = []

    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        try:
            status, data = _get_json(client, "/health")
            checks.append(_result("health", status == 200 and data.get("status") == "ok", f"status={status} body={data}"))
        except Exception as exc:
            checks.append(_result("health", False, repr(exc)))

        try:
            status, data = _get_json(client, "/api/coze/podi/openapi.json")
            openapi = data if isinstance(data, dict) else {}
            server_url = ""
            servers = openapi.get("servers") if isinstance(openapi.get("servers"), list) else []
            if servers and isinstance(servers[0], dict):
                server_url = str(servers[0].get("url") or "")
            expected = args.expect_server_url.strip()
            ok = status == 200 and bool(server_url) and (not expected or server_url == expected)
            detail = f"status={status} server={server_url or '-'}"
            if expected:
                detail += f" expected={expected}"
            checks.append(_result("coze_openapi", ok, detail))
        except Exception as exc:
            checks.append(_result("coze_openapi", False, repr(exc)))

        try:
            status, data = _post_json(client, "/api/coze/podi/tasks/get", {"taskId": "__release_smoke_not_found__"})
            detail = data.get("detail") if isinstance(data, dict) else data
            checks.append(_result("internal_tasks_get", status == 404 and detail == "TASK_NOT_FOUND", f"status={status} detail={detail}"))
        except Exception as exc:
            checks.append(_result("internal_tasks_get", False, repr(exc)))

        try:
            status, data = _post_json(client, "/api/coze/podi/comfyui/queue-summary", {})
            servers = data.get("servers") if isinstance(data, dict) else None
            ok = status == 200 and isinstance(servers, list) and len(servers) > 0
            detail = f"status={status} servers={len(servers) if isinstance(servers, list) else 0}"
            if isinstance(data, dict) and data.get("error"):
                detail += f" error={_short(data.get('error'))}"
            checks.append(_result("comfyui_queue_summary", ok, detail))
        except Exception as exc:
            checks.append(_result("comfyui_queue_summary", False, repr(exc)))

    ok = all(item.get("ok") for item in checks)
    summary = {"baseUrl": base_url, "ok": ok, "checks": checks}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
