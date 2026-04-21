"""Cleanup overrides for redundant eval workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_EVAL_WORKFLOW_CLEANUP_OVERRIDES: dict[str, dict[str, Any]] = {
    "7597723984687267840": {
        "presentation": {
            "visible": False,
            "usage_hint": "旧版扩图入口，已由统一 FLUX2-Klein 扩图替代。",
            "operation_label": "旧版扩图",
        },
        "deprecation": {
            "is_deprecated": True,
            "replacement_workflow_id": "7631174682116358144",
            "replacement_display_name": "扩图 · flux2_klein_9b_outpaint",
            "reason": "统一扩图评测入口，避免业务同时理解多模型旧版扩图。",
            "retirement_mode": "hide_public",
        },
    },
    "7598587935331450880": {
        "presentation": {
            "visible": False,
            "usage_hint": "旧版 ComfyUI 扩图入口，已由统一 FLUX2-Klein 扩图替代。",
            "operation_label": "旧版扩图",
        },
        "deprecation": {
            "is_deprecated": True,
            "replacement_workflow_id": "7631174682116358144",
            "replacement_display_name": "扩图 · flux2_klein_9b_outpaint",
            "reason": "统一扩图评测入口，减少旧版工作流重复暴露。",
            "retirement_mode": "hide_public",
        },
    },
}


def get_eval_workflow_cleanup_overrides(workflow_id: str | None) -> dict[str, Any]:
    payload = _EVAL_WORKFLOW_CLEANUP_OVERRIDES.get(str(workflow_id or "").strip())
    return deepcopy(payload) if isinstance(payload, dict) else {}
