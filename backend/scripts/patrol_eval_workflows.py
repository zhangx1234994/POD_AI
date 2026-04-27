#!/usr/bin/env python3
"""Run active eval workflows through the public eval API and wait for final states."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


DEFAULT_SAMPLE_IMAGE_URL = (
    "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/"
    "98904c502d9d4dd78432ec2bd1f79def/20260424/228be55f-1777009905.jpg"
)


def _now_slug() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _workflow_fields(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    schema = workflow.get("parameters_schema") or workflow.get("parametersSchema") or {}
    fields = schema.get("fields") if isinstance(schema, dict) else None
    return [field for field in fields if isinstance(field, dict)] if isinstance(fields, list) else []


def _build_params(workflow: dict[str, Any], sample_url: str, tag: str) -> dict[str, Any]:
    params: dict[str, Any] = {}
    field_names: set[str] = set()
    for field in _workflow_fields(workflow):
        name = str(field.get("name") or "").strip()
        if not name:
            continue
        field_names.add(name)
        default_value = field.get("defaultValue")
        if default_value is not None:
            params[name] = default_value

    if {"url", "Url", "URL", "image_url"} & field_names:
        params.setdefault("url", sample_url)
        params.setdefault("Url", sample_url)
        params.setdefault("URL", sample_url)
        params.setdefault("image_url", sample_url)
    if "cankaotu" in field_names:
        params.setdefault("cankaotu", sample_url)
    if "image_urls" in field_names:
        params.setdefault("image_urls", [sample_url])
    if "prompt" in field_names:
        params.setdefault("prompt", "日常巡检测试，请保持主体和风格稳定")
    if "bili" in field_names:
        params.setdefault("bili", "0.35")
    # Patrol is a functional smoke, not a load test. Force single output even
    # when workflow defaults use multi-image fan-out.
    if "count" in field_names:
        params["count"] = 1
    if "generateCount" in field_names:
        params["generateCount"] = 1
    if "variantCount" in field_names:
        params["variantCount"] = 1
    if "n" in field_names:
        params["n"] = 1
    if "batch" in field_names:
        params["batch"] = 1
    if "batch_size" in field_names:
        params["batch_size"] = 1
    if "expand_left" in field_names:
        params.setdefault("expand_left", 64)
    if "expand_right" in field_names:
        params.setdefault("expand_right", 64)
    if "expand_top" in field_names:
        params.setdefault("expand_top", 64)
    if "expand_bottom" in field_names:
        params.setdefault("expand_bottom", 64)
    if "width" in field_names:
        params.setdefault("width", 1024)
    if "height" in field_names:
        params.setdefault("height", 1024)

    params["__patrol_tag"] = tag
    return params


def _short_error(value: Any, limit: int = 300) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split())[:limit]


def _result_image_count(run: dict[str, Any]) -> int:
    images = run.get("result_image_urls_json")
    if not isinstance(images, list):
        images = run.get("resultImageUrlsJson")
    if not isinstance(images, list):
        images = run.get("imageUrls")
    return len([item for item in images or [] if isinstance(item, str) and item.strip()])


def _has_output(run: dict[str, Any]) -> bool:
    if _result_image_count(run) > 0:
        return True
    for key in ("result_output_json", "resultOutputJson", "outputJson", "jsonOutput"):
        if key in run and run.get(key) is not None:
            return True
    return False


def _classify_issue(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "").strip()
    error_text = f"{item.get('error') or ''} {item.get('errorCode') or ''}".upper()
    if "INTERNAL_ONLY" in error_text:
        return "INTERNAL_ONLY"
    if "COZE_WORKFLOW_ERROR" in error_text:
        return "COZE_WORKFLOW_ERROR"
    if status == "succeeded" and not item.get("hasOutput"):
        return "EVAL_SUCCEEDED_WITHOUT_OUTPUT"
    if status in {"create_failed", "query_failed"}:
        return status.upper()
    if status != "succeeded":
        return "RUN_NOT_SUCCEEDED"
    return ""


def _make_report_item(row: dict[str, Any]) -> dict[str, Any]:
    latest = row.get("latest", {}) if isinstance(row.get("latest"), dict) else {}
    run = row.get("run", {}) if isinstance(row.get("run"), dict) else {}
    workflow = row.get("workflow", {}) if isinstance(row.get("workflow"), dict) else {}
    image_count = _result_image_count(latest)
    has_output = _has_output(latest)
    item = {
        "name": workflow.get("name"),
        "workflowId": workflow.get("workflow_id"),
        "runId": latest.get("id") or run.get("id"),
        "status": latest.get("status"),
        "finalStatus": latest.get("final_status"),
        "callbackStatus": latest.get("callback_status"),
        "cozeExecuteId": latest.get("coze_execute_id"),
        "podiTaskId": latest.get("podi_task_id"),
        "imageCount": image_count,
        "hasOutput": has_output,
        "errorCode": latest.get("error_code") or run.get("error_code"),
        "error": _short_error(latest.get("error_message") or run.get("error_message")),
    }
    item["issueCode"] = _classify_issue(item)
    return item


def _failed_items(items: list[dict[str, Any]], *, allow_empty_output: bool = False) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    for item in items:
        status = str(item.get("status") or "")
        if status != "succeeded":
            failed.append(item)
            continue
        if not allow_empty_output and not item.get("hasOutput"):
            failed.append(item)
    return failed


def _get_json(client: httpx.Client, path: str) -> Any:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def _post_json(client: httpx.Client, path: str, payload: dict[str, Any]) -> Any:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all active eval workflows through the eval API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8099", help="Backend base URL.")
    parser.add_argument("--sample-image-url", default=DEFAULT_SAMPLE_IMAGE_URL, help="Stable sample image URL.")
    parser.add_argument("--status", default="active", help="Workflow status filter.")
    parser.add_argument("--category", default="", help="Optional category filter.")
    parser.add_argument("--limit", type=int, default=0, help="Limit workflows, 0 means all.")
    parser.add_argument("--timeout", type=int, default=1800, help="Total wait timeout in seconds.")
    parser.add_argument("--poll-interval", type=float, default=10.0, help="Polling interval in seconds.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop immediately when any run fails.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned runs only.")
    parser.add_argument(
        "--allow-empty-output",
        action="store_true",
        help="Only check terminal status. By default succeeded runs without images/json are failures.",
    )
    parser.add_argument("--report", default="", help="Optional report JSON path.")
    args = parser.parse_args()

    tag = f"eval-patrol-{_now_slug()}"
    base_url = args.base_url.rstrip("/")
    timeout = httpx.Timeout(30.0, connect=10.0)
    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        workflows = _get_json(client, f"/api/evals/workflow-versions?status={args.status}")
        items = workflows.get("items") or workflows.get("data") or [] if isinstance(workflows, dict) else workflows
        if not isinstance(items, list):
            print("workflow list response is not a list", file=sys.stderr)
            return 2

        selected = [
            workflow
            for workflow in items
            if isinstance(workflow, dict) and (not args.category or str(workflow.get("category") or "") == args.category)
        ]
        if args.limit > 0:
            selected = selected[: args.limit]

        print(f"patrol tag: {tag}")
        print(f"backend: {base_url}")
        print(f"workflows: {len(selected)}")
        if args.dry_run:
            for workflow in selected:
                params = _build_params(workflow, args.sample_image_url, tag)
                print(f"- {workflow.get('name')} | {workflow.get('workflow_id')} | params={sorted(params.keys())}")
            return 0

        runs: list[dict[str, Any]] = []
        for workflow in selected:
            payload = {
                "workflow_version_id": workflow.get("id"),
                "input_oss_urls_json": [args.sample_image_url],
                "parameters_json": _build_params(workflow, args.sample_image_url, tag),
            }
            try:
                run = _post_json(client, "/api/evals/runs", payload)
            except Exception as exc:
                run = {"status": "create_failed", "error_message": repr(exc)}
            runs.append({"workflow": workflow, "run": run})
            print(f"submitted: {workflow.get('name')} | workflow={workflow.get('workflow_id')} | run={run.get('id')} | status={run.get('status')}")
            if args.fail_fast and run.get("status") == "create_failed":
                break

        deadline = time.monotonic() + max(30, args.timeout)
        final_rows: list[dict[str, Any]] = []
        while True:
            final_rows = []
            for item in runs:
                run_id = item.get("run", {}).get("id")
                if not run_id:
                    final_rows.append({**item, "latest": item.get("run", {})})
                    continue
                try:
                    latest = _get_json(client, f"/api/evals/runs/{run_id}")
                except Exception as exc:
                    latest = {"status": "query_failed", "error_message": repr(exc)}
                final_rows.append({**item, "latest": latest})

            counts = Counter(str(row.get("latest", {}).get("status") or "") for row in final_rows)
            print(f"status: {dict(counts)}")
            unfinished = [
                row
                for row in final_rows
                if str(row.get("latest", {}).get("status") or "") not in {"succeeded", "failed", "create_failed", "query_failed"}
            ]
            if args.fail_fast and any(str(row.get("latest", {}).get("status") or "") in {"failed", "create_failed", "query_failed"} for row in final_rows):
                break
            if not unfinished or time.monotonic() >= deadline:
                break
            time.sleep(max(1.0, args.poll_interval))

        report = {
            "tag": tag,
            "baseUrl": base_url,
            "summary": dict(Counter(str(row.get("latest", {}).get("status") or "") for row in final_rows)),
            "items": [_make_report_item(row) for row in final_rows],
        }
        issue_counts = Counter(str(item.get("issueCode") or "OK") for item in report["items"])
        report["issueSummary"] = dict(issue_counts)
        report_path = Path(args.report) if args.report else Path("reports") / f"eval_patrol_{tag}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report: {report_path}")

        failed = _failed_items(report["items"], allow_empty_output=args.allow_empty_output)
        if failed:
            print("failed or unfinished:")
            for item in failed:
                issue = item.get("issueCode") or "UNKNOWN"
                print(
                    f"- {issue} | {item['status']} | {item['name']} | "
                    f"task={item['podiTaskId']} | images={item.get('imageCount', 0)} | {item['error']}"
                )
            return 2
        print("all eval workflows succeeded")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
