#!/usr/bin/env python3
"""Audit ability/workflow test coverage before release.

This is a static preflight, not a generation smoke test. It catches the class
of mistakes where an ability is active but its route/test contract is incomplete
or stale, before operators discover it from the UI.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db import get_session  # noqa: E402
from app.models.eval import EvalWorkflowVersion  # noqa: E402
from app.models.integration import Ability, Executor, VendorModelCatalog  # noqa: E402
from app.services.eval_workflow_response import build_eval_workflow_response_metadata  # noqa: E402
from app.services.eval_workflow_routing_governance import resolve_eval_workflow_routing_governance  # noqa: E402


FAIL_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
PUBLIC_WORKFLOW_ROLES = {"production", "candidate"}
VENDOR_PROVIDERS = {"openai", "openai_compatible", "volcengine", "baidu", "kie"}


def _now_slug() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _field_names(schema: Any) -> list[str]:
    fields = _as_dict(schema).get("fields")
    names: list[str] = []
    for field in _as_list(fields):
        if isinstance(field, dict) and str(field.get("name") or "").strip():
            names.append(str(field["name"]).strip())
    return names


def _acceptance_passed(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    latest = metadata.get("latestAcceptance")
    records = metadata.get("acceptanceRecords")
    if not isinstance(latest, dict) and isinstance(records, list):
        latest = next((item for item in records if isinstance(item, dict)), None)
    return isinstance(latest, dict) and str(latest.get("status") or "").strip().lower() == "passed"


def _has_cost_policy(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    for key in ("unitPrice", "unit_price", "discountPrice", "discount_price", "listPrice", "list_price", "price"):
        raw = value.get(key)
        if raw in (None, ""):
            continue
        try:
            if float(raw) > 0:
                return True
        except (TypeError, ValueError):
            return False
    return False


def _tags(executor: Executor) -> set[str]:
    return {str(tag).strip().lower() for tag in executor.tags if str(tag).strip()}


def _issue(
    *,
    severity: str,
    area: str,
    code: str,
    object_id: str,
    title: str,
    detail: str,
    fix: str,
) -> dict[str, str]:
    return {
        "severity": severity,
        "area": area,
        "code": code,
        "objectId": object_id,
        "title": title,
        "detail": detail,
        "fix": fix,
    }


def _is_mock_executor(executor: Executor) -> bool:
    text = f"{executor.id} {executor.name} {executor.base_url or ''}".lower()
    return "mock" in text or "127.0.0.1:62359" in text or "history_success_no_images" in text


def _probe_comfyui_executor(executor: Executor, timeout_seconds: float) -> dict[str, Any]:
    base_url = str(executor.base_url or "").rstrip("/")
    if not base_url:
        return {"ok": False, "detail": "missing base_url"}
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 3.0))) as client:
            stats = client.get(f"{base_url}/system_stats")
            queue = client.get(f"{base_url}/queue")
        return {
            "ok": stats.status_code == 200 and queue.status_code == 200,
            "systemStatsStatus": stats.status_code,
            "queueStatus": queue.status_code,
            "detail": "",
        }
    except Exception as exc:
        return {"ok": False, "detail": repr(exc)}


def _audit_executors(
    executors: list[Executor],
    *,
    probe_comfyui: bool,
    probe_timeout_seconds: float,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    issues: list[dict[str, str]] = []
    probes: list[dict[str, Any]] = []
    for executor in executors:
        if _is_mock_executor(executor) and executor.status == "active":
            issues.append(
                _issue(
                    severity="P1",
                    area="executor",
                    code="ACTIVE_MOCK_EXECUTOR",
                    object_id=executor.id,
                    title="测试执行节点处于 active",
                    detail=f"{executor.name} 会进入生产候选池，存在误路由风险。",
                    fix="将测试节点置为 inactive，或删除该节点。",
                )
            )
        if executor.status == "active" and executor.type == "comfyui":
            if not executor.base_url:
                issues.append(
                    _issue(
                        severity="P1",
                        area="executor",
                        code="COMFYUI_EXECUTOR_MISSING_BASE_URL",
                        object_id=executor.id,
                        title="ComfyUI 执行节点缺少地址",
                        detail="active 节点没有 base_url，无法提交任务或探测队列。",
                        fix="补齐 base_url，或先将节点置为 inactive。",
                    )
                )
            executor_tags = _tags(executor)
            if "comfyui-general" not in executor_tags and "high-mem" not in executor_tags:
                issues.append(
                    _issue(
                        severity="P2",
                        area="executor",
                        code="COMFYUI_EXECUTOR_MISSING_ROUTE_TAG",
                        object_id=executor.id,
                        title="ComfyUI 执行节点缺少路由标签",
                        detail=f"当前 tags={sorted(executor_tags)}，调度规则无法准确识别普通/高内存能力。",
                        fix="为普通节点补 comfyui-general；高内存节点补 high-mem/upscale。",
                    )
                )
            if probe_comfyui:
                probe = {"executorId": executor.id, "name": executor.name}
                probe.update(_probe_comfyui_executor(executor, probe_timeout_seconds))
                probes.append(probe)
                if not probe.get("ok"):
                    issues.append(
                        _issue(
                            severity="P1",
                            area="executor",
                            code="COMFYUI_EXECUTOR_UNREACHABLE",
                            object_id=executor.id,
                            title="ComfyUI 执行节点不可达",
                            detail=str(probe.get("detail") or probe),
                            fix="先修复节点服务/网络；未恢复前置为 inactive，避免调度进来。",
                        )
                    )
    return issues, probes


def _audit_abilities(session: Session, executors: list[Executor]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    active_executors = {executor.id: executor for executor in executors if executor.status == "active"}
    general_comfyui_ids = {
        executor.id
        for executor in executors
        if executor.status == "active" and executor.type == "comfyui" and "comfyui-general" in _tags(executor)
    }
    active_abilities = session.execute(select(Ability).where(Ability.status == "active")).scalars().all()
    for ability in active_abilities:
        object_id = f"{ability.provider}.{ability.capability_key}"
        fields = _field_names(ability.input_schema)
        metadata = _as_dict(ability.extra_metadata)
        if not fields and ability.provider not in {"podi"}:
            issues.append(
                _issue(
                    severity="P2",
                    area="ability",
                    code="ABILITY_SCHEMA_EMPTY",
                    object_id=object_id,
                    title="能力缺少测试表单字段",
                    detail="input_schema.fields 为空，管理端/测评端无法稳定生成用例。",
                    fix="补齐 input_schema.fields，并写清中文字段名、英文说明、默认值和必填规则。",
                )
            )

        if ability.provider != "comfyui":
            continue

        allowed_ids = [str(item).strip() for item in _as_list(metadata.get("allowed_executor_ids")) if str(item).strip()]
        if not allowed_ids:
            issues.append(
                _issue(
                    severity="P1",
                    area="ability",
                    code="COMFYUI_ROUTE_NO_ALLOWED_EXECUTORS",
                    object_id=object_id,
                    title="ComfyUI 能力没有声明可用执行节点",
                    detail="allowed_executor_ids 为空，调度会退回历史默认逻辑，容易误路由。",
                    fix="在能力 metadata 中声明 allowed_executor_ids，并运行 ability seed 同步。",
                )
            )
            continue

        missing = [executor_id for executor_id in allowed_ids if executor_id not in active_executors]
        if missing:
            issues.append(
                _issue(
                    severity="P1",
                    area="ability",
                    code="COMFYUI_ROUTE_INACTIVE_EXECUTOR",
                    object_id=object_id,
                    title="ComfyUI 能力引用了不可用执行节点",
                    detail=f"不可用节点：{missing}",
                    fix="恢复节点并置为 active，或从 allowed_executor_ids 移除。",
                )
            )

        required_tags = {str(item).strip().lower() for item in _as_list(metadata.get("required_tags")) if str(item).strip()}
        if required_tags:
            bad_tags: list[str] = []
            for executor_id in allowed_ids:
                executor = active_executors.get(executor_id)
                if executor and not required_tags.issubset(_tags(executor)):
                    bad_tags.append(executor_id)
            if bad_tags:
                issues.append(
                    _issue(
                        severity="P1",
                        area="ability",
                        code="COMFYUI_ROUTE_TAG_MISMATCH",
                        object_id=object_id,
                        title="ComfyUI 能力要求的标签与执行节点不匹配",
                        detail=f"required_tags={sorted(required_tags)}；不匹配节点={bad_tags}",
                        fix="修正能力 required_tags 或执行节点 tags，确保标签约束能真正命中。",
                    )
                )

        is_dedicated_heavy = "high-mem" in required_tags or metadata.get("fallback_to_default") is False
        allowed_general_count = len(general_comfyui_ids.intersection(allowed_ids))
        if not is_dedicated_heavy and len(general_comfyui_ids) >= 2 and allowed_general_count < 2:
            issues.append(
                _issue(
                    severity="P1",
                    area="ability",
                    code="COMFYUI_ROUTE_SINGLE_NODE",
                    object_id=object_id,
                    title="普通 ComfyUI 能力只命中单台机器",
                    detail=(
                        f"当前普通节点={sorted(general_comfyui_ids)}；"
                        f"能力 allowed_executor_ids={allowed_ids}。这会导致任务集中到一台机器。"
                    ),
                    fix="把所有普通 ComfyUI 执行节点纳入 allowed_executor_ids，或明确标记为专用能力。",
                )
            )
    return issues


def _audit_eval_workflows(session: Session) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    workflows = session.execute(select(EvalWorkflowVersion).where(EvalWorkflowVersion.status == "active")).scalars().all()
    for workflow in workflows:
        response_meta = build_eval_workflow_response_metadata(workflow)
        governance = _as_dict(response_meta.get("governance"))
        role = str(governance.get("role") or "").strip().lower()
        object_id = f"{workflow.workflow_id}:{workflow.name}"
        param_fields = _field_names(workflow.parameters_schema)
        output_fields = _field_names(workflow.output_schema)
        if role in PUBLIC_WORKFLOW_ROLES and not param_fields:
            issues.append(
                _issue(
                    severity="P1",
                    area="eval_workflow",
                    code="EVAL_WORKFLOW_SCHEMA_EMPTY",
                    object_id=object_id,
                    title="公开测评工作流缺少入参 schema",
                    detail=f"role={role}，但 parameters_schema.fields 为空，无法生成稳定巡检参数。",
                    fix="补齐 parameters_schema.fields，至少包含图片地址和关键可调参数。",
                )
            )
        routing = resolve_eval_workflow_routing_governance(
            workflow_id=workflow.workflow_id,
            name=workflow.name,
            category=workflow.category,
            output_schema=workflow.output_schema,
        )
        if role == "production" and routing.get("trackingRequired") and not output_fields:
            issues.append(
                _issue(
                    severity="P2",
                    area="eval_workflow",
                    code="EVAL_WORKFLOW_OUTPUT_SCHEMA_EMPTY",
                    object_id=object_id,
                    title="生产工作流缺少出参 schema",
                    detail="output_schema.fields 为空，巡检无法明确判断 taskId、图片或结构化输出。",
                    fix="补齐 output_schema.fields，并明确 output/taskId/imageUrls/debugUrl 字段口径。",
                )
            )
    return issues


def _audit_vendor_models(session: Session) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    abilities = (
        session.execute(select(Ability).where(Ability.status == "active", Ability.provider.in_(VENDOR_PROVIDERS)))
        .scalars()
        .all()
    )
    model_ids = sorted({ability.vendor_model_id for ability in abilities if ability.vendor_model_id})
    models = (
        session.execute(select(VendorModelCatalog).where(VendorModelCatalog.id.in_(model_ids))).scalars().all()
        if model_ids
        else []
    )
    model_by_id = {model.id: model for model in models}
    for ability in abilities:
        object_id = f"{ability.provider}.{ability.capability_key}"
        if not ability.vendor_model_id:
            issues.append(
                _issue(
                    severity="P2",
                    area="vendor_model",
                    code="VENDOR_ABILITY_MODEL_UNBOUND",
                    object_id=object_id,
                    title="第三方能力未绑定模型目录",
                    detail="active 第三方能力没有 vendor_model_id，业务治理无法稳定拿到模型边界、计价和验收状态。",
                    fix="在能力目录中绑定模型弹药库条目，或先将能力置为 inactive。",
                )
            )
            continue
        model = model_by_id.get(ability.vendor_model_id)
        if not model:
            issues.append(
                _issue(
                    severity="P1",
                    area="vendor_model",
                    code="VENDOR_ABILITY_MODEL_NOT_FOUND",
                    object_id=object_id,
                    title="第三方能力绑定的模型目录不存在",
                    detail=f"vendor_model_id={ability.vendor_model_id} 不存在，业务版本无法做上线门禁。",
                    fix="修正能力 vendor_model_id，或恢复模型目录项。",
                )
            )
            continue
        model_object_id = f"{model.provider}.{model.model}"
        if model.status != "active":
            issues.append(
                _issue(
                    severity="P1",
                    area="vendor_model",
                    code="VENDOR_ABILITY_MODEL_INACTIVE",
                    object_id=model_object_id,
                    title="第三方能力绑定了未启用模型",
                    detail=f"能力 {object_id} 绑定模型状态为 {model.status}。",
                    fix="启用模型，或把能力切到已启用模型。",
                )
            )
        if not _acceptance_passed(model.extra_metadata):
            issues.append(
                _issue(
                    severity="P1",
                    area="vendor_model",
                    code="VENDOR_MODEL_ACCEPTANCE_MISSING",
                    object_id=model_object_id,
                    title="第三方模型缺少验收通过记录",
                    detail=f"能力 {object_id} 正在引用该模型，但模型弹药库没有 passed 验收记录。",
                    fix="在管理端模型弹药库完成能力测试/测评端实跑，并记录模型验收通过。",
                )
            )
        if not _has_cost_policy(model.cost_policy):
            issues.append(
                _issue(
                    severity="P2",
                    area="vendor_model",
                    code="VENDOR_MODEL_COST_POLICY_MISSING",
                    object_id=model_object_id,
                    title="第三方模型缺少计价策略",
                    detail=f"能力 {object_id} 正在引用该模型，但成本口径为空。",
                    fix="补齐 costPolicy.unitPrice、billingUnit、currency 和定价版本。",
                )
            )
        if not model.api_types:
            issues.append(
                _issue(
                    severity="P2",
                    area="vendor_model",
                    code="VENDOR_MODEL_API_TYPES_MISSING",
                    object_id=model_object_id,
                    title="第三方模型缺少能力类型",
                    detail="用户无法判断该模型用于图片、视频、文字还是图像理解。",
                    fix="补齐 apiTypes，例如 image_generation、image_edit、vision、video_generation。",
                )
            )
    return issues


def build_audit_report(
    session: Session,
    *,
    probe_comfyui: bool = False,
    probe_timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    executors = session.execute(select(Executor)).scalars().all()
    executor_issues, probes = _audit_executors(
        executors,
        probe_comfyui=probe_comfyui,
        probe_timeout_seconds=probe_timeout_seconds,
    )
    ability_issues = _audit_abilities(session, executors)
    workflow_issues = _audit_eval_workflows(session)
    vendor_model_issues = _audit_vendor_models(session)
    issues = executor_issues + ability_issues + workflow_issues + vendor_model_issues
    severity_counts = Counter(issue["severity"] for issue in issues)
    area_counts = Counter(issue["area"] for issue in issues)
    code_counts = Counter(issue["code"] for issue in issues)
    return {
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "status": "pass" if not issues else "fail",
            "issueCount": len(issues),
            "severityCounts": dict(severity_counts),
            "areaCounts": dict(area_counts),
            "codeCounts": dict(code_counts),
        },
        "probes": probes,
        "issues": issues,
    }


def _print_text(report: dict[str, Any]) -> None:
    summary = _as_dict(report.get("summary"))
    print(
        "能力测试覆盖审计："
        f"status={summary.get('status')}；"
        f"issues={summary.get('issueCount')}；"
        f"severity={summary.get('severityCounts')}"
    )
    if report.get("probes"):
        print("ComfyUI 节点探测：")
        for probe in report["probes"]:
            print(f"- {probe.get('executorId')} | ok={probe.get('ok')} | {probe.get('detail') or probe}")
    for issue in report.get("issues", []):
        print(
            f"- [{issue['severity']}] {issue['code']} | {issue['area']} | "
            f"{issue['objectId']} | {issue['title']} | {issue['fix']}"
        )


def _should_fail(report: dict[str, Any], fail_on: str) -> bool:
    threshold = FAIL_RANK.get(fail_on, 1)
    for issue in report.get("issues", []):
        if FAIL_RANK.get(str(issue.get("severity") or "P3"), 3) <= threshold:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ability/workflow release test coverage.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--report", default="", help="Optional report JSON path.")
    parser.add_argument("--probe-comfyui", action="store_true", help="Call /system_stats and /queue for active ComfyUI nodes.")
    parser.add_argument("--probe-timeout", type=float, default=5.0, help="ComfyUI probe timeout seconds.")
    parser.add_argument("--fail-on", choices=sorted(FAIL_RANK), default="P1", help="Exit non-zero at or above severity.")
    args = parser.parse_args()

    with get_session() as session:
        report = build_audit_report(
            session,
            probe_comfyui=args.probe_comfyui,
            probe_timeout_seconds=args.probe_timeout,
        )

    report_path = Path(args.report) if args.report else Path("reports") / f"ability_test_coverage_audit_{_now_slug()}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["reportPath"] = str(report_path)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text(report)
        print(f"报告：{report_path}")

    return 2 if _should_fail(report, args.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
