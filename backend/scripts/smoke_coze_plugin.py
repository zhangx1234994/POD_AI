import json
import sys
from typing import Any

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099"
HEADERS = {"x-real-ip": "127.0.0.1"}


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def get_json(path: str) -> dict[str, Any]:
    resp = httpx.get(f"{BASE}{path}", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    expect(isinstance(data, dict), f"{path} did not return JSON object")
    return data


def post_json(path: str, payload: dict[str, Any] | None = None) -> httpx.Response:
    return httpx.post(f"{BASE}{path}", headers=HEADERS, json=payload, timeout=15)


print("[1] openapi.json")
openapi = get_json("/api/coze/podi/openapi.json")
paths = openapi.get("paths") or {}
expect("/api/coze/podi/comfyui/queue-summary" in paths, "queue-summary missing in openapi.json")

print("[2] comfyui openapi.json")
openapi_comfy = get_json("/api/coze/podi/comfyui/openapi.json")
paths_comfy = openapi_comfy.get("paths") or {}
expect("/api/coze/podi/comfyui/queue-summary" in paths_comfy, "queue-summary missing in comfyui openapi.json")

print("[3] queue-summary endpoint")
resp = post_json("/api/coze/podi/comfyui/queue-summary")
resp.raise_for_status()
summary = resp.json()
expect(isinstance(summary, dict), "queue-summary response not object")
for key in ("totalRunning", "totalPending", "totalCount", "servers"):
    expect(key in summary, f"queue-summary missing {key}")

print("[4] tasks/get missing taskId -> 400")
resp = post_json("/api/coze/podi/tasks/get", {})
expect(resp.status_code == 400, f"expected 400, got {resp.status_code}")

print("[5] tasks/get unknown taskId -> 404")
resp = post_json(
    "/api/coze/podi/tasks/get",
    {"taskId": "t1.comfyui.auto.00000000000000000000000000000000"},
)
expect(resp.status_code == 404, f"expected 404, got {resp.status_code}")

print("All smoke checks passed.")
