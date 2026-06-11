from types import SimpleNamespace

import httpx

from app.services.integration_test import IntegrationTestService


def test_vidu_video_task_polls_and_persists_to_oss(monkeypatch) -> None:
    service = IntegrationTestService()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        service,
        "_get_executor",
        lambda executor_id: SimpleNamespace(
            id=executor_id,
            type="vidu",
            base_url="https://api.vidu.cn",
            config={"apiKey": "test-key", "baseUrl": "https://api.vidu.cn"},
        ),
    )
    monkeypatch.setattr(
        service,
        "_pick_vidu_api_key",
        lambda executor, exclude_ids=None: SimpleNamespace(id="legacy", key="test-key"),
    )

    def fake_post(url, *, headers, json, timeout):
        captured["post_url"] = url
        captured["post_headers"] = headers
        captured["post_json"] = json
        return httpx.Response(200, json={"task_id": "vidu_task_1", "state": "created"})

    def fake_get(url, *, headers, timeout):
        captured["get_url"] = url
        captured["get_headers"] = headers
        return httpx.Response(
            200,
            json={
                "id": "vidu_task_1",
                "state": "success",
                "creations": [
                    {"url": "https://vidu.example/output.mp4", "cover_url": "https://vidu.example/cover.png"}
                ],
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(
        service,
        "_store_remote_asset",
        lambda url, **kwargs: {
            "sourceUrl": url,
            "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/vidu/output.mp4",
            "ossKey": "test/vidu/output.mp4",
            "contentType": "video/mp4",
        },
    )

    result = service.run_vidu_video_task(
        executor_id="executor_vidu_default",
        input_payload={
            "prompt": "Create an ecommerce product video.",
            "images": ["https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/product.png"],
            "duration": 8,
            "aspectRatio": "16:9",
        },
        poll_timeout=10,
        poll_interval=0.01,
    )

    assert captured["post_url"] == "https://api.vidu.cn/ent/v2/img2video"
    assert captured["post_headers"]["Authorization"] == "Token test-key"
    assert captured["post_json"]["model"] == "viduq3-turbo"
    assert captured["post_json"]["images"] == ["https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/product.png"]
    assert "aspectRatio" not in captured["post_json"]
    assert "aspect_ratio" not in captured["post_json"]
    assert captured["get_url"] == "https://api.vidu.cn/ent/v2/tasks/vidu_task_1/creations"
    assert captured["get_headers"]["Authorization"] == "Token test-key"
    assert result["status"] == "succeeded"
    assert result["provider"] == "vidu"
    assert result["videoUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/vidu/output.mp4"]
    assert result["resultUrls"] == ["https://podi.oss-cn-hangzhou.aliyuncs.com/vidu/output.mp4"]
