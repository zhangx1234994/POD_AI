#!/usr/bin/env python3
"""Create/update the "PODI Abilities" plugin inside Coze Studio automatically.

This replaces manual "Import OpenAPI" clicks for non-technical users.

How it works:
- Login with the bridge account (email/password) to obtain a session cookie.
- Pick the first available Space (or recently-used one).
- Create (or update) a plugin whose OpenAPI document is our backend-generated spec.

Env (preferred) or `backend/.env`:
  - COZE_BASE_URL (required)
  - PODI_PUBLIC_BASE_URL (default: http://127.0.0.1:8099)  # where this script fetches openapi.json
  - BRIDGE_EMAIL / BRIDGE_PASSWORD
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
from typing import Iterable
from typing import Any
import subprocess

REPO_ROOT = Path(__file__).resolve().parents[1]
# Ensure `scripts._dotenv` is importable when running as a standalone script.
sys.path.insert(0, str(REPO_ROOT))

from scripts._dotenv import load_dotenv  # noqa: E402


PLUGIN_NAME_HUMAN = "PODI Abilities"
PLUGIN_NAME_MODEL = "podi_abilities"


def _force_debug_pass(plugin_id: int) -> None:
    """Coze requires all tools debugged before publish.

    In our single-host internal deployment, we skip the UI-debug friction by
    marking draft tools as DebugPassed in Coze Studio's MySQL.
    """
    flag = os.getenv("COZE_FORCE_PASS_DEBUG", "").strip().lower()
    if flag in {"0", "false", "no", "n"}:
        return
    # Default: enabled (internal-only deployment).
    cmd = [sys.executable, str(REPO_ROOT / "scripts" / "coze_studio_force_debug_pass.py"), "--plugin-id", str(plugin_id)]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        # Non-fatal; publish may still work if tools are already debugged.
        return


def _load_cfg() -> dict[str, str]:
    dotenv = load_dotenv(REPO_ROOT / "backend" / ".env")

    def get(key: str, default: str = "") -> str:
        return (os.getenv(key) or dotenv.get(key) or default).strip()

    cfg = {
        "coze_base_url": get("COZE_BASE_URL").rstrip("/"),
        # For fetching openapi.json from the host (not from inside the container).
        "podi_public_base_url": get("PODI_PUBLIC_BASE_URL", "http://127.0.0.1:8099").rstrip("/"),
        "email": get("BRIDGE_EMAIL"),
        "password": get("BRIDGE_PASSWORD"),
        # Optional: force a specific Coze Space ID (helps when multiple spaces exist).
        "space_id": get("COZE_SPACE_ID", ""),
        # Optional: force a specific plugin id (avoids relying on list APIs).
        "plugin_id": get("COZE_PLUGIN_ID", ""),
    }
    # Prompt interactively if missing; avoids writing secrets into repo files.
    if not cfg["coze_base_url"]:
        raise SystemExit("Missing COZE_BASE_URL; set env var or backend/.env")
    if not cfg["email"]:
        if not sys.stdin.isatty():
            raise SystemExit("Missing BRIDGE_EMAIL and stdin is not interactive; set env var BRIDGE_EMAIL.")
        cfg["email"] = input("Bridge email (Coze Studio login): ").strip()
    if not cfg["password"]:
        if not sys.stdin.isatty():
            raise SystemExit("Missing BRIDGE_PASSWORD and stdin is not interactive; set env var BRIDGE_PASSWORD.")
        cfg["password"] = getpass("Bridge password (Coze Studio login): ").strip()
    if not cfg["email"] or not cfg["password"]:
        raise SystemExit("Bridge email/password required.")
    return cfg


def _json_request(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    cookie: str | None = None,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with opener.open(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body) if body else {}
    except Exception:
        return {"_raw": body}


def _extract_cookie_value(set_cookie_values: Iterable[str], key: str) -> str | None:
    prefix = f"{key}="
    for raw in set_cookie_values:
        # Example: session_key=xxx; Path=/; HttpOnly
        parts = [p.strip() for p in raw.split(";") if p.strip()]
        if not parts:
            continue
        if parts[0].startswith(prefix):
            return parts[0][len(prefix) :]
    return None


def _redact_set_cookie(raw: str) -> str:
    # Redact the cookie value while preserving the cookie name for debugging.
    # Example: "session_key=abc; Path=/; HttpOnly" -> "session_key=<redacted>; Path=/; HttpOnly"
    if "=" not in raw:
        return raw
    name, rest = raw.split("=", 1)
    if ";" in rest:
        _val, tail = rest.split(";", 1)
        return f"{name}=<redacted>;{tail}"
    return f"{name}=<redacted>"


def _login(
    opener: urllib.request.OpenerDirector, base: str, email: str, password: str
) -> tuple[dict[str, Any], str | None]:
    # We do not rely on CookieJar here because some Coze deployments set cookies with
    # Domain attributes that Python may refuse for 127.0.0.1. We extract session_key
    # from Set-Cookie and send it explicitly afterwards.
    data = json.dumps({"email": email, "password": password}).encode("utf-8")
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
        payload = json.loads(body) if body else {}
    except Exception:
        payload = {"_raw": body}

    if payload.get("code") != 0:
        raise SystemExit(f"Coze Studio login failed: code={payload.get('code')} msg={payload.get('msg')}")

    session_key = _extract_cookie_value(set_cookies, "session_key")
    debug = os.getenv("COZE_PLUGIN_DEBUG", "").strip().lower() in {"1", "true", "yes", "y"}
    if debug and not session_key:
        redacted = [_redact_set_cookie(v) for v in set_cookies]
        print("debug: login Set-Cookie headers:")
        for v in redacted:
            print(f"  {v}")
    return payload, session_key


def _account_info(opener: urllib.request.OpenerDirector, base: str) -> dict[str, Any]:
    return _json_request(opener, "POST", f"{base}/api/passport/account/info/v2/", {})


def _pick_space_id(opener: urllib.request.OpenerDirector, base: str, cookie: str | None) -> int:
    # Allow forcing a space via env to avoid "plugin created but not visible" confusion.
    forced = os.getenv("COZE_SPACE_ID", "").strip()
    if forced:
        try:
            return int(forced)
        except Exception:
            raise SystemExit("Invalid COZE_SPACE_ID (must be an integer).")

    resp = _json_request(opener, "POST", f"{base}/api/playground_api/space/list", {}, cookie=cookie)
    if resp.get("code") not in (0, None):
        raise SystemExit(f"Failed to list spaces: code={resp.get('code')} msg={resp.get('msg')}")

    data = resp.get("data") or {}
    # Prefer recently used space if available; else first space.
    candidates = []
    for key in ("recently_used_space_list", "bot_space_list", "team_space_list"):
        v = ((data or {}).get(key) or []) if isinstance(data, dict) else []
        if isinstance(v, list):
            candidates.extend([item for item in v if isinstance(item, dict)])
    if not candidates:
        raise SystemExit("No space found in Coze Studio (cannot create plugin).")

    space_id = candidates[0].get("id")
    if not isinstance(space_id, int):
        # Sometimes js_conv means it may come as string.
        try:
            space_id = int(str(space_id))
        except Exception:
            raise SystemExit("Invalid space id from Coze Studio.")
    return space_id


def _fetch_podi_openapi(podi_public_base_url: str) -> str:
    url = f"{podi_public_base_url}/api/coze/podi/openapi.json"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _manifest() -> str:
    # Minimal manifest that passes Coze Studio validation.
    mf = {
        "schema_version": "v1",
        "name_for_model": PLUGIN_NAME_MODEL,
        "name_for_human": PLUGIN_NAME_HUMAN,
        "description_for_model": "Expose PODI atomic abilities as tools (one tool per ability).",
        "description_for_human": "将 PODI 原子能力作为工具接入（每个能力一个 Tool）。",
        "auth": {"type": "none", "sub_type": "", "payload": ""},
        "logo_url": "",
        "api": {"type": "cloud"},
    }
    return json.dumps(mf, ensure_ascii=True)


def _get_next_version_name(opener: urllib.request.OpenerDirector, base: str, plugin_id: int, space_id: int, cookie: str | None) -> str | None:
    resp = _json_request(
        opener,
        "POST",
        f"{base}/api/plugin_api/get_plugin_next_version",
        {"plugin_id": str(plugin_id), "space_id": str(space_id)},
        cookie=cookie,
    )
    if resp.get("code") not in (0, None):
        return None
    name = resp.get("next_version_name")
    return str(name) if name else None


def _publish_plugin(opener: urllib.request.OpenerDirector, base: str, plugin_id: int, space_id: int, cookie: str | None) -> None:
    version_name = _get_next_version_name(opener, base, plugin_id, space_id, cookie) or "v0.1.0"
    resp = _json_request(
        opener,
        "POST",
        f"{base}/api/plugin_api/publish_plugin",
        {
            "plugin_id": str(plugin_id),
            "privacy_status": False,
            "privacy_info": "",
            "version_name": version_name,
            "version_desc": "auto publish",
        },
        cookie=cookie,
    )
    # If already published and no changes, Coze may return non-zero; we don't treat it as fatal.
    if resp.get("code") not in (0, None):
        msg = str(resp.get("msg") or "")
        if "published" in msg.lower() or "no change" in msg.lower():
            return
        raise SystemExit(f"Plugin publish failed: code={resp.get('code')} msg={resp.get('msg')}")


def _find_existing_plugin_id(
    opener: urllib.request.OpenerDirector, base: str, user_id: int, space_id: int, cookie: str | None
) -> int | None:
    resp = _json_request(
        opener,
        "POST",
        f"{base}/api/plugin_api/get_dev_plugin_list",
        {"dev_id": str(user_id), "space_id": str(space_id), "name": PLUGIN_NAME_HUMAN},
        cookie=cookie,
    )
    if resp.get("code") not in (0, None):
        return None
    plugin_list = resp.get("plugin_list") or resp.get("pluginList") or resp.get("data", {}).get("plugin_list")
    if not isinstance(plugin_list, list):
        plugin_list = resp.get("data", {}).get("plugin_list") if isinstance(resp.get("data"), dict) else None
    if not isinstance(plugin_list, list):
        return None
    for item in plugin_list:
        if not isinstance(item, dict):
            continue
        if item.get("name") == PLUGIN_NAME_HUMAN:
            pid = item.get("id")
            try:
                return int(str(pid))
            except Exception:
                continue
    return None


def _register_plugin(opener: urllib.request.OpenerDirector, base: str, space_id: int, openapi: str) -> int:
    resp = _json_request(
        opener,
        "POST",
        f"{base}/api/plugin_api/register",
        {
            "ai_plugin": _manifest(),
            "openapi": openapi,
            "space_id": str(space_id),
            "import_from_file": False,
        },
    )
    if resp.get("code") != 0:
        raise SystemExit(f"Plugin register failed: code={resp.get('code')} msg={resp.get('msg')}")
    data = resp.get("data") or {}
    plugin_id = data.get("plugin_id") or data.get("id")
    try:
        return int(str(plugin_id))
    except Exception:
        raise SystemExit("Plugin created but plugin_id missing in response.")


def _update_plugin(opener: urllib.request.OpenerDirector, base: str, plugin_id: int, openapi: str) -> None:
    resp = _json_request(
        opener,
        "POST",
        f"{base}/api/plugin_api/update",
        {"plugin_id": str(plugin_id), "ai_plugin": _manifest(), "openapi": openapi},
    )
    if resp.get("code") != 0:
        raise SystemExit(f"Plugin update failed: code={resp.get('code')} msg={resp.get('msg')}")


def _batch_create_apis(
    opener: urllib.request.OpenerDirector,
    base: str,
    *,
    plugin_id: int,
    space_id: int,
    dev_id: int,
    openapi: str,
    cookie: str | None,
) -> None:
    """Sync tool definitions from OpenAPI into the plugin draft.

    Coze's `/api/plugin_api/update` updates only plugin meta; tools are updated via
    `/api/plugin_api/batch_create_api` (same flow as "Import OpenAPI" in UI).
    """

    resp = _json_request(
        opener,
        "POST",
        f"{base}/api/plugin_api/batch_create_api",
        {
            "plugin_id": str(plugin_id),
            "space_id": str(space_id),
            "dev_id": str(dev_id),
            "replace_same_paths": True,
            "ai_plugin": _manifest(),
            "openapi": openapi,
        },
        cookie=cookie,
    )
    if resp.get("code") != 0:
        raise SystemExit(f"Batch create APIs failed: code={resp.get('code')} msg={resp.get('msg')}")


def main() -> None:
    cfg = _load_cfg()
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    login, session_key = _login(opener, cfg["coze_base_url"], cfg["email"], cfg["password"])
    if not session_key:
        debug = os.getenv("COZE_PLUGIN_DEBUG", "").strip().lower() in {"1", "true", "yes", "y"}
        if debug:
            # Best-effort visibility into whether Coze is setting cookies at all.
            print("debug: session_key missing; enable COZE_PLUGIN_DEBUG=1 to see Set-Cookie names")
        raise SystemExit("Coze Studio did not set session_key cookie; cannot access web APIs.")
    cookie_header = f"session_key={session_key}" if session_key else None
    # Prefer user id from login response; it's the most reliable and avoids
    # any extra auth/session issues on some deployments.
    data = (login or {}).get("data") or {}
    user_id = data.get("user_id_str") or data.get("userId") or data.get("user_id")
    if not user_id:
        # Fallback to account info endpoint.
        info = _account_info(opener, cfg["coze_base_url"])
        data = info.get("data") or {}
        user_id = data.get("user_id_str") or data.get("userId") or data.get("user_id")
    try:
        user_id_int = int(str(user_id))
    except Exception:
        # Print minimal debug info without exposing secrets.
        hint = {}
        for k in ("code", "msg"):
            if isinstance(login, dict) and k in login:
                hint[f"login_{k}"] = login.get(k)
        raise SystemExit(f"Cannot read Coze Studio user_id_str for plugin operations. hint={hint}")

    space_id = _pick_space_id(opener, cfg["coze_base_url"], cookie_header)
    openapi = _fetch_podi_openapi(cfg["podi_public_base_url"])

    forced_plugin_id = cfg.get("plugin_id", "").strip()
    if forced_plugin_id:
        try:
            plugin_id = int(forced_plugin_id)
        except Exception:
            raise SystemExit("Invalid COZE_PLUGIN_ID (must be an integer).")
        _batch_create_apis(
            opener,
            cfg["coze_base_url"],
            plugin_id=plugin_id,
            space_id=space_id,
            dev_id=user_id_int,
            openapi=openapi,
            cookie=cookie_header,
        )
        _force_debug_pass(plugin_id)
        _publish_plugin(opener, cfg["coze_base_url"], plugin_id, space_id, cookie_header)
        print(f"Coze Studio: PODI plugin updated (space_id={space_id} plugin_id={plugin_id})")
        return

    existing = _find_existing_plugin_id(opener, cfg["coze_base_url"], user_id_int, space_id, cookie_header)
    if existing:
        _batch_create_apis(
            opener,
            cfg["coze_base_url"],
            plugin_id=existing,
            space_id=space_id,
            dev_id=user_id_int,
            openapi=openapi,
            cookie=cookie_header,
        )
        _force_debug_pass(existing)
        _publish_plugin(opener, cfg["coze_base_url"], existing, space_id, cookie_header)
        print(f"Coze Studio: PODI plugin updated (space_id={space_id} plugin_id={existing})")
        return

    _json_request(
        opener,
        "POST",
        f"{cfg['coze_base_url']}/api/plugin_api/register",
        {
            "ai_plugin": _manifest(),
            "openapi": openapi,
            "space_id": str(space_id),
            "import_from_file": False,
        },
        cookie=cookie_header,
    )
    # Some deployments don't return plugin_id in the register response; query it back by name.
    created_id = _find_existing_plugin_id(opener, cfg["coze_base_url"], user_id_int, space_id, cookie_header)
    if created_id:
        _force_debug_pass(created_id)
        _publish_plugin(opener, cfg["coze_base_url"], created_id, space_id, cookie_header)
        print(f"Coze Studio: PODI plugin created (space_id={space_id} plugin_id={created_id})")
        return

    print(f"Coze Studio: PODI plugin created (space_id={space_id}) but plugin_id not found via list")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
