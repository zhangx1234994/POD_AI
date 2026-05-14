from __future__ import annotations

from io import BytesIO

from PIL import Image

import app.services.ability_invocation as ability_invocation_module
from app.models.integration import Ability
from app.services.ability_invocation import AbilityInvocationService, _ImageBundle


def _png_bytes(size: tuple[int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGBA", size, (0, 0, 255, 255)).save(output, format="PNG")
    return output.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def test_openai_image_edit_auto_size_uses_source_dimensions(monkeypatch) -> None:
    def fake_get(url: str, timeout: int = 30) -> _FakeResponse:
        assert url == "https://oss.example.com/source.png"
        return _FakeResponse(_png_bytes((720, 1280)))

    monkeypatch.setattr(ability_invocation_module.httpx, "get", fake_get)
    ability = Ability(
        provider="openai",
        capability_key="gpt_image_2_edit",
        extra_metadata={"api_type": "image_edit"},
    )
    service = AbilityInvocationService()

    desired_size = service._desired_vendor_image_size(
        ability=ability,
        payload_inputs={"size": "auto", "image_url": "https://oss.example.com/source.png"},
        images=_ImageBundle(image_url=None, image_base64=None, image_list=[]),
    )

    assert desired_size == (720, 1280)


def test_openai_image_edit_fixed_size_does_not_use_source_dimensions(monkeypatch) -> None:
    def fail_get(url: str, timeout: int = 30) -> _FakeResponse:  # pragma: no cover - should not be called
        raise AssertionError("source image should not be read when caller selected a fixed size")

    monkeypatch.setattr(ability_invocation_module.httpx, "get", fail_get)
    ability = Ability(
        provider="openai",
        capability_key="gpt_image_2_edit",
        extra_metadata={"api_type": "image_edit"},
    )
    service = AbilityInvocationService()

    desired_size = service._desired_vendor_image_size(
        ability=ability,
        payload_inputs={"size": "1024x1024", "image_url": "https://oss.example.com/source.png"},
        images=_ImageBundle(image_url=None, image_base64=None, image_list=[]),
    )

    assert desired_size is None
