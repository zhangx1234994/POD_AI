from __future__ import annotations

from datetime import datetime

from app.models.eval import EvalRun
from app.routers.evals_public import (
    _compact_eval_output_for_list,
    _is_recoverable_business_eval_row,
    _is_recoverable_business_timeout_row,
    _recover_business_timeout_rows_for_display,
    _serialize_eval_run_for_list,
)


def test_eval_list_output_compaction_removes_heavy_business_step_payloads() -> None:
    output = {
        "businessRunId": "run_1",
        "status": "succeeded",
        "imageUrls": ["https://example.com/out.png"],
        "steps": [
            {
                "displayName": "GPT Image 2",
                "status": "succeeded",
                "request_payload": {"prompt": "x" * 6000},
                "result_payload": {"raw": "y" * 6000},
            }
        ],
    }

    compact = _compact_eval_output_for_list(output)

    assert compact["businessRunId"] == "run_1"
    assert compact["imageUrls"] == ["https://example.com/out.png"]
    assert compact["stepCount"] == 1
    assert compact["steps"] == [{"displayName": "GPT Image 2", "status": "succeeded"}]


def test_eval_list_serializer_omits_heavy_structured_output() -> None:
    now = datetime.utcnow()
    run = EvalRun(
        id="run_1",
        workflow_version_id="wf_1",
        dataset_item_id=None,
        input_oss_urls_json=["https://example.com/input.png"],
        parameters_json={"bili": "15"},
        status="succeeded",
        coze_execute_id=None,
        coze_debug_url=None,
        podi_task_id="task_1",
        result_image_urls_json=["https://example.com/output.png"],
        result_output_json={"steps": [{"request_payload": {"prompt": "x" * 10000}}]},
        error_message=None,
        duration_ms=123,
        created_by="tester",
        created_at=now,
        updated_at=now,
    )

    payload = _serialize_eval_run_for_list(run).model_dump()

    assert payload["result_image_urls_json"] == ["https://example.com/output.png"]
    assert payload["result_output_json"] is None
    assert payload["final_status"] == "success"


def test_eval_list_detects_recoverable_business_timeout_rows() -> None:
    now = datetime.utcnow()
    run = EvalRun(
        id="run_timeout",
        workflow_version_id="wf_1",
        dataset_item_id=None,
        input_oss_urls_json=["https://example.com/input.png"],
        parameters_json={},
        status="failed",
        coze_execute_id=None,
        coze_debug_url=None,
        podi_task_id="task_1",
        result_image_urls_json=[],
        result_output_json={"businessRunId": "biz_run_1"},
        error_message="BUSINESS_RUN_TIMEOUT:{'id': 'biz_run_1', 'status': 'running'}",
        duration_ms=1800000,
        created_by="tester",
        created_at=now,
        updated_at=now,
    )

    assert _is_recoverable_business_timeout_row(run) is True

    run.error_message = "COMFYUI_TIMEOUT"
    assert _is_recoverable_business_timeout_row(run) is False


def test_eval_list_detects_recoverable_business_get_failed_rows() -> None:
    now = datetime.utcnow()
    run = EvalRun(
        id="run_get_failed",
        workflow_version_id="wf_1",
        dataset_item_id=None,
        input_oss_urls_json=["https://example.com/input.png"],
        parameters_json={},
        status="failed",
        coze_execute_id=None,
        coze_debug_url=None,
        podi_task_id="task_1",
        result_image_urls_json=[],
        result_output_json={"businessRunId": "biz_run_1"},
        error_message="BUSINESS_RUN_GET_FAILED:业务任务结果查询失败，请稍后重试",
        duration_ms=120000,
        created_by="tester",
        created_at=now,
        updated_at=now,
    )

    assert _is_recoverable_business_eval_row(run) is True

    run.error_message = "BUSINESS_RUN_TEMPORARY_UNAVAILABLE"
    assert _is_recoverable_business_eval_row(run) is True

    run.error_message = "BUSINESS_RUN_FAILED:真实业务失败"
    assert _is_recoverable_business_eval_row(run) is False


def test_eval_list_reconciles_business_timeout_rows_before_display(monkeypatch) -> None:
    now = datetime.utcnow()
    run = EvalRun(
        id="run_timeout",
        workflow_version_id="wf_1",
        dataset_item_id=None,
        input_oss_urls_json=["https://example.com/input.png"],
        parameters_json={},
        status="failed",
        coze_execute_id=None,
        coze_debug_url=None,
        podi_task_id="task_1",
        result_image_urls_json=[],
        result_output_json={"businessRunId": "biz_run_1"},
        error_message="BUSINESS_RUN_TIMEOUT:{'id': 'biz_run_1', 'status': 'running'}",
        duration_ms=1800000,
        created_by="tester",
        created_at=now,
        updated_at=now,
    )

    class FakeEvalService:
        calls: list[str]

        def __init__(self) -> None:
            self.calls = []

        def reconcile_business_run_for_eval(self, run_id: str) -> bool:
            self.calls.append(run_id)
            run.status = "success"
            run.error_message = None
            run.result_image_urls_json = ["https://example.com/output.png"]
            return True

    class FakeDb:
        expired = False

        def expire_all(self) -> None:
            self.expired = True

        def get(self, model, row_id):  # noqa: ANN001
            assert model is EvalRun
            assert row_id == "run_timeout"
            return run

    service = FakeEvalService()
    monkeypatch.setattr("app.routers.evals_public.get_eval_service", lambda: service)

    rows, recovered = _recover_business_timeout_rows_for_display(FakeDb(), [run])

    assert recovered is True
    assert service.calls == ["run_timeout"]
    assert rows[0].status == "success"
    assert rows[0].result_image_urls_json == ["https://example.com/output.png"]
