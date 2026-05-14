#!/usr/bin/env python3
"""Run GPT Image 2 controlled fission through PODI business API."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


BACKEND = os.environ.get("PODI_BACKEND", "http://114.55.0.56:8099").rstrip("/")
API_KEY = os.environ.get("PODI_API_KEY", "")
IMAGE_URL = os.environ.get("PODI_IMAGE_URL", "https://example.com/input.png")


def post_json(path: str, payload: dict) -> dict:
    if not API_KEY:
        raise SystemExit("请先设置 PODI_API_KEY")
    req = urllib.request.Request(
        f"{BACKEND}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-PODI-API-Key": API_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code}: {body}") from exc


def main() -> None:
    submit_payload = {
        "imageUrl": IMAGE_URL,
        "version": "gpt-image2-vl-v2",
        "prompt": "保留系列感，元素要明显变化",
        "variation_strength": "same_series",
        "quality": "preview",
        "size": "auto",
        "source": "partner-api",
        "channel": "open-api",
        "requestId": f"biz-gpt-image2-fission-{int(time.time())}",
        "traceId": f"trace-gpt-image2-fission-{int(time.time())}",
    }
    created = post_json("/api/business/fission/runs", submit_payload)
    run_id = created.get("runId") or created.get("id")
    print("submitted:", json.dumps(created, ensure_ascii=False, indent=2))
    if not run_id:
        raise SystemExit("提交成功但没有返回 runId")

    for _ in range(90):
        result = post_json("/api/business/runs/get", {"runId": run_id})
        status = result.get("status")
        print("poll:", status)
        if status in {"succeeded", "failed", "cancelled"}:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        time.sleep(10)
    raise SystemExit(f"轮询超时，runId={run_id}")


if __name__ == "__main__":
    main()

