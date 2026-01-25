#!/usr/bin/env python3
"""Smoke-run all eval workflow versions against the configured Coze backend.

This is intended for dev/staging verification after updating COZE_BASE_URL / COZE_API_TOKEN.
It runs each workflow once with a minimal parameter set and prints a compact summary.

It uses the same parsing/extraction logic as the evaluation service, so we can quickly
spot: "workflow succeeded but UI shows empty output".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services.coze_client import coze_client  # noqa: E402
from app.services.eval_seed import DEFAULT_EVAL_WORKFLOW_VERSIONS  # noqa: E402
from app.services.eval_service import EvalService  # noqa: E402


def _now_slug() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _detect_kind(item: dict[str, Any]) -> str:
    schema = item.get("output_schema") or {}
    fields = schema.get("fields") if isinstance(schema, dict) else None
    if isinstance(fields, list):
        for f in fields:
            if isinstance(f, dict) and f.get("name") == "output":
                desc = str(f.get("description") or "").lower()
                if "回调" in desc or "task id" in desc or "taskid" in desc:
                    return "taskid"
                if "图片" in desc or "url" in desc:
                    return "image"
    return "unknown"


def _first_sample_url() -> str:
    # Prefer a stable repo-known OSS URL if present, otherwise require caller to set SAMPLE_IMAGE_URL.
    env_url = (os.getenv("SAMPLE_IMAGE_URL") or "").strip()
    if env_url:
        return env_url
    return "https://podi.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin/20260120/fc661480-1768882378.jpg"


def _build_params(workflow_id: str, item: dict[str, Any], sample_url: str) -> dict[str, Any]:
    # Start with schema defaults.
    params: dict[str, Any] = {"url": sample_url, "Url": sample_url, "URL": sample_url}
    schema = item.get("parameters_schema") or {}
    fields = schema.get("fields") if isinstance(schema, dict) else None
    if isinstance(fields, list):
        for f in fields:
            if not isinstance(f, dict):
                continue
            name = str(f.get("name") or "").strip()
            if not name or name in params:
                continue
            dv = f.get("defaultValue")
            if isinstance(dv, (str, int, float, bool)):
                params[name] = dv

    # Workflow-specific required knobs.
    if workflow_id == "7598563505054154752":  # lianxu
        params.setdefault("patternType", "seamless")
    if workflow_id in {"7597421439045599232", "7598559869544693760", "7598560946579046400"}:
        params.setdefault("moxing", "1")
    if workflow_id in {"7598558185544220672", "7597421439045599232", "7598560946579046400"}:
        params.setdefault("prompt", "test")
    if workflow_id == "7598589746561941504":  # dpi
        # Some Coze versions used `pdi` by mistake; send both to be safe.
        params.setdefault("dpi", "300")
        params.setdefault("pdi", params.get("dpi"))
    # outpaint comfyui
    if workflow_id == "7598587935331450880":
        params.setdefault("expand_left", "0")
        params.setdefault("expand_right", "0")
        params.setdefault("expand_top", "0")
        params.setdefault("expand_bottom", "0")
    if workflow_id == "7597659369861283840":  # multi_model_gen
        params.setdefault("prompt", "test")
    # 图裂变 (required bili; some variants also require prompt / moxing)
    if workflow_id in {"7598820684801769472", "7598841920114130944", "7598844004557389824", "7598848725942796288"}:
        params.setdefault("bili", "50%")
    if workflow_id in {"7598844004557389824", "7598848725942796288"}:
        params.setdefault("moxing", "1")
    if workflow_id in {"7598820684801769472", "7598848725942796288"}:
        params.setdefault("prompt", "test")
    return params


def _coze_failed(resp: dict[str, Any]) -> str | None:
    base_resp = resp.get("BaseResp") or {}
    status_code = base_resp.get("StatusCode")
    code = resp.get("code")
    if (isinstance(code, int) and code != 0) or (isinstance(status_code, int) and status_code != 0):
        msg = resp.get("msg") or base_resp.get("StatusMessage") or "COZE_EXECUTION_FAILED"
        return f"code={code} statusCode={status_code} msg={msg}"
    return None


@dataclass
class Result:
    name: str
    workflow_id: str
    category: str
    kind: str
    ok: bool
    duration_ms: int
    debug_url: str | None
    output: Any
    image_urls: list[str]
    error: str | None


def run_one(item: dict[str, Any], sample_url: str, *, poll_callback: bool = True) -> Result:
    workflow_id = str(item.get("workflow_id") or "").strip()
    name = str(item.get("name") or workflow_id)
    category = str(item.get("category") or "")
    kind = _detect_kind(item)
    params = _build_params(workflow_id, item, sample_url)

    started = time.monotonic()
    resp = coze_client.run_workflow(workflow_id=workflow_id, parameters=params, is_async=False)
    duration_ms = int((time.monotonic() - started) * 1000)
    debug_url = resp.get("debug_url") if isinstance(resp, dict) else None
    failed = _coze_failed(resp) if isinstance(resp, dict) else "COZE_RESPONSE_INVALID"
    if failed:
        return Result(
            name=name,
            workflow_id=workflow_id,
            category=category,
            kind=kind,
            ok=False,
            duration_ms=duration_ms,
            debug_url=str(debug_url) if debug_url else None,
            output=None,
            image_urls=[],
            error=failed,
        )

    parsed = EvalService._parse_coze_payload(resp)  # noqa: SLF001 - smoke script
    output = parsed.get("output") if isinstance(parsed, dict) else None
    image_urls = EvalService._extract_image_urls(parsed if isinstance(parsed, dict) else {"output": parsed})  # noqa: SLF001

    # If we expect taskid, resolve via PODI task polling (preferred; no separate Coze callback).
    if poll_callback and kind == "taskid" and isinstance(output, str) and output.strip():
        podi_base = (os.getenv("PODI_BASE_URL") or "http://127.0.0.1:8099").rstrip("/")
        cb_started = time.monotonic()
        deadline = cb_started + 900.0
        interval = 2.0
        last: dict[str, Any] = {}
        first_failed_at: float | None = None
        while time.monotonic() < deadline and not image_urls:
            try:
                r = httpx.post(f"{podi_base}/api/coze/podi/tasks/get", json={"taskId": output.strip()}, timeout=25)
                last = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text}
            except Exception:
                last = {}
            status = str(last.get("taskStatus") or "").lower()
            if status == "succeeded":
                urls = last.get("imageUrls")
                if isinstance(urls, list):
                    image_urls = [u for u in urls if isinstance(u, str) and u.strip()]
                    if image_urls:
                        break
            if status == "failed":
                if first_failed_at is None:
                    first_failed_at = time.monotonic()
                # Allow a short grace period in case the backend revived a ComfyUI submit-only task
                # (some tasks may be marked failed too early and then corrected on the next poll).
                if time.monotonic() - first_failed_at > 60:
                    break
            time.sleep(interval)
            interval = min(interval * 1.4, 8.0)
        duration_ms += int((time.monotonic() - cb_started) * 1000)

    ok = bool(image_urls) if kind in {"image", "taskid"} else True
    return Result(
        name=name,
        workflow_id=workflow_id,
        category=category,
        kind=kind,
        ok=ok,
        duration_ms=duration_ms,
        debug_url=str(debug_url) if debug_url else None,
        output=output,
        image_urls=image_urls,
        error=None if ok else "OUTPUT_EMPTY",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not call Coze; only print each workflow's input params (from schema) and expected output kind.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional report output path (json). Default: reports/eval_workflow_smoke_<ts>.json",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not args.dry_run:
        missing = []
        if not (settings.coze_base_url or "").strip():
            missing.append("COZE_BASE_URL")
        if not ((settings.coze_api_token or settings.service_api_token) or "").strip():
            missing.append("COZE_API_TOKEN/SERVICE_API_TOKEN")
        if missing:
            print(f"missing env: {', '.join(missing)}")
            return 2

    sample_url = _first_sample_url()
    items = [i for i in DEFAULT_EVAL_WORKFLOW_VERSIONS if str(i.get("status") or "") != "inactive"]

    results: list[Result] = []
    for item in items:
        if args.dry_run:
            workflow_id = str(item.get("workflow_id") or "").strip()
            r = Result(
                name=str(item.get("name") or ""),
                workflow_id=workflow_id,
                category=str(item.get("category") or ""),
                kind=_detect_kind(item),
                ok=True,
                duration_ms=0,
                debug_url=None,
                output=_build_params(workflow_id, item, sample_url),
                image_urls=[],
                error=None,
            )
        else:
            try:
                r = run_one(item, sample_url)
            except Exception as exc:
                r = Result(
                    name=str(item.get("name") or ""),
                    workflow_id=str(item.get("workflow_id") or ""),
                    category=str(item.get("category") or ""),
                    kind=_detect_kind(item),
                    ok=False,
                    duration_ms=0,
                    debug_url=None,
                    output=None,
                    image_urls=[],
                    error=f"EXCEPTION:{exc}",
                )
        results.append(r)
        status = "OK" if r.ok else "FAIL"
        if args.dry_run:
            print(f"[{status}] {r.name} {r.workflow_id} category={r.category} kind={r.kind}")
            print(json.dumps(r.output or {}, ensure_ascii=False, indent=2))
        else:
            print(f"[{status}] {r.name} {r.workflow_id} kind={r.kind} ms={r.duration_ms} urls={len(r.image_urls)} err={r.error or '-'}")
            if not r.ok and r.debug_url:
                print(f"  debug_url={r.debug_url}")

    report_dir = REPO / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out).expanduser() if args.out else (report_dir / f"eval_workflow_smoke_{_now_slug()}.json")
    out_path.write_text(
        json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nreport: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
