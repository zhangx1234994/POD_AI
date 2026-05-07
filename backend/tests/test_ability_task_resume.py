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


def test_is_vendor_api_submitted_only_true_when_has_vendor_ids_and_executor():
    from app.services.ability_task_service import AbilityTaskService

    task = SimpleNamespace(
        ability_provider="volcengine",
        status="running",
        result_payload={
            "status": "running",
            "metadata": {
                "vendorInvocationId": "vinv_1",
                "vendorTaskId": "cgt_1",
                "executorId": "executor_vendor_api_domestic_default",
            },
        },
    )

    assert AbilityTaskService._is_vendor_api_submitted_only(task) is True


def test_is_vendor_api_submitted_only_false_without_vendor_task_id():
    from app.services.ability_task_service import AbilityTaskService

    task = SimpleNamespace(
        ability_provider="volcengine",
        status="running",
        result_payload={
            "status": "running",
            "metadata": {
                "vendorInvocationId": "vinv_1",
                "executorId": "executor_vendor_api_domestic_default",
            },
        },
    )

    assert AbilityTaskService._is_vendor_api_submitted_only(task) is False


def test_count_outputs_includes_text_and_structured_payloads():
    from app.services.ability_task_service import AbilityTaskService

    assert AbilityTaskService._count_outputs(
        {
            "texts": ["图片主体是蓝白植物纹样"],
            "jsonOutput": {"tags": ["植物", "蓝色"]},
            "structured": [{"score": 0.9}],
        }
    ) == 3
