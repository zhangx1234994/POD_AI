from app.services.ability_task_service import AbilityTaskService


def test_resolve_invoke_status_maps_failed_variants() -> None:
    for value in ("failed", "error", "timeout", "rejected"):
        assert AbilityTaskService._resolve_invoke_status(value) == "failed"


def test_resolve_invoke_status_maps_running_variants() -> None:
    for value in ("queued", "running"):
        assert AbilityTaskService._resolve_invoke_status(value) == "running"


def test_resolve_invoke_status_maps_cancelled_variants() -> None:
    for value in ("cancelled", "canceled", "stopped", "aborted"):
        assert AbilityTaskService._resolve_invoke_status(value) == "cancelled"


def test_resolve_invoke_status_defaults_to_succeeded() -> None:
    assert AbilityTaskService._resolve_invoke_status("succeeded") == "succeeded"
    assert AbilityTaskService._resolve_invoke_status(None) == "succeeded"
