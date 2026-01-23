#!/usr/bin/env python3
"""Debug a Coze workflow execution from the backend context.

This script helps answer: where did the workflow put the output?
- prints raw Coze response (top-level keys)
- prints parsed payload (EvalService-compatible)
- extracts `output` and best-effort image URLs
- if output looks like a task id, optionally runs the configured callback workflow

Usage examples:
  python backend/scripts/debug_eval_workflow.py --workflow-id 7598587935331450880 --url "https://..." --params '{"expand_left":"0"}'
  python backend/scripts/debug_eval_workflow.py --workflow-id 7597421439045599232 --url "https://..." --params '{"prompt":"...","moxing":"1"}'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from uuid import uuid4

from pathlib import Path

# Ensure `backend/` is on sys.path when running from repo root.
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.core.config import get_settings
from app.services.coze_client import coze_client
from app.services.eval_service import EvalService


def _parse_json(s: str) -> dict:
    s = (s or "").strip()
    if not s:
        return {}
    return json.loads(s)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--url", default="")
    parser.add_argument(
        "--params",
        default="{}",
        help="JSON string for extra parameters (merged on top of url).",
    )
    parser.add_argument(
        "--poll-callback",
        action="store_true",
        help="If output is a task id, use COZE_COMFYUI_CALLBACK_WORKFLOW_ID to resolve images.",
    )
    args = parser.parse_args()

    params = _parse_json(args.params)
    if args.url:
        params.setdefault("url", args.url)
        # Some workflows use Url/URL; keep compat.
        params.setdefault("Url", args.url)
        params.setdefault("URL", args.url)

    request_id = uuid4().hex
    print(f"[request_id] {request_id}")
    print(f"[workflow_id] {args.workflow_id}")
    print("[params]")
    print(json.dumps(params, ensure_ascii=False, indent=2))

    resp = coze_client.run_workflow(
        workflow_id=str(args.workflow_id),
        parameters=params,
        is_async=False,
        request_id=request_id,
    )

    print("\n[raw_coze_response:keys]")
    print(sorted(resp.keys()))
    # Keep the dump small-ish but still useful.
    print("\n[raw_coze_response]")
    print(json.dumps(resp, ensure_ascii=False, indent=2)[:20000])

    parsed = EvalService._parse_coze_payload(resp)  # noqa: SLF001 - debug script
    print("\n[parsed_payload]")
    print(json.dumps(parsed, ensure_ascii=False, indent=2)[:20000])

    output = parsed.get("output")
    print("\n[output]")
    print(output)

    task_id = EvalService._guess_podi_task_id(parsed, output)  # noqa: SLF001 - debug script
    print("\n[guessed_task_id]")
    print(task_id)

    images = EvalService._extract_image_urls(parsed)  # noqa: SLF001 - debug script
    print("\n[extracted_image_urls]")
    print(json.dumps(images, ensure_ascii=False, indent=2))

    if not args.poll_callback:
        return 0

    settings = get_settings()
    callback_wf = (settings.coze_comfyui_callback_workflow_id or "").strip()
    if not callback_wf:
        print("\n[callback] COZE_COMFYUI_CALLBACK_WORKFLOW_ID is not set; skip.")
        return 0
    if not task_id:
        print("\n[callback] output/task_id missing; skip.")
        return 0

    print(f"\n[callback] polling via workflow_id={callback_wf} taskid={task_id}")
    deadline = time.monotonic() + 180.0
    interval = 2.0
    last_images: list[str] = []
    while time.monotonic() < deadline:
        cb = coze_client.run_workflow(
            workflow_id=callback_wf,
            parameters={"taskid": task_id},
            is_async=False,
            request_id=request_id,
        )
        cb_parsed = EvalService._parse_coze_payload(cb)  # noqa: SLF001 - debug script
        last_images = EvalService._extract_image_urls(cb_parsed)  # noqa: SLF001 - debug script
        if last_images:
            break
        time.sleep(interval)
        interval = min(interval * 1.4, 8.0)

    print("\n[callback_images]")
    print(json.dumps(last_images, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
