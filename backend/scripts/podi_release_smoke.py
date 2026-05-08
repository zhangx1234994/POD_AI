#!/usr/bin/env python3
"""Small release smoke check for the backend business chain.

Run this on the backend/Coze host after restart. It intentionally calls
internal Coze toolbox endpoints, so running it from an untrusted external host
should fail with INTERNAL_ONLY.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import httpx


PUBLIC_EVAL_WORKFLOW_ROLES = {"production", "candidate"}
INTERNAL_EVAL_WORKFLOW_ROLES = PUBLIC_EVAL_WORKFLOW_ROLES | {"auxiliary"}
REQUIRED_INTERNAL_EVAL_AUXILIARY_WORKFLOW_IDS = {
    "7597760543788630016",  # 8K 高清放大
    "7598589746561941504",  # DPI 增分
    "7597767702970630144",  # 图片打标签
    "7598080013539213312",  # 图片打标签
    "7600254097513512960",  # 图片打标签
    "7600254796297142272",  # 图片打标签
    "7612002440056930304",  # LoRA 查询
}
DEFAULT_MAX_PRODUCTION_PER_CATEGORY = 2
CORE_BUSINESS_PATROL_IMAGE_URL = (
    "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/"
    "98904c502d9d4dd78432ec2bd1f79def/20260424/228be55f-1777009905.jpg"
)


class BusinessRouteSpec:
    def __init__(self, *, key: str, label: str, path: str, payload: dict[str, Any]) -> None:
        self.key = key
        self.label = label
        self.path = path
        self.payload = payload


BUSINESS_ROUTE_SPECS: tuple[BusinessRouteSpec, ...] = (
    BusinessRouteSpec(
        key="pattern_extract",
        label="花纹提取",
        path="/api/business/pattern-extract/route-preview",
        payload={
            "imageUrl": CORE_BUSINESS_PATROL_IMAGE_URL,
            "prompt": "发版自检：提取主体花纹，保持边缘清晰。",
            "negative_prompt": "不要背景、不要文字水印、不要阴影。",
            "width": 1024,
            "height": 1024,
            "batch": 1,
            "source": "release-smoke",
            "clientId": "release-smoke",
        },
    ),
    BusinessRouteSpec(
        key="fission",
        label="图裂变",
        path="/api/business/fission/route-preview",
        payload={
            "imageUrl": CORE_BUSINESS_PATROL_IMAGE_URL,
            "prompt": "发版自检：保持主体风格，生成一张稳定花纹变体。",
            "bili": 35,
            "width": 1024,
            "height": 1024,
            "batch_size": 1,
            "image_desc": "发版自检样例图。",
            "source": "release-smoke",
            "clientId": "release-smoke",
        },
    ),
    BusinessRouteSpec(
        key="outpaint",
        label="扩图",
        path="/api/business/outpaint/route-preview",
        payload={
            "imageUrl": CORE_BUSINESS_PATROL_IMAGE_URL,
            "prompt": "发版自检：向四周扩展，保持纹理和色彩连续。",
            "expand_left": 64,
            "expand_right": 64,
            "expand_top": 64,
            "expand_bottom": 64,
            "width": 1024,
            "height": 1024,
            "source": "release-smoke",
            "clientId": "release-smoke",
        },
    ),
)


def _short(value: Any, limit: int = 500) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split())[:limit]


def _result(name: str, ok: bool, detail: str) -> dict[str, Any]:
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {name}: {detail}")
    return {"name": name, "ok": ok, "detail": detail}


def _write_report(summary: dict[str, Any], report_path: str) -> str:
    path = Path(report_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    return str(path)


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


def _validate_comfyui_queue_summary(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "queue summary is not an object"
    servers = data.get("servers")
    if not isinstance(servers, list) or not servers:
        return False, "no active ComfyUI executor returned"
    unsupported = int(data.get("unsupportedServers") or 0)
    blocked = int(data.get("backendBlockedServers") or 0)
    feed_gap = int(data.get("feedGapServers") or 0)
    total_capacity = data.get("totalCapacity")
    idle_slots = data.get("totalIdleSlots")
    utilization = data.get("utilization")
    diagnostics = data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
    if unsupported > 0:
        return False, f"unsupportedServers={unsupported} diagnostics={_short(diagnostics)}"
    if blocked > 0:
        return False, f"backendBlockedServers={blocked} diagnostics={_short(diagnostics)}"
    return (
        True,
        "servers="
        f"{len(servers)} capacity={total_capacity} idle={idle_slots} utilization={utilization} "
        f"feedGapServers={feed_gap} diagnostics={_short(diagnostics) if diagnostics else '-'}",
    )


def _validate_comfyui_workflow_compatibility(
    data: Any,
    *,
    allow_warnings: bool = False,
) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "workflow compatibility is not an object"
    total = int(data.get("totalWorkflows") or 0)
    ok_count = int(data.get("okCount") or 0)
    warning_count = int(data.get("warningCount") or 0)
    failed_count = int(data.get("failedCount") or 0)
    workflows = data.get("workflows")
    servers = data.get("servers")
    if total <= 0 or not isinstance(workflows, list) or not workflows:
        return False, "no active ComfyUI workflow compatibility result"
    if not isinstance(servers, list) or not servers:
        return False, "no active ComfyUI executor compatibility result"

    def summarize_issue(item: dict[str, Any]) -> str:
        ability_id = str(item.get("abilityId") or item.get("workflowKey") or "-")
        server_summaries: list[str] = []
        servers = item.get("servers") if isinstance(item.get("servers"), list) else []
        for server in servers:
            if not isinstance(server, dict) or server.get("compatible") is True:
                continue
            executor_id = str(server.get("executorId") or "-")
            parts: list[str] = []
            missing_nodes = server.get("missingNodes") if isinstance(server.get("missingNodes"), list) else []
            missing_models = server.get("missingModels") if isinstance(server.get("missingModels"), list) else []
            if missing_nodes:
                node_sample = [
                    str(node.get("classType") or node.get("nodeId") or "-")
                    for node in missing_nodes[:3]
                    if isinstance(node, dict)
                ]
                parts.append(f"缺节点={node_sample}")
            if missing_models:
                model_sample = [
                    str(model.get("value") or model.get("inputName") or "-")
                    for model in missing_models[:3]
                    if isinstance(model, dict)
                ]
                parts.append(f"缺模型={model_sample}")
            message = str(server.get("message") or "").strip()
            if message and not parts:
                parts.append(f"原因={message}")
            server_summaries.append(f"{executor_id}({'; '.join(parts) if parts else '不兼容'})")
        diagnostics = item.get("diagnostics") if isinstance(item.get("diagnostics"), list) else []
        diagnostic_codes = [
            str(diag.get("code") or diag.get("message") or "-")
            for diag in diagnostics[:3]
            if isinstance(diag, dict)
        ]
        if diagnostic_codes:
            server_summaries.append(f"诊断={diagnostic_codes}")
        return f"{ability_id} {' | '.join(server_summaries) if server_summaries else '无明细'}"

    failed_items: list[str] = []
    warning_items: list[str] = []
    for item in workflows:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status == "failed":
            failed_items.append(summarize_issue(item))
        elif status == "warning":
            warning_items.append(summarize_issue(item))

    if failed_count > 0 or failed_items:
        return False, f"failed={failed_count} sample={failed_items[:5]}"
    if warning_count > 0 and not allow_warnings:
        return False, f"warnings={warning_count} sample={warning_items[:5]}"
    return (
        True,
        f"total={total} ok={ok_count} warnings={warning_count} failed={failed_count} "
        f"servers={len(servers)}",
    )


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


def _validate_internal_eval_workflow_catalog(data: Any) -> tuple[bool, str]:
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return False, "workflow list is not a list"
    if not items:
        return False, "workflow list is empty"

    role_counts: Counter[str] = Counter()
    workflow_ids: set[str] = set()
    leaked: list[str] = []
    hidden_public: list[str] = []
    general_count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        workflow_id = str(item.get("workflow_id") or item.get("workflowId") or item.get("id") or "").strip()
        if workflow_id:
            workflow_ids.add(workflow_id)
        presentation = item.get("presentation") if isinstance(item.get("presentation"), dict) else {}
        category = str(
            presentation.get("categoryLabel")
            or presentation.get("category_label")
            or item.get("category")
            or "未归类"
        ).strip()
        if category == "通用类":
            general_count += 1
        governance = item.get("governance") if isinstance(item.get("governance"), dict) else {}
        role = str(governance.get("role") or "").strip().lower()
        if role:
            role_counts[role] += 1
        if role not in INTERNAL_EVAL_WORKFLOW_ROLES:
            leaked.append(f"{workflow_id or '-'}:{role or 'missing'}")
        raw_visible = presentation.get("visible")
        if raw_visible is False and role in PUBLIC_EVAL_WORKFLOW_ROLES:
            hidden_public.append(workflow_id or "-")

    missing_required = sorted(REQUIRED_INTERNAL_EVAL_AUXILIARY_WORKFLOW_IDS - workflow_ids)
    if leaked:
        return False, f"unexpected roles in internal eval catalog={leaked[:5]} roles={dict(role_counts)}"
    if hidden_public:
        return False, f"internal eval catalog contains hidden public workflows={hidden_public[:5]}"
    if missing_required:
        return False, f"missing required auxiliary workflows={missing_required[:5]} roles={dict(role_counts)}"
    if role_counts.get("auxiliary", 0) <= 0:
        return False, f"no auxiliary workflows returned roles={dict(role_counts)}"
    return True, f"count={len(items)} general={general_count} roles={dict(role_counts)}"


def _validate_business_usage_summary(
    data: Any,
    *,
    max_unresolved_issues: int = 0,
) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "business usage summary is not an object"
    total = int(data.get("total") or 0)
    failed = int(data.get("failed") or 0)
    running = int(data.get("running") or 0)
    queued = int(data.get("queued") or 0)
    by_issue = data.get("byIssue")
    unresolved = data.get("unresolvedIssues")
    recent_unresolved = data.get("recentUnresolvedIssues")
    if not isinstance(by_issue, list):
        return False, "byIssue is missing or not a list"
    if not isinstance(unresolved, list):
        return False, "unresolvedIssues is missing or not a list"
    if not isinstance(recent_unresolved, list):
        return False, "recentUnresolvedIssues is missing or not a list"

    unresolved_total = 0
    unresolved_detail: list[str] = []
    for bucket in unresolved:
        if not isinstance(bucket, dict):
            continue
        count = int(bucket.get("total") or 0)
        unresolved_total += count
        if count > 0:
            label = str(bucket.get("label") or bucket.get("key") or "unknown")
            retested = int(bucket.get("retested") or 0)
            unresolved_detail.append(f"{label}:{count},retested={retested}")

    schema_gaps: list[str] = []
    for item in recent_unresolved[:10]:
        if not isinstance(item, dict):
            schema_gaps.append("recent item is not an object")
            continue
        missing = [key for key in ("id", "businessKey", "issueCategory", "issueLabel", "createdAt") if not item.get(key)]
        if missing:
            schema_gaps.append(f"{item.get('id') or '-'} missing={missing}")
    if schema_gaps:
        return False, f"recentUnresolvedIssues schema gaps={schema_gaps[:3]}"

    if unresolved_total > max(0, max_unresolved_issues):
        return (
            False,
            "unresolved="
            f"{unresolved_total} max={max_unresolved_issues} detail={unresolved_detail[:5]} "
            f"total={total} failed={failed} running={running} queued={queued}",
        )
    return (
        True,
        "total="
        f"{total} failed={failed} running={running} queued={queued} "
        f"unresolved={unresolved_total} detail={unresolved_detail[:5] if unresolved_detail else '-'}",
    )


def _validate_business_capability_governance(
    data: Any,
    *,
    max_warnings: int = 0,
) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "business capability response is not an object"
    items = data.get("items")
    if not isinstance(items, list):
        return False, "items is missing or not a list"

    core_keys = {spec.key for spec in BUSINESS_ROUTE_SPECS}
    default_by_key: dict[str, dict[str, Any]] = {}
    schema_gaps: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            schema_gaps.append("capability item is not an object")
            continue
        missing = [
            key
            for key in (
                "businessKey",
                "version",
                "displayName",
                "status",
                "isDefault",
                "governanceStatus",
                "governanceIssues",
            )
            if key not in item
        ]
        if missing:
            schema_gaps.append(f"{item.get('id') or item.get('businessKey') or '-'} missing={missing}")
        business_key = str(item.get("businessKey") or "").strip()
        if item.get("isDefault") is True and business_key in core_keys:
            default_by_key[business_key] = item
    if schema_gaps:
        return False, f"schema gaps={schema_gaps[:3]}"

    missing_defaults = sorted(core_keys - set(default_by_key))
    if missing_defaults:
        return False, f"missing core business defaults={missing_defaults}"

    blockers: list[str] = []
    warnings: list[str] = []
    for business_key, item in sorted(default_by_key.items()):
        status = str(item.get("status") or "").strip().lower()
        governance_status = str(item.get("governanceStatus") or "").strip().lower()
        issues = item.get("governanceIssues") if isinstance(item.get("governanceIssues"), list) else []
        primary_ability_id = str(item.get("primaryAbilityId") or "").strip()
        latest_acceptance = item.get("latestAcceptance") if isinstance(item.get("latestAcceptance"), dict) else {}
        release_gate = item.get("releaseGate") if isinstance(item.get("releaseGate"), dict) else {}
        label = f"{business_key}:{item.get('version') or '-'}"
        if status != "active":
            blockers.append(f"{label}:status={status or '-'}")
        if not primary_ability_id:
            blockers.append(f"{label}:missing-primary-ability")
        if str(latest_acceptance.get("status") or "").strip().lower() != "passed":
            blockers.append(f"{label}:acceptance-required")
        if str(release_gate.get("status") or "").strip().lower() == "blocked":
            blockers.append(f"{label}:release-gate={release_gate.get('blockers') or []}")
        if governance_status == "blocker":
            blockers.append(f"{label}:issues={issues[:3]}")
        elif governance_status == "warning":
            warnings.append(f"{label}:issues={issues[:3]}")
        elif governance_status not in {"ready", ""}:
            warnings.append(f"{label}:governance={governance_status or 'unknown'}")
    if blockers:
        return False, f"business governance blockers={blockers[:5]}"
    if len(warnings) > max(0, int(max_warnings or 0)):
        return False, f"business governance warnings={len(warnings)} max={max_warnings} sample={warnings[:5]}"
    return (
        True,
        f"defaults={len(default_by_key)} warnings={len(warnings)} "
        f"items={len(items)} core={sorted(core_keys)}",
    )


def _validate_commercial_report(
    data: Any,
    *,
    max_billing_issues: int = 0,
    max_unpriced_runs: int = 0,
) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "commercial report is not an object"
    required_numbers = [
        "runCount",
        "billableRunCount",
        "chargedRunCount",
        "unpricedRunCount",
        "billingIssueCount",
        "paidPackageOrderCount",
        "pendingPackageOrderCount",
    ]
    missing_numbers = [key for key in required_numbers if key not in data]
    if missing_numbers:
        return False, f"missing numeric fields={missing_numbers}"
    business_rows = data.get("businessRows")
    risk_items = data.get("riskItems")
    if not isinstance(business_rows, list):
        return False, "businessRows is missing or not a list"
    if not isinstance(risk_items, list):
        return False, "riskItems is missing or not a list"
    for field in ("costByCurrency", "packageOrderRevenueByCurrency", "pendingPackageRevenueByCurrency"):
        if not isinstance(data.get(field), list):
            return False, f"{field} is missing or not a list"

    row_gaps: list[str] = []
    for row in business_rows[:10]:
        if not isinstance(row, dict):
            row_gaps.append("business row is not an object")
            continue
        missing = [key for key in ("businessKey", "runCount", "chargedRunCount", "billingIssueCount") if key not in row]
        if missing:
            row_gaps.append(f"{row.get('businessKey') or '-'} missing={missing}")
    if row_gaps:
        return False, f"businessRows schema gaps={row_gaps[:3]}"

    issue_count = int(data.get("billingIssueCount") or 0)
    unpriced_count = int(data.get("unpricedRunCount") or 0)
    run_count = int(data.get("runCount") or 0)
    billable_count = int(data.get("billableRunCount") or 0)
    charged_count = int(data.get("chargedRunCount") or 0)
    if issue_count > max(0, max_billing_issues):
        return (
            False,
            f"billingIssues={issue_count} max={max_billing_issues} "
            f"unpriced={unpriced_count} riskSample={_short(risk_items[:3])}",
        )
    if unpriced_count > max(0, max_unpriced_runs):
        return False, f"unpriced={unpriced_count} max={max_unpriced_runs}"
    return (
        True,
        f"runs={run_count} billable={billable_count} charged={charged_count} "
        f"billingIssues={issue_count} unpriced={unpriced_count} rows={len(business_rows)}",
    )


def _validate_auth_scope_summary(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "auth scope summary is not an object"
    totals = data.get("totals")
    roles = data.get("roles")
    tenants = data.get("tenants")
    risks = data.get("risks")
    checklist = data.get("checklist")
    business_api_policy = data.get("businessApiPolicy")
    role_boundary = data.get("roleBoundary")
    if not isinstance(totals, dict):
        return False, "totals is missing or not an object"
    if not isinstance(roles, list):
        return False, "roles is missing or not a list"
    if not isinstance(tenants, list):
        return False, "tenants is missing or not a list"
    if not isinstance(risks, list):
        return False, "risks is missing or not a list"
    if not isinstance(checklist, list):
        return False, "checklist is missing or not a list"
    if not isinstance(business_api_policy, list):
        return False, "businessApiPolicy is missing or not a list"
    if not isinstance(role_boundary, list):
        return False, "roleBoundary is missing or not a list"
    if "releaseReady" not in data:
        return False, "releaseReady is missing"

    users = int(totals.get("users") or 0)
    active_users = int(totals.get("activeUsers") or 0)
    admin_users = int(totals.get("adminUsers") or 0)
    active_sessions = int(totals.get("activeSessions") or 0)
    blocking_count = int(data.get("blockingRiskCount") or 0)
    warning_count = int(data.get("warningRiskCount") or 0)
    if users <= 0:
        return False, "no users returned"
    if active_users <= 0:
        return False, f"no active users users={users}"
    if admin_users <= 0:
        return False, f"no admin users users={users}"

    schema_gaps: list[str] = []
    for item in roles[:10]:
        if not isinstance(item, dict) or not item.get("role"):
            schema_gaps.append(f"bad role item={_short(item)}")
    for item in risks[:10]:
        if not isinstance(item, dict):
            schema_gaps.append("risk item is not an object")
            continue
        missing = [key for key in ("key", "title", "severity", "count", "detail") if key not in item]
        if missing:
            schema_gaps.append(f"{item.get('key') or '-'} missing={missing}")
    for item in checklist[:10]:
        if not isinstance(item, dict):
            schema_gaps.append("checklist item is not an object")
            continue
        missing = [key for key in ("key", "title", "passed", "detail", "action") if key not in item]
        if missing:
            schema_gaps.append(f"{item.get('key') or '-'} missing={missing}")
    policy_keys: set[str] = set()
    for item in business_api_policy[:10]:
        if not isinstance(item, dict):
            schema_gaps.append("businessApiPolicy item is not an object")
            continue
        missing = [key for key in ("key", "title", "detail", "enforced") if key not in item]
        if missing:
            schema_gaps.append(f"{item.get('key') or '-'} missing={missing}")
        policy_keys.add(str(item.get("key") or ""))
    boundary_keys: set[str] = set()
    for item in role_boundary[:10]:
        if not isinstance(item, dict):
            schema_gaps.append("roleBoundary item is not an object")
            continue
        missing = [key for key in ("key", "title", "principal", "allowed", "blocked", "enforced") if key not in item]
        if missing:
            schema_gaps.append(f"{item.get('key') or '-'} missing={missing}")
        boundary_keys.add(str(item.get("key") or ""))
    if schema_gaps:
        return False, f"schema gaps={schema_gaps[:3]}"
    required_policy_keys = {
        "client_user_bound_scope",
        "unscoped_client_user_blocked",
        "admin_service_can_act_as_tenant",
    }
    missing_policy_keys = sorted(required_policy_keys - policy_keys)
    if missing_policy_keys:
        return False, f"businessApiPolicy missing required policies={missing_policy_keys}"
    required_boundary_keys = {
        "admin_user",
        "client_user",
        "service_token",
        "coze_toolbox",
    }
    missing_boundary_keys = sorted(required_boundary_keys - boundary_keys)
    if missing_boundary_keys:
        return False, f"roleBoundary missing required boundaries={missing_boundary_keys}"
    not_enforced = [
        str(item.get("key") or "-")
        for item in business_api_policy
        if isinstance(item, dict) and item.get("enforced") is not True
    ]
    if not_enforced:
        return False, f"business API policies not enforced={not_enforced[:5]}"
    boundary_not_enforced = [
        str(item.get("key") or "-")
        for item in role_boundary
        if isinstance(item, dict) and item.get("enforced") is not True
    ]
    if boundary_not_enforced:
        return False, f"role boundaries not enforced={boundary_not_enforced[:5]}"

    blocking_risks = [
        f"{item.get('key')}:{item.get('count')}"
        for item in risks
        if isinstance(item, dict)
        and item.get("severity") == "danger"
        and int(item.get("count") or 0) > 0
    ]
    if blocking_risks:
        return False, f"blocking auth risks={blocking_risks[:5]}"
    failed_checks = [
        str(item.get("key") or "-")
        for item in checklist
        if isinstance(item, dict) and item.get("passed") is False
    ]
    if data.get("releaseReady") is False or blocking_count > 0 or warning_count > 0 or failed_checks:
        return (
            False,
            f"auth not release ready blocking={blocking_count} warnings={warning_count} "
            f"failedChecks={failed_checks[:5]}",
        )
    return (
        True,
        f"users={users} active={active_users} admins={admin_users} "
        f"sessions={active_sessions} risks={len(risks)} checklist={len(checklist)} "
        f"policies={len(business_api_policy)} boundaries={len(role_boundary)}",
    )


def _business_headers(token: str) -> dict[str, str]:
    normalized = str(token or "").strip()
    return {"Authorization": f"Bearer {normalized}"} if normalized else {}


def _run_comfyui_workflow_compatibility_check(
    *,
    base_url: str,
    admin_token: str,
    allow_warnings: bool,
) -> dict[str, Any]:
    if not str(admin_token or "").strip():
        return _result("comfyui_workflow_compatibility", True, "skipped: admin/service token not provided")
    timeout = httpx.Timeout(60.0, connect=10.0)
    with httpx.Client(base_url=base_url, headers=_business_headers(admin_token), timeout=timeout, trust_env=False) as client:
        response = client.get("/api/admin/comfyui/workflow-compatibility")
        try:
            data = response.json()
        except Exception:
            data = {"text": response.text}
    ok, detail = _validate_comfyui_workflow_compatibility(data, allow_warnings=allow_warnings)
    return _result("comfyui_workflow_compatibility", response.status_code == 200 and ok, f"status={response.status_code} {detail}")


def _run_business_route_checks(
    *,
    base_url: str,
    token: str,
) -> list[dict[str, Any]]:
    timeout = httpx.Timeout(30.0, connect=10.0)
    checks: list[dict[str, Any]] = []
    with httpx.Client(base_url=base_url, headers=_business_headers(token), timeout=timeout, trust_env=False) as client:
        for spec in BUSINESS_ROUTE_SPECS:
            try:
                status, data = _post_json(client, spec.path, dict(spec.payload))
                if isinstance(data, dict):
                    selected = data.get("selectedDisplayName") or data.get("selectedCapabilityId")
                    selected_by = data.get("selectedBy") or "-"
                    ok = status == 200 and bool(data.get("selectedCapabilityId"))
                    detail = f"status={status} selected={selected or '-'} by={selected_by}"
                else:
                    ok = False
                    detail = f"status={status} body={_short(data)}"
                checks.append(_result(f"business_route_{spec.key}", ok, detail))
            except Exception as exc:
                checks.append(_result(f"business_route_{spec.key}", False, repr(exc)))
    return checks


def _run_eval_operations_health_check(
    *,
    base_url: str,
    eval_admin_token: str,
) -> dict[str, Any]:
    if not str(eval_admin_token or "").strip():
        return _result("eval_operations_health", True, "skipped: EVAL_ADMIN_TOKEN not provided")
    params = {
        "admin_token": eval_admin_token,
        "staleMinutes": "30",
        "submitGraceMinutes": "5",
        "recentHours": "24",
        "limit": "20",
    }
    timeout = httpx.Timeout(30.0, connect=10.0)
    with httpx.Client(base_url=base_url, timeout=timeout, trust_env=False) as client:
        response = client.get("/api/evals/admin/operations-health", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"text": response.text}
    status = str(data.get("status") or "").strip().lower() if isinstance(data, dict) else ""
    issue_count = len(data.get("issues") or []) if isinstance(data, dict) and isinstance(data.get("issues"), list) else 0
    ok = response.status_code == 200 and status in {"healthy", "warning"}
    detail = f"status={response.status_code} health={status or '-'} issues={issue_count}"
    if status == "critical":
        detail += f" sample={_short((data.get('issues') or [])[:3]) if isinstance(data, dict) else '-'}"
    return _result("eval_operations_health", ok, detail)


def _run_business_usage_summary_check(
    *,
    base_url: str,
    admin_token: str,
    window_hours: int,
    max_unresolved_issues: int,
) -> dict[str, Any]:
    if not str(admin_token or "").strip():
        return _result("business_usage_summary", True, "skipped: admin/service token not provided")
    timeout = httpx.Timeout(30.0, connect=10.0)
    params = {"window_hours": str(max(1, min(int(window_hours or 24), 24 * 90)))}
    with httpx.Client(base_url=base_url, headers=_business_headers(admin_token), timeout=timeout, trust_env=False) as client:
        response = client.get("/api/admin/business/usage-summary", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"text": response.text}
    ok, detail = _validate_business_usage_summary(data, max_unresolved_issues=max_unresolved_issues)
    return _result("business_usage_summary", response.status_code == 200 and ok, f"status={response.status_code} {detail}")


def _run_business_capability_governance_check(
    *,
    base_url: str,
    admin_token: str,
    max_warnings: int,
) -> dict[str, Any]:
    if not str(admin_token or "").strip():
        return _result("business_capability_governance", True, "skipped: admin/service token not provided")
    timeout = httpx.Timeout(30.0, connect=10.0)
    with httpx.Client(base_url=base_url, headers=_business_headers(admin_token), timeout=timeout, trust_env=False) as client:
        response = client.get("/api/admin/business/capabilities")
        try:
            data = response.json()
        except Exception:
            data = {"text": response.text}
    ok, detail = _validate_business_capability_governance(data, max_warnings=max_warnings)
    return _result("business_capability_governance", response.status_code == 200 and ok, f"status={response.status_code} {detail}")


def _run_commercial_report_check(
    *,
    base_url: str,
    admin_token: str,
    month: str,
    business_key: str,
    max_billing_issues: int,
    max_unpriced_runs: int,
) -> dict[str, Any]:
    if not str(admin_token or "").strip():
        return _result("commercial_report", True, "skipped: admin/service token not provided")
    timeout = httpx.Timeout(30.0, connect=10.0)
    params = {"limit": "1000"}
    if str(month or "").strip():
        params["month"] = str(month).strip()
    if str(business_key or "").strip() and str(business_key).strip() != "all":
        params["business_key"] = str(business_key).strip()
    with httpx.Client(base_url=base_url, headers=_business_headers(admin_token), timeout=timeout, trust_env=False) as client:
        response = client.get("/api/admin/billing/commercial-report", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"text": response.text}
    ok, detail = _validate_commercial_report(
        data,
        max_billing_issues=max_billing_issues,
        max_unpriced_runs=max_unpriced_runs,
    )
    return _result("commercial_report", response.status_code == 200 and ok, f"status={response.status_code} {detail}")


def _run_auth_scope_summary_check(
    *,
    base_url: str,
    admin_token: str,
) -> dict[str, Any]:
    if not str(admin_token or "").strip():
        return _result("auth_scope_summary", True, "skipped: admin/service token not provided")
    timeout = httpx.Timeout(30.0, connect=10.0)
    with httpx.Client(base_url=base_url, headers=_business_headers(admin_token), timeout=timeout, trust_env=False) as client:
        response = client.get("/api/auth/scope-summary")
        try:
            data = response.json()
        except Exception:
            data = {"text": response.text}
    ok, detail = _validate_auth_scope_summary(data)
    return _result("auth_scope_summary", response.status_code == 200 and ok, f"status={response.status_code} {detail}")


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
    parser.add_argument(
        "--skip-business-route",
        action="store_true",
        help="Skip no-cost core business route preview checks.",
    )
    parser.add_argument(
        "--service-token",
        default=os.getenv("SERVICE_API_TOKEN") or "",
        help="Optional service token for business route preview APIs.",
    )
    parser.add_argument(
        "--admin-token",
        default=os.getenv("ADMIN_API_TOKEN") or os.getenv("SERVICE_API_TOKEN") or "",
        help="Optional admin/service token for admin-only preflight checks.",
    )
    parser.add_argument(
        "--allow-comfyui-compat-warnings",
        action="store_true",
        help="Allow partial ComfyUI workflow compatibility warnings. Default blocks warnings.",
    )
    parser.add_argument(
        "--eval-admin-token",
        default=os.getenv("EVAL_ADMIN_TOKEN") or "",
        help="Optional eval admin token. If omitted, eval operations health is skipped.",
    )
    parser.add_argument(
        "--business-summary-window-hours",
        type=int,
        default=24,
        help="Business usage summary window for unresolved issue gate.",
    )
    parser.add_argument(
        "--max-unresolved-business-issues",
        type=int,
        default=0,
        help="Maximum unresolved business issues allowed in the summary window.",
    )
    parser.add_argument(
        "--max-business-governance-warnings",
        type=int,
        default=0,
        help="Maximum warnings allowed on default core business versions.",
    )
    parser.add_argument(
        "--billing-report-month",
        default="",
        help="Optional YYYY-MM month for the commercial billing report gate. Default uses backend current month.",
    )
    parser.add_argument(
        "--billing-business-key",
        default="all",
        help="Optional business key for the commercial billing report gate.",
    )
    parser.add_argument(
        "--max-billing-issues",
        type=int,
        default=0,
        help="Maximum commercial report billing issues allowed.",
    )
    parser.add_argument(
        "--max-unpriced-billing-runs",
        type=int,
        default=0,
        help="Maximum succeeded but unpriced business runs allowed in the commercial report.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary at the end.")
    parser.add_argument("--report", default="", help="Optional JSON report path.")
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
            ok, queue_detail = _validate_comfyui_queue_summary(data)
            detail = f"status={status} {queue_detail}"
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

        try:
            status, data = _get_json(client, "/api/evals/workflow-versions?includeAuxiliary=true")
            ok, catalog_detail = _validate_internal_eval_workflow_catalog(data)
            checks.append(_result("eval_workflow_internal_catalog", status == 200 and ok, f"status={status} {catalog_detail}"))
        except Exception as exc:
            checks.append(_result("eval_workflow_internal_catalog", False, repr(exc)))

    if not args.skip_business_route:
        checks.extend(_run_business_route_checks(base_url=base_url, token=args.service_token))

    checks.append(
        _run_comfyui_workflow_compatibility_check(
            base_url=base_url,
            admin_token=args.admin_token or args.service_token,
            allow_warnings=args.allow_comfyui_compat_warnings,
        )
    )

    checks.append(
        _run_business_capability_governance_check(
            base_url=base_url,
            admin_token=args.admin_token or args.service_token,
            max_warnings=args.max_business_governance_warnings,
        )
    )

    checks.append(
        _run_business_usage_summary_check(
            base_url=base_url,
            admin_token=args.admin_token or args.service_token,
            window_hours=args.business_summary_window_hours,
            max_unresolved_issues=args.max_unresolved_business_issues,
        )
    )

    checks.append(
        _run_commercial_report_check(
            base_url=base_url,
            admin_token=args.admin_token or args.service_token,
            month=args.billing_report_month,
            business_key=args.billing_business_key,
            max_billing_issues=args.max_billing_issues,
            max_unpriced_runs=args.max_unpriced_billing_runs,
        )
    )

    checks.append(
        _run_auth_scope_summary_check(
            base_url=base_url,
            admin_token=args.admin_token or args.service_token,
        )
    )

    checks.append(_run_eval_operations_health_check(base_url=base_url, eval_admin_token=args.eval_admin_token))

    ok = all(item.get("ok") for item in checks)
    summary = {"baseUrl": base_url, "ok": ok, "checks": checks}
    if args.report:
        report_path = _write_report(summary, args.report)
        if not args.json:
            print(f"report: {report_path}")
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
