#!/usr/bin/env python3
"""Run a Coze Studio workflow via HTTP (self-hosted).

This deployment uses cookie-based auth (session_key). PAT bearer tokens are not
accepted by `/api/v1/workflow/run` in our current setup.

Usage:
  COZE_BASE_URL=http://118.31.18.249:8888 \\
  BRIDGE_EMAIL=zhangxposeidon@... \\
  BRIDGE_PASSWORD='...' \\
  python3 scripts/coze_studio_run_workflow.py --space-id 7597421439045599232 --workflow-id 7597530887256801280 \\
    --inputs '{"image_urls":"https://...","prompt":"..."}'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from getpass import getpass
from http.cookiejar import CookieJar
from typing import Any, Iterable


def _extract_cookie_value(set_cookie_values: Iterable[str], key: str) -> str | None:
    prefix = f"{key}="
    for raw in set_cookie_values:
        parts = [p.strip() for p in raw.split(";") if p.strip()]
        if not parts:
            continue
        if parts[0].startswith(prefix):
            return parts[0][len(prefix) :]
    return None


def _json_request(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    cookie: str | None = None,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with opener.open(req, timeout=45) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"_raw": body}
        parsed["_http_status"] = e.code
        return parsed


def _login(opener: urllib.request.OpenerDirector, base: str, email: str, password: str) -> str:
    payload = {"email": email, "password": password}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{base}/api/passport/web/email/login/", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            set_cookies = resp.headers.get_all("Set-Cookie") or []
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        set_cookies = e.headers.get_all("Set-Cookie") or []

    try:
        parsed = json.loads(body) if body else {}
    except Exception:
        parsed = {"_raw": body}

    if parsed.get("code") != 0:
        raise SystemExit(f"Coze Studio login failed: code={parsed.get('code')} msg={parsed.get('msg')}")

    session_key = _extract_cookie_value(set_cookies, "session_key")
    if not session_key:
        raise SystemExit("Login succeeded but no session_key cookie returned.")
    return f"session_key={session_key}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.getenv("COZE_BASE_URL", "").strip() or "http://127.0.0.1:8888")
    ap.add_argument("--space-id", required=True)
    ap.add_argument("--workflow-id", required=True)
    ap.add_argument(
        "--inputs",
        default="{}",
        help='JSON string, e.g. \'{"prompt":"...","image_urls":"https://..."}\'',
    )
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    base = str(args.base_url).rstrip("/")
    email = (os.getenv("BRIDGE_EMAIL") or os.getenv("COZE_EMAIL") or "").strip()
    password = (os.getenv("BRIDGE_PASSWORD") or os.getenv("COZE_PASSWORD") or "").strip()
    if not email:
        if not sys.stdin.isatty():
            raise SystemExit("Missing BRIDGE_EMAIL/COZE_EMAIL.")
        email = input("Coze Studio login email: ").strip()
    if not password:
        if not sys.stdin.isatty():
            raise SystemExit("Missing BRIDGE_PASSWORD/COZE_PASSWORD.")
        password = getpass("Coze Studio login password: ").strip()

    try:
        inputs = json.loads(args.inputs) if args.inputs.strip() else {}
    except Exception:
        raise SystemExit("--inputs must be valid JSON")
    if not isinstance(inputs, dict):
        raise SystemExit("--inputs must be a JSON object")

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    cookie = _login(opener, base, email, password)

    # Note: Coze open-source deployments differ; current server expects cookie auth
    # and returns 401 "missing session_key in cookie" otherwise.
    run_url = f"{base}/api/v1/workflow/run"
    payload = {
        "workflow_id": str(args.workflow_id),
        "space_id": str(args.space_id),
        "inputs": inputs,
        "timeout": int(args.timeout),
    }
    resp = _json_request(opener, "POST", run_url, payload, cookie=cookie)
    print(json.dumps(resp, ensure_ascii=False, indent=2)[:12000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

