from app.routers.coze_podi_plugin import _normalize_coze_task_status


def test_normalize_coze_task_status_success_variants():
    for value in ("success", "succeeded", "completed", "ok"):
        assert _normalize_coze_task_status(value) == "succeeded"


def test_normalize_coze_task_status_failure_variants():
    for value in ("failed", "error", "timeout", "rejected", "cancelled"):
        assert _normalize_coze_task_status(value) == "failed"


def test_normalize_coze_task_status_queue_running_variants():
    assert _normalize_coze_task_status("pending") == "queued"
    assert _normalize_coze_task_status("processing") == "running"

