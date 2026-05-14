"""Static definitions for built-in ability catalogs."""

from __future__ import annotations

from textwrap import dedent
from typing import Any, TypedDict


def _compose_bilingual_label(primary: str, secondary: str) -> str:
    primary = primary.strip()
    secondary = secondary.strip()
    if primary and secondary and primary.lower() != secondary.lower():
        return f"{primary} {secondary}"
    return primary or secondary


def _presentation_field(
    *,
    label: str | None = None,
    description: str | None = None,
    placeholder: str | None = None,
    advanced: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if label:
        payload["label"] = label.strip()
    if description:
        payload["description"] = description.strip()
    if placeholder:
        payload["placeholder"] = placeholder.strip()
    if isinstance(advanced, bool):
        payload["advanced"] = advanced
    return payload


def _presentation(
    *,
    name: str | None = None,
    summary: str | None = None,
    form_intro: str | None = None,
    expected_output: str | None = None,
    surfaces: dict[str, Any] | None = None,
    fields: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if name:
        payload["name"] = name.strip()
    if summary:
        payload["summary"] = summary.strip()
    if form_intro:
        payload["formIntro"] = form_intro.strip()
    if expected_output:
        payload["expectedOutput"] = expected_output.strip()
    if isinstance(surfaces, dict) and surfaces:
        payload["surfaces"] = {str(key): value for key, value in surfaces.items() if value is not None}
    if isinstance(fields, dict) and fields:
        payload["fields"] = {str(key): value for key, value in fields.items() if isinstance(value, dict) and value}
    return payload


def _baidu_image_schema(
    *,
    include_resolution: bool = False,
    resolution_default: str | None = None,
    include_type: bool = False,
    type_default: str | None = None,
    type_options: list[str] | None = None,
) -> dict[str, Any]:
    fields: list[dict[str, Any]] = [
        {
            "name": "image_url",
            "type": "image",
            "label": _compose_bilingual_label("输入图片", "Input Image"),
            "description": _compose_bilingual_label(
                "上传或填写需要处理的图片地址；测试时会统一上传到 OSS。",
                "Upload or provide the image URL; tests store it in OSS first.",
            ),
            "required": True,
        }
    ]
    if include_resolution:
        fields.append(
            {
                "name": "resolution",
                "type": "select",
                "label": _compose_bilingual_label("输出分辨率", "Output Resolution"),
                "options": [
                    {"label": "1K · 1024px", "value": "1k"},
                    {"label": "2K · 2048px", "value": "2k"},
                    {"label": "4K · 4096px", "value": "4k"},
                ],
                "default": (resolution_default or "2k").lower(),
                "description": _compose_bilingual_label(
                    "控制放大后的目标尺寸，默认 2K。", "Controls upscaled resolution, default 2K."
                ),
            }
        )
    if include_type:
        options = type_options or ["auto", "clarity", "detail", "texture"]
        fields.append(
            {
                "name": "type",
                "type": "select",
                "label": _compose_bilingual_label("处理模式", "Enhance Mode"),
                "options": [{"label": value, "value": value} for value in options],
                "default": (type_default or "auto").lower(),
                "description": _compose_bilingual_label(
                    "不同模式在清晰度、细节与纹理间取舍，参照百度文档。", "See Baidu docs for mode semantics."
                ),
            }
        )
    return {"fields": fields}


def _baidu_metadata(capability_key: str, endpoint: str) -> dict[str, Any]:
    return {
        "executor_type": "baidu",
        "executor_tag": "baidu_image",
        "api_type": "baidu_image_process",
        "model_id": capability_key,
        "request_endpoint": endpoint,
        "requires_image_input": True,
        "supports_vision": True,
        "seed_version": 2,
        "pricing": {
            "currency": "CNY",
            "unit": "per_image",
            "list_price": 0.15,
            "discount_price": 0.10,
        },
        "reference": "https://ai.baidu.com/ai-doc/IMAGEPROCESS/Vk3bcxb07",
    }


def _volcengine_llm_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("提示词", "Prompt"),
                "placeholder": _compose_bilingual_label("请输入中文/英文提示词", "Enter prompt text"),
                "required": True,
            },
            {
                "name": "image_url",
                "type": "text",
                "label": _compose_bilingual_label("图片 URL（可选）", "Image URL (optional)"),
                "description": _compose_bilingual_label(
                    "若存在视觉输入，请填公网可访问链接。", "Provide a public image URL for multimodal prompts."
                ),
                "required": False,
            },
        ]
    }


DEFAULT_VOLCENGINE_VL_ABILITY_ID = "volcengine_doubao_seed_2_0_lite"
DEFAULT_VOLCENGINE_VL_MODEL_ID = "doubao-seed-2-0-lite-260428"
DEFAULT_VOLCENGINE_VL_DISPLAY_NAME = "火山 Doubao-Seed-2.0-lite VL"


def _vl_analyze_image_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("图片 URL", "Image URL"),
                "required": True,
                "description": _compose_bilingual_label(
                    "用于视觉理解的主图。", "Primary image for visual-language analysis."
                ),
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("分析要求", "Analysis Prompt"),
                "required": False,
                "description": _compose_bilingual_label(
                    "为空时使用平台默认的商品图/图案分析模板。",
                    "Uses PODI's default product/pattern analysis template when empty.",
                ),
            },
            {
                "name": "provider",
                "type": "select",
                "label": _compose_bilingual_label("VL 来源", "VL Provider"),
                "default": "volcengine_vl",
                "options": [
                    {"label": DEFAULT_VOLCENGINE_VL_DISPLAY_NAME, "value": "volcengine_vl"},
                    {"label": "Coze 已接入 VL", "value": "coze_vl"},
                ],
                "description": _compose_bilingual_label(
                    "Coze VL 需要在能力元信息或请求中配置 coze_workflow_id。",
                    "Coze VL requires coze_workflow_id in ability metadata or request inputs.",
                ),
            },
            {
                "name": "coze_workflow_id",
                "type": "text",
                "label": _compose_bilingual_label("Coze VL 工作流 ID", "Coze VL Workflow ID"),
                "required": False,
            },
        ]
    }


FISSION_CONTROL_CARD_VL_PROMPT = dedent(
    """
    你是一个专业的装饰图案、印花纹样、装饰插画与主视觉结构分析助手。

    请分析输入图片，并只输出 JSON，不要输出 Markdown、解释、代码块或前后缀。
    这个 JSON 会直接传给图裂变工作流，目标是让后续模型稳定理解原图的结构、风格、材质、疏密和可变化范围。

    输出字段必须严格包含：
    {
      "prompt_main": "",
      "image_desc": "",
      "pattern_risk_type": "small_scatter_high_density | medium_floral_textile | clean_vector_cartoon_repeat | separable_cartoon_icon_repeat | large_single_motif | unknown_or_uncertain",
      "density_risk_level": "low | medium | high",
      "motif_scale_band": "tiny | small | medium | large | mixed",
      "layout_lock_level": "low | medium | high",
      "object_variation_level": "low | medium | high",
      "palette_lock_required": true,
      "max_denoise": 0.68,
      "recommended_reference_lock": 0.42,
      "recommended_color_lock": 0.90,
      "palette_card": {
        "dominant_colors": [],
        "accent_colors": [],
        "background_color": "",
        "forbidden_color_drift": []
      },
      "density_card": {
        "motif_count_level": "sparse | medium | dense | very_dense",
        "spacing_rhythm": "random_scatter | loose_repeat | regular_repeat | packed_repeat",
        "large_medium_small_ratio": "",
        "background_to_motif_ratio": ""
      },
      "scale_card": {
        "average_motif_size": "tiny | small | medium | large",
        "must_not_enlarge": true,
        "must_not_reduce_count": true
      },
      "negative_control": []
    }

    关键要求：
    - pattern_risk_type 用于后端路由实际 denoise。分离的卡通、贴纸、图标、儿童、动物、食物、玩具等可识别对象，使用 separable_cartoon_icon_repeat。
    - prompt_main 是给生成模型的主提示词，重点描述要保留的系列感、主要元素、构图、风格和允许变化的对象级细节。
    - image_desc 是给工作流的补充控制描述，重点描述疏密、层级、边框、颜色比例、材质、禁止漂移方向。
    - 对 separable_cartoon_icon_repeat，高裂变幅度必须使用强对象级变化，不要写“微调”“轻微调整”“局部优化”等保守表达。
    - 对 separable_cartoon_icon_repeat，prompt_main 必须包含或等价表达：
      "High object-level fission: every repeated object should show visible local redesign. Vary poses, contour details, hair, clothing, expressions, accessory details, object decoration, ball panel patterns, heart silhouettes, and small shape details. Avoid keeping identical repeated objects. Preserve all-over repeat layout, motif count level, average motif size, spacing rhythm, background-to-motif area ratio, and source palette."
    - palette_card 必须给出主色、底色、点缀色、面积关系以及禁止新增的主导色系。
    - 颜色控制优先级高：保持原图主色、辅色、点缀色和深浅面积比例，不得新增原图没有的主导色系。
    - prompt_main 禁止出现“不同配色方案”“可调整配色”“重新设计色彩”“更丰富的色彩”等放权表达。
    - 不要把图案误判成真实场景，不要把裂变理解成只换颜色。
    - 如果原图是花纹/印花/装饰插画，必须明确它是平面图案或主视觉，不是摄影场景。
    """
).strip()


def _vl_fission_control_card_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("原图 URL", "Image URL"),
                "required": True,
                "description": _compose_bilingual_label(
                    "用于生成图裂变控制卡的原图。", "Source image used to build the fission control card."
                ),
            },
            {
                "name": "provider",
                "type": "select",
                "label": _compose_bilingual_label("VL 来源", "VL Provider"),
                "default": "volcengine_vl",
                "options": [
                    {"label": DEFAULT_VOLCENGINE_VL_DISPLAY_NAME, "value": "volcengine_vl"},
                    {"label": "Coze 已接入 VL", "value": "coze_vl"},
                ],
                "description": _compose_bilingual_label(
                    "后续切换 VL 模型时优先改这里的默认来源，依赖方不需要改配方。",
                    "Change this default provider first when replacing the central VL model.",
                ),
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("控制卡提示词（高级）", "Control Prompt (Advanced)"),
                "required": False,
                "description": _compose_bilingual_label(
                    "默认使用平台图裂变控制卡模板；只有调试新模型时才需要覆盖。",
                    "Defaults to PODI's fission control-card template; override only for model debugging.",
                ),
            },
            {
                "name": "coze_workflow_id",
                "type": "text",
                "label": _compose_bilingual_label("Coze VL 工作流 ID", "Coze VL Workflow ID"),
                "required": False,
            },
        ]
    }


def _vl_generated_image_evaluation_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "original_image",
                "type": "image",
                "label": _compose_bilingual_label("原图 URL", "Original Image URL"),
                "required": True,
                "description": _compose_bilingual_label("裂变前的参考原图。", "Reference image before fission."),
            },
            {
                "name": "generated_image",
                "type": "image",
                "label": _compose_bilingual_label("生成图 URL", "Generated Image URL"),
                "required": True,
                "description": _compose_bilingual_label("裂变后需要评估的生成图。", "Generated image to evaluate."),
            },
            {
                "name": "context",
                "type": "textarea",
                "label": _compose_bilingual_label("评估上下文 JSON", "Evaluation Context JSON"),
                "required": False,
                "description": _compose_bilingual_label(
                    "可传 task_id、profile、pattern_type 等信息；为空也可评估。",
                    "Optional task_id, profile, pattern_type, and other evaluation context.",
                ),
            },
            {
                "name": "provider",
                "type": "select",
                "label": _compose_bilingual_label("评估来源", "Evaluation Provider"),
                "default": "coze_eval",
                "options": [
                    {"label": "Coze 生成图评估工作流", "value": "coze_eval"},
                ],
                "description": _compose_bilingual_label(
                    "当前先复用 AI 团队已验证的 Coze 评估工作流，后续可切换为中台直连 VL。",
                    "Uses the verified Coze evaluation workflow first; can later switch to a backend VL provider.",
                ),
            },
            {
                "name": "coze_workflow_id",
                "type": "text",
                "label": _compose_bilingual_label("Coze 评估工作流 ID", "Coze Evaluation Workflow ID"),
                "required": False,
            },
        ]
    }


def _vl_metadata(*, seed_version: int) -> dict[str, Any]:
    return {
        "executor_type": "vl",
        "api_type": "vl_analyze_image",
        "default_provider": "volcengine_vl",
        "provider_ability_map": {
            "volcengine_vl": DEFAULT_VOLCENGINE_VL_ABILITY_ID,
            "coze_vl": "coze_workflow",
        },
        "requires_image_input": True,
        "supports_vision": True,
        "structured_output": True,
        "default_provider_label": DEFAULT_VOLCENGINE_VL_DISPLAY_NAME,
        "seed_version": seed_version,
        "presentation": _presentation(
            name="VL 图像理解",
            summary="把图片转成结构化分析卡，用于裂变、扩图、提示词增强和业务审核。",
            form_intro="上传图片即可分析主体、风格、颜色、构图和后续生成建议。",
            expected_output="返回结构化 JSON，供业务编排、MCP、技能或 Coze 继续使用。",
            surfaces={"client": False, "coze": True, "admin": True, "eval": False},
            fields={
                "image_url": _presentation_field(label="待分析图片"),
                "prompt": _presentation_field(label="分析要求", advanced=True),
                "provider": _presentation_field(label="VL 来源", advanced=True),
            },
        ),
    }


def _vl_fission_control_card_metadata(*, seed_version: int) -> dict[str, Any]:
    return {
        "executor_type": "vl",
        "api_type": "vl_analyze_image",
        "component_key": "fission_control_card",
        "default_provider": "volcengine_vl",
        "provider_ability_map": {
            "volcengine_vl": DEFAULT_VOLCENGINE_VL_ABILITY_ID,
            "coze_vl": "coze_workflow",
        },
        "requires_image_input": True,
        "supports_vision": True,
        "structured_output": True,
        "output_schema": "fission_control_card_v2",
        "default_provider_label": DEFAULT_VOLCENGINE_VL_DISPLAY_NAME,
        "seed_version": seed_version,
        "presentation": _presentation(
            name="图裂变 VL 控制卡",
            summary="把原图分析成裂变工作流可直接使用的控制卡，集中承载 VL 模型选择。",
            form_intro="上传原图后生成 prompt_main、prompt_control 和控制卡；图裂变配方统一依赖该组件。",
            expected_output="返回 fissionControlCard JSON，可直接传给 ComfyUI 或商业模型裂变能力。",
            surfaces={"client": False, "coze": True, "admin": True, "eval": True},
            fields={
                "image_url": _presentation_field(label="原图"),
                "provider": _presentation_field(label="VL 来源", advanced=True),
                "prompt": _presentation_field(label="控制卡提示词", advanced=True),
            },
        ),
    }


def _vl_generated_image_evaluation_metadata(*, seed_version: int) -> dict[str, Any]:
    return {
        "executor_type": "vl",
        "api_type": "generated_image_evaluation",
        "component_key": "fission_generated_image_evaluate",
        "default_provider": "coze_eval",
        "coze_workflow_id": "7632187670952673280",
        "requires_image_input": True,
        "supports_vision": True,
        "structured_output": True,
        "output_schema": "generated_image_evaluation_v1",
        "seed_version": seed_version,
        "presentation": _presentation(
            name="裂变生成图评估",
            summary="评估裂变生成图是否保持原图逻辑、质量和系列感，输出 pass / needs_refission / reject。",
            form_intro="传入原图和生成图，系统返回结构化评分、问题标签和建议动作。",
            expected_output="返回 decision、score、scores、problem_tags、reason、next_action。",
            surfaces={"client": False, "coze": True, "admin": True, "eval": True},
            fields={
                "original_image": _presentation_field(label="原图"),
                "generated_image": _presentation_field(label="生成图"),
                "context": _presentation_field(label="评估上下文", advanced=True),
            },
        ),
    }


def _volcengine_image_schema(
    defaults: dict[str, Any],
    *,
    size_options: list[dict[str, str]] | None = None,
    include_n: bool = True,
) -> dict[str, Any]:
    size_default = defaults.get("size", "2K")
    response_format_default = defaults.get("response_format", "url")
    n_default = defaults.get("n", 1)
    # Seedream models have different size constraints (e.g. 4.5 minimum is 2K).
    # Keep the UI aligned with what the provider accepts to reduce user trial/error.
    size_options = size_options or [
        {"label": "1K · 1024x1024", "value": "1K"},
        {"label": "2K · 2048x2048", "value": "2K"},
        {"label": "4K · 4096x4096", "value": "4K"},
    ]
    fields: list[dict[str, Any]] = [
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("提示词", "Prompt"),
                "placeholder": _compose_bilingual_label("描述你想生成的画面", "Describe the scene you want"),
                "required": True,
            },
            {
                "name": "negative_prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("反向提示词", "Negative Prompt"),
                "required": False,
            },
            {
                "name": "image_urls",
                "type": "textarea",
                "label": _compose_bilingual_label("参考图 URL（单张或多张）", "Reference Image URL(s)"),
                "description": _compose_bilingual_label(
                    "Seedream 4.x 图生图：单张填 1 行；多参考图每行 1 个 URL。",
                    "Seedream 4.x image-to-image: one URL per line (1+).",
                ),
            },
            {
                "name": "sequential_image_generation",
                "type": "select",
                "label": _compose_bilingual_label("连续生成", "Sequential Image Generation"),
                "options": [
                    {"label": "disabled（默认）", "value": "disabled"},
                    {"label": "auto（生成一组图）", "value": "auto"},
                ],
                "default": "disabled",
                "description": _compose_bilingual_label(
                    "auto 时可配 max_images 控制生成张数（由模型决定具体效果）。",
                    "When auto, set max_images to control batch size.",
                ),
            },
            {
                "name": "max_images",
                "type": "number",
                "label": _compose_bilingual_label("连续生成张数", "Max Images"),
                "default": 3,
                "description": _compose_bilingual_label(
                    "仅在连续生成=auto 时生效。", "Only used when sequential_image_generation=auto."
                ),
            },
            {
                "name": "size",
                "type": "select",
                "label": _compose_bilingual_label("输出尺寸", "Output Size"),
                "options": size_options,
                "default": size_default,
                "description": _compose_bilingual_label(
                    "常用分辨率，可与自定义宽高共同决定画幅。", "Presets, can combine with custom width/height."
                ),
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("自定义宽度 (px)", "Custom Width (px)"),
                "description": _compose_bilingual_label(
                    "仅用于 PODI 侧后处理裁切/画布适配；Seedream 4.x 不保证严格按该尺寸生成。",
                    "Used for PODI post-processing only; model may ignore exact size.",
                ),
            },
            {
                "name": "height",
                "type": "number",
                "label": _compose_bilingual_label("自定义高度 (px)", "Custom Height (px)"),
            },
            {
                "name": "response_format",
                "type": "select",
                "label": _compose_bilingual_label("返回格式", "Response Format"),
                "options": [{"label": "URL", "value": "url"}, {"label": "Base64 JSON", "value": "b64_json"}],
                "default": response_format_default,
            },
        ]

    if include_n:
        fields.append(
            {
                "name": "n",
                "type": "number",
                "label": _compose_bilingual_label("输出张数", "Number of Images"),
                "default": n_default,
                "description": _compose_bilingual_label(
                    "部分模型会忽略该字段；Seedream 4.x 建议用“连续生成”生成一组图。",
                    "Some models ignore this; for Seedream 4.x prefer sequential generation.",
                ),
            }
        )

    return {"fields": fields}


def _volcengine_video_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("提示词", "Prompt"),
                "placeholder": _compose_bilingual_label("描述场景、镜头与参数", "Describe scene, motion and cues"),
                "required": True,
            },
            {
                "name": "image_url",
                "type": "text",
                "label": _compose_bilingual_label("参考图 URL（可选）", "Reference Image URL (optional)"),
                "description": _compose_bilingual_label(
                    "可提供一张参考图指导镜头风格。", "Optional still image to guide the style."
                ),
            },
            {
                "name": "duration",
                "type": "select",
                "label": _compose_bilingual_label("视频时长（秒）", "Duration (sec)"),
                "options": [{"label": "5s", "value": "5"}, {"label": "8s", "value": "8"}, {"label": "10s", "value": "10"}],
                "default": "5",
            },
            {
                "name": "camera_fixed",
                "type": "switch",
                "label": _compose_bilingual_label("固定镜头", "Fixed Camera"),
                "description": _compose_bilingual_label("勾选则锁定机位", "Lock camera movement when enabled"),
            },
            {
                "name": "watermark",
                "type": "switch",
                "label": _compose_bilingual_label("开启水印", "Enable Watermark"),
                "default": True,
            },
        ]
    }


def _volcengine_metadata(
    *,
    endpoint: str,
    model_id: str,
    api_type: str,
    supports_vision: bool,
    reference: str,
    seed_version: int | None = None,
) -> dict[str, Any]:
    metadata = {
        "executor_type": "volcengine",
        "executor_tag": "volcengine",
        "model_id": model_id,
        "api_type": api_type,
        "supports_vision": supports_vision,
        "request_endpoint": endpoint,
        "reference": reference,
    }
    if api_type == "chat_completions":
        metadata["pricing"] = {
            "currency": "CNY",
            "unit": "per_call",
            "list_price": 0.08,
            "discount_price": 0.05,
        }
    elif api_type == "image_generation":
        metadata["pricing"] = {
            "currency": "CNY",
            "unit": "per_image",
            "list_price": 0.45,
            "discount_price": 0.30,
        }
    elif api_type == "video_generation":
        metadata["pricing"] = {
            "currency": "CNY",
            "unit": "per_video",
            "list_price": 2.00,
            "discount_price": 1.50,
        }
    if seed_version:
        metadata["seed_version"] = seed_version
    return metadata


def _openai_image_edit_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("编辑说明", "Edit Prompt"),
                "placeholder": _compose_bilingual_label("描述要如何修改图片", "Describe how to edit the image"),
                "required": True,
            },
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("原图 URL", "Source Image URL"),
                "description": _compose_bilingual_label(
                    "公网可访问的原图地址，backend 会统一沉淀结果到 OSS。",
                    "Public source image URL; backend stores outputs to OSS.",
                ),
                "required": True,
            },
            {
                "name": "mask_url",
                "type": "image",
                "label": _compose_bilingual_label("蒙版 URL（可选）", "Mask URL (optional)"),
                "description": _compose_bilingual_label(
                    "需要局部编辑时填写蒙版图地址。", "Provide a mask URL for localized edits."
                ),
            },
            {
                "name": "image_urls",
                "type": "textarea",
                "label": _compose_bilingual_label("参考图 URLs（可选）", "Reference Image URLs (optional)"),
                "description": _compose_bilingual_label(
                    "多张参考图每行一个 URL。", "One reference image URL per line."
                ),
            },
            {
                "name": "size",
                "type": "select",
                "label": _compose_bilingual_label("输出尺寸", "Output Size"),
                "options": [
                    {"label": "auto", "value": "auto"},
                    {"label": "1024x1024", "value": "1024x1024"},
                    {"label": "1024x1536", "value": "1024x1536"},
                    {"label": "1536x1024", "value": "1536x1024"},
                ],
                "default": "auto",
                "description": _compose_bilingual_label(
                    "默认跟随原图尺寸；只有手动选择固定尺寸时才改变输出画布。",
                    "Defaults to the source image size; fixed presets change the output canvas.",
                ),
            },
            {
                "name": "quality",
                "type": "select",
                "label": _compose_bilingual_label("质量", "Quality"),
                "options": [
                    {"label": "auto", "value": "auto"},
                    {"label": "high", "value": "high"},
                    {"label": "medium", "value": "medium"},
                    {"label": "low", "value": "low"},
                ],
                "default": "auto",
            },
            {
                "name": "background",
                "type": "select",
                "label": _compose_bilingual_label("背景模式", "Background Mode"),
                "description": _compose_bilingual_label(
                    "GPT Image 2 当前支持自动或不透明背景，不支持透明背景。",
                    "GPT Image 2 currently supports auto or opaque background, not transparent.",
                ),
                "options": [
                    {"label": "auto", "value": "auto"},
                    {"label": "opaque", "value": "opaque"},
                ],
                "default": "auto",
            },
            {
                "name": "output_format",
                "type": "select",
                "label": _compose_bilingual_label("输出格式", "Output Format"),
                "options": [
                    {"label": "png", "value": "png"},
                    {"label": "jpeg", "value": "jpeg"},
                    {"label": "webp", "value": "webp"},
                ],
                "default": "png",
            },
            {
                "name": "output_compression",
                "type": "number",
                "label": _compose_bilingual_label("输出压缩率", "Output Compression"),
                "description": _compose_bilingual_label(
                    "仅 jpeg/webp 有效，范围 0-100；PNG 可留空。",
                    "Only applies to jpeg/webp, range 0-100; leave empty for PNG.",
                ),
                "min": 0,
                "max": 100,
            },
            {
                "name": "n",
                "type": "number",
                "label": _compose_bilingual_label("生成张数", "Number of Images"),
                "description": _compose_bilingual_label(
                    "默认 1 张；批量生成会增加成本和等待时间。",
                    "Defaults to 1; larger batches increase cost and wait time.",
                ),
                "default": 1,
                "min": 1,
                "max": 4,
            },
        ]
    }


def _openai_image_generation_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("提示词", "Prompt"),
                "placeholder": _compose_bilingual_label("描述要生成的画面", "Describe the image to generate"),
                "required": True,
            },
            {
                "name": "size",
                "type": "select",
                "label": _compose_bilingual_label("输出尺寸", "Output Size"),
                "options": [
                    {"label": "1024x1024", "value": "1024x1024"},
                    {"label": "1024x1536", "value": "1024x1536"},
                    {"label": "1536x1024", "value": "1536x1024"},
                    {"label": "auto", "value": "auto"},
                ],
                "default": "1024x1024",
            },
            {
                "name": "quality",
                "type": "select",
                "label": _compose_bilingual_label("质量", "Quality"),
                "options": [
                    {"label": "auto", "value": "auto"},
                    {"label": "high", "value": "high"},
                    {"label": "medium", "value": "medium"},
                    {"label": "low", "value": "low"},
                ],
                "default": "auto",
            },
            {
                "name": "background",
                "type": "select",
                "label": _compose_bilingual_label("背景模式", "Background Mode"),
                "description": _compose_bilingual_label(
                    "GPT Image 2 当前支持自动或不透明背景，不支持透明背景。",
                    "GPT Image 2 currently supports auto or opaque background, not transparent.",
                ),
                "options": [
                    {"label": "auto", "value": "auto"},
                    {"label": "opaque", "value": "opaque"},
                ],
                "default": "auto",
            },
            {
                "name": "output_format",
                "type": "select",
                "label": _compose_bilingual_label("输出格式", "Output Format"),
                "options": [
                    {"label": "png", "value": "png"},
                    {"label": "jpeg", "value": "jpeg"},
                    {"label": "webp", "value": "webp"},
                ],
                "default": "png",
            },
            {
                "name": "output_compression",
                "type": "number",
                "label": _compose_bilingual_label("输出压缩率", "Output Compression"),
                "description": _compose_bilingual_label(
                    "仅 jpeg/webp 有效，范围 0-100；PNG 可留空。",
                    "Only applies to jpeg/webp, range 0-100; leave empty for PNG.",
                ),
                "min": 0,
                "max": 100,
            },
            {
                "name": "n",
                "type": "number",
                "label": _compose_bilingual_label("生成张数", "Number of Images"),
                "description": _compose_bilingual_label(
                    "默认 1 张；批量生成会增加成本和等待时间。",
                    "Defaults to 1; larger batches increase cost and wait time.",
                ),
                "default": 1,
                "min": 1,
                "max": 4,
            },
        ]
    }


def _openai_metadata(*, model_id: str, api_type: str, seed_version: int = 1) -> dict[str, Any]:
    return {
        "executor_type": "vendor_api",
        "executor_tag": "global-egress",
        "provider_family": "openai",
        "model_id": model_id,
        "api_type": api_type,
        "execution_mode": "sync_then_store",
        "requires_image_input": api_type == "image_edit",
        "supports_vision": True,
        "supports_mask": api_type == "image_edit",
        "supports_multiple_images": True,
        "request_endpoint": "/v1/images/edits" if api_type == "image_edit" else "/v1/images/generations",
        "seed_version": seed_version,
        "pricing": {
            "currency": "USD",
            "unit": "per_image",
            "list_price": 0.08,
            "discount_price": 0.08,
        },
    }


def _comfyui_seamless_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "patternType",
                "type": "select",
                "label": _compose_bilingual_label("图案类型", "Pattern Type"),
                "description": "节点 97 · easy ifElse(boolean)",
                "options": [
                    {"label": _compose_bilingual_label("四方连续", "Four-way Seamless"), "value": "seamless"},
                    {"label": _compose_bilingual_label("两方连续", "Two-way Seamless"), "value": "twoway"},
                ],
                "default": "seamless",
            },
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("样例图 URL", "Reference Image URL"),
                "description": _compose_bilingual_label(
                    "输入公网图片链接，或在测试面板上传图片自动填写", "Provide a public URL or upload image in the tester"
                )
                + "（节点 96）",
                "required": True,
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("生图宽度(px)", "Output Width (px)"),
                "description": "节点 102 · ImageResize+.width（默认 1024）",
                "default": 1024,
                "min": 256,
                "max": 4096,
            },
            {
                "name": "height",
                "type": "number",
                "label": _compose_bilingual_label("生图高度(px)", "Output Height (px)"),
                "description": "节点 102 · ImageResize+.height（默认 1024）",
                "default": 1024,
                "min": 256,
                "max": 4096,
            },
        ]
    }


PATTERN_EXTRACT_POSITIVE_DEFAULT = dedent(
    """
    1. 纯平面化处理
    彻底消除因载体曲率、褶皱、拉伸、弯曲、折叠或缝合造成的透视、阴影、扭曲、压缩或拉伸。无论载体是圆柱体（杯子）、球面（帽子）、软质织物（毛毯）还是复合曲面（背包），输出均需为完全平坦、无变形的二维图案。

    2. 剥离所有非图案本体元素
    移除载体结构：衣物轮廓、杯身弧度、拉链、纽扣、缝线、标签、水洗标、提手、杯底、帽檐、填充物等。
    移除拍摄环境：背景、模特、支架、反光、投影、污渍、指纹、灰尘、镜头畸变。
    移除材质表现：布料纹理、针织孔隙、陶瓷釉面、塑料反光、绒毛颗粒、印刷网点、油墨堆积等一切非设计意图的物理细节。
    同时完整保留图案内部的设计性元素（底纹、渐变、水印、装饰线条、色块分层、手绘笔触、做旧纹理等）。

    3. 文字像素级还原（最高优先级）
    所有文字（含标点、符号、数字、装饰框、引号、特殊字符）必须逐像素还原：字体、字号、字重、字间距、行距、排版位置、旋转角度、对齐方式、颜色值（RGB/CMYK/HEX）。
    禁止任何“优化”行为：不得去模糊、锐化、提亮、去灰或修改对比度/饱和度。若原文存在印刷瑕疵（褪色、边缘晕染、叠印错位、油墨渗透），必须如实保留。输出中文字颜色误差 ≤ 1 个色阶（ΔE < 2）。

    4. 构图结构 100% 忠实
    所有元素的位置、大小、比例、遮挡关系、环绕逻辑、散点密度、对称轴、中心点等必须与原始设计完全一致。
    - 独立构图：保持原始边界、留白与视觉重心。
    - 重复/无缝图案：精准识别并提取最小可重复单元（Tile Unit），无缝平铺，禁止接缝错位或断裂。

    5. 密度与呼吸感还原
    保持原图的视觉节奏：稀疏处不可填充，密集处不可稀释，确保设计的留白与节奏不被破坏。散点、粒子、文字阵列的随机性或规律性必须原样呈现。

    6. 色彩空间与艺术风格锁定
    保持原始色彩配置文件（sRGB/Adobe RGB/CMYK/Pantone 等）及色彩表现：饱和度、明暗过渡、色彩层次、渐变平滑度均不得改动。
    保留原始艺术风格（手绘、矢量、丝网印刷、喷墨、水彩、像素风、做旧、荧光等），禁止 AI 自动风格迁移或后期增强（自动白平衡、色彩校正、去色、HDR 等）。

    7. 背景色必须 100% 还原载体底色
    输出背景必须为纯色，且颜色严格对应原物品未被图案覆盖的基底色。禁止使用透明、白色或默认灰色。需从多个未覆盖区域取样（边缘、背面、空白区）求平均或主导色。
    - 深色载体：保持深色调，严禁提亮。
    - 彩色载体：背景必须精确匹配该色。
    背景应为均匀纯色，无渐变/噪点/纹理，画布尺寸可扩展（A4、1024×1024、300 dpi 等），但背景色必须全局一致。

    8. 严禁添加或删减任何内容
    禁止新增边框、水印、Logo、版权信息、说明文字、“Sample”字样、AI 生成标记等；禁止裁切核心主体；禁止拼接或凭空补全（除非原图为明确可推导的无缝图案）。

    交付标准
    - 文字颜色误差 ≤ 1 色阶（ΔE < 2）。
    - 背景色与原载体底色误差 ≤ 1 色阶（ΔE < 2）。
    - 图案结构、比例、层次、密度、风格与原图视觉一致性达 100%。
    - 最终输出：干净的平面图案 + 精确还原的纯色背景，可直接进入印刷/制版流程。
    """
).strip()

PATTERN_EXTRACT_NEGATIVE_DEFAULT = (
    "低分辨率, 模糊, 像素化, 有噪点, 有水印, 有文字, 有边框, 有阴影, 有折痕, 有污渍, 有磨损, "
    "有划痕, 有毛刺, 有锯齿, 有压缩痕迹, 有伪影, 有变形, 有拉伸, 有透视畸变, 有透视效果, 有3D渲染感, "
    "有立体感, 有厚度, 有深度, 有光照, 有反射, 有人物, 有手脚, 有鞋子, 有地板, 有背景, 有家具, 有物品, "
    "有拉链, 有扣子, 有缝线, 有带子, 有边缘, 有裁切, 有不完整图案, 有拼接痕迹, 有重复块状感, 有马赛克, "
    "有卡通风格, 有写实风格, 有油画风格, 有水彩风格, 有手绘感, 有草稿感, 有涂鸦感, 有抽象感, 有现代感, "
    "有极简主义, 有留白, 有空隙, 有空白区域, 有产品轮廓, 有杯口, 有瓶盖, 有液体, 有冰块, 有倾倒效果, "
    "有褶皱, 有布料纹理, 有弯曲弧度, 有曲面变形, 有材质颗粒感, 有织物网格, 有塑料反光, 有金属光泽, 色彩过饱和, "
    "色彩失真, 色彩偏移, 背景变为纯白色, 背景变为纯黑色, 过度锐化, 过度模糊, 风格化处理, 添加新元素, 删除原图元素, "
    "切割核心主体, 重复核心主体, 变形核心主体, 打乱构图关系, 元素前后关系错误, 元素位置错乱, 错误地将独立构图图案进行无缝平铺, "
    "错误地将无缝图案添加边框, 破坏中心对称性, 扭曲图案比例, 可见的拼接痕迹, 垂直方向拼接失败, 水平方向拼接失败, 重复单元边界明显, "
    "图案断层, 错误识别最小重复单元, 单元对齐错误, 图案元素在单元边界处被切断, 单元内图案不完整, 破坏边框完整性, 边框被错误平铺, "
    "中心对称性被破坏, 图案比例失调, 移除设计性背景底纹, 移除水印, 破坏背景层次感, 背景变为纯色, 移除产品结构, 移除功能部件, "
    "破坏产品结构完整性, 功能部件被错误移除, 破坏视觉结构, 忽略设计意图, 结构混乱, 层次不清, 失去渐变效果, 失去分层效果, "
    "视觉焦点错误, 元素密度失衡, 分布规律错误, 过度填充, 元素过于密集, 失去呼吸感, 失去手绘韵味, 元素分布均匀化, 元素分布僵硬"
)


PATTERN_EXTRACT_CUP_PROMPT = dedent(
    """
    核心原则：
    1. 曲面展平处理
       彻底消除因杯子圆柱形结构造成的透视压缩、边缘拉伸、接缝扭曲、左右不对称、顶部/底部变形。将印花区域展开为完整的 2D 平面，环绕式印花需展开 360°，部分覆盖则仅展平对应区域，修复拍摄角度造成的比例失真或文字倾斜。
    2. 剥离所有非印花元素
       移除杯身轮廓、杯盖、吸管、手柄、杯口金属圈、杯底、标签、水印、反光、阴影、倒影、背景、拍摄台面等所有硬件与环境干扰。若为手持拍摄，必须清除手指、衣角、背景家具等残影。
    3. 移除物理材质纹理
       去除塑料反光、金属光泽、磨砂质感、喷漆颗粒、划痕、指纹、水渍等物理干扰；但需保留图案内部的艺术元素（手绘、渐变、点状纹理、底纹肌理等）。

    文字 100% 精准还原：
    - 中文/英文/符号逐字逐形还原：字体、字号、字重、颜色、排版结构完全一致。
    - 禁止 AI 自动纠错或美化（例如不得将 “U” 改为 “YOU” 或 “4” 改为 “FOR”）。
    - 模糊、断笔、墨迹不均需保留原貌；排版结构（行距、字距、对齐、换行、缩进）保持不变，沿弧线排列的文字需保留原路径。

    背景色 100% 还原：
    - 输出背景为纯色，且与原杯子底色完全一致（允许误差 ≤ 1 色阶）。
    - 禁止透明/白/默认背景色，需精准提取未被印花覆盖的区域颜色。
    - 背景无渐变、噪点或纹理，可按印刷需求扩展尺寸但颜色必须统一。

    特别强调：
    - 禁止新增边框、水印、logo、说明文字，禁止裁切核心主体。
    - 输出必须是干净的平面图案 + 纯色背景，可直接导入 AI/PS/CDR 制版。
    """
).strip()

PATTERN_EXTRACT_TSHIRT_PROMPT = dedent(
    """
    核心原则：
    1. 纯平面化处理：彻底消除因 T 恤褶皱、肩部弧度、袖口弯曲、下摆拉伸造成的透视、阴影或形变。
    2. 剥离所有非印花元素：移除领口、袖口、下摆、缝线、标签、水洗标、纽扣，以及拍摄背景、模特、光照反射、污渍等。
    3. 移除物理材质纹理：去除布料网格、棉质颗粒、针织纹路、油墨反光、印刷网点等物理干扰，但保留印花内的设计底纹、渐变、水印、装饰线条、色块分层。

    文字必须像素级还原：
    - 字体、字号、字重、字间距、行距、排版位置、颜色值完全一致。
    - 禁止色彩校正、锐化、提亮或对比度调整；原有褪色、模糊、叠印均需保留。
    - 输出中文字颜色误差 ≤ 1 个色阶（ΔE < 2）。

    构图结构 100% 忠实：
    - 独立构图必须保留原始边界与对称性。
    - 重复式/散点式图案需提取最小重复单元并无缝平铺。
    - 严格保持原始密度与留白，禁止过度填充或稀释。

    背景色 100% 还原：
    - 背景必须与原 T 恤面料底色完全一致（误差 ≤ 1 色阶）。
    - 禁止透明/白色/默认背景，需通过取色工具从未覆盖区域取样。
    - 背景为均匀纯色，无渐变、噪点或纹理。

    特别强调：
    - 禁止新增任何元素，禁止裁切核心主体。
    - 最终输出为干净平面图案 + 纯色背景，可直接用于印刷制版。
    """
).strip()

PATTERN_EXTRACT_BLANKET_PROMPT = dedent(
    """
    目标：从实物毛毯照片中提取表面印花，生成可直接用于印刷/打版的 100% 忠实平面设计稿，包含与原毛毯面料底色完全一致的纯色背景。

    核心原则：
    1. 纯平面化处理
       消除因手持、折叠、悬挂或铺开造成的透视倾斜、边缘卷曲、鼓包、拉伸变形和阴影遮挡，将印花区域展平为无三维形变的二维平面。
    2. 剥离所有非印花元素
       移除毛毯轮廓、流苏、缝线、标签、拉链、纽扣等硬件，清除人物、背景家具、光照反射、污渍、褶皱投影，严禁保留任何残影。
    3. 移除物理材质纹理
       去除绒毛、针织纹、压花纹、织物网格、反光点、毛边等物理干扰，但需保留木纹、水彩、渐变、装饰线条等设计性元素。

    文字 100% 精准还原：
    - 中文/英文/符号逐字逐形还原，不得替换、省略或自动纠错。
    - 模糊、断笔、墨迹不均需保留原貌。
    - 排版结构（行距、字距、对齐、换行、缩进）与原图完全一致。

    背景色必须 100% 还原：
    - 从未被印花覆盖的区域采样底色（边缘、角落、背面等），填充整个画布。
    - 背景为均匀纯色，无渐变、噪点或纹理；允许误差 ≤ 1 色阶。

    特别强调：
    - 禁止新增元素或裁切核心主体（文字、边框、图标等）。
    - 输出格式建议为 PNG（纯色背景、300 DPI 以上）或带出血线的 TIFF/PDF，可直接交付印刷厂。
    """
).strip()

PATTERN_EXTRACT_BLANKET_PROMPT_SQUARE = PATTERN_EXTRACT_BLANKET_PROMPT
PATTERN_EXTRACT_BLANKET_PROMPT_LANDSCAPE = PATTERN_EXTRACT_BLANKET_PROMPT
PATTERN_EXTRACT_BLANKET_PROMPT_PORTRAIT = PATTERN_EXTRACT_BLANKET_PROMPT
PATTERN_EXTRACT_GENERIC_QWEN2511_STEPS = [5000, 5500, 6000, 6500, 7000, 7500, 8000]
PATTERN_EXTRACT_GENERIC_QWEN2511_PRESETS: list[dict[str, Any]] = [
    {
        "value": f"印花提取-通用_QwenImageEdit2511_{step}.safetensors",
        "label": f"通用（QwenImageEdit2511 · {step}）",
        "notes": f"通用全品类训练（QwenImageEdit2511，{step} checkpoint），适用于多材质印花提取回归对比。",
        "prompt": PATTERN_EXTRACT_POSITIVE_DEFAULT,
        "negative_prompt": PATTERN_EXTRACT_NEGATIVE_DEFAULT,
    }
    for step in PATTERN_EXTRACT_GENERIC_QWEN2511_STEPS
]

PATTERN_EXTRACT_LORA_PRESETS: list[dict[str, Any]] = [
    {
        "value": "T-Shirt-1-1.safetensors",
        "label": "T 恤（1:1 标准）",
        "notes": "T 恤/卫衣 1:1 训练集，强调褶皱展开、文字像素级还原与面料底色复刻，可直接输出制版平面稿。",
        "prompt": PATTERN_EXTRACT_TSHIRT_PROMPT,
        "negative_prompt": PATTERN_EXTRACT_NEGATIVE_DEFAULT,
    },
    {
        "value": "杯子1124.safetensors",
        "label": "杯子 / 圆柱形介质",
        "notes": "杯子/保温杯等圆柱体训练，保持原图比例，自动展平 360° 图案并剥离手柄/反光，要求背景色与杯身一致。",
        "prompt": PATTERN_EXTRACT_CUP_PROMPT,
        "negative_prompt": PATTERN_EXTRACT_NEGATIVE_DEFAULT,
    },
    *PATTERN_EXTRACT_GENERIC_QWEN2511_PRESETS,
    {
        "value": "印花提取-毛毯1-1.safetensors",
        "label": "毛毯（1:1 正方形）",
        "notes": "毛毯/抱枕 1:1 数据集，适合正方形展开与桌布类素材，默认输出 1800×1800。",
        "prompt": PATTERN_EXTRACT_BLANKET_PROMPT_SQUARE,
        "negative_prompt": PATTERN_EXTRACT_NEGATIVE_DEFAULT,
    },
    {
        "value": "印花提取-毛毯2-1.safetensors",
        "label": "毛毯（2:1 横向）",
        "notes": "横向毛毯/围巾 2:1 数据集，适配左右长条（例如沙发披毯），可按 3600×1800 输出。",
        "prompt": PATTERN_EXTRACT_BLANKET_PROMPT_LANDSCAPE,
        "negative_prompt": PATTERN_EXTRACT_NEGATIVE_DEFAULT,
    },
    {
        "value": "印花提取-毛毯1-2.safetensors",
        "label": "毛毯（1:2 纵向）",
        "notes": "纵向毛毯/挂布 1:2 数据集，适合上下长条（窗帘/壁挂），可按 1800×3600 输出。",
        "prompt": PATTERN_EXTRACT_BLANKET_PROMPT_PORTRAIT,
        "negative_prompt": PATTERN_EXTRACT_NEGATIVE_DEFAULT,
    },
]


def _pattern_extract_lora_options() -> list[dict[str, str]]:
    return [
        {
            "label": entry["label"],
            "value": entry["value"],
        }
        for entry in PATTERN_EXTRACT_LORA_PRESETS
    ]


def _comfyui_pattern_extract_schema() -> dict[str, Any]:
    positive_default = PATTERN_EXTRACT_POSITIVE_DEFAULT
    negative_default = PATTERN_EXTRACT_NEGATIVE_DEFAULT
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("样例图 URL", "Reference Image URL"),
                "description": "节点 393 · LoadImagesFromURL.url",
                "placeholder": "https://example.com/sample.png",
                "required": True,
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("正向提示词", "Positive Prompt"),
                "description": "节点 111 · TextEncodeQwenImageEditPlus.prompt",
                "default": positive_default,
            },
            {
                "name": "negative_prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("反向提示词", "Negative Prompt"),
                "description": "节点 110 · TextEncodeQwenImageEditPlus.prompt",
                "default": negative_default,
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("输出宽度 (px)", "Output Width (px)"),
                "description": "节点 400 · LatentUpscale.width",
                "default": 1800,
            },
            {
                "name": "height",
                "type": "number",
                "label": _compose_bilingual_label("输出高度 (px)", "Output Height (px)"),
                "description": "节点 400 · LatentUpscale.height",
                "default": 1800,
            },
            {
                "name": "batch",
                "type": "number",
                "label": _compose_bilingual_label("批次数量", "Batch Count"),
                "description": "节点 424 · RepeatLatentBatch.amount，控制一次生成多少张图（批次越大耗时越久，超时限制会自动按批次增加）。",
                "default": 1,
                "min": 1,
                "max": 8,
            },
            {
                "name": "lora",
                "type": "select",
                "label": _compose_bilingual_label("LoRA", "LoRA"),
                "description": "节点 390 · LoraLoaderModelOnly.lora_name（可在根目录 LORA_CATALOG.md 查看说明）。",
                "default": "杯子1124.safetensors",
                "options": _pattern_extract_lora_options(),
            },
        ]
    }


def _comfyui_pattern_extract_lora_8step_schema() -> dict[str, Any]:
    positive_default = PATTERN_EXTRACT_POSITIVE_DEFAULT
    negative_default = PATTERN_EXTRACT_NEGATIVE_DEFAULT
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("样例图 URL", "Reference Image URL"),
                "description": "节点 393 · LoadImagesFromURL.url",
                "placeholder": "https://example.com/sample.png",
                "required": True,
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("正向提示词", "Positive Prompt"),
                "description": "节点 111 · TextEncodeQwenImageEditPlus.prompt",
                "default": positive_default,
            },
            {
                "name": "negative_prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("反向提示词", "Negative Prompt"),
                "description": "节点 110 · TextEncodeQwenImageEditPlus.prompt",
                "default": negative_default,
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("输出宽度 (px)", "Output Width (px)"),
                "description": "节点 400 · LatentUpscale.width。不填则默认按原图宽度处理。",
            },
            {
                "name": "height",
                "type": "number",
                "label": _compose_bilingual_label("输出高度 (px)", "Output Height (px)"),
                "description": "节点 400 · LatentUpscale.height。不填则默认按原图高度处理。",
            },
            {
                "name": "batch",
                "type": "number",
                "label": _compose_bilingual_label("批次数量", "Batch Count"),
                "description": "节点 424 · RepeatLatentBatch.amount，控制一次生成多少张图（批次越大耗时越久，超时限制会自动按批次增加）。",
                "default": 1,
                "min": 1,
                "max": 8,
            },
            {
                "name": "lora",
                "type": "select",
                "label": _compose_bilingual_label("LoRA", "LoRA"),
                "description": "节点 390 · LoraLoaderModelOnly.lora_name（可在根目录 LORA_CATALOG.md 查看说明）。",
                "default": "杯子1124.safetensors",
                "options": _pattern_extract_lora_options(),
            },
        ]
    }


def _comfyui_pattern_expand_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("样例图 URL", "Reference Image URL"),
                "description": "节点 205 · LoadImagesFromURL.url",
                "placeholder": "https://example.com/pattern.png",
                "required": True,
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("提示词（可选）", "Prompt (optional)"),
                "description": "节点 74 · Text _O.text（不填使用默认提示词）",
                "required": False,
            },
            {
                "name": "expand_left",
                "type": "number",
                "label": _compose_bilingual_label("左侧扩展 (px)", "Expand Left (px)"),
                "description": "节点 188 · ImpactInt.value",
                "default": 200,
            },
            {
                "name": "expand_right",
                "type": "number",
                "label": _compose_bilingual_label("右侧扩展 (px)", "Expand Right (px)"),
                "description": "节点 189 · ImpactInt.value",
                "default": 200,
            },
            {
                "name": "expand_top",
                "type": "number",
                "label": _compose_bilingual_label("上侧扩展 (px)", "Expand Top (px)"),
                "description": "节点 186 · ImpactInt.value",
                "default": 0,
            },
            {
                "name": "expand_bottom",
                "type": "number",
                "label": _compose_bilingual_label("下侧扩展 (px)", "Expand Bottom (px)"),
                "description": "节点 187 · ImpactInt.value",
                "default": 0,
            },
        ]
    }

def _comfyui_jisu_chuli_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("输入图片 URL", "Input Image URL"),
                "description": _compose_bilingual_label(
                    "上传/填写一张图片 URL。", "Upload/provide one image URL."
                ),
                "required": True,
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("正向提示词", "Positive Prompt"),
                "placeholder": _compose_bilingual_label("例如：把这只大公鸡变个颜色其他不变", "Describe the edit"),
                "required": True,
            },
            {
                "name": "negative_prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("反向提示词（可选）", "Negative Prompt (optional)"),
                "required": False,
            },
            {
                "name": "batch",
                "type": "number",
                "label": _compose_bilingual_label("批次", "Batch"),
                "default": 1,
                "description": _compose_bilingual_label("默认 1。", "Default 1."),
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("输出宽度(px)", "Output Width(px)"),
                "description": _compose_bilingual_label(
                    "不填则默认原图宽度。", "If omitted, defaults to input image width."
                ),
            },
            {
                "name": "height",
                "type": "number",
                "label": _compose_bilingual_label("输出高度(px)", "Output Height(px)"),
                "description": _compose_bilingual_label(
                    "不填则默认原图高度。", "If omitted, defaults to input image height."
                ),
            },
        ]
    }


def _comfyui_e7_flux2_liebian_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("输入图片 URL", "Input Image URL"),
                "description": "节点 10 · LoadImagesFromURL.url",
                "required": True,
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("裂变提示词", "Fission Prompt"),
                "description": "节点 13 · CR Text Concatenate.text1",
                "required": True,
            },
            {
                "name": "bili",
                "type": "number",
                "label": _compose_bilingual_label("重绘幅度（0-100）", "Repaint Strength (0-100)"),
                "description": _compose_bilingual_label(
                    "与旧裂变工作流保持一致的 bili 参数。数值越大重绘越强、变化越明显；后端按 0→0.45、50→0.625、100→0.80 换算为 denoise。",
                    "Compatibility bili parameter aligned with older fission workflows. Higher means stronger repaint and larger variation; backend maps 0→0.45, 50→0.625, 100→0.80 to denoise.",
                ),
                "min": 0,
                "max": 100,
            },
            {
                "name": "seed",
                "type": "number",
                "label": _compose_bilingual_label("随机种子", "Seed"),
                "description": "节点 19 · RandomNoise.noise_seed；不填则自动随机。",
                "required": False,
            },
            {
                "name": "steps",
                "type": "number",
                "label": _compose_bilingual_label("步数", "Steps"),
                "description": "节点 21 · BasicScheduler.steps",
                "default": 8,
                "min": 1,
            },
            {
                "name": "cfg",
                "type": "number",
                "label": _compose_bilingual_label("CFG", "CFG"),
                "description": "节点 18 · CFGGuider.cfg",
                "default": 1.0,
                "min": 0,
            },
            {
                "name": "batch_size",
                "type": "number",
                "label": _compose_bilingual_label("批次数量", "Batch Size"),
                "description": "节点 24 · CR Latent Batch Size.batch_size",
                "default": 1,
                "min": 1,
                "max": 8,
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("输出宽度(px)", "Output Width(px)"),
                "description": _compose_bilingual_label(
                    "节点 12 · ImageResize+.width。不填则默认按原图宽度处理。",
                    "Node 12 · ImageResize+.width. Omit to keep original image width.",
                ),
                "required": False,
            },
            {
                "name": "height",
                "type": "number",
                "label": _compose_bilingual_label("输出高度(px)", "Output Height(px)"),
                "description": _compose_bilingual_label(
                    "节点 12 · ImageResize+.height。不填则默认按原图高度处理。",
                    "Node 12 · ImageResize+.height. Omit to keep original image height.",
                ),
                "required": False,
            },
        ]
    }


def _comfyui_flux_strong_hq_softstyle_fission_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("输入图片 URL", "Input Image URL"),
                "description": _compose_bilingual_label(
                    "节点 10 · LoadImage.image。提交时后端会先把 OSS 图片上传到 ComfyUI input 目录，再写入文件名。",
                    "Node 10 · LoadImage.image. Backend uploads the OSS image into the ComfyUI input folder before setting the staged filename.",
                ),
                "required": True,
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("裂变提示词", "Fission Prompt"),
                "description": "节点 13 · CR Text Concatenate.text1",
                "required": True,
            },
            {
                "name": "image_desc",
                "type": "textarea",
                "label": _compose_bilingual_label("图像补充描述（高级）", "Image Description (Advanced)"),
                "description": _compose_bilingual_label(
                    "节点 13 · CR Text Concatenate.text2。建议由上游 VL / Coze 自动生成，不建议业务手写。",
                    "Node 13 · CR Text Concatenate.text2. Prefer generating this from upstream VL / Coze instead of writing it manually.",
                ),
                "required": False,
            },
            {
                "name": "bili",
                "type": "number",
                "label": _compose_bilingual_label("重绘幅度（0-100）", "Repaint Strength (0-100)"),
                "description": _compose_bilingual_label(
                    "沿用旧图裂变的 bili 口径，后端映射到节点 24 · BasicScheduler.denoise。数值越大重绘越强；默认 90 ≈ denoise 0.765。",
                    "Keeps the previous fission-style bili parameter and maps it to node 24 · BasicScheduler.denoise. Higher values repaint more strongly; default 90 is about denoise 0.765.",
                ),
                "default": 90,
                "min": 0,
                "max": 100,
                "required": False,
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("输出宽度(px)", "Output Width(px)"),
                "description": _compose_bilingual_label(
                    "节点 12 · ImageResize+.width。不填则默认按原图宽度处理。",
                    "Node 12 · ImageResize+.width. Omit to keep the original image width.",
                ),
                "required": False,
            },
            {
                "name": "height",
                "type": "number",
                "label": _compose_bilingual_label("输出高度(px)", "Output Height(px)"),
                "description": _compose_bilingual_label(
                    "节点 12 · ImageResize+.height。不填则默认按原图高度处理。",
                    "Node 12 · ImageResize+.height. Omit to keep the original image height.",
                ),
                "required": False,
            },
        ]
    }


def _comfyui_flux_strong_hq_softstyle_fission_control_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("输入图片 URL", "Input Image URL"),
                "required": True,
                "description": _compose_bilingual_label(
                    "裂变原图；后端会上传到 ComfyUI input 目录后执行。",
                    "Source image; backend stages it into ComfyUI input before execution.",
                ),
            },
            {
                "name": "vl_result",
                "type": "textarea",
                "label": _compose_bilingual_label("VL 控制卡 JSON", "VL Control Card JSON"),
                "required": True,
                "description": _compose_bilingual_label(
                    "来自 vl_fission_control_card 的结果，至少包含 prompt_main 和 prompt_control。",
                    "Result from vl_fission_control_card; should contain prompt_main and prompt_control.",
                ),
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("输出宽度(px)", "Output Width(px)"),
                "default": 2000,
                "required": False,
            },
            {
                "name": "height",
                "type": "number",
                "label": _compose_bilingual_label("输出高度(px)", "Output Height(px)"),
                "default": 2000,
                "required": False,
            },
            {
                "name": "bili",
                "type": "text",
                "label": _compose_bilingual_label("裂变幅度百分比", "Variation Percent"),
                "default": "50%",
                "description": _compose_bilingual_label(
                    "沿用 AI 团队接口包口径：0%=更保守，100%=变化更大；默认 50%。",
                    "AI handoff contract: 0%=conservative, 100%=stronger variation; default 50%.",
                ),
                "required": False,
            },
            {
                "name": "profile",
                "type": "text",
                "label": _compose_bilingual_label("裂变配置", "Profile"),
                "default": "pattern_default_v1",
                "required": False,
            },
            {
                "name": "mode",
                "type": "text",
                "label": _compose_bilingual_label("执行模式", "Mode"),
                "default": "fission",
                "required": False,
            },
            {
                "name": "seed",
                "type": "number",
                "label": _compose_bilingual_label("随机种子（可选）", "Seed (optional)"),
                "required": False,
            },
        ]
    }


def _comfyui_flux_strong_hq_softstyle_fission_colorlock_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("输入图片 URL", "Input Image URL"),
                "required": True,
                "description": _compose_bilingual_label(
                    "裂变原图；后端会上传到 ComfyUI input 目录后执行。",
                    "Source image; backend stages it into ComfyUI input before execution.",
                ),
            },
            {
                "name": "vl_result",
                "type": "textarea",
                "label": _compose_bilingual_label("VL 控制卡 JSON", "VL Control Card JSON"),
                "required": True,
                "description": _compose_bilingual_label(
                    "来自 vl_fission_control_card 的结果，包含 prompt_main、image_desc、pattern_risk_type 和 palette_card。",
                    "Result from vl_fission_control_card; includes prompt_main, image_desc, pattern_risk_type, and palette_card.",
                ),
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("输出宽度(px)", "Output Width(px)"),
                "required": False,
                "description": _compose_bilingual_label(
                    "不填则按原图宽度处理；如手动填写，建议保持原图比例。",
                    "Omit to keep the original width. Keep the source aspect ratio when manually setting it.",
                ),
            },
            {
                "name": "height",
                "type": "number",
                "label": _compose_bilingual_label("输出高度(px)", "Output Height(px)"),
                "required": False,
                "description": _compose_bilingual_label(
                    "不填则按原图高度处理；如手动填写，建议保持原图比例。",
                    "Omit to keep the original height. Keep the source aspect ratio when manually setting it.",
                ),
            },
            {
                "name": "bili",
                "type": "text",
                "label": _compose_bilingual_label("重绘幅度(%)", "Variation Percent"),
                "default": "80%",
                "description": _compose_bilingual_label(
                    "控制图案变化大小；建议低 30%、中 60%、高 80%、极高 100%+。后端会结合 VL 图案类型路由实际 denoise。",
                    "Controls variation size. Suggested: low 30%, medium 60%, high 80%, experimental 100%+. Backend routes denoise by VL pattern risk type.",
                ),
                "required": False,
            },
            {
                "name": "profile",
                "type": "select",
                "label": _compose_bilingual_label("裂变路由配置", "Fission Routing Profile"),
                "default": "pattern_risk_routed_v4",
                "options": [
                    {"label": "智能风险路由（推荐）", "value": "pattern_risk_routed_v4"},
                    {"label": "默认颜色锁定（兼容）", "value": "pattern_color_lock_v2"},
                    {"label": "严格颜色锁定（更像原图）", "value": "pattern_color_lock_strict_v2"},
                ],
                "description": _compose_bilingual_label(
                    "普通业务使用智能风险路由；兼容配置保留给旧样本对照。",
                    "Use risk-routed profile by default. Compatibility profiles are kept for old sample comparison.",
                ),
                "required": False,
            },
            {
                "name": "reference_lock",
                "type": "number",
                "label": _compose_bilingual_label("原图结构保留度", "Reference Lock"),
                "default": 0.42,
                "description": _compose_bilingual_label(
                    "控制生成图贴近原图结构的程度；建议 0.34-0.50，不做硬限制。越高越像原图，裂变感更弱。",
                    "Controls how strongly the result follows the source structure. Suggested 0.34-0.50, not hard-limited. Higher is more faithful but less varied.",
                ),
                "required": False,
            },
            {
                "name": "color_lock",
                "type": "number",
                "label": _compose_bilingual_label("颜色锁定强度", "Color Lock"),
                "default": 0.90,
                "description": _compose_bilingual_label(
                    "控制是否保持原图配色；建议 0.75-1.00，不做硬限制。越高越不容易偏色。",
                    "Controls palette preservation. Suggested 0.75-1.00, not hard-limited. Higher reduces color drift.",
                ),
                "required": False,
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("额外要求", "Extra Prompt"),
                "required": False,
                "description": _compose_bilingual_label(
                    "可选补充说明；不要写放开配色或重新设计色彩的要求。",
                    "Optional extra instruction. Do not ask for open-ended palette redesign.",
                ),
            },
        ]
    }


def _comfyui_multi_image_fusion_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("主图 URL", "Primary Image URL"),
                "description": "节点 78 · LoadImage.image（主图，经 390 节点缩放后送入 image1）",
                "required": True,
            },
            {
                "name": "image_url_2",
                "type": "image",
                "label": _compose_bilingual_label("辅图 1 URL", "Aux Image 1 URL"),
                "description": _compose_bilingual_label(
                    "可选，映射到节点 106 · LoadImage.image（image2）。不传则提交时移除 image2。",
                    "Optional, mapped to node 106 · LoadImage.image (image2). Omitted values will remove image2 on submit.",
                ),
                "required": False,
            },
            {
                "name": "image_url_3",
                "type": "image",
                "label": _compose_bilingual_label("辅图 2 URL", "Aux Image 2 URL"),
                "description": _compose_bilingual_label(
                    "可选，映射到节点 108 · LoadImage.image（image3）。不传则提交时移除 image3。",
                    "Optional, mapped to node 108 · LoadImage.image (image3). Omitted values will remove image3 on submit.",
                ),
                "required": False,
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("输出宽度", "Output Width"),
                "description": "节点 112 · EmptySD3LatentImage.width",
                "required": False,
            },
            {
                "name": "height",
                "type": "number",
                "label": _compose_bilingual_label("输出高度", "Output Height"),
                "description": "节点 112 · EmptySD3LatentImage.height",
                "required": False,
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("正向提示词", "Positive Prompt"),
                "description": "节点 111 · TextEncodeQwenImageEditPlus.prompt",
                "required": False,
            },
            {
                "name": "negative_prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("反向提示词", "Negative Prompt"),
                "description": "节点 110 · TextEncodeQwenImageEditPlus.prompt",
                "required": False,
            },
            {
                "name": "seed",
                "type": "number",
                "label": _compose_bilingual_label("随机种子", "Seed"),
                "description": "节点 151 · CR Seed.seed；不填则后端自动生成随机种子。",
                "required": False,
            },
        ]
    }


def _comfyui_background_remove_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("输入图片 URL", "Input Image URL"),
                "description": "节点 5 · LoadImagesFromURL.url",
                "required": True,
            }
        ]
    }


def _comfyui_head_extract_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("输入图片 URL", "Input Image URL"),
                "description": "节点 141 · LoadImagesFromURL.url",
                "required": True,
            }
        ]
    }


def _comfyui_flux2_9b_liebian_sifang_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("输入图片 URL", "Input Image URL"),
                "description": "节点 141 · LoadImagesFromURL.url",
                "required": True,
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("主提示词", "Prompt"),
                "description": "节点 132 · String.inStr",
                "required": True,
            },
        ]
    }


def _comfyui_flux2_klein_9b_outpaint_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("输入图片 URL", "Input Image URL"),
                "description": "节点 76 · LoadImage.image（后端会先上传到 ComfyUI input 目录）",
                "required": True,
            },
            {
                "name": "expand_left",
                "type": "number",
                "label": _compose_bilingual_label("左侧扩展 (px)", "Expand Left (px)"),
                "description": "节点 102 · ImagePadForOutpaint.left",
                "default": 408,
            },
            {
                "name": "expand_right",
                "type": "number",
                "label": _compose_bilingual_label("右侧扩展 (px)", "Expand Right (px)"),
                "description": "节点 102 · ImagePadForOutpaint.right",
                "default": 408,
            },
            {
                "name": "expand_top",
                "type": "number",
                "label": _compose_bilingual_label("上侧扩展 (px)", "Expand Top (px)"),
                "description": "节点 102 · ImagePadForOutpaint.top",
                "default": 0,
            },
            {
                "name": "expand_bottom",
                "type": "number",
                "label": _compose_bilingual_label("下侧扩展 (px)", "Expand Bottom (px)"),
                "description": "节点 102 · ImagePadForOutpaint.bottom",
                "default": 0,
            },
        ]
    }


def _comfyui_qwen2512_print_shape_text_enhance_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "image",
                "label": _compose_bilingual_label("输入图片 URL", "Input Image URL"),
                "description": "节点 10 · LoadImagesFromURL.url",
                "required": True,
            },
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("文字强化提示词", "Text Enhancement Prompt"),
                "description": "节点 13 · CR Text Concatenate.text1",
                "required": True,
            },
            {
                "name": "bili",
                "type": "number",
                "label": _compose_bilingual_label("相似度", "Similarity"),
                "description": _compose_bilingual_label(
                    "映射到节点 27 · KSampler.denoise：0→0.95，50→0.75，100→0.55。",
                    "Mapped to node 27 · KSampler.denoise: 0→0.95, 50→0.75, 100→0.55.",
                ),
                "required": False,
            },
        ]
    }


def _build_kie_schema(capability_key: str) -> dict[str, Any]:
    if capability_key == "nano_banana_pro_image_to_image":
        return {
            "fields": [
                {
                    "name": "image_url",
                    "type": "image",
                    "label": _compose_bilingual_label("参考图 Image URL", "Reference Image URL"),
                    "description": _compose_bilingual_label(
                        "上传/填写 1 张参考图（会自动上传到 OSS 并转为 URL）。",
                        "Upload/provide one reference image (we'll upload to OSS and convert to URL).",
                    ),
                    # The provider requires an image. Making it required avoids "IMAGE_REQUIRED" surprises in Coze.
                    "required": True,
                },
                {
                    "name": "prompt",
                    "type": "textarea",
                    "label": _compose_bilingual_label("提示词", "Prompt"),
                    "placeholder": _compose_bilingual_label("例如：赛博朋克风格的城市，霓虹灯与雨夜", "Describe style or intent"),
                    "required": True,
                },
                {
                    "name": "image_urls",
                    "type": "textarea",
                    "label": _compose_bilingual_label("参考图 URL 列表", "Reference Image URLs"),
                    "description": _compose_bilingual_label(
                        "可选：每行一个公网图片链接（用于多参考图）。",
                        "Optional: one URL per line (for multiple reference images).",
                    ),
                },
                {
                    "name": "aspect_ratio",
                    "type": "select",
                    "label": _compose_bilingual_label("画幅比例", "Aspect Ratio"),
                    "options": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"],
                    "description": _compose_bilingual_label("留空将按原图处理。", "Leave empty to keep input size."),
                },
                {
                    "name": "resolution",
                    "type": "select",
                    "label": _compose_bilingual_label("分辨率", "Resolution"),
                    "options": ["1K", "2K", "4K"],
                    "description": _compose_bilingual_label("留空将按原图处理。", "Leave empty to keep input size."),
                },
                {
                    "name": "output_format",
                    "type": "select",
                    "label": _compose_bilingual_label("输出格式", "Output Format"),
                    "options": ["png", "jpg"],
                    "default": "png",
                },
                {
                    "name": "callBackUrl",
                    "type": "text",
                    "label": _compose_bilingual_label("回调地址", "Callback URL"),
                    "placeholder": "https://your-domain.com/api/callback",
                },
            ]
        }
    if capability_key == "flux2_pro_image_to_image":
        return {
            "fields": [
                {
                    "name": "prompt",
                    "type": "textarea",
                    "label": _compose_bilingual_label("提示词", "Prompt"),
                    "placeholder": _compose_bilingual_label("描述希望保留/修改的细节", "Describe what to keep or change"),
                    "required": True,
                },
                {
                    "name": "image_urls",
                    "type": "textarea",
                    "label": _compose_bilingual_label("输入图 URL 列表", "Input Image URLs"),
                    "description": _compose_bilingual_label("必填，1-8 行；支持 auto 比例参考。", "Required 1-8 URLs; first image used for auto ratio."),
                    "required": True,
                },
                {
                    "name": "aspect_ratio",
                    "type": "select",
                    "label": _compose_bilingual_label("画幅比例", "Aspect Ratio"),
                    "options": ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "auto"],
                    "description": _compose_bilingual_label("留空将按原图处理。", "Leave empty to keep input size."),
                },
                {
                    "name": "resolution",
                    "type": "select",
                    "label": _compose_bilingual_label("分辨率", "Resolution"),
                    "options": ["1K", "2K"],
                    "description": _compose_bilingual_label("留空将按原图处理。", "Leave empty to keep input size."),
                },
                {
                    "name": "callBackUrl",
                    "type": "text",
                    "label": _compose_bilingual_label("回调地址", "Callback URL"),
                    "placeholder": "https://your-domain.com/api/callback",
                },
            ]
        }
    if capability_key == "nano_banana_2_image_to_image":
        return {
            "fields": [
                {
                    "name": "image_url",
                    "type": "image",
                    "label": _compose_bilingual_label("主图 URL", "Primary Image URL"),
                    "description": _compose_bilingual_label(
                        "上传/填写主图（图1）。",
                        "Upload/provide the primary image (Image 1).",
                    ),
                    "required": True,
                },
                {
                    "name": "prompt",
                    "type": "textarea",
                    "label": _compose_bilingual_label("提示词", "Prompt"),
                    "placeholder": _compose_bilingual_label("例如：保持主体不变，替换背景风格", "Describe desired edits"),
                    "required": True,
                },
                {
                    "name": "image_urls",
                    "type": "textarea",
                    "label": _compose_bilingual_label("参考图 URL 列表", "Reference Image URLs"),
                    "description": _compose_bilingual_label(
                        "可选：每行一个 URL（按顺序作为图2/图3...）。",
                        "Optional: one URL per line (used as Image 2/3...).",
                    ),
                },
                {
                    "name": "aspect_ratio",
                    "type": "select",
                    "label": _compose_bilingual_label("画幅比例", "Aspect Ratio"),
                    "options": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"],
                    "description": _compose_bilingual_label("留空将按原图处理。", "Leave empty to keep input size."),
                },
                {
                    "name": "resolution",
                    "type": "select",
                    "label": _compose_bilingual_label("分辨率", "Resolution"),
                    "options": ["1K", "2K", "4K"],
                    "description": _compose_bilingual_label("留空将按原图处理。", "Leave empty to keep input size."),
                },
                {
                    "name": "google_search",
                    "type": "switch",
                    "label": _compose_bilingual_label("联网搜索增强", "Google Search"),
                    "description": _compose_bilingual_label("可选：开启后增强事实参考。", "Optional: enable web grounding."),
                    "default": False,
                },
                {
                    "name": "output_format",
                    "type": "select",
                    "label": _compose_bilingual_label("输出格式", "Output Format"),
                    "options": ["jpg", "png"],
                    "default": "jpg",
                },
                {
                    "name": "callBackUrl",
                    "type": "text",
                    "label": _compose_bilingual_label("回调地址", "Callback URL"),
                    "placeholder": "https://your-domain.com/api/callback",
                },
            ]
        }
    if capability_key == "sora2_pro_text_to_video":
        return {
            "fields": [
                {
                    "name": "prompt",
                    "type": "textarea",
                    "label": _compose_bilingual_label("提示词", "Prompt"),
                    "placeholder": _compose_bilingual_label("描述镜头、运动与氛围", "Describe shots, movement and mood"),
                    "required": True,
                },
                {
                    "name": "image_url",
                    "type": "image",
                    "label": _compose_bilingual_label("参考图（可选）", "Reference Image (Optional)"),
                    "description": _compose_bilingual_label(
                        "可选：上传/填写 1 张参考图，用于更贴近预期的镜头风格。",
                        "Optional: upload/provide a reference image to guide the style.",
                    ),
                },
                {
                    "name": "aspect_ratio",
                    "type": "select",
                    "label": _compose_bilingual_label("画幅", "Aspect Ratio"),
                    "options": ["portrait", "landscape"],
                    "default": "landscape",
                },
                {
                    "name": "n_frames",
                    "type": "select",
                    "label": _compose_bilingual_label("帧数", "Frames"),
                    "options": ["10", "15"],
                    "default": "10",
                },
                {
                    "name": "size",
                    "type": "select",
                    "label": _compose_bilingual_label("清晰度", "Quality"),
                    "options": ["standard", "high"],
                    "default": "high",
                },
                {
                    "name": "remove_watermark",
                    "type": "switch",
                    "label": _compose_bilingual_label("移除水印", "Remove Watermark"),
                },
                {
                    "name": "character_ids",
                    "type": "textarea",
                    "label": _compose_bilingual_label("角色 ID 列表", "Character IDs"),
                    "description": _compose_bilingual_label("可选，每行一个角色 ID。", "Optional; one character ID per line."),
                },
                {
                    "name": "image_urls",
                    "type": "textarea",
                    "label": _compose_bilingual_label("参考图 URL 列表（可选）", "Reference Image URLs (optional)"),
                    "description": _compose_bilingual_label(
                        "每行一个图像 URL，如提供将作为风格/角色参考。",
                        "One URL per line. When provided, images will be used as style/character references.",
                    ),
                },
                {
                    "name": "callBackUrl",
                    "type": "text",
                    "label": _compose_bilingual_label("回调地址", "Callback URL"),
                },
            ]
        }
    return {"fields": []}


def _kie_metadata(
    *,
    capability_key: str,
    endpoint: str,
    api_type: str,
    model_id: str,
    requires_image_input: bool,
    input_array_target: str | None = None,
    supports_vision: bool | None = None,
    auto_fill_size: bool | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "executor_type": "kie",
        "executor_tag": "kie_market",
        "api_type": api_type,
        "model_id": model_id,
        "request_endpoint": endpoint,
        # Bump when changing built-in KIE schemas/metadata/defaults so ability_seed can refresh DB rows.
        "seed_version": 6,
    }
    if requires_image_input:
        metadata["requires_image_input"] = True
        metadata["supports_vision"] = True
    elif supports_vision:
        metadata["supports_vision"] = True
    if input_array_target:
        metadata["input_array_target"] = input_array_target
    if auto_fill_size is not None:
        metadata["auto_fill_size"] = auto_fill_size
    return metadata


_DOUBAO_SEEDREAM_45_DEFAULTS: dict[str, Any] = {
    "model": "doubao-seedream-4-5-251128",
    "response_format": "url",
    "size": "2K",
    "watermark": True,
    "stream": False,
}

_DOUBAO_SEEDREAM_40_DEFAULTS: dict[str, Any] = {
    # NOTE: Model IDs vary by account entitlements.
    "model": "doubao-seedream-4-0-250828",
    "response_format": "url",
    "size": "1K",
    "watermark": True,
    "stream": False,
}


class AbilityDefinition(TypedDict, total=False):
    endpoint: str
    defaults: dict[str, Any]
    display_name: str
    description: str
    category: str
    input_schema: dict[str, Any]
    metadata: dict[str, Any]


OPENAI_IMAGE_ABILITIES: dict[str, AbilityDefinition] = {
    "gpt_image_2_generate": {
        "endpoint": "/v1/images/generations",
        "defaults": {
            "model": "gpt-image-2",
            "size": "1024x1024",
            "quality": "auto",
            "background": "auto",
            "output_format": "png",
            "n": 1,
        },
        "display_name": "OpenAI · GPT Image 2 文生图",
        "description": "OpenAI GPT Image 2 官方文生图能力；经 vendor-api-ops 统一代理、Key 管理和结果落库。",
        "category": "image_generation",
        "input_schema": _openai_image_generation_schema(),
        "metadata": _openai_metadata(model_id="gpt-image-2", api_type="image_generation", seed_version=1),
    },
    "gpt_image_2_edit": {
        "endpoint": "/v1/images/edits",
        "defaults": {
            "model": "gpt-image-2",
            "size": "auto",
            "quality": "auto",
            "background": "auto",
            "output_format": "png",
            "n": 1,
        },
        "display_name": "OpenAI · GPT Image 2 图片编辑",
        "description": "支持原图、蒙版、多参考图的图片编辑能力；经 vendor-api-ops 统一代理和落库。",
        "category": "image_generation",
        "input_schema": _openai_image_edit_schema(),
        "metadata": _openai_metadata(model_id="gpt-image-2", api_type="image_edit", seed_version=3),
    },
}


VL_ABILITIES: dict[str, AbilityDefinition] = {
    "analyze_image": {
        "defaults": {
            "provider": "volcengine_vl",
        },
        "display_name": "VL · 图像结构化分析",
        "description": "统一图像理解原子能力，输出商品/图案分析 JSON，可服务裂变、扩图、MCP、技能和业务 API。",
        "category": "vision_language",
        "input_schema": _vl_analyze_image_schema(),
        "metadata": _vl_metadata(seed_version=2),
    },
    "fission_control_card": {
        "defaults": {
            "provider": "volcengine_vl",
            "prompt": FISSION_CONTROL_CARD_VL_PROMPT,
        },
        "display_name": "VL · 图裂变控制卡",
        "description": "统一的图裂变前置 VL 组件，输出 prompt_main、prompt_control 和控制卡，供 ComfyUI/商业模型裂变复用。",
        "category": "vision_language",
        "input_schema": _vl_fission_control_card_schema(),
        "metadata": _vl_fission_control_card_metadata(seed_version=5),
    },
    "fission_generated_image_evaluate": {
        "defaults": {
            "provider": "coze_eval",
            "coze_workflow_id": "7632187670952673280",
        },
        "display_name": "VL · 裂变生成图评估",
        "description": "单独评估裂变生成图质量和逻辑合理性，输出 pass / needs_refission / reject，业务侧自行决定是否二次裂变。",
        "category": "image_quality_evaluation",
        "input_schema": _vl_generated_image_evaluation_schema(),
        "metadata": _vl_generated_image_evaluation_metadata(seed_version=1),
    },
}


BAIDU_IMAGE_ABILITIES: dict[str, AbilityDefinition] = {
    "quality_upgrade": {
        "endpoint": "/rest/2.0/image-process/v1/image_quality_enhance",
        "defaults": {"resolution": "2k", "type": "auto"},
        "display_name": "百度 · 无损放大",
        "description": "无损放大（2K/4K，可配置分辨率与超分类型）。",
        "category": "image_process",
        "input_schema": _baidu_image_schema(
            include_resolution=True,
            resolution_default="2k",
            include_type=True,
            type_default="auto",
            type_options=["auto", "clarity", "detail", "texture"],
        ),
        "metadata": _baidu_metadata("quality_upgrade", "/rest/2.0/image-process/v1/image_quality_enhance")
        | {
            "presentation": _presentation(
                name="AI超清",
                summary="把现有结果收口成更清晰、更适合交付或详情页展示的终稿。",
                form_intro="上传图片后，选择更偏整体清晰度还是局部细节增强。",
                expected_output="产出高清图，可继续用于详情页、终稿下载或细节展示。",
                surfaces={"client": True, "coze": True, "admin": True, "eval": True},
                fields={
                    "resolution": _presentation_field(
                        label="输出清晰度",
                        description="选择本次要增强到的清晰度级别。",
                    ),
                    "type": _presentation_field(
                        label="增强重点",
                        description="选择更偏整体清晰度、局部细节还是纹理表现。",
                    ),
                },
            )
        },
    },
    "colourize": {
        "endpoint": "/rest/2.0/image-process/v1/colourize",
        "defaults": {},
        "display_name": "百度 · 老照片上色",
        "description": "为黑白照片自动着色，适合法制、历史修复场景。",
        "category": "image_process",
        "input_schema": _baidu_image_schema(),
        "metadata": _baidu_metadata("colourize", "/rest/2.0/image-process/v1/colourize"),
    },
    "remove_moire": {
        "endpoint": "/rest/2.0/image-process/v1/remove_moire",
        "defaults": {},
        "display_name": "百度 · 摩尔纹去除",
        "description": "检测并去除摩尔纹、条纹等噪声。",
        "category": "image_process",
        "input_schema": _baidu_image_schema(),
        "metadata": _baidu_metadata("remove_moire", "/rest/2.0/image-process/v1/remove_moire"),
    },
    "stretch_restore": {
        "endpoint": "/rest/2.0/image-process/v1/stretch_restore",
        "defaults": {},
        "display_name": "百度 · 拉伸修复",
        "description": "修复被拉伸变形的人像或场景。",
        "category": "image_process",
        "input_schema": _baidu_image_schema(),
        "metadata": _baidu_metadata("stretch_restore", "/rest/2.0/image-process/v1/stretch_restore"),
    },
    "dehaze": {
        "endpoint": "/rest/2.0/image-process/v1/dehaze",
        "defaults": {},
        "display_name": "百度 · 去雾增强",
        "description": "清除雾霾、烟尘造成的灰暗画面。",
        "category": "image_process",
        "input_schema": _baidu_image_schema(),
        "metadata": _baidu_metadata("dehaze", "/rest/2.0/image-process/v1/dehaze"),
    },
    "contrast_enhance": {
        "endpoint": "/rest/2.0/image-process/v1/contrast_enhance",
        "defaults": {},
        "display_name": "百度 · 对比度增强",
        "description": "自动提升对比度与明暗层次。",
        "category": "image_process",
        "input_schema": _baidu_image_schema(),
        "metadata": _baidu_metadata("contrast_enhance", "/rest/2.0/image-process/v1/contrast_enhance"),
    },
    "denoise": {
        "endpoint": "/rest/2.0/image-process/v1/denoise",
        "defaults": {},
        "display_name": "百度 · 去噪净化",
        "description": "降低图像噪点，突出主体细节。",
        "category": "image_process",
        "input_schema": _baidu_image_schema(),
        "metadata": _baidu_metadata("denoise", "/rest/2.0/image-process/v1/denoise"),
    },
}


VOLCENGINE_LLM_ABILITIES: dict[str, AbilityDefinition] = {
    "doubao_seed_2_0_lite": {
        "endpoint": "/api/v3/chat/completions",
        "defaults": {
            "model": DEFAULT_VOLCENGINE_VL_MODEL_ID,
            "stream": False,
        },
        "display_name": "火山 · Doubao-Seed-2.0-lite VL",
        "description": "当前统一 VL 底层模型，服务图像结构化分析、图裂变控制卡和后续业务编排。",
        "category": "vision_language",
        "input_schema": _volcengine_llm_schema(),
        "metadata": _volcengine_metadata(
            endpoint="/api/v3/chat/completions",
            model_id=DEFAULT_VOLCENGINE_VL_MODEL_ID,
            api_type="chat_completions",
            supports_vision=True,
            reference="https://ark.cn-beijing.volces.com/api/v3/models",
            seed_version=1,
        )
        | {
            "presentation": _presentation(
                name="Doubao-Seed-2.0-lite VL",
                summary="中台默认图像理解底层模型，所有依赖 VL 组件的业务优先走这里。",
                form_intro="上传图片并填写分析要求，返回可给裂变、扩图、审核继续使用的结构化文本。",
                expected_output="返回一段结构化 JSON 文本。",
                surfaces={"client": False, "coze": True, "admin": True, "eval": False},
            )
        },
    },
    "doubao_seed_1_8": {
        "endpoint": "/api/v3/chat/completions",
        "defaults": {
            "model": "doubao-seed-1-8-251228",
            "stream": False,
        },
        "display_name": "火山 · Doubao Seed 1.8 VL",
        "description": "多模态对话模型，支持图文输入，可执行视觉问答、创作指令等。",
        "category": "text_generation",
        "input_schema": _volcengine_llm_schema(),
        "metadata": _volcengine_metadata(
            endpoint="/api/v3/chat/completions",
            model_id="doubao-seed-1-8-251228",
            api_type="chat_completions",
            supports_vision=True,
            reference="https://www.volcengine.com/docs/82379/1399008",
            seed_version=1,
        ),
    },
    "doubao_seed_1_6_lite": {
        "endpoint": "/api/v3/chat/completions",
        "defaults": {
            "model": "doubao-seed-1-6-lite-251015",
            "stream": False,
            "reasoning_effort": "medium",
            "max_completion_tokens": 2048,
        },
        "display_name": "火山 · Doubao Seed 1.6 Lite",
        "description": "更轻量的多模态大模型，速度快、成本低，适合日常图文问答/辅助。",
        "category": "text_generation",
        "input_schema": _volcengine_llm_schema(),
        "metadata": _volcengine_metadata(
            endpoint="/api/v3/chat/completions",
            model_id="doubao-seed-1-6-lite-251015",
            api_type="chat_completions",
            supports_vision=True,
            reference="https://www.volcengine.com/docs/82379/1399008",
            seed_version=1,
        ),
    },
}


VOLCENGINE_IMAGE_ABILITIES: dict[str, AbilityDefinition] = {
    "doubao_seedream_4_5": {
        "endpoint": "/api/v3/images/generations",
        "defaults": _DOUBAO_SEEDREAM_45_DEFAULTS,
        "display_name": "火山 · Doubao Seedream 4.5",
        "description": "文生图模型，支持 2K 输出并可选 sequential/watermark 配置。",
        "category": "image_generation",
        "input_schema": _volcengine_image_schema(
            _DOUBAO_SEEDREAM_45_DEFAULTS,
            size_options=[
                {"label": "2K · 2048x2048", "value": "2K"},
                {"label": "4K · 4096x4096", "value": "4K"},
            ],
            include_n=False,
        ),
        "metadata": _volcengine_metadata(
            endpoint="/api/v3/images/generations",
            model_id="doubao-seedream-4-5-251128",
            api_type="image_generation",
            supports_vision=True,
            reference="https://www.volcengine.com/docs/82379/1541523",
            seed_version=10,
        )
        | {
            "presentation": _presentation(
                name="以文生款",
                summary="从一句设计意图快速生成可讨论的新款方向。",
                form_intro="先描述款式、面料、风格和场景，不必写成技术提示词。",
                expected_output="产出 1 张新款方向图，可继续改款、提取图案或转入商拍。",
                surfaces={"client": True, "coze": False, "admin": True, "eval": True},
                fields={
                    "prompt": _presentation_field(
                        label="设计说明",
                        placeholder="例如：米白亚麻长裙，植物印花，轻复古，高级成衣质感。",
                        description="先写想做的款式、风格、面料和场景。",
                    ),
                    "negative_prompt": _presentation_field(
                        label="不想出现的元素",
                        description="可选：补充不希望出现的元素、风格或画面问题。",
                        advanced=True,
                    ),
                    "image_urls": _presentation_field(
                        label="参考图（可选）",
                        description="可选：每行一张参考图，用来约束风格或结构。",
                        advanced=True,
                    ),
                    "sequential_image_generation": _presentation_field(
                        label="生成策略",
                        description="高级设置：只有需要一组方向图时再开启。",
                        advanced=True,
                    ),
                    "max_images": _presentation_field(
                        label="生成张数",
                        description="高级设置：控制一组方向图的数量。",
                        advanced=True,
                    ),
                    "size": _presentation_field(label="出图尺寸"),
                    "width": _presentation_field(label="自定义宽度", advanced=True),
                    "height": _presentation_field(label="自定义高度", advanced=True),
                    "response_format": _presentation_field(label="返回格式", advanced=True),
                },
            )
        },
    },
    "doubao_seedream_4_0": {
        "endpoint": "/api/v3/images/generations",
        "defaults": _DOUBAO_SEEDREAM_40_DEFAULTS,
        "display_name": "火山 · Doubao Seedream 4.0",
        "description": "性价比更高的文生图模型，适合预算敏感场景。",
        "category": "image_generation",
        "input_schema": _volcengine_image_schema(_DOUBAO_SEEDREAM_40_DEFAULTS, include_n=False),
        "metadata": _volcengine_metadata(
            endpoint="/api/v3/images/generations",
            model_id="doubao-seedream-4-0-250828",
            api_type="image_generation",
            supports_vision=True,
            reference="https://www.volcengine.com/docs/82379/1541523",
            seed_version=10,
        ),
    },
}

VOLCENGINE_VIDEO_ABILITIES: dict[str, AbilityDefinition] = {
    "doubao_seedance_1_5_pro": {
        "endpoint": "/api/v3/contents/generations/tasks",
        "defaults": {
            "model": "doubao-seedance-1-5-pro-251215",
            "stream": False,
        },
        "display_name": "火山 · Doubao Seedance 1.5 Pro",
        "description": "图生视频模型，可输入提示词与参考图生成 5s 动画，支持水印/固定机位参数。",
        "category": "video_generation",
        "input_schema": _volcengine_video_schema(),
        "metadata": _volcengine_metadata(
            endpoint="/api/v3/contents/generations/tasks",
            model_id="doubao-seedance-1-5-pro-251215",
            api_type="video_generation",
            supports_vision=True,
            reference="https://www.volcengine.com/docs/82379/1520757",
            seed_version=1,
        )
        | {
            "presentation": _presentation(
                name="图生视频",
                summary="把已验证的静态图延展成动销短视频。",
                form_intro="描述镜头运动、人物动作或画面节奏，不必关心模型参数。",
                expected_output="产出短视频，可回到素材中心继续沉淀和复用。",
                surfaces={"client": True, "coze": False, "admin": True, "eval": True},
                fields={
                    "prompt": _presentation_field(
                        label="视频说明",
                        placeholder="例如：模特轻微转身，镜头平稳推进，保持服装纹理稳定。",
                        description="写清镜头、动作和节奏感。",
                    ),
                    "image_url": _presentation_field(
                        label="参考图（可选）",
                        description="可选：放一张参考图，让视频更贴近已有主图风格。",
                    ),
                    "duration": _presentation_field(label="视频时长"),
                    "camera_fixed": _presentation_field(label="固定镜头", advanced=True),
                    "watermark": _presentation_field(label="水印", advanced=True),
                },
            )
        },
    },
}


KIE_MARKET_ABILITIES: dict[str, AbilityDefinition] = {
    "nano_banana_pro_image_to_image": {
        "endpoint": "/api/v1/jobs/createTask",
        "defaults": {
            "model": "nano-banana-pro",
            "output_format": "png",
        },
        "display_name": "KIE · Nano Banana Pro 图生图",
        "description": "Google Nano Banana Pro 模型，支持多参考图进行图生图或风格迁移，最高 4K 输出。",
        "category": "image_generation",
        "input_schema": _build_kie_schema("nano_banana_pro_image_to_image"),
        "metadata": _kie_metadata(
            capability_key="nano_banana_pro_image_to_image",
            endpoint="/api/v1/jobs/createTask",
            api_type="market_image_to_image",
            model_id="nano-banana-pro",
            requires_image_input=True,
            input_array_target="image_input",
            supports_vision=True,
            auto_fill_size=True,
        )
        | {
            "pricing": {
                "currency": "USD",
                "unit": "per_image",
                "list_price": 0.04,
                "discount_price": 0.04,
            },
            "pricing_tiers": [
                {"label": "1K", "price": 0.04},
                {"label": "2K", "price": 0.04},
                {"label": "4K", "price": 0.07},
            ],
            "presentation": _presentation(
                name="以款生款",
                summary="围绕参考款快速做改款和方向延展。",
                form_intro="说明哪些部分要保留，哪些部分想变化。",
                expected_output="产出同风格变体，可继续进入套图或图案整理。",
                surfaces={"client": True, "coze": True, "admin": True, "eval": True},
                fields={
                    "image_url": _presentation_field(
                        label="参考款",
                        description="上传一张本次要延展的参考款图片。",
                    ),
                    "prompt": _presentation_field(
                        label="改款说明",
                        placeholder="例如：保留廓形和面料质感，把领型改得更利落，整体更偏轻复古。",
                        description="写清这次想保留什么、变化什么。",
                    ),
                    "image_urls": _presentation_field(
                        label="补充参考图（可选）",
                        description="可选：每行一张补充参考图，帮助约束风格、工艺或局部细节。",
                        advanced=True,
                    ),
                    "aspect_ratio": _presentation_field(label="出图比例"),
                    "resolution": _presentation_field(label="清晰度"),
                    "output_format": _presentation_field(label="输出格式", advanced=True),
                    "callBackUrl": _presentation_field(label="回调地址", advanced=True),
                },
            ),
        },
    },
    "flux2_pro_image_to_image": {
        "endpoint": "/api/v1/jobs/createTask",
        "defaults": {
            "model": "flux-2/pro-image-to-image",
        },
        "display_name": "KIE · Flux-2 Pro 图生图",
        "description": "Flux-2 专业版，要求 1-8 张参考图，支持 auto 比例匹配，适合高精图像编辑。",
        "category": "image_generation",
        "input_schema": _build_kie_schema("flux2_pro_image_to_image"),
        "metadata": _kie_metadata(
            capability_key="flux2_pro_image_to_image",
            endpoint="/api/v1/jobs/createTask",
            api_type="market_image_to_image",
            model_id="flux-2/pro-image-to-image",
            requires_image_input=True,
            input_array_target="input_urls",
        )
        | {
            "pricing": {
                "currency": "USD",
                "unit": "per_image",
                "list_price": 0.025,
                "discount_price": 0.025,
            },
            "pricing_tiers": [
                {"label": "1K", "price": 0.025},
                {"label": "2K", "price": 0.035},
            ],
        },
    },
    "nano_banana_2_image_to_image": {
        "endpoint": "/api/v1/jobs/createTask",
        "defaults": {
            "model": "nano-banana-2",
            "output_format": "jpg",
            "google_search": False,
        },
        "display_name": "KIE · Nano Banana 2 图生图",
        "description": "Nano Banana 2 图生图，支持更多参考图输入与多分辨率输出。",
        "category": "image_generation",
        "input_schema": _build_kie_schema("nano_banana_2_image_to_image"),
        "metadata": _kie_metadata(
            capability_key="nano_banana_2_image_to_image",
            endpoint="/api/v1/jobs/createTask",
            api_type="market_image_to_image",
            model_id="nano-banana-2",
            requires_image_input=True,
            input_array_target="image_input",
            supports_vision=True,
            auto_fill_size=True,
        )
        | {
            "pricing": {
                "currency": "USD",
                "unit": "per_image",
                "list_price": 0.04,
                "discount_price": 0.04,
            },
            "pricing_tiers": [
                {"label": "1K", "price": 0.04},
                {"label": "2K", "price": 0.04},
                {"label": "4K", "price": 0.07},
            ],
            "presentation": _presentation(
                name="参考图延展",
                summary="围绕已有图快速延展成更多展示场景。",
                form_intro="先说明想保留什么、想变化什么，以及最终想把结果用在哪里。",
                expected_output="按具体动作生成营销图、展示图或上身图。",
                surfaces={"client": True, "coze": True, "admin": True, "eval": True},
                fields={
                    "image_url": _presentation_field(
                        label="主图",
                        description="上传这次要延展的主图。",
                    ),
                    "prompt": _presentation_field(
                        label="编辑说明",
                        placeholder="例如：保持主体不变，替换背景为更高级的电商棚拍场景。",
                        description="写清要保留什么、变化什么、想呈现什么结果。",
                    ),
                    "image_urls": _presentation_field(
                        label="补充参考图（可选）",
                        description="可选：每行一张补充参考图，用来约束背景、姿态或搭配风格。",
                    ),
                    "aspect_ratio": _presentation_field(label="出图比例"),
                    "resolution": _presentation_field(label="清晰度"),
                    "google_search": _presentation_field(label="联网增强", advanced=True),
                    "output_format": _presentation_field(label="输出格式", advanced=True),
                    "callBackUrl": _presentation_field(label="回调地址", advanced=True),
                },
            ),
        },
    },
    "sora2_pro_text_to_video": {
        "endpoint": "/api/v1/jobs/createTask",
        "defaults": {
            "model": "sora-2-pro-text-to-video",
            "aspect_ratio": "landscape",
            "n_frames": "10",
            "size": "high",
            "remove_watermark": False,
        },
        "display_name": "KIE · Sora2 Pro 文生视频",
        "description": "Sora 2 Pro 文生视频模型，支持 10/15 帧品质，并可选角色动画列表。",
        "category": "video_generation",
        "input_schema": _build_kie_schema("sora2_pro_text_to_video"),
        "metadata": _kie_metadata(
            capability_key="sora2_pro_text_to_video",
            endpoint="/api/v1/jobs/createTask",
            api_type="market_text_to_video",
            model_id="sora-2-pro-text-to-video",
            requires_image_input=False,
            input_array_target="image_input",
            supports_vision=True,
        )
        | {
            "pricing": {
                "currency": "USD",
                "unit": "per_video",
                "list_price": 0.375,
                "discount_price": 0.375,
            },
            "pricing_tiers": [
                {"label": "10s", "price": 0.375},
                {"label": "15-25s", "price": 0.675},
            ],
        },
    },
}

COMFYUI_ABILITIES: dict[str, AbilityDefinition] = {
    "sifang_lianxu": {
        "defaults": {
            "workflow_key": "sifang_lianxu",
            "patternType": "seamless",
            "width": 1024,
            "height": 1024,
            "timeout": 900,
        },
        "display_name": "ComfyUI · 四方连续",
        "description": "将输入图转为可四方连续拼接的纹理，自动结合图像理解提示词与自定义 prompt。",
        "category": "image_generation",
        "input_schema": _comfyui_seamless_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "sifang_lianxu",
            "action": "seamless",
            "requires_image_input": True,
            "supports_vision": True,
            # Only keep final outputs from the known "SaveImage" node for this workflow.
            # Otherwise ComfyUI history may contain multiple intermediate previews.
            "output_node_ids": ["111"],
            # Route across both ComfyUI nodes (same plugin/model baseline).
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 9,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.5,
                "discount_price": 0.3,
            },
            "presentation": _presentation(
                name="四方连续",
                summary="让图案变成可连续铺陈的面料纹理。",
                form_intro="上传图案后，说明边缘是否要更自然、主花是否要保留。",
                expected_output="产出连续纹理，可继续做配色、工艺表达或营销展示。",
                surfaces={"client": True, "coze": False, "admin": True, "eval": True},
                fields={
                    "patternType": _presentation_field(label="连续方式"),
                    "image_url": _presentation_field(
                        label="图案原图",
                        description="上传要做连续化的图案原图。",
                    ),
                    "width": _presentation_field(label="输出宽度"),
                    "height": _presentation_field(label="输出高度"),
                },
            ),
        },
    },
    "yinhua_tiqu": {
        "defaults": {
            "workflow_key": "yinhua_tiqu",
            "timeout": 420,
            "width": 1800,
            "height": 1800,
            "lora": "杯子1124.safetensors",
            "prompt": PATTERN_EXTRACT_POSITIVE_DEFAULT,
            "negative_prompt": PATTERN_EXTRACT_NEGATIVE_DEFAULT,
            "batch": 1,
        },
        "display_name": "ComfyUI · 印花提取",
        "description": "基于 Qwen Image Edit 与印花 LoRA，将实物照片中的装饰纹样智能抠取成纯净的设计稿，可直接用于印刷或再创作。",
        "category": "image_generation",
        "input_schema": _comfyui_pattern_extract_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "yinhua_tiqu",
            "action": "pattern_extract",
            "requires_image_input": True,
            "supports_vision": True,
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 7,
            "lora_presets": PATTERN_EXTRACT_LORA_PRESETS,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.5,
                "discount_price": 0.3,
            },
            "presentation": _presentation(
                name="图案提取",
                summary="把实拍图中的花型或纹样整理成可复用的干净设计稿。",
                form_intro="上传原图后，只补充是否需要更干净、更完整或更适合连续化。",
                expected_output="产出干净花型稿，可继续做四方连续或清晰度增强。",
                surfaces={"client": True, "coze": True, "admin": True, "eval": True},
                fields={
                    "image_url": _presentation_field(
                        label="原图",
                        description="上传这次要提取花型或纹样的原图。",
                    ),
                    "prompt": _presentation_field(
                        label="提取要求",
                        description="可选：补充这次提取更关注的清理方向或保留重点。",
                    ),
                    "negative_prompt": _presentation_field(
                        label="不要出现的内容",
                        advanced=True,
                    ),
                    "width": _presentation_field(label="输出宽度"),
                    "height": _presentation_field(label="输出高度"),
                    "batch": _presentation_field(label="生成张数", advanced=True),
                    "lora": _presentation_field(label="LoRA 方案", advanced=True),
                },
            ),
        },
    },
    "yinhua_tiqu_lora_8step": {
        "defaults": {
            "workflow_key": "yinhua_tiqu_lora_8step",
            "timeout": 420,
            "lora": "杯子1124.safetensors",
            "prompt": PATTERN_EXTRACT_POSITIVE_DEFAULT,
            "negative_prompt": PATTERN_EXTRACT_NEGATIVE_DEFAULT,
            "batch": 1,
        },
        "display_name": "ComfyUI · 8步加速可换LoRA",
        "description": "基于印花提取同款工作流单独封装的 8 步加速工具，支持独立更换效果 LoRA，并单独统计 Coze 业务使用量。",
        "category": "image_generation",
        "input_schema": _comfyui_pattern_extract_lora_8step_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "yinhua_tiqu_lora_8step",
            "action": "pattern_extract",
            "requires_image_input": True,
            "supports_vision": True,
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 4,
            "lora_presets": PATTERN_EXTRACT_LORA_PRESETS,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.5,
                "discount_price": 0.3,
            },
        },
    },
    "beijing_koutu": {
        "defaults": {
            "workflow_key": "beijing_koutu",
            "timeout": 240,
        },
        "display_name": "ComfyUI · 背景抠图",
        "description": "输入图片 URL，移除主体背景，输出最终抠图结果。",
        "category": "image_generation",
        "input_schema": _comfyui_background_remove_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "beijing_koutu",
            "action": "background_remove",
            "requires_image_input": True,
            "supports_vision": True,
            "output_node_ids": ["4"],
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 2,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.2,
                "discount_price": 0.1,
            },
        },
    },
    "toubu_kouxiang": {
        "defaults": {
            "workflow_key": "toubu_kouxiang",
            "timeout": 300,
        },
        "display_name": "ComfyUI · 头部抠像",
        "description": "输入图片 URL，提取完整头部与人脸区域，输出最终抠像结果。",
        "category": "image_generation",
        "input_schema": _comfyui_head_extract_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "toubu_kouxiang",
            "action": "head_extract",
            "requires_image_input": True,
            "supports_vision": True,
            "output_node_ids": ["140"],
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 2,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.25,
                "discount_price": 0.15,
            },
        },
    },
    "flux2_9b_liebian_sifang": {
        "defaults": {
            "workflow_key": "flux2_9b_liebian_sifang",
            "timeout": 420,
        },
        "display_name": "ComfyUI · FLUX2裂变+四方",
        "description": "输入图片 URL 与主提示词，走 FLUX2-9b 裂变+四方 workflow，输出最终拼缝结果。",
        "category": "image_generation",
        "input_schema": _comfyui_flux2_9b_liebian_sifang_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "flux2_9b_liebian_sifang",
            "action": "image_fission",
            "requires_image_input": True,
            "supports_vision": True,
            "output_node_ids": ["111"],
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 1,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35,
            },
            "presentation": _presentation(
                name="AI扩图",
                summary="在不破坏原有风格的前提下延展画布和边缘。",
                form_intro="说明向哪个方向扩、希望保持什么风格。",
                expected_output="产出更完整画面，可继续做 AI 超清或营销套图。",
                surfaces={"client": True, "coze": False, "admin": True, "eval": True},
                fields={
                    "image_url": _presentation_field(
                        label="原图",
                        description="上传这次要扩展边缘的原图。",
                    ),
                    "prompt": _presentation_field(
                        label="扩图说明",
                        description="可选：补充扩展方向、风格和边缘要求。",
                    ),
                    "expand_left": _presentation_field(label="左侧扩展"),
                    "expand_right": _presentation_field(label="右侧扩展"),
                    "expand_top": _presentation_field(label="上侧扩展"),
                    "expand_bottom": _presentation_field(label="下侧扩展"),
                },
            ),
        },
    },
    "qwen2512_print_shape_text_enhance": {
        "defaults": {
            "workflow_key": "qwen2512_print_shape_text_enhance",
            "timeout": 420,
            "steps": 8,
            "cfg": 1.0,
        },
        "display_name": "ComfyUI · 裂变文字强化",
        "description": "输入图片 URL、文字强化提示词和相似度，走 Qwen2512 图像形状强化 workflow，输出最终强化结果。",
        "category": "image_generation",
        "input_schema": _comfyui_qwen2512_print_shape_text_enhance_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "qwen2512_print_shape_text_enhance",
            "action": "image_fission",
            "requires_image_input": True,
            "supports_vision": True,
            "output_node_ids": ["29"],
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 1,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35,
            },
            "presentation": _presentation(
                name="融合创款",
                summary="把多张参考图的轮廓、花型、配色融合成一个新方向。",
                form_intro="分别准备结构、风格、花型或配色参考图，再说明融合重点。",
                expected_output="产出 1 张融合方向图，可继续改款或做图案整理。",
                surfaces={"client": True, "coze": True, "admin": True, "eval": True},
                fields={
                    "image_url": _presentation_field(label="主参考图"),
                    "image_url_2": _presentation_field(label="参考图 2"),
                    "image_url_3": _presentation_field(label="参考图 3"),
                    "prompt": _presentation_field(
                        label="融合要求",
                        placeholder="例如：保留图一轮廓、图二印花、图三配色，整体更偏高级成衣质感。",
                    ),
                    "width": _presentation_field(label="输出宽度", advanced=True),
                    "height": _presentation_field(label="输出高度", advanced=True),
                    "negative_prompt": _presentation_field(label="不要出现的内容", advanced=True),
                    "seed": _presentation_field(label="随机种子", advanced=True),
                },
            ),
        },
    },
    "huawen_kuotu": {
        "defaults": {
            "workflow_key": "huawen_kuotu",
            "timeout": 420,
            "expand_left": 200,
            "expand_right": 200,
            "expand_top": 0,
            "expand_bottom": 0,
            "feathering": 24,
            "mask_expand": 20,
            "size": 720,
            "prompt": "8k, 最佳质量，将输入图像左右两侧进行自然无缝延伸，保持风格一致，延续背景，禁止新增元素。",
            "negative_prompt": "solid color, text, watermark, extra objects, low quality, blurry",
            "lora_name": "Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors",
        },
        "display_name": "ComfyUI · 花纹扩图",
        "description": "在保持原图风格的前提下向左右（或其他方向）延展布料/壁纸图案，适合做无缝扩展或画布补边。",
        "category": "image_generation",
        "input_schema": _comfyui_pattern_expand_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "huawen_kuotu",
            "action": "pattern_expand",
            "requires_image_input": True,
            "supports_vision": True,
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 5,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35,
            },
        },
    },
    "flux2_klein_9b_outpaint": {
        "defaults": {
            "workflow_key": "flux2_klein_9b_outpaint",
            "timeout": 420,
            "expand_left": 408,
            "expand_right": 408,
            "expand_top": 0,
            "expand_bottom": 0,
        },
        "display_name": "ComfyUI · FLUX2-Klein 扩图",
        "description": "使用 FLUX2-Klein 9b 扩图 workflow 做画布外延与边缘补全，适合做更自然的左右/上下扩边。",
        "category": "image_generation",
        "input_schema": _comfyui_flux2_klein_9b_outpaint_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "flux2_klein_9b_outpaint",
            "action": "outpaint",
            "requires_image_input": True,
            "supports_vision": True,
            "output_node_ids": ["9"],
            "allowed_executor_ids": ["executor_comfyui_pattern_extract_158", "executor_comfyui_seamless_117"],
            "routing_policy": "queue",
            "seed_version": 5,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35,
            },
            "presentation": _presentation(
                name="FLUX2 扩图",
                summary="用 FLUX2-Klein 模型做更自然的边缘延展与画布补全。",
                form_intro="上传原图，再说明向哪个方向扩、希望保持什么边缘与风格规律。",
                expected_output="产出 1 张扩图结果，可继续做 AI 超清、营销套图或终稿交付。",
                surfaces={"client": False, "coze": True, "admin": True, "eval": True},
                fields={
                    "image_url": _presentation_field(
                        label="原图",
                        description="上传这次要向外延展的原图。",
                    ),
                    "expand_left": _presentation_field(label="左侧扩展"),
                    "expand_right": _presentation_field(label="右侧扩展"),
                    "expand_top": _presentation_field(label="上侧扩展"),
                    "expand_bottom": _presentation_field(label="下侧扩展"),
                },
            ),
        },
    },
    "jisu_chuli": {
        "defaults": {
            "workflow_key": "jisu_chuli",
            "timeout": 300,
            "batch": 1,
        },
        "display_name": "ComfyUI · 极速处理版",
        "description": "极速图生图编辑：上传图片，配置正/反提示词，支持批次与输出尺寸（默认原图大小）。",
        "category": "image_generation",
        "input_schema": _comfyui_jisu_chuli_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "jisu_chuli",
            "action": "image_edit_fast",
            "requires_image_input": True,
            "supports_vision": True,
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 5,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.4,
                "discount_price": 0.25
            }
        },
    },
    "zhongsu_tisheng": {
        "defaults": {
            "workflow_key": "zhongsu_tisheng",
            "timeout": 420,
            "batch": 1,
        },
        "display_name": "ComfyUI · 中速提质版",
        "description": "中速质量提升：8 steps（更精细），上传图片，配置正/反提示词，支持批次与输出尺寸（默认原图大小）。",
        "category": "image_generation",
        "input_schema": _comfyui_jisu_chuli_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "zhongsu_tisheng",
            "action": "image_edit_medium",
            "requires_image_input": True,
            "supports_vision": True,
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 5,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35
            }
        },
    },
    "duotu_ronghe": {
        "defaults": {
            "workflow_key": "duotu_ronghe",
            "timeout": 360,
        },
        "display_name": "ComfyUI · 多图融合",
        "description": "输入 2~3 张图片，基于 Qwen Image Edit / Flux Kontext 做多图融合，输出 1 张融合图。",
        "category": "image_generation",
        "input_schema": _comfyui_multi_image_fusion_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "duotu_ronghe",
            "action": "multi_image_fusion",
            "requires_image_input": True,
            "supports_vision": True,
            "allowed_executor_ids": ["executor_comfyui_pattern_extract_158", "executor_comfyui_seamless_117"],
            "routing_policy": "queue",
            "seed_version": 4,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35,
            },
        },
    },
    "e7_flux2_liebian": {
        "defaults": {
            "workflow_key": "e7_flux2_liebian",
            "timeout": 420,
            "steps": 8,
            "cfg": 1.0,
            "batch_size": 1,
        },
        "display_name": "ComfyUI · E7裂变重绘",
        "description": "基于 E7 + FLUX2 的裂变重绘工作流。输入参考图与单文本裂变提示词，支持重绘幅度、输出尺寸与批次。",
        "category": "image_generation",
        "input_schema": _comfyui_e7_flux2_liebian_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "e7_flux2_liebian",
            "action": "image_fission",
            "requires_image_input": True,
            "supports_vision": True,
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 4,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35,
            },
        },
    },
    "flux_strong_hq_softstyle_fission": {
        "defaults": {
            "workflow_key": "flux_strong_hq_softstyle_fission",
            "timeout": 420,
            "profile_id": "pattern_default_v1",
            "steps": 8,
            "cfg": 1.0,
            "bili": 90,
            "batch_size": 1,
            "ipadapter_weight": 0.25,
            "colormatch_method": "mkl",
            "colormatch_strength": 0.20,
            "image_desc": "",
        },
        "display_name": "ComfyUI · 多元素花纹裂变",
        "description": "基于 05 FLUX Strong HQ SoftStyle 的图裂变高质量版本。保留旧图裂变的 bili 口径，适合多元素花纹类默认高质量裂变。",
        "category": "image_generation",
        "input_schema": _comfyui_flux_strong_hq_softstyle_fission_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "flux_strong_hq_softstyle_fission",
            "action": "image_fission",
            "requires_image_input": True,
            "supports_vision": True,
            "output_node_ids": ["31"],
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 3,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35,
            },
            "presentation": _presentation(
                name="多元素花纹裂变",
                summary="给多元素花纹图做更稳的高质量裂变，保留旧裂变里的重绘幅度调节习惯。",
                form_intro="上传原图，填写裂变提示词；如上游有 VL 控制卡，可额外传图像补充描述。",
                expected_output="产出 1 张高质量裂变结果，适合继续接 Coze 工作流或后续精修。",
                surfaces={"client": False, "coze": True, "admin": True, "eval": False},
                fields={
                    "image_url": _presentation_field(
                        label="原图",
                        description="上传这次要做图裂变的原图。",
                    ),
                    "prompt": _presentation_field(
                        label="裂变提示词",
                        placeholder="例如：保留原图结构和疏密关系，做更稳的多元素花纹裂变。",
                    ),
                    "image_desc": _presentation_field(
                        label="图像补充描述",
                        description="建议由上游 VL 自动生成，例如元素层级、疏密、filler 预算。",
                        advanced=True,
                    ),
                    "bili": _presentation_field(label="裂变幅度"),
                    "width": _presentation_field(label="输出宽度"),
                    "height": _presentation_field(label="输出高度"),
                },
            ),
        },
    },
    "flux_strong_hq_softstyle_fission_control_v1": {
        "defaults": {
            "workflow_key": "flux_strong_hq_softstyle_fission",
            "timeout": 420,
            "profile": "pattern_default_v1",
            "profile_id": "pattern_default_v1",
            "mode": "fission",
            "bili": "50%",
            "bili_mapping": "variation_percent_045_080",
            "width": 2000,
            "height": 2000,
            "steps": 8,
            "cfg": 1.0,
            "batch_size": 1,
            "ipadapter_weight": 0.25,
            "colormatch_method": "mkl",
            "colormatch_strength": 0.20,
        },
        "display_name": "ComfyUI · VL 控制卡裂变",
        "description": "AI 团队 2026-05-12 交付的 ComfyUI 裂变接口版本：输入原图、宽高、裂变幅度和 VL 控制卡，输出 05 FLUX Strong HQ SoftStyle 裂变图。",
        "category": "image_generation",
        "input_schema": _comfyui_flux_strong_hq_softstyle_fission_control_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "flux_strong_hq_softstyle_fission",
            "action": "image_fission",
            "interface_pack": "11_2026-05-12_comfyui_fission_interface_pack_v1",
            "vl_component_ability_id": "vl_fission_control_card",
            "requires_image_input": True,
            "supports_vision": True,
            "output_node_ids": ["31"],
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 1,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35,
            },
            "presentation": _presentation(
                name="VL 控制卡裂变",
                summary="先由统一 VL 组件生成控制卡，再调用 05 FLUX Strong HQ SoftStyle 裂变。",
                form_intro="业务可直接传 VL 控制卡；也可通过业务版本让中台自动先跑 VL。",
                expected_output="产出 1 张高质量裂变图；生成后可单独调用“裂变生成图评估”。",
                surfaces={"client": False, "coze": True, "admin": True, "eval": True},
                fields={
                    "image_url": _presentation_field(label="原图"),
                    "vl_result": _presentation_field(label="VL 控制卡"),
                    "bili": _presentation_field(label="裂变幅度"),
                    "width": _presentation_field(label="输出宽度"),
                    "height": _presentation_field(label="输出高度"),
                },
            ),
        },
    },
    "flux_strong_hq_softstyle_fission_colorlock_v2": {
        "defaults": {
            "workflow_key": "flux_strong_hq_softstyle_fission",
            "timeout": 420,
            "profile": "pattern_risk_routed_v4",
            "profile_id": "pattern_risk_routed_v4",
            "mode": "fission",
            "bili": "80%",
            "bili_mapping": "pattern_risk_routed_v4",
            "width": None,
            "height": None,
            "steps": 8,
            "cfg": 1.0,
            "batch_size": 1,
            "reference_lock": 0.42,
            "color_lock": 0.90,
            "ipadapter_weight": 0.42,
            "colormatch_method": "mkl",
            "colormatch_strength": 0.90,
        },
        "display_name": "ComfyUI · VL 颜色锁定裂变",
        "description": "AI 团队 2026-05-14 修补的 ComfyUI 裂变接口：保留颜色/密度风险路由，并针对可分离卡通图标类图案加强对象级变化。",
        "category": "image_generation",
        "input_schema": _comfyui_flux_strong_hq_softstyle_fission_colorlock_schema(),
        "metadata": {
            "executor_type": "comfyui",
            "executor_tag": "comfyui",
            "api_type": "comfyui_workflow",
            "workflow_key": "flux_strong_hq_softstyle_fission",
            "action": "image_fission",
            "interface_pack": "15_2026-05-14_comfyui_fission_object_variation_interface_pack_v4",
            "vl_component_ability_id": "vl_fission_control_card",
            "requires_image_input": True,
            "supports_vision": True,
            "output_node_ids": ["31"],
            "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
            "routing_policy": "queue",
            "seed_version": 2,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35,
            },
            "presentation": _presentation(
                name="VL 颜色锁定裂变",
                summary="先由统一 VL 组件识别图案风险类型，再调用 05 FLUX Strong HQ SoftStyle 做智能路由裂变。",
                form_intro="适合测试对象级变化和颜色稳定性；默认重绘幅度 80%，可用预设快速切换。",
                expected_output="产出 1 张颜色关系更稳定的裂变图；如仍有色偏，可用生成图评估接口复核。",
                surfaces={"client": False, "coze": True, "admin": True, "eval": True},
                fields={
                    "image_url": _presentation_field(label="原图"),
                    "vl_result": _presentation_field(label="VL 控制卡"),
                    "bili": _presentation_field(label="重绘幅度"),
                    "width": _presentation_field(label="输出宽度"),
                    "height": _presentation_field(label="输出高度"),
                    "profile": _presentation_field(label="裂变路由配置", advanced=True),
                    "reference_lock": _presentation_field(label="原图结构保留度", advanced=True),
                    "color_lock": _presentation_field(label="颜色锁定强度", advanced=True),
                    "prompt": _presentation_field(label="额外要求", advanced=True),
                },
            ),
        },
    },
}


PODI_UTILITY_ABILITIES: dict[str, AbilityDefinition] = {
    "expand_mask_color": {
        "defaults": {
            "expand_left": 0,
            "expand_right": 0,
            "expand_top": 0,
            "expand_bottom": 0,
        },
        "display_name": "PODI · 扩边占位图",
        "description": "输入图片与上下左右扩展像素，扩展区域填充特殊颜色（亮紫色）用于后续模型补全/扩图提示。",
        "category": "utilities",
        "input_schema": {
            "fields": [
                {
                    "name": "image_url",
                    "type": "image",
                    "label": _compose_bilingual_label("图片 URL", "Image URL"),
                    "required": True,
                },
                {
                    "name": "expand_left",
                    "type": "number",
                    "label": _compose_bilingual_label("左侧扩展(px)", "Expand Left(px)"),
                    "default": 0,
                },
                {
                    "name": "expand_right",
                    "type": "number",
                    "label": _compose_bilingual_label("右侧扩展(px)", "Expand Right(px)"),
                    "default": 0,
                },
                {
                    "name": "expand_top",
                    "type": "number",
                    "label": _compose_bilingual_label("上侧扩展(px)", "Expand Top(px)"),
                    "default": 0,
                },
                {
                    "name": "expand_bottom",
                    "type": "number",
                    "label": _compose_bilingual_label("下侧扩展(px)", "Expand Bottom(px)"),
                    "default": 0,
                },
            ]
        },
        "metadata": {
            "api_type": "podi_utility",
            "action": "expand_mask_color",
            "requires_image_input": True,
            "supports_vision": True,
            "seed_version": 2,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.03,
                "discount_price": 0.02,
            },
        },
    }
    ,
    "set_dpi": {
        "defaults": {
            "dpi": 300,
        },
        "display_name": "PODI · 设置 DPI",
        "description": "不改变像素尺寸，仅修改图片 DPI/PPI 元数据（例如改为 300dpi 便于印刷/排版）。",
        "category": "utilities",
        "input_schema": {
            "fields": [
                {
                    "name": "image_url",
                    "type": "image",
                    "label": _compose_bilingual_label("图片 URL", "Image URL"),
                    "required": True,
                },
                {
                    "name": "dpi",
                    "type": "number",
                    "label": _compose_bilingual_label("DPI", "DPI"),
                    "default": 300,
                },
            ]
        },
        "metadata": {
            "api_type": "podi_utility",
            "action": "set_dpi",
            "requires_image_input": True,
            "supports_vision": True,
            "seed_version": 2,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.03,
                "discount_price": 0.02,
            },
            "presentation": _presentation(
                name="DPI处理",
                summary="把图片改成适合印刷或排版的输出参数。",
                form_intro="只需要填写目标 DPI，不必关心内部元数据。",
                expected_output="产出适合印刷或排版的终稿文件。",
                surfaces={"client": True, "coze": False, "admin": True, "eval": True},
                fields={
                    "image_url": _presentation_field(label="原图"),
                    "dpi": _presentation_field(label="目标 DPI"),
                },
            ),
        },
    },
    "upscale_resize": {
        "defaults": {
            "max_long_edge": 4096,
            "output_format": "png",
        },
        "display_name": "PODI · 高质量缩放",
        "description": "非 AI 超分：将图片按比例缩放到指定长边像素（默认 4096，最大 8192），用于输出尺寸放大。",
        "category": "utilities",
        "input_schema": {
            "fields": [
                {
                    "name": "image_url",
                    "type": "image",
                    "label": _compose_bilingual_label("图片 URL", "Image URL"),
                    "required": True,
                },
                {
                    "name": "max_long_edge",
                    "type": "number",
                    "label": _compose_bilingual_label("长边像素", "Long Edge(px)"),
                    "default": 4096,
                },
                {
                    "name": "output_format",
                    "type": "select",
                    "label": _compose_bilingual_label("输出格式", "Output Format"),
                    "options": ["png", "jpg"],
                    "default": "png",
                },
            ]
        },
        "metadata": {
            "api_type": "podi_utility",
            "action": "upscale_resize",
            "requires_image_input": True,
            "supports_vision": True,
            "seed_version": 2,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.03,
                "discount_price": 0.02,
            },
            "presentation": _presentation(
                name="高质量缩放",
                summary="快速把图调整到适合交付的像素尺寸。",
                form_intro="只需要填写目标长边和输出格式。",
                expected_output="产出统一尺寸结果，适合后续下载交付。",
                surfaces={"client": True, "coze": False, "admin": True, "eval": True},
                fields={
                    "image_url": _presentation_field(label="原图"),
                    "max_long_edge": _presentation_field(label="目标长边"),
                    "output_format": _presentation_field(label="输出格式"),
                },
            ),
        },
    },
}
