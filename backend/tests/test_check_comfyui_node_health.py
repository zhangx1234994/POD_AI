from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_comfyui_node_health.py"
    spec = importlib.util.spec_from_file_location("check_comfyui_node_health", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_executor_arg_requires_id_and_url() -> None:
    module = _load_module()

    target = module._parse_executor_arg("executor_158=http://117.50.80.158:8079/")

    assert target.executor_id == "executor_158"
    assert target.base_url == "http://117.50.80.158:8079"


def test_parse_executor_arg_rejects_missing_url_scheme() -> None:
    module = _load_module()

    with pytest.raises(Exception):
        module._parse_executor_arg("executor_158=117.50.80.158:8079")


def test_summarize_node_payloads() -> None:
    module = _load_module()

    system = module._summarize_system_stats(
        {
            "system": {
                "os": "win32",
                "comfyui_version": "0.12.0",
                "python_version": "3.11.9",
                "pytorch_version": "2.7.0+cu128",
                "ram_total": 100,
                "ram_free": 60,
            },
            "devices": [{"name": "cuda:0 RTX 5090", "type": "cuda", "vram_total": 32, "vram_free": 30}],
        }
    )
    queue = module._summarize_queue({"queue_running": [1], "queue_pending": [2, 3]})
    object_info = module._summarize_object_info({"KSampler": {}, "SaveImage": {}, "LoadImage": {}}, ["KSampler", "SaveImage"])

    assert system["comfyuiVersion"] == "0.12.0"
    assert system["deviceCount"] == 1
    assert queue == {"runningCount": 1, "pendingCount": 2, "totalCount": 3}
    assert object_info["nodeCount"] == 3
    assert object_info["missingRequiredClasses"] == []


def test_assess_node_blocks_missing_gpu_and_required_class() -> None:
    module = _load_module()

    ok, issues = module._assess_node(
        {
            "systemStatsStatus": 200,
            "queueStatus": 200,
            "objectInfoStatus": 200,
            "system": {"deviceCount": 0},
            "objectInfo": {"nodeCount": 1, "missingRequiredClasses": ["LoadImage"]},
        }
    )

    assert ok is False
    assert any("GPU" in item for item in issues)
    assert any("LoadImage" in item for item in issues)


def test_backend_summary_assessment_blocks_missing_and_blocked_servers() -> None:
    module = _load_module()

    summary = module._summarize_backend_route_summary(
        {
            "totalCapacity": 10,
            "totalIdleSlots": 5,
            "supportedServers": 1,
            "unsupportedServers": 0,
            "backendBlockedServers": 1,
            "servers": [
                {
                    "executorId": "executor_158",
                    "supported": True,
                    "diagnosisLevel": "success",
                    "feedDiagnosisLevel": "success",
                }
            ],
        },
        ["executor_158", "executor_233"],
    )
    ok, issues = module._assess_backend_summary(summary)

    assert summary["missingExpectedExecutors"] == ["executor_233"]
    assert ok is False
    assert any("缺少节点" in item for item in issues)
    assert any("backendBlockedServers=1" in item for item in issues)


def test_build_report_combines_node_and_backend_checks(monkeypatch) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module,
        "check_nodes",
        lambda **kwargs: [{"executorId": "executor_158", "ok": True, "issues": []}],
    )
    monkeypatch.setattr(
        module,
        "check_backend_summary",
        lambda **kwargs: {"ok": True, "issues": [], "totalCapacity": 10},
    )

    report = module.build_report(
        targets=[module.ExecutorTarget("executor_158", "http://117.50.80.158:8079")],
        required_classes=["KSampler"],
        backend_url="http://127.0.0.1:8099",
        timeout=3,
    )

    assert report["ok"] is True
    assert report["nodes"][0]["executorId"] == "executor_158"
    assert report["backendSummary"]["totalCapacity"] == 10
