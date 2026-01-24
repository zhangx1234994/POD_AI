from types import SimpleNamespace


def test_is_comfyui_submitted_only_true_when_has_prompt_and_baseurl():
    from app.services.ability_task_service import AbilityTaskService

    task = SimpleNamespace(
        ability_provider="comfyui",
        result_payload={"metadata": {"promptId": "abc", "baseUrl": "http://1.2.3.4:8079"}},
    )
    assert AbilityTaskService._is_comfyui_submitted_only(task) is True


def test_is_comfyui_submitted_only_false_for_non_comfyui():
    from app.services.ability_task_service import AbilityTaskService

    task = SimpleNamespace(ability_provider="kie", result_payload={"metadata": {"promptId": "abc", "baseUrl": "x"}})
    assert AbilityTaskService._is_comfyui_submitted_only(task) is False


def test_is_comfyui_submitted_only_false_without_metadata():
    from app.services.ability_task_service import AbilityTaskService

    task = SimpleNamespace(ability_provider="comfyui", result_payload={"promptId": "abc"})
    assert AbilityTaskService._is_comfyui_submitted_only(task) is False

