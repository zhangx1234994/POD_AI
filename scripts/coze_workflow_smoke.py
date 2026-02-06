#!/usr/bin/env python3
"""Smoke test all active Coze workflows using local eval docs schema."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib import request as urllib_request
from urllib import error as urllib_error

DEFAULT_DOCS_URL = "http://127.0.0.1:8099/api/evals/docs/workflows"
DEFAULT_UPLOAD_URL = "http://127.0.0.1:8099/api/evals/uploads"
DEFAULT_TASK_GET_URL = "http://127.0.0.1:8099/api/coze/podi/tasks/get"
DEFAULT_IMAGE_PATH = ""

IP_OUTPUT_WORKFLOW_IDS = {
    "7597530887256801280",
    "7598545860393172992",
    "7598560946579046400",
    "7598563505054154752",
    "7598587935331450880",
    "7597701996124045312",
    "7597702948247830528",
    "7598841920114130944",
    "7598820684801769472",
}


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
    with urllib_request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    return json.loads(raw)


def upload_image(upload_url: str, image_path: Path) -> str:
    boundary = "----podi-smoke-boundary"
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
    with urllib_request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    data = json.loads(raw)
    url = data.get("url")
    if not isinstance(url, str) or not url:
        raise RuntimeError("upload failed: missing url")
    return url


def build_params(fields: List[Dict[str, Any]], image_url: str, size: int) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for f in fields:
        name = str(f.get("name") or "").strip()
        if not name:
            continue
        ftype = str(f.get("type") or "text").lower()
        required = bool(f.get("required"))
        default = f.get("defaultValue")
        options = f.get("options") if isinstance(f.get("options"), list) else []

        key_lower = name.lower()
        if key_lower in {"url", "image_url", "imageurl"}:
            params[name] = image_url
            continue
        if key_lower in {"height", "width", "expand_left", "expand_right", "expand_top", "expand_bottom"}:
            params[name] = str(size)
            continue
        if key_lower in {"dpi", "pdi"}:
            params[name] = "300"
            continue
        if key_lower in {"bianchang", "max_long_edge"}:
            params[name] = "2048"
            continue
        if key_lower in {"bili", "similarity"}:
            params[name] = "50%"
            continue
        if key_lower in {"patterntype", "pattern_type"}:
            params[name] = "seamless"
            continue
        if key_lower in {"prompt", "positive_prompt", "description"}:
            params[name] = "test prompt"
            continue
        if key_lower in {"negative_prompt"}:
            params[name] = ""
            continue
        if key_lower in {"moxing", "model"}:
            params[name] = "1"
            continue

        if ftype == "select":
            if default not in (None, ""):
                params[name] = default
                continue
            if options:
                first = options[0]
                if isinstance(first, dict):
                    params[name] = first.get("value") or first.get("label")
                else:
                    params[name] = str(first)
                continue

        if default not in (None, ""):
            params[name] = default
            continue

        if required:
            params[name] = "<required>"

    return params


def parse_coze_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {"output": data}
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and data:
        last = data[-1]
        if isinstance(last, dict):
            out = last.get("output")
            run_status = last.get("execute_status") or last.get("executeStatus") or last.get("status")
            debug_url = last.get("debug_url") or last.get("debugUrl")
            error_msg = last.get("error_msg") or last.get("errorMsg")
            parsed_out: Dict[str, Any] | None = None
            if isinstance(out, str):
                try:
                    maybe = json.loads(out)
                    parsed_out = maybe if isinstance(maybe, dict) else {"output": maybe}
                except Exception:
                    parsed_out = {"output": out}
            elif isinstance(out, dict):
                parsed_out = out
            elif out is not None:
                parsed_out = {"output": out}
            if isinstance(parsed_out, dict):
                if run_status is not None and "run_status" not in parsed_out and "status" not in parsed_out:
                    parsed_out["run_status"] = run_status
                if debug_url and "debug_url" not in parsed_out:
                    parsed_out["debug_url"] = debug_url
                if error_msg and "error_msg" not in parsed_out:
                    parsed_out["error_msg"] = error_msg
                return parsed_out
    return payload if isinstance(payload, dict) else {}


def run_workflow(base_url: str, token: str, workflow_id: str, params: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/v1/workflow/run"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        data = http_json(url, {"workflow_id": workflow_id, "parameters": params}, headers=headers)
        return 200, data
    except urllib_error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload = {"error": exc.read().decode("utf-8", errors="ignore")}
        return exc.code, payload
    except Exception as exc:
        return 0, {"error": str(exc)}


def poll_task(task_get_url: str, service_token: str | None, task_id: str, max_wait: int) -> Dict[str, Any]:
    deadline = time.time() + max_wait
    headers = {}
    if service_token:
        headers["Authorization"] = f"Bearer {service_token}"
    last: Dict[str, Any] = {}
    while time.time() < deadline:
        try:
            last = http_json(task_get_url, {"taskId": task_id}, headers=headers)
        except Exception as exc:
            last = {"error": str(exc)}
        status = str(last.get("taskStatus") or "").lower()
        if status in {"succeeded", "failed"}:
            return last
        time.sleep(3)
    return last


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-url", default=DEFAULT_DOCS_URL)
    parser.add_argument("--upload-url", default=DEFAULT_UPLOAD_URL)
    parser.add_argument("--task-url", default=DEFAULT_TASK_GET_URL)
    parser.add_argument("--image", default=DEFAULT_IMAGE_PATH)
    parser.add_argument("--image-url", default="")
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--poll", type=int, default=30, help="max seconds to poll callback tasks")
    parser.add_argument("--out", default="")
    parser.add_argument("--workflow-id", action="append", default=[])
    args = parser.parse_args()

    env = load_env(Path("backend/.env"))
    base_url = env.get("COZE_BASE_URL") or os.getenv("COZE_BASE_URL") or ""
    token = env.get("COZE_API_TOKEN") or env.get("COZE_PAT") or os.getenv("COZE_API_TOKEN") or os.getenv("COZE_PAT") or ""
    service_token = env.get("SERVICE_API_TOKEN") or os.getenv("SERVICE_API_TOKEN")

    if not base_url or not token:
        print("Missing COZE_BASE_URL or COZE_API_TOKEN/COZE_PAT in backend/.env", file=sys.stderr)
        return 2

    image_url = args.image_url
    if not image_url:
        if not args.image:
            print("Missing image input; pass --image <path> or --image-url <url>.", file=sys.stderr)
            return 2
        image_path = Path(args.image)
        if not image_path.exists():
            print(f"Image not found: {image_path}", file=sys.stderr)
            return 2
        image_url = upload_image(args.upload_url, image_path)

    docs = http_json(args.docs_url)
    workflows = docs.get("workflows") or []
    if args.workflow_id:
        wanted = {w.strip() for w in args.workflow_id if w.strip()}
        workflows = [w for w in workflows if str(w.get("workflow_id")) in wanted]

    callback_taskid = os.getenv("COZE_CALLBACK_TASKID") or env.get("COZE_CALLBACK_TASKID") or ""

    results: List[Dict[str, Any]] = []
    for wf in workflows:
        workflow_id = str(wf.get("workflow_id") or "")
        name = str(wf.get("name") or "")
        output_kind = str(wf.get("output_kind") or "")
        if workflow_id == "7597556718159003648" and not callback_taskid:
            results.append(
                {
                    "workflow_id": workflow_id,
                    "name": name,
                    "status_code": 0,
                    "param_mismatch": False,
                    "output_kind": output_kind,
                    "output": None,
                    "ip": None,
                    "prompt": None,
                    "error": "SKIPPED (set COZE_CALLBACK_TASKID to test)",
                    "task": None,
                    "params": {},
                }
            )
            continue
        params = build_params(wf.get("parameters") or [], image_url, args.size)
        if workflow_id == "7597556718159003648" and callback_taskid:
            params["taskid"] = callback_taskid
        status_code, payload = run_workflow(base_url, token, workflow_id, params)
        parsed = parse_coze_data(payload if isinstance(payload, dict) else {})
        output = parsed.get("output")
        ip = parsed.get("ip")
        prompt = parsed.get("prompt")
        error_msg = parsed.get("error_msg") if isinstance(parsed, dict) else None
        if not error_msg and isinstance(payload, dict):
            error_msg = payload.get("msg") or payload.get("message")
        param_mismatch = False
        if status_code != 200:
            param_mismatch = True
        if isinstance(error_msg, str) and "Missing required" in error_msg:
            param_mismatch = True
        if output_kind == "callback_task_id" and not (isinstance(output, str) and output.strip()):
            param_mismatch = True
        if workflow_id in IP_OUTPUT_WORKFLOW_IDS and not ip:
            param_mismatch = True

        task_result: Dict[str, Any] | None = None
        if output_kind == "callback_task_id" and isinstance(output, str) and output.strip():
            task_result = poll_task(args.task_url, service_token, output.strip(), args.poll)

        results.append(
            {
                "workflow_id": workflow_id,
                "name": name,
                "status_code": status_code,
                "param_mismatch": param_mismatch,
                "output_kind": output_kind,
                "output": output,
                "ip": ip,
                "prompt": prompt,
                "error": error_msg,
                "task": task_result,
                "params": params,
            }
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = args.out or f"reports/coze_workflow_smoke_{timestamp}.md"
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# Coze 工作流冒烟测试 {timestamp}")
    lines.append("")
    lines.append(f"- Coze Base URL: {base_url}")
    lines.append(f"- Image URL: {image_url}")
    lines.append("")
    lines.append("| workflow_id | 名称 | HTTP | 期望输出 | 回调ID | ip | 任务状态 | 参数一致 | 错误 |")
    lines.append("|---|---|---:|---|---|---|---|---|---|")
    for item in results:
        task_status = ""
        if isinstance(item.get("task"), dict):
            task_status = str(item["task"].get("taskStatus") or item["task"].get("error") or "")
        lines.append(
            "| {workflow_id} | {name} | {status_code} | {output_kind} | {output} | {ip} | {task_status} | {param_ok} | {error} |".format(
                workflow_id=item.get("workflow_id"),
                name=item.get("name"),
                status_code=item.get("status_code"),
                output_kind=item.get("output_kind"),
                output=str(item.get("output") or "")[:64],
                ip=str(item.get("ip") or "")[:24],
                task_status=task_status[:24],
                param_ok="否" if item.get("param_mismatch") else "是",
                error=str(item.get("error") or "")[:64],
            )
        )
    lines.append("")

    with out_file.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    json_path = out_file.with_suffix(".json")
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(str(out_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
