#!/usr/bin/env python3
"""Check ComfyUI executor health after a machine restart.

This is a no-cost check. It only reads ComfyUI HTTP endpoints and optionally
checks the backend route summary; it does not submit generation jobs.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


DEFAULT_EXECUTORS: tuple[tuple[str, str], ...] = (
    # 233 已停止服务；默认巡检只检查当前生产节点，历史节点仍可通过 --executor 显式检查。
    ("executor_comfyui_pattern_extract_158", "http://117.50.80.158:8079"),
)
DEFAULT_REQUIRED_CLASSES = ("KSampler", "SaveImage", "LoadImage")


@dataclass(frozen=True)
class ExecutorTarget:
    executor_id: str
    base_url: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_executor_arg(value: str) -> ExecutorTarget:
    raw = str(value or "").strip()
    if not raw:
        raise argparse.ArgumentTypeError("executor cannot be empty")
    if "=" in raw:
        executor_id, base_url = raw.split("=", 1)
    elif "," in raw:
        executor_id, base_url = raw.split(",", 1)
    else:
        raise argparse.ArgumentTypeError("executor must use id=url")
    executor_id = executor_id.strip()
    base_url = base_url.strip().rstrip("/")
    if not executor_id:
        raise argparse.ArgumentTypeError("executor id cannot be empty")
    if not base_url.startswith(("http://", "https://")):
        raise argparse.ArgumentTypeError("executor url must start with http:// or https://")
    return ExecutorTarget(executor_id=executor_id, base_url=base_url)


def _http_get_json(client: httpx.Client, base_url: str, path: str) -> tuple[int, Any, float]:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    started = datetime.now(timezone.utc)
    response = client.get(url)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    try:
        data = response.json()
    except Exception:
        data = {"text": response.text[:500]}
    return response.status_code, data, elapsed


def _summarize_system_stats(data: Any) -> dict[str, Any]:
    payload = data if isinstance(data, dict) else {}
    system = payload.get("system") if isinstance(payload.get("system"), dict) else {}
    devices = payload.get("devices") if isinstance(payload.get("devices"), list) else []
    summarized_devices: list[dict[str, Any]] = []
    for item in devices:
        if not isinstance(item, dict):
            continue
        summarized_devices.append(
            {
                "name": item.get("name"),
                "type": item.get("type"),
                "vramTotal": item.get("vram_total"),
                "vramFree": item.get("vram_free"),
            }
        )
    return {
        "os": system.get("os"),
        "comfyuiVersion": system.get("comfyui_version"),
        "pythonVersion": system.get("python_version"),
        "pytorchVersion": system.get("pytorch_version"),
        "ramTotal": system.get("ram_total"),
        "ramFree": system.get("ram_free"),
        "deviceCount": len(summarized_devices),
        "devices": summarized_devices,
    }


def _summarize_queue(data: Any) -> dict[str, Any]:
    payload = data if isinstance(data, dict) else {}
    running = payload.get("queue_running")
    pending = payload.get("queue_pending")
    running_count = len(running) if isinstance(running, list) else 0
    pending_count = len(pending) if isinstance(pending, list) else 0
    return {
        "runningCount": running_count,
        "pendingCount": pending_count,
        "totalCount": running_count + pending_count,
    }


def _summarize_object_info(data: Any, required_classes: list[str]) -> dict[str, Any]:
    payload = data if isinstance(data, dict) else {}
    keys = {str(key) for key in payload.keys()}
    missing = [item for item in required_classes if item not in keys]
    return {
        "nodeCount": len(keys),
        "requiredClasses": required_classes,
        "missingRequiredClasses": missing,
    }


def _assess_node(node: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if node.get("systemStatsStatus") != 200:
        issues.append(f"system_stats HTTP {node.get('systemStatsStatus')}")
    if node.get("queueStatus") != 200:
        issues.append(f"queue HTTP {node.get('queueStatus')}")
    if node.get("objectInfoStatus") != 200:
        issues.append(f"object_info HTTP {node.get('objectInfoStatus')}")

    system = node.get("system") if isinstance(node.get("system"), dict) else {}
    if int(system.get("deviceCount") or 0) <= 0:
        issues.append("未识别到 GPU 设备")

    object_info = node.get("objectInfo") if isinstance(node.get("objectInfo"), dict) else {}
    if int(object_info.get("nodeCount") or 0) <= 0:
        issues.append("object_info 为空")
    missing = object_info.get("missingRequiredClasses")
    if isinstance(missing, list) and missing:
        issues.append(f"缺少关键节点 {missing}")
    return not issues, issues


def _summarize_backend_route_summary(data: Any, expected_executor_ids: list[str]) -> dict[str, Any]:
    payload = data if isinstance(data, dict) else {}
    servers = payload.get("servers") if isinstance(payload.get("servers"), list) else []
    by_id = {
        str(item.get("executorId") or item.get("executor_id") or ""): item
        for item in servers
        if isinstance(item, dict)
    }
    missing = [executor_id for executor_id in expected_executor_ids if executor_id not in by_id]
    unavailable: list[str] = []
    for executor_id in expected_executor_ids:
        item = by_id.get(executor_id)
        if not isinstance(item, dict):
            continue
        if item.get("supported") is not True:
            unavailable.append(executor_id)
        if str(item.get("diagnosisLevel") or "").lower() in {"error", "danger"}:
            unavailable.append(executor_id)
        if str(item.get("feedDiagnosisLevel") or "").lower() in {"error", "danger"}:
            unavailable.append(executor_id)
    return {
        "totalCapacity": payload.get("totalCapacity"),
        "totalIdleSlots": payload.get("totalIdleSlots"),
        "supportedServers": payload.get("supportedServers"),
        "unsupportedServers": payload.get("unsupportedServers"),
        "backendBlockedServers": payload.get("backendBlockedServers"),
        "routeEvidenceCoveredServers": payload.get("routeEvidenceCoveredServers"),
        "missingExpectedExecutors": missing,
        "unavailableExpectedExecutors": sorted(set(unavailable)),
        "diagnostics": payload.get("diagnostics") if isinstance(payload.get("diagnostics"), list) else [],
    }


def _assess_backend_summary(summary: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if summary.get("missingExpectedExecutors"):
        issues.append(f"中台队列汇总缺少节点 {summary.get('missingExpectedExecutors')}")
    if summary.get("unavailableExpectedExecutors"):
        issues.append(f"中台认为不可用节点 {summary.get('unavailableExpectedExecutors')}")
    if int(summary.get("unsupportedServers") or 0) > 0:
        issues.append(f"unsupportedServers={summary.get('unsupportedServers')}")
    if int(summary.get("backendBlockedServers") or 0) > 0:
        issues.append(f"backendBlockedServers={summary.get('backendBlockedServers')}")
    return not issues, issues


def check_nodes(
    *,
    targets: list[ExecutorTarget],
    required_classes: list[str],
    timeout: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    timeout_config = httpx.Timeout(timeout, connect=min(timeout, 8.0))
    with httpx.Client(timeout=timeout_config, trust_env=False) as client:
        for target in targets:
            item: dict[str, Any] = {
                "executorId": target.executor_id,
                "baseUrl": target.base_url,
            }
            try:
                status, data, elapsed = _http_get_json(client, target.base_url, "/system_stats")
                item["systemStatsStatus"] = status
                item["systemStatsSeconds"] = round(elapsed, 3)
                item["system"] = _summarize_system_stats(data)
            except Exception as exc:
                item["systemStatsStatus"] = 0
                item["systemStatsError"] = str(exc)[:500]

            try:
                status, data, elapsed = _http_get_json(client, target.base_url, "/queue")
                item["queueStatus"] = status
                item["queueSeconds"] = round(elapsed, 3)
                item["queue"] = _summarize_queue(data)
            except Exception as exc:
                item["queueStatus"] = 0
                item["queueError"] = str(exc)[:500]

            try:
                status, data, elapsed = _http_get_json(client, target.base_url, "/object_info")
                item["objectInfoStatus"] = status
                item["objectInfoSeconds"] = round(elapsed, 3)
                item["objectInfo"] = _summarize_object_info(data, required_classes)
            except Exception as exc:
                item["objectInfoStatus"] = 0
                item["objectInfoError"] = str(exc)[:500]

            ok, issues = _assess_node(item)
            item["ok"] = ok
            item["issues"] = issues
            results.append(item)
    return results


def check_backend_summary(
    *,
    backend_url: str,
    expected_executor_ids: list[str],
    timeout: float,
) -> dict[str, Any]:
    timeout_config = httpx.Timeout(timeout, connect=min(timeout, 8.0))
    with httpx.Client(base_url=backend_url.rstrip("/"), timeout=timeout_config, trust_env=False) as client:
        response = client.post("/api/coze/podi/comfyui/queue-summary", json={})
        try:
            data = response.json()
        except Exception:
            data = {"text": response.text[:500]}
    summary = _summarize_backend_route_summary(data, expected_executor_ids)
    summary["status"] = response.status_code
    ok, issues = _assess_backend_summary(summary)
    if response.status_code >= 400:
        ok = False
        issues.append(f"queue-summary HTTP {response.status_code}")
    summary["ok"] = ok
    summary["issues"] = issues
    return summary


def build_report(
    *,
    targets: list[ExecutorTarget],
    required_classes: list[str],
    backend_url: str | None,
    timeout: float,
) -> dict[str, Any]:
    nodes = check_nodes(targets=targets, required_classes=required_classes, timeout=timeout)
    backend_summary = None
    if backend_url:
        backend_summary = check_backend_summary(
            backend_url=backend_url,
            expected_executor_ids=[target.executor_id for target in targets],
            timeout=timeout,
        )
    ok = all(item.get("ok") for item in nodes) and (backend_summary is None or backend_summary.get("ok") is True)
    return {
        "ok": ok,
        "checkedAt": _utc_now(),
        "nodes": nodes,
        "backendSummary": backend_summary,
    }


def _print_human(report: dict[str, Any]) -> None:
    print(f"ComfyUI 节点重启后自检: {'PASS' if report.get('ok') else 'FAIL'}")
    print(f"checkedAt={report.get('checkedAt')}")
    for item in report.get("nodes") or []:
        if not isinstance(item, dict):
            continue
        mark = "PASS" if item.get("ok") else "FAIL"
        system = item.get("system") if isinstance(item.get("system"), dict) else {}
        queue = item.get("queue") if isinstance(item.get("queue"), dict) else {}
        object_info = item.get("objectInfo") if isinstance(item.get("objectInfo"), dict) else {}
        devices = system.get("devices") if isinstance(system.get("devices"), list) else []
        device_names = [str(device.get("name") or "-") for device in devices if isinstance(device, dict)]
        print(
            f"[{mark}] {item.get('executorId')} {item.get('baseUrl')} "
            f"version={system.get('comfyuiVersion') or '-'} "
            f"gpu={'; '.join(device_names) or '-'} "
            f"queue={queue.get('totalCount', '-')} "
            f"nodes={object_info.get('nodeCount', '-')}"
        )
        for issue in item.get("issues") or []:
            print(f"  - {issue}")
    backend_summary = report.get("backendSummary")
    if isinstance(backend_summary, dict):
        mark = "PASS" if backend_summary.get("ok") else "FAIL"
        print(
            f"[{mark}] backend queue-summary "
            f"capacity={backend_summary.get('totalCapacity')} "
            f"idle={backend_summary.get('totalIdleSlots')} "
            f"supported={backend_summary.get('supportedServers')} "
            f"blocked={backend_summary.get('backendBlockedServers')}"
        )
        for issue in backend_summary.get("issues") or []:
            print(f"  - {issue}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check ComfyUI executor health after restart.")
    parser.add_argument(
        "--executor",
        action="append",
        type=_parse_executor_arg,
        help="Executor target in id=url format. Defaults to the active 158 production node.",
    )
    parser.add_argument(
        "--required-class",
        action="append",
        default=[],
        help="ComfyUI node class that must appear in object_info. Can be repeated.",
    )
    parser.add_argument(
        "--backend-url",
        default="",
        help="Optional backend URL. When set, also checks /api/coze/podi/comfyui/queue-summary.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    parser.add_argument("--report", default="", help="Optional JSON report path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    targets = list(args.executor or [ExecutorTarget(executor_id=item[0], base_url=item[1]) for item in DEFAULT_EXECUTORS])
    required_classes = list(args.required_class or DEFAULT_REQUIRED_CLASSES)
    report = build_report(
        targets=targets,
        required_classes=required_classes,
        backend_url=args.backend_url.strip() or None,
        timeout=max(3.0, float(args.timeout or 30.0)),
    )
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
        if args.report:
            print(f"report={Path(args.report).resolve()}")
    return 0 if report.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
