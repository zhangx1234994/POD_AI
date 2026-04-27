"""Business-facing catalog role for eval workflows."""

from __future__ import annotations

from typing import Any


_PRIMARY_WORKFLOW_IDS = {
    # 图裂变：AI 团队最新高质量裂变主线。
    "7631838631375667200",
    # 扩图：当前 FLUX2-Klein 主线。
    "7631174682116358144",
    # 花纹提取：当前多模型提取主线。
    "7601080398864449536",
    # 四方连续裂变主线。
    "7629026792103215104",
    # 高频通用处理。
    "7629023903431524352",
    "7629023041988591616",
}

_AUXILIARY_NAME_TOKENS = {
    "查询",
    "监控",
    "回调",
    "打标签",
    "dpi",
    "高清放大",
    "catalog",
    "queue",
    "callback",
}

_ROLE_LABELS = {
    "production": "生产主入口",
    "candidate": "灰度/对照版本",
    "legacy": "历史保留",
    "auxiliary": "辅助工具",
    "disabled": "已停用",
}

_ROLE_RANKS = {
    "production": 10,
    "candidate": 30,
    "auxiliary": 70,
    "legacy": 90,
    "disabled": 100,
}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_role(value: Any) -> str:
    text = _clean_text(value).lower()
    aliases = {
        "primary": "production",
        "prod": "production",
        "main": "production",
        "canary": "candidate",
        "gray": "candidate",
        "grey": "candidate",
        "compare": "candidate",
        "comparison": "candidate",
        "history": "legacy",
        "deprecated": "legacy",
        "internal": "auxiliary",
        "helper": "auxiliary",
        "tool": "auxiliary",
        "inactive": "disabled",
    }
    text = aliases.get(text, text)
    return text if text in _ROLE_LABELS else ""


def _is_auxiliary_name(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in _AUXILIARY_NAME_TOKENS)


def resolve_eval_workflow_governance(
    *,
    status: str | None,
    category: str | None,
    workflow_id: str | None,
    name: str | None,
    metadata: dict[str, Any] | None,
    deprecation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a stable catalog role for eval UI and admin review.

    The role is intentionally business-facing: it tells operators whether a
    card is the current main entry, a gray/comparison version, a historical
    entry, or an internal helper.
    """

    base = metadata if isinstance(metadata, dict) else {}
    override = base.get("governance") if isinstance(base.get("governance"), dict) else {}
    role = _normalize_role(override.get("role"))
    workflow_id_text = _clean_text(workflow_id)
    status_text = _clean_text(status).lower()
    category_text = _clean_text(category) or "通用类"
    name_text = _clean_text(name)

    if not role:
        if status_text not in {"active", "draft"}:
            role = "disabled"
        elif deprecation:
            mode = _clean_text(deprecation.get("retirement_mode")).lower()
            role = "auxiliary" if mode == "admin_only" else "legacy"
        elif workflow_id_text in _PRIMARY_WORKFLOW_IDS:
            role = "production"
        elif _is_auxiliary_name(name_text):
            role = "auxiliary"
        else:
            # 未明确声明为主入口的 active 版本默认作为灰度/对照，
            # 避免公开目录里出现过多“生产主入口”。
            role = "candidate"

    label = (
        _clean_text(override.get("label"))
        or _clean_text(override.get("role_label"))
        or _clean_text(override.get("roleLabel"))
        or _ROLE_LABELS.get(role, "未归类")
    )
    reason = (
        _clean_text(override.get("reason"))
        or _clean_text(override.get("role_reason"))
        or _clean_text(override.get("roleReason"))
    )
    if not reason:
        if role == "production":
            reason = "当前推荐给业务优先使用。"
        elif role == "candidate":
            reason = "用于灰度验证或与主线结果对照。"
        elif role == "legacy":
            reason = "保留历史记录和回溯，不建议作为新评测入口。"
        elif role == "auxiliary":
            reason = "用于内部排障或辅助查询，不是业务主入口。"
        else:
            reason = "当前不建议使用。"

    rank = _ROLE_RANKS.get(role, 999)
    try:
        rank = int(override.get("rank", override.get("sortRank", rank)))
    except (TypeError, ValueError):
        pass

    return {
        "role": role,
        "role_label": label,
        "role_reason": reason,
        "rank": rank,
        "is_primary": role == "production",
    }
