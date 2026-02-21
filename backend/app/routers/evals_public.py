"""Public evaluation APIs (no login) for internal testers.

This router is intended for internal usage on a trusted network. You can:
- enable it with `EVAL_PUBLIC_ENABLED=true`
- optionally protect it with `EVAL_PUBLIC_TOKEN`
"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, File
from sqlalchemy import case, exists, func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.eval import EvalAnnotation, EvalRun, EvalWorkflowVersion
from app.models.integration import AbilityTask
from app.schemas.eval import (
    EvalAnnotationCreate,
    EvalAnnotationResponse,
    EvalRunWithLatestAnnotationListResponse,
    EvalRunWithLatestAnnotationResponse,
    EvalRunCreate,
    EvalRunListResponse,
    EvalRunResponse,
    EvalWorkflowVersionResponse,
)
from app.services.eval_seed import FISSION_WORKFLOW_IDS, ensure_default_eval_workflow_versions
from app.services.eval_service import get_eval_service
from app.services.oss import oss_service


router = APIRouter(prefix="/api/evals", tags=["evals-public"])


def _require_public_enabled(request: Request) -> None:
    settings = get_settings()
    if not settings.eval_public_enabled:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if settings.eval_public_token:
        token = request.headers.get("X-Eval-Token") or request.query_params.get("token")
        if token != settings.eval_public_token:
            raise HTTPException(status_code=401, detail="UNAUTHORIZED")


def _require_eval_admin(request: Request) -> None:
    settings = get_settings()
    token = request.headers.get("X-Eval-Admin-Token") or request.query_params.get("admin_token")
    if not settings.eval_admin_token or token != settings.eval_admin_token:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")


def _get_or_set_rater_id(request: Request, response: Response) -> str:
    rid = request.cookies.get("podi_eval_rater")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    rid = uuid4().hex
    response.set_cookie(
        "podi_eval_rater",
        rid,
        max_age=3600 * 24 * 365,
        httponly=False,
        samesite="lax",
    )
    return rid


def _batch_session_expr():
    return func.json_unquote(func.json_extract(EvalRun.parameters_json, "$.__batch_session_id"))


def _batch_mode_expr():
    return func.json_unquote(func.json_extract(EvalRun.parameters_json, "$.__eval_batch_mode"))


@router.get("/me")
def get_me(request: Request, response: Response) -> dict[str, Any]:
    _require_public_enabled(request)
    rid = _get_or_set_rater_id(request, response)
    return {"raterId": rid}


@router.get("/workflow-versions", response_model=list[EvalWorkflowVersionResponse])
def list_workflow_versions(
    request: Request,
    response: Response,
    category: str | None = Query(None),
    status: str | None = Query("active"),
    db: Session = Depends(get_db),
) -> list[EvalWorkflowVersion]:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    ensure_default_eval_workflow_versions(db)
    stmt = select(EvalWorkflowVersion)
    if category:
        stmt = stmt.where(EvalWorkflowVersion.category == category)
    if status:
        stmt = stmt.where(EvalWorkflowVersion.status == status)
    return db.execute(stmt.order_by(EvalWorkflowVersion.category.asc(), EvalWorkflowVersion.created_at.desc())).scalars().all()


@router.get("/docs/workflows")
def get_workflow_docs(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Developer doc: how to call Coze workflows + full IO schema list (active)."""
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    ensure_default_eval_workflow_versions(db)

    rows = (
        db.execute(
            select(EvalWorkflowVersion)
            .where(EvalWorkflowVersion.status == "active")
            .order_by(EvalWorkflowVersion.category.asc(), EvalWorkflowVersion.name.asc())
        )
        .scalars()
        .all()
    )

    def _md_escape(text: str) -> str:
        return (text or "").replace("|", "\\|").replace("\n", " ").strip()

    def _infer_output_kind(wf: EvalWorkflowVersion) -> str:
        schema = wf.output_schema or {}
        fields = schema.get("fields") if isinstance(schema, dict) else None
        if isinstance(fields, list):
            for f in fields:
                if isinstance(f, dict) and f.get("name") == "output":
                    desc = str(f.get("description") or "")
                    if "task" in desc.lower() or "回调" in desc:
                        return "callback_task_id"
        return "image_url"

    def _coerce_schema(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            return {"fields": value}
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"fields": parsed}
        return {}

    def _normalize_options(options: Any) -> list[dict[str, str]]:
        if isinstance(options, str):
            raw = options.strip()
            if not raw:
                return []
            # Allow comma-separated strings as a fallback.
            return [{"label": item.strip(), "value": item.strip()} for item in raw.split(",") if item.strip()]
        if not isinstance(options, list):
            return []
        normalized: list[dict[str, str]] = []
        for opt in options:
            if isinstance(opt, dict):
                label = opt.get("label")
                value = opt.get("value")
                if value is None:
                    value = label
                if label is None:
                    label = value
                if value is None and label is None:
                    continue
                normalized.append({"label": str(label or ""), "value": str(value or "")})
            else:
                normalized.append({"label": str(opt), "value": str(opt)})
        return [x for x in normalized if x.get("label") or x.get("value")]

    def _normalize_fields(schema: Any) -> list[dict[str, Any]]:
        schema = _coerce_schema(schema)
        fields = schema.get("fields") if isinstance(schema, dict) else None
        if not isinstance(fields, list):
            return []
        normalized: list[dict[str, Any]] = []
        for f in fields:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            normalized.append(
                {
                    "name": str(f.get("name") or "").strip(),
                    "label": str(f.get("label") or "").strip() or None,
                    "type": str(f.get("type") or "text").strip(),
                    "required": bool(f.get("required")),
                    "defaultValue": f.get("defaultValue") if f.get("defaultValue") is not None else "",
                    "description": str(f.get("description") or "").strip(),
                    "options": _normalize_options(f.get("options")),
                }
            )
        return normalized

    def _filter_doc_fields(wf: EvalWorkflowVersion, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
        is_fission = wf.category == "图裂变" or str(wf.workflow_id) in FISSION_WORKFLOW_IDS
        if is_fission:
            internal_keys = {"count", "generateCount", "variantCount", "n"}
            return [f for f in fields if str(f.get("name") or "") not in internal_keys]
        return fields

    def _example_parameters(fields: list[dict[str, Any]]) -> dict[str, str]:
        example: dict[str, str] = {}
        for f in fields:
            name = str(f.get("name") or "")
            if not name:
                continue
            example[name] = "<required>" if f.get("required") else "<optional>"
        return example

    def _render_schema_table(fields: list[dict[str, Any]], *, empty_hint: str) -> list[str]:
        if not fields:
            return [empty_hint, ""]
        lines: list[str] = []
        lines.append("| 字段 | 必填 | 类型 | 默认值 | 可选项 | 描述 |")
        lines.append("|---|---:|---|---|---|---|")
        for f in fields:
            name = str(f.get("name") or "")
            required = "Y" if f.get("required") else ""
            ftype = str(f.get("type") or "text")
            default = str(f.get("defaultValue") or "")
            opts = ""
            options = f.get("options")
            if isinstance(options, list) and options:
                rendered = []
                for o in options:
                    if isinstance(o, dict):
                        rendered.append(str(o.get("value") or o.get("label") or ""))
                    else:
                        rendered.append(str(o))
                opts = " / ".join([x for x in rendered if x])
            desc = str(f.get("description") or "")
            lines.append(
                f"| `{_md_escape(name)}` | {required} | `{_md_escape(ftype)}` | `{_md_escape(default)}` | {_md_escape(opts)} | {_md_escape(desc)} |"
            )
        lines.append("")
        return lines

    def _workflow_error_hints(output_kind: str) -> list[str]:
        hints = [
            "`INTERNAL_ONLY`：非内网访问或缺少 SERVICE_API_TOKEN。",
            "`COZE_FAILED` / `COZE_EXECUTION_FAILED`：Coze 返回 code!=0 或执行失败。",
            "`COZE_RUN_*`：Coze run_status=failed/canceled/timeout 等。",
            "`COZE_ASYNC_TIMEOUT` / `COZE_ASYNC_EMPTY`：异步轮询超时/无响应。",
            "`COZE_WORKFLOW_ERROR`：工作流 output 内含错误字段。",
            "`COZE_SUBMIT_FAILED` / `COZE_SUBMIT_MISSING_EXECUTE_ID`：提交失败或缺少 execute_id。",
            "`COZE_HISTORY_FAILED`：Coze history 查询失败。",
            "`WORKFLOW_VERSION_NOT_FOUND`：评测平台未找到对应 workflow 版本。",
            "`FANOUT_EMPTY` / `FANOUT_PARTIAL_FAILED`：批量子任务全部失败或部分失败。",
        ]
        if output_kind == "callback_task_id":
            hints.extend(
                [
                    "`TASK_ID_REQUIRED`：缺少 taskId。",
                    "`TASK_NOT_FOUND`：任务不存在或已过期。",
                    "`TASK_FAILED`：任务执行失败。",
                    "`TASK_TIMEOUT`：任务超时。",
                    "`TASK_IMAGES_EMPTY`：任务结果无图片。",
                    "`CALLBACK_OUTPUT_EMPTY`：回调 task id 为空。",
                    "`CALLBACK_IMAGES_EMPTY`：回调解析不到图片。",
                    "`CALLBACK_TASK_NOT_RESOLVED`：task id 无法解析/失效。",
                    "`COMFYUI_*`：ComfyUI 相关错误（如 `COMFYUI_SUBMIT_ERROR`、`COMFYUI_HISTORY_INVALID`）。",
                    "`ERR|Q1001|...` / `ERR|Q2001|...`：并发/队列超限。",
                ]
            )
        return hints

    def _strip_backticks(values: list[str]) -> list[str]:
        return [value.replace("`", "") for value in values]

    lines: list[str] = []
    lines.append("# PODI 评测平台 · Coze 工作流调用文档")
    lines.append("")
    lines.append("用于开发人员直接通过 Coze OpenAPI 调用工作流，确认入参/出参与 workflow_id。")
    lines.append("")
    lines.append("## 调用方式")
    lines.append("")
    lines.append("环境变量：")
    lines.append("- `COZE_BASE_URL`：例如 `https://api.coze.cn`（以实际为准）")
    lines.append("- `COZE_API_TOKEN`：Coze 平台生成的 token")
    lines.append("")
    lines.append("网络/鉴权注意：")
    lines.append("- PODI 的 Coze 插件接口默认仅允许内网访问（返回 `401 {\"detail\":\"INTERNAL_ONLY\"}`）。")
    lines.append("- 若 Coze 与 PODI 不在同一内网：在 PODI 后端配置 `COZE_TRUSTED_IPS=<coze_source_ip,...>` 放行 Coze 源 IP。")
    lines.append("- 也可在请求头携带 `Authorization: Bearer $SERVICE_API_TOKEN`（若后端已配置该 token）。")
    lines.append("")
    lines.append("示例：")
    lines.append("```bash")
    lines.append("curl -X POST \"$COZE_BASE_URL/v1/workflow/run\" \\")
    lines.append("  -H \"Authorization: Bearer $COZE_API_TOKEN\" \\")
    lines.append("  -H \"Content-Type: application/json\" \\")
    lines.append("  -d '{\"workflow_id\":\"<WORKFLOW_ID>\",\"parameters\":{}}'")
    lines.append("```")
    lines.append("")
    lines.append("## ComfyUI 回调（重要）")
    lines.append("")
    lines.append("部分工作流的 `output` 返回的是回调 task id（例如 ComfyUI 类工作流）。评测平台会：")
    lines.append("1) 先运行 Coze 工作流拿到 `data.output`（task id）")
    lines.append("2) 再轮询 task 结果，拿到最终图片 URL 列表并展示")
    lines.append("")
    lines.append("回调工作流（通用类）：")
    lines.append("- `ComfyUI 回调 · comfyui_huidiao` 输入 `taskid`，输出 `images` 数组。")
    lines.append("")
    lines.append("task id 兼容格式：")
    lines.append("- 旧格式：`<raw_id>`（数据库/历史返回）")
    lines.append("- 新格式：`t1.<provider>.<executorId>.<raw_id>`（可解析，便于路由与排障）")
    lines.append("")
    lines.append("如需在 Coze 侧自行解析回调图片：")
    lines.append("- 推荐：调用 PODI `/api/coze/podi/tasks/get`（入参 `taskId`）直接获取 `images`。")
    lines.append("- 备选：配置 `COZE_COMFYUI_CALLBACK_WORKFLOW_ID`，由一个专门的回调工作流负责将 task id 解析为 images。")
    lines.append("")
    lines.append("## debug_url 是什么？")
    lines.append("")
    lines.append("当 Coze 执行失败或需要排查时，后端会透出 `debug_url`，可在 Coze Studio/Loop 中打开对应 run 的节点级日志。")
    lines.append("")
    lines.append("## 注意事项（统一规则）")
    lines.append("")
    lines.append("- 图片类参数统一使用 URL（纯字符串），像素类参数仅传数字（不要带 `px`）。")
    lines.append("- 回调类工作流的 `output` 为 task id，需轮询 `/api/coze/podi/tasks/get` 获取最终图片。")
    lines.append("- ComfyUI 类工作流会额外返回 `ip`（执行节点），用于排障与路由判断。")
    lines.append("- ComfyUI 队列汇总工具无需入参，直接返回各节点队列状态。")
    lines.append("")
    lines.append("## 常见错误速查（报错编号体系）")
    lines.append("")
    lines.append("### 错误码格式")
    lines.append("- `ERR|<CODE>|<message>`：用于队列/并发等强约束错误（回调 id 字段会直接返回该值）。")
    lines.append("- 其余错误多为**错误关键字**（如 `TASK_NOT_FOUND`），在 error_message 或 debugResponse 中出现。")
    lines.append("")
    lines.append("### 错误码一览（完整）")
    lines.append("| 编号 | 含义 | 典型场景 |")
    lines.append("|---|---|---|")
    lines.append("| Q1001 | ComfyUI 队列已满（单机 >= 10） | ComfyUI 并发超限 |")
    lines.append("| Q2001 | 商业模型队列已满（单机 >= 10） | 商业模型并发超限 |")
    lines.append("| INTERNAL_ONLY | 仅内网可访问 | IP 未放行 |")
    lines.append("| WORKFLOW_ID_MISSING | 缺少 workflow_id | 请求体缺字段 |")
    lines.append("| WORKFLOW_VERSION_NOT_FOUND | workflow 版本不存在 | workflow_id 不在评测库 |")
    lines.append("| FANOUT_EMPTY | 批量子任务全部失败 | fanout 模式 |")
    lines.append("| FANOUT_PARTIAL_FAILED | 批量部分失败 | fanout 模式 |")
    lines.append("| COZE_SUBMIT_FAILED | 提交 Coze 失败 | /v1/workflow/run 返回错误 |")
    lines.append("| COZE_SUBMIT_MISSING_EXECUTE_ID | 缺少 execute_id | Coze 返回体异常 |")
    lines.append("| COZE_HISTORY_FAILED | Coze history 失败 | /v1/workflow/history 异常 |")
    lines.append("| COZE_EXECUTION_FAILED | Coze 执行失败 | run_status=failed |")
    lines.append("| COZE_FAILED | Coze 执行失败 | code!=0 |")
    lines.append("| COZE_RUN_* | Coze 状态异常 | run_status=failed/canceled/timeout |")
    lines.append("| COZE_ASYNC_EMPTY | Coze 异步空响应 | async poll 返回空 |")
    lines.append("| COZE_ASYNC_TIMEOUT | Coze 轮询超时 | async 超时 |")
    lines.append("| COZE_WORKFLOW_ERROR | workflow error | output 内 error 字段 |")
    lines.append("| TASK_ID_REQUIRED | 缺少 taskId | /api/coze/podi/tasks/get |")
    lines.append("| TASK_NOT_FOUND | 任务不存在 | taskId 错误或被清理 |")
    lines.append("| TASK_FAILED | 任务执行失败 | 上游执行失败 |")
    lines.append("| TASK_TIMEOUT | 任务超时 | 超过轮询期限 |")
    lines.append("| TASK_IMAGES_EMPTY | 任务无图片 | task 结果无 images |")
    lines.append("| CALLBACK_OUTPUT_EMPTY | 回调 task id 为空 | 工作流未返回 output |")
    lines.append("| CALLBACK_IMAGES_EMPTY | 回调解析不到图片 | 回调未产出 images |")
    lines.append("| CALLBACK_TASK_NOT_RESOLVED | task id 无法解析/失效 | 回调任务无法完成 |")
    lines.append("| COMFYUI_QUEUE_STATUS_ERROR | ComfyUI 队列查询失败 | /queue/status 异常 |")
    lines.append("| COMFYUI_QUEUE_STATUS_INVALID | ComfyUI 队列响应异常 | queue JSON 不合法 |")
    lines.append("| COMFYUI_SUBMIT_ERROR | 提交 ComfyUI 失败 | /prompt 失败 |")
    lines.append("| COMFYUI_SUBMIT_NODE_ERROR | ComfyUI 节点错误 | 节点报错/缺模型 |")
    lines.append("| COMFYUI_HISTORY_HTTP_* | ComfyUI history 非 200 | /history/<id> 失败 |")
    lines.append("| COMFYUI_HISTORY_INVALID | ComfyUI history JSON 异常 | history 解析失败 |")
    lines.append("| COMFYUI_STATUS_* | ComfyUI 状态异常 | status=error/unknown |")
    lines.append("| COMFYUI_IMAGES_EMPTY | ComfyUI 无输出图 | history 没有 images |")
    lines.append("| COMFYUI_ASSETS_EMPTY | OSS 入库为空 | 图片落盘失败 |")
    lines.append("| COMFYUI_TIMEOUT | ComfyUI 轮询超时 | /history 超时 |")
    lines.append("| COMFYUI_WORKFLOW_EMPTY | ComfyUI workflow 为空 | 工作流配置缺失 |")
    lines.append("| COMFYUI_BASE_URL_MISSING | 缺少 ComfyUI Base URL | 执行节点未配置 |")
    lines.append("| COMFYUI_IMAGE_REQUIRED | 缺少图片 | 需要图片输入 |")
    lines.append("")
    lines.append("### 补充说明")
    lines.append("- `Q1001/Q2001` 触发时，**回调 id 字段会返回 `ERR|Qxxxx|...`**，便于业务侧统一处理。")
    lines.append("- 其余错误关键字由后端直接透传，评测平台可直接显示在失败详情。")
    lines.append("")
    lines.append("## 功能列表（active）")
    lines.append("")
    lines.append("| 分类 | 功能 | workflow_id | 输出类型 | 备注 |")
    lines.append("|---|---|---:|---|---|")
    workflows: list[dict[str, Any]] = []
    grouped: dict[str, list[EvalWorkflowVersion]] = {}

    for wf in rows:
        parameters = _filter_doc_fields(wf, _normalize_fields(wf.parameters_schema or {}))
        outputs = _normalize_fields(wf.output_schema or {})
        output_kind = _infer_output_kind(wf)
        workflows.append(
            {
                "category": wf.category,
                "name": wf.name,
                "workflow_id": wf.workflow_id,
                "notes": wf.notes,
                "output_kind": output_kind,
                "parameters": parameters,
                "outputs": outputs,
                "errors": _strip_backticks(_workflow_error_hints(output_kind)),
                "request": {
                    "method": "POST",
                    "path": "/v1/workflow/run",
                    "body": {"workflow_id": wf.workflow_id, "parameters": _example_parameters(parameters)},
                },
            }
        )
        grouped.setdefault(wf.category, []).append(wf)
        lines.append(
            f"| {_md_escape(wf.category)} | {_md_escape(wf.name)} | `{_md_escape(wf.workflow_id)}` | `{output_kind}` | {_md_escape(wf.notes or '')} |"
        )
    lines.append("")

    lines.append("## 目录")
    lines.append("")
    for category, items in grouped.items():
        lines.append(f"- {category}（{len(items)}）")
    lines.append("")

    lines.append("## 分类明细")
    lines.append("")

    for category, items in grouped.items():
        lines.append(f"## {category}")
        lines.append("")
        for wf in items:
            lines.append(f"### {wf.name}")
            lines.append("")
            lines.append(f"- workflow_id：`{wf.workflow_id}`")
            lines.append(f"- 输出类型：`{_infer_output_kind(wf)}`（主字段为 `output`，额外字段见出参说明）")
            if wf.notes:
                lines.append(f"- 备注：{wf.notes}")
            lines.append("")
            lines.append("#### 调用方法")
            lines.append("")
            lines.append("```json")
            example_params = _example_parameters(
                _filter_doc_fields(wf, _normalize_fields(wf.parameters_schema or {}))
            )
            lines.append(
                json.dumps(
                    {"workflow_id": wf.workflow_id, "parameters": example_params},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            lines.append("```")
            lines.append("")
            lines.append("#### 入参 parameters")
            lines.append("")
            fields = _filter_doc_fields(wf, _normalize_fields(wf.parameters_schema or {}))
            lines.extend(_render_schema_table(fields, empty_hint="_无 schema（请在后台补齐 parameters_schema 以生成动态表单）。_"))
            if wf.category == "图裂变" or str(wf.workflow_id) in FISSION_WORKFLOW_IDS:
                lines.append(
                    "> 说明：`count` 为评测平台内部“裂变数量”控制参数，不属于 Coze workflow 入参，调用 Coze OpenAPI 请勿传递。"
                )
                lines.append("")

            lines.append("#### 出参 data")
            lines.append("")
            output_fields = _normalize_fields(wf.output_schema or {})
            lines.extend(_render_schema_table(output_fields, empty_hint="_无 schema（请在后台补齐 output_schema 以生成文档）。_"))
            lines.append("> Coze 返回结构中 `data` 可能是 JSON 字符串或对象。建议直接查看 `data` 的字段（以上表格）。")
            lines.append("")

            lines.append("#### 错误码")
            lines.append("")
            lines.append("可能出现以下错误（详见本文档「错误码一览」）：")
            for hint in _workflow_error_hints(_infer_output_kind(wf)):
                lines.append(f"- {hint}")
            lines.append("")

    return {
        "markdown": "\n".join(lines),
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "workflows": workflows,
    }


@router.post("/uploads")
async def upload_image(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Upload an image to OSS and return its public URL."""
    _require_public_enabled(request)
    user_id = _get_or_set_rater_id(request, response)
    data = await file.read()
    uploaded = oss_service.upload_bytes(user_id=user_id, filename=file.filename or "upload.png", data=data, content_type=file.content_type)
    return {"url": uploaded.get("url"), "objectKey": uploaded.get("objectKey")}


@router.get("/admin/workflow-versions", response_model=list[EvalWorkflowVersionResponse])
def admin_list_workflow_versions(
    request: Request,
    category: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[EvalWorkflowVersion]:
    _require_eval_admin(request)
    ensure_default_eval_workflow_versions(db)
    stmt = select(EvalWorkflowVersion)
    if category:
        stmt = stmt.where(EvalWorkflowVersion.category == category)
    return db.execute(stmt.order_by(EvalWorkflowVersion.category.asc(), EvalWorkflowVersion.created_at.desc())).scalars().all()


@router.put("/admin/workflow-versions/{workflow_version_id}", response_model=EvalWorkflowVersionResponse)
def admin_update_workflow_version(
    workflow_version_id: str,
    request: Request,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> EvalWorkflowVersion:
    _require_eval_admin(request)
    row = db.get(EvalWorkflowVersion, workflow_version_id)
    if not row:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    for key in ("name", "notes", "category", "status", "version"):
        if key in body and isinstance(body[key], str):
            setattr(row, key, body[key].strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/runs", response_model=EvalRunResponse)
def create_run(
    request: Request,
    response: Response,
    payload: EvalRunCreate,
    db: Session = Depends(get_db),
) -> EvalRun:
    _require_public_enabled(request)
    created_by = _get_or_set_rater_id(request, response)
    run = get_eval_service().create_eval_run(
        workflow_version_id=payload.workflow_version_id,
        dataset_item_id=payload.dataset_item_id,
        input_oss_urls=payload.input_oss_urls_json,
        parameters=payload.parameters_json,
        created_by=created_by,
        db=db,
    )
    return run


@router.get("/runs", response_model=EvalRunListResponse)
def list_runs(
    request: Request,
    response: Response,
    workflow_version_id: str | None = Query(None),
    batch_session_id: str | None = Query(None),
    batch_mode: bool | None = Query(None),
    mine_only: bool = Query(False),
    status: str | None = Query(None),
    unrated: bool | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> EvalRunListResponse:
    _require_public_enabled(request)
    rater_id = _get_or_set_rater_id(request, response)

    stmt = select(EvalRun)
    count_stmt = select(func.count()).select_from(EvalRun)
    if workflow_version_id:
        stmt = stmt.where(EvalRun.workflow_version_id == workflow_version_id)
        count_stmt = count_stmt.where(EvalRun.workflow_version_id == workflow_version_id)
    if mine_only:
        stmt = stmt.where(EvalRun.created_by == rater_id)
        count_stmt = count_stmt.where(EvalRun.created_by == rater_id)
    if batch_mode is True:
        batch_mode_expr = _batch_mode_expr()
        stmt = stmt.where(batch_mode_expr.in_(["1", "true", "True"]))
        count_stmt = count_stmt.where(batch_mode_expr.in_(["1", "true", "True"]))
    if batch_session_id:
        batch_expr = _batch_session_expr()
        stmt = stmt.where(batch_expr == batch_session_id.strip())
        count_stmt = count_stmt.where(batch_expr == batch_session_id.strip())
    if status:
        stmt = stmt.where(EvalRun.status == status)
        count_stmt = count_stmt.where(EvalRun.status == status)
    if unrated:
        subq = select(EvalAnnotation.id).where(EvalAnnotation.run_id == EvalRun.id)
        stmt = stmt.where(~exists(subq))
        count_stmt = count_stmt.where(~exists(subq))

    total = int(db.execute(count_stmt).scalar_one())
    items = db.execute(stmt.order_by(EvalRun.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    return EvalRunListResponse(total=total, items=items)


@router.get("/runs/batches")
def list_run_batches(
    request: Request,
    response: Response,
    workflow_version_id: str | None = Query(None),
    mine_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List LoRA batch sessions grouped by `__batch_session_id`."""
    _require_public_enabled(request)
    rater_id = _get_or_set_rater_id(request, response)
    batch_expr = _batch_session_expr()
    completed_expr = case((EvalRun.status.in_(["succeeded", "failed"]), 1), else_=0)
    queued_expr = case((EvalRun.status == "queued", 1), else_=0)
    running_expr = case((EvalRun.status == "running", 1), else_=0)
    succeeded_expr = case((EvalRun.status == "succeeded", 1), else_=0)
    failed_expr = case((EvalRun.status == "failed", 1), else_=0)

    base_stmt = (
        select(
            batch_expr.label("batch_id"),
            func.min(EvalRun.workflow_version_id).label("workflow_version_id"),
            func.min(EvalWorkflowVersion.name).label("workflow_name"),
            func.count(EvalRun.id).label("total"),
            func.sum(completed_expr).label("completed"),
            func.sum(queued_expr).label("queued"),
            func.sum(running_expr).label("running"),
            func.sum(succeeded_expr).label("succeeded"),
            func.sum(failed_expr).label("failed"),
            func.max(EvalRun.created_at).label("latest_created_at"),
            func.max(EvalRun.updated_at).label("latest_updated_at"),
        )
        .select_from(EvalRun)
        .join(EvalWorkflowVersion, EvalWorkflowVersion.id == EvalRun.workflow_version_id, isouter=True)
        .where(batch_expr.is_not(None), batch_expr != "")
        .group_by(batch_expr)
    )
    if workflow_version_id:
        base_stmt = base_stmt.where(EvalRun.workflow_version_id == workflow_version_id)
    if mine_only:
        base_stmt = base_stmt.where(EvalRun.created_by == rater_id)
    total = int(db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar_one())
    rows = db.execute(base_stmt.order_by(func.max(EvalRun.created_at).desc()).offset(offset).limit(limit)).all()
    items: list[dict[str, Any]] = []
    for row in rows:
        latest_created = row.latest_created_at.isoformat() if row.latest_created_at else None
        latest_updated = row.latest_updated_at.isoformat() if row.latest_updated_at else None
        items.append(
            {
                "batchId": str(row.batch_id or ""),
                "workflowVersionId": str(row.workflow_version_id or "") if row.workflow_version_id else None,
                "workflowName": str(row.workflow_name or "") if row.workflow_name else None,
                "total": int(row.total or 0),
                "completed": int(row.completed or 0),
                "queued": int(row.queued or 0),
                "running": int(row.running or 0),
                "succeeded": int(row.succeeded or 0),
                "failed": int(row.failed or 0),
                "latestCreatedAt": latest_created,
                "latestUpdatedAt": latest_updated,
            }
        )
    return {"total": total, "items": items}


@router.post("/runs/batches/{batch_id}/stop")
def stop_run_batch(
    batch_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Stop queued/running runs in a batch and mark them failed."""
    _require_public_enabled(request)
    rater_id = _get_or_set_rater_id(request, response)
    batch_key = str(batch_id or "").strip()
    if not batch_key:
        raise HTTPException(status_code=400, detail="BATCH_ID_REQUIRED")

    batch_expr = _batch_session_expr()
    rows = db.execute(
        select(EvalRun.id, EvalRun.podi_task_id)
        .where(batch_expr == batch_key)
        .where(EvalRun.created_by == rater_id)
        .where(EvalRun.status.in_(["queued", "running"]))
    ).all()
    if not rows:
        return {"batchId": batch_key, "stoppedRuns": 0, "stoppedTasks": 0}

    run_ids = [str(row.id) for row in rows]
    task_ids = [
        str(row.podi_task_id)
        for row in rows
        if isinstance(row.podi_task_id, str) and row.podi_task_id.strip()
    ]
    now = datetime.utcnow()
    stopped_tasks = 0
    if task_ids:
        stopped_tasks = (
            db.execute(
                update(AbilityTask)
                .where(AbilityTask.id.in_(task_ids))
                .where(AbilityTask.status.in_(["queued", "running"]))
                .values(
                    status="failed",
                    error_message="MANUAL_STOP_BY_OPERATOR",
                    finished_at=now,
                    updated_at=now,
                )
            ).rowcount
            or 0
        )
    stopped_runs = (
        db.execute(
            update(EvalRun)
            .where(EvalRun.id.in_(run_ids))
            .where(EvalRun.status.in_(["queued", "running"]))
            .values(
                status="failed",
                error_message="MANUAL_STOP_BY_OPERATOR",
                updated_at=now,
            )
        ).rowcount
        or 0
    )
    db.commit()
    return {
        "batchId": batch_key,
        "stoppedRuns": int(stopped_runs),
        "stoppedTasks": int(stopped_tasks),
    }

@router.get("/runs/with-latest-annotation", response_model=EvalRunWithLatestAnnotationListResponse)
def list_runs_with_latest_annotation(
    request: Request,
    response: Response,
    workflow_version_id: str | None = Query(None),
    status: str | None = Query(None),
    unrated: bool | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> Any:
    """List runs and attach each run's latest annotation.

    This endpoint is optimized for the evaluation UI: filtering by rating/comment is easier
    when annotation info is present on each row.
    """
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)

    stmt = select(EvalRun)
    count_stmt = select(func.count()).select_from(EvalRun)
    if workflow_version_id:
        stmt = stmt.where(EvalRun.workflow_version_id == workflow_version_id)
        count_stmt = count_stmt.where(EvalRun.workflow_version_id == workflow_version_id)
    if status:
        stmt = stmt.where(EvalRun.status == status)
        count_stmt = count_stmt.where(EvalRun.status == status)
    if unrated:
        subq = select(EvalAnnotation.id).where(EvalAnnotation.run_id == EvalRun.id)
        stmt = stmt.where(~exists(subq))
        count_stmt = count_stmt.where(~exists(subq))

    total = int(db.execute(count_stmt).scalar_one())
    runs = db.execute(stmt.order_by(EvalRun.created_at.desc()).offset(offset).limit(limit)).scalars().all()

    run_ids = [r.id for r in runs]
    latest_map: dict[str, EvalAnnotation] = {}
    if run_ids:
        ann_rows = (
            db.execute(
                select(EvalAnnotation)
                .where(EvalAnnotation.run_id.in_(run_ids))
                .order_by(EvalAnnotation.run_id.asc(), EvalAnnotation.created_at.desc())
            )
            .scalars()
            .all()
        )
        for ann in ann_rows:
            if ann.run_id not in latest_map:
                latest_map[ann.run_id] = ann

    items: list[EvalRunWithLatestAnnotationResponse] = []
    for r in runs:
        items.append(
            EvalRunWithLatestAnnotationResponse.model_validate(
                {
                    **EvalRunResponse.model_validate(r).model_dump(),
                    "latest_annotation": EvalAnnotationResponse.model_validate(latest_map.get(r.id)).model_dump()
                    if latest_map.get(r.id)
                    else None,
                }
            )
        )
    return EvalRunWithLatestAnnotationListResponse(total=total, items=items)


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
def get_run(
    run_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> EvalRun:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return run


@router.post("/runs/{run_id}/annotations", response_model=EvalAnnotationResponse)
def create_annotation(
    run_id: str,
    request: Request,
    response: Response,
    payload: EvalAnnotationCreate,
    db: Session = Depends(get_db),
) -> EvalAnnotation:
    _require_public_enabled(request)
    created_by = _get_or_set_rater_id(request, response)
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="RUN_NOT_FOUND")
    ann = EvalAnnotation(
        id=uuid4().hex,
        run_id=run_id,
        rating=payload.rating,
        tags_json=payload.tags_json,
        comment=payload.comment,
        created_by=created_by,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


@router.get("/runs/{run_id}/annotations", response_model=list[EvalAnnotationResponse])
def list_run_annotations(
    run_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> list[EvalAnnotation]:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    stmt = select(EvalAnnotation).where(EvalAnnotation.run_id == run_id).order_by(EvalAnnotation.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.get("/metrics/workflows")
def workflow_metrics(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return per-workflow aggregate rating metrics for business comparison."""
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    # avg rating + count per workflow_version_id
    rows = db.execute(
        select(
            EvalRun.workflow_version_id,
            func.count(EvalAnnotation.id).label("rating_count"),
            func.avg(EvalAnnotation.rating).label("avg_rating"),
        )
        .select_from(EvalRun)
        .join(EvalAnnotation, EvalAnnotation.run_id == EvalRun.id, isouter=True)
        .group_by(EvalRun.workflow_version_id)
    ).all()
    metrics: dict[str, Any] = {}
    for workflow_version_id, rating_count, avg_rating in rows:
        if not workflow_version_id:
            continue
        metrics[str(workflow_version_id)] = {
            "ratingCount": int(rating_count or 0),
            "avgRating": float(avg_rating) if avg_rating is not None else None,
        }
    return {"metrics": metrics}
