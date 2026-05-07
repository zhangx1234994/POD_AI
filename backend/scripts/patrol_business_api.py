#!/usr/bin/env python3
"""Patrol the stable business APIs for core image businesses."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
KNOWN_GOOD_SAMPLE_IMAGE_URL = (
    "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/"
    "98904c502d9d4dd78432ec2bd1f79def/20260424/228be55f-1777009905.jpg"
)


@dataclass(frozen=True)
class BusinessSpec:
    key: str
    label: str
    run_path: str
    preview_path: str
    payload: dict[str, Any]


BUSINESS_SPECS: tuple[BusinessSpec, ...] = (
    BusinessSpec(
        key="pattern_extract",
        label="花纹提取",
        run_path="/api/business/pattern-extract/runs",
        preview_path="/api/business/pattern-extract/route-preview",
        payload={
            "prompt": "巡检测试：提取主体花纹，保持边缘清晰。",
            "negative_prompt": "不要背景、不要文字水印、不要阴影。",
            "width": 1024,
            "height": 1024,
            "batch": 1,
        },
    ),
    BusinessSpec(
        key="fission",
        label="图裂变",
        run_path="/api/business/fission/runs",
        preview_path="/api/business/fission/route-preview",
        payload={
            "prompt": "巡检测试：保持主体风格，生成一张稳定花纹变体。",
            "bili": 35,
            "width": 1024,
            "height": 1024,
            "batch_size": 1,
            "image_desc": "业务巡检样例图。",
        },
    ),
    BusinessSpec(
        key="outpaint",
        label="扩图",
        run_path="/api/business/outpaint/runs",
        preview_path="/api/business/outpaint/route-preview",
        payload={
            "prompt": "巡检测试：向四周扩展，保持纹理和色彩连续。",
            "expand_left": 64,
            "expand_right": 64,
            "expand_top": 64,
            "expand_bottom": 64,
            "width": 1024,
            "height": 1024,
        },
    ),
)


def _now_tag() -> str:
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")


def _short(value: Any, limit: int = 500) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split())[:limit]


def _json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return {"text": response.text[:1000]}


def _headers(token: str | None) -> dict[str, str]:
    normalized = str(token or "").strip()
    return {"Authorization": f"Bearer {normalized}"} if normalized else {}


def _select_specs(raw: str | None) -> list[BusinessSpec]:
    requested = {item.strip() for item in str(raw or "").split(",") if item.strip()}
    if not requested or "all" in requested:
        return list(BUSINESS_SPECS)
    by_key = {spec.key: spec for spec in BUSINESS_SPECS}
    unknown = sorted(requested - set(by_key))
    if unknown:
        raise ValueError(f"unknown business keys: {','.join(unknown)}")
    return [by_key[key] for key in requested]


def _build_payload(spec: BusinessSpec, *, image_url: str | None, tag: str) -> dict[str, Any]:
    payload = dict(spec.payload)
    if image_url:
        payload["imageUrl"] = image_url
    payload.update(
        {
            "source": "business-api-patrol",
            "channel": "release-smoke",
            "traceId": f"patrol-{spec.key}-{tag}",
            "requestId": f"patrol-{spec.key}-{tag}",
            "tenantId": "podi-internal-patrol",
            "clientId": "business-api-patrol",
            "metadata": {
                "grayKey": "podi-internal-patrol",
                "patrol": True,
                "businessKey": spec.key,
            },
        }
    )
    return payload


def _has_output(run: dict[str, Any]) -> bool:
    for key in ("imageUrls", "image_urls"):
        values = run.get(key)
        if isinstance(values, list) and any(isinstance(item, str) and item.strip() for item in values):
            return True
    for key in ("videoUrls", "video_urls", "texts"):
        values = run.get(key)
        if isinstance(values, list) and any(item for item in values):
            return True
    result = run.get("resultPayload") or run.get("result_payload")
    return isinstance(result, dict) and bool(result)


def _extract_executor_evidence(run: dict[str, Any]) -> str:
    flow = run.get("flowSummary") or run.get("flow_summary")
    if isinstance(flow, dict):
        executor = flow.get("executor")
        if isinstance(executor, dict):
            label = executor.get("name") or executor.get("executorName") or executor.get("id") or executor.get("executorId")
            if isinstance(label, str) and label.strip():
                return label.strip()
    steps = run.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            label = step.get("executorName") or step.get("executor_name") or step.get("executorId") or step.get("executor_id")
            if isinstance(label, str) and label.strip():
                return label.strip()
    return ""


def _extract_selected_capability_id(run: dict[str, Any]) -> str:
    route_info = run.get("routeInfo") or run.get("route_info")
    if isinstance(route_info, dict):
        for key in ("selectedCapabilityId", "selected_capability_id", "businessVersionId", "business_version_id"):
            value = route_info.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    flow = run.get("flowSummary") or run.get("flow_summary")
    if isinstance(flow, dict):
        route = flow.get("route")
        if isinstance(route, dict):
            for key in ("selectedCapabilityId", "selected_capability_id", "businessVersionId", "business_version_id"):
                value = route.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    for key in ("businessVersionId", "business_version_id", "capabilityId", "capability_id"):
        value = run.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_output_counts(run: dict[str, Any]) -> dict[str, int]:
    image_urls = run.get("imageUrls") or run.get("image_urls") or []
    video_urls = run.get("videoUrls") or run.get("video_urls") or []
    texts = run.get("texts") or []
    return {
        "imageCount": len(image_urls) if isinstance(image_urls, list) else 0,
        "videoCount": len(video_urls) if isinstance(video_urls, list) else 0,
        "textCount": len(texts) if isinstance(texts, list) else 0,
    }


def _record_acceptance_for_result(
    client: httpx.Client,
    item: dict[str, Any],
    *,
    note: str,
    evidence_url: str,
    require_executor_evidence: bool,
) -> dict[str, Any]:
    run = item.get("response") if isinstance(item.get("response"), dict) else {}
    run = run if isinstance(run, dict) else {}
    capability_id = _extract_selected_capability_id(run)
    if not capability_id:
        return {
            "businessKey": item.get("businessKey"),
            "label": item.get("label"),
            "ok": False,
            "detail": "missing selected business capability id",
            "capabilityId": None,
        }
    run_id = str(item.get("runId") or run.get("runId") or run.get("id") or "").strip()
    executor = _extract_executor_evidence(run)
    output_counts = _extract_output_counts(run)
    flow = run.get("flowSummary") or run.get("flow_summary")
    callback = flow.get("callback") if isinstance(flow, dict) and isinstance(flow.get("callback"), dict) else {}
    has_callback = bool(callback.get("status") or run.get("callbackStatus") or run.get("callback_status"))
    payload = {
        "status": "passed",
        "note": note
        or (
            f"业务巡检通过：{item.get('label') or item.get('businessKey')}，"
            f"{item.get('detail') or '真实链路已成功'}"
        ),
        "evidenceRunId": run_id,
        "evidenceUrl": evidence_url or "",
        "checklist": {
            "businessFlow": True,
            "resultAssets": _has_output(run),
            "callbackObserved": has_callback,
            "executorEvidence": bool(executor) if require_executor_evidence else None,
        },
        "metadata": {
            "source": "patrol_business_api",
            "mode": item.get("mode"),
            "businessKey": item.get("businessKey"),
            "businessLabel": item.get("label"),
            "detail": item.get("detail"),
            "runId": run_id,
            "executor": executor,
            "output": output_counts,
            "requireExecutorEvidence": require_executor_evidence,
            "recordedBy": "business-api-patrol",
        },
    }
    response = client.post(f"/api/admin/business/capabilities/{capability_id}/acceptance-records", json=payload)
    data = _json_or_text(response)
    return {
        "businessKey": item.get("businessKey"),
        "label": item.get("label"),
        "ok": response.status_code < 400,
        "detail": f"status={response.status_code} capability={capability_id}",
        "capabilityId": capability_id,
        "response": data,
    }


def _build_summary(
    *,
    ok: bool,
    mode: str,
    base_url: str,
    specs: list[BusinessSpec],
    results: list[dict[str, Any]],
    acceptance_results: list[dict[str, Any]],
    tag: str,
) -> dict[str, Any]:
    failed_items = [item for item in results if not item.get("ok")]
    return {
        "ok": ok,
        "mode": mode,
        "baseUrl": str(base_url).rstrip("/"),
        "generatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "tag": tag,
        "businessKeys": [spec.key for spec in specs],
        "total": len(results),
        "passed": len(results) - len(failed_items),
        "failed": len(failed_items),
        "failedOrUnfinished": len(failed_items),
        "results": results,
        "failedItems": failed_items,
        "acceptanceResults": acceptance_results,
    }


def _write_report(summary: dict[str, Any], report_path: str) -> str:
    path = Path(report_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(path)


def _record_release_patrol(
    client: httpx.Client,
    *,
    summary: dict[str, Any],
    status: str,
    report_path: str,
    command: str,
    note: str,
) -> dict[str, Any]:
    payload = {
        "status": status,
        "command": command,
        "reportPath": report_path or None,
        "note": note or None,
        "summary": summary,
    }
    response = client.post("/api/admin/dashboard/release-patrol/records", json=payload)
    data = _json_or_text(response)
    return {
        "ok": response.status_code < 400,
        "detail": f"status={response.status_code}",
        "response": data,
    }


def _redacted_command(argv: list[str]) -> str:
    parts: list[str] = []
    redact_next = False
    for item in argv:
        if redact_next:
            parts.append("***")
            redact_next = False
            continue
        if item == "--token":
            parts.append(item)
            redact_next = True
            continue
        if item.startswith("--token="):
            parts.append("--token=***")
            continue
        parts.append(item)
    return " ".join(parts)


def _validate_terminal_run(run: dict[str, Any], *, require_executor_evidence: bool = False) -> tuple[bool, str]:
    status = str(run.get("status") or "").strip().lower()
    if status != "succeeded":
        return False, f"status={status or '-'} error={_short(run.get('error') or run.get('errorMessage'))}"
    if not _has_output(run):
        return False, "status=succeeded but no output"
    executor = _extract_executor_evidence(run)
    if require_executor_evidence and not executor:
        return False, "status=succeeded outputs present but no executor evidence"
    suffix = f" executor={executor}" if executor else ""
    return True, f"status=succeeded outputs={len(run.get('imageUrls') or run.get('image_urls') or [])}{suffix}"


def _post_json(client: httpx.Client, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
    response = client.post(path, json=payload)
    return response.status_code, _json_or_text(response)


def _check_image_url_accessible(image_url: str) -> tuple[bool, str]:
    url = str(image_url or "").strip()
    if not url:
        return False, "image url is empty"
    try:
        timeout = httpx.Timeout(10.0, connect=5.0)
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=False) as client:
            response = client.head(url)
            if response.status_code == 405:
                response = client.get(url, headers={"Range": "bytes=0-0"})
            if response.status_code >= 400:
                return False, f"image url returned HTTP {response.status_code}"
            content_type = str(response.headers.get("content-type") or "").lower()
            if content_type and "image" not in content_type and "octet-stream" not in content_type:
                return False, f"image url content-type is {content_type}"
            return True, f"image url ok HTTP {response.status_code}"
    except Exception as exc:
        return False, f"image url check failed: {_short(repr(exc), 240)}"


def _run_route_preview(client: httpx.Client, spec: BusinessSpec, payload: dict[str, Any]) -> dict[str, Any]:
    status, data = _post_json(client, spec.preview_path, payload)
    ok = status == 200 and isinstance(data, dict) and bool(data.get("selectedCapabilityId"))
    detail = ""
    if isinstance(data, dict):
        detail = (
            f"status={status} selected={data.get('selectedDisplayName') or data.get('selectedCapabilityId') or '-'} "
            f"by={data.get('selectedBy') or '-'}"
        )
    else:
        detail = f"status={status} body={_short(data)}"
    return {"businessKey": spec.key, "label": spec.label, "mode": "route", "ok": ok, "detail": detail, "response": data}


def _poll_run(
    client: httpx.Client,
    run_id: str,
    *,
    timeout_seconds: int,
    interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(1, timeout_seconds)
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        status, data = _post_json(client, "/api/business/runs/get", {"runId": run_id})
        latest = data if isinstance(data, dict) else {"body": data}
        if status >= 400:
            latest.setdefault("status", "query_failed")
            latest.setdefault("error", latest.get("detail") or f"HTTP_{status}")
            return latest
        if str(latest.get("status") or "").strip().lower() in TERMINAL_STATUSES:
            return latest
        time.sleep(max(0.2, interval_seconds))
    latest.setdefault("status", "query_timeout")
    latest.setdefault("error", f"BUSINESS_RUN_TIMEOUT_AFTER_{timeout_seconds}s")
    return latest


def _run_live(
    client: httpx.Client,
    spec: BusinessSpec,
    payload: dict[str, Any],
    *,
    timeout_seconds: int,
    interval_seconds: float,
    require_executor_evidence: bool,
) -> dict[str, Any]:
    status, data = _post_json(client, spec.run_path, payload)
    if status >= 400 or not isinstance(data, dict):
        return {
            "businessKey": spec.key,
            "label": spec.label,
            "mode": "live",
            "ok": False,
            "detail": f"submit failed status={status} body={_short(data)}",
            "response": data,
        }
    run_id = str(data.get("runId") or data.get("id") or "").strip()
    if not run_id:
        return {
            "businessKey": spec.key,
            "label": spec.label,
            "mode": "live",
            "ok": False,
            "detail": f"submit returned no runId status={status}",
            "response": data,
        }
    final = _poll_run(client, run_id, timeout_seconds=timeout_seconds, interval_seconds=interval_seconds)
    ok, detail = _validate_terminal_run(final, require_executor_evidence=require_executor_evidence)
    return {
        "businessKey": spec.key,
        "label": spec.label,
        "mode": "live",
        "ok": ok,
        "detail": f"runId={run_id} {detail}",
        "runId": run_id,
        "response": final,
    }


def _print_result(item: dict[str, Any]) -> None:
    marker = "PASS" if item.get("ok") else "FAIL"
    print(f"[{marker}] {item.get('label')}({item.get('businessKey')}): {item.get('detail')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patrol PODI stable business APIs.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8099", help="Backend base URL.")
    parser.add_argument("--token", default=os.getenv("SERVICE_API_TOKEN") or "", help="Optional service API token.")
    parser.add_argument("--business", default="all", help="Comma-separated keys: pattern_extract,fission,outpaint or all.")
    parser.add_argument("--mode", choices=["route", "live"], default="route", help="route only previews routing; live submits real tasks.")
    parser.add_argument("--image-url", default=os.getenv("PODI_PATROL_IMAGE_URL") or "", help="Required for live mode.")
    parser.add_argument("--timeout", type=int, default=900, help="Live run polling timeout seconds.")
    parser.add_argument("--interval", type=float, default=5.0, help="Live run polling interval seconds.")
    parser.add_argument(
        "--require-executor-evidence",
        action="store_true",
        help="In live mode, require flowSummary/steps to expose the actual executor.",
    )
    parser.add_argument(
        "--record-acceptance",
        action="store_true",
        help="After all live patrols pass, write passed acceptance records for the selected business versions.",
    )
    parser.add_argument(
        "--acceptance-note",
        default="",
        help="Optional note for acceptance records. Defaults to a patrol-generated note.",
    )
    parser.add_argument(
        "--acceptance-evidence-url",
        default="",
        help="Optional report/screenshot URL attached to acceptance records.",
    )
    parser.add_argument(
        "--report",
        default="",
        help="Optional JSON report path. When set, writes the patrol summary for later import or review.",
    )
    parser.add_argument(
        "--record-release-patrol",
        action="store_true",
        help="After the patrol finishes, write the summary into admin dashboard release patrol records.",
    )
    parser.add_argument(
        "--release-patrol-note",
        default="",
        help="Optional note for the release patrol record.",
    )
    parser.add_argument("--skip-image-check", action="store_true", help="Skip live-mode image URL HEAD/Range check.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary.")
    args = parser.parse_args()

    if args.record_acceptance and args.mode != "live":
        print("--record-acceptance requires --mode live.", flush=True)
        return 2
    if args.record_release_patrol and args.mode != "live":
        print("--record-release-patrol requires --mode live.", flush=True)
        return 2
    if args.mode == "live" and not str(args.image_url or "").strip():
        print(
            "live mode requires --image-url or PODI_PATROL_IMAGE_URL. "
            f"Known good sample: {KNOWN_GOOD_SAMPLE_IMAGE_URL}",
            flush=True,
        )
        return 2
    if args.mode == "live" and not args.skip_image_check:
        image_ok, image_detail = _check_image_url_accessible(args.image_url)
        if not image_ok:
            print(f"image url precheck failed: {image_detail}", flush=True)
            return 2
        if not args.json:
            print(image_detail, flush=True)

    try:
        specs = _select_specs(args.business)
    except ValueError as exc:
        print(str(exc), flush=True)
        return 2

    tag = _now_tag()
    timeout = httpx.Timeout(30.0, connect=10.0)
    results: list[dict[str, Any]] = []
    acceptance_results: list[dict[str, Any]] = []
    with httpx.Client(
        base_url=str(args.base_url).rstrip("/"),
        headers=_headers(args.token),
        timeout=timeout,
        trust_env=False,
    ) as client:
        for spec in specs:
            payload = _build_payload(spec, image_url=args.image_url.strip() or None, tag=tag)
            try:
                if args.mode == "live":
                    item = _run_live(
                        client,
                        spec,
                        payload,
                        timeout_seconds=args.timeout,
                        interval_seconds=args.interval,
                        require_executor_evidence=args.require_executor_evidence,
                    )
                else:
                    item = _run_route_preview(client, spec, payload)
            except Exception as exc:
                item = {
                    "businessKey": spec.key,
                    "label": spec.label,
                    "mode": args.mode,
                    "ok": False,
                    "detail": f"request failed: {_short(repr(exc))}",
                    "response": None,
                }
            results.append(item)
            if not args.json:
                _print_result(item)
        if args.record_acceptance:
            if all(item.get("ok") for item in results):
                for item in results:
                    acceptance_item = _record_acceptance_for_result(
                        client,
                        item,
                        note=str(args.acceptance_note or "").strip(),
                        evidence_url=str(args.acceptance_evidence_url or "").strip(),
                        require_executor_evidence=bool(args.require_executor_evidence),
                    )
                    acceptance_results.append(acceptance_item)
                    if not args.json:
                        _print_result({**acceptance_item, "label": f"{acceptance_item.get('label')}验收"})
            else:
                acceptance_results.append(
                    {
                        "ok": False,
                        "detail": "skip acceptance recording because at least one live patrol failed",
                    }
                )
                if not args.json:
                    print("[FAIL] 验收记录: live patrol failed, skip acceptance recording", flush=True)

    ok = all(item.get("ok") for item in results)
    if args.record_acceptance:
        ok = ok and all(item.get("ok") for item in acceptance_results)
    summary = _build_summary(
        ok=ok,
        mode=args.mode,
        base_url=str(args.base_url).rstrip("/"),
        specs=specs,
        results=results,
        acceptance_results=acceptance_results,
        tag=tag,
    )
    report_path = ""
    if args.report:
        report_path = _write_report(summary, str(args.report))
        if not args.json:
            print(f"[PASS] 巡检报告: {report_path}", flush=True)
    if args.record_release_patrol:
        command = _redacted_command(sys.argv)
        status = "passed" if ok else "failed"
        with httpx.Client(
            base_url=str(args.base_url).rstrip("/"),
            headers=_headers(args.token),
            timeout=timeout,
            trust_env=False,
        ) as client:
            patrol_record = _record_release_patrol(
                client,
                summary=summary,
                status=status,
                report_path=report_path,
                command=command,
                note=str(args.release_patrol_note or "").strip()
                or f"业务真实巡检{'通过' if ok else '失败'}：{','.join(summary['businessKeys'])}",
            )
        summary["releasePatrolRecord"] = patrol_record
        if not args.json:
            _print_result({**patrol_record, "label": "发版巡检记录", "businessKey": "dashboard"})
        ok = ok and bool(patrol_record.get("ok"))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
