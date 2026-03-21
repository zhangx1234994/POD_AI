import json


def test_parse_run_history_list_parses_output_json_dict():
    from app.services.eval_service import EvalService

    payload = {
        "data": [
            {
                "execute_id": 1,
                "execute_status": "Success",
                "debug_url": "http://coze.local/work_flow?execute_id=1",
                "output": json.dumps({"output": "task_123"}),
            }
        ]
    }
    parsed = EvalService._parse_coze_payload(payload)
    assert parsed["output"] == "task_123"
    assert parsed["run_status"] == "Success"
    assert "debug_url" in parsed


def test_parse_run_history_list_handles_non_dict_output_json():
    from app.services.eval_service import EvalService

    payload = {"data": [{"output": json.dumps(["a", "b"])}]}
    parsed = EvalService._parse_coze_payload(payload)
    assert parsed["output"] == ["a", "b"]


def test_extract_image_urls_excludes_coze_debug_url():
    from app.services.eval_service import EvalService

    parsed = {
        "debug_url": "http://114.55.0.56:8888/work_flow?execute_id=1&execute_mode=2",
        "output": "http://114.55.0.56:8888/work_flow?execute_id=2&execute_mode=2",
        "assets": [{"storedUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/x.png"}],
    }
    urls = EvalService._extract_image_urls(parsed)
    assert urls == ["https://podi.oss-cn-hangzhou.aliyuncs.com/x.png"]


def test_extract_output_json_keeps_business_payload_without_output_key():
    from app.services.eval_service import EvalService

    payload = {
        "items": [{"fileName": "a.safetensors", "status": "active"}],
        "lora_names": ["a.safetensors"],
        "run_status": "Success",
    }
    out = EvalService._extract_output_json(payload)
    assert isinstance(out, dict)
    assert out.get("lora_names") == ["a.safetensors"]
    assert "run_status" not in out


def test_extract_output_json_returns_none_for_metadata_only_payload():
    from app.services.eval_service import EvalService

    payload = {
        "run_status": "Success",
        "debug_url": "http://coze/debug",
        "status": "running",
    }
    assert EvalService._extract_output_json(payload) is None


def test_classify_eval_error_recognizes_transient_network_cases():
    from app.services.eval_service import EvalService

    assert EvalService._classify_eval_error("Workflow execution failure: EOF") == "NETWORK_EOF"
    assert EvalService._classify_eval_error("COZE_HISTORY_FAILED code=0 statusCode=502 msg=Bad Gateway") == "HTTP_502"
    assert EvalService._classify_eval_error("COZE_ASYNC_TIMEOUT") == "TIMEOUT"
    assert EvalService._is_retryable_eval_error("Workflow execution failure: EOF") is True


def test_summarize_fanout_errors_groups_by_kind():
    from app.services.eval_service import EvalService

    summary = EvalService._summarize_fanout_errors(
        [
            "COZE_WORKFLOW_ERROR: Workflow execution failure: EOF",
            "COZE_WORKFLOW_ERROR: Workflow execution failure: EOF",
            "TASK_IMAGES_EMPTY:status=failed;provider=comfyui",
        ]
    )
    assert summary is not None
    assert "FANOUT_PARTIAL_FAILED[" in summary
    assert "NETWORK_EOF=2" in summary
    assert "TASK_IMAGES_EMPTY=1" in summary
