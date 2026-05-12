from __future__ import annotations

from datetime import datetime

from app.schemas.eval import EvalWorkflowVersionResponse
from app.services.eval_workflow_routing_governance import resolve_eval_workflow_routing_governance


def test_comfyui_fission_routing_governance_requires_podi_task() -> None:
    governance = resolve_eval_workflow_routing_governance(
        workflow_id="7631838631375667200",
        name="图裂变 · Liebian_comfyui_20260423",
        category="图裂变",
        output_schema={"fields": [{"name": "output", "type": "text", "description": "回调 task id"}]},
    )

    assert governance["abilityType"] == "fission"
    assert governance["executionSurface"] == "comfyui"
    assert governance["trackingRequired"] is True
    assert governance["expectedTracking"] == "podi_task"
    assert governance["governanceStatus"] == "needs_task_model"


def test_vendor_workflow_routing_governance_targets_vendor_api_ops() -> None:
    governance = resolve_eval_workflow_routing_governance(
        workflow_id="7598848725942796288",
        name="图裂变 · 商业模型有提示词",
        category="图裂变",
        output_schema={"fields": [{"name": "output", "type": "text", "description": "回调 task id"}]},
    )

    assert governance["executionSurface"] == "vendor_api_ops"
    assert governance["expectedTracking"] == "vendor_task"
    assert governance["governanceStatus"] == "needs_vendor_task_model"


def test_internal_callback_workflow_does_not_require_business_tracking() -> None:
    governance = resolve_eval_workflow_routing_governance(
        workflow_id="7597556718159003648",
        name="ComfyUI 回调 · comfyui_huidiao",
        category="通用类",
        output_schema={"fields": [{"name": "images", "type": "array"}]},
    )

    assert governance["entryMode"] == "internal_tool"
    assert governance["executionSurface"] == "backend_internal"
    assert governance["trackingRequired"] is False
    assert governance["governanceStatus"] == "internal_only"


def test_vl_workflow_routing_governance_uses_vendor_log_not_image_task() -> None:
    governance = resolve_eval_workflow_routing_governance(
        workflow_id="7625930748914040832",
        name="图片打标签 · 结构化打标版",
        category="图像理解",
        output_schema={"fields": [{"name": "output", "type": "json", "description": "JSON 标签"}]},
    )

    assert governance["abilityType"] == "image_analysis"
    assert governance["executionSurface"] == "vendor_api_ops"
    assert governance["expectedTracking"] == "vendor_invocation_log"
    assert governance["governanceStatus"] == "needs_vendor_governance"


def test_workflow_response_serializes_routing_governance_without_overloading_catalog_governance() -> None:
    governance = resolve_eval_workflow_routing_governance(
        workflow_id="7631838631375667200",
        name="图裂变 · Liebian_comfyui_20260423",
        category="图裂变",
        output_schema={"fields": [{"name": "output", "type": "text", "description": "回调 task id"}]},
    )
    payload = EvalWorkflowVersionResponse(
        id="wf_001",
        category="图裂变",
        name="图裂变 · Liebian_comfyui_20260423",
        version="v1",
        workflow_id="7631838631375667200",
        status="active",
        governance={"role": "production", "roleLabel": "生产主入口"},
        routingGovernance=governance,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    ).model_dump(by_alias=True)

    assert payload["governance"]["role"] == "production"
    assert payload["routingGovernance"]["executionSurface"] == "comfyui"
