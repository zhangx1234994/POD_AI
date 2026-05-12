"""Seed built-in business capability versions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.integration import BusinessCapability


def _field(
    name: str,
    label: str,
    *,
    field_type: str = "text",
    required: bool = False,
    default: Any = None,
    description: str | None = None,
    options: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name, "type": field_type, "label": label, "required": required}
    if default is not None:
        payload["default"] = default
    if description:
        payload["description"] = description
    if options:
        payload["options"] = options
    return payload


def _image_generation_output_schema() -> dict[str, Any]:
    return {
        "fields": [
            {"name": "runId", "type": "text", "label": "业务任务 ID Business Run ID"},
            {"name": "status", "type": "text", "label": "任务状态 Status"},
            {"name": "imageUrls", "type": "array", "label": "结果图片 Result Images"},
            {"name": "error", "type": "text", "label": "错误信息 Error"},
        ]
    }


GPT_IMAGE2_SIZE_OPTIONS: list[dict[str, str]] = [
    {"label": "自动匹配 auto", "value": "auto"},
    {"label": "1:1 方图 1024x1024", "value": "1024x1024"},
    {"label": "3:2 横图 1536x1024", "value": "1536x1024"},
    {"label": "2:3 竖图 1024x1536", "value": "1024x1536"},
    {"label": "1:1 方图 2048x2048（实验）", "value": "2048x2048"},
    {"label": "16:9 横图 2048x1152（实验）", "value": "2048x1152"},
    {"label": "16:9 横图 3840x2160（高成本）", "value": "3840x2160"},
    {"label": "9:16 竖图 2160x3840（高成本）", "value": "2160x3840"},
]


GPT_IMAGE2_PATTERN_FISSION_VL_PROMPT = """你是一个专业的装饰图案、印花纹样、装饰插画与主视觉结构分析助手。

你会看到一张用户上传的原图。你的任务不是生成图片，也不是给审美评价，而是把图片解析成后续图片裂变模型可执行的结构化视觉卡。最终必须只输出一个 JSON 对象，不要输出 markdown、代码块、解释、前言或结尾。

请稳定识别：图片类型、风格家族、构图、主要元素、层级关系、画风与材质、色彩关系、必须保留的系列感、裂变时应该变化的元素范围、禁止漂移方向。

输出 JSON schema：
{
  "image_type": "",
  "pattern_type": "",
  "style_family": "",
  "composition": {
    "layout": "",
    "symmetry": "",
    "border_logic": "",
    "density": "",
    "visual_hierarchy": ""
  },
  "motifs": {
    "primary": [],
    "secondary": [],
    "fillers": [],
    "border": [],
    "background": []
  },
  "material_style": {
    "rendering": "",
    "linework": "",
    "texture": "",
    "aging_or_surface": ""
  },
  "color_palette": {
    "main_colors": [],
    "accent_colors": [],
    "color_relationship": ""
  },
  "preserve_locks": [],
  "change_targets": [],
  "forbidden_drifts": [],
  "fission_brief": ""
}

关键要求：preserve_locks 必须描述不能破坏的结构、风格、画风、材质和色彩关系；change_targets 必须覆盖主要元素，不能只写改变颜色；forbidden_drifts 必须包含不要只换色、不要变成写实场景、不要现代矢量化、不要减少元素、不要破坏构图；fission_brief 必须是一段可以直接拼进图像编辑 prompt 的中文裂变任务说明；如果图片是平面图案，必须明确它不是场景图。"""


@dataclass(frozen=True)
class BusinessCapabilitySeed:
    id: str
    business_key: str
    version: str
    display_name: str
    description: str
    status: str
    is_default: bool
    release_time: datetime
    recipe: dict[str, Any]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    metadata: dict[str, Any]


DEFAULT_BUSINESS_CAPABILITY_SEEDS: list[BusinessCapabilitySeed] = [
    BusinessCapabilitySeed(
        id="biz_pattern_extract_v1_yinhua_tiqu",
        business_key="pattern_extract",
        version="v1",
        display_name="花纹提取 · 印花提取稳定版",
        description="面向业务侧的花纹提取稳定入口，底层使用当前印花提取 ComfyUI 工作流。",
        status="active",
        is_default=True,
        release_time=datetime(2026, 4, 24, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "comfyui_yinhua_tiqu",
            "steps": [
                {
                    "id": "pattern_extract",
                    "type": "ability_task",
                    "abilityId": "comfyui_yinhua_tiqu",
                }
            ],
            "vlAssist": {"enabled": False, "abilityId": "vl_analyze_image"},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True, description="业务侧只需要传入可访问图片地址。"),
                _field("prompt", "提取要求 Prompt", field_type="textarea", required=False),
                _field("negative_prompt", "不要出现的内容 Negative Prompt", field_type="textarea", required=False),
                _field("width", "输出宽度 Width", field_type="number", default=1800),
                _field("height", "输出高度 Height", field_type="number", default=1800),
                _field("batch", "生成张数 Batch", field_type="number", default=1),
                _field("lora", "LoRA 方案 LoRA", field_type="text", required=False),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "pattern_extract",
            "entry": "business-api",
            "coze_strategy": "Coze 只调用该业务入口，不再手搓底层节点。",
            "seed_version": 1,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_pattern_extract_rollback_lora_8step",
        business_key="pattern_extract",
        version="rollback-lora-8step-v1",
        display_name="花纹提取 · 8步加速备选版",
        description="花纹提取业务入口的备选版本，底层使用 8 步加速可换 LoRA 工作流；用于稳定版异常时快速切回。",
        status="active",
        is_default=False,
        release_time=datetime(2026, 4, 16, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "comfyui_yinhua_tiqu_lora_8step",
            "steps": [
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "8步加速可换 LoRA",
                    "abilityId": "comfyui_yinhua_tiqu_lora_8step",
                }
            ],
            "vlAssist": {"enabled": False, "abilityId": "vl_analyze_image"},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True, description="业务侧只需要传入可访问图片地址。"),
                _field("prompt", "提取要求 Prompt", field_type="textarea", required=False),
                _field("negative_prompt", "不要出现的内容 Negative Prompt", field_type="textarea", required=False),
                _field("batch", "生成张数 Batch", field_type="number", default=1),
                _field("lora", "LoRA 方案 LoRA", field_type="text", required=False),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "pattern_extract",
            "entry": "business-api",
            "role": "rollback_safety",
            "rollbackSafety": True,
            "rollbackReason": "默认花纹提取版本异常时，保留可直接切回的 8 步加速执行链路。",
            "coze_strategy": "Coze 仍调用同一个业务入口，回滚只在中台切默认版本。",
            "seed_version": 1,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_fission_v1_flux_strong_hq_softstyle",
        business_key="fission",
        version="v1",
        display_name="图裂变 · 高质量多元素花纹",
        description="面向业务侧的图裂变稳定入口，底层使用当前 05 FLUX Strong HQ SoftStyle ComfyUI 工作流。",
        status="active",
        is_default=True,
        release_time=datetime(2026, 4, 24, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "comfyui_flux_strong_hq_softstyle_fission",
            "steps": [
                {
                    "id": "fission",
                    "type": "ability_task",
                    "abilityId": "comfyui_flux_strong_hq_softstyle_fission",
                }
            ],
            "vlAssist": {"enabled": False, "abilityId": "vl_analyze_image"},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True, description="业务侧只需要传入可访问图片地址。"),
                _field("prompt", "裂变提示词 Prompt", field_type="textarea", required=False),
                _field(
                    "bili",
                    "重绘幅度 Repaint Strength",
                    field_type="number",
                    default=90,
                    description="0-100；值越大重绘越强、变化越明显。中台会按约定比例换算为 ComfyUI denoise。",
                ),
                _field("width", "输出宽度 Width", field_type="number", default=1024),
                _field("height", "输出高度 Height", field_type="number", default=1024),
                _field("batch_size", "生成张数 Batch Size", field_type="number", default=1),
                _field("image_desc", "图像补充描述 Image Description", field_type="textarea", required=False),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "image_fission",
            "entry": "business-api",
            "coze_strategy": "Coze 只调用该业务入口，不再手搓底层节点。",
            "seed_version": 3,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_fission_v2_openai_gpt_image2_vl",
        business_key="fission",
        version="gpt-image2-vl-v1",
        display_name="图裂变 · GPT Image 2 + VL 控制版",
        description="AI 团队 2026-05-12 交付的商业模型裂变方案：先用 VL 生成图案结构卡，再编译提示词并调用 GPT Image 2 图片编辑能力。",
        status="active",
        is_default=False,
        release_time=datetime(2026, 5, 12, 0, 0, 0),
        recipe={
            "mode": "vl_then_primary",
            "primaryAbilityId": "openai_gpt_image_2_edit",
            "steps": [
                {
                    "id": "vl_card",
                    "type": "vl_analyze",
                    "role": "preprocess",
                    "displayName": "VL 图案结构卡",
                    "abilityId": "vl_analyze_image",
                    "config": {
                        "defaultInputs": {
                            "provider": "volcengine_vl",
                            "prompt": GPT_IMAGE2_PATTERN_FISSION_VL_PROMPT,
                        }
                    },
                },
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "GPT Image 2 图片编辑裂变",
                    "abilityId": "openai_gpt_image_2_edit",
                },
            ],
            "vlAssist": {
                "enabled": True,
                "abilityId": "vl_analyze_image",
                "waitForResult": True,
                "applyToPrimary": {
                    "compiler": "pattern_fission_prompt_template_v21",
                    "overwrite": True,
                },
            },
            "promptCompiler": {
                "id": "pattern_fission_prompt_template_v21",
                "routeId": "OPENAI_GPT_IMAGE2_PATTERN_V21",
            },
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True, description="业务侧传入可访问图片地址；上传图片会先落 OSS。"),
                _field("prompt", "额外要求 Extra Prompt", field_type="textarea", required=False, description="可写业务侧额外要求，系统会拼入最终提示词。"),
                _field(
                    "variation_strength",
                    "裂变幅度 Variation Strength",
                    field_type="select",
                    default="high",
                    description="控制变化幅度；high 更明显，medium 更稳，low 更保守。",
                    options=[
                        {"label": "明显变化 high", "value": "high"},
                        {"label": "中等变化 medium", "value": "medium"},
                        {"label": "保守变化 low", "value": "low"},
                    ],
                ),
                _field(
                    "quality",
                    "质量档位 Quality",
                    field_type="select",
                    default="preview",
                    description="preview=低成本预览，production=正式质量，premium=高质量高成本。",
                    options=[
                        {"label": "预览 preview", "value": "preview"},
                        {"label": "正式 production", "value": "production"},
                        {"label": "高质 premium", "value": "premium"},
                    ],
                ),
                _field("count", "生成张数 Count", field_type="number", default=1, description="建议 1-3；数量越多成本越高。"),
                _field("preserve_layout", "保留版式 Preserve Layout", field_type="switch", default=True),
                _field("preserve_border", "边框策略 Preserve Border", field_type="text", default="auto", description="auto / true / false。"),
                _field("preserve_count_density", "保留数量和密度 Preserve Count Density", field_type="switch", default=True),
                _field("style_shift", "风格迁移 Style Shift", field_type="text", default="standard", description="standard / conservative / creative。"),
                _field(
                    "size",
                    "比例尺寸 Size",
                    field_type="select",
                    default="auto",
                    description="GPT Image 2 输出尺寸预设；高分辨率档位成本和耗时更高。",
                    options=GPT_IMAGE2_SIZE_OPTIONS,
                ),
                _field("output_format", "输出格式 Output Format", field_type="text", default="png"),
                _field("maskUrl", "蒙版 URL Mask URL", field_type="text", required=False, description="可选；需要指定局部编辑时传入。"),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "image_fission",
            "entry": "business-api",
            "role": "gray_candidate",
            "badge": "新版",
            "isNewVersion": True,
            "provider": "openai",
            "model": "gpt-image-2",
            "route_id": "OPENAI_GPT_IMAGE2_PATTERN_V21",
            "prompt_template_id": "pattern_fission_prompt_template_v21",
            "quality_map": {"preview": "low", "production": "medium", "premium": "high"},
            "coze_strategy": "Coze 只调用图裂变业务入口；中台内部完成 VL 分析、提示词编译和 GPT Image 2 调用。",
            "seed_version": 3,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_fission_v3_comfyui_vl_control_card",
        business_key="fission",
        version="comfyui-vl-control-v1",
        display_name="图裂变 · ComfyUI VL 控制卡版",
        description="AI 团队 2026-05-12 交付的 ComfyUI 裂变接口：先用统一 VL 组件生成控制卡，再调用 05 FLUX Strong HQ SoftStyle 裂变工作流。",
        status="active",
        is_default=False,
        release_time=datetime(2026, 5, 12, 0, 0, 0),
        recipe={
            "mode": "vl_then_primary",
            "primaryAbilityId": "comfyui_flux_strong_hq_softstyle_fission_control_v1",
            "steps": [
                {
                    "id": "vl_card",
                    "type": "vl_analyze",
                    "role": "preprocess",
                    "displayName": "VL 图裂变控制卡",
                    "abilityId": "vl_fission_control_card",
                    "config": {
                        "defaultInputs": {
                            "provider": "volcengine_vl",
                        }
                    },
                },
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "ComfyUI VL 控制卡裂变",
                    "abilityId": "comfyui_flux_strong_hq_softstyle_fission_control_v1",
                },
            ],
            "vlAssist": {
                "enabled": True,
                "abilityId": "vl_fission_control_card",
                "waitForResult": True,
                "applyToPrimary": {
                    "compiler": "comfyui_fission_control_card_v1",
                    "overwrite": True,
                },
            },
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True, description="业务侧传入可访问图片地址；上传图片会先落 OSS。"),
                _field("bili", "裂变幅度 Variation Percent", field_type="text", default="50%", description="0%=更保守，100%=变化更大；默认 50%。"),
                _field("width", "输出宽度 Width", field_type="number", default=2000),
                _field("height", "输出高度 Height", field_type="number", default=2000),
                _field("profile", "裂变配置 Profile", field_type="text", default="pattern_default_v1"),
                _field("prompt", "额外要求 Extra Prompt", field_type="textarea", required=False, description="可选；会作为补充要求保留在调用日志中。"),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "image_fission",
            "entry": "business-api",
            "role": "gray_candidate",
            "badge": "新版",
            "isNewVersion": True,
            "provider": "comfyui",
            "interface_pack": "11_2026-05-12_comfyui_fission_interface_pack_v1",
            "vl_component_ability_id": "vl_fission_control_card",
            "eval_component_ability_id": "vl_fission_generated_image_evaluate",
            "coze_strategy": "Coze 仍调用图裂变业务入口；中台内部完成 VL 控制卡生成和 ComfyUI 裂变调用，生成图评估由业务方按需单独调用。",
            "seed_version": 2,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_fission_rollback_e7_flux2_liebian",
        business_key="fission",
        version="rollback-e7-v1",
        display_name="图裂变 · E7 保底版",
        description="图裂变业务入口的保底版本，底层使用 E7 + FLUX2 裂变重绘工作流；用于默认版本异常时快速回滚，不作为日常默认版本。",
        status="active",
        is_default=False,
        release_time=datetime(2026, 3, 28, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "comfyui_e7_flux2_liebian",
            "steps": [
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "E7 + FLUX2 裂变重绘",
                    "abilityId": "comfyui_e7_flux2_liebian",
                }
            ],
            "vlAssist": {"enabled": False, "abilityId": "vl_analyze_image"},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True, description="业务侧只需要传入可访问图片地址。"),
                _field("prompt", "裂变提示词 Prompt", field_type="textarea", required=False),
                _field(
                    "bili",
                    "重绘幅度 Repaint Strength",
                    field_type="number",
                    default=90,
                    description="0-100；值越大重绘越强、变化越明显。中台会按约定比例换算为 ComfyUI denoise。",
                ),
                _field("width", "输出宽度 Width", field_type="number", required=False),
                _field("height", "输出高度 Height", field_type="number", required=False),
                _field("batch_size", "生成张数 Batch Size", field_type="number", default=1),
                _field("steps", "采样步数 Steps", field_type="number", default=8),
                _field("cfg", "提示词强度 CFG", field_type="number", default=1.0),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "image_fission",
            "entry": "business-api",
            "role": "rollback_safety",
            "rollbackSafety": True,
            "rollbackReason": "默认高质量裂变版本异常时，保留可直接切回的旧稳定执行链路。",
            "coze_strategy": "Coze 仍调用同一个业务入口，回滚只在中台切默认版本。",
            "seed_version": 3,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_outpaint_v1_flux2_klein_9b",
        business_key="outpaint",
        version="v1",
        display_name="扩图 · FLUX2-Klein 9B",
        description="面向业务侧的扩图稳定入口，底层使用当前 FLUX2-Klein 9B 扩图 ComfyUI 工作流。",
        status="active",
        is_default=True,
        release_time=datetime(2026, 4, 24, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "comfyui_flux2_klein_9b_outpaint",
            "steps": [
                {
                    "id": "outpaint",
                    "type": "ability_task",
                    "abilityId": "comfyui_flux2_klein_9b_outpaint",
                }
            ],
            "vlAssist": {"enabled": False, "abilityId": "vl_analyze_image"},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True),
                _field("prompt", "扩图说明 Prompt", field_type="textarea", required=False),
                _field("expand_left", "左侧扩展 Expand Left", field_type="number", default=408),
                _field("expand_right", "右侧扩展 Expand Right", field_type="number", default=408),
                _field("expand_top", "上侧扩展 Expand Top", field_type="number", default=0),
                _field("expand_bottom", "下侧扩展 Expand Bottom", field_type="number", default=0),
                _field("width", "输出宽度 Width", field_type="number", required=False),
                _field("height", "输出高度 Height", field_type="number", required=False),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "outpaint",
            "entry": "business-api",
            "coze_strategy": "Coze 只调用该业务入口，不再手搓底层节点。",
            "seed_version": 1,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_outpaint_rollback_huawen_kuotu",
        business_key="outpaint",
        version="rollback-huawen-v1",
        display_name="扩图 · 花纹扩图保底版",
        description="扩图业务入口的保底版本，底层使用旧花纹扩图工作流；用于 FLUX2-Klein 扩图异常时快速回滚，不作为日常默认版本。",
        status="active",
        is_default=False,
        release_time=datetime(2026, 3, 28, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "comfyui_huawen_kuotu",
            "steps": [
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "花纹扩图",
                    "abilityId": "comfyui_huawen_kuotu",
                }
            ],
            "vlAssist": {"enabled": False, "abilityId": "vl_analyze_image"},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True),
                _field("prompt", "扩图说明 Prompt", field_type="textarea", required=False),
                _field("expand_left", "左侧扩展 Expand Left", field_type="number", default=200),
                _field("expand_right", "右侧扩展 Expand Right", field_type="number", default=200),
                _field("expand_top", "上侧扩展 Expand Top", field_type="number", default=0),
                _field("expand_bottom", "下侧扩展 Expand Bottom", field_type="number", default=0),
                _field("width", "输出宽度 Width", field_type="number", required=False),
                _field("height", "输出高度 Height", field_type="number", required=False),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "outpaint",
            "entry": "business-api",
            "role": "rollback_safety",
            "rollbackSafety": True,
            "rollbackReason": "默认 FLUX2-Klein 扩图版本异常时，保留可直接切回的旧稳定执行链路。",
            "coze_strategy": "Coze 仍调用同一个业务入口，回滚只在中台切默认版本。",
            "seed_version": 1,
        },
    ),
]


def ensure_default_business_capabilities(session: Session) -> bool:
    changed = False
    for seed in DEFAULT_BUSINESS_CAPABILITY_SEEDS:
        existing = session.get(BusinessCapability, seed.id)
        if existing:
            next_metadata = {**(seed.metadata or {}), **(existing.extra_metadata or {})}
            if int((seed.metadata or {}).get("seed_version") or 0) > int((existing.extra_metadata or {}).get("seed_version") or 0):
                existing.display_name = seed.display_name
                existing.description = seed.description
                existing.recipe = seed.recipe
                existing.input_schema = seed.input_schema
                existing.output_schema = seed.output_schema
                next_metadata = seed.metadata
                changed = True
            if existing.extra_metadata != next_metadata:
                existing.extra_metadata = next_metadata
                changed = True
            if existing.release_time is None:
                existing.release_time = seed.release_time
                changed = True
            continue

        active_default_exists = bool(
            session.execute(
                select(BusinessCapability.id)
                .where(
                    BusinessCapability.business_key == seed.business_key,
                    BusinessCapability.status == "active",
                    BusinessCapability.is_default.is_(True),
                )
                .limit(1)
            ).scalar_one_or_none()
        )
        should_be_default = seed.is_default and not active_default_exists
        if should_be_default:
            session.execute(
                update(BusinessCapability)
                .where(BusinessCapability.business_key == seed.business_key)
                .values(is_default=False)
            )
        session.add(
            BusinessCapability(
                id=seed.id,
                business_key=seed.business_key,
                version=seed.version,
                display_name=seed.display_name,
                description=seed.description,
                status=seed.status,
                is_default=should_be_default,
                release_time=seed.release_time,
                recipe=seed.recipe,
                input_schema=seed.input_schema,
                output_schema=seed.output_schema,
                extra_metadata=seed.metadata,
            )
        )
        changed = True

    # Enforce one active default per business key without overwriting an admin's chosen default.
    for seed in DEFAULT_BUSINESS_CAPABILITY_SEEDS:
        if not seed.is_default:
            continue
        rows = (
            session.execute(
                select(BusinessCapability)
                .where(BusinessCapability.business_key == seed.business_key)
                .order_by(BusinessCapability.created_at.asc())
            )
            .scalars()
            .all()
        )
        active_defaults = [row for row in rows if row.status == "active" and row.is_default]
        desired_default_id = active_defaults[0].id if active_defaults else seed.id
        for row in rows:
            desired = row.status == "active" and row.id == desired_default_id
            if row.is_default != desired:
                row.is_default = desired
                changed = True

    if changed:
        session.commit()
    return changed
