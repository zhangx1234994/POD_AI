from __future__ import annotations

from datetime import datetime

from app.models.eval import EvalRun
from app.routers.evals_public import _compact_eval_output_for_list, _serialize_eval_run_for_list


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
