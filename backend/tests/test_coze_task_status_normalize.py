from app.routers.coze_podi_plugin import (
    _extract_comfyui_expected_adjust_mode,
    _extract_comfyui_expected_output_size,
    _limit_comfyui_images,
    _normalize_coze_task_status,
)


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
    assert _limit_comfyui_images("yinhua_tiqu_lora_8step", images) == images


def test_extract_expected_output_size_for_seamless_custom_pixels():
    assert _extract_comfyui_expected_output_size(
        "sifang_lianxu",
        {"inputs": {"width": "1566", "height": "1885"}},
    ) == (1566, 1885)
    assert _extract_comfyui_expected_output_size(
        "yinhua_tiqu",
        {"inputs": {"width": "1566", "height": "1885"}},
    ) == (1566, 1885)


def test_extract_expected_adjust_mode_for_exact_size_comfyui_tasks():
    assert _extract_comfyui_expected_adjust_mode("sifang_lianxu") == "resize"
    assert _extract_comfyui_expected_adjust_mode("comfyui_sifang_lianxu") == "resize"
    assert _extract_comfyui_expected_adjust_mode("flux_strong_hq_softstyle_fission") == "cover_crop"
    assert _extract_comfyui_expected_adjust_mode("yinhua_tiqu") == "resize"
    assert _extract_comfyui_expected_adjust_mode("yinhua_tiqu_lora_8step") == "resize"
