#!/usr/bin/env python3
"""Run smoke tests for Coze workflows and persist results to a JSON report.

This script is designed for the internal PODI workflow evaluation setup:
- Uploads local sample images to OSS (so Coze can fetch them).
- Calls Coze `/v1/workflow/run` for each workflow under multiple parameter sets.
- For workflows that output a ComfyUI task id, optionally resolves images via a callback workflow.

Environment (recommended):
- COZE_BASE_URL, COZE_API_TOKEN
- OSS_ACCESS_KEY/OSS_SECRET_KEY (and OSS_PUBLIC_DOMAIN/OSS_DOWNLOAD_DOMAIN)
- COZE_COMFYUI_CALLBACK_WORKFLOW_ID (optional; defaults to comfyui_huidiao if known)

Usage:
  python3 scripts/workflow_smoke_test.py --backend http://127.0.0.1:8099
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


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.coze_client import coze_client  # noqa: E402
from app.services.oss import oss_service  # noqa: E402


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_local_images(limit: int = 6) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    candidates: list[Path] = []
    for p in REPO_ROOT.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            candidates.append(p)
    # Also look under common folders.
    for folder in ("docs", "assets", "testdata", "tests", "提取测试图"):
        d = REPO_ROOT / folder
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                candidates.append(p)
    # de-dup + stable order
    seen: set[str] = set()
    out: list[Path] = []
    for p in candidates:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= limit:
            break
    return out


def _guess_content_type(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return None


def upload_samples(user_id: str, max_images: int = 3) -> list[str]:
    images = _find_local_images(limit=max_images)
    if not images:
        raise RuntimeError(
            f"No local images found under {REPO_ROOT}. Put a few .jpg/.png files in repo root (or docs/)."
        )
    urls: list[str] = []
    for img in images:
        data = img.read_bytes()
        uploaded = oss_service.upload_bytes(
            user_id=user_id,
            filename=img.name,
            data=data,
            content_type=_guess_content_type(img),
        )
        urls.append(str(uploaded["url"]))
    return urls


def parse_coze_data(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract the actual workflow output payload.

    Coze returns:
    - top-level: { code, msg, data: "<json-string>" }
    - and the inner JSON string can itself contain { output: "...", ... }.
    """
    raw = payload.get("data")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return {"output": raw}
        except Exception:
            return {"output": raw}
    if isinstance(raw, dict):
        return raw
    # fallback: some deployments may return the final data directly in payload
    if isinstance(payload, dict) and "output" in payload:
        return payload
    return {}


def extract_output_text(parsed_data: dict[str, Any]) -> str | None:
    out = parsed_data.get("output")
    if isinstance(out, str) and out.strip():
        return out.strip()
    return None


def extract_images_from_callback(parsed_data: dict[str, Any]) -> list[str]:
    images = parsed_data.get("images")
    out: list[str] = []
    if isinstance(images, list):
        for it in images:
            if isinstance(it, str) and it.startswith(("http://", "https://")):
                out.append(it)
            elif isinstance(it, dict):
                for k in ("url", "ossUrl", "sourceUrl"):
                    v = it.get(k)
                    if isinstance(v, str) and v.startswith(("http://", "https://")):
                        out.append(v)
                        break
    # de-dup
    seen: set[str] = set()
    dedup: list[str] = []
    for u in out:
        if u in seen:
            continue
        seen.add(u)
        dedup.append(u)
    return dedup


@dataclass
class WorkflowSpec:
    key: str
    name: str
    workflow_id: str
    category: str
    kind: str  # "text" | "image" | "taskid"


WORKFLOWS: list[WorkflowSpec] = [
    WorkflowSpec(
        key="tishici_tiqu",
        name="提示词提取",
        workflow_id="7597535455856295936",
        category="general",
        kind="text",
    ),
    WorkflowSpec(
        key="tiqu_comfyui",
        name="ComfyUI 花纹提取",
        workflow_id="7597530887256801280",
        category="pattern_extract",
        kind="taskid",
    ),
    WorkflowSpec(
        key="multi_model_gen",
        name="多模型生图",
        workflow_id="7597659369861283840",
        category="image_variation",
        kind="image",
    ),
    WorkflowSpec(
        key="comfyui_4steps",
        name="四步急速生图",
        workflow_id="7597701996124045312",
        category="image_variation",
        kind="taskid",
    ),
    WorkflowSpec(
        key="comfyui_8steps",
        name="八步急速生图",
        workflow_id="7597702948247830528",
        category="image_variation",
        kind="taskid",
    ),
    WorkflowSpec(
        key="expand_multi_model",
        name="扩图多模型版本",
        workflow_id="7597723984687267840",
        category="image_extend",
        kind="image",
    ),
    WorkflowSpec(
        key="upscale_8k",
        name="8K 高清放大",
        workflow_id="7597760543788630016",
        category="general",
        kind="image",
    ),
]


def build_cases(urls: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Return mapping workflow.key -> list of parameter dicts."""
    url = urls[0]
    alt_url = urls[1] if len(urls) > 1 else url
    cases: dict[str, list[dict[str, Any]]] = {}

    cases["tishici_tiqu"] = [
        {"url": url},
        {"url": url, "shuru": "把图里主要元素描述出来（可为空）"},
    ]

    cases["tiqu_comfyui"] = [
        {"url": url},
        {"url": alt_url, "width": "1200", "height": "1200", "lora": ""},
    ]

    cases["multi_model_gen"] = [
        {"url": url, "prompt": "把图片转成线稿风格", "moxing": "1", "resolution": "1K", "aspect_ratio": "auto"},
        {"url": url, "prompt": "把图片转成线稿风格", "moxing": "2", "resolution": "1K", "aspect_ratio": "1:1"},
        {"url": url, "prompt": "把图片转成线稿风格", "moxing": "3", "width": "1200", "height": "1200"},
    ]

    cases["comfyui_4steps"] = [
        {"url": url, "prompt": "把图片转成线稿风格", "width": "1200", "height": "1200"},
    ]

    cases["comfyui_8steps"] = [
        {"url": url, "prompt": "把图片转成线稿风格", "width": "1200", "height": "1200"},
    ]

    cases["expand_multi_model"] = [
        {
            "url": url,
            "Url": url,
            "expand_left": "200",
            "expand_right": "200",
            "expand_top": "0",
            "expand_bottom": "0",
            "moxing": "1",
        },
        {
            "url": url,
            "Url": url,
            "expand_left": "100",
            "expand_right": "100",
            "expand_top": "100",
            "expand_bottom": "100",
            "moxing": "2",
        },
    ]

    cases["upscale_8k"] = [
        {"url": url, "bianchang": "4096"},
        {"url": url, "bianchang": "8192"},
    ]

    return cases


def run_one(workflow_id: str, params: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    resp = coze_client.run_workflow(workflow_id=workflow_id, parameters=params, is_async=False)
    parsed = parse_coze_data(resp)
    return {
        "ts": _now(),
        "duration_ms": int((time.time() - started) * 1000),
        "coze": {
            "code": resp.get("code"),
            "msg": resp.get("msg"),
            "execute_id": resp.get("execute_id"),
            "debug_url": resp.get("debug_url"),
        },
        "data": parsed,
    }


def resolve_task_images(
    *,
    callback_workflow_id: str,
    taskid: str,
) -> dict[str, Any]:
    # Callback workflows often return empty images if the ComfyUI task hasn't finished yet.
    # Poll a bit so the smoke test reflects end-to-end success.
    deadline = time.time() + 180
    sleep_s = 2.0
    last_resp: dict[str, Any] | None = None
    last_parsed: dict[str, Any] | None = None
    last_images: list[str] = []
    attempts = 0

    while time.time() < deadline:
        attempts += 1
        resp = coze_client.run_workflow(workflow_id=callback_workflow_id, parameters={"taskid": taskid}, is_async=False)
        parsed = parse_coze_data(resp)
        images = extract_images_from_callback(parsed)
        last_resp, last_parsed, last_images = resp, parsed, images
        if images:
            break
        time.sleep(sleep_s)
        sleep_s = min(sleep_s * 1.4, 8.0)

    resp = last_resp or {}
    parsed = last_parsed or {}
    images = last_images
    return {
        "attempts": attempts,
        "coze": {
            "code": resp.get("code"),
            "msg": resp.get("msg"),
            "execute_id": resp.get("execute_id"),
            "debug_url": resp.get("debug_url"),
        },
        "images": images,
        "data": parsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="eval-smoke", help="OSS user_id prefix")
    parser.add_argument("--max-images", type=int, default=2, help="How many local images to upload to OSS")
    parser.add_argument("--out", default="", help="Output JSON report path (default: reports/...)")
    parser.add_argument(
        "--summary-out",
        default="",
        help="Output Markdown summary path (default: reports/..._summary.md)",
    )
    parser.add_argument("--no-upload", action="store_true", help="Skip OSS upload and use provided --url")
    parser.add_argument("--url", default="", help="Public image URL to use when --no-upload is set")
    parser.add_argument(
        "--resolve-task",
        action="store_true",
        default=True,
        help="Resolve taskid outputs via callback workflow (default: true)",
    )
    args = parser.parse_args()

    callback_workflow_id = os.getenv("COZE_COMFYUI_CALLBACK_WORKFLOW_ID") or "7597556718159003648"
    if args.no_upload:
        if not args.url:
            print("--no-upload requires --url", file=sys.stderr)
            return 2
        sample_urls = [args.url]
    else:
        sample_urls = upload_samples(user_id=args.user_id, max_images=args.max_images)

    cases = build_cases(sample_urls)

    report: dict[str, Any] = {
        "generated_at": _now(),
        "coze_base_url": os.getenv("COZE_BASE_URL") or "",
        "workflows": [],
        "sample_urls": sample_urls,
    }

    for wf in WORKFLOWS:
        wf_item: dict[str, Any] = {
            "key": wf.key,
            "name": wf.name,
            "workflow_id": wf.workflow_id,
            "category": wf.category,
            "kind": wf.kind,
            "cases": [],
        }
        for idx, params in enumerate(cases.get(wf.key, []), start=1):
            entry: dict[str, Any] = {
                "case": idx,
                "params": params,
                "ok": False,
            }
            try:
                result = run_one(wf.workflow_id, params)
                entry["result"] = result
                # Heuristic success
                data = result.get("data") or {}
                output = extract_output_text(data if isinstance(data, dict) else {})
                entry["output"] = output
                if wf.kind == "text":
                    entry["ok"] = bool(output)
                elif wf.kind == "image":
                    # Either output is a URL, or workflow returns structured images.
                    ok = False
                    if isinstance(output, str) and output.startswith(("http://", "https://")):
                        ok = True
                    if isinstance(data, dict) and any(k in data for k in ("imageUrl", "imageUrls", "images", "assets")):
                        ok = True
                    entry["ok"] = ok
                else:  # taskid
                    entry["ok"] = bool(output)
                    if args.resolve_task and output:
                        entry["resolved"] = resolve_task_images(
                            callback_workflow_id=callback_workflow_id,
                            taskid=output,
                        )
                        entry["resolved_ok"] = bool(entry["resolved"].get("images"))
            except Exception as exc:
                entry["error"] = str(exc)
                entry["ok"] = False
            wf_item["cases"].append(entry)
        report["workflows"].append(wf_item)

    out_path = args.out
    if not out_path:
        Path(REPO_ROOT / "reports").mkdir(parents=True, exist_ok=True)
        out_path = str(REPO_ROOT / "reports" / f"workflow_smoke_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")

    Path(out_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_path = args.summary_out
    if not summary_path:
        summary_path = out_path.replace(".json", "_summary.md")
    summary_lines: list[str] = []
    summary_lines.append(f"# Workflow Smoke Test\n\n- generated_at: `{report['generated_at']}`\n- coze_base_url: `{report['coze_base_url']}`\n")
    summary_lines.append("## Sample URLs\n")
    for u in report["sample_urls"]:
        summary_lines.append(f"- {u}\n")
    summary_lines.append("\n## Results\n")
    for wf in report["workflows"]:
        summary_lines.append(f"\n### {wf['name']} (`{wf['key']}`)\n\n- workflow_id: `{wf['workflow_id']}`\n- category: `{wf['category']}`\n- kind: `{wf['kind']}`\n\n")
        summary_lines.append("| case | ok | duration_ms | output/taskid | images(resolved) | debug_url |\n")
        summary_lines.append("|---:|:--:|---:|---|---:|---|\n")
        for c in wf["cases"]:
            ok = "✅" if c.get("ok") else "❌"
            dur = ""
            dbg = ""
            output = c.get("output")
            if isinstance(output, str) and len(output) > 80:
                output = output[:80] + "..."
            if c.get("result"):
                dur = str(c["result"].get("duration_ms") or "")
                dbg = str((c["result"].get("coze") or {}).get("debug_url") or "")
            resolved_imgs = 0
            if isinstance(c.get("resolved"), dict) and isinstance(c["resolved"].get("images"), list):
                resolved_imgs = len(c["resolved"]["images"])
            summary_lines.append(
                f"| {c.get('case')} | {ok} | {dur} | {output or ''} | {resolved_imgs} | {dbg} |\n"
            )
            if c.get("error"):
                summary_lines.append(f"\n> error: `{c['error']}`\n\n")
        summary_lines.append("\n")
    Path(summary_path).write_text("".join(summary_lines), encoding="utf-8")

    # Print summary
    failed = 0
    for wf in report["workflows"]:
        total = len(wf["cases"])
        ok = sum(1 for c in wf["cases"] if c.get("ok"))
        print(f"{wf['key']}: {ok}/{total} ok")
        if ok != total:
            failed += 1
    print(f"Report: {out_path}")
    print(f"Summary: {summary_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
