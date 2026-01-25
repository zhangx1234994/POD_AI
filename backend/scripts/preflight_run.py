#!/usr/bin/env python3
"""Release preflight runner (test machine).

This script is meant to be run *on the PODI backend host* (where 8099 is reachable).
It performs:
- ComfyUI executor connectivity checks
- Optional Coze workflow runs + result resolution (including ComfyUI callback tasks)

It avoids destructive actions and prints a clear report for operators.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx

# Allow running from repo root: `python3 backend/scripts/preflight_run.py`
sys.path.insert(0, "backend")

from app.core.config import get_settings
from app.core.db import get_session
from app.models.integration import Executor
from app.services.coze_client import coze_client


# Keep this URL stable and publicly reachable from both:
# - the PODI backend host (for base64/upload fallbacks)
# - ComfyUI executors (for URL loader nodes)
DEFAULT_TEST_IMAGE_URL = "https://podi.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin/20260120/fc661480-1768882378.jpg"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def _now() -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _http_ok(url: str, *, timeout: float = 4.0) -> tuple[bool, str]:
    try:
        r = httpx.get(url, timeout=timeout)
        return True, f"HTTP {r.status_code}"
    except Exception as exc:
        return False, str(exc)


def check_comfyui_executors() -> list[CheckResult]:
    results: list[CheckResult] = []
    with get_session() as session:
        rows = (
            session.query(Executor)  # type: ignore[attr-defined]
            .filter(Executor.type.in_(["comfyui", "ComfyUI", "COMFYUI"]))  # type: ignore[attr-defined]
            .all()
        )
    if not rows:
        results.append(CheckResult("ComfyUI executors", False, "no executors found in DB"))
        return results

    for ex in rows:
        cfg = ex.config or {}
        base = (ex.base_url or cfg.get("baseUrl") or cfg.get("base_url") or "").rstrip("/")
        if not base:
            results.append(CheckResult(f"ComfyUI executor {ex.id}", False, "baseUrl missing"))
            continue
        # /system_stats is common; fall back to root if unavailable.
        ok, detail = _http_ok(f"{base}/system_stats")
        if not ok:
            ok2, detail2 = _http_ok(f"{base}/")
            ok = ok2
            detail = f"/system_stats failed: {detail}; / => {detail2}"
        results.append(CheckResult(f"ComfyUI reachable {ex.id}", ok, f"{base} | {detail}"))
    return results


def _coze_poll_history(*, workflow_id: str, execute_id: str, timeout_s: float = 600, verbose: bool = False) -> dict[str, Any]:
    deadline = time.monotonic() + max(10, timeout_s)
    interval = 1.2
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = coze_client.get_workflow_run_history(execute_id=execute_id, workflow_id=workflow_id)
        data = last.get("data")
        # run_history returns list; terminal state is in the last record.
        record = data[-1] if isinstance(data, list) and data else None
        if isinstance(record, dict):
            status = record.get("execute_status")
            if isinstance(status, str) and status.lower() in {"success", "fail"}:
                return last
            if verbose:
                remaining = int(max(0, deadline - time.monotonic()))
                print(f"  - polling coze history: execute_status={status} (remaining={remaining}s)", flush=True)
        time.sleep(interval)
        interval = min(interval * 1.4, 8.0)
    return last


def _parse_run_history_output(hist: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (task_or_output, debug_url)."""
    data = hist.get("data")
    record = data[-1] if isinstance(data, list) and data else None
    if not isinstance(record, dict):
        return None, None
    debug_url = record.get("debug_url")
    out_raw = record.get("output")
    if isinstance(out_raw, str):
        try:
            parsed = json.loads(out_raw)
            if isinstance(parsed, dict):
                v = parsed.get("output")
                return (str(v).strip() if v is not None else None), (str(debug_url).strip() if debug_url else None)
            return str(parsed), (str(debug_url).strip() if debug_url else None)
        except Exception:
            return out_raw.strip() or None, (str(debug_url).strip() if debug_url else None)
    if isinstance(out_raw, dict):
        v = out_raw.get("output")
        return (str(v).strip() if v is not None else None), (str(debug_url).strip() if debug_url else None)
    return None, (str(debug_url).strip() if debug_url else None)


def _poll_podi_task_get(*, podi_base: str, task_id: str, timeout_s: float = 900, verbose: bool = False) -> dict[str, Any]:
    url = f"{podi_base.rstrip('/')}/api/coze/podi/tasks/get"
    deadline = time.monotonic() + max(10, timeout_s)
    interval = 1.2
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        r = httpx.post(url, json={"taskId": task_id}, timeout=20)
        try:
            last = r.json()
        except Exception:
            last = {"status": r.status_code, "text": r.text[:300]}
        status = str(last.get("taskStatus") or last.get("task_status") or "").lower()
        if status in {"succeeded", "failed"}:
            return last
        if verbose:
            remaining = int(max(0, deadline - time.monotonic()))
            hint = last.get("debugResponse") or ""
            hint = (str(hint)[:120] + "...") if hint else ""
            print(f"  - polling podi task: status={status} (remaining={remaining}s) {hint}", flush=True)
        time.sleep(interval)
        interval = min(interval * 1.4, 8.0)
    return last


def run_coze_workflow(
    *,
    name: str,
    workflow_id: str,
    parameters: dict[str, Any],
    expects_callback: bool,
    podi_base: str,
    history_timeout_s: float,
    task_timeout_s: float,
) -> list[CheckResult]:
    out: list[CheckResult] = []
    print(f"\n=== {name} ===", flush=True)
    try:
        resp = coze_client.run_workflow(workflow_id=workflow_id, parameters=parameters, is_async=True)
    except Exception as exc:
        out.append(CheckResult(f"Coze submit {name}", False, str(exc)))
        return out

    execute_id = str(resp.get("execute_id") or "").strip()
    debug_url = str(resp.get("debug_url") or "").strip()
    if not execute_id:
        out.append(CheckResult(f"Coze submit {name}", False, f"missing execute_id. resp={resp!r}"))
        return out
    out.append(CheckResult(f"Coze submit {name}", True, f"execute_id={execute_id} debug_url={debug_url}"))

    try:
        hist = _coze_poll_history(
            workflow_id=workflow_id, execute_id=execute_id, timeout_s=history_timeout_s, verbose=True
        )
    except Exception as exc:
        out.append(CheckResult(f"Coze history {name}", False, str(exc)))
        return out

    output, hist_debug = _parse_run_history_output(hist)
    out.append(CheckResult(f"Coze history {name}", True, f"output={output!r} debug_url={hist_debug or debug_url}"))

    if not expects_callback:
        # For direct-image workflows, output should include a URL somewhere; we only print.
        return out

    if not output:
        out.append(CheckResult(f"PODI task resolve {name}", False, "missing output/taskId from coze history"))
        return out

    task = _poll_podi_task_get(podi_base=podi_base, task_id=output, timeout_s=task_timeout_s, verbose=True)
    status = str(task.get("taskStatus") or "").lower()
    if status == "succeeded":
        imgs = task.get("imageUrls") or []
        out.append(CheckResult(f"PODI task resolve {name}", True, f"images={len(imgs)}"))
        return out
    out.append(CheckResult(f"PODI task resolve {name}", False, f"taskStatus={status} debug={task.get('debugResponse')!r}"))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--podi-base", default=os.environ.get("PODI_BASE_URL", "http://127.0.0.1:8099"))
    parser.add_argument("--image-url", default=os.environ.get("PREFLIGHT_TEST_IMAGE_URL", DEFAULT_TEST_IMAGE_URL))
    parser.add_argument("--skip-coze", action="store_true", help="Only run local connectivity checks")
    parser.add_argument("--only", choices=["all", "lianxu", "liebain", "liebain_1", "multi_model"], default="all")
    parser.add_argument("--history-timeout", type=float, default=420, help="Coze run_history polling timeout (seconds)")
    parser.add_argument("--task-timeout", type=float, default=900, help="PODI task polling timeout (seconds)")
    args = parser.parse_args()

    settings = get_settings()
    print(f"[{_now()}] PODI Preflight")
    print(f"- PODI_BASE: {args.podi_base}")
    print(f"- COZE_BASE_URL: {settings.coze_base_url}")
    print(f"- IMAGE_URL: {args.image_url}")
    print("")

    checks: list[CheckResult] = []
    checks.extend(check_comfyui_executors())

    if not args.skip_coze:
        # Minimal "logic pit" suite (stable mode, low count). Tune parameters as needed.
        if args.only in {"all", "lianxu"}:
            checks.extend(
                run_coze_workflow(
                    name="连续图 lianxu",
                    workflow_id="7598563505054154752",
                    parameters={"url": args.image_url, "height": "1024", "width": "1024", "patternType": "seamless"},
                    expects_callback=True,
                    podi_base=args.podi_base,
                    history_timeout_s=args.history_timeout,
                    task_timeout_s=args.task_timeout,
                )
            )
        if args.only in {"all", "liebain"}:
            checks.extend(
                run_coze_workflow(
                    name="图裂变 Liebian_comfyui_20260124",
                    workflow_id="7598820684801769472",
                    parameters={"url": args.image_url, "height": "1024", "width": "1024", "bili": "50%", "prompt": " "},
                    expects_callback=True,
                    podi_base=args.podi_base,
                    history_timeout_s=args.history_timeout,
                    task_timeout_s=args.task_timeout,
                )
            )
        if args.only in {"all", "liebain_1"}:
            checks.extend(
                run_coze_workflow(
                    name="图裂变 Liebian_comfyui_20260124_1",
                    workflow_id="7598841920114130944",
                    parameters={"url": args.image_url, "height": "1024", "width": "1024", "bili": "50%"},
                    expects_callback=True,
                    podi_base=args.podi_base,
                    history_timeout_s=args.history_timeout,
                    task_timeout_s=args.task_timeout,
                )
            )
        if args.only in {"all", "multi_model"}:
            checks.extend(
                run_coze_workflow(
                    name="多模型生图",
                    workflow_id="7597659369861283840",
                    parameters={"url": args.image_url, "height": "1024", "width": "1024", "moxing": "1", "prompt": "test"},
                    expects_callback=False,
                    podi_base=args.podi_base,
                    history_timeout_s=args.history_timeout,
                    task_timeout_s=args.task_timeout,
                )
            )

    print("\n=== Report ===")
    ok = 0
    for c in checks:
        mark = "OK" if c.ok else "FAIL"
        print(f"[{mark}] {c.name} :: {c.detail}")
        ok += 1 if c.ok else 0
    print(f"\nPassed {ok}/{len(checks)} checks")
    return 0 if ok == len(checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
