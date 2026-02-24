from app.services.ability_invocation import ability_invocation_service


def test_normalize_public_status_success_variants():
    for value in ("success", "succeeded", "completed", "ok"):
        assert ability_invocation_service._normalize_public_status(value) == "succeeded"


def test_normalize_public_status_failure_variants():
    for value in ("failed", "error", "timeout", "rejected"):
        assert ability_invocation_service._normalize_public_status(value) == "failed"


def test_normalize_public_status_running_variants():
    assert ability_invocation_service._normalize_public_status("processing") == "running"
    assert ability_invocation_service._normalize_public_status("queued") == "queued"
    assert ability_invocation_service._normalize_public_status("canceled") == "cancelled"
