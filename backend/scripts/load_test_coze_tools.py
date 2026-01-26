#!/usr/bin/env python3
"""Light load test for PODI "ability layer" via Coze plugin tool endpoints.

Why this script exists
- "能力层并发" here means: our PODI backend wrappers for abilities (coze plugin tools + ability tasks),
  not Coze-side workflow fanout.
- We hit `/api/coze/podi/tools/{provider}/{capability_key}` because:
  - ComfyUI is submit+poll (taskId + /tasks/get)
  - Other providers are synchronous but still need executor-level concurrency control.

Usage (dev machine)
  export PODI_BASE_URL=http://127.0.0.1:8099
  # SERVICE_API_TOKEN is read from backend settings (SERVICE_API_TOKEN) if not provided.
  python3 -u backend/scripts/load_test_coze_tools.py --qps 5 --duration 60 --providers comfyui,kie,volcengine,baidu,podi

Notes
- Requires the backend DB migration `20260126_add_eval_run_output_json` to be applied if you pulled latest main:
    cd backend && alembic upgrade head
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "backend"))

from app.core.config import get_settings  # noqa: E402


@dataclass
class Target:
    provider: str
    capability_key: str
    # capability/ability schema as returned by /api/abilities
    input_schema: dict[str, Any] | None


PREFERRED_KEYS: dict[str, list[str]] = {
    "podi": ["set_dpi", "upscale_resize", "expand_mask_color"],
    "comfyui": ["sifang_lianxu", "huawen_kuotu", "yinhua_tiqu", "jisu_chuli", "zhongsu_tisheng"],
    "kie": ["nano_banana_pro_image_to_image", "flux_2_pro_image_to_image", "sora2_pro_text_to_video"],
    # Best-effort (may change as catalogue evolves)
    "volcengine": ["seedream", "doubao", "seedance", "seed"],
    "baidu": ["image", "process", "enhance"],
}


def _now() -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _coerce_int(v: Any) -> int | None:
    try:
        return int(str(v).strip())
    except Exception:
        return None


def _build_payload_from_schema(schema: dict[str, Any] | None, *, image_url: str) -> dict[str, Any]:
    """Best-effort payload builder for `/tools/{provider}/{capability_key}`.

    We fill required fields with conservative defaults to avoid Coze 4000 "missing required parameters".
    """

    payload: dict[str, Any] = {"url": image_url}
    if not isinstance(schema, dict):
        return payload
    fields = schema.get("fields")
    if not isinstance(fields, list):
        return payload

    for f in fields:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name") or "").strip()
        if not name or name in {"url", "imageUrl", "image_url"}:
            continue
        required = bool(f.get("required"))
        ftype = str(f.get("type") or "text").lower()
        dv = f.get("defaultValue")
        if dv is None:
            dv = f.get("default")

        # Prompt-like fields: even if not marked required, many providers will reject empty prompts.
        if name in {"prompt", "positive_prompt", "question", "text"} and name not in payload:
            if isinstance(dv, (str, int, float, bool)):
                payload[name] = str(dv) if not isinstance(dv, str) else dv
            else:
                payload[name] = "test"
            continue

        # Use schema-provided defaults if possible.
        if isinstance(dv, (str, int, float, bool)):
            payload[name] = str(dv) if not isinstance(dv, str) else dv
            continue

        if ftype == "select":
            opts = f.get("options")
            if isinstance(opts, list) and opts:
                first = opts[0]
                if isinstance(first, dict) and first.get("value") is not None:
                    payload[name] = str(first["value"])
                else:
                    payload[name] = str(first)
            elif required:
                payload[name] = "1"
            continue

        if ftype in {"switch", "boolean"}:
            if required:
                payload[name] = "true"
            continue

        if ftype == "image":
            payload[name] = image_url
            continue

        # For numeric-like fields, default to 0/1024 depending on common patterns.
        if name in {"width", "height"}:
            payload[name] = "1024"
            continue
        if name.startswith("expand_"):
            payload[name] = "0"
            continue
        if name in {"dpi", "pdi"}:
            payload[name] = "300"
            continue

        # Fallback: satisfy required strings with whitespace.
        if required:
            payload[name] = " "

    return payload


async def _fetch_targets(podi_base: str, *, providers: set[str]) -> list[Target]:
    url = f"{podi_base.rstrip('/')}/api/abilities"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []

    targets: list[Target] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        provider = str(it.get("provider") or "").strip().lower()
        if provider not in providers:
            continue
        # Public API uses camelCase.
        capability_key = str(it.get("capabilityKey") or it.get("capability_key") or "").strip()
        if not capability_key:
            continue
        schema = it.get("inputSchema") if isinstance(it.get("inputSchema"), dict) else None
        targets.append(Target(provider=provider, capability_key=capability_key, input_schema=schema))

    # Keep deterministic order (avoid mixing noise across runs).
    def _rank(t: Target) -> tuple[int, str, str]:
        pref = PREFERRED_KEYS.get(t.provider, [])
        # Exact match first; then substring match for rough buckets (volcengine/baidu).
        if t.capability_key in pref:
            return (0, f"{pref.index(t.capability_key):04d}", f"{t.provider}:{t.capability_key}")
        for i, key in enumerate(pref, start=1):
            if key and key in t.capability_key:
                return (i, f"{i:04d}", f"{t.provider}:{t.capability_key}")
        return (999, "9999", f"{t.provider}:{t.capability_key}")

    targets.sort(key=_rank)
    return targets


@dataclass
class Sample:
    ok: bool
    status_code: int | None
    latency_ms: int
    provider: str
    capability_key: str
    error: str | None = None


async def _one_call(
    client: httpx.AsyncClient,
    *,
    podi_base: str,
    token: str,
    target: Target,
    image_url: str,
) -> Sample:
    url = f"{podi_base.rstrip('/')}/api/coze/podi/tools/{target.provider}/{target.capability_key}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = _build_payload_from_schema(target.input_schema, image_url=image_url)
    t0 = time.perf_counter()
    try:
        resp = await client.post(url, headers=headers, json=payload)
        elapsed = int((time.perf_counter() - t0) * 1000)
        if resp.status_code >= 400:
            return Sample(
                ok=False,
                status_code=resp.status_code,
                latency_ms=elapsed,
                provider=target.provider,
                capability_key=target.capability_key,
                error=(resp.text or "")[:300],
            )
        return Sample(
            ok=True,
            status_code=resp.status_code,
            latency_ms=elapsed,
            provider=target.provider,
            capability_key=target.capability_key,
        )
    except Exception as exc:
        elapsed = int((time.perf_counter() - t0) * 1000)
        return Sample(
            ok=False,
            status_code=None,
            latency_ms=elapsed,
            provider=target.provider,
            capability_key=target.capability_key,
            error=str(exc),
        )


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    values_sorted = sorted(values)
    k = int(round((len(values_sorted) - 1) * p))
    return values_sorted[max(0, min(k, len(values_sorted) - 1))]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--podi-base", default=os.environ.get("PODI_BASE_URL", "http://127.0.0.1:8099"))
    parser.add_argument("--qps", type=float, default=5.0)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--providers", default="comfyui,kie,volcengine,baidu,podi")
    parser.add_argument("--max-per-provider", type=int, default=1, help="Limit targets per provider (default: 1)")
    parser.add_argument("--inflight-cap", type=int, default=40, help="Backpressure cap for in-flight requests")
    parser.add_argument(
        "--image-url",
        default=os.environ.get(
            "LOAD_TEST_IMAGE_URL",
            "https://podi.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin/20260120/fc661480-1768882378.jpg",
        ),
    )
    args = parser.parse_args()

    settings = get_settings()
    token = (os.environ.get("SERVICE_API_TOKEN") or settings.service_api_token or "").strip()
    if not token:
        print("missing SERVICE_API_TOKEN (env or backend settings.service_api_token)")
        return 2

    providers = {p.strip().lower() for p in str(args.providers).split(",") if p.strip()}
    targets_all = await _fetch_targets(args.podi_base, providers=providers)
    if not targets_all:
        print(f"no targets found for providers={sorted(providers)}")
        return 2

    # Keep only N targets per provider to make runs stable/predictable at small QPS.
    max_per = max(1, int(args.max_per_provider))
    targets: list[Target] = []
    per_provider: dict[str, int] = {}
    for t in targets_all:
        n = per_provider.get(t.provider, 0)
        if n >= max_per:
            continue
        targets.append(t)
        per_provider[t.provider] = n + 1
    print(f"[{_now()}] PODI ability-layer load test (QPS={args.qps}, duration={args.duration}s)")
    print(f"- PODI_BASE: {args.podi_base}")
    print(f"- providers: {', '.join(sorted(providers))}")
    print(f"- targets: {len(targets)}")
    for t in targets[:12]:
        print(f"  - {t.provider}:{t.capability_key}")
    print("")

    interval = 1.0 / max(0.1, float(args.qps))
    stop_at = time.monotonic() + max(1.0, float(args.duration))

    samples: list[Sample] = []
    in_flight: set[asyncio.Task[Sample]] = set()
    idx = 0

    limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)
    async with httpx.AsyncClient(timeout=60, limits=limits) as client:
        next_at = time.monotonic()
        while time.monotonic() < stop_at or in_flight:
            now = time.monotonic()
            if now >= stop_at:
                # stop scheduling new requests
                pass
            else:
                if now >= next_at and len(in_flight) < max(1, int(args.inflight_cap)):
                    target = targets[idx % len(targets)]
                    idx += 1
                    in_flight.add(
                        asyncio.create_task(
                            _one_call(
                                client,
                                podi_base=args.podi_base,
                                token=token,
                                target=target,
                                image_url=args.image_url,
                            )
                        )
                    )
                    next_at += interval

            if in_flight:
                done, in_flight = await asyncio.wait(in_flight, timeout=0.05, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    samples.append(t.result())
            else:
                await asyncio.sleep(0.02)

    ok = [s for s in samples if s.ok]
    fail = [s for s in samples if not s.ok]
    lat = [s.latency_ms for s in samples]
    lat_ok = [s.latency_ms for s in ok]

    def _group(items: list[Sample]) -> dict[str, list[Sample]]:
        out: dict[str, list[Sample]] = {}
        for s in items:
            k = f"{s.provider}:{s.capability_key}"
            out.setdefault(k, []).append(s)
        return out

    print("=== Summary ===")
    print(f"total={len(samples)} ok={len(ok)} fail={len(fail)} err_rate={(len(fail)/max(1,len(samples))):.2%}")
    if lat:
        print(f"lat(ms): p50={_percentile(lat,0.50)} p95={_percentile(lat,0.95)} max={max(lat)}")
    if lat_ok:
        print(f"lat_ok(ms): p50={_percentile(lat_ok,0.50)} p95={_percentile(lat_ok,0.95)} max={max(lat_ok)}")

    if fail:
        by_code: dict[str, int] = {}
        for s in fail:
            key = str(s.status_code) if s.status_code is not None else "exception"
            by_code[key] = by_code.get(key, 0) + 1
        top = sorted(by_code.items(), key=lambda kv: kv[1], reverse=True)[:8]
        print(f"fail_by_code: {top}")

        # show a few examples
        examples = fail[:5]
        for ex in examples:
            print(f"- fail {ex.provider}:{ex.capability_key} status={ex.status_code} ms={ex.latency_ms} err={ex.error!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
