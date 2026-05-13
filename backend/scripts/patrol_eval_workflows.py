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
TERMINAL_STATUSES = {"succeeded", "failed", "create_failed", "query_failed"}


def _now_slug() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _workflow_fields(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    schema = workflow.get("parameters_schema") or workflow.get("parametersSchema") or {}
    fields = schema.get("fields") if isinstance(schema, dict) else None
    return [field for field in fields if isinstance(field, dict)] if isinstance(fields, list) else []


def _metadata_dict(workflow: dict[str, Any]) -> dict[str, Any]:
    metadata = workflow.get("metadata") or workflow.get("extra_metadata") or workflow.get("extraMetadata") or {}
    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return metadata if isinstance(metadata, dict) else {}


def _workflow_role(workflow: dict[str, Any]) -> str:
    governance = workflow.get("governance")
    if isinstance(governance, dict) and governance.get("role"):
        return str(governance.get("role")).strip() or "unknown"

    metadata = _metadata_dict(workflow)
    metadata_governance = metadata.get("governance")
    if isinstance(metadata_governance, dict) and metadata_governance.get("role"):
        return str(metadata_governance.get("role")).strip() or "unknown"
    for key in ("governance_role", "governanceRole", "role"):
        if metadata.get(key):
            return str(metadata.get(key)).strip() or "unknown"
    return "unknown"


def _role_matches(workflow: dict[str, Any], role_filter: str) -> bool:
    requested = {part.strip() for part in str(role_filter or "").split(",") if part.strip()}
    if not requested or "all" in requested:
        return True
    return _workflow_role(workflow) in requested


def _select_workflows(
    items: list[Any],
    *,
    category: str,
    role_filter: str,
    limit: int,
) -> list[dict[str, Any]]:
    selected = [
        workflow
        for workflow in items
        if isinstance(workflow, dict)
        and (not category or str(workflow.get("category") or "") == category)
        and _role_matches(workflow, role_filter)
    ]
    if limit > 0:
        return selected[:limit]
    return selected


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _set_if_blank(params: dict[str, Any], key: str, value: Any) -> None:
    if _is_blank(params.get(key)):
        params[key] = value


def _build_params(workflow: dict[str, Any], sample_url: str, tag: str) -> dict[str, Any]:
    params: dict[str, Any] = {}
    field_names: set[str] = set()
    image_field_names: set[str] = set()
    for field in _workflow_fields(workflow):
        name = str(field.get("name") or "").strip()
        if not name:
            continue
        field_names.add(name)
        field_type = str(field.get("type") or field.get("fieldType") or "").strip().lower()
        if field_type in {"image", "image_url", "url"}:
            image_field_names.add(name)
        default_value = field.get("defaultValue")
        if default_value is not None:
            params[name] = default_value

    metadata = _metadata_dict(workflow)
    eval_execution = metadata.get("eval_execution") if isinstance(metadata.get("eval_execution"), dict) else {}
    metadata_image_fields = eval_execution.get("image_fields") if isinstance(eval_execution, dict) else None
    if isinstance(metadata_image_fields, list):
        for image_field in metadata_image_fields:
            name = str(image_field or "").strip()
            if name:
                image_field_names.add(name)

    if {"url", "Url", "URL", "image_url"} & field_names:
        _set_if_blank(params, "url", sample_url)
        _set_if_blank(params, "Url", sample_url)
        _set_if_blank(params, "URL", sample_url)
        _set_if_blank(params, "image_url", sample_url)
    if "cankaotu" in field_names:
        _set_if_blank(params, "cankaotu", sample_url)
    if "image_urls" in field_names:
        if _is_blank(params.get("image_urls")):
            params["image_urls"] = [sample_url]
    for image_field in sorted(image_field_names):
        if image_field == "image_urls":
            continue
        _set_if_blank(params, image_field, sample_url)
    if "prompt" in field_names:
        _set_if_blank(params, "prompt", "日常巡检测试，请保持主体和风格稳定")
    if "bili" in field_names:
        _set_if_blank(params, "bili", "0.35")
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
        _set_if_blank(params, "expand_left", 64)
    if "expand_right" in field_names:
        _set_if_blank(params, "expand_right", 64)
    if "expand_top" in field_names:
        _set_if_blank(params, "expand_top", 64)
    if "expand_bottom" in field_names:
        _set_if_blank(params, "expand_bottom", 64)
    if "width" in field_names:
        _set_if_blank(params, "width", 1024)
    if "height" in field_names:
        _set_if_blank(params, "height", 1024)

    params["__patrol_tag"] = tag
    return params


def _short_error(value: Any, limit: int = 300) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split())[:limit]


def _count_string_or_url_items(value: Any) -> int:
    if not isinstance(value, list):
        return 0
    count = 0
    for item in value:
        if isinstance(item, str) and item.strip():
            count += 1
            continue
        if isinstance(item, dict):
            for key in ("url", "storedUrl", "stored_url", "outputUrl", "output_url", "imageUrl", "videoUrl"):
                nested = item.get(key)
                if isinstance(nested, str) and nested.strip():
                    count += 1
                    break
    return count


def _result_image_count(run: dict[str, Any]) -> int:
    images = run.get("result_image_urls_json")
    if not isinstance(images, list):
        images = run.get("resultImageUrlsJson")
    if not isinstance(images, list):
        images = run.get("imageUrls")
    if not isinstance(images, list):
        images = run.get("image_urls")
    if not isinstance(images, list):
        output = run.get("result_output_json") or run.get("resultOutputJson") or run.get("outputJson") or run.get("jsonOutput")
        if isinstance(output, dict):
            images = output.get("imageUrls") or output.get("image_urls") or output.get("images")
    return _count_string_or_url_items(images)


def _result_video_count(run: dict[str, Any]) -> int:
    videos = run.get("result_video_urls_json")
    if not isinstance(videos, list):
        videos = run.get("resultVideoUrlsJson")
    if not isinstance(videos, list):
        videos = run.get("videoUrls")
    if not isinstance(videos, list):
        videos = run.get("video_urls")
    if not isinstance(videos, list):
        output = run.get("result_output_json") or run.get("resultOutputJson") or run.get("outputJson") or run.get("jsonOutput")
        if isinstance(output, dict):
            videos = output.get("videoUrls") or output.get("video_urls") or output.get("videos")
    return _count_string_or_url_items(videos)


def _result_text_count(run: dict[str, Any]) -> int:
    texts = run.get("texts")
    if not isinstance(texts, list):
        texts = run.get("result_texts_json")
    if not isinstance(texts, list):
        texts = run.get("resultTextsJson")
    output = run.get("result_output_json") or run.get("resultOutputJson") or run.get("outputJson") or run.get("jsonOutput")
    if isinstance(output, str) and output.strip():
        return 1
    if isinstance(output, dict) and not isinstance(texts, list):
        texts = output.get("texts") or output.get("resultTexts") or output.get("result_texts")
        if not isinstance(texts, list):
            single = output.get("text") or output.get("content") or output.get("message")
            if isinstance(single, str) and single.strip():
                return 1
    return len([item for item in texts or [] if isinstance(item, str) and item.strip()])


def _has_structured_output(run: dict[str, Any]) -> bool:
    for key in ("result_output_json", "resultOutputJson", "outputJson", "jsonOutput"):
        if key not in run:
            continue
        value = run.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, list):
            return any(item is not None and (not isinstance(item, str) or item.strip()) for item in value)
        if isinstance(value, dict):
            return bool(value)
        return True
    return False


def _has_output(run: dict[str, Any]) -> bool:
    if _result_image_count(run) > 0:
        return True
    if _result_video_count(run) > 0:
        return True
    if _result_text_count(run) > 0:
        return True
    return _has_structured_output(run)


def _classify_issue(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "").strip()
    error_text = f"{item.get('error') or ''} {item.get('errorCode') or ''}".upper()
    if "INTERNAL_ONLY" in error_text:
        return "INTERNAL_ONLY"
    if "COMFYUI_QUEUE_FULL" in error_text:
        return "COMFYUI_QUEUE_FULL"
    if "PROMPT_REQUIRED" in error_text:
        return "PROMPT_REQUIRED"
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
    video_count = _result_video_count(latest)
    text_count = _result_text_count(latest)
    has_output = _has_output(latest)
    output_kind = "none"
    if image_count > 0:
        output_kind = "image"
    elif video_count > 0:
        output_kind = "video"
    elif text_count > 0:
        output_kind = "text"
    elif _has_structured_output(latest):
        output_kind = "structured"
    item = {
        "name": workflow.get("name"),
        "workflowId": workflow.get("workflow_id"),
        "role": _workflow_role(workflow),
        "runId": latest.get("id") or run.get("id"),
        "status": latest.get("status"),
        "finalStatus": latest.get("final_status"),
        "callbackStatus": latest.get("callback_status"),
        "cozeExecuteId": latest.get("coze_execute_id"),
        "podiTaskId": latest.get("podi_task_id"),
        "imageCount": image_count,
        "videoCount": video_count,
        "textCount": text_count,
        "outputKind": output_kind,
        "hasOutput": has_output,
        "errorCode": latest.get("error_code") or run.get("error_code"),
        "error": _short_error(latest.get("error_message") or run.get("error_message")),
    }
    item["issueCode"] = _classify_issue(item)
    return item


def _is_terminal(row: dict[str, Any]) -> bool:
    latest = row.get("latest", {}) if isinstance(row.get("latest"), dict) else {}
    return str(latest.get("status") or "") in TERMINAL_STATUSES


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


def _output_kind_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(item.get("outputKind") or "none") for item in items))


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
    parser.add_argument(
        "--role",
        default="production",
        help="Governance role filter. Use production for periodic patrol, comma-separated roles, or all.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit workflows, 0 means all.")
    parser.add_argument(
        "--max-in-flight",
        type=int,
        default=1,
        help="Maximum submitted eval runs that may be unfinished at the same time.",
    )
    parser.add_argument(
        "--submit-delay",
        type=float,
        default=0.0,
        help="Optional delay in seconds after each submission.",
    )
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
    max_in_flight = max(1, args.max_in_flight)
    timeout = httpx.Timeout(30.0, connect=10.0)
    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        workflows = _get_json(client, f"/api/evals/workflow-versions?status={args.status}")
        items = (workflows.get("items") or workflows.get("data") or []) if isinstance(workflows, dict) else workflows
        if not isinstance(items, list):
            print("workflow list response is not a list", file=sys.stderr)
            return 2

        selected = _select_workflows(items, category=args.category, role_filter=args.role, limit=args.limit)

        print(f"patrol tag: {tag}")
        print(f"backend: {base_url}")
        print(f"role filter: {args.role}")
        print(f"category filter: {args.category or 'all'}")
        print(f"max in flight: {max_in_flight}")
        print(f"workflows: {len(selected)}")
        if not selected:
            print("no workflows selected; check role/category/status filters", file=sys.stderr)
            return 2
        if args.dry_run:
            for workflow in selected:
                params = _build_params(workflow, args.sample_image_url, tag)
                print(
                    f"- {workflow.get('name')} | {workflow.get('workflow_id')} | "
                    f"role={_workflow_role(workflow)} | params={sorted(params.keys())}"
                )
            return 0

        pending = list(selected)
        runs: list[dict[str, Any]] = []
        deadline = time.monotonic() + max(30, args.timeout)
        final_rows: list[dict[str, Any]] = []
        while True:
            active_count = len([row for row in final_rows if not _is_terminal(row)])
            while pending and active_count < max_in_flight:
                workflow = pending.pop(0)
                payload = {
                    "workflow_version_id": workflow.get("id"),
                    "input_oss_urls_json": [args.sample_image_url],
                    "parameters_json": _build_params(workflow, args.sample_image_url, tag),
                }
                try:
                    run = _post_json(client, "/api/evals/runs", payload)
                except Exception as exc:
                    run = {"status": "create_failed", "error_message": repr(exc)}
                submitted_row = {"workflow": workflow, "run": run, "latest": run}
                runs.append(submitted_row)
                if not _is_terminal(submitted_row):
                    active_count += 1
                print(
                    f"submitted: {workflow.get('name')} | role={_workflow_role(workflow)} | "
                    f"workflow={workflow.get('workflow_id')} | run={run.get('id')} | status={run.get('status')}"
                )
                if args.fail_fast and run.get("status") == "create_failed":
                    pending.clear()
                    break
                if args.submit_delay > 0:
                    time.sleep(args.submit_delay)

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
            print(f"status: {dict(counts)} | pending submit: {len(pending)}")
            unfinished = [row for row in final_rows if not _is_terminal(row)]
            if args.fail_fast and any(str(row.get("latest", {}).get("status") or "") in {"failed", "create_failed", "query_failed"} for row in final_rows):
                break
            if (not pending and not unfinished) or time.monotonic() >= deadline:
                break
            time.sleep(max(1.0, args.poll_interval))

        report = {
            "tag": tag,
            "baseUrl": base_url,
            "roleFilter": args.role,
            "categoryFilter": args.category or "all",
            "maxInFlight": max_in_flight,
            "selectedCount": len(selected),
            "submittedCount": len(runs),
            "notSubmittedCount": max(0, len(selected) - len(runs)),
            "summary": dict(Counter(str(row.get("latest", {}).get("status") or "") for row in final_rows)),
            "items": [_make_report_item(row) for row in final_rows],
        }
        issue_counts = Counter(str(item.get("issueCode") or "OK") for item in report["items"])
        report["issueSummary"] = dict(issue_counts)
        report["outputKindSummary"] = _output_kind_summary(report["items"])
        report_path = Path(args.report) if args.report else Path("reports") / f"eval_patrol_{tag}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report: {report_path}")
        print(f"output kinds: {report['outputKindSummary']}")

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
