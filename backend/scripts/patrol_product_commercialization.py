#!/usr/bin/env python3
"""Patrol product commercialization copy/image/video flows.

Default mode is non-cost preview validation. Pass --include-live-visual or
--include-live-video only when running against an environment that is allowed to
submit real business runs and consume upstream credits.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
import time
from typing import Any

import httpx


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
DEFAULT_PRODUCT_IMAGE_URL = (
    "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/"
    "98904c502d9d4dd78432ec2bd1f79def/20260424/228be55f-1777009905.jpg"
)


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    payload: dict[str, Any]
    expected_conflict: bool = False


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


def _base_payload(*, product_image_url: str, tag: str) -> dict[str, Any]:
    return {
        "productImageUrl": product_image_url,
        "outputLanguage": "en-US",
        "marketRegion": "US",
        "commercePlatform": "Amazon / marketplace",
        "copyTone": "natural_professional",
        "copyScenarios": [
            "listing_title",
            "bullet_points",
            "detail_description",
            "ad_short_copy",
            "keyword_pack",
        ],
        "visualSupportMode": "recommendation",
        "videoScenario": "product_showcase_short",
        "aspectRatio": "16:9",
        "requestId": f"pcg-patrol-{tag}",
        "traceId": f"pcg-patrol-{tag}",
        "source": "product-commercialization-patrol",
    }


def _sample_product_fields() -> dict[str, Any]:
    return {
        "英文名称": "Floral printed lightweight hooded jacket",
        "产品型号": "POD-FLORAL-JACKET-001",
        "一级分类": "Apparel",
        "二级分类": "Outerwear",
        "产品材质": "lightweight woven fabric",
        "建议售价": "29.99",
        "卖点": "all-over floral print, relaxed hooded silhouette, casual layering",
    }


def _conflicting_product_fields() -> dict[str, Any]:
    return {
        "英文名称": "Women's knitted woolen socks",
        "产品型号": "GZ-1535",
        "一级分类": "饰品/配件",
        "二级分类": "穿搭配件",
        "产品材质": "包纱、涤纶、尼龙、橡筋",
        "产品重量": "110g",
    }


def _build_scenarios(*, product_image_url: str, tag: str) -> list[Scenario]:
    normal = _base_payload(product_image_url=product_image_url, tag=f"{tag}-normal")
    normal["productFields"] = _sample_product_fields()
    no_json = _base_payload(product_image_url=product_image_url, tag=f"{tag}-no-json")
    no_json["productFields"] = {}
    conflict = _base_payload(product_image_url=product_image_url, tag=f"{tag}-conflict")
    conflict["productFields"] = _conflicting_product_fields()
    return [
        Scenario("normal", "正常产品图 + 正常字段", normal),
        Scenario("no_json", "仅产品图，无导出 JSON", no_json),
        Scenario("conflict", "产品图与导出字段明显不一致", conflict, expected_conflict=True),
    ]


def _post_json(client: httpx.Client, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
    response = client.post(path, json=payload)
    return response.status_code, _json_or_text(response)


def _find_text(value: Any, needle: str) -> bool:
    if isinstance(value, dict):
        return any(_find_text(item, needle) for item in value.values())
    if isinstance(value, list):
        return any(_find_text(item, needle) for item in value)
    return needle.lower() in str(value or "").lower()


def _list_len(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _validate_preview(data: Any, scenario: Scenario) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return False, ["response is not an object"]
    if str(data.get("businessKey") or "") != "product_commercialization":
        errors.append("businessKey is not product_commercialization")
    if str(data.get("status") or "") not in {"preview", "previewed", "succeeded"}:
        errors.append("status is not preview/previewed")
    if not isinstance(data.get("resolvedProductFacts"), dict):
        errors.append("missing resolvedProductFacts")
    content_package = data.get("contentPackage")
    copy_package = data.get("copyPackage")
    if not isinstance(content_package, dict) and not isinstance(copy_package, dict):
        errors.append("missing contentPackage/copyPackage")
    else:
        package = content_package if isinstance(content_package, dict) else copy_package
        if not package:
            errors.append("content package is empty")
    visual_plan = data.get("visualAssetPlan")
    if not isinstance(visual_plan, dict):
        errors.append("missing visualAssetPlan")
    else:
        scene_count = _list_len(
            visual_plan.get("scenes")
            or visual_plan.get("recommendedScenes")
            or visual_plan.get("modelImageBriefs")
            or visual_plan.get("assets")
            or visual_plan.get("items")
        )
        if scene_count == 0:
            errors.append("visualAssetPlan has no scenes/items/recommendedScenes")
    video_plan = data.get("videoPlan")
    if not isinstance(video_plan, dict):
        errors.append("missing videoPlan")
    video_asset_plan = data.get("videoAssetPackagePlan")
    if not isinstance(video_asset_plan, dict):
        errors.append("missing videoAssetPackagePlan")
    else:
        for key in ("script", "storyboard", "keyframeNeeds", "compositionPlan"):
            if key not in video_asset_plan:
                errors.append(f"videoAssetPackagePlan missing {key}")
    if scenario.expected_conflict:
        review = data.get("review")
        facts = data.get("resolvedProductFacts")
        if not (_find_text(review, "CONFLICT") or _find_text(facts, "conflict") or _find_text(data, "冲突")):
            errors.append("expected image/json conflict was not surfaced")
    if "productFields" not in scenario.payload or not scenario.payload.get("productFields"):
        product_card = data.get("productCard")
        if _find_text(product_card, "Women's knitted woolen socks"):
            errors.append("no-json scenario leaked old sample product fields")
    return not errors, errors


def _preview_scenario(client: httpx.Client, scenario: Scenario) -> dict[str, Any]:
    status, data = _post_json(client, "/api/business/product-commercialization/preview", scenario.payload)
    ok, errors = _validate_preview(data, scenario) if status == 200 else (False, [f"HTTP_{status}"])
    fallback = None
    if isinstance(data, dict) and isinstance(data.get("copyGeneration"), dict):
        fallback = data["copyGeneration"].get("fallback")
    detail_parts = [f"status={status}"]
    if fallback is not None:
        detail_parts.append(f"copyFallback={fallback}")
    if errors:
        detail_parts.append("errors=" + "; ".join(errors[:4]))
    return {
        "case": scenario.key,
        "label": scenario.label,
        "mode": "preview",
        "ok": ok,
        "detail": " ".join(detail_parts),
        "response": data,
    }


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
        status, data = _post_json(client, "/api/business/runs/get", {"runId": run_id, "detail": "full"})
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


def _has_oss_url(values: Any) -> bool:
    if not isinstance(values, list):
        return False
    return any(isinstance(item, str) and "oss-" in item and item.startswith("http") for item in values)


def _validate_live_visual(run: dict[str, Any]) -> tuple[bool, str]:
    status = str(run.get("status") or "").lower()
    if status != "succeeded":
        return False, f"status={status or '-'} error={_short(run.get('errorMessage') or run.get('error'))}"
    if not _has_oss_url(run.get("imageUrls") or run.get("image_urls")):
        return False, "succeeded but no OSS image URL"
    result_payload = run.get("resultPayload") or run.get("result_payload") or {}
    if isinstance(result_payload, dict) and not (
        _find_text(result_payload, "GPT Image 2")
        or _find_text(result_payload, "gpt-image-2")
        or _find_text(result_payload, "gpt_image_2")
    ):
        return False, "visual result did not expose GPT Image 2/default route evidence"
    return True, f"status=succeeded images={_list_len(run.get('imageUrls') or run.get('image_urls'))}"


def _validate_live_video(run: dict[str, Any]) -> tuple[bool, str]:
    status = str(run.get("status") or "").lower()
    if status != "succeeded":
        return False, f"status={status or '-'} error={_short(run.get('errorMessage') or run.get('error'))}"
    result_payload = run.get("resultPayload") or run.get("result_payload") or {}
    if not isinstance(result_payload, dict):
        return False, "succeeded but resultPayload is missing"
    package = result_payload.get("videoAssetPackage") or result_payload.get("video_asset_package")
    if not isinstance(package, dict):
        return False, "succeeded but videoAssetPackage is missing"
    if not isinstance(package.get("script"), dict):
        return False, "videoAssetPackage missing script"
    segments = package.get("segmentVideos") or package.get("segment_videos")
    if not isinstance(segments, list) or not segments:
        return False, "videoAssetPackage has no segmentVideos"
    return True, f"status=succeeded segments={len(segments)} delivery={package.get('deliveryStatus') or '-'}"


def _submit_live_run(
    client: httpx.Client,
    *,
    label: str,
    payload: dict[str, Any],
    validator: Any,
    timeout_seconds: int,
    interval_seconds: float,
) -> dict[str, Any]:
    status, data = _post_json(client, "/api/business/product-commercialization/runs", payload)
    if status >= 400 or not isinstance(data, dict):
        return {
            "case": label,
            "label": label,
            "mode": "live",
            "ok": False,
            "detail": f"submit failed status={status} body={_short(data)}",
            "response": data,
        }
    run_id = str(data.get("runId") or data.get("id") or "").strip()
    if not run_id:
        return {
            "case": label,
            "label": label,
            "mode": "live",
            "ok": False,
            "detail": f"submit returned no runId status={status}",
            "response": data,
        }
    final = _poll_run(client, run_id, timeout_seconds=timeout_seconds, interval_seconds=interval_seconds)
    ok, detail = validator(final)
    return {
        "case": label,
        "label": label,
        "mode": "live",
        "ok": ok,
        "detail": f"runId={run_id} {detail}",
        "runId": run_id,
        "response": final,
    }


def _live_visual_payload(base: dict[str, Any], tag: str) -> dict[str, Any]:
    payload = dict(base)
    payload.update(
        {
            "action": "visual_generate",
            "visualSupportMode": "generate",
            "visualScenes": ["social-ad-cover"],
            "requestId": f"pcg-patrol-visual-{tag}",
            "traceId": f"pcg-patrol-visual-{tag}",
        }
    )
    return payload


def _live_video_payload(base: dict[str, Any], *, tag: str, executor_id: str, target_duration: int) -> dict[str, Any]:
    payload = dict(base)
    payload.update(
        {
            "action": "video_generate",
            "executorId": executor_id or None,
            "targetDurationSeconds": target_duration,
            "durationSeconds": None,
            "requestId": f"pcg-patrol-video-{tag}",
            "traceId": f"pcg-patrol-video-{tag}",
        }
    )
    return payload


def _write_report(summary: dict[str, Any], report_path: str) -> str:
    path = Path(report_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(path)


def _print_result(item: dict[str, Any]) -> None:
    marker = "PASS" if item.get("ok") else "FAIL"
    print(f"[{marker}] {item.get('label')}({item.get('case')}): {item.get('detail')}", flush=True)


def _redact_summary(summary: dict[str, Any]) -> dict[str, Any]:
    compact = dict(summary)
    compact["results"] = [
        {
            "case": item.get("case"),
            "label": item.get("label"),
            "mode": item.get("mode"),
            "ok": item.get("ok"),
            "detail": item.get("detail"),
            "runId": item.get("runId"),
        }
        for item in summary.get("results", [])
    ]
    compact["failedItems"] = [
        {
            "case": item.get("case"),
            "label": item.get("label"),
            "mode": item.get("mode"),
            "ok": item.get("ok"),
            "detail": item.get("detail"),
            "runId": item.get("runId"),
        }
        for item in summary.get("failedItems", [])
    ]
    return compact


def main() -> int:
    parser = argparse.ArgumentParser(description="Patrol PODI product commercialization flows.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8099", help="Backend base URL.")
    parser.add_argument(
        "--token",
        default=os.getenv("SERVICE_API_TOKEN") or os.getenv("PODI_BUSINESS_API_KEY") or "",
        help="Optional service/business token. Prefer env vars; command output redacts only summaries.",
    )
    parser.add_argument("--product-image-url", default=os.getenv("PODI_PRODUCT_IMAGE_URL") or DEFAULT_PRODUCT_IMAGE_URL)
    parser.add_argument("--request-timeout", type=int, default=180, help="Per HTTP request timeout seconds.")
    parser.add_argument("--timeout", type=int, default=1200, help="Live run polling timeout seconds.")
    parser.add_argument("--interval", type=float, default=8.0, help="Live run polling interval seconds.")
    parser.add_argument("--include-live-visual", action="store_true", help="Submit a paid GPT Image 2 visual task.")
    parser.add_argument("--include-live-video", action="store_true", help="Submit a paid video asset package task.")
    parser.add_argument(
        "--video-executor",
        default=os.getenv("PODI_VIDEO_EXECUTOR_ID") or "",
        help="Optional executor id, for example executor_vidu_default or executor_kie_market_default.",
    )
    parser.add_argument("--target-duration", type=int, default=8, help="Target duration for the live video package.")
    parser.add_argument("--report", default="", help="Optional JSON report path.")
    parser.add_argument("--json", action="store_true", help="Print full machine-readable summary.")
    parser.add_argument("--compact-json", action="store_true", help="Print compact machine-readable summary.")
    args = parser.parse_args()

    tag = _now_tag()
    timeout = httpx.Timeout(float(max(10, args.request_timeout)), connect=10.0)
    results: list[dict[str, Any]] = []
    with httpx.Client(
        base_url=str(args.base_url).rstrip("/"),
        headers=_headers(args.token),
        timeout=timeout,
        trust_env=False,
    ) as client:
        scenarios = _build_scenarios(product_image_url=str(args.product_image_url).strip(), tag=tag)
        for scenario in scenarios:
            try:
                item = _preview_scenario(client, scenario)
            except Exception as exc:
                item = {
                    "case": scenario.key,
                    "label": scenario.label,
                    "mode": "preview",
                    "ok": False,
                    "detail": f"request failed: {_short(repr(exc))}",
                    "response": None,
                }
            results.append(item)
            if not args.json and not args.compact_json:
                _print_result(item)

        normal_payload = dict(scenarios[0].payload)
        if args.include_live_visual:
            item = _submit_live_run(
                client,
                label="GPT Image 2 配图真实任务",
                payload=_live_visual_payload(normal_payload, tag),
                validator=_validate_live_visual,
                timeout_seconds=args.timeout,
                interval_seconds=args.interval,
            )
            results.append(item)
            if not args.json and not args.compact_json:
                _print_result(item)
        if args.include_live_video:
            item = _submit_live_run(
                client,
                label="视频素材包真实任务",
                payload=_live_video_payload(
                    normal_payload,
                    tag=tag,
                    executor_id=str(args.video_executor or "").strip(),
                    target_duration=max(1, min(60, int(args.target_duration))),
                ),
                validator=_validate_live_video,
                timeout_seconds=args.timeout,
                interval_seconds=args.interval,
            )
            results.append(item)
            if not args.json and not args.compact_json:
                _print_result(item)

    failed_items = [item for item in results if not item.get("ok")]
    summary = {
        "ok": not failed_items,
        "baseUrl": str(args.base_url).rstrip("/"),
        "generatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "tag": tag,
        "liveVisual": bool(args.include_live_visual),
        "liveVideo": bool(args.include_live_video),
        "productImageUrl": str(args.product_image_url).strip(),
        "total": len(results),
        "passed": len(results) - len(failed_items),
        "failed": len(failed_items),
        "results": results,
        "failedItems": failed_items,
    }
    if args.report:
        report_path = _write_report(summary, str(args.report))
        if not args.json and not args.compact_json:
            print(f"[PASS] 巡检报告: {report_path}", flush=True)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    elif args.compact_json:
        print(json.dumps(_redact_summary(summary), ensure_ascii=False, indent=2, default=str))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
