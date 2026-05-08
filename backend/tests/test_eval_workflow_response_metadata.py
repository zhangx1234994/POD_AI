from __future__ import annotations

from datetime import datetime

from app.models.eval import EvalWorkflowVersion
from app.services.eval_workflow_response import (
    build_eval_workflow_response_metadata,
    is_eval_workflow_visible_for_eval_catalog,
    is_eval_workflow_publicly_visible,
    merge_eval_workflow_metadata_update,
)


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


def test_eval_workflow_unlisted_active_defaults_to_candidate() -> None:
    payload = build_eval_workflow_response_metadata(
        _workflow(
            category="花纹提取类",
            name="花纹提取 · 实验版本",
            workflow_id="unlisted_workflow_id",
        )
    )

    assert payload["governance"]["role"] == "candidate"
    assert payload["governance"]["roleLabel"] == "灰度/对照版本"
    assert payload["governance"]["isPrimary"] is False


def test_eval_workflow_known_primary_remains_production() -> None:
    payload = build_eval_workflow_response_metadata(
        _workflow(
            category="花纹提取类",
            name="花纹提取 · 当前主线",
            workflow_id="7601080398864449536",
        )
    )

    assert payload["governance"]["role"] == "production"
    assert payload["governance"]["roleLabel"] == "生产主入口"
    assert payload["governance"]["isPrimary"] is True


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


def test_eval_workflow_metadata_update_merges_governance_without_losing_blocks() -> None:
    merged = merge_eval_workflow_metadata_update(
        {
            "presentation": {"variant_label": "高质量新版", "visible": True},
            "usage": {"batch_enabled": True},
        },
        {
            "governance": {
                "role": "production",
                "roleLabel": "生产主入口",
                "roleReason": "用于业务默认入口。",
                "rank": 8,
            }
        },
    )

    assert merged == {
        "presentation": {"variant_label": "高质量新版", "visible": True},
        "usage": {"batch_enabled": True},
        "governance": {
            "role": "production",
            "roleLabel": "生产主入口",
            "roleReason": "用于业务默认入口。",
            "rank": 8,
        },
    }


def test_eval_workflow_governance_accepts_camel_case_admin_override() -> None:
    payload = build_eval_workflow_response_metadata(
        _workflow(
            extra_metadata={
                "governance": {
                    "role": "production",
                    "roleLabel": "生产主入口",
                    "roleReason": "人工标记为当前入口。",
                    "rank": 5,
                }
            }
        )
    )

    assert payload["governance"] == {
        "role": "production",
        "roleLabel": "生产主入口",
        "roleReason": "人工标记为当前入口。",
        "rank": 5,
        "isPrimary": True,
    }


def test_eval_workflow_disabled_governance_hides_public_entry() -> None:
    row = _workflow(
        extra_metadata={
            "presentation": {"visible": True},
            "governance": {
                "role": "disabled",
                "roleLabel": "已停用",
                "roleReason": "暂不作为可用入口。",
            },
        }
    )

    payload = build_eval_workflow_response_metadata(row)

    assert payload["governance"]["role"] == "disabled"
    assert payload["presentation"]["visible"] is False
    assert is_eval_workflow_publicly_visible(row) is False


def test_eval_workflow_auxiliary_governance_hides_public_entry() -> None:
    row = _workflow(
        extra_metadata={
            "presentation": {"visible": True},
            "governance": {"role": "auxiliary"},
        }
    )

    payload = build_eval_workflow_response_metadata(row)

    assert payload["governance"]["role"] == "auxiliary"
    assert payload["presentation"]["visible"] is False
    assert is_eval_workflow_publicly_visible(row) is False


def test_eval_workflow_auxiliary_can_appear_in_internal_eval_catalog() -> None:
    row = _workflow(
        category="通用类",
        name="8K 高清放大",
        workflow_id="7597760543788630016",
        extra_metadata={"governance": {"role": "auxiliary"}},
    )

    assert is_eval_workflow_publicly_visible(row) is False
    assert is_eval_workflow_visible_for_eval_catalog(row) is False
    assert is_eval_workflow_visible_for_eval_catalog(row, include_auxiliary=True) is True


def test_eval_workflow_legacy_stays_hidden_from_internal_eval_catalog() -> None:
    row = _workflow(
        category="图延伸类",
        name="ComfyUI 扩图 · comfyuo_tukuozhan",
        workflow_id="7598587935331450880",
    )

    assert is_eval_workflow_publicly_visible(row) is False
    assert is_eval_workflow_visible_for_eval_catalog(row, include_auxiliary=True) is False


def test_eval_workflow_candidate_governance_remains_public() -> None:
    row = _workflow(
        extra_metadata={
            "presentation": {"visible": True},
            "governance": {"role": "candidate"},
        }
    )

    payload = build_eval_workflow_response_metadata(row)

    assert payload["governance"]["role"] == "candidate"
    assert payload["presentation"]["visible"] is True
    assert is_eval_workflow_publicly_visible(row) is True
