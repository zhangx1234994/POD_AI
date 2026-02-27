from app.services.task_status_contract import (
    derive_ability_log_status,
    derive_ability_task_status,
    derive_agent_task_status,
    derive_eval_run_status,
    extract_error_code,
)


def test_extract_error_code_from_err_format() -> None:
    assert extract_error_code("ERR|Q1001|COMFYUI_QUEUE_FULL(limit=10)") == "Q1001"


def test_ability_task_status_success() -> None:
    stage = derive_ability_task_status(status="succeeded")
    assert stage.submit_status == "submitted"
    assert stage.callback_status == "success"
    assert stage.final_status == "success"


def test_ability_log_status_callback_failed() -> None:
    stage = derive_ability_log_status(
        log_status="success",
        callback_status="failed",
        callback_http_status=500,
        callback_configured=True,
        callback_error="ERR|CALLBACK_TIMEOUT|remote timeout",
    )
    assert stage.submit_status == "submitted"
    assert stage.final_status == "failed"
    assert stage.error_code == "CALLBACK_TIMEOUT"


def test_eval_run_status_running_without_result() -> None:
    stage = derive_eval_run_status(status="succeeded", podi_task_id="t1.xx", has_result=False)
    assert stage.final_status == "running"
    assert stage.callback_status == "running"


def test_agent_task_status_pending_after_push_marks_submit_failed() -> None:
    stage = derive_agent_task_status(status="pending", pushed_at="2026-02-26T00:00:00")
    assert stage.submit_status == "submit_failed"
    assert stage.final_status == "pending"
