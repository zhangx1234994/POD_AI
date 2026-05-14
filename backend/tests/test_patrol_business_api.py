from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "patrol_business_api.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("patrol_business_api", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_core_business_specs_are_complete() -> None:
    module = _load_module()

    keys = [spec.key for spec in module.BUSINESS_SPECS]

    assert keys == ["pattern_extract", "fission", "outpaint"]


def test_select_specs_rejects_unknown_business() -> None:
    module = _load_module()

    try:
        module._select_specs("fission,unknown")
    except ValueError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("unknown business key should be rejected")


def test_build_payload_adds_trace_context_and_business_fields() -> None:
    module = _load_module()
    spec = module._select_specs("pattern_extract")[0]

    payload = module._build_payload(spec, image_url="https://example.com/a.png", tag="t1")

    assert payload["imageUrl"] == "https://example.com/a.png"
    assert payload["traceId"] == "patrol-pattern_extract-t1"
    assert payload["tenantId"] == "podi-internal-patrol"
    assert payload["batch"] == 1
    assert payload["negative_prompt"]


def test_validate_terminal_run_requires_success_and_output() -> None:
    module = _load_module()

    ok, detail = module._validate_terminal_run({"status": "succeeded", "imageUrls": ["https://example.com/out.png"]})
    assert ok is True
    assert "outputs=1" in detail

    ok, detail = module._validate_terminal_run({"status": "succeeded", "imageUrls": []})
    assert ok is False
    assert "no output" in detail

    ok, detail = module._validate_terminal_run({"status": "failed", "error": "COMFYUI_TIMEOUT"})
    assert ok is False
    assert "COMFYUI_TIMEOUT" in detail


def test_validate_terminal_run_can_require_executor_evidence() -> None:
    module = _load_module()

    ok, detail = module._validate_terminal_run(
        {"status": "succeeded", "imageUrls": ["https://example.com/out.png"]},
        require_executor_evidence=True,
    )
    assert ok is False
    assert "no executor evidence" in detail

    ok, detail = module._validate_terminal_run(
        {
            "status": "succeeded",
            "imageUrls": ["https://example.com/out.png"],
            "flowSummary": {"executor": {"name": "ComfyUI 4090"}},
        },
        require_executor_evidence=True,
    )
    assert ok is True
    assert "ComfyUI 4090" in detail


def test_live_poll_signature_stays_compatible() -> None:
    module = _load_module()

    called: dict[str, object] = {}

    class FakeClient:
        def post(self, path: str, json: dict[str, object]):
            called["path"] = path
            called["payload"] = json

            class Response:
                status_code = 200

                def json(self):
                    return {"runId": "run-1"}

            return Response()

    def fake_poll_run(client, run_id, *, timeout_seconds, interval_seconds, detail_full=False):
        called["run_id"] = run_id
        called["timeout_seconds"] = timeout_seconds
        called["interval_seconds"] = interval_seconds
        called["detail_full"] = detail_full
        return {"status": "succeeded", "imageUrls": ["https://example.com/out.png"]}

    module._poll_run = fake_poll_run

    item = module._run_live(
        FakeClient(),
        module._select_specs("fission")[0],
        {"imageUrl": "https://example.com/in.png"},
        timeout_seconds=10,
        interval_seconds=1,
        require_executor_evidence=False,
    )

    assert item["ok"] is True
    assert item["businessKey"] == "fission"
    assert item["runId"] == "run-1"
    assert called["run_id"] == "run-1"
    assert called["detail_full"] is False


def test_extract_selected_capability_id_from_run_evidence() -> None:
    module = _load_module()

    assert (
        module._extract_selected_capability_id(
            {"routeInfo": {"selectedCapabilityId": "biz_fission_v2"}}
        )
        == "biz_fission_v2"
    )
    assert (
        module._extract_selected_capability_id(
            {"flowSummary": {"route": {"selectedCapabilityId": "biz_outpaint_v1"}}}
        )
        == "biz_outpaint_v1"
    )
    assert module._extract_selected_capability_id({"status": "succeeded"}) == ""


def test_record_acceptance_for_result_uses_admin_endpoint() -> None:
    module = _load_module()
    called: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        text = "{}"

        def json(self):
            return {"id": "biz_fission_v2", "latestAcceptance": {"status": "passed"}}

    class FakeClient:
        def post(self, path: str, json: dict[str, object]):
            called["path"] = path
            called["payload"] = json
            return FakeResponse()

    result = module._record_acceptance_for_result(
        FakeClient(),
        {
            "businessKey": "fission",
            "label": "图裂变",
            "mode": "live",
            "ok": True,
            "detail": "runId=run-1 status=succeeded outputs=1 executor=4090",
            "runId": "run-1",
            "response": {
                "status": "succeeded",
                "imageUrls": ["https://example.com/out.png"],
                "flowSummary": {
                    "route": {"selectedCapabilityId": "biz_fission_v2"},
                    "executor": {"name": "4090"},
                    "callback": {"status": "skipped"},
                },
            },
        },
        note="巡检通过",
        evidence_url="https://example.com/report",
        require_executor_evidence=True,
    )

    assert result["ok"] is True
    assert result["capabilityId"] == "biz_fission_v2"
    assert called["path"] == "/api/admin/business/capabilities/biz_fission_v2/acceptance-records"
    payload = called["payload"]
    assert payload["status"] == "passed"
    assert payload["note"] == "巡检通过"
    assert payload["evidenceRunId"] == "run-1"
    assert payload["evidenceUrl"] == "https://example.com/report"
    assert payload["checklist"]["businessFlow"] is True
    assert payload["checklist"]["executorEvidence"] is True
    assert payload["metadata"]["source"] == "patrol_business_api"


def test_build_summary_and_record_release_patrol() -> None:
    module = _load_module()
    called: dict[str, object] = {}
    specs = module._select_specs("fission")
    summary = module._build_summary(
        ok=True,
        mode="live",
        base_url="http://127.0.0.1:8099",
        specs=specs,
        results=[
            {
                "businessKey": "fission",
                "label": "图裂变",
                "mode": "live",
                "ok": True,
                "detail": "runId=run-1 status=succeeded outputs=1",
                "runId": "run-1",
            }
        ],
        acceptance_results=[],
        tag="t1",
    )

    class FakeResponse:
        status_code = 200
        text = "{}"

        def json(self):
            return {"id": "patrol_1", "status": "passed"}

    class FakeClient:
        def post(self, path: str, json: dict[str, object]):
            called["path"] = path
            called["payload"] = json
            return FakeResponse()

    result = module._record_release_patrol(
        FakeClient(),
        summary=summary,
        status="passed",
        report_path="reports/business_patrol.json",
        command=module._redacted_command(["patrol_business_api.py", "--token", "secret-token", "--mode", "live"]),
        note="巡检通过",
    )

    assert summary["total"] == 1
    assert summary["failedOrUnfinished"] == 0
    assert result["ok"] is True
    assert called["path"] == "/api/admin/dashboard/release-patrol/records"
    payload = called["payload"]
    assert payload["status"] == "passed"
    assert payload["reportPath"] == "reports/business_patrol.json"
    assert payload["summary"]["businessKeys"] == ["fission"]
    assert "secret-token" not in payload["command"]
    assert "--token ***" in payload["command"]


def test_write_patrol_report(tmp_path: Path) -> None:
    module = _load_module()
    report_path = tmp_path / "reports" / "business_patrol.json"

    written = module._write_report({"ok": True, "results": []}, str(report_path))

    assert written == str(report_path)
    assert report_path.exists()
    assert '"ok": true' in report_path.read_text(encoding="utf-8")


def test_image_url_precheck_rejects_http_errors(monkeypatch) -> None:
    module = _load_module()

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

    ok, detail = module._check_image_url_accessible("https://example.com/missing.png")

    assert ok is False
    assert "HTTP 404" in detail


def test_image_url_precheck_accepts_images(monkeypatch) -> None:
    module = _load_module()

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

    ok, detail = module._check_image_url_accessible("https://example.com/a.png")

    assert ok is True
    assert "HTTP 200" in detail
