"""Helpers for business-facing eval workflow presentation metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.eval_workflow_deprecation import resolve_eval_workflow_deprecation

_CATEGORY_SORT_BUCKETS = {
    "花纹提取类": 1000,
    "图延伸类": 2000,
    "四方/两方连续图类": 3000,
    "图裂变": 4000,
    "图像理解": 4500,
    "通用类": 5000,
}

_CATEGORY_OPERATION_LABELS = {
    "花纹提取类": "花纹提取",
    "图延伸类": "图像延伸",
    "四方/两方连续图类": "连续图生成",
    "图裂变": "图像裂变",
    "图像理解": "图像理解",
    "通用类": "通用处理",
}

_IMAGE_TAGGING_WORKFLOW_IDS = {
    "7597767702970630144": "小参数标签版",
    "7598080013539213312": "大参数标签版",
    "7600254097513512960": "Lits 标签版",
    "7600254796297142272": "色号标签版",
}

_IMAGE_URL_AUXILIARY_WORKFLOW_IDS = {
    "7597760543788630016": "8K 高清放大",
    "7598589746561941504": "DPI 增分",
}


def _normalize_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _normalize_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _field_names(schema: dict[str, Any] | None) -> list[str]:
    fields = schema.get("fields") if isinstance(schema, dict) else None
    if not isinstance(fields, list):
        return []
    result: list[str] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip()
        if name:
            result.append(name)
    return result


def _field_by_name(schema: dict[str, Any] | None, name: str) -> dict[str, Any]:
    fields = schema.get("fields") if isinstance(schema, dict) else None
    if not isinstance(fields, list):
        return {}
    for field in fields:
        if isinstance(field, dict) and str(field.get("name") or "").strip() == name:
            return field
    return {}


def _guess_entry_mode(parameters_schema: dict[str, Any] | None) -> str:
    names = set(_field_names(parameters_schema))
    if {"image_url_2", "image_url_3"} & names:
        return "multi_image"
    if "url" in names:
        return "single_image"
    if not names:
        return "parameter_only"
    return "parameter_form"


def _guess_result_mode(output_schema: dict[str, Any] | None) -> str:
    output_field = _field_by_name(output_schema, "output")
    output_desc = str(output_field.get("description") or "").lower()
    names = set(_field_names(output_schema))
    if {"items", "lora_names"} & names:
        return "structured_json"
    if "json" in output_desc or "结构化" in output_desc or "标签" in output_desc:
        return "structured_json"
    if "task id" in output_desc or "回调" in output_desc or "callback" in output_desc:
        return "callback_image"
    if "url" in output_desc and ("图片" in output_desc or "image" in output_desc):
        return "image_url"
    if "output" in names and "ip" in names:
        return "image"
    if "output" in names:
        return "text"
    return "unknown"


def _guess_operation_label(*, category: str, workflow_id: str, name: str) -> str:
    lowered = f"{workflow_id} {name}".lower()
    if any(token in lowered for token in ("biaoqian", "打标签", "tag", "label")):
        return "图片打标签"
    if any(token in lowered for token in ("高清放大", "upscale", "dpi", "增分")):
        return "图像原子处理"
    if any(token in lowered for token in ("outpaint", "kuotu", "kuozhan", "延伸")):
        return "图像延伸"
    if any(token in lowered for token in ("koutu", "kouxiang", "抠图", "抠像")):
        return "抠图"
    if any(token in lowered for token in ("liebian", "裂变", "fission")):
        return "图像裂变"
    if any(token in lowered for token in ("tiqu", "提取", "extract")):
        return "花纹提取"
    return _CATEGORY_OPERATION_LABELS.get(category, "工作流评测")


def _guess_variant_label(*, workflow_id: str, name: str) -> str:
    lowered = f"{workflow_id} {name}".lower()
    if workflow_id == "7631838631375667200" or "softstyle" in lowered or "高质量" in name:
        return "高质量 SoftStyle"
    if workflow_id == "7631174682116358144" or "flux2_klein" in lowered:
        return "当前扩图主线"
    if "文字增强" in name or "text_enhance" in lowered:
        return "文字增强版"
    if "四方连续裂变" in name or "liebian_sifang" in lowered:
        return "四方连续裂变"
    if "有提示词" in name:
        return "有提示词"
    if "无提示词" in name:
        return "无提示词"
    if "商业" in name or "shangye" in lowered:
        return "商业模型"
    if "comfyui" in lowered:
        if "20260328" in lowered:
            return "ComfyUI 20260328"
        if "20260124" in lowered:
            return "ComfyUI 旧版"
        return "ComfyUI"
    if "背景抠图" in name or "beijing_koutu" in lowered:
        return "背景抠图"
    if "头部抠像" in name or "toubu_kouxiang" in lowered:
        return "头部抠像"
    if "biaoqian_tiqu_3_1" in lowered:
        return "色号标签版"
    if "biaoqian_tiqu_3" in lowered:
        return "Lits 标签版"
    if "biaoqian_tiqu_1" in lowered:
        return "大参数标签版"
    if "biaoqian_tiqu" in lowered or "图片打标签" in name:
        return "小参数标签版"
    if "8k" in lowered or "高清放大" in name:
        return "8K 高清放大"
    if "dpi" in lowered or "增分" in name:
        return "DPI 增分"
    parts = [
        item.strip()
        for item in name.replace("｜", "·").replace("|", "·").replace("/", "·").split("·")
        if item.strip()
    ]
    return parts[-1] if len(parts) > 1 else ""


def _normalize_badges(value: Any) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, list) else [value]
    badges: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        badges.append(text)
        seen.add(text)
    return badges[:4]


def _forced_presentation_values(*, workflow_id: str, name: str) -> dict[str, str]:
    lowered = f"{workflow_id} {name}".lower()
    if workflow_id in _IMAGE_TAGGING_WORKFLOW_IDS or "biaoqian_tiqu" in lowered:
        return {
            "operation_label": "图片打标签",
            "variant_label": _IMAGE_TAGGING_WORKFLOW_IDS.get(workflow_id) or _guess_variant_label(
                workflow_id=workflow_id,
                name=name,
            ),
            "result_mode": "structured_json",
        }
    if workflow_id in _IMAGE_URL_AUXILIARY_WORKFLOW_IDS or "高清放大" in name or "dpi" in lowered or "增分" in name:
        return {
            "operation_label": "图像原子处理",
            "variant_label": _IMAGE_URL_AUXILIARY_WORKFLOW_IDS.get(workflow_id) or _guess_variant_label(
                workflow_id=workflow_id,
                name=name,
            ),
            "result_mode": "image_url",
        }
    return {}


def _guess_usage_hint(
    *,
    category: str,
    result_mode: str,
    entry_mode: str,
    supports_batch: bool,
) -> str:
    if category == "图裂变":
        return "适合先验证单张结果，再决定是否进入批量裂变"
    if category == "图延伸类":
        return "适合验证扩边尺寸、留白方向和结果边界是否符合预期"
    if category == "花纹提取类":
        return "适合先确认提取干净度和提示词反馈，再决定是否进入批量处理"
    if category == "四方/两方连续图类":
        return "适合验证连续纹样是否闭环，再决定是否继续放量"
    if result_mode == "structured_json":
        return "适合先核对结构化输出字段，再决定是否进入业务流程"
    if supports_batch:
        return "适合先做单次验证，确认稳定后再进入批量测评"
    if entry_mode == "single_image":
        return "适合直接在测评端发起单次图片验证"
    return "适合先做单次验证，再决定是否发布给业务使用"


def _extract_recommended_repeat_count(parameters_schema: dict[str, Any] | None) -> int:
    field = _field_by_name(parameters_schema, "count")
    for key in ("defaultValue", "default", "value"):
        if key in field:
            try:
                value = int(str(field.get(key)).strip())
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
    return 1


def resolve_eval_workflow_presentation(
    *,
    status: str | None,
    category: str | None,
    workflow_id: str | None,
    name: str | None,
    parameters_schema: dict[str, Any] | None,
    output_schema: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    base = metadata if isinstance(metadata, dict) else {}
    presentation = base.get("presentation") if isinstance(base.get("presentation"), dict) else {}
    category_text = str(category or "").strip() or "通用类"
    workflow_id_text = str(workflow_id or "").strip()
    name_text = str(name or "").strip()
    forced_values = _forced_presentation_values(workflow_id=workflow_id_text, name=name_text)
    entry_mode = str(
        presentation.get("entry_mode") or _guess_entry_mode(parameters_schema)
    ).strip() or "parameter_form"
    result_mode = str(
        forced_values.get("result_mode") or presentation.get("result_mode") or _guess_result_mode(output_schema)
    ).strip() or "unknown"
    supports_batch = _normalize_bool(
        presentation.get("supports_batch"),
        default=category_text in {"图裂变", "花纹提取类", "四方/两方连续图类"},
    )
    recommended_repeat_count = _normalize_int(
        presentation.get("recommended_repeat_count"),
        default=_extract_recommended_repeat_count(parameters_schema),
    )
    badges = _normalize_badges(presentation.get("badges") or base.get("badges") or base.get("badge"))
    if _normalize_bool(base.get("is_new_version") or base.get("isNewVersion"), default=False) and "新版" not in badges:
        badges.insert(0, "新版")
    default_sort = _CATEGORY_SORT_BUCKETS.get(category_text, 9000)
    return {
        "visible": _normalize_bool(
            presentation.get("visible"),
            default=(str(status or "").strip().lower() == "active"),
        ),
        "sort_order": _normalize_int(presentation.get("sort_order"), default=default_sort),
        "category_label": str(presentation.get("category_label") or category_text).strip(),
        "usage_hint": str(
            presentation.get("usage_hint")
            or _guess_usage_hint(
                category=category_text,
                result_mode=result_mode,
                entry_mode=entry_mode,
                supports_batch=supports_batch,
            )
        ).strip(),
        "operation_label": str(
            forced_values.get("operation_label")
            or presentation.get("operation_label")
            or _guess_operation_label(
                category=category_text,
                workflow_id=workflow_id_text,
                name=name_text,
            )
        ).strip(),
        "variant_label": str(
            forced_values.get("variant_label")
            or presentation.get("variant_label")
            or _guess_variant_label(workflow_id=workflow_id_text, name=name_text)
        ).strip(),
        "entry_mode": entry_mode,
        "result_mode": result_mode,
        "supports_batch": supports_batch,
        "recommended_repeat_count": max(1, recommended_repeat_count),
        "badges": badges,
    }


def enrich_metadata_with_eval_workflow_presentation(
    metadata: dict[str, Any] | None,
    *,
    status: str | None,
    category: str | None,
    workflow_id: str | None,
    name: str | None,
    parameters_schema: dict[str, Any] | None,
    output_schema: dict[str, Any] | None,
    presentation_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = deepcopy(metadata) if isinstance(metadata, dict) else {}
    if presentation_override is not None:
        payload = {
            "visible": presentation_override.get("visible"),
            "sort_order": presentation_override.get("sort_order"),
            "category_label": str(presentation_override.get("category_label") or "").strip() or None,
            "usage_hint": str(presentation_override.get("usage_hint") or "").strip() or None,
            "operation_label": str(presentation_override.get("operation_label") or "").strip() or None,
            "variant_label": str(presentation_override.get("variant_label") or "").strip() or None,
            "entry_mode": str(presentation_override.get("entry_mode") or "").strip() or None,
            "result_mode": str(presentation_override.get("result_mode") or "").strip() or None,
            "supports_batch": presentation_override.get("supports_batch"),
            "recommended_repeat_count": presentation_override.get("recommended_repeat_count"),
            "badges": presentation_override.get("badges"),
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        if payload:
            base["presentation"] = payload
        else:
            base.pop("presentation", None)
    base["presentation"] = resolve_eval_workflow_presentation(
        status=status,
        category=category,
        workflow_id=workflow_id,
        name=name,
        parameters_schema=parameters_schema,
        output_schema=output_schema,
        metadata=base,
    )
    return base


def build_eval_workflow_presentation_sort_key(
    *,
    status: str | None,
    category: str | None,
    workflow_id: str | None,
    name: str | None,
    parameters_schema: dict[str, Any] | None,
    output_schema: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
) -> tuple[int, str, str, str]:
    presentation = resolve_eval_workflow_presentation(
        status=status,
        category=category,
        workflow_id=workflow_id,
        name=name,
        parameters_schema=parameters_schema,
        output_schema=output_schema,
        metadata=metadata,
    )
    return (
        int(presentation.get("sort_order") or 999999),
        str(category or ""),
        str(workflow_id or ""),
        str(name or ""),
    )


def is_eval_workflow_visible(
    *,
    status: str | None,
    category: str | None,
    workflow_id: str | None,
    name: str | None,
    parameters_schema: dict[str, Any] | None,
    output_schema: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
) -> bool:
    deprecation = resolve_eval_workflow_deprecation(status=status, metadata=metadata)
    if deprecation and deprecation.get("is_deprecated"):
        retirement_mode = str(deprecation.get("retirement_mode") or "hide_public").strip().lower()
        if retirement_mode in {"hide_public", "admin_only", "delete_candidate"}:
            return False
    presentation = resolve_eval_workflow_presentation(
        status=status,
        category=category,
        workflow_id=workflow_id,
        name=name,
        parameters_schema=parameters_schema,
        output_schema=output_schema,
        metadata=metadata,
    )
    return bool(presentation.get("visible"))
