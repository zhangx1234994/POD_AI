#!/usr/bin/env python3
"""Ensure a "bridge" user exists in Coze Studio, and (best-effort) set username.

Reads credentials from env (preferred), falling back to `backend/.env`:
  - BRIDGE_USERNAME / BRIDGE_EMAIL / BRIDGE_PASSWORD
  - COZE_BASE_URL (required)

We intentionally do not print the password.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from getpass import getpass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Ensure `scripts._dotenv` is importable when running as a standalone script.
sys.path.insert(0, str(REPO_ROOT))

from scripts._dotenv import load_dotenv  # noqa: E402


def _read_settings() -> tuple[str, str, str, str]:
    dotenv = load_dotenv(REPO_ROOT / "backend" / ".env")
    base_url = (os.getenv("COZE_BASE_URL") or dotenv.get("COZE_BASE_URL") or "").rstrip("/")
    if not base_url:
        raise SystemExit("Missing COZE_BASE_URL (set env or backend/.env)")

    username = (os.getenv("BRIDGE_USERNAME") or dotenv.get("BRIDGE_USERNAME") or "").strip()
    email = (os.getenv("BRIDGE_EMAIL") or dotenv.get("BRIDGE_EMAIL") or "").strip()
    password = (os.getenv("BRIDGE_PASSWORD") or dotenv.get("BRIDGE_PASSWORD") or "").strip()

    if not email:
        email = input("Bridge email (Coze Studio login): ").strip()
    if not password:
        password = getpass("Bridge password (Coze Studio login): ").strip()
    if not email or not password:
        raise SystemExit("Bridge email/password required.")
    if not username:
        # Coze can work without forcing a specific username; we still try if provided.
        username = email.split("@", 1)[0]
    return base_url, username, email, password


def _post_json(opener: urllib.request.OpenerDirector, url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body) if body else {}
    except Exception:
        return {"_raw": body}


def main() -> None:
    base_url, username, email, password = _read_settings()

    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    # 1) Register (idempotent-ish). If already exists, proceed to login.
    register = _post_json(
        opener,
        f"{base_url}/api/passport/web/email/register/v2/",
        {"email": email, "password": password},
    )
    code = register.get("code")

    # Coze returns {code:0} on success. If failed, try login anyway.
    if code != 0:
        login = _post_json(
            opener,
            f"{base_url}/api/passport/web/email/login/",
            {"email": email, "password": password},
        )
        if login.get("code") != 0:
            raise SystemExit(f"Coze Studio login failed: code={login.get('code')} msg={login.get('msg')}")

    # 2) Best-effort set display name + unique name.
    update = _post_json(
        opener,
        f"{base_url}/api/user/update_profile",
        # Set locale so the UI defaults to Chinese for this bridge account.
        {"name": username, "user_unique_name": username, "locale": "zh-CN"},
    )
    if update.get("code") not in (0, None):
        # Not fatal; user may already have a different unique name.
        print(f"Coze Studio: profile update skipped (code={update.get('code')} msg={update.get('msg')})")
        return

    print("Coze Studio: bridge user ok")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
