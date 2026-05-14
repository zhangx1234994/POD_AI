from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_business_sample_pack.py"
SPEC = importlib.util.spec_from_file_location("export_business_sample_pack", SCRIPT_PATH)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def test_sample_pack_extracts_input_output_vl_and_executor() -> None:
    run = {
        "id": "run_1",
        "request_payload": {"imageUrl": "https://oss.example.com/input.png", "apiKey": "secret"},
        "image_urls": ["https://oss.example.com/output.png"],
        "flow_summary": {"executor": {"id": "executor_158", "name": "ComfyUI 5090"}},
        "steps": [
            {
                "id": "step_vl",
                "step_type": "vl_analyze",
                "display_name": "VL 分析",
                "status": "succeeded",
                "result_summary": {"vlCard": {"pattern_type": "floral"}, "imageDesc": "花卉"},
            },
            {
                "id": "step_primary",
                "role": "primary",
                "executor_id": "executor_158",
                "execution_evidence": {"storedUrl": "https://oss.example.com/output.png"},
            },
        ],
    }

    assert exporter._extract_input_urls(run) == ["https://oss.example.com/input.png"]
    assert "https://oss.example.com/output.png" in exporter._extract_output_urls(run)
    assert exporter._extract_vl_payloads(run)[0]["resultSummary"]["vlCard"]["pattern_type"] == "floral"
    assert exporter._extract_executor_ids(run) == ["executor_158"]
    assert exporter._matches_executor(run, "executor_158") is True
    assert exporter._matches_executor(run, "executor_233") is False


def test_sample_pack_redacts_sensitive_fields() -> None:
    payload = {
        "headers": {"Authorization": "Bearer abc"},
        "api_key": "sk-test",
        "nested": [{"vendorToken": "token"}],
        "url": "https://oss.example.com/a.png",
    }

    redacted = exporter._redact(payload)

    assert redacted["headers"]["Authorization"] == "[redacted]"
    assert redacted["api_key"] == "[redacted]"
    assert redacted["nested"][0]["vendorToken"] == "[redacted]"
    assert redacted["url"] == "https://oss.example.com/a.png"


def test_summary_row_is_business_readable() -> None:
    run = {
        "id": "run_1",
        "business_key": "fission",
        "version": "comfyui-vl-control-v2",
        "status": "succeeded",
        "source": "eval",
        "image_urls": ["https://oss.example.com/out.png"],
        "request_payload": {"url": "https://oss.example.com/in.png"},
        "flow_summary": {
            "executor": {"id": "executor_233", "name": "ComfyUI 4090"},
            "output": {"imageCount": 1, "videoCount": 0, "textCount": 0},
        },
        "steps": [],
    }

    row = exporter._summary_row(run)

    assert row["run_id"] == "run_1"
    assert row["business_key"] == "fission"
    assert row["executor_name"] == "ComfyUI 4090"
    assert row["image_count"] == 1
    assert row["input_urls"] == "https://oss.example.com/in.png"
    assert row["output_urls"] == "https://oss.example.com/out.png"
