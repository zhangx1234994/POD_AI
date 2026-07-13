from io import BytesIO
from types import SimpleNamespace

from fastapi import HTTPException
from PIL import Image

from app.services.ability_task_service import AbilityTaskService
from app.services.executors.comfyui import ComfyUIExecutorAdapter
from app.services.executors import comfyui as comfyui_module


def test_extract_comfyui_error_detail_with_execution_error_message():
    history = {
        "status": {
            "status_str": "error",
            "messages": [
                ["execution_start", {"prompt_id": "abc"}],
                [
                    "execution_error",
                    {
                        "node_id": "102",
                        "node_type": "ImageResize+",
                        "exception_type": "IndexError",
                        "exception_message": "list index out of range\n",
                    },
                ],
            ],
        }
    }

    detail = AbilityTaskService._extract_comfyui_error_detail(history)
    assert detail == "COMFYUI_ERROR(node=102:ImageResize+, type=IndexError): list index out of range"


def test_extract_comfyui_error_detail_returns_none_without_error_message():
    history = {"status": {"status_str": "running", "messages": [["execution_start", {"prompt_id": "abc"}]]}}

    detail = AbilityTaskService._extract_comfyui_error_detail(history)
    assert detail is None


def test_empty_comfyui_outputs_fail_fast_after_short_grace_period():
    assert (
        AbilityTaskService._should_fail_comfyui_finalize_error(
            current_error="COMFYUI_IMAGES_EMPTY",
            count=3,
            age_seconds=60,
        )
        is True
    )


def test_empty_comfyui_outputs_keep_running_during_grace_period():
    assert (
        AbilityTaskService._should_fail_comfyui_finalize_error(
            current_error="COMFYUI_IMAGES_EMPTY",
            count=2,
            age_seconds=120,
        )
        is False
    )
    assert (
        AbilityTaskService._should_fail_comfyui_finalize_error(
            current_error="COMFYUI_IMAGES_EMPTY",
            count=3,
            age_seconds=30,
        )
        is False
    )


def test_comfyui_submit_connection_error_is_reroutable():
    exc = HTTPException(status_code=502, detail="COMFYUI_SUBMIT_ERROR: connection refused")

    assert AbilityTaskService._is_comfyui_reroutable_error(exc) is True


def test_comfyui_input_validation_error_is_not_reroutable():
    exc = HTTPException(status_code=400, detail="COMFYUI_IMAGE_REQUIRED")

    assert AbilityTaskService._is_comfyui_reroutable_error(exc) is False


def test_comfyui_asset_store_accepts_finalize_expected_size(monkeypatch):
    adapter = ComfyUIExecutorAdapter()
    context = SimpleNamespace(task=SimpleNamespace(user_id="test-user"))
    monkeypatch.setattr(
        comfyui_module.media_ingest_service,
        "ingest_from_remote_url",
        lambda *args, **kwargs: {"ossUrl": "https://example.com/result.png"},
    )

    result = adapter._store_remote_asset(
        "https://example.com/result.png",
        context,
        tag="comfyui",
        expected_size=None,
    )

    assert result == {"ossUrl": "https://example.com/result.png"}


def test_comfyui_delivery_resize_outputs_exact_pixels():
    source = Image.new("RGB", (64, 64), (20, 80, 120))
    payload = BytesIO()
    source.save(payload, format="PNG")

    normalized = ComfyUIExecutorAdapter._resize_delivery_image(payload.getvalue(), (96, 48))

    with Image.open(BytesIO(normalized)) as result:
        assert result.size == (96, 48)
