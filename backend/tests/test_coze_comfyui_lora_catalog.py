from types import SimpleNamespace

from app.routers.coze_podi_plugin import _match_lora_base_model


def test_match_lora_base_model_accepts_single_and_list_values():
    row = SimpleNamespace(base_model="qwen_image_edit", base_models=["sdxl", "flux"])  # noqa: N806
    assert _match_lora_base_model(row, "qwen-image-edit")
    assert _match_lora_base_model(row, "flux")
    assert _match_lora_base_model(row, "SDXL")


def test_match_lora_base_model_rejects_when_not_matched():
    row = SimpleNamespace(base_model="qwen_image_edit", base_models=["sdxl"])  # noqa: N806
    assert not _match_lora_base_model(row, "wan2.2")
