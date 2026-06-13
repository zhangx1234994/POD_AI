import importlib.util
import json
from pathlib import Path
import sys
import time
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.core.db import get_session
from app.main import app
from app.models.integration import BusinessRun, BusinessRunStep
from app.routers.business import _business_http_exception_detail
from app.schemas.abilities import AbilityInvokeResponse, AbilityOutputAsset
from app.schemas.business import Product3DRenderVideoRequest, ProductCommercializationRequest
from app.services.business_runs import BusinessRunService
from app.services import product_3d_render_video as product_3d_render_video_module
from app.services.product_3d_render_video import Product3DRenderVideoService
from app.services.product_commercialization import ProductCommercializationService, _build_visual_prompt


client = TestClient(app)


def _load_product_commercialization_patrol_module():
    module_name = "podi_product_commercialization_patrol_test"
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "patrol_product_commercialization.py"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _confirmed_video_keyframes(count: int = 1) -> list[dict[str, object]]:
    frames: list[dict[str, object]] = []
    for shot in range(1, count + 1):
        frames.extend(
            [
                {
                    "role": "first_frame",
                    "shot": str(shot),
                    "segmentIndex": shot,
                    "imageUrl": f"https://podi.oss-cn-hangzhou.aliyuncs.com/confirmed-shot-{shot}-first.png",
                    "confirmed": True,
                },
                {
                    "role": "last_frame",
                    "shot": str(shot),
                    "segmentIndex": shot,
                    "imageUrl": f"https://podi.oss-cn-hangzhou.aliyuncs.com/confirmed-shot-{shot}-last.png",
                    "confirmed": True,
                },
            ]
        )
    return frames


@pytest.fixture(autouse=True)
def disable_external_copy_model(monkeypatch) -> None:
    def fake_generate_model_content_package(*args, **kwargs):
        raise RuntimeError("COPY_MODEL_DISABLED_IN_TEST")

    monkeypatch.setattr(
        ProductCommercializationService,
        "_generate_model_content_package",
        fake_generate_model_content_package,
    )


def test_product_commercialization_openai_planner_can_use_key_pool(monkeypatch) -> None:
    service = ProductCommercializationService()
    session_marker = object()

    class DummySessionContext:
        def __enter__(self):
            return session_marker

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_pick_provider_api_key(session, *, provider: str, exclude_ids=None):
        assert session is session_marker
        if provider != "openai":
            return None
        return SimpleNamespace(
            id="openai-key-1",
            key="sk-test-key",
            extra_metadata={"baseUrl": "https://openai-compatible.example.com/"},
        )

    monkeypatch.setattr("app.services.product_commercialization.get_session", lambda: DummySessionContext())
    monkeypatch.setattr("app.services.product_commercialization.pick_provider_api_key", fake_pick_provider_api_key)

    credentials = service._resolve_openai_planner_credentials(
        SimpleNamespace(
            business_agent_openai_api_key=None,
            business_agent_openai_base_url="https://api.openai.com",
        )
    )

    assert credentials == {
        "apiKey": "sk-test-key",
        "baseUrl": "https://openai-compatible.example.com",
        "source": "api_key_pool:openai:openai-key-1",
    }


def test_product_commercialization_volcengine_copy_uses_ability_router(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured: dict[str, object] = {}

    class FakeAbilityInvocationService:
        def invoke(self, *, ability_id, payload, user, source):
            captured["ability_id"] = ability_id
            captured["payload"] = payload
            captured["user"] = user
            captured["source"] = source
            return SimpleNamespace(
                status="succeeded",
                texts=['{"commercePositioning":{},"copyPackage":{},"imageFactAssessment":{}}'],
                metadata={"executorId": "executor_vendor_api"},
            )

    monkeypatch.setattr(
        "app.services.product_commercialization.ability_invocation_service",
        FakeAbilityInvocationService(),
    )

    result = service._call_volcengine_copy_model(
        prompt="describe product",
        image_url="https://example.com/product.png",
        temperature=0.5,
    )

    payload = captured["payload"]
    assert captured["ability_id"] == "volcengine_doubao_seed_2_0_lite"
    assert captured["source"] == "product-commercialization-copy"
    assert payload.inputs["prompt"] == "describe product"
    assert payload.inputs["temperature"] == 0.5
    assert payload.imageUrl == "https://example.com/product.png"
    assert result["text"].startswith('{"commercePositioning"')


def test_product_commercialization_preview_builds_english_copy_and_visual_plan() -> None:
    service = ProductCommercializationService()

    result = service.preview(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/socks.png",
            productFields={
                "模板名称": "女款长袜（3D打印）",
                "英文名称": "Women's knitted woolen socks",
                "产品材质": "包纱、涤纶、尼龙、橡筋",
                "生产工艺": "3D印花",
                "二级分类": "穿搭配件",
            },
            outputLanguage="en-US",
            marketRegion="US",
            visualSupportMode="recommendation",
        ),
        user_id="tester",
    )

    assert result["businessKey"] == "product_commercialization"
    assert result["outputLanguage"] == "en-US"
    assert result["productCard"]["sourceFacts"]["productNameEn"] == "Women's knitted woolen socks"
    assert result["copyPackage"]["listingTitle"].startswith("Women's knitted woolen socks")
    assert result["copyGeneration"]["method"] == "template_fallback"
    assert result["execution"]["copyGenerated"] is False
    assert len(result["copyPackage"]["bulletPoints"]) == 5
    assert result["visualAssetPlan"]["mode"] == "recommendation"
    assert result["visualAssetPlan"]["hasProductImage"] is True
    assert result["visualAssetPlan"]["generationPolicy"]["requiresExplicitAction"] is True
    assert result["videoPlan"]["model"] == "veo3_fast"
    assert result["execution"]["costActions"] == []


def test_product_commercialization_english_fallback_translates_common_chinese_facts() -> None:
    service = ProductCommercializationService()

    result = service.preview(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/socks.png",
            productFields={
                "英文名称": "Women's knitted woolen socks",
                "产品材质": "包纱、涤纶、尼龙、橡筋",
                "具体成分": "65%涤纶，15%氨纶，20%尼龙",
                "生产工艺": "3D印花",
                "二级分类": "穿搭配件",
            },
            outputLanguage="en-US",
            marketRegion="US",
        ),
        user_id="tester",
    )

    rendered = json.dumps(result["copyPackage"], ensure_ascii=False)
    assert "穿搭配件" not in rendered
    assert "包纱" not in rendered
    assert "涤纶" not in rendered
    assert not _contains_cjk(rendered)
    assert "fashion accessories" in rendered
    assert "covered yarn" in rendered
    assert "polyester" in rendered


def test_product_commercialization_preview_uses_model_content_package(monkeypatch) -> None:
    service = ProductCommercializationService()

    def fake_generate_model_content_package(*args, **kwargs):
        return (
            {
                "commercePositioning": {
                    "coreAngle": "Gift-ready patterned socks for overseas ecommerce buyers.",
                    "targetCustomers": ["gift shoppers", "daily outfit buyers"],
                    "purchaseOccasions": ["birthday gifting", "seasonal collection"],
                    "sellingPoints": ["original pattern", "soft material", "POD-ready listing"],
                    "factBoundaries": ["Do not claim certification", "Do not invent shipping speed"],
                },
                "copyPackage": {
                    "listingTitle": {
                        "en-US": "Gift-Ready Patterned Socks for Everyday Outfits",
                        "zh-CN": "适合礼品场景的图案长袜",
                    },
                    "bulletPoints": {
                        "en-US": [
                            "Soft everyday styling",
                            "Pattern-forward gift appeal",
                            "POD-ready product presentation",
                            "Easy to pair with casual outfits",
                            "Designed for seasonal store updates",
                        ],
                        "zh-CN": ["日常穿搭", "礼品属性", "适合 POD", "易搭配", "适合上新"],
                    },
                    "detailDescription": {
                        "en-US": "A natural ecommerce detail-page description written by the model.",
                        "zh-CN": "由模型生成的自然详情页文案。",
                    },
                    "adShortCopy": {
                        "en-US": ["A fresh patterned gift for everyday outfits.", "Bring a seasonal accent to your store.", "Soft style, easy gifting."],
                        "zh-CN": ["适合日常穿搭的礼品。", "为店铺带来季节氛围。", "柔和风格，适合送礼。"],
                    },
                    "keywordPack": {
                        "coreKeywords": ["patterned socks", "gift socks", "POD socks"],
                        "sceneKeywords": ["custom socks", "seasonal socks", "women socks"],
                    },
                    "styleGuardrails": ["Avoid unsupported certification claims.", "Avoid brand words."],
                    "sourcePrompt": None,
                },
                "imageBriefs": [
                    {
                        "id": "listing-main",
                        "label": "上架主图",
                        "usage": "用于商品主图",
                        "linkedCopy": ["listingTitle"],
                        "prompt": "Create a clean ecommerce main image for the socks.",
                        "riskNotes": ["No embedded text."],
                    },
                    {
                        "id": "detail-closeup",
                        "label": "细节图",
                        "usage": "用于详情页材质说明",
                        "linkedCopy": ["detailDescription"],
                        "prompt": "Create a detail close-up.",
                        "riskNotes": ["Do not invent components."],
                    },
                    {
                        "id": "social-ad-cover",
                        "label": "广告封面",
                        "usage": "用于社媒广告",
                        "linkedCopy": ["adShortCopy"],
                        "prompt": "Create a social ad cover.",
                        "riskNotes": ["No logo."],
                    },
                ],
                "channelUsageGuide": [
                    {
                        "channel": "Amazon",
                        "howToUse": "Use title, bullets and listing-main visual together.",
                        "assets": ["listingTitle", "bulletPoints", "listing-main"],
                    },
                    {
                        "channel": "Social ad",
                        "howToUse": "Use ad copy with the social cover.",
                        "assets": ["adShortCopy", "social-ad-cover"],
                    },
                ],
                "styleGuardrails": ["Avoid unsupported certification claims.", "Avoid brand words."],
                "modelNotes": ["Generated by test model fixture."],
            },
            {
                "method": "volcengine_chat",
                "provider": "volcengine",
                "model": "doubao-seed-1-6",
                "fallback": False,
                "evidence": "test model evidence",
            },
        )

    monkeypatch.setattr(
        ProductCommercializationService,
        "_generate_model_content_package",
        fake_generate_model_content_package,
    )

    result = service.preview(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/socks.png",
            productFields={"英文名称": "Women's knitted woolen socks", "产品材质": "polyester", "二级分类": "socks"},
            outputLanguage="en-US",
            commercePlatform="amazon_marketplace",
            copyTone="warm_gift",
            targetAudience="gift buyers",
            sellingAngle="giftable_moment",
            forbiddenClaims=["certification", "shipping speed"],
        )
    )

    assert result["copyGeneration"]["method"] == "volcengine_chat"
    assert result["execution"]["copyGenerated"] is True
    assert result["copyPackage"]["listingTitle"] == "Gift-Ready Patterned Socks for Everyday Outfits"
    assert result["copyPackage"]["keywordPack"] == [
        "patterned socks",
        "gift socks",
        "POD socks",
        "custom socks",
        "seasonal socks",
        "women socks",
    ]
    assert result["contentPackage"]["commercePositioning"]["coreAngle"].startswith("Gift-ready")
    assert result["visualAssetPlan"]["modelImageBriefs"][0]["id"] == "listing-main"


def test_product_commercialization_fact_guard_falls_back_when_model_changes_product_type(monkeypatch) -> None:
    service = ProductCommercializationService()

    def fake_generate_model_content_package(*args, **kwargs):
        return (
            {
                "commercePositioning": {
                    "coreAngle": "Coastal cowboy tote bag for summer shoppers.",
                    "targetCustomers": ["beach shoppers", "gift buyers"],
                    "purchaseOccasions": ["beach trip", "summer gifting"],
                    "sellingPoints": ["cotton canvas", "foldable tote", "western print"],
                    "factBoundaries": ["Model saw a bag in the image."],
                },
                "copyPackage": {
                    "listingTitle": {
                        "en-US": "Coastal Cowboy Print Cotton Canvas Tote Bag",
                        "zh-CN": "海岸牛仔印花帆布包",
                    },
                    "bulletPoints": {
                        "en-US": ["Reusable tote bag", "Cotton canvas", "Beach-ready", "Foldable", "Giftable"],
                        "zh-CN": ["可复用托特包", "棉帆布", "适合海边", "可折叠", "适合送礼"],
                    },
                    "detailDescription": {
                        "en-US": "A reusable tote bag for shopping and beach trips.",
                        "zh-CN": "适合购物和海边出行的托特包。",
                    },
                    "adShortCopy": {"en-US": ["Carry summer style."], "zh-CN": ["带上海边风格。"]},
                    "keywordPack": ["cotton tote bag", "western tote", "beach bag"],
                    "styleGuardrails": ["Avoid unsupported claims.", "Check marketplace policy."],
                    "sourcePrompt": None,
                },
                "imageBriefs": [],
                "channelUsageGuide": [],
                "styleGuardrails": ["Avoid unsupported claims.", "Check marketplace policy."],
                "modelNotes": ["Image looked like a tote bag."],
            },
            {
                "method": "volcengine_chat",
                "provider": "volcengine",
                "model": "test-vl",
                "fallback": False,
                "evidence": "test model evidence",
            },
        )

    monkeypatch.setattr(
        ProductCommercializationService,
        "_generate_model_content_package",
        fake_generate_model_content_package,
    )

    result = service.preview(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/mismatched-bag.png",
            productFields={
                "英文名称": "Women's knitted woolen socks",
                "产品材质": "包纱、涤纶、尼龙、橡筋",
                "生产工艺": "3D印花",
                "二级分类": "穿搭配件",
            },
            outputLanguage="en-US",
            marketRegion="US",
        )
    )

    assert result["copyGeneration"]["fallback"] is True
    assert result["copyGeneration"]["factGuard"]["passed"] is False
    assert result["execution"]["copyGenerated"] is False
    assert "Women's knitted woolen socks" in result["copyPackage"]["listingTitle"]
    assert "Tote Bag" not in result["copyPackage"]["listingTitle"]
    assert any(issue["code"] == "PRODUCT_COPY_FACT_GUARD_FALLBACK" for issue in result["review"]["issues"])


def test_product_commercialization_template_fallback_requires_image_field_review() -> None:
    service = ProductCommercializationService()

    result = service.preview(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/floral-jacket.png",
            productFields={
                "英文名称": "Women's knitted woolen socks",
                "产品材质": "包纱、涤纶、尼龙、橡筋",
                "生产工艺": "3D印花",
                "二级分类": "穿搭配件",
            },
            outputLanguage="en-US",
            marketRegion="US",
        )
    )

    assert result["copyGeneration"]["fallback"] is True
    assert result["contentPackage"]["imageFactAssessment"]["fieldConflicts"]
    assert result["resolvedProductFacts"]["source"] == "product_image_primary"
    assert result["resolvedProductFacts"]["hasFieldConflicts"] is True
    assert any(issue["code"] == "PRODUCT_IMAGE_FIELD_CONFLICT" for issue in result["review"]["issues"])


def test_product_commercialization_template_fallback_does_not_flag_image_only_payload() -> None:
    service = ProductCommercializationService()

    result = service.preview(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/floral-jacket.png",
            productFields={},
            outputLanguage="en-US",
            marketRegion="US",
        )
    )

    assert result["copyGeneration"]["fallback"] is True
    assert result["contentPackage"]["imageFactAssessment"]["fieldConflicts"] == []
    assert result["resolvedProductFacts"]["hasFieldConflicts"] is False
    assert not any(issue["code"] == "PRODUCT_IMAGE_FIELD_CONFLICT" for issue in result["review"]["issues"])


def test_product_commercialization_keeps_image_primary_copy_when_model_reports_field_conflict(monkeypatch) -> None:
    service = ProductCommercializationService()

    def fake_generate_model_content_package(*args, **kwargs):
        return (
            {
                "commercePositioning": {
                    "coreAngle": "Coastal cowboy tote bag for summer shoppers.",
                    "targetCustomers": ["beach shoppers", "gift buyers"],
                    "purchaseOccasions": ["beach trip", "summer gifting"],
                    "sellingPoints": ["cotton canvas", "foldable tote", "western print"],
                    "factBoundaries": ["Imported JSON conflicts with the visible product image."],
                },
                "copyPackage": {
                    "listingTitle": {
                        "en-US": "Coastal Cowboy Print Cotton Canvas Tote Bag",
                        "zh-CN": "海岸牛仔印花帆布包",
                    },
                    "bulletPoints": {
                        "en-US": [
                            "Reusable tote bag",
                            "Cotton canvas feel",
                            "Beach-ready western print",
                            "Foldable for daily carry",
                            "Giftable casual style",
                        ],
                        "zh-CN": ["可复用托特包", "棉帆布质感", "适合海边的西部印花", "可折叠便于日常携带", "适合作为休闲礼品"],
                    },
                    "detailDescription": {
                        "en-US": "A reusable tote bag for shopping and beach trips.",
                        "zh-CN": "适合购物和海边出行的托特包。",
                    },
                    "adShortCopy": {"en-US": ["Carry summer style."], "zh-CN": ["带上海边风格。"]},
                    "keywordPack": ["cotton tote bag", "western tote", "beach bag"],
                    "styleGuardrails": ["Avoid unsupported claims.", "Check marketplace policy."],
                    "sourcePrompt": None,
                },
                "imageFactAssessment": {
                    "fieldConflicts": "Exported JSON says women's knitted woolen socks, but the product image shows a cotton tote bag.",
                    "missingFieldInferences": "Production process is not visible; print process is only inferred from the image.",
                    "confidence": "low",
                    "confidenceScore": 0.6,
                },
                "imageBriefs": [],
                "channelUsageGuide": [],
                "styleGuardrails": ["Avoid unsupported claims.", "Check marketplace policy."],
                "modelNotes": ["Image looked like a tote bag; JSON looked like socks."],
            },
            {
                "method": "volcengine_chat",
                "provider": "volcengine",
                "model": "test-vl",
                "fallback": False,
                "evidence": "test model evidence",
            },
        )

    monkeypatch.setattr(
        ProductCommercializationService,
        "_generate_model_content_package",
        fake_generate_model_content_package,
    )

    result = service.preview(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/mismatched-bag.png",
            productFields={
                "英文名称": "Women's knitted woolen socks",
                "产品材质": "包纱、涤纶、尼龙、橡筋",
                "生产工艺": "3D印花",
                "二级分类": "穿搭配件",
            },
            outputLanguage="en-US",
            marketRegion="US",
        )
    )

    assert result["copyGeneration"]["fallback"] is False
    assert result["copyGeneration"]["factGuard"]["conflictOverride"] is True
    assert result["execution"]["copyGenerated"] is True
    assert result["copyPackage"]["listingTitle"] == "Coastal Cowboy Print Cotton Canvas Tote Bag"
    assert "Reusable tote bag" in result["copyPackage"]["bulletPoints"]
    assert result["contentPackage"]["imageFactAssessment"]["fieldConflicts"]
    assert result["contentPackage"]["imageFactAssessment"]["confidence"] == "low"
    assert any(issue["code"] == "PRODUCT_IMAGE_FIELD_CONFLICT" for issue in result["review"]["issues"])


def test_product_commercialization_resolved_facts_drive_video_and_visual_plan_on_conflict(monkeypatch) -> None:
    service = ProductCommercializationService()

    def fake_generate_model_content_package(*args, **kwargs):
        return (
            {
                "commercePositioning": {
                    "coreAngle": "Floral hooded jacket for lifestyle shoppers.",
                    "targetCustomers": ["outerwear buyers", "gift buyers"],
                    "purchaseOccasions": ["daily wear", "seasonal gifting"],
                    "sellingPoints": ["floral print", "hooded jacket", "soft outerwear"],
                    "factBoundaries": ["Exported JSON conflicts with product image."],
                },
                "copyPackage": {
                    "listingTitle": {
                        "en-US": "Floral Hooded Lightweight Jacket",
                        "zh-CN": "花卉连帽轻薄外套",
                    },
                    "bulletPoints": {
                        "en-US": ["Floral hooded jacket", "Lightweight outerwear", "Colorful all-over print", "Casual daily layer", "Giftable style"],
                        "zh-CN": ["花卉连帽外套", "轻薄外套", "满版彩色印花", "日常休闲层搭", "适合礼品场景"],
                    },
                    "detailDescription": {
                        "en-US": "A floral hooded jacket based on the visible product image.",
                        "zh-CN": "基于产品图可见事实生成的花卉连帽外套描述。",
                    },
                    "adShortCopy": {"en-US": ["A colorful floral layer."], "zh-CN": ["彩色花卉层搭外套。"]},
                    "keywordPack": ["floral hooded jacket", "lightweight jacket", "printed outerwear"],
                    "styleGuardrails": ["Avoid unsupported fabric claims.", "Check marketplace policy."],
                    "sourcePrompt": None,
                },
                "imageFactAssessment": {
                    "visualSourcePriority": "product_image_primary",
                    "observedProductType": "floral hooded jacket",
                    "observedVisualFeatures": ["hooded outerwear silhouette", "colorful floral all-over print"],
                    "fieldConflicts": ["Exported JSON says women's knitted woolen socks, but the image shows a floral hooded jacket."],
                    "missingFieldInferences": ["Material composition is not official; infer only visible lightweight fabric."],
                    "copyDecision": "Use the visible product image as the primary fact source.",
                    "confidence": "low",
                },
                "imageBriefs": [],
                "channelUsageGuide": [],
                "styleGuardrails": ["Avoid unsupported fabric claims.", "Check marketplace policy."],
                "modelNotes": ["Image facts override exported sock fields."],
            },
            {
                "method": "volcengine_chat",
                "provider": "volcengine",
                "model": "test-vl",
                "fallback": False,
                "evidence": "test model evidence",
            },
        )

    monkeypatch.setattr(
        ProductCommercializationService,
        "_generate_model_content_package",
        fake_generate_model_content_package,
    )

    result = service.preview(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/floral-jacket.png",
            productFields={
                "英文名称": "Women's knitted woolen socks",
                "产品材质": "wool blend",
                "生产工艺": "3D印花",
                "二级分类": "穿搭配件",
            },
            outputLanguage="en-US",
            marketRegion="US",
            visualSupportMode="generate",
        )
    )

    prompt_surface = json.dumps(
        {
            "videoPrompt": result["videoPlan"]["videoPrompt"],
            "storyboard": result["videoPlan"]["storyboard"],
            "visualPlan": result["visualAssetPlan"],
            "resolved": result["resolvedProductFacts"],
        },
        ensure_ascii=False,
    )
    assert "Floral Hooded Lightweight Jacket" in prompt_surface
    assert "Women's knitted woolen socks" not in prompt_surface
    assert result["resolvedProductFacts"]["source"] == "product_image_primary"
    assert result["videoPlan"]["factSource"]["hasFieldConflicts"] is True


def test_product_commercialization_model_normalization_does_not_leak_template_fallback_boundary() -> None:
    service = ProductCommercializationService()
    payload = ProductCommercializationRequest(
        productImageUrl="https://example.com/socks.png",
        productFields={
            "英文名称": "Women's knitted woolen socks",
            "产品材质": "包纱、涤纶、尼龙、橡筋",
            "生产工艺": "3D印花",
            "二级分类": "穿搭配件",
        },
        outputLanguage="en-US",
        marketRegion="US",
    )
    product_card = service._build_product_card(payload)
    template_package = service._build_template_content_package(
        product_card=product_card,
        market_region="US",
        extra_prompt=None,
    )

    normalized = service._normalize_model_content_package(
        {
            "commercePositioning": {
                "coreAngle": "Gift-ready socks for ecommerce buyers.",
                "targetCustomers": ["gift buyers", "穿搭配件"],
                "purchaseOccasions": ["birthday gifting", "seasonal collection"],
                "sellingPoints": ["soft material", "POD-ready listing", "3D印花"],
            },
            "listingTitle": {"en-US": "Gift Socks", "zh-CN": "礼品袜"},
            "bulletPoints": {
                "en-US": ["Soft 包纱 fabric", "涤纶 blend", "3D印花 design", "Gift ready", "Daily wear"],
                "zh-CN": ["柔软包纱", "涤纶混纺", "3D印花", "适合送礼", "日常穿搭"],
            },
            "detailDescription": {"en-US": "A product description.", "zh-CN": "商品描述。"},
            "adShortCopy": {"en-US": ["Gift-ready socks", "Soft daily style", "POD friendly"], "zh-CN": ["礼品袜", "日常风格", "适合 POD"]},
            "keywordPack": ["gift socks", "穿搭配件", "3D印花"],
            "imageBriefs": [],
            "channelUsageGuide": [],
            "styleGuardrails": ["Avoid unsupported claims.", "Check marketplace policy."],
            "modelNotes": ["Model generated package."],
        },
        template_package=template_package,
    )

    normalized_text = json.dumps(normalized, ensure_ascii=False)
    english_delivery_surface = {
        "commercePositioning": normalized["commercePositioning"],
        "listingTitle": normalized["copyPackage"]["listingTitle"]["en-US"],
        "bulletPoints": normalized["copyPackage"]["bulletPoints"]["en-US"],
        "detailDescription": normalized["copyPackage"]["detailDescription"]["en-US"],
        "adShortCopy": normalized["copyPackage"]["adShortCopy"]["en-US"],
        "keywordPack": normalized["copyPackage"]["keywordPack"],
    }
    english_text = json.dumps(english_delivery_surface, ensure_ascii=False)
    assert "Template fallback only" not in normalized_text
    assert "穿搭配件" not in english_text
    assert "包纱" not in english_text
    assert "3D印花" not in english_text
    assert not _contains_cjk(english_text)
    assert "fashion accessories" in english_text
    assert "covered yarn" in english_text
    assert "3D print" in english_text


def test_product_commercialization_preview_supports_bilingual_copy_and_missing_fields() -> None:
    service = ProductCommercializationService()

    result = service.preview(
        ProductCommercializationRequest(
            productFields={"productNameEn": "POD tote bag"},
            outputLanguage="bilingual",
            copyScenarios=["ad_short_copy", "keyword_pack"],
            visualSupportMode="none",
        )
    )

    assert set(result["copyPackage"]["adShortCopy"].keys()) == {"en-US", "zh-CN"}
    assert result["visualAssetPlan"]["recommendedScenes"] == []
    assert "productImageUrl" in result["productCard"]["missingFields"]
    assert any(issue["code"] == "PRODUCT_IMAGE_MISSING" for issue in result["review"]["issues"])


def test_product_commercialization_rejects_invalid_language() -> None:
    service = ProductCommercializationService()
    with pytest.raises(HTTPException) as excinfo:
        service.preview(ProductCommercializationRequest(outputLanguage="jp-JP"))
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "PRODUCT_COMMERCIALIZATION_LANGUAGE_INVALID"


def test_product_commercialization_video_requires_product_image() -> None:
    service = ProductCommercializationService()
    with pytest.raises(HTTPException) as excinfo:
        service.generate_video(ProductCommercializationRequest(productFields={"productNameEn": "POD socks"}))
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "PRODUCT_COMMERCIALIZATION_IMAGE_REQUIRED"


def test_product_commercialization_video_retries_single_segment(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured_calls = []

    def fake_run_kie_market_task(**kwargs):
        captured_calls.append(kwargs)
        if len(captured_calls) == 1:
            return {
                "status": "failed",
                "taskId": "veo_single_failed_once",
                "state": "fail",
                "raw": {
                    "response": {
                        "data": {
                            "successFlag": 2,
                            "errorCode": "KIE_TEMPORARY_FAILURE",
                            "errorMessage": "temporary upstream generation failure",
                        }
                    }
                },
            }
        return {
            "status": "succeeded",
            "taskId": "veo_single_succeeded",
            "state": "success",
            "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/product-video.mp4"],
            "storedAssets": [{"ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/product-video.mp4"}],
        }

    monkeypatch.setattr(
        "app.services.product_commercialization.integration_test_service",
        SimpleNamespace(run_kie_market_task=fake_run_kie_market_task),
    )

    result = service.generate_video(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/socks.png",
            productFields={"productNameEn": "Women's knitted woolen socks"},
            confirmedVideoKeyframes=_confirmed_video_keyframes(),
        )
    )

    assert len(captured_calls) == 2
    assert result["status"] == "succeeded"
    assert result["videoResult"]["taskId"] == "veo_single_succeeded"
    assert result["videoResult"]["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/product-video.mp4"]


def test_product_commercialization_video_rejects_unconfirmed_keyframes(monkeypatch) -> None:
    service = ProductCommercializationService()

    def fail_run_kie_market_task(**kwargs):
        raise AssertionError("video provider must not be called before keyframe confirmation")

    monkeypatch.setattr(
        "app.services.product_commercialization.integration_test_service",
        SimpleNamespace(run_kie_market_task=fail_run_kie_market_task),
    )

    with pytest.raises(HTTPException) as excinfo:
        service.generate_video(
            ProductCommercializationRequest(
                productImageUrl="https://example.com/socks.png",
                productFields={"productNameEn": "Women's knitted woolen socks"},
            )
        )

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail["errorCode"] == "PRODUCT_COMMERCIALIZATION_KEYFRAMES_UNCONFIRMED"
    assert excinfo.value.detail["requiredCount"] >= 2
    assert excinfo.value.detail["confirmedCount"] == 0
    assert {item["role"] for item in excinfo.value.detail["missingKeyframes"]} >= {"first_frame", "last_frame"}


def test_product_commercialization_video_rejects_confirmed_keyframes_with_missing_role(monkeypatch) -> None:
    service = ProductCommercializationService()

    def fail_run_kie_market_task(**kwargs):
        raise AssertionError("video provider must not be called when confirmed keyframe roles are incomplete")

    monkeypatch.setattr(
        "app.services.product_commercialization.integration_test_service",
        SimpleNamespace(run_kie_market_task=fail_run_kie_market_task),
    )

    with pytest.raises(HTTPException) as excinfo:
        service.generate_video(
            ProductCommercializationRequest(
                productImageUrl="https://example.com/socks.png",
                productFields={"productNameEn": "Women's knitted woolen socks"},
                confirmedVideoKeyframes=[
                    {
                        "role": "first_frame",
                        "shot": "1",
                        "segmentIndex": 1,
                        "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/confirmed-shot-1-first-a.png",
                        "confirmed": True,
                    },
                    {
                        "role": "first_frame",
                        "shot": "1",
                        "segmentIndex": 1,
                        "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/confirmed-shot-1-first-b.png",
                        "confirmed": True,
                    },
                ],
            )
        )

    assert excinfo.value.status_code == 400
    detail = excinfo.value.detail
    assert detail["errorCode"] == "PRODUCT_COMMERCIALIZATION_KEYFRAMES_UNCONFIRMED"
    assert detail["confirmedCount"] == 2
    assert detail["matchedCount"] == 1
    assert any(item["shot"] == "1" and item["role"] == "last_frame" for item in detail["missingKeyframes"])


def test_product_commercialization_video_keyframes_are_separate_cost_action(monkeypatch) -> None:
    service = ProductCommercializationService()
    generated: list[dict[str, object]] = []

    def fake_generate_video_keyframe_image(**kwargs):
        url = f"https://podi.oss-cn-hangzhou.aliyuncs.com/keyframe-{len(generated) + 1}.png"
        frame = {
            "role": kwargs["role"],
            "status": "succeeded",
            "shot": kwargs["segment_index"],
            "segmentIndex": kwargs["segment_index"],
            "imageUrl": url,
            "ossUrl": url,
            "prompt": kwargs["prompt"],
            "width": 1792,
            "height": 1024,
        }
        generated.append(frame)
        return frame

    monkeypatch.setattr(service, "_generate_video_keyframe_image", fake_generate_video_keyframe_image)

    result = service.generate_video_keyframes(
        ProductCommercializationRequest(
            action="video_keyframes",
            productImageUrl="https://example.com/socks.png",
            productFields={"productNameEn": "Women's knitted woolen socks", "material": "polyester"},
            targetDurationSeconds=15,
        )
    )

    assert result["status"] == "succeeded"
    assert result["videoResult"]["status"] == "keyframes_ready"
    assert result["execution"]["imageGenerated"] is True
    assert result["execution"]["videoGenerated"] is False
    assert result["videoAssetPackage"]["deliveryStatus"] == "keyframes_ready"
    assert result["videoAssetPackage"]["segmentVideos"] == []
    assert len(result["videoAssetPackage"]["keyframes"]) == len(result["videoPlan"]["keyframePlan"])
    assert all(item["imageUrl"].startswith("https://podi.oss-cn-hangzhou.aliyuncs.com/") for item in generated)


def test_product_commercialization_video_keyframes_can_scope_single_shot(monkeypatch) -> None:
    service = ProductCommercializationService()
    generated: list[dict[str, object]] = []

    def fake_generate_video_keyframe_image(**kwargs):
        frame = {
            "role": kwargs["role"],
            "status": "succeeded",
            "shot": kwargs["segment_index"],
            "segmentIndex": kwargs["segment_index"],
            "imageUrl": f"https://podi.oss-cn-hangzhou.aliyuncs.com/keyframe-shot-{kwargs['segment_index']}.png",
            "ossUrl": f"https://podi.oss-cn-hangzhou.aliyuncs.com/keyframe-shot-{kwargs['segment_index']}.png",
            "prompt": kwargs["prompt"],
        }
        generated.append(frame)
        return frame

    monkeypatch.setattr(service, "_generate_video_keyframe_image", fake_generate_video_keyframe_image)

    result = service.generate_video_keyframes(
        ProductCommercializationRequest(
            action="video_keyframes",
            productImageUrl="https://example.com/socks.png",
            productFields={"productNameEn": "Women's knitted woolen socks", "material": "polyester"},
            targetDurationSeconds=15,
            keyframeShotScope="2",
        )
    )

    assert result["status"] == "succeeded"
    assert result["execution"]["keyframeShotScope"] == "2"
    assert generated
    assert {item["segmentIndex"] for item in generated} == {2}
    assert {item["segmentIndex"] for item in result["videoAssetPackage"]["keyframes"]} == {2}


def test_product_commercialization_video_keyframes_reject_unknown_scope(monkeypatch) -> None:
    service = ProductCommercializationService()

    def fake_generate_video_keyframe_image(**kwargs):
        raise AssertionError("unknown scope should fail before image generation")

    monkeypatch.setattr(service, "_generate_video_keyframe_image", fake_generate_video_keyframe_image)

    with pytest.raises(HTTPException) as exc_info:
        service.generate_video_keyframes(
            ProductCommercializationRequest(
                action="video_keyframes",
                productImageUrl="https://example.com/socks.png",
                productFields={"productNameEn": "Women's knitted woolen socks", "material": "polyester"},
                targetDurationSeconds=15,
                keyframeShotScope="99",
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "PRODUCT_COMMERCIALIZATION_KEYFRAME_SCOPE_EMPTY"


def test_product_commercialization_preview_plans_long_video_segments() -> None:
    service = ProductCommercializationService()

    result = service.preview(
        ProductCommercializationRequest(
            action="video_preview",
            productImageUrl="https://example.com/socks.png",
            productFields={"productNameEn": "Women's knitted woolen socks", "material": "polyester"},
            targetDurationSeconds=15,
        )
    )

    video_plan = result["videoPlan"]
    assert video_plan["targetDurationSeconds"] == 15
    assert video_plan["durationSeconds"] == 8
    assert video_plan["segmentDurationOptions"] == [8]
    assert video_plan["segmentCount"] == 2
    assert video_plan["totalGeneratedSeconds"] == 16
    assert video_plan["requiresComposition"] is True
    assert [shot["keepSeconds"] for shot in video_plan["storyboard"]] == [8, 7]
    assert video_plan["planner"]["method"]
    assert video_plan["planner"]["provider"]
    assert video_plan["directorBrief"]["productUnderstanding"]
    assert video_plan["directorBrief"]["commercialGoal"]
    editable_fields = {item["id"]: item for item in video_plan["editablePlanningFields"]}
    assert set(editable_fields) >= {"core_message", "target_audience", "usage_scene", "shot_preference", "avoid"}
    assert editable_fields["core_message"]["editable"] is True
    assert editable_fields["target_audience"]["source"] in {"auto", "manual"}
    assert editable_fields["shot_preference"]["value"]
    assert video_plan["planningFieldContract"]["frontendEditable"] is True
    assert video_plan["planningFieldContract"]["manualChangesRequireReplan"] is True
    assert video_plan["negativePrompt"]
    assert video_plan["vendorExecutionNotes"]
    assert video_plan["riskChecks"]
    for shot in video_plan["storyboard"]:
        assert shot["scene"]
        assert shot["cameraMovement"]
        assert shot["firstFramePrompt"]
        assert shot["lastFramePrompt"]
        assert shot["negativePrompt"]
    assert video_plan["compositionPlan"]["status"] == "planned_ready_for_compose_endpoint"
    assert video_plan["compositionPlan"]["executionReady"] is True
    assert video_plan["compositionPlan"]["costActionPreview"] == [
        "kie.veo3_fast.video",
        "kie.veo3_fast.video",
        "ffmpeg.compose",
    ]
    keyframe_needs = result["videoAssetPackagePlan"]["keyframeNeeds"]
    assert keyframe_needs
    assert keyframe_needs[0]["role"] in {"first_frame", "last_frame"}
    assert keyframe_needs[0]["prompt"]
    shot_packages = result["videoAssetPackagePlan"]["shotPackages"]
    assert len(shot_packages) == video_plan["segmentCount"]
    assert shot_packages[0]["shotNo"] == 1
    assert shot_packages[0]["videoPrompt"]
    assert shot_packages[0]["firstFramePrompt"]
    assert shot_packages[0]["lastFramePrompt"]
    assert shot_packages[0]["confirmationRequired"] is True
    assert shot_packages[0]["keyframeNeeds"]
    assert shot_packages[0]["executionState"] == "needs_keyframes"
    assert result["videoAssetPackagePlan"]["planningFieldSnapshot"]["fields"][0]["id"] == "core_message"


def test_product_commercialization_video_director_uses_volcengine_router_without_env(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "app.services.product_commercialization.get_settings",
        lambda: SimpleNamespace(
            business_agent_planner_enabled=True,
            business_agent_planner_model="gpt-5.5",
            business_agent_openai_api_key=None,
            business_agent_openai_base_url="https://api.openai.com",
            business_agent_planner_timeout_seconds=30,
            volcengine_api_key=None,
        ),
    )
    monkeypatch.setattr(
        ProductCommercializationService,
        "_resolve_openai_planner_credentials",
        lambda self, settings: {},
    )

    def fake_call_volcengine_copy_model(self, **kwargs):
        captured.update(kwargs)
        return {
            "model": "doubao-video-director-test",
            "text": json.dumps(
                {
                    "directorBrief": {
                        "productUnderstanding": "Visible floral mug with ceramic body.",
                        "commercialGoal": "Create a concise marketplace product showcase.",
                        "targetAudience": "US gift buyers.",
                        "visualStyle": "Clean tabletop commercial video.",
                        "continuityRule": "Keep the same mug shape, print and color in every segment.",
                    },
                    "videoPrompt": "Model-planned 15 second ceramic mug showcase with controlled camera movement.",
                    "negativePrompt": "No text, watermark, logo, price tag, deformation, or wrong product category.",
                    "storyboard": [
                        {
                            "shot": 1,
                            "scene": "bright tabletop hero setup",
                            "subject": "Floral ceramic mug",
                            "goal": "show full product silhouette",
                            "cameraMovement": "slow 30 degree orbit from front-left to center",
                            "composition": "full mug visible, centered, clean negative space",
                            "prompt": "Generate an 8 second tabletop hero orbit of the floral ceramic mug.",
                            "firstFramePrompt": "Opening frame: floral ceramic mug centered on a clean tabletop.",
                            "lastFramePrompt": "Ending frame: mug still centered after a slow orbit.",
                            "negativePrompt": "No text, watermark, logo, price tag, deformation.",
                            "transition": "cut",
                            "referenceImageRole": "primary",
                        },
                        {
                            "shot": 2,
                            "scene": "close material detail setup",
                            "subject": "Floral ceramic mug",
                            "goal": "show print and handle detail",
                            "cameraMovement": "gentle push-in toward the printed surface and handle",
                            "composition": "medium close-up with handle and print visible",
                            "prompt": "Generate a 7 second close detail push-in for the floral ceramic mug.",
                            "firstFramePrompt": "Opening detail frame: mug print and handle visible.",
                            "lastFramePrompt": "Ending detail frame: clean close-up of ceramic surface and print.",
                            "negativePrompt": "No text, watermark, logo, price tag, deformation.",
                            "transition": "cut",
                            "referenceImageRole": "primary",
                        },
                    ],
                    "keyframePlan": [
                        {
                            "role": "first_frame",
                            "shot": 1,
                            "required": False,
                            "source": "gpt_image_2_planned",
                            "prompt": "Create a controlled opening tabletop hero frame for the floral mug.",
                            "reason": "Stabilize the first video segment.",
                        }
                    ],
                    "vendorExecutionNotes": [
                        "Use one reference image per generated segment.",
                        "Preserve product identity and avoid extra props unless requested.",
                    ],
                    "riskChecks": [
                        "Check mug shape deformation.",
                        "Check unexpected text or watermark.",
                    ],
                },
                ensure_ascii=False,
            ),
        }

    monkeypatch.setattr(
        ProductCommercializationService,
        "_call_volcengine_copy_model",
        fake_call_volcengine_copy_model,
    )

    result = service.preview(
        ProductCommercializationRequest(
            action="video_preview",
            productImageUrl="https://example.com/mug.png",
            productFields={"productNameEn": "Floral ceramic mug", "material": "ceramic"},
            targetDurationSeconds=15,
            videoPlanningContext={
                "targetAudience": "US gift buyers and coffee commuters",
                "shotPreference": "gentle orbit first, then slow push-in without cropping the mug handle",
                "avoid": "no text, no watermark, keep the mug shape stable",
                "fields": [
                    {
                        "id": "usage_scene",
                        "label": "使用场景",
                        "value": "clean tabletop marketplace scene",
                        "source": "manual",
                    }
                ],
            },
        )
    )

    assert captured["source"] == "product-commercialization-video-planner"
    assert captured["route_source"] == "product_commercialization_video_director"
    assert captured["image_url"] == "https://example.com/mug.png"
    assert "US gift buyers and coffee commuters" in str(captured["prompt"])
    assert "gentle orbit first" in str(captured["prompt"])
    assert "clean tabletop marketplace scene" in str(captured["prompt"])
    assert result["videoPlan"]["planner"]["provider"] == "volcengine"
    assert result["videoPlan"]["planner"]["fallback"] is False
    assert result["videoPlan"]["planner"]["model"] == "doubao-video-director-test"
    assert result["videoPlan"]["videoPrompt"].startswith("Model-planned 15 second")
    assert result["videoPlan"]["storyboard"][0]["cameraMovement"].startswith("slow 30 degree orbit")
    editable_fields = {item["id"]: item for item in result["videoPlan"]["editablePlanningFields"]}
    assert editable_fields["target_audience"]["value"] == "US gift buyers and coffee commuters"
    assert editable_fields["target_audience"]["source"] == "manual"
    assert editable_fields["shot_preference"]["value"].startswith("gentle orbit first")
    assert editable_fields["usage_scene"]["value"] == "clean tabletop marketplace scene"
    assert editable_fields["usage_scene"]["source"] == "manual"
    assert result["videoAssetPackagePlan"]["keyframeNeeds"][0]["source"] == "gpt_image_2_planned"
    assert result["videoAssetPackagePlan"]["shotPackages"][0]["videoPrompt"].startswith("Generate an 8 second")
    assert result["videoAssetPackagePlan"]["shotPackages"][0]["keyframeNeeds"][0]["source"] == "gpt_image_2_planned"
    assert not any(issue["code"] == "PRODUCT_VIDEO_PLANNER_FALLBACK" for issue in result["review"]["issues"])


def test_product_commercialization_video_preview_skips_copy_model(monkeypatch) -> None:
    service = ProductCommercializationService()

    def fail_copy_model(**_: object) -> None:
        raise AssertionError("video preview must not call copy generation")

    monkeypatch.setattr(service, "_generate_model_content_package", fail_copy_model)

    result = service.preview(
        ProductCommercializationRequest(
            action="video_preview",
            productImageUrl="https://example.com/mug.png",
            productFields={"productNameEn": "Ceramic travel mug", "material": "ceramic"},
            targetDurationSeconds=15,
        )
    )

    assert result["copyScenarios"] == []
    assert result["copyGeneration"]["method"] == "skipped_for_video_preview"
    assert result["copyGeneration"]["skipped"] is True
    assert result["execution"]["copyGenerated"] is False
    assert result["videoPlan"]["targetDurationSeconds"] == 15
    assert result["review"]["nextActions"][0].startswith("Verify product image")


def test_product_commercialization_preview_keeps_customer_duration_and_planning_context() -> None:
    service = ProductCommercializationService()

    result = service.preview(
        ProductCommercializationRequest(
            action="video_preview",
            productImageUrl="https://example.com/mug.png",
            productFields={"productNameEn": "Ceramic travel mug", "material": "ceramic"},
            targetDurationSeconds=5,
            extraPrompt="核心信息：展示杯身花纹和杯盖结构。镜头偏好：慢速转圈。",
        )
    )

    video_plan = result["videoPlan"]
    assert video_plan["targetDurationSeconds"] == 5
    assert video_plan["totalGeneratedSeconds"] == 8
    assert video_plan["requiresComposition"] is True
    assert video_plan["storyboard"][0]["keepSeconds"] == 5
    assert "核心信息" in video_plan["videoPrompt"]
    assert "慢速转圈" in video_plan["storyboard"][0]["prompt"]


def test_product_commercialization_preview_uses_vidu_duration_profile() -> None:
    service = ProductCommercializationService()

    result = service.preview(
        ProductCommercializationRequest(
            action="video_preview",
            productImageUrl="https://example.com/blanket.png",
            productFields={"productNameEn": "Floral throw blanket", "material": "soft plush"},
            executorId="executor_vidu_default",
            targetDurationSeconds=13,
        )
    )

    video_plan = result["videoPlan"]
    assert video_plan["provider"] == "vidu"
    assert video_plan["model"] == "viduq3-turbo"
    assert video_plan["modelProfile"]["segmentDurationOptions"] == [3, 5, 8]
    assert video_plan["targetDurationSeconds"] == 13
    assert video_plan["aspectPolicy"]["mode"] == "input_image_ratio"
    assert video_plan["aspectPolicy"]["requestedAspectRatio"] == "16:9"
    assert video_plan["aspectPolicy"]["executionAspectRatio"] == "input_image_ratio"
    assert video_plan["aspectPolicy"]["requiresFirstFrameNormalization"] is True
    assert [shot["durationSeconds"] for shot in video_plan["storyboard"]] == [8, 5]
    assert [shot["keepSeconds"] for shot in video_plan["storyboard"]] == [8, 5]
    assert video_plan["compositionPlan"]["segmentDurations"] == [8, 5]
    normalized_need = next(item for item in video_plan["assetNeeds"] if item["asset"] == "normalized_first_frame")
    assert normalized_need["required"] is True
    assert normalized_need["available"] is False


def test_product_commercialization_preview_accepts_multi_product_images() -> None:
    service = ProductCommercializationService()

    result = service.preview(
        ProductCommercializationRequest(
            action="video_preview",
            productImageUrl="https://example.com/front.png",
            productImages=[
                {"url": "https://example.com/back.png", "role": "back", "label": "背面"},
                {"url": "https://example.com/detail.png", "role": "detail", "label": "材质细节"},
            ],
            productFields={"productNameEn": "Floral ceramic mug", "material": "ceramic"},
            targetDurationSeconds=16,
        )
    )

    image_set = result["videoPlan"]["referenceImageSet"]
    assert result["productCard"]["sourceFacts"]["productImageUrl"] == "https://example.com/front.png"
    assert len(result["productCard"]["sourceFacts"]["productImages"]) == 3
    assert result["videoPlan"]["generationMode"] == "multi_reference_planned"
    assert image_set["primaryImageUrl"] == "https://example.com/front.png"
    assert image_set["count"] == 3
    assert [shot["referenceImage"]["role"] for shot in result["videoPlan"]["storyboard"]] == ["primary", "back"]
    assert next(item for item in result["videoPlan"]["assetNeeds"] if item["asset"] == "multi_angle_images")["available"] is True


def test_product_commercialization_video_uses_primary_image_from_image_set(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured = {}

    def fake_run_kie_market_task(**kwargs):
        captured.update(kwargs)
        return {
            "status": "succeeded",
            "taskId": "veo_from_image_set",
            "state": "success",
            "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/video.mp4"],
            "storedAssets": [{"ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/video.mp4", "type": "video"}],
        }

    monkeypatch.setattr(
        "app.services.product_commercialization.integration_test_service",
        SimpleNamespace(run_kie_market_task=fake_run_kie_market_task),
    )

    result = service.generate_video(
        ProductCommercializationRequest(
            productImages=[
                {"url": "https://example.com/front.png", "role": "front", "label": "正面", "isPrimary": True},
                {"url": "https://example.com/back.png", "role": "back", "label": "背面"},
            ],
            productFields={"productNameEn": "Floral ceramic mug"},
            confirmedVideoKeyframes=_confirmed_video_keyframes(),
        )
    )

    assert captured["input_payload"]["imageUrls"] == [
        "https://podi.oss-cn-hangzhou.aliyuncs.com/confirmed-shot-1-first.png"
    ]
    assert result["videoResult"]["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/video.mp4"]


def test_product_3d_render_video_preview_returns_plan_without_video() -> None:
    service = Product3DRenderVideoService()

    result = service.preview(
        Product3DRenderVideoRequest(
            modelKey="cup_1660",
            textureImageUrl="https://example.com/pattern.png",
            materialSlot="front",
            cameraPreset="hero_turntable",
            cameraDistance="wide",
            scenePreset="desktop_lifestyle",
            motionPath=[{"x": 0.2, "y": 0.72}, {"x": 0.5, "y": 0.5}, {"x": 0.78, "y": 0.42}],
            durationSeconds=6,
        )
    )

    assert result["businessKey"] == "product_3d_render_video"
    assert result["model"]["preferredFile"] == "1660.glb"
    assert result["assetReadiness"]["uvReady"] is True
    assert result["assetReadiness"]["renderWorkerReady"] is True
    assert result["assetReadiness"]["renderWorker"] == "lightweight_scene_renderer_v1"
    assert result["assetReadiness"]["highFidelityWorkerReady"] is False
    assert result["renderPlan"]["executionStatus"] == "preview_only"
    assert result["renderPlan"]["camera"]["key"] == "hero_turntable"
    assert result["renderPlan"]["camera"]["motionTemplate"] == "slow_turntable_hero"
    assert result["renderPlan"]["camera"]["distance"]["key"] == "wide"
    assert result["renderPlan"]["cameraPlan"]["template"] == "hero_turntable"
    assert result["renderPlan"]["cameraPlan"]["productMotion"] == "fixed"
    assert result["renderPlan"]["cameraPlan"]["cameraMotion"] == "path_playback"
    assert result["renderPlan"]["cameraPlan"]["confirmationRequiredBeforeRender"] is True
    assert result["renderPlan"]["cameraPlan"]["constraints"]["productFixed"] is True
    assert result["renderPlan"]["cameraPlan"]["path"]["points"][0] == {"x": 0.2, "y": 0.72}
    assert result["renderPlan"]["camera"]["framing"]["mode"] == "fit_product_safe_bounds"
    assert result["renderPlan"]["camera"]["framing"]["safeMarginRatio"] == 0.07
    assert result["renderPlan"]["framingSafety"]["mode"] == "fit_product_safe_bounds"
    assert result["renderPlan"]["framingSafety"]["motionPathBounds"] == {
        "minX": 0.2,
        "maxX": 0.78,
        "minY": 0.42,
        "maxY": 0.72,
        "spanX": 0.58,
        "spanY": 0.3,
    }
    assert result["renderPlan"]["framingSafety"]["finalDeliveryRecommended"] is True
    assert result["renderPlan"]["camera"]["framing"]["safety"]["fullProductFitRequired"] is True
    assert result["renderPlan"]["camera"]["framing"]["safety"]["appliedMotionScale"]["xFrameRatio"] == 0.22
    assert result["renderPlan"]["scene"]["key"] == "desktop_lifestyle"
    assert result["renderPlan"]["scene"]["placement"]["anchor"] == "front center on tabletop"
    assert result["renderPlan"]["scene"]["assetId"] == "podi.scene.procedural.desktop_lifestyle.v1"
    assert result["renderPlan"]["scene"]["fusion"]["landingZone"] == "front_center_tabletop_zone"
    assert result["renderPlan"]["scene"]["fusion"]["occlusionPolicy"] == (
        "secondary props stay behind the product and cannot cover texture slots"
    )
    assert result["renderPlan"]["scene"]["fusion"]["verification"]["failureIf"] == [
        "product cropped",
        "active texture slot occluded",
        "fake text/logo appears in scene props",
    ]
    assert result["renderPlan"]["scene"]["asset"]["assetType"] == "procedural_scene_model"
    assert result["renderPlan"]["scene"]["asset"]["externalCandidates"][0]["license"] == "CC0"
    assert result["renderPlan"]["scene"]["asset"]["ingestPolicy"]["allowCommercialUseOnly"] is True
    scene_acceptance = result["renderPlan"]["sceneVisualAcceptance"]
    assert scene_acceptance["status"] == "mvp_ready"
    assert scene_acceptance["currentAsset"]["assetId"] == "podi.scene.procedural.desktop_lifestyle.v1"
    assert scene_acceptance["candidateSummary"]["total"] >= 3
    assert scene_acceptance["candidateSummary"]["blockedCount"] >= 1
    assert {item["code"] for item in scene_acceptance["checks"]} >= {
        "CURRENT_SCENE_ASSET_READY",
        "PRODUCT_OCCLUSION_GUARDED",
        "SAFE_FRAMING",
        "HIGH_FIDELITY_IMPORT_SMOKE",
    }
    assert result["renderPlan"]["scene"]["visualAcceptance"]["status"] == "mvp_ready"
    assert result["review"]["sceneVisualAcceptance"]["promotionPolicy"]["currentRendererCanExecute"] is True
    assert result["assetReadiness"]["sceneAssetReady"] is True
    assert result["assetReadiness"]["sceneAssetId"] == "podi.scene.procedural.desktop_lifestyle.v1"
    assert result["assetReadiness"]["sceneVisualAcceptanceStatus"] == "mvp_ready"
    assert result["renderPlan"]["motionPath"]["pointCount"] == 3
    assert result["renderPlan"]["motionPath"]["points"][0] == {"x": 0.2, "y": 0.72}
    assert result["renderPlan"]["motionPath"]["mode"] == "legacy_camera_path_points"
    assert result["execution"]["videoGenerated"] is False


def test_product_3d_render_video_preview_accepts_texture_slots() -> None:
    service = Product3DRenderVideoService()

    result = service.preview(
        Product3DRenderVideoRequest(
            modelKey="cup_1660",
            materialSlot="front",
            textureSlots=[
                {"materialSlot": "front", "imageUrl": "https://example.com/front.png", "label": "杯身正面"},
                {"materialSlot": "bottom", "imageUrl": "https://example.com/bottom.png", "label": "底部"},
            ],
        )
    )

    texture_application = result["renderPlan"]["textureApplication"]
    assert texture_application["mode"] == "slot_texture_mapping"
    assert texture_application["textureSlotCount"] == 2
    assert [item["materialSlot"] for item in texture_application["textureSlots"]] == ["front", "bottom"]
    assert result["assetReadiness"]["textureSlotCount"] == 2


def test_product_3d_render_video_loads_svg_raster_companion(monkeypatch) -> None:
    requested_urls: list[str] = []
    raster = BytesIO()
    Image.new("RGB", (24, 18), "#336699").save(raster, format="PNG")

    class FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, **_: object) -> FakeResponse:
        requested_urls.append(url)
        if url.endswith(".svg?token=sample"):
            return FakeResponse(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>')
        if url.endswith(".png?token=sample"):
            return FakeResponse(raster.getvalue())
        raise AssertionError(f"unexpected texture URL: {url}")

    monkeypatch.setattr(product_3d_render_video_module.httpx, "get", fake_get)

    image = product_3d_render_video_module._load_texture_image("https://example.com/front.svg?token=sample")

    assert image is not None
    assert image.mode == "RGB"
    assert image.size == (24, 18)
    assert requested_urls == [
        "https://example.com/front.svg?token=sample",
        "https://example.com/front.png?token=sample",
    ]


def test_product_3d_render_video_catalog_returns_ui_contract() -> None:
    service = Product3DRenderVideoService()

    result = service.catalog()

    assert result["businessKey"] == "product_3d_render_video"
    assert result["version"] == "product-3d-render-video-catalog-v1"
    assert result["defaults"]["cameraDistance"] == "wide"
    assert result["defaults"]["motionPath"][0] == {"x": 0.22, "y": 0.66}
    assert {item["modelKey"] for item in result["models"]} == {"cup_1660", "backpack_2551"}
    cup = next(item for item in result["models"] if item["modelKey"] == "cup_1660")
    assert cup["recommendedMaterialSlot"] == "front"
    assert "front" in cup["materialSlots"]
    desktop_scene = next(item for item in result["scenePresets"] if item["key"] == "desktop_lifestyle")
    assert desktop_scene["asset"]["assetId"] == "podi.scene.procedural.desktop_lifestyle.v1"
    assert desktop_scene["asset"]["externalCandidates"][0]["license"] == "CC0"
    assert desktop_scene["sceneVisualAcceptance"]["status"] == "mvp_ready"
    assert desktop_scene["sceneVisualAcceptance"]["candidateSummary"]["cc0Count"] >= 3
    assert desktop_scene["sceneVisualAcceptance"]["candidateAssets"][0]["promotionNextAction"].startswith("download asset")
    desktop_elements = {item["elementId"]: item for item in desktop_scene["renderElements"]}
    assert desktop_elements["wood_tabletop"]["type"] == "table_surface"
    assert desktop_elements["rear_book_block"]["occlusion"] == "behind_product_only"
    desktop_candidates = {item["assetId"]: item for item in desktop_scene["asset"]["externalCandidates"]}
    assert desktop_candidates["Wood095"]["url"] == "https://ambientcg.com/a/Wood095"
    assert desktop_candidates["Wood095"]["sourceUrl"] == "https://ambientcg.com/a/Wood095"
    assert desktop_candidates["Wood095"]["ingestStage"] == "staging_candidate"
    assert desktop_candidates["Wood095"]["downloadDate"] == "not_downloaded"
    assert desktop_candidates["Wood095"]["workerReadiness"]["highFidelityWorker"] == "requires_asset_import_test"
    assert "safe_framing_with_close_camera" in desktop_candidates["Wood095"]["requiredValidation"]
    assert desktop_candidates["blue_photo_studio"]["url"] == "https://polyhaven.com/a/blue_photo_studio"
    assert desktop_candidates["blue_photo_studio"]["licenseReview"]["required"] is False
    assert desktop_candidates["metal_office_desk"]["kind"] == "desk scene model"
    assert desktop_candidates["metal_office_desk"]["sourceUrl"] == "https://polyhaven.com/a/metal_office_desk"
    assert "scene_fusion_no_occlusion" in desktop_candidates["metal_office_desk"]["requiredValidation"]
    assert desktop_candidates["industrial_coffee_table"]["kind"] == "tabletop scene model"
    assert desktop_candidates["industrial_coffee_table"]["sourceUrl"] == (
        "https://polyhaven.com/a/industrial_coffee_table"
    )
    assert desktop_candidates["industrial_coffee_table"]["workerReadiness"]["browserPreview"] == "not_ingested"
    assert "browser_preview_performance" in desktop_candidates["industrial_coffee_table"]["requiredValidation"]
    gift_scene = next(item for item in result["scenePresets"] if item["key"] == "gift_table")
    gift_candidates = {item["assetId"]: item for item in gift_scene["asset"]["externalCandidates"]}
    assert gift_candidates["industrial_coffee_table"]["kind"] == "gift tabletop scene model"
    assert "gift_table" in gift_candidates["industrial_coffee_table"]["targetScenePresets"]
    retail_scene = next(item for item in result["scenePresets"] if item["key"] == "retail_shelf")
    retail_candidates = {item["assetId"]: item for item in retail_scene["asset"]["externalCandidates"]}
    assert retail_candidates["wooden_display_shelves_01"]["kind"] == "retail display shelf model"
    assert retail_candidates["wooden_display_shelves_01"]["sourceUrl"] == (
        "https://polyhaven.com/a/wooden_display_shelves_01"
    )
    assert retail_candidates["wooden_display_shelves_01"]["licenseReview"]["commercialUse"] is True
    assert retail_candidates["steel_frame_shelves_01"]["kind"] == "industrial shelf scene model"
    assert retail_candidates["steel_frame_shelves_01"]["sourceUrl"] == (
        "https://polyhaven.com/a/steel_frame_shelves_01"
    )
    assert "no_text_logo_watermark_or_brand_props" in retail_candidates["steel_frame_shelves_01"]["requiredValidation"]
    assert retail_candidates["Metal037"]["licenseUrl"] == "https://docs.ambientcg.com/license/"
    assert retail_candidates["Metal037"]["workerReadiness"]["highFidelityWorker"] == "requires_asset_import_test"
    assert desktop_scene["fusion"]["occlusionPolicy"] == (
        "secondary props stay behind the product and cannot cover texture slots"
    )
    sources = {item["provider"]: item for item in result["sceneAssetSources"]}
    assert sources["Poly Haven"]["license"] == "CC0"
    assert sources["Poly Haven"]["commercialUse"] is True
    assert "studio HDRI" in sources["Poly Haven"]["currentUse"]
    assert {item["assetId"] for item in sources["Poly Haven"]["candidateAssets"]} >= {
        "blocky_photo_studio",
        "blue_photo_studio",
        "brown_photostudio_01",
        "metal_office_desk",
        "SchoolDesk_01",
        "wooden_display_shelves_01",
        "steel_frame_shelves_01",
        "industrial_coffee_table",
    }
    poly_candidate = next(item for item in sources["Poly Haven"]["candidateAssets"] if item["assetId"] == "blocky_photo_studio")
    assert poly_candidate["ingestStage"] == "staging_candidate"
    assert poly_candidate["assetVersion"] == "to_be_recorded"
    assert poly_candidate["downloadRequired"] is True
    assert poly_candidate["licenseReview"]["commercialUse"] is True
    assert sources["Poly Haven"]["candidateAssetPolicy"]["executionInput"] is False
    assert sources["ambientCG"]["license"] == "CC0 1.0 Universal"
    assert {item["assetId"] for item in sources["ambientCG"]["candidateAssets"]} >= {
        "Wood095",
        "Paper006",
        "Cardboard002",
        "Concrete036",
        "Fabric079",
        "Metal037",
    }
    assert "record asset URL, provider, license URL, version, and download date" in sources["ambientCG"]["ingestGate"]
    assert sources["ambientCG"]["candidateAssetCount"] >= 5
    assert sources["internal_or_cc0"]["ingestStatus"] == "needs_license_review"
    assert sources["internal_or_cc0"]["candidateAssetPolicy"]["status"] == "staging_only"
    assert any(item["key"] == "social_arc" for item in result["cameraPresets"])
    assert any(item["key"] == "close" for item in result["cameraDistances"])
    assert result["renderers"]["serverLightweight"]["worker"] == "lightweight_scene_renderer_v1"
    assert result["renderers"]["highFidelity"]["status"] == "planned"


def test_product_3d_render_video_catalog_endpoint() -> None:
    resp = client.get("/api/business/product-3d-render-video/catalog", headers={"x-real-ip": "127.0.0.1"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["businessKey"] == "product_3d_render_video"
    assert body["defaults"]["scenePreset"] == "clean_studio"
    assert body["endpoints"]["renderRun"] == "POST /api/business/product-3d-render-video/runs"
    assert body["models"][0]["materialSlots"]
    assert any(item["provider"] == "Poly Haven" for item in body["sceneAssetSources"])


def test_product_3d_render_video_preview_marks_missing_texture() -> None:
    service = Product3DRenderVideoService()

    result = service.preview(Product3DRenderVideoRequest(modelKey="cup_1660", materialSlot="front"))

    issue_codes = [item.get("code") for item in result["assetReadiness"]["warnings"]]
    assert result["assetReadiness"]["textureProvided"] is False
    assert "PRODUCT_3D_RENDER_VIDEO_TEXTURE_MISSING" in issue_codes


def test_product_3d_render_video_rejects_invalid_material_slot() -> None:
    service = Product3DRenderVideoService()

    with pytest.raises(HTTPException) as excinfo:
        service.preview(Product3DRenderVideoRequest(modelKey="cup_1660", materialSlot="backpack-front"))

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "PRODUCT_3D_RENDER_VIDEO_MATERIAL_SLOT_INVALID"


def test_product_3d_render_video_rejects_invalid_camera_distance() -> None:
    service = Product3DRenderVideoService()

    with pytest.raises(HTTPException) as excinfo:
        service.preview(Product3DRenderVideoRequest(modelKey="cup_1660", cameraDistance="macro_only"))

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "PRODUCT_3D_RENDER_VIDEO_CAMERA_DISTANCE_INVALID"


def test_product_3d_render_video_rejects_invalid_motion_path() -> None:
    service = Product3DRenderVideoService()

    with pytest.raises(HTTPException) as excinfo:
        service.preview(Product3DRenderVideoRequest(modelKey="cup_1660", motionPath=[{"x": 1.2, "y": 0.5}]))

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "PRODUCT_3D_RENDER_VIDEO_MOTION_PATH_INVALID"


def test_product_3d_render_video_lightweight_renderer_keeps_subject_inside_frame() -> None:
    texture = Image.new("RGB", (96, 96), "#ff00cc")
    motion_path = [{"x": 0, "y": 1}, {"x": 1, "y": 0}]
    size = (640, 360)
    min_horizontal_margin = int(size[0] * 0.03)
    min_vertical_margin = int(size[1] * 0.04)

    for model_key in ("cup_1660", "backpack_2551"):
        for progress in (0, 0.5, 1):
            frame = product_3d_render_video_module._draw_product_frame(
                size=size,
                model_key=model_key,
                texture=texture,
                scene_preset="retail_shelf",
                camera_preset="detail_sweep",
                camera_distance="close",
                motion_path=motion_path,
                progress=progress,
            )
            pixels = frame.load()
            subject_pixels: list[tuple[int, int]] = []
            for y in range(frame.height):
                for x in range(frame.width):
                    red, green, blue = pixels[x, y]
                    is_texture = red > 180 and blue > 120 and green < 80
                    is_outline = red < 70 and green < 80 and blue < 95
                    if is_texture or is_outline:
                        subject_pixels.append((x, y))

            assert subject_pixels, f"{model_key} progress={progress} did not render detectable subject pixels"
            xs = [point[0] for point in subject_pixels]
            ys = [point[1] for point in subject_pixels]
            assert min(xs) >= min_horizontal_margin
            assert frame.width - 1 - max(xs) >= min_horizontal_margin
            assert min(ys) >= min_vertical_margin
            assert frame.height - 1 - max(ys) >= min_vertical_margin


def test_product_3d_render_video_render_run_keeps_all_frames_inside_safe_bounds(monkeypatch) -> None:
    service = Product3DRenderVideoService()
    texture = Image.new("RGB", (96, 96), "#ff00cc")
    uploaded: dict[str, bytes] = {}

    monkeypatch.setattr(product_3d_render_video_module, "_load_texture_image", lambda url: texture)

    def assert_rendered_frames_are_safe(frames, fps):
        assert fps == 10
        assert len(frames) >= 10
        for frame_index, frame in enumerate(frames):
            pixels = frame.load()
            subject_pixels: list[tuple[int, int]] = []
            for y in range(frame.height):
                for x in range(frame.width):
                    red, green, blue = pixels[x, y]
                    is_texture = red > 180 and blue > 120 and green < 80
                    is_outline = red < 70 and green < 80 and blue < 95
                    if is_texture or is_outline:
                        subject_pixels.append((x, y))

            assert subject_pixels, f"rendered frame {frame_index} did not contain detectable product pixels"
            xs = [point[0] for point in subject_pixels]
            ys = [point[1] for point in subject_pixels]
            assert min(xs) >= int(frame.width * 0.03), f"rendered frame {frame_index} is cropped on the left"
            assert frame.width - 1 - max(xs) >= int(frame.width * 0.03), (
                f"rendered frame {frame_index} is cropped on the right"
            )
            assert min(ys) >= int(frame.height * 0.04), f"rendered frame {frame_index} is cropped at the top"
            assert frame.height - 1 - max(ys) >= int(frame.height * 0.04), (
                f"rendered frame {frame_index} is cropped at the bottom"
            )
        return b"mp4-bytes"

    monkeypatch.setattr(product_3d_render_video_module, "_encode_mp4", assert_rendered_frames_are_safe)

    def fake_upload_bytes(*, user_id, filename, data, content_type):
        uploaded[filename] = data
        return {"url": f"https://podi.oss-cn-hangzhou.aliyuncs.com/{filename}", "contentType": content_type}

    monkeypatch.setattr(product_3d_render_video_module.oss_service, "upload_bytes", fake_upload_bytes)

    result = service.submit_render_run(
        Product3DRenderVideoRequest(
            modelKey="cup_1660",
            textureSlots=[{"materialSlot": "front", "imageUrl": "https://example.com/front.png"}],
            cameraPreset="detail_sweep",
            cameraDistance="close",
            scenePreset="retail_shelf",
            motionPath=[{"x": 0, "y": 1}, {"x": 1, "y": 0}],
            durationSeconds=1,
            aspectRatio="16:9",
            outputMode="render_video",
            requestId="req-3d-render-safe-bounds",
        )
    )

    assert result["renderAssetPackage"]["manifest"]["framingPolicy"]["mode"] == "fit_product_safe_bounds"
    assert result["renderAssetPackage"]["manifest"]["framingPolicy"]["framingSafety"]["cameraDistance"] == "close"
    assert result["renderAssetPackage"]["manifest"]["framingPolicy"]["framingSafety"]["finalDeliveryRecommended"] is False
    assert result["renderAssetPackage"]["manifest"]["framingSafety"]["checks"]["motionCannotOverrideSafeBounds"] is True
    assert result["renderAssetPackage"]["manifest"]["cameraPlan"]["productMotion"] == "fixed"
    assert result["renderAssetPackage"]["manifest"]["cameraPlan"]["cameraMotion"] == "path_playback"
    assert result["renderAssetPackage"]["manifest"]["cameraPlan"]["constraints"]["productFixed"] is True
    assert result["renderAssetPackage"]["manifest"]["cameraDistance"] == "close"
    assert result["renderAssetPackage"]["manifest"]["motionPath"] == [{"x": 0, "y": 1}, {"x": 1, "y": 0}]
    cover_bytes = uploaded["req-3d-render-safe-bounds-cover.png"]
    cover = Image.open(BytesIO(cover_bytes))
    assert cover.width >= 900
    assert cover.width / cover.height == pytest.approx(16 / 9)


def test_product_3d_render_video_render_run_encodes_real_mp4_bytes(monkeypatch) -> None:
    try:
        product_3d_render_video_module._get_ffmpeg_executable()
    except HTTPException as exc:
        if exc.detail == "PRODUCT_3D_RENDER_VIDEO_FFMPEG_MISSING":
            pytest.skip("ffmpeg is not available in this environment")
        raise

    service = Product3DRenderVideoService()
    texture = Image.new("RGB", (80, 80), "#ff00cc")
    uploaded: dict[str, dict[str, object]] = {}

    monkeypatch.setattr(product_3d_render_video_module, "_load_texture_image", lambda url: texture)

    def fake_upload_bytes(*, user_id, filename, data, content_type):
        uploaded[filename] = {"data": data, "contentType": content_type, "userId": user_id}
        return {
            "url": f"https://podi.oss-cn-hangzhou.aliyuncs.com/{filename}",
            "contentType": content_type,
        }

    monkeypatch.setattr(product_3d_render_video_module.oss_service, "upload_bytes", fake_upload_bytes)

    result = service.submit_render_run(
        Product3DRenderVideoRequest(
            modelKey="cup_1660",
            textureSlots=[{"materialSlot": "front", "imageUrl": "https://example.com/front.png", "label": "杯身正面"}],
            cameraPreset="orbit_360",
            cameraDistance="wide",
            scenePreset="gift_table",
            motionPath=[{"x": 0.45, "y": 0.58}, {"x": 0.55, "y": 0.54}],
            durationSeconds=1,
            aspectRatio="16:9",
            outputMode="render_video",
            requestId="req-3d-real-mp4-001",
        )
    )

    video = uploaded["req-3d-real-mp4-001.mp4"]
    cover = uploaded["req-3d-real-mp4-001-cover.png"]
    manifest = uploaded["req-3d-real-mp4-001-manifest.json"]
    assert video["contentType"] == "video/mp4"
    assert cover["contentType"] == "image/png"
    assert manifest["contentType"] == "application/json"
    video_bytes = video["data"]
    assert isinstance(video_bytes, bytes)
    assert len(video_bytes) > 1000
    assert b"ftyp" in video_bytes[:64]
    cover_image = Image.open(BytesIO(cover["data"]))
    assert cover_image.size == (960, 540)
    manifest_payload = json.loads(manifest["data"].decode("utf-8"))
    assert manifest_payload["renderer"] == "lightweight_scene_renderer_v1"
    assert manifest_payload["scenePreset"] == "gift_table"
    assert manifest_payload["sceneAsset"]["assetId"] == "podi.scene.procedural.gift_table.v1"
    assert manifest_payload["framingPolicy"]["mode"] == "fit_product_safe_bounds"
    assert manifest_payload["textureApplication"]["textureSlots"] == [
        {"materialSlot": "front", "imageUrl": "https://example.com/front.png", "label": "杯身正面"}
    ]
    assert result["renderAssetPackage"]["videoUrl"].endswith("req-3d-real-mp4-001.mp4")
    assert result["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/req-3d-real-mp4-001.mp4"]


def test_product_3d_render_video_lightweight_renderer_applies_scene_elements() -> None:
    size = (960, 540)
    texture = Image.new("RGB", (96, 96), "#ff00cc")
    motion_path = [{"x": 0.5, "y": 0.5}, {"x": 0.52, "y": 0.48}]

    desktop = product_3d_render_video_module._draw_product_frame(
        size=size,
        model_key="cup_1660",
        texture=texture,
        scene_preset="desktop_lifestyle",
        camera_preset="orbit_360",
        camera_distance="wide",
        motion_path=motion_path,
        progress=0.5,
    )
    marketplace = product_3d_render_video_module._draw_product_frame(
        size=size,
        model_key="cup_1660",
        texture=texture,
        scene_preset="marketplace_white",
        camera_preset="orbit_360",
        camera_distance="wide",
        motion_path=motion_path,
        progress=0.5,
    )
    retail = product_3d_render_video_module._draw_product_frame(
        size=size,
        model_key="cup_1660",
        texture=texture,
        scene_preset="retail_shelf",
        camera_preset="orbit_360",
        camera_distance="wide",
        motion_path=motion_path,
        progress=0.5,
    )

    assert desktop.getpixel((int(size[0] * 0.1), int(size[1] * 0.62))) != marketplace.getpixel(
        (int(size[0] * 0.1), int(size[1] * 0.62))
    )
    assert desktop.getpixel((int(size[0] * 0.5), int(size[1] * 0.9))) != marketplace.getpixel(
        (int(size[0] * 0.5), int(size[1] * 0.9))
    )
    assert retail.getpixel((int(size[0] * 0.05), int(size[1] * 0.56))) != marketplace.getpixel(
        (int(size[0] * 0.05), int(size[1] * 0.56))
    )

    pixels = desktop.load()
    texture_pixels = [
        (x, y)
        for y in range(desktop.height)
        for x in range(desktop.width)
        if pixels[x, y][0] > 180 and pixels[x, y][2] > 120 and pixels[x, y][1] < 80
    ]
    assert len(texture_pixels) > 5000
    xs = [point[0] for point in texture_pixels]
    ys = [point[1] for point in texture_pixels]
    assert min(xs) >= int(size[0] * 0.03)
    assert size[0] - 1 - max(xs) >= int(size[0] * 0.03)
    assert min(ys) >= int(size[1] * 0.04)
    assert size[1] - 1 - max(ys) >= int(size[1] * 0.04)


def test_product_3d_render_video_rejects_render_mode_until_worker_exists() -> None:
    service = Product3DRenderVideoService()

    with pytest.raises(HTTPException) as excinfo:
        service.preview(Product3DRenderVideoRequest(modelKey="cup_1660", outputMode="render_video"))

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "PRODUCT_3D_RENDER_VIDEO_EXECUTION_NOT_READY"


def test_product_3d_render_video_render_run_generates_asset_package(monkeypatch) -> None:
    service = Product3DRenderVideoService()

    monkeypatch.setattr(
        product_3d_render_video_module,
        "_load_texture_image",
        lambda url: Image.new("RGB", (64, 64), "#336699"),
    )
    captured_draw_calls = []

    def fake_draw_product_frame(**kwargs):
        captured_draw_calls.append(kwargs)
        return Image.new("RGB", kwargs["size"], "#ffffff")

    monkeypatch.setattr(product_3d_render_video_module, "_draw_product_frame", fake_draw_product_frame)
    monkeypatch.setattr(product_3d_render_video_module, "_encode_mp4", lambda frames, fps: b"mp4-bytes")

    def fake_upload_bytes(*, user_id, filename, data, content_type):
        return {"url": f"https://podi.oss-cn-hangzhou.aliyuncs.com/{filename}", "contentType": content_type}

    monkeypatch.setattr(product_3d_render_video_module.oss_service, "upload_bytes", fake_upload_bytes)

    result = service.submit_render_run(
        Product3DRenderVideoRequest(
            modelKey="cup_1660",
            textureSlots=[
                {"materialSlot": "front", "imageUrl": "https://example.com/front.png", "label": "杯身正面"},
                {"materialSlot": "bottom", "imageUrl": "https://example.com/bottom.png", "label": "杯底"},
            ],
            cameraPreset="social_arc",
            cameraDistance="close",
            scenePreset="desktop_lifestyle",
            motionPath=[{"x": 0.18, "y": 0.7}, {"x": 0.46, "y": 0.52}, {"x": 0.82, "y": 0.44}],
            outputMode="render_video",
            requestId="req-3d-render-run-001",
        )
    )

    assert result["businessKey"] == "product_3d_render_video"
    assert result["status"] == "succeeded"
    assert result["assetReadiness"]["renderWorkerReady"] is True
    assert result["renderPlan"]["executionStatus"] == "rendered"
    assert result["renderAssetPackage"]["videoUrl"].endswith("req-3d-render-run-001.mp4")
    assert result["renderAssetPackage"]["manifest"]["sceneModelVersion"] == "procedural-commerce-scene-v2"
    assert result["renderAssetPackage"]["manifest"]["sceneAsset"]["assetId"] == "podi.scene.procedural.desktop_lifestyle.v1"
    assert result["renderAssetPackage"]["manifest"]["sceneAsset"]["license"]["commercialUse"] is True
    assert result["renderAssetPackage"]["manifest"]["sceneAsset"]["externalCandidates"][0]["licenseUrl"] == "https://docs.ambientcg.com/license/"
    assert result["renderAssetPackage"]["manifest"]["sceneAsset"]["ingestPolicy"]["doNotBundleLargeVendorAssetsInRepo"] is True
    assert result["renderAssetPackage"]["manifest"]["sceneFusion"]["landingZone"] == "front_center_tabletop_zone"
    manifest_elements = {item["elementId"]: item for item in result["renderAssetPackage"]["manifest"]["sceneElements"]}
    assert manifest_elements["wood_tabletop"]["depthLayer"] == "surface"
    assert manifest_elements["rear_soft_cube"]["occlusion"] == "behind_product_only"
    assert result["renderAssetPackage"]["manifest"]["sceneFusion"]["occlusionPolicy"] == (
        "secondary props stay behind the product and cannot cover texture slots"
    )
    assert result["renderAssetPackage"]["manifest"]["sceneVisualAcceptance"]["status"] == "mvp_ready"
    assert result["renderAssetPackage"]["manifest"]["sceneVisualAcceptance"]["currentAsset"]["assetId"] == (
        "podi.scene.procedural.desktop_lifestyle.v1"
    )
    assert "SAFE_FRAMING" in {
        item["code"] for item in result["renderAssetPackage"]["manifest"]["sceneVisualAcceptance"]["checks"]
    }
    assert result["renderAssetPackage"]["manifest"]["framingPolicy"]["mode"] == "fit_product_safe_bounds"
    assert result["renderAssetPackage"]["manifest"]["framingPolicy"]["safeMarginRatio"] == 0.06
    assert result["renderAssetPackage"]["manifest"]["framingPolicy"]["framingSafety"]["motionPathBounds"]["spanX"] == 0.64
    assert result["renderAssetPackage"]["manifest"]["framingSafety"]["caution"]
    assert result["renderAssetPackage"]["manifest"]["cameraPreset"] == "social_arc"
    assert result["renderAssetPackage"]["manifest"]["cameraDistance"] == "close"
    assert result["renderAssetPackage"]["manifest"]["scenePreset"] == "desktop_lifestyle"
    assert result["renderAssetPackage"]["manifest"]["motionPath"] == [
        {"x": 0.18, "y": 0.7},
        {"x": 0.46, "y": 0.52},
        {"x": 0.82, "y": 0.44},
    ]
    assert captured_draw_calls
    assert captured_draw_calls[0]["scene_preset"] == "desktop_lifestyle"
    assert captured_draw_calls[0]["camera_preset"] == "social_arc"
    assert captured_draw_calls[0]["camera_distance"] == "close"
    assert captured_draw_calls[0]["motion_path"] == [
        {"x": 0.18, "y": 0.7},
        {"x": 0.46, "y": 0.52},
        {"x": 0.82, "y": 0.44},
    ]
    assert result["renderAssetPackage"]["textureApplication"]["textureSlotCount"] == 2
    assert result["renderAssetPackage"]["textureApplication"]["primaryTextureUrl"] == "https://example.com/front.png"
    assert result["renderAssetPackage"]["textureApplication"]["textureSlots"] == [
        {"materialSlot": "front", "imageUrl": "https://example.com/front.png", "label": "杯身正面"},
        {"materialSlot": "bottom", "imageUrl": "https://example.com/bottom.png", "label": "杯底"},
    ]
    assert "high-fidelity workers" in result["renderAssetPackage"]["manifest"]["textureApplication"]["note"]
    assert result["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/req-3d-render-run-001.mp4"]
    assert result["imageUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/req-3d-render-run-001-cover.png"]


def test_product_commercialization_patrol_builds_live_3d_render_payload() -> None:
    patrol = _load_product_commercialization_patrol_module()

    payload = patrol._product_3d_render_payload(texture_url="https://example.com/front.png", tag="unit")

    assert payload["outputMode"] == "render_video"
    assert payload["requestId"] == "product-3d-render-patrol-unit"
    assert payload["cameraPreset"] == "social_arc"
    assert payload["cameraDistance"] == "close"
    assert payload["scenePreset"] == "desktop_lifestyle"
    assert payload["textureSlots"] == [
        {"materialSlot": "front", "imageUrl": "https://example.com/front.png", "label": "正面主贴图区"},
        {"materialSlot": "mouth", "imageUrl": "https://example.com/front.png", "label": "杯口测试贴图"},
    ]
    assert len(payload["motionPath"]) >= 2


def test_product_commercialization_patrol_validates_live_3d_render_result() -> None:
    patrol = _load_product_commercialization_patrol_module()
    run = {
        "status": "succeeded",
        "businessKey": "product_3d_render_video",
        "imageUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/req-cover.png"],
        "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/req.mp4"],
        "quotaUnits": 0,
        "resultPayload": {
            "renderAssetPackage": {
                "deliveryStatus": "assets_ready",
                "manifest": {
                    "sceneAsset": {"assetId": "podi.scene.procedural.desktop_lifestyle.v1"},
                    "sceneFusion": {"landingZone": "front_center_tabletop_zone"},
                    "sceneElements": [
                        {
                            "elementId": "wood_tabletop",
                            "depthLayer": "surface",
                            "occlusion": "shadow_receiver_only",
                        }
                    ],
                    "framingPolicy": {"mode": "fit_product_safe_bounds"},
                    "textureApplication": {"textureSlotCount": 2},
                    "cameraDistance": "close",
                    "motionPath": [{"x": 0.2, "y": 0.6}, {"x": 0.8, "y": 0.4}],
                },
            }
        },
    }

    ok, detail = patrol._validate_live_product_3d_render(run)
    assert ok is True
    assert "scene=podi.scene.procedural.desktop_lifestyle.v1" in detail

    broken = {
        **run,
        "resultPayload": {"renderAssetPackage": {"deliveryStatus": "assets_ready", "manifest": {}}},
    }
    ok, detail = patrol._validate_live_product_3d_render(broken)
    assert ok is False
    assert "sceneAsset" in detail

    missing_elements = {
        **run,
        "resultPayload": {
            "renderAssetPackage": {
                "deliveryStatus": "assets_ready",
                "manifest": {
                    "sceneAsset": {"assetId": "podi.scene.procedural.desktop_lifestyle.v1"},
                    "sceneFusion": {"landingZone": "front_center_tabletop_zone"},
                    "framingPolicy": {"mode": "fit_product_safe_bounds"},
                    "textureApplication": {"textureSlotCount": 2},
                    "cameraDistance": "close",
                    "motionPath": [{"x": 0.2, "y": 0.6}, {"x": 0.8, "y": 0.4}],
                },
            }
        },
    }
    ok, detail = patrol._validate_live_product_3d_render(missing_elements)
    assert ok is False
    assert "sceneElements" in detail


def test_product_commercialization_patrol_chains_keyframes_into_video_payload() -> None:
    patrol = _load_product_commercialization_patrol_module()
    keyframe_url = "https://podi.oss-cn-hangzhou.aliyuncs.com/patrol-keyframe-shot-1.png"
    keyframe_run = {
        "status": "succeeded",
        "resultPayload": {
            "videoAssetPackage": {
                "deliveryStatus": "keyframes_ready",
                "keyframes": [
                    {
                        "role": "first_frame",
                        "shot": "1",
                        "segmentIndex": 1,
                        "imageUrl": keyframe_url,
                    }
                ],
            }
        },
    }

    confirmed = patrol._extract_confirmed_video_keyframes(keyframe_run)
    payload = patrol._live_video_payload(
        {"productImageUrl": "https://example.com/product.png"},
        tag="unit",
        executor_id="executor_vidu_default",
        target_duration=15,
        confirmed_keyframes=confirmed,
    )

    assert confirmed == [
        {
            "role": "first_frame",
            "shot": "1",
            "segmentIndex": 1,
            "imageUrl": keyframe_url,
            "confirmed": True,
            "source": "patrol_confirmed_video_keyframe",
        }
    ]
    assert payload["action"] == "video_generate"
    assert payload["confirmedVideoKeyframes"] == confirmed
    assert payload["targetDurationSeconds"] == 15


def test_product_commercialization_patrol_requires_confirmed_keyframe_evidence_for_chained_video() -> None:
    patrol = _load_product_commercialization_patrol_module()
    keyframe_url = "https://podi.oss-cn-hangzhou.aliyuncs.com/patrol-keyframe-shot-1.png"
    run = {
        "status": "succeeded",
        "resultPayload": {
            "videoAssetPackage": {
                "deliveryStatus": "assets_ready",
                "script": {"text": "show product"},
                "keyframes": [
                    {
                        "role": "first_frame",
                        "segmentIndex": 1,
                        "imageUrl": keyframe_url,
                        "confirmed": True,
                    }
                ],
                "segmentVideos": [
                    {
                        "videoUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/patrol-video.mp4",
                        "referenceImageUrl": keyframe_url,
                    }
                ],
            },
            "videoResult": {
                "segments": [
                    {
                        "videoUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/patrol-video.mp4",
                        "referenceImageUrl": keyframe_url,
                    }
                ]
            },
        },
    }

    ok, detail = patrol._validate_live_video(run, require_confirmed_keyframes=True)
    assert ok is True
    assert "segments=1" in detail

    missing_confirmation = {
        **run,
        "resultPayload": {
            **run["resultPayload"],
            "videoAssetPackage": {
                **run["resultPayload"]["videoAssetPackage"],
                "keyframes": [{"imageUrl": keyframe_url, "confirmed": False}],
            },
        },
    }
    ok, detail = patrol._validate_live_video(missing_confirmation, require_confirmed_keyframes=True)
    assert ok is False
    assert "confirmed keyframes" in detail

    missing_reference = {
        **run,
        "resultPayload": {
            **run["resultPayload"],
            "videoAssetPackage": {
                **run["resultPayload"]["videoAssetPackage"],
                "segmentVideos": [{"videoUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/patrol-video.mp4"}],
            },
            "videoResult": {"segments": []},
        },
    }
    ok, detail = patrol._validate_live_video(missing_reference, require_confirmed_keyframes=True)
    assert ok is False
    assert "reference evidence" in detail


def test_product_3d_render_video_run_endpoint_returns_standard_run(monkeypatch) -> None:
    class FakeBusinessRunService:
        def create_product_3d_render_video_run(self, *, payload, user):
            assert payload.outputMode == "render_video"
            return {
                "id": "run-product-3d-001",
                "business_key": "product_3d_render_video",
                "businessKey": "product_3d_render_video",
                "version": "p3d-render-video-v1",
                "status": "queued",
                "source": "business-api",
                "trace_id": "trace-product-3d-001",
                "request_id": payload.requestId,
                "created_at": "2026-06-13T00:00:00",
                "updated_at": "2026-06-13T00:00:00",
            }

    monkeypatch.setattr("app.routers.business.get_business_run_service", lambda: FakeBusinessRunService())
    resp = client.post(
        "/api/business/product-3d-render-video/runs",
        headers={"x-real-ip": "127.0.0.1"},
        json={
            "modelKey": "cup_1660",
            "textureSlots": [{"materialSlot": "front", "imageUrl": "https://example.com/front.png"}],
            "cameraDistance": "wide",
            "outputMode": "render_video",
            "requestId": "req-3d-render-run-002",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["runId"] == "run-product-3d-001"
    assert body["taskId"] == "run-product-3d-001"
    assert body["businessKey"] == "product_3d_render_video"
    assert body["version"] == "p3d-render-video-v1"
    assert len(body["version"]) <= 32
    assert body["status"] == "queued"


def test_product_3d_render_video_run_endpoint_can_be_polled_to_manifest(monkeypatch) -> None:
    video_url = "https://podi.oss-cn-hangzhou.aliyuncs.com/test/3d/polled-render.mp4"
    cover_url = "https://podi.oss-cn-hangzhou.aliyuncs.com/test/3d/polled-render-cover.png"

    def fake_render_video(payload, *, user_id=None):
        assert payload.outputMode == "render_video"
        assert payload.cameraDistance == "close"
        assert payload.scenePreset == "desktop_lifestyle"
        assert payload.motionPath == [{"x": 0.18, "y": 0.7}, {"x": 0.82, "y": 0.44}]
        return {
            "status": "succeeded",
            "businessKey": "product_3d_render_video",
            "version": "product-3d-render-video-lightweight-v1",
            "requestId": payload.requestId,
            "videoUrls": [video_url],
            "imageUrls": [cover_url],
            "renderAssetPackage": {
                "deliveryStatus": "assets_ready",
                "renderer": "lightweight_scene_renderer_v1",
                "videoUrl": video_url,
                "coverFrameUrl": cover_url,
                "textureApplication": {
                    "textureSlotCount": 1,
                    "textureSlots": [{"materialSlot": "front", "imageUrl": "https://example.com/front.png"}],
                    "primaryTextureUrl": "https://example.com/front.png",
                    "preserveUv": True,
                },
                "manifest": {
                    "sceneAsset": {"assetId": "podi.scene.procedural.desktop_lifestyle.v1"},
                    "sceneFusion": {"landingZone": "front_center_tabletop_zone"},
                    "sceneElements": [
                        {
                            "elementId": "wood_tabletop",
                            "depthLayer": "surface",
                            "occlusion": "shadow_receiver_only",
                        }
                    ],
                    "framingPolicy": {"mode": "fit_product_safe_bounds"},
                    "textureApplication": {
                        "textureSlotCount": 1,
                        "textureSlots": [{"materialSlot": "front", "imageUrl": "https://example.com/front.png"}],
                    },
                    "cameraDistance": "close",
                    "motionPath": [{"x": 0.18, "y": 0.7}, {"x": 0.82, "y": 0.44}],
                },
            },
            "videoResult": {"status": "succeeded", "videoUrls": [video_url]},
        }

    monkeypatch.setattr(
        "app.services.business_runs.product_3d_render_video_service.render_video",
        fake_render_video,
    )

    resp = client.post(
        "/api/business/product-3d-render-video/runs",
        headers={"x-real-ip": "127.0.0.1"},
        json={
            "modelKey": "cup_1660",
            "textureSlots": [{"materialSlot": "front", "imageUrl": "https://example.com/front.png"}],
            "cameraPreset": "social_arc",
            "cameraDistance": "close",
            "scenePreset": "desktop_lifestyle",
            "motionPath": [{"x": 0.18, "y": 0.7}, {"x": 0.82, "y": 0.44}],
            "durationSeconds": 3,
            "outputMode": "render_video",
            "requestId": "req-3d-render-polled-001",
        },
    )

    assert resp.status_code == 200
    submit = resp.json()
    assert submit["businessKey"] == "product_3d_render_video"
    assert submit["taskId"] == submit["runId"]
    assert submit["version"] == "p3d-render-video-v1"
    assert len(submit["version"]) <= 32

    detail = {}
    for _ in range(30):
        poll = client.post(
            "/api/business/runs/get",
            headers={"x-real-ip": "127.0.0.1"},
            json={"runId": submit["runId"], "detail": "full"},
        )
        assert poll.status_code == 200
        detail = poll.json()
        if detail["status"] == "succeeded":
            break
        time.sleep(0.1)

    assert detail["status"] == "succeeded"
    assert detail["businessKey"] == "product_3d_render_video"
    assert detail["taskId"] == submit["runId"]
    assert detail["version"] == "p3d-render-video-v1"
    assert detail["resultPayload"]["version"] == "product-3d-render-video-lightweight-v1"
    assert detail["billingUnit"] == "p3d_render_video_lightweight"
    assert len(detail["billingUnit"]) <= 32
    assert detail["videoUrls"] == [video_url]
    assert detail["imageUrls"] == [cover_url]
    assert detail["quotaUnits"] == 0
    assert detail["costBreakdown"]["billingMode"] == "no_charge"
    assert detail["costBreakdown"]["billingUnit"] == "p3d_render_video_lightweight"
    assert len(detail["costBreakdown"]["billingUnit"]) <= 32
    package = detail["resultPayload"]["renderAssetPackage"]
    assert package["deliveryStatus"] == "assets_ready"
    assert package["manifest"]["sceneAsset"]["assetId"] == "podi.scene.procedural.desktop_lifestyle.v1"
    assert package["manifest"]["framingPolicy"]["mode"] == "fit_product_safe_bounds"
    assert package["manifest"]["textureApplication"]["textureSlotCount"] == 1
    assert package["manifest"]["cameraDistance"] == "close"
    assert package["manifest"]["motionPath"] == [{"x": 0.18, "y": 0.7}, {"x": 0.82, "y": 0.44}]


def test_promo_video_split_run_endpoints_force_actions(monkeypatch) -> None:
    captured_actions: list[str | None] = []
    captured_business_keys: list[str | None] = []

    class FakeBusinessRunService:
        def create_product_commercialization_run(self, *, payload, user, business_key="product_commercialization"):
            captured_actions.append(payload.action)
            captured_business_keys.append(business_key)
            return {
                "id": f"run-promo-video-{len(captured_actions)}",
                "business_key": business_key,
                "businessKey": business_key,
                "version": "promo-video-mvp-v1",
                "status": "queued",
                "source": "business-api",
                "trace_id": f"trace-promo-video-{len(captured_actions)}",
                "request_id": payload.requestId,
                "created_at": "2026-06-13T00:00:00",
                "updated_at": "2026-06-13T00:00:00",
            }

    monkeypatch.setattr("app.routers.business.get_business_run_service", lambda: FakeBusinessRunService())

    base_payload = {
        "productImageUrl": "https://example.com/product.png",
        "requestId": "req-promo-video-split",
    }
    for path in (
        "/api/business/promo-video/keyframes/runs",
        "/api/business/promo-video/runs",
        "/api/business/promo-video/compose/runs",
    ):
        resp = client.post(path, headers={"x-real-ip": "127.0.0.1"}, json={**base_payload, "action": "wrong_action"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"
        assert resp.json()["businessKey"] == "promo_video"
        assert resp.json()["taskId"] == resp.json()["runId"]

    assert captured_actions == ["video_keyframes", "video_generate", "compose_video"]
    assert captured_business_keys == ["promo_video", "promo_video", "promo_video"]


def test_promo_video_plan_endpoint_forces_video_preview(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    def fake_preview(payload, *, user_id=None):
        captured["action"] = payload.action
        return {
            "requestId": payload.requestId or "req-promo-video-plan",
            "businessKey": "product_commercialization",
            "version": "product-commercialization-mvp-v1",
            "status": "previewed",
            "generatedAt": "2026-06-13T00:00:00+00:00",
            "strategyProfile": "default_pod_profile",
            "outputLanguage": "en-US",
            "marketRegion": "US",
            "copyScenarios": [],
            "productCard": {},
            "resolvedProductFacts": {},
            "copyPackage": {},
            "contentPackage": {},
            "copyGeneration": {"method": "skipped_for_video_preview"},
            "visualAssetPlan": {},
            "videoPlan": {},
            "videoAssetPackagePlan": {},
            "review": {"score": 80, "issues": []},
            "execution": {"videoGenerated": False, "costActions": []},
            "audit": {"userId": user_id},
        }

    monkeypatch.setattr("app.routers.business.product_commercialization_service.preview", fake_preview)
    resp = client.post(
        "/api/business/promo-video/plan",
        headers={"x-real-ip": "127.0.0.1"},
        json={
            "productImageUrl": "https://example.com/product.png",
            "action": "copy_preview",
            "requestId": "req-promo-video-plan",
        },
    )

    assert resp.status_code == 200
    assert captured["action"] == "video_preview"
    assert resp.json()["businessKey"] == "promo_video"
    assert resp.json()["underlyingBusinessKey"] == "product_commercialization"
    assert resp.json()["copyGeneration"]["method"] == "skipped_for_video_preview"


def test_product_commercialization_video_rejects_long_target_on_single_segment_endpoint() -> None:
    service = ProductCommercializationService()

    with pytest.raises(HTTPException) as excinfo:
        service.generate_video(
            ProductCommercializationRequest(
                productImageUrl="https://example.com/socks.png",
                productFields={"productNameEn": "Women's knitted woolen socks"},
                targetDurationSeconds=15,
            )
        )

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "PRODUCT_COMMERCIALIZATION_COMPOSE_NOT_READY"


def test_product_commercialization_long_video_defaults_to_segment_asset_package(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured_calls = []
    compose_called = False

    def fake_run_kie_market_task(**kwargs):
        captured_calls.append(kwargs)
        index = len(captured_calls)
        return {
            "status": "succeeded",
            "taskId": f"veo_segment_{index}",
            "state": "success",
            "videoUrls": [f"https://podi.oss-cn-hangzhou.aliyuncs.com/segment-{index}.mp4"],
            "storedAssets": [{"ossUrl": f"https://podi.oss-cn-hangzhou.aliyuncs.com/segment-{index}.mp4", "type": "video"}],
        }

    def fake_compose_segment_videos(**kwargs):
        nonlocal compose_called
        compose_called = True
        return {}

    monkeypatch.setattr(
        "app.services.product_commercialization.integration_test_service",
        SimpleNamespace(run_kie_market_task=fake_run_kie_market_task),
    )
    monkeypatch.setattr(service, "_compose_segment_videos", fake_compose_segment_videos)

    result = service.generate_composed_video(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/socks.png",
            productFields={"productNameEn": "Women's knitted woolen socks"},
            targetDurationSeconds=15,
            confirmedVideoKeyframes=_confirmed_video_keyframes(2),
        )
    )

    assert len(captured_calls) == 2
    assert compose_called is False
    assert result["videoAssetPackage"]["deliveryStatus"] == "assets_ready"
    assert result["videoAssetPackage"]["composition"]["status"] == "skipped"
    assert result["videoAssetPackage"]["composition"]["enabled"] is False
    assert [segment["videoUrl"] for segment in result["videoAssetPackage"]["segmentVideos"]] == [
        "https://podi.oss-cn-hangzhou.aliyuncs.com/segment-1.mp4",
        "https://podi.oss-cn-hangzhou.aliyuncs.com/segment-2.mp4",
    ]
    assert result["videoResult"]["provider"] == "kie"
    assert result["videoResult"]["videoUrls"] == [
        "https://podi.oss-cn-hangzhou.aliyuncs.com/segment-1.mp4",
        "https://podi.oss-cn-hangzhou.aliyuncs.com/segment-2.mp4",
    ]
    assert result["execution"]["costActions"] == ["kie.veo3_fast.video", "kie.veo3_fast.video"]


def test_product_commercialization_composed_video_calls_segments_and_compose(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured_calls = []
    captured_compose = {}

    def fake_run_kie_market_task(**kwargs):
        captured_calls.append(kwargs)
        index = len(captured_calls)
        return {
            "status": "succeeded",
            "taskId": f"veo_segment_{index}",
            "state": "success",
            "videoUrls": [f"https://podi.oss-cn-hangzhou.aliyuncs.com/segment-{index}.mp4"],
            "storedAssets": [{"ossUrl": f"https://podi.oss-cn-hangzhou.aliyuncs.com/segment-{index}.mp4", "type": "video"}],
        }

    def fake_compose_segment_videos(**kwargs):
        captured_compose.update(kwargs)
        return {
            "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/composed.mp4",
            "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/composed.mp4",
            "ossKey": "test/composed.mp4",
            "contentType": "video/mp4",
            "size": 12345,
            "tag": "product-commercialization-compose",
        }

    monkeypatch.setattr(
        "app.services.product_commercialization.integration_test_service",
        SimpleNamespace(run_kie_market_task=fake_run_kie_market_task),
    )
    monkeypatch.setattr(service, "_compose_segment_videos", fake_compose_segment_videos)

    result = service.generate_composed_video(
        ProductCommercializationRequest(
            action="compose_video",
            productImageUrl="https://example.com/socks.png",
            productFields={"productNameEn": "Women's knitted woolen socks"},
            targetDurationSeconds=15,
            confirmedVideoKeyframes=_confirmed_video_keyframes(2),
        )
    )

    assert len(captured_calls) == 2
    assert captured_calls[0]["input_payload"]["duration"] == 8
    assert "Segment 1 of 2" in captured_calls[0]["input_payload"]["prompt"]
    assert "Segment 2 of 2" in captured_calls[1]["input_payload"]["prompt"]
    assert [segment["videoUrl"] for segment in captured_compose["segments"]] == [
        "https://podi.oss-cn-hangzhou.aliyuncs.com/segment-1.mp4",
        "https://podi.oss-cn-hangzhou.aliyuncs.com/segment-2.mp4",
    ]
    assert [item["keepSeconds"] for item in captured_compose["trim_plan"]] == [8, 7]
    assert result["videoResult"]["provider"] == "kie+ffmpeg"
    assert result["videoResult"]["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/composed.mp4"]
    assert result["execution"]["costActions"] == ["kie.veo3_fast.video", "kie.veo3_fast.video", "ffmpeg.compose"]


def test_product_commercialization_composed_video_retries_failed_segment(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured_calls = []

    def fake_run_kie_market_task(**kwargs):
        captured_calls.append(kwargs)
        if len(captured_calls) == 1:
            return {
                "status": "failed",
                "taskId": "veo_segment_failed_once",
                "state": "fail",
                "raw": {
                    "response": {
                        "data": {
                            "successFlag": 2,
                            "errorCode": "KIE_TEMPORARY_FAILURE",
                            "errorMessage": "temporary upstream generation failure",
                        }
                    }
                },
            }
        index = len(captured_calls)
        return {
            "status": "succeeded",
            "taskId": f"veo_segment_{index}",
            "state": "success",
            "videoUrls": [f"https://podi.oss-cn-hangzhou.aliyuncs.com/segment-{index}.mp4"],
            "storedAssets": [{"ossUrl": f"https://podi.oss-cn-hangzhou.aliyuncs.com/segment-{index}.mp4"}],
        }

    monkeypatch.setattr(
        "app.services.product_commercialization.integration_test_service",
        SimpleNamespace(run_kie_market_task=fake_run_kie_market_task),
    )
    monkeypatch.setattr(
        service,
        "_compose_segment_videos",
        lambda **kwargs: {
            "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/composed.mp4",
            "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/composed.mp4",
            "ossKey": "test/composed.mp4",
            "contentType": "video/mp4",
            "size": 12345,
        },
    )

    result = service.generate_composed_video(
        ProductCommercializationRequest(
            action="compose_video",
            productImageUrl="https://example.com/socks.png",
            productFields={"productNameEn": "Women's knitted woolen socks"},
            targetDurationSeconds=15,
            confirmedVideoKeyframes=_confirmed_video_keyframes(2),
        )
    )

    assert len(captured_calls) == 3
    assert "Segment 1 of 2" in captured_calls[0]["input_payload"]["prompt"]
    assert "Segment 1 of 2" in captured_calls[1]["input_payload"]["prompt"]
    assert "Segment 2 of 2" in captured_calls[2]["input_payload"]["prompt"]
    assert captured_calls[0]["poll_timeout"] >= 300
    assert result["status"] == "succeeded"


def test_product_commercialization_video_calls_veo_fast(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured = {}

    def fake_run_kie_market_task(**kwargs):
        captured.update(kwargs)
        return {
            "status": "succeeded",
            "taskId": "veo_task_1",
            "state": "success",
            "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/video.mp4"],
            "storedAssets": [{"ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/video.mp4", "type": "video"}],
        }

    monkeypatch.setattr(
        "app.services.product_commercialization.integration_test_service",
        SimpleNamespace(run_kie_market_task=fake_run_kie_market_task),
    )

    result = service.generate_video(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/socks.png",
            productFields={"productNameEn": "Women's knitted woolen socks"},
            aspectRatio="9:16",
            durationSeconds=8,
            confirmedVideoKeyframes=_confirmed_video_keyframes(),
        )
    )

    assert captured["endpoint"] == "/api/v1/veo/generate"
    assert captured["status_endpoint"] == "/api/v1/veo/record-info"
    assert captured["model"] == "veo3_fast"
    assert captured["input_payload"]["imageUrls"] == [
        "https://podi.oss-cn-hangzhou.aliyuncs.com/confirmed-shot-1-first.png"
    ]
    assert captured["input_payload"]["aspectRatio"] == "9:16"
    assert captured["input_payload"]["duration"] == 8
    assert captured["input_payload"]["enableFallback"] is False
    assert result["execution"]["costActions"] == ["kie.veo3_fast.video"]
    assert result["videoResult"]["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/video.mp4"]


def test_product_commercialization_video_uses_user_edited_prompt(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured = {}
    edited_prompt = "Use a slow close-up pan over the floral blanket texture, then reveal the full sofa throw. No text."

    def fake_run_kie_market_task(**kwargs):
        captured.update(kwargs)
        return {
            "status": "succeeded",
            "taskId": "veo_edited_prompt",
            "state": "success",
            "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/edited-prompt.mp4"],
            "storedAssets": [{"ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/edited-prompt.mp4", "type": "video"}],
        }

    monkeypatch.setattr(
        "app.services.product_commercialization.integration_test_service",
        SimpleNamespace(run_kie_market_task=fake_run_kie_market_task),
    )

    result = service.generate_video(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/blanket.png",
            productFields={"productNameEn": "Floral plush throw blanket"},
            videoPromptOverride=edited_prompt,
            confirmedVideoKeyframes=_confirmed_video_keyframes(),
        )
    )

    assert captured["input_payload"]["prompt"] == edited_prompt
    assert result["videoPlan"]["videoPrompt"] == edited_prompt
    assert result["videoPlan"]["promptSource"] == "user_edited"
    assert result["videoResult"]["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/edited-prompt.mp4"]


def test_product_commercialization_video_can_use_vidu_executor(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured = {}
    composition_calls = []

    def fake_run_vidu_video_task(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "vidu",
            "model": "viduq3-turbo",
            "status": "succeeded",
            "taskId": "vidu_task_1",
            "state": "success",
            "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/vidu-video.mp4"],
            "storedAssets": [{"ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/vidu-video.mp4", "type": "video"}],
        }

    monkeypatch.setattr(
        "app.services.product_commercialization.integration_test_service",
        SimpleNamespace(run_vidu_video_task=fake_run_vidu_video_task),
    )

    def fail_generate_normalized_first_frame(**kwargs):
        raise AssertionError("video_generate must not create keyframes without user confirmation")

    monkeypatch.setattr(service, "_generate_normalized_first_frame", fail_generate_normalized_first_frame)

    def fake_compose_opening_hold_with_segment(**kwargs):
        composition_calls.append(kwargs)
        return {
            "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/hero-composed.mp4",
            "contentType": "video/mp4",
            "mode": "opening_hold_plus_vidu_segment",
            "introHoldSeconds": 2.0,
            "tailSeconds": 3.0,
        }

    monkeypatch.setattr(service, "_compose_opening_hold_with_segment", fake_compose_opening_hold_with_segment)

    result = service.generate_video(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/socks.png",
            productFields={"productNameEn": "Women's knitted woolen socks"},
            executorId="executor_vidu_default",
            confirmedVideoKeyframes=_confirmed_video_keyframes(),
        )
    )

    assert captured["endpoint"] == "/ent/v2/img2video"
    assert captured["status_endpoint"] == "/ent/v2/tasks/{task_id}/creations"
    assert captured["model"] == "viduq3-turbo"
    assert captured["input_payload"]["images"] == [
        "https://podi.oss-cn-hangzhou.aliyuncs.com/confirmed-shot-1-first.png"
    ]
    assert captured["input_payload"]["duration"] == 5
    assert "Vidu product framing guardrails" in captured["input_payload"]["prompt"]
    assert "complete product silhouette" in captured["input_payload"]["prompt"]
    assert "do not crop product handles" in captured["input_payload"]["prompt"]
    assert "aspectRatio" not in captured["input_payload"]
    assert captured["input_payload"]["audio"] is False
    assert captured["input_payload"]["bgm"] is False
    assert result["videoPlan"]["provider"] == "vidu"
    assert result["videoPlan"]["model"] == "viduq3-turbo"
    assert result["videoPlan"]["aspectPolicy"]["mode"] == "normalized_first_frame"
    assert result["videoPlan"]["aspectPolicy"]["executionAspectRatio"] == "16:9"
    assert result["videoPlan"]["targetDurationSeconds"] == 5
    assert composition_calls[0]["first_frame_url"].endswith("confirmed-shot-1-first.png")
    assert composition_calls[0]["segment_video_url"].endswith("vidu-video.mp4")
    assert result["videoAssetPackage"]["deliveryStatus"] == "composed_ready"
    assert result["videoAssetPackage"]["composition"]["videoUrl"].endswith("hero-composed.mp4")
    assert result["videoResult"]["provider"] == "vidu+ffmpeg"
    assert result["videoResult"]["model"] == "viduq3-turbo"
    assert result["execution"]["imageGenerated"] is False
    assert result["execution"]["costActions"] == ["vidu.viduq3_turbo.video", "ffmpeg.compose"]
    assert result["videoAssetPackage"]["keyframes"][0]["imageUrl"].endswith("confirmed-shot-1-first.png")
    assert result["videoResult"]["segments"][0]["referenceImageUrl"].endswith("confirmed-shot-1-first.png")
    assert result["videoResult"]["videoUrls"] == [
        "https://podi.oss-cn-hangzhou.aliyuncs.com/hero-composed.mp4",
        "https://podi.oss-cn-hangzhou.aliyuncs.com/vidu-video.mp4",
    ]


def test_product_commercialization_vidu_keyframe_generation_uses_asset_package_needs(monkeypatch) -> None:
    service = ProductCommercializationService()
    generated_roles: list[str] = []

    def fake_generate_video_director_plan(**kwargs):
        return (
            {
                "directorBrief": {
                    "productUnderstanding": "printed throw blanket",
                    "commercialGoal": "show the full product for a marketplace listing",
                    "targetAudience": "home decor buyers",
                },
                "storyboard": [
                    {
                        "shot": 1,
                        "durationSeconds": 5,
                        "keepSeconds": 5,
                        "subject": "printed throw blanket",
                        "scene": "clean studio sweep",
                        "goal": "show the full blanket silhouette",
                        "cameraMovement": "slow push-in",
                        "composition": "wide product-safe frame",
                        "prompt": "Show the full blanket in a clean studio scene.",
                        "firstFramePrompt": "Open with the complete blanket visible inside the frame.",
                        "lastFramePrompt": "End on a stable full-product hero frame.",
                    }
                ],
                "keyframePlan": [
                    {
                        "role": "last_frame",
                        "shot": 1,
                        "required": True,
                        "prompt": "End on a stable full-product hero frame.",
                    }
                ],
                "videoPrompt": "Create a clean marketplace product video for the blanket.",
                "negativePrompt": "text, watermark, cropped product",
            },
            {"provider": "test", "model": "video-director-test", "fallback": False},
        )

    def fake_generate_video_keyframe_image(**kwargs):
        role = kwargs["role"]
        generated_roles.append(role)
        return {
            "role": role,
            "status": "succeeded",
            "shot": kwargs["segment_index"],
            "segmentIndex": kwargs["segment_index"],
            "source": "test",
            "imageUrl": f"https://podi.oss-cn-hangzhou.aliyuncs.com/{role}.png",
            "prompt": kwargs["prompt"],
        }

    monkeypatch.setattr(service, "_generate_video_director_plan", fake_generate_video_director_plan)
    monkeypatch.setattr(service, "_generate_video_keyframe_image", fake_generate_video_keyframe_image)

    result = service.generate_video_keyframes(
        ProductCommercializationRequest(
            action="video_keyframes",
            productImageUrl="https://example.com/blanket.png",
            productFields={"productNameEn": "Printed throw blanket"},
            executorId="executor_vidu_default",
        )
    )

    assert generated_roles == ["last_frame", "normalized_first_frame"]
    needs = result["videoAssetPackagePlan"]["keyframeNeeds"]
    assert {item["role"] for item in needs} >= {"last_frame", "normalized_first_frame"}
    assert result["videoAssetPackagePlan"]["shotPackages"][0]["confirmationRequired"] is True
    assert {item["role"] for item in result["videoResult"]["keyframes"]} >= {"last_frame", "normalized_first_frame"}


def test_product_commercialization_video_uses_confirmed_keyframe_as_reference(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured = {}
    composition_calls = []

    def fake_run_vidu_video_task(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "vidu",
            "model": "viduq3-turbo",
            "status": "succeeded",
            "taskId": "vidu_confirmed_keyframe",
            "state": "success",
            "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/vidu-confirmed.mp4"],
            "storedAssets": [{"ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/vidu-confirmed.mp4", "type": "video"}],
        }

    monkeypatch.setattr(
        "app.services.product_commercialization.integration_test_service",
        SimpleNamespace(run_vidu_video_task=fake_run_vidu_video_task),
    )

    def fail_generate_normalized_first_frame(**kwargs):
        raise AssertionError("confirmed keyframe should prevent regenerated first frame")

    monkeypatch.setattr(service, "_generate_normalized_first_frame", fail_generate_normalized_first_frame)

    def fake_compose_opening_hold_with_segment(**kwargs):
        composition_calls.append(kwargs)
        return {
            "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/confirmed-composed.mp4",
            "contentType": "video/mp4",
            "mode": "opening_hold_plus_vidu_segment",
        }

    monkeypatch.setattr(service, "_compose_opening_hold_with_segment", fake_compose_opening_hold_with_segment)

    confirmed_frame_url = "https://podi.oss-cn-hangzhou.aliyuncs.com/confirmed-shot-1.png"
    result = service.generate_video(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/socks.png",
            productFields={"productNameEn": "Women's knitted woolen socks"},
            executorId="executor_vidu_default",
            confirmedVideoKeyframes=[
                {
                    "role": "first_frame",
                    "shot": "1",
                    "segmentIndex": 1,
                    "imageUrl": confirmed_frame_url,
                    "confirmed": True,
                },
                {
                    "role": "last_frame",
                    "shot": "1",
                    "segmentIndex": 1,
                    "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/confirmed-shot-1-last.png",
                    "confirmed": True,
                },
            ],
        )
    )

    assert captured["input_payload"]["images"] == [confirmed_frame_url]
    assert composition_calls[0]["first_frame_url"] == confirmed_frame_url
    assert result["execution"]["imageGenerated"] is False
    assert result["execution"]["costActions"] == ["vidu.viduq3_turbo.video", "ffmpeg.compose"]
    assert result["videoAssetPackage"]["keyframes"][0]["imageUrl"] == confirmed_frame_url
    assert result["videoAssetPackage"]["keyframes"][0]["confirmed"] is True
    assert result["videoResult"]["segments"][0]["referenceImageUrl"] == confirmed_frame_url
    assert result["videoPlan"]["confirmedKeyframesUsed"][0]["imageUrl"] == confirmed_frame_url


def test_product_commercialization_first_frame_prompt_blocks_framed_layout() -> None:
    service = ProductCommercializationService()

    prompt = service._build_normalized_first_frame_prompt(
        video_plan={"directorBrief": {"productUnderstanding": "a printed cotton tote bag"}},
        shot={
            "scene": "coastal lifestyle tabletop",
            "goal": "show the full product and print",
            "composition": "wide hero shot",
            "firstFramePrompt": "Open on the tote bag standing upright on a table.",
        },
        prompt="Create a clean product video opening frame.",
        aspect_ratio="16:9",
        segment_index=1,
    )

    assert "edge-to-edge commercial scene" in prompt
    assert "smaller framed picture" in prompt
    assert "white mat" in prompt
    assert "do not crop handles" in prompt


def test_product_commercialization_vidu_execution_prompt_preserves_full_product() -> None:
    service = ProductCommercializationService()

    prompt = service._build_video_execution_prompt(
        provider="vidu",
        prompt="Show the tote bag with a slow camera move.",
        shot={"durationSeconds": 8},
        video_plan={"scenario": "product_showcase_short", "durationSeconds": 8},
    )

    assert prompt.startswith("Show the tote bag")
    assert "Vidu product framing guardrails" in prompt
    assert "first 2 seconds" in prompt
    assert "avoid aggressive zoom" in prompt
    assert "End on a stable medium product frame" in prompt
    assert "inset image" in prompt
    assert "Avoid large empty padding" in prompt


def test_product_commercialization_trims_generated_white_mat_before_canvas() -> None:
    service = ProductCommercializationService()
    source = Image.new("RGB", (1000, 1000), (250, 250, 250))
    content = Image.new("RGB", (1000, 420), (120, 180, 210))
    source.paste(content, (0, 290))

    trimmed = service._trim_large_light_border(source)

    assert trimmed.width == 1000
    assert trimmed.height < 460
    assert trimmed.height > 400


def test_product_commercialization_does_not_trim_all_white_frame() -> None:
    service = ProductCommercializationService()
    source = Image.new("RGB", (800, 800), (250, 250, 250))

    trimmed = service._trim_large_light_border(source)

    assert trimmed.size == source.size


def test_product_commercialization_first_frame_canvas_normalizes_to_target_ratio(monkeypatch) -> None:
    service = ProductCommercializationService()
    source = Image.new("RGB", (600, 1000), (220, 120, 60))
    buffer = BytesIO()
    source.save(buffer, format="PNG")
    uploads: list[dict[str, object]] = []

    class FakeResponse:
        content = buffer.getvalue()
        headers = {"Content-Type": "image/png"}

        def raise_for_status(self):
            return None

    def fake_upload_generated_image_bytes(**kwargs):
        uploads.append(kwargs)
        return {
            "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/normalized.png",
            "ossKey": "normalized.png",
            "contentType": kwargs["content_type"],
        }

    monkeypatch.setattr("app.services.product_commercialization.httpx.get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(
        "app.services.product_commercialization.media_ingest_service.upload_generated_image_bytes",
        fake_upload_generated_image_bytes,
    )

    result = service._normalize_first_frame_canvas(
        image_url="https://example.com/generated-first-frame.png",
        aspect_ratio="16:9",
        request_id="req-test",
        segment_index=1,
        user_id="tester",
    )

    uploaded = Image.open(BytesIO(uploads[0]["data"]))
    assert uploaded.size == (1280, 720)
    assert result["width"] == 1280
    assert result["height"] == 720
    assert result["ossUrl"].endswith("normalized.png")


def test_product_commercialization_visual_generation_defaults_to_gpt_image2(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured = {}

    def fake_invoke(**kwargs):
        captured.update(kwargs)
        return AbilityInvokeResponse(
            abilityId="openai_gpt_image_2_edit",
            provider="openai",
            status="succeeded",
            requestId="gpt-image2-visual-test",
            images=[AbilityOutputAsset(ossUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/visual.png", type="image")],
        )

    monkeypatch.setattr(
        "app.services.product_commercialization.ability_invocation_service",
        SimpleNamespace(invoke=fake_invoke),
    )

    result = service.generate_visual(
        ProductCommercializationRequest(
            productImageUrl="https://example.com/product.png",
            productFields={"productNameEn": "Floral throw blanket", "material": "soft plush"},
            visualScenes=["listing-main"],
        )
    )

    assert captured["ability_id"] == "openai_gpt_image_2_edit"
    ability_payload = captured["payload"]
    assert ability_payload.inputs["model"] == "gpt-image-2"
    assert ability_payload.inputs["size"] == "auto"
    assert ability_payload.inputs["image_url"] == "https://example.com/product.png"
    assert ability_payload.imageUrl == "https://example.com/product.png"
    assert ability_payload.metadata["routeType"] == "image2_quality_first"
    assert captured["source"] == "product-commercialization-visual"
    assert result["imageResult"]["provider"] == "openai"
    assert result["imageResult"]["model"] == "gpt-image-2"
    assert result["imageResult"]["imageUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/visual.png"]


def test_product_commercialization_visual_prompt_does_not_inherit_brief_product_identity() -> None:
    prompt = _build_visual_prompt(
        product_card={"sourceFacts": {"productNameEn": "Floral printed lightweight hooded jacket"}},
        resolved_product_facts={
            "facts": {
                "productNameEn": "Preppy Western Coastal Print 100% Cotton Tote Bag",
                "material": "100% cotton canvas",
                "keywords": ["western coastal print", "reusable tote bag"],
            }
        },
        copy_package={
            "listingTitle": "Preppy Western Coastal Print 100% Cotton Tote Bag",
            "bulletPoints": ["100% cotton canvas", "Reusable shoulder tote"],
            "adShortCopy": ["A western coastal tote for daily errands."],
        },
        visual_brief={
            "id": "social-ad-cover",
            "label": "Social ad cover",
            "usage": "Social ad cover for ecommerce marketing",
            "prompt": "Create a clean lifestyle ad cover for Floral printed lightweight hooded jacket.",
            "riskNotes": ["Avoid overpromising performance or sustainability."],
            "linkedCopy": ["adShortCopy"],
        },
        output_language="en-US",
        market_region="US",
        extra_prompt="Beach lifestyle setting.",
    )

    assert "Preppy Western Coastal Print 100% Cotton Tote Bag" in prompt
    assert "Floral printed lightweight hooded jacket" not in prompt
    assert "Brief hint" not in prompt
    assert "Visual scenario only" in prompt
    assert "Do not inherit product identity" in prompt
    assert "no letterboxing" in prompt


def test_product_commercialization_runs_submit_and_poll(monkeypatch) -> None:
    def fake_generate_video(payload, *, user_id=None):
        return {
            "requestId": payload.requestId or "pc-run-test",
            "businessKey": "product_commercialization",
            "version": "product-commercialization-mvp-v1",
            "status": "succeeded",
            "generatedAt": "2026-06-09T00:00:00+00:00",
            "strategyProfile": "default_pod_profile",
            "outputLanguage": "en-US",
            "marketRegion": "US",
            "copyScenarios": ["listing_title"],
            "productCard": {"confidence": 0.9, "missingFields": [], "inferredFacts": {}},
            "copyPackage": {"listingTitle": "POD socks listing title"},
            "visualAssetPlan": {"mode": "recommendation"},
            "videoPlan": {"model": "veo3_fast", "targetDurationSeconds": 8},
            "review": {"score": 90},
            "execution": {"videoGenerated": True, "costActions": ["kie.veo3_fast.video"]},
            "videoUrls": ["https://tempfile.aiquickdraw.com/v/transient.mp4"],
            "videoResult": {
                "provider": "kie",
                "model": "veo3_fast",
                "status": "succeeded",
                "videoUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/product-video.mp4"],
                "resultUrls": ["https://tempfile.aiquickdraw.com/v/transient.mp4"],
                "raw": {
                    "response": {
                        "data": {
                            "response": {
                                "resultUrls": ["https://tempfile.aiquickdraw.com/v/transient.mp4"]
                            }
                        }
                    }
                },
            },
        }

    monkeypatch.setattr(
        "app.services.business_runs.product_commercialization_service.generate_video",
        fake_generate_video,
    )

    resp = client.post(
        "/api/business/product-commercialization/runs",
        headers={"x-real-ip": "127.0.0.1"},
        json={
            "productImageUrl": "https://example.com/socks.png",
            "productFields": {"productNameEn": "POD socks"},
            "requestId": "pc-run-test",
        },
    )

    assert resp.status_code == 200
    submitted = resp.json()
    run_id = submitted["runId"]
    assert submitted["businessKey"] == "product_commercialization"
    assert submitted["taskId"] == run_id
    assert submitted["status"] in {"queued", "running"}

    polled = None
    for _ in range(40):
        poll_resp = client.post(
            "/api/business/runs/get",
            headers={"x-real-ip": "127.0.0.1"},
            json={"runId": run_id, "detail": "full"},
        )
        assert poll_resp.status_code == 200
        polled = poll_resp.json()
        if polled["status"] == "succeeded":
            break
        time.sleep(0.05)

    assert polled is not None
    assert polled["status"] == "succeeded"
    assert polled["taskId"] == run_id
    assert polled["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/product-video.mp4"]
    assert polled["billingStatus"] == "billable"
    assert polled["billingUnit"] == "kie_veo3_fast_video_segment"
    assert polled["quotaUnits"] == 1
    assert polled["costBreakdown"]["pricingStatus"] == "quota_only_mvp"
    assert polled["costBreakdown"]["primaryCostAction"] == "kie.veo3_fast.video"
    assert polled["resultPayload"]["videoResult"]["videoUrls"] == [
        "https://podi.oss-cn-hangzhou.aliyuncs.com/product-video.mp4"
    ]

    alias_resp = client.post(
        "/api/business/runs/get",
        headers={"x-real-ip": "127.0.0.1"},
        json={"taskId": run_id},
    )
    assert alias_resp.status_code == 200
    assert alias_resp.json()["runId"] == run_id


def test_product_commercialization_keyframe_run_finishes_with_images(monkeypatch) -> None:
    def fake_generate_video_keyframes(payload, *, user_id=None):
        keyframe_url = "https://podi.oss-cn-hangzhou.aliyuncs.com/product-video-keyframe.png"
        return {
            "requestId": payload.requestId or "pc-keyframe-run-test",
            "businessKey": "product_commercialization",
            "version": "product-commercialization-mvp-v1",
            "status": "succeeded",
            "generatedAt": "2026-06-13T00:00:00+00:00",
            "strategyProfile": "default_pod_profile",
            "outputLanguage": "en-US",
            "marketRegion": "US",
            "copyScenarios": [],
            "productCard": {"confidence": 0.9, "missingFields": [], "inferredFacts": {}},
            "copyPackage": {},
            "visualAssetPlan": {"mode": "recommendation"},
            "videoPlan": {"model": "viduq3-turbo", "targetDurationSeconds": 15, "keyframePlan": [{"role": "first_frame"}]},
            "videoAssetPackage": {
                "deliveryStatus": "keyframes_ready",
                "script": {"status": "succeeded", "editable": True, "text": "show product"},
                "storyboard": [],
                "keyframes": [
                    {
                        "role": "first_frame",
                        "status": "succeeded",
                        "imageUrl": keyframe_url,
                        "ossUrl": keyframe_url,
                    }
                ],
                "segmentVideos": [],
                "composition": {"enabled": False, "status": "skipped"},
            },
            "review": {"score": 90},
            "execution": {
                "imageGenerated": True,
                "videoGenerated": False,
                "costActions": ["openai.gpt_image_2.image"],
            },
            "videoResult": {
                "provider": "openai",
                "model": "gpt-image-2",
                "status": "keyframes_ready",
                "videoUrls": [],
                "keyframes": [{"imageUrl": keyframe_url}],
            },
        }

    monkeypatch.setattr(
        "app.services.business_runs.product_commercialization_service.generate_video_keyframes",
        fake_generate_video_keyframes,
    )

    resp = client.post(
        "/api/business/product-commercialization/runs",
        headers={"x-real-ip": "127.0.0.1"},
        json={
            "action": "video_keyframes",
            "productImageUrl": "https://example.com/socks.png",
            "productFields": {"productNameEn": "POD socks"},
            "requestId": "pc-keyframe-run-test",
        },
    )

    assert resp.status_code == 200
    run_id = resp.json()["runId"]
    polled = None
    for _ in range(40):
        poll_resp = client.post(
            "/api/business/runs/get",
            headers={"x-real-ip": "127.0.0.1"},
            json={"runId": run_id, "detail": "full"},
        )
        assert poll_resp.status_code == 200
        polled = poll_resp.json()
        if polled["status"] == "succeeded":
            break
        time.sleep(0.05)

    assert polled is not None
    assert polled["status"] == "succeeded"
    assert polled["imageUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/product-video-keyframe.png"]
    assert not polled.get("videoUrls")
    assert polled["billingStatus"] == "billable"
    assert polled["billingUnit"] == "openai.gpt_image_2.image"
    assert polled["quotaUnits"] == 1
    assert polled["costBreakdown"]["policy"] == "one_quota_per_generated_video_keyframe"
    assert polled["resultPayload"]["videoAssetPackage"]["deliveryStatus"] == "keyframes_ready"
    with get_session() as session:
        step = session.execute(
            select(BusinessRunStep).where(
                BusinessRunStep.run_id == run_id,
                BusinessRunStep.step_id == "product_commercialization_keyframes",
            )
        ).scalar_one()
        assert step.status == "succeeded"
        assert step.result_payload["videoAssetPackage"]["deliveryStatus"] == "keyframes_ready"


def test_product_commercialization_keyframe_run_failure_keeps_structured_error(monkeypatch) -> None:
    def fake_generate_video_keyframes(payload, *, user_id=None):
        raise HTTPException(
            status_code=502,
            detail={
                "detail": {
                    "success": False,
                    "errorCode": "VENDOR_API_CLIENT_FORBIDDEN",
                    "message": "vendor-api-ops only accepts requests from backend allowlisted hosts.",
                    "suggestion": "Route calls through the backend service or add the backend host to VENDOR_API_ALLOWED_CLIENTS.",
                }
            },
        )

    monkeypatch.setattr(
        "app.services.business_runs.product_commercialization_service.generate_video_keyframes",
        fake_generate_video_keyframes,
    )

    resp = client.post(
        "/api/business/product-commercialization/runs",
        headers={"x-real-ip": "127.0.0.1"},
        json={
            "action": "video_keyframes",
            "productImageUrl": "https://example.com/socks.png",
            "productFields": {"productNameEn": "POD socks"},
            "requestId": "pc-keyframe-run-failed-test",
        },
    )

    assert resp.status_code == 200
    run_id = resp.json()["runId"]
    polled = None
    for _ in range(40):
        poll_resp = client.post(
            "/api/business/runs/get",
            headers={"x-real-ip": "127.0.0.1"},
            json={"runId": run_id, "detail": "full"},
        )
        assert poll_resp.status_code == 200
        polled = poll_resp.json()
        if polled["status"] == "failed":
            break
        time.sleep(0.05)

    assert polled is not None
    assert polled["status"] == "failed"
    assert polled["errorMessage"] == "VENDOR_API_CLIENT_FORBIDDEN"
    assert polled["resultPayload"]["errorCode"] == "VENDOR_API_CLIENT_FORBIDDEN"
    assert polled["resultPayload"]["businessErrorCode"] == "PRODUCT_COMMERCIALIZATION_KEYFRAME_GENERATION_FAILED"
    assert polled["resultPayload"]["suggestion"] == (
        "Route calls through the backend service or add the backend host to VENDOR_API_ALLOWED_CLIENTS."
    )
    assert polled["resultPayload"]["detail"]["errorCode"] == "VENDOR_API_CLIENT_FORBIDDEN"
    with get_session() as session:
        step = session.execute(
            select(BusinessRunStep).where(
                BusinessRunStep.run_id == run_id,
                BusinessRunStep.step_id == "product_commercialization_keyframes",
            )
        ).scalar_one()
        assert step.status == "failed"
        assert step.error_message == "VENDOR_API_CLIENT_FORBIDDEN"
        assert step.result_payload["errorCode"] == "VENDOR_API_CLIENT_FORBIDDEN"


def test_product_commercialization_run_rejects_invalid_action() -> None:
    resp = client.post(
        "/api/business/product-commercialization/runs",
        headers={"x-real-ip": "127.0.0.1"},
        json={
            "productImageUrl": "https://example.com/product.png",
            "productFields": {"productNameEn": "POD product"},
            "action": "visual-generate-typo",
        },
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "PRODUCT_COMMERCIALIZATION_ACTION_INVALID"


def test_product_commercialization_keyframe_error_unwraps_upstream_detail() -> None:
    exc = HTTPException(
        status_code=403,
        detail={
            "detail": {
                "detail": {
                    "success": False,
                    "errorCode": "VENDOR_API_CLIENT_FORBIDDEN",
                    "message": "vendor-api-ops only accepts requests from backend allowlisted hosts.",
                    "suggestion": "Route calls through the backend service or add the backend host to VENDOR_API_ALLOWED_CLIENTS.",
                }
            }
        },
    )

    detail = _business_http_exception_detail(
        exc,
        fallback_code="PRODUCT_COMMERCIALIZATION_KEYFRAME_GENERATION_FAILED",
    )

    assert detail == {
        "errorCode": "VENDOR_API_CLIENT_FORBIDDEN",
        "message": "vendor-api-ops only accepts requests from backend allowlisted hosts.",
        "businessErrorCode": "PRODUCT_COMMERCIALIZATION_KEYFRAME_GENERATION_FAILED",
        "suggestion": "Route calls through the backend service or add the backend host to VENDOR_API_ALLOWED_CLIENTS.",
    }


def test_product_commercialization_internal_run_is_not_route_missing() -> None:
    row = BusinessRun(
        id="pc-failed-route-check",
        business_key="product_commercialization",
        version="product-commercialization-mvp-v1",
        status="failed",
        source="business-api",
        error_message="PRODUCT_COMMERCIALIZATION_VIDEO_GENERATION_FAILED",
    )
    service = BusinessRunService()

    assert service._build_usage_run_issue_summary(row)["category"] == "executor"
    assert service._build_run_issue_summary(row)["category"] == "executor"

    product_3d_row = BusinessRun(
        id="p3d-failed-route-check",
        business_key="product_3d_render_video",
        version="p3d-render-video-v1",
        status="failed",
        source="business-api",
        error_message="PRODUCT_3D_RENDER_VIDEO_RENDER_RUN_FAILED",
    )
    assert service._build_usage_run_issue_summary(product_3d_row)["category"] == "executor"
    assert service._build_run_issue_summary(product_3d_row)["category"] == "executor"


def test_business_openapi_exposes_product_commercialization() -> None:
    resp = client.get("/api/business/openapi.json", headers={"x-real-ip": "127.0.0.1"})
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/business/product-commercialization/runs" in paths
    assert "/api/business/product-commercialization/preview" in paths
    assert "/api/business/product-commercialization/video" in paths
    assert "/api/business/product-commercialization/video-keyframes" in paths
    assert "/api/business/product-commercialization/video-compose" in paths
    assert "/api/business/promo-video/plan" in paths
    assert "/api/business/promo-video/keyframes/runs" in paths
    assert "/api/business/promo-video/runs" in paths
    assert "/api/business/promo-video/compose/runs" in paths
    assert "/api/business/product-3d-render-video/catalog" in paths
    assert "/api/business/product-3d-render-video/preview" in paths
    assert "/api/business/product-3d-render-video/runs" in paths
    runs_schema = paths["/api/business/product-commercialization/runs"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert runs_schema["x-podi-required-one-of"] == ["productImageUrl", "productImages"]
    preview_schema = paths["/api/business/product-commercialization/preview"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert preview_schema["properties"]["outputLanguage"]["enum"] == ["en-US", "zh-CN", "bilingual"]
    assert preview_schema["properties"]["visualSupportMode"]["enum"] == ["none", "recommendation", "generate"]
    assert "video_keyframes" in preview_schema["properties"]["action"]["enum"]
    assert preview_schema["properties"]["durationSeconds"]["minimum"] == 1
    assert "productImages" in preview_schema["properties"]
    assert "enum" not in preview_schema["properties"]["durationSeconds"]
    assert preview_schema["properties"]["targetDurationSeconds"]["minimum"] == 1
    assert preview_schema["properties"]["targetDurationSeconds"]["maximum"] == 60
    promo_plan_schema = paths["/api/business/promo-video/plan"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert promo_plan_schema["x-podi-fixed-action"] == "video_preview"
    promo_plan_response_schema = paths["/api/business/promo-video/plan"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert promo_plan_response_schema["properties"]["businessKey"]["enum"] == ["promo_video"]
    assert promo_plan_response_schema["properties"]["underlyingBusinessKey"]["enum"] == ["product_commercialization"]
    promo_keyframes_schema = paths["/api/business/promo-video/keyframes/runs"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert promo_keyframes_schema["x-podi-fixed-action"] == "video_keyframes"
    assert promo_keyframes_schema["x-podi-required-one-of"] == ["productImageUrl", "productImages"]
    promo_video_schema = paths["/api/business/promo-video/runs"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert promo_video_schema["x-podi-fixed-action"] == "video_generate"
    assert "videoPlanningContext" in promo_video_schema["properties"]
    assert "shotPreference" in promo_video_schema["properties"]["videoPlanningContext"]["properties"]
    assert "confirmedVideoKeyframes" in promo_video_schema["properties"]
    assert "PRODUCT_COMMERCIALIZATION_KEYFRAMES_UNCONFIRMED" in paths["/api/business/promo-video/runs"]["post"][
        "responses"
    ]["400"]["x-podi-errors"]
    assert promo_video_schema["properties"]["confirmedVideoKeyframes"]["items"]["properties"]["segmentIndex"]["type"] == "integer"
    promo_compose_schema = paths["/api/business/promo-video/compose/runs"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert promo_compose_schema["x-podi-fixed-action"] == "compose_video"
    product_3d_catalog_schema = paths["/api/business/product-3d-render-video/catalog"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    assert product_3d_catalog_schema["properties"]["models"]["description"] == "可用 3D 模型与材质槽清单。"
    assert (
        product_3d_catalog_schema["properties"]["scenePresets"]["description"]
        == "可用场景预设、场景资产、renderElements 场景模型结构、融合规则、sceneVisualAcceptance 验收合同和外部高保真候选。"
    )
    assert (
        product_3d_catalog_schema["properties"]["sceneAssetSources"]["description"]
        == "可用于高保真场景资产入库的来源、授权、资产级 candidateAssets、场景模型候选、当前状态和入库门禁；业务方只读，不作为执行入参。"
    )
    assert (
        product_3d_catalog_schema["properties"]["cameraDistances"]["description"]
        == "镜头远近档位，包含完整入画比例、安全边距和 cameraZ/FOV 参考。"
    )
    product_3d_schema = paths["/api/business/product-3d-render-video/preview"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert product_3d_schema["properties"]["modelKey"]["enum"] == ["cup_1660", "backpack_2551"]
    assert product_3d_schema["properties"]["outputMode"]["enum"] == ["plan_only"]
    product_3d_response_schema = paths["/api/business/product-3d-render-video/preview"]["post"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    assert "scene.renderElements" in product_3d_response_schema["properties"]["renderPlan"]["description"]
    assert "sceneVisualAcceptance" in product_3d_response_schema["properties"]["renderPlan"]["description"]
    product_3d_run_schema = paths["/api/business/product-3d-render-video/runs"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert product_3d_run_schema["properties"]["outputMode"]["enum"] == ["render_video"]
    product_3d_run_errors = paths["/api/business/product-3d-render-video/runs"]["post"]["responses"]
    assert "PRODUCT_3D_RENDER_VIDEO_RENDER_RUN_NOT_READY" not in product_3d_run_errors.get("409", {}).get(
        "x-podi-errors",
        [],
    )
    assert "PRODUCT_3D_RENDER_VIDEO_TEXTURE_REQUIRED" in product_3d_run_errors["400"]["x-podi-errors"]
    assert "BACKGROUND_WORKERS_DISABLED" in product_3d_run_errors["503"]["x-podi-errors"]
    assert "PRODUCT_3D_RENDER_VIDEO_TEXTURE_LOAD_FAILED" in product_3d_run_errors["500"]["x-podi-errors"]
    assert "PRODUCT_3D_RENDER_VIDEO_FFMPEG_MISSING" in product_3d_run_errors["500"]["x-podi-errors"]
