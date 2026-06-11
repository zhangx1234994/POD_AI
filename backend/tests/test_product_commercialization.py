import json
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.integration import BusinessRun
from app.schemas.abilities import AbilityInvokeResponse, AbilityOutputAsset
from app.schemas.business import ProductCommercializationRequest
from app.services.business_runs import BusinessRunService
from app.services.product_commercialization import ProductCommercializationService


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
    assert video_plan["compositionPlan"]["status"] == "planned_ready_for_compose_endpoint"
    assert video_plan["compositionPlan"]["executionReady"] is True
    assert video_plan["compositionPlan"]["costActionPreview"] == [
        "kie.veo3_fast.video",
        "kie.veo3_fast.video",
        "ffmpeg.compose",
    ]


def test_product_commercialization_preview_uses_vidu_duration_profile() -> None:
    service = ProductCommercializationService()

    result = service.preview(
        ProductCommercializationRequest(
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
    assert any(item["asset"] == "normalized_first_frame" for item in video_plan["assetNeeds"])


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
    assert captured["input_payload"]["images"] == ["https://example.com/socks.png"]
    assert captured["input_payload"]["duration"] == 5
    assert "aspectRatio" not in captured["input_payload"]
    assert captured["input_payload"]["audio"] is False
    assert captured["input_payload"]["bgm"] is False
    assert result["videoPlan"]["provider"] == "vidu"
    assert result["videoPlan"]["model"] == "viduq3-turbo"
    assert result["videoPlan"]["aspectPolicy"]["mode"] == "input_image_ratio"
    assert result["videoPlan"]["targetDurationSeconds"] == 5
    assert result["videoResult"]["provider"] == "vidu"
    assert result["videoResult"]["model"] == "viduq3-turbo"
    assert result["execution"]["costActions"] == ["vidu.viduq3_turbo.video"]
    assert result["videoResult"]["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/vidu-video.mp4"]


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
    runs_schema = paths["/api/business/product-commercialization/runs"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert runs_schema["required"] == ["productImageUrl"]
    preview_schema = paths["/api/business/product-commercialization/preview"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert preview_schema["properties"]["outputLanguage"]["enum"] == ["en-US", "zh-CN", "bilingual"]
    assert preview_schema["properties"]["visualSupportMode"]["enum"] == ["none", "recommendation", "generate"]
    assert preview_schema["properties"]["durationSeconds"]["minimum"] == 1
    assert "enum" not in preview_schema["properties"]["durationSeconds"]
    assert preview_schema["properties"]["targetDurationSeconds"]["minimum"] == 1
    assert preview_schema["properties"]["targetDurationSeconds"]["maximum"] == 60
