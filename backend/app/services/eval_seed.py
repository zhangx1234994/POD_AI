"""Seed default evaluation workflow versions.

This is intentionally lightweight and safe to call on request:
- It only inserts missing rows (by workflow_id).
- It never mutates existing rows (to avoid surprising changes).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.eval import EvalWorkflowVersion
from app.constants.abilities import PATTERN_EXTRACT_LORA_PRESETS


LORA_OPTIONS = [
    entry.get("value")
    for entry in PATTERN_EXTRACT_LORA_PRESETS
    if isinstance(entry, dict) and entry.get("value")
]
if not LORA_OPTIONS:
    # Fallback (should not happen unless presets are removed).
    LORA_OPTIONS = ["杯子1124.safetensors"]

# Workflows that should not show up in the evaluation UI anymore.
# Note: seed inserts are append-only, so we also apply a small normalization pass
# to mark these as inactive if they already exist in DB.
DEPRECATED_EVAL_WORKFLOW_IDS: set[str] = {
    # 提取类
    "7597535455856295936",  # 提示词提取 · tishici_tiqu
    # 花纹提取类（旧的 space_id 误填版本，保留但不再展示）
    "7597421439045599232",  # tiqu_duoMoxing_2 (wrong id, superseded by 7598558185544220672)
    # 花纹提取类（旧版本，已替换为 7601080398864449536）
    "7598558185544220672",  # tiqu_duoMoxing_2 (old)
    # 图裂变（旧商业模型版本）
    "7598844004557389824",  # Liebian_shangye_20260124_1_1
}

# Evaluation UI category policy: keep the sidebar fixed to these groups.
ALLOWED_EVAL_CATEGORIES: set[str] = {
    "花纹提取类",
    "图延伸类",
    "四方/两方连续图类",
    "图裂变",
    "通用类",
}

# Workflows whose output should include prompt feedback.
PROMPT_OUTPUT_WORKFLOW_IDS: set[str] = {
    "7597530887256801280",  # tiqu_comfyui_20260123
    "7598545860393172992",  # tiqu_comfyui_20260123_2
    "7601080398864449536",  # tiqu_duoMoxing_2
    "7598559869544693760",  # tiqu_duoMoxing_20260130
    "7598560946579046400",  # tiqu_duoMoxing_2_2
    "7597701996124045312",  # sibu_comfyui
    "7597702948247830528",  # zhongsu_comfyui
    "7598841920114130944",  # Liebian_comfyui_20260124_1
    "7598820684801769472",  # Liebian_comfyui_20260124
    "7601077530077954048",  # Liebian_shangye_20260130
    "7598848725942796288",  # Liebian_shangye_20260124_1_1_1
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
    if c in {"general", "common"}:
        return "通用类"
    # Safe fallback to avoid leaking extra categories into the sidebar.
    return "通用类"


# Workflows we want to keep visible in the evaluation UI.
# Some were previously marked inactive during cleanup; we flip them back to active
# in the normalization pass so existing DB rows recover without manual edits.
FORCE_ACTIVE_EVAL_WORKFLOW_IDS: set[str] = {
    # 花纹提取 5 个
    "7597530887256801280",  # tiqu_comfyui_20260123
    "7598545860393172992",  # tiqu_comfyui_20260123_2
    "7601080398864449536",  # tiqu_duoMoxing_2
    "7598559869544693760",  # tiqu_duoMoxing_20260130
    "7598560946579046400",  # tiqu_duoMoxing_2_2
    # 连续图
    "7598563505054154752",  # lianxu
    # 图扩展
    "7597723984687267840",  # duomotaikuotu (multi-model outpaint)
    "7598587935331450880",  # comfyuo_tukuozhan (comfyui outpaint)
    # 通用
    "7598589746561941504",  # dpi增分
    "7597767702970630144",  # Biaoqian_tiqu (small)
    "7598080013539213312",  # Biaoqian_tiqu_1 (large)
    "7600254097513512960",  # Biaoqian_tiqu_3
    "7600254796297142272",  # Biaoqian_tiqu_3_1
    "7601054603211177984",  # comfyui_duilie
    "7597701996124045312",  # sibu_comfyui
    "7597702948247830528",  # zhongsu_comfyui
    # 图裂变
    "7598841920114130944",  # Liebian_comfyui_20260124_1
    "7598820684801769472",  # Liebian_comfyui_20260124
    "7601077530077954048",  # Liebian_shangye_20260130
    "7598848725942796288",  # Liebian_shangye_20260124_1_1_1
    "7597760543788630016",  # 8K 高清放大
}


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
        "notes": "输出 output 为回调 task id。此版本在工作流侧支持提示词拼接（如启用对应输入字段）。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "height", "label": "高度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "width", "label": "宽度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "prompt", "label": "提示词", "type": "textarea", "required": False, "defaultValue": ""},
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
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    # 花纹提取类 / 商业模型 + ComfyUI 串联（为兼顾输出尺寸；输出回调 task id）
    {
        "category": "花纹提取类",
        "name": "花纹提取 · tiqu_duoMoxing_2_2",
        "version": "v1",
        "workflow_id": "7598560946579046400",
        "status": "active",
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
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
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
                {"name": "height", "label": "高度", "type": "text", "required": True, "defaultValue": "1024"},
                {"name": "width", "label": "宽度", "type": "text", "required": True, "defaultValue": "1024"},
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
                {"name": "expand_left", "label": "左扩(px)", "type": "text", "required": False, "defaultValue": "0"},
                {"name": "expand_right", "label": "右扩(px)", "type": "text", "required": False, "defaultValue": "0"},
                {"name": "expand_top", "label": "上扩(px)", "type": "text", "required": False, "defaultValue": "0"},
                {"name": "expand_bottom", "label": "下扩(px)", "type": "text", "required": False, "defaultValue": "0"},
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
                {"name": "expand_left", "label": "左扩(px)", "type": "text", "required": False, "defaultValue": "0"},
                {"name": "expand_right", "label": "右扩(px)", "type": "text", "required": False, "defaultValue": "0"},
                {"name": "expand_top", "label": "上扩(px)", "type": "text", "required": False, "defaultValue": "0"},
                {"name": "expand_bottom", "label": "下扩(px)", "type": "text", "required": False, "defaultValue": "0"},
            ]
        },
        "output_schema": {
            "fields": [
                {"name": "output", "type": "text", "description": "回调 task id"},
                {"name": "prompt", "type": "text", "description": "提示词反馈字符串"},
            ]
        },
    },
    # 图略变类 / 多模型生图（Banana Pro / Flux2 / Doubao 4.5）
    {
        "category": "general",
        "name": "多模型生图",
        "version": "v1",
        "workflow_id": "7597659369861283840",
        "status": "active",
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
                {"name": "width", "label": "宽度(px)", "type": "text", "required": False, "defaultValue": ""},
                {"name": "height", "label": "高度(px)", "type": "text", "required": False, "defaultValue": ""},
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
                {"name": "bianchang", "label": "最长边(px)", "type": "text", "required": False, "defaultValue": "4096"},
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
                {"name": "height", "label": "高度", "type": "text", "required": True, "defaultValue": "1024"},
                {"name": "width", "label": "宽度", "type": "text", "required": True, "defaultValue": "1024"},
                {
                    "name": "similarity",
                    "label": "相似度(%)",
                    "type": "text",
                    "required": True,
                    "defaultValue": "50%",
                    "description": "与原图保持相似的百分比（越高越接近原图）。兼容字段：bili。",
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
                {"name": "height", "label": "高度", "type": "text", "required": True, "defaultValue": "1024"},
                {"name": "width", "label": "宽度", "type": "text", "required": True, "defaultValue": "1024"},
                {
                    "name": "similarity",
                    "label": "相似度(%)",
                    "type": "text",
                    "required": True,
                    "defaultValue": "50%",
                    "description": "与原图保持相似的百分比（越高越接近原图）。兼容字段：bili。",
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
                    "label": "相似度(%)",
                    "type": "text",
                    "required": True,
                    "defaultValue": "50%",
                    "description": "与原图保持相似的百分比（越高越接近原图）。",
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
                    "label": "相似度(%)",
                    "type": "text",
                    "required": True,
                    "defaultValue": "50%",
                    "description": "与原图保持相似的百分比（越高越接近原图）。",
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
    # 不建议直接使用：ComfyUI 回调工作流（供后端兜底解析 images）
    {
        "category": "general",
        "name": "ComfyUI 回调（不建议手动调用）",
        "version": "v1",
        "workflow_id": "7597556718159003648",
        "status": "inactive",
        "notes": "输入 taskid，输出 images 数组。建议直接由 PODI 轮询 ability_tasks。",
        "parameters_schema": {"fields": [{"name": "taskid", "label": "taskid", "type": "text", "required": True}]},
        "output_schema": {"fields": [{"name": "images", "type": "array", "description": "图片数组"}]},
    },
]


def ensure_default_eval_workflow_versions(session: Session) -> bool:
    """Insert missing default workflow versions. Returns True if any created."""
    existing = set(
        session.execute(select(EvalWorkflowVersion.workflow_id)).scalars().all()
    )
    created = False
    for item in DEFAULT_EVAL_WORKFLOW_VERSIONS:
        workflow_id = str(item.get("workflow_id") or "").strip()
        if not workflow_id or workflow_id in existing:
            continue
        row = EvalWorkflowVersion(
            id=uuid4().hex,
            category=item["category"],
            name=item["name"],
            version=item.get("version") or "v1",
            workflow_id=workflow_id,
            status=item.get("status") or "active",
            notes=item.get("notes"),
            parameters_schema=item.get("parameters_schema"),
            output_schema=item.get("output_schema"),
        )
        session.add(row)
        created = True
    if created:
        session.commit()

    # Small safe normalizations for seeded workflows (no destructive updates):
    # - ensure ComfyUI lora field is a select with known options
    # - move certain workflows to general category (as per business definition)
    category_fixes = {
        "7597701996124045312": "通用类",  # 4 steps
        "7597702948247830528": "通用类",  # 8 steps
        "7597659369861283840": "通用类",  # multi-model gen
    }
    rows = session.execute(select(EvalWorkflowVersion)).scalars().all()
    dirty = False
    for row in rows:
        if row.workflow_id in DEPRECATED_EVAL_WORKFLOW_IDS and row.status != "inactive":
            row.status = "inactive"
            dirty = True
        if row.workflow_id in FORCE_ACTIVE_EVAL_WORKFLOW_IDS and row.status != "active":
            row.status = "active"
            dirty = True
        normalized_category = _normalize_eval_category(row.category)
        if row.category != normalized_category:
            row.category = normalized_category
            dirty = True
        if row.workflow_id in category_fixes and row.category != category_fixes[row.workflow_id]:
            row.category = category_fixes[row.workflow_id]
            dirty = True
        # Ensure outpainting workflows show up under the "图延伸类" group.
        if row.workflow_id in {"7597723984687267840", "7598587935331450880"} and row.category != "图延伸类":
            row.category = "图延伸类"
            dirty = True
        # Ensure "图裂变" workflows stay under their own category (for the sidebar).
        if row.workflow_id in {
            "7598841920114130944",
            "7598820684801769472",
            "7598844004557389824",
            "7598848725942796288",
        } and row.category != "图裂变":
            row.category = "图裂变"
            dirty = True
        if row.workflow_id == "7597723984687267840" and row.name != "扩图多模型版本":
            row.name = "扩图多模型版本"
            dirty = True
        if row.workflow_id == "7598587935331450880" and row.name != "ComfyUI 扩图 · comfyuo_tukuozhan":
            row.name = "ComfyUI 扩图 · comfyuo_tukuozhan"
            dirty = True
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
            schema = json.loads(json.dumps(row.output_schema or {}, ensure_ascii=False))
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
            schema = json.loads(json.dumps(row.output_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if not isinstance(fields, list):
                fields = []
            has_prompt = any(isinstance(f, dict) and f.get("name") == "prompt" for f in fields)
            if not has_prompt:
                fields.append({"name": "prompt", "type": "text", "description": "提示词反馈字符串"})
                schema["fields"] = fields
                row.output_schema = schema
                dirty = True
        if row.workflow_id in {
            "7598841920114130944",
            "7598820684801769472",
            "7601077530077954048",
            "7598848725942796288",
        }:
            # Normalize similarity labels to avoid "重绘比例" ambiguity.
            schema = json.loads(json.dumps(row.parameters_schema or {}, ensure_ascii=False))
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if isinstance(fields, list):
                changed = False
                for f in fields:
                    if not isinstance(f, dict):
                        continue
                    if f.get("name") == "similarity":
                        if f.get("label") != "相似度(%)":
                            f["label"] = "相似度(%)"
                            changed = True
                        if "相似的百分比" not in str(f.get("description") or ""):
                            f["description"] = "与原图保持相似的百分比（越高越接近原图）。兼容字段：bili。"
                            changed = True
                    if f.get("name") == "bili":
                        if f.get("label") != "相似度(%)":
                            f["label"] = "相似度(%)"
                            changed = True
                        if "相似的百分比" not in str(f.get("description") or ""):
                            f["description"] = "与原图保持相似的百分比（越高越接近原图）。"
                            changed = True
                if changed:
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
    if dirty:
        session.commit()
    return created
