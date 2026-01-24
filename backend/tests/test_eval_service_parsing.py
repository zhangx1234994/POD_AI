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

