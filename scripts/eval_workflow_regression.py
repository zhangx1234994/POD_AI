#!/usr/bin/env python3
"""Regression runner for eval workflows (Coze) with multiple parameter variants.

Runs each active workflow from /api/evals/docs/workflows with 3 parameter sets:
- normal (common sizes)
- high (higher sizes)
- extreme (stress/boundary sizes)

It records durations, output status, and error samples.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib import error as urllib_error
from urllib import request as urllib_request

REPO = Path(__file__).resolve().parents[1]
BACKEND_ENV = REPO / "backend" / ".env"

# Add backend for EvalService helpers (output parsing / image url extraction).
sys.path.insert(0, str(REPO / "backend"))
from app.services.eval_service import EvalService  # noqa: E402

DEFAULT_DOCS_URL = "http://127.0.0.1:8099/api/evals/docs/workflows"
DEFAULT_UPLOAD_URL = "http://127.0.0.1:8099/api/evals/uploads"
DEFAULT_TASK_GET_URL = "http://127.0.0.1:8099/api/coze/podi/tasks/get"

DEFAULT_IMAGE_PATHS = [
    "tmp/expand_mask_preview.png",
    "tmp/upscale_2048.png",
    "tmp/set_dpi_300.jpg",
    "tmp/expand_mask_test.png",
]

INTERNAL_FIELDS = {"count", "generatecount", "variantcount", "n"}

SIZE_MAP = {
    "normal": 1024,
    "high": 2048,
    "extreme": 4096,
}
EXPAND_MAP = {
    "normal": 0,
    "high": 256,
    "extreme": 512,
}
DPI_MAP = {
    "normal": 300,
    "high": 600,
    "extreme": 1200,
}
BILI_MAP = {
    "normal": "50%",
    "high": "70%",
    "extreme": "90%",
}
PROMPT_MAP = {
    "normal": "test prompt",
    "high": "high detail seamless texture, clean edges",
    "extreme": "ultra detailed, complex high-frequency pattern, sharp edges",
}
PATTERN_MAP = {
    "normal": "seamless",
    "high": "twoway",
    "extreme": "seamless",
}


def _now_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, val = raw.split("=", 1)
        env[key.strip()] = val.strip()
    return env


def http_json(url: str, payload: Dict[str, Any] | None = None, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url, data=data, headers=headers or {})
    req.add_header("Content-Type", "application/json")
    with urllib_request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
    return json.loads(raw)


def upload_image(upload_url: str, image_path: Path) -> str:
    boundary = "----podi-regression-boundary"
    content = image_path.read_bytes()
    filename = image_path.name
    lines: List[bytes] = []
    lines.append(f"--{boundary}".encode())
    lines.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode())
    lines.append(b"Content-Type: image/png")
    lines.append(b"")
    lines.append(content)
    lines.append(f"--{boundary}--".encode())
    body = b"\r\n".join(lines)

    req = urllib_request.Request(upload_url, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib_request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
    data = json.loads(raw)
    url = data.get("url")
    if not isinstance(url, str) or not url:
        raise RuntimeError("upload failed: missing url")
    return url


def choose_option(field: Dict[str, Any], variant: str) -> Any:
    options = field.get("options") if isinstance(field.get("options"), list) else []
    default = field.get("defaultValue")
    if variant == "normal":
        if default not in (None, ""):
            return default
        if options:
            return _option_value(options[0])
        return default

    if not options:
        return default
    if variant == "high":
        idx = min(1, len(options) - 1)
        return _option_value(options[idx])
    # extreme
    return _option_value(options[-1])


def _option_value(option: Any) -> Any:
    if isinstance(option, dict):
        return option.get("value") or option.get("label")
    return option


def build_params(fields: List[Dict[str, Any]], image_url: str | None, variant: str) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    size = SIZE_MAP[variant]
    expand = EXPAND_MAP[variant]
    dpi = DPI_MAP[variant]
    bili = BILI_MAP[variant]
    prompt = PROMPT_MAP[variant]
    pattern = PATTERN_MAP[variant]

    for f in fields:
        name = str(f.get("name") or "").strip()
        if not name:
            continue
        key_lower = name.lower()
        if key_lower in INTERNAL_FIELDS:
            continue
        ftype = str(f.get("type") or "text").lower()
        required = bool(f.get("required"))
        default = f.get("defaultValue")

        if key_lower in {"url", "image_url", "imageurl"}:
            if image_url:
                params[name] = image_url
                continue
        if key_lower in {"height", "width", "bianchang", "max_long_edge"}:
            params[name] = str(size)
            continue
        if key_lower in {"expand_left", "expand_right", "expand_top", "expand_bottom"}:
            params[name] = str(expand)
            continue
        if key_lower in {"dpi", "pdi"}:
            params[name] = str(dpi)
            continue
        if key_lower in {"bili", "similarity"}:
            params[name] = bili
            continue
        if key_lower in {"patterntype", "pattern_type"}:
            params[name] = pattern
            continue
        if key_lower in {"prompt", "positive_prompt", "description"}:
            params[name] = prompt
            continue
        if key_lower in {"negative_prompt"}:
            params[name] = ""
            continue
        if key_lower in {"moxing", "model"}:
            params[name] = "1"
            continue

        if ftype == "select":
            choice = choose_option(f, variant)
            if choice not in (None, ""):
                params[name] = choice
                continue

        if default not in (None, ""):
            params[name] = default
            continue

        if required:
            # Best-effort fallback for required fields.
            if key_lower in {"resolution", "aspect_ratio", "lora"}:
                choice = choose_option(f, variant)
                if choice not in (None, ""):
                    params[name] = choice
                else:
                    params[name] = "1"
            elif key_lower.endswith("ratio"):
                params[name] = "1:1"
            else:
                params[name] = "1"

    return params


def coze_failed(payload: Dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return "COZE_RESPONSE_INVALID"
    base_resp = payload.get("BaseResp") or {}
    status_code = base_resp.get("StatusCode")
    code = payload.get("code")
    if (isinstance(code, int) and code != 0) or (isinstance(status_code, int) and status_code != 0):
        msg = payload.get("msg") or base_resp.get("StatusMessage") or "COZE_EXECUTION_FAILED"
        return f"code={code} statusCode={status_code} msg={msg}"
    return None


def output_error(output: Any) -> str | None:
    if isinstance(output, str):
        value = output.strip()
        if value.startswith("ERR|"):
            return value
        if value.lower().startswith("error"):
            return value
    if isinstance(output, dict):
        msg = output.get("error") or output.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()
    return None


def run_workflow(base_url: str, token: str, workflow_id: str, params: Dict[str, Any]) -> Tuple[int, Dict[str, Any], int]:
    url = f"{base_url.rstrip('/')}/v1/workflow/run"
    headers = {"Authorization": f"Bearer {token}"}
    started = time.monotonic()
    try:
        data = http_json(url, {"workflow_id": workflow_id, "parameters": params}, headers=headers)
        duration_ms = int((time.monotonic() - started) * 1000)
        return 200, data, duration_ms
    except urllib_error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload = {"error": exc.read().decode("utf-8", errors="ignore")}
        duration_ms = int((time.monotonic() - started) * 1000)
        return exc.code, payload, duration_ms
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return 0, {"error": str(exc)}, duration_ms


def poll_task(task_get_url: str, service_token: str | None, task_id: str, max_wait: int) -> Tuple[Dict[str, Any], int]:
    deadline = time.time() + max_wait
    headers = {}
    if service_token:
        headers["Authorization"] = f"Bearer {service_token}"
    last: Dict[str, Any] = {}
    started = time.monotonic()
    while time.time() < deadline:
        try:
            last = http_json(task_get_url, {"taskId": task_id}, headers=headers)
        except Exception as exc:
            last = {"error": str(exc)}
        status = str(last.get("taskStatus") or "").lower()
        if status in {"succeeded", "failed"}:
            break
        time.sleep(3)
    if str(last.get("taskStatus") or "").lower() not in {"succeeded", "failed"}:
        last = dict(last)
        last["poll_timeout"] = True
    duration_ms = int((time.monotonic() - started) * 1000)
    return last, duration_ms


def _image_urls(parsed: Dict[str, Any]) -> List[str]:
    try:
        return EvalService._extract_image_urls(parsed)
    except Exception:
        return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-url", default=DEFAULT_DOCS_URL)
    parser.add_argument("--upload-url", default=DEFAULT_UPLOAD_URL)
    parser.add_argument("--task-url", default=DEFAULT_TASK_GET_URL)
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--variants", default="normal,high,extreme")
    parser.add_argument("--poll", type=int, default=600, help="max seconds to poll callback tasks")
    parser.add_argument("--out", default="")
    parser.add_argument("--workflow-id", action="append", default=[])
    parser.add_argument("--max-workflows", type=int, default=0)
    parser.add_argument("--callback-taskid", default="")
    args = parser.parse_args()

    env = load_env(BACKEND_ENV)
    base_url = env.get("COZE_BASE_URL") or os.getenv("COZE_BASE_URL") or ""
    token = env.get("COZE_API_TOKEN") or env.get("COZE_PAT") or os.getenv("COZE_API_TOKEN") or os.getenv("COZE_PAT") or ""
    service_token = env.get("SERVICE_API_TOKEN") or os.getenv("SERVICE_API_TOKEN")

    if not base_url or not token:
        print("Missing COZE_BASE_URL or COZE_API_TOKEN/COZE_PAT in backend/.env", file=sys.stderr)
        return 2

    image_paths = [Path(p) for p in (args.image or [])]
    if not image_paths:
        image_paths = [REPO / p for p in DEFAULT_IMAGE_PATHS]

    image_urls: List[str] = []
    for path in image_paths:
        if not path.exists():
            continue
        try:
            image_urls.append(upload_image(args.upload_url, path))
        except Exception as exc:
            print(f"Image upload failed: {path} ({exc})", file=sys.stderr)
    if not image_urls:
        print("No image URLs available; workflows requiring URL may fail.", file=sys.stderr)

    docs = http_json(args.docs_url)
    workflows = docs.get("workflows") or []
    if args.workflow_id:
        wanted = {w.strip() for w in args.workflow_id if w.strip()}
        workflows = [w for w in workflows if str(w.get("workflow_id")) in wanted]
    if args.max_workflows and args.max_workflows > 0:
        workflows = workflows[: args.max_workflows]

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    callback_taskid = args.callback_taskid or os.getenv("COZE_CALLBACK_TASKID") or env.get("COZE_CALLBACK_TASKID") or ""

    results: List[Dict[str, Any]] = []
    for idx, wf in enumerate(workflows):
        workflow_id = str(wf.get("workflow_id") or "")
        name = str(wf.get("name") or "")
        output_kind = str(wf.get("output_kind") or "")
        fields = wf.get("parameters") or []

        for v_idx, variant in enumerate(variants):
            image_url = image_urls[(idx + v_idx) % len(image_urls)] if image_urls else ""
            if workflow_id == "7597556718159003648" and not callback_taskid:
                results.append(
                    {
                        "workflow_id": workflow_id,
                        "name": name,
                        "variant": variant,
                        "status_code": 0,
                        "output_kind": output_kind,
                        "error": "SKIPPED (set COZE_CALLBACK_TASKID to test callback workflow)",
                        "params": {},
                        "durations_ms": {"request": 0, "task_poll": 0, "total": 0},
                    }
                )
                continue

            params = build_params(fields, image_url, variant)
            if workflow_id == "7597556718159003648" and callback_taskid:
                params["taskid"] = callback_taskid

            status_code, payload, request_ms = run_workflow(base_url, token, workflow_id, params)
            parsed = EvalService._parse_coze_payload(payload if isinstance(payload, dict) else {})
            output = parsed.get("output") if isinstance(parsed, dict) else None
            debug_url = parsed.get("debug_url") if isinstance(parsed, dict) else None
            error_msg = parsed.get("error_msg") if isinstance(parsed, dict) else None
            if not error_msg and isinstance(payload, dict):
                error_msg = payload.get("msg") or payload.get("message")
            failed_reason = coze_failed(payload if isinstance(payload, dict) else None)
            output_err = output_error(output)
            if output_err and not error_msg:
                error_msg = output_err

            image_urls_out = _image_urls(parsed if isinstance(parsed, dict) else {"output": parsed})
            task_result = None
            task_poll_ms = 0
            task_status = None
            if output_kind == "callback_task_id" and isinstance(output, str) and output.strip() and not output_err:
                task_result, task_poll_ms = poll_task(args.task_url, service_token, output.strip(), args.poll)
                task_status = task_result.get("taskStatus") if isinstance(task_result, dict) else None
                if isinstance(task_result, dict):
                    urls = task_result.get("imageUrls")
                    if isinstance(urls, list):
                        image_urls_out = [u for u in urls if isinstance(u, str) and u.strip()]
                    if task_result.get("poll_timeout") and not error_msg:
                        error_msg = "TASK_POLL_TIMEOUT"

            total_ms = request_ms + task_poll_ms
            if not error_msg and not failed_reason:
                if output_kind == "callback_task_id" and not image_urls_out:
                    error_msg = "OUTPUT_EMPTY"
                elif output_kind == "image_url" and not (image_urls_out or output):
                    error_msg = "OUTPUT_EMPTY"
            results.append(
                {
                    "workflow_id": workflow_id,
                    "name": name,
                    "variant": variant,
                    "status_code": status_code,
                    "output_kind": output_kind,
                    "params": params,
                    "output": output,
                    "debug_url": debug_url,
                    "error": error_msg or failed_reason,
                    "task_status": task_status,
                    "task_result": task_result,
                    "image_urls": image_urls_out,
                    "durations_ms": {"request": request_ms, "task_poll": task_poll_ms, "total": total_ms},
                }
            )

            ok = (status_code == 200) and not (error_msg or failed_reason)
            if output_kind == "callback_task_id":
                ok = ok and bool(image_urls_out)
            elif output_kind == "image_url":
                ok = ok and bool(image_urls_out or output)
            print(
                f"[{ 'OK' if ok else 'FAIL' }] {name} {workflow_id} variant={variant} ms={total_ms} images={len(image_urls_out)} err={error_msg or failed_reason or '-'}"
            )

    timestamp = _now_slug()
    out_path = Path(args.out) if args.out else (REPO / "reports" / "regression" / f"workflow_run_{timestamp}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown report
    md_path = out_path.with_suffix(".md")
    lines = []
    lines.append(f"# Eval workflow regression {timestamp}")
    lines.append("")
    lines.append(f"- Coze Base URL: {base_url}")
    lines.append(f"- Docs URL: {args.docs_url}")
    lines.append(f"- Variants: {', '.join(variants)}")
    lines.append(f"- Image URLs: {', '.join(image_urls)}")
    lines.append("")
    lines.append("| workflow_id | 名称 | variant | HTTP | 输出类型 | 总耗时(ms) | 图片数 | task | 错误 |")
    lines.append("|---|---|---|---:|---|---:|---:|---|---|")
    for item in results:
        lines.append(
            "| {workflow_id} | {name} | {variant} | {status_code} | {output_kind} | {total} | {images} | {task} | {error} |".format(
                workflow_id=item.get("workflow_id"),
                name=item.get("name"),
                variant=item.get("variant"),
                status_code=item.get("status_code"),
                output_kind=item.get("output_kind"),
                total=item.get("durations_ms", {}).get("total"),
                images=len(item.get("image_urls") or []),
                task=str(item.get("task_status") or ""),
                error=str(item.get("error") or "")[:80],
            )
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nreport: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
