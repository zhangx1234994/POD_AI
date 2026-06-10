"""Seed built-in business capability versions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.constants.abilities import (
    FISSION_CONTROL_CARD_WITH_ASPECT_RECOMPOSE_VL_PROMPT,
    TEXT2IMG_TEXT_ALLOWED_NEGATIVE_DEFAULT,
)
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


def _version_line(key: str, label: str, detail: str, priority: int) -> dict[str, Any]:
    return {"key": key, "label": label, "detail": detail, "priority": priority}


def _version_lineage(
    *,
    decision: str = "version_upgrade",
    decision_note: str,
    change_summary: str,
    parent_version_id: str | None = None,
    supersedes_version_id: str | None = None,
    breaking_change: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "decision": decision,
        "decisionNote": decision_note,
        "changeSummary": change_summary,
        "breakingChange": breaking_change,
    }
    if parent_version_id:
        payload["parentVersionId"] = parent_version_id
    if supersedes_version_id:
        payload["supersedesVersionId"] = supersedes_version_id
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


def _fission_evaluate_output_schema() -> dict[str, Any]:
    return {
        "fields": [
            {"name": "runId", "type": "text", "label": "业务任务 ID Business Run ID"},
            {"name": "status", "type": "text", "label": "任务状态 Status"},
            {"name": "decision", "type": "text", "label": "评估结论 Decision"},
            {"name": "score", "type": "number", "label": "质量分 Score"},
            {"name": "problemTags", "type": "array", "label": "问题标签 Problem Tags"},
            {"name": "reason", "type": "text", "label": "评估原因 Reason"},
            {"name": "nextAction", "type": "text", "label": "建议动作 Next Action"},
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

IMAGE_EDIT_SKILL_OPTIONS: list[dict[str, str]] = [
    {"label": "局部修改", "value": "local_modify"},
    {"label": "参考图替换", "value": "reference_element_transfer"},
    {"label": "删除修补", "value": "remove_inpaint"},
    {"label": "补色校正", "value": "color_reference_correction"},
    {"label": "扩展画布", "value": "canvas_outpaint"},
]

IMAGE_EDIT_QUALITY_OPTIONS: list[dict[str, str]] = [
    {"label": "自动 auto", "value": "auto"},
    {"label": "快速预览 preview", "value": "preview"},
    {"label": "正式候选 production", "value": "production"},
    {"label": "高质量 premium", "value": "premium"},
]

IMAGE_EDIT_OUTPUT_FORMAT_OPTIONS: list[dict[str, str]] = [
    {"label": "PNG", "value": "png"},
    {"label": "JPEG", "value": "jpeg"},
    {"label": "WebP", "value": "webp"},
]

PRODUCT_DESIGN_PRODUCT_TYPE_OPTIONS: list[dict[str, str]] = [
    {"label": "服装/面料", "value": "apparel"},
    {"label": "家纺/软装", "value": "home_textile"},
    {"label": "箱包", "value": "bag"},
    {"label": "鞋履", "value": "shoe"},
    {"label": "文具/小商品", "value": "stationery"},
    {"label": "包装", "value": "packaging"},
    {"label": "通用产品", "value": "generic"},
]

PRODUCT_DESIGN_SCENE_OPTIONS: list[dict[str, str]] = [
    {"label": "棚拍产品图", "value": "studio_product"},
    {"label": "平铺产品图", "value": "flat_lay"},
    {"label": "电商主图", "value": "ecommerce"},
    {"label": "生活方式场景", "value": "lifestyle"},
    {"label": "印花/图案上产品 mockup", "value": "print_mockup"},
    {"label": "通用场景", "value": "generic"},
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


GPT_IMAGE2_PATTERN_FISSION_VL_PROMPT_V2 = """你是一个专业的装饰图案、印花纹样、装饰插画与主视觉结构分析助手。

你会看到一张用户上传的原图。你的任务只做客观识别，不做创意改法，不生成图片，不评价审美。最终必须只输出一个 JSON 对象，不要输出 markdown、代码块、解释、前言或结尾。

输出 JSON schema：
{
  "image_type": "flat_pattern",
  "pattern_type": "",
  "style_family": "",
  "composition": {
    "layout": "",
    "symmetry": "",
    "density": "",
    "border_logic": ""
  },
  "motifs": {
    "primary": [],
    "secondary": [],
    "fillers": [],
    "border": []
  },
  "color_palette": {
    "background": "",
    "primary_colors": [],
    "color_relationship": ""
  },
  "material_style": {
    "rendering": "",
    "linework": "",
    "texture": ""
  },
  "risk_flags": {
    "has_text_or_logo": false,
    "has_border": false,
    "is_seamless_claim_uncertain": true
  }
}

关键要求：
- VL 只负责识别事实，不允许输出 fission_brief、change_targets、creative_plan、replacement_plan、rewrite_prompt。
- pattern_type 必须尽量具体，例如满版花卉、散点水果、四方连续、复杂边框挂毯、几何抽象连续图案。
- 如果识别到文字、logo、标签或伪文字，risk_flags.has_text_or_logo 必须为 true。
- 如果图片是平面图案，必须明确它不是摄影场景、商品图或空间渲染。
- 不要把颜色词误判为主体类别，例如橘色花卉不能判成橘子水果。
"""


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
            "versionLine": _version_line(
                "comfyui",
                "ComfyUI 自研线",
                "花纹提取稳定入口，底层由自研 ComfyUI 工作流执行。",
                20,
            ),
            "versionLineage": _version_lineage(
                decision_note="花纹提取初始生产版本，业务入口保持稳定。",
                change_summary="建立花纹提取业务入口，作为后续裂变和扩图的上游素材能力。",
            ),
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
            "versionLine": _version_line(
                "rollback",
                "保底回滚",
                "只在主线异常时切回，不作为新功能入口。",
                80,
            ),
            "versionLineage": _version_lineage(
                decision="rollback",
                parent_version_id="biz_pattern_extract_v1_yinhua_tiqu",
                decision_note="保底回滚版本，只在默认花纹提取异常时切回，不作为新业务入口。",
                change_summary="保留 8 步加速 LoRA 链路作为花纹提取回滚方案。",
            ),
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
            "versionLine": _version_line(
                "comfyui",
                "ComfyUI 自研线",
                "图裂变生产主线，底层由自研 ComfyUI 工作流执行。",
                20,
            ),
            "versionLineage": _version_lineage(
                decision_note="图裂变初始生产版本，业务入口保持稳定。",
                change_summary="建立图裂变业务入口，底层使用高质量多元素花纹 ComfyUI 工作流。",
            ),
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
                _field(
                    "size",
                    "比例尺寸 Size",
                    field_type="select",
                    default="auto",
                    description="默认 auto，最终结果按原图尺寸回填；选择固定预设才改变画布。",
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
            "versionLine": _version_line(
                "commercial-model",
                "商业模型线",
                "同一图裂变入口下的商业模型验证路线。",
                30,
            ),
            "versionLineage": _version_lineage(
                parent_version_id="biz_fission_v1_flux_strong_hq_softstyle",
                decision_note="入口不变，只替换底层模型和提示词编译链路。",
                change_summary="新增 GPT Image 2 + VL 控制的图裂变验证路线。",
            ),
            "route_id": "OPENAI_GPT_IMAGE2_PATTERN_V21",
            "prompt_template_id": "pattern_fission_prompt_template_v21",
            "quality_map": {"preview": "low", "production": "medium", "premium": "high"},
            "coze_strategy": "Coze 只调用图裂变业务入口；中台内部完成 VL 分析、提示词编译和 GPT Image 2 调用。",
            "seed_version": 3,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_fission_v5_openai_gpt_image2_controlled",
        business_key="fission",
        version="gpt-image2-vl-v2",
        display_name="图裂变 · GPT Image 2 受控版",
        description="AI 团队 2026-05-13 交付的 GPT Image 2 受控裂变方案：VL 只输出客观识别卡，中台负责图案类型路由、定量提示词编译和质量门禁审计。",
        status="active",
        is_default=False,
        release_time=datetime(2026, 5, 13, 0, 0, 0),
        recipe={
            "mode": "vl_then_primary",
            "primaryAbilityId": "openai_gpt_image_2_edit",
            "steps": [
                {
                    "id": "vl_card",
                    "type": "vl_analyze",
                    "role": "preprocess",
                    "displayName": "VL 图案识别卡",
                    "abilityId": "vl_analyze_image",
                    "config": {
                        "defaultInputs": {
                            "provider": "volcengine_vl",
                            "prompt": GPT_IMAGE2_PATTERN_FISSION_VL_PROMPT_V2,
                        }
                    },
                },
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "GPT Image 2 受控裂变",
                    "abilityId": "openai_gpt_image_2_edit",
                },
            ],
            "vlAssist": {
                "enabled": True,
                "abilityId": "vl_analyze_image",
                "waitForResult": True,
                "applyToPrimary": {
                    "compiler": "pattern_fission_controlled_v2",
                    "overwrite": True,
                },
            },
            "promptCompiler": {
                "id": "pattern_fission_controlled_v2",
                "routeId": "OPENAI_GPT_IMAGE2_PATTERN_CONTROLLED_V2",
            },
            "qualityGate": {
                "enabled": True,
                "passScore": 78,
                "mode": "audit_metadata_first",
            },
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True, description="业务侧传入可访问图片地址；上传图片会先落 OSS。"),
                _field(
                    "prompt",
                    "额外要求 Extra Prompt",
                    field_type="textarea",
                    required=False,
                    description="可选补充要求。不填也会按 VL 识别卡和默认受控提示词运行。",
                ),
                _field(
                    "variation_strength",
                    "裂变幅度 Variation Strength",
                    field_type="select",
                    default="same_series",
                    description="默认同系列裂变；保守更像原图，强变化只在需要更大差异时使用。",
                    options=[
                        {"label": "同系列裂变", "value": "same_series"},
                        {"label": "保守变化", "value": "conservative"},
                        {"label": "强变化同系列", "value": "creative_same_series"},
                    ],
                ),
                _field(
                    "quality",
                    "质量档位 Quality",
                    field_type="select",
                    default="preview",
                    description="preview=低成本预览，candidate=候选抽样，premium=高质量高成本。",
                    options=[
                        {"label": "预览 preview", "value": "preview"},
                        {"label": "候选 candidate", "value": "candidate"},
                        {"label": "高质 premium", "value": "premium"},
                    ],
                ),
                _field(
                    "size",
                    "比例尺寸 Size",
                    field_type="select",
                    default="auto",
                    description="默认 auto，最终结果按原图尺寸回填；选择固定预设才改变画布。",
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
            "versionLine": _version_line(
                "commercial-model",
                "商业模型线",
                "同一图裂变入口下的商业模型验证路线。",
                30,
            ),
            "versionLineage": _version_lineage(
                parent_version_id="biz_fission_v2_openai_gpt_image2_vl",
                supersedes_version_id="biz_fission_v2_openai_gpt_image2_vl",
                decision_note="入口不变，修正 GPT Image 2 裂变控制方式和提示词编译链路。",
                change_summary="将 GPT Image 2 + VL 控制版升级为受控提示词和质量门禁版本。",
            ),
            "route_id": "OPENAI_GPT_IMAGE2_PATTERN_CONTROLLED_V2",
            "route_version": "pattern_fission_controlled_v2.0",
            "prompt_template_id": "pattern_fission_controlled_v2",
            "interface_pack": "gpt_image2_vl_pattern_fission_controlled_dev_pack_20260513_v2",
            "quality_map": {"preview": "low", "candidate": "medium", "premium": "high"},
            "coze_strategy": "Coze 只调用图裂变业务入口；中台内部完成 VL 识别、图案路由、提示词编译和 GPT Image 2 调用。",
            "seed_version": 1,
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
            "versionLine": _version_line(
                "comfyui",
                "ComfyUI 自研线",
                "同一图裂变入口下的自研 ComfyUI 验证路线。",
                20,
            ),
            "versionLineage": _version_lineage(
                parent_version_id="biz_fission_v1_flux_strong_hq_softstyle",
                decision_note="入口不变，增加 VL 控制卡作为前置步骤。",
                change_summary="新增 ComfyUI VL 控制卡裂变路线。",
            ),
            "vl_component_ability_id": "vl_fission_control_card",
            "eval_component_ability_id": "vl_fission_generated_image_evaluate",
            "coze_strategy": "Coze 仍调用图裂变业务入口；中台内部完成 VL 控制卡生成和 ComfyUI 裂变调用，生成图评估由业务方按需单独调用。",
            "seed_version": 2,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_fission_v4_comfyui_vl_colorlock",
        business_key="fission",
        version="comfyui-vl-control-v2",
        display_name="图裂变 · ComfyUI 颜色锁定版",
        description="AI 团队 2026-05-14 修补的 ComfyUI 裂变版本：先用统一 VL 组件识别图案风险类型，再调用 05 FLUX Strong HQ SoftStyle 做智能路由裂变。",
        status="active",
        is_default=False,
        release_time=datetime(2026, 5, 13, 0, 0, 0),
        recipe={
            "mode": "vl_then_primary",
            "primaryAbilityId": "comfyui_flux_strong_hq_softstyle_fission_colorlock_v2",
            "steps": [
                {
                    "id": "vl_card",
                    "type": "vl_analyze",
                    "role": "preprocess",
                    "displayName": "VL 图裂变颜色控制卡",
                    "abilityId": "vl_fission_control_card",
                    "config": {
                        "defaultInputs": {
                            "provider": "volcengine_vl",
                            "prompt": FISSION_CONTROL_CARD_WITH_ASPECT_RECOMPOSE_VL_PROMPT,
                        }
                    },
                },
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "ComfyUI 颜色锁定裂变",
                    "abilityId": "comfyui_flux_strong_hq_softstyle_fission_colorlock_v2",
                },
            ],
            "vlAssist": {
                "enabled": True,
                "abilityId": "vl_fission_control_card",
                "waitForResult": True,
                "applyToPrimary": {
                    "compiler": "comfyui_fission_control_card_v2",
                    "overwrite": True,
                },
            },
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True, description="业务侧传入可访问图片地址；上传图片会先落 OSS。"),
                _field("bili", "重绘幅度 Variation Percent", field_type="text", default="80%", description="控制图案变化大小；建议低 30%、中 60%、高 80%、极高 100%+。后端会结合 VL 图案类型路由实际 denoise。"),
                _field("width", "输出宽度 Width", field_type="number", required=False, description="不填则按原图宽度处理；手动填写时保留目标画布，底层按 16 像素安全倍数归一。"),
                _field("height", "输出高度 Height", field_type="number", required=False, description="不填则按原图高度处理；手动填写时保留目标画布，底层按 16 像素安全倍数归一。"),
                _field(
                    "profile",
                    "裂变路由配置 Fission Routing Profile",
                    field_type="select",
                    default="pattern_risk_routed_v4",
                    options=[
                        {"label": "智能风险路由（推荐）", "value": "pattern_risk_routed_v4"},
                        {"label": "默认颜色锁定（兼容）", "value": "pattern_color_lock_v2"},
                        {"label": "严格颜色锁定（更像原图）", "value": "pattern_color_lock_strict_v2"},
                    ],
                ),
                _field("reference_lock", "原图结构保留度 Reference Lock", field_type="number", default=0.42, description="建议 0.34-0.50，不做硬限制。越高越像原图，裂变感更弱。"),
                _field("color_lock", "颜色锁定强度 Color Lock", field_type="number", default=0.90, description="建议 0.75-1.00，不做硬限制。越高越不容易偏色。"),
                _field("prompt", "额外要求 Extra Prompt", field_type="textarea", required=False, description="可选；不要写放开配色或重新设计色彩的要求。"),
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
            "interface_pack": "15_2026-05-14_comfyui_fission_object_variation_interface_pack_v4",
            "versionLine": _version_line(
                "comfyui",
                "ComfyUI 自研线",
                "同一图裂变入口下的自研 ComfyUI 验证路线。",
                20,
            ),
            "versionLineage": _version_lineage(
                parent_version_id="biz_fission_v3_comfyui_vl_control_card",
                supersedes_version_id="biz_fission_v3_comfyui_vl_control_card",
                decision_note="入口不变，升级为颜色锁定和智能风险路由版本。",
                change_summary="将 ComfyUI VL 控制卡裂变升级为颜色锁定版。",
            ),
            "vl_component_ability_id": "vl_fission_control_card",
            "eval_component_ability_id": "vl_fission_generated_image_evaluate",
            "coze_strategy": "Coze 仍调用图裂变业务入口；中台内部完成 VL 风险类型识别和 ComfyUI 智能路由裂变调用。",
            "aspect_recompose_branch": "当业务接口传入的输出比例与原图差异较大，且 VL 判断为满版密集小元素图案时，后端生成目标比例引导图后再调用同一 ComfyUI 工作流；若 VL 不允许比例重构，则保留用户目标画布直接出图，不再静默回退到原图尺寸。",
            "seed_version": 4,
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
            "versionLine": _version_line(
                "rollback",
                "保底回滚",
                "只在主线异常时切回，不作为新功能入口。",
                80,
            ),
            "versionLineage": _version_lineage(
                decision="rollback",
                parent_version_id="biz_fission_v1_flux_strong_hq_softstyle",
                decision_note="保底回滚版本，只在图裂变主线异常时切回，不作为新业务入口。",
                change_summary="保留 E7 + FLUX2 旧稳定链路作为图裂变回滚方案。",
            ),
            "coze_strategy": "Coze 仍调用同一个业务入口，回滚只在中台切默认版本。",
            "seed_version": 3,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_text_fission_qwen2512_text2img_user_editable_v1",
        business_key="text_fission",
        version="qwen2512-text2img-v1",
        display_name="文字强化裂变（文生图）",
        description="先用 VL 从原图生成可编辑提示词草稿，用户确认或修改后再调用 Qwen2512 文生图工作流，适合需要准确文字内容的裂变场景。",
        status="active",
        is_default=True,
        release_time=datetime(2026, 5, 19, 0, 0, 0),
        recipe={
            "mode": "user_editable_prompt_then_primary",
            "primaryAbilityId": "comfyui_qwen2512_text2img_text_allowed",
            "steps": [
                {
                    "id": "prompt_draft",
                    "type": "vl_analyze",
                    "role": "preprocess",
                    "displayName": "VL 生成可编辑提示词",
                    "abilityId": "vl_text2img_prompt_draft",
                    "manualConfirmRequired": True,
                },
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "Qwen 文生图",
                    "abilityId": "comfyui_qwen2512_text2img_text_allowed",
                },
            ],
            "vlAssist": {
                "enabled": False,
                "reason": "该业务需要用户先确认提示词，不能在提交出图时自动二次改写。",
            },
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True, description="用于第一步 VL 分析、测评对比和链路追踪；第二步文生图不直接使用原图。"),
                _field("editable_prompt", "生成提示词 Editable Prompt", field_type="textarea", required=True, description="第一步生成后可人工编辑；第二步会原样送入 ComfyUI。"),
                _field("editable_negative_prompt", "反向提示词 Negative Prompt", field_type="textarea", required=False, default=TEXT2IMG_TEXT_ALLOWED_NEGATIVE_DEFAULT, description="默认不会禁用文字、字母或数字。"),
                _field("width", "输出宽度 Width", field_type="number", required=False, description="不填则跟随原图宽度；手动填写时覆盖，底层会按 8 像素安全倍数归一。"),
                _field("height", "输出高度 Height", field_type="number", required=False, description="不填则跟随原图高度；手动填写时覆盖，底层会按 8 像素安全倍数归一。"),
                _field("promptDraftId", "提示词草稿 ID Prompt Draft ID", field_type="text", required=False, description="第一步接口返回；用于排查链路。"),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "text_fission",
            "entry": "business-api",
            "role": "gray_candidate",
            "badge": "新版",
            "isNewVersion": True,
            "provider": "comfyui",
            "interface_pack": "19_2026-05-19_text2img_user_editable_vl_pack_v2",
            "vl_component_ability_id": "vl_text2img_prompt_draft",
            "primary_ability_id": "comfyui_qwen2512_text2img_text_allowed",
            "versionLine": _version_line(
                "text-to-image",
                "文字强化文生图线",
                "为文字要求强的图案单独建立两步式文生图入口。",
                25,
            ),
            "versionLineage": _version_lineage(
                decision="new_business_entry",
                decision_note="这不是旧图生图文字增强的简单升级，而是两步式文生图业务入口。",
                change_summary="新增 VL 提示词草稿接口和 Qwen2512 文生图接口，用户可在中间编辑提示词。",
            ),
            "coze_strategy": "Coze 可只调用业务接口；测评端提供两步交互，业务方也可按 prompts -> runs 顺序接入。",
            "seed_version": 4,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_image_edit_gpt_image2_editor_v1",
        business_key="image_edit",
        version="gpt-image2-editor-v1",
        display_name="图编辑 · GPT Image 2 通用改图",
        description="面向内部客户的组件型图编辑业务入口：前端组件收集主图、标注、参考图、蒙版和编辑指令，中台统一编译后调用 GPT Image 2 图片编辑能力。",
        status="active",
        is_default=True,
        release_time=datetime(2026, 5, 19, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "openai_gpt_image_2_edit",
            "steps": [
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "GPT Image 2 图片编辑",
                    "abilityId": "openai_gpt_image_2_edit",
                }
            ],
            "promptCompiler": {
                "id": "image_edit_prompt_compiler_v1",
                "location": "backend.business_runs",
            },
            "vlAssist": {"enabled": False},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "主图 URL Image URL", field_type="image", required=True, description="需要编辑的主图；测评端上传后会自动落 OSS。"),
                _field("editSkill", "改图技能 Edit Skill", field_type="select", required=False, default="local_modify", description="首版统一叫改图，下方按技能分流。", options=IMAGE_EDIT_SKILL_OPTIONS),
                _field("instruction", "编辑指令 Instruction", field_type="textarea", required=False, description="用业务语言描述想改哪里、改成什么；扩展画布可不填，默认自然补全外扩区域。"),
                _field("selectionHints", "区域标注 Selection Hints", field_type="json", required=False, description="点选、框选、圆选或手绘区域提示；只是告诉模型看哪里，不等同于蒙版。"),
                _field("referenceImages", "参考图 Reference Images", field_type="json", required=False, description="参考图列表；参考图替换和补色校正必须提供。"),
                _field("maskUrl", "蒙版 URL Mask URL", field_type="image", required=False, description="高级模式使用；只允许一个最终 alpha mask，尺寸必须和主图一致。"),
                _field("targetWidth", "扩展画布目标宽度 Target Width", field_type="integer", required=False, description="扩展画布模式使用；不传时由左右扩展像素计算，并向上取整到 16 的倍数。"),
                _field("targetHeight", "扩展画布目标高度 Target Height", field_type="integer", required=False, description="扩展画布模式使用；不传时由上下扩展像素计算，并向上取整到 16 的倍数。"),
                _field("anchor", "扩展锚点 Anchor", field_type="select", required=False, default="center", description="扩展画布模式使用；默认居中。", options=[
                    {"label": "居中", "value": "center"},
                    {"label": "靠左", "value": "left"},
                    {"label": "靠右", "value": "right"},
                    {"label": "靠上", "value": "top"},
                    {"label": "靠下", "value": "bottom"},
                ]),
                _field("preserveOriginal", "保持原图 Preserve Original", field_type="switch", required=False, default=True, description="扩展画布模式默认开启，尽量保持原图区域不变。"),
                _field("size", "输出尺寸 Size", field_type="select", default="auto", description="默认跟随原图/自动；2K 以上高成本高耗时。高级自定义尺寸由后端按官方约束校验。", options=GPT_IMAGE2_SIZE_OPTIONS),
                _field("quality", "质量档位 Quality", field_type="select", default="auto", description="preview=快速预览，production=正式候选，premium=高质量高成本。", options=IMAGE_EDIT_QUALITY_OPTIONS),
                _field("output_format", "输出格式 Output Format", field_type="select", default="png", description="默认 PNG。", options=IMAGE_EDIT_OUTPUT_FORMAT_OPTIONS),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "image_edit",
            "entry": "business-api",
            "role": "gray_candidate",
            "badge": "新版",
            "isNewVersion": True,
            "provider": "openai",
            "model": "gpt-image-2",
            "component": {
                "type": "image-edit-workbench",
                "hostedPath": "/image-edit",
                "sourceAvailable": True,
                "supportsMask": True,
                "supportsReferenceImages": True,
                "supportsSelectionHints": True,
            },
            "versionLine": _version_line(
                "gpt-image2-editor",
                "通用图编辑线",
                "组件型改图入口，面向内部客户源码嵌入和中台托管两种接入方式。",
                35,
            ),
            "versionLineage": _version_lineage(
                decision="new_business_entry",
                decision_note="图编辑是组件型业务，不合并到图裂变；首版只解决通用改图。",
                change_summary="新增主图、标注、参考图、单蒙版和尺寸质量策略编译链路。",
            ),
            "quality_map": {"auto": "auto", "preview": "low", "production": "medium", "premium": "high"},
            "coze_strategy": "Coze 可只调用图编辑业务 API；复杂画布交互由托管组件或业务方源码组件完成。",
            "seed_version": 1,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_product_design_gpt_image2_v1",
        business_key="product_design",
        version="product-design-gpt-image2-v1",
        display_name="产品设计 · GPT Image 2 上品设计",
        description="面向端到端业务闭环的产品设计能力：输入花纹/素材图、产品品类、设计 brief 和展示场景，中台编译为产品设计 prompt 后调用 GPT Image 2 图片编辑能力。",
        status="active",
        is_default=True,
        release_time=datetime(2026, 6, 3, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "openai_gpt_image_2_edit",
            "steps": [
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "GPT Image 2 产品设计",
                    "abilityId": "openai_gpt_image_2_edit",
                }
            ],
            "promptCompiler": {
                "id": "product_design_prompt_compiler_v1",
                "location": "backend.business_runs",
            },
            "vlAssist": {"enabled": False},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "素材/花纹 URL Image URL", field_type="image", required=True, description="用于上品设计的素材图、花纹图或参考主图。"),
                _field("productType", "产品类型 Product Type", field_type="select", required=False, default="apparel", description="决定设计图的产品载体。", options=PRODUCT_DESIGN_PRODUCT_TYPE_OPTIONS),
                _field("designBrief", "设计要求 Design Brief", field_type="textarea", required=True, default="把主图花纹应用到一款适合电商展示的产品设计图，保持图案识别度和商业质感。", description="说明要做什么产品、目标风格、必须保留或避免的内容。"),
                _field("scene", "展示场景 Scene", field_type="select", required=False, default="studio_product", description="决定输出图的展示方式。", options=PRODUCT_DESIGN_SCENE_OPTIONS),
                _field("referenceImages", "参考图 Reference Images", field_type="json", required=False, description="可选参考图列表，用于补充版型、材质或风格。"),
                _field("clientContextId", "调用上下文 ID Client Context ID", required=False, description="客户端侧关联一次业务链路的上下文 ID，用于跨能力回溯和排查。"),
                _field("inputAssetIds", "输入资产 ID Input Asset IDs", field_type="array", required=False, description="客户端侧传入的素材资产 ID 列表，便于回溯。"),
                _field("size", "输出尺寸 Size", field_type="select", default="auto", description="默认跟随原图/自动；2K 以上高成本高耗时。", options=GPT_IMAGE2_SIZE_OPTIONS),
                _field("quality", "质量档位 Quality", field_type="select", default="production", description="preview=快速预览，production=正式候选，premium=高质量高成本。", options=IMAGE_EDIT_QUALITY_OPTIONS),
                _field("output_format", "输出格式 Output Format", field_type="select", default="png", description="默认 PNG。", options=IMAGE_EDIT_OUTPUT_FORMAT_OPTIONS),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "product_design",
            "entry": "business-api",
            "role": "candidate",
            "badge": "新版",
            "isNewVersion": True,
            "provider": "openai",
            "model": "gpt-image-2",
            "versionLine": _version_line(
                "product-design",
                "产品设计能力线",
                "把素材/花纹转成产品设计图，为客户端端到端业务闭环提供中台能力。",
                45,
            ),
            "versionLineage": _version_lineage(
                decision="new_business_entry",
                decision_note="产品设计是独立业务能力，不归并到通用图编辑；客户端可把它编排进业务链路。",
                change_summary="新增产品类型、展示场景、设计 brief 和调用上下文字段，底层首版复用 GPT Image 2 图片编辑能力。",
            ),
            "quality_map": {"auto": "auto", "preview": "low", "production": "medium", "premium": "high"},
            "coze_strategy": "Coze 或客户端只调用产品设计业务 API；中台负责 prompt 编译、版本路由、结果回填和质量治理。",
            "seed_version": 2,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_fission_evaluate_v1",
        business_key="fission_evaluate",
        version="v1",
        display_name="生成图评估 · 裂变质量与逻辑评估",
        description="输入裂变前原图和裂变后生成图，判断结果是否可用、是否需要二次裂变。该接口只负责评分，不自动再次裂变。",
        status="active",
        is_default=True,
        release_time=datetime(2026, 5, 12, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "vl_fission_generated_image_evaluate",
            "steps": [
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "裂变生成图评估",
                    "abilityId": "vl_fission_generated_image_evaluate",
                }
            ],
            "vlAssist": {"enabled": False},
        },
        input_schema={
            "fields": [
                _field(
                    "originalImageUrl",
                    "原图 URL Original Image URL",
                    required=True,
                    description="裂变前的参考原图，必须能被中台访问。",
                ),
                _field(
                    "generatedImageUrl",
                    "生成图 URL Generated Image URL",
                    required=True,
                    description="裂变后的结果图，必须能被中台访问。",
                ),
                _field(
                    "context",
                    "业务上下文 Context",
                    field_type="textarea",
                    required=False,
                    description="可选。建议填写裂变版本、提示词、profile、重绘幅度等，帮助评分模型判断是否符合目标。",
                ),
            ]
        },
        output_schema=_fission_evaluate_output_schema(),
        metadata={
            "category": "image_fission_evaluate",
            "entry": "business-api",
            "role": "quality_gate",
            "badge": "新接入",
            "isNewVersion": True,
            "provider": "vl",
            "ability_id": "vl_fission_generated_image_evaluate",
            "interface_pack": "12_2026-05-12_generated_image_eval_interface_pack_v1",
            "versionLine": _version_line(
                "quality-gate",
                "质量评估线",
                "裂变完成后的独立质量评估入口，不自动再次裂变。",
                40,
            ),
            "versionLineage": _version_lineage(
                decision_note="裂变评分初始版本，作为图裂变后置质检接口。",
                change_summary="建立裂变生成图质量与逻辑评估业务入口。",
            ),
            "coze_strategy": "业务方可在裂变完成后单独调用该业务 API；中台返回 runId 并统一走 /api/business/runs/get 轮询。",
            "seed_version": 1,
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
            "versionLine": _version_line(
                "comfyui",
                "ComfyUI 自研线",
                "扩图稳定入口，底层由自研 ComfyUI 工作流执行。",
                20,
            ),
            "versionLineage": _version_lineage(
                decision_note="扩图初始生产版本，业务入口保持稳定。",
                change_summary="建立扩图业务入口，底层使用 FLUX2-Klein 9B 扩图工作流。",
            ),
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
            "versionLine": _version_line(
                "rollback",
                "保底回滚",
                "只在主线异常时切回，不作为新功能入口。",
                80,
            ),
            "versionLineage": _version_lineage(
                decision="rollback",
                parent_version_id="biz_outpaint_v1_flux2_klein_9b",
                decision_note="保底回滚版本，只在默认扩图异常时切回，不作为新业务入口。",
                change_summary="保留旧花纹扩图工作流作为扩图回滚方案。",
            ),
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
