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
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

try:
    from app.constants.business_api_contract import business_api_enum_doc_tokens
except Exception:  # pragma: no cover - smoke can still validate docs in stripped envs
    business_api_enum_doc_tokens = None


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
BACKEND_LOG_REGRESSION_PATTERNS = (
    "QueuePool limit",
    "business run finalize loop failed",
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


REQUIRED_BUSINESS_DELIVERY_SAMPLE_FILES = (
    "request.example.json",
    "submit.response.example.json",
    "poll.request.example.json",
    "poll.running.response.example.json",
    "poll.succeeded.response.example.json",
    "poll.failed.response.example.json",
)

BUSINESS_DELIVERY_DOC_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "image_edit_gpt_image2_editor",
        "label": "图编辑 · GPT Image 2 通用改图",
        "base_folder": "image-edit-business-delivery",
        "folder": "01_gpt_image2_editor",
        "path": "/api/business/image-edit/runs",
        "enum_fields": ("editSkill", "quality", "size", "image_edit.output_format"),
        "error_codes": (
            "IMAGE_EDIT_INSTRUCTION_REQUIRED",
            "IMAGE_EDIT_SKILL_INVALID",
            "IMAGE_EDIT_REFERENCE_REQUIRED",
            "IMAGE_EDIT_TARGET_REQUIRED",
            "IMAGE_EDIT_CANVAS_TOO_SMALL",
            "VENDOR_API_EXECUTION_FAILED",
        ),
    },
    {
        "key": "gpt_image2_controlled_fission",
        "label": "GPT Image 2 + VL 受控裂变",
        "folder": "01_gpt_image2_controlled_fission",
        "path": "/api/business/fission/runs",
        "enum_fields": ("status", "variation_strength", "quality", "size"),
        "error_codes": (
            "BUSINESS_IMAGE_URL_REQUIRED",
            "BUSINESS_RUN_TEMPORARY_UNAVAILABLE",
            "VENDOR_API_EXECUTION_FAILED",
        ),
    },
    {
        "key": "comfyui_colorlock_fission",
        "label": "ComfyUI 颜色锁定裂变",
        "folder": "02_comfyui_colorlock_fission",
        "path": "/api/business/fission/runs",
        "enum_fields": ("status", "profile", "variation_preset"),
        "error_codes": (
            "BUSINESS_IMAGE_URL_REQUIRED",
            "COMFYUI_TIMEOUT",
            "ABILITY_TASK_FAILED",
        ),
    },
    {
        "key": "fission_generated_image_score",
        "label": "裂变生成图评估",
        "folder": "03_fission_generated_image_score",
        "path": "/api/business/fission-evaluate/runs",
        "enum_fields": ("status", "decision"),
        "error_codes": (
            "VL_EVAL_IMAGE_REQUIRED",
            "ABILITY_TASK_FAILED",
        ),
    },
)

BUSINESS_TRUTH_SOURCE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "pattern_extract",
        "version": None,
        "label": "花纹提取默认版",
        "submit_path": "/api/business/pattern-extract/runs",
        "route_path": "/api/business/pattern-extract/route-preview",
    },
    {
        "key": "fission",
        "version": None,
        "label": "图裂变默认版",
        "submit_path": "/api/business/fission/runs",
        "route_path": "/api/business/fission/route-preview",
    },
    {
        "key": "fission",
        "version": "gpt-image2-vl-v2",
        "label": "GPT Image 2 + VL 受控裂变",
        "submit_path": "/api/business/fission/runs",
        "eval_workflow_id": "business_fission_gpt_image2_vl_v1",
        "eval_version": "gpt-image2-vl-v2",
    },
    {
        "key": "fission",
        "version": "comfyui-vl-control-v2",
        "label": "ComfyUI 颜色锁定裂变",
        "submit_path": "/api/business/fission/runs",
        "eval_workflow_id": "business_fission_comfyui_vl_control_v1",
        "eval_version": "comfyui-vl-control-v2",
    },
    {
        "key": "fission_evaluate",
        "version": "v1",
        "label": "裂变生成图评估",
        "submit_path": "/api/business/fission-evaluate/runs",
        "eval_workflow_id": "ability_fission_generated_image_evaluate_v1",
        "eval_version": "generated-image-eval-v1",
    },
    {
        "key": "image_edit",
        "version": "gpt-image2-editor-v1",
        "label": "图编辑 · GPT Image 2 通用改图",
        "submit_path": "/api/business/image-edit/runs",
        "eval_workflow_id": "business_image_edit_gpt_image2_editor_v1",
        "eval_version": "gpt-image2-editor-v1",
    },
    {
        "key": "product_design",
        "version": "product-design-gpt-image2-v1",
        "label": "产品设计 · GPT Image 2 上品设计",
        "submit_path": "/api/business/product-design/runs",
        "route_path": "/api/business/product-design/route-preview",
        "eval_workflow_id": "business_product_design_gpt_image2_v1",
        "eval_version": "product-design-gpt-image2-v1",
    },
    {
        "key": "outpaint",
        "version": None,
        "label": "扩图默认版",
        "submit_path": "/api/business/outpaint/runs",
        "route_path": "/api/business/outpaint/route-preview",
    },
)

BUSINESS_API_ENUM_DOC_TOKENS = tuple(business_api_enum_doc_tokens()) if business_api_enum_doc_tokens else (
    "queued",
    "running",
    "succeeded",
    "failed",
    "gpt-image2-vl-v2",
    "comfyui-vl-control-v2",
    "generated-image-eval-v1",
    "variation_strength",
    "profile",
    "variation_preset",
    "selectedBy",
    "selectedStatus",
    "BUSINESS_IMAGE_URL_REQUIRED",
    "BUSINESS_RUN_ID_REQUIRED",
    "COMFYUI_QUEUE_FULL",
    "POLLING_TOO_FREQUENT",
)

PER_FEATURE_RELEASE_CHECKLIST_TOKENS = (
    "逐功能上线检查表",
    "接口入口",
    "入参字段",
    "参数映射",
    "执行节点",
    "节点依赖",
    "结果回填",
    "错误路径",
    "GPT Image 2 + VL 受控裂变",
    "ComfyUI 颜色锁定裂变",
    "裂变生成图评估",
    "图编辑 · GPT Image 2 通用改图",
    "旧四方连续裂变",
    "String",
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
    supported = int(data.get("supportedServers") or 0)
    blocked = int(data.get("backendBlockedServers") or 0)
    feed_gap = int(data.get("feedGapServers") or 0)
    total_capacity = data.get("totalCapacity")
    idle_slots = data.get("totalIdleSlots")
    utilization = data.get("utilization")
    diagnostics = data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
    if supported <= 0:
        return False, f"no supported ComfyUI server diagnostics={_short(diagnostics)}"
    if blocked > 0:
        return False, f"backendBlockedServers={blocked} diagnostics={_short(diagnostics)}"
    degraded = unsupported > 0
    prefix = f"degraded unsupportedServers={unsupported} " if degraded else ""
    return (
        True,
        prefix
        + "servers="
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


def _validate_business_api_usage_center(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "business API usage response is not an object"
    items = data.get("items")
    groups = data.get("groups")
    summary = data.get("summary")
    pagination = data.get("pagination")
    if not isinstance(items, list):
        return False, "items is missing or not a list"
    if not isinstance(groups, list):
        return False, "groups is missing or not a list"
    if not isinstance(summary, dict):
        return False, "summary is missing or not an object"
    if not isinstance(pagination, dict):
        return False, "pagination is missing or not an object"

    required_summary_keys = {
        "total",
        "successCount",
        "errorCount",
        "submitCount",
        "pollCount",
        "callbackCount",
        "uniqueRunCount",
        "averageDurationMs",
    }
    missing_summary = sorted(required_summary_keys - set(summary))
    if missing_summary:
        return False, f"summary missing={missing_summary}"
    required_pagination_keys = {"total", "offset", "limit", "hasMore", "nextOffset"}
    missing_pagination = sorted(required_pagination_keys - set(pagination))
    if missing_pagination:
        return False, f"pagination missing={missing_pagination}"

    schema_gaps: list[str] = []
    for item in items[:10]:
        if not isinstance(item, dict):
            schema_gaps.append("usage item is not an object")
            continue
        missing = [key for key in ("id", "method", "path", "createdAt") if key not in item]
        if missing:
            schema_gaps.append(f"usage item {item.get('id') or '-'} missing={missing}")
    for group in groups[:10]:
        if not isinstance(group, dict):
            schema_gaps.append("run group is not an object")
            continue
        missing = [
            key
            for key in (
                "runId",
                "totalCount",
                "submitCount",
                "pollCount",
                "callbackCount",
                "errorCount",
                "needsAttention",
                "lastSeenAt",
            )
            if key not in group
        ]
        if missing:
            schema_gaps.append(f"run group {group.get('runId') or '-'} missing={missing}")
    if schema_gaps:
        return False, f"schema gaps={schema_gaps[:3]}"

    total = int(summary.get("total") or data.get("total") or 0)
    submit_count = int(summary.get("submitCount") or 0)
    poll_count = int(summary.get("pollCount") or 0)
    callback_count = int(summary.get("callbackCount") or 0)
    error_count = int(summary.get("errorCount") or 0)
    unique_run_count = int(summary.get("uniqueRunCount") or 0)
    needs_attention = [
        str(group.get("runId") or "-")
        for group in groups
        if isinstance(group, dict) and group.get("needsAttention") is True
    ]
    if unique_run_count > 0 and not groups:
        return False, f"uniqueRunCount={unique_run_count} but run groups are empty"
    return (
        True,
        "total="
        f"{total} submit={submit_count} poll={poll_count} callback={callback_count} "
        f"errors={error_count} runs={unique_run_count} groups={len(groups)} "
        f"attention={len(needs_attention)} sample={needs_attention[:5] if needs_attention else '-'}",
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validate_business_delivery_docs(repo_root: str | Path | None = None) -> tuple[bool, str]:
    root = Path(repo_root).expanduser() if repo_root is not None else _repo_root()
    examples_base = root / "docs" / "api" / "examples"
    enum_doc = root / "docs" / "standards" / "business-api-enums.md"
    error_catalog = root / "docs" / "standards" / "error-catalog.md"
    errors: list[str] = []
    enum_text = ""
    error_text = ""
    if not enum_doc.exists():
        errors.append("missing docs/standards/business-api-enums.md")
    else:
        enum_text = enum_doc.read_text(encoding="utf-8")
    if not error_catalog.exists():
        errors.append("missing docs/standards/error-catalog.md")
    else:
        error_text = error_catalog.read_text(encoding="utf-8")

    base_folders = sorted({str(spec.get("base_folder") or "fission-business-delivery") for spec in BUSINESS_DELIVERY_DOC_SPECS})
    for base_folder in base_folders:
        root_readme = examples_base / base_folder / "README.md"
        if not root_readme.exists():
            errors.append(f"missing {base_folder} README.md")
        else:
            root_text = root_readme.read_text(encoding="utf-8")
            for token in (
                "runId",
                "/api/business/runs/get",
                "status",
                "错误码",
                "docs/standards/business-api-enums.md",
                "docs/standards/error-catalog.md",
            ):
                if token not in root_text:
                    errors.append(f"{base_folder} README missing {token}")

    for spec in BUSINESS_DELIVERY_DOC_SPECS:
        base = examples_base / str(spec.get("base_folder") or "fission-business-delivery")
        folder = base / str(spec["folder"])
        readme = folder / "README.md"
        label = str(spec["label"])
        if not folder.exists():
            errors.append(f"{label} missing folder={folder.relative_to(root) if folder.is_absolute() else folder}")
            continue
        if not readme.exists():
            errors.append(f"{label} missing README.md")
            continue
        text = readme.read_text(encoding="utf-8")
        required_text_tokens = (
            str(spec["path"]),
            "参数说明",
            "常见错误",
            "runId",
            "status",
            "docs/standards/business-api-enums.md",
            "docs/standards/error-catalog.md",
        )
        for token in required_text_tokens:
            if token not in text:
                errors.append(f"{label} README missing {token}")
        for field in spec["enum_fields"]:
            if str(field) not in text:
                errors.append(f"{label} README missing enum field={field}")
            if enum_text and str(field) not in enum_text:
                errors.append(f"{label} enum field not in business-api-enums.md={field}")
        for code in spec["error_codes"]:
            if str(code) not in text:
                errors.append(f"{label} README missing error code={code}")
            if error_text and str(code) not in error_text:
                errors.append(f"{label} error code not in error-catalog.md={code}")

        for sample_name in REQUIRED_BUSINESS_DELIVERY_SAMPLE_FILES:
            sample_path = folder / sample_name
            if not sample_path.exists():
                errors.append(f"{label} missing sample={sample_name}")
                continue
            try:
                sample = json.loads(sample_path.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"{label} invalid json sample={sample_name} error={exc}")
                continue
            if not isinstance(sample, dict):
                errors.append(f"{label} sample is not object={sample_name}")
                continue
            if sample_name == "submit.response.example.json":
                missing = [key for key in ("runId", "taskId", "status", "taskStatus", "retryAfterSeconds") if key not in sample]
                if missing:
                    errors.append(f"{label} submit response missing={missing}")
            elif sample_name == "poll.request.example.json":
                if not (sample.get("runId") or sample.get("taskId")):
                    errors.append(f"{label} poll request missing runId/taskId")
            elif sample_name.startswith("poll."):
                if "status" not in sample:
                    errors.append(f"{label} {sample_name} missing status")
                if sample_name == "poll.failed.response.example.json":
                    missing = [key for key in ("errorCode", "errorMessage") if key not in sample]
                    if missing:
                        errors.append(f"{label} failed response missing={missing}")

    if errors:
        return False, f"errors={errors[:8]} total={len(errors)}"
    return True, f"contracts={len(BUSINESS_DELIVERY_DOC_SPECS)} samples={len(REQUIRED_BUSINESS_DELIVERY_SAMPLE_FILES)} each"


def _run_business_delivery_docs_check() -> dict[str, Any]:
    ok, detail = _validate_business_delivery_docs()
    return _result("business_delivery_docs", ok, detail)


def _field_names_from_schema(schema: Any) -> set[str]:
    if not isinstance(schema, dict):
        return set()
    fields = schema.get("fields")
    if not isinstance(fields, list):
        return set()
    names: set[str] = set()
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip()
        if name:
            names.add(name)
    return names


def _openapi_request_properties(openapi: Any, path: str) -> set[str]:
    if not isinstance(openapi, dict):
        return set()
    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        return set()
    operation = paths.get(path)
    if not isinstance(operation, dict):
        return set()
    post = operation.get("post")
    if not isinstance(post, dict):
        return set()
    request_body = post.get("requestBody")
    if not isinstance(request_body, dict):
        return set()
    content = request_body.get("content")
    if not isinstance(content, dict):
        return set()
    json_content = content.get("application/json")
    if not isinstance(json_content, dict):
        return set()
    schema = json_content.get("schema")
    if not isinstance(schema, dict):
        return set()
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return set()
    return {str(key) for key in properties}


def _find_business_capability(items: list[Any], *, business_key: str, version: str | None) -> dict[str, Any] | None:
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("businessKey") or "").strip() != business_key:
            continue
        if version is None and item.get("isDefault") is True:
            return item
        if version is not None and str(item.get("version") or "").strip() == version:
            return item
    return None


def _eval_workflow_index(eval_catalog: Any) -> dict[str, dict[str, Any]]:
    items = eval_catalog.get("items") if isinstance(eval_catalog, dict) else eval_catalog
    if not isinstance(items, list):
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        workflow_id = str(item.get("workflow_id") or item.get("workflowId") or item.get("id") or "").strip()
        if workflow_id:
            indexed[workflow_id] = item
    return indexed


def _graph_primary_node(graph: Any, primary_ability_id: str) -> dict[str, Any] | None:
    if not isinstance(graph, dict):
        return None
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if isinstance(node, dict) and str(node.get("abilityId") or "").strip() == primary_ability_id:
            return node
    return None


def _validate_business_api_enum_docs(repo_root: str | Path | None = None) -> tuple[bool, str]:
    root = Path(repo_root).expanduser() if repo_root is not None else _repo_root()
    path = root / "docs" / "standards" / "business-api-enums.md"
    if not path.exists():
        return False, f"missing {path.relative_to(root)}"
    text = path.read_text(encoding="utf-8")
    missing = [token for token in BUSINESS_API_ENUM_DOC_TOKENS if token not in text]
    if missing:
        return False, f"missing tokens={missing[:8]} total={len(missing)}"
    return True, f"tokens={len(BUSINESS_API_ENUM_DOC_TOKENS)} path={path.relative_to(root)}"


def _validate_business_truth_source_consistency(
    capabilities_data: Any,
    business_openapi: Any,
    eval_catalog: Any,
    *,
    repo_root: str | Path | None = None,
) -> tuple[bool, str]:
    if not isinstance(capabilities_data, dict):
        return False, "business capability response is not an object"
    items = capabilities_data.get("items")
    if not isinstance(items, list):
        return False, "business capability items is missing or not a list"
    if not isinstance(business_openapi, dict):
        return False, "business OpenAPI is not an object"

    errors: list[str] = []
    checked: list[str] = []
    eval_index = _eval_workflow_index(eval_catalog)

    run_get_props = _openapi_request_properties(business_openapi, "/api/business/runs/get")
    if not {"runId", "taskId", "detail", "includeDebug"}.issubset(run_get_props):
        errors.append("查询接口 /api/business/runs/get 缺少 runId/taskId/detail/includeDebug")

    for spec in BUSINESS_TRUTH_SOURCE_SPECS:
        business_key = str(spec["key"])
        version = spec.get("version")
        version_text = str(version) if version is not None else None
        label = str(spec["label"])
        item = _find_business_capability(items, business_key=business_key, version=version_text)
        if item is None:
            errors.append(f"{label} 缺少业务版本 businessKey={business_key} version={version_text or 'default'}")
            continue
        checked.append(f"{business_key}:{item.get('version') or '-'}")

        if str(item.get("status") or "").strip().lower() != "active":
            errors.append(f"{label} 业务版本未启用 status={item.get('status') or '-'}")
        input_fields = _field_names_from_schema(item.get("inputSchema"))
        output_fields = _field_names_from_schema(item.get("outputSchema"))
        if not input_fields:
            errors.append(f"{label} 缺少 inputSchema.fields")
        if not output_fields:
            errors.append(f"{label} 缺少 outputSchema.fields")

        submit_path = str(spec["submit_path"])
        request_props = _openapi_request_properties(business_openapi, submit_path)
        if not request_props:
            errors.append(f"{label} 业务 OpenAPI 缺少提交接口 {submit_path}")
        else:
            missing_fields = sorted(input_fields - request_props - {"url", "original_image", "generated_image"})
            # 测评端会用 url/original_image/generated_image，业务 API 必须有规范字段。
            alias_requirements = {
                "url": "imageUrl",
                "original_image": "originalImageUrl",
                "generated_image": "generatedImageUrl",
            }
            for alias, canonical in alias_requirements.items():
                if alias in input_fields and canonical not in request_props:
                    missing_fields.append(canonical)
            if missing_fields:
                errors.append(f"{label} OpenAPI 参数缺失={missing_fields[:8]} path={submit_path}")

        route_path = spec.get("route_path")
        if route_path and not _openapi_request_properties(business_openapi, str(route_path)):
            errors.append(f"{label} 业务 OpenAPI 缺少路由预览接口 {route_path}")

        primary_ability_id = str(item.get("primaryAbilityId") or "").strip()
        if not primary_ability_id:
            errors.append(f"{label} 缺少 primaryAbilityId")
            continue
        recipe = item.get("recipe") if isinstance(item.get("recipe"), dict) else {}
        recipe_primary = str(recipe.get("primaryAbilityId") or "").strip()
        if recipe_primary and recipe_primary != primary_ability_id:
            errors.append(f"{label} recipe.primaryAbilityId 与 primaryAbilityId 不一致 {recipe_primary}!={primary_ability_id}")
        graph = item.get("orchestrationGraph") if isinstance(item.get("orchestrationGraph"), dict) else {}
        summary = graph.get("summary") if isinstance(graph.get("summary"), dict) else {}
        if int(summary.get("executableStepCount") or 0) <= 0:
            errors.append(f"{label} 编排图没有可执行步骤")
        if summary.get("hasPrimaryStep") is not True:
            errors.append(f"{label} 编排图缺少主能力步骤")
        primary_node = _graph_primary_node(graph, primary_ability_id)
        if primary_node is None:
            errors.append(f"{label} 编排图没有主能力节点 {primary_ability_id}")
        else:
            node_schema = primary_node.get("inputSchema") if isinstance(primary_node.get("inputSchema"), dict) else {}
            if int(node_schema.get("fieldCount") or 0) <= 0:
                errors.append(f"{label} 主能力节点缺少参数摘要 {primary_ability_id}")
            if primary_node.get("routing") in (None, "", {}, []):
                errors.append(f"{label} 主能力节点缺少路由摘要 {primary_ability_id}")

        eval_workflow_id = str(spec.get("eval_workflow_id") or "").strip()
        if eval_workflow_id:
            eval_item = eval_index.get(eval_workflow_id)
            if not eval_item:
                errors.append(f"{label} 测评端缺少入口 workflow={eval_workflow_id}")
            else:
                expected_eval_version = str(spec.get("eval_version") or "").strip()
                actual_eval_version = str(eval_item.get("version") or "").strip()
                if expected_eval_version and actual_eval_version != expected_eval_version:
                    errors.append(f"{label} 测评端版本不一致 {actual_eval_version}!={expected_eval_version}")
                if str(eval_item.get("status") or "").strip().lower() != "active":
                    errors.append(f"{label} 测评端入口未启用 status={eval_item.get('status') or '-'}")
                eval_fields = _field_names_from_schema(eval_item.get("parameters_schema") or eval_item.get("parametersSchema"))
                if not eval_fields:
                    errors.append(f"{label} 测评端入口缺少参数 schema workflow={eval_workflow_id}")

    docs_ok, docs_detail = _validate_business_api_enum_docs(repo_root)
    if not docs_ok:
        errors.append(f"业务 API 枚举文档不完整：{docs_detail}")

    if errors:
        return False, f"errors={errors[:10]} total={len(errors)} checked={checked}"
    return True, f"checked={checked} enumDocs=ok evalLinks={len(eval_index)}"


def _run_business_truth_source_consistency_check(
    *,
    base_url: str,
    admin_token: str,
) -> dict[str, Any]:
    if not str(admin_token or "").strip():
        return _result("business_truth_source_consistency", True, "skipped: admin/service token not provided")
    timeout = httpx.Timeout(30.0, connect=10.0)
    headers = _business_headers(admin_token)
    with httpx.Client(base_url=base_url, headers=headers, timeout=timeout, trust_env=False) as authed_client:
        cap_response = authed_client.get("/api/admin/business/capabilities")
        try:
            cap_data = cap_response.json()
        except Exception:
            cap_data = {"text": cap_response.text}
    with httpx.Client(base_url=base_url, timeout=timeout, trust_env=False) as client:
        openapi_response = client.get("/api/business/openapi.json")
        try:
            openapi_data = openapi_response.json()
        except Exception:
            openapi_data = {"text": openapi_response.text}
        eval_response = client.get("/api/evals/workflow-versions", params={"includeAuxiliary": "true"})
        try:
            eval_data = eval_response.json()
        except Exception:
            eval_data = {"text": eval_response.text}
    ok, detail = _validate_business_truth_source_consistency(cap_data, openapi_data, eval_data)
    status_ok = cap_response.status_code == 200 and openapi_response.status_code == 200 and eval_response.status_code == 200
    return _result(
        "business_truth_source_consistency",
        status_ok and ok,
        "status="
        f"capabilities:{cap_response.status_code} openapi:{openapi_response.status_code} "
        f"eval:{eval_response.status_code} {detail}",
    )


def _validate_per_feature_release_checklist(repo_root: str | Path | None = None) -> tuple[bool, str]:
    root = Path(repo_root).expanduser() if repo_root is not None else _repo_root()
    path = root / "docs" / "standards" / "per-feature-release-checklist.md"
    if not path.exists():
        return False, f"missing {path.relative_to(root)}"
    text = path.read_text(encoding="utf-8")
    missing = [token for token in PER_FEATURE_RELEASE_CHECKLIST_TOKENS if token not in text]
    if missing:
        return False, f"missing tokens={missing} total={len(missing)}"
    return True, f"tokens={len(PER_FEATURE_RELEASE_CHECKLIST_TOKENS)} path={path.relative_to(root)}"


def _run_per_feature_release_checklist_check() -> dict[str, Any]:
    ok, detail = _validate_per_feature_release_checklist()
    return _result("per_feature_release_checklist", ok, detail)


def _validate_per_feature_release_audit(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "delivery contract audit response is not an object"
    checks = data.get("featureReleaseChecks")
    if not isinstance(checks, list):
        return False, "featureReleaseChecks is missing or not a list"
    required_keys = {
        "image-edit-gpt-image2",
        "gpt-image2-fission",
        "comfyui-colorlock-fission",
        "fission-score",
        "legacy-seamless-fission",
    }
    seen_keys: set[str] = set()
    schema_gaps: list[str] = []
    blocked: list[str] = []
    attention: list[str] = []
    for item in checks:
        if not isinstance(item, dict):
            schema_gaps.append("feature release check is not an object")
            continue
        key = str(item.get("key") or "").strip()
        seen_keys.add(key)
        missing = [
            field
            for field in (
                "key",
                "name",
                "entry",
                "status",
                "mustCheck",
                "releaseEvidence",
                "currentRisk",
                "summary",
                "blockers",
                "warnings",
                "evidence",
            )
            if field not in item
        ]
        if missing:
            schema_gaps.append(f"{key or '-'} missing={missing}")
            continue
        if item.get("status") not in {"done", "doing", "todo"}:
            schema_gaps.append(f"{key}:bad status={item.get('status')}")
        if not isinstance(item.get("mustCheck"), list) or not item.get("mustCheck"):
            schema_gaps.append(f"{key}:mustCheck empty")
        if not isinstance(item.get("blockers"), list):
            schema_gaps.append(f"{key}:blockers not list")
        if not isinstance(item.get("warnings"), list):
            schema_gaps.append(f"{key}:warnings not list")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            schema_gaps.append(f"{key}:evidence empty")
        else:
            for evidence_item in evidence[:5]:
                if not isinstance(evidence_item, dict):
                    schema_gaps.append(f"{key}:evidence item is not object")
                    continue
                evidence_missing = [
                    field
                    for field in ("key", "title", "status", "detail", "action")
                    if field not in evidence_item
                ]
                if evidence_missing:
                    schema_gaps.append(f"{key}:evidence missing={evidence_missing}")
        if item.get("status") == "todo":
            blocked.append(key or "-")
        elif item.get("status") == "doing":
            attention.append(key or "-")
    missing_keys = sorted(required_keys - seen_keys)
    if missing_keys:
        schema_gaps.append(f"missing feature checks={missing_keys}")
    if schema_gaps:
        return False, f"schema gaps={schema_gaps[:5]} total={len(schema_gaps)}"
    return (
        True,
        f"features={len(checks)} blocked={len(blocked)} attention={len(attention)} "
        f"blockedSample={blocked[:5] if blocked else '-'} attentionSample={attention[:5] if attention else '-'}",
    )


def _run_per_feature_release_audit_check(
    *,
    base_url: str,
    admin_token: str,
) -> dict[str, Any]:
    if not str(admin_token or "").strip():
        return _result("per_feature_release_audit", True, "skipped: admin/service token not provided")
    timeout = httpx.Timeout(30.0, connect=10.0)
    with httpx.Client(base_url=base_url, headers=_business_headers(admin_token), timeout=timeout, trust_env=False) as client:
        response = client.get("/api/admin/business/delivery-contracts")
        try:
            data = response.json()
        except Exception:
            data = {"text": response.text}
    ok, detail = _validate_per_feature_release_audit(data)
    return _result("per_feature_release_audit", response.status_code == 200 and ok, f"status={response.status_code} {detail}")


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
    max_billing_issues: int = -1,
    max_unpriced_runs: int = -1,
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
    if max_billing_issues < 0 and max_unpriced_runs < 0:
        return (
            True,
            f"observed-only runs={run_count} billable={billable_count} charged={charged_count} "
            f"billingIssues={issue_count} unpriced={unpriced_count} rows={len(business_rows)} "
            f"riskSample={_short(risk_items[:3])}",
        )
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


def _run_business_api_usage_center_check(
    *,
    base_url: str,
    admin_token: str,
    window_hours: int,
) -> dict[str, Any]:
    if not str(admin_token or "").strip():
        return _result("business_api_usage_center", True, "skipped: admin/service token not provided")
    timeout = httpx.Timeout(30.0, connect=10.0)
    params = {
        "window_hours": str(max(0, min(int(window_hours or 24), 24 * 90))),
        "limit": "10",
        "group_limit": "20",
    }
    with httpx.Client(base_url=base_url, headers=_business_headers(admin_token), timeout=timeout, trust_env=False) as client:
        response = client.get("/api/admin/business/api-key-usage", params=params)
        try:
            data = response.json()
        except Exception:
            data = {"text": response.text}
    ok, detail = _validate_business_api_usage_center(data)
    return _result("business_api_usage_center", response.status_code == 200 and ok, f"status={response.status_code} {detail}")


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


def _run_backend_log_regression_check(
    *,
    unit: str,
    since: str,
    max_regressions: int,
) -> dict[str, Any]:
    unit = str(unit or "podi-backend.service").strip()
    since = str(since or "30 min ago").strip()
    command = ["journalctl", "-u", unit, "--since", since, "--no-pager"]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        return _result("backend_log_regression", True, "skipped: journalctl unavailable")
    except subprocess.TimeoutExpired:
        return _result("backend_log_regression", False, f"journalctl timed out unit={unit} since={since}")
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        return _result("backend_log_regression", True, f"skipped: journalctl failed unit={unit} detail={_short(detail, 240)}")
    lines = (completed.stdout or "").splitlines()
    matched = [line for line in lines if any(pattern in line for pattern in BACKEND_LOG_REGRESSION_PATTERNS)]
    max_regressions = max(0, int(max_regressions))
    ok = len(matched) <= max_regressions
    sample = " | ".join(matched[:3])
    detail = f"unit={unit} since={since} matches={len(matched)} max={max_regressions}"
    if sample:
        detail += f" sample={_short(sample, 500)}"
    return _result("backend_log_regression", ok, detail)


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
        default=-1,
        help="Maximum commercial report billing issues allowed. Negative means observe only.",
    )
    parser.add_argument(
        "--max-unpriced-billing-runs",
        type=int,
        default=-1,
        help="Maximum succeeded but unpriced business runs allowed in the commercial report. Negative means observe only.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary at the end.")
    parser.add_argument("--report", default="", help="Optional JSON report path.")
    parser.add_argument(
        "--skip-backend-log-scan",
        action="store_true",
        help="Skip recent backend journal scan for known production regressions.",
    )
    parser.add_argument(
        "--backend-log-unit",
        default=os.getenv("RELEASE_BACKEND_LOG_UNIT") or "podi-backend.service",
        help="Systemd unit used by the backend journal regression scan.",
    )
    parser.add_argument(
        "--backend-log-since",
        default=os.getenv("RELEASE_BACKEND_LOG_SINCE") or "30 min ago",
        help="Recent window for backend journal regression scan.",
    )
    parser.add_argument(
        "--max-backend-log-regressions",
        type=int,
        default=int(os.getenv("RELEASE_MAX_BACKEND_LOG_REGRESSIONS") or "0"),
        help="Maximum QueuePool/finalize-loop regression log lines allowed in the scan window.",
    )
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

    checks.append(_run_business_delivery_docs_check())
    checks.append(_run_per_feature_release_checklist_check())
    checks.append(
        _run_per_feature_release_audit_check(
            base_url=base_url,
            admin_token=args.admin_token or args.service_token,
        )
    )

    checks.append(
        _run_business_truth_source_consistency_check(
            base_url=base_url,
            admin_token=args.admin_token or args.service_token,
        )
    )

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
        _run_business_api_usage_center_check(
            base_url=base_url,
            admin_token=args.admin_token or args.service_token,
            window_hours=args.business_summary_window_hours,
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
    if not args.skip_backend_log_scan:
        checks.append(
            _run_backend_log_regression_check(
                unit=args.backend_log_unit,
                since=args.backend_log_since,
                max_regressions=args.max_backend_log_regressions,
            )
        )

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
