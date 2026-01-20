#!/usr/bin/env python3
"""Run a Coze workflow via HTTP (self-hosted).

Coze open-source deployments typically expose *two* kinds of endpoints:
1) OpenAPI-style endpoint: `/v1/workflow/run` (Bearer token auth, "parameters" payload)
2) Web-console endpoint: `/api/v1/workflow/run` (cookie auth, used by the UI)

Usage:
  COZE_BASE_URL=http://118.31.18.249:8888 \\
  COZE_PAT='pat_...' \\
  python3 scripts/coze_studio_run_workflow.py --workflow-id 7597530887256801280 \\
    --parameters '{"image_urls":"https://...","prompt":"..."}'

If COZE_PAT is not set, the script falls back to email/password login and cookie auth
to call the UI endpoint.
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
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
# Ensure `scripts._dotenv` is importable when running as a standalone script.
sys.path.insert(0, str(REPO_ROOT))

from scripts._dotenv import load_dotenv  # noqa: E402


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
    dotenv = load_dotenv(REPO_ROOT / "backend" / ".env")

    ap = argparse.ArgumentParser()
    base_url_default = (os.getenv("COZE_BASE_URL") or dotenv.get("COZE_BASE_URL") or "").strip() or "http://127.0.0.1:8888"
    ap.add_argument("--base-url", default=base_url_default)
    ap.add_argument("--workflow-id", required=True)
    ap.add_argument("--space-id", default="", help="Optional; only used by some UI endpoints.")
    ap.add_argument(
        "--parameters",
        default="{}",
        help='JSON string, e.g. \'{"prompt":"...","image_urls":"https://..."}\'',
    )
    ap.add_argument("--bot-id", default="", help="Optional bot_id for workflows that require an associated bot.")
    ap.add_argument("--is-async", action="store_true", help="Request async execution (if supported).")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    base = str(args.base_url).rstrip("/")
    try:
        parameters = json.loads(args.parameters) if args.parameters.strip() else {}
    except Exception:
        raise SystemExit("--parameters must be valid JSON")
    if not isinstance(parameters, dict):
        raise SystemExit("--parameters must be a JSON object")

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    # Preferred: OpenAPI endpoint with Bearer token auth.
    pat = (
        os.getenv("COZE_PAT")
        or dotenv.get("COZE_PAT")
        or os.getenv("COZE_API_KEY")
        or dotenv.get("COZE_API_KEY")
        or os.getenv("COZE_TOKEN")
        or dotenv.get("COZE_TOKEN")
        or ""
    ).strip()
    if pat:
        run_url = f"{base}/v1/workflow/run"
        payload: dict[str, Any] = {
            "workflow_id": str(args.workflow_id),
            "parameters": parameters,
        }
        if args.bot_id:
            payload["bot_id"] = str(args.bot_id)
        if args.is_async:
            payload["is_async"] = True
        req = urllib.request.Request(run_url, data=json.dumps(payload).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {pat}")
        try:
            with opener.open(req, timeout=45) as resp_obj:
                body = resp_obj.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
        try:
            resp = json.loads(body) if body else {}
        except Exception:
            resp = {"_raw": body}
        print(json.dumps(resp, ensure_ascii=False, indent=2)[:12000])
        return 0

    # Fallback: UI endpoint (cookie auth).
    email = (os.getenv("BRIDGE_EMAIL") or dotenv.get("BRIDGE_EMAIL") or os.getenv("COZE_EMAIL") or dotenv.get("COZE_EMAIL") or "").strip()
    password = (os.getenv("BRIDGE_PASSWORD") or dotenv.get("BRIDGE_PASSWORD") or os.getenv("COZE_PASSWORD") or dotenv.get("COZE_PASSWORD") or "").strip()
    if not email:
        if not sys.stdin.isatty():
            raise SystemExit("Missing BRIDGE_EMAIL/COZE_EMAIL.")
        email = input("Coze Studio login email: ").strip()
    if not password:
        if not sys.stdin.isatty():
            raise SystemExit("Missing BRIDGE_PASSWORD/COZE_PASSWORD.")
        password = getpass("Coze Studio login password: ").strip()

    cookie = _login(opener, base, email, password)
    run_url = f"{base}/api/v1/workflow/run"
    payload = {
        "workflow_id": str(args.workflow_id),
        "space_id": str(args.space_id),
        "inputs": parameters,
        "timeout": int(args.timeout),
    }
    resp = _json_request(opener, "POST", run_url, payload, cookie=cookie)
    print(json.dumps(resp, ensure_ascii=False, indent=2)[:12000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
