#!/usr/bin/env python3
"""Run batch E7 fission tests and build an HTML report."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import get_session
from app.models.integration import AbilityTask
from app.services.coze_client import coze_client
from app.services.oss import oss_service
from app.services.task_id_codec import decode_task_id


WORKFLOW_ID_WITH_PROMPT = "7622190276932534272"
WORKFLOW_NAME_WITH_PROMPT = "图裂变 · Liebian_comfyui_20260328"
CALLBACK_WORKFLOW_ID = "7597556718159003648"
DEFAULT_INPUT_DIR = Path("/Volumes/MAC 1/comfyui_zhuanjia/testset_images")
DEFAULT_CURATED_DIR = DEFAULT_INPUT_DIR / "curated_v1"
DEFAULT_REPORT_ROOT = Path("/Volumes/MAC 1/pod_codex/reports")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _discover_images(input_dir: Path, prefer_curated: bool, exclude_dirs: list[Path] | None = None) -> tuple[Path, list[Path]]:
    chosen = input_dir
    if prefer_curated and input_dir == DEFAULT_INPUT_DIR and DEFAULT_CURATED_DIR.exists():
        chosen = DEFAULT_CURATED_DIR
    exclude_dirs = [p.resolve() for p in (exclude_dirs or [])]
    files: list[Path] = []
    for p in chosen.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        resolved = p.resolve()
        if any(parent == resolved.parent or parent in resolved.parents for parent in exclude_dirs):
            continue
        files.append(p)
    files.sort()
    return chosen, files


def _guess_content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def _upload_source(path: Path, *, user_id: str) -> dict[str, Any]:
    with path.open("rb") as fh:
        payload = fh.read()
    return oss_service.upload_bytes(
        user_id=user_id,
        filename=path.name,
        data=payload,
        content_type=_guess_content_type(path),
    )


def _poll_history(*, workflow_id: str, execute_id: str, timeout_s: float) -> dict[str, Any]:
    deadline = time.monotonic() + max(10.0, timeout_s)
    sleep_s = 1.2
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = coze_client.get_workflow_run_history(workflow_id=workflow_id, execute_id=execute_id)
        records = last.get("data")
        record = records[-1] if isinstance(records, list) and records else None
        if isinstance(record, dict):
            status = str(record.get("execute_status") or "").lower()
            if status in {"success", "fail"}:
                return record
        time.sleep(sleep_s)
        sleep_s = min(8.0, sleep_s * 1.4)
    return last


def _extract_output_payload(record: dict[str, Any]) -> dict[str, Any]:
    output = record.get("output")
    if isinstance(output, dict):
        return output
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {"raw": output}
        return {"raw": parsed}
    return {}


def _extract_image_urls(result_payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(result_payload, dict):
        return []
    images = result_payload.get("images") or []
    if not isinstance(images, list):
        return []
    urls: list[str] = []
    for item in images:
        if not isinstance(item, dict):
            continue
        for key in ("ossUrl", "sourceUrl", "url"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                urls.append(value.strip())
                break
        else:
            filename = item.get("filename")
            if isinstance(filename, str) and filename.strip():
                base = ""
                meta = result_payload.get("metadata")
                if isinstance(meta, dict):
                    base = str(meta.get("baseUrl") or "").rstrip("/")
                if base:
                    urls.append(f"{base}/view?filename={filename.strip()}&subfolder={item.get('subfolder') or ''}&type={item.get('type') or 'output'}")
    seen: set[str] = set()
    dedup: list[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        dedup.append(url)
    return dedup


def _poll_ability_task(task_id: str, *, timeout_s: float) -> dict[str, Any]:
    db_id = decode_task_id(task_id) or task_id
    deadline = time.monotonic() + max(15.0, timeout_s)
    last_row: AbilityTask | None = None
    while time.monotonic() < deadline:
        with get_session() as session:
            row = session.get(AbilityTask, db_id)
            if row:
                last_row = row
                if row.status in {"succeeded", "failed"}:
                    break
        time.sleep(5)
    if not last_row:
        return {
            "dbTaskId": db_id,
            "status": "missing",
            "error": "ABILITY_TASK_NOT_FOUND",
            "imageUrls": [],
        }
    result_payload = last_row.result_payload if isinstance(last_row.result_payload, dict) else {}
    metadata = result_payload.get("metadata") if isinstance(result_payload, dict) and isinstance(result_payload.get("metadata"), dict) else {}
    return {
        "dbTaskId": db_id,
        "status": last_row.status,
        "error": last_row.error_message,
        "imageUrls": _extract_image_urls(result_payload),
        "resultPayload": result_payload,
        "metadata": metadata,
        "durationMs": result_payload.get("durationMs") if isinstance(result_payload, dict) else None,
    }


def _poll_callback_workflow(task_id: str, *, timeout_s: float) -> dict[str, Any]:
    deadline = time.monotonic() + max(15.0, timeout_s)
    sleep_s = 2.0
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = coze_client.run_workflow(
            workflow_id=CALLBACK_WORKFLOW_ID,
            parameters={"taskid": task_id},
            is_async=False,
        )
        data = last.get("data")
        payload: dict[str, Any]
        if isinstance(data, str):
            try:
                payload = json.loads(data)
            except Exception:
                payload = {"raw": data}
        elif isinstance(data, dict):
            payload = data
        else:
            payload = {}
        images = payload.get("images")
        if isinstance(images, str) and images.strip():
            payload["_image_list"] = [u.strip() for u in images.split(",") if isinstance(u, str) and u.strip()]
            return payload
        if isinstance(images, list) and images:
            payload["_image_list"] = [str(u).strip() for u in images if isinstance(u, str) and str(u).strip()]
            return payload
        time.sleep(sleep_s)
        sleep_s = min(10.0, sleep_s * 1.3)
    return last


def _run_one(
    *,
    image_path: Path,
    source_url: str,
    repeat_index: int,
    bili: int,
    workflow_id: str,
    prompt: str,
    history_timeout_s: float,
    task_timeout_s: float,
) -> dict[str, Any]:
    started = time.time()
    result: dict[str, Any] = {
        "imagePath": str(image_path),
        "repeatIndex": repeat_index,
        "workflowId": workflow_id,
        "bili": bili,
        "sourceUrl": source_url,
        "status": "submitted",
    }
    try:
        submit = coze_client.run_workflow(
            workflow_id=workflow_id,
            parameters={"url": source_url, "bili": bili, "prompt": prompt},
            is_async=True,
        )
        execute_id = str(submit.get("execute_id") or "").strip()
        result["executeId"] = execute_id
        result["debugUrl"] = submit.get("debug_url")
        if not execute_id:
            result["status"] = "submit_failed"
            result["error"] = f"missing execute_id: {submit!r}"
            return result

        history_record = _poll_history(workflow_id=workflow_id, execute_id=execute_id, timeout_s=history_timeout_s)
        result["historyRecord"] = history_record
        history_status = str(history_record.get("execute_status") or "").lower()
        result["historyStatus"] = history_status
        out = _extract_output_payload(history_record)
        result["historyOutput"] = out
        result["promptText"] = out.get("prompt") if isinstance(out.get("prompt"), str) else None
        result["executorHint"] = out.get("ip") if isinstance(out.get("ip"), str) else None
        task_id = out.get("output") if isinstance(out.get("output"), str) else None
        result["externalTaskId"] = task_id
        if history_status != "success":
            result["status"] = "history_failed"
            result["error"] = history_record.get("error_msg") or history_record.get("error_message") or "COZE_HISTORY_FAILED"
            return result
        if not task_id:
            result["status"] = "task_missing"
            result["error"] = f"missing output task id: {out!r}"
            return result

        callback = _poll_callback_workflow(task_id, timeout_s=min(task_timeout_s, 180))
        result["callbackResult"] = callback
        if isinstance(callback, dict):
            callback_images = callback.get("_image_list")
            if isinstance(callback_images, list) and callback_images:
                result["callbackImageUrls"] = callback_images

        task = _poll_ability_task(task_id, timeout_s=task_timeout_s)
        result["task"] = task
        result["imageUrls"] = result.get("callbackImageUrls") or task.get("imageUrls") or []
        result["status"] = str(task.get("status") or "unknown")
        if task.get("error"):
            result["error"] = task.get("error")
    except Exception as exc:
        result["status"] = "exception"
        result["error"] = str(exc)
    finally:
        result["durationSec"] = round(time.time() - started, 2)
    return result


def _render_html(
    *,
    report_name: str,
    chosen_dir: Path,
    workflow_name: str,
    bili: int,
    repeat_count: int,
    image_count: int,
    records: list[dict[str, Any]],
) -> str:
    total_runs = len(records)
    succeeded = sum(1 for item in records if str(item.get("status")) == "succeeded")
    with_images = sum(1 for item in records if item.get("imageUrls"))
    failed = total_runs - succeeded
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        grouped.setdefault(item["imagePath"], []).append(item)
    cards: list[str] = []
    for image_path, items in sorted(grouped.items()):
        source_uri = Path(image_path).as_uri()
        first_prompt = next((str(it.get("promptText")).strip() for it in items if str(it.get("promptText") or "").strip()), "")
        outputs: list[str] = []
        for it in sorted(items, key=lambda x: int(x.get("repeatIndex") or 0)):
            urls = it.get("imageUrls") or []
            url = urls[0] if urls else ""
            status = str(it.get("status") or "")
            err = str(it.get("error") or "")
            executor = ""
            task = it.get("task") or {}
            if isinstance(task, dict):
                meta = task.get("metadata") or {}
                if isinstance(meta, dict):
                    executor = str(meta.get("executorId") or "")
            outputs.append(
                f"""
                <div class="output-card">
                  <div class="output-head">Run {it.get('repeatIndex')} · {status}</div>
                  {"<img src='" + url + "' loading='lazy' />" if url else "<div class='missing'>无图</div>"}
                  <div class="meta">executor: {executor or "-"}</div>
                  <div class="meta">task: {it.get('externalTaskId') or '-'}</div>
                  <div class="meta">耗时: {it.get('durationSec')}s</div>
                  {f"<pre>{err}</pre>" if err else ""}
                </div>
                """
            )
        cards.append(
            f"""
            <section class="case">
              <div class="source">
                <div class="section-title">{Path(image_path).name}</div>
                <img src="{source_uri}" loading="lazy" />
                <div class="meta">source: {image_path}</div>
                {f"<pre>{first_prompt}</pre>" if first_prompt else ""}
              </div>
              <div class="outputs">{''.join(outputs)}</div>
            </section>
            """
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{report_name}</title>
  <style>
    :root {{
      --bg: #0d1117;
      --panel: #161b22;
      --line: #2b3440;
      --text: #e6edf3;
      --muted: #9da7b3;
      --ok: #3fb950;
      --bad: #f85149;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 24px; background: var(--bg); color: var(--text);
      font: 14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    }}
    h1,h2,p {{ margin: 0; }}
    .summary {{
      display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin: 20px 0 28px;
    }}
    .tile,.case,.output-card,.source {{
      background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
    }}
    .tile {{ padding: 14px 16px; }}
    .tile strong {{ display: block; font-size: 24px; margin-top: 4px; }}
    .tile small,.meta {{ color: var(--muted); }}
    .case {{
      display: grid; grid-template-columns: 300px 1fr; gap: 16px;
      padding: 16px; margin-bottom: 18px;
    }}
    .source {{ padding: 12px; }}
    .source img,.output-card img {{
      width: 100%; height: auto; display: block; border-radius: 10px; background: #fff;
    }}
    .outputs {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .output-card {{ padding: 12px; }}
    .output-head {{ font-weight: 600; margin-bottom: 8px; }}
    .section-title {{ font-size: 16px; font-weight: 700; margin-bottom: 10px; }}
    .missing {{
      min-height: 220px; display: flex; align-items: center; justify-content: center;
      border: 1px dashed var(--line); border-radius: 10px; color: var(--bad);
    }}
    pre {{
      white-space: pre-wrap; word-break: break-word; background: #0b0f14; border-radius: 10px;
      padding: 10px; margin: 10px 0 0; color: var(--text);
    }}
    @media (max-width: 1280px) {{
      .case {{ grid-template-columns: 1fr; }}
      .outputs {{ grid-template-columns: 1fr; }}
      .summary {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
    }}
  </style>
</head>
<body>
  <h1>{report_name}</h1>
  <p>workflow: {workflow_name} · 输入目录: {chosen_dir} · bili={bili} · 每张图重复 {repeat_count} 次 · 图片数 {image_count}</p>
  <div class="summary">
    <div class="tile"><small>总运行数</small><strong>{total_runs}</strong></div>
    <div class="tile"><small>成功</small><strong style="color:var(--ok)">{succeeded}</strong></div>
    <div class="tile"><small>有图结果</small><strong>{with_images}</strong></div>
    <div class="tile"><small>失败/无图</small><strong style="color:var(--bad)">{failed}</strong></div>
  </div>
  {''.join(cards)}
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--workflow-id", default=WORKFLOW_ID_WITH_PROMPT)
    parser.add_argument("--workflow-name", default=WORKFLOW_NAME_WITH_PROMPT)
    parser.add_argument("--bili", type=int, default=80)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--history-timeout", type=float, default=300)
    parser.add_argument("--task-timeout", type=float, default=900)
    parser.add_argument("--prompt", default="")
    parser.add_argument("--use-all", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--exclude-dir", action="append", default=[])
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    exclude_dirs = [Path(p) for p in args.exclude_dir]
    chosen_dir, images = _discover_images(input_dir, prefer_curated=not args.use_all, exclude_dirs=exclude_dirs)
    if args.limit and args.limit > 0:
        images = images[: args.limit]
    if not images:
        raise SystemExit(f"No images found under {chosen_dir}")

    timestamp = _now_tag()
    report_dir = DEFAULT_REPORT_ROOT / f"e7_fission_batch_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Using input dir: {chosen_dir}")
    print(f"[1/4] Images: {len(images)}")

    uploaded_sources: dict[str, str] = {}
    source_records: list[dict[str, Any]] = []
    print("[2/4] Uploading source images to OSS...")
    for idx, image_path in enumerate(images, start=1):
        upload = _upload_source(image_path, user_id="batch-e7-test")
        source_url = str(upload.get("url") or "").strip()
        uploaded_sources[str(image_path)] = source_url
        source_records.append(
            {
                "imagePath": str(image_path),
                "sourceUrl": source_url,
                "objectKey": upload.get("objectKey"),
            }
        )
        print(f"  - {idx}/{len(images)} {image_path.name}")

    jobs: list[dict[str, Any]] = []
    for image_path in images:
        source_url = uploaded_sources[str(image_path)]
        for repeat_index in range(1, args.repeat + 1):
            jobs.append(
                {
                    "image_path": image_path,
                    "source_url": source_url,
                    "repeat_index": repeat_index,
                }
            )

    print(f"[3/4] Submitting {len(jobs)} runs (concurrency={args.concurrency})...")
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        future_map = {
            executor.submit(
                _run_one,
                image_path=job["image_path"],
                source_url=job["source_url"],
                repeat_index=job["repeat_index"],
                bili=args.bili,
                workflow_id=args.workflow_id,
                prompt=args.prompt,
                history_timeout_s=args.history_timeout,
                task_timeout_s=args.task_timeout,
            ): job
            for job in jobs
        }
        finished = 0
        for future in as_completed(future_map):
            item = future.result()
            results.append(item)
            finished += 1
            print(
                f"  - {finished}/{len(jobs)} {Path(item['imagePath']).name} run{item['repeatIndex']} => {item.get('status')} "
                f"{'(images=' + str(len(item.get('imageUrls') or [])) + ')' if item.get('imageUrls') else ''}"
            )

    results.sort(key=lambda x: (x["imagePath"], int(x["repeatIndex"])))

    report_name = f"E7 裂变批测报告 {timestamp}"
    html = _render_html(
        report_name=report_name,
        chosen_dir=chosen_dir,
        workflow_name=args.workflow_name,
        bili=args.bili,
        repeat_count=args.repeat,
        image_count=len(images),
        records=results,
    )
    html_path = report_dir / "index.html"
    json_path = report_dir / "results.json"
    summary_path = report_dir / "summary.json"
    html_path.write_text(html, encoding="utf-8")
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "reportName": report_name,
        "workflowId": args.workflow_id,
        "workflowName": args.workflow_name,
        "inputDir": str(chosen_dir),
        "imageCount": len(images),
        "repeat": args.repeat,
        "bili": args.bili,
        "sourceRecords": source_records,
        "totalRuns": len(results),
        "succeededRuns": sum(1 for item in results if item.get("status") == "succeeded"),
        "runsWithImages": sum(1 for item in results if item.get("imageUrls")),
        "failedRuns": sum(1 for item in results if item.get("status") != "succeeded"),
        "htmlPath": str(html_path),
        "jsonPath": str(json_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[4/4] Report ready")
    print(f"HTML: {html_path}")
    print(f"JSON: {json_path}")
    print(f"SUMMARY: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
