#!/usr/bin/env python3
"""Patrol product commercialization copy/image/video flows.

Default mode is non-cost preview validation. Pass --include-live-visual,
--include-live-keyframes, --include-live-video, or --include-live-3d-render only
when running against an environment that is allowed to submit real business runs
and consume upstream credits or render resources.
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
DEFAULT_3D_TEXTURE_URL = DEFAULT_PRODUCT_IMAGE_URL


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


def _video_planning_context() -> dict[str, Any]:
    return {
        "coreMessage": "Open with the complete product shape and visible print before any detail movement.",
        "targetAudience": "US marketplace shoppers and gift buyers",
        "usageScene": "clean ecommerce tabletop product showcase",
        "shotPreference": "wide hero hold first, then gentle orbit or slow push-in without cropping handles or edges",
        "avoid": "no embedded text, watermark, logo, price tag, unrealistic deformation, or cropped product bottom",
        "fields": [
            {
                "id": "quality_gate",
                "label": "质量门禁",
                "value": "first shot must keep the full product readable",
                "source": "patrol",
            }
        ],
        "source": "product-commercialization-patrol",
    }


def _sample_product_fields() -> dict[str, Any]:
    return {
        "英文名称": "Preppy Western Coastal Print 100% Cotton Tote Bag",
        "产品型号": "POD-TOTE-WESTERN-COASTAL-001",
        "一级分类": "Bags",
        "二级分类": "Tote Bags",
        "产品材质": "100% cotton canvas",
        "建议售价": "29.99",
        "卖点": "western coastal illustration print, reusable lightweight shoulder bag, foldable daily shopping and beach tote",
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


def _get_json(client: httpx.Client, path: str) -> tuple[int, Any]:
    response = client.get(path)
    return response.status_code, _json_or_text(response)


def _find_text(value: Any, needle: str) -> bool:
    if isinstance(value, dict):
        return any(_find_text(item, needle) for item in value.values())
    if isinstance(value, list):
        return any(_find_text(item, needle) for item in value)
    return needle.lower() in str(value or "").lower()


def _list_len(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean_url(value: Any) -> str:
    text = str(value or "").strip()
    return text if text.startswith("http") else ""


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


def _promo_video_plan_payload(*, product_image_url: str, tag: str) -> dict[str, Any]:
    return {
        "productImageUrl": product_image_url,
        "productImages": [
            {"url": product_image_url, "role": "primary", "label": "主图", "isPrimary": True},
        ],
        "productFields": _sample_product_fields(),
        "outputLanguage": "en-US",
        "marketRegion": "US",
        "videoScenario": "product_showcase_short",
        "targetDurationSeconds": 15,
        "aspectRatio": "16:9",
        "videoPlanningContext": _video_planning_context(),
        "extraPrompt": "Patrol: preserve product identity and keep the first shot fully readable.",
        "requestId": f"promo-video-plan-patrol-{tag}",
        "traceId": f"promo-video-plan-patrol-{tag}",
        "source": "product-commercialization-patrol",
    }


def _validate_promo_video_plan(data: Any) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return False, ["response is not an object"]
    if str(data.get("businessKey") or "") != "promo_video":
        errors.append("businessKey is not promo_video")
    if not isinstance(data.get("resolvedProductFacts"), dict):
        errors.append("missing resolvedProductFacts")
    video_plan = data.get("videoPlan")
    if not isinstance(video_plan, dict):
        errors.append("missing videoPlan")
    else:
        if not isinstance(video_plan.get("planner"), dict):
            errors.append("videoPlan missing planner evidence")
        if not isinstance(video_plan.get("directorBrief"), dict):
            errors.append("videoPlan missing directorBrief")
        if _list_len(video_plan.get("storyboard")) == 0:
            errors.append("videoPlan storyboard is empty")
    package_plan = data.get("videoAssetPackagePlan")
    if not isinstance(package_plan, dict):
        errors.append("missing videoAssetPackagePlan")
    else:
        shot_packages = package_plan.get("shotPackages")
        if not isinstance(shot_packages, list) or not shot_packages:
            errors.append("videoAssetPackagePlan has no shotPackages")
        else:
            first = shot_packages[0] if isinstance(shot_packages[0], dict) else {}
            for key in ("videoPrompt", "firstFramePrompt", "lastFramePrompt", "cameraMovement", "keyframeNeeds"):
                if key not in first:
                    errors.append(f"first shotPackage missing {key}")
    execution = data.get("execution")
    if isinstance(execution, dict) and (execution.get("imageGenerated") or execution.get("videoGenerated")):
        errors.append("plan triggered image/video generation")
    return not errors, errors


def _preview_promo_video_plan(client: httpx.Client, *, product_image_url: str, tag: str) -> dict[str, Any]:
    payload = _promo_video_plan_payload(product_image_url=product_image_url, tag=tag)
    status, data = _post_json(client, "/api/business/promo-video/plan", payload)
    ok, errors = _validate_promo_video_plan(data) if status == 200 else (False, [f"HTTP_{status}"])
    detail_parts = [f"status={status}"]
    if errors:
        detail_parts.append("errors=" + "; ".join(errors[:5]))
    return {
        "case": "promo_video_plan",
        "label": "正式产品视频规划接口",
        "mode": "promo-video-plan",
        "ok": ok,
        "detail": " ".join(detail_parts),
        "request": payload,
        "response": data,
    }


def _product_3d_preview_payload(*, texture_url: str, tag: str) -> dict[str, Any]:
    return {
        "modelKey": "cup_1660",
        "materialSlot": "front",
        "textureImageUrl": texture_url,
        "textureSlots": [
            {"materialSlot": "front", "imageUrl": texture_url, "label": "正面主贴图区"},
            {"materialSlot": "mouth", "imageUrl": texture_url, "label": "杯口测试贴图"},
        ],
        "cameraPreset": "orbit_360",
        "cameraDistance": "wide",
        "scenePreset": "desktop_lifestyle",
        "motionPath": [{"x": 0.22, "y": 0.66}, {"x": 0.5, "y": 0.5}, {"x": 0.78, "y": 0.42}],
        "durationSeconds": 6,
        "aspectRatio": "16:9",
        "outputMode": "plan_only",
        "requestId": f"product-3d-preview-patrol-{tag}",
        "traceId": f"product-3d-preview-patrol-{tag}",
        "source": "product-commercialization-patrol",
    }


def _product_3d_render_payload(*, texture_url: str, tag: str) -> dict[str, Any]:
    payload = _product_3d_preview_payload(texture_url=texture_url, tag=tag)
    payload.update(
        {
            "cameraPreset": "social_arc",
            "cameraDistance": "close",
            "scenePreset": "desktop_lifestyle",
            "outputMode": "render_video",
            "requestId": f"product-3d-render-patrol-{tag}",
            "traceId": f"product-3d-render-patrol-{tag}",
        }
    )
    return payload


def _validate_product_3d_catalog(data: Any) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return False, ["response is not an object"]
    if str(data.get("businessKey") or "") != "product_3d_render_video":
        errors.append("businessKey is not product_3d_render_video")
    if _list_len(data.get("models")) < 2:
        errors.append("catalog has fewer than two models")
    scenes = data.get("scenePresets")
    if not isinstance(scenes, list) or len(scenes) < 6:
        errors.append("catalog scenePresets missing expected scene library")
    else:
        keys = {str(item.get("key") or "") for item in scenes if isinstance(item, dict)}
        for key in ("clean_studio", "desktop_lifestyle", "retail_shelf"):
            if key not in keys:
                errors.append(f"scene preset missing {key}")
        desktop_scene = next((item for item in scenes if isinstance(item, dict) and item.get("key") == "desktop_lifestyle"), {})
        render_elements = desktop_scene.get("renderElements") if isinstance(desktop_scene, dict) else None
        if not isinstance(render_elements, list) or not render_elements:
            errors.append("desktop_lifestyle missing renderElements")
        elif not any(isinstance(item, dict) and item.get("elementId") == "wood_tabletop" for item in render_elements):
            errors.append("desktop_lifestyle renderElements missing wood_tabletop")
    distances = data.get("cameraDistances")
    if not isinstance(distances, list):
        errors.append("catalog missing cameraDistances")
    else:
        keys = {str(item.get("key") or "") for item in distances if isinstance(item, dict)}
        for key in ("wide", "standard", "close"):
            if key not in keys:
                errors.append(f"camera distance missing {key}")
    sources = data.get("sceneAssetSources")
    if not isinstance(sources, list) or len(sources) < 2:
        errors.append("catalog missing sceneAssetSources")
    else:
        source_map = {str(item.get("provider") or ""): item for item in sources if isinstance(item, dict)}
        for provider in ("Poly Haven", "ambientCG"):
            source = source_map.get(provider)
            if not isinstance(source, dict):
                errors.append(f"scene asset source missing {provider}")
                continue
            if str(source.get("license") or "").upper().find("CC0") < 0:
                errors.append(f"scene asset source {provider} is not CC0")
            if _list_len(source.get("ingestGate")) == 0:
                errors.append(f"scene asset source {provider} missing ingestGate")
            if _list_len(source.get("candidateAssets")) == 0:
                errors.append(f"scene asset source {provider} missing candidateAssets")
    endpoints = data.get("endpoints")
    if not isinstance(endpoints, dict) or endpoints.get("renderRun") != "POST /api/business/product-3d-render-video/runs":
        errors.append("catalog missing renderRun endpoint")
    return not errors, errors


def _validate_product_3d_preview(data: Any) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return False, ["response is not an object"]
    if str(data.get("businessKey") or "") != "product_3d_render_video":
        errors.append("businessKey is not product_3d_render_video")
    render_plan = data.get("renderPlan")
    if not isinstance(render_plan, dict):
        errors.append("missing renderPlan")
        return False, errors
    scene = render_plan.get("scene")
    camera = render_plan.get("camera")
    motion = render_plan.get("motionPath")
    texture = render_plan.get("textureApplication")
    if not isinstance(scene, dict):
        errors.append("missing renderPlan.scene")
    else:
        if not isinstance(scene.get("asset"), dict):
            errors.append("scene missing asset evidence")
        if not isinstance(scene.get("fusion"), dict):
            errors.append("scene missing fusion evidence")
        render_elements = scene.get("renderElements")
        if not isinstance(render_elements, list) or not render_elements:
            errors.append("scene missing renderElements")
        elif not all(isinstance(item, dict) and item.get("elementId") and item.get("occlusion") for item in render_elements):
            errors.append("scene renderElements missing elementId/occlusion")
    if not isinstance(camera, dict):
        errors.append("missing renderPlan.camera")
    else:
        framing = camera.get("framing")
        if not isinstance(framing, dict) or framing.get("mode") != "fit_product_safe_bounds":
            errors.append("camera framing is not fit_product_safe_bounds")
    if not isinstance(motion, dict) or _list_len(motion.get("points")) < 2:
        errors.append("motionPath missing normalized points")
    if not isinstance(texture, dict) or _list_len(texture.get("textureSlots")) < 2:
        errors.append("textureApplication missing multi-slot evidence")
    readiness = data.get("assetReadiness")
    if not isinstance(readiness, dict) or readiness.get("renderWorkerReady") is not True:
        errors.append("renderWorkerReady is not true")
    return not errors, errors


def _preview_product_3d(client: httpx.Client, *, texture_url: str, tag: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    catalog_status, catalog_data = _get_json(client, "/api/business/product-3d-render-video/catalog")
    catalog_ok, catalog_errors = (
        _validate_product_3d_catalog(catalog_data) if catalog_status == 200 else (False, [f"HTTP_{catalog_status}"])
    )
    results.append(
        {
            "case": "product_3d_catalog",
            "label": "3D 渲染视频能力目录",
            "mode": "product-3d-catalog",
            "ok": catalog_ok,
            "detail": f"status={catalog_status}" + (f" errors={'; '.join(catalog_errors[:5])}" if catalog_errors else ""),
            "response": catalog_data,
        }
    )

    payload = _product_3d_preview_payload(texture_url=texture_url, tag=tag)
    preview_status, preview_data = _post_json(client, "/api/business/product-3d-render-video/preview", payload)
    preview_ok, preview_errors = (
        _validate_product_3d_preview(preview_data) if preview_status == 200 else (False, [f"HTTP_{preview_status}"])
    )
    results.append(
        {
            "case": "product_3d_preview",
            "label": "3D 渲染视频方案预览",
            "mode": "product-3d-preview",
            "ok": preview_ok,
            "detail": f"status={preview_status}" + (f" errors={'; '.join(preview_errors[:5])}" if preview_errors else ""),
            "request": payload,
            "response": preview_data,
        }
    )
    return results


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


def _validate_live_video(run: dict[str, Any], *, require_confirmed_keyframes: bool = False) -> tuple[bool, str]:
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
    if require_confirmed_keyframes:
        video_result = result_payload.get("videoResult") or result_payload.get("video_result")
        confirmed_keyframes = [
            item
            for item in _as_list(package.get("keyframes") or package.get("key_frames"))
            if isinstance(item, dict) and item.get("confirmed") is True and _clean_url(item.get("imageUrl") or item.get("ossUrl"))
        ]
        result_segments = [
            item
            for item in _as_list(video_result.get("segments") if isinstance(video_result, dict) else [])
            if isinstance(item, dict)
        ]
        segment_refs = [
            _clean_url(item.get("referenceImageUrl") or item.get("reference_image_url"))
            for item in [*segments, *result_segments]
            if isinstance(item, dict)
        ]
        if not confirmed_keyframes:
            return False, "video task did not preserve confirmed keyframes"
        if not any(ref for ref in segment_refs):
            return False, "video task did not expose confirmed keyframe reference evidence"
    return True, f"status=succeeded segments={len(segments)} delivery={package.get('deliveryStatus') or '-'}"


def _validate_live_keyframes(run: dict[str, Any]) -> tuple[bool, str]:
    status = str(run.get("status") or "").lower()
    if status != "succeeded":
        return False, f"status={status or '-'} error={_short(run.get('errorMessage') or run.get('error'))}"
    if not _has_oss_url(run.get("imageUrls") or run.get("image_urls")):
        return False, "succeeded but no OSS keyframe image URL"
    result_payload = run.get("resultPayload") or run.get("result_payload") or {}
    if not isinstance(result_payload, dict):
        return False, "succeeded but resultPayload is missing"
    package = result_payload.get("videoAssetPackage") or result_payload.get("video_asset_package")
    if not isinstance(package, dict):
        return False, "succeeded but videoAssetPackage is missing"
    keyframes = package.get("keyframes") or package.get("key_frames")
    if not isinstance(keyframes, list) or not keyframes:
        return False, "videoAssetPackage has no keyframes"
    delivery_status = str(package.get("deliveryStatus") or package.get("delivery_status") or "").strip()
    if delivery_status != "keyframes_ready":
        return False, f"deliveryStatus={delivery_status or '-'} expected keyframes_ready"
    if run.get("videoUrls") or run.get("video_urls"):
        return False, "keyframe task returned videoUrls; action boundary is mixed"
    return True, f"status=succeeded keyframes={len(keyframes)} delivery={delivery_status}"


def _extract_confirmed_video_keyframes(run: dict[str, Any]) -> list[dict[str, Any]]:
    result_payload = run.get("resultPayload") or run.get("result_payload") or {}
    if not isinstance(result_payload, dict):
        return []
    package = result_payload.get("videoAssetPackage") or result_payload.get("video_asset_package")
    if not isinstance(package, dict):
        return []
    extracted: list[dict[str, Any]] = []
    for fallback_index, item in enumerate(_as_list(package.get("keyframes") or package.get("key_frames")), start=1):
        if not isinstance(item, dict):
            continue
        image_url = _clean_url(
            item.get("imageUrl")
            or item.get("image_url")
            or item.get("ossUrl")
            or item.get("oss_url")
            or item.get("storedUrl")
            or item.get("stored_url")
        )
        if not image_url:
            continue
        raw_segment = item.get("segmentIndex") or item.get("segment_index") or item.get("shot") or item.get("segment")
        try:
            segment_index = int(str(raw_segment or fallback_index).strip())
        except (TypeError, ValueError):
            segment_index = fallback_index
        extracted.append(
            {
                "role": str(item.get("role") or "confirmed_keyframe").strip() or "confirmed_keyframe",
                "shot": str(item.get("shot") or segment_index),
                "segmentIndex": segment_index,
                "imageUrl": image_url,
                "confirmed": True,
                "source": "patrol_confirmed_video_keyframe",
            }
        )
    return extracted


def _validate_live_product_3d_render(run: dict[str, Any]) -> tuple[bool, str]:
    status = str(run.get("status") or "").lower()
    if status != "succeeded":
        return False, f"status={status or '-'} error={_short(run.get('errorMessage') or run.get('error'))}"
    if str(run.get("businessKey") or "") != "product_3d_render_video":
        return False, f"businessKey={run.get('businessKey') or '-'} expected product_3d_render_video"
    if not _has_oss_url(run.get("videoUrls") or run.get("video_urls")):
        return False, "succeeded but no OSS video URL"
    if not _has_oss_url(run.get("imageUrls") or run.get("image_urls")):
        return False, "succeeded but no OSS cover image URL"
    result_payload = run.get("resultPayload") or run.get("result_payload") or {}
    if not isinstance(result_payload, dict):
        return False, "succeeded but resultPayload is missing"
    package = result_payload.get("renderAssetPackage") or result_payload.get("render_asset_package")
    if not isinstance(package, dict):
        return False, "succeeded but renderAssetPackage is missing"
    if str(package.get("deliveryStatus") or package.get("delivery_status") or "") != "assets_ready":
        return False, f"deliveryStatus={package.get('deliveryStatus') or package.get('delivery_status') or '-'} expected assets_ready"
    manifest = package.get("manifest")
    if not isinstance(manifest, dict):
        return False, "renderAssetPackage missing manifest"
    scene_asset = manifest.get("sceneAsset")
    scene_fusion = manifest.get("sceneFusion")
    scene_elements = manifest.get("sceneElements")
    framing = manifest.get("framingPolicy")
    texture = manifest.get("textureApplication")
    if not isinstance(scene_asset, dict) or not scene_asset.get("assetId"):
        return False, "manifest missing sceneAsset evidence"
    if not isinstance(scene_fusion, dict) or not scene_fusion.get("landingZone"):
        return False, "manifest missing sceneFusion evidence"
    if not isinstance(scene_elements, list) or not scene_elements:
        return False, "manifest missing sceneElements evidence"
    if not all(isinstance(item, dict) and item.get("elementId") and item.get("depthLayer") for item in scene_elements):
        return False, "manifest sceneElements missing elementId/depthLayer"
    if not isinstance(framing, dict) or framing.get("mode") != "fit_product_safe_bounds":
        return False, "manifest framingPolicy is not fit_product_safe_bounds"
    if not isinstance(texture, dict) or int(texture.get("textureSlotCount") or 0) < 1:
        return False, "manifest missing textureApplication slot evidence"
    if not manifest.get("cameraDistance"):
        return False, "manifest missing cameraDistance"
    if _list_len(manifest.get("motionPath")) < 2:
        return False, "manifest missing motionPath"
    quota_units = run.get("quotaUnits") if "quotaUnits" in run else run.get("quota_units")
    if quota_units not in (0, None):
        return False, f"quotaUnits={quota_units} expected 0/no-charge for lightweight 3D renderer"
    return (
        True,
        "status=succeeded "
        f"videos={_list_len(run.get('videoUrls') or run.get('video_urls'))} "
        f"covers={_list_len(run.get('imageUrls') or run.get('image_urls'))} "
        f"scene={scene_asset.get('assetId')} cameraDistance={manifest.get('cameraDistance')}",
    )


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
        "request": payload,
        "response": final,
    }


def _submit_live_product_3d_render_run(
    client: httpx.Client,
    *,
    texture_url: str,
    tag: str,
    timeout_seconds: int,
    interval_seconds: float,
) -> dict[str, Any]:
    payload = _product_3d_render_payload(texture_url=texture_url, tag=tag)
    status, data = _post_json(client, "/api/business/product-3d-render-video/runs", payload)
    label = "3D 渲染视频服务端真实任务"
    if status >= 400 or not isinstance(data, dict):
        return {
            "case": "product_3d_render_live",
            "label": label,
            "mode": "live-3d-render",
            "ok": False,
            "detail": f"submit failed status={status} body={_short(data)}",
            "request": payload,
            "response": data,
        }
    run_id = str(data.get("runId") or data.get("id") or "").strip()
    if not run_id:
        return {
            "case": "product_3d_render_live",
            "label": label,
            "mode": "live-3d-render",
            "ok": False,
            "detail": f"submit returned no runId status={status}",
            "request": payload,
            "response": data,
        }
    final = _poll_run(client, run_id, timeout_seconds=timeout_seconds, interval_seconds=interval_seconds)
    ok, detail = _validate_live_product_3d_render(final)
    return {
        "case": "product_3d_render_live",
        "label": label,
        "mode": "live-3d-render",
        "ok": ok,
        "detail": f"runId={run_id} {detail}",
        "runId": run_id,
        "request": payload,
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


def _live_video_payload(
    base: dict[str, Any],
    *,
    tag: str,
    executor_id: str,
    target_duration: int,
    confirmed_keyframes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
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
    if confirmed_keyframes:
        payload["confirmedVideoKeyframes"] = confirmed_keyframes
    return payload


def _live_keyframes_payload(base: dict[str, Any], *, tag: str, executor_id: str, target_duration: int) -> dict[str, Any]:
    payload = dict(base)
    payload.update(
        {
            "action": "video_keyframes",
            "executorId": executor_id or None,
            "targetDurationSeconds": target_duration,
            "durationSeconds": None,
            "visualSupportMode": "recommendation",
            "requestId": f"pcg-patrol-keyframes-{tag}",
            "traceId": f"pcg-patrol-keyframes-{tag}",
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
    parser.add_argument("--texture-url", default=os.getenv("PODI_3D_TEXTURE_URL") or DEFAULT_3D_TEXTURE_URL)
    parser.add_argument("--request-timeout", type=int, default=180, help="Per HTTP request timeout seconds.")
    parser.add_argument("--timeout", type=int, default=1200, help="Live run polling timeout seconds.")
    parser.add_argument("--interval", type=float, default=8.0, help="Live run polling interval seconds.")
    parser.add_argument(
        "--skip-ability-preview",
        action="store_true",
        help="Skip non-cost promo-video and product-3d-render-video ability checks.",
    )
    parser.add_argument("--include-live-visual", action="store_true", help="Submit a paid GPT Image 2 visual task.")
    parser.add_argument("--include-live-keyframes", action="store_true", help="Submit a paid GPT Image 2 video keyframe task.")
    parser.add_argument("--include-live-video", action="store_true", help="Submit a paid video asset package task.")
    parser.add_argument(
        "--include-live-3d-render",
        action="store_true",
        help="Submit a live product-3d-render-video run and verify MP4/cover/manifest OSS delivery.",
    )
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

        if not args.skip_ability_preview:
            ability_items: list[dict[str, Any]] = []
            try:
                ability_items.append(
                    _preview_promo_video_plan(
                        client,
                        product_image_url=str(args.product_image_url).strip(),
                        tag=tag,
                    )
                )
            except Exception as exc:
                ability_items.append(
                    {
                        "case": "promo_video_plan",
                        "label": "正式产品视频规划接口",
                        "mode": "promo-video-plan",
                        "ok": False,
                        "detail": f"request failed: {_short(repr(exc))}",
                        "response": None,
                    }
                )
            try:
                ability_items.extend(
                    _preview_product_3d(
                        client,
                        texture_url=str(args.texture_url).strip() or str(args.product_image_url).strip(),
                        tag=tag,
                    )
                )
            except Exception as exc:
                ability_items.append(
                    {
                        "case": "product_3d_preview",
                        "label": "3D 渲染视频非成本接口",
                        "mode": "product-3d-preview",
                        "ok": False,
                        "detail": f"request failed: {_short(repr(exc))}",
                        "response": None,
                    }
                )
            for item in ability_items:
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
        confirmed_video_keyframes: list[dict[str, Any]] = []
        if args.include_live_keyframes:
            item = _submit_live_run(
                client,
                label="视频首尾帧真实任务",
                payload=_live_keyframes_payload(
                    normal_payload,
                    tag=tag,
                    executor_id=str(args.video_executor or "").strip(),
                    target_duration=max(1, min(60, int(args.target_duration))),
                ),
                validator=_validate_live_keyframes,
                timeout_seconds=args.timeout,
                interval_seconds=args.interval,
            )
            results.append(item)
            if not args.json and not args.compact_json:
                _print_result(item)
            if item.get("ok") and isinstance(item.get("response"), dict):
                confirmed_video_keyframes = _extract_confirmed_video_keyframes(item["response"])
                if args.include_live_video and not confirmed_video_keyframes:
                    handoff_item = {
                        "case": "video_keyframe_handoff",
                        "label": "视频首尾帧确认交接",
                        "mode": "live-handoff",
                        "ok": False,
                        "detail": "keyframe run succeeded but no usable confirmedVideoKeyframes could be extracted",
                        "runId": item.get("runId"),
                    }
                    results.append(handoff_item)
                    if not args.json and not args.compact_json:
                        _print_result(handoff_item)
        if args.include_live_video:
            if args.include_live_keyframes and not confirmed_video_keyframes:
                item = {
                    "case": "视频素材包真实任务",
                    "label": "视频素材包真实任务",
                    "mode": "live",
                    "ok": False,
                    "detail": "skipped paid video task because confirmed keyframes were not available",
                    "response": None,
                }
            else:
                require_confirmed = bool(confirmed_video_keyframes)
                item = _submit_live_run(
                    client,
                    label="视频素材包真实任务",
                    payload=_live_video_payload(
                        normal_payload,
                        tag=tag,
                        executor_id=str(args.video_executor or "").strip(),
                        target_duration=max(1, min(60, int(args.target_duration))),
                        confirmed_keyframes=confirmed_video_keyframes,
                    ),
                    validator=lambda run: _validate_live_video(
                        run,
                        require_confirmed_keyframes=require_confirmed,
                    ),
                    timeout_seconds=args.timeout,
                    interval_seconds=args.interval,
                )
            results.append(item)
            if not args.json and not args.compact_json:
                _print_result(item)
        if args.include_live_3d_render:
            item = _submit_live_product_3d_render_run(
                client,
                texture_url=str(args.texture_url).strip() or str(args.product_image_url).strip(),
                tag=tag,
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
        "liveKeyframes": bool(args.include_live_keyframes),
        "liveVideo": bool(args.include_live_video),
        "liveVideoChainedConfirmedKeyframes": len(confirmed_video_keyframes),
        "live3DRender": bool(args.include_live_3d_render),
        "abilityPreview": not bool(args.skip_ability_preview),
        "productImageUrl": str(args.product_image_url).strip(),
        "textureUrl": str(args.texture_url).strip(),
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
