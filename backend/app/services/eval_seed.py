"""Seed default evaluation workflow versions.

This is intentionally lightweight and safe to call on request:
- It inserts missing rows (by workflow_id).
- It applies small, explicit normalizations for known workflows (schema fixes, category labels).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4
import json

from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session

from app.models.eval import EvalBatchSession, EvalRun, EvalWorkflowVersion
from app.constants.abilities import PATTERN_EXTRACT_LORA_PRESETS


LORA_OPTIONS = [
    entry.get("value")
    for entry in PATTERN_EXTRACT_LORA_PRESETS
    if isinstance(entry, dict) and entry.get("value")
]
if not LORA_OPTIONS:
    # Fallback (should not happen unless presets are removed).
    LORA_OPTIONS = ["杯子1124.safetensors"]

GPT_IMAGE2_SIZE_OPTIONS = [
    {"label": "自动匹配 auto", "value": "auto"},
    {"label": "1:1 方图 1024x1024", "value": "1024x1024"},
    {"label": "3:2 横图 1536x1024", "value": "1536x1024"},
    {"label": "2:3 竖图 1024x1536", "value": "1024x1536"},
    {"label": "1:1 方图 2048x2048（实验）", "value": "2048x2048"},
    {"label": "16:9 横图 2048x1152（实验）", "value": "2048x1152"},
    {"label": "16:9 横图 3840x2160（高成本）", "value": "3840x2160"},
    {"label": "9:16 竖图 2160x3840（高成本）", "value": "2160x3840"},
]

# Workflows that should not show up in the evaluation UI anymore.
# Note: seed inserts are append-only, so we also apply a small normalization pass
# to mark these as inactive if they already exist in DB.
DEPRECATED_EVAL_WORKFLOW_IDS: set[str] = {
    # 提取类
    "7597535455856295936",  # 提示词提取 · tishici_tiqu
    # 花纹提取类（旧版本，已替换为 7601080398864449536）
    "7598558185544220672",  # tiqu_duoMoxing_2 (old)
    # 图裂变（旧商业模型版本）
    "7598844004557389824",  # Liebian_shangye_20260124_1_1
    # 2026-05-13：这两个 v2 是对原生图裂变入口的替换升级，不应作为独立测评卡片展示。
    "business_fission_gpt_image2_vl_v2",
    "business_fission_comfyui_vl_colorlock_v2",
    # 下线/作废
    "7598560946579046400",  # tiqu_duoMoxing_2_2 (commercial + comfyui, deprecated)
    "7597659369861283840",  # 多模型生图
    "7597421439045599232",  # shengtu_shangye (旧 ID，已更换)
}

# Evaluation UI category policy: keep the sidebar fixed to these groups.
ALLOWED_EVAL_CATEGORIES: set[str] = {
    "花纹提取类",
    "图延伸类",
    "四方/两方连续图类",
    "图裂变",
    "图像理解",
    "通用类",
}

# 图裂变（Fan-out）工作流：需要展示“裂变数量”参数。
# 注意：中台原生业务接口必须保持“一次提交一张图”，不要在测评配置里自动补 count。
FISSION_WORKFLOW_IDS: set[str] = {
    "7598841920114130944",  # Liebian_comfyui_20260124_1
    "7598820684801769472",  # Liebian_comfyui_20260124
    "7622193261276299264",  # Liebian_comfyui_20260328_1
    "7622190276932534272",  # Liebian_comfyui_20260328
    "7601077530077954048",  # Liebian_shangye_20260130
    "7598848725942796288",  # Liebian_shangye_20260124_1_1_1
    "7629024620879806464",  # qwen2512_print_shape_text_enhance
    "7629026792103215104",  # flux2_9b_liebian_sifang
    "7631838631375667200",  # high quality softstyle fission
}

# 图裂变里的 bili 本质映射 ComfyUI denoise，不是“相似度”。
# 文字增强仍保留原相似度口径，避免误改不同业务语义。
REPAINT_STRENGTH_WORKFLOW_IDS: set[str] = FISSION_WORKFLOW_IDS - {
    "7629024620879806464",  # qwen2512_print_shape_text_enhance
}
REPAINT_STRENGTH_LABEL = "重绘幅度(%)"
REPAINT_STRENGTH_DESCRIPTION = "控制裂变重绘变化程度，0%=更保守，100%=变化更大；后端按约定比例换算为 denoise。"

# 同时属于"图裂变"和"四方/两方连续图类"的工作流。
DUAL_CATEGORY_FISSION_WORKFLOW_IDS: set[str] = {
    "7629026792103215104",  # flux2_9b_liebian_sifang
}

CATEGORY_FIX_WORKFLOW_IDS: dict[str, str] = {
    "7597701996124045312": "通用类",  # 4 steps
    "7597702948247830528": "通用类",  # 8 steps
    "7597659369861283840": "通用类",  # multi-model gen
}

OUTPAINTING_WORKFLOW_IDS: set[str] = {
    "7597723984687267840",
    "7598587935331450880",
}

# Workflows whose output should include prompt feedback.
PROMPT_OUTPUT_WORKFLOW_IDS: set[str] = {
    "7597530887256801280",  # tiqu_comfyui_20260123
    "7598545860393172992",  # tiqu_comfyui_20260123_2
    "7601080398864449536",  # tiqu_duoMoxing_2
    "7598559869544693760",  # tiqu_duoMoxing_20260130
    "7602916576198656000",  # shengtu_shangye
    "7597701996124045312",  # sibu_comfyui
    "7597702948247830528",  # zhongsu_comfyui
    "7598841920114130944",  # Liebian_comfyui_20260124_1
    "7598820684801769472",  # Liebian_comfyui_20260124
    "7622193261276299264",  # Liebian_comfyui_20260328_1
    "7622190276932534272",  # Liebian_comfyui_20260328
    "7601077530077954048",  # Liebian_shangye_20260130
    "7598848725942796288",  # Liebian_shangye_20260124_1_1_1
    "7629024620879806464",  # qwen2512_print_shape_text_enhance
    "7629026792103215104",  # flux2_9b_liebian_sifang
    "7631838631375667200",  # high quality softstyle fission
}

IP_OUTPUT_WORKFLOW_IDS: set[str] = {
    "7597530887256801280",  # tiqu_comfyui_20260123
    "7598545860393172992",  # tiqu_comfyui_20260123_2
    "7598563505054154752",  # lianxu
    "7598587935331450880",  # comfyuo_tukuozhan
    "7597701996124045312",  # sibu_comfyui
    "7597702948247830528",  # zhongsu_comfyui
    "7598841920114130944",  # Liebian_comfyui_20260124_1
    "7598820684801769472",  # Liebian_comfyui_20260124
    "7622193261276299264",  # Liebian_comfyui_20260328_1
    "7622190276932534272",  # Liebian_comfyui_20260328
    "7629023041988591616",  # toubu_kouxiang
    "7629023903431524352",  # beijing_koutu
    "7629024620879806464",  # qwen2512_print_shape_text_enhance
    "7629026792103215104",  # flux2_9b_liebian_sifang
    "7631838631375667200",  # high quality softstyle fission
}

FORCE_SYNC_EVAL_WORKFLOW_IDS: set[str] = {
    "business_fission_gpt_image2_vl_v1",
    "business_fission_comfyui_vl_control_v1",
    "ability_fission_generated_image_evaluate_v1",
    "7631838631375667200",
    "7625930748914040832",
}


def _normalize_eval_category(category: str | None) -> str:
    """Map legacy/internal categories into the business-facing groups."""
    c = (category or "").strip()
    if not c:
        return "通用类"
    if c in ALLOWED_EVAL_CATEGORIES:
        return c
    if c in {"pattern_extract", "pattern", "pattern-extract"}:
        return "花纹提取类"
    if c in {"image_extend", "image_extension", "image_extend_v1", "图扩展", "图延伸", "图延伸"}:
        return "图延伸类"
    if c in {"continuous", "lianxu", "seamless"}:
        return "四方/两方连续图类"
    if c in {"图裂变", "liebiam", "liebain", "variation", "image_variation"}:
        return "图裂变"
    if c in {"图像理解", "vision_analysis", "vision", "vl", "image_quality_evaluation", "quality_evaluation"}:
        return "图像理解"
    if c in {"general", "common"}:
        return "通用类"
    # Safe fallback to avoid leaking extra categories into the sidebar.
    return "通用类"


def _resolve_eval_category(workflow_id: str | None, category: str | None) -> str:
    workflow_id = str(workflow_id or "").strip()
    normalized = _normalize_eval_category(category)
    if workflow_id in CATEGORY_FIX_WORKFLOW_IDS:
        return CATEGORY_FIX_WORKFLOW_IDS[workflow_id]
    if workflow_id in OUTPAINTING_WORKFLOW_IDS:
        return "图延伸类"
    if workflow_id in FISSION_WORKFLOW_IDS and workflow_id not in DUAL_CATEGORY_FISSION_WORKFLOW_IDS:
        return "图裂变"
    return normalized


def _dedupe_eval_workflow_versions(session: Session) -> bool:
    rows = session.execute(select(EvalWorkflowVersion)).scalars().all()
    grouped: dict[tuple[str, str], list[EvalWorkflowVersion]] = {}
    for row in rows:
        workflow_id = str(row.workflow_id or "").strip()
        desired_category = _resolve_eval_category(workflow_id, row.category)
        grouped.setdefault((workflow_id, desired_category), []).append(row)

    dirty = False
    for (_, desired_category), bucket in grouped.items():
        bucket.sort(
            key=lambda row: (
                0 if row.status == "active" else 1,
                row.created_at.isoformat() if getattr(row, "created_at", None) else "",
                row.id,
            )
        )
        canonical = bucket[0]
        if canonical.category != desired_category:
            canonical.category = desired_category
            dirty = True
        for duplicate in bucket[1:]:
            session.execute(
                sa_update(EvalRun)
                .where(EvalRun.workflow_version_id == duplicate.id)
                .values(workflow_version_id=canonical.id)
            )
            session.execute(
                sa_update(EvalBatchSession)
                .where(EvalBatchSession.workflow_version_id == duplicate.id)
                .values(workflow_version_id=canonical.id)
            )
            session.delete(duplicate)
            dirty = True
    return dirty




DEFAULT_EVAL_WORKFLOW_VERSIONS: list[dict[str, Any]] = [
    # 通用类 / 提示词提取
    {
        "category": "general",
        "name": "提示词提取 · tishici_tiqu",
        "version": "v1",
        "workflow_id": "7597535455856295936",
        "status": "inactive",
        "notes": "输入：url, shuru(可空)。输出：output(提示词文本)。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True, "description": "图片地址"},
                {"name": "shuru", "label": "输入内容", "type": "text", "required": False, "description": "用户输入，可为空"},
            ]
        },
        "output_schema": {"fields": [{"name": "output", "type": "text", "description": "提示词内容"}]},
    },
    # 花纹提取类 / ComfyUI 花纹提取（输出为回调 task id）
    {
        "category": "花纹提取类",
        "name": "花纹提取 · tiqu_comfyui_20260123",
        "version": "v1",
        "workflow_id": "7597530887256801280",
        "status": "active",
        "notes": "花纹提取原生版（无需提示词，用于批量）。输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "width", "label": "生成宽度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "height", "label": "生成高度", "type": "text", "required": False, "defaultValue": ""},
                {
                    "name": "lora",
                    "label": "LoRA",
                    "type": "select",
                    "required": False,
                    "defaultValue": LORA_OPTIONS[0],
                    "options": [{"label": x, "value": x} for x in LORA_OPTIONS],
                },
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 花纹提取类 / ComfyUI 花纹提取（支持提示词拼接版本；输出为回调 task id）
    {
        "category": "花纹提取类",
        "name": "花纹提取 · tiqu_comfyui_20260123_2",
        "version": "v1",
        "workflow_id": "7598545860393172992",
        "status": "active",
        "notes": "输出 output 为回调 task id。此版本支持 is_raw_prompt 控制提示词拼接。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "height", "label": "高度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "width", "label": "宽度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
                {
                    "name": "is_raw_prompt",
                    "label": "提示词模式",
                    "type": "select",
                    "required": False,
                    "defaultValue": "0",
                    "options": [
                        {"label": "0 · 用户提示词 + 系统提示词", "value": "0"},
                        {"label": "1 · 仅使用用户提示词", "value": "1"},
                    ],
                    "description": "为空/0=拼接系统提示词；1=只使用用户提示词（系统提示词不生效）",
                },
                {
                    "name": "lora",
                    "label": "LoRA",
                    "type": "select",
                    "required": False,
                    "defaultValue": LORA_OPTIONS[0],
                    "options": [{"label": x, "value": x} for x in LORA_OPTIONS],
                },
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 花纹提取类 / 商业模型提取花纹（支持提示词；输出回调 task id）
    {
        "category": "花纹提取类",
        "name": "花纹提取 · tiqu_duoMoxing_2",
        "version": "v1",
        "workflow_id": "7601080398864449536",
        "status": "active",
        "notes": "商业模型提取花纹：moxing=1(Banana Pro)/2(Flux2)/3(Doubao 4.5)。输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {
                    "name": "moxing",
                    "label": "模型",
                    "type": "select",
                    "required": True,
                    "defaultValue": "1",
                    "options": [
                        {"label": "1 · Banana Pro", "value": "1"},
                        {"label": "2 · Flux2", "value": "2"},
                        {"label": "3 · Doubao 4.5", "value": "3"},
                    ],
                },
                {
                    "name": "aspect_ratio",
                    "label": "比例（仅 Banana/Flux2 生效）",
                    "type": "select",
                    "required": False,
                    "defaultValue": "",
                    "options": [
                        {"label": "auto", "value": "auto"},
                        {"label": "1:1", "value": "1:1"},
                        {"label": "4:3", "value": "4:3"},
                        {"label": "3:4", "value": "3:4"},
                        {"label": "16:9", "value": "16:9"},
                        {"label": "9:16", "value": "9:16"},
                    ],
                },
                {
                    "name": "resolution",
                    "label": "分辨率（仅 Banana/Flux2 生效）",
                    "type": "select",
                    "required": False,
                    "defaultValue": "",
                    "options": [
                        {"label": "1K", "value": "1K"},
                        {"label": "2K", "value": "2K"},
                        {"label": "4K", "value": "4K"},
                    ],
                },
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 花纹提取类 / 商业模型提取花纹（无需提示词；输出回调 task id）
    {
        "category": "花纹提取类",
        "name": "花纹提取 · tiqu_duoMoxing_20260130",
        "version": "v1",
        "workflow_id": "7598559869544693760",
        "status": "active",
        "notes": "商业模型提取花纹（批量版）：不输入提示词，输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {
                    "name": "moxing",
                    "label": "模型",
                    "type": "select",
                    "required": True,
                    "defaultValue": "1",
                    "options": [
                        {"label": "1 · Banana Pro", "value": "1"},
                        {"label": "2 · Flux2", "value": "2"},
                        {"label": "3 · Doubao 4.5", "value": "3"},
                    ],
                },
                {
                    "name": "aspect_ratio",
                    "label": "比例（仅 Banana/Flux2 生效）",
                    "type": "select",
                    "required": False,
                    "defaultValue": "",
                    "options": [
                        {"label": "auto", "value": "auto"},
                        {"label": "1:1", "value": "1:1"},
                        {"label": "4:3", "value": "4:3"},
                        {"label": "3:4", "value": "3:4"},
                        {"label": "16:9", "value": "16:9"},
                        {"label": "9:16", "value": "9:16"},
                    ],
                },
                {
                    "name": "resolution",
                    "label": "分辨率（仅 Banana/Flux2 生效）",
                    "type": "select",
                    "required": False,
                    "defaultValue": "",
                    "options": [
                        {"label": "1K", "value": "1K"},
                        {"label": "2K", "value": "2K"},
                        {"label": "4K", "value": "4K"},
                    ],
                },
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 花纹提取类 / 商业模型 + ComfyUI 串联（为兼顾输出尺寸；输出回调 task id）
    {
        "category": "花纹提取类",
        "name": "花纹提取 · tiqu_duoMoxing_2_2",
        "version": "v1",
        "workflow_id": "7598560946579046400",
        "status": "inactive",
        "notes": "商业模型+ComfyUI 串联版本：为兼顾输出尺寸，速度更慢；输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {
                    "name": "moxing",
                    "label": "模型",
                    "type": "select",
                    "required": True,
                    "defaultValue": "1",
                    "options": [
                        {"label": "1 · Banana Pro", "value": "1"},
                        {"label": "2 · Flux2", "value": "2"},
                        {"label": "3 · Doubao 4.5", "value": "3"},
                    ],
                },
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "height", "label": "高度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "width", "label": "宽度", "type": "text", "required": False, "defaultValue": ""},
                {
                    "name": "aspect_ratio",
                    "label": "比例（仅 Banana/Flux2 生效）",
                    "type": "select",
                    "required": False,
                    "defaultValue": "",
                    "options": [
                        {"label": "auto", "value": "auto"},
                        {"label": "1:1", "value": "1:1"},
                        {"label": "4:3", "value": "4:3"},
                        {"label": "3:4", "value": "3:4"},
                        {"label": "16:9", "value": "16:9"},
                        {"label": "9:16", "value": "9:16"},
                    ],
                },
                {
                    "name": "resolution",
                    "label": "分辨率（仅 Banana/Flux2 生效）",
                    "type": "select",
                    "required": False,
                    "defaultValue": "",
                    "options": [
                        {"label": "1K", "value": "1K"},
                        {"label": "2K", "value": "2K"},
                        {"label": "4K", "value": "4K"},
                    ],
                },
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 连续图 / 四方连续、两方连续（输出为回调 task id）
    {
        "category": "四方/两方连续图类",
        "name": "连续图 · lianxu",
        "version": "v1",
        "workflow_id": "7598563505054154752",
        "status": "active",
        "notes": "四方连续/两方连续。patternType=seamless(四方)/twoway(两方)。输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                # Coze workflow requires height/width; provide safe defaults and mark required so UI blocks early.
                {"name": "height", "label": "高度", "type": "text", "required": False, "defaultValue": "", "description": "可选。不填默认原图高度。"},
                {"name": "width", "label": "宽度", "type": "text", "required": False, "defaultValue": "", "description": "可选。不填默认原图宽度。"},
                {
                    "name": "patternType",
                    "label": "连续类型",
                    "type": "select",
                    "required": True,
                    "defaultValue": "seamless",
                    "options": [
                        {"label": "seamless · 四方连续", "value": "seamless"},
                        {"label": "twoway · 两方连续", "value": "twoway"},
                    ],
                },
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 图延伸类 / 扩图（多模型，输出回调 task id）
    {
        "category": "图延伸类",
        "name": "扩图多模型版本",
        "version": "v1",
        "workflow_id": "7597723984687267840",
        "status": "active",
        "notes": "默认 moxing=1(Banana Pro)。输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "expand_left", "label": "左扩", "type": "text", "required": False, "defaultValue": "0", "description": "像素数值（纯数字，不要带 px）"},
                {"name": "expand_right", "label": "右扩", "type": "text", "required": False, "defaultValue": "0", "description": "像素数值（纯数字，不要带 px）"},
                {"name": "expand_top", "label": "上扩", "type": "text", "required": False, "defaultValue": "0", "description": "像素数值（纯数字，不要带 px）"},
                {"name": "expand_bottom", "label": "下扩", "type": "text", "required": False, "defaultValue": "0", "description": "像素数值（纯数字，不要带 px）"},
                {
                    "name": "moxing",
                    "label": "模型",
                    "type": "select",
                    "required": False,
                    "defaultValue": "1",
                    "options": [
                        {"label": "1 · Banana Pro", "value": "1"},
                        {"label": "2 · Flux2", "value": "2"},
                        {"label": "3 · Doubao 4.5", "value": "3"},
                    ],
                },
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 图扩展 / ComfyUI 扩图（输出为回调 task id）
    {
        "category": "图延伸类",
        "name": "ComfyUI 扩图 · comfyuo_tukuozhan",
        "version": "v1",
        "workflow_id": "7598587935331450880",
        "status": "active",
        "notes": "输入 url + 四向扩图像素；输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "expand_left", "label": "左扩", "type": "text", "required": False, "defaultValue": "0", "description": "像素数值（纯数字，不要带 px）"},
                {"name": "expand_right", "label": "右扩", "type": "text", "required": False, "defaultValue": "0", "description": "像素数值（纯数字，不要带 px）"},
                {"name": "expand_top", "label": "上扩", "type": "text", "required": False, "defaultValue": "0", "description": "像素数值（纯数字，不要带 px）"},
                {"name": "expand_bottom", "label": "下扩", "type": "text", "required": False, "defaultValue": "0", "description": "像素数值（纯数字，不要带 px）"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 通用类 / 多模型生图（商业模型生图 · shengtu_shangye）
    {
        "category": "通用类",
        "name": "多模型生图 · shengtu_shangye",
        "version": "v1",
        "workflow_id": "7602916576198656000",
        "status": "active",
        "notes": "商业模型生图：moxing=1(Banana Pro)/2(Flux2 Pro)/3(Seedream 4.5)/4(Banana 2)。参考图字段使用 cankaotu（会兼容映射 image_urls）。输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "主图 URL", "type": "text", "required": True, "description": "主图（图1）。"},
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
                {
                    "name": "moxing",
                    "label": "模型",
                    "type": "select",
                    "required": False,
                    "defaultValue": "1",
                    "description": "1=Banana Pro，2=Flux2 Pro，3=Seedream 4.5，4=Banana 2。",
                    "options": [
                        {"label": "1 · Banana Pro", "value": "1"},
                        {"label": "2 · Flux2 Pro", "value": "2"},
                        {"label": "3 · Seedream 4.5", "value": "3"},
                        {"label": "4 · Banana 2", "value": "4"},
                    ],
                },
                {
                    "name": "cankaotu",
                    "label": "参考图 URLs（可选）",
                    "type": "textarea",
                    "required": False,
                    "defaultValue": "",
                    "supportedModels": ["1", "2", "4"],
                    "description": "每行一个 URL（或英文逗号分隔）。仅模型 1/2/4 生效；会按图2/图3... 顺序传参。",
                },
                {
                    "name": "aspect_ratio",
                    "label": "画幅比例",
                    "type": "select",
                    "required": False,
                    "defaultValue": "",
                    "description": "模型 1/2/4 生效；模型 3（Seedream 4.5）忽略该参数。",
                    "options": [
                        {"label": "原图比例（默认）", "value": ""},
                        {"label": "auto", "value": "auto"},
                        {"label": "1:1", "value": "1:1"},
                        {"label": "2:3", "value": "2:3"},
                        {"label": "3:2", "value": "3:2"},
                        {"label": "3:4", "value": "3:4"},
                        {"label": "4:3", "value": "4:3"},
                        {"label": "4:5", "value": "4:5"},
                        {"label": "5:4", "value": "5:4"},
                        {"label": "9:16", "value": "9:16"},
                        {"label": "16:9", "value": "16:9"},
                        {"label": "21:9", "value": "21:9"},
                    ],
                    "modelOptions": {
                        "1": ["", "auto", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
                        "2": ["", "auto", "1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"],
                        "3": [""],
                        "4": ["", "auto", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
                    },
                },
                {
                    "name": "resolution",
                    "label": "分辨率",
                    "type": "select",
                    "required": False,
                    "defaultValue": "",
                    "description": "模型 1/2/4 生效；模型 3（Seedream 4.5）忽略该参数。",
                    "options": [
                        {"label": "跟随原图（默认）", "value": ""},
                        {"label": "1K", "value": "1K"},
                        {"label": "2K", "value": "2K"},
                        {"label": "4K", "value": "4K"},
                    ],
                    "modelOptions": {
                        "1": ["", "1K", "2K", "4K"],
                        "2": ["", "1K", "2K"],
                        "3": [""],
                        "4": ["", "1K", "2K", "4K"],
                    },
                },
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    {
        "category": "通用类",
        "name": "LoRA 查询 · lora_catalog_query",
        "version": "v1",
        "workflow_id": "7612002440056930304",
        "status": "active",
        "notes": "查询可用 LoRA 列表。无入参；输出 items（详情）与 lora_names（可直接作为 LoRA 入参）。",
        "parameters_schema": {"fields": []},
        "output_schema": {
            "fields": [
                {
                    "name": "items",
                    "type": "json",
                    "description": "LoRA 详情列表（包含 fileName/displayName/status/baseModels/tags/installed）。",
                },
                {
                    "name": "lora_names",
                    "type": "array",
                    "description": "LoRA 文件名列表（作为 LoRA 入参请优先使用该字段）。",
                },
            ]
        },
    },
    # 通用类 / 多模型生图（旧版，下线）
    {
        "category": "general",
        "name": "多模型生图",
        "version": "v1",
        "workflow_id": "7597659369861283840",
        "status": "inactive",
        "notes": "moxing：1=Banana Pro，2=Flux2，3=Doubao 4.5。Flux2 更偏比例参数；其余更偏宽高参数。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": True},
                {
                    "name": "moxing",
                    "label": "模型",
                    "type": "select",
                    "required": False,
                    "defaultValue": "1",
                    "options": [
                        {"label": "1 · Banana Pro", "value": "1"},
                        {"label": "2 · Flux2", "value": "2"},
                        {"label": "3 · Doubao 4.5", "value": "3"},
                    ],
                },
                {"name": "width", "label": "宽度", "type": "text", "required": False, "defaultValue": "", "description": "像素数值（纯数字，不要带 px）"},
                {"name": "height", "label": "高度", "type": "text", "required": False, "defaultValue": "", "description": "像素数值（纯数字，不要带 px）"},
                {
                    "name": "aspect_ratio",
                    "label": "比例（仅 Banana/Flux2 生效）",
                    "type": "select",
                    "required": False,
                    "defaultValue": "auto",
                    "options": [
                        {"label": "auto", "value": "auto"},
                        {"label": "1:1", "value": "1:1"},
                        {"label": "4:3", "value": "4:3"},
                        {"label": "3:4", "value": "3:4"},
                        {"label": "16:9", "value": "16:9"},
                        {"label": "9:16", "value": "9:16"},
                    ],
                },
                {
                    "name": "resolution",
                    "label": "分辨率（仅 Banana/Flux2 生效）",
                    "type": "select",
                    "required": False,
                    "defaultValue": "1K",
                    "options": [
                        {"label": "1K", "value": "1K"},
                        {"label": "2K", "value": "2K"},
                        {"label": "4K", "value": "4K"},
                    ],
                },
            ]
        },
        "output_schema": {"fields": [{"name": "output", "type": "text", "description": "图片 URL（或 task id）"}]},
    },
    # 图略变/通用类 / 四步快速生图（输出为回调 task id）
    {
        "category": "general",
        "name": "四步快速生图 · sibu_comfyui",
        "version": "v1",
        "workflow_id": "7597701996124045312",
        "status": "active",
        "notes": "输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "width", "label": "生成宽度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "height", "label": "生成高度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": True},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 图略变/通用类 / 八步中速生图（输出为回调 task id）
    {
        "category": "general",
        "name": "八步中速生图 · zhongsu_comfyui",
        "version": "v1",
        "workflow_id": "7597702948247830528",
        "status": "active",
        "notes": "输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "width", "label": "生成宽度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "height", "label": "生成高度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": True},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    # 通用类 / 8K 高清放大
    {
        "category": "通用类",
        "name": "8K 高清放大",
        "version": "v1",
        "workflow_id": "7597760543788630016",
        "status": "active",
        "notes": "输入 bianchang=最长边目标尺寸（<=8K）。输出为图片地址。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "bianchang", "label": "最长边", "type": "text", "required": False, "defaultValue": "4096", "description": "像素数值（纯数字，不要带 px）"},
            ]
        },
        "output_schema": {"fields": [{"name": "output", "type": "text", "description": "图片 URL"}]},
    },
    # 通用类 / DPI 增分（仅修改 DPI 元数据，不改变像素）
    {
        "category": "通用类",
        "name": "DPI 增分",
        "version": "v1",
        "workflow_id": "7598589746561941504",
        "status": "active",
        "notes": "输入 url + dpi（默认 300）。输出 output 为图片 URL。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "dpi", "label": "DPI", "type": "text", "required": False, "defaultValue": "300"},
            ]
        },
        "output_schema": {"fields": [{"name": "output", "type": "text", "description": "图片 URL"}]},
    },
    # 通用类 / 图片打标签（小参数版本）
    {
        "category": "通用类",
        "name": "图片打标签 · Biaoqian_tiqu",
        "version": "v1",
        "workflow_id": "7597767702970630144",
        "status": "active",
        "notes": "小参数版本图片打标签。输出 output 为 JSON（图片标签）。",
        "parameters_schema": {"fields": [{"name": "url", "label": "图片 URL", "type": "text", "required": True}]},
        "output_schema": {"fields": [{"name": "output", "type": "json", "description": "JSON 标签"}]},
    },
    # 通用类 / 图片打标签（大参数版本）
    {
        "category": "通用类",
        "name": "图片打标签 · Biaoqian_tiqu_1",
        "version": "v1",
        "workflow_id": "7598080013539213312",
        "status": "active",
        "notes": "大参数版本图片打标签。输出 output 为 JSON（图片标签）。",
        "parameters_schema": {"fields": [{"name": "url", "label": "图片 URL", "type": "text", "required": True}]},
        "output_schema": {"fields": [{"name": "output", "type": "json", "description": "JSON 标签"}]},
    },
    # 通用类 / 图片打标签（lits 版本）
    {
        "category": "通用类",
        "name": "图片打标签 · Biaoqian_tiqu_3",
        "version": "v1",
        "workflow_id": "7600254097513512960",
        "status": "active",
        "notes": "lits 版本图片打标签。输出 output 为 JSON（图片标签）。",
        "parameters_schema": {"fields": [{"name": "url", "label": "图片 URL", "type": "text", "required": True}]},
        "output_schema": {"fields": [{"name": "output", "type": "json", "description": "JSON 标签"}]},
    },
    # 通用类 / 图片打标签（lits 版本 · 主色为色号）
    {
        "category": "通用类",
        "name": "图片打标签 · Biaoqian_tiqu_3_1",
        "version": "v1",
        "workflow_id": "7600254796297142272",
        "status": "active",
        "notes": "lits 版本图片打标签（主色为色号）。输出 output 为 JSON（图片标签）。",
        "parameters_schema": {"fields": [{"name": "url", "label": "图片 URL", "type": "text", "required": True}]},
        "output_schema": {"fields": [{"name": "output", "type": "json", "description": "JSON 标签"}]},
    },
    # 图像理解 / 图片打标签（结构化打标版）
    {
        "category": "图像理解",
        "name": "图片打标签 · 结构化打标版",
        "version": "v1",
        "workflow_id": "7625930748914040832",
        "status": "active",
        "notes": "图片结构化打标工作流。输入图片 URL，输出 output 为 JSON 标签，可用于裂变前后质量判断和素材归档。",
        "parameters_schema": {"fields": [{"name": "url", "label": "图片 URL", "type": "image", "required": True}]},
        "output_schema": {"fields": [{"name": "output", "type": "json", "description": "JSON 标签"}]},
        "metadata": {
            "presentation": {
                "operation_label": "图片打标签",
                "variant_label": "结构化打标版",
                "result_mode": "structured_json",
                "usage_hint": "适合检查图片主题、风格、颜色、图案和可用标签，辅助裂变结果筛选。",
                "badges": ["打标"],
            },
            "usage": {
                "single_run_enabled": True,
                "batch_enabled": False,
                "docs_enabled": True,
                "recommended_entry": "single",
                "supports_annotation": True,
            },
            "governance": {
                "role": "candidate",
                "role_label": "待验证打标入口",
                "role_reason": "新补齐到测评端，先作为可测版本观察。",
                "rank": 30,
            },
        },
    },
    # 通用类 / ComfyUI 队列监控
    {
        "category": "通用类",
        "name": "ComfyUI 队列监控 · comfyui_duilie",
        "version": "v1",
        "workflow_id": "7601054603211177984",
        "status": "active",
        "notes": "返回各 ComfyUI 执行节点的队列状态与时间戳。",
        "parameters_schema": {"fields": []},
        "output_schema": {
            "fields": [
                {"name": "servers", "type": "json", "description": "执行节点队列列表"},
                {"name": "timestamp", "type": "text", "description": "返回时间"},
                {"name": "totalRunning", "type": "number", "description": "处理中数量"},
                {"name": "totalPending", "type": "number", "description": "排队中数量"},
                {"name": "totalCount", "type": "number", "description": "总数量"},
            ]
        },
    },
    # 图裂变 / 图裂变（ComfyUI，无提示词，输出回调 task id）
    {
        "category": "图裂变",
        "name": "图裂变 · Liebian_comfyui_20260124_1",
        "version": "v1",
        "workflow_id": "7598841920114130944",
        "status": "active",
        "notes": "图裂变（ComfyUI 无提示词）。输出 output 为回调 task id。裂变数量通过 count 控制（业务侧循环，不在工作流中循环）。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "height", "label": "高度", "type": "text", "required": False, "defaultValue": "", "description": "可选。不填默认原图高度。"},
                {"name": "width", "label": "宽度", "type": "text", "required": False, "defaultValue": "", "description": "可选。不填默认原图宽度。"},
                {
                    "name": "bili",
                    "label": REPAINT_STRENGTH_LABEL,
                    "type": "text",
                    "required": True,
                    "defaultValue": "50%",
                    "description": REPAINT_STRENGTH_DESCRIPTION,
                },
                {"name": "count", "label": "裂变数量", "type": "text", "required": False, "defaultValue": "4", "description": "一次评测会触发 count 个子任务并聚合结果"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    # 图裂变 / 图裂变（ComfyUI，有提示词，输出回调 task id）
    {
        "category": "图裂变",
        "name": "图裂变 · Liebian_comfyui_20260124",
        "version": "v1",
        "workflow_id": "7598820684801769472",
        "status": "active",
        "notes": "图裂变（ComfyUI 有提示词）。输出 output 为回调 task id。裂变数量通过 count 控制。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "height", "label": "高度", "type": "text", "required": False, "defaultValue": "", "description": "可选。不填默认原图高度。"},
                {"name": "width", "label": "宽度", "type": "text", "required": False, "defaultValue": "", "description": "可选。不填默认原图宽度。"},
                {
                    "name": "bili",
                    "label": REPAINT_STRENGTH_LABEL,
                    "type": "text",
                    "required": True,
                    "defaultValue": "50%",
                    "description": REPAINT_STRENGTH_DESCRIPTION,
                },
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
                {"name": "count", "label": "裂变数量", "type": "text", "required": False, "defaultValue": "4", "description": "一次评测会触发 count 个子任务并聚合结果"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    # 图裂变 / 图裂变（ComfyUI，无提示词，输出回调 task id）- 2026-03-28 版本
    {
        "category": "图裂变",
        "name": "图裂变 · Liebian_comfyui_20260328_1",
        "version": "v1",
        "workflow_id": "7622193261276299264",
        "status": "active",
        "notes": "图裂变（ComfyUI 无提示词，2026-03-28 版本）。输出 output 为回调 task id。裂变数量通过 count 控制（业务侧循环，不在工作流中循环）。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "height", "label": "高度", "type": "text", "required": False, "defaultValue": "", "description": "可选。不填默认原图高度。"},
                {"name": "width", "label": "宽度", "type": "text", "required": False, "defaultValue": "", "description": "可选。不填默认原图宽度。"},
                {
                    "name": "bili",
                    "label": REPAINT_STRENGTH_LABEL,
                    "type": "text",
                    "required": True,
                    "defaultValue": "50%",
                    "description": REPAINT_STRENGTH_DESCRIPTION,
                },
                {"name": "count", "label": "裂变数量", "type": "text", "required": False, "defaultValue": "4", "description": "一次评测会触发 count 个子任务并聚合结果"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    # 图裂变 / 图裂变（ComfyUI，有提示词，输出回调 task id）- 2026-03-28 版本
    {
        "category": "图裂变",
        "name": "图裂变 · Liebian_comfyui_20260328",
        "version": "v1",
        "workflow_id": "7622190276932534272",
        "status": "active",
        "notes": "图裂变（ComfyUI 有提示词，2026-03-28 版本）。输出 output 为回调 task id。裂变数量通过 count 控制。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "height", "label": "高度", "type": "text", "required": False, "defaultValue": "", "description": "可选。不填默认原图高度。"},
                {"name": "width", "label": "宽度", "type": "text", "required": False, "defaultValue": "", "description": "可选。不填默认原图宽度。"},
                {
                    "name": "bili",
                    "label": REPAINT_STRENGTH_LABEL,
                    "type": "text",
                    "required": True,
                    "defaultValue": "50%",
                    "description": REPAINT_STRENGTH_DESCRIPTION,
                },
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
                {"name": "count", "label": "裂变数量", "type": "text", "required": False, "defaultValue": "4", "description": "一次评测会触发 count 个子任务并聚合结果"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    # 图裂变 / 图裂变（商业模型，无提示词，输出回调 task id）
    {
        "category": "图裂变",
        "name": "图裂变 · Liebian_shangye_20260130",
        "version": "v1",
        "workflow_id": "7601077530077954048",
        "status": "active",
        "notes": "图裂变（商业模型无提示词）。输出 output 为回调 task id。裂变数量通过 count 控制；当前比例参数后续可能需要额外处理。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {
                    "name": "aspect_ratio",
                    "label": "画幅比例",
                    "type": "select",
                    "required": True,
                    "defaultValue": "1:1",
                    "options": [
                        {"label": "1:1", "value": "1:1"},
                        {"label": "1:2", "value": "1:2"},
                    ],
                },
                {
                    "name": "resolution",
                    "label": "分辨率",
                    "type": "select",
                    "required": True,
                    "defaultValue": "1K",
                    "options": [
                        {"label": "1K", "value": "1K"},
                        {"label": "2K", "value": "2K"},
                        {"label": "4K", "value": "4K"},
                    ],
                },
                {
                    "name": "bili",
                    "label": REPAINT_STRENGTH_LABEL,
                    "type": "text",
                    "required": True,
                    "defaultValue": "50%",
                    "description": REPAINT_STRENGTH_DESCRIPTION,
                },
                {
                    "name": "moxing",
                    "label": "模型",
                    "type": "select",
                    "required": False,
                    "defaultValue": "1",
                    "options": [
                        {"label": "1 · Banana Pro", "value": "1"},
                        {"label": "2 · Flux2 Pro", "value": "2"},
                        {"label": "3 · Seedream 4.5", "value": "3"},
                    ],
                },
                {"name": "count", "label": "裂变数量", "type": "text", "required": False, "defaultValue": "4", "description": "一次评测会触发 count 个子任务并聚合结果"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    # 图裂变 / 图裂变（商业模型，有提示词，输出回调 task id）
    {
        "category": "图裂变",
        "name": "图裂变 · Liebian_shangye_20260124_1_1_1",
        "version": "v1",
        "workflow_id": "7598848725942796288",
        "status": "active",
        "notes": "图裂变（商业模型有提示词）。输出 output 为回调 task id。裂变数量通过 count 控制；当前比例参数后续可能需要额外处理。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {
                    "name": "aspect_ratio",
                    "label": "画幅比例",
                    "type": "select",
                    "required": True,
                    "defaultValue": "1:1",
                    "options": [
                        {"label": "1:1", "value": "1:1"},
                        {"label": "1:2", "value": "1:2"},
                    ],
                },
                {
                    "name": "resolution",
                    "label": "分辨率",
                    "type": "select",
                    "required": True,
                    "defaultValue": "1K",
                    "options": [
                        {"label": "1K", "value": "1K"},
                        {"label": "2K", "value": "2K"},
                        {"label": "4K", "value": "4K"},
                    ],
                },
                {
                    "name": "bili",
                    "label": REPAINT_STRENGTH_LABEL,
                    "type": "text",
                    "required": True,
                    "defaultValue": "50%",
                    "description": REPAINT_STRENGTH_DESCRIPTION,
                },
                {
                    "name": "moxing",
                    "label": "模型",
                    "type": "select",
                    "required": False,
                    "defaultValue": "1",
                    "options": [
                        {"label": "1 · Banana Pro", "value": "1"},
                        {"label": "2 · Flux2 Pro", "value": "2"},
                        {"label": "3 · Seedream 4.5", "value": "3"},
                    ],
                },
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
                {"name": "count", "label": "裂变数量", "type": "text", "required": False, "defaultValue": "4", "description": "一次评测会触发 count 个子任务并聚合结果"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    # AI 图片编辑器（KIE nano-banana-pro 图生图编辑）
    {
        "category": "通用类",
        "name": "AI 图片编辑器 · nano_banana_pro_edit",
        "version": "v1",
        "workflow_id": "7604714915110060032",
        "status": "active",
        "notes": "AI 图片编辑器（业务接入版）：输入主图+标注+参考图，输出回调 task id。主图=图1，参考图从图2开始编号；提示词支持 @标注 与 #参考图（#1 对应 图2）。若不传画幅/分辨率则自动跟随原图尺寸。",
        "parameters_schema": {
            "fields": [
                {
                    "name": "url",
                    "label": "主图 URL",
                    "type": "text",
                    "required": True,
                    "description": "必填。主图=图1；用于标注与编辑的原始图片。",
                },
                {
                    "name": "image_urls",
                    "label": "参考图 URLs（逗号分隔）",
                    "type": "text",
                    "required": False,
                    "defaultValue": "",
                    "description": "可选。多张参考图用英文逗号或换行分隔，会按 #1/#2... 排序（模型侧=图2/图3…）。",
                },
                {
                    "name": "prompt",
                    "label": "提示词（含 @ 标注 / # 参考图）",
                    "type": "textarea",
                    "required": True,
                    "description": "必填。示例：@标注1 把文字改成“新年快乐”；@标注2 纹理参考 #1（模型侧=图2）。",
                },
                {
                    "name": "output_format",
                    "label": "输出格式",
                    "type": "select",
                    "required": False,
                    "defaultValue": "png",
                    "options": [
                        {"label": "PNG", "value": "png"},
                        {"label": "JPG", "value": "jpg"},
                        {"label": "WEBP", "value": "webp"},
                    ],
                },
                {
                    "name": "aspect_ratio",
                    "label": "画幅比例",
                    "type": "select",
                    "required": False,
                    "defaultValue": "",
                    "options": [
                        {"label": "跟随原图（默认）", "value": ""},
                        {"label": "auto", "value": "auto"},
                        {"label": "1:1", "value": "1:1"},
                        {"label": "4:3", "value": "4:3"},
                        {"label": "3:4", "value": "3:4"},
                        {"label": "16:9", "value": "16:9"},
                        {"label": "9:16", "value": "9:16"},
                    ],
                    "description": "可选。为空=跟随原图；手动选择将强制画幅比例。",
                },
                {
                    "name": "resolution",
                    "label": "分辨率",
                    "type": "select",
                    "required": False,
                    "defaultValue": "",
                    "options": [
                        {"label": "跟随原图（默认）", "value": ""},
                        {"label": "1K", "value": "1K"},
                        {"label": "2K", "value": "2K"},
                        {"label": "4K", "value": "4K"},
                    ],
                    "description": "可选。为空=跟随原图；手动选择将强制分辨率。",
                },
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    # 通用类 / 多图融合（ComfyUI，多图输入）
    {
        "category": "通用类",
        "name": "多图融合 · duotu_ronghe",
        "version": "v1",
        "workflow_id": "7615600173695107072",
        "status": "active",
        "notes": "ComfyUI 多图融合：输入主图 + 辅图1/辅图2（可选），支持输出宽高、正/反向提示词和随机种子；无外部 LoRA 入参。辅图未传时会在提交时移除对应引用；宽高不传时沿用 workflow 默认 1024x1024。",
        "parameters_schema": {
            "fields": [
                {
                    "name": "url",
                    "label": "主图 URL",
                    "type": "text",
                    "required": True,
                    "description": "必填。主图=图1。",
                },
                {
                    "name": "image_url_2",
                    "label": "辅图 1 URL",
                    "type": "text",
                    "required": False,
                    "defaultValue": "",
                    "description": "可选。对应节点 106（image2）；不传则提交时移除。",
                },
                {
                    "name": "image_url_3",
                    "label": "辅图 2 URL",
                    "type": "text",
                    "required": False,
                    "defaultValue": "",
                    "description": "可选。对应节点 108（image3）；不传则提交时移除。",
                },
                {
                    "name": "width",
                    "label": "输出宽度",
                    "type": "text",
                    "required": False,
                    "defaultValue": "",
                    "description": "可选。评测页留空时会自动读取主图宽度；若绕过前端直调则沿用 workflow 默认 1024。",
                },
                {
                    "name": "height",
                    "label": "输出高度",
                    "type": "text",
                    "required": False,
                    "defaultValue": "",
                    "description": "可选。评测页留空时会自动读取主图高度；若绕过前端直调则沿用 workflow 默认 1024。",
                },
                {
                    "name": "negative_prompt",
                    "label": "反向提示词",
                    "type": "textarea",
                    "required": False,
                    "defaultValue": "",
                    "description": "可选。对应节点 110.prompt。",
                },
                {
                    "name": "prompt",
                    "label": "提示词",
                    "type": "textarea",
                    "required": False,
                    "defaultValue": "",
                    "description": "可选。对应节点 111.prompt。",
                },
                {
                    "name": "seed",
                    "label": "随机种子",
                    "type": "text",
                    "required": False,
                    "defaultValue": "",
                    "description": "可选。对应节点 151.seed；不填由后端自动生成。",
                },
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    # 通用类 / 背景抠图
    {
        "category": "通用类",
        "name": "背景抠图 · beijing_koutu",
        "version": "v1",
        "workflow_id": "7629023903431524352",
        "status": "active",
        "notes": "背景抠图（ComfyUI）。输入 url，输出透明背景图片。输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 通用类 / 头部抠像
    {
        "category": "通用类",
        "name": "头部抠像 · toubu_kouxiang",
        "version": "v1",
        "workflow_id": "7629023041988591616",
        "status": "active",
        "notes": "头部抠像（ComfyUI）。输入 url，输出头部/头发抠像。输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 图裂变 / 文字增强
    {
        "category": "图裂变",
        "name": "文字增强 · qwen2512_print_shape_text_enhance",
        "version": "v1",
        "workflow_id": "7629024620879806464",
        "status": "active",
        "notes": "文字增强（ComfyUI）。输入 url + prompt + bili（相似度），输出增强后的图片。输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
                {
                    "name": "bili",
                    "label": "相似度(%)",
                    "type": "text",
                    "required": True,
                    "defaultValue": "50%",
                    "description": "与原图保持相似的百分比（越高越接近原图）。",
                },
                {"name": "count", "label": "裂变数量", "type": "text", "required": False, "defaultValue": "4", "description": "一次评测会触发 count 个子任务并聚合结果"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 四方/两方连续图类 / 四方连续裂变（双栏目展示）
    {
        "category": "四方/两方连续图类",
        "name": "四方连续裂变 · flux2_9b_liebian_sifang",
        "version": "v1",
        "workflow_id": "7629026792103215104",
        "status": "active",
        "notes": "四方连续图裂变（ComfyUI）。输入 url + prompt，输出四方连续裂变图片。输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
                {"name": "count", "label": "裂变数量", "type": "text", "required": False, "defaultValue": "4", "description": "一次评测会触发 count 个子任务并聚合结果"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 图裂变 / 四方连续裂变（同时属于 四方/两方连续图类）
    {
        "category": "图裂变",
        "name": "四方连续裂变 · flux2_9b_liebian_sifang",
        "version": "v1",
        "workflow_id": "7629026792103215104",
        "status": "active",
        "notes": "四方连续图裂变（ComfyUI）。输入 url + prompt，输出四方连续裂变图片。输出 output 为回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
                {"name": "count", "label": "裂变数量", "type": "text", "required": False, "defaultValue": "4", "description": "一次评测会触发 count 个子任务并聚合结果"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
    },
    # 图裂变 / AI 团队高质量 SoftStyle Coze 工作流
    {
        "category": "图裂变",
        "name": "图裂变 · 高质量 SoftStyle",
        "version": "2026-04-23",
        "workflow_id": "7631838631375667200",
        "status": "active",
        "notes": "AI 团队 2026-04-23 交付的高质量 SoftStyle 裂变主线。输入 url + bili + 宽高，输出回调 task id。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "image", "required": True},
                {"name": "bili", "label": REPAINT_STRENGTH_LABEL, "type": "text", "required": True, "defaultValue": "50%", "description": REPAINT_STRENGTH_DESCRIPTION},
                {"name": "width", "label": "宽度", "type": "text", "required": False, "defaultValue": "", "description": "像素数值（纯数字，不要带 px）"},
                {"name": "height", "label": "高度", "type": "text", "required": False, "defaultValue": "", "description": "像素数值（纯数字，不要带 px）"},
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
                {"name": "count", "label": "裂变数量", "type": "text", "required": False, "defaultValue": "4", "description": "一次评测会触发 count 个子任务并聚合结果"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
                {"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"},
            ]
        },
        "metadata": {
            "presentation": {
                "operation_label": "图像裂变",
                "variant_label": "高质量 SoftStyle",
                "result_mode": "callback_image",
                "supports_batch": True,
                "usage_hint": "当前推荐的 Coze 图裂变主线，用于对照原生业务接口效果。",
            },
            "governance": {
                "role": "production",
                "role_label": "生产主入口",
                "role_reason": "当前业务正在使用的高质量 SoftStyle 裂变主线。",
            },
        },
    },
    # 图裂变 / 中台原生业务接口：GPT Image 2 + VL 控制版
    {
        "category": "图裂变",
        "name": "图裂变 · GPT Image 2 + VL 控制版",
        "version": "gpt-image2-vl-v2",
        "workflow_id": "business_fission_gpt_image2_vl_v1",
        "status": "active",
        "notes": "中台原生图裂变业务接口。VL 只生成客观识别卡，中台做图案路由、定量提示词编译，再调用 GPT Image 2 图片编辑。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "原图 URL", "type": "image", "required": True, "description": "裂变前的参考原图；测评端上传后会自动写入。"},
                {"name": "prompt", "label": "额外要求", "type": "textarea", "required": False, "defaultValue": "", "description": "可选；不填也会按 VL 识别卡和默认受控提示词运行。"},
                {
                    "name": "variation_strength",
                    "label": "裂变幅度",
                    "type": "select",
                    "required": False,
                    "defaultValue": "same_series",
                    "description": "默认同系列裂变；保守更像原图，强变化只在需要更大差异时使用。",
                    "options": [
                        {"label": "同系列裂变", "value": "same_series"},
                        {"label": "保守变化", "value": "conservative"},
                        {"label": "强变化同系列", "value": "creative_same_series"},
                    ],
                },
                {
                    "name": "quality",
                    "label": "质量档位",
                    "type": "select",
                    "required": False,
                    "defaultValue": "preview",
                    "options": [
                        {"label": "预览", "value": "preview"},
                        {"label": "候选抽样", "value": "candidate"},
                        {"label": "高质", "value": "premium"},
                    ],
                },
                {"name": "maskUrl", "label": "蒙版 URL", "type": "text", "required": False, "defaultValue": "", "description": "可选；需要局部编辑时传入。"},
                {
                    "name": "size",
                    "label": "比例尺寸",
                    "type": "select",
                    "required": False,
                    "defaultValue": "auto",
                    "description": "默认 auto，尽量保持原图比例。",
                    "options": GPT_IMAGE2_SIZE_OPTIONS,
                },
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "imageUrls", "type": "array", "description": "中台 OSS 结果图"},
                {"name": "runId", "type": "text", "description": "业务运行 ID"},
                {"name": "taskId", "type": "text", "description": "底层能力任务 ID"},
            ]
        },
        "metadata": {
            "isNewVersion": False,
            "badge": "已优化",
            "presentation": {
                "operation_label": "图像裂变",
                "variant_label": "GPT Image 2 + VL 控制版",
                "badges": ["已优化", "原生业务接口"],
                "release_time": "2026-05-12",
                "update_time": "2026-05-13",
                "update_note": "底层升级为 GPT Image 2 受控版：VL 只生成客观识别卡，中台统一编译图案路由、密度、主色和构图约束。",
                "supports_batch": True,
                "result_mode": "image",
                "usage_hint": "用于验证 GPT Image 2 受控裂变接口，重点看图案类别、密度、主色和构图是否稳定。",
            },
            "governance": {
                "role": "candidate",
                "role_label": "灰度验证版本",
                "role_reason": "2026-05-13 优化替换，沿用原测评入口做效果和稳定性验证。",
            },
            "eval_execution": {
                "mode": "business_run",
                "business_key": "fission",
                "version": "gpt-image2-vl-v2",
            },
        },
    },
    # 图裂变 / 中台原生业务接口：ComfyUI VL 控制卡版
    {
        "category": "图裂变",
        "name": "图裂变 · ComfyUI VL 控制卡版",
        "version": "comfyui-vl-control-v2",
        "workflow_id": "business_fission_comfyui_vl_control_v1",
        "status": "active",
        "notes": "中台原生图裂变业务接口。先由统一 VL 组件识别图案风险类型，再调用 ComfyUI 智能路由参数，重点兼顾对象级变化和颜色稳定性。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "原图 URL", "type": "image", "required": True, "description": "裂变前的参考原图；测评端上传后会自动写入。"},
                {"name": "bili", "label": REPAINT_STRENGTH_LABEL, "type": "text", "required": False, "defaultValue": "80%", "description": "控制图案变化大小；建议低 30%、中 60%、高 80%、极高 100%+。后端会结合 VL 图案类型路由实际 denoise。"},
                {"name": "width", "label": "输出宽度", "type": "text", "required": False, "defaultValue": "", "description": "不填则跟随原图宽度；手动填写时只填数字，不要带 px。"},
                {"name": "height", "label": "输出高度", "type": "text", "required": False, "defaultValue": "", "description": "不填则跟随原图高度；手动填写时只填数字，不要带 px。"},
                {
                    "name": "profile",
                    "label": "裂变路由配置",
                    "type": "select",
                    "required": False,
                    "defaultValue": "pattern_risk_routed_v4",
                    "description": "默认智能风险路由适合大多数样本；兼容配置用于旧样本对照。",
                    "options": [
                        {"label": "智能风险路由（推荐）", "value": "pattern_risk_routed_v4"},
                        {"label": "默认颜色锁定（兼容）", "value": "pattern_color_lock_v2"},
                        {"label": "严格颜色锁定（更像原图）", "value": "pattern_color_lock_strict_v2"},
                    ],
                },
                {"name": "reference_lock", "label": "原图结构保留度", "type": "text", "required": False, "defaultValue": "0.42", "description": "建议 0.34-0.50，不做硬限制。越高越像原图，裂变感更弱。"},
                {"name": "color_lock", "label": "颜色锁定强度", "type": "text", "required": False, "defaultValue": "0.90", "description": "建议 0.75-1.00，不做硬限制。越高越不容易偏色。"},
                {"name": "prompt", "label": "额外要求", "type": "textarea", "required": False, "defaultValue": "", "description": "可选；不要写放开配色或重新设计色彩的要求。"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "imageUrls", "type": "array", "description": "中台 OSS 结果图"},
                {"name": "runId", "type": "text", "description": "业务运行 ID"},
                {"name": "taskId", "type": "text", "description": "底层能力任务 ID"},
            ]
        },
        "metadata": {
            "isNewVersion": False,
            "badge": "已优化",
            "presentation": {
                "operation_label": "图像裂变",
                "variant_label": "ComfyUI VL 控制卡版",
                "badges": ["已优化", "原生业务接口"],
                "release_time": "2026-05-12",
                "update_time": "2026-05-14",
                "update_note": "修补为对象级裂变路由版：新增原图结构保留度、颜色锁定强度和测评预设；原有 URL、重绘幅度、宽高和额外要求参数保持可用。",
                "supports_batch": True,
                "result_mode": "image",
                "usage_hint": "用于验证 ComfyUI 智能路由裂变接口，重点看对象级变化、主色、深浅比例和图案结构是否稳定。",
            },
            "governance": {
                "role": "candidate",
                "role_label": "灰度验证版本",
                "role_reason": "2026-05-13 优化替换，沿用原测评入口做效果和稳定性验证。",
            },
            "eval_execution": {
                "mode": "business_run",
                "business_key": "fission",
                "version": "comfyui-vl-control-v2",
            },
        },
    },
    # 图像理解 / 裂变生成图质量评估
    {
        "category": "图像理解",
        "name": "生成图评估 · 裂变质量与逻辑评估",
        "version": "generated-image-eval-v1",
        "workflow_id": "ability_fission_generated_image_evaluate_v1",
        "status": "active",
        "notes": "单独评估裂变生成图质量和逻辑合理性，输出 pass / needs_refission / reject，业务侧自行决定是否二次裂变。",
        "parameters_schema": {
            "fields": [
                {"name": "original_image", "label": "原图 URL", "type": "image", "required": True, "description": "裂变前的参考原图。"},
                {"name": "generated_image", "label": "生成图 URL", "type": "image", "required": True, "description": "裂变后需要评估的生成图。"},
                {"name": "context", "label": "评估上下文 JSON", "type": "textarea", "required": False, "defaultValue": "", "description": "可传 task_id、profile、pattern_type 等信息；为空也可评估。"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "json", "description": "评估结果 JSON：decision、score、problem_tags、reason、next_action"},
            ]
        },
        "metadata": {
            "isNewVersion": True,
            "badge": "新版",
            "presentation": {
                "operation_label": "图像理解",
                "variant_label": "裂变质量评估",
                "badges": ["新版", "原子组件"],
                "supports_batch": False,
                "result_mode": "structured_json",
                "usage_hint": "用于评估裂变结果是否合理，通常接在裂变出图之后单独调用。",
            },
            "governance": {
                "role": "candidate",
                "role_label": "灰度验证版本",
                "role_reason": "2026-05-12 新接入，先在测评端验证评估结论稳定性。",
            },
            "eval_execution": {
                "mode": "ability_task",
                "ability_id": "vl_fission_generated_image_evaluate",
                "image_fields": ["original_image", "generated_image"],
            },
        },
    },
    # 不建议直接使用：ComfyUI 回调工作流（供后端兜底解析 images）
    {
        "category": "general",
        "name": "ComfyUI 回调 · comfyui_huidiao",
        "version": "v1",
        "workflow_id": "7597556718159003648",
        "status": "active",
        "notes": "输入 taskid，输出 images 数组（回调工作流）。业务侧可直接调用该 workflow 获取图片。",
        "parameters_schema": {"fields": [{"name": "taskid", "label": "taskid", "type": "text", "required": True}]},
        "output_schema": {"fields": [{"name": "images", "type": "array", "description": "图片数组"}]},
    },
]

DEFAULT_OUTPUT_SCHEMA_BY_ID: dict[str, dict[str, Any]] = {
    str(item.get("workflow_id")): item.get("output_schema") or {}
    for item in DEFAULT_EVAL_WORKFLOW_VERSIONS
    if item.get("workflow_id")
}

DEFAULT_EVAL_WORKFLOW_BY_ID: dict[str, dict[str, Any]] = {
    str(item.get("workflow_id")): item
    for item in DEFAULT_EVAL_WORKFLOW_VERSIONS
    if item.get("workflow_id")
}


def ensure_default_eval_workflow_versions(session: Session) -> bool:
    """Insert missing default workflow versions. Returns True if any created."""
    existing = set(
        (
            str(row.workflow_id or "").strip(),
            _resolve_eval_category(str(row.workflow_id or "").strip(), str(row.category or "").strip()),
        )
        for row in session.execute(select(EvalWorkflowVersion.workflow_id, EvalWorkflowVersion.category)).all()
    )
    created = False
    for item in DEFAULT_EVAL_WORKFLOW_VERSIONS:
        workflow_id = str(item.get("workflow_id") or "").strip()
        desired_category = _resolve_eval_category(workflow_id, str(item.get("category") or "").strip())
        if not workflow_id or (workflow_id, desired_category) in existing:
            continue
        row = EvalWorkflowVersion(
            id=uuid4().hex,
            category=desired_category,
            name=item["name"],
            version=item.get("version") or "v1",
            workflow_id=workflow_id,
            status=item.get("status") or "active",
            notes=item.get("notes"),
            parameters_schema=item.get("parameters_schema"),
            output_schema=item.get("output_schema"),
            extra_metadata=item.get("metadata"),
        )
        session.add(row)
        existing.add((workflow_id, desired_category))
        created = True
    if created:
        session.commit()

    # Small safe normalizations for seeded workflows (no destructive updates):
    # - ensure ComfyUI lora field is a select with known options
    # - move certain workflows to general category (as per business definition)
    def _coerce_schema(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            return {"fields": value}
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"fields": parsed}
        return {}

    def _schema_expects_callback(schema: dict[str, Any] | None) -> bool:
        fields = schema.get("fields") if isinstance(schema, dict) else None
        if not isinstance(fields, list):
            return False
        for f in fields:
            if not isinstance(f, dict) or f.get("name") != "output":
                continue
            desc = str(f.get("description") or "")
            if "task" in desc.lower() or "回调" in desc:
                return True
        return False

    rows = session.execute(select(EvalWorkflowVersion)).scalars().all()
    dirty = False
    for row in rows:
        if row.workflow_id in DEPRECATED_EVAL_WORKFLOW_IDS and row.status != "inactive":
            row.status = "inactive"
            dirty = True
        if row.workflow_id == "7597556718159003648":
            # Ensure callback workflow is visible for developers.
            if row.status != "active":
                row.status = "active"
                dirty = True
            if row.name != "ComfyUI 回调 · comfyui_huidiao":
                row.name = "ComfyUI 回调 · comfyui_huidiao"
                dirty = True
            if row.notes != "输入 taskid，输出 images 数组（回调工作流）。业务侧可直接调用该 workflow 获取图片。":
                row.notes = "输入 taskid，输出 images 数组（回调工作流）。业务侧可直接调用该 workflow 获取图片。"
                dirty = True
        if row.workflow_id in {"7602916576198656000", "7612002440056930304"} | FORCE_SYNC_EVAL_WORKFLOW_IDS:
            # Force-reset critical workflows to the latest agreed schema.
            desired = DEFAULT_EVAL_WORKFLOW_BY_ID.get(row.workflow_id)
            if desired:
                desired_category = _resolve_eval_category(row.workflow_id, desired.get("category"))
                if row.status != (desired.get("status") or "active"):
                    row.status = desired.get("status") or "active"
                    dirty = True
                if row.name != desired.get("name"):
                    row.name = desired.get("name")
                    dirty = True
                if row.version != (desired.get("version") or "v1"):
                    row.version = desired.get("version") or "v1"
                    dirty = True
                if row.notes != desired.get("notes"):
                    row.notes = desired.get("notes")
                    dirty = True
                if row.category != desired_category:
                    row.category = desired_category
                    dirty = True
                if row.parameters_schema != desired.get("parameters_schema"):
                    row.parameters_schema = desired.get("parameters_schema")
                    dirty = True
                if row.output_schema != desired.get("output_schema"):
                    row.output_schema = desired.get("output_schema")
                    dirty = True
                if "metadata" in desired and row.extra_metadata != desired.get("metadata"):
                    row.extra_metadata = desired.get("metadata")
                    dirty = True
        if row.workflow_id == "7598848725942796288":
            # Force-reset to the latest "裂变（商业有提示词）" spec (field list has changed).
            desired = DEFAULT_EVAL_WORKFLOW_BY_ID.get(row.workflow_id)
            if desired:
                if row.parameters_schema != desired.get("parameters_schema"):
                    row.parameters_schema = desired.get("parameters_schema")
                    dirty = True
                if row.output_schema != desired.get("output_schema"):
                    row.output_schema = desired.get("output_schema")
                    dirty = True
        if row.workflow_id == "7604714915110060032":
            # Ensure AI 图片编辑器参数表单与默认值保持最新。
            desired = DEFAULT_EVAL_WORKFLOW_BY_ID.get(row.workflow_id)
            if desired:
                if row.parameters_schema != desired.get("parameters_schema"):
                    row.parameters_schema = desired.get("parameters_schema")
                    dirty = True
                if row.output_schema != desired.get("output_schema"):
                    row.output_schema = desired.get("output_schema")
                    dirty = True
        desired_category = _resolve_eval_category(row.workflow_id, row.category)
        if row.category != desired_category:
            row.category = desired_category
            dirty = True
        # Keep workflow names editable in the admin UI; do not force-reset names here.
        # Ensure lora field stays a select with known options.
        if row.workflow_id in {"7597530887256801280", "7598545860393172992"}:
            # Work on a copy: mutating JSON in-place is not tracked by SQLAlchemy.
            schema = json.loads(json.dumps(row.parameters_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if isinstance(fields, list):
                for f in fields:
                    if not isinstance(f, dict) or f.get("name") != "lora":
                        continue
                    desired_options = [{"label": x, "value": x} for x in LORA_OPTIONS]
                    desired_default = LORA_OPTIONS[0]
                    # Always normalize the options list to avoid stale/removed LoRA names
                    # lingering in DB rows (e.g. old YinHuaTiQu presets).
                    if (
                        f.get("type") != "select"
                        or f.get("defaultValue") != desired_default
                        or f.get("options") != desired_options
                    ):
                        f["type"] = "select"
                        f["defaultValue"] = desired_default
                        f["options"] = desired_options
                        row.parameters_schema = schema
                        dirty = True
        if row.workflow_id == "7598545860393172992":
            schema = json.loads(json.dumps(row.parameters_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if isinstance(fields, list):
                desired_field = {
                    "name": "is_raw_prompt",
                    "label": "提示词模式",
                    "type": "select",
                    "required": False,
                    "defaultValue": "0",
                    "options": [
                        {"label": "0 · 用户提示词 + 系统提示词", "value": "0"},
                        {"label": "1 · 仅使用用户提示词", "value": "1"},
                    ],
                    "description": "为空/0=拼接系统提示词；1=只使用用户提示词（系统提示词不生效）",
                }
                idx = None
                existing = None
                for i, f in enumerate(fields):
                    if not isinstance(f, dict):
                        continue
                    if f.get("name") == "is_raw_prompt":
                        idx = i
                        existing = f
                        break
                if existing:
                    if existing != desired_field:
                        fields[idx] = desired_field
                        row.parameters_schema = schema
                        dirty = True
                else:
                    insert_at = None
                    for i, f in enumerate(fields):
                        if isinstance(f, dict) and f.get("name") == "prompt":
                            insert_at = i + 1
                            break
                    if insert_at is None:
                        insert_at = len(fields)
                    fields.insert(insert_at, desired_field)
                    row.parameters_schema = schema
                    dirty = True
        if row.workflow_id in {"7597723984687267840", "7598587935331450880"}:
            # Normalize outpaint schema to use `url` as the canonical image key.
            schema = json.loads(json.dumps(row.parameters_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if isinstance(fields, list):
                changed = False
                has_url = False
                for f in fields:
                    if not isinstance(f, dict):
                        continue
                    if f.get("name") == "url":
                        has_url = True
                if not has_url:
                    for f in fields:
                        if isinstance(f, dict) and f.get("name") == "Url":
                            f["name"] = "url"
                            f["label"] = "图片 URL"
                            f["required"] = True
                            changed = True
                            has_url = True
                            break
                if has_url:
                    filtered = []
                    for f in fields:
                        if not isinstance(f, dict):
                            filtered.append(f)
                            continue
                        if f.get("name") == "Url":
                            changed = True
                            continue
                        if f.get("name") == "url":
                            if f.get("required") is not True:
                                f["required"] = True
                                changed = True
                            if not f.get("label"):
                                f["label"] = "图片 URL"
                                changed = True
                        filtered.append(f)
                    fields = filtered
                if changed:
                    schema["fields"] = fields
                    row.parameters_schema = schema
                    dirty = True
        if row.workflow_id in {"7601080398864449536", "7598559869544693760", "7598560946579046400"}:
            # Ensure image URL field exists (some legacy rows were missing it).
            schema = json.loads(json.dumps(row.parameters_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if isinstance(fields, list):
                changed = False
                has_url = any(isinstance(f, dict) and f.get("name") == "url" for f in fields)
                has_Url = any(isinstance(f, dict) and f.get("name") == "Url" for f in fields)
                if not has_url and has_Url:
                    for f in fields:
                        if isinstance(f, dict) and f.get("name") == "Url":
                            f["name"] = "url"
                            f["label"] = "图片 URL"
                            f["required"] = True
                            changed = True
                            has_url = True
                            break
                if not has_url:
                    fields.insert(
                        0,
                        {
                            "name": "url",
                            "label": "图片 URL",
                            "type": "text",
                            "required": True,
                        },
                    )
                    changed = True
                if has_Url:
                    filtered = []
                    for f in fields:
                        if isinstance(f, dict) and f.get("name") == "Url":
                            changed = True
                            continue
                        filtered.append(f)
                    fields = filtered
                if changed:
                    schema["fields"] = fields
                    row.parameters_schema = schema
                    dirty = True
        if row.workflow_id in {
            "7597723984687267840",
            "7598587935331450880",
            "7601080398864449536",
            "7598559869544693760",
            "7598560946579046400",
            "7601077530077954048",
            "7598848725942796288",
        }:
            # Ensure output schema hints callback task ids for new async workflows.
            schema = _coerce_schema(row.output_schema or {})
            desired = _coerce_schema(DEFAULT_OUTPUT_SCHEMA_BY_ID.get(row.workflow_id) or {})
            if not schema or not _schema_expects_callback(schema):
                if desired:
                    row.output_schema = desired
                    dirty = True
            else:
                fields = schema.get("fields") if isinstance(schema, dict) else None
                if isinstance(fields, list):
                    changed = False
                    for f in fields:
                        if not isinstance(f, dict) or f.get("name") != "output":
                            continue
                        desc = str(f.get("description") or "")
                        if "回调" not in desc and "task" not in desc.lower():
                            f["description"] = "回调 task id"
                            changed = True
                    if changed:
                        schema["fields"] = fields
                        row.output_schema = schema
                        dirty = True
        if row.workflow_id in PROMPT_OUTPUT_WORKFLOW_IDS:
            # Ensure prompt is documented in output schema.
            schema = _coerce_schema(row.output_schema or {})
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if not isinstance(fields, list):
                fields = []
            has_prompt = any(isinstance(f, dict) and f.get("name") == "prompt" for f in fields)
            if not has_prompt:
                fields.append({"name": "prompt", "type": "text", "description": "提示词反馈字符串"})
                schema["fields"] = fields
                row.output_schema = schema
                dirty = True
        if row.workflow_id in IP_OUTPUT_WORKFLOW_IDS:
            # Ensure ComfyUI executor IP is documented in output schema.
            schema = json.loads(json.dumps(row.output_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if not isinstance(fields, list):
                fields = []
            has_ip = any(isinstance(f, dict) and f.get("name") == "ip" for f in fields)
            if not has_ip:
                fields.append({"name": "ip", "type": "text", "description": "ComfyUI 执行节点 IP"})
                schema["fields"] = fields
                row.output_schema = schema
                dirty = True
        if row.workflow_id in {"7598563505054154752", "7598587935331450880"}:
            # These workflows do not return prompt feedback; remove prompt field if present.
            schema = json.loads(json.dumps(row.output_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if isinstance(fields, list):
                filtered = [f for f in fields if not (isinstance(f, dict) and f.get("name") == "prompt")]
                if filtered != fields:
                    schema["fields"] = filtered
                    row.output_schema = schema
                    dirty = True
        if row.workflow_id in REPAINT_STRENGTH_WORKFLOW_IDS:
            # Normalize bili/similarity display: this parameter controls denoise, not similarity.
            schema = json.loads(json.dumps(row.parameters_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if isinstance(fields, list):
                changed = False
                for f in fields:
                    if not isinstance(f, dict):
                        continue
                    if f.get("name") == "similarity":
                        if f.get("label") != REPAINT_STRENGTH_LABEL:
                            f["label"] = REPAINT_STRENGTH_LABEL
                            changed = True
                        if f.get("description") != f"{REPAINT_STRENGTH_DESCRIPTION} 兼容字段：bili。":
                            f["description"] = f"{REPAINT_STRENGTH_DESCRIPTION} 兼容字段：bili。"
                            changed = True
                    if f.get("name") == "bili":
                        if f.get("label") != REPAINT_STRENGTH_LABEL:
                            f["label"] = REPAINT_STRENGTH_LABEL
                            changed = True
                        if f.get("description") != REPAINT_STRENGTH_DESCRIPTION:
                            f["description"] = REPAINT_STRENGTH_DESCRIPTION
                            changed = True
                if changed:
                    schema["fields"] = fields
                    row.parameters_schema = schema
                    dirty = True
        if row.workflow_id in FISSION_WORKFLOW_IDS:
            # Ensure "裂变数量" (count) is present in schema for evaluation-only fan-out.
            schema = json.loads(json.dumps(row.parameters_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if isinstance(fields, list):
                has_count = any(isinstance(f, dict) and f.get("name") == "count" for f in fields)
                if not has_count:
                    fields.append(
                        {
                            "name": "count",
                            "label": "裂变数量",
                            "type": "text",
                            "required": False,
                            "defaultValue": "4",
                            "description": "一次评测会触发 count 个子任务并聚合结果",
                        }
                    )
                    schema["fields"] = fields
                    row.parameters_schema = schema
                    dirty = True
        if row.workflow_id in {"7601080398864449536", "7598559869544693760", "7598560946579046400"}:
            # For Banana/Flux2 aspect_ratio/resolution, leave default empty so UI doesn't force 1K.
            schema = json.loads(json.dumps(row.parameters_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if isinstance(fields, list):
                changed = False
                for f in fields:
                    if not isinstance(f, dict):
                        continue
                    if f.get("name") in {"aspect_ratio", "resolution"}:
                        if f.get("defaultValue") != "":
                            f["defaultValue"] = ""
                            changed = True
                if changed:
                    schema["fields"] = fields
                    row.parameters_schema = schema
                    dirty = True
        # Normalize pixel field labels/descriptions (avoid "px" suffix and enforce numeric).
        schema = json.loads(json.dumps(row.parameters_schema or {}, ensure_ascii=False))
        fields = schema.get("fields") if isinstance(schema, dict) else None
        if isinstance(fields, list):
            changed = False
            pixel_fields = {"width", "height", "expand_left", "expand_right", "expand_top", "expand_bottom", "bianchang"}
            for f in fields:
                if not isinstance(f, dict):
                    continue
                name = f.get("name")
                if name not in pixel_fields:
                    continue
                label = str(f.get("label") or "")
                if "px" in label.lower():
                    cleaned = (
                        label.replace("（px）", "")
                        .replace("(px)", "")
                        .replace("px", "")
                        .replace("PX", "")
                        .replace("Px", "")
                        .replace("()", "")
                        .replace("（）", "")
                        .strip()
                    )
                    f["label"] = cleaned
                    changed = True
                desc = str(f.get("description") or "")
                if "不要带" not in desc:
                    f["description"] = "像素数值（纯数字，不要带 px）"
                    changed = True
            if changed:
                schema["fields"] = fields
                row.parameters_schema = schema
                dirty = True
        if row.workflow_id == "7598563505054154752":
            # Coze workflow requires height/width. Ensure DB schema matches so UI and
            # client requests always include them (avoids COZE code=4000 failures).
            schema = json.loads(json.dumps(row.parameters_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if isinstance(fields, list):
                changed = False
                for f in fields:
                    if not isinstance(f, dict):
                        continue
                    if f.get("name") in {"height", "width"}:
                        if f.get("required") is not True:
                            f["required"] = True
                            changed = True
                        if not isinstance(f.get("defaultValue"), str) or not str(f.get("defaultValue") or "").strip():
                            f["defaultValue"] = "1024"
                            changed = True
                if changed:
                    schema["fields"] = fields
                    row.parameters_schema = schema
                    dirty = True
        if row.workflow_id == "7597659369861283840":
            # Coze workflow requires prompt. Some older DB rows were seeded with prompt optional
            # which causes COZE code=4000 failures when UI leaves it empty. Normalize it.
            schema = json.loads(json.dumps(row.parameters_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if isinstance(fields, list):
                changed = False
                has_prompt = False
                for f in fields:
                    if not isinstance(f, dict):
                        continue
                    if f.get("name") == "prompt":
                        has_prompt = True
                        if f.get("required") is not True:
                            f["required"] = True
                            changed = True
                        if not isinstance(f.get("type"), str) or not str(f.get("type") or "").strip():
                            f["type"] = "textarea"
                            changed = True
                        if "defaultValue" not in f:
                            f["defaultValue"] = ""
                            changed = True
                if not has_prompt:
                    # Insert after url for a predictable form order.
                    insert_at = 1 if fields and isinstance(fields[0], dict) and fields[0].get("name") == "url" else 0
                    fields.insert(
                        insert_at,
                        {"name": "prompt", "label": "提示词", "type": "textarea", "required": True, "defaultValue": ""},
                    )
                    changed = True
                if changed:
                    schema["fields"] = fields
                    row.parameters_schema = schema
                    dirty = True
    if _dedupe_eval_workflow_versions(session):
        dirty = True
    if dirty:
        session.commit()
    return created
