from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_probe_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "comfyui_capacity_probe.py"
    spec = importlib.util.spec_from_file_location("comfyui_capacity_probe", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_capacity_probe_peak_queue_metrics_tracks_servers() -> None:
    module = _load_probe_module()

    metrics = module._peak_queue_metrics(
        [
            {
                "queue": {"totalCount": 4, "totalRunning": 2, "totalPending": 2},
                "serverQueueCounts": {"executor_a": 1, "executor_b": 3},
            },
            {
                "queue": {"totalCount": 7, "totalRunning": 3, "totalPending": 4},
                "serverQueueCounts": {"executor_a": 4, "executor_b": 3},
            },
        ]
    )

    assert metrics["peakQueueTotal"] == 7
    assert metrics["peakRunning"] == 3
    assert metrics["peakPending"] == 4
    assert metrics["peakServerQueueCounts"] == {"executor_a": 4, "executor_b": 3}


def test_capacity_probe_assessment_enforces_thresholds() -> None:
    module = _load_probe_module()

    report = {
        "submittedTaskIds": ["task_1", "task_2", "task_3"],
        "finalStatusCounts": {"succeeded": 3},
        "finalExecutorCounts": {"executor_a": 2, "executor_b": 1},
        "peakQueueTotal": 6,
    }

    ok, issues = module._assess_report(
        report,
        min_peak_queue_total=5,
        min_used_executors=2,
        min_successful_tasks=3,
    )

    assert ok is True
    assert issues == []


def test_capacity_probe_assessment_fails_when_queue_does_not_fill() -> None:
    module = _load_probe_module()

    report = {
        "submittedTaskIds": ["task_1", "task_2"],
        "finalStatusCounts": {"succeeded": 2},
        "finalExecutorCounts": {"executor_a": 2},
        "peakQueueTotal": 2,
    }

    ok, issues = module._assess_report(
        report,
        min_peak_queue_total=10,
        min_used_executors=2,
        min_successful_tasks=2,
    )

    assert ok is False
    assert any("峰值队列" in issue for issue in issues)
    assert any("执行节点" in issue for issue in issues)


def test_capacity_probe_sample_image_check_rejects_http_errors(monkeypatch) -> None:
    module = _load_probe_module()

    class FakeResponse:
        status_code = 404
        headers = {"content-type": "application/xml"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def head(self, url):
            return FakeResponse()

    monkeypatch.setattr(module.httpx, "Client", FakeClient)

    ok, detail = module._check_sample_image_url("https://example.com/missing.png")

    assert ok is False
    assert "HTTP 404" in detail


def test_capacity_probe_sample_image_check_accepts_images(monkeypatch) -> None:
    module = _load_probe_module()

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "image/png"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def head(self, url):
            return FakeResponse()

    monkeypatch.setattr(module.httpx, "Client", FakeClient)

    ok, detail = module._check_sample_image_url("https://example.com/a.png")

    assert ok is True
    assert "HTTP 200" in detail
