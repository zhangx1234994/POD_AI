#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from typing import Any

import httpx


MINIMAL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8B9l8AAAAASUVORK5CYII="
)


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
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        client.close()
