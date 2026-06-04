#!/usr/bin/env python3
"""Benchmark high-frequency PODI control-plane read endpoints."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class EndpointSpec:
    key: str
    path: str
    token_env: str | None
    p95_ms: float


DEFAULT_ENDPOINTS: tuple[EndpointSpec, ...] = (
    EndpointSpec("health", "/health", None, 300),
    EndpointSpec("business_capabilities", "/api/admin/business/capabilities", "ADMIN_API_TOKEN", 1500),
    EndpointSpec(
        "business_usage_summary",
        "/api/admin/business/usage-summary?window_hours=24",
        "ADMIN_API_TOKEN",
        1500,
    ),
    EndpointSpec(
        "business_api_usage",
        "/api/admin/business/api-key-usage?window_hours=24&limit=50&group_limit=30",
        "ADMIN_API_TOKEN",
        1500,
    ),
    EndpointSpec("comfyui_queue_summary", "/api/admin/comfyui/queue-summary", "ADMIN_API_TOKEN", 1500),
)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = int(round((percentile / 100.0) * (len(ordered) - 1)))
    return ordered[max(0, min(index, len(ordered) - 1))]


def _request(
    *,
    base_url: str,
    endpoint: EndpointSpec,
    token: str | None,
    timeout: float,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + endpoint.path
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=headers)
        elapsed_ms = (time.perf_counter() - started) * 1000
        ok = 200 <= response.status_code < 400
        return {
            "ok": ok,
            "statusCode": response.status_code,
            "durationMs": round(elapsed_ms, 2),
            "error": None if ok else response.text[:300],
        }
    except Exception as exc:  # pragma: no cover - benchmark diagnostics
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "ok": False,
            "statusCode": None,
            "durationMs": round(elapsed_ms, 2),
            "error": str(exc)[:300],
        }


def _run_endpoint(
    *,
    base_url: str,
    endpoint: EndpointSpec,
    token: str | None,
    sequential: int,
    concurrency: int,
    timeout: float,
) -> dict[str, Any]:
    sequential_results = [
        _request(base_url=base_url, endpoint=endpoint, token=token, timeout=timeout)
        for _ in range(sequential)
    ]
    concurrent_results: list[dict[str, Any]] = []
    if concurrency > 0:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(_request, base_url=base_url, endpoint=endpoint, token=token, timeout=timeout)
                for _ in range(concurrency)
            ]
            for future in as_completed(futures):
                concurrent_results.append(future.result())

    all_results = sequential_results + concurrent_results
    durations = [float(item["durationMs"]) for item in all_results if item.get("ok")]
    failed = [item for item in all_results if not item.get("ok")]
    p95 = _percentile(durations, 95)
    return {
        "key": endpoint.key,
        "path": endpoint.path,
        "thresholdP95Ms": endpoint.p95_ms,
        "ok": not failed and p95 is not None and p95 <= endpoint.p95_ms,
        "total": len(all_results),
        "success": len(all_results) - len(failed),
        "failed": len(failed),
        "minMs": min(durations) if durations else None,
        "avgMs": round(statistics.fmean(durations), 2) if durations else None,
        "p95Ms": p95,
        "maxMs": max(durations) if durations else None,
        "failures": failed[:5],
        "sequential": sequential_results,
        "concurrent": concurrent_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("BACKEND_URL", "http://127.0.0.1:8099"))
    parser.add_argument("--admin-token", default=os.getenv("ADMIN_API_TOKEN") or os.getenv("SERVICE_API_TOKEN"))
    parser.add_argument("--sequential", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument(
        "--endpoint",
        action="append",
        choices=[item.key for item in DEFAULT_ENDPOINTS],
        help="Endpoint key to run. Can be passed multiple times; defaults to all endpoints.",
    )
    parser.add_argument("--json", action="store_true", help="Only print machine-readable JSON.")
    args = parser.parse_args()

    selected = set(args.endpoint or [])
    endpoints = [item for item in DEFAULT_ENDPOINTS if not selected or item.key in selected]
    endpoint_results = []
    for endpoint in endpoints:
        token = args.admin_token if endpoint.token_env else None
        endpoint_results.append(
            _run_endpoint(
                base_url=args.base_url,
                endpoint=endpoint,
                token=token,
                sequential=max(1, args.sequential),
                concurrency=max(0, args.concurrency),
                timeout=args.timeout,
            )
        )

    payload = {
        "ok": all(item["ok"] for item in endpoint_results),
        "baseUrl": args.base_url,
        "sequential": max(1, args.sequential),
        "concurrency": max(0, args.concurrency),
        "selectedEndpoints": [item.key for item in endpoints],
        "endpoints": endpoint_results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.json else None))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
