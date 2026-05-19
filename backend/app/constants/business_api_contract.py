"""Structured contract data for public business APIs."""

from __future__ import annotations

from typing import Any


BUSINESS_TASK_STATUS_VALUES = ["queued", "running", "succeeded", "failed"]

GPT_IMAGE2_VARIATION_STRENGTH_VALUES = [
    "conservative",
    "same_series",
    "creative_same_series",
]

GPT_IMAGE2_QUALITY_VALUES = ["preview", "candidate", "premium"]

GPT_IMAGE2_SIZE_VALUES = [
    "auto",
    "1024x1024",
    "1536x1024",
    "1024x1536",
    "2048x2048",
    "2048x1152",
    "3840x2160",
    "2160x3840",
]

COMFYUI_FISSION_PROFILE_VALUES = [
    "pattern_risk_routed_v4",
    "pattern_color_lock_v2",
    "pattern_color_lock_strict_v2",
    "pattern_default_v1",
]

COMFYUI_FISSION_V4_PROFILE = "pattern_risk_routed_v4"

COMFYUI_FISSION_VARIATION_PRESET_CONFIGS: list[dict[str, Any]] = [
    {
        "key": "default-high",
        "label": "高幅度默认",
        "description": "适合对象可分离的卡通、图标、童趣元素，变化更明显。",
        "values": {
            "bili": "80%",
            "reference_lock": "0.42",
            "color_lock": "0.90",
            "profile": COMFYUI_FISSION_V4_PROFILE,
            "profile_id": COMFYUI_FISSION_V4_PROFILE,
        },
    },
    {
        "key": "safe",
        "label": "保守稳定",
        "description": "更像原图，适合先看结构稳定性。",
        "values": {
            "bili": "30%",
            "reference_lock": "0.50",
            "color_lock": "1.00",
            "profile": COMFYUI_FISSION_V4_PROFILE,
            "profile_id": COMFYUI_FISSION_V4_PROFILE,
        },
    },
    {
        "key": "object-strong",
        "label": "对象变化更强",
        "description": "放开对象细节变化，适合找更明显的裂变方向。",
        "values": {
            "bili": "100%",
            "reference_lock": "0.34",
            "color_lock": "0.90",
            "profile": COMFYUI_FISSION_V4_PROFILE,
            "profile_id": COMFYUI_FISSION_V4_PROFILE,
        },
    },
    {
        "key": "color-free",
        "label": "配色更自由",
        "description": "结构仍保留，但允许配色稍微自由。",
        "values": {
            "bili": "80%",
            "reference_lock": "0.42",
            "color_lock": "0.75",
            "profile": COMFYUI_FISSION_V4_PROFILE,
            "profile_id": COMFYUI_FISSION_V4_PROFILE,
        },
    },
]

COMFYUI_FISSION_VARIATION_PRESET_VALUES = [
    str(item.get("key"))
    for item in COMFYUI_FISSION_VARIATION_PRESET_CONFIGS
    if item.get("key")
]

FISSION_PATTERN_RISK_TYPE_VALUES = [
    "element_pattern",
    "object_variation",
    "text_or_logo",
    "border_or_layout",
    "unknown",
]

FISSION_EVALUATE_DECISION_VALUES = ["pass", "needs_refission", "reject"]

FISSION_EVALUATE_NEXT_ACTION_VALUES = ["accept", "refission_repeat", "reject"]

BUSINESS_ROUTE_SELECTED_BY_VALUES = ["explicit", "default", "rollout_allowlist", "rollout_percent"]
BUSINESS_ROUTE_SELECTED_STATUS_VALUES = ["active", "disabled", "archived"]

BUSINESS_BILLING_STATUS_VALUES = ["billable", "unpriced", "no_charge", "billing_pending"]
BUSINESS_CALLBACK_STATUS_VALUES = ["pending", "succeeded", "failed", "skipped"]

BUSINESS_API_ENDPOINT_KIND_VALUES = ["submit", "poll", "callback"]
BUSINESS_API_STATUS_GROUP_VALUES = ["success", "error"]
BUSINESS_API_USAGE_ISSUE_CODES = ["HAS_ERROR", "POLL_WITHOUT_SUBMIT", "POLLING_TOO_FREQUENT"]
BUSINESS_KEY_VALUES = ["pattern_extract", "fission", "text_fission", "fission_evaluate", "outpaint"]

BUSINESS_API_ENUM_DOCS: list[dict[str, str]] = [
    {"field": "status / taskStatus", "value": "queued", "meaning": "已进入中台队列，还没开始执行。", "action": "按 retryAfterSeconds 继续查询。"},
    {"field": "status / taskStatus", "value": "running", "meaning": "正在执行或等待结果回填。", "action": "按 retryAfterSeconds 继续查询。"},
    {"field": "status / taskStatus", "value": "succeeded", "meaning": "任务成功，结果字段可读取。", "action": "读取 imageUrls / videoUrls / texts / resultPayload。"},
    {"field": "status / taskStatus", "value": "failed", "meaning": "任务失败或无法继续。", "action": "读取 errorCode / errorMessage，并按错误码处理。"},
    {"field": "businessKey", "value": "text_fission", "meaning": "文字强化裂变，两步式：先生成可编辑提示词，再提交文生图。", "action": "业务方先调 prompts，再把确认后的 editable_prompt 传给 runs。"},
    {"field": "variation_strength", "value": "conservative", "meaning": "GPT Image 2 保守裂变，更接近原图。", "action": "希望变化小的时候使用。"},
    {"field": "variation_strength", "value": "same_series", "meaning": "GPT Image 2 同系列裂变，默认推荐。", "action": "常规业务优先使用。"},
    {"field": "variation_strength", "value": "creative_same_series", "meaning": "GPT Image 2 更开放的同系列变化。", "action": "需要更明显变化时使用。"},
    {"field": "quality", "value": "preview", "meaning": "快速预览档。", "action": "适合内部测试和批量初筛。"},
    {"field": "quality", "value": "candidate", "meaning": "候选质量档。", "action": "适合交给业务方看效果。"},
    {"field": "quality", "value": "premium", "meaning": "高质量档。", "action": "成本更高，正式精品样本再用。"},
    {"field": "size", "value": "auto", "meaning": "默认按原图尺寸和比例处理。", "action": "不确定尺寸时优先使用。"},
    {"field": "size", "value": "1024x1024 / 1536x1024 / 1024x1536", "meaning": "常用 1K 正方形、横图、竖图。", "action": "业务明确尺寸时传入。"},
    {"field": "profile", "value": "pattern_risk_routed_v4", "meaning": "ComfyUI 智能风险路由，默认推荐。", "action": "常规裂变优先使用。"},
    {"field": "profile", "value": "pattern_color_lock_strict_v2", "meaning": "严格颜色锁定，更像原图但裂变感更弱。", "action": "颜色一致性要求高时使用。"},
    *[
        {
            "field": "variation_preset",
            "value": str(item.get("key") or ""),
            "meaning": f"{item.get('label') or item.get('key')}配置。",
            "action": str(item.get("description") or ""),
        }
        for item in COMFYUI_FISSION_VARIATION_PRESET_CONFIGS
    ],
    {"field": "decision", "value": "pass", "meaning": "裂变评分通过。", "action": "可以接受当前生成图。"},
    {"field": "decision", "value": "needs_refission", "meaning": "建议二次裂变。", "action": "业务侧可重新提交裂变任务。"},
    {"field": "decision", "value": "reject", "meaning": "不建议使用。", "action": "拒绝当前结果或人工复核。"},
    {"field": "endpoint_kind", "value": "submit", "meaning": "业务方提交任务。", "action": "用于确认任务是否真正进入中台。"},
    {"field": "endpoint_kind", "value": "poll", "meaning": "业务方查询结果。", "action": "用于判断是否按 retryAfterSeconds 合理轮询。"},
    {"field": "endpoint_kind", "value": "callback", "meaning": "业务回调相关请求。", "action": "用于排查终态通知。"},
    {"field": "status_group", "value": "success", "meaning": "HTTP 成功且没有平台错误码。", "action": "可继续看业务任务详情。"},
    {"field": "status_group", "value": "error", "meaning": "HTTP 异常或存在平台错误码。", "action": "按错误码和 runId 排查。"},
    {"field": "issueCode", "value": "HAS_ERROR", "meaning": "同一个 runId 链路中存在错误。", "action": "打开业务任务详情，先看失败步骤。"},
    {"field": "issueCode", "value": "POLL_WITHOUT_SUBMIT", "meaning": "当前窗口只看到查询，没有看到提交。", "action": "放宽时间窗口或核对 runId。"},
    {"field": "issueCode", "value": "POLLING_TOO_FREQUENT", "meaning": "同一个 runId 轮询次数偏高。", "action": "业务方应按 retryAfterSeconds 控制查询频率。"},
]

REQUIRED_BUSINESS_API_ENUM_FIELDS = [
    "status / taskStatus",
    "variation_strength",
    "quality",
    "size",
    "profile",
    "variation_preset",
    "decision",
    "endpoint_kind",
    "status_group",
    "issueCode",
]


def business_api_enum_doc_tokens() -> list[str]:
    tokens: list[str] = []

    def add_token(value: str) -> None:
        text = str(value or "").strip()
        if text and text not in tokens:
            tokens.append(text)

    for token in [
        "gpt-image2-vl-v2",
        "comfyui-vl-control-v2",
        "generated-image-eval-v1",
        "qwen2512-text2img-v1",
        "text_fission",
        "selectedBy",
        "selectedStatus",
        "BUSINESS_IMAGE_URL_REQUIRED",
        "BUSINESS_RUN_ID_REQUIRED",
        "TEXT_FISSION_PROMPT_REQUIRED",
        "TEXT_FISSION_PROMPT_EMPTY",
        "TEXT_FISSION_PROMPT_PREPARE_FAILED",
        "COMFYUI_QUEUE_FULL",
        "POLLING_TOO_FREQUENT",
    ]:
        add_token(token)
    for item in BUSINESS_API_ENUM_DOCS:
        field = str(item.get("field") or "").strip()
        value = str(item.get("value") or "").strip()
        if field:
            for part in field.split(" / "):
                add_token(part)
        if value:
            for part in value.split(" / "):
                add_token(part)
    return tokens


def business_api_contract_payload() -> dict[str, Any]:
    return {
        "version": "2026-05-19",
        "source": "backend.app.constants.business_api_contract",
        "enumDocs": BUSINESS_API_ENUM_DOCS,
        "requiredEnumFields": REQUIRED_BUSINESS_API_ENUM_FIELDS,
        "values": {
            "taskStatus": BUSINESS_TASK_STATUS_VALUES,
            "businessKey": BUSINESS_KEY_VALUES,
            "variation_strength": GPT_IMAGE2_VARIATION_STRENGTH_VALUES,
            "quality": GPT_IMAGE2_QUALITY_VALUES,
            "size": GPT_IMAGE2_SIZE_VALUES,
            "profile": COMFYUI_FISSION_PROFILE_VALUES,
            "variation_preset": COMFYUI_FISSION_VARIATION_PRESET_VALUES,
            "variationPresetDetails": COMFYUI_FISSION_VARIATION_PRESET_CONFIGS,
            "pattern_risk_type": FISSION_PATTERN_RISK_TYPE_VALUES,
            "decision": FISSION_EVALUATE_DECISION_VALUES,
            "next_action.type": FISSION_EVALUATE_NEXT_ACTION_VALUES,
            "selectedBy": BUSINESS_ROUTE_SELECTED_BY_VALUES,
            "selectedStatus": BUSINESS_ROUTE_SELECTED_STATUS_VALUES,
            "billingStatus": BUSINESS_BILLING_STATUS_VALUES,
            "callbackStatus": BUSINESS_CALLBACK_STATUS_VALUES,
            "endpoint_kind": BUSINESS_API_ENDPOINT_KIND_VALUES,
            "status_group": BUSINESS_API_STATUS_GROUP_VALUES,
            "issueCode": BUSINESS_API_USAGE_ISSUE_CODES,
        },
    }
