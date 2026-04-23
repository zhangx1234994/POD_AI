#!/usr/bin/env python3
"""Check Coze control-plane migration readiness / post-cutover state.

Usage:
  python3 backend/scripts/check_coze_control_plane_migration.py \
    --backend-base http://127.0.0.1:8099 \
    --admin-base http://127.0.0.1:8199 \
    --eval-base http://127.0.0.1:8200

This script is intentionally read-only. It verifies:
- backend control-plane endpoints are healthy
- Coze OpenAPI documents resolve on backend host
- OpenAPI documents do not leak direct ComfyUI/host.docker.internal addresses
- optional admin/eval frontends are running build artifacts rather than Vite dev server
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _get_json(base: str, path: str) -> dict[str, Any]:
    resp = httpx.get(f"{base.rstrip('/')}{path}", timeout=20)
    resp.raise_for_status()
    data = resp.json()
    _expect(isinstance(data, dict), f"{path} did not return JSON object")
    return data


def _get_text(base: str, path: str = "/") -> str:
    resp = httpx.get(f"{base.rstrip('/')}{path}", timeout=20)
    resp.raise_for_status()
    return resp.text


def _check_openapi(base: str, path: str, *, label: str) -> None:
    data = _get_json(base, path)
    paths = data.get("paths") or {}
    _expect(isinstance(paths, dict) and paths, f"{label} missing paths")
    _expect("/api/coze/podi/tasks/get" in paths, f"{label} missing /api/coze/podi/tasks/get")
    serialized = json.dumps(data, ensure_ascii=False)
    _expect(":8079" not in serialized, f"{label} leaked direct ComfyUI executor URL")
    _expect("host.docker.internal" not in serialized, f"{label} leaked host.docker.internal")


def _check_frontend_build(base: str, *, label: str) -> None:
    html = _get_text(base, "/")
    _expect("@vite/client" not in html, f"{label} is still running Vite dev server")
    _expect("/src/main.tsx" not in html, f"{label} is still serving source entrypoint")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-base", default="http://127.0.0.1:8099")
    parser.add_argument("--admin-base", default="")
    parser.add_argument("--eval-base", default="")
    args = parser.parse_args()

    print("[1] backend health")
    health = _get_json(args.backend_base, "/health")
    _expect(health.get("status") == "ok", "backend /health is not ok")

    print("[2] backend control-plane endpoints")
    _get_json(args.backend_base, "/api/abilities")
    _get_json(args.backend_base, "/api/evals/workflow-versions")

    print("[3] coze openapi documents")
    _check_openapi(args.backend_base, "/api/coze/podi/openapi.json", label="plugin openapi")
    _check_openapi(args.backend_base, "/api/coze/podi/comfyui/openapi.json", label="comfyui openapi")

    if args.admin_base:
        print("[4] admin build artifact check")
        _check_frontend_build(args.admin_base, label="admin web")
    if args.eval_base:
        print("[5] eval build artifact check")
        _check_frontend_build(args.eval_base, label="eval web")

    print("All Coze control-plane checks passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"CHECK_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
