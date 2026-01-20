#!/usr/bin/env python3
"""Publish a Coze Studio plugin draft so it appears in Library/Tools.

Usage:
  python3 scripts/coze_studio_publish_plugin.py --space-id <space_id> --plugin-id <plugin_id>

Auth:
- Web login with email/password to obtain `session_key` cookie.
- Prompts interactively if BRIDGE_EMAIL/BRIDGE_PASSWORD are not set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from getpass import getpass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
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


def _json_request(method: str, url: str, payload: dict[str, Any] | None = None, cookie: str | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body) if body else {}
    except Exception:
        return {"_raw": body}


def _login(base: str, email: str, password: str) -> str:
    data = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(f"{base}/api/passport/web/email/login/", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            set_cookies = resp.headers.get_all("Set-Cookie") or []
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        set_cookies = e.headers.get_all("Set-Cookie") or []

    payload = json.loads(body) if body else {}
    if payload.get("code") != 0:
        raise SystemExit(f"Login failed: code={payload.get('code')} msg={payload.get('msg')}")

    session_key = _extract_cookie_value(set_cookies, "session_key")
    if not session_key:
        raise SystemExit("Coze Studio did not set session_key cookie; cannot call plugin APIs.")
    return session_key


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space-id", required=True)
    ap.add_argument("--plugin-id", required=True)
    args = ap.parse_args()

    dotenv = load_dotenv(REPO_ROOT / "backend" / ".env")
    base = (os.getenv("COZE_BASE_URL") or dotenv.get("COZE_BASE_URL") or "http://127.0.0.1:8888").rstrip("/")
    base = base.replace("localhost", "127.0.0.1")

    email = (os.getenv("BRIDGE_EMAIL") or dotenv.get("BRIDGE_EMAIL") or "").strip()
    password = (os.getenv("BRIDGE_PASSWORD") or dotenv.get("BRIDGE_PASSWORD") or "").strip()
    if not email:
        email = input("Coze Studio login email: ").strip()
    if not password:
        password = getpass("Coze Studio login password: ").strip()

    session_key = _login(base, email, password)
    cookie = f"session_key={session_key}"

    next_ver = _json_request(
        "POST",
        f"{base}/api/plugin_api/get_plugin_next_version",
        {"plugin_id": str(args.plugin_id), "space_id": str(args.space_id)},
        cookie=cookie,
    )
    version_name = next_ver.get("next_version_name") or "v0.1.0"

    resp = _json_request(
        "POST",
        f"{base}/api/plugin_api/publish_plugin",
        {
            "plugin_id": str(args.plugin_id),
            "privacy_status": False,
            "privacy_info": "",
            "version_name": str(version_name),
            "version_desc": "auto publish",
        },
        cookie=cookie,
    )
    if resp.get("code") not in (0, None):
        raise SystemExit(f"Publish failed: code={resp.get('code')} msg={resp.get('msg')}")
    print(f"Published plugin {args.plugin_id} in space {args.space_id} (version={version_name})")


if __name__ == "__main__":
    main()

