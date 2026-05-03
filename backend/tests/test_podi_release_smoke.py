from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_smoke_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "podi_release_smoke.py"
    spec = importlib.util.spec_from_file_location("podi_release_smoke", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_eval_workflow_catalog_check_accepts_public_roles() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [
            {"workflow_id": "wf_prod", "governance": {"role": "production"}, "presentation": {"visible": True}},
            {"workflow_id": "wf_candidate", "governance": {"role": "candidate"}, "presentation": {"visible": True}},
        ]
    )

    assert ok is True
    assert "production" in detail


def test_eval_workflow_catalog_check_blocks_leaked_internal_roles() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [
            {"workflow_id": "wf_prod", "governance": {"role": "production"}, "presentation": {"visible": True}},
            {"workflow_id": "wf_aux", "governance": {"role": "auxiliary"}, "presentation": {"visible": True}},
        ]
    )

    assert ok is False
    assert "non-public roles leaked" in detail


def test_eval_workflow_catalog_check_blocks_duplicate_workflow_ids() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [
            {
                "workflow_id": "wf_prod",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
            {
                "workflow_id": "wf_prod",
                "category": "四方/两方连续图类",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
        ]
    )

    assert ok is False
    assert "duplicated workflow ids" in detail


def test_eval_workflow_catalog_check_requires_a_production_entry() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [{"workflow_id": "wf_candidate", "governance": {"role": "candidate"}, "presentation": {"visible": True}}]
    )

    assert ok is False
    assert "no production workflow" in detail


def test_eval_workflow_catalog_check_blocks_too_many_production_entries_per_category() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [
            {
                "workflow_id": "wf_prod_1",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
            {
                "workflow_id": "wf_prod_2",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
            {
                "workflow_id": "wf_prod_3",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
        ],
        max_production_per_category=2,
    )

    assert ok is False
    assert "too many production workflows" in detail


def test_eval_workflow_catalog_check_allows_configured_production_limit() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [
            {
                "workflow_id": "wf_prod_1",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
            {
                "workflow_id": "wf_prod_2",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
            {
                "workflow_id": "wf_candidate",
                "category": "图裂变",
                "governance": {"role": "candidate"},
                "presentation": {"visible": True},
            },
        ],
        max_production_per_category=2,
    )

    assert ok is True
    assert "productionByCategory" in detail


def test_comfyui_queue_summary_check_blocks_unavailable_executors() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_comfyui_queue_summary(
        {
            "servers": [{"executorId": "executor_233"}],
            "unsupportedServers": 1,
            "backendBlockedServers": 0,
            "diagnostics": [{"code": "COMFYUI_EXECUTOR_UNAVAILABLE"}],
        }
    )

    assert ok is False
    assert "unsupportedServers=1" in detail


def test_comfyui_queue_summary_check_blocks_backend_running_not_visible() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_comfyui_queue_summary(
        {
            "servers": [{"executorId": "executor_158"}],
            "unsupportedServers": 0,
            "backendBlockedServers": 1,
            "diagnostics": [{"code": "COMFYUI_BACKEND_RUNNING_NOT_VISIBLE"}],
        }
    )

    assert ok is False
    assert "backendBlockedServers=1" in detail


def test_comfyui_queue_summary_check_allows_feed_gap_as_warning_detail() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_comfyui_queue_summary(
        {
            "servers": [{"executorId": "executor_158"}, {"executorId": "executor_233"}],
            "unsupportedServers": 0,
            "backendBlockedServers": 0,
            "feedGapServers": 1,
            "totalCapacity": 20,
            "totalIdleSlots": 8,
            "utilization": 0.6,
            "diagnostics": [{"code": "COMFYUI_FEED_GAP"}],
        }
    )

    assert ok is True
    assert "feedGapServers=1" in detail
