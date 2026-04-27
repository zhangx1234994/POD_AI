#!/usr/bin/env python3
"""Probe ComfyUI queue capacity through the running backend service.

This script is HTTP-only. Run it on the backend host or another trusted
internal host that can call `/api/coze/podi/*`.
"""

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


def _post(client: httpx.Client, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = client.post(path, json=payload or {})
    try:
        data = response.json()
    except Exception:
        data = {"text": response.text[:500]}
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code} {path}: {data}")
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} did not return JSON object")
    return data


def _get(client: httpx.Client, path: str) -> Any:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def _queue_summary(client: httpx.Client) -> dict[str, Any]:
    return _post(client, "/api/coze/podi/comfyui/queue-summary", {})


def _ability_options(client: httpx.Client) -> list[dict[str, Any]]:
    data = _get(client, "/api/abilities/options?status=active&provider=comfyui")
    items = data.get("items") if isinstance(data, dict) else None
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _find_ability(client: httpx.Client, capability_key: str) -> dict[str, Any]:
    items = _ability_options(client)
    for item in items:
        if str(item.get("capability_key") or item.get("capabilityKey") or "").strip() == capability_key:
            return item
    available = ", ".join(
        str(item.get("capability_key") or item.get("capabilityKey") or "").strip()
        for item in items
        if item.get("capability_key") or item.get("capabilityKey")
    )
    raise RuntimeError(f"ComfyUI ability not found: {capability_key}. Available: {available}")


def _field_names(ability: dict[str, Any]) -> set[str]:
    schema = ability.get("input_schema") or ability.get("inputSchema") or {}
    fields = schema.get("fields") if isinstance(schema, dict) else None
    names: set[str] = set()
    if isinstance(fields, list):
        for field in fields:
            if isinstance(field, dict):
                name = str(field.get("name") or "").strip()
                if name:
                    names.add(name)
    return names


def _default_payload(ability: dict[str, Any], sample_url: str, batch_id: str, index: int, executor_id: str) -> dict[str, Any]:
    inputs = dict(ability.get("default_params") or ability.get("defaultParams") or {})
    names = _field_names(ability)
    for key in ("url", "Url", "URL", "image_url"):
        if key in names or key in inputs:
            inputs.setdefault(key, sample_url)
    if "cankaotu" in names:
        inputs.setdefault("cankaotu", sample_url)
    if "prompt" in names:
        inputs.setdefault("prompt", "容量探测测试，请保持主体稳定")
    if "bili" in names:
        inputs.setdefault("bili", "0.35")
    if "count" in names:
        inputs.setdefault("count", 1)
    if "batch" in names:
        inputs.setdefault("batch", 1)
    if "batch_size" in names:
        inputs.setdefault("batch_size", 1)
    if "expand_left" in names:
        inputs.setdefault("expand_left", 64)
    if "expand_right" in names:
        inputs.setdefault("expand_right", 64)
    if "expand_top" in names:
        inputs.setdefault("expand_top", 64)
    if "expand_bottom" in names:
        inputs.setdefault("expand_bottom", 64)

    inputs["__capacity_probe_batch"] = batch_id
    inputs["__capacity_probe_index"] = index
    if executor_id:
        inputs["executorId"] = executor_id
    return inputs


def _submit_tool(client: httpx.Client, capability_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _post(client, f"/api/coze/podi/tools/comfyui/{capability_key}", payload)


def _task_get(client: httpx.Client, task_id: str) -> dict[str, Any]:
    return _post(client, "/api/coze/podi/tasks/get", {"taskId": task_id})


def _extract_executor(task_payload: dict[str, Any]) -> str:
    for key in ("executorId", "executor_id"):
        value = task_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    debug = task_payload.get("debugResponse")
    if isinstance(debug, dict):
        for key in ("executorId", "executor_id"):
            value = debug.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "unknown"


def _status_counts(task_payloads: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for payload in task_payloads.values():
        status = str(payload.get("taskStatus") or payload.get("status") or "unknown").strip() or "unknown"
        counts[status] += 1
    return dict(counts)


def _executor_counts(task_payloads: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for payload in task_payloads.values():
        counts[_extract_executor(payload)] += 1
    return dict(counts)


def _int_value(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _server_queue_counts(queue: dict[str, Any]) -> dict[str, int]:
    servers = queue.get("servers")
    if not isinstance(servers, list):
        return {}
    counts: dict[str, int] = {}
    for item in servers:
        if not isinstance(item, dict):
            continue
        executor_id = str(item.get("executorId") or item.get("executor_id") or "unknown").strip() or "unknown"
        counts[executor_id] = _int_value(item.get("runningCount")) + _int_value(item.get("pendingCount"))
    return counts


def _make_snapshot(
    task_payloads: dict[str, dict[str, Any]],
    queue: dict[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    return {
        "at": datetime.utcnow().isoformat() + "Z",
        "phase": phase,
        "queue": queue,
        "serverQueueCounts": _server_queue_counts(queue),
        "statusCounts": _status_counts(task_payloads),
        "executorCounts": _executor_counts(task_payloads),
    }


def _peak_queue_metrics(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    peak_total = 0
    peak_running = 0
    peak_pending = 0
    peak_server_counts: dict[str, int] = {}
    for snapshot in snapshots:
        queue = snapshot.get("queue") if isinstance(snapshot.get("queue"), dict) else {}
        total = _int_value(queue.get("totalCount"))
        running = _int_value(queue.get("totalRunning"))
        pending = _int_value(queue.get("totalPending"))
        if total == 0:
            total = running + pending
        peak_total = max(peak_total, total)
        peak_running = max(peak_running, running)
        peak_pending = max(peak_pending, pending)
        server_counts = snapshot.get("serverQueueCounts") if isinstance(snapshot.get("serverQueueCounts"), dict) else {}
        for executor_id, count in server_counts.items():
            peak_server_counts[str(executor_id)] = max(_int_value(peak_server_counts.get(str(executor_id))), _int_value(count))
    return {
        "peakQueueTotal": peak_total,
        "peakRunning": peak_running,
        "peakPending": peak_pending,
        "peakServerQueueCounts": peak_server_counts,
    }


def _assess_report(
    report: dict[str, Any],
    *,
    min_peak_queue_total: int = 0,
    min_used_executors: int = 0,
    min_successful_tasks: int = 0,
    allow_failures: int = 0,
) -> tuple[bool, list[str]]:
    issues: list[str] = []
    submitted = report.get("submittedTaskIds")
    submitted_count = len(submitted) if isinstance(submitted, list) else 0
    if submitted_count <= 0:
        issues.append("没有成功提交任何任务")

    final_counts = report.get("finalStatusCounts") if isinstance(report.get("finalStatusCounts"), dict) else {}
    successful_count = _int_value(final_counts.get("succeeded"))
    failed_count = (
        _int_value(final_counts.get("failed"))
        + _int_value(final_counts.get("query_failed"))
        + _int_value(final_counts.get("cancelled"))
        + _int_value(final_counts.get("canceled"))
    )
    if failed_count > max(0, allow_failures):
        issues.append(f"失败任务数 {failed_count} 超过允许值 {allow_failures}")
    if min_successful_tasks > 0 and successful_count < min_successful_tasks:
        issues.append(f"成功任务数 {successful_count} 低于期望 {min_successful_tasks}")

    peak_total = _int_value(report.get("peakQueueTotal"))
    if min_peak_queue_total > 0 and peak_total < min_peak_queue_total:
        issues.append(f"峰值队列 {peak_total} 低于期望 {min_peak_queue_total}")

    executor_counts = report.get("finalExecutorCounts") if isinstance(report.get("finalExecutorCounts"), dict) else {}
    used_executors = [key for key, count in executor_counts.items() if key != "unknown" and _int_value(count) > 0]
    if min_used_executors > 0 and len(used_executors) < min_used_executors:
        issues.append(f"实际使用执行节点 {len(used_executors)} 台，低于期望 {min_used_executors} 台")

    return not issues, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit real ComfyUI tasks through the running backend and observe queues.")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8099", help="Backend URL reachable from this host.")
    parser.add_argument("--capability-key", default="", help="ComfyUI capability key to submit.")
    parser.add_argument("--count", type=int, default=0, help="How many real tasks to submit. 0 only prints queue.")
    parser.add_argument("--sample-image-url", default=DEFAULT_SAMPLE_IMAGE_URL)
    parser.add_argument("--executor-id", default="", help="Optional fixed executor for this probe.")
    parser.add_argument("--submit-interval", type=float, default=0.2)
    parser.add_argument("--watch-seconds", type=int, default=600)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--min-peak-queue-total", type=int, default=0, help="Fail if observed queue peak is lower than this.")
    parser.add_argument("--min-used-executors", type=int, default=0, help="Fail if fewer executors receive tasks.")
    parser.add_argument("--min-successful-tasks", type=int, default=0, help="Fail if successful tasks are fewer than this.")
    parser.add_argument("--allow-failures", type=int, default=0, help="Allowed failed/query_failed tasks.")
    parser.add_argument("--report", default="", help="Optional JSON report path.")
    parser.add_argument("--yes", action="store_true", help="Required when --count > 0 to acknowledge real cost.")
    args = parser.parse_args()

    batch_id = f"comfyui-capacity-{_now_slug()}"
    backend_url = args.backend_url.rstrip("/")
    timeout = httpx.Timeout(30.0, connect=10.0)
    with httpx.Client(base_url=backend_url, timeout=timeout) as client:
        print(f"backend: {backend_url}")
        print("current queue:")
        try:
            print(json.dumps(_queue_summary(client), ensure_ascii=False, indent=2))
        except Exception as exc:
            print(f"queue-summary failed: {exc}", file=sys.stderr)
            print("Run this script on the backend host or a trusted internal host.", file=sys.stderr)
            return 2

        if args.count <= 0:
            return 0
        if not args.yes:
            print("Refusing to submit real tasks without --yes.", file=sys.stderr)
            return 2
        if not args.capability_key:
            print("--capability-key is required when --count > 0.", file=sys.stderr)
            return 2

        ability = _find_ability(client, args.capability_key)
        print(f"probe batch: {batch_id}")
        print(f"ability: {ability.get('capability_key') or ability.get('capabilityKey')} | {ability.get('display_name') or ability.get('displayName')}")

        task_ids: list[str] = []
        initial_task_payloads: dict[str, dict[str, Any]] = {}
        snapshots: list[dict[str, Any]] = []
        for index in range(1, max(1, args.count) + 1):
            payload = _default_payload(ability, args.sample_image_url, batch_id, index, args.executor_id.strip())
            try:
                submitted = _submit_tool(client, args.capability_key, payload)
            except Exception as exc:
                print(f"submit failed at {index}: {exc}", file=sys.stderr)
                break
            task_id = str(submitted.get("taskId") or "").strip()
            if task_id:
                task_ids.append(task_id)
                initial_task_payloads[task_id] = submitted
            print(f"submitted {index}/{args.count}: task={task_id or '-'} executor={_extract_executor(submitted)} status={submitted.get('taskStatus')}")
            try:
                snapshots.append(_make_snapshot(initial_task_payloads, _queue_summary(client), phase=f"submit:{index}"))
            except Exception:
                pass
            time.sleep(max(0, args.submit_interval))

        task_payloads: dict[str, dict[str, Any]] = dict(initial_task_payloads)
        deadline = time.monotonic() + max(1, args.watch_seconds)
        while True:
            for task_id in list(task_ids):
                try:
                    task_payloads[task_id] = _task_get(client, task_id)
                except Exception as exc:
                    task_payloads[task_id] = {"taskStatus": "query_failed", "debugResponse": str(exc)}
            try:
                queue = _queue_summary(client)
            except Exception as exc:
                queue = {"error": str(exc), "servers": []}
            snapshot = _make_snapshot(task_payloads, queue, phase="watch")
            snapshots.append(snapshot)
            print(
                f"tasks={snapshot['statusCounts']} executors={snapshot['executorCounts']} "
                f"queueTotal={queue.get('totalCount')} running={queue.get('totalRunning')} pending={queue.get('totalPending')}"
            )

            statuses = set(snapshot["statusCounts"].keys())
            terminal = {"succeeded", "failed", "cancelled", "canceled", "query_failed"}
            if statuses and statuses.issubset(terminal):
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(max(1.0, args.poll_interval))

        report = {
            "batchId": batch_id,
            "backendUrl": backend_url,
            "capabilityKey": args.capability_key,
            "submittedTaskIds": task_ids,
            "finalStatusCounts": _status_counts(task_payloads),
            "finalExecutorCounts": _executor_counts(task_payloads),
            "tasks": task_payloads,
            "snapshots": snapshots,
        }
        report.update(_peak_queue_metrics(snapshots))
        ok, assessment_issues = _assess_report(
            report,
            min_peak_queue_total=max(0, args.min_peak_queue_total),
            min_used_executors=max(0, args.min_used_executors),
            min_successful_tasks=max(0, args.min_successful_tasks),
            allow_failures=max(0, args.allow_failures),
        )
        report["assessment"] = {
            "ok": ok,
            "issues": assessment_issues,
            "minPeakQueueTotal": max(0, args.min_peak_queue_total),
            "minUsedExecutors": max(0, args.min_used_executors),
            "minSuccessfulTasks": max(0, args.min_successful_tasks),
            "allowFailures": max(0, args.allow_failures),
        }
        report_path = Path(args.report) if args.report else Path("reports") / f"comfyui_capacity_{batch_id}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report: {report_path}")
        print(
            "summary: "
            f"peakQueue={report['peakQueueTotal']} peakRunning={report['peakRunning']} "
            f"peakPending={report['peakPending']} executors={report['finalExecutorCounts']} "
            f"status={report['finalStatusCounts']}"
        )
        if assessment_issues:
            print("capacity assessment failed:")
            for issue in assessment_issues:
                print(f"- {issue}")

        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
