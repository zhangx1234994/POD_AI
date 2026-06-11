"""Product commercialization planning for post-design POD workflows."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.constants.abilities import DEFAULT_VOLCENGINE_VL_MODEL_ID
from app.core.config import get_settings
from app.core.db import get_session
from app.schemas.abilities import AbilityInvokeRequest
from app.services.api_key_selector import pick_provider_api_key
from app.services.ability_invocation import ability_invocation_service
from app.services.integration_test import integration_test_service
from app.services.media_ingest import media_ingest_service

logger = logging.getLogger(__name__)


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
ENGLISH_FACT_TRANSLATIONS: tuple[tuple[str, str], ...] = (
    ("饰品/配件", "accessories"),
    ("穿搭配件", "fashion accessories"),
    ("女款长袜", "women's long socks"),
    ("3D打印", "3D printed"),
    ("3D印花", "3D print"),
    ("包纱", "covered yarn"),
    ("涤纶", "polyester"),
    ("氨纶", "spandex"),
    ("尼龙", "nylon"),
    ("橡筋", "elastic"),
    ("棉", "cotton"),
    ("羊毛", "wool"),
    ("陶瓷", "ceramic"),
    ("杯具", "drinkware"),
)
FACT_GUARD_STOPWORDS = {
    "and",
    "for",
    "the",
    "with",
    "from",
    "into",
    "your",
    "women",
    "woman",
    "womens",
    "men",
    "mens",
    "custom",
    "design",
    "product",
    "ready",
    "daily",
    "style",
    "printed",
    "print",
}
FACT_GUARD_MIN_FIELD_HITS = 2
DEFAULT_VIDEO_SEGMENT_SECONDS = 8
MAX_TARGET_VIDEO_SECONDS = 60
VIDEO_COMPOSE_TIMEOUT_SECONDS = 300
VIDEO_SEGMENT_MAX_ATTEMPTS = 2
DEFAULT_KIE_VIDEO_EXECUTOR_ID = "executor_kie_market_default"
DEFAULT_VIDU_VIDEO_MODEL = "viduq3-turbo"
DEFAULT_VISUAL_ABILITY_ID = "openai_gpt_image_2_edit"
DEFAULT_VISUAL_PROVIDER = "openai"
DEFAULT_VISUAL_MODEL = "gpt-image-2"
VIDEO_MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "kie": {
        "provider": "kie",
        "model": "veo3_fast",
        "displayName": "KIE · Veo3.1 Fast",
        "segmentDurationOptions": [8],
        "defaultSegmentSeconds": 8,
        "maxTargetSeconds": 60,
        "endpoint": "/api/v1/veo/generate",
        "statusEndpoint": "/api/v1/veo/record-info",
        "modes": [
            {
                "key": "single_reference",
                "label": "单参考图生视频",
                "executable": True,
                "requiresGeneratedFrames": False,
            },
            {
                "key": "first_last_frames",
                "label": "首尾帧控制",
                "executable": False,
                "requiresGeneratedFrames": True,
                "reason": "待完成首尾帧生成与接口适配后开放执行。",
            },
        ],
    },
    "vidu": {
        "provider": "vidu",
        "model": DEFAULT_VIDU_VIDEO_MODEL,
        "displayName": "Vidu · viduq3-turbo",
        "segmentDurationOptions": [3, 5, 8],
        "defaultSegmentSeconds": 5,
        "maxTargetSeconds": 60,
        "endpoint": "/ent/v2/img2video",
        "statusEndpoint": "/ent/v2/tasks/{task_id}/creations",
        "modes": [
            {
                "key": "single_reference",
                "label": "单参考图生视频",
                "executable": True,
                "requiresGeneratedFrames": False,
            },
            {
                "key": "first_last_frames",
                "label": "首尾帧控制",
                "executable": False,
                "requiresGeneratedFrames": True,
                "reason": "待接入 start-end-to-video 和首尾帧确认流后开放执行。",
            },
        ],
    },
}

COPY_MODEL_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "commercePositioning": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "coreAngle": {"type": "string"},
                "targetCustomers": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 6},
                "purchaseOccasions": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 8},
                "sellingPoints": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 8},
                "factBoundaries": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 8},
            },
            "required": ["coreAngle", "targetCustomers", "purchaseOccasions", "sellingPoints", "factBoundaries"],
        },
        "listingTitle": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"en-US": {"type": "string"}, "zh-CN": {"type": "string"}},
            "required": ["en-US", "zh-CN"],
        },
        "bulletPoints": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "en-US": {"type": "array", "items": {"type": "string"}, "minItems": 5, "maxItems": 5},
                "zh-CN": {"type": "array", "items": {"type": "string"}, "minItems": 5, "maxItems": 5},
            },
            "required": ["en-US", "zh-CN"],
        },
        "detailDescription": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"en-US": {"type": "string"}, "zh-CN": {"type": "string"}},
            "required": ["en-US", "zh-CN"],
        },
        "adShortCopy": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "en-US": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 5},
                "zh-CN": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 5},
            },
            "required": ["en-US", "zh-CN"],
        },
        "keywordPack": {"type": "array", "items": {"type": "string"}, "minItems": 6, "maxItems": 20},
        "imageFactAssessment": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "visualSourcePriority": {"type": "string"},
                "observedProductType": {"type": "string"},
                "observedVisualFeatures": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 10},
                "fieldConflicts": {"type": "array", "items": {"type": "string"}, "minItems": 0, "maxItems": 10},
                "missingFieldInferences": {"type": "array", "items": {"type": "string"}, "minItems": 0, "maxItems": 10},
                "copyDecision": {"type": "string"},
                "confidence": {"type": "string"},
            },
            "required": [
                "visualSourcePriority",
                "observedProductType",
                "observedVisualFeatures",
                "fieldConflicts",
                "missingFieldInferences",
                "copyDecision",
                "confidence",
            ],
        },
        "imageBriefs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "usage": {"type": "string"},
                    "linkedCopy": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6},
                    "prompt": {"type": "string"},
                    "riskNotes": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5},
                },
                "required": ["id", "label", "usage", "linkedCopy", "prompt", "riskNotes"],
            },
            "minItems": 3,
            "maxItems": 6,
        },
        "channelUsageGuide": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "channel": {"type": "string"},
                    "howToUse": {"type": "string"},
                    "assets": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
                },
                "required": ["channel", "howToUse", "assets"],
            },
            "minItems": 2,
            "maxItems": 6,
        },
        "styleGuardrails": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 8},
        "modelNotes": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
    },
    "required": [
        "commercePositioning",
        "listingTitle",
        "bulletPoints",
        "detailDescription",
        "adShortCopy",
        "keywordPack",
        "imageFactAssessment",
        "imageBriefs",
        "channelUsageGuide",
        "styleGuardrails",
        "modelNotes",
    ],
}


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
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_normalize_list(item))
        return result
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, (dict, list)):
                result.extend(_normalize_list(item))
                continue
            text = _clean_text(item)
            if text:
                result.append(text)
        return result
    text = _clean_text(value)
    if not text:
        return []
    for sep in ("；", ";", "，", ",", "\n", "|"):
        text = text.replace(sep, ",")
    return [item.strip() for item in text.split(",") if item.strip()]


def _compact_sentence(parts: list[str]) -> str:
    return ", ".join([part for part in (_clean_text(p) for p in parts) if part])


def _as_record(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    if isinstance(value, dict):
        return [item for item in value.values()]
    return [value]


def _build_visual_prompt(
    *,
    product_card: dict[str, Any],
    resolved_product_facts: dict[str, Any] | None = None,
    copy_package: dict[str, Any] | None,
    visual_brief: dict[str, Any],
    output_language: str,
    market_region: str,
    extra_prompt: str | None = None,
) -> str:
    facts = (
        _as_record(resolved_product_facts.get("facts")) if isinstance(resolved_product_facts, dict) else {}
    ) or {**product_card.get("inferredFacts", {}), **product_card.get("sourceFacts", {})}
    english_name = _english_product_name(facts)
    chinese_name = _zh_product_name(facts)
    material = _clean_text(facts.get("material") or facts.get("composition"))
    pattern = _clean_text(facts.get("pattern") or facts.get("keywords"))
    selling_points = _critical_product_terms(facts)

    brief_prompt = _clean_text(visual_brief.get("prompt"))
    brief_usage = _clean_text(visual_brief.get("usage"))
    linked_copy = _normalize_list(visual_brief.get("linkedCopy"))
    scene_label = _clean_text(visual_brief.get("label") or visual_brief.get("id"))
    risk_notes = _normalize_list(visual_brief.get("riskNotes"))

    copy_highlights = []
    if isinstance(copy_package, dict):
        copy_highlights.extend(_normalize_list(copy_package.get("listingTitle")))
        copy_highlights.extend(_normalize_list(copy_package.get("bulletPoints"))[:2])
        copy_highlights.extend(_normalize_list(copy_package.get("adShortCopy"))[:2])

    if output_language == "zh-CN":
        subject = f"基于上传的产品图生成一张高质量配图，场景：{scene_label or '商品主视觉'}。"
        subject += f"商品名称：{chinese_name}。"
        if material:
            subject += f"材质：{material}。"
        if brief_usage:
            subject += f"用途意图：{brief_usage}。"
        if linked_copy:
            subject += f"参考文案方向：{_compact_sentence(linked_copy)}。"
        if pattern:
            subject += f"图案信息：{pattern}。"
        if selling_points:
            subject += f"核心卖点：{_compact_sentence(selling_points)}。"
        if copy_highlights:
            subject += f"可参考文案：{_compact_sentence(copy_highlights)}。"
        if market_region:
            subject += f"目标市场：{market_region}。"
        if risk_notes:
            subject += f"约束：{_compact_sentence(risk_notes)}。"
        if extra_prompt:
            subject += f"补充要求：{extra_prompt}。"
        return _compact_sentence([subject, "禁止加入文字、水印、logo、价格标签或未提供的属性。", brief_prompt or "保持产品结构、花纹和比例一致。"])

    english_name = _english_text_or_empty(english_name) or "POD product"
    market = _clean_text(market_region) or "global marketplace"
    scene_desc = f"Scene: {scene_label or 'product visual asset'}."
    subject = f"Generate a high-quality product marketing image based on the source product image. Scene: {scene_desc}"
    subject += f" Product: {english_name}."
    if material:
        subject += f" Material: {material}."
    if brief_usage:
        subject += f" Usage intent: {brief_usage}."
    if linked_copy:
        subject += f" Reference copy direction: {_compact_sentence(linked_copy)}."
    if pattern:
        subject += f" Pattern clues: {pattern}."
    if selling_points:
        subject += f" Key points: {_compact_sentence(selling_points)}."
    if copy_highlights:
        subject += f" Copy hints: {_compact_sentence(copy_highlights)}."
    if market:
        subject += f" Target market: {market}."
    if risk_notes:
        subject += f" Constraints: {_compact_sentence(risk_notes)}."
    if extra_prompt:
        subject += f" Additional request: {extra_prompt}."
    subject += " Keep product silhouette, print, material consistency. No watermark, text, logos, brand claims, or irrelevant props."
    if brief_prompt:
        subject += f" Brief hint: {brief_prompt}."
    return " ".join([part for part in subject.split() if part]).strip()


def _english_fact_phrase(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    for source, target in ENGLISH_FACT_TRANSLATIONS:
        text = text.replace(source, target)
    for sep in ("；", "，", "、"):
        text = text.replace(sep, ", ")
    return " ".join(text.split())


def _contains_cjk(value: Any) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", _clean_text(value)))


def _english_text_or_empty(value: Any) -> str:
    text = _english_fact_phrase(value)
    return "" if _contains_cjk(text) else text


def _english_product_name(facts: dict[str, Any]) -> str:
    for key in ("productNameEn", "templateName", "categoryLevel2", "categoryLevel1"):
        value = _clean_text(facts.get(key))
        if value:
            if key == "productNameEn":
                return value
            translated = _english_text_or_empty(value)
            if translated:
                return translated
    return "POD product"


def _word_tokens(value: Any) -> list[str]:
    text = _english_fact_phrase(value).lower()
    return [token for token in re.findall(r"[a-z0-9]+", text) if token]


def _critical_product_terms(facts: dict[str, Any]) -> list[str]:
    candidates = [
        _english_product_name(facts),
        facts.get("categoryLevel2"),
        facts.get("categoryLevel1"),
    ]
    terms: list[str] = []
    for candidate in candidates:
        for token in _word_tokens(candidate):
            if len(token) < 3 or token in FACT_GUARD_STOPWORDS:
                continue
            if token not in terms:
                terms.append(token)
    return terms[:8]


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return _clean_text(value)


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
        content_bundle = self._build_content_bundle(
            payload=payload,
            product_card=product_card,
            scenarios=copy_scenarios,
            output_language=output_language,
            market_region=market_region,
        )
        copy_package = content_bundle["copyPackage"]
        content_package = content_bundle["contentPackage"]
        copy_generation = content_bundle["copyGeneration"]
        resolved_product_facts = self._build_resolved_product_facts(
            product_card=product_card,
            content_package=content_package,
            copy_package=copy_package,
            output_language=output_language,
        )
        visual_asset_plan = self._build_visual_asset_plan(
            product_card=product_card,
            resolved_product_facts=resolved_product_facts,
            content_package=content_package,
            visual_mode=visual_mode,
            output_language=output_language,
            product_image_url=getattr(payload, "productImageUrl", None),
        )
        video_plan = self._build_video_plan(
            product_card=product_card,
            resolved_product_facts=resolved_product_facts,
            product_image_url=getattr(payload, "productImageUrl", None),
            scenario=video_scenario,
            duration_seconds=getattr(payload, "durationSeconds", None),
            target_duration_seconds=getattr(payload, "targetDurationSeconds", None),
            aspect_ratio=getattr(payload, "aspectRatio", None),
            output_language=output_language,
            market_region=market_region,
            executor_id=getattr(payload, "executorId", None),
        )
        review = self._build_review(
            product_card=product_card,
            copy_package=copy_package,
            content_package=content_package,
            copy_generation=copy_generation,
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
            "resolvedProductFacts": resolved_product_facts,
            "copyPackage": copy_package,
            "contentPackage": content_package,
            "copyGeneration": copy_generation,
            "visualAssetPlan": visual_asset_plan,
            "videoPlan": video_plan,
            "review": review,
            "execution": {
                "copyGenerated": not bool(copy_generation.get("fallback")),
                "copyGenerationMethod": copy_generation.get("method"),
                "imageGenerated": False,
                "videoGenerated": False,
                "costActions": [],
                "note": (
                    "Copy preview uses the configured LLM/VL planner when available. "
                    "Image/video generation requires explicit execute endpoint."
                ),
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
        video_plan = self._apply_video_prompt_override(video_plan, getattr(payload, "videoPromptOverride", None))
        preview["videoPlan"] = video_plan
        prompt = _clean_text(video_plan.get("videoPrompt"))
        if not prompt:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_VIDEO_PROMPT_REQUIRED")
        if video_plan.get("requiresComposition"):
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_COMPOSE_NOT_READY")
        result, video_urls = self._generate_segment_with_retry(
            executor_id=_clean_text(getattr(payload, "executorId", None)) or DEFAULT_KIE_VIDEO_EXECUTOR_ID,
            prompt=prompt,
            image_url=image_url,
            aspect_ratio=video_plan.get("aspectRatio") or "16:9",
            duration_seconds=int(video_plan.get("durationSeconds") or DEFAULT_VIDEO_SEGMENT_SECONDS),
            poll_timeout=float(getattr(payload, "pollTimeout", None) or 180),
            segment_index=1,
        )
        status = _clean_text(result.get("status")) or "running"
        provider = self._normalize_video_provider(result.get("provider"))
        model = _clean_text(result.get("model")) or ("veo3_fast" if provider == "kie" else DEFAULT_VIDU_VIDEO_MODEL)
        return {
            **preview,
            "status": "succeeded" if status == "succeeded" and video_urls else status,
            "videoResult": {
                "provider": provider,
                "model": model,
                "taskId": result.get("taskId"),
                "state": result.get("state"),
                "status": status,
                "videoUrls": video_urls,
                "storedAssets": result.get("storedAssets") or [],
                "raw": result.get("raw"),
            },
            "execution": {
                "copyGenerated": not bool(preview.get("copyGeneration", {}).get("fallback")),
                "copyGenerationMethod": preview.get("copyGeneration", {}).get("method"),
                "imageGenerated": False,
                "videoGenerated": bool(video_urls),
                "costActions": [self._video_cost_action(provider=provider, model=model)],
                "note": "Video generation is an explicit cost action and result assets are persisted to PODI OSS.",
            },
        }

    def generate_composed_video(self, payload: Any, *, user_id: str | None = None) -> dict[str, Any]:
        preview = self.preview(payload, user_id=user_id)
        image_url = _clean_text(getattr(payload, "productImageUrl", None))
        if not image_url:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_IMAGE_REQUIRED")
        video_plan = preview["videoPlan"]
        video_plan = self._apply_video_prompt_override(video_plan, getattr(payload, "videoPromptOverride", None))
        preview["videoPlan"] = video_plan
        if not video_plan.get("requiresComposition"):
            return self.generate_video(payload, user_id=user_id)

        storyboard = video_plan.get("storyboard") or []
        if not isinstance(storyboard, list) or not storyboard:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_VIDEO_PROMPT_REQUIRED")

        executor_id = _clean_text(getattr(payload, "executorId", None)) or DEFAULT_KIE_VIDEO_EXECUTOR_ID
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
                duration_seconds=int(shot.get("durationSeconds") or video_plan.get("durationSeconds") or DEFAULT_VIDEO_SEGMENT_SECONDS),
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
                        "error": self._summarize_video_failure(result),
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
                    "durationSeconds": int(shot.get("durationSeconds") or video_plan.get("durationSeconds") or DEFAULT_VIDEO_SEGMENT_SECONDS),
                    "provider": self._normalize_video_provider(result.get("provider")),
                    "model": _clean_text(result.get("model")) or _clean_text(video_plan.get("model")) or "veo3_fast",
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
        providers = [self._normalize_video_provider(segment.get("provider")) for segment in segment_results]
        models = [_clean_text(segment.get("model")) or "veo3_fast" for segment in segment_results]
        primary_provider = providers[0] if providers else "kie"
        primary_model = models[0] if models else "veo3_fast"
        cost_actions = [
            self._video_cost_action(provider=provider, model=model) for provider, model in zip(providers, models)
        ]
        cost_actions.append("ffmpeg.compose")
        return {
            **preview,
            "status": "succeeded",
            "videoResult": {
                "provider": f"{primary_provider}+ffmpeg",
                "model": primary_model,
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
                "copyGenerated": not bool(preview.get("copyGeneration", {}).get("fallback")),
                "copyGenerationMethod": preview.get("copyGeneration", {}).get("method"),
                "imageGenerated": False,
                "videoGenerated": bool(video_url),
                "costActions": cost_actions,
                "note": (
                    "Composed video generation is an explicit multi-segment cost action; "
                    "all segment and final assets are persisted to PODI OSS."
                ),
            },
        }

    def _apply_video_prompt_override(self, video_plan: dict[str, Any], prompt_override: Any) -> dict[str, Any]:
        prompt = _clean_text(prompt_override)
        if not prompt:
            return video_plan
        updated = dict(video_plan)
        updated["videoPrompt"] = prompt
        updated["promptSource"] = "user_edited"
        storyboard = updated.get("storyboard")
        if isinstance(storyboard, list):
            segment_count = len(storyboard)
            updated_storyboard: list[dict[str, Any]] = []
            for index, shot in enumerate(storyboard, start=1):
                if not isinstance(shot, dict):
                    continue
                segment_prompt = prompt
                if segment_count > 1:
                    segment_prompt = (
                        f"{prompt} Segment {index} of {segment_count}: "
                        f"{_clean_text(shot.get('goal') or shot.get('camera')) or 'continue the planned visual story'}. "
                        "Keep visual continuity with the previous segment when provided."
                    )
                updated_storyboard.append({**shot, "prompt": segment_prompt})
            updated["storyboard"] = updated_storyboard
        return updated

    def generate_visual(self, payload: Any, *, user_id: str | None = None) -> dict[str, Any]:
        preview = self.preview(payload, user_id=user_id)
        image_url = _clean_text(getattr(payload, "productImageUrl", None))
        if not image_url:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_IMAGE_REQUIRED")
        content_package = preview.get("contentPackage") if isinstance(preview.get("contentPackage"), dict) else {}
        briefs = self._normalize_image_briefs_for_visual(
            payload=payload,
            content_package=content_package,
        )
        if not briefs:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_IMAGE_BRIEF_MISSING")
        image_results: list[dict[str, Any]] = []
        stored_urls: list[str] = []
        image_urls: list[str] = []
        for brief in briefs:
            scene_id = _clean_text(brief.get("id")) or "listing-main"
            scene_label = _clean_text(brief.get("label")) or scene_id or "visual"
            prompt = _build_visual_prompt(
                product_card=preview.get("productCard", {}),
                resolved_product_facts=preview.get("resolvedProductFacts") if isinstance(preview.get("resolvedProductFacts"), dict) else None,
                copy_package=preview.get("copyPackage"),
                visual_brief=_as_record(brief),
                output_language=preview.get("outputLanguage"),
                market_region=preview.get("marketRegion"),
                extra_prompt=_clean_text(getattr(payload, "extraPrompt", None)),
            )
            if not prompt:
                raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_VISUAL_PROMPT_EMPTY")
            negative_prompt = " ".join(
                item
                for item in _normalize_list(_clean_text(getattr(payload, "forbiddenClaims", None)) or getattr(payload, "forbiddenClaims", None))
                if item
            )
            result = self._generate_visual_image(
                product_image_url=image_url,
                prompt=prompt,
                negative_prompt=negative_prompt,
                user_id=user_id,
                metadata={
                    "businessKey": "product_commercialization",
                    "sceneId": scene_id,
                    "sceneLabel": scene_label,
                    "visualRoute": "image2_quality_first",
                    "source": "product_commercialization.visual_generate",
                },
            )
            image_result_urls = self._extract_image_urls(result)
            if not image_result_urls:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "PRODUCT_COMMERCIALIZATION_VISUAL_GENERATION_FAILED",
                        "taskId": result.get("taskId"),
                        "raw": result.get("raw"),
                    },
                )
            scene_url = image_result_urls[0]
            stored_urls.extend(_as_list(result.get("resultUrls")))
            image_urls.extend(image_result_urls)
            image_results.append(
                {
                    "sceneId": scene_id,
                    "label": scene_label,
                    "provider": self._normalize_visual_provider(result.get("provider")),
                    "model": _clean_text(result.get("model")) or DEFAULT_VISUAL_MODEL,
                    "taskId": result.get("taskId"),
                    "state": result.get("state"),
                    "status": _clean_text(result.get("status")) or "succeeded",
                    "imageUrl": scene_url,
                    "imageUrls": image_result_urls,
                    "storedAssets": result.get("assets") or result.get("storedAssets") or result.get("result"),
                    "prompt": prompt,
                    "raw": result.get("raw"),
                }
            )

        provider = self._normalize_visual_provider(
            image_results[0].get("provider") if isinstance(image_results, list) and image_results else None
        )
        model = _clean_text(image_results[0].get("model")) or DEFAULT_VISUAL_MODEL
        cost_action = self._visual_cost_action(provider=provider, model=model)
        return {
            **preview,
            "status": "succeeded",
            "imageResult": {
                "provider": provider,
                "model": model,
                "status": "succeeded",
                "imageResults": image_results,
                "imageUrls": image_urls,
                "storedAssets": stored_urls,
                "costActions": [cost_action] + [item.get("costAction") for item in image_results if item.get("costAction")],
            },
            "execution": {
                "copyGenerated": not bool(preview.get("copyGeneration", {}).get("fallback")),
                "copyGenerationMethod": preview.get("copyGeneration", {}).get("method"),
                "imageGenerated": bool(image_urls),
                "videoGenerated": False,
                "costActions": [cost_action],
                "note": "Image generation is an explicit cost action and result assets are persisted to PODI OSS.",
            },
        }

    def _normalize_image_briefs_for_visual(self, payload: Any, content_package: dict[str, Any]) -> list[dict[str, Any]]:
        requested = _normalize_list(getattr(payload, "visualScenes", None))
        raw_briefs = content_package.get("imageBriefs") if isinstance(content_package, dict) else None
        briefs = raw_briefs if isinstance(raw_briefs, list) else []
        normalized: list[dict[str, Any]] = []
        scene_map: dict[str, dict[str, Any]] = {}
        for index, brief in enumerate(briefs):
            if not isinstance(brief, dict):
                continue
            brief_id = _clean_text(brief.get("id")) or f"visual-{index + 1}"
            scene_map[brief_id] = brief
        if requested:
            for scene_id in requested:
                scene = scene_map.get(_clean_text(scene_id))
                if isinstance(scene, dict):
                    normalized.append(scene)
            if normalized:
                return normalized
        for scene_id in ("listing-main", "social-ad-cover", "detail-closeup"):
            scene = scene_map.get(scene_id)
            if isinstance(scene, dict):
                normalized.append(scene)
        if normalized:
            return normalized
        if isinstance(briefs, list):
            return [brief for brief in briefs if isinstance(brief, dict)][:3]
        return []

    def _generate_visual_image(
        self,
        *,
        product_image_url: str,
        prompt: str,
        negative_prompt: str,
        user_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        del user_id
        compiled_prompt = prompt
        if negative_prompt:
            compiled_prompt = f"{prompt}\n\nAvoid: {negative_prompt}"
        response = ability_invocation_service.invoke(
            ability_id=DEFAULT_VISUAL_ABILITY_ID,
            payload=AbilityInvokeRequest(
                inputs={
                    "image_url": product_image_url,
                    "prompt": compiled_prompt,
                    "model": DEFAULT_VISUAL_MODEL,
                    "size": "auto",
                    "quality": "auto",
                    "background": "auto",
                    "output_format": "png",
                    "n": 1,
                },
                imageUrl=product_image_url,
                metadata={
                    **(metadata or {}),
                    "primaryExecutionEngine": "gpt-image-2",
                    "routeType": "image2_quality_first",
                    "abilityId": DEFAULT_VISUAL_ABILITY_ID,
                },
            ),
            user=None,
            source="product-commercialization-visual",
        )
        if not response:
            raise HTTPException(status_code=502, detail="PRODUCT_COMMERCIALIZATION_VISUAL_GENERATION_FAILED")
        result = response.model_dump()
        image_urls = self._extract_response_asset_urls(result.get("images") or result.get("assets"))
        result = {
            "provider": DEFAULT_VISUAL_PROVIDER,
            "model": DEFAULT_VISUAL_MODEL,
            "status": result.get("status") or "succeeded",
            "taskId": result.get("requestId") or result.get("logId"),
            "state": result.get("status") or "succeeded",
            "imageUrls": image_urls,
            "resultUrls": image_urls,
            "assets": result.get("images") or result.get("assets") or [],
            "raw": result.get("raw"),
            "logId": result.get("logId"),
        }
        return result

    @staticmethod
    def _extract_response_asset_urls(value: Any) -> list[str]:
        urls: list[str] = []

        def add(item: Any) -> None:
            if isinstance(item, str) and item.strip().startswith(("http://", "https://")):
                urls.append(item.strip())
            elif isinstance(item, dict):
                for key in ("ossUrl", "storedUrl", "sourceUrl", "url", "imageUrl"):
                    add(item.get(key))
            elif isinstance(item, list):
                for child in item:
                    add(child)

        add(value)
        seen: set[str] = set()
        out: list[str] = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            out.append(url)
        return out

    @staticmethod
    def _normalize_visual_provider(value: Any) -> str:
        text = _clean_text(value).lower()
        if text.startswith("openai"):
            return "openai"
        return DEFAULT_VISUAL_PROVIDER

    @staticmethod
    def _visual_cost_action(*, provider: str, model: str) -> str:
        normalized_provider = _clean_text(provider).lower() or DEFAULT_VISUAL_PROVIDER
        normalized_model = _clean_text(model).lower().replace("-", "_") or DEFAULT_VISUAL_MODEL.replace("-", "_")
        return f"{normalized_provider}.{normalized_model}.image"

    @staticmethod
    def _extract_image_urls(value: dict[str, Any]) -> list[str]:
        image_urls = value.get("imageUrls") or value.get("resultUrls") or []
        urls: list[str] = []
        if isinstance(image_urls, str):
            candidates = [image_urls]
        elif isinstance(image_urls, list):
            candidates = [str(item) for item in image_urls]
        else:
            candidates = []
        for item in candidates:
            url = _clean_text(item)
            if url.startswith(("http://", "https://")):
                urls.append(url)
        return urls


    def _generate_segment_with_retry(
        self,
        *,
        executor_id: str,
        prompt: str,
        image_url: str,
        aspect_ratio: str,
        duration_seconds: int,
        poll_timeout: float,
        segment_index: int,
    ) -> tuple[dict[str, Any], list[str]]:
        last_result: dict[str, Any] = {}
        last_exception: Exception | None = None
        provider = self._resolve_video_provider(executor_id)
        profile = self._video_profile_for_provider(provider)
        duration = self._normalize_segment_duration(duration_seconds, profile)
        for attempt in range(1, VIDEO_SEGMENT_MAX_ATTEMPTS + 1):
            try:
                if provider == "vidu":
                    result = integration_test_service.run_vidu_video_task(
                        executor_id=executor_id,
                        endpoint=_clean_text(profile.get("endpoint")) or "/ent/v2/img2video",
                        status_endpoint=_clean_text(profile.get("statusEndpoint")) or "/ent/v2/tasks/{task_id}/creations",
                        model=_clean_text(profile.get("model")) or DEFAULT_VIDU_VIDEO_MODEL,
                        input_payload={
                            "prompt": prompt,
                            "images": [image_url],
                            "duration": duration,
                            "resolution": "720p",
                            "movement_amplitude": "auto",
                            "audio": False,
                            "bgm": False,
                        },
                        input_array_target="images",
                        poll_timeout=poll_timeout,
                        poll_interval=2.5,
                    )
                else:
                    result = integration_test_service.run_kie_market_task(
                        executor_id=executor_id,
                        endpoint=_clean_text(profile.get("endpoint")) or "/api/v1/veo/generate",
                        status_endpoint=_clean_text(profile.get("statusEndpoint")) or "/api/v1/veo/record-info",
                        result_format="veo3",
                        model=_clean_text(profile.get("model")) or "veo3_fast",
                        input_payload={
                            "prompt": prompt,
                            "imageUrls": [image_url],
                            "aspectRatio": aspect_ratio,
                            "duration": duration,
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
            "error": self._summarize_video_failure(last_result),
        }
        if last_exception is not None and not detail["error"]:
            detail["error"] = str(getattr(last_exception, "detail", last_exception))
        raise HTTPException(status_code=502, detail=detail)

    def _resolve_video_provider(self, executor_id: str) -> str:
        lowered = _clean_text(executor_id).lower()
        if "vidu" in lowered:
            return "vidu"
        try:
            executor = integration_test_service._get_executor(executor_id)  # type: ignore[attr-defined]
        except Exception:
            return "kie"
        executor_type = _clean_text(getattr(executor, "type", None)).lower()
        if executor_type in {"vidu", "vidu-video", "vidu_video"}:
            return "vidu"
        return "kie"

    def _video_profile_for_provider(self, provider: str) -> dict[str, Any]:
        normalized = "vidu" if _clean_text(provider).lower().startswith("vidu") else "kie"
        return dict(VIDEO_MODEL_PROFILES[normalized])

    def _normalize_segment_duration(self, value: Any, profile: dict[str, Any]) -> int:
        options = [int(item) for item in profile.get("segmentDurationOptions", []) if int(item) > 0]
        if not options:
            return DEFAULT_VIDEO_SEGMENT_SECONDS
        try:
            requested = int(value)
        except (TypeError, ValueError):
            requested = int(profile.get("defaultSegmentSeconds") or options[0])
        if requested in options:
            return requested
        return min(options, key=lambda item: (abs(item - requested), item))

    def _plan_video_segment_durations(self, target_duration: int, profile: dict[str, Any]) -> list[int]:
        options = sorted(
            [int(item) for item in profile.get("segmentDurationOptions", []) if int(item) > 0],
            reverse=True,
        )
        if not options:
            return [DEFAULT_VIDEO_SEGMENT_SECONDS]
        durations: list[int] = []
        remaining = target_duration
        max_segment_count = max(1, int(profile.get("maxSegmentCount") or 12))
        while remaining > 0 and len(durations) < max_segment_count:
            exact_or_under = [item for item in options if item <= remaining]
            duration = exact_or_under[0] if exact_or_under else options[-1]
            durations.append(duration)
            remaining -= duration
        return durations or [int(profile.get("defaultSegmentSeconds") or options[0])]

    def _normalize_video_provider(self, value: Any) -> str:
        text = _clean_text(value).lower()
        if text.startswith("vidu"):
            return "vidu"
        return "kie"

    def _video_cost_action(self, *, provider: str, model: str) -> str:
        normalized_provider = self._normalize_video_provider(provider)
        normalized_model = _clean_text(model).lower().replace("-", "_") or (
            DEFAULT_VIDU_VIDEO_MODEL.replace("-", "_") if normalized_provider == "vidu" else "veo3_fast"
        )
        return f"{normalized_provider}.{normalized_model}.video"

    def _summarize_video_failure(self, result: dict[str, Any]) -> dict[str, Any] | str | None:
        provider = self._normalize_video_provider(result.get("provider") if isinstance(result, dict) else None)
        if provider == "vidu":
            return self._summarize_vidu_failure(result)
        return self._summarize_kie_failure(result)

    def _summarize_vidu_failure(self, result: dict[str, Any]) -> dict[str, Any] | str | None:
        raw = result.get("raw") if isinstance(result, dict) else None
        response = raw.get("response") if isinstance(raw, dict) else None
        if isinstance(response, dict):
            summary = {
                "state": response.get("state") or response.get("status"),
                "error": response.get("error"),
                "message": response.get("message") or response.get("detail"),
            }
            nested = response.get("data")
            if isinstance(nested, dict):
                summary.update(
                    {
                        "dataState": nested.get("state") or nested.get("status"),
                        "dataError": nested.get("error"),
                        "dataMessage": nested.get("message") or nested.get("detail"),
                    }
                )
            compact = {key: value for key, value in summary.items() if value not in (None, "", [])}
            return compact or None
        return None

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
        fallback = float(DEFAULT_VIDEO_SEGMENT_SECONDS)
        for item in trims:
            if not isinstance(item, dict):
                continue
            try:
                if int(item.get("segment")) != index:
                    continue
                source_duration = float(item.get("sourceDurationSeconds") or item.get("durationSeconds") or fallback)
                keep = float(item.get("keepSeconds") or source_duration)
            except (TypeError, ValueError):
                return fallback
            return max(0.5, min(source_duration, keep))
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
            logger.warning("ffmpeg failed: %s", (completed.stderr or completed.stdout or "")[-1000:])
            raise HTTPException(status_code=502, detail="PRODUCT_COMMERCIALIZATION_COMPOSE_FAILED")

    def _normalize_target_duration_seconds(self, value: Any, profile: dict[str, Any] | None = None) -> int:
        profile = profile or VIDEO_MODEL_PROFILES["kie"]
        options = [int(item) for item in profile.get("segmentDurationOptions", []) if int(item) > 0]
        default_duration = int(profile.get("defaultSegmentSeconds") or (options[0] if options else DEFAULT_VIDEO_SEGMENT_SECONDS))
        if value in (None, ""):
            return default_duration
        try:
            duration = int(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_TARGET_DURATION_INVALID") from exc
        min_duration = min(options) if options else DEFAULT_VIDEO_SEGMENT_SECONDS
        max_duration = min(int(profile.get("maxTargetSeconds") or MAX_TARGET_VIDEO_SECONDS), MAX_TARGET_VIDEO_SECONDS)
        if duration < min_duration or duration > max_duration:
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
                "The product image is the primary visual fact source; exported fields explain the image.",
                "Use exported fields directly when they match the image; conflicts must be recorded and reviewed.",
                "Missing fields should not block MVP preview, but should lower review confidence.",
            ],
        }

    def _localized_copy(self, *, en: Any, zh: Any, output_language: str) -> Any:
        if output_language == "en-US":
            return en
        if output_language == "zh-CN":
            return zh
        return {"en-US": en, "zh-CN": zh}

    def _build_content_bundle(
        self,
        *,
        payload: Any,
        product_card: dict[str, Any],
        scenarios: list[str],
        output_language: str,
        market_region: str,
    ) -> dict[str, Any]:
        template_package = self._build_template_content_package(
            product_card=product_card,
            market_region=market_region,
            extra_prompt=getattr(payload, "extraPrompt", None),
        )
        generation: dict[str, Any] = {
            "method": "template_fallback",
            "provider": "internal",
            "model": "template-commercial-copy-v1",
            "fallback": True,
            "evidence": "No LLM/VL response was used.",
        }
        content_package = template_package
        try:
            content_package, generation = self._generate_model_content_package(
                payload=payload,
                product_card=product_card,
                template_package=template_package,
                market_region=market_region,
            )
            fact_guard = self._content_fact_guard(content_package=content_package, product_card=product_card)
            generation = {**generation, "factGuard": fact_guard}
            if not fact_guard.get("passed", True):
                if self._has_image_field_conflict(content_package):
                    generation = {
                        **generation,
                        "factGuard": {
                            **fact_guard,
                            "passed": True,
                            "conflictOverride": True,
                            "reason": "image_field_conflict_reported_product_image_primary",
                        },
                        "evidence": (
                            "LLM/VL response reported a product image/exported field conflict; "
                            "copy is kept because product image is the primary visual fact source."
                        ),
                    }
                else:
                    logger.warning("product commercialization copy model fact guard fallback: %s", fact_guard)
                    content_package = template_package
                    generation = {
                        **generation,
                        "fallback": True,
                        "fallbackReason": f"PRODUCT_COPY_FACT_GUARD_FAILED: {', '.join(fact_guard.get('missingFields') or [])}",
                        "evidence": "LLM/VL response failed product fact guard; field-anchored template fallback used.",
                    }
        except Exception as exc:  # pragma: no cover - defensive provider path
            logger.warning("product commercialization copy model fallback: %s", exc)
            generation = {
                **generation,
                "fallbackReason": str(exc)[:500],
                "evidence": "LLM/VL unavailable or returned invalid JSON; template fallback used.",
                "factGuard": {"passed": False, "reason": "model_unavailable_or_invalid"},
            }

        copy_package = self._select_copy_package(
            full_package=content_package,
            scenarios=scenarios,
            output_language=output_language,
            market_region=market_region,
            extra_prompt=getattr(payload, "extraPrompt", None),
        )
        return {
            "copyPackage": copy_package,
            "contentPackage": content_package,
            "copyGeneration": generation,
        }

    def _content_fact_guard(self, *, content_package: dict[str, Any], product_card: dict[str, Any]) -> dict[str, Any]:
        facts = {**product_card.get("inferredFacts", {}), **product_card.get("sourceFacts", {})}
        terms = _critical_product_terms(facts)
        if not terms:
            return {"passed": True, "terms": [], "fieldHits": {}, "reason": "no_critical_terms"}
        copy = content_package.get("copyPackage") if isinstance(content_package.get("copyPackage"), dict) else {}
        fields = {
            "listingTitle": self._pick_language(copy.get("listingTitle"), "en-US"),
            "detailDescription": self._pick_language(copy.get("detailDescription"), "en-US"),
            "keywordPack": copy.get("keywordPack"),
        }
        field_hits: dict[str, bool] = {}
        for field, value in fields.items():
            text = _flatten_text(value).lower()
            field_hits[field] = any(term in text for term in terms)
        missing = [field for field, hit in field_hits.items() if not hit]
        passed = len(field_hits) - len(missing) >= FACT_GUARD_MIN_FIELD_HITS
        return {
            "passed": passed,
            "terms": terms,
            "fieldHits": field_hits,
            "missingFields": missing,
            "reason": None if passed else "critical_product_terms_missing_from_major_copy_fields",
        }

    def _has_image_field_conflict(self, content_package: dict[str, Any]) -> bool:
        assessment = content_package.get("imageFactAssessment") if isinstance(content_package.get("imageFactAssessment"), dict) else {}
        return bool(self._normalize_string_list(assessment.get("fieldConflicts"), [], min_items=0))

    def _build_template_content_package(
        self,
        *,
        product_card: dict[str, Any],
        market_region: str,
        extra_prompt: Any,
    ) -> dict[str, Any]:
        copy_package = self._build_copy_package(
            product_card=product_card,
            scenarios=list(DEFAULT_COPY_SCENARIOS),
            output_language="bilingual",
            market_region=market_region,
            extra_prompt=extra_prompt,
        )
        facts = {**product_card.get("inferredFacts", {}), **product_card.get("sourceFacts", {})}
        name_en = _english_product_name(facts)
        name_zh = _zh_product_name(facts)
        material = _clean_text(facts.get("material") or facts.get("composition"))
        category = _clean_text(facts.get("categoryLevel2") or facts.get("categoryLevel1"))
        material_en = _english_text_or_empty(material)
        category_en = _english_text_or_empty(category)
        positioning = {
            "coreAngle": f"{name_en} positioned as a practical POD-ready ecommerce item for {market_region} buyers.",
            "targetCustomers": [category_en or "POD shoppers", "gift buyers", "everyday style shoppers"],
            "purchaseOccasions": ["daily use", "seasonal gifting", "custom design collections"],
            "sellingPoints": [
                f"Recognizable product type: {name_en}",
                f"Material cue: {material_en or 'source material needs review'}",
                "Suitable for listing copy, ad copy, and visual asset planning.",
            ],
            "factBoundaries": [
                "Validate product facts before publishing.",
                "Do not claim shipping, certification, or trademark details unless source fields provide them.",
            ],
        }
        image_briefs = [
            {
                "id": "listing-main",
                "label": "商品主图",
                "usage": "Marketplace listing hero image / 商品上架首图",
                "linkedCopy": ["listingTitle", "bulletPoints"],
                "prompt": (
                    f"Create a clean ecommerce hero image for {name_en}. Preserve product shape, pattern, "
                    "color and material. No text, watermark, logo, price tag or unrelated props."
                ),
                "riskNotes": ["Use the uploaded product image as factual reference."],
            },
            {
                "id": "detail-closeup",
                "label": "材质细节图",
                "usage": "Detail page proof image / 详情页材质卖点图",
                "linkedCopy": ["bulletPoints", "detailDescription"],
                "prompt": (
                    f"Create a close-up detail image for {name_en}, focusing on material texture, print clarity "
                    f"and product construction. Material cue: {material_en or 'use visible material only'}."
                ),
                "riskNotes": ["Do not invent unavailable product components."],
            },
            {
                "id": "social-ad-cover",
                "label": "社媒广告封面",
                "usage": "Social ad cover / 社媒广告封面",
                "linkedCopy": ["adShortCopy"],
                "prompt": (
                    f"Create a clean lifestyle ad cover for {name_en}, suitable for {market_region} ecommerce "
                    "marketing. Premium but natural, no embedded text."
                ),
                "riskNotes": ["Avoid overpromising performance or sustainability."],
            },
        ]
        channel_usage = [
            {
                "channel": "Marketplace listing",
                "howToUse": "Use listing title, bullet points, detail description, and listing-main visual together.",
                "assets": ["listingTitle", "bulletPoints", "detailDescription", "listing-main"],
            },
            {
                "channel": "Social advertising",
                "howToUse": "Use ad short copy with a social-ad-cover visual; keep final ad claims factual.",
                "assets": ["adShortCopy", "social-ad-cover"],
            },
        ]
        image_fact_assessment = {
            "visualSourcePriority": "product_image_primary",
            "observedProductType": "Image analysis unavailable in template fallback.",
            "observedVisualFeatures": ["Use uploaded product image as the visual anchor.", "Review visible product shape and pattern manually."],
            "fieldConflicts": [],
            "missingFieldInferences": product_card.get("missingFields") or [],
            "copyDecision": "Template fallback uses exported fields but requires manual image/field consistency review.",
            "confidence": "low",
        }
        return {
            "commercePositioning": positioning,
            "copyPackage": copy_package,
            "imageFactAssessment": image_fact_assessment,
            "imageBriefs": image_briefs,
            "channelUsageGuide": channel_usage,
            "styleGuardrails": copy_package.get("styleGuardrails") or [],
            "modelNotes": ["Template fallback package. Use only when LLM/VL is unavailable."],
        }

    def _generate_model_content_package(
        self,
        *,
        payload: Any,
        product_card: dict[str, Any],
        template_package: dict[str, Any],
        market_region: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        settings = get_settings()
        image_url = _clean_text(getattr(payload, "productImageUrl", None))
        context_payload = self._build_copy_model_context(
            payload=payload,
            product_card=product_card,
            market_region=market_region,
        )
        provider_errors: list[str] = []
        planner_credentials = self._resolve_openai_planner_credentials(settings)
        if settings.business_agent_planner_enabled and planner_credentials.get("apiKey"):
            try:
                data = self._call_openai_copy_model(
                    settings=settings,
                    context_payload=context_payload,
                    image_url=image_url,
                    api_key=str(planner_credentials["apiKey"]),
                    base_url=str(planner_credentials["baseUrl"]),
                )
                content = self._normalize_model_content_package(data["content"], template_package=template_package)
                return content, {
                    "method": "openai_responses",
                    "provider": "openai",
                    "model": settings.business_agent_planner_model,
                    "fallback": False,
                    "keySource": planner_credentials.get("source"),
                    "responseId": data.get("responseId"),
                    "usage": data.get("usage"),
                    "evidence": "LLM/VL generated structured ecommerce content package.",
                }
            except Exception as exc:
                provider_errors.append(f"openai:{str(exc)[:240]}")

        try:
            prompt = self._build_copy_model_prompt(context_payload=context_payload)
            result = integration_test_service.run_volcengine_chat_completion(
                executor_id="executor_volcengine_default",
                model=DEFAULT_VOLCENGINE_VL_MODEL_ID,
                prompt=prompt,
                image_url=image_url or None,
                params={"temperature": 0.72},
            )
            content = self._normalize_model_content_package(
                self._parse_model_json_text(_clean_text(result.get("text"))),
                template_package=template_package,
            )
            return content, {
                "method": "volcengine_chat",
                "provider": "volcengine",
                "model": _clean_text(result.get("model")) or DEFAULT_VOLCENGINE_VL_MODEL_ID,
                "fallback": False,
                "usage": None,
                "evidence": "Volcengine VL chat generated structured ecommerce content package.",
            }
        except Exception as exc:
            provider_errors.append(f"volcengine:{str(exc)[:240]}")

        raise RuntimeError("; ".join(provider_errors) or "COPY_MODEL_NOT_CONFIGURED")

    def _resolve_openai_planner_credentials(self, settings: Any) -> dict[str, str]:
        env_key = _clean_text(getattr(settings, "business_agent_openai_api_key", None))
        env_base_url = _clean_text(getattr(settings, "business_agent_openai_base_url", None)) or "https://api.openai.com"
        if env_key:
            return {"apiKey": env_key, "baseUrl": env_base_url.rstrip("/"), "source": "env"}

        try:
            with get_session() as session:
                for provider in ("openai", "openai_compatible"):
                    api_key = pick_provider_api_key(session, provider=provider)
                    if not api_key or not _clean_text(api_key.key):
                        continue
                    metadata = api_key.extra_metadata if isinstance(api_key.extra_metadata, dict) else {}
                    key_base_url = (
                        _clean_text(metadata.get("baseUrl"))
                        or _clean_text(metadata.get("base_url"))
                        or _clean_text(metadata.get("baseURL"))
                        or env_base_url
                    )
                    return {
                        "apiKey": _clean_text(api_key.key),
                        "baseUrl": key_base_url.rstrip("/"),
                        "source": f"api_key_pool:{provider}:{api_key.id}",
                    }
        except Exception as exc:  # noqa: BLE001 - planner can still try other providers.
            logger.warning("product commercialization openai key pool lookup failed: %s", exc)
        return {}

    def _build_copy_model_context(self, *, payload: Any, product_card: dict[str, Any], market_region: str) -> dict[str, Any]:
        return {
            "task": "Generate a one-stop ecommerce copy and visual-brief content package for a POD merchant.",
            "outputLanguage": _clean_text(getattr(payload, "outputLanguage", None)) or "en-US",
            "marketRegion": market_region,
            "commercePlatform": _clean_text(getattr(payload, "commercePlatform", None)) or "marketplace",
            "copyTone": _clean_text(getattr(payload, "copyTone", None)) or "natural_professional",
            "targetAudience": _clean_text(getattr(payload, "targetAudience", None)) or "general ecommerce shoppers",
            "sellingAngle": _clean_text(getattr(payload, "sellingAngle", None)) or "product benefits and gifting occasions",
            "forbiddenClaims": _normalize_list(getattr(payload, "forbiddenClaims", None)),
            "extraPrompt": _clean_text(getattr(payload, "extraPrompt", None)) or None,
            "productCard": product_card,
            "rules": [
                "The uploaded product image is the primary visual source of truth. Read it first, then use exported fields as structured explanation.",
                "Use exported fields when they match or reasonably explain the image. If fields are missing, infer only visible facts from the image and mark them in imageFactAssessment.missingFieldInferences.",
                "If exported fields conflict with the product image, do not blindly keep the fields. Record the conflict in imageFactAssessment.fieldConflicts, base copy on the visible product image, and mark low confidence.",
                "Write natural ecommerce copy; avoid generic template phrases and mechanical repetition.",
                "For en-US output, translate Chinese source fields into natural English. Do not mix Chinese category or material words into English copy unless they are exact product names.",
                "Do not include medical, trademark, sustainability, shipping, discount, certification, or size claims unless the fields explicitly provide them.",
                "Return JSON only and follow the provided schema exactly.",
            ],
        }

    def _build_copy_model_prompt(self, *, context_payload: dict[str, Any]) -> str:
        return (
            "你是 PODI 的电商商品内容策略师。请基于产品图和产品导出字段，为 POD 商家生成可直接用于上架和营销的内容包。\n"
            "事实优先级：产品图是最高优先级的视觉事实来源；导出 JSON 是对产品图的结构化说明。"
            "你必须先识别产品图中的商品类型、颜色、图案、材质视觉线索和使用场景，再读取 JSON 字段。\n"
            "如果 JSON 字段缺失，可以基于图片推断可见事实，但必须写入 imageFactAssessment.missingFieldInferences 并降低 confidence。"
            "如果 JSON 与产品图疑似不符，不能无脑按 JSON 写；必须写入 imageFactAssessment.fieldConflicts，文案以图片中可见商品为主，冲突字段只作为待人工复核信息。\n"
            "必须输出 JSON，不要 Markdown，不要解释。JSON 字段必须包含 commercePositioning、listingTitle、bulletPoints、"
            "detailDescription、adShortCopy、keywordPack、imageFactAssessment、imageBriefs、channelUsageGuide、styleGuardrails、modelNotes。\n"
            "listingTitle/detailDescription 使用 {\"en-US\": string, \"zh-CN\": string}；bulletPoints/adShortCopy 使用双语数组。"
            "en-US 字段必须是自然英文，需要把中文类目、材质、工艺翻译成英文，不能把中文词直接混进英文文案。"
            "imageBriefs 要说明每张配图服务哪类文案和使用场景。\n"
            f"输入上下文：{json.dumps(context_payload, ensure_ascii=False)}"
        )

    def _call_openai_copy_model(
        self,
        *,
        settings: Any,
        context_payload: dict[str, Any],
        image_url: str,
        api_key: str,
        base_url: str,
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [
            {"type": "input_text", "text": json.dumps(context_payload, ensure_ascii=False)}
        ]
        if image_url:
            content.append({"type": "input_image", "image_url": image_url})
        request_payload = {
            "model": settings.business_agent_planner_model,
            "instructions": (
                "You are PODI's ecommerce copy strategist for POD merchants. Generate a practical, non-mechanical "
                "content package for listing and marketing. The uploaded product image is the highest-priority "
                "visual fact source; exported fields are structured explanations of that image. Read the image first. "
                "Use fields when they match the image, infer missing visible facts from the image with low-confidence "
                "notes, and record conflicts in imageFactAssessment.fieldConflicts instead of blindly trusting fields. "
                "Return only JSON matching the schema."
            ),
            "input": [{"role": "user", "content": content}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "podi_product_commerce_content_package",
                    "strict": True,
                    "schema": COPY_MODEL_JSON_SCHEMA,
                }
            },
            "store": False,
        }
        resolved_base_url = str(base_url or "https://api.openai.com").rstrip("/")
        with httpx.Client(timeout=float(settings.business_agent_planner_timeout_seconds or 30)) as client:
            response = client.post(
                f"{resolved_base_url}/v1/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
            response.raise_for_status()
            data = response.json()
        return {
            "content": self._parse_model_json_text(self._extract_openai_output_text(data)),
            "responseId": data.get("id"),
            "usage": data.get("usage"),
        }

    def _normalize_model_content_package(
        self,
        raw: dict[str, Any],
        *,
        template_package: dict[str, Any],
    ) -> dict[str, Any]:
        template_copy = template_package.get("copyPackage") if isinstance(template_package.get("copyPackage"), dict) else {}
        return {
            "commercePositioning": self._normalize_positioning(
                raw.get("commercePositioning"),
                fallback=template_package.get("commercePositioning") if isinstance(template_package.get("commercePositioning"), dict) else {},
            ),
            "copyPackage": {
                "listingTitle": self._normalize_bilingual_text(raw.get("listingTitle"), template_copy.get("listingTitle")),
                "bulletPoints": self._normalize_bilingual_list(raw.get("bulletPoints"), template_copy.get("bulletPoints"), min_items=5),
                "detailDescription": self._normalize_bilingual_text(raw.get("detailDescription"), template_copy.get("detailDescription")),
                "adShortCopy": self._normalize_bilingual_list(raw.get("adShortCopy"), template_copy.get("adShortCopy"), min_items=3),
                "keywordPack": self._normalize_english_string_list(raw.get("keywordPack"), template_copy.get("keywordPack"), min_items=6),
                "styleGuardrails": self._normalize_string_list(
                    raw.get("styleGuardrails"),
                    template_package.get("styleGuardrails"),
                    min_items=2,
                ),
                "sourcePrompt": template_copy.get("sourcePrompt"),
            },
            "imageFactAssessment": self._normalize_image_fact_assessment(
                raw.get("imageFactAssessment"),
                template_package.get("imageFactAssessment"),
            ),
            "imageBriefs": self._normalize_image_briefs(raw.get("imageBriefs"), template_package.get("imageBriefs")),
            "channelUsageGuide": self._normalize_channel_usage(raw.get("channelUsageGuide"), template_package.get("channelUsageGuide")),
            "styleGuardrails": self._normalize_string_list(raw.get("styleGuardrails"), template_package.get("styleGuardrails"), min_items=2),
            "modelNotes": self._normalize_string_list(raw.get("modelNotes"), ["Model generated package; review facts before publishing."], min_items=1),
        }

    def _normalize_image_fact_assessment(self, value: Any, fallback: Any) -> dict[str, Any]:
        raw = value if isinstance(value, dict) else {}
        fallback_map = fallback if isinstance(fallback, dict) else {}
        field_conflicts = self._normalize_string_list(
            raw.get("fieldConflicts"),
            fallback_map.get("fieldConflicts"),
            min_items=0,
        )[:10]
        missing_inferences = self._normalize_string_list(
            raw.get("missingFieldInferences"),
            fallback_map.get("missingFieldInferences"),
            min_items=0,
        )[:10]
        confidence = self._normalize_image_fact_confidence(
            raw.get("confidence") or raw.get("confidenceScore") or raw.get("confidenceLevel"),
            fallback_map.get("confidence"),
            has_conflicts=bool(field_conflicts),
        )
        return {
            "visualSourcePriority": _clean_text(raw.get("visualSourcePriority"))
            or _clean_text(fallback_map.get("visualSourcePriority"))
            or "product_image_primary",
            "observedProductType": _clean_text(raw.get("observedProductType"))
            or (
                "Product image conflicts with exported fields; visible product facts are recorded in fieldConflicts."
                if field_conflicts
                else _clean_text(fallback_map.get("observedProductType"))
            )
            or "Needs manual review.",
            "observedVisualFeatures": self._normalize_string_list(
                raw.get("observedVisualFeatures"),
                fallback_map.get("observedVisualFeatures"),
                min_items=2,
            )[:10],
            "fieldConflicts": field_conflicts,
            "missingFieldInferences": missing_inferences,
            "copyDecision": _clean_text(raw.get("copyDecision"))
            or (
                "Use the visible product image as the primary fact source; exported fields with conflicts require manual review."
                if field_conflicts
                else _clean_text(fallback_map.get("copyDecision"))
            )
            or "Use product image as visual anchor and review field consistency before publishing.",
            "confidence": confidence,
        }

    def _normalize_image_fact_confidence(self, value: Any, fallback: Any, *, has_conflicts: bool) -> str:
        text = _clean_text(value).lower()
        if text:
            if text in {"high", "medium", "low"}:
                return text
            try:
                score = float(text)
            except ValueError:
                score = None
            if score is not None:
                if has_conflicts or score < 0.67:
                    return "low"
                if score < 0.85:
                    return "medium"
                return "high"
        fallback_text = _clean_text(fallback).lower()
        if fallback_text in {"high", "medium", "low"}:
            return fallback_text
        return "low" if has_conflicts else "medium"

    def _select_copy_package(
        self,
        *,
        full_package: dict[str, Any],
        scenarios: list[str],
        output_language: str,
        market_region: str,
        extra_prompt: Any,
    ) -> dict[str, Any]:
        full_copy = full_package.get("copyPackage") if isinstance(full_package.get("copyPackage"), dict) else {}
        result: dict[str, Any] = {
            "marketRegion": market_region,
            "styleGuardrails": full_package.get("styleGuardrails") or full_copy.get("styleGuardrails") or [],
            "sourcePrompt": _clean_text(extra_prompt) or None,
        }
        if "listing_title" in scenarios:
            result["listingTitle"] = self._pick_language(full_copy.get("listingTitle"), output_language)
        if "bullet_points" in scenarios:
            result["bulletPoints"] = self._pick_language(full_copy.get("bulletPoints"), output_language)
        if "detail_description" in scenarios:
            result["detailDescription"] = self._pick_language(full_copy.get("detailDescription"), output_language)
        if "ad_short_copy" in scenarios:
            result["adShortCopy"] = self._pick_language(full_copy.get("adShortCopy"), output_language)
        if "keyword_pack" in scenarios:
            result["keywordPack"] = self._normalize_string_list(full_copy.get("keywordPack"), [], min_items=0)
        return result

    def _pick_language(self, value: Any, output_language: str) -> Any:
        if not isinstance(value, dict):
            return value
        if output_language == "bilingual":
            return {"en-US": value.get("en-US"), "zh-CN": value.get("zh-CN")}
        return value.get(output_language) or value.get("en-US") or value.get("zh-CN")

    def _normalize_positioning(self, value: Any, *, fallback: dict[str, Any]) -> dict[str, Any]:
        raw = value if isinstance(value, dict) else {}
        return {
            "coreAngle": _english_text_or_empty(raw.get("coreAngle")) or _english_text_or_empty(fallback.get("coreAngle")) or "POD ecommerce content angle.",
            "targetCustomers": self._normalize_english_string_list(raw.get("targetCustomers"), fallback.get("targetCustomers"), min_items=2),
            "purchaseOccasions": self._normalize_english_string_list(raw.get("purchaseOccasions"), fallback.get("purchaseOccasions"), min_items=2),
            "sellingPoints": self._normalize_english_string_list(raw.get("sellingPoints"), fallback.get("sellingPoints"), min_items=3),
            "factBoundaries": self._normalize_english_string_list(raw.get("factBoundaries"), fallback.get("factBoundaries"), min_items=2),
        }

    def _normalize_bilingual_text(self, value: Any, fallback: Any) -> dict[str, str]:
        raw = value if isinstance(value, dict) else {}
        fallback_map = fallback if isinstance(fallback, dict) else {}
        if isinstance(fallback, str):
            fallback_map = {"en-US": fallback, "zh-CN": fallback}
        en = _english_text_or_empty(raw.get("en-US")) or _english_text_or_empty(fallback_map.get("en-US")) or "POD ecommerce listing draft"
        zh = _clean_text(raw.get("zh-CN")) or _clean_text(fallback_map.get("zh-CN")) or en
        return {"en-US": en, "zh-CN": zh}

    def _normalize_bilingual_list(self, value: Any, fallback: Any, *, min_items: int) -> dict[str, list[str]]:
        fallback_map = fallback if isinstance(fallback, dict) else {}
        if isinstance(value, list):
            en_source: list[Any] = []
            zh_source: list[Any] = []
            for item in value:
                if isinstance(item, dict):
                    en_source.append(item.get("en-US") or item.get("en") or item.get("english"))
                    zh_source.append(item.get("zh-CN") or item.get("zh") or item.get("chinese"))
                else:
                    en_source.append(item)
                    zh_source.append(item)
            en_value: Any = en_source
            zh_value: Any = zh_source
        else:
            raw = value if isinstance(value, dict) else {}
            en_value = raw.get("en-US") or raw.get("en") or raw.get("english")
            zh_value = raw.get("zh-CN") or raw.get("zh") or raw.get("chinese")
        en = self._normalize_english_string_list(
            en_value,
            fallback_map.get("en-US") if isinstance(fallback_map, dict) else fallback,
            min_items=min_items,
        )
        zh = self._normalize_string_list(
            zh_value,
            fallback_map.get("zh-CN") if isinstance(fallback_map, dict) else fallback,
            min_items=min_items,
        )
        return {"en-US": en[:8], "zh-CN": zh[:8]}

    def _normalize_english_string_list(self, value: Any, fallback: Any = None, *, min_items: int = 1) -> list[str]:
        items: list[str] = []
        for item in _normalize_list(value):
            cleaned = _english_text_or_empty(item)
            if cleaned and cleaned not in items:
                items.append(cleaned)
        if len(items) < min_items:
            for item in _normalize_list(fallback):
                cleaned = _english_text_or_empty(item)
                if cleaned and cleaned not in items:
                    items.append(cleaned)
        while len(items) < min_items:
            items.append("Review and refine this item before publishing.")
        return items[:20]

    def _normalize_string_list(self, value: Any, fallback: Any = None, *, min_items: int = 1) -> list[str]:
        items = _normalize_list(value)
        if len(items) < min_items:
            items.extend(item for item in _normalize_list(fallback) if item not in items)
        while len(items) < min_items:
            items.append("Review and refine this item before publishing.")
        return items[:20]

    def _normalize_image_briefs(self, value: Any, fallback: Any) -> list[dict[str, Any]]:
        raw_items = value if isinstance(value, list) else []
        fallback_items = fallback if isinstance(fallback, list) else []
        items: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_items[:6]):
            if not isinstance(raw, dict):
                continue
            items.append(
                {
                    "id": _clean_text(raw.get("id")) or f"image-brief-{index + 1}",
                    "label": _clean_text(raw.get("label")) or "配图建议",
                    "usage": _clean_text(raw.get("usage")) or "Ecommerce visual asset",
                    "linkedCopy": self._normalize_string_list(raw.get("linkedCopy"), ["listingTitle"], min_items=1)[:6],
                    "prompt": _clean_text(raw.get("prompt")) or "Create a clean ecommerce product visual.",
                    "riskNotes": self._normalize_string_list(raw.get("riskNotes"), ["Keep product facts consistent."], min_items=1)[:5],
                }
            )
        if len(items) < 3:
            items.extend(item for item in fallback_items if isinstance(item, dict))
        return items[:6]

    def _normalize_channel_usage(self, value: Any, fallback: Any) -> list[dict[str, Any]]:
        raw_items = value if isinstance(value, list) else []
        fallback_items = fallback if isinstance(fallback, list) else []
        items: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_items[:6]):
            if not isinstance(raw, dict):
                continue
            items.append(
                {
                    "channel": _clean_text(raw.get("channel")) or f"Channel {index + 1}",
                    "howToUse": _clean_text(raw.get("howToUse")) or "Use the generated copy and visual together.",
                    "assets": self._normalize_string_list(raw.get("assets"), ["listingTitle"], min_items=1)[:8],
                }
            )
        if len(items) < 2:
            items.extend(item for item in fallback_items if isinstance(item, dict))
        return items[:6]

    def _extract_openai_output_text(self, data: dict[str, Any]) -> str:
        direct = data.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        for item in data.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text = content.get("text") or content.get("output_text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        raise RuntimeError("PRODUCT_COPY_MODEL_EMPTY_RESPONSE")

    def _parse_model_json_text(self, text: str) -> dict[str, Any]:
        cleaned = _clean_text(text)
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start < 0 or end <= start:
                raise
            parsed = json.loads(cleaned[start : end + 1])
        if not isinstance(parsed, dict):
            raise RuntimeError("PRODUCT_COPY_MODEL_JSON_NOT_OBJECT")
        return parsed

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
        material_en = _english_text_or_empty(material)
        process_en = _english_text_or_empty(process)
        category_en = _english_text_or_empty(category)
        source_keywords = [_english_text_or_empty(item) for item in _normalize_list(facts.get("keywords"))]
        keywords = _join_keywords(
            source_keywords,
            [name_en, category_en, material_en, "custom design", "POD"],
        )
        selling_base_en = [
            f"Made for everyday styling in {category_en}" if category_en else "Made for everyday styling",
            _compact_sentence(["Soft, comfortable feel", material_en]) if material_en else "Designed for comfort and easy pairing",
            _compact_sentence(["Print-on-demand friendly", process_en]) if process_en else "Clean visual presentation for POD listings",
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
                f"{'Key material: ' + material_en + '. ' if material_en else ''}"
                f"{'Production process: ' + process_en + '. ' if process_en else ''}"
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
                    f"A gift-ready POD pick for {category_en}." if category_en else "A gift-ready POD pick with a clean custom design.",
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

    def _build_resolved_product_facts(
        self,
        *,
        product_card: dict[str, Any],
        content_package: dict[str, Any],
        copy_package: dict[str, Any],
        output_language: str,
    ) -> dict[str, Any]:
        source_facts = {**product_card.get("inferredFacts", {}), **product_card.get("sourceFacts", {})}
        assessment = content_package.get("imageFactAssessment") if isinstance(content_package, dict) else {}
        assessment = assessment if isinstance(assessment, dict) else {}
        field_conflicts = self._normalize_string_list(assessment.get("fieldConflicts"), [], min_items=0)
        missing_inferences = self._normalize_string_list(assessment.get("missingFieldInferences"), [], min_items=0)
        visual_features = self._normalize_string_list(assessment.get("observedVisualFeatures"), [], min_items=0)
        has_conflicts = bool(field_conflicts)

        copy = copy_package if isinstance(copy_package, dict) else {}
        listing_title = _clean_text(copy.get("listingTitle"))
        if isinstance(content_package.get("copyPackage"), dict):
            listing_title = listing_title or _clean_text(
                self._pick_language(content_package["copyPackage"].get("listingTitle"), output_language)
            )
        keyword_pack = self._normalize_string_list(copy.get("keywordPack"), [], min_items=0)
        if not keyword_pack and isinstance(content_package.get("copyPackage"), dict):
            keyword_pack = self._normalize_string_list(content_package["copyPackage"].get("keywordPack"), [], min_items=0)

        observed_type = _clean_text(assessment.get("observedProductType"))
        generic_observed = {
            "image analysis unavailable in template fallback.",
            "needs manual review.",
            "product image conflicts with exported fields; visible product facts are recorded in fieldconflicts.",
        }
        observed_is_generic = observed_type.lower() in generic_observed or not observed_type

        resolved = dict(source_facts)
        source = "exported_fields"
        if has_conflicts:
            source = "product_image_primary"
            resolved = {
                key: value
                for key, value in source_facts.items()
                if key in {"productImageUrl", "designImageUrl"}
            }
            if listing_title:
                resolved["productNameEn"] = listing_title
                resolved["templateName"] = listing_title
            elif observed_type and not observed_is_generic:
                resolved["productNameEn"] = observed_type
                resolved["templateName"] = observed_type
            resolved["fieldConflictPolicy"] = "exclude_conflicting_exported_fields"
            if keyword_pack:
                resolved["keywords"] = keyword_pack
            if visual_features:
                resolved["visualFeatures"] = visual_features
            if missing_inferences:
                resolved["imageInferredFacts"] = missing_inferences
        else:
            if keyword_pack and not resolved.get("keywords"):
                resolved["keywords"] = keyword_pack
            if observed_type and not observed_is_generic:
                resolved["observedProductType"] = observed_type
            if visual_features:
                resolved["visualFeatures"] = visual_features

        resolved_name = _english_product_name(resolved)
        return {
            "source": source,
            "hasFieldConflicts": has_conflicts,
            "summary": resolved_name,
            "facts": resolved,
            "fieldConflicts": field_conflicts,
            "missingFieldInferences": missing_inferences,
            "observedVisualFeatures": visual_features,
            "copyDecision": _clean_text(assessment.get("copyDecision")),
            "confidence": _clean_text(assessment.get("confidence")) or ("low" if has_conflicts else "medium"),
            "rejectedSourceFields": list(product_card.get("sourceMap", {}).keys()) if has_conflicts else [],
        }

    def _build_visual_asset_plan(
        self,
        *,
        product_card: dict[str, Any],
        resolved_product_facts: dict[str, Any] | None = None,
        content_package: dict[str, Any] | None = None,
        visual_mode: str,
        output_language: str,
        product_image_url: Any,
    ) -> dict[str, Any]:
        facts = (
            _as_record(resolved_product_facts.get("facts")) if isinstance(resolved_product_facts, dict) else {}
        ) or {**product_card.get("inferredFacts", {}), **product_card.get("sourceFacts", {})}
        name = _english_product_name(facts) if output_language != "zh-CN" else _zh_product_name(facts)
        has_image = bool(_clean_text(product_image_url))
        model_briefs = []
        if isinstance(content_package, dict) and isinstance(content_package.get("imageBriefs"), list):
            model_briefs = content_package.get("imageBriefs") or []
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
        scene_by_id = {scene["id"]: scene for scene in scenes}
        for brief in model_briefs:
            if not isinstance(brief, dict):
                continue
            brief_id = _clean_text(brief.get("id"))
            if brief_id in scene_by_id:
                scene_by_id[brief_id]["modelBrief"] = brief
                scene_by_id[brief_id]["recommendation"] = _clean_text(brief.get("usage")) or scene_by_id[brief_id]["recommendation"]
                scene_by_id[brief_id]["prompt"] = _clean_text(brief.get("prompt")) or None
        return {
            "mode": visual_mode,
            "hasProductImage": has_image,
            "primaryAssetRole": "product_image" if has_image else "missing_product_image",
            "recommendedScenes": scenes if visual_mode != "none" else [],
            "modelImageBriefs": model_briefs if visual_mode != "none" else [],
            "generatedAssets": [],
            "generationPolicy": {
                "requiresExplicitAction": True,
                "defaultGenerateImages": visual_mode == "generate",
                "candidateRoute": "business.product_design_or_gpt_image2",
                "ossPersistenceRequired": True,
                "factSource": resolved_product_facts.get("source") if isinstance(resolved_product_facts, dict) else "exported_fields",
            },
            "warnings": [] if has_image else ["Missing product image limits visual and video generation quality."],
        }

    def _build_video_plan(
        self,
        *,
        product_card: dict[str, Any],
        resolved_product_facts: dict[str, Any] | None = None,
        product_image_url: Any,
        scenario: str,
        duration_seconds: Any,
        target_duration_seconds: Any,
        aspect_ratio: Any,
        output_language: str,
        market_region: str,
        executor_id: Any,
    ) -> dict[str, Any]:
        facts = (
            _as_record(resolved_product_facts.get("facts")) if isinstance(resolved_product_facts, dict) else {}
        ) or {**product_card.get("inferredFacts", {}), **product_card.get("sourceFacts", {})}
        name = _english_product_name(facts)
        material = _clean_text(facts.get("material") or facts.get("composition"))
        provider = self._resolve_video_provider(_clean_text(executor_id) or DEFAULT_KIE_VIDEO_EXECUTOR_ID)
        profile = self._video_profile_for_provider(provider)
        model = _clean_text(profile.get("model")) or (DEFAULT_VIDU_VIDEO_MODEL if provider == "vidu" else "veo3_fast")
        target_duration = self._normalize_target_duration_seconds(target_duration_seconds or duration_seconds, profile)
        segment_durations = self._plan_video_segment_durations(target_duration, profile)
        duration = segment_durations[0]
        segment_count = len(segment_durations)
        total_generated_seconds = sum(segment_durations)
        requires_composition = segment_count > 1
        ratio = _clean_text(aspect_ratio) or "16:9"
        if provider == "vidu":
            aspect_policy = {
                "mode": "input_image_ratio",
                "requestedAspectRatio": ratio,
                "executionAspectRatio": "input_image_ratio",
                "requiresFirstFrameNormalization": True,
                "reason": "Vidu img2video follows the submitted product/first-frame image ratio; fixed 16:9 or 9:16 output requires generating or padding a matching first frame before execution.",
            }
        else:
            aspect_policy = {
                "mode": "provider_parameter",
                "requestedAspectRatio": ratio,
                "executionAspectRatio": ratio,
                "requiresFirstFrameNormalization": False,
                "reason": "This provider accepts aspect ratio as an execution parameter.",
            }
        prompt_parts = [
            f"Create a {target_duration}-second POD product showcase video for {name}.",
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
        consumed_seconds = 0
        for index, segment_duration in enumerate(segment_durations, start=1):
            keep_seconds = min(segment_duration, max(1, target_duration - consumed_seconds))
            consumed_seconds += keep_seconds
            role = segment_roles[index - 1]
            segment_prompt = " ".join(
                [
                    *prompt_parts,
                    f"Generate this segment as {segment_duration} seconds.",
                    f"Segment {index} of {segment_count}: {role['direction']}.",
                    "Keep visual continuity with the previous segment when provided.",
                ]
            )
            storyboard.append(
                {
                    "shot": index,
                    "durationSeconds": segment_duration,
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
                    "sourceDurationSeconds": segment_duration,
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
                "reason": "Image-to-video generation needs a factual visual anchor.",
            },
            {
                "asset": "multi_angle_images",
                "required": requires_composition,
                "available": False,
                "reason": "Recommended for long videos to reduce repeated angles and improve continuity.",
            },
            {
                "asset": "first_last_frames",
                "required": False,
                "available": False,
                "reason": "Optional controlled-frame mode; generate and confirm opening/ending frames before video execution once enabled.",
            },
        ]
        if provider == "vidu":
            asset_needs.append(
                {
                    "asset": "normalized_first_frame",
                    "required": False,
                    "available": False,
                    "reason": "Required when the final video must strictly match a target aspect ratio; Vidu single-reference generation otherwise follows the uploaded image ratio.",
                }
            )
        return {
            "scenario": scenario,
            "provider": provider,
            "model": model,
            "modelProfile": {
                "displayName": _clean_text(profile.get("displayName")) or model,
                "segmentDurationOptions": profile.get("segmentDurationOptions") or [duration],
                "maxTargetSeconds": profile.get("maxTargetSeconds") or MAX_TARGET_VIDEO_SECONDS,
                "executableModes": [
                    item for item in profile.get("modes", []) if isinstance(item, dict) and item.get("executable")
                ],
                "plannedModes": [
                    item for item in profile.get("modes", []) if isinstance(item, dict) and not item.get("executable")
                ],
            },
            "generationMode": "single_reference",
            "targetDurationSeconds": target_duration,
            "durationSeconds": duration,
            "singleSegmentSeconds": duration,
            "segmentDurationOptions": profile.get("segmentDurationOptions") or [duration],
            "segmentCount": segment_count,
            "totalGeneratedSeconds": total_generated_seconds,
            "requiresComposition": requires_composition,
            "aspectRatio": ratio,
            "aspectPolicy": aspect_policy,
            "storyboard": storyboard,
            "assetNeeds": asset_needs,
            "videoPrompt": " ".join(prompt_parts),
            "compositionPlan": {
                "status": "planned_ready_for_compose_endpoint" if requires_composition else "not_required",
                "composeEngine": "ffmpeg",
                "executionReady": True,
                "targetDurationSeconds": target_duration,
                "singleSegmentSeconds": duration,
                "segmentDurations": segment_durations,
                "segmentCount": segment_count,
                "totalGeneratedSeconds": total_generated_seconds,
                "trimPlan": trim_plan,
                "transition": {
                    "type": "cut" if requires_composition else "none",
                    "durationSeconds": 0,
                },
                "costActionPreview": [
                    self._video_cost_action(provider=provider, model=model) for _ in range(segment_count)
                ]
                + (["ffmpeg.compose"] if requires_composition else []),
                "plannerRole": "llm_storyboard_planner",
                "nextEndpoint": "/api/business/product-commercialization/video-compose" if requires_composition else None,
                "guardrails": [
                    "Backend validates target duration and segment count before execution.",
                    "Each ability call must persist returned video assets to PODI OSS before composition.",
                    "Provider-specific temporary URLs must not be exposed as the final business result.",
                ],
            },
            "languagePolicy": {
                "outputLanguage": output_language,
                "spokenAudio": "disabled",
                "embeddedText": "disabled",
            },
            "factSource": {
                "source": resolved_product_facts.get("source") if isinstance(resolved_product_facts, dict) else "exported_fields",
                "hasFieldConflicts": bool(resolved_product_facts.get("hasFieldConflicts")) if isinstance(resolved_product_facts, dict) else False,
                "summary": resolved_product_facts.get("summary") if isinstance(resolved_product_facts, dict) else None,
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
        content_package: dict[str, Any],
        copy_generation: dict[str, Any],
        visual_asset_plan: dict[str, Any],
        video_plan: dict[str, Any],
    ) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        image_fact_assessment = (
            content_package.get("imageFactAssessment") if isinstance(content_package.get("imageFactAssessment"), dict) else {}
        )
        field_conflicts = self._normalize_string_list(image_fact_assessment.get("fieldConflicts"), [], min_items=0)
        if field_conflicts:
            issues.append(
                {
                    "level": "warning",
                    "code": "PRODUCT_IMAGE_FIELD_CONFLICT",
                    "message": "Product image and exported JSON may describe different facts; copy should follow visible product facts and needs manual review.",
                }
            )
        missing_inferences = self._normalize_string_list(image_fact_assessment.get("missingFieldInferences"), [], min_items=0)
        if missing_inferences:
            issues.append(
                {
                    "level": "info",
                    "code": "PRODUCT_FACTS_INFERRED_FROM_IMAGE",
                    "message": "Some missing fields were inferred from the product image; verify them before publishing.",
                }
            )
        fact_guard = copy_generation.get("factGuard") if isinstance(copy_generation.get("factGuard"), dict) else {}
        if fact_guard and not fact_guard.get("passed", True):
            issues.append(
                {
                    "level": "warning",
                    "code": "PRODUCT_COPY_FACT_GUARD_FALLBACK",
                    "message": "LLM/VL output did not keep enough product fact anchors, so the system used field-anchored fallback copy.",
                }
            )
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
                "After the copy package is accepted, optionally continue in the product video ability.",
            ],
            "videoReady": all(item.get("available") or not item.get("required") for item in video_plan.get("assetNeeds") or []),
        }


product_commercialization_service = ProductCommercializationService()
