from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "patrol_eval_workflows.py"
SPEC = importlib.util.spec_from_file_location("patrol_eval_workflows", SCRIPT_PATH)
assert SPEC and SPEC.loader
patrol = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patrol)


def test_report_item_marks_success_without_output_as_failure() -> None:
    item = patrol._make_report_item(
        {
            "workflow": {"name": "图裂变", "workflow_id": "wf_1"},
            "run": {"id": "run_1"},
            "latest": {
                "id": "run_1",
                "status": "succeeded",
                "result_image_urls_json": [],
                "result_output_json": None,
            },
        }
    )

    assert item["hasOutput"] is False
    assert item["imageCount"] == 0
    assert item["issueCode"] == "EVAL_SUCCEEDED_WITHOUT_OUTPUT"
    assert patrol._failed_items([item]) == [item]


def test_report_item_accepts_structured_output_without_images() -> None:
    item = patrol._make_report_item(
        {
            "workflow": {"name": "标签识别", "workflow_id": "wf_json"},
            "run": {"id": "run_json"},
            "latest": {
                "id": "run_json",
                "status": "succeeded",
                "result_image_urls_json": [],
                "result_output_json": {"tags": ["印花"]},
            },
        }
    )

    assert item["hasOutput"] is True
    assert item["issueCode"] == ""
    assert patrol._failed_items([item]) == []


def test_report_item_classifies_internal_only_and_coze_workflow_error() -> None:
    internal_only = patrol._make_report_item(
        {
            "workflow": {"name": "图裂变", "workflow_id": "wf_1"},
            "run": {"id": "run_1"},
            "latest": {
                "id": "run_1",
                "status": "failed",
                "error_message": 'status=401 Unauthorized resp={"detail":"INTERNAL_ONLY"}',
            },
        }
    )
    coze_failed = patrol._make_report_item(
        {
            "workflow": {"name": "图裂变", "workflow_id": "wf_2"},
            "run": {"id": "run_2"},
            "latest": {
                "id": "run_2",
                "status": "failed",
                "error_code": "COZE_WORKFLOW_ERROR",
                "error_message": "Workflow execution failure",
            },
        }
    )

    assert internal_only["issueCode"] == "INTERNAL_ONLY"
    assert coze_failed["issueCode"] == "COZE_WORKFLOW_ERROR"


def test_allow_empty_output_keeps_legacy_terminal_status_check() -> None:
    item = {
        "status": "succeeded",
        "hasOutput": False,
        "issueCode": "EVAL_SUCCEEDED_WITHOUT_OUTPUT",
    }

    assert patrol._failed_items([item]) == [item]
    assert patrol._failed_items([item], allow_empty_output=True) == []
