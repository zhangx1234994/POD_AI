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


def _baidu_image_schema(
    *,
    include_resolution: bool = False,
    resolution_default: str | None = None,
    include_type: bool = False,
    type_default: str | None = None,
    type_options: list[str] | None = None,
) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
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
        "seed_version": 1,
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


def _volcengine_image_schema(defaults: dict[str, Any]) -> dict[str, Any]:
    size_default = defaults.get("size", "2K")
    response_format_default = defaults.get("response_format", "url")
    return {
        "fields": [
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
                "name": "size",
                "type": "select",
                "label": _compose_bilingual_label("输出尺寸", "Output Size"),
                "options": [
                    {"label": "1K · 1024x1024", "value": "1K"},
                    {"label": "2K · 2048x2048", "value": "2K"},
                    {"label": "4K · 4096x4096", "value": "4K"},
                ],
                "default": size_default,
                "description": _compose_bilingual_label(
                    "常用分辨率，可与自定义宽高共同决定画幅。", "Presets, can combine with custom width/height."
                ),
            },
            {
                "name": "ratio",
                "type": "select",
                "label": _compose_bilingual_label("画幅比例", "Aspect Ratio"),
                "options": [
                    {"label": "1:1 Square", "value": "1:1"},
                    {"label": "3:4 Portrait", "value": "3:4"},
                    {"label": "4:3 Landscape", "value": "4:3"},
                    {"label": "16:9 Wide", "value": "16:9"},
                    {"label": "9:16 Vertical", "value": "9:16"},
                ],
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("自定义宽度 (px)", "Custom Width (px)"),
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
    }


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
    if seed_version:
        metadata["seed_version"] = seed_version
    return metadata


def _comfyui_seamless_schema() -> dict[str, Any]:
    return {
        "fields": [
            {
                "name": "prompt",
                "type": "textarea",
                "label": _compose_bilingual_label("提示词", "Prompt"),
                "description": "节点 42 · StringConcatenate.string_a",
                "placeholder": _compose_bilingual_label("例如：手绘花纹、几何、素材描述", "Describe the seamless pattern you expect"),
            },
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
                "name": "resolution",
                "type": "select",
                "label": _compose_bilingual_label("输出比例", "Output Ratio"),
                "description": "节点 102 · ImageResize+",
                "options": [
                    {"label": "1:1 正方形", "value": "1:1"},
                    {"label": "1:2 竖版", "value": "1:2"},
                    {"label": "2:1 横版", "value": "2:1"},
                    {"label": "original 原图", "value": "original"},
                    {"label": "auto 自定义", "value": "auto"},
                ],
                "default": "1:1",
            },
            {
                "name": "width",
                "type": "number",
                "label": _compose_bilingual_label("输出宽度 (px)", "Output Width (px)"),
                "description": "节点 102.width",
                "placeholder": "2048",
            },
            {
                "name": "height",
                "type": "number",
                "label": _compose_bilingual_label("输出高度 (px)", "Output Height (px)"),
                "description": "节点 102.height",
                "placeholder": "2048",
            },
            {
                "name": "image_url",
                "type": "text",
                "label": _compose_bilingual_label("样例图 URL", "Reference Image URL"),
                "description": _compose_bilingual_label(
                    "输入公网图片链接，或在测试面板上传图片自动填写", "Provide a public URL or upload image in the tester"
                )
                + "（节点 96）",
            },
        ]
    }


def _comfyui_pattern_extract_schema() -> dict[str, Any]:
    positive_default = dedent(
        """
        高分辨率，超清细节，商业级印刷品质。

        请将提供的产品图片视为一个“实物照片”，并根据其表面的装饰性印花内容，生成一份100%忠于原作的“原始设计稿”。

        这份“设计稿”必须是：
        - 纯平面的，彻底消除所有因产品立体形态、弯曲、折叠带来的透视、阴影、形变或褶皱。
        - 彻底剥离所有非图案元素，包括但不限于：拉链、扣件、缝线、带子、背景、人物、污渍、边缘裁切、产品轮廓、产品硬件（如杯口、瓶盖）、液体、冰块、以及任何放置在产品表面的独立物体（如盘子、餐具、杯子、花瓶、植物等）。
        - 彻底移除产品本身的所有材质纹理（如布料网格、皮革纹路、塑料反光），但保留图案中所有设计性的背景层次、底纹和水印，仅移除物理性的干扰。
        - 智能判断图案类型：如果图案是散点式/重复式/无明确边界的，先提取最小重复单元并保持无缝平铺；如果图案是具有明确边框或中心对称的，完整保留其原始构图、边框和中心对称性。
        - 严格保持原始设计的每一个细节、色彩空间、色彩饱和度、明暗关系和艺术风格（如水彩、油画、矢量等），禁止任何色彩增强、去色或风格化处理。
        - 识别并完整保留图案中的核心主体（如动物、人物、大型花卉等），确保其形态完整、位置准确。
        - 尊重并还原图案中各元素的构图关系（前后遮挡、环绕、散点分布等），保持整体布局一致。
        - 深入理解并再现图案的视觉结构和设计意图，例如渐变、分层、区域划分、视觉焦点等，使输出结构清晰、层次分明和富有设计感。
        - 精确还原图案中元素的原始密度和分布规律，禁止过度填充或稀释，以保持图案的“呼吸感”和“设计韵味”。

        ⚠️ 特别注意：
        - 所有餐具（盘子、刀、叉）、桌椅、植物、柜子等环境元素必须彻底移除，不能保留任何残影或轮廓。
        - 图案中的文字需保持原始字体、字号、间距和排版，不可替换或模糊。
        - 背景网格必须保持原始颜色、线条粗细和间距，不可偏色或变形。

        最终输出应为纯净设计稿，无任何产品实物或干扰物，可直接用于印刷。
        """
    ).strip()
    negative_default = (
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
    return {
        "fields": [
            {
                "name": "image_url",
                "type": "text",
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
                "name": "output_width",
                "type": "number",
                "label": _compose_bilingual_label("输出宽度 (px)", "Output Width (px)"),
                "description": "节点 400 · LatentUpscale.width",
                "default": 1800,
            },
            {
                "name": "output_height",
                "type": "number",
                "label": _compose_bilingual_label("输出高度 (px)", "Output Height (px)"),
                "description": "节点 400 · LatentUpscale.height",
                "default": 1800,
            },
            {
                "name": "lora_name",
                "type": "text",
                "label": _compose_bilingual_label("LoRA 文件名", "LoRA Filename"),
                "description": "节点 390 · LoraLoaderModelOnly.lora_name（当前默认：印花提取-YinHuaTiQu-Qwen-Image-Edit-LoRA_V1.safetensors）",
                "default": "印花提取-YinHuaTiQu-Qwen-Image-Edit-LoRA_V1.safetensors",
                "component": "select",
                "allow_custom_value": True,
            },
        ]
    }


def _build_kie_schema(capability_key: str) -> dict[str, Any]:
    if capability_key == "nano_banana_pro_image_to_image":
        return {
            "fields": [
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
                    "description": _compose_bilingual_label("每行一个公网图片链接；留空纯文生图。", "One URL per line; leave empty for text-to-image."),
                },
                {
                    "name": "aspect_ratio",
                    "type": "select",
                    "label": _compose_bilingual_label("画幅比例", "Aspect Ratio"),
                    "options": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"],
                    "default": "1:1",
                },
                {
                    "name": "resolution",
                    "type": "select",
                    "label": _compose_bilingual_label("分辨率", "Resolution"),
                    "options": ["1K", "2K", "4K"],
                    "default": "1K",
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
                    "default": "1:1",
                },
                {
                    "name": "resolution",
                    "type": "select",
                    "label": _compose_bilingual_label("分辨率", "Resolution"),
                    "options": ["1K", "2K"],
                    "default": "1K",
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
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "executor_type": "kie",
        "executor_tag": "kie_market",
        "api_type": api_type,
        "model_id": model_id,
        "request_endpoint": endpoint,
        "seed_version": 1,
    }
    if requires_image_input:
        metadata["requires_image_input"] = True
        metadata["supports_vision"] = True
    elif supports_vision:
        metadata["supports_vision"] = True
    if input_array_target:
        metadata["input_array_target"] = input_array_target
    return metadata


_DOUBAO_SEEDREAM_45_DEFAULTS: dict[str, Any] = {
    "model": "doubao-seedream-4-5-251128",
    "response_format": "url",
    "size": "2K",
    "watermark": True,
    "stream": False,
}

_DOUBAO_SEEDREAM_40_DEFAULTS: dict[str, Any] = {
    "model": "doubao-seedream-4-0-250901",
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
        "metadata": _baidu_metadata("quality_upgrade", "/rest/2.0/image-process/v1/image_quality_enhance"),
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
        "input_schema": _volcengine_image_schema(_DOUBAO_SEEDREAM_45_DEFAULTS),
        "metadata": _volcengine_metadata(
            endpoint="/api/v3/images/generations",
            model_id="doubao-seedream-4-5-251128",
            api_type="image_generation",
            supports_vision=False,
            reference="https://www.volcengine.com/docs/82379/1541523",
            seed_version=2,
        ),
    },
    "doubao_seedream_4_0": {
        "endpoint": "/api/v3/images/generations",
        "defaults": _DOUBAO_SEEDREAM_40_DEFAULTS,
        "display_name": "火山 · Doubao Seedream 4.0",
        "description": "性价比更高的文生图模型，适合预算敏感场景。",
        "category": "image_generation",
        "input_schema": _volcengine_image_schema(_DOUBAO_SEEDREAM_40_DEFAULTS),
        "metadata": _volcengine_metadata(
            endpoint="/api/v3/images/generations",
            model_id="doubao-seedream-4-0-250901",
            api_type="image_generation",
            supports_vision=False,
            reference="https://www.volcengine.com/docs/82379/1541523",
            seed_version=2,
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
        ),
    },
}


KIE_MARKET_ABILITIES: dict[str, AbilityDefinition] = {
    "nano_banana_pro_image_to_image": {
        "endpoint": "/api/v1/jobs/createTask",
        "defaults": {
            "model": "nano-banana-pro",
            "aspect_ratio": "1:1",
            "resolution": "1K",
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
            requires_image_input=False,
            input_array_target="image_input",
            supports_vision=True,
        ),
    },
    "flux2_pro_image_to_image": {
        "endpoint": "/api/v1/jobs/createTask",
        "defaults": {
            "model": "flux-2/pro-image-to-image",
            "aspect_ratio": "1:1",
            "resolution": "1K",
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
        ),
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
        ),
    },
}

COMFYUI_ABILITIES: dict[str, AbilityDefinition] = {
    "sifang_lianxu": {
        "defaults": {
            "patternType": "seamless",
            "resolution": "1:1",
            "workflow_key": "sifang_lianxu",
            "timeout": 480,
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
            "seed_version": 3,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.5,
                "discount_price": 0.3,
            },
        },
    },
    "yinhua_tiqu": {
        "defaults": {
            "workflow_key": "yinhua_tiqu",
            "timeout": 420,
            "output_width": 1800,
            "output_height": 1800,
            "lora_name": "印花提取-YinHuaTiQu-Qwen-Image-Edit-LoRA_V1.safetensors",
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
            "seed_version": 3,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.5,
                "discount_price": 0.3,
            },
        },
    },
}
