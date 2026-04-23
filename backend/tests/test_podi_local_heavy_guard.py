from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

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
