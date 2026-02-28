from app.services.ability_invocation import AbilityInvocationService
from app.services.integration_test import integration_test_service


def test_pick_comfyui_executor_by_queue_prefers_lower_queue(monkeypatch):
    service = AbilityInvocationService()

    def _fake_status(*, executor_id: str):
        mapping = {
            "executor_a": {"runningCount": 2, "pendingCount": 4, "supported": True},
            "executor_b": {"runningCount": 0, "pendingCount": 1, "supported": True},
        }
        return mapping[executor_id]

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)
    picked = service._pick_comfyui_executor_by_queue(["executor_a", "executor_b"])
    assert picked == "executor_b"


def test_pick_comfyui_executor_by_queue_round_robin_on_tie(monkeypatch):
    service = AbilityInvocationService()

    def _fake_status(*, executor_id: str):
        # Equal queue load -> should rotate instead of always picking lexical first.
        return {"runningCount": 1, "pendingCount": 1, "supported": True}

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)
    first = service._pick_comfyui_executor_by_queue(["executor_a", "executor_b"])
    second = service._pick_comfyui_executor_by_queue(["executor_a", "executor_b"])
    assert first in {"executor_a", "executor_b"}
    assert second in {"executor_a", "executor_b"}
    assert first != second
