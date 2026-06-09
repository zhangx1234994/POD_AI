import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.business import ProductCommercializationRequest
from app.services.product_commercialization import ProductCommercializationService


client = TestClient(app)


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
    assert len(result["copyPackage"]["bulletPoints"]) == 5
    assert result["visualAssetPlan"]["mode"] == "recommendation"
    assert result["visualAssetPlan"]["hasProductImage"] is True
    assert result["visualAssetPlan"]["generationPolicy"]["requiresExplicitAction"] is True
    assert result["videoPlan"]["model"] == "veo3_fast"
    assert result["execution"]["costActions"] == []


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
    assert polled["billingUnit"] == "veo3_fast_video_segment"
    assert polled["quotaUnits"] == 1
    assert polled["costBreakdown"]["pricingStatus"] == "quota_only_mvp"
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
    assert preview_schema["properties"]["durationSeconds"]["enum"] == [8]
    assert preview_schema["properties"]["targetDurationSeconds"]["minimum"] == 8
    assert preview_schema["properties"]["targetDurationSeconds"]["maximum"] == 60
