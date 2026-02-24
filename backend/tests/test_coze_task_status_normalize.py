from app.routers.coze_podi_plugin import _limit_comfyui_images, _normalize_coze_task_status


def test_normalize_coze_task_status_success_variants():
    for value in ("success", "succeeded", "completed", "ok"):
        assert _normalize_coze_task_status(value) == "succeeded"


def test_normalize_coze_task_status_failure_variants():
    for value in ("failed", "error", "timeout", "rejected", "cancelled"):
        assert _normalize_coze_task_status(value) == "failed"


def test_normalize_coze_task_status_queue_running_variants():
    assert _normalize_coze_task_status("pending") == "queued"
    assert _normalize_coze_task_status("processing") == "running"


def test_limit_comfyui_images_for_seamless_only_keeps_one():
    images = [{"url": "a"}, {"url": "b"}]
    assert _limit_comfyui_images("sifang_lianxu", images) == [{"url": "a"}]
    assert _limit_comfyui_images("yinhua_tiqu", images) == images
