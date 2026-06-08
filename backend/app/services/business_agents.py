"""Lightweight controlled business Agent runtime."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.constants.business_api_contract import (
    IMAGE_EDIT_OUTPUT_FORMAT_VALUES,
    IMAGE_EDIT_QUALITY_VALUES,
    IMAGE_EDIT_SIZE_VALUES,
    IMAGE_EDIT_SKILL_VALUES,
)
from app.core.config import get_settings
from app.core.db import get_session
from app.models.integration import (
    BusinessAgentMessage,
    BusinessAgentPlan,
    BusinessAgentSession,
    BusinessAgentToolCall,
    BusinessRun,
)
from app.models.user import User
from app.schemas.business import (
    BusinessAgentConfirmRequest,
    BusinessAgentMessageRequest,
    BusinessAgentSessionCreateRequest,
    BusinessRunCreateRequest,
)
from app.services.business_runs import get_business_run_service


logger = logging.getLogger(__name__)

IMAGE_EDIT_AGENT_KEY = "agent.image_edit_assistant"
AGENT_BUSINESS_KEY = "image_edit_chat"
IMAGE_EDIT_TOOL_NAME = "business.image_edit"
PATTERN_EXTRACT_TOOL_NAME = "business.pattern_extract"
ALLOWED_AGENT_TOOLS = {
    IMAGE_EDIT_TOOL_NAME: "image_edit",
    PATTERN_EXTRACT_TOOL_NAME: "pattern_extract",
}
ROUTE_TYPE_VALUES = ["image2_quality_first", "ability_accelerated", "clarification_required"]
REFERENCE_REQUIRED_SKILLS = {"reference_element_transfer", "color_reference_correction"}
ROUTE_CONFIDENCE_THRESHOLD = 0.65
ALLOWED_AGENT_KEYS = {IMAGE_EDIT_AGENT_KEY}
ALLOWED_TOOL_PAYLOAD_KEYS = {
    "imageUrl",
    "prompt",
    "negative_prompt",
    "batch",
    "width",
    "height",
    "lora",
    "instruction",
    "editSkill",
    "quality",
    "size",
    "output_format",
    "maskUrl",
    "referenceImages",
    "selectionHints",
    "metadata",
    "projectId",
    "flowStepKey",
    "flowStepName",
    "flowTemplateId",
    "inputAssetIds",
}


PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {"type": "string", "enum": ["image_edit", "pattern_extract"]},
        "routeType": {"type": "string", "enum": ROUTE_TYPE_VALUES},
        "targetAbility": {"type": "string", "enum": list(ALLOWED_AGENT_TOOLS.keys())},
        "targetBusinessKey": {"type": "string", "enum": list(ALLOWED_AGENT_TOOLS.values())},
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "editSkill": {"type": ["string", "null"], "enum": [*IMAGE_EDIT_SKILL_VALUES, None]},
        "instruction": {"type": ["string", "null"]},
        "prompt": {"type": ["string", "null"]},
        "negativePrompt": {"type": ["string", "null"]},
        "batch": {"type": ["integer", "null"]},
        "size": {"type": "string"},
        "quality": {"type": "string", "enum": IMAGE_EDIT_QUALITY_VALUES},
        "outputFormat": {"type": "string", "enum": IMAGE_EDIT_OUTPUT_FORMAT_VALUES},
        "editPlan": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "step": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["step", "reason"],
            },
        },
        "estimatedCostLevel": {"type": "string", "enum": ["low", "medium", "high"]},
        "riskLevel": {"type": "string", "enum": ["low", "medium", "high"]},
        "confidence": {"type": ["number", "null"]},
        "missingFields": {"type": ["array", "null"], "items": {"type": "string"}},
        "routeReason": {"type": ["string", "null"]},
        "rejectedAbilities": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ability": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["ability", "reason"],
            },
        },
        "warnings": {"type": ["array", "null"], "items": {"type": "string"}},
    },
    "required": [
        "intent",
        "routeType",
        "targetAbility",
        "targetBusinessKey",
        "title",
        "summary",
        "editSkill",
        "instruction",
        "prompt",
        "negativePrompt",
        "batch",
        "size",
        "quality",
        "outputFormat",
        "editPlan",
        "estimatedCostLevel",
        "riskLevel",
        "confidence",
        "missingFields",
        "routeReason",
        "rejectedAbilities",
        "warnings",
    ],
}


PLANNER_INSTRUCTIONS = """你是 PODI 中台的受控图片能力 Agent。你负责把用户自然语言整理成结构化 JSON 规划，再由后端白名单执行。
必须遵守：
1. 只能在 business.image_edit 与 business.pattern_extract 两个白名单工具中选择，不直接调用外部模型，不承诺已执行。
2. 当前阶段默认采用质量优先主路径：GPT-5.5 规划 + GPT Image 2 执行，对应 routeType=image2_quality_first、targetAbility=business.image_edit。
3. business.pattern_extract 是专项能力，适合批量、快速、低成本、固定 SOP 或用户明确要求“走花纹提取能力/批量提取/快速提取”时使用，对应 routeType=ability_accelerated。
4. 用户只说“提取花纹/图案/纹样/把桌布或衣服上的花纹取出来”但没有批量、速度、成本或专项能力要求时，仍选择 business.image_edit，让 GPT Image 2 做高质量单张处理；routeReason 中记录可选专项能力是 business.pattern_extract。
5. 输出必须是结构化 JSON，字段符合 schema；与当前能力无关的字段返回 null 或空数组，不要硬填专项能力参数。
6. 选择 business.image_edit 时，instruction 要面向 GPT Image 2，可覆盖开放式生成、改图、花纹提取、风格优化等单张高质量任务。
7. 选择 business.pattern_extract 时，prompt 要能直接描述提取目标，默认强调保留花纹主体、还原纹理、减少背景干扰。
8. instruction/prompt 是内部执行参数；面向用户只展示 title、summary、关键步骤和执行状态，不展示完整 JSON、routeReason 或模型内部推理。
9. 必须给出 confidence、missingFields、routeReason、rejectedAbilities，供后端做路由稳定性校验。
"""


def _now() -> datetime:
    return datetime.utcnow()


def _safe_text(value: Any, *, max_length: int = 4000) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        return text[:max_length]
    return text


def _safe_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = _safe_text(value)
        if text:
            return text
    return None


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_string_list(value: Any, *, max_items: int = 12) -> list[str]:
    if not value:
        return []
    raw_items = value if isinstance(value, list) else [value]
    items: list[str] = []
    for item in raw_items[:max_items]:
        text = _safe_text(item, max_length=128)
        if text and text not in items:
            items.append(text)
    return items


def _normalize_base_image_role(value: Any) -> str:
    text = _safe_text(value)
    if text in {"previous_result", "source_image", "selected_history_result"}:
        return text
    return "source_image"


def _normalize_rejected_abilities(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, str]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        ability = _safe_text(item.get("ability"), max_length=96)
        reason = _safe_text(item.get("reason"), max_length=240)
        if ability:
            items.append({"ability": ability, "reason": reason or "本轮不匹配用户目标。"})
    return items


def _has_pattern_extract_intent(message: str) -> bool:
    text = _safe_text(message, max_length=400).lower()
    compact = "".join(text.split())
    pattern_tokens = [
        "花纹提取",
        "提取花纹",
        "提取图案",
        "图案提取",
        "花型提取",
        "提取花型",
        "纹样提取",
        "提取纹样",
        "抠出花纹",
        "抠花",
        "取出花纹",
        "extractpattern",
        "patternextract",
    ]
    if any(token in compact for token in pattern_tokens):
        return True
    if "提取" in compact and any(token in compact for token in ["花", "纹", "图案", "桌布", "面料", "印花"]):
        return True
    return False


def _wants_specialized_agent_ability(message: str, request_context: dict[str, Any] | None = None) -> bool:
    request_context = request_context or {}
    preference = _safe_text(
        _first_text(
            request_context.get("routeType"),
            request_context.get("routingPreference"),
            request_context.get("routing_preference"),
            request_context.get("executionPreference"),
            request_context.get("execution_preference"),
        ),
        max_length=64,
    )
    if preference in {"ability_accelerated", "batch", "fast", "low_cost", "specialized", "workflow"}:
        return True
    text = _safe_text(message, max_length=400).lower()
    compact = "".join(text.split())
    specialized_tokens = [
        "批量",
        "跑一批",
        "多张",
        "快速",
        "快一点",
        "低成本",
        "省成本",
        "便宜",
        "固定流程",
        "固定能力",
        "专项能力",
        "走花纹提取",
        "用花纹提取",
        "调用花纹提取",
        "花纹提取能力",
        "pattern_extract",
        "ability_accelerated",
    ]
    return any(token in compact for token in specialized_tokens)


def _infer_agent_business_key(message: str, *, request_context: dict[str, Any] | None = None) -> str:
    if _has_pattern_extract_intent(message) and _wants_specialized_agent_ability(message, request_context):
        return "pattern_extract"
    return "image_edit"


def _tool_name_for_business_key(business_key: str) -> str:
    for tool_name, item_business_key in ALLOWED_AGENT_TOOLS.items():
        if item_business_key == business_key:
            return tool_name
    return IMAGE_EDIT_TOOL_NAME


def _normalize_agent_tool_name(value: Any, *, fallback_business_key: str = "image_edit") -> str:
    text = _safe_text(value, max_length=96)
    if text in ALLOWED_AGENT_TOOLS and ALLOWED_AGENT_TOOLS[text] == fallback_business_key:
        return text
    return _tool_name_for_business_key(fallback_business_key)


def _normalize_agent_business_key(
    value: Any,
    *,
    message: str = "",
    request_context: dict[str, Any] | None = None,
) -> str:
    text = _safe_text(value, max_length=64)
    inferred = _infer_agent_business_key(message, request_context=request_context)
    if text == "pattern_extract" and inferred != "pattern_extract":
        return "image_edit"
    if text in set(ALLOWED_AGENT_TOOLS.values()):
        return text
    return inferred


def _is_vague_edit_message(message: str) -> bool:
    text = _safe_text(message, max_length=120).lower()
    compact = "".join(text.split())
    if not compact:
        return True
    vague_tokens = {
        "改一下",
        "优化一下",
        "处理一下",
        "修一下",
        "做一下",
        "随便改",
        "好看点",
        "高级点",
        "变好看",
        "makebetter",
        "improve",
    }
    if compact in vague_tokens:
        return True
    return len(compact) <= 4 and not any(token in compact for token in ["扩", "删", "去", "色", "花", "提取", "背景", "质感"])


def _valid_http_url(value: Any) -> str | None:
    text = _safe_text(value, max_length=1024)
    if not text:
        return None
    if not text.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="AGENT_IMAGE_URL_INVALID")
    return text


def _normalize_quality(value: Any) -> str:
    text = _safe_text(value).lower()
    if text == "candidate":
        return "production"
    if text in {"low", "fast"}:
        return "preview"
    if text in {"medium", "standard"}:
        return "production"
    if text in {"high", "best"}:
        return "premium"
    return text if text in IMAGE_EDIT_QUALITY_VALUES else "preview"


def _normalize_size(value: Any) -> str:
    text = _safe_text(value)
    if text in IMAGE_EDIT_SIZE_VALUES:
        return text
    return "auto"


def _normalize_output_format(value: Any) -> str:
    text = _safe_text(value).lower()
    return text if text in IMAGE_EDIT_OUTPUT_FORMAT_VALUES else "png"


def _normalize_edit_skill(value: Any, *, has_reference: bool, has_target_hint: bool) -> tuple[str, list[str]]:
    warnings: list[str] = []
    text = _safe_text(value)
    if text not in IMAGE_EDIT_SKILL_VALUES:
        return "local_modify", warnings
    if text in REFERENCE_REQUIRED_SKILLS and not has_reference:
        warnings.append("当前没有参考图，已先按局部修改方案处理；如需参考图替换或补色，请先上传参考图。")
        return "local_modify", warnings
    if text == "remove_inpaint" and not has_target_hint:
        warnings.append("删除修补最好配合标注或蒙版；当前先生成可确认方案，建议执行前补充标注。")
    return text, warnings


def _normalize_reference_images(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    raw_items: list[Any]
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = [value]
    items: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items[:8]):
        if isinstance(item, dict):
            url = _safe_text(item.get("url") or item.get("imageUrl") or item.get("image_url"), max_length=1024)
            if not url:
                continue
            items.append({**item, "url": url, "index": item.get("index", index)})
        else:
            url = _safe_text(item, max_length=1024)
            if url:
                items.append({"url": url, "index": index})
    return items


def _normalize_selection_hints(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, list):
        return [item for item in value[:24] if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


class BusinessAgentPlanner:
    """Planner with optional OpenAI Responses call and deterministic fallback."""

    def generate_plan(
        self,
        *,
        message: str,
        image_url: str | None,
        request_context: dict[str, Any],
        session_context: dict[str, Any],
    ) -> dict[str, Any]:
        settings = get_settings()
        if settings.business_agent_planner_enabled and settings.business_agent_openai_api_key:
            try:
                return self._generate_with_openai(
                    message=message,
                    image_url=image_url,
                    request_context=request_context,
                    session_context=session_context,
                    settings=settings,
                )
            except Exception as exc:  # pragma: no cover - network/provider defensive path
                logger.warning("business agent OpenAI planner fallback: %s", exc)
                fallback = self._generate_rule_plan(
                    message=message,
                    image_url=image_url,
                    request_context=request_context,
                    session_context=session_context,
                )
                fallback["plannerMode"] = "rule_fallback"
                fallback["warnings"] = [
                    *fallback.get("warnings", []),
                    "模型 planner 暂不可用，已使用规则 planner 生成可测试方案。",
                ]
                fallback["rawResponse"] = {"plannerError": str(exc)[:500]}
                return fallback
        return self._generate_rule_plan(
            message=message,
            image_url=image_url,
            request_context=request_context,
            session_context=session_context,
        )

    def _generate_with_openai(
        self,
        *,
        message: str,
        image_url: str | None,
        request_context: dict[str, Any],
        session_context: dict[str, Any],
        settings: Any,
    ) -> dict[str, Any]:
        context_payload = {
            "userMessage": message,
            "hasImage": bool(image_url),
            "requestContext": request_context,
            "sessionContext": session_context,
            "availableTools": [
                {
                    "targetAbility": IMAGE_EDIT_TOOL_NAME,
                    "targetBusinessKey": "image_edit",
                    "description": "修改已有图片、局部修补、换色、参考图迁移、扩图。",
                },
                {
                    "targetAbility": PATTERN_EXTRACT_TOOL_NAME,
                    "targetBusinessKey": "pattern_extract",
                    "description": "从图片中提取花纹、图案、印花或纹样，输出可继续用于裂变/设计的图案图。",
                },
            ],
            "availableSkills": IMAGE_EDIT_SKILL_VALUES,
            "qualityValues": IMAGE_EDIT_QUALITY_VALUES,
            "sizeValues": IMAGE_EDIT_SIZE_VALUES,
            "outputFormats": IMAGE_EDIT_OUTPUT_FORMAT_VALUES,
        }
        content: list[dict[str, Any]] = [
            {"type": "input_text", "text": json.dumps(context_payload, ensure_ascii=False)}
        ]
        if image_url:
            content.append({"type": "input_image", "image_url": image_url})
        payload = {
            "model": settings.business_agent_planner_model,
            "instructions": PLANNER_INSTRUCTIONS,
            "input": [{"role": "user", "content": content}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "podi_image_edit_agent_plan",
                    "strict": True,
                    "schema": PLAN_JSON_SCHEMA,
                }
            },
            "store": False,
        }
        base_url = str(settings.business_agent_openai_base_url or "https://api.openai.com").rstrip("/")
        with httpx.Client(timeout=float(settings.business_agent_planner_timeout_seconds or 30)) as client:
            response = client.post(
                f"{base_url}/v1/responses",
                headers={
                    "Authorization": f"Bearer {settings.business_agent_openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        output_text = self._extract_openai_output_text(data)
        parsed = json.loads(output_text)
        normalized = self._normalize_model_plan(
            parsed,
            request_context=request_context,
            session_context=session_context,
            image_url=image_url,
            message=message,
        )
        normalized["plannerMode"] = "openai_responses"
        normalized["plannerModel"] = settings.business_agent_planner_model
        normalized["rawResponse"] = {"responseId": data.get("id"), "usage": data.get("usage")}
        return normalized

    @staticmethod
    def _extract_openai_output_text(data: dict[str, Any]) -> str:
        direct = data.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        for item in data.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text = content.get("text") or content.get("output_text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        raise RuntimeError("AGENT_PLANNER_EMPTY_RESPONSE")

    def _normalize_model_plan(
        self,
        parsed: dict[str, Any],
        *,
        request_context: dict[str, Any],
        session_context: dict[str, Any],
        image_url: str | None,
        message: str,
    ) -> dict[str, Any]:
        target_business_key = _normalize_agent_business_key(
            parsed.get("targetBusinessKey") or parsed.get("intent"),
            message=message,
            request_context=request_context,
        )
        target_ability = _normalize_agent_tool_name(parsed.get("targetAbility"), fallback_business_key=target_business_key)
        if target_business_key == "pattern_extract":
            prompt = _safe_text(parsed.get("prompt") or parsed.get("instruction") or message, max_length=3000)
            edit_plan = (
                self._normalize_edit_plan(parsed.get("editPlan"))
                if isinstance(parsed.get("editPlan"), list)
                else self._build_pattern_extract_plan()
            )
            tool_payload = {
                "prompt": prompt,
                "batch": int(parsed.get("batch") or request_context.get("batch") or 1),
                "quality": _normalize_quality(parsed.get("quality") or request_context.get("quality")),
                "size": _normalize_size(parsed.get("size") or request_context.get("size")),
                "output_format": _normalize_output_format(parsed.get("outputFormat") or request_context.get("outputFormat")),
                **({"negative_prompt": _safe_text(parsed.get("negativePrompt"), max_length=1000)} if parsed.get("negativePrompt") else {}),
            }
            route_evidence = self._build_route_evidence(
                message=message,
                image_url=image_url,
                request_context=request_context,
                session_context=session_context,
                tool_payload=tool_payload,
                parsed={**parsed, "targetAbility": target_ability, "targetBusinessKey": target_business_key},
            )
            warnings = [str(item) for item in parsed.get("warnings") or [] if str(item).strip()]
            return {
                "intent": "pattern_extract",
                "title": _safe_text(parsed.get("title") or "花纹提取", max_length=128),
                "summary": _safe_text(parsed.get("summary") or "已识别为花纹提取任务，将从当前图片中提取图案主体。", max_length=1000),
                "editPlan": edit_plan,
                "toolPayload": tool_payload,
                "estimatedCostLevel": self._normalize_cost_level(parsed.get("estimatedCostLevel"), tool_payload),
                "riskLevel": self._normalize_risk_level(parsed.get("riskLevel"), tool_payload),
                "routeEvidence": route_evidence,
                "warnings": warnings,
            }
        refs = _normalize_reference_images(request_context.get("referenceImages"))
        selection_hints = _normalize_selection_hints(request_context.get("selectionHints"))
        has_target_hint = bool(selection_hints or request_context.get("maskUrl"))
        skill, skill_warnings = _normalize_edit_skill(
            parsed.get("editSkill"),
            has_reference=bool(refs),
            has_target_hint=has_target_hint,
        )
        warnings = [*skill_warnings, *[str(item) for item in parsed.get("warnings") or [] if str(item).strip()]]
        tool_payload = {
            "instruction": _safe_text(parsed.get("instruction") or message, max_length=3000),
            "editSkill": skill,
            "quality": _normalize_quality(parsed.get("quality") or request_context.get("quality")),
            "size": _normalize_size(parsed.get("size") or request_context.get("size")),
            "output_format": _normalize_output_format(parsed.get("outputFormat") or request_context.get("outputFormat")),
            **({"referenceImages": refs} if refs else {}),
            **({"selectionHints": selection_hints} if selection_hints else {}),
            **({"maskUrl": request_context.get("maskUrl")} if request_context.get("maskUrl") else {}),
        }
        route_evidence = self._build_route_evidence(
            message=message,
            image_url=image_url,
            request_context=request_context,
            session_context=session_context,
            tool_payload=tool_payload,
            parsed=parsed,
        )
        if route_evidence.get("requiresClarification"):
            warnings.append("当前意图不够明确，请先补充要改哪里、保留什么、希望变成什么效果。")
        edit_plan = (
            self._normalize_edit_plan(parsed.get("editPlan"))
            if isinstance(parsed.get("editPlan"), list)
            else (
                self._build_image2_pattern_extract_plan()
                if _has_pattern_extract_intent(message)
                else self._normalize_edit_plan(parsed.get("editPlan"))
            )
        )
        return {
            "intent": "image_edit",
            "title": _safe_text(parsed.get("title") or "图片处理计划", max_length=128),
            "summary": _safe_text(parsed.get("summary") or "已整理为可确认的图编辑任务。", max_length=1000),
            "editPlan": edit_plan,
            "toolPayload": tool_payload,
            "estimatedCostLevel": self._normalize_cost_level(parsed.get("estimatedCostLevel"), tool_payload),
            "riskLevel": self._normalize_risk_level(parsed.get("riskLevel"), tool_payload),
            "routeEvidence": route_evidence,
            "warnings": warnings,
        }

    def _generate_rule_plan(
        self,
        *,
        message: str,
        image_url: str | None,
        request_context: dict[str, Any],
        session_context: dict[str, Any],
    ) -> dict[str, Any]:
        target_business_key = _infer_agent_business_key(message, request_context=request_context)
        if target_business_key == "pattern_extract":
            warnings: list[str] = []
            if not image_url:
                warnings.append("当前会话还没有主图，执行前需要先上传或粘贴图片 URL。")
            prompt = self._build_pattern_extract_prompt(message)
            tool_payload: dict[str, Any] = {
                "prompt": prompt,
                "batch": int(request_context.get("batch") or 1),
                "quality": _normalize_quality(request_context.get("quality")),
                "size": _normalize_size(request_context.get("size")),
                "output_format": _normalize_output_format(request_context.get("outputFormat")),
            }
            route_evidence = self._build_route_evidence(
                message=message,
                image_url=image_url,
                request_context=request_context,
                session_context=session_context,
                tool_payload=tool_payload,
                parsed={
                    "intent": "pattern_extract",
                    "targetAbility": PATTERN_EXTRACT_TOOL_NAME,
                    "targetBusinessKey": "pattern_extract",
                    "routeReason": "用户明确要求批量、快速、低成本或专项花纹提取，后端白名单路由到 business.pattern_extract。",
                    "rejectedAbilities": [
                        {"ability": IMAGE_EDIT_TOOL_NAME, "reason": "本轮更强调专项能力加速或固定 SOP，而不是单张质量优先处理。"},
                        {"ability": "business.fission", "reason": "当前还没有进入裂变生成，只先提取可复用花纹。"},
                    ],
                },
            )
            return {
                "intent": "pattern_extract",
                "title": self._infer_title(message, skill="pattern_extract"),
                "summary": self._build_summary(message, skill="pattern_extract"),
                "editPlan": self._build_pattern_extract_plan(),
                "toolPayload": tool_payload,
                "estimatedCostLevel": "medium",
                "riskLevel": "low",
                "routeEvidence": route_evidence,
                "warnings": warnings,
                "plannerMode": "rule",
                "plannerModel": "rule-planner-v1",
                "rawResponse": {"rulePlanner": True},
            }
        refs = _normalize_reference_images(request_context.get("referenceImages"))
        selection_hints = _normalize_selection_hints(request_context.get("selectionHints"))
        has_target_hint = bool(selection_hints or request_context.get("maskUrl"))
        explicit_skill = request_context.get("editSkill")
        skill = self._infer_skill(message, has_reference=bool(refs), has_target_hint=has_target_hint, explicit_skill=explicit_skill)
        skill, warnings = _normalize_edit_skill(skill, has_reference=bool(refs), has_target_hint=has_target_hint)
        quality = _normalize_quality(request_context.get("quality"))
        size = _normalize_size(request_context.get("size"))
        output_format = _normalize_output_format(request_context.get("outputFormat"))
        if not image_url:
            warnings.append("当前会话还没有主图，提交图片任务前需要先上传或粘贴图片 URL。")
        instruction = self._build_instruction(message=message, skill=skill, has_target_hint=has_target_hint)
        tool_payload: dict[str, Any] = {
            "instruction": instruction,
            "editSkill": skill,
            "quality": quality,
            "size": size,
            "output_format": output_format,
        }
        if refs:
            tool_payload["referenceImages"] = refs
        if selection_hints:
            tool_payload["selectionHints"] = selection_hints
        if request_context.get("maskUrl"):
            tool_payload["maskUrl"] = request_context["maskUrl"]
        for key in ("projectId", "flowStepKey", "flowStepName", "flowTemplateId", "inputAssetIds"):
            if session_context.get(key):
                tool_payload[key] = session_context[key]
        route_evidence = self._build_route_evidence(
            message=message,
            image_url=image_url,
            request_context=request_context,
            session_context=session_context,
            tool_payload=tool_payload,
        )
        if route_evidence.get("requiresClarification"):
            warnings.append("当前意图不够明确，请先补充要改哪里、保留什么、希望变成什么效果。")
        edit_plan = (
            self._build_image2_pattern_extract_plan()
            if _has_pattern_extract_intent(message) and target_business_key == "image_edit"
            else self._build_edit_plan(skill=skill, has_reference=bool(refs), has_target_hint=has_target_hint)
        )
        return {
            "intent": "image_edit",
            "title": self._infer_title(message, skill=skill),
            "summary": self._build_summary(message, skill=skill),
            "editPlan": edit_plan,
            "toolPayload": tool_payload,
            "estimatedCostLevel": self._normalize_cost_level(None, tool_payload),
            "riskLevel": self._normalize_risk_level(None, tool_payload),
            "routeEvidence": route_evidence,
            "warnings": warnings,
            "plannerMode": "rule",
            "plannerModel": "rule-planner-v1",
            "rawResponse": {"rulePlanner": True},
        }

    def _build_route_evidence(
        self,
        *,
        message: str,
        image_url: str | None,
        request_context: dict[str, Any],
        session_context: dict[str, Any],
        tool_payload: dict[str, Any],
        parsed: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parsed = parsed or {}
        skill = _safe_text(tool_payload.get("editSkill")) or "local_modify"
        target_business_key = _normalize_agent_business_key(
            parsed.get("targetBusinessKey") or parsed.get("intent"),
            message=message,
            request_context=request_context,
        )
        target_ability = _normalize_agent_tool_name(parsed.get("targetAbility"), fallback_business_key=target_business_key)
        pattern_candidate = _has_pattern_extract_intent(message)
        vague = _is_vague_edit_message(message)
        has_image = bool(image_url)
        missing_fields = _safe_string_list(parsed.get("missingFields"))
        if not has_image and "imageUrl" not in missing_fields:
            missing_fields.append("imageUrl")
        if vague and "editGoal" not in missing_fields:
            missing_fields.append("editGoal")

        parsed_confidence = parsed.get("confidence")
        if parsed_confidence is None:
            confidence = 0.84
            if not has_image:
                confidence -= 0.22
            if vague:
                confidence -= 0.32
            if skill == "canvas_outpaint":
                confidence += 0.04
            if request_context.get("editSkill"):
                confidence += 0.04
        else:
            confidence = _safe_float(parsed_confidence, default=0.72)
        confidence = max(0.25, min(0.96, round(confidence, 2)))

        base_image_role = _normalize_base_image_role(
            _first_text(
                request_context.get("baseImageRole"),
                request_context.get("base_image_role"),
                (session_context.get("assetState") or {}).get("currentBaseImageRole") if isinstance(session_context.get("assetState"), dict) else None,
            )
        )
        parent_run_id = _first_text(
            request_context.get("parentRunId"),
            request_context.get("parent_run_id"),
            request_context.get("previousRunId"),
            request_context.get("previous_run_id"),
        )
        methodology_id = _first_text(request_context.get("methodologyId"), request_context.get("methodology_id"))
        methodology_version = _first_text(request_context.get("methodologyVersion"), request_context.get("methodology_version"))
        parsed_business_key = _safe_text(parsed.get("targetBusinessKey") or parsed.get("intent"), max_length=64)
        route_reason = _safe_text(parsed.get("routeReason"), max_length=600)
        if parsed_business_key and parsed_business_key != target_business_key:
            route_reason = ""
        if not route_reason:
            if target_business_key == "pattern_extract":
                base_reason = "用户明确要求批量、速度、低成本或专项花纹提取，后端白名单路由到 business.pattern_extract。"
            elif pattern_candidate:
                base_reason = "用户目标可由花纹提取专项能力覆盖，但当前 AI 图片助手采用 GPT-5.5 规划 + GPT Image 2 质量优先主路径；专项能力保留给批量、速度或成本优先场景。"
            else:
                base_reason = "当前 AI 图片助手采用 GPT-5.5 规划 + GPT Image 2 质量优先主路径，后端白名单路由到 business.image_edit。"
            if base_image_role == "previous_result":
                base_reason += " 用户继续同一会话，因此默认基于上一轮成功输出继续修改。"
            elif not has_image:
                base_reason += " 当前缺少主图，只能先整理计划，开始执行前必须补图。"
            route_reason = base_reason
        rejected = _normalize_rejected_abilities(parsed.get("rejectedAbilities"))
        if not rejected:
            if target_business_key == "pattern_extract":
                rejected = [
                    {"ability": IMAGE_EDIT_TOOL_NAME, "reason": "用户明确要求专项/批量/快速提取，本轮优先使用花纹提取能力。"},
                    {"ability": "business.product_design", "reason": "本轮没有要求生成产品设计图。"},
                    {"ability": "business.promo_video", "reason": "本轮输出目标是图片，不是视频。"},
                ]
            else:
                rejected = [
                    {"ability": "business.product_design", "reason": "本轮是对既有图片进行修改，不是生成产品设计图。"},
                    {
                        "ability": PATTERN_EXTRACT_TOOL_NAME,
                        "reason": "作为批量/速度/成本优先的专项候选保留；当前单张任务先走 GPT Image 2 质量优先主路径。"
                        if pattern_candidate
                        else "用户没有要求提取花纹或还原边缘纹路。",
                    },
                    {"ability": "business.promo_video", "reason": "本轮输出目标是图片，不是视频。"},
                ]
        clarification_reasons = []
        if vague:
            clarification_reasons.append("edit_goal_too_vague")
        route_type = "ability_accelerated" if target_business_key == "pattern_extract" else "image2_quality_first"
        if clarification_reasons:
            route_type = "clarification_required"
        specialized_candidate = (
            {
                "targetAbility": PATTERN_EXTRACT_TOOL_NAME,
                "targetBusinessKey": "pattern_extract",
                "reason": "该意图存在专项花纹提取能力，可在批量、速度或成本优先时分流。",
            }
            if pattern_candidate and target_business_key != "pattern_extract"
            else None
        )
        return {
            "intent": target_business_key,
            "routeType": route_type,
            "targetAbility": target_ability,
            "targetBusinessKey": target_business_key,
            "primaryExecutionEngine": "podi-specialized-ability" if target_business_key == "pattern_extract" else "gpt-image-2",
            "plannerModelFamily": "gpt-5.5",
            "specializedAbilityCandidate": specialized_candidate,
            "confidence": confidence,
            "threshold": ROUTE_CONFIDENCE_THRESHOLD,
            "baseImageRole": base_image_role,
            "parentRunId": parent_run_id,
            "methodologyId": methodology_id,
            "methodologyVersion": methodology_version,
            "missingFields": missing_fields,
            "routeReason": route_reason,
            "rejectedAbilities": rejected,
            "requiresClarification": bool(clarification_reasons),
            "clarificationReasons": clarification_reasons,
        }

    @staticmethod
    def _infer_skill(message: str, *, has_reference: bool, has_target_hint: bool, explicit_skill: Any) -> str:
        explicit = _safe_text(explicit_skill)
        if explicit in IMAGE_EDIT_SKILL_VALUES:
            return explicit
        text = message.lower()
        if any(token in text for token in ["扩图", "外扩", "扩展画布", "outpaint", "延展"]):
            return "canvas_outpaint"
        if any(token in text for token in ["删除", "去掉", "移除", "修补", "水印", "瑕疵", "杂物"]):
            return "remove_inpaint" if has_target_hint else "local_modify"
        if has_reference and any(token in text for token in ["补色", "色调", "配色", "颜色参考", "冷暖", "饱和"]):
            return "color_reference_correction"
        if has_reference and any(token in text for token in ["参考", "替换", "材质", "质感", "元素"]):
            return "reference_element_transfer"
        return "local_modify"

    @staticmethod
    def _build_instruction(*, message: str, skill: str, has_target_hint: bool) -> str:
        base = (_safe_text(message, max_length=2400) or "优化图片，使画面更自然、更适合商业使用。").rstrip("。.!！?？；; ")
        constraints = ["保持未提及区域不变", "保持主体结构和构图稳定", "不要新增无关文字、水印或多余元素"]
        if _has_pattern_extract_intent(message) and skill == "local_modify":
            constraints = [
                "使用 GPT Image 2 做单张质量优先处理",
                "提取并还原主要花纹/图案主体",
                "弱化桌布、衣物、阴影或拍摄背景干扰",
                "保持纹理自然、边缘完整，适合后续裂变和产品设计使用",
            ]
        elif skill == "canvas_outpaint":
            constraints = ["只补全外扩区域", "原图已有内容尽量保持不变", "延续原图纹理、光照和图案密度"]
        elif skill == "remove_inpaint":
            constraints = ["删除或修补目标区域", "自然补齐背景", "不要改变其他区域"]
        elif skill in REFERENCE_REQUIRED_SKILLS:
            constraints = ["只迁移用户要求的参考特征", "保持主图构图和主体不变", "不要直接拼贴参考图"]
        elif not has_target_hint:
            constraints.append("如果没有明确区域，就做整体轻量优化")
        return f"{base}。执行约束：{'；'.join(constraints)}。"

    @staticmethod
    def _infer_title(message: str, *, skill: str) -> str:
        labels = {
            "pattern_extract": "花纹提取",
            "local_modify": "局部/整体轻量改图",
            "reference_element_transfer": "参考图风格/元素迁移",
            "remove_inpaint": "删除修补",
            "color_reference_correction": "补色校正",
            "canvas_outpaint": "扩展画布",
        }
        title = "高质量花纹提取" if _has_pattern_extract_intent(message) and skill == "local_modify" else labels.get(skill, "图编辑方案")
        text = _safe_text(message, max_length=28)
        return f"{title} · {text}" if text else title

    @staticmethod
    def _build_summary(message: str, *, skill: str) -> str:
        skill_label = {
            "pattern_extract": "花纹提取",
            "local_modify": "局部修改",
            "reference_element_transfer": "参考图替换",
            "remove_inpaint": "删除修补",
            "color_reference_correction": "补色校正",
            "canvas_outpaint": "扩展画布",
        }.get(skill, "图编辑")
        text = _safe_text(message, max_length=160) or "优化图片"
        if skill == "pattern_extract":
            return f"已将需求整理为「花纹提取」任务：{text}"
        if _has_pattern_extract_intent(message) and skill == "local_modify":
            return f"已按质量优先主路径整理为「GPT Image 2 花纹提取」任务：{text}"
        return f"已将需求整理为「{skill_label}」任务：{text}"

    @staticmethod
    def _build_pattern_extract_prompt(message: str) -> str:
        base = _safe_text(message, max_length=2000) or "提取图片中的花纹图案"
        return (
            f"{base}。执行约束：提取并还原主要花纹/图案主体；弱化桌布、衣物或背景材质干扰；"
            "保持纹理自然、边缘完整、适合后续裂变和产品设计使用。"
        )

    @staticmethod
    def _build_pattern_extract_plan() -> list[dict[str, str]]:
        return [
            {"step": "识别提取目标", "reason": "确认用户要从当前图片中取出花纹/图案主体。"},
            {"step": "分离背景干扰", "reason": "降低桌布、衣物、阴影或拍摄背景对图案的影响。"},
            {"step": "输出可复用花纹", "reason": "生成适合后续裂变、设计和组图使用的图案结果。"},
        ]

    @staticmethod
    def _build_image2_pattern_extract_plan() -> list[dict[str, str]]:
        return [
            {"step": "理解提取目标", "reason": "先由 GPT-5.5 将用户诉求整理成单张高质量图片处理计划。"},
            {"step": "调用 Image 2 质量路径", "reason": "当前阶段优先追求结果上限，而不是使用速度更快但上限较低的专项小模型。"},
            {"step": "输出可继续使用的图案", "reason": "结果需要适合后续裂变、产品设计和人工复盘。"},
        ]

    @staticmethod
    def _build_edit_plan(*, skill: str, has_reference: bool, has_target_hint: bool) -> list[dict[str, str]]:
        steps = [
            {"step": "识别用户目标", "reason": "先把自然语言需求转成明确的图编辑动作。"},
            {"step": "保护原图主体", "reason": "默认保持构图、主体结构和未提及区域稳定。"},
        ]
        if skill == "canvas_outpaint":
            steps.append({"step": "补全外扩区域", "reason": "只让模型生成画布外扩部分，降低原图被重绘的风险。"})
        elif skill == "remove_inpaint":
            steps.append({"step": "修补目标区域", "reason": "删除或弱化目标内容，并自然补齐背景。"})
        elif skill in REFERENCE_REQUIRED_SKILLS and has_reference:
            steps.append({"step": "受控使用参考图", "reason": "参考图只提供用户要求的颜色、材质或元素方向。"})
        elif has_target_hint:
            steps.append({"step": "按标注区域处理", "reason": "优先改动用户圈定的位置，减少误改。"})
        else:
            steps.append({"step": "整体轻量优化", "reason": "未指定区域时采用保守改图策略。"})
        return steps

    @staticmethod
    def _normalize_edit_plan(value: Any) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return [{"step": "整理图编辑需求", "reason": "把用户意图转成可执行参数。"}]
        items: list[dict[str, str]] = []
        for item in value[:6]:
            if isinstance(item, dict):
                step = _safe_text(item.get("step"), max_length=120)
                reason = _safe_text(item.get("reason"), max_length=240)
            else:
                step = _safe_text(item, max_length=120)
                reason = "按用户需求执行。"
            if step:
                items.append({"step": step, "reason": reason or "按用户需求执行。"})
        return items or [{"step": "整理图编辑需求", "reason": "把用户意图转成可执行参数。"}]

    @staticmethod
    def _normalize_cost_level(value: Any, tool_payload: dict[str, Any]) -> str:
        text = _safe_text(value).lower()
        if text in {"low", "medium", "high"}:
            return text
        quality = _safe_text(tool_payload.get("quality"))
        size = _safe_text(tool_payload.get("size"))
        if quality == "premium" or size in {"3840x2160", "2160x3840"}:
            return "high"
        if quality == "production" or tool_payload.get("editSkill") == "canvas_outpaint":
            return "medium"
        return "low"

    @staticmethod
    def _normalize_risk_level(value: Any, tool_payload: dict[str, Any]) -> str:
        text = _safe_text(value).lower()
        if text in {"low", "medium", "high"}:
            return text
        skill = tool_payload.get("editSkill")
        if skill in {"remove_inpaint", "reference_element_transfer"}:
            return "medium"
        return "low"


class BusinessAgentService:
    def __init__(self) -> None:
        self.planner = BusinessAgentPlanner()

    @staticmethod
    def _persistable_user_id(user: User | None) -> str | None:
        user_id = _safe_text(getattr(user, "id", None), max_length=64)
        if not user_id or user_id == "service" or user_id.startswith("business-api-key:"):
            return None
        return user_id

    def create_session(self, payload: BusinessAgentSessionCreateRequest, *, user: User | None) -> dict[str, Any]:
        agent_key = _safe_text(payload.agentKey or IMAGE_EDIT_AGENT_KEY, max_length=96)
        if agent_key not in ALLOWED_AGENT_KEYS:
            raise HTTPException(status_code=404, detail="AGENT_CAPABILITY_NOT_FOUND")
        image_url = _valid_http_url(payload.imageUrl) if payload.imageUrl else None
        now = _now()
        context = dict(payload.context or {})
        if payload.projectId:
            context["projectId"] = payload.projectId
        session_id = _safe_id("ags")
        request_id = _safe_text(payload.requestId, max_length=64) or None
        tenant_id = _first_text(payload.tenantId, getattr(user, "tenant_id", None))
        client_id = _first_text(payload.clientId, getattr(user, "client_id", None))
        existing_session_id_for_message: str | None = None
        if request_id:
            with get_session() as db:
                existing_session = self._find_existing_session_by_request_id(
                    db,
                    agent_key=agent_key,
                    request_id=request_id,
                    tenant_id=tenant_id,
                    client_id=client_id,
                )
                if existing_session:
                    self._ensure_session_access(existing_session, user=user)
                    if payload.message and not existing_session.latest_plan_id:
                        existing_session_id_for_message = existing_session.id
                    else:
                        return self._create_session_response_from_existing(db, session_id=existing_session.id)
            if existing_session_id_for_message:
                return self.send_message(
                    existing_session_id_for_message,
                    self._initial_message_request(payload, image_url=image_url),
                    user=user,
                )
        session_obj = BusinessAgentSession(
            id=session_id,
            agent_key=agent_key,
            status="collecting_context",
            title=_safe_text(payload.title, max_length=128) or None,
            image_url=image_url,
            trace_id=_safe_text(payload.traceId, max_length=64) or uuid4().hex,
            request_id=request_id,
            tenant_id=tenant_id,
            client_id=client_id,
            user_id=self._persistable_user_id(user),
            user_name=_safe_text(getattr(user, "username", None), max_length=128) or None,
            context=context,
            extra_metadata={
                **(payload.metadata or {}),
                "source": payload.source or "image-edit-chat",
                "channel": payload.channel or "eval-agent",
                "businessKey": AGENT_BUSINESS_KEY,
            },
            created_at=now,
            updated_at=now,
        )
        with get_session() as db:
            db.add(session_obj)
            db.commit()
        if payload.message:
            return self.send_message(
                session_id,
                self._initial_message_request(payload, image_url=image_url),
                user=user,
            )
        return {"session": self.get_session(session_id, user=user)}

    def send_message(self, session_id: str, payload: BusinessAgentMessageRequest, *, user: User | None) -> dict[str, Any]:
        message = _safe_text(payload.message)
        if not message:
            raise HTTPException(status_code=400, detail="AGENT_MESSAGE_REQUIRED")
        image_url = _valid_http_url(payload.imageUrl) if payload.imageUrl else None
        request_id = _safe_text(payload.requestId, max_length=128) or None
        with get_session() as db:
            session_obj = self._get_session_for_update(db, session_id=session_id, user=user)
            if request_id and self._find_existing_message_by_request_id(db, session_id=session_obj.id, request_id=request_id):
                return self._message_response_from_existing_request(db, session_id=session_obj.id, request_id=request_id)
            if image_url:
                session_obj.image_url = image_url
            request_context = self._request_context_from_message(payload)
            request_context = self._apply_previous_result_base_image(
                db,
                session_obj=session_obj,
                request_context=request_context,
            )
            session_context = dict(session_obj.context or {})
            plan_payload = self.planner.generate_plan(
                message=message,
                image_url=session_obj.image_url,
                request_context=request_context,
                session_context=session_context,
            )
            target_business_key = _normalize_agent_business_key(
                (plan_payload.get("routeEvidence") or {}).get("targetBusinessKey")
                if isinstance(plan_payload.get("routeEvidence"), dict)
                else plan_payload.get("targetBusinessKey") or plan_payload.get("intent"),
                message=message,
                request_context=request_context,
            )
            tool_payload = self._build_tool_payload(
                plan_payload.get("toolPayload") or {},
                session_obj=session_obj,
                request_context=request_context,
                target_business_key=target_business_key,
            )
            route_evidence = self._normalize_route_evidence(
                plan_payload.get("routeEvidence"),
                session_obj=session_obj,
                request_context=request_context,
                tool_payload=tool_payload,
                message=message,
            )
            working_memory = self._build_working_memory(
                session_obj=session_obj,
                message=message,
                tool_payload=tool_payload,
                route_evidence=route_evidence,
            )
            asset_state = self._build_asset_state(
                session_obj=session_obj,
                request_context=request_context,
                route_evidence=route_evidence,
            )
            methodology = self._build_methodology_snapshot(request_context=request_context, route_evidence=route_evidence)
            plan_raw_response = self._build_plan_raw_response(
                plan_payload=plan_payload,
                route_evidence=route_evidence,
                working_memory=working_memory,
                asset_state=asset_state,
                methodology=methodology,
            )
            warnings = [str(item) for item in plan_payload.get("warnings") or [] if str(item).strip()]
            if route_evidence.get("requiresClarification") and not any("意图不够明确" in item for item in warnings):
                warnings.append("当前意图不够明确，请先补充要改哪里、保留什么、希望变成什么效果。")
            now = _now()
            plan = BusinessAgentPlan(
                id=_safe_id("agp"),
                session_id=session_obj.id,
                agent_key=session_obj.agent_key,
                status="awaiting_confirmation",
                intent=target_business_key,
                title=_safe_text(plan_payload.get("title"), max_length=128) or "图片处理计划",
                summary=_safe_text(plan_payload.get("summary"), max_length=2000),
                edit_plan=plan_payload.get("editPlan") or [],
                tool_name=_tool_name_for_business_key(target_business_key),
                tool_payload=tool_payload,
                estimated_cost_level=_safe_text(plan_payload.get("estimatedCostLevel"), max_length=32) or "low",
                risk_level=_safe_text(plan_payload.get("riskLevel"), max_length=32) or "low",
                confirmation_required=True,
                planner_model=_safe_text(plan_payload.get("plannerModel"), max_length=128),
                planner_mode=_safe_text(plan_payload.get("plannerMode"), max_length=64),
                warnings=warnings,
                raw_response=plan_raw_response,
                created_at=now,
                updated_at=now,
            )
            user_message = BusinessAgentMessage(
                id=_safe_id("agm"),
                session_id=session_obj.id,
                role="user",
                content=message,
                attachments=self._message_attachments(image_url=session_obj.image_url, request_context=request_context),
                plan_id=plan.id,
                request_id=request_id,
                extra_metadata=payload.metadata or {},
                created_at=now,
            )
            assistant_message = BusinessAgentMessage(
                id=_safe_id("agm"),
                session_id=session_obj.id,
                role="assistant",
                content=plan.summary,
                plan_id=plan.id,
                extra_metadata={"messageType": "plan_card"},
                created_at=now,
            )
            session_obj.status = "awaiting_confirmation"
            session_obj.latest_plan_id = plan.id
            session_obj.title = session_obj.title or plan.title
            session_obj.context = {
                **session_context,
                "workingMemory": working_memory,
                "assetState": asset_state,
                "lastRouteEvidence": route_evidence,
            }
            session_obj.updated_at = now
            db.add(user_message)
            db.add(plan)
            db.add(assistant_message)
            db.add(session_obj)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                if request_id:
                    return self._message_response_from_existing_request(db, session_id=session_obj.id, request_id=request_id)
                raise
            return {"session": self._read_session(db, session_id=session_obj.id), "plan": self._plan_to_dict(plan)}

    def confirm_plan(
        self,
        session_id: str,
        plan_id: str,
        payload: BusinessAgentConfirmRequest,
        *,
        user: User | None,
    ) -> dict[str, Any]:
        with get_session() as db:
            session_obj = self._get_session_for_update(db, session_id=session_id, user=user)
            plan = (
                db.execute(
                    select(BusinessAgentPlan)
                    .where(BusinessAgentPlan.id == plan_id)
                    .with_for_update()
                )
                .scalars()
                .first()
            )
            if not plan or plan.session_id != session_obj.id:
                raise HTTPException(status_code=404, detail="AGENT_PLAN_NOT_FOUND")
            existing_tool_call = self._latest_tool_call_for_plan(db, plan_id=plan.id)
            if plan.status == "executed" and existing_tool_call and existing_tool_call.run_id:
                return self._confirm_response_from_existing_tool_call(
                    db,
                    session_id=session_id,
                    plan=plan,
                    tool_call=existing_tool_call,
                )
            if session_obj.latest_plan_id and session_obj.latest_plan_id != plan.id:
                raise HTTPException(status_code=409, detail="AGENT_PLAN_STALE")
            if plan.status == "confirming":
                raise HTTPException(status_code=409, detail="AGENT_PLAN_CONFIRM_IN_PROGRESS")
            if plan.status not in {"awaiting_confirmation", "failed"}:
                raise HTTPException(status_code=409, detail="AGENT_PLAN_NOT_CONFIRMABLE")
            tool_payload = self._merge_confirm_overrides(plan.tool_payload or {}, payload.overrides or {})
            image_url = _valid_http_url(tool_payload.get("imageUrl") or session_obj.image_url)
            if not image_url:
                raise HTTPException(status_code=400, detail="AGENT_IMAGE_URL_REQUIRED")
            route_evidence = self._plan_route_evidence(plan)
            target_business_key = self._target_business_key_from_plan(plan, route_evidence=route_evidence)
            target_tool_name = _tool_name_for_business_key(target_business_key)
            if self._route_requires_clarification(route_evidence):
                raise HTTPException(status_code=409, detail="AGENT_PLAN_REQUIRES_CLARIFICATION")
            tool_payload["imageUrl"] = image_url
            request_id = _safe_text(payload.requestId or session_obj.request_id or f"{session_obj.id}:{plan.id}", max_length=128)
            run_payload = self._to_business_run_request(
                tool_payload=tool_payload,
                session_obj=session_obj,
                plan=plan,
                callback_url=payload.callbackUrl,
                callback_headers=payload.callbackHeaders,
                request_id=request_id,
            )
            tool_call = BusinessAgentToolCall(
                id=_safe_id("agtc"),
                session_id=session_obj.id,
                plan_id=plan.id,
                tool_name=target_tool_name,
                business_key=target_business_key,
                status="queued",
                request_payload=run_payload.model_dump(exclude_none=True),
                created_at=_now(),
                updated_at=_now(),
            )
            tool_call_id = tool_call.id
            now = _now()
            plan.status = "confirming"
            plan.error_code = None
            plan.error_message = None
            plan.updated_at = now
            session_obj.status = "confirming"
            session_obj.updated_at = now
            db.add(tool_call)
            db.add(plan)
            db.add(session_obj)
            db.commit()

        try:
            run = get_business_run_service().create_run(
                business_key=target_business_key,
                payload=run_payload,
                user=user,
                source="image-edit-chat",
            )
        except HTTPException as exc:
            self._mark_tool_call_failed(
                tool_call_id=tool_call_id,
                plan_id=plan_id,
                session_id=session_id,
                error_code=str(exc.detail or "AGENT_TOOL_CALL_FAILED"),
                error_message=str(exc.detail or ""),
            )
            raise
        except Exception as exc:
            self._mark_tool_call_failed(
                tool_call_id=tool_call_id,
                plan_id=plan_id,
                session_id=session_id,
                error_code="AGENT_TOOL_CALL_FAILED",
                error_message=str(exc),
            )
            raise

        run_response = self._run_submit_response(run)
        run_id = str(run_response.get("runId") or "")
        with get_session() as db:
            db_tool_call = db.get(BusinessAgentToolCall, tool_call_id)
            db_plan = db.get(BusinessAgentPlan, plan_id)
            db_session = db.get(BusinessAgentSession, session_id)
            if not db_tool_call or not db_plan or not db_session:
                raise HTTPException(status_code=404, detail="AGENT_SESSION_NOT_FOUND")
            now = _now()
            db_tool_call.status = "submitted"
            db_tool_call.run_id = run_id
            db_tool_call.response_payload = run_response
            db_tool_call.updated_at = now
            db_plan.status = "executed"
            db_plan.confirmed_at = db_plan.confirmed_at or now
            db_plan.executed_at = now
            db_plan.tool_payload = tool_payload
            db_plan.updated_at = now
            db_session.status = "running"
            db_session.latest_run_id = run_id
            db_session.updated_at = now
            db.add(
                BusinessAgentMessage(
                    id=_safe_id("agm"),
                    session_id=db_session.id,
                    role="tool",
                    content=f"已提交{self._business_key_label(target_business_key)}任务，runId={run_id}",
                    plan_id=db_plan.id,
                    run_id=run_id,
                    extra_metadata={"messageType": "tool_result"},
                    created_at=now,
                )
            )
            db.add(db_tool_call)
            db.add(db_plan)
            db.add(db_session)
            db.commit()
            return {
                "session": self._read_session(db, session_id=session_id),
                "plan": self._plan_to_dict(db_plan),
                "tool_call": self._tool_call_to_dict(db_tool_call),
                "run": run_response,
            }

    def confirm_latest_plan(
        self,
        session_id: str,
        payload: BusinessAgentConfirmRequest,
        *,
        user: User | None,
    ) -> dict[str, Any]:
        plan_id = _safe_text(payload.planId, max_length=64)
        if not plan_id:
            session_payload = self.get_session(session_id, user=user)
            plan_id = _safe_text(session_payload.get("latestPlanId"), max_length=64)
        if not plan_id:
            raise HTTPException(status_code=400, detail="AGENT_PLAN_REQUIRED")
        return self.confirm_plan(session_id, plan_id, payload, user=user)

    def get_session(self, session_id: str, *, user: User | None) -> dict[str, Any]:
        with get_session() as db:
            session_obj = db.get(BusinessAgentSession, session_id)
            if not session_obj:
                raise HTTPException(status_code=404, detail="AGENT_SESSION_NOT_FOUND")
            self._ensure_session_access(session_obj, user=user)
            return self._read_session(db, session_id=session_id)

    @staticmethod
    def _find_existing_session_by_request_id(
        db: Any,
        *,
        agent_key: str,
        request_id: str,
        tenant_id: str | None,
        client_id: str | None,
    ) -> BusinessAgentSession | None:
        stmt = select(BusinessAgentSession).where(
            BusinessAgentSession.agent_key == agent_key,
            BusinessAgentSession.request_id == request_id,
        )
        stmt = stmt.where(BusinessAgentSession.tenant_id == tenant_id) if tenant_id else stmt.where(BusinessAgentSession.tenant_id.is_(None))
        stmt = stmt.where(BusinessAgentSession.client_id == client_id) if client_id else stmt.where(BusinessAgentSession.client_id.is_(None))
        return db.execute(stmt.order_by(BusinessAgentSession.created_at.desc())).scalars().first()

    def _create_session_response_from_existing(self, db: Any, *, session_id: str) -> dict[str, Any]:
        session_payload = self._read_session(db, session_id=session_id)
        response: dict[str, Any] = {"session": session_payload}
        latest_plan = session_payload.get("latestPlan")
        if latest_plan:
            response["plan"] = latest_plan
        return response

    @staticmethod
    def _initial_message_request(
        payload: BusinessAgentSessionCreateRequest,
        *,
        image_url: str | None,
    ) -> BusinessAgentMessageRequest:
        return BusinessAgentMessageRequest(
            message=payload.message or "",
            imageUrl=image_url,
            editSkill=payload.editSkill,
            quality=payload.quality,
            size=payload.size,
            outputFormat=payload.outputFormat,
            maskUrl=payload.maskUrl,
            referenceImages=payload.referenceImages,
            selectionHints=payload.selectionHints,
            context=payload.context,
            metadata=payload.metadata,
            requestId=payload.requestId,
        )

    @staticmethod
    def _latest_tool_call_for_plan(db: Any, *, plan_id: str) -> BusinessAgentToolCall | None:
        return (
            db.execute(
                select(BusinessAgentToolCall)
                .where(BusinessAgentToolCall.plan_id == plan_id)
                .order_by(BusinessAgentToolCall.created_at.desc())
            )
            .scalars()
            .first()
        )

    @staticmethod
    def _find_existing_message_by_request_id(
        db: Any,
        *,
        session_id: str,
        request_id: str,
    ) -> BusinessAgentMessage | None:
        return (
            db.execute(
                select(BusinessAgentMessage)
                .where(
                    BusinessAgentMessage.session_id == session_id,
                    BusinessAgentMessage.request_id == request_id,
                    BusinessAgentMessage.role == "user",
                )
                .order_by(BusinessAgentMessage.created_at.desc())
            )
            .scalars()
            .first()
        )

    def _message_response_from_existing_request(
        self,
        db: Any,
        *,
        session_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        existing_message = self._find_existing_message_by_request_id(db, session_id=session_id, request_id=request_id)
        session_payload = self._read_session(db, session_id=session_id)
        if existing_message and existing_message.plan_id:
            plan = db.get(BusinessAgentPlan, existing_message.plan_id)
            if plan:
                return {"session": session_payload, "plan": self._plan_to_dict(plan)}
        latest_plan = session_payload.get("latestPlan")
        if latest_plan:
            return {"session": session_payload, "plan": latest_plan}
        raise HTTPException(status_code=409, detail="AGENT_MESSAGE_DUPLICATE_IN_PROGRESS")

    def _confirm_response_from_existing_tool_call(
        self,
        db: Any,
        *,
        session_id: str,
        plan: BusinessAgentPlan,
        tool_call: BusinessAgentToolCall,
    ) -> dict[str, Any]:
        run_response = tool_call.response_payload if isinstance(tool_call.response_payload, dict) else {}
        if not run_response:
            run_response = {
                "runId": tool_call.run_id,
                "businessKey": tool_call.business_key or "image_edit",
                "status": "submitted",
                "retryAfterSeconds": 5,
                "pollUrl": "/api/business/runs/get",
            }
        return {
            "session": self._read_session(db, session_id=session_id),
            "plan": self._plan_to_dict(plan),
            "tool_call": self._tool_call_to_dict(tool_call),
            "run": run_response,
        }

    @staticmethod
    def _mark_tool_call_failed(
        *,
        tool_call_id: str,
        plan_id: str,
        session_id: str,
        error_code: str,
        error_message: str,
    ) -> None:
        now = _now()
        with get_session() as db:
            db_tool_call = db.get(BusinessAgentToolCall, tool_call_id)
            db_plan = db.get(BusinessAgentPlan, plan_id)
            db_session = db.get(BusinessAgentSession, session_id)
            if db_tool_call:
                db_tool_call.status = "failed"
                db_tool_call.error_code = error_code
                db_tool_call.error_message = _safe_text(error_message, max_length=500)
                db_tool_call.updated_at = now
                db.add(db_tool_call)
            if db_plan:
                db_plan.status = "failed"
                db_plan.error_code = error_code
                db_plan.error_message = _safe_text(error_message, max_length=500)
                db_plan.updated_at = now
                db.add(db_plan)
            if db_session:
                db_session.status = "failed"
                db_session.updated_at = now
                db.add(db_session)
            db.commit()

    def _get_session_for_update(self, db: Any, *, session_id: str, user: User | None) -> BusinessAgentSession:
        session_obj = db.get(BusinessAgentSession, session_id)
        if not session_obj:
            raise HTTPException(status_code=404, detail="AGENT_SESSION_NOT_FOUND")
        self._ensure_session_access(session_obj, user=user)
        return session_obj

    @staticmethod
    def _ensure_session_access(session_obj: BusinessAgentSession, *, user: User | None) -> None:
        if not user:
            return
        role = str(getattr(user, "role", "") or "").lower()
        if role in {"admin", "service"}:
            return
        user_tenant = _safe_text(getattr(user, "tenant_id", None), max_length=64)
        user_client = _safe_text(getattr(user, "client_id", None), max_length=64)
        if session_obj.tenant_id and user_tenant and session_obj.tenant_id != user_tenant:
            raise HTTPException(status_code=403, detail="AGENT_SESSION_FORBIDDEN")
        if session_obj.client_id and user_client and session_obj.client_id != user_client:
            raise HTTPException(status_code=403, detail="AGENT_SESSION_FORBIDDEN")

    @staticmethod
    def _request_context_from_message(payload: BusinessAgentMessageRequest) -> dict[str, Any]:
        refs = _normalize_reference_images(payload.referenceImages)
        hints = _normalize_selection_hints(payload.selectionHints)
        context = dict(payload.context or {})
        return {
            **context,
            "imageUrl": _safe_text(payload.imageUrl, max_length=1024) or None,
            "editSkill": _safe_text(payload.editSkill) or None,
            "quality": _safe_text(payload.quality) or None,
            "size": _safe_text(payload.size) or None,
            "outputFormat": _safe_text(payload.outputFormat) or None,
            "maskUrl": _safe_text(payload.maskUrl, max_length=1024) or None,
            "referenceImages": refs,
            "selectionHints": hints,
        }

    @staticmethod
    def _message_attachments(*, image_url: str | None, request_context: dict[str, Any]) -> list[dict[str, Any]]:
        attachments: list[dict[str, Any]] = []
        if image_url:
            role = _normalize_base_image_role(
                _first_text(request_context.get("baseImageRole"), request_context.get("base_image_role"))
            )
            attachments.append({"type": "image", "url": image_url, "role": role})
        for item in request_context.get("referenceImages") or []:
            if isinstance(item, dict) and item.get("url"):
                attachments.append({"type": "image", "url": item["url"], "role": "reference"})
        return attachments

    @staticmethod
    def _first_business_run_image_url(run: BusinessRun | None) -> str | None:
        if not run or str(run.status or "").lower() != "succeeded":
            return None
        for value in run.image_urls or []:
            url = _valid_http_url(value)
            if url:
                return url
        payload = run.result_payload if isinstance(run.result_payload, dict) else {}
        for key in ("imageUrls", "image_urls", "resultUrls", "images", "assets"):
            values = payload.get(key)
            if not isinstance(values, list):
                continue
            for item in values:
                if isinstance(item, str):
                    url = _valid_http_url(item)
                elif isinstance(item, dict):
                    url = _valid_http_url(item.get("storedUrl") or item.get("url"))
                else:
                    url = None
                if url:
                    return url
        return None

    def _apply_previous_result_base_image(
        self,
        db: Any,
        *,
        session_obj: BusinessAgentSession,
        request_context: dict[str, Any],
    ) -> dict[str, Any]:
        explicit_image = _valid_http_url(request_context.get("imageUrl"))
        if explicit_image:
            return request_context
        explicit_base_role = _first_text(request_context.get("baseImageRole"), request_context.get("base_image_role"))
        normalized_base_role = _normalize_base_image_role(explicit_base_role)
        if explicit_base_role and normalized_base_role != "previous_result":
            return request_context
        parent_run_id = _first_text(
            request_context.get("parentRunId"),
            request_context.get("parent_run_id"),
            request_context.get("previousRunId"),
            request_context.get("previous_run_id"),
            session_obj.latest_run_id,
        )
        if not parent_run_id:
            return request_context
        latest_run = db.get(BusinessRun, parent_run_id)
        result_url = self._first_business_run_image_url(latest_run)
        if not result_url:
            return request_context
        next_context = dict(request_context)
        next_context["imageUrl"] = result_url
        next_context["baseImageRole"] = "previous_result"
        next_context["parentRunId"] = parent_run_id
        session_obj.image_url = result_url
        return next_context

    def _normalize_route_evidence(
        self,
        value: Any,
        *,
        session_obj: BusinessAgentSession,
        request_context: dict[str, Any],
        tool_payload: dict[str, Any],
        message: str,
    ) -> dict[str, Any]:
        evidence = value if isinstance(value, dict) else {}
        if not evidence:
            evidence = self.planner._build_route_evidence(
                message=message,
                image_url=session_obj.image_url,
                request_context=request_context,
                session_context=dict(session_obj.context or {}),
                tool_payload=tool_payload,
            )
        confidence = max(0.0, min(1.0, round(_safe_float(evidence.get("confidence"), default=0.72), 2)))
        threshold = max(0.0, min(1.0, _safe_float(evidence.get("threshold"), default=ROUTE_CONFIDENCE_THRESHOLD)))
        base_role = _normalize_base_image_role(evidence.get("baseImageRole"))
        parent_run_id = _first_text(evidence.get("parentRunId"))
        missing_fields = _safe_string_list(evidence.get("missingFields"))
        clarification_reasons = _safe_string_list(evidence.get("clarificationReasons"))
        blocking_missing_fields = [
            item
            for item in missing_fields
            if item.replace("_", "").lower()
            not in {
                "imageurl",
                "sourceimageurl",
                "currentbaseimageurl",
            }
        ]
        if blocking_missing_fields and "missing_required_fields" not in clarification_reasons:
            clarification_reasons.append("missing_required_fields")
        if confidence < threshold and "low_route_confidence" not in clarification_reasons:
            clarification_reasons.append("low_route_confidence")
        if evidence.get("requiresClarification") and not clarification_reasons:
            clarification_reasons.append("route_requires_clarification")
        target_business_key = _normalize_agent_business_key(
            evidence.get("targetBusinessKey") or evidence.get("intent"),
            message=message,
            request_context=request_context,
        )
        target_ability = _normalize_agent_tool_name(evidence.get("targetAbility"), fallback_business_key=target_business_key)
        pattern_candidate = _has_pattern_extract_intent(message)
        incoming_business_key = _safe_text(evidence.get("targetBusinessKey") or evidence.get("intent"), max_length=64)
        route_reason = _safe_text(evidence.get("routeReason"), max_length=800)
        if incoming_business_key and incoming_business_key != target_business_key:
            route_reason = ""
        if not route_reason:
            if target_business_key == "pattern_extract":
                route_reason = "用户明确要求批量、速度、低成本或专项花纹提取，后端白名单路由到 business.pattern_extract。"
            elif pattern_candidate:
                route_reason = "用户目标可由花纹提取专项能力覆盖，但当前 AI 图片助手采用 GPT-5.5 规划 + GPT Image 2 质量优先主路径；专项能力保留给批量、速度或成本优先场景。"
            else:
                route_reason = "当前 AI 图片助手采用 GPT-5.5 规划 + GPT Image 2 质量优先主路径，后端白名单路由到 business.image_edit。"
        route_type = _safe_text(evidence.get("routeType"), max_length=64)
        if incoming_business_key and incoming_business_key != target_business_key:
            route_type = ""
        if route_type not in set(ROUTE_TYPE_VALUES):
            route_type = "ability_accelerated" if target_business_key == "pattern_extract" else "image2_quality_first"
        if clarification_reasons:
            route_type = "clarification_required"
        specialized_candidate = evidence.get("specializedAbilityCandidate") if isinstance(evidence.get("specializedAbilityCandidate"), dict) else None
        if not specialized_candidate and pattern_candidate and target_business_key != "pattern_extract":
            specialized_candidate = {
                "targetAbility": PATTERN_EXTRACT_TOOL_NAME,
                "targetBusinessKey": "pattern_extract",
                "reason": "该意图存在专项花纹提取能力，可在批量、速度或成本优先时分流。",
            }
        return {
            "intent": target_business_key,
            "routeType": route_type,
            "targetAbility": target_ability,
            "targetBusinessKey": target_business_key,
            "primaryExecutionEngine": "podi-specialized-ability" if target_business_key == "pattern_extract" else "gpt-image-2",
            "plannerModelFamily": _safe_text(evidence.get("plannerModelFamily"), max_length=64) or "gpt-5.5",
            "specializedAbilityCandidate": specialized_candidate,
            "confidence": confidence,
            "threshold": threshold,
            "baseImageRole": base_role,
            "parentRunId": parent_run_id,
            "methodologyId": _first_text(evidence.get("methodologyId")),
            "methodologyVersion": _first_text(evidence.get("methodologyVersion")),
            "missingFields": missing_fields,
            "routeReason": route_reason,
            "rejectedAbilities": _normalize_rejected_abilities(evidence.get("rejectedAbilities")),
            "requiresClarification": bool(clarification_reasons),
            "clarificationReasons": clarification_reasons,
        }

    @staticmethod
    def _build_working_memory(
        *,
        session_obj: BusinessAgentSession,
        message: str,
        tool_payload: dict[str, Any],
        route_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        existing = (session_obj.context or {}).get("workingMemory") if isinstance(session_obj.context, dict) else {}
        existing = existing if isinstance(existing, dict) else {}
        preserve = _safe_string_list(existing.get("preserveConstraints"), max_items=8)
        for item in ["保持主体结构和构图稳定", "保持未提及区域不变", "不要新增无关文字、水印或多余元素"]:
            if item not in preserve:
                preserve.append(item)
        target_business_key = _safe_text(route_evidence.get("targetBusinessKey"), max_length=64) or "image_edit"
        return {
            "latestUserGoal": _safe_text(message, max_length=500),
            "activeSkill": _safe_text(tool_payload.get("editSkill"), max_length=64) or target_business_key,
            "activeAbility": target_business_key,
            "currentInstruction": _safe_text(tool_payload.get("instruction") or tool_payload.get("prompt"), max_length=1000),
            "preserveConstraints": preserve[:8],
            "baseImageRole": route_evidence.get("baseImageRole") or "source_image",
            "parentRunId": route_evidence.get("parentRunId"),
            "updatedAt": _now().isoformat(),
        }

    @staticmethod
    def _build_asset_state(
        *,
        session_obj: BusinessAgentSession,
        request_context: dict[str, Any],
        route_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        previous_asset_state = (session_obj.context or {}).get("assetState") if isinstance(session_obj.context, dict) else {}
        previous_asset_state = previous_asset_state if isinstance(previous_asset_state, dict) else {}
        current_url = _safe_text(session_obj.image_url, max_length=1024) or None
        source_url = _safe_text(previous_asset_state.get("sourceImageUrl"), max_length=1024) or current_url
        if route_evidence.get("baseImageRole") == "source_image" and current_url:
            source_url = current_url
        return {
            "sourceImageUrl": source_url,
            "currentBaseImageUrl": current_url,
            "currentBaseImageRole": route_evidence.get("baseImageRole") or "source_image",
            "parentRunId": route_evidence.get("parentRunId"),
            "referenceCount": len(request_context.get("referenceImages") or []),
            "selectionHintCount": len(request_context.get("selectionHints") or []),
            "updatedAt": _now().isoformat(),
        }

    @staticmethod
    def _build_methodology_snapshot(*, request_context: dict[str, Any], route_evidence: dict[str, Any]) -> dict[str, Any]:
        target_business_key = _safe_text(route_evidence.get("targetBusinessKey"), max_length=64) or "image_edit"
        methodology_id = _first_text(
            route_evidence.get("methodologyId"),
            request_context.get("methodologyId"),
            request_context.get("methodology_id"),
            "image_edit_chat_mvp",
        )
        methodology_version = _first_text(
            route_evidence.get("methodologyVersion"),
            request_context.get("methodologyVersion"),
            request_context.get("methodology_version"),
            "v0.6",
        )
        return {
            "id": methodology_id,
            "version": methodology_version,
            "phase": "single_pattern_extract" if target_business_key == "pattern_extract" else "single_image_edit",
            "confirmationPoint": "backend_guarded_execution",
        }

    @staticmethod
    def _build_plan_raw_response(
        *,
        plan_payload: dict[str, Any],
        route_evidence: dict[str, Any],
        working_memory: dict[str, Any],
        asset_state: dict[str, Any],
        methodology: dict[str, Any],
    ) -> dict[str, Any]:
        raw_response = plan_payload.get("rawResponse") if isinstance(plan_payload.get("rawResponse"), dict) else {}
        return {
            "plannerRawResponse": raw_response,
            "routeEvidence": route_evidence,
            "workingMemory": working_memory,
            "assetState": asset_state,
            "methodology": methodology,
        }

    @staticmethod
    def _plan_route_evidence(plan: BusinessAgentPlan) -> dict[str, Any]:
        raw = plan.raw_response if isinstance(plan.raw_response, dict) else {}
        evidence = raw.get("routeEvidence") if isinstance(raw.get("routeEvidence"), dict) else {}
        return evidence

    @staticmethod
    def _plan_supporting_context(plan: BusinessAgentPlan, key: str) -> dict[str, Any]:
        raw = plan.raw_response if isinstance(plan.raw_response, dict) else {}
        value = raw.get(key) if isinstance(raw, dict) else {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _route_requires_clarification(route_evidence: dict[str, Any]) -> bool:
        if not route_evidence:
            return False
        missing_fields = _safe_string_list(route_evidence.get("missingFields"))
        blocking_missing_fields = [
            item
            for item in missing_fields
            if item.replace("_", "").lower()
            not in {
                "imageurl",
                "sourceimageurl",
                "currentbaseimageurl",
            }
        ]
        if blocking_missing_fields:
            return True
        confidence = _safe_float(route_evidence.get("confidence"), default=1.0)
        threshold = _safe_float(route_evidence.get("threshold"), default=ROUTE_CONFIDENCE_THRESHOLD)
        if confidence < threshold:
            return True
        if not route_evidence.get("requiresClarification"):
            return False
        reasons = set(_safe_string_list(route_evidence.get("clarificationReasons")))
        return bool(reasons - {"image_missing"})

    @staticmethod
    def _build_tool_payload(
        payload: dict[str, Any],
        *,
        session_obj: BusinessAgentSession,
        request_context: dict[str, Any],
        target_business_key: str,
    ) -> dict[str, Any]:
        clean = {key: value for key, value in payload.items() if key in ALLOWED_TOOL_PAYLOAD_KEYS and value is not None}
        if session_obj.image_url:
            clean["imageUrl"] = session_obj.image_url
        if target_business_key == "pattern_extract":
            pattern_payload: dict[str, Any] = {
                "imageUrl": clean.get("imageUrl"),
                "prompt": (
                _safe_text(clean.get("prompt") or clean.get("instruction") or request_context.get("prompt"), max_length=3000)
                or "提取图片中的花纹图案。"
                ),
                "batch": int(clean.get("batch") or request_context.get("batch") or 1),
                "quality": _normalize_quality(clean.get("quality")),
                "size": _normalize_size(clean.get("size")),
                "output_format": _normalize_output_format(clean.get("output_format") or clean.get("outputFormat")),
            }
            for optional_key in ("negative_prompt", "lora", "width", "height"):
                if clean.get(optional_key):
                    pattern_payload[optional_key] = clean[optional_key]
            for key in ("projectId", "flowStepKey", "flowStepName", "flowTemplateId", "inputAssetIds"):
                value = (session_obj.context or {}).get(key)
                if value:
                    pattern_payload[key] = value
            return {key: value for key, value in pattern_payload.items() if value is not None}
        if request_context.get("maskUrl"):
            clean["maskUrl"] = request_context["maskUrl"]
        if request_context.get("referenceImages"):
            clean["referenceImages"] = request_context["referenceImages"]
        if request_context.get("selectionHints"):
            clean["selectionHints"] = request_context["selectionHints"]
        clean["editSkill"], skill_warnings = _normalize_edit_skill(
            clean.get("editSkill"),
            has_reference=bool(clean.get("referenceImages")),
            has_target_hint=bool(clean.get("selectionHints") or clean.get("maskUrl")),
        )
        clean["quality"] = _normalize_quality(clean.get("quality"))
        clean["size"] = _normalize_size(clean.get("size"))
        clean["output_format"] = _normalize_output_format(clean.get("output_format") or clean.get("outputFormat"))
        clean["instruction"] = _safe_text(clean.get("instruction") or clean.get("prompt"), max_length=3000) or "优化图片，保持主体结构和未提及区域不变。"
        for pattern_only_key in ("prompt", "negative_prompt", "batch", "lora", "width", "height"):
            clean.pop(pattern_only_key, None)
        if skill_warnings:
            clean["metadata"] = {**(clean.get("metadata") if isinstance(clean.get("metadata"), dict) else {}), "plannerWarnings": skill_warnings}
        for key in ("projectId", "flowStepKey", "flowStepName", "flowTemplateId", "inputAssetIds"):
            value = (session_obj.context or {}).get(key)
            if value:
                clean[key] = value
        return clean

    @staticmethod
    def _target_business_key_from_plan(plan: BusinessAgentPlan, *, route_evidence: dict[str, Any]) -> str:
        business_key = _normalize_agent_business_key(
            route_evidence.get("targetBusinessKey") or plan.intent,
            message="",
        )
        if plan.tool_name in ALLOWED_AGENT_TOOLS:
            business_key = ALLOWED_AGENT_TOOLS[plan.tool_name]
        return business_key if business_key in set(ALLOWED_AGENT_TOOLS.values()) else "image_edit"

    @staticmethod
    def _business_key_label(business_key: str) -> str:
        return {
            "image_edit": "图编辑",
            "pattern_extract": "花纹提取",
        }.get(business_key, "图片能力")

    @staticmethod
    def _merge_confirm_overrides(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base or {})
        for key, value in overrides.items():
            if key in ALLOWED_TOOL_PAYLOAD_KEYS and value is not None:
                merged[key] = value
        return merged

    @staticmethod
    def _to_business_run_request(
        *,
        tool_payload: dict[str, Any],
        session_obj: BusinessAgentSession,
        plan: BusinessAgentPlan,
        callback_url: str | None,
        callback_headers: dict[str, str] | None,
        request_id: str,
    ) -> BusinessRunCreateRequest:
        route_evidence = BusinessAgentService._plan_route_evidence(plan)
        working_memory = BusinessAgentService._plan_supporting_context(plan, "workingMemory")
        methodology = BusinessAgentService._plan_supporting_context(plan, "methodology")
        metadata = {
            **(tool_payload.get("metadata") if isinstance(tool_payload.get("metadata"), dict) else {}),
            "agentKey": session_obj.agent_key,
            "agentSessionId": session_obj.id,
            "agentPlanId": plan.id,
            "agentPlannerMode": plan.planner_mode,
            "agentPlannerModel": plan.planner_model,
            "agentToolName": plan.tool_name or _tool_name_for_business_key(route_evidence.get("targetBusinessKey") or "image_edit"),
            "agentRouteEvidence": route_evidence,
            "agentWorkingMemory": working_memory,
            "agentBaseImageRole": route_evidence.get("baseImageRole"),
            "agentParentRunId": route_evidence.get("parentRunId"),
            "agentMethodologyId": methodology.get("id"),
            "agentMethodologyVersion": methodology.get("version"),
        }
        target_business_key = BusinessAgentService._target_business_key_from_plan(plan, route_evidence=route_evidence)
        flow_step_key = "pattern_extract_chat" if target_business_key == "pattern_extract" else "image_edit_chat"
        flow_step_name = "对话花纹提取" if target_business_key == "pattern_extract" else "AI 图片助手图编辑"
        return BusinessRunCreateRequest(
            imageUrl=tool_payload.get("imageUrl") or session_obj.image_url,
            prompt=tool_payload.get("prompt"),
            instruction=tool_payload.get("instruction"),
            editSkill=tool_payload.get("editSkill"),
            quality=tool_payload.get("quality"),
            size=tool_payload.get("size"),
            output_format=tool_payload.get("output_format"),
            batch=tool_payload.get("batch"),
            negative_prompt=tool_payload.get("negative_prompt"),
            lora=tool_payload.get("lora"),
            maskUrl=tool_payload.get("maskUrl"),
            referenceImages=tool_payload.get("referenceImages"),
            selectionHints=tool_payload.get("selectionHints"),
            source="image-edit-chat",
            channel="image-edit-chat",
            traceId=session_obj.trace_id,
            requestId=request_id,
            tenantId=session_obj.tenant_id,
            clientId=session_obj.client_id,
            userId=session_obj.user_id,
            userName=session_obj.user_name,
            callbackUrl=callback_url,
            callbackHeaders=callback_headers,
            metadata=metadata,
            projectId=tool_payload.get("projectId"),
            flowStepKey=tool_payload.get("flowStepKey") or flow_step_key,
            flowStepName=tool_payload.get("flowStepName") or flow_step_name,
            flowTemplateId=tool_payload.get("flowTemplateId"),
            inputAssetIds=tool_payload.get("inputAssetIds"),
            clientRequestId=request_id,
        )

    @staticmethod
    def _run_submit_response(run: Any) -> dict[str, Any]:
        if isinstance(run, dict):
            run_id = str(run.get("runId") or run.get("id") or "").strip()
            return {
                "runId": run_id,
                "businessKey": run.get("businessKey") or run.get("business_key") or "image_edit",
                "status": run.get("status") or "queued",
                "version": run.get("version"),
                "traceId": run.get("traceId") or run.get("trace_id"),
                "requestId": run.get("requestId") or run.get("request_id"),
                "retryAfterSeconds": run.get("retryAfterSeconds") or 5,
                "pollUrl": run.get("pollUrl") or "/api/business/runs/get",
            }
        return {
            "runId": run.id,
            "businessKey": getattr(run, "business_key", "image_edit"),
            "status": getattr(run, "status", "queued"),
            "version": getattr(run, "version", None),
            "traceId": getattr(run, "trace_id", None),
            "requestId": getattr(run, "request_id", None),
            "retryAfterSeconds": 5,
            "pollUrl": "/api/business/runs/get",
        }

    def _read_session(self, db: Any, *, session_id: str) -> dict[str, Any]:
        session_obj = db.get(BusinessAgentSession, session_id)
        if not session_obj:
            raise HTTPException(status_code=404, detail="AGENT_SESSION_NOT_FOUND")
        messages = (
            db.execute(
                select(BusinessAgentMessage)
                .where(BusinessAgentMessage.session_id == session_id)
                .order_by(BusinessAgentMessage.created_at.asc())
            )
            .scalars()
            .all()
        )
        plans = (
            db.execute(
                select(BusinessAgentPlan)
                .where(BusinessAgentPlan.session_id == session_id)
                .order_by(BusinessAgentPlan.created_at.desc())
            )
            .scalars()
            .all()
        )
        tool_calls = (
            db.execute(
                select(BusinessAgentToolCall)
                .where(BusinessAgentToolCall.session_id == session_id)
                .order_by(BusinessAgentToolCall.created_at.desc())
            )
            .scalars()
            .all()
        )
        latest_plan = next((item for item in plans if item.id == session_obj.latest_plan_id), plans[0] if plans else None)
        latest_tool_call = tool_calls[0] if tool_calls else None
        return {
            **self._session_to_dict(session_obj),
            "messages": [self._message_to_dict(item) for item in messages],
            "plans": [self._plan_to_dict(item) for item in plans],
            "toolCalls": [self._tool_call_to_dict(item) for item in tool_calls],
            "latestPlan": self._plan_to_dict(latest_plan) if latest_plan else None,
            "latestToolCall": self._tool_call_to_dict(latest_tool_call) if latest_tool_call else None,
        }

    @staticmethod
    def _session_to_dict(item: BusinessAgentSession) -> dict[str, Any]:
        return {
            "id": item.id,
            "agentKey": item.agent_key,
            "status": item.status,
            "title": item.title,
            "imageUrl": item.image_url,
            "latestPlanId": item.latest_plan_id,
            "latestRunId": item.latest_run_id,
            "traceId": item.trace_id,
            "requestId": item.request_id,
            "tenantId": item.tenant_id,
            "clientId": item.client_id,
            "userId": item.user_id,
            "userName": item.user_name,
            "context": item.context,
            "metadata": item.extra_metadata,
            "createdAt": item.created_at,
            "updatedAt": item.updated_at,
        }

    @staticmethod
    def _message_to_dict(item: BusinessAgentMessage) -> dict[str, Any]:
        return {
            "id": item.id,
            "sessionId": item.session_id,
            "role": item.role,
            "content": item.content,
            "attachments": item.attachments or [],
            "planId": item.plan_id,
            "runId": item.run_id,
            "requestId": item.request_id,
            "metadata": item.extra_metadata,
            "createdAt": item.created_at,
        }

    @staticmethod
    def _plan_to_dict(item: BusinessAgentPlan) -> dict[str, Any]:
        route_evidence = BusinessAgentService._plan_route_evidence(item)
        return {
            "id": item.id,
            "sessionId": item.session_id,
            "agentKey": item.agent_key,
            "status": item.status,
            "intent": item.intent,
            "title": item.title,
            "summary": item.summary,
            "editPlan": item.edit_plan or [],
            "toolName": item.tool_name,
            "toolPayload": item.tool_payload or {},
            "estimatedCostLevel": item.estimated_cost_level,
            "riskLevel": item.risk_level,
            "confirmationRequired": item.confirmation_required,
            "plannerModel": item.planner_model,
            "plannerMode": item.planner_mode,
            "warnings": item.warnings or [],
            "routeEvidence": route_evidence,
            "workingMemory": BusinessAgentService._plan_supporting_context(item, "workingMemory"),
            "assetState": BusinessAgentService._plan_supporting_context(item, "assetState"),
            "methodology": BusinessAgentService._plan_supporting_context(item, "methodology"),
            "baseImageRole": route_evidence.get("baseImageRole"),
            "parentRunId": route_evidence.get("parentRunId"),
            "errorCode": item.error_code,
            "errorMessage": item.error_message,
            "confirmedAt": item.confirmed_at,
            "executedAt": item.executed_at,
            "createdAt": item.created_at,
            "updatedAt": item.updated_at,
        }

    @staticmethod
    def _tool_call_to_dict(item: BusinessAgentToolCall) -> dict[str, Any]:
        return {
            "id": item.id,
            "sessionId": item.session_id,
            "planId": item.plan_id,
            "toolName": item.tool_name,
            "businessKey": item.business_key,
            "runId": item.run_id,
            "status": item.status,
            "requestPayload": item.request_payload,
            "responsePayload": item.response_payload,
            "errorCode": item.error_code,
            "errorMessage": item.error_message,
            "createdAt": item.created_at,
            "updatedAt": item.updated_at,
        }


_business_agent_service: BusinessAgentService | None = None


def get_business_agent_service() -> BusinessAgentService:
    global _business_agent_service
    if _business_agent_service is None:
        _business_agent_service = BusinessAgentService()
    return _business_agent_service
