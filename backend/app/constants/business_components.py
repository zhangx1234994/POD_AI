"""Controlled component catalog for business orchestration recipes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


BUSINESS_COMPONENT_CATALOG_VERSION = "2026-05-19.v1"
BUSINESS_COMPONENT_CATALOG_SOURCE = "backend.app.constants.business_components"


def _io(key: str, label: str, description: str, *, required: bool = False) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "description": description,
        "required": required,
    }


def _field(
    key: str,
    label: str,
    field_type: str,
    description: str,
    *,
    required: bool = False,
    options: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": key,
        "label": label,
        "type": field_type,
        "description": description,
        "required": required,
    }
    if options is not None:
        payload["options"] = options
    return payload


def _locked(key: str, label: str, reason: str) -> dict[str, str]:
    return {
        "key": key,
        "label": label,
        "reason": reason,
    }


def _error(code: str, label: str, action: str) -> dict[str, str]:
    return {
        "code": code,
        "label": label,
        "action": action,
    }


BUSINESS_COMPONENT_TYPES: tuple[dict[str, Any], ...] = (
    {
        "type": "input",
        "label": "业务入口",
        "summary": "接收业务方参数，生成本次业务任务 runId。",
        "stage": "entry",
        "owner": "backend",
        "draftEditable": True,
        "inputs": [],
        "outputs": [
            _io("runId", "任务编号", "业务方保存和轮询结果的主编号。", required=True),
            _io("businessKey", "业务类型", "花纹提取、图裂变、扩图或评分等业务入口。", required=True),
            _io("inputs", "业务参数", "经过兼容和默认值补齐后的业务参数。", required=True),
        ],
        "routing": {
            "mode": "none",
            "description": "入口组件不选择执行节点，只负责参数接收、鉴权、runId 和调用审计。",
        },
        "editableFields": [
            _field("fieldLabels", "字段说明", "schema", "调整字段中文说明、示例和是否高级参数。"),
            _field("defaultInputs", "默认参数", "json", "只允许修改业务参数默认值，不允许改接口路径。"),
        ],
        "lockedFields": [
            _locked("businessKey", "业务类型", "业务入口路径和统计归属依赖它，变更必须新建业务。"),
            _locked("submitPath", "提交接口", "对外接口路径属于稳定契约，不能在草稿里直接改。"),
            _locked("runId", "任务编号", "任务主线编号由后端生成，不能由编排节点覆盖。"),
        ],
        "errors": [
            _error("BUSINESS_IMAGE_URL_REQUIRED", "缺少主图", "补充 imageUrl 后重新提交。"),
            _error("BUSINESS_RUN_ID_REQUIRED", "缺少任务编号", "查询结果时必须传 runId。"),
            _error("AUTHORIZATION_REQUIRED", "缺少鉴权", "检查业务 API Key 或登录态。"),
        ],
    },
    {
        "type": "vl",
        "label": "图像理解",
        "summary": "读取原图并输出结构化理解结果、提示词或控制卡。",
        "stage": "understanding",
        "owner": "vendor-api-ops",
        "draftEditable": True,
        "inputs": [
            _io("imageUrl", "原图", "需要分析的图片地址。", required=True),
            _io("promptTemplate", "分析要求", "给 VL 模型的业务化分析说明。"),
        ],
        "outputs": [
            _io("imageDesc", "图片描述", "可给后续生图能力使用的图片理解。"),
            _io("promptCard", "提示词卡片", "结构、颜色、主体、构图等可复用提示词信息。"),
            _io("controlCard", "控制卡", "裂变、扩图等业务可读取的结构化控制信息。"),
        ],
        "routing": {
            "mode": "provider_model",
            "description": "通过业务版本指定 VL 组件或 provider/model；默认使用当前统一 VL 组件。",
        },
        "editableFields": [
            _field("abilityId", "VL 组件", "ability", "选择已验收的 VL 原子能力。"),
            _field("promptTemplate", "分析模板", "textarea", "调整业务分析要求。"),
            _field("applyToPrimary", "回填到主能力", "boolean", "是否把 VL 输出回填到后续生图参数。"),
            _field("waitForResult", "等待分析完成", "boolean", "是否必须等 VL 成功后再执行主能力。"),
        ],
        "lockedFields": [
            _locked("rawProviderKey", "厂商密钥", "密钥由模型弹药库管理，业务编排不能直接填写。"),
            _locked("rawResponse", "厂商原始返回", "只进入排障信息，不能作为业务方默认返回。"),
        ],
        "errors": [
            _error("VL_EVAL_IMAGE_REQUIRED", "图片缺失", "补齐原图或生成图后重试。"),
            _error("VENDOR_API_EXECUTION_FAILED", "模型调用失败", "查看模型弹药库、Key、余额和上游错误。"),
            _error("VENDOR_API_RATE_LIMITED", "模型限流", "降低并发或切换可用 Key。"),
        ],
    },
    {
        "type": "comfyui",
        "label": "自有 GPU 生图",
        "summary": "调用 ComfyUI 执行节点完成裂变、扩图、抠图等 GPU 任务。",
        "stage": "generation",
        "owner": "backend",
        "draftEditable": True,
        "inputs": [
            _io("imageUrl", "原图", "ComfyUI 工作流输入图。", required=True),
            _io("prompt", "提示词", "可由业务方传入，也可由 VL 组件生成。"),
            _io("routeTags", "路由标签", "用于选择 158/233 等执行节点。"),
        ],
        "outputs": [
            _io("imageUrls", "结果图", "落到自有 OSS 后返回的图片地址。", required=True),
            _io("executorId", "执行节点", "实际命中的 ComfyUI 节点，用于排障。"),
        ],
        "routing": {
            "mode": "executor_tags",
            "description": "通过 required_executor_tags、allowed_executor_ids、健康状态和队列容量选择执行节点。",
        },
        "editableFields": [
            _field("abilityId", "生图能力", "ability", "选择已接入的 ComfyUI 原子能力。", required=True),
            _field("profile", "裂变配置", "select", "选择业务预设，不直接暴露工作流节点。"),
            _field("bili", "重绘幅度", "number", "越高变化越明显；后端按约定映射 denoise。"),
            _field("width", "输出宽度", "number", "不填时尽量跟随原图宽度。"),
            _field("height", "输出高度", "number", "不填时尽量跟随原图高度。"),
            _field("routeTags", "路由标签", "tags", "选择 comfyui-general、high-mem 等受控标签。"),
            _field("timeout", "超时时间", "number", "业务级超时上限。"),
        ],
        "lockedFields": [
            _locked("workflowJson", "工作流 JSON", "工作流文件由能力目录和交付包管理，草稿只改受控字段。"),
            _locked("nodeIdMapping", "节点映射", "节点映射属于原子能力定义，不能在业务页临时改。"),
        ],
        "errors": [
            _error("COMFYUI_QUEUE_FULL", "队列已满", "稍后重试或检查节点容量。"),
            _error("COMFYUI_TIMEOUT", "执行超时", "检查工作流耗时、节点健康和输入尺寸。"),
            _error("ABILITY_TASK_FAILED", "能力执行失败", "打开子步骤查看 ComfyUI 错误。"),
        ],
    },
    {
        "type": "vendor_api",
        "label": "第三方模型",
        "summary": "调用 OpenAI、火山、KIE、Qwen 等商业模型能力。",
        "stage": "generation",
        "owner": "vendor-api-ops",
        "draftEditable": True,
        "inputs": [
            _io("imageUrl", "输入图", "图生图、图片编辑或评分输入。"),
            _io("prompt", "提示词", "模型执行说明。"),
            _io("maskUrl", "蒙版", "图片编辑类模型可选蒙版。"),
        ],
        "outputs": [
            _io("imageUrls", "图片结果", "模型生成图片，统一落 OSS 后返回。"),
            _io("texts", "文本结果", "模型输出文本或结构化判断。"),
            _io("vendorInvocationId", "厂商调用编号", "排查和成本统计用编号。"),
        ],
        "routing": {
            "mode": "provider_model_key_pool",
            "description": "由 vendor-api-ops 选择 provider、model、Key 和出网节点；业务编排只选择受控模型。",
        },
        "editableFields": [
            _field("provider", "模型厂商", "select", "选择已接入厂商，例如 openai、volcengine、kie。"),
            _field("model", "模型", "select", "选择模型弹药库中已启用模型。"),
            _field("quality", "质量档", "select", "商业模型质量和成本档位。"),
            _field("size", "输出尺寸", "select", "支持模型定义的尺寸枚举。"),
            _field("costSensitive", "成本敏感", "boolean", "是否允许发布检查跳过真实消耗型测试。"),
        ],
        "lockedFields": [
            _locked("apiKey", "模型密钥", "密钥由 Key 池管理，不进入业务配方。"),
            _locked("proxy", "出网代理", "出网策略由 vendor-api-ops 和执行节点配置管理。"),
        ],
        "errors": [
            _error("VENDOR_API_KEY_MISSING", "缺少模型 Key", "到模型弹药库配置可用 Key。"),
            _error("VENDOR_API_CONCURRENCY_LIMITED", "模型并发满", "降低并发或扩容 Key/节点。"),
            _error("VENDOR_API_EXECUTION_FAILED", "模型执行失败", "查看厂商调用记录和错误摘要。"),
        ],
    },
    {
        "type": "image_ops",
        "label": "图像处理",
        "summary": "调用自研图像处理服务，例如高清放大、DPI、尺寸修复。",
        "stage": "postprocess",
        "owner": "image-ops-service",
        "draftEditable": True,
        "inputs": [
            _io("imageUrl", "输入图", "待处理图片。", required=True),
            _io("operation", "处理类型", "放大、DPI、压缩、格式转换等。", required=True),
        ],
        "outputs": [
            _io("imageUrls", "处理结果", "处理后的图片 OSS 地址。", required=True),
        ],
        "routing": {
            "mode": "service_endpoint",
            "description": "统一走 image-ops-service，不允许回落到 Coze 主机本机执行重任务。",
        },
        "editableFields": [
            _field("operation", "处理类型", "select", "选择已注册的图像处理能力。", required=True),
            _field("scale", "放大倍数", "number", "高清放大类能力使用。"),
            _field("dpi", "目标 DPI", "number", "DPI 修复类能力使用。"),
            _field("timeout", "超时时间", "number", "图像处理服务调用超时。"),
        ],
        "lockedFields": [
            _locked("localFallback", "本机兜底", "重图像处理不允许落到控制面主机执行。"),
        ],
        "errors": [
            _error("IMAGE_OPS_BASE_URL_NOT_CONFIGURED", "处理服务未配置", "检查 image-ops-service 地址。"),
            _error("IMAGE_OPS_INVALID_RESPONSE", "处理服务返回异常", "查看图像处理服务日志。"),
            _error("IMAGE_OPS_CONTENT_MISSING", "处理结果为空", "确认上游服务是否真正产出文件。"),
        ],
    },
    {
        "type": "score",
        "label": "质量评估",
        "summary": "对生成结果进行质量、逻辑或业务规则评分。",
        "stage": "quality",
        "owner": "backend",
        "draftEditable": True,
        "inputs": [
            _io("originalImageUrl", "原图", "评分基准图。", required=True),
            _io("generatedImageUrl", "结果图", "需要评分的生成图。", required=True),
            _io("context", "业务背景", "本次评分需要关注的业务要求。"),
        ],
        "outputs": [
            _io("decision", "判定", "pass、needs_refission 或 reject。", required=True),
            _io("score", "分数", "模型或规则给出的质量分。"),
            _io("problemTags", "问题标签", "用于解释为什么需要复核或重跑。"),
        ],
        "routing": {
            "mode": "ability_or_vendor_model",
            "description": "评分可以走 VL 原子能力或第三方模型，但输出必须归一为业务判定。",
        },
        "editableFields": [
            _field("abilityId", "评分能力", "ability", "选择已验收评分组件。", required=True),
            _field("thresholds", "判定阈值", "json", "调整通过、复核、不通过阈值说明。"),
            _field("decisionLabels", "判定文案", "json", "给业务方看的判定说明。"),
        ],
        "lockedFields": [
            _locked("autoRefission", "自动二次裂变", "评分组件只给判断，不自动重跑业务。"),
        ],
        "errors": [
            _error("VL_EVAL_IMAGE_REQUIRED", "评分图片缺失", "补齐原图和结果图。"),
            _error("VENDOR_API_EXECUTION_FAILED", "评分模型失败", "检查评分模型和 Key。"),
        ],
    },
    {
        "type": "result",
        "label": "结果整理",
        "summary": "统一整理图片、视频、文本和结构化结果，并控制轻量/完整返回。",
        "stage": "delivery",
        "owner": "backend",
        "draftEditable": True,
        "inputs": [
            _io("stepResults", "步骤结果", "上游步骤产生的图片、视频、文本或 JSON。", required=True),
        ],
        "outputs": [
            _io("imageUrls", "图片结果", "默认对外图片结果。"),
            _io("videoUrls", "视频结果", "默认对外视频结果。"),
            _io("texts", "文本结果", "默认对外文本结果。"),
            _io("resultPayload", "结构化结果", "轻量查询可读取的业务结构化结果。"),
        ],
        "routing": {
            "mode": "none",
            "description": "结果整理不选执行节点，只负责字段归一、OSS 地址和轻量返回。",
        },
        "editableFields": [
            _field("publicFields", "默认返回字段", "json", "控制业务方轻量查询能看到哪些字段。"),
            _field("fullDetailFields", "排障字段", "json", "控制 detail=full 时展示哪些内部证据。"),
        ],
        "lockedFields": [
            _locked("rawSecrets", "敏感原始信息", "密钥、代理、完整厂商原始返回不能进入对外默认结果。"),
        ],
        "errors": [
            _error("ABILITY_TASK_ID_MISSING", "底层任务编号缺失", "检查执行步骤是否成功提交。"),
            _error("BUSINESS_RUN_TEMPORARY_UNAVAILABLE", "查询临时不可用", "稍后重试查询，不要重新提交任务。"),
        ],
    },
    {
        "type": "callback",
        "label": "业务通知",
        "summary": "任务终态后通知业务方系统；轮询仍是主查询方式。",
        "stage": "delivery",
        "owner": "backend",
        "draftEditable": True,
        "inputs": [
            _io("callbackUrl", "通知地址", "业务方提供的 Webhook 地址。"),
            _io("runResult", "任务结果", "任务终态轻量结果。", required=True),
        ],
        "outputs": [
            _io("callbackStatus", "通知状态", "pending、succeeded、failed 或 skipped。"),
        ],
        "routing": {
            "mode": "http_callback",
            "description": "只向业务配置的回调地址发送终态通知；失败不影响 runId 轮询。",
        },
        "editableFields": [
            _field("retryPolicy", "重试策略", "json", "通知失败后的重试次数和间隔。"),
            _field("payloadMode", "通知内容", "select", "选择轻量或完整通知内容。", options=["light", "full"]),
        ],
        "lockedFields": [
            _locked("callbackSecret", "通知签名密钥", "签名密钥不进入业务配方明文。"),
        ],
        "errors": [
            _error("BUSINESS_CALLBACK_NOT_CONFIGURED", "未配置回调", "没有回调地址时不执行重试。"),
            _error("CALLBACK_FAILED", "通知失败", "业务方仍可用 runId 查询终态。"),
        ],
    },
    {
        "type": "billing",
        "label": "成本记录",
        "summary": "记录模型、GPU、图片数量和计费状态；当前只做运营骨架。",
        "stage": "governance",
        "owner": "backend",
        "draftEditable": True,
        "inputs": [
            _io("runId", "任务编号", "需要计费或免计费的业务任务。", required=True),
            _io("usage", "用量", "图片、视频、模型调用、耗时等计量信息。"),
        ],
        "outputs": [
            _io("billingStatus", "计费状态", "billable、unpriced、no_charge 或 billing_pending。"),
            _io("costAmount", "成本", "内部成本核算金额。"),
        ],
        "routing": {
            "mode": "none",
            "description": "计费组件不执行模型，只记录成本、免费策略和后续账单证据。",
        },
        "editableFields": [
            _field("billingMode", "计费方式", "select", "按图、按视频、按模型调用或免费。"),
            _field("unitPrice", "单价", "number", "内部成本或后续收费单价。"),
            _field("noChargePolicy", "免计费策略", "json", "巡检、测试、内部任务的免计费规则。"),
        ],
        "lockedFields": [
            _locked("walletMutation", "钱包扣费流水", "真实扣费必须走账单服务，不在编排草稿里直接改。"),
        ],
        "errors": [
            _error("BILLING_DATETIME_INVALID", "账单时间非法", "检查计费时间字段。"),
            _error("BUSINESS_RELEASE_GATE_BLOCKED", "上线门禁阻断", "正式收费前必须补齐成本和验收。"),
        ],
    },
    {
        "type": "acceptance",
        "label": "验收证据",
        "summary": "记录真实测试、样本包、人工验收和发布门禁结论。",
        "stage": "governance",
        "owner": "backend",
        "draftEditable": True,
        "inputs": [
            _io("runId", "样本任务", "作为验收证据的真实业务任务。"),
            _io("evidenceUrl", "证据链接", "样本包、截图、评测记录或巡检报告。"),
        ],
        "outputs": [
            _io("acceptanceStatus", "验收状态", "passed、failed 或 pending。", required=True),
            _io("releaseGate", "发布门禁", "可发布、需复核或阻断。"),
        ],
        "routing": {
            "mode": "none",
            "description": "验收组件不调模型，只汇总真实样本、测试和人工确认。",
        },
        "editableFields": [
            _field("status", "验收状态", "select", "记录通过、失败或待补验收。", options=["pending", "passed", "failed"]),
            _field("notes", "验收说明", "textarea", "说明样本质量、风险和是否可切默认。"),
            _field("evidenceUrl", "证据链接", "url", "关联样本包、巡检报告或截图。"),
        ],
        "lockedFields": [
            _locked("releaseGateRules", "发布门禁规则", "门禁规则由后端统一执行，不能在单个草稿里绕过。"),
        ],
        "errors": [
            _error("BUSINESS_RELEASE_ACCEPTANCE_REQUIRED", "缺少验收", "登记通过验收后才能切默认。"),
            _error("BUSINESS_RELEASE_GATE_BLOCKED", "门禁阻断", "先处理阻断项，再申请发布。"),
        ],
    },
)


def business_component_catalog_payload() -> dict[str, Any]:
    return {
        "version": BUSINESS_COMPONENT_CATALOG_VERSION,
        "source": BUSINESS_COMPONENT_CATALOG_SOURCE,
        "rules": {
            "defaultVersionReadonly": True,
            "draftOnlyEditing": True,
            "noArbitraryCode": True,
            "noArbitraryHttp": True,
            "businessLanguageFirst": True,
            "internalIdsAsDebugOnly": True,
            "heavyExecutionMustBeExternal": True,
        },
        "componentTypes": deepcopy(list(BUSINESS_COMPONENT_TYPES)),
    }
