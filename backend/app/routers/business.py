"""Business-facing API over PODI atomic abilities."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.deps.auth import get_current_user
from app.deps.internal import is_internal_request
from app.models.user import User
from app.schemas import business as schemas
from app.services.auth_service import auth_service
from app.services.business_runs import get_business_run_service


router = APIRouter(prefix="/api/business", tags=["business"])
bearer_scheme = HTTPBearer(auto_error=False)


def _business_export_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _business_runs_to_csv(items: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "run_id",
            "业务",
            "版本",
            "状态",
            "链路问题",
            "处理建议",
            "入口",
            "业务方",
            "客户端",
            "排障编号",
            "能力",
            "执行任务",
            "图片数",
            "视频数",
            "文本数",
            "计费状态",
            "成本",
            "额度",
            "回调状态",
            "错误",
            "创建时间",
            "完成时间",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item.get("id") or "",
                item.get("business_key") or "",
                item.get("version") or "",
                item.get("status") or "",
                item.get("issue_label") or item.get("issue_category") or "",
                item.get("issue_action") or "",
                item.get("source") or "",
                item.get("tenant_id") or "",
                item.get("client_id") or "",
                item.get("trace_id") or "",
                item.get("ability_name") or item.get("ability_id") or "",
                item.get("ability_task_id") or "",
                len(item.get("image_urls") or []),
                len(item.get("video_urls") or []),
                len(item.get("texts") or []),
                item.get("billing_status") or "",
                _business_export_cell(item.get("cost_amount")),
                _business_export_cell(item.get("quota_units")),
                item.get("callback_status") or "",
                item.get("error_message") or item.get("issue_evidence") or "",
                _business_export_cell(item.get("created_at")),
                _business_export_cell(item.get("finished_at")),
            ]
        )
    return output.getvalue()


def _is_internal_request(request: Request) -> bool:
    return is_internal_request(request)


def _resolve_business_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    settings = get_settings()
    token = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else None
    if token and settings.service_api_token and token == settings.service_api_token:
        return auth_service.build_service_user()
    if token:
        return get_current_user(request=request, credentials=credentials)  # type: ignore[arg-type]
    if _is_internal_request(request):
        return auth_service.build_service_user()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTHORIZATION_REQUIRED")


def _server_from_request(request: Request) -> str:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").strip()
    forwarded_host = (request.headers.get("x-forwarded-host") or "").strip()
    host = forwarded_host or (request.headers.get("host") or "").strip()
    scheme = forwarded_proto or request.url.scheme
    if host:
        return f"{scheme}://{host}"
    return str(request.base_url).rstrip("/")


@router.get("/capabilities", response_model=schemas.BusinessCapabilityListResponse, response_model_by_alias=False)
def list_business_capabilities(
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityListResponse:
    _ = user
    items = get_business_run_service().list_capabilities()
    return schemas.BusinessCapabilityListResponse(items=items)


@router.post("/fission/runs", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def create_fission_run(
    payload: schemas.BusinessRunCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    return get_business_run_service().create_run(business_key="fission", payload=payload, user=user)


@router.post("/outpaint/runs", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def create_outpaint_run(
    payload: schemas.BusinessRunCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    return get_business_run_service().create_run(business_key="outpaint", payload=payload, user=user)


@router.post("/pattern-extract/runs", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def create_pattern_extract_run(
    payload: schemas.BusinessRunCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    return get_business_run_service().create_run(business_key="pattern_extract", payload=payload, user=user)


@router.post("/fission/route-preview", response_model=schemas.BusinessRoutePreviewResponse, response_model_by_alias=False)
def preview_fission_route(
    payload: schemas.BusinessRunCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRoutePreviewResponse:
    return get_business_run_service().preview_route(business_key="fission", payload=payload, user=user)


@router.post("/outpaint/route-preview", response_model=schemas.BusinessRoutePreviewResponse, response_model_by_alias=False)
def preview_outpaint_route(
    payload: schemas.BusinessRunCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRoutePreviewResponse:
    return get_business_run_service().preview_route(business_key="outpaint", payload=payload, user=user)


@router.post("/pattern-extract/route-preview", response_model=schemas.BusinessRoutePreviewResponse, response_model_by_alias=False)
def preview_pattern_extract_route(
    payload: schemas.BusinessRunCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRoutePreviewResponse:
    return get_business_run_service().preview_route(business_key="pattern_extract", payload=payload, user=user)


@router.get("/runs/{run_id}", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def get_business_run(
    run_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    return get_business_run_service().get_run(run_id=run_id, user=user)


@router.post("/runs/get", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def get_business_run_post(
    body: dict[str, Any],
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    run_id = str(body.get("runId") or body.get("run_id") or "").strip()
    if not run_id:
        raise HTTPException(status_code=400, detail="BUSINESS_RUN_ID_REQUIRED")
    return get_business_run(run_id=run_id, user=user)


@router.get("/openapi.json")
def get_business_openapi(request: Request) -> dict[str, Any]:
    server = _server_from_request(request)
    run_response_schema = {
        "type": "object",
        "properties": {
            "runId": {"type": "string"},
            "taskId": {"type": "string", "nullable": True},
            "businessKey": {"type": "string"},
            "version": {"type": "string", "nullable": True},
            "status": {"type": "string"},
            "source": {"type": "string"},
            "channel": {"type": "string", "nullable": True},
            "traceId": {"type": "string", "nullable": True},
            "requestId": {"type": "string", "nullable": True},
            "tenantId": {"type": "string", "nullable": True},
            "clientId": {"type": "string", "nullable": True},
            "abilityId": {"type": "string", "nullable": True},
            "abilityName": {"type": "string", "nullable": True},
            "vendorModelId": {"type": "integer", "nullable": True},
            "vendorModelName": {"type": "string", "nullable": True},
            "routeInfo": {"type": "object", "nullable": True},
            "steps": {
                "type": "array",
                "description": "业务配方步骤状态，便于排查 VL 前置分析、主执行能力等链路。",
                "items": {
                    "type": "object",
                    "properties": {
                        "order": {"type": "integer"},
                        "stepType": {"type": "string"},
                        "role": {"type": "string", "nullable": True},
                        "displayName": {"type": "string", "nullable": True},
                        "status": {"type": "string"},
                        "abilityId": {"type": "string", "nullable": True},
                        "abilityName": {"type": "string", "nullable": True},
                        "abilityTaskId": {"type": "string", "nullable": True},
                        "resultSummary": {
                            "type": "object",
                            "nullable": True,
                            "description": "步骤结果摘要，只包含可读摘要、图片数量、文本预览等安全信息。",
                        },
                        "error": {"type": "string", "nullable": True},
                        "durationMs": {"type": "integer", "nullable": True},
                        "costAmount": {"type": "number", "nullable": True},
                        "currency": {"type": "string", "nullable": True},
                        "quotaUnits": {"type": "integer", "nullable": True},
                    },
                },
            },
            "imageUrls": {"type": "array", "items": {"type": "string"}},
            "videoUrls": {"type": "array", "items": {"type": "string"}},
            "texts": {"type": "array", "items": {"type": "string"}},
            "error": {"type": "string", "nullable": True},
            "durationMs": {"type": "integer", "nullable": True},
            "costAmount": {"type": "number", "nullable": True},
            "currency": {"type": "string", "nullable": True},
            "quotaUnits": {"type": "integer", "nullable": True},
            "billingStatus": {
                "type": "string",
                "nullable": True,
                "description": "业务计费状态：billable/unpriced/no_charge/billing_pending。",
            },
            "chargeable": {"type": "boolean", "nullable": True, "description": "是否可进入业务方正式账单。"},
            "noChargeReason": {"type": "string", "nullable": True, "description": "不计费或暂不计费原因。"},
            "callbackStatus": {"type": "string", "nullable": True},
            "callbackHttpStatus": {"type": "integer", "nullable": True},
            "callbackError": {"type": "string", "nullable": True},
            "debugUrl": {"type": "string", "nullable": True},
        },
    }
    route_preview_schema = {
        "type": "object",
        "properties": {
            "businessKey": {"type": "string"},
            "requestedVersion": {"type": "string", "nullable": True},
            "selectedCapabilityId": {"type": "string"},
            "selectedVersion": {"type": "string"},
            "selectedDisplayName": {"type": "string"},
            "selectedStatus": {"type": "string"},
            "selectedIsDefault": {"type": "boolean"},
            "selectedBy": {"type": "string", "description": "explicit/default/rollout_allowlist/rollout_percent"},
            "routeInfo": {"type": "object"},
            "defaultCapabilityId": {"type": "string", "nullable": True},
            "defaultVersion": {"type": "string", "nullable": True},
            "activeVersions": {"type": "array", "items": {"type": "object"}},
        },
    }
    base_submit_properties = {
        "imageUrl": {"type": "string", "description": "原图 URL Image URL"},
        "prompt": {"type": "string", "nullable": True, "description": "业务提示词 Prompt"},
        "version": {"type": "string", "nullable": True, "description": "指定业务版本；为空使用默认版本"},
        "inputs": {"type": "object", "description": "兼容旧格式；新接入优先使用顶层业务参数。"},
        "source": {"type": "string", "nullable": True, "description": "调用来源，例如 coze、client、partner-api。"},
        "channel": {"type": "string", "nullable": True, "description": "业务渠道，例如 coze-workflow、open-api、eval。"},
        "traceId": {"type": "string", "nullable": True, "description": "调用链路 ID，用于跨系统排查。"},
        "requestId": {"type": "string", "nullable": True, "description": "业务方请求 ID，用于幂等和日志关联。"},
        "tenantId": {"type": "string", "nullable": True, "description": "租户/业务方 ID。"},
        "clientId": {"type": "string", "nullable": True, "description": "客户端/应用 ID。"},
        "callbackUrl": {"type": "string", "nullable": True, "description": "终态回调地址"},
        "callbackHeaders": {"type": "object", "nullable": True, "description": "终态回调请求头。"},
        "metadata": {"type": "object", "nullable": True, "description": "业务上下文，例如 grayKey、tenantId、userId。"},
    }
    fission_submit_schema = {
        "type": "object",
        "required": ["imageUrl"],
        "properties": {
            **base_submit_properties,
            "bili": {
                "oneOf": [{"type": "number"}, {"type": "string"}],
                "nullable": True,
                "description": "裂变幅度；旧版本可传数字，新 ComfyUI VL 控制卡版本可传 `50%` 这类百分比。",
            },
            "width": {"type": "integer", "nullable": True, "description": "输出宽度。"},
            "height": {"type": "integer", "nullable": True, "description": "输出高度。"},
            "profile": {"type": "string", "nullable": True, "description": "裂变配置，例如 pattern_default_v1。"},
            "mode": {"type": "string", "nullable": True, "description": "执行模式，例如 fission。"},
            "vl_result": {
                "oneOf": [{"type": "object"}, {"type": "string"}],
                "nullable": True,
                "description": "上游 VL 控制卡 JSON；通常由中台 VL 组件自动生成。",
            },
            "image_desc": {"type": "string", "nullable": True, "description": "图片描述，可由 VL 分析结果填入。"},
            "batch_size": {"type": "integer", "nullable": True, "description": "输出张数。"},
            "steps": {"type": "integer", "nullable": True, "description": "采样步数。"},
            "cfg": {"type": "number", "nullable": True, "description": "提示词控制强度。"},
            "variation_strength": {
                "type": "string",
                "nullable": True,
                "description": "GPT Image 2 裂变幅度：low / medium / high。",
                "enum": ["low", "medium", "high"],
            },
            "quality": {
                "type": "string",
                "nullable": True,
                "description": "商业模型质量档位：preview / production / premium。",
                "enum": ["preview", "production", "premium"],
            },
            "count": {"type": "integer", "nullable": True, "description": "GPT Image 2 输出张数，建议 1-3。"},
            "preserve_layout": {"type": "boolean", "nullable": True, "description": "是否保留原图版式。"},
            "preserve_border": {"type": "string", "nullable": True, "description": "边框保留策略：auto / true / false。"},
            "preserve_count_density": {"type": "boolean", "nullable": True, "description": "是否保留元素数量感和密度。"},
            "style_shift": {"type": "string", "nullable": True, "description": "风格迁移幅度：standard / conservative / creative。"},
            "size": {"type": "string", "nullable": True, "description": "GPT Image 2 输出尺寸，默认 auto。"},
            "output_format": {"type": "string", "nullable": True, "description": "GPT Image 2 输出格式，默认 png。"},
            "maskUrl": {"type": "string", "nullable": True, "description": "可选蒙版 URL；用于局部编辑。"},
        },
    }
    pattern_extract_submit_schema = {
        "type": "object",
        "required": ["imageUrl"],
        "properties": {
            **base_submit_properties,
            "negative_prompt": {"type": "string", "nullable": True, "description": "不要出现的内容。"},
            "width": {"type": "integer", "nullable": True, "description": "输出宽度。"},
            "height": {"type": "integer", "nullable": True, "description": "输出高度。"},
            "batch": {"type": "integer", "nullable": True, "description": "生成张数；数值越大耗时越久。"},
            "lora": {"type": "string", "nullable": True, "description": "LoRA 方案；为空使用当前业务版本默认值。"},
            "timeout": {"type": "integer", "nullable": True, "description": "任务超时时间，单位秒。"},
        },
    }
    fission_route_preview_schema = {
        **fission_submit_schema,
        "required": [],
    }
    pattern_extract_route_preview_schema = {
        **pattern_extract_submit_schema,
        "required": [],
    }
    outpaint_submit_schema = {
        "type": "object",
        "required": ["imageUrl"],
        "properties": {
            **base_submit_properties,
            "expand_left": {"type": "integer", "nullable": True, "description": "向左扩展像素。"},
            "expand_right": {"type": "integer", "nullable": True, "description": "向右扩展像素。"},
            "expand_top": {"type": "integer", "nullable": True, "description": "向上扩展像素。"},
            "expand_bottom": {"type": "integer", "nullable": True, "description": "向下扩展像素。"},
            "width": {"type": "integer", "nullable": True, "description": "输出宽度。"},
            "height": {"type": "integer", "nullable": True, "description": "输出高度。"},
            "timeout": {"type": "integer", "nullable": True, "description": "任务超时时间，单位秒。"},
        },
    }
    outpaint_route_preview_schema = {
        **outpaint_submit_schema,
        "required": [],
    }
    error_schema = {
        "type": "object",
        "properties": {
            "detail": {
                "type": "string",
                "description": "平台错误码，例如 BUSINESS_IMAGE_URL_REQUIRED、BUSINESS_RUN_NOT_FOUND。",
            }
        },
    }

    def _business_responses(*, success_description: str, errors_by_status: dict[str, list[str]]) -> dict[str, Any]:
        return {
            "200": {
                "description": success_description,
                "content": {"application/json": {"schema": run_response_schema}},
            },
            "400": {
                "description": "请求参数缺失或业务配置非法",
                "content": {"application/json": {"schema": error_schema}},
                "x-podi-errors": errors_by_status.get("400", []),
            },
            "401": {
                "description": "未认证或服务 Token 无效",
                "content": {"application/json": {"schema": error_schema}},
                "x-podi-errors": ["AUTHORIZATION_REQUIRED"],
            },
            "403": {
                "description": "无权访问该业务任务",
                "content": {"application/json": {"schema": error_schema}},
                "x-podi-errors": errors_by_status.get("403", ["BUSINESS_RUN_FORBIDDEN"]),
            },
            "404": {
                "description": "业务版本或任务不存在",
                "content": {"application/json": {"schema": error_schema}},
                "x-podi-errors": errors_by_status.get("404", []),
            },
            "409": {
                "description": "业务状态冲突或上游任务状态不允许",
                "content": {"application/json": {"schema": error_schema}},
                "x-podi-errors": errors_by_status.get("409", []),
            },
            "429": {
                "description": "队列或并发限制",
                "content": {"application/json": {"schema": error_schema}},
                "x-podi-errors": errors_by_status.get("429", []),
            },
            "500": {
                "description": "底层能力或执行节点失败",
                "content": {"application/json": {"schema": error_schema}},
                "x-podi-errors": errors_by_status.get("500", []),
            },
        }

    def _route_preview_responses(*, errors_by_status: dict[str, list[str]]) -> dict[str, Any]:
        responses = _business_responses(success_description="Business route preview", errors_by_status=errors_by_status)
        responses["200"] = {
            "description": "Business route preview",
            "content": {"application/json": {"schema": route_preview_schema}},
        }
        return responses

    submit_errors = {
        "400": [
            "BUSINESS_IMAGE_URL_REQUIRED",
            "BUSINESS_RECIPE_INVALID",
            "BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE",
            "COMFYUI_IMAGE_REQUIRED",
        ],
        "404": ["BUSINESS_CAPABILITY_NOT_FOUND"],
        "429": ["VENDOR_API_CONCURRENCY_LIMITED", "VENDOR_API_KEY_CONCURRENCY_LIMITED"],
        "500": ["ABILITY_TASK_FAILED", "COMFYUI_TIMEOUT", "VENDOR_API_EXECUTION_FAILED"],
    }
    get_errors = {
        "400": ["BUSINESS_RUN_ID_REQUIRED"],
        "403": ["BUSINESS_RUN_FORBIDDEN"],
        "404": ["BUSINESS_RUN_NOT_FOUND"],
    }
    submit_errors["403"] = [
        "BUSINESS_CLIENT_DISABLED",
        "BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED",
        "BUSINESS_USER_SCOPE_REQUIRED",
        "BUSINESS_USER_SCOPE_FORBIDDEN",
    ]
    submit_errors["429"] = [
        "BUSINESS_CLIENT_CONCURRENCY_LIMITED",
        "BUSINESS_CLIENT_DAILY_RUN_LIMITED",
        "BUSINESS_CLIENT_DAILY_QUOTA_LIMITED",
        *submit_errors["429"],
    ]
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "PODI Business APIs",
            "version": "0.1.0",
            "description": "业务层稳定入口：花纹提取、图裂变、扩图、任务查询。Coze 只需要调用这些扁平 API。",
        },
        "servers": [{"url": server}],
        "paths": {
            "/api/business/pattern-extract/runs": {
                "post": {
                    "operationId": "podi_business_pattern_extract_run",
                    "summary": "PODI · 花纹提取",
                    "description": "提交花纹提取业务任务。业务方只需要传原图和可选提取要求，底层版本由中台路由。",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": pattern_extract_submit_schema}}},
                    "responses": _business_responses(success_description="Business run", errors_by_status=submit_errors),
                }
            },
            "/api/business/fission/runs": {
                "post": {
                    "operationId": "podi_business_fission_run",
                    "summary": "PODI · 图裂变",
                    "description": "提交图裂变业务任务。业务方只需要传原图、提示词和可选参数，返回 runId 后轮询结果。",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": fission_submit_schema}}},
                    "responses": _business_responses(success_description="Business run", errors_by_status=submit_errors),
                }
            },
            "/api/business/outpaint/runs": {
                "post": {
                    "operationId": "podi_business_outpaint_run",
                    "summary": "PODI · 扩图",
                    "description": "提交扩图业务任务。宽高、上下左右扩展量从 inputs 传入，底层版本由中台路由。",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": outpaint_submit_schema}}},
                    "responses": _business_responses(success_description="Business run", errors_by_status=submit_errors),
                }
            },
            "/api/business/pattern-extract/route-preview": {
                "post": {
                    "operationId": "podi_business_pattern_extract_route_preview",
                    "summary": "PODI · 花纹提取路由预览",
                    "description": "不提交真实任务，只预览当前 tenantId/clientId/grayKey 会命中哪个花纹提取版本，用于灰度验证。",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": pattern_extract_route_preview_schema}}},
                    "responses": _route_preview_responses(errors_by_status=submit_errors),
                }
            },
            "/api/business/fission/route-preview": {
                "post": {
                    "operationId": "podi_business_fission_route_preview",
                    "summary": "PODI · 图裂变路由预览",
                    "description": "不提交真实任务，只预览当前 tenantId/clientId/grayKey 会命中哪个业务版本，用于灰度验证。",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": fission_route_preview_schema}}},
                    "responses": _route_preview_responses(errors_by_status=submit_errors),
                }
            },
            "/api/business/outpaint/route-preview": {
                "post": {
                    "operationId": "podi_business_outpaint_route_preview",
                    "summary": "PODI · 扩图路由预览",
                    "description": "不提交真实任务，只预览当前 tenantId/clientId/grayKey 会命中哪个业务版本，用于灰度验证。",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": outpaint_route_preview_schema}}},
                    "responses": _route_preview_responses(errors_by_status=submit_errors),
                }
            },
            "/api/business/runs/get": {
                "post": {
                    "operationId": "podi_business_run_get",
                    "summary": "PODI · 查询业务任务",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["runId"],
                                    "properties": {"runId": {"type": "string", "description": "业务任务 ID"}},
                                }
                            }
                        },
                    },
                    "responses": _business_responses(success_description="Business run", errors_by_status=get_errors),
                }
            },
        },
    }


admin_router = APIRouter(prefix="/admin/business", tags=["admin-business"])


@admin_router.get("/capabilities", response_model=schemas.BusinessCapabilityListResponse, response_model_by_alias=False)
def admin_list_business_capabilities(
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return list_business_capabilities(user=user)


@admin_router.get("/clients", response_model=schemas.BusinessClientListResponse, response_model_by_alias=False)
def admin_list_business_clients(
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessClientListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return schemas.BusinessClientListResponse(
        items=get_business_run_service().list_clients(
            tenant_id=tenant_id,
            client_id=client_id,
            status=status,
        )
    )


@admin_router.post("/clients", response_model=schemas.BusinessClientRead, response_model_by_alias=False)
def admin_create_business_client(
    payload: schemas.BusinessClientCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessClientRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().create_client(payload)


@admin_router.patch("/clients/{client_config_id}", response_model=schemas.BusinessClientRead, response_model_by_alias=False)
def admin_update_business_client(
    client_config_id: str,
    payload: schemas.BusinessClientUpdateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessClientRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().update_client(client_config_id, payload)


@admin_router.post("/capabilities", response_model=schemas.BusinessCapabilityRead, response_model_by_alias=False)
def admin_create_business_capability(
    payload: schemas.BusinessCapabilityCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().create_capability(payload)


@admin_router.patch("/capabilities/{capability_id}", response_model=schemas.BusinessCapabilityRead, response_model_by_alias=False)
def admin_update_business_capability(
    capability_id: str,
    payload: schemas.BusinessCapabilityUpdateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().update_capability(capability_id, payload)


@admin_router.post(
    "/capabilities/{capability_id}/acceptance-records",
    response_model=schemas.BusinessCapabilityRead,
    response_model_by_alias=False,
)
def admin_record_business_capability_acceptance(
    capability_id: str,
    payload: schemas.BusinessAcceptanceRecordRequest | None = None,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().record_acceptance(capability_id, payload, actor=user)


@admin_router.post("/capabilities/{capability_id}/promote", response_model=schemas.BusinessCapabilityRead, response_model_by_alias=False)
def admin_promote_business_capability(
    capability_id: str,
    payload: schemas.BusinessCapabilityPromoteRequest | None = None,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().promote_capability(capability_id, payload, actor=user)


@admin_router.post(
    "/capabilities/{capability_id}/default-approvals",
    response_model=schemas.BusinessDefaultApprovalRead,
    response_model_by_alias=False,
)
def admin_create_business_default_approval(
    capability_id: str,
    payload: schemas.BusinessDefaultApprovalCreateRequest | None = None,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessDefaultApprovalRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().create_default_approval(capability_id, payload, actor=user)


@admin_router.get(
    "/default-approvals",
    response_model=schemas.BusinessDefaultApprovalListResponse,
    response_model_by_alias=False,
)
def admin_list_business_default_approvals(
    status: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessDefaultApprovalListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return schemas.BusinessDefaultApprovalListResponse(
        items=get_business_run_service().list_default_approvals(
            status=status,
            business_key=business_key,
            limit=limit,
        )
    )


@admin_router.post(
    "/default-approvals/{approval_id}/approve",
    response_model=schemas.BusinessDefaultApprovalRead,
    response_model_by_alias=False,
)
def admin_approve_business_default_approval(
    approval_id: str,
    payload: schemas.BusinessDefaultApprovalDecisionRequest | None = None,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessDefaultApprovalRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().decide_default_approval(approval_id, payload, actor=user, approve=True)


@admin_router.post(
    "/default-approvals/{approval_id}/reject",
    response_model=schemas.BusinessDefaultApprovalRead,
    response_model_by_alias=False,
)
def admin_reject_business_default_approval(
    approval_id: str,
    payload: schemas.BusinessDefaultApprovalDecisionRequest | None = None,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessDefaultApprovalRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().decide_default_approval(approval_id, payload, actor=user, approve=False)


@admin_router.post("/rollback/{business_key}", response_model=schemas.BusinessCapabilityRead, response_model_by_alias=False)
def admin_rollback_business_default(
    business_key: str,
    payload: schemas.BusinessCapabilityRollbackRequest | None = None,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().rollback_default(business_key, payload, actor=user)


@admin_router.post("/route-preview/{business_key}", response_model=schemas.BusinessRoutePreviewResponse, response_model_by_alias=False)
def admin_preview_business_route(
    business_key: str,
    payload: schemas.BusinessRunCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRoutePreviewResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().preview_route(business_key=business_key, payload=payload, user=user)


@admin_router.get("/runs", response_model=schemas.BusinessRunListResponse, response_model_by_alias=False)
def admin_list_business_runs(
    business_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    billing_status: str | None = Query(default=None),
    callback_status: str | None = Query(default=None),
    issue_category: str | None = Query(default=None),
    version: str | None = Query(default=None),
    source: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    total, items = get_business_run_service().list_runs(
        limit=limit,
        business_key=business_key,
        status=status,
        billing_status=billing_status,
        callback_status=callback_status,
        issue_category=issue_category,
        version=version,
        source=source,
        tenant_id=tenant_id,
        client_id=client_id,
        trace_id=trace_id,
    )
    return schemas.BusinessRunListResponse(items=items, total=total)


@admin_router.get("/runs/export")
def admin_export_business_runs(
    business_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    billing_status: str | None = Query(default=None),
    callback_status: str | None = Query(default=None),
    issue_category: str | None = Query(default=None),
    version: str | None = Query(default=None),
    source: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=1000),
    user: User = Depends(_resolve_business_user),
) -> Response:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    _, items = get_business_run_service().list_runs(
        limit=limit,
        business_key=business_key,
        status=status,
        billing_status=billing_status,
        callback_status=callback_status,
        issue_category=issue_category,
        version=version,
        source=source,
        tenant_id=tenant_id,
        client_id=client_id,
        trace_id=trace_id,
    )
    return Response(
        content="\ufeff" + _business_runs_to_csv(items),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="business-runs.csv"'},
    )


@admin_router.post("/runs/{run_id}/callback/retry", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def admin_retry_business_run_callback(
    run_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().retry_callback(run_id, actor=user)


@admin_router.post("/runs/{run_id}/billing/retry", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def admin_retry_business_run_billing(
    run_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().retry_billing(run_id, actor=user)


@admin_router.post("/runs/{run_id}/billing/refund", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def admin_refund_business_run_billing(
    run_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().refund_billing(run_id, actor=user)


@admin_router.post(
    "/runs/bulk/callback-retry",
    response_model=schemas.BusinessRunBulkActionResponse,
    response_model_by_alias=False,
)
def admin_bulk_retry_business_run_callbacks(
    payload: schemas.BusinessRunBulkActionRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunBulkActionResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().bulk_retry_callbacks(
        payload.runIds,
        actor=user,
        only_failed=payload.onlyFailed,
    )


@admin_router.post("/runs/{run_id}/retest", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def admin_retest_business_run(
    run_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().retest_run(run_id, actor=user)


@admin_router.post(
    "/runs/bulk/retest",
    response_model=schemas.BusinessRunBulkActionResponse,
    response_model_by_alias=False,
)
def admin_bulk_retest_business_runs(
    payload: schemas.BusinessRunBulkActionRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunBulkActionResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().bulk_retest_runs(
        payload.runIds,
        actor=user,
        only_failed=payload.onlyFailed,
    )


@admin_router.post(
    "/runs/bulk/mark-ignored",
    response_model=schemas.BusinessRunBulkActionResponse,
    response_model_by_alias=False,
)
def admin_mark_business_runs_ignored(
    payload: schemas.BusinessRunBulkActionRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunBulkActionResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().mark_issues_ignored(payload.runIds, note=payload.note, actor=user)


@admin_router.post(
    "/runs/issue-checklist",
    response_model=schemas.BusinessRunIssueChecklistResponse,
    response_model_by_alias=False,
)
def admin_generate_business_run_issue_checklist(
    payload: schemas.BusinessRunIssueChecklistRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunIssueChecklistResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().generate_issue_checklist(
        payload.runIds,
        only_failed=payload.onlyFailed,
        actor=user,
    )


@admin_router.get(
    "/operation-logs",
    response_model=schemas.BusinessOperationLogListResponse,
    response_model_by_alias=False,
)
def admin_list_business_operation_logs(
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    actor_user_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessOperationLogListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return schemas.BusinessOperationLogListResponse(
        items=get_business_run_service().list_operation_logs(
            action=action,
            target_type=target_type,
            business_key=business_key,
            tenant_id=tenant_id,
            client_id=client_id,
            actor_user_id=actor_user_id,
            limit=limit,
        )
    )


@admin_router.get("/usage-summary", response_model=schemas.BusinessUsageSummaryResponse, response_model_by_alias=False)
def admin_business_usage_summary(
    window_hours: int = Query(default=24, ge=1, le=2160),
    business_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    issue_category: str | None = Query(default=None),
    version: str | None = Query(default=None),
    source: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessUsageSummaryResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().usage_summary(
        window_hours=window_hours,
        business_key=business_key,
        status=status,
        issue_category=issue_category,
        version=version,
        source=source,
        tenant_id=tenant_id,
        client_id=client_id,
        trace_id=trace_id,
    )
