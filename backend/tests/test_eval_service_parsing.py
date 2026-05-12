import json
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.models.eval import EvalRun, EvalWorkflowVersion


class _FakeSession:
    def __init__(self, *, run=None, workflow=None):
        self.run = run
        self.workflow = workflow
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, model, key):
        if model is EvalRun:
            return self.run
        if model is EvalWorkflowVersion:
            return self.workflow
        return None

    def add(self, item):
        return None

    def commit(self):
        self.commits += 1


def _fake_session_factory(fake_session):
    return lambda: fake_session


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


def test_extract_workflow_tool_error_detects_queue_full_payload():
    from app.services.eval_service import EvalService

    payload = {
        "text": "queue_full",
        "texts": ["COMFYUI_QUEUE_FULL(limit=10, current=10)；请稍后重试"],
        "taskId": "ERR|Q1001|COMFYUI_QUEUE_FULL(limit=10, current=10)",
        "taskStatus": "failed",
        "errorCode": "Q1001",
        "retryAfterSeconds": 60,
        "debugResponse": "COMFYUI_QUEUE_FULL(limit=10, current=10)",
    }

    assert EvalService._extract_workflow_tool_error(payload) == "ERR|Q1001|COMFYUI_QUEUE_FULL(limit=10, current=10)"


def test_extract_workflow_tool_error_detects_nested_failed_tool_without_err_task_id():
    from app.services.eval_service import EvalService

    payload = {
        "output": {
            "taskStatus": "failed",
            "errorCode": "Q1001",
            "debugResponse": "COMFYUI_QUEUE_FULL(limit=10, current=10)",
        }
    }

    assert EvalService._extract_workflow_tool_error(payload) == "ERR|Q1001|COMFYUI_QUEUE_FULL(limit=10, current=10)"


def test_business_eval_output_summary_is_json_safe():
    from app.services.eval_service import EvalService

    now = datetime(2026, 5, 12, 12, 0, 0)
    summary = EvalService._business_eval_output_summary(
        {
            "id": "run_1",
            "status": "running",
            "route_info": {"selectedAt": now},
            "steps": [{"startedAt": now}],
            "created_at": now,
        }
    )

    assert summary["route_info"]["selectedAt"] == "2026-05-12T12:00:00"
    assert summary["steps"][0]["startedAt"] == "2026-05-12T12:00:00"
    assert "created_at" not in summary


def test_business_poll_task_not_found_is_transient_only_briefly():
    from app.services.eval_service import EvalService

    now = time.monotonic()
    assert EvalService._is_transient_business_poll_error("TASK_NOT_FOUND", started=now) is True
    assert EvalService._is_transient_business_poll_error("TASK_NOT_FOUND", started=now - 240) is False
    assert EvalService._is_transient_business_poll_error("OPENAI_FAILED", started=now) is False


def test_extract_image_urls_from_task_payload_accepts_stored_url():
    from app.services.eval_service import EvalService

    payload = {
        "images": [
            {"storedUrl": "https://oss.example/a.png", "url": "https://vendor.example/a.png"},
            {"ossUrl": "https://oss.example/b.png"},
        ]
    }

    assert EvalService._extract_image_urls_from_task_payload(payload) == [
        "https://oss.example/a.png",
        "https://oss.example/b.png",
    ]


def test_submit_coze_async_run_persists_execute_id(monkeypatch):
    from app.services import eval_service as eval_service_module
    from app.services.eval_service import EvalService

    run = SimpleNamespace(
        id="run_1",
        status="queued",
        coze_execute_id=None,
        coze_debug_url=None,
        created_at=datetime.utcnow(),
    )
    fake_session = _FakeSession(run=run)
    monkeypatch.setattr(eval_service_module, "get_session", _fake_session_factory(fake_session))

    def _fake_run_workflow(**kwargs):
        assert kwargs["is_async"] is True
        return {"execute_id": "exec_1", "debug_url": "https://coze.example/debug"}

    monkeypatch.setattr(eval_service_module.coze_client, "run_workflow", _fake_run_workflow)

    service = EvalService.__new__(EvalService)
    submitted, error = service._submit_coze_async_run(
        run_id="run_1",
        workflow_id="workflow_1",
        coze_params={"url": "https://oss.example/input.png"},
    )

    assert submitted is True
    assert error is None
    assert run.status == "running"
    assert run.coze_execute_id == "exec_1"
    assert run.coze_debug_url == "https://coze.example/debug"
    assert fake_session.commits == 1


def test_finalize_coze_async_run_succeeds_with_text_output(monkeypatch):
    from app.services import eval_service as eval_service_module
    from app.services.eval_service import EvalService

    run = SimpleNamespace(
        id="run_1",
        workflow_version_id="wf_v1",
        status="running",
        error_message=None,
        result_image_urls_json=None,
        result_output_json=None,
        duration_ms=None,
        created_at=datetime.utcnow() - timedelta(seconds=2),
    )
    workflow = SimpleNamespace(
        id="wf_v1",
        workflow_id="coze_workflow_1",
        output_schema={"fields": [{"name": "output", "description": "文本结果"}]},
    )
    fake_session = _FakeSession(run=run, workflow=workflow)
    monkeypatch.setattr(eval_service_module, "get_session", _fake_session_factory(fake_session))

    def _fake_get_history(**kwargs):
        return {
            "data": [
                {
                    "execute_status": "Success",
                    "output": json.dumps({"output": "这是一段文字结果"}),
                }
            ]
        }

    monkeypatch.setattr(eval_service_module.coze_client, "get_workflow_run_history", _fake_get_history)

    service = EvalService.__new__(EvalService)
    service._finalize_coze_async_run_once(
        run_id="run_1",
        workflow_version_id="wf_v1",
        execute_id="exec_1",
        created_at=run.created_at,
    )

    assert run.status == "succeeded"
    assert run.result_image_urls_json == []
    assert run.result_output_json == "这是一段文字结果"
    assert run.duration_ms is not None
