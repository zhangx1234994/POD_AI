"""Business-facing API over PODI atomic abilities."""

from __future__ import annotations

import csv
import io
import json
import re
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_session
from app.deps.auth import get_current_user, require_admin
from app.deps.internal import is_internal_request
from app.models.integration import ApiKey, BusinessApiKeyUsageLog
from app.models.user import User
from app.schemas import business as schemas
from app.services.auth_service import auth_service
from app.services.business_runs import get_business_run_service


router = APIRouter(prefix="/api/business", tags=["business"])
bearer_scheme = HTTPBearer(auto_error=False)
BUSINESS_API_KEY_PROVIDERS = {"business_api", "podi_business_api"}


def _business_export_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _business_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on", "full", "debug"}


def _business_run_wants_full_detail(*, detail: Any = None, include_debug: Any = None) -> bool:
    return str(detail or "").strip().lower() in {"full", "debug", "detail", "all"} or _business_bool(include_debug)


def _normalize_business_task_status(status: Any) -> str:
    text = str(status or "").strip().lower()
    if text in {"queued", "pending", "created"}:
        return "queued"
    if text in {"running", "processing", "in_progress", "submitted"}:
        return "running"
    if text in {"succeeded", "success", "completed", "done"}:
        return "succeeded"
    if text in {"failed", "error", "cancelled", "canceled", "timeout"}:
        return "failed"
    return text or "queued"


def _business_error_code(message: Any) -> str | None:
    text = str(message or "").strip()
    if not text:
        return None
    match = re.search(r"\b([A-Z][A-Z0-9_]{2,})\b", text)
    return match.group(1) if match else None


def _compact_business_payload(value: Any, *, max_text: int = 800) -> Any:
    if isinstance(value, dict):
        blocked = {
            "raw",
            "metadata",
            "request",
            "response",
            "debug",
            "debugRequest",
            "debugResponse",
            "_trace",
            "_route",
        }
        compact: dict[str, Any] = {}
        for key, item in value.items():
            if str(key) in blocked:
                continue
            compact[str(key)] = _compact_business_payload(item, max_text=max_text)
        return compact
    if isinstance(value, list):
        return [_compact_business_payload(item, max_text=max_text) for item in value[:20]]
    if isinstance(value, str) and len(value) > max_text:
        return f"{value[:max_text]}..."
    return value


def _parse_json_object_text(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _business_run_full_response(run: dict[str, Any]) -> dict[str, Any]:
    return schemas.BusinessRunRead.model_validate(run).model_dump(mode="json", by_alias=False)


def _business_run_light_response(run: dict[str, Any]) -> dict[str, Any]:
    full = _business_run_full_response(run)
    status = _normalize_business_task_status(full.get("status"))
    image_urls = full.get("imageUrls") if isinstance(full.get("imageUrls"), list) else []
    video_urls = full.get("videoUrls") if isinstance(full.get("videoUrls"), list) else []
    texts = full.get("texts") if isinstance(full.get("texts"), list) else []
    error_message = str(full.get("errorMessage") or full.get("error") or full.get("callbackError") or "").strip() or None
    result = {
        "runId": full.get("runId") or full.get("id"),
        "taskId": full.get("taskId"),
        "status": status,
        "taskStatus": status,
        "imageUrl": image_urls[0] if image_urls else None,
        "imageUrls": image_urls,
        "videoUrl": video_urls[0] if video_urls else None,
        "videoUrls": video_urls,
        "text": texts[0] if texts else ("failed" if status == "failed" else status),
        "texts": texts,
        "error": error_message,
        "errorMessage": error_message,
        "errorCode": _business_error_code(error_message),
        "debugUrl": full.get("debugUrl"),
        "debugResponse": error_message,
        "retryAfterSeconds": 10 if status in {"queued", "running"} else None,
        "expectedImageCount": None,
        "logId": full.get("abilityLogId"),
        "traceId": full.get("traceId"),
        "requestId": full.get("requestId"),
        "durationMs": full.get("durationMs"),
        "createdAt": full.get("createdAt"),
        "startedAt": full.get("startedAt"),
        "finishedAt": full.get("finishedAt"),
    }
    result_payload = full.get("resultPayload")
    if not isinstance(result_payload, dict) or not result_payload:
        result_payload = _parse_json_object_text(texts[0]) if texts else None
    if isinstance(result_payload, dict) and result_payload:
        result["resultPayload"] = _compact_business_payload(result_payload)
    return result


def _get_business_run_response(
    *,
    run_id: str,
    request: Request,
    user: User,
    full_detail: bool = False,
) -> dict[str, Any]:
    try:
        result = get_business_run_service().get_run(run_id=run_id, user=user)
    except HTTPException as exc:
        _record_business_api_key_usage(
            request,
            status_code=exc.status_code,
            run_id=run_id,
            error_code=str(exc.detail or ""),
        )
        raise
    except Exception:
        _record_business_api_key_usage(
            request,
            status_code=500,
            run_id=run_id,
            error_code="BUSINESS_RUN_GET_FAILED",
        )
        raise HTTPException(status_code=503, detail="BUSINESS_RUN_TEMPORARY_UNAVAILABLE")
    _record_business_api_key_usage(request, status_code=200, run=result, run_id=run_id)
    return _business_run_full_response(result) if full_detail else _business_run_light_response(result)


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
    api_key_user = _resolve_business_api_key_user(request, token)
    if api_key_user is not None:
        return api_key_user
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


def _preview_secret(value: str | None) -> str:
    raw = str(value or "")
    if len(raw) <= 8:
        return "***" if raw else ""
    return f"{raw[:4]}...{raw[-4:]}"


def _client_ip(request: Request) -> str | None:
    for header in ("x-forwarded-for", "x-real-ip"):
        value = request.headers.get(header)
        if value:
            return value.split(",", 1)[0].strip()[:64]
    return request.client.host[:64] if request.client and request.client.host else None


def _string_meta(metadata: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text[:64]
    return None


def _resolve_business_api_key_user(request: Request, token: str | None) -> User | None:
    normalized = str(token or request.headers.get("x-podi-api-key") or request.headers.get("x-api-key") or "").strip()
    if not normalized:
        return None
    now = datetime.utcnow()
    with get_session() as session:
        api_key = (
            session.execute(
                select(ApiKey).where(ApiKey.provider.in_(BUSINESS_API_KEY_PROVIDERS), ApiKey.key == normalized)
            )
            .scalars()
            .first()
        )
        if not api_key:
            return None
        if api_key.status != "active":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="BUSINESS_API_KEY_INACTIVE")
        if api_key.expire_at and api_key.expire_at <= now:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="BUSINESS_API_KEY_EXPIRED")
        metadata = api_key.extra_metadata if isinstance(api_key.extra_metadata, dict) else {}
        api_key.usage_count = int(api_key.usage_count or 0) + 1
        api_key.extra_metadata = {
            **metadata,
            "lastUsedAt": now.isoformat(),
            "lastUsedIp": _client_ip(request),
        }
        session.add(api_key)
        session.commit()
        request.state.business_api_key_context = {
            "apiKeyId": api_key.id,
            "apiKeyName": api_key.name,
            "apiKeyPreview": _preview_secret(api_key.key),
            "tenantId": _string_meta(metadata, "tenantId", "tenant_id"),
            "clientId": _string_meta(metadata, "clientId", "client_id"),
            "allowedBusinessKeys": metadata.get("allowedBusinessKeys") or metadata.get("allowed_business_keys") or [],
            "startedAt": time.perf_counter(),
        }
        return User(
            id=f"business-api-key:{api_key.id}",
            email=f"{api_key.id}@business-api.podi.internal",
            username=api_key.name or api_key.id,
            password_hash="",
            role="client",
            status="active",
            tenant_id=request.state.business_api_key_context["tenantId"],
            client_id=request.state.business_api_key_context["clientId"],
            extra_metadata={"apiKeyId": api_key.id},
        )


def _record_business_api_key_usage(
    request: Request,
    *,
    status_code: int,
    business_key: str | None = None,
    run: Any | None = None,
    run_id: str | None = None,
    error_code: str | None = None,
) -> None:
    context = getattr(request.state, "business_api_key_context", None)
    if not isinstance(context, dict):
        return
    payload = run if isinstance(run, dict) else {}
    resolved_run_id = run_id or str(payload.get("id") or payload.get("runId") or "").strip() or None
    duration_ms = None
    started_at = context.get("startedAt")
    if isinstance(started_at, (int, float)):
        duration_ms = max(0, int((time.perf_counter() - started_at) * 1000))
    with get_session() as session:
        session.add(
            BusinessApiKeyUsageLog(
                api_key_id=str(context.get("apiKeyId") or "") or None,
                api_key_name=str(context.get("apiKeyName") or "") or None,
                api_key_preview=str(context.get("apiKeyPreview") or "") or None,
                method=request.method[:16],
                path=request.url.path[:256],
                status_code=status_code,
                business_key=business_key or str(payload.get("business_key") or payload.get("businessKey") or "") or None,
                run_id=resolved_run_id,
                request_id=str(payload.get("request_id") or payload.get("requestId") or "") or None,
                trace_id=str(payload.get("trace_id") or payload.get("traceId") or "") or None,
                tenant_id=str(payload.get("tenant_id") or payload.get("tenantId") or context.get("tenantId") or "") or None,
                client_id=str(payload.get("client_id") or payload.get("clientId") or context.get("clientId") or "") or None,
                error_code=str(error_code or "") or None,
                duration_ms=duration_ms,
                ip_address=_client_ip(request),
                user_agent=(request.headers.get("user-agent") or "")[:255] or None,
                created_at=datetime.utcnow(),
            )
        )
        session.commit()


def _business_key_allowed_for_api_key(request: Request, business_key: str) -> None:
    context = getattr(request.state, "business_api_key_context", None)
    if not isinstance(context, dict):
        return
    allowed = context.get("allowedBusinessKeys")
    if not allowed:
        return
    raw_allowed = allowed.split(",") if isinstance(allowed, str) else allowed
    allowed_set = {str(item).strip() for item in raw_allowed if str(item).strip()}
    if allowed_set and business_key not in allowed_set:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED")


def _business_api_key_metadata(
    *,
    tenant_id: str | None,
    client_id: str | None,
    allowed_business_keys: list[str] | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    base = dict(metadata or {})
    if tenant_id is not None:
        base["tenantId"] = tenant_id
    if client_id is not None:
        base["clientId"] = client_id
    if allowed_business_keys is not None:
        base["allowedBusinessKeys"] = [str(item).strip() for item in allowed_business_keys if str(item).strip()]
    return base


def _business_api_key_to_read(api_key: ApiKey) -> schemas.BusinessApiKeyRead:
    metadata = api_key.extra_metadata if isinstance(api_key.extra_metadata, dict) else {}
    raw_allowed = metadata.get("allowedBusinessKeys") or metadata.get("allowed_business_keys") or []
    if isinstance(raw_allowed, str):
        allowed_business_keys = [item.strip() for item in raw_allowed.split(",") if item.strip()]
    elif isinstance(raw_allowed, list):
        allowed_business_keys = [str(item).strip() for item in raw_allowed if str(item).strip()]
    else:
        allowed_business_keys = []
    payload = {
        "id": api_key.id,
        "name": api_key.name,
        "status": api_key.status,
        "key_preview": _preview_secret(api_key.key),
        "tenant_id": _string_meta(metadata, "tenantId", "tenant_id"),
        "client_id": _string_meta(metadata, "clientId", "client_id"),
        "allowed_business_keys": allowed_business_keys,
        "usage_count": api_key.usage_count or 0,
        "expire_at": api_key.expire_at,
        "metadata": metadata,
        "created_at": api_key.created_at,
        "updated_at": api_key.updated_at,
    }
    return schemas.BusinessApiKeyRead.model_validate(payload)


def _create_business_run_with_usage(
    *,
    request: Request,
    business_key: str,
    payload: schemas.BusinessRunCreateRequest,
    user: User,
) -> schemas.BusinessRunRead:
    try:
        _business_key_allowed_for_api_key(request, business_key)
        result = get_business_run_service().create_run(business_key=business_key, payload=payload, user=user)
    except HTTPException as exc:
        _record_business_api_key_usage(
            request,
            status_code=exc.status_code,
            business_key=business_key,
            error_code=str(exc.detail or ""),
        )
        raise
    except Exception:
        _record_business_api_key_usage(
            request,
            status_code=500,
            business_key=business_key,
            error_code="BUSINESS_RUN_CREATE_FAILED",
        )
        raise
    _record_business_api_key_usage(request, status_code=200, business_key=business_key, run=result)
    return result


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
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    return _create_business_run_with_usage(request=request, business_key="fission", payload=payload, user=user)


@router.post("/fission-evaluate/runs", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
@router.post("/fission/evaluate/runs", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def create_fission_evaluate_run(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    return _create_business_run_with_usage(request=request, business_key="fission_evaluate", payload=payload, user=user)


@router.post("/outpaint/runs", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def create_outpaint_run(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    return _create_business_run_with_usage(request=request, business_key="outpaint", payload=payload, user=user)


@router.post("/pattern-extract/runs", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def create_pattern_extract_run(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    return _create_business_run_with_usage(request=request, business_key="pattern_extract", payload=payload, user=user)


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


@router.get("/runs/{run_id}", response_model=dict[str, Any], response_model_by_alias=False)
def get_business_run(
    run_id: str,
    request: Request,
    detail: str | None = Query(default=None, description="默认轻量返回；传 full/debug/detail/all 返回完整排障字段。"),
    include_debug: bool | None = Query(default=None, alias="includeDebug", description="true 时返回完整排障字段。"),
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    return _get_business_run_response(
        run_id=run_id,
        request=request,
        user=user,
        full_detail=_business_run_wants_full_detail(detail=detail, include_debug=include_debug),
    )


@router.post("/runs/get", response_model=dict[str, Any], response_model_by_alias=False)
def get_business_run_post(
    body: dict[str, Any],
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    run_id = str(body.get("runId") or body.get("run_id") or body.get("taskId") or body.get("task_id") or "").strip()
    if not run_id:
        _record_business_api_key_usage(
            request,
            status_code=400,
            error_code="BUSINESS_RUN_ID_REQUIRED",
        )
        raise HTTPException(status_code=400, detail="BUSINESS_RUN_ID_REQUIRED")
    return _get_business_run_response(
        run_id=run_id,
        request=request,
        user=user,
        full_detail=_business_run_wants_full_detail(
            detail=body.get("detail") or body.get("responseMode") or body.get("response_mode"),
            include_debug=body.get("includeDebug") or body.get("include_debug"),
        ),
    )


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
    run_query_response_schema = {
        "type": "object",
        "description": "默认轻量查询结果。业务方正常轮询只需要读取这些字段；需要完整排障字段时传 detail=full。",
        "properties": {
            "runId": {"type": "string", "description": "业务任务 ID。"},
            "taskId": {"type": "string", "nullable": True, "description": "底层能力任务 ID，仅用于排查。"},
            "status": {
                "type": "string",
                "description": "业务任务状态：queued/running/succeeded/failed。",
                "enum": ["queued", "running", "succeeded", "failed"],
            },
            "taskStatus": {
                "type": "string",
                "description": "兼容 Coze 轮询字段，值与 status 保持一致。",
                "enum": ["queued", "running", "succeeded", "failed"],
            },
            "imageUrl": {"type": "string", "nullable": True, "description": "第一张结果图，兼容 Coze 字段。"},
            "imageUrls": {"type": "array", "items": {"type": "string"}, "description": "全部结果图。"},
            "videoUrl": {"type": "string", "nullable": True, "description": "第一个结果视频，兼容 Coze 字段。"},
            "videoUrls": {"type": "array", "items": {"type": "string"}, "description": "全部结果视频。"},
            "text": {"type": "string", "nullable": True, "description": "第一条文本结果或当前状态。"},
            "texts": {"type": "array", "items": {"type": "string"}, "description": "文本结果。"},
            "resultPayload": {
                "type": "object",
                "nullable": True,
                "description": "仅在无图片/视频/文本时返回轻量结构化结果；完整链路请用 detail=full。",
            },
            "error": {"type": "string", "nullable": True, "description": "失败原因。"},
            "errorMessage": {"type": "string", "nullable": True, "description": "失败原因，兼容业务方字段。"},
            "errorCode": {"type": "string", "nullable": True, "description": "可机器判断的错误码。"},
            "debugResponse": {"type": "string", "nullable": True, "description": "轻量排障提示，不返回内部 SQL 或密钥。"},
            "debugUrl": {"type": "string", "nullable": True, "description": "排障链接。"},
            "retryAfterSeconds": {"type": "integer", "nullable": True, "description": "排队或运行中建议轮询间隔。"},
            "expectedImageCount": {"type": "integer", "nullable": True, "description": "预期图片数，兼容 Coze 字段。"},
            "logId": {"type": "integer", "nullable": True, "description": "能力调用日志 ID。"},
            "traceId": {"type": "string", "nullable": True},
            "requestId": {"type": "string", "nullable": True},
            "durationMs": {"type": "integer", "nullable": True},
            "createdAt": {"type": "string", "nullable": True},
            "startedAt": {"type": "string", "nullable": True},
            "finishedAt": {"type": "string", "nullable": True},
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
        "prompt": {
            "type": "string",
            "nullable": True,
            "description": "业务提示词 Prompt；可选。不传时中台会使用 VL 图像理解结果和当前版本默认系统提示词。",
        },
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
                "description": "图裂变重绘幅度，0-100；值越大重绘越强、变化越明显。可传 `50` 或 `50%`，中台按约定比例换算为 ComfyUI denoise。",
            },
            "width": {"type": "integer", "nullable": True, "description": "输出宽度。"},
            "height": {"type": "integer", "nullable": True, "description": "输出高度。"},
            "profile": {
                "type": "string",
                "nullable": True,
                "description": "裂变配置；颜色锁定版默认 pattern_color_lock_v2，旧版可继续兼容 pattern_default_v1。",
            },
            "mode": {"type": "string", "nullable": True, "description": "执行模式，例如 fission。"},
            "vl_result": {
                "oneOf": [{"type": "object"}, {"type": "string"}],
                "nullable": True,
                "description": "上游 VL 控制卡 JSON；通常由中台 VL 组件自动生成。",
            },
            "image_desc": {"type": "string", "nullable": True, "description": "图片描述，可由 VL 分析结果填入。"},
            "batch_size": {
                "type": "integer",
                "nullable": True,
                "description": "旧 ComfyUI 兼容字段；新交付接口固定一次生成 1 张图，不建议业务方传。",
            },
            "steps": {"type": "integer", "nullable": True, "description": "旧 ComfyUI 兼容字段；普通业务不需要传。"},
            "cfg": {"type": "number", "nullable": True, "description": "旧 ComfyUI 兼容字段；普通业务不需要传。"},
            "variation_strength": {
                "type": "string",
                "nullable": True,
                "description": "GPT Image 2 裂变幅度：conservative / same_series / creative_same_series。",
                "enum": ["conservative", "same_series", "creative_same_series"],
            },
            "quality": {
                "type": "string",
                "nullable": True,
                "description": "商业模型质量档位：preview / candidate / premium。",
                "enum": ["preview", "candidate", "premium"],
            },
            "size": {
                "type": "string",
                "nullable": True,
                "description": "GPT Image 2 比例尺寸预设；默认 auto，高分辨率档位成本和耗时更高。",
                "enum": [
                    "auto",
                    "1024x1024",
                    "1536x1024",
                    "1024x1536",
                    "2048x2048",
                    "2048x1152",
                    "3840x2160",
                    "2160x3840",
                ],
            },
            "output_format": {"type": "string", "nullable": True, "description": "GPT Image 2 输出格式，默认 png。"},
            "maskUrl": {"type": "string", "nullable": True, "description": "可选蒙版 URL；用于局部编辑。"},
        },
    }
    fission_evaluate_submit_schema = {
        "type": "object",
        "required": ["originalImageUrl", "generatedImageUrl"],
        "properties": {
            **base_submit_properties,
            "originalImageUrl": {"type": "string", "description": "裂变前原图 URL。"},
            "generatedImageUrl": {"type": "string", "description": "裂变后生成图 URL。"},
            "context": {
                "oneOf": [{"type": "object"}, {"type": "string"}],
                "nullable": True,
                "description": "可选业务上下文，例如裂变版本、提示词、profile、重绘幅度，用于辅助评分。",
            },
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
    business_api_key_security = [{"BusinessApiKey": []}, {"BearerAuth": []}]
    submit_examples = {
        "fission_gpt_image2_vl": {
            "summary": "图裂变 · GPT Image 2 + VL 控制版",
            "value": {
                "imageUrl": "https://example.com/input.png",
                "version": "gpt-image2-vl-v2",
                "prompt": "保持原图主体关系，做商业可用的花纹变化",
                "variation_strength": "same_series",
                "quality": "preview",
                "size": "auto",
                "maskUrl": "https://example.com/mask.png",
                "source": "partner-api",
                "channel": "open-api",
                "requestId": "biz-request-001",
                "traceId": "biz-trace-001",
                "callbackUrl": "https://your-service.example.com/podi/callback",
            },
        },
        "fission_comfyui_vl": {
            "summary": "图裂变 · ComfyUI 颜色锁定版",
            "value": {
                "imageUrl": "https://example.com/input.png",
                "version": "comfyui-vl-control-v2",
                "bili": "15%",
                "width": 2000,
                "height": 2000,
                "profile": "pattern_color_lock_v2",
                "source": "partner-api",
                "channel": "open-api",
                "requestId": "biz-request-002",
            },
        },
    }
    fission_evaluate_examples = {
        "fission_generated_image_evaluate": {
            "summary": "生成图评估 · 裂变质量与逻辑评估",
            "value": {
                "originalImageUrl": "https://example.com/original.png",
                "generatedImageUrl": "https://example.com/generated.png",
                "context": {
                    "business": "fission",
                    "version": "gpt-image2-vl-v2",
                    "prompt": "保持原图系列感，生成同系列变化图",
                },
                "source": "partner-api",
                "channel": "open-api",
                "requestId": "biz-request-eval-001",
                "traceId": "biz-trace-eval-001",
            },
        }
    }
    run_get_examples = {
        "poll_by_run_id": {
            "summary": "按提交接口返回的 runId 查询",
            "value": {"runId": "f5393c42a2b24c5d90852cce09f40b06"},
        },
        "poll_full_detail": {
            "summary": "排障时返回完整链路字段",
            "value": {"runId": "f5393c42a2b24c5d90852cce09f40b06", "detail": "full"},
        },
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

    def _business_responses(
        *,
        success_description: str,
        errors_by_status: dict[str, list[str]],
        success_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        schema = success_schema or run_response_schema
        return {
            "200": {
                "description": success_description,
                "content": {"application/json": {"schema": schema}},
            },
            "400": {
                "description": "请求参数缺失或业务配置非法",
                "content": {"application/json": {"schema": error_schema}},
                "x-podi-errors": errors_by_status.get("400", []),
            },
            "401": {
                "description": "未认证、服务 Token 无效或业务 API Key 不可用",
                "content": {"application/json": {"schema": error_schema}},
                "x-podi-errors": errors_by_status.get(
                    "401",
                    ["AUTHORIZATION_REQUIRED", "BUSINESS_API_KEY_INACTIVE", "BUSINESS_API_KEY_EXPIRED"],
                ),
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
            "503": {
                "description": "任务查询或依赖服务临时不可用，可稍后重试",
                "content": {"application/json": {"schema": error_schema}},
                "x-podi-errors": errors_by_status.get("503", ["BUSINESS_RUN_TEMPORARY_UNAVAILABLE"]),
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
            "VL_EVAL_IMAGE_REQUIRED",
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
        "403": ["BUSINESS_RUN_FORBIDDEN", "BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED"],
        "404": ["BUSINESS_RUN_NOT_FOUND"],
        "503": ["BUSINESS_RUN_TEMPORARY_UNAVAILABLE"],
    }
    submit_errors["403"] = [
        "BUSINESS_CLIENT_DISABLED",
        "BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED",
        "BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED",
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
            "description": "业务层稳定入口：花纹提取、图裂变、裂变生成图评估、扩图、任务查询。Coze 只需要调用这些扁平 API。",
        },
        "servers": [{"url": server}],
        "components": {
            "securitySchemes": {
                "BusinessApiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-PODI-API-Key",
                    "description": "业务方 API Key。当前先用于身份识别和调用审计，暂不强制限流。",
                },
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "也可使用 Authorization: Bearer <业务方 API Key 或平台 JWT>。",
                },
            }
        },
        "security": business_api_key_security,
        "paths": {
            "/api/business/pattern-extract/runs": {
                "post": {
                    "operationId": "podi_business_pattern_extract_run",
                    "summary": "PODI · 花纹提取",
                    "description": "提交花纹提取业务任务。业务方只需要传原图和可选提取要求，底层版本由中台路由。",
                    "security": business_api_key_security,
                    "requestBody": {"required": True, "content": {"application/json": {"schema": pattern_extract_submit_schema}}},
                    "responses": _business_responses(success_description="Business run", errors_by_status=submit_errors),
                }
            },
            "/api/business/fission/runs": {
                "post": {
                    "operationId": "podi_business_fission_run",
                    "summary": "PODI · 图裂变",
                    "description": "提交图裂变业务任务。业务方只需要传原图、提示词和可选参数，返回 runId 后轮询结果。",
                    "security": business_api_key_security,
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": fission_submit_schema, "examples": submit_examples}},
                    },
                    "x-codeSamples": [
                        {
                            "lang": "curl",
                            "label": "提交 GPT Image 2 + VL 控制版",
                            "source": "curl -X POST \"$PODI_BASE_URL/api/business/fission/runs\" \\\n  -H \"X-PODI-API-Key: $PODI_API_KEY\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"imageUrl\":\"https://example.com/input.png\",\"version\":\"gpt-image2-vl-v2\",\"variation_strength\":\"same_series\",\"quality\":\"preview\",\"size\":\"auto\",\"source\":\"partner-api\",\"channel\":\"open-api\",\"requestId\":\"biz-request-001\"}'",
                        }
                    ],
                    "responses": _business_responses(success_description="Business run", errors_by_status=submit_errors),
                }
            },
            "/api/business/fission-evaluate/runs": {
                "post": {
                    "operationId": "podi_business_fission_evaluate_run",
                    "summary": "PODI · 裂变生成图评估",
                    "description": "提交裂变生成图评估任务。输入原图和生成图，返回 runId 后轮询评分结论；该接口只评分，不自动二次裂变。",
                    "security": business_api_key_security,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": fission_evaluate_submit_schema,
                                "examples": fission_evaluate_examples,
                            }
                        },
                    },
                    "x-codeSamples": [
                        {
                            "lang": "curl",
                            "label": "提交裂变生成图评估",
                            "source": "curl -X POST \"$PODI_BASE_URL/api/business/fission-evaluate/runs\" \\\n  -H \"X-PODI-API-Key: $PODI_API_KEY\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"originalImageUrl\":\"https://example.com/original.png\",\"generatedImageUrl\":\"https://example.com/generated.png\",\"context\":{\"business\":\"fission\",\"version\":\"gpt-image2-vl-v2\"},\"source\":\"partner-api\",\"channel\":\"open-api\",\"requestId\":\"biz-request-eval-001\"}'",
                        }
                    ],
                    "responses": _business_responses(success_description="Business run", errors_by_status=submit_errors),
                }
            },
            "/api/business/outpaint/runs": {
                "post": {
                    "operationId": "podi_business_outpaint_run",
                    "summary": "PODI · 扩图",
                    "description": "提交扩图业务任务。宽高、上下左右扩展量从 inputs 传入，底层版本由中台路由。",
                    "security": business_api_key_security,
                    "requestBody": {"required": True, "content": {"application/json": {"schema": outpaint_submit_schema}}},
                    "responses": _business_responses(success_description="Business run", errors_by_status=submit_errors),
                }
            },
            "/api/business/pattern-extract/route-preview": {
                "post": {
                    "operationId": "podi_business_pattern_extract_route_preview",
                    "summary": "PODI · 花纹提取路由预览",
                    "description": "不提交真实任务，只预览当前 tenantId/clientId/grayKey 会命中哪个花纹提取版本，用于灰度验证。",
                    "security": business_api_key_security,
                    "requestBody": {"required": True, "content": {"application/json": {"schema": pattern_extract_route_preview_schema}}},
                    "responses": _route_preview_responses(errors_by_status=submit_errors),
                }
            },
            "/api/business/fission/route-preview": {
                "post": {
                    "operationId": "podi_business_fission_route_preview",
                    "summary": "PODI · 图裂变路由预览",
                    "description": "不提交真实任务，只预览当前 tenantId/clientId/grayKey 会命中哪个业务版本，用于灰度验证。",
                    "security": business_api_key_security,
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": fission_route_preview_schema, "examples": submit_examples}},
                    },
                    "responses": _route_preview_responses(errors_by_status=submit_errors),
                }
            },
            "/api/business/outpaint/route-preview": {
                "post": {
                    "operationId": "podi_business_outpaint_route_preview",
                    "summary": "PODI · 扩图路由预览",
                    "description": "不提交真实任务，只预览当前 tenantId/clientId/grayKey 会命中哪个业务版本，用于灰度验证。",
                    "security": business_api_key_security,
                    "requestBody": {"required": True, "content": {"application/json": {"schema": outpaint_route_preview_schema}}},
                    "responses": _route_preview_responses(errors_by_status=submit_errors),
                }
            },
            "/api/business/runs/get": {
                "post": {
                    "operationId": "podi_business_run_get",
                    "summary": "PODI · 查询业务任务",
                    "description": "默认返回轻量结果，字段与 Coze 轮询口径兼容。排障需要完整 routeInfo/steps/flowSummary 时传 detail=full 或 includeDebug=true。",
                    "security": business_api_key_security,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["runId"],
                                    "properties": {
                                        "runId": {"type": "string", "description": "业务任务 ID。"},
                                        "taskId": {
                                            "type": "string",
                                            "description": "兼容旧 Coze 轮询字段；业务 API 中等价于 runId。",
                                        },
                                        "detail": {
                                            "type": "string",
                                            "nullable": True,
                                            "enum": ["light", "full"],
                                            "description": "默认 light；传 full 返回完整排障字段。",
                                        },
                                        "includeDebug": {
                                            "type": "boolean",
                                            "nullable": True,
                                            "description": "true 时返回完整排障字段。",
                                        },
                                    },
                                },
                                "examples": run_get_examples,
                            }
                        },
                    },
                    "responses": _business_responses(
                        success_description="Business run",
                        errors_by_status=get_errors,
                        success_schema=run_query_response_schema,
                    ),
                }
            },
        },
    }


admin_router = APIRouter(prefix="/admin/business", dependencies=[Depends(require_admin)], tags=["admin-business"])


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


@admin_router.get("/api-keys", response_model=schemas.BusinessApiKeyListResponse, response_model_by_alias=False)
def admin_list_business_api_keys(
    status: str | None = Query(default=None),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessApiKeyListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    with get_session() as session:
        stmt = select(ApiKey).where(ApiKey.provider == "business_api").order_by(ApiKey.created_at.desc())
        if status:
            stmt = stmt.where(ApiKey.status == status)
        rows = session.execute(stmt).scalars().all()
        return schemas.BusinessApiKeyListResponse(items=[_business_api_key_to_read(row) for row in rows])


@admin_router.post("/api-keys", response_model=schemas.BusinessApiKeyRead, response_model_by_alias=False)
def admin_create_business_api_key(
    payload: schemas.BusinessApiKeyCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessApiKeyRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    with get_session() as session:
        existing = (
            session.execute(
                select(ApiKey).where(
                    ApiKey.provider == "business_api",
                    ApiKey.key == payload.key,
                )
            )
            .scalars()
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="BUSINESS_API_KEY_DUPLICATED")
        api_key = ApiKey(
            id=(payload.id or uuid4().hex),
            provider="business_api",
            name=payload.name,
            key=payload.key,
            status=payload.status,
            expire_at=payload.expireAt,
            extra_metadata=_business_api_key_metadata(
                tenant_id=payload.tenantId,
                client_id=payload.clientId,
                allowed_business_keys=payload.allowedBusinessKeys,
                metadata=payload.metadata,
            ),
        )
        session.add(api_key)
        session.commit()
        session.refresh(api_key)
        return _business_api_key_to_read(api_key)


@admin_router.patch("/api-keys/{key_id}", response_model=schemas.BusinessApiKeyRead, response_model_by_alias=False)
def admin_update_business_api_key(
    key_id: str,
    payload: schemas.BusinessApiKeyUpdateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessApiKeyRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    with get_session() as session:
        api_key = session.get(ApiKey, key_id)
        if not api_key or api_key.provider != "business_api":
            raise HTTPException(status_code=404, detail="BUSINESS_API_KEY_NOT_FOUND")
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and payload.name is not None:
            api_key.name = payload.name
        if "key" in data and payload.key is not None:
            api_key.key = payload.key
        if "status" in data and payload.status is not None:
            api_key.status = payload.status
        if "expireAt" in data or "expire_at" in data:
            api_key.expire_at = payload.expireAt
        if any(key in data for key in ("tenantId", "tenant_id", "clientId", "client_id", "allowedBusinessKeys", "allowed_business_keys", "metadata")):
            api_key.extra_metadata = _business_api_key_metadata(
                tenant_id=payload.tenantId,
                client_id=payload.clientId,
                allowed_business_keys=payload.allowedBusinessKeys,
                metadata=payload.metadata if payload.metadata is not None else api_key.extra_metadata,
            )
        session.add(api_key)
        session.commit()
        session.refresh(api_key)
        return _business_api_key_to_read(api_key)


@admin_router.get(
    "/api-key-usage",
    response_model=schemas.BusinessApiKeyUsageLogListResponse,
    response_model_by_alias=False,
)
def admin_list_business_api_key_usage(
    api_key_id: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessApiKeyUsageLogListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    with get_session() as session:
        stmt = select(BusinessApiKeyUsageLog)
        filters = []
        if api_key_id:
            filters.append(BusinessApiKeyUsageLog.api_key_id == api_key_id)
        if business_key:
            filters.append(BusinessApiKeyUsageLog.business_key == business_key)
        if tenant_id:
            filters.append(BusinessApiKeyUsageLog.tenant_id == tenant_id)
        if client_id:
            filters.append(BusinessApiKeyUsageLog.client_id == client_id)
        if filters:
            stmt = stmt.where(*filters)
        rows = session.execute(stmt.order_by(BusinessApiKeyUsageLog.created_at.desc()).limit(limit)).scalars().all()
        return schemas.BusinessApiKeyUsageLogListResponse(items=rows, total=len(rows))


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
