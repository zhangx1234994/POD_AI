from app.services.image_ops_registry import (
    get_image_ops_capability,
    image_ops_managed_capabilities,
    is_heavy_image_ops_capability,
    is_image_ops_capability,
)


def test_image_ops_registry_lists_expected_capabilities() -> None:
    assert image_ops_managed_capabilities() == [
        "expand_mask_color",
        "set_dpi",
        "upscale_resize",
    ]


def test_image_ops_registry_marks_upscale_as_heavy_only() -> None:
    assert is_heavy_image_ops_capability("upscale_resize") is True
    assert is_heavy_image_ops_capability("set_dpi") is False
    assert is_heavy_image_ops_capability("expand_mask_color") is False


def test_image_ops_registry_requires_podi_provider() -> None:
    assert is_image_ops_capability(provider="podi", capability_key="set_dpi") is True
    assert is_image_ops_capability(provider="comfyui", capability_key="set_dpi") is False
    assert is_image_ops_capability(provider="podi", capability_key="unknown") is False


def test_image_ops_registry_returns_copy_of_spec() -> None:
    spec = get_image_ops_capability("upscale_resize")
    assert spec is not None
    assert spec["operation"] == "upscale-resize"
    assert spec["heavy"] is True
    spec["operation"] = "changed"
    assert get_image_ops_capability("upscale_resize")["operation"] == "upscale-resize"
