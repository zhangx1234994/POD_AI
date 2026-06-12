import json
import time
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models.integration import BusinessRun
from app.schemas.abilities import AbilityInvokeResponse, AbilityOutputAsset
from app.schemas.business import Product3DRenderVideoRequest, ProductCommercializationRequest
from app.services.business_runs import BusinessRunService
from app.services.product_3d_render_video import Product3DRenderVideoService
from app.services.product_commercialization import ProductCommercializationService, _build_visual_prompt


client = TestClient(app)


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


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
        )
    )

    assert len(captured_calls) == 2
    assert result["status"] == "succeeded"
    assert result["videoResult"]["taskId"] == "veo_single_succeeded"
    assert result["videoResult"]["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/product-video.mp4"]


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
        )
    )

    assert captured["source"] == "product-commercialization-video-planner"
    assert captured["route_source"] == "product_commercialization_video_director"
    assert captured["image_url"] == "https://example.com/mug.png"
    assert result["videoPlan"]["planner"]["provider"] == "volcengine"
    assert result["videoPlan"]["planner"]["fallback"] is False
    assert result["videoPlan"]["planner"]["model"] == "doubao-video-director-test"
    assert result["videoPlan"]["videoPrompt"].startswith("Model-planned 15 second")
    assert result["videoPlan"]["storyboard"][0]["cameraMovement"].startswith("slow 30 degree orbit")
    assert result["videoAssetPackagePlan"]["keyframeNeeds"][0]["source"] == "gpt_image_2_planned"
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
        )
    )

    assert captured["input_payload"]["imageUrls"] == ["https://example.com/front.png"]
    assert result["videoResult"]["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/video.mp4"]


def test_product_3d_render_video_preview_returns_plan_without_video() -> None:
    service = Product3DRenderVideoService()

    result = service.preview(
        Product3DRenderVideoRequest(
            modelKey="cup_1660",
            textureImageUrl="https://example.com/pattern.png",
            materialSlot="front",
            cameraPreset="hero_turntable",
            scenePreset="desktop_lifestyle",
            durationSeconds=6,
        )
    )

    assert result["businessKey"] == "product_3d_render_video"
    assert result["model"]["preferredFile"] == "1660.glb"
    assert result["assetReadiness"]["uvReady"] is True
    assert result["assetReadiness"]["renderWorkerReady"] is False
    assert result["renderPlan"]["executionStatus"] == "preview_only"
    assert result["renderPlan"]["camera"]["key"] == "hero_turntable"
    assert result["renderPlan"]["camera"]["motionTemplate"] == "slow_turntable_hero"
    assert result["renderPlan"]["scene"]["key"] == "desktop_lifestyle"
    assert result["renderPlan"]["scene"]["placement"]["anchor"] == "front center on tabletop"
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


def test_product_3d_render_video_rejects_render_mode_until_worker_exists() -> None:
    service = Product3DRenderVideoService()

    with pytest.raises(HTTPException) as excinfo:
        service.preview(Product3DRenderVideoRequest(modelKey="cup_1660", outputMode="render_video"))

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "PRODUCT_3D_RENDER_VIDEO_EXECUTION_NOT_READY"


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
        )
    )

    assert captured["endpoint"] == "/api/v1/veo/generate"
    assert captured["status_endpoint"] == "/api/v1/veo/record-info"
    assert captured["model"] == "veo3_fast"
    assert captured["input_payload"]["imageUrls"] == ["https://example.com/socks.png"]
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
        )
    )

    assert captured["input_payload"]["prompt"] == edited_prompt
    assert result["videoPlan"]["videoPrompt"] == edited_prompt
    assert result["videoPlan"]["promptSource"] == "user_edited"
    assert result["videoResult"]["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/edited-prompt.mp4"]


def test_product_commercialization_video_can_use_vidu_executor(monkeypatch) -> None:
    service = ProductCommercializationService()
    captured = {}
    frame_calls = []
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

    def fake_generate_normalized_first_frame(**kwargs):
        frame_calls.append(kwargs)
        return {
            "role": "normalized_first_frame",
            "status": "succeeded",
            "shot": kwargs["segment_index"],
            "segmentIndex": kwargs["segment_index"],
            "source": "gpt_image_2_plus_canvas_normalization",
            "provider": "openai",
            "model": "gpt-image-2",
            "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/first-frame-16x9.png",
            "rawImageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/raw-first-frame.png",
            "sourceImageUrl": kwargs["source_image_url"],
            "aspectRatio": kwargs["aspect_ratio"],
            "width": 1280,
            "height": 720,
        }

    monkeypatch.setattr(service, "_generate_normalized_first_frame", fake_generate_normalized_first_frame)

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
        )
    )

    assert captured["endpoint"] == "/ent/v2/img2video"
    assert captured["status_endpoint"] == "/ent/v2/tasks/{task_id}/creations"
    assert captured["model"] == "viduq3-turbo"
    assert frame_calls[0]["source_image_url"] == "https://example.com/socks.png"
    assert frame_calls[0]["aspect_ratio"] == "16:9"
    assert captured["input_payload"]["images"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/first-frame-16x9.png"]
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
    assert composition_calls[0]["first_frame_url"].endswith("first-frame-16x9.png")
    assert composition_calls[0]["segment_video_url"].endswith("vidu-video.mp4")
    assert result["videoAssetPackage"]["deliveryStatus"] == "composed_ready"
    assert result["videoAssetPackage"]["composition"]["videoUrl"].endswith("hero-composed.mp4")
    assert result["videoResult"]["provider"] == "vidu+ffmpeg"
    assert result["videoResult"]["model"] == "viduq3-turbo"
    assert result["execution"]["imageGenerated"] is True
    assert result["execution"]["costActions"] == ["openai.gpt_image_2.image", "vidu.viduq3_turbo.video", "ffmpeg.compose"]
    assert result["videoAssetPackage"]["keyframes"][0]["imageUrl"].endswith("first-frame-16x9.png")
    assert result["videoResult"]["segments"][0]["referenceImageUrl"].endswith("first-frame-16x9.png")
    assert result["videoResult"]["segments"][0]["normalizedFirstFrame"]["width"] == 1280
    assert result["videoResult"]["videoUrls"] == [
        "https://podi.oss-cn-hangzhou.aliyuncs.com/hero-composed.mp4",
        "https://podi.oss-cn-hangzhou.aliyuncs.com/vidu-video.mp4",
    ]


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


def test_business_openapi_exposes_product_commercialization() -> None:
    resp = client.get("/api/business/openapi.json", headers={"x-real-ip": "127.0.0.1"})
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/business/product-commercialization/runs" in paths
    assert "/api/business/product-commercialization/preview" in paths
    assert "/api/business/product-commercialization/video" in paths
    assert "/api/business/product-commercialization/video-compose" in paths
    assert "/api/business/product-3d-render-video/preview" in paths
    runs_schema = paths["/api/business/product-commercialization/runs"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert runs_schema["x-podi-required-one-of"] == ["productImageUrl", "productImages"]
    preview_schema = paths["/api/business/product-commercialization/preview"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert preview_schema["properties"]["outputLanguage"]["enum"] == ["en-US", "zh-CN", "bilingual"]
    assert preview_schema["properties"]["visualSupportMode"]["enum"] == ["none", "recommendation", "generate"]
    assert preview_schema["properties"]["durationSeconds"]["minimum"] == 1
    assert "productImages" in preview_schema["properties"]
    assert "enum" not in preview_schema["properties"]["durationSeconds"]
    assert preview_schema["properties"]["targetDurationSeconds"]["minimum"] == 1
    assert preview_schema["properties"]["targetDurationSeconds"]["maximum"] == 60
    product_3d_schema = paths["/api/business/product-3d-render-video/preview"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert product_3d_schema["properties"]["modelKey"]["enum"] == ["cup_1660", "backpack_2551"]
    assert product_3d_schema["properties"]["outputMode"]["enum"] == ["plan_only"]
