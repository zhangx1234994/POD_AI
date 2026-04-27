from __future__ import annotations

from datetime import datetime

from app.models.eval import EvalWorkflowVersion
from app.services.eval_workflow_response import build_eval_workflow_response_metadata, is_eval_workflow_publicly_visible


def _workflow(**overrides) -> EvalWorkflowVersion:
    data = {
        "id": "wf-row",
        "category": "图裂变",
        "name": "图裂变 · Liebian_comfyui_20260328_1",
        "version": "v1",
        "workflow_id": "7622193261276299264",
        "status": "active",
        "parameters_schema": {"fields": [{"name": "url"}, {"name": "count", "defaultValue": "4"}]},
        "output_schema": {"fields": [{"name": "output", "description": "回调 task id"}]},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    data.update(overrides)
    return EvalWorkflowVersion(**data)


def test_eval_workflow_response_exposes_business_catalog_role() -> None:
    payload = build_eval_workflow_response_metadata(_workflow())

    assert payload["presentation"]["operationLabel"] == "图像裂变"
    assert payload["presentation"]["variantLabel"] == "ComfyUI 新版"
    assert payload["usage"]["batchEnabled"] is True
    assert payload["governance"] == {
        "role": "candidate",
        "roleLabel": "灰度/对照版本",
        "roleReason": "用于灰度验证或与主线结果对照。",
        "rank": 30,
        "isPrimary": False,
    }


def test_eval_workflow_cleanup_override_hides_deprecated_public_entry() -> None:
    row = _workflow(
        category="图延伸类",
        name="ComfyUI 扩图 · comfyuo_tukuozhan",
        workflow_id="7598587935331450880",
    )

    payload = build_eval_workflow_response_metadata(row)

    assert payload["deprecation"]["isDeprecated"] is True
    assert payload["governance"]["role"] == "legacy"
    assert is_eval_workflow_publicly_visible(row) is False
