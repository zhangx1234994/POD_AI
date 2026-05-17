from __future__ import annotations

from datetime import datetime

from app.models.eval import EvalWorkflowVersion
from app.models.integration import BusinessCapability
from app.routers.evals_public import _dedupe_workflow_versions, _serialize_workflow_version


def _workflow(row_id: str, *, category: str, workflow_id: str) -> EvalWorkflowVersion:
    return EvalWorkflowVersion(
        id=row_id,
        category=category,
        name="四方连续裂变",
        version="v1",
        workflow_id=workflow_id,
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_public_workflow_dedupe_uses_workflow_id_across_categories() -> None:
    rows = [
        _workflow("row_1", category="四方/两方连续图类", workflow_id="7629026792103215104"),
        _workflow("row_2", category="图裂变", workflow_id="7629026792103215104"),
        _workflow("row_3", category="图裂变", workflow_id="7631838631375667200"),
    ]

    deduped = _dedupe_workflow_versions(rows)

    assert [row.id for row in deduped] == ["row_1", "row_3"]


def test_business_eval_catalog_entry_uses_business_capability_schema() -> None:
    now = datetime.utcnow()
    row = EvalWorkflowVersion(
        id="eval_business_fission",
        category="图裂变",
        name="旧测评端名称",
        version="old-v1",
        workflow_id="business_fission_comfyui_vl_control_v1",
        status="active",
        parameters_schema={"fields": [{"name": "url", "type": "text", "defaultValue": "old"}]},
        output_schema={"fields": [{"name": "output", "type": "text"}]},
        extra_metadata={
            "eval_execution": {
                "mode": "business_run",
                "business_key": "fission",
                "version": "comfyui-vl-control-v2",
            },
            "governance": {"role": "candidate"},
        },
        created_at=now,
        updated_at=now,
    )
    capability = BusinessCapability(
        id="biz_fission_colorlock",
        business_key="fission",
        version="comfyui-vl-control-v2",
        display_name="图裂变 · ComfyUI 颜色锁定版",
        description="业务版本描述",
        status="active",
        is_default=False,
        release_time=now,
        recipe={"steps": []},
        input_schema={
            "fields": [
                {"name": "imageUrl", "type": "text", "label": "原图 URL", "required": True},
                {"name": "bili", "type": "text", "label": "重绘幅度", "default": "80%"},
            ]
        },
        output_schema={"fields": [{"name": "imageUrls", "type": "array", "label": "结果图片"}]},
        extra_metadata={"badge": "新版", "provider": "comfyui"},
        created_at=now,
        updated_at=now,
    )

    payload = _serialize_workflow_version(row, {("fission", "comfyui-vl-control-v2"): capability})

    assert payload.name == "图裂变 · ComfyUI 颜色锁定版"
    assert payload.version == "comfyui-vl-control-v2"
    fields = {field["name"]: field for field in payload.parameters_schema["fields"]}
    assert "url" not in fields
    assert fields["imageUrl"]["required"] is True
    assert fields["bili"]["defaultValue"] == "80%"
    assert payload.presentation["operationLabel"] == "图像裂变"
    assert payload.presentation["variantLabel"] == "ComfyUI 颜色锁定版"
    assert "原生业务接口" in payload.presentation["badges"]
    assert payload.metadata["source_of_truth"]["schema"] == "business_capabilities.input_schema"
