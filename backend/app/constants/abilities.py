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
    if seed_version:
        metadata["seed_version"] = seed_version
    return metadata


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
        "seed_version": 5,
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
        ),
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
        ),
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
        ),
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
            # Only 117 server has the required seamless-pattern custom nodes.
            "allowed_executor_ids": ["executor_comfyui_seamless_117"],
            "seed_version": 8,
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
            # Only 158 server has the pattern-extract LoRA + nodes.
            "allowed_executor_ids": ["executor_comfyui_pattern_extract_158"],
            "seed_version": 5,
            "lora_presets": PATTERN_EXTRACT_LORA_PRESETS,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.5,
                "discount_price": 0.3,
            },
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
            # Only 117 server has the required outpaint custom nodes.
            "allowed_executor_ids": ["executor_comfyui_seamless_117"],
            "seed_version": 4,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35,
            },
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
            "allowed_executor_ids": ["executor_comfyui_pattern_extract_158"],
            "seed_version": 4,
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
            "allowed_executor_ids": ["executor_comfyui_pattern_extract_158"],
            "seed_version": 4,
            "pricing": {
                "currency": "CNY",
                "unit": "per_image",
                "list_price": 0.6,
                "discount_price": 0.35
            }
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
            "seed_version": 1,
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
            "seed_version": 1,
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
            "seed_version": 1,
        },
    },
}
