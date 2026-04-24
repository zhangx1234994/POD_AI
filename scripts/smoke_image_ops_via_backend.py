#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


MINIMAL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8B9l8AAAAASUVORK5CYII="
)
MANAGED_IMAGE_OPS_KEYS = ["expand_mask_color", "set_dpi", "upscale_resize"]


def _auth_headers(token: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(client: httpx.Client, path: str) -> Any:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def _post_json(client: httpx.Client, path: str, payload: dict[str, Any]) -> Any:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def _find_ability(items: list[dict[str, Any]], capability_key: str) -> dict[str, Any]:
    for item in items:
        if item.get("provider") == "podi" and item.get("capabilityKey") == capability_key:
            return item
    raise RuntimeError(f"ABILITY_NOT_FOUND:{capability_key}")


def _load_db_abilities(backend_env_file: str | None) -> list[dict[str, Any]]:
    env_candidates = []
    if backend_env_file:
        env_candidates.append(Path(backend_env_file))
    env_candidates.extend([Path("/srv/pod/backend/.env"), Path(__file__).resolve().parents[1] / "backend" / ".env"])

    for env_path in env_candidates:
        if env_path.is_file():
            for raw in env_path.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value)
            break

    from sqlalchemy import select

    from app.core.db import get_session
    from app.models.integration import Ability

    with get_session() as session:
        rows = session.execute(
            select(Ability.id, Ability.provider, Ability.capability_key).where(
                Ability.provider == "podi", Ability.capability_key.in_(MANAGED_IMAGE_OPS_KEYS)
            )
        ).all()
    return [{"id": row.id, "provider": row.provider, "capabilityKey": row.capability_key} for row in rows]


def _assert_success(resp: dict[str, Any], capability_key: str) -> None:
    status = resp.get("status")
    if status != "succeeded":
        raise RuntimeError(f"{capability_key}: unexpected status {status}")
    images = resp.get("images") or []
    assets = resp.get("assets") or []
    if not images and not assets:
        raise RuntimeError(f"{capability_key}: missing images/assets")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke image-ops abilities via backend API.")
    parser.add_argument("--backend-base", default=os.environ.get("BACKEND_URL", "http://127.0.0.1:8099"))
    parser.add_argument("--token", default=os.environ.get("SERVICE_API_TOKEN", ""))
    parser.add_argument("--image-base64", default=MINIMAL_PNG_BASE64)
    parser.add_argument("--backend-env-file", default=os.environ.get("BACKEND_ENV_FILE", ""))
    args = parser.parse_args()

    # Validate base64 early so failures are explicit.
    base64.b64decode(args.image_base64)

    client = httpx.Client(
        base_url=args.backend_base.rstrip("/"),
        headers=_auth_headers(args.token or None),
        timeout=120,
    )
    try:
        abilities = _get_json(client, "/api/abilities").get("items") or []
        available_keys = {item.get("capabilityKey") for item in abilities}
        if not set(MANAGED_IMAGE_OPS_KEYS).issubset(available_keys):
            abilities.extend(_load_db_abilities(args.backend_env_file))

        expand = _find_ability(abilities, "expand_mask_color")
        set_dpi = _find_ability(abilities, "set_dpi")
        upscale = _find_ability(abilities, "upscale_resize")

        common_payload = {"imageBase64": args.image_base64, "metadata": {"requestFrom": "image-ops-smoke"}}

        resp_expand = _post_json(
            client,
            f"/api/abilities/{expand['id']}/invoke",
            {
                **common_payload,
                "inputs": {
                    "expand_left": 8,
                    "expand_right": 8,
                    "expand_top": 8,
                    "expand_bottom": 8,
                },
            },
        )
        _assert_success(resp_expand, "expand_mask_color")

        resp_set_dpi = _post_json(
            client,
            f"/api/abilities/{set_dpi['id']}/invoke",
            {
                **common_payload,
                "inputs": {
                    "dpi": 300,
                },
            },
        )
        _assert_success(resp_set_dpi, "set_dpi")

        resp_upscale = _post_json(
            client,
            f"/api/abilities/{upscale['id']}/invoke",
            {
                **common_payload,
                "inputs": {
                    "max_long_edge": 64,
                    "output_format": "png",
                },
            },
        )
        _assert_success(resp_upscale, "upscale_resize")

        result = {
            "backend": args.backend_base.rstrip("/"),
            "checked": ["expand_mask_color", "set_dpi", "upscale_resize"],
            "status": "ok",
        }
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        sys.stdout.flush()
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2) + "\n")
        sys.stderr.flush()
        return 1
    finally:
        client.close()
