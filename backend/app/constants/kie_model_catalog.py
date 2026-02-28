"""KIE model catalog for Coze query-only toolbox.

This module provides a normalized, provider-agnostic schema so business-side
workflows can discover model params before invoking execution tools.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

FieldDef = dict[str, Any]
ModelDef = dict[str, Any]

# NOTE:
# - modelKey is our stable contract key for Coze/workflow orchestration.
# - providerModel maps to KIE upstream model/path.
# - fields is a normalized schema, not raw provider OpenAPI.
KIE_MODEL_CATALOG: list[ModelDef] = [
    {
        "modelKey": "nano_banana_pro_image_to_image",
        "displayName": "Nano Banana Pro 图生图",
        "providerModel": "nano-banana-pro",
        "mediaType": "image",
        "status": "active",
        "docsUrl": "https://kie.ai/zh-CN/nano-banana-pro",
        "summary": "多参考图图像编辑，适合保持主体并替换局部元素。",
        "abilityProvider": "kie",
        "abilityKey": "nano_banana_pro_image_to_image",
        "pricingHint": "1K/2K/4K 分档计费（以 KIE 页面实时价格为准）。",
        "supports": {
            "multiImage": True,
            "maxImages": 8,
            "aspectRatios": ["auto", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
            "resolutions": ["1K", "2K", "4K"],
        },
        "fields": [
            {
                "name": "prompt",
                "label": "提示词",
                "type": "string",
                "required": True,
                "description": "编辑指令。",
                "example": "把杯子改成马克杯，保持其他区域不变",
            },
            {
                "name": "url",
                "label": "主图 URL",
                "type": "string",
                "required": True,
                "description": "主图，作为图1。",
            },
            {
                "name": "image_urls",
                "label": "参考图 URL 列表",
                "type": "string_list",
                "required": False,
                "description": "多参考图。每行一张或使用英文逗号分隔。",
                "maxItems": 7,
            },
            {
                "name": "aspect_ratio",
                "label": "画幅比例",
                "type": "enum",
                "required": False,
                "default": "auto",
                "enum": ["auto", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
                "description": "为空或 auto 时按原图推断。",
            },
            {
                "name": "resolution",
                "label": "分辨率",
                "type": "enum",
                "required": False,
                "default": "1K",
                "enum": ["1K", "2K", "4K"],
            },
            {
                "name": "output_format",
                "label": "输出格式",
                "type": "enum",
                "required": False,
                "default": "png",
                "enum": ["png", "jpg"],
            },
        ],
    },
    {
        "modelKey": "nano_banana_2_image_to_image",
        "displayName": "Nano Banana 2 图生图",
        "providerModel": "nano-banana-2",
        "mediaType": "image",
        "status": "active",
        "docsUrl": "https://kie.ai/zh-CN/nano-banana-2",
        "summary": "新版 Nano Banana，多参考图上限更高。",
        "abilityProvider": "kie",
        "abilityKey": "nano_banana_2_image_to_image",
        "pricingHint": "按 1K/2K/4K 分档计费（以 KIE 页面实时价格为准）。",
        "supports": {
            "multiImage": True,
            "maxImages": 14,
            "aspectRatios": ["auto", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
            "resolutions": ["1K", "2K", "4K"],
        },
        "fields": [
            {
                "name": "prompt",
                "label": "提示词",
                "type": "string",
                "required": True,
                "description": "编辑指令。",
            },
            {
                "name": "url",
                "label": "主图 URL",
                "type": "string",
                "required": True,
                "description": "主图，作为图1。",
            },
            {
                "name": "image_urls",
                "label": "参考图 URL 列表",
                "type": "string_list",
                "required": False,
                "description": "每行一个 URL，按顺序对应图2/图3/...",
                "maxItems": 13,
            },
            {
                "name": "aspect_ratio",
                "label": "画幅比例",
                "type": "enum",
                "required": False,
                "default": "auto",
                "enum": ["auto", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
            },
            {
                "name": "resolution",
                "label": "分辨率",
                "type": "enum",
                "required": False,
                "default": "1K",
                "enum": ["1K", "2K", "4K"],
            },
            {
                "name": "google_search",
                "label": "联网搜索增强",
                "type": "boolean",
                "required": False,
                "default": False,
            },
            {
                "name": "output_format",
                "label": "输出格式",
                "type": "enum",
                "required": False,
                "default": "jpg",
                "enum": ["jpg", "png"],
            },
        ],
    },
    {
        "modelKey": "flux_2_pro_image_to_image",
        "displayName": "Flux-2 Pro 图生图",
        "providerModel": "flux-2/pro-image-to-image",
        "mediaType": "image",
        "status": "active",
        "docsUrl": "https://kie.ai/zh-CN/flux-2",
        "summary": "强调风格一致性与高保真修改，要求至少 1 张输入图。",
        "abilityProvider": "kie",
        "abilityKey": "flux2_pro_image_to_image",
        "pricingHint": "按 1K/2K 分档计费（以 KIE 页面实时价格为准）。",
        "supports": {
            "multiImage": True,
            "maxImages": 8,
            "aspectRatios": ["auto", "1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"],
            "resolutions": ["1K", "2K"],
        },
        "fields": [
            {
                "name": "prompt",
                "label": "提示词",
                "type": "string",
                "required": True,
            },
            {
                "name": "image_urls",
                "label": "输入图 URL 列表",
                "type": "string_list",
                "required": True,
                "description": "1~8 张，每行一个 URL。",
                "minItems": 1,
                "maxItems": 8,
            },
            {
                "name": "aspect_ratio",
                "label": "画幅比例",
                "type": "enum",
                "required": True,
                "default": "auto",
                "enum": ["auto", "1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"],
            },
            {
                "name": "resolution",
                "label": "分辨率",
                "type": "enum",
                "required": True,
                "default": "1K",
                "enum": ["1K", "2K"],
            },
        ],
    },
    {
        "modelKey": "sora_2_pro_storyboard_video",
        "displayName": "Sora 2 Pro Storyboard 视频",
        "providerModel": "sora-2-pro-storyboard",
        "mediaType": "video",
        "status": "active",
        "docsUrl": "https://kie.ai/zh-CN/sora-2-pro-storyboard",
        "summary": "故事板模式，适合单图驱动视频生成。",
        "abilityProvider": "kie",
        "abilityKey": None,
        "pricingHint": "按时长与清晰度计费（以 KIE 页面实时价格为准）。",
        "supports": {
            "multiImage": False,
            "maxImages": 1,
            "aspectRatios": ["portrait", "landscape"],
            "frames": [10, 15],
        },
        "fields": [
            {"name": "n_frames", "label": "帧数", "type": "enum", "required": True, "default": "15", "enum": ["10", "15"]},
            {
                "name": "image_urls",
                "label": "参考图 URL",
                "type": "string_list",
                "required": False,
                "description": "最多 1 张。",
                "maxItems": 1,
            },
            {
                "name": "aspect_ratio",
                "label": "画幅",
                "type": "enum",
                "required": False,
                "default": "landscape",
                "enum": ["portrait", "landscape"],
            },
            {
                "name": "upload_method",
                "label": "上传方式",
                "type": "enum",
                "required": False,
                "default": "s3",
                "enum": ["s3"],
            },
        ],
    },
    {
        "modelKey": "sora_2_pro_text_to_video",
        "displayName": "Sora 2 Pro 文生视频",
        "providerModel": "sora-2-pro-text-to-video",
        "mediaType": "video",
        "status": "active",
        "docsUrl": "https://kie.ai/zh-CN/s-2pro",
        "summary": "文生视频主链路，可选参考图。",
        "abilityProvider": "kie",
        "abilityKey": "sora2_pro_text_to_video",
        "pricingHint": "按时长、清晰度、是否去水印计费。",
        "supports": {
            "multiImage": True,
            "maxImages": 8,
            "aspectRatios": ["portrait", "landscape"],
            "frames": [10, 15],
            "qualities": ["standard", "high"],
        },
        "fields": [
            {"name": "prompt", "label": "提示词", "type": "string", "required": True},
            {
                "name": "image_urls",
                "label": "参考图 URL 列表",
                "type": "string_list",
                "required": False,
                "description": "每行一个 URL。",
                "maxItems": 8,
            },
            {
                "name": "aspect_ratio",
                "label": "画幅",
                "type": "enum",
                "required": False,
                "default": "landscape",
                "enum": ["portrait", "landscape"],
            },
            {"name": "n_frames", "label": "帧数", "type": "enum", "required": False, "default": "10", "enum": ["10", "15"]},
            {"name": "size", "label": "清晰度", "type": "enum", "required": False, "default": "high", "enum": ["standard", "high"]},
            {"name": "remove_watermark", "label": "去水印", "type": "boolean", "required": False, "default": True},
            {"name": "upload_method", "label": "上传方式", "type": "enum", "required": False, "default": "s3", "enum": ["s3"]},
        ],
    },
    {
        "modelKey": "seedance_2_0_text_to_video",
        "displayName": "Seedance 2.0 文生视频",
        "providerModel": "bytedance/seedance-2-text-to-video",
        "mediaType": "video",
        "status": "preview",
        "docsUrl": "https://kie.ai/zh-CN/seedance-2-0",
        "summary": "Seedance 2.0 文生视频（参数以 KIE 最新文档为准）。",
        "abilityProvider": "kie",
        "abilityKey": None,
        "pricingHint": "以 KIE 页面实时价格为准。",
        "supports": {"multiImage": False},
        "fields": [
            {"name": "prompt", "label": "提示词", "type": "string", "required": True},
            {
                "name": "aspect_ratio",
                "label": "画幅",
                "type": "enum",
                "required": False,
                "enum": ["16:9", "9:16", "1:1"],
            },
            {
                "name": "duration",
                "label": "时长",
                "type": "enum",
                "required": False,
                "enum": ["5", "10"],
                "description": "秒。",
            },
        ],
    },
    {
        "modelKey": "seedance_2_0_image_to_video",
        "displayName": "Seedance 2.0 图生视频",
        "providerModel": "bytedance/seedance-2-image-to-video",
        "mediaType": "video",
        "status": "preview",
        "docsUrl": "https://kie.ai/zh-CN/seedance-2-0",
        "summary": "Seedance 2.0 图生视频（参数以 KIE 最新文档为准）。",
        "abilityProvider": "kie",
        "abilityKey": None,
        "pricingHint": "以 KIE 页面实时价格为准。",
        "supports": {"multiImage": False, "maxImages": 1},
        "fields": [
            {"name": "url", "label": "主图 URL", "type": "string", "required": True},
            {"name": "prompt", "label": "提示词", "type": "string", "required": False},
            {
                "name": "aspect_ratio",
                "label": "画幅",
                "type": "enum",
                "required": False,
                "enum": ["16:9", "9:16", "1:1"],
            },
            {
                "name": "duration",
                "label": "时长",
                "type": "enum",
                "required": False,
                "enum": ["5", "10"],
            },
        ],
    },
]


KIE_MODEL_ALIASES: dict[str, str] = {
    "nano-banana-pro": "nano_banana_pro_image_to_image",
    "nano_banana_pro": "nano_banana_pro_image_to_image",
    "nano-banana-2": "nano_banana_2_image_to_image",
    "nano_banana_2": "nano_banana_2_image_to_image",
    "flux-2": "flux_2_pro_image_to_image",
    "flux_2": "flux_2_pro_image_to_image",
    "flux2_pro_image_to_image": "flux_2_pro_image_to_image",
    "sora-2-pro-storyboard": "sora_2_pro_storyboard_video",
    "sora_storyboard": "sora_2_pro_storyboard_video",
    "s-2pro": "sora_2_pro_text_to_video",
    "sora2_pro_text_to_video": "sora_2_pro_text_to_video",
    "seedance-2-0-text-to-video": "seedance_2_0_text_to_video",
    "seedance-2-0-image-to-video": "seedance_2_0_image_to_video",
}


def normalize_model_key(model_key: str | None) -> str:
    raw = (model_key or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    return KIE_MODEL_ALIASES.get(lowered, lowered)


def list_kie_models(*, media_type: str | None = None, keyword: str | None = None, status: str | None = None) -> list[ModelDef]:
    media = (media_type or "all").strip().lower()
    q = (keyword or "").strip().lower()
    wanted_status = (status or "all").strip().lower()

    out: list[ModelDef] = []
    for model in KIE_MODEL_CATALOG:
        if media not in {"", "all"} and model.get("mediaType") != media:
            continue
        model_status = str(model.get("status") or "").lower()
        if wanted_status not in {"", "all"} and model_status != wanted_status:
            continue
        if q:
            hay = " ".join(
                [
                    str(model.get("modelKey") or ""),
                    str(model.get("displayName") or ""),
                    str(model.get("providerModel") or ""),
                ]
            ).lower()
            if q not in hay:
                continue
        out.append(deepcopy(model))
    return out


def get_kie_model(model_key: str | None) -> ModelDef | None:
    normalized = normalize_model_key(model_key)
    if not normalized:
        return None
    for model in KIE_MODEL_CATALOG:
        if str(model.get("modelKey") or "").lower() == normalized:
            return deepcopy(model)
    return None


def build_coze_param_suggestion(model: ModelDef) -> dict[str, Any]:
    fields: list[FieldDef] = list(model.get("fields") or [])
    required = [str(field.get("name")) for field in fields if field.get("required")]

    coze_inputs: list[dict[str, str]] = []
    for field in fields:
        name = str(field.get("name") or "").strip()
        if not name:
            continue
        entry = {
            "name": name,
            "type": str(field.get("type") or "string"),
            "required": "true" if field.get("required") else "false",
            "description": str(field.get("description") or field.get("label") or ""),
        }
        coze_inputs.append(entry)

    transform_rules = [
        "`url` 为主图（图1）；`image_urls` 按顺序映射为图2、图3、图4...。",
        "`image_urls` 建议用换行分隔；也支持逗号分隔（仅在 http/https 前拆分）。",
        "布尔值统一传 true/false；枚举值必须传 value，不要传中文标签。",
    ]

    template_inputs: dict[str, Any] = {}
    for field in fields:
        name = str(field.get("name") or "").strip()
        if not name:
            continue
        if field.get("default") is not None:
            template_inputs[name] = field.get("default")
            continue
        ftype = field.get("type")
        if ftype == "boolean":
            template_inputs[name] = False
        elif ftype in {"string_list"}:
            template_inputs[name] = ""
        else:
            template_inputs[name] = ""

    return {
        "requiredParams": required,
        "cozeInputParams": coze_inputs,
        "transformRules": transform_rules,
        "payloadTemplate": {
            "modelKey": model.get("modelKey"),
            "inputs": template_inputs,
        },
    }
