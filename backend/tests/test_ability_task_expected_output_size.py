from types import SimpleNamespace

from app.services.ability_task_service import AbilityTaskService


def test_ability_task_finalize_expected_output_size_for_seamless():
    service = object.__new__(AbilityTaskService)
    task = SimpleNamespace(
        capability_key="sifang_lianxu",
        ability_id="comfyui_sifang_lianxu",
        result_payload={},
        request_payload={"inputs": {"width": 1566, "height": 1885}},
    )

    assert service._expected_comfyui_output_size(task) == (1566, 1885)
    assert service._expected_comfyui_adjust_mode(task) == "resize"
