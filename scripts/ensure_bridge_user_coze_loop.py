#!/usr/bin/env python3
"""Ensure a "bridge" user exists in Coze Loop, and set username (best-effort).

Reads credentials from env (preferred), falling back to `backend/.env`:
  - BRIDGE_USERNAME / BRIDGE_EMAIL / BRIDGE_PASSWORD
  - COZE_LOOP_BASE_URL (default: http://127.0.0.1:8082)
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
    base_url = (
        os.getenv("COZE_LOOP_BASE_URL") or dotenv.get("COZE_LOOP_BASE_URL") or "http://127.0.0.1:8082"
    ).rstrip("/")

    username = (os.getenv("BRIDGE_USERNAME") or dotenv.get("BRIDGE_USERNAME") or "").strip()
    email = (os.getenv("BRIDGE_EMAIL") or dotenv.get("BRIDGE_EMAIL") or "").strip()
    password = (os.getenv("BRIDGE_PASSWORD") or dotenv.get("BRIDGE_PASSWORD") or "").strip()

    if not email:
        email = input("Bridge email (Coze Loop login): ").strip()
    if not password:
        password = getpass("Bridge password (Coze Loop login): ").strip()
    if not email or not password:
        raise SystemExit("Bridge email/password required.")
    if not username:
        username = email.split("@", 1)[0]
    return base_url, username, email, password


def _request_json(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    payload: dict | None = None,
) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
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


def _base_code(resp: dict) -> int | None:
    # Coze Loop wraps status in BaseResp.
    base = resp.get("BaseResp") or resp.get("base_resp") or {}
    code = base.get("StatusCode") if isinstance(base, dict) else None
    if code is None and isinstance(resp.get("code"), int):
        return resp["code"]
    return code


def main() -> None:
    base_url, username, email, password = _read_settings()
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    # 1) Register or login.
    reg = _request_json(opener, "POST", f"{base_url}/api/foundation/v1/users/register", {"email": email, "password": password})
    if _base_code(reg) not in (0, None):
        login = _request_json(
            opener,
            "POST",
            f"{base_url}/api/foundation/v1/users/login_by_password",
            {"email": email, "password": password},
        )
        if _base_code(login) not in (0, None):
            raise SystemExit("Coze Loop login failed")

    # 2) Get session user info to obtain user_id.
    sess = _request_json(opener, "GET", f"{base_url}/api/foundation/v1/users/session")
    user_info = sess.get("user_info") or sess.get("UserInfo") or sess.get("userInfo") or {}
    user_id = (
        user_info.get("user_id")
        or user_info.get("userId")
        or user_info.get("UserID")
        or user_info.get("id")
    )
    if not user_id:
        # Not fatal, but we cannot set profile without user_id.
        print("Coze Loop: bridge user ok (session user_id missing; skip profile update)")
        return

    # 3) Best-effort update profile. The thrift comment says `name` is the unique name.
    upd = _request_json(
        opener,
        "PUT",
        f"{base_url}/api/foundation/v1/users/{user_id}/update_profile",
        {"name": username},
    )
    if _base_code(upd) not in (0, None):
        print("Coze Loop: bridge user ok (profile update skipped)")
        return

    print("Coze Loop: bridge user ok")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
