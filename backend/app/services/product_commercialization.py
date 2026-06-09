"""Product commercialization planning for post-design POD workflows."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.core.config import get_settings
from app.services.integration_test import integration_test_service
from app.services.media_ingest import media_ingest_service


OUTPUT_LANGUAGE_VALUES = {"en-US", "zh-CN", "bilingual"}
MARKET_REGION_VALUES = {"US", "UK", "EU", "global"}
COPY_SCENARIO_VALUES = {
    "listing_title",
    "bullet_points",
    "detail_description",
    "ad_short_copy",
    "keyword_pack",
}
VISUAL_SUPPORT_MODE_VALUES = {"none", "recommendation", "generate"}
VIDEO_SCENARIO_VALUES = {"product_showcase_short", "social_ad_short", "detail_explainer"}
DEFAULT_COPY_SCENARIOS = [
    "listing_title",
    "bullet_points",
    "detail_description",
    "ad_short_copy",
    "keyword_pack",
]
VEO_FAST_SEGMENT_SECONDS = 8
MAX_TARGET_VIDEO_SECONDS = 60
VIDEO_COMPOSE_TIMEOUT_SECONDS = 300
VIDEO_SEGMENT_MAX_ATTEMPTS = 2


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "templateName": ("templateName", "template_name", "模板名称", "中文名称", "productNameCn", "product_name_cn", "name"),
    "templateCode": ("templateCode", "template_code", "模板编号", "模板号"),
    "subjectCode": ("subjectCode", "subject_code", "主体编码", "主体编号"),
    "productModel": ("productModel", "product_model", "产品型号", "型号"),
    "productNameEn": ("productNameEn", "product_name_en", "英文名称", "englishName", "品类名称"),
    "categoryLevel1": ("categoryLevel1", "category_level_1", "一级分类", "平台分类"),
    "categoryLevel2": ("categoryLevel2", "category_level_2", "二级分类", "工厂分类"),
    "productWeight": ("productWeight", "product_weight", "产品重量", "重量"),
    "material": ("material", "材质", "产品材质"),
    "composition": ("composition", "成分", "具体成分"),
    "productionProcess": ("productionProcess", "production_process", "生产工艺"),
    "suggestedPrice": ("suggestedPrice", "suggested_price", "建议售价"),
    "packagingSizeCm": ("packagingSizeCm", "packaging_size_cm", "包装尺寸(cm)", "包装尺寸"),
    "packagingWeightG": ("packagingWeightG", "packaging_weight_g", "含包装重量(g)", "含包装重量"),
    "keywords": ("keywords", "keyword", "品类词", "关键词"),
    "description": ("description", "otherDescription", "其他描述", "产品配件", "产品详情"),
}


def _clean_text(value: Any) -> str:
    text = str(value or "").replace("\u3000", " ").strip()
    return " ".join(text.split())


def _first_present(data: dict[str, Any], aliases: tuple[str, ...]) -> tuple[str | None, str | None]:
    for alias in aliases:
        if alias not in data:
            continue
        value = data.get(alias)
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            text = ", ".join(_clean_text(item) for item in value) if isinstance(value, list) else str(value)
        else:
            text = _clean_text(value)
        if text:
            return text, alias
    return None, None


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    text = _clean_text(value)
    if not text:
        return []
    for sep in ("；", ";", "，", ",", "\n", "|"):
        text = text.replace(sep, ",")
    return [item.strip() for item in text.split(",") if item.strip()]


def _compact_sentence(parts: list[str]) -> str:
    return ", ".join([part for part in (_clean_text(p) for p in parts) if part])


def _english_product_name(facts: dict[str, Any]) -> str:
    for key in ("productNameEn", "templateName", "categoryLevel2", "categoryLevel1"):
        value = _clean_text(facts.get(key))
        if value:
            return value
    return "POD product"


def _zh_product_name(facts: dict[str, Any]) -> str:
    for key in ("templateName", "productNameEn", "categoryLevel2", "categoryLevel1"):
        value = _clean_text(facts.get(key))
        if value:
            return value
    return "POD 商品"


def _join_keywords(values: list[str], fallback: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in values + fallback:
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result[:18]


class ProductCommercializationService:
    """Builds a first-pass copy/video commercialization package."""

    def preview(self, payload: Any, *, user_id: str | None = None) -> dict[str, Any]:
        request_id = _clean_text(getattr(payload, "requestId", None)) or f"pcp_{uuid4().hex[:12]}"
        output_language = self._normalize_output_language(getattr(payload, "outputLanguage", None))
        market_region = self._normalize_market_region(getattr(payload, "marketRegion", None))
        visual_mode = self._normalize_visual_mode(getattr(payload, "visualSupportMode", None))
        video_scenario = self._normalize_video_scenario(getattr(payload, "videoScenario", None))
        copy_scenarios = self._normalize_copy_scenarios(getattr(payload, "copyScenarios", None))
        product_card = self._build_product_card(payload)
        copy_package = self._build_copy_package(
            product_card=product_card,
            scenarios=copy_scenarios,
            output_language=output_language,
            market_region=market_region,
            extra_prompt=getattr(payload, "extraPrompt", None),
        )
        visual_asset_plan = self._build_visual_asset_plan(
            product_card=product_card,
            visual_mode=visual_mode,
            output_language=output_language,
            product_image_url=getattr(payload, "productImageUrl", None),
        )
        video_plan = self._build_video_plan(
            product_card=product_card,
            product_image_url=getattr(payload, "productImageUrl", None),
            scenario=video_scenario,
            duration_seconds=getattr(payload, "durationSeconds", None),
            target_duration_seconds=getattr(payload, "targetDurationSeconds", None),
            aspect_ratio=getattr(payload, "aspectRatio", None),
            output_language=output_language,
            market_region=market_region,
        )
        review = self._build_review(
            product_card=product_card,
            copy_package=copy_package,
            visual_asset_plan=visual_asset_plan,
            video_plan=video_plan,
        )
        return {
            "requestId": request_id,
            "businessKey": "product_commercialization",
            "version": "product-commercialization-mvp-v1",
            "status": "previewed",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "strategyProfile": _clean_text(getattr(payload, "strategyProfile", None)) or "default_pod_profile",
            "outputLanguage": output_language,
            "marketRegion": market_region,
            "copyScenarios": copy_scenarios,
            "productCard": product_card,
            "copyPackage": copy_package,
            "visualAssetPlan": visual_asset_plan,
            "videoPlan": video_plan,
            "review": review,
            "execution": {
                "copyGenerated": True,
                "imageGenerated": False,
                "videoGenerated": False,
                "costActions": [],
                "note": "Preview only. Image/video generation requires explicit execute endpoint.",
            },
            "audit": {
                "userId": user_id,
                "source": _clean_text(getattr(payload, "source", None)) or "eval",
                "traceId": _clean_text(getattr(payload, "traceId", None)) or None,
            },
        }

    def generate_video(self, payload: Any, *, user_id: str | None = None) -> dict[str, Any]:
        preview = self.preview(payload, user_id=user_id)
        image_url = _clean_text(getattr(payload, "productImageUrl", None))
        if not image_url:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_IMAGE_REQUIRED")
        video_plan = preview["videoPlan"]
        prompt = _clean_text(video_plan.get("videoPrompt"))
        if not prompt:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_VIDEO_PROMPT_REQUIRED")
        if video_plan.get("requiresComposition"):
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_COMPOSE_NOT_READY")
        result, video_urls = self._generate_segment_with_retry(
            executor_id=_clean_text(getattr(payload, "executorId", None)) or "executor_kie_market_default",
            prompt=prompt,
            image_url=image_url,
            aspect_ratio=video_plan.get("aspectRatio") or "16:9",
            poll_timeout=float(getattr(payload, "pollTimeout", None) or 180),
            segment_index=1,
        )
        status = _clean_text(result.get("status")) or "running"
        return {
            **preview,
            "status": "succeeded" if status == "succeeded" and video_urls else status,
            "videoResult": {
                "provider": "kie",
                "model": "veo3_fast",
                "taskId": result.get("taskId"),
                "state": result.get("state"),
                "status": status,
                "videoUrls": video_urls,
                "storedAssets": result.get("storedAssets") or [],
                "raw": result.get("raw"),
            },
            "execution": {
                "copyGenerated": True,
                "imageGenerated": False,
                "videoGenerated": bool(video_urls),
                "costActions": ["kie.veo3_fast.video"],
                "note": "Video generation is an explicit cost action and result assets are persisted to PODI OSS.",
            },
        }

    def generate_composed_video(self, payload: Any, *, user_id: str | None = None) -> dict[str, Any]:
        preview = self.preview(payload, user_id=user_id)
        image_url = _clean_text(getattr(payload, "productImageUrl", None))
        if not image_url:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_IMAGE_REQUIRED")
        video_plan = preview["videoPlan"]
        if not video_plan.get("requiresComposition"):
            return self.generate_video(payload, user_id=user_id)

        storyboard = video_plan.get("storyboard") or []
        if not isinstance(storyboard, list) or not storyboard:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_VIDEO_PROMPT_REQUIRED")

        executor_id = _clean_text(getattr(payload, "executorId", None)) or "executor_kie_market_default"
        default_poll_timeout = max(float(get_settings().kie_task_timeout_seconds), 300.0)
        poll_timeout = float(getattr(payload, "pollTimeout", None) or default_poll_timeout)
        segment_results: list[dict[str, Any]] = []
        for index, shot in enumerate(storyboard, start=1):
            if not isinstance(shot, dict):
                continue
            prompt = _clean_text(shot.get("prompt") or video_plan.get("videoPrompt"))
            if not prompt:
                raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_VIDEO_PROMPT_REQUIRED")
            result, video_urls = self._generate_segment_with_retry(
                executor_id=executor_id,
                prompt=prompt,
                image_url=image_url,
                aspect_ratio=video_plan.get("aspectRatio") or "16:9",
                poll_timeout=poll_timeout,
                segment_index=index,
            )
            if _clean_text(result.get("status")) != "succeeded" or not video_urls:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "PRODUCT_COMMERCIALIZATION_SEGMENT_GENERATION_FAILED",
                        "segment": index,
                        "taskId": result.get("taskId"),
                        "state": result.get("state"),
                        "status": result.get("status"),
                        "error": self._summarize_kie_failure(result),
                    },
                )
            segment_results.append(
                {
                    "segment": index,
                    "shot": shot,
                    "taskId": result.get("taskId"),
                    "state": result.get("state"),
                    "status": result.get("status"),
                    "videoUrl": video_urls[0],
                    "videoUrls": video_urls,
                    "storedAssets": result.get("storedAssets") or [],
                    "prompt": prompt,
                }
            )

        if len(segment_results) != len(storyboard):
            raise HTTPException(status_code=502, detail="PRODUCT_COMMERCIALIZATION_SEGMENT_GENERATION_FAILED")

        composition = self._compose_segment_videos(
            segments=segment_results,
            trim_plan=(video_plan.get("compositionPlan") or {}).get("trimPlan"),
            request_id=_clean_text(preview.get("requestId")) or f"pcp_{uuid4().hex[:12]}",
            user_id=user_id or "product-commercialization",
        )
        video_url = _clean_text(composition.get("ossUrl"))
        return {
            **preview,
            "status": "succeeded",
            "videoResult": {
                "provider": "kie+ffmpeg",
                "model": "veo3_fast",
                "status": "succeeded",
                "videoUrls": [video_url] if video_url else [],
                "storedAssets": [composition] if composition else [],
                "segments": segment_results,
                "composition": {
                    "targetDurationSeconds": video_plan.get("targetDurationSeconds"),
                    "segmentCount": len(segment_results),
                    "composeEngine": "ffmpeg",
                    "transition": (video_plan.get("compositionPlan") or {}).get("transition"),
                    "trimPlan": (video_plan.get("compositionPlan") or {}).get("trimPlan"),
                    "output": composition,
                },
            },
            "execution": {
                "copyGenerated": True,
                "imageGenerated": False,
                "videoGenerated": bool(video_url),
                "costActions": (video_plan.get("compositionPlan") or {}).get("costActionPreview")
                or ["kie.veo3_fast.video", "ffmpeg.compose"],
                "note": "Composed video generation is an explicit multi-segment cost action; all segment and final assets are persisted to PODI OSS.",
            },
        }

    def _generate_segment_with_retry(
        self,
        *,
        executor_id: str,
        prompt: str,
        image_url: str,
        aspect_ratio: str,
        poll_timeout: float,
        segment_index: int,
    ) -> tuple[dict[str, Any], list[str]]:
        last_result: dict[str, Any] = {}
        last_exception: Exception | None = None
        for attempt in range(1, VIDEO_SEGMENT_MAX_ATTEMPTS + 1):
            try:
                result = integration_test_service.run_kie_market_task(
                    executor_id=executor_id,
                    endpoint="/api/v1/veo/generate",
                    status_endpoint="/api/v1/veo/record-info",
                    result_format="veo3",
                    model="veo3_fast",
                    input_payload={
                        "prompt": prompt,
                        "imageUrls": [image_url],
                        "aspectRatio": aspect_ratio,
                        "duration": VEO_FAST_SEGMENT_SECONDS,
                        "enableTranslation": True,
                        "enableFallback": False,
                    },
                    input_array_target="imageUrls",
                    poll_timeout=poll_timeout,
                    poll_interval=2.5,
                )
            except HTTPException as exc:
                last_exception = exc
                if attempt >= VIDEO_SEGMENT_MAX_ATTEMPTS:
                    raise
                continue
            except Exception as exc:  # pragma: no cover - defensive
                last_exception = exc
                if attempt >= VIDEO_SEGMENT_MAX_ATTEMPTS:
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "code": "PRODUCT_COMMERCIALIZATION_SEGMENT_GENERATION_FAILED",
                            "segment": segment_index,
                            "attempts": attempt,
                            "error": str(exc),
                        },
                    ) from exc
                continue
            last_result = result
            video_urls = self._extract_video_urls(result)
            if _clean_text(result.get("status")) == "succeeded" and video_urls:
                return result, video_urls
            if attempt >= VIDEO_SEGMENT_MAX_ATTEMPTS:
                break
        detail = {
            "code": "PRODUCT_COMMERCIALIZATION_SEGMENT_GENERATION_FAILED",
            "segment": segment_index,
            "attempts": VIDEO_SEGMENT_MAX_ATTEMPTS,
            "taskId": last_result.get("taskId"),
            "state": last_result.get("state"),
            "status": last_result.get("status"),
            "error": self._summarize_kie_failure(last_result),
        }
        if last_exception is not None and not detail["error"]:
            detail["error"] = str(getattr(last_exception, "detail", last_exception))
        raise HTTPException(status_code=502, detail=detail)

    def _summarize_kie_failure(self, result: dict[str, Any]) -> dict[str, Any] | str | None:
        raw = result.get("raw") if isinstance(result, dict) else None
        response = raw.get("response") if isinstance(raw, dict) else None
        data = response.get("data") if isinstance(response, dict) else None
        if isinstance(data, dict):
            summary = {
                "errorCode": data.get("errorCode"),
                "errorMessage": data.get("errorMessage"),
                "successFlag": data.get("successFlag"),
            }
            return {key: value for key, value in summary.items() if value not in (None, "", [])}
        if isinstance(response, dict):
            return response.get("msg") or response.get("detail") or None
        return None

    def _extract_video_urls(self, result: dict[str, Any]) -> list[str]:
        raw = result.get("videoUrls") or result.get("resultUrls") or []
        if isinstance(raw, str):
            values = [raw]
        elif isinstance(raw, list):
            values = [str(item) for item in raw if isinstance(item, str) and item.strip()]
        else:
            values = []
        return [_clean_text(item) for item in values if _clean_text(item)]

    def _compose_segment_videos(
        self,
        *,
        segments: list[dict[str, Any]],
        trim_plan: Any,
        request_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        ffmpeg = self._resolve_ffmpeg_binary()
        if not ffmpeg:
            raise HTTPException(status_code=500, detail="PRODUCT_COMMERCIALIZATION_FFMPEG_MISSING")
        trims = trim_plan if isinstance(trim_plan, list) else []
        with tempfile.TemporaryDirectory(prefix="podi-video-compose-") as temp_dir:
            work_dir = Path(temp_dir)
            normalized_paths: list[Path] = []
            for index, segment in enumerate(segments, start=1):
                source_url = _clean_text(segment.get("videoUrl"))
                if not source_url:
                    raise HTTPException(status_code=502, detail="PRODUCT_COMMERCIALIZATION_SEGMENT_GENERATION_FAILED")
                source_path = work_dir / f"segment-{index:02d}-source.mp4"
                normalized_path = work_dir / f"segment-{index:02d}-normalized.mp4"
                self._download_video(source_url, source_path)
                keep_seconds = self._resolve_keep_seconds(index=index, trims=trims)
                self._run_ffmpeg(
                    [
                        ffmpeg,
                        "-y",
                        "-i",
                        str(source_path),
                        "-t",
                        f"{keep_seconds:.3f}",
                        "-vf",
                        "scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=24,format=yuv420p,setsar=1",
                        "-an",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "20",
                        str(normalized_path),
                    ]
                )
                normalized_paths.append(normalized_path)
            concat_file = work_dir / "concat.txt"
            concat_lines = []
            for path in normalized_paths:
                escaped_path = str(path).replace("'", "'\\''")
                concat_lines.append(f"file '{escaped_path}'")
            concat_file.write_text("\n".join(concat_lines), encoding="utf-8")
            output_path = work_dir / "composed.mp4"
            self._run_ffmpeg(
                [
                    ffmpeg,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    "-an",
                    str(output_path),
                ]
            )
            data = output_path.read_bytes()
        return media_ingest_service.upload_generated_media_bytes(
            data=data,
            user_id=user_id or "product-commercialization",
            filename=f"{request_id}-composed.mp4",
            content_type="video/mp4",
            tag="product-commercialization-compose",
        )

    def _resolve_ffmpeg_binary(self) -> str | None:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
        try:
            import imageio_ffmpeg

            candidate = _clean_text(imageio_ffmpeg.get_ffmpeg_exe())
        except Exception:
            return None
        return candidate or None

    def _download_video(self, url: str, target_path: Path) -> None:
        try:
            with httpx.stream("GET", url, timeout=120) as response:
                response.raise_for_status()
                with target_path.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        if chunk:
                            handle.write(chunk)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="PRODUCT_COMMERCIALIZATION_COMPOSE_DOWNLOAD_FAILED") from exc

    def _resolve_keep_seconds(self, *, index: int, trims: list[Any]) -> float:
        fallback = float(VEO_FAST_SEGMENT_SECONDS)
        for item in trims:
            if not isinstance(item, dict):
                continue
            try:
                if int(item.get("segment")) != index:
                    continue
                keep = float(item.get("keepSeconds") or fallback)
            except (TypeError, ValueError):
                return fallback
            return max(0.5, min(float(VEO_FAST_SEGMENT_SECONDS), keep))
        return fallback

    def _run_ffmpeg(self, command: list[str]) -> None:
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=VIDEO_COMPOSE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=502, detail="PRODUCT_COMMERCIALIZATION_COMPOSE_TIMEOUT") from exc
        if completed.returncode != 0:
            self._logger.warning("ffmpeg failed: %s", (completed.stderr or completed.stdout or "")[-1000:])
            raise HTTPException(status_code=502, detail="PRODUCT_COMMERCIALIZATION_COMPOSE_FAILED")

    def _normalize_target_duration_seconds(self, value: Any) -> int:
        if value in (None, ""):
            return VEO_FAST_SEGMENT_SECONDS
        try:
            duration = int(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_TARGET_DURATION_INVALID") from exc
        if duration < VEO_FAST_SEGMENT_SECONDS or duration > MAX_TARGET_VIDEO_SECONDS:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_TARGET_DURATION_INVALID")
        return duration

    def _normalize_output_language(self, value: Any) -> str:
        text = _clean_text(value) or "en-US"
        if text not in OUTPUT_LANGUAGE_VALUES:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_LANGUAGE_INVALID")
        return text

    def _normalize_market_region(self, value: Any) -> str:
        text = _clean_text(value) or "US"
        if text not in MARKET_REGION_VALUES:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_MARKET_INVALID")
        return text

    def _normalize_visual_mode(self, value: Any) -> str:
        text = _clean_text(value) or "recommendation"
        if text not in VISUAL_SUPPORT_MODE_VALUES:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_VISUAL_MODE_INVALID")
        return text

    def _normalize_video_scenario(self, value: Any) -> str:
        text = _clean_text(value) or "product_showcase_short"
        if text not in VIDEO_SCENARIO_VALUES:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_VIDEO_SCENARIO_INVALID")
        return text

    def _normalize_copy_scenarios(self, value: Any) -> list[str]:
        raw = value if isinstance(value, list) else _normalize_list(value)
        scenarios: list[str] = []
        for item in raw or DEFAULT_COPY_SCENARIOS:
            key = _clean_text(item)
            if not key:
                continue
            if key not in COPY_SCENARIO_VALUES:
                raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_COPY_SCENARIO_INVALID")
            if key not in scenarios:
                scenarios.append(key)
        return scenarios or list(DEFAULT_COPY_SCENARIOS)

    def _build_product_card(self, payload: Any) -> dict[str, Any]:
        data = getattr(payload, "productFields", None) or {}
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_CONTEXT_INVALID")
        source_facts: dict[str, Any] = {}
        source_map: dict[str, str] = {}
        for key, aliases in FIELD_ALIASES.items():
            value, source_key = _first_present(data, aliases)
            if value:
                source_facts[key] = value
                source_map[key] = source_key or key
        image_url = _clean_text(getattr(payload, "productImageUrl", None))
        design_image_url = _clean_text(getattr(payload, "designImageUrl", None))
        if image_url:
            source_facts["productImageUrl"] = image_url
        if design_image_url:
            source_facts["designImageUrl"] = design_image_url

        keywords = _normalize_list(source_facts.get("keywords"))
        inferred_facts: dict[str, Any] = {}
        if "productNameEn" not in source_facts:
            inferred_facts["productNameEn"] = _english_product_name(source_facts)
        if "templateName" not in source_facts:
            inferred_facts["templateName"] = _zh_product_name(source_facts)
        if not keywords:
            keywords = _join_keywords(
                [],
                [
                    _english_product_name(source_facts),
                    _clean_text(source_facts.get("categoryLevel2")),
                    _clean_text(source_facts.get("material")),
                    "print on demand",
                ],
            )
            inferred_facts["keywords"] = keywords
        required = ["productNameEn", "templateName", "material", "productionProcess", "categoryLevel2", "productImageUrl"]
        missing = [key for key in required if not source_facts.get(key) and not inferred_facts.get(key)]
        confidence = max(0.35, min(0.92, 0.58 + 0.04 * len(source_facts) - 0.05 * len(missing)))
        return {
            "title": _english_product_name({**inferred_facts, **source_facts}),
            "sourceFacts": source_facts,
            "sourceMap": source_map,
            "inferredFacts": inferred_facts,
            "missingFields": missing,
            "confidence": round(confidence, 2),
            "usageNotes": [
                "Use source facts directly when present; inferred facts are only drafting aids.",
                "Missing fields should not block MVP preview, but should lower review confidence.",
            ],
        }

    def _localized_copy(self, *, en: Any, zh: Any, output_language: str) -> Any:
        if output_language == "en-US":
            return en
        if output_language == "zh-CN":
            return zh
        return {"en-US": en, "zh-CN": zh}

    def _build_copy_package(
        self,
        *,
        product_card: dict[str, Any],
        scenarios: list[str],
        output_language: str,
        market_region: str,
        extra_prompt: Any,
    ) -> dict[str, Any]:
        facts = {**product_card.get("inferredFacts", {}), **product_card.get("sourceFacts", {})}
        name_en = _english_product_name(facts)
        name_zh = _zh_product_name(facts)
        material = _clean_text(facts.get("material") or facts.get("composition"))
        process = _clean_text(facts.get("productionProcess"))
        category = _clean_text(facts.get("categoryLevel2") or facts.get("categoryLevel1"))
        keywords = _join_keywords(
            _normalize_list(facts.get("keywords")),
            [name_en, category, material, "custom design", "POD"],
        )
        selling_base_en = [
            _compact_sentence(["Made for everyday styling", category]),
            _compact_sentence(["Soft, comfortable feel", material]) if material else "Designed for comfort and easy pairing",
            _compact_sentence(["Print-on-demand friendly", process]) if process else "Clean visual presentation for POD listings",
            "Works as a practical gift or seasonal wardrobe update",
            "Lightweight product story suitable for marketplace and ad copy",
        ]
        selling_base_zh = [
            _compact_sentence(["适合日常穿搭", category]),
            _compact_sentence(["触感舒适", material]) if material else "兼顾舒适度和搭配场景",
            _compact_sentence(["适合 POD 定制展示", process]) if process else "适合电商详情页和广告素材使用",
            "可作为礼品、季节上新或主题系列商品",
            "文案风格适合海外平台上架与广告初稿",
        ]
        result: dict[str, Any] = {
            "marketRegion": market_region,
            "styleGuardrails": [
                "Avoid unverifiable medical, sustainability, trademark, or performance claims.",
                "Do not mention unavailable sizes, shipping promises, or platform policies unless source fields provide them.",
            ],
            "sourcePrompt": _clean_text(extra_prompt) or None,
        }
        if "listing_title" in scenarios:
            result["listingTitle"] = self._localized_copy(
                en=f"{name_en} - Custom POD Design, Comfortable Everyday Style",
                zh=f"{name_zh} - POD 定制设计，适合日常穿搭",
                output_language=output_language,
            )
        if "bullet_points" in scenarios:
            result["bulletPoints"] = self._localized_copy(en=selling_base_en[:5], zh=selling_base_zh[:5], output_language=output_language)
        if "detail_description" in scenarios:
            detail_en = (
                f"Refresh your store with {name_en}, a POD-ready product designed around clear product visuals, "
                f"comfortable styling, and easy giftable appeal. "
                f"{'Key material: ' + material + '. ' if material else ''}"
                f"{'Production process: ' + process + '. ' if process else ''}"
                "Use the final copy as a listing draft and adjust factual fields before publishing."
            )
            detail_zh = (
                f"{name_zh} 适合作为 POD 商品上架初稿，重点突出清晰的商品视觉、舒适穿搭和礼品属性。"
                f"{'材质：' + material + '。' if material else ''}"
                f"{'生产工艺：' + process + '。' if process else ''}"
                "发布前需要人工核对尺码、物流、平台禁词和真实属性。"
            )
            result["detailDescription"] = self._localized_copy(en=detail_en, zh=detail_zh, output_language=output_language)
        if "ad_short_copy" in scenarios:
            result["adShortCopy"] = self._localized_copy(
                en=[
                    f"Freshen up your look with {name_en}.",
                    f"A gift-ready {category or 'POD pick'} with a clean custom design.",
                    "Designed for everyday comfort, styled for seasonal moments.",
                ],
                zh=[
                    f"用 {name_zh} 更新你的日常造型。",
                    f"适合作为礼品或主题上新的 {category or 'POD 商品'}。",
                    "兼顾舒适穿搭与季节氛围的定制设计。",
                ],
                output_language=output_language,
            )
        if "keyword_pack" in scenarios:
            result["keywordPack"] = keywords
        return result

    def _build_visual_asset_plan(
        self,
        *,
        product_card: dict[str, Any],
        visual_mode: str,
        output_language: str,
        product_image_url: Any,
    ) -> dict[str, Any]:
        facts = {**product_card.get("inferredFacts", {}), **product_card.get("sourceFacts", {})}
        name = _english_product_name(facts) if output_language != "zh-CN" else _zh_product_name(facts)
        has_image = bool(_clean_text(product_image_url))
        scenes = [
            {
                "id": "listing-main",
                "label": "Listing main visual",
                "neededFor": ["detail_description"],
                "recommendation": "Use the exported product image as the factual anchor; do not regenerate unless quality is poor.",
                "generateByDefault": False,
            },
            {
                "id": "social-ad-cover",
                "label": "Social ad cover",
                "neededFor": ["ad_short_copy"],
                "recommendation": f"Create a clean lifestyle or seasonal scene featuring {name}, with no embedded text or logos.",
                "generateByDefault": visual_mode == "generate",
            },
            {
                "id": "detail-closeup",
                "label": "Detail close-up",
                "neededFor": ["detail_description", "product_showcase_short"],
                "recommendation": "Use a close-up or crop that shows material, print clarity, and product shape.",
                "generateByDefault": False,
            },
        ]
        return {
            "mode": visual_mode,
            "hasProductImage": has_image,
            "primaryAssetRole": "product_image" if has_image else "missing_product_image",
            "recommendedScenes": scenes if visual_mode != "none" else [],
            "generatedAssets": [],
            "generationPolicy": {
                "requiresExplicitAction": True,
                "defaultGenerateImages": visual_mode == "generate",
                "candidateRoute": "business.product_design_or_gpt_image2",
                "ossPersistenceRequired": True,
            },
            "warnings": [] if has_image else ["Missing product image limits visual and video generation quality."],
        }

    def _build_video_plan(
        self,
        *,
        product_card: dict[str, Any],
        product_image_url: Any,
        scenario: str,
        duration_seconds: Any,
        target_duration_seconds: Any,
        aspect_ratio: Any,
        output_language: str,
        market_region: str,
    ) -> dict[str, Any]:
        facts = {**product_card.get("inferredFacts", {}), **product_card.get("sourceFacts", {})}
        name = _english_product_name(facts)
        material = _clean_text(facts.get("material") or facts.get("composition"))
        # KIE Veo 3.1 direct generation currently returns 8-second clips in live tests.
        # Longer or precisely variable lengths are planned as storyboard + composition.
        duration = VEO_FAST_SEGMENT_SECONDS
        target_duration = self._normalize_target_duration_seconds(target_duration_seconds or duration_seconds)
        segment_count = max(1, (target_duration + duration - 1) // duration)
        total_generated_seconds = segment_count * duration
        requires_composition = target_duration > duration
        ratio = _clean_text(aspect_ratio) or "16:9"
        prompt_parts = [
            f"Create an {duration}-second POD product showcase video for {name}.",
            "Use the provided product image as the exact visual reference.",
            "Slow camera movement, clean studio lighting, premium ecommerce presentation.",
            "Keep product shape, pattern, color, and material consistent.",
            "No extra text, no watermarks, no logos, no unrealistic deformation.",
        ]
        if material:
            prompt_parts.append(f"Material cue: {material}.")
        if market_region:
            prompt_parts.append(f"Target marketplace region: {market_region}.")
        segment_roles = self._build_video_segment_roles(
            scenario=scenario,
            segment_count=segment_count,
        )
        storyboard: list[dict[str, Any]] = []
        trim_plan: list[dict[str, Any]] = []
        for index in range(1, segment_count + 1):
            keep_seconds = min(duration, max(1, target_duration - ((index - 1) * duration)))
            role = segment_roles[index - 1]
            segment_prompt = " ".join(
                [
                    *prompt_parts,
                    f"Segment {index} of {segment_count}: {role['direction']}.",
                    "Keep visual continuity with the previous segment when provided.",
                ]
            )
            storyboard.append(
                {
                    "shot": index,
                    "durationSeconds": duration,
                    "keepSeconds": keep_seconds,
                    "label": role["label"],
                    "camera": role["camera"],
                    "subject": name,
                    "goal": role["goal"],
                    "prompt": segment_prompt,
                }
            )
            trim_plan.append(
                {
                    "segment": index,
                    "sourceDurationSeconds": duration,
                    "keepSeconds": keep_seconds,
                    "trimStartSeconds": 0,
                    "trimEndSeconds": keep_seconds,
                }
            )
        asset_needs = [
            {
                "asset": "product_image",
                "required": True,
                "available": bool(_clean_text(product_image_url)),
                "reason": "Veo image-to-video needs a factual visual anchor.",
            },
            {
                "asset": "multi_angle_images",
                "required": requires_composition,
                "available": False,
                "reason": "Recommended for long videos to reduce repeated angles and improve continuity.",
            },
            {
                "asset": "first_last_frames",
                "required": requires_composition,
                "available": False,
                "reason": "Needed for controlled opening/ending frames once composition execution is enabled.",
            },
        ]
        return {
            "scenario": scenario,
            "model": "veo3_fast",
            "targetDurationSeconds": target_duration,
            "durationSeconds": duration,
            "singleSegmentSeconds": duration,
            "segmentCount": segment_count,
            "totalGeneratedSeconds": total_generated_seconds,
            "requiresComposition": requires_composition,
            "aspectRatio": ratio,
            "storyboard": storyboard,
            "assetNeeds": asset_needs,
            "videoPrompt": " ".join(prompt_parts),
            "compositionPlan": {
                "status": "planned_ready_for_compose_endpoint" if requires_composition else "not_required",
                "composeEngine": "ffmpeg",
                "executionReady": True,
                "targetDurationSeconds": target_duration,
                "singleSegmentSeconds": duration,
                "segmentCount": segment_count,
                "totalGeneratedSeconds": total_generated_seconds,
                "trimPlan": trim_plan,
                "transition": {
                    "type": "cut" if requires_composition else "none",
                    "durationSeconds": 0,
                },
                "costActionPreview": ["kie.veo3_fast.video" for _ in range(segment_count)]
                + (["ffmpeg.compose"] if requires_composition else []),
                "plannerRole": "llm_storyboard_planner",
                "nextEndpoint": "/api/business/product-commercialization/video-compose" if requires_composition else None,
                "guardrails": [
                    "Backend validates target duration and segment count before execution.",
                    "Each ability call must persist returned video assets to PODI OSS before composition.",
                    "Direct video execution remains single-segment until compose endpoint is implemented.",
                ],
            },
            "languagePolicy": {
                "outputLanguage": output_language,
                "spokenAudio": "disabled",
                "embeddedText": "disabled",
            },
        }

    def _build_video_segment_roles(self, *, scenario: str, segment_count: int) -> list[dict[str, str]]:
        base = [
            {
                "label": "Opening product hero",
                "camera": "slow push-in with a slight side movement",
                "goal": "establish product shape, pattern, and marketplace appeal",
                "direction": "start with a clean hero view that clearly shows the full product",
            },
            {
                "label": "Material and print detail",
                "camera": "smooth close-up glide across the product surface",
                "goal": "show material texture, print clarity, and design quality",
                "direction": "move closer to highlight texture, print detail, and product finish",
            },
            {
                "label": "Lifestyle selling moment",
                "camera": "gentle product rotation in a minimal commercial scene",
                "goal": "connect the product to the target buying occasion",
                "direction": "present a simple ecommerce lifestyle moment without adding logos or text",
            },
            {
                "label": "Clean ending frame",
                "camera": "settle into a stable final product frame",
                "goal": "end with a usable commercial frame for cover or editing",
                "direction": "finish on a stable product-focused frame suitable for the final cut",
            },
        ]
        if scenario == "social_ad_short":
            base[0]["goal"] = "create an immediate social ad hook while preserving factual product appearance"
            base[2]["direction"] = "use a faster but smooth commercial movement suitable for social advertising"
        elif scenario == "detail_explainer":
            base[0]["goal"] = "introduce the product clearly for a detail-page explainer"
            base[1]["direction"] = "slowly inspect material, construction, and visible print quality"
        return [base[min(index, len(base) - 1)] for index in range(segment_count)]

    def _build_review(
        self,
        *,
        product_card: dict[str, Any],
        copy_package: dict[str, Any],
        visual_asset_plan: dict[str, Any],
        video_plan: dict[str, Any],
    ) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        if product_card.get("missingFields"):
            issues.append(
                {
                    "level": "warning",
                    "code": "PRODUCT_FACTS_INCOMPLETE",
                    "message": f"Missing fields: {', '.join(product_card.get('missingFields') or [])}",
                }
            )
        if not visual_asset_plan.get("hasProductImage"):
            issues.append(
                {
                    "level": "warning",
                    "code": "PRODUCT_IMAGE_MISSING",
                    "message": "Copy preview can continue, but image/video generation should wait for a product image.",
                }
            )
        if any("gift" in str(item).lower() for item in copy_package.get("adShortCopy", []) if isinstance(item, str)):
            issues.append(
                {
                    "level": "info",
                    "code": "AD_COPY_FACT_CHECK",
                    "message": "Gift-oriented wording is a marketing suggestion and should be checked against the target marketplace.",
                }
            )
        return {
            "profile": "default_pod_profile",
            "score": max(40, min(92, int((product_card.get("confidence") or 0.5) * 100))),
            "issues": issues,
            "nextActions": [
                "Verify product facts before publishing.",
                "Generate visual assets only when the target copy scenario needs them.",
                "Run Veo Fast only after the product image and storyboard are accepted.",
            ],
            "videoReady": all(item.get("available") or not item.get("required") for item in video_plan.get("assetNeeds") or []),
        }


product_commercialization_service = ProductCommercializationService()
