#!/usr/bin/env python3
"""Check the 117 image-ops cutover path before and after switching backend.

Phases:
- pre: current safe state before 117 is updated.
- post-117: 117 has image-ops running on the reused port, but Coze backend is not switched yet.
- post-coze: Coze backend has IMAGE_OPS_BASE_URL pointed to 117 image-ops.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


MINIMAL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8B9l8AAAAASUVORK5CYII="
)


def load_env(path: str) -> dict[str, str]:
    env: dict[str, str] = {}
    p = Path(path)
    if not p.is_file():
        return env
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def http_json(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: int = 30,
) -> tuple[int, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if payload is not None else "GET")
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}
    try:
        return status, json.loads(body) if body else {}
    except Exception:
        return status, {"raw": body[:500]}


def expect(condition: bool, message: str, failures: list[str]) -> None:
    label = "OK" if condition else "FAIL"
    print(f"[{label}] {message}")
    if not condition:
        failures.append(message)


def check_health(name: str, base: str, failures: list[str], *, required: bool = True) -> bool:
    status, payload = http_json(f"{base.rstrip('/')}/health", timeout=10)
    ok = status == 200 and isinstance(payload, dict) and payload.get("status") == "ok"
    if required:
        expect(ok, f"{name} health {base}/health", failures)
    else:
        print(f"[INFO] {name} health status={status} payload={payload}")
    return ok


def check_direct_image_ops(remote_base: str, token: str, failures: list[str]) -> None:
    payload = {
        "imageBase64": MINIMAL_PNG_BASE64,
        "params": {"dpi": 300},
    }
    status, data = http_json(
        f"{remote_base.rstrip('/')}/internal/image-ops/set-dpi",
        payload=payload,
        token=token,
        timeout=60,
    )
    ok = (
        status == 200
        and isinstance(data, dict)
        and isinstance(data.get("contentBase64"), str)
        and data.get("contentType") in {"image/png", "image/jpeg"}
    )
    expect(ok, f"remote image-ops direct set-dpi {remote_base}", failures)


def check_backend_image_ops_smoke(args: argparse.Namespace, failures: list[str]) -> None:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parent / "smoke_image_ops_via_backend.py"),
        "--backend-base",
        args.backend_base,
        "--backend-env-file",
        args.backend_env_file,
        "--require-remote-image-ops",
    ]
    print("[INFO] running backend image-ops smoke")
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    expect(result.returncode == 0, "backend image-ops smoke via /api/abilities", failures)


def check_phase(args: argparse.Namespace) -> int:
    failures: list[str] = []
    env = load_env(args.backend_env_file)
    token = env.get("IMAGE_OPS_SERVICE_TOKEN") or os.environ.get("IMAGE_OPS_SERVICE_TOKEN") or ""
    current_base = env.get("IMAGE_OPS_BASE_URL") or os.environ.get("IMAGE_OPS_BASE_URL") or ""

    print(f"[INFO] phase={args.phase}")
    print(f"[INFO] backend_base={args.backend_base}")
    print(f"[INFO] remote_image_ops_base={args.remote_image_ops_base}")
    print(f"[INFO] old_backend_base={args.old_backend_base}")
    print(f"[INFO] current IMAGE_OPS_BASE_URL={current_base or '<empty>'}")

    check_health("coze backend", args.backend_base, failures)

    if args.phase == "pre":
        expect(
            current_base.rstrip("/") in {"http://127.0.0.1:8301", "http://localhost:8301"},
            "Coze backend still points to local image-ops before 117 update",
            failures,
        )
        check_health("117 old backend rollback", args.old_backend_base, failures)
        check_health("117 remote image-ops candidate", args.remote_image_ops_base, failures, required=False)

    elif args.phase == "post-117":
        check_health("117 remote image-ops", args.remote_image_ops_base, failures)
        check_health("117 old backend rollback", args.old_backend_base, failures)
        expect(bool(token), "IMAGE_OPS_SERVICE_TOKEN available for direct remote check", failures)
        if token:
            check_direct_image_ops(args.remote_image_ops_base, token, failures)
        expect(
            current_base.rstrip("/") != args.remote_image_ops_base.rstrip("/"),
            "Coze backend not switched yet during post-117 check",
            failures,
        )

    elif args.phase == "post-coze":
        check_health("117 remote image-ops", args.remote_image_ops_base, failures)
        expect(
            current_base.rstrip("/") == args.remote_image_ops_base.rstrip("/"),
            "Coze backend IMAGE_OPS_BASE_URL points to 117 image-ops",
            failures,
        )
        check_backend_image_ops_smoke(args, failures)

    else:
        raise RuntimeError(f"unknown phase: {args.phase}")

    if failures:
        print("[RESULT] failed")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("[RESULT] ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("pre", "post-117", "post-coze"), required=True)
    parser.add_argument("--backend-base", default="http://127.0.0.1:8099")
    parser.add_argument("--backend-env-file", default="/srv/pod/backend/.env")
    parser.add_argument("--remote-image-ops-base", default="http://117.50.80.158:8200")
    parser.add_argument("--old-backend-base", default="http://117.50.80.158:8099")
    base64.b64decode(MINIMAL_PNG_BASE64)
    return check_phase(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
