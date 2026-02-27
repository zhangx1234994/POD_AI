from app.services.ability_task_service import AbilityTaskService


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
