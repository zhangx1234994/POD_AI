#!/usr/bin/env python3
"""Small release smoke check for the backend business chain.

Run this on the backend/Coze host after restart. It intentionally calls
internal Coze toolbox endpoints, so running it from an untrusted external host
should fail with INTERNAL_ONLY.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any

import httpx


PUBLIC_EVAL_WORKFLOW_ROLES = {"production", "candidate"}
DEFAULT_MAX_PRODUCTION_PER_CATEGORY = 2


def _short(value: Any, limit: int = 500) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split())[:limit]


def _result(name: str, ok: bool, detail: str) -> dict[str, Any]:
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {name}: {detail}")
    return {"name": name, "ok": ok, "detail": detail}


def _get_json(client: httpx.Client, path: str) -> tuple[int, Any]:
    response = client.get(path)
    try:
        data = response.json()
    except Exception:
        data = {"text": response.text}
    return response.status_code, data


def _post_json(client: httpx.Client, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
    response = client.post(path, json=payload)
    try:
        data = response.json()
    except Exception:
        data = {"text": response.text}
    return response.status_code, data


def _validate_eval_workflow_catalog(
    data: Any,
    *,
    max_production_per_category: int = DEFAULT_MAX_PRODUCTION_PER_CATEGORY,
) -> tuple[bool, str]:
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return False, "workflow list is not a list"
    if not items:
        return False, "workflow list is empty"

    role_counts: Counter[str] = Counter()
    production_by_category: dict[str, list[str]] = {}
    workflow_id_counts: Counter[str] = Counter()
    leaked: list[str] = []
    missing_governance: list[str] = []
    hidden_public: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        workflow_id = str(item.get("workflow_id") or item.get("workflowId") or item.get("id") or "-")
        workflow_id_counts[workflow_id] += 1
        presentation = item.get("presentation") if isinstance(item.get("presentation"), dict) else {}
        category = str(
            presentation.get("categoryLabel")
            or presentation.get("category_label")
            or item.get("category")
            or "未归类"
        ).strip() or "未归类"
        governance = item.get("governance") if isinstance(item.get("governance"), dict) else {}
        role = str(governance.get("role") or "").strip().lower()
        if not role:
            missing_governance.append(workflow_id)
            continue
        role_counts[role] += 1
        if role == "production":
            production_by_category.setdefault(category, []).append(workflow_id)
        if role not in PUBLIC_EVAL_WORKFLOW_ROLES:
            leaked.append(f"{workflow_id}:{role}")
        if presentation.get("visible") is False:
            hidden_public.append(workflow_id)

    if missing_governance:
        return False, f"missing governance={missing_governance[:5]}"
    duplicated_ids = [workflow_id for workflow_id, count in workflow_id_counts.items() if workflow_id and count > 1]
    if duplicated_ids:
        return False, f"duplicated workflow ids in public catalog={duplicated_ids[:5]}"
    if leaked:
        return False, f"non-public roles leaked={leaked[:5]} roles={dict(role_counts)}"
    if hidden_public:
        return False, f"public list contains visible=false workflows={hidden_public[:5]}"
    if role_counts.get("production", 0) <= 0:
        return False, f"no production workflow in public catalog roles={dict(role_counts)}"
    over_limit = {
        category: workflow_ids
        for category, workflow_ids in production_by_category.items()
        if len(workflow_ids) > max(1, max_production_per_category)
    }
    if over_limit:
        preview = {category: workflow_ids[:5] for category, workflow_ids in over_limit.items()}
        return (
            False,
            "too many production workflows per category="
            f"{preview} max={max_production_per_category} roles={dict(role_counts)}",
        )
    production_counts = {category: len(workflow_ids) for category, workflow_ids in production_by_category.items()}
    return True, f"count={len(items)} roles={dict(role_counts)} productionByCategory={production_counts}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PODI backend release smoke checks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8099")
    parser.add_argument("--expect-server-url", default="", help="Optional OpenAPI servers[0].url expectation.")
    parser.add_argument(
        "--max-production-per-category",
        type=int,
        default=DEFAULT_MAX_PRODUCTION_PER_CATEGORY,
        help="Maximum public production entries allowed in one business category.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary at the end.")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    timeout = httpx.Timeout(20.0, connect=5.0)
    checks: list[dict[str, Any]] = []

    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        try:
            status, data = _get_json(client, "/health")
            checks.append(_result("health", status == 200 and data.get("status") == "ok", f"status={status} body={data}"))
        except Exception as exc:
            checks.append(_result("health", False, repr(exc)))

        try:
            status, data = _get_json(client, "/api/coze/podi/openapi.json")
            openapi = data if isinstance(data, dict) else {}
            server_url = ""
            servers = openapi.get("servers") if isinstance(openapi.get("servers"), list) else []
            if servers and isinstance(servers[0], dict):
                server_url = str(servers[0].get("url") or "")
            expected = args.expect_server_url.strip()
            ok = status == 200 and bool(server_url) and (not expected or server_url == expected)
            detail = f"status={status} server={server_url or '-'}"
            if expected:
                detail += f" expected={expected}"
            checks.append(_result("coze_openapi", ok, detail))
        except Exception as exc:
            checks.append(_result("coze_openapi", False, repr(exc)))

        try:
            status, data = _post_json(client, "/api/coze/podi/tasks/get", {"taskId": "__release_smoke_not_found__"})
            detail = data.get("detail") if isinstance(data, dict) else data
            checks.append(_result("internal_tasks_get", status == 404 and detail == "TASK_NOT_FOUND", f"status={status} detail={detail}"))
        except Exception as exc:
            checks.append(_result("internal_tasks_get", False, repr(exc)))

        try:
            status, data = _post_json(client, "/api/coze/podi/comfyui/queue-summary", {})
            servers = data.get("servers") if isinstance(data, dict) else None
            ok = status == 200 and isinstance(servers, list) and len(servers) > 0
            detail = f"status={status} servers={len(servers) if isinstance(servers, list) else 0}"
            if isinstance(data, dict) and data.get("error"):
                detail += f" error={_short(data.get('error'))}"
            checks.append(_result("comfyui_queue_summary", ok, detail))
        except Exception as exc:
            checks.append(_result("comfyui_queue_summary", False, repr(exc)))

        try:
            status, data = _get_json(client, "/api/evals/workflow-versions")
            ok, catalog_detail = _validate_eval_workflow_catalog(
                data,
                max_production_per_category=args.max_production_per_category,
            )
            checks.append(_result("eval_workflow_catalog", status == 200 and ok, f"status={status} {catalog_detail}"))
        except Exception as exc:
            checks.append(_result("eval_workflow_catalog", False, repr(exc)))

    ok = all(item.get("ok") for item in checks)
    summary = {"baseUrl": base_url, "ok": ok, "checks": checks}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
