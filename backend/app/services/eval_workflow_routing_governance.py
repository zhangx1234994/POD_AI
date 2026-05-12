"""Execution-surface governance labels for eval workflows."""

from __future__ import annotations

from typing import Any


TASK_TRACKED_WORKFLOW_IDS: set[str] = {
    "7598563505054154752",  # 两方四方连续图
    "7597701996124045312",  # 四步急速生图
    "7597702948247830528",  # 八步急速生图
}

VENDOR_API_WORKFLOW_IDS: set[str] = {
    "7601080398864449536",  # 花纹提取 · 商业模型有提示词
    "7598559869544693760",  # 花纹提取 · 商业模型免提示词
    "7601077530077954048",  # 图裂变 · 商业模型免提示词
    "7598848725942796288",  # 图裂变 · 商业模型有提示词
    "7604714915110060032",  # AI 图片编辑器
    "7602916576198656000",  # 多模型生图
}

IMAGE_OPS_WORKFLOW_IDS: set[str] = {
    "7597760543788630016",  # 8K 高清放大
    "7598589746561941504",  # DPI 增分
}

VL_WORKFLOW_IDS: set[str] = {
    "7597767702970630144",  # 图片打标签
    "7598080013539213312",  # 图片打标签
    "7600254097513512960",  # 图片打标签
    "7600254796297142272",  # 图片打标签
    "ability_fission_generated_image_evaluate_v1",  # 裂变生成图评估
}

BUSINESS_API_WORKFLOW_IDS: set[str] = {
    "business_fission_gpt_image2_vl_v1",
    "business_fission_comfyui_vl_control_v1",
}

INTERNAL_TOOL_WORKFLOW_IDS: set[str] = {
    "7597556718159003648",  # ComfyUI 回调
    "7601054603211177984",  # ComfyUI 队列监控
    "7612002440056930304",  # LoRA 查询
}


def _schema_has_field(schema: dict[str, Any] | None, field_name: str) -> bool:
    fields = schema.get("fields") if isinstance(schema, dict) else None
    if not isinstance(fields, list):
        return False
    return any(isinstance(field, dict) and field.get("name") == field_name for field in fields)


def _schema_output_mentions_callback(schema: dict[str, Any] | None) -> bool:
    fields = schema.get("fields") if isinstance(schema, dict) else None
    if not isinstance(fields, list):
        return False
    for field in fields:
        if not isinstance(field, dict) or field.get("name") != "output":
            continue
        text = f"{field.get('description') or ''} {field.get('type') or ''}".lower()
        if "task" in text or "回调" in text:
            return True
    return False


def _ability_type_for(workflow_id: str, name: str, category: str) -> tuple[str, str]:
    text = f"{name} {category}".lower()
    if workflow_id in VL_WORKFLOW_IDS or "打标签" in text or "biaoqian" in text:
        return "image_analysis", "图片理解/打标签"
    if workflow_id in IMAGE_OPS_WORKFLOW_IDS or "高清" in text or "dpi" in text:
        return "image_ops", "图像原子处理"
    if "扩图" in text or "图延伸" in text or "outpaint" in text:
        return "outpaint", "扩图"
    if "裂变" in text or "liebian" in text:
        return "fission", "图裂变"
    if "花纹提取" in text or "tiqu" in text:
        return "pattern_extract", "花纹提取"
    if "抠" in text or "cutout" in text:
        return "cutout", "抠图/抠像"
    if "融合" in text or "ronghe" in text:
        return "image_fusion", "多图融合"
    if workflow_id in INTERNAL_TOOL_WORKFLOW_IDS:
        return "internal_tool", "后台辅助工具"
    return "image_generation", "生图/图处理"


def resolve_eval_workflow_routing_governance(
    *,
    workflow_id: str | None,
    name: str | None,
    category: str | None,
    output_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return stable execution-surface governance metadata for eval workflow APIs."""

    wid = str(workflow_id or "").strip()
    display_name = str(name or "").strip()
    display_category = str(category or "").strip()
    ability_type, ability_type_label = _ability_type_for(wid, display_name, display_category)

    if wid in INTERNAL_TOOL_WORKFLOW_IDS:
        return {
            "abilityType": ability_type,
            "abilityTypeLabel": ability_type_label,
            "entryMode": "internal_tool",
            "entryLabel": "后台辅助工具",
            "executionSurface": "backend_internal",
            "executionLabel": "中台内部辅助能力",
            "trackingRequired": False,
            "expectedTracking": "operation_log",
            "currentTracking": "operation_log",
            "currentTrackingLabel": "后台工具日志即可",
            "governanceStatus": "internal_only",
            "governanceLabel": "不作为业务卡片治理",
            "notes": ["用于回调、队列或资源查询，不要求生成业务任务。"],
        }

    if wid in VL_WORKFLOW_IDS:
        return {
            "abilityType": ability_type,
            "abilityTypeLabel": ability_type_label,
            "entryMode": "coze_or_vendor_api",
            "entryLabel": "Coze 或第三方 API 入口",
            "executionSurface": "vendor_api_ops",
            "executionLabel": "第三方 API 执行面",
            "trackingRequired": True,
            "expectedTracking": "vendor_invocation_log",
            "currentTracking": "coze_output",
            "currentTrackingLabel": "当前主要依赖 Coze 输出",
            "governanceStatus": "needs_vendor_governance",
            "governanceLabel": "需要纳入第三方 API 管理",
            "notes": ["不按生图任务治理，但需要统一密钥、限流、成本和调用日志。"],
        }

    if wid in IMAGE_OPS_WORKFLOW_IDS:
        return {
            "abilityType": ability_type,
            "abilityTypeLabel": ability_type_label,
            "entryMode": "coze_toolbox",
            "entryLabel": "Coze 工具箱入口",
            "executionSurface": "image_ops",
            "executionLabel": "image-ops 原子能力服务",
            "trackingRequired": True,
            "expectedTracking": "podi_task",
            "currentTracking": "legacy_or_unknown",
            "currentTrackingLabel": "待补齐中台任务追踪",
            "governanceStatus": "needs_task_model",
            "governanceLabel": "需要统一任务化",
            "notes": ["高清放大、DPI 等能力应由 image-ops 执行，中台负责任务和回填。"],
        }

    if wid in BUSINESS_API_WORKFLOW_IDS:
        return {
            "abilityType": ability_type,
            "abilityTypeLabel": ability_type_label,
            "entryMode": "business_api",
            "entryLabel": "中台业务接口",
            "executionSurface": "backend_orchestration",
            "executionLabel": "中台业务编排",
            "trackingRequired": True,
            "expectedTracking": "business_run",
            "currentTracking": "business_run",
            "currentTrackingLabel": "已进入业务运行记录",
            "governanceStatus": "aligned",
            "governanceLabel": "业务接口治理达标",
            "notes": ["测评端直接调用中台业务层，底层可继续路由到 VL、ComfyUI 或第三方 API。"],
        }

    execution_surface = "vendor_api_ops" if wid in VENDOR_API_WORKFLOW_IDS else "comfyui"
    execution_label = "第三方 API 执行面" if execution_surface == "vendor_api_ops" else "ComfyUI 执行面"
    expected_tracking = "vendor_task" if execution_surface == "vendor_api_ops" else "podi_task"

    if wid in TASK_TRACKED_WORKFLOW_IDS:
        current_tracking = "podi_task"
        current_label = "已能沉淀中台任务 ID"
        governance_status = "aligned"
        governance_label = "追踪基本达标"
        notes = ["可作为后续工作流任务化的样板。"]
    else:
        callback_like = _schema_output_mentions_callback(output_schema) or _schema_has_field(output_schema, "ip")
        current_tracking = "legacy_callback" if callback_like else "coze_output"
        current_label = "当前主要靠回调或 Coze 输出追踪" if callback_like else "当前主要靠 Coze 输出追踪"
        governance_status = "needs_task_model"
        governance_label = "需要统一任务化"
        notes = ["功能可用不等于链路可治理，后续应补齐中台任务 ID 或统一追踪 ID。"]
        if execution_surface == "vendor_api_ops":
            governance_status = "needs_vendor_task_model"
            governance_label = "需要接入第三方 API 任务模型"
            notes = ["商业模型能力应收口到 vendor-api-ops，再由中台统一提交和轮询。"]

    return {
        "abilityType": ability_type,
        "abilityTypeLabel": ability_type_label,
        "entryMode": "coze_toolbox",
        "entryLabel": "Coze 工具箱入口",
        "executionSurface": execution_surface,
        "executionLabel": execution_label,
        "trackingRequired": True,
        "expectedTracking": expected_tracking,
        "currentTracking": current_tracking,
        "currentTrackingLabel": current_label,
        "governanceStatus": governance_status,
        "governanceLabel": governance_label,
        "notes": notes,
    }
