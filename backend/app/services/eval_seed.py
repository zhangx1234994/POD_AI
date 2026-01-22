"""Seed default evaluation workflow versions.

This is intentionally lightweight and safe to call on request:
- It only inserts missing rows (by workflow_id).
- It never mutates existing rows (to avoid surprising changes).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.eval import EvalWorkflowVersion


DEFAULT_EVAL_WORKFLOW_VERSIONS: list[dict[str, Any]] = [
    # 通用类 / 提示词提取
    {
        "category": "general",
        "name": "提示词提取 · tishici_tiqu",
        "version": "v1",
        "workflow_id": "7597535455856295936",
        "status": "active",
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
        "category": "pattern_extract",
        "name": "花纹提取 · tiqu_comfyui",
        "version": "v1",
        "workflow_id": "7597530887256801280",
        "status": "active",
        "notes": "输出 output 为回调 task id（推荐用 PODI ability_task_id 方式轮询）。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
                {"name": "width", "label": "生成宽度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "height", "label": "生成高度", "type": "text", "required": False, "defaultValue": ""},
                {"name": "lora", "label": "LoRA", "type": "text", "required": False, "defaultValue": ""},
            ]
        },
        "output_schema": {"fields": [{"name": "output", "type": "text", "description": "回调 task id"}]},
    },
    # 图延伸类 / 扩图（多模型）
    {
        "category": "image_extend",
        "name": "扩图多模型版本",
        "version": "v1",
        "workflow_id": "7597723984687267840",
        "status": "active",
        "notes": "默认 moxing=1(Banana Pro)。输出 output 为图片地址。",
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
        "output_schema": {"fields": [{"name": "output", "type": "text", "description": "图片 URL"}]},
    },
    # 图略变类 / 多模型生图（Banana Pro / Flux2 / Doubao 4.5）
    {
        "category": "image_variation",
        "name": "多模型生图",
        "version": "v1",
        "workflow_id": "7597659369861283840",
        "status": "active",
        "notes": "moxing：1=Banana Pro，2=Flux2，3=Doubao 4.5。Flux2 更偏比例参数；其余更偏宽高参数。",
        "parameters_schema": {
            "fields": [
                {"name": "url", "label": "图片 URL", "type": "text", "required": True},
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
    # 图略变/通用类 / 四步急速生图（输出为回调 task id）
    {
        "category": "image_variation",
        "name": "四步急速生图",
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
        "output_schema": {"fields": [{"name": "output", "type": "text", "description": "回调 task id"}]},
    },
    # 图略变/通用类 / 八步急速生图（输出为回调 task id）
    {
        "category": "image_variation",
        "name": "八步急速生图",
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
        "output_schema": {"fields": [{"name": "output", "type": "text", "description": "回调 task id"}]},
    },
    # 通用类 / 8K 高清放大
    {
        "category": "general",
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
    return created
