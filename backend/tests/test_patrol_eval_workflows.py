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
    assert item["outputKind"] == "structured"
    assert item["issueCode"] == ""
    assert patrol._failed_items([item]) == []


def test_report_item_accepts_video_output_without_images() -> None:
    item = patrol._make_report_item(
        {
            "workflow": {"name": "图生视频", "workflow_id": "wf_video"},
            "run": {"id": "run_video"},
            "latest": {
                "id": "run_video",
                "status": "succeeded",
                "result_image_urls_json": [],
                "videoUrls": ["https://oss.example.com/out.mp4"],
                "result_output_json": None,
            },
        }
    )

    assert item["hasOutput"] is True
    assert item["videoCount"] == 1
    assert item["outputKind"] == "video"
    assert item["issueCode"] == ""
    assert patrol._failed_items([item]) == []


def test_report_item_accepts_text_output_without_images() -> None:
    item = patrol._make_report_item(
        {
            "workflow": {"name": "VL 分析", "workflow_id": "wf_text"},
            "run": {"id": "run_text"},
            "latest": {
                "id": "run_text",
                "status": "succeeded",
                "result_image_urls_json": [],
                "result_output_json": "图片主体是蓝色花纹",
            },
        }
    )

    assert item["hasOutput"] is True
    assert item["textCount"] == 1
    assert item["outputKind"] == "text"
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


def test_report_item_classifies_queue_full_and_prompt_required() -> None:
    queue_full = patrol._make_report_item(
        {
            "workflow": {"name": "图裂变", "workflow_id": "wf_queue"},
            "run": {"id": "run_queue"},
            "latest": {
                "id": "run_queue",
                "status": "failed",
                "error_message": "ERR|Q1001|COMFYUI_QUEUE_FULL(limit=10, current=10)",
            },
        }
    )
    prompt_required = patrol._make_report_item(
        {
            "workflow": {"name": "多模型生图", "workflow_id": "wf_prompt"},
            "run": {"id": "run_prompt"},
            "latest": {
                "id": "run_prompt",
                "status": "failed",
                "error_code": "PROMPT_REQUIRED",
                "error_message": "prompt is required",
            },
        }
    )

    assert queue_full["issueCode"] == "COMFYUI_QUEUE_FULL"
    assert prompt_required["issueCode"] == "PROMPT_REQUIRED"


def test_allow_empty_output_keeps_legacy_terminal_status_check() -> None:
    item = {
        "status": "succeeded",
        "hasOutput": False,
        "issueCode": "EVAL_SUCCEEDED_WITHOUT_OUTPUT",
    }

    assert patrol._failed_items([item]) == [item]
    assert patrol._failed_items([item], allow_empty_output=True) == []


def test_select_workflows_defaults_to_production_role() -> None:
    items = [
        {"workflow_id": "wf_prod", "category": "图裂变", "governance": {"role": "production"}},
        {"workflow_id": "wf_candidate", "category": "图裂变", "governance": {"role": "candidate"}},
        {"workflow_id": "wf_other", "category": "扩图", "metadata": {"governance": {"role": "production"}}},
    ]

    selected = patrol._select_workflows(items, category="图裂变", role_filter="production", limit=0)

    assert [item["workflow_id"] for item in selected] == ["wf_prod"]


def test_select_workflows_can_run_all_or_multiple_roles() -> None:
    items = [
        {"workflow_id": "wf_prod", "governance": {"role": "production"}},
        {"workflow_id": "wf_candidate", "metadata": '{"governance":{"role":"candidate"}}'},
        {"workflow_id": "wf_legacy", "metadata": {"governance_role": "legacy"}},
    ]

    all_selected = patrol._select_workflows(items, category="", role_filter="all", limit=0)
    selected = patrol._select_workflows(items, category="", role_filter="production,candidate", limit=0)

    assert [item["workflow_id"] for item in all_selected] == ["wf_prod", "wf_candidate", "wf_legacy"]
    assert [item["workflow_id"] for item in selected] == ["wf_prod", "wf_candidate"]


def test_build_params_replaces_blank_schema_defaults_for_patrol() -> None:
    workflow = {
        "parameters_schema": {
            "fields": [
                {"name": "url", "defaultValue": ""},
                {"name": "prompt", "defaultValue": ""},
                {"name": "width", "defaultValue": ""},
                {"name": "height", "defaultValue": ""},
                {"name": "image_urls", "defaultValue": ""},
            ]
        }
    }

    params = patrol._build_params(workflow, "https://oss.example/input.png", "tag_1")

    assert params["url"] == "https://oss.example/input.png"
    assert params["prompt"]
    assert params["width"] == 1024
    assert params["height"] == 1024
    assert params["image_urls"] == ["https://oss.example/input.png"]
