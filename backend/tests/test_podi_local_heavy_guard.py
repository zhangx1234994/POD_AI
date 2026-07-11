from __future__ import annotations

import base64
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image

from app.core.config import get_settings
from app.schemas.abilities import AbilityInvokeRequest
from app.services.ability_invocation import AbilityInvocationService, _ImageBundle, _InvocationContext


_MINIMAL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8B9l8AAAAASUVORK5CYII="
)


def test_upscale_resize_is_blocked_when_local_heavy_tasks_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLE_LOCAL_HEAVY_IMAGE_TASKS", "true")
    get_settings.cache_clear()
    try:
        service = AbilityInvocationService()
        ability = SimpleNamespace(provider="podi", capability_key="upscale_resize")
        images = _ImageBundle(image_url=None, image_base64=_MINIMAL_PNG_BASE64, image_list=[])
        context = _InvocationContext(
            request_id="req-heavy-guard",
            source="pytest",
            user=None,
            payload=AbilityInvokeRequest(),
        )

        with pytest.raises(HTTPException) as exc_info:
            service._invoke_podi(ability, {}, images, context)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "LOCAL_HEAVY_IMAGE_TASK_DISABLED"
    finally:
        get_settings.cache_clear()


def _non_periodic_png_base64() -> str:
    image = Image.new("RGBA", (8, 6), (255, 255, 255, 255))
    for y in range(image.height):
        image.putpixel((0, y), (255, 0, 0, 255))
        image.putpixel((image.width - 1, y), (0, 0, 255, 255))
    for x in range(image.width):
        image.putpixel((x, 0), (0, 255, 0, 255))
        image.putpixel((x, image.height - 1), (255, 255, 0, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def test_seamless_production_normalize_requires_tiled_review() -> None:
    service = AbilityInvocationService()
    ability = SimpleNamespace(provider="podi", capability_key="seamless_production_normalize")
    images = _ImageBundle(image_url=None, image_base64=_non_periodic_png_base64(), image_list=[])
    context = _InvocationContext(
        request_id="req-seamless-review",
        source="pytest",
        user=None,
        payload=AbilityInvokeRequest(),
    )

    with pytest.raises(HTTPException) as exc_info:
        service._invoke_podi(ability, {"repeat_axis": "both"}, images, context)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "SEAMLESS_TILED_REVIEW_REQUIRED"


def test_seamless_production_normalize_returns_zero_edge_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AbilityInvocationService()
    ability = SimpleNamespace(provider="podi", capability_key="seamless_production_normalize")
    images = _ImageBundle(image_url=None, image_base64=_non_periodic_png_base64(), image_list=[])
    context = _InvocationContext(
        request_id="req-seamless-normalize",
        source="pytest",
        user=None,
        payload=AbilityInvokeRequest(),
    )
    monkeypatch.setattr(
        "app.services.ability_invocation.media_ingest_service.upload_generated_image_bytes",
        lambda **_: {"url": "https://example.test/seamless.png", "objectKey": "test/seamless.png"},
    )

    result = service._invoke_podi(
        ability,
        {"repeat_axis": "both", "tiled_review_confirmed": True},
        images,
        context,
    )

    evidence = result["raw"]["request"]["edgeEvidence"]
    assert result["storedUrl"] == "https://example.test/seamless.png"
    assert evidence["horizontal"]["before"]["maxAbs"] > 0
    assert evidence["vertical"]["before"]["maxAbs"] > 0
    assert evidence["horizontal"]["after"]["maxAbs"] == 0
    assert evidence["vertical"]["after"]["maxAbs"] == 0
