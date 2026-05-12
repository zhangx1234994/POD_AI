"""Normalize generated-image evaluation output for fission workflows."""

from __future__ import annotations

import json
import re
from typing import Any


REPAIR_ACTIONS = {"reference_repair", "current_image_repair", "regenerate", "needs_refission", "repair"}
REVIEW_VERDICTS = {"review", "needs_repair", "needs_refission", "repair"}


def normalize_generated_image_eval_result(value: Any) -> dict[str, Any]:
    """Return a stable public result from the AI team's eval workflow payload.

    The current upstream workflow returns a JSON object with `eval_json` and
    `route_json`, sometimes wrapped inside `output/text/data`. Business users
    should only consume the normalized fields below.
    """

    payload = _unwrap_eval_payload(value)
    eval_json = _as_dict(payload.get("eval_json")) if isinstance(payload, dict) else {}
    route_json = _as_dict(payload.get("route_json")) if isinstance(payload, dict) else {}
    hard_fail = _truthy(_deep_get(eval_json, ("sanity_eval", "hard_fail")))
    route_action = _lower_text(route_json.get("route_action") or route_json.get("action"))
    final_verdict = _lower_text(eval_json.get("final_verdict") or eval_json.get("verdict") or eval_json.get("decision"))

    if hard_fail:
        decision = "reject"
    elif route_action == "pass" and final_verdict in {"", "pass"}:
        decision = "pass"
    elif route_action in REPAIR_ACTIONS:
        decision = "needs_refission"
    elif final_verdict in REVIEW_VERDICTS:
        decision = "needs_refission"
    elif final_verdict == "pass":
        decision = "pass"
    else:
        decision = "reject"

    score = _score(eval_json, route_json, decision)
    scores = _dimension_scores(eval_json)
    problem_tags = _problem_tags(eval_json, route_json)
    reason = _reason(eval_json, route_json, decision)
    next_action = _next_action(route_json, decision)

    return {
        "decision": decision,
        "score": score,
        "scores": scores,
        "problem_tags": problem_tags,
        "reason": reason,
        "next_action": next_action,
        "eval_json": eval_json,
        "route_json": route_json,
    }


def _unwrap_eval_payload(value: Any) -> dict[str, Any]:
    parsed = _parse_jsonish(value)
    if isinstance(parsed, dict) and ("eval_json" in parsed or "route_json" in parsed):
        return parsed
    if isinstance(parsed, dict):
        for key in ("output", "text", "data", "content", "message", "result"):
            if key in parsed:
                nested = _unwrap_eval_payload(parsed[key])
                if nested:
                    return nested
    if isinstance(parsed, list):
        for item in parsed:
            nested = _unwrap_eval_payload(item)
            if nested:
                return nested
    return {}


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                return None
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    parsed = _parse_jsonish(value)
    return parsed if isinstance(parsed, dict) else {}


def _deep_get(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "是"}
    return False


def _lower_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score(eval_json: dict[str, Any], route_json: dict[str, Any], decision: str) -> int:
    for value in (
        eval_json.get("overall_score"),
        eval_json.get("total_score"),
        eval_json.get("score"),
        route_json.get("score"),
    ):
        number = _number(value)
        if number is not None:
            return max(0, min(100, int(round(number))))
    if decision == "pass":
        return 85
    if decision == "needs_refission":
        return 65
    return 0


def _dimension_scores(eval_json: dict[str, Any]) -> dict[str, int | None]:
    candidates = (
        eval_json.get("scores"),
        eval_json.get("dimension_scores"),
        eval_json.get("score_detail"),
        eval_json.get("score_details"),
    )
    source = next((item for item in candidates if isinstance(item, dict)), {})

    def pick(*keys: str) -> int | None:
        for key in keys:
            number = _number(source.get(key) if isinstance(source, dict) else None)
            if number is not None:
                return int(round(number))
        number = _number(_deep_get(eval_json, keys[:2]) if len(keys) >= 2 else None)
        return int(round(number)) if number is not None else None

    return {
        "shape": pick("shape", "shape_score", "structure", "structure_score"),
        "material": pick("material", "material_score", "style", "style_score"),
        "scale": pick("scale", "scale_score", "density", "density_score"),
        "logic": pick("logic", "logic_score", "reasoning", "reasoning_score"),
    }


def _problem_tags(eval_json: dict[str, Any], route_json: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for container in (route_json, eval_json):
        for key in ("problem_tags", "issue_tags", "risk_tags", "failed_dimensions"):
            value = container.get(key)
            if isinstance(value, list):
                tags.extend(str(item).strip() for item in value if str(item).strip())
            elif isinstance(value, str) and value.strip():
                tags.extend(item.strip() for item in re.split(r"[,，\n]", value) if item.strip())
    return list(dict.fromkeys(tags))


def _reason(eval_json: dict[str, Any], route_json: dict[str, Any], decision: str) -> str:
    for value in (
        route_json.get("reason_summary"),
        route_json.get("reason"),
        route_json.get("route_reason"),
        eval_json.get("reason"),
        eval_json.get("summary"),
        eval_json.get("comment"),
    ):
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
    if decision == "pass":
        return "生成图通过裂变质量评估。"
    if decision == "needs_refission":
        return "生成图存在可修复问题，建议重新裂变。"
    return "生成图未通过裂变质量评估。"


def _next_action(route_json: dict[str, Any], decision: str) -> dict[str, Any]:
    existing = route_json.get("next_action")
    if isinstance(existing, dict):
        return existing
    if decision == "pass":
        return {"type": "accept"}
    if decision == "needs_refission":
        repeat = _number(route_json.get("repeat") or route_json.get("refission_repeat")) or 2
        route_action = _lower_text(route_json.get("route_action"))
        return {"type": "refission_repeat", "repeat": int(repeat), "route_action": route_action or None}
    return {"type": "reject"}
