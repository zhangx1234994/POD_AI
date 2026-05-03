from types import SimpleNamespace

from fastapi import HTTPException

import app.services.ability_invocation as ability_invocation_module
from app.constants.abilities import COMFYUI_ABILITIES
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


def test_flux_strong_hq_seed_excludes_known_incompatible_4090_node():
    metadata = COMFYUI_ABILITIES["flux_strong_hq_softstyle_fission"]["metadata"]

    assert metadata["allowed_executor_ids"] == ["executor_comfyui_pattern_extract_158"]
    assert metadata["seed_version"] >= 2


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


def test_pick_comfyui_executor_by_queue_counts_internal_queued_tasks(monkeypatch):
    service = AbilityInvocationService()

    def _fake_status(*, executor_id: str):
        return {"runningCount": 0, "pendingCount": 0, "supported": True}

    def _fake_internal_queued(executor_id: str):
        return {"executor_a": 2, "executor_b": 0}.get(executor_id, 0)

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)
    monkeypatch.setattr(service, "_count_internal_comfyui_queued", _fake_internal_queued)

    picked = service._pick_comfyui_executor_by_queue(["executor_a", "executor_b"])

    assert picked == "executor_b"


def test_queue_auto_selection_skips_unreachable_executor(monkeypatch):
    service = AbilityInvocationService()

    def _fake_status(*, executor_id: str):
        if executor_id == "executor_a":
            raise HTTPException(status_code=502, detail="COMFYUI_QUEUE_STATUS_ERROR")
        return {"runningCount": 0, "pendingCount": 0, "supported": True}

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)
    picked = service._select_comfyui_executor(
        [SimpleNamespace(id="executor_a"), SimpleNamespace(id="executor_b")],
        policy="auto",
        route_by_queue=True,
        ability_id="ability_test",
        preferred_order=["executor_a", "executor_b"],
    )
    assert picked == "executor_b"


def test_queue_auto_selection_returns_none_when_every_executor_unreachable(monkeypatch):
    service = AbilityInvocationService()

    def _fake_status(*, executor_id: str):
        raise HTTPException(status_code=502, detail="COMFYUI_QUEUE_STATUS_ERROR")

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)
    picked = service._select_comfyui_executor(
        [SimpleNamespace(id="executor_a")],
        policy="auto",
        route_by_queue=True,
        ability_id="ability_test",
        preferred_order=["executor_a"],
    )
    assert picked is None


def test_pick_comfyui_executor_by_queue_allows_reachable_executor_without_queue_endpoint(monkeypatch):
    service = AbilityInvocationService()

    def _fake_status(*, executor_id: str):
        return {"supported": False}

    def _fake_system_stats(*, executor_id: str):
        return {"executorId": executor_id, "system": {}, "devices": []}

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)
    monkeypatch.setattr(integration_test_service, "get_comfyui_system_stats", _fake_system_stats)
    picked = service._pick_comfyui_executor_by_queue(["executor_a"])
    assert picked == "executor_a"


def test_queue_policy_does_not_fallback_to_first_when_health_unknown(monkeypatch):
    service = AbilityInvocationService()

    def _fake_status(*, executor_id: str):
        raise HTTPException(status_code=502, detail="COMFYUI_QUEUE_STATUS_ERROR")

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)
    picked = service._select_comfyui_executor(
        [SimpleNamespace(id="executor_a"), SimpleNamespace(id="executor_b")],
        policy="queue",
        route_by_queue=True,
        ability_id="ability_test",
        preferred_order=["executor_a", "executor_b"],
    )
    assert picked is None


def test_allowed_comfyui_executors_do_not_escape_to_legacy_default_when_unreachable(monkeypatch):
    service = AbilityInvocationService()
    ability = SimpleNamespace(
        id="ability_test",
        capability_key="flux_strong_hq_softstyle_fission",
        extra_metadata={
            "allowed_executor_ids": ["executor_a", "executor_b"],
            "routing_policy": "queue",
            "fallback_to_default": True,
        },
    )

    monkeypatch.setattr(
        service,
        "_prepare_comfyui_candidates",
        lambda executor_ids, required_tags: [SimpleNamespace(id=eid) for eid in executor_ids],
    )

    def _fake_status(*, executor_id: str):
        raise HTTPException(status_code=502, detail="COMFYUI_QUEUE_STATUS_ERROR")

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)

    picked = service._pick_comfyui_executor_id(ability, {})
    assert picked is None


def test_global_default_does_not_override_multi_executor_queue_policy(monkeypatch):
    service = AbilityInvocationService()
    ability = SimpleNamespace(
        id="ability_test",
        capability_key="flux_strong_hq_softstyle_fission",
        extra_metadata={
            "allowed_executor_ids": ["executor_a", "executor_b"],
            "routing_policy": "queue",
            "fallback_to_default": True,
        },
    )

    monkeypatch.setattr(
        ability_invocation_module,
        "get_settings",
        lambda: SimpleNamespace(
            comfyui_default_executor_id="executor_a",
            comfyui_route_by_queue=True,
            comfyui_queue_batch_size=10,
        ),
    )
    monkeypatch.setattr(
        service,
        "_prepare_comfyui_candidates",
        lambda executor_ids, required_tags: [SimpleNamespace(id=eid) for eid in executor_ids],
    )
    monkeypatch.setattr(service, "_count_internal_comfyui_queued", lambda executor_id: 0)

    def _fake_status(*, executor_id: str):
        if executor_id == "executor_a":
            return {"runningCount": 4, "pendingCount": 2, "supported": True}
        return {"runningCount": 0, "pendingCount": 0, "supported": True}

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)

    picked = service._pick_comfyui_executor_id(ability, {})

    assert picked == "executor_b"


def test_exact_workflow_binding_does_not_reroute_when_compatible_executor_excluded(monkeypatch):
    service = AbilityInvocationService()
    ability = SimpleNamespace(
        id="ability_test",
        capability_key="flux_strong_hq_softstyle_fission",
        extra_metadata={
            "workflow_key": "flux_strong_hq_softstyle_fission",
            "routing_policy": "queue",
            "fallback_to_default": True,
        },
    )

    monkeypatch.setattr(
        service,
        "_prepare_comfyui_candidates",
        lambda executor_ids, required_tags: [SimpleNamespace(id=eid) for eid in executor_ids],
    )

    def _fake_status(*, executor_id: str):
        return {"runningCount": 0, "pendingCount": 0, "supported": True}

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)

    picked = service._pick_comfyui_executor_id(
        ability,
        {},
        exclude_executor_ids=["executor_comfyui_pattern_extract_158"],
    )
    assert picked is None


def test_exact_workflow_binding_uses_compatible_executor_even_if_other_node_is_less_busy(monkeypatch):
    service = AbilityInvocationService()
    ability = SimpleNamespace(
        id="ability_test",
        capability_key="flux_strong_hq_softstyle_fission",
        extra_metadata={
            "workflow_key": "flux_strong_hq_softstyle_fission",
            "routing_policy": "queue",
            "fallback_to_default": True,
        },
    )

    monkeypatch.setattr(
        service,
        "_prepare_comfyui_candidates",
        lambda executor_ids, required_tags: [SimpleNamespace(id=eid) for eid in executor_ids],
    )

    def _fake_status(*, executor_id: str):
        if executor_id == "executor_comfyui_pattern_extract_158":
            return {"runningCount": 1, "pendingCount": 3, "supported": True}
        return {"runningCount": 0, "pendingCount": 0, "supported": True}

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)

    picked = service._pick_comfyui_executor_id(ability, {})
    assert picked == "executor_comfyui_pattern_extract_158"


def test_nested_routing_allowed_ids_override_legacy_top_level_ids(monkeypatch):
    service = AbilityInvocationService()
    ability = SimpleNamespace(
        id="ability_test",
        capability_key="flux_strong_hq_softstyle_fission",
        extra_metadata={
            "workflow_key": "flux_strong_hq_softstyle_fission",
            "routing_policy": "queue",
            "allowed_executor_ids": [
                "executor_comfyui_seamless_117",
                "executor_comfyui_pattern_extract_158",
            ],
            "routing": {
                "workflow_key": "flux_strong_hq_softstyle_fission",
                "selection_policy": "queue",
                "fallback_to_default": False,
                "allowed_executor_ids": ["executor_comfyui_pattern_extract_158"],
            },
        },
    )

    monkeypatch.setattr(
        service,
        "_prepare_comfyui_candidates",
        lambda executor_ids, required_tags: [SimpleNamespace(id=eid) for eid in executor_ids],
    )

    def _fake_status(*, executor_id: str):
        return {"runningCount": 0, "pendingCount": 0, "supported": True}

    monkeypatch.setattr(integration_test_service, "get_comfyui_queue_status", _fake_status)

    picked = service._pick_comfyui_executor_id(ability, {})

    assert picked == "executor_comfyui_pattern_extract_158"
