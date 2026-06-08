"""Business-facing API over PODI atomic abilities."""

from __future__ import annotations

from copy import deepcopy
import csv
import io
import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, case, func, or_, select

from app.constants.business_api_contract import (
    BUSINESS_ROUTE_SELECTED_BY_VALUES,
    BUSINESS_ROUTE_SELECTED_STATUS_VALUES,
    BUSINESS_TASK_STATUS_VALUES,
    COMFYUI_FISSION_PROFILE_VALUES,
    COMFYUI_FISSION_VARIATION_PRESET_VALUES,
    FISSION_PATTERN_RISK_TYPE_VALUES,
    GPT_IMAGE2_QUALITY_VALUES,
    GPT_IMAGE2_SIZE_VALUES,
    GPT_IMAGE2_VARIATION_STRENGTH_VALUES,
    IMAGE_EDIT_CUSTOM_SIZE_CONSTRAINTS,
    IMAGE_EDIT_OUTPUT_FORMAT_VALUES,
    IMAGE_EDIT_QUALITY_VALUES,
    IMAGE_EDIT_SIZE_VALUES,
    IMAGE_EDIT_SKILL_VALUES,
    PRODUCT_DESIGN_PRODUCT_TYPE_VALUES,
    PRODUCT_DESIGN_SCENE_VALUES,
    business_api_contract_payload,
)
from app.constants.business_components import business_component_catalog_payload
from app.core.config import get_settings
from app.core.db import get_session
from app.deps.auth import get_current_user, require_admin
from app.deps.internal import is_internal_request
from app.models.integration import ApiKey, BusinessApiKeyUsageLog, BusinessRun
from app.models.user import User
from app.schemas import business as schemas
from app.services.business_agents import AGENT_BUSINESS_KEY, get_business_agent_service
from app.services.auth_service import auth_service
from app.services.business_projects import get_business_project_service
from app.services.business_runs import get_business_run_service
from app.services.runtime_safety import suppress_background_threads_for_tests


router = APIRouter(prefix="/api/business", tags=["business"])
bearer_scheme = HTTPBearer(auto_error=False)
BUSINESS_API_KEY_PROVIDERS = {"business_api", "podi_business_api"}
logger = logging.getLogger(__name__)
BUSINESS_ADMIN_READ_CACHE_TTL_SECONDS = 12
BUSINESS_ADMIN_READ_CACHE_MAX_ITEMS = 96
_BUSINESS_ADMIN_READ_CACHE_LOCK = threading.RLock()
_BUSINESS_ADMIN_READ_CACHE: dict[tuple[Any, ...], tuple[float, Any]] = {}


def _business_admin_read_cache_enabled() -> bool:
    return not suppress_background_threads_for_tests()


def _business_admin_read_cache_key(*parts: Any) -> tuple[Any, ...]:
    return tuple("" if part is None else part for part in parts)


def _business_admin_read_cached(key: tuple[Any, ...], producer) -> Any:
    if not _business_admin_read_cache_enabled():
        return producer()
    now = time.monotonic()
    with _BUSINESS_ADMIN_READ_CACHE_LOCK:
        cached = _BUSINESS_ADMIN_READ_CACHE.get(key)
        if cached and cached[0] > now:
            return deepcopy(cached[1])

    value = producer()
    with _BUSINESS_ADMIN_READ_CACHE_LOCK:
        if len(_BUSINESS_ADMIN_READ_CACHE) >= BUSINESS_ADMIN_READ_CACHE_MAX_ITEMS:
            oldest_key = min(_BUSINESS_ADMIN_READ_CACHE.items(), key=lambda item: item[1][0])[0]
            _BUSINESS_ADMIN_READ_CACHE.pop(oldest_key, None)
        _BUSINESS_ADMIN_READ_CACHE[key] = (
            time.monotonic() + BUSINESS_ADMIN_READ_CACHE_TTL_SECONDS,
            deepcopy(value),
        )
    return value


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


def _business_structured_result_payload(full: dict[str, Any], texts: list[Any]) -> dict[str, Any] | None:
    result_payload = full.get("resultPayload")
    if isinstance(result_payload, dict) and result_payload:
        if any(key in result_payload for key in ("decision", "score", "problem_tags", "next_action")):
            return result_payload
        payload_texts = result_payload.get("texts")
        if isinstance(payload_texts, list) and payload_texts:
            parsed = _parse_json_object_text(payload_texts[0])
            if parsed:
                return parsed
        return result_payload
    if texts:
        parsed = _parse_json_object_text(texts[0])
        if parsed:
            return parsed
    return None


def _business_run_full_response(run: dict[str, Any]) -> dict[str, Any]:
    return schemas.BusinessRunRead.model_validate(run).model_dump(mode="json", by_alias=False)


def _business_run_light_response(run: dict[str, Any]) -> dict[str, Any]:
    full = _business_run_full_response(run)
    status = _normalize_business_task_status(full.get("status"))
    image_urls = full.get("imageUrls") if isinstance(full.get("imageUrls"), list) else []
    video_urls = full.get("videoUrls") if isinstance(full.get("videoUrls"), list) else []
    texts = full.get("texts") if isinstance(full.get("texts"), list) else []
    business_key = str(full.get("businessKey") or full.get("business_key") or "").strip()
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
        "expectedImageCount": 1 if business_key in {"fission", "image_edit", "product_design", "text_fission", "pattern_extract", "outpaint"} else None,
        "logId": full.get("abilityLogId"),
        "traceId": full.get("traceId"),
        "requestId": full.get("requestId"),
        "durationMs": full.get("durationMs"),
        "createdAt": full.get("createdAt"),
        "startedAt": full.get("startedAt"),
        "finishedAt": full.get("finishedAt"),
    }
    result_payload = _business_structured_result_payload(full, texts)
    if not image_urls and not video_urls and isinstance(result_payload, dict) and result_payload:
        result["resultPayload"] = _compact_business_payload(result_payload)
    return result


def _business_run_submit_response(run: dict[str, Any]) -> dict[str, Any]:
    full = _business_run_full_response(run)
    status = _normalize_business_task_status(full.get("status"))
    error_message = str(full.get("errorMessage") or full.get("error") or "").strip() or None
    return {
        "runId": full.get("runId") or full.get("id"),
        "taskId": full.get("taskId"),
        "businessKey": full.get("businessKey"),
        "version": full.get("version"),
        "status": status,
        "taskStatus": status,
        "traceId": full.get("traceId"),
        "requestId": full.get("requestId"),
        "debugUrl": full.get("debugUrl"),
        "debugResponse": error_message,
        "retryAfterSeconds": 10 if status in {"queued", "running"} else None,
        "error": error_message,
        "errorMessage": error_message,
        "errorCode": _business_error_code(error_message),
        "createdAt": full.get("createdAt"),
    }


def _get_business_run_response(
    *,
    run_id: str,
    request: Request,
    user: User,
    full_detail: bool = False,
    request_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        result = get_business_run_service().get_run(run_id=run_id, user=user)
    except HTTPException as exc:
        _record_business_api_key_usage(
            request,
            status_code=exc.status_code,
            run_id=run_id,
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    except Exception:
        _record_business_api_key_usage(
            request,
            status_code=500,
            run_id=run_id,
            error_code="BUSINESS_RUN_GET_FAILED",
            request_payload=request_payload,
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


def _business_output_reviews_to_csv(items: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "batch_id",
            "业务",
            "样例 Key",
            "样例名称",
            "run_id",
            "版本 ID",
            "版本",
            "输出序号",
            "质量档位",
            "下一步动作",
            "输入标签",
            "问题标签",
            "输出 URL",
            "备注",
            "标注人",
            "创建时间",
            "更新时间",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item.get("batch_id") or "",
                item.get("business_key") or "",
                item.get("sample_key") or "",
                item.get("sample_label") or "",
                item.get("run_id") or "",
                item.get("business_version_id") or "",
                item.get("version") or "",
                item.get("output_index") if item.get("output_index") is not None else "",
                item.get("quality_grade") or "",
                item.get("next_action") or "",
                "、".join(str(tag) for tag in item.get("input_tags") or []),
                "、".join(str(tag) for tag in item.get("issue_tags") or []),
                item.get("output_url") or "",
                item.get("note") or "",
                item.get("reviewer_username") or item.get("reviewer_user_id") or "",
                _business_export_cell(item.get("created_at")),
                _business_export_cell(item.get("updated_at")),
            ]
        )
    return output.getvalue()


def _business_api_usage_endpoint_kind(*, method: str | None, path: str | None) -> str:
    normalized_path = str(path or "")
    normalized_method = str(method or "").upper()
    if normalized_path == "/api/business/runs/get":
        return "poll"
    if "callback" in normalized_path:
        return "callback"
    if (
        normalized_method == "POST"
        and normalized_path.endswith("/confirm")
        and (
            normalized_path.startswith("/api/business/image-edit-chat/sessions/")
            or normalized_path.startswith("/api/business/agents/image-edit/sessions/")
        )
    ):
        return "submit"
    if normalized_method == "POST" and normalized_path.endswith("/runs"):
        return "submit"
    return "other"


def _business_api_usage_group_issue(
    *,
    submit_count: int,
    poll_count: int,
    error_count: int,
) -> tuple[bool, str | None, str | None]:
    if error_count > 0:
        return True, "HAS_ERROR", "该任务链路存在异常响应或错误码，请优先查看最后错误。"
    if poll_count > 0 and submit_count == 0:
        return True, "POLL_WITHOUT_SUBMIT", "当前筛选范围内只有结果查询记录，未看到提交记录；可放宽时间窗口或核对 runId。"
    if poll_count >= 30:
        return True, "POLLING_TOO_FREQUENT", "同一 runId 查询次数偏多，建议业务方按 retryAfterSeconds 控制轮询频率。"
    return False, None, None


def _business_api_key_usage_to_csv(items: list[BusinessApiKeyUsageLog]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "时间",
            "接口动作",
            "方法",
            "路径",
            "状态码",
            "业务",
            "run_id",
            "request_id",
            "trace_id",
            "Key 名称",
            "Key 脱敏",
            "租户",
            "客户端",
            "错误码",
            "耗时 ms",
            "IP",
            "User-Agent",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item.id,
                item.created_at.isoformat(sep=" ") if item.created_at else "",
                _business_api_usage_endpoint_kind(method=item.method, path=item.path),
                item.method,
                item.path,
                item.status_code or "",
                item.business_key or "",
                item.run_id or "",
                item.request_id or "",
                item.trace_id or "",
                item.api_key_name or "",
                item.api_key_preview or "",
                item.tenant_id or "",
                item.client_id or "",
                item.error_code or "",
                item.duration_ms if item.duration_ms is not None else "",
                item.ip_address or "",
                item.user_agent or "",
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
        _ensure_business_usage_context(request, auth_type="service_token", api_key_name="服务令牌")
        return auth_service.build_service_user()
    api_key_user = _resolve_business_api_key_user(request, token)
    if api_key_user is not None:
        return api_key_user
    if token:
        user = get_current_user(request=request, credentials=credentials)  # type: ignore[arg-type]
        _ensure_business_usage_context(
            request,
            auth_type="platform_jwt",
            api_key_name="平台登录",
            tenant_id=getattr(user, "tenant_id", None),
            client_id=getattr(user, "client_id", None),
        )
        return user
    if _is_internal_request(request):
        _ensure_business_usage_context(request, auth_type="internal_request", api_key_name="内部请求")
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


def _ensure_business_usage_context(
    request: Request,
    *,
    auth_type: str,
    api_key_id: str | None = None,
    api_key_name: str | None = None,
    api_key_preview: str | None = None,
    tenant_id: str | None = None,
    client_id: str | None = None,
    allowed_business_keys: list[str] | str | None = None,
) -> None:
    if isinstance(getattr(request.state, "business_api_key_context", None), dict):
        return
    request.state.business_api_key_context = {
        "apiKeyId": api_key_id,
        "apiKeyName": api_key_name,
        "apiKeyPreview": api_key_preview,
        "tenantId": tenant_id,
        "clientId": client_id,
        "allowedBusinessKeys": allowed_business_keys or [],
        "authType": auth_type,
        "startedAt": time.perf_counter(),
    }


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


def _usage_log_text(value: Any, *, max_length: int) -> str | None:
    text = str(value or "").strip()
    return text[:max_length] or None


def _record_business_api_key_usage(
    request: Request,
    *,
    status_code: int,
    business_key: str | None = None,
    run: Any | None = None,
    run_id: str | None = None,
    error_code: str | None = None,
    request_payload: dict[str, Any] | None = None,
) -> None:
    context = getattr(request.state, "business_api_key_context", None)
    if not isinstance(context, dict):
        return
    payload = run if isinstance(run, dict) else {}
    request_payload = request_payload if isinstance(request_payload, dict) else {}
    resolved_run_id = _usage_log_text(run_id or payload.get("id") or payload.get("runId"), max_length=64)
    request_id = _usage_log_text(
        payload.get("request_id")
        or payload.get("requestId")
        or request_payload.get("request_id")
        or request_payload.get("requestId")
        or "",
        max_length=64,
    )
    trace_id = _usage_log_text(
        payload.get("trace_id")
        or payload.get("traceId")
        or request_payload.get("trace_id")
        or request_payload.get("traceId")
        or "",
        max_length=64,
    )
    tenant_id = _usage_log_text(
        payload.get("tenant_id")
        or payload.get("tenantId")
        or request_payload.get("tenant_id")
        or request_payload.get("tenantId")
        or context.get("tenantId")
        or "",
        max_length=64,
    )
    client_id = _usage_log_text(
        payload.get("client_id")
        or payload.get("clientId")
        or request_payload.get("client_id")
        or request_payload.get("clientId")
        or context.get("clientId")
        or "",
        max_length=64,
    )
    duration_ms = None
    started_at = context.get("startedAt")
    if isinstance(started_at, (int, float)):
        duration_ms = max(0, int((time.perf_counter() - started_at) * 1000))
    try:
        with get_session() as session:
            session.add(
                BusinessApiKeyUsageLog(
                    api_key_id=_usage_log_text(context.get("apiKeyId"), max_length=64),
                    api_key_name=_usage_log_text(context.get("apiKeyName"), max_length=128),
                    api_key_preview=_usage_log_text(context.get("apiKeyPreview"), max_length=32),
                    method=request.method[:16],
                    path=request.url.path[:256],
                    status_code=status_code,
                    business_key=_usage_log_text(
                        business_key or payload.get("business_key") or payload.get("businessKey"),
                        max_length=64,
                    ),
                    run_id=resolved_run_id,
                    request_id=request_id,
                    trace_id=trace_id,
                    tenant_id=tenant_id,
                    client_id=client_id,
                    error_code=_usage_log_text(error_code, max_length=128),
                    duration_ms=duration_ms,
                    ip_address=_usage_log_text(_client_ip(request), max_length=64),
                    user_agent=_usage_log_text(request.headers.get("user-agent"), max_length=255),
                    created_at=datetime.utcnow(),
                )
            )
            session.commit()
    except Exception as exc:  # pragma: no cover - diagnostic logging must not mask business responses
        logger.warning(
            "business api usage log skipped: %s path=%s status=%s request_id=%s",
            exc,
            request.url.path,
            status_code,
            request_id,
        )


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


def _business_agent_allowed_for_api_key(request: Request) -> None:
    context = getattr(request.state, "business_api_key_context", None)
    if not isinstance(context, dict):
        return
    allowed = context.get("allowedBusinessKeys")
    if not allowed:
        return
    raw_allowed = allowed.split(",") if isinstance(allowed, str) else allowed
    allowed_set = {str(item).strip() for item in raw_allowed if str(item).strip()}
    if allowed_set and not ({"image_edit_chat", "agent_image_edit", "image_edit"} & allowed_set):
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
) -> dict[str, Any]:
    try:
        _business_key_allowed_for_api_key(request, business_key)
        result = get_business_run_service().create_run(business_key=business_key, payload=payload, user=user)
    except HTTPException as exc:
        _record_business_api_key_usage(
            request,
            status_code=exc.status_code,
            business_key=business_key,
            error_code=str(exc.detail or ""),
            request_payload=payload.model_dump(exclude_none=True),
        )
        raise
    except Exception:
        _record_business_api_key_usage(
            request,
            status_code=500,
            business_key=business_key,
            error_code="BUSINESS_RUN_CREATE_FAILED",
            request_payload=payload.model_dump(exclude_none=True),
        )
        raise
    _record_business_api_key_usage(request, status_code=200, business_key=business_key, run=result)
    return _business_run_submit_response(result)


def _record_project_api_usage(
    request: Request,
    *,
    status_code: int,
    error_code: str | None = None,
    request_payload: dict[str, Any] | None = None,
) -> None:
    _record_business_api_key_usage(
        request,
        status_code=status_code,
        business_key="project_context",
        error_code=error_code,
        request_payload=request_payload,
    )


def _preview_business_route_with_usage(
    *,
    request: Request,
    business_key: str,
    payload: schemas.BusinessRunCreateRequest,
    user: User,
) -> schemas.BusinessRoutePreviewResponse:
    request_payload = payload.model_dump(exclude_none=True)
    try:
        _business_key_allowed_for_api_key(request, business_key)
        result = get_business_run_service().preview_route(business_key=business_key, payload=payload, user=user)
    except HTTPException as exc:
        _record_business_api_key_usage(
            request,
            status_code=exc.status_code,
            business_key=business_key,
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    except Exception:
        _record_business_api_key_usage(
            request,
            status_code=500,
            business_key=business_key,
            error_code="BUSINESS_ROUTE_PREVIEW_FAILED",
            request_payload=request_payload,
        )
        raise
    _record_business_api_key_usage(
        request,
        status_code=200,
        business_key=business_key,
        request_payload=request_payload,
    )
    return result


@router.get("/capabilities", response_model=schemas.BusinessCapabilityListResponse, response_model_by_alias=False)
def list_business_capabilities(
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityListResponse:
    _ = user
    items = get_business_run_service().list_capabilities()
    return schemas.BusinessCapabilityListResponse(items=items)


@router.post("/fission/runs", response_model=dict[str, Any], response_model_by_alias=False)
def create_fission_run(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    return _create_business_run_with_usage(request=request, business_key="fission", payload=payload, user=user)


@router.post("/text-fission/prompts", response_model=schemas.TextFissionPromptResponse, response_model_by_alias=False)
def prepare_text_fission_prompt(
    payload: schemas.TextFissionPromptRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    request_payload = payload.model_dump(exclude_none=True)
    _business_key_allowed_for_api_key(request, "text_fission")
    try:
        result = get_business_run_service().prepare_text_fission_prompt(payload=payload, user=user)
    except HTTPException as exc:
        _record_business_api_key_usage(
            request,
            status_code=exc.status_code,
            business_key="text_fission",
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    _record_business_api_key_usage(
        request,
        status_code=200,
        business_key="text_fission",
        request_payload=request_payload,
    )
    return result


@router.post("/text-fission/runs", response_model=dict[str, Any], response_model_by_alias=False)
def create_text_fission_run(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    return _create_business_run_with_usage(request=request, business_key="text_fission", payload=payload, user=user)


@router.post("/fission-evaluate/runs", response_model=dict[str, Any], response_model_by_alias=False)
@router.post("/fission/evaluate/runs", response_model=dict[str, Any], response_model_by_alias=False)
def create_fission_evaluate_run(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    return _create_business_run_with_usage(request=request, business_key="fission_evaluate", payload=payload, user=user)


@router.post("/outpaint/runs", response_model=dict[str, Any], response_model_by_alias=False)
def create_outpaint_run(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    return _create_business_run_with_usage(request=request, business_key="outpaint", payload=payload, user=user)


@router.post("/image-edit/runs", response_model=dict[str, Any], response_model_by_alias=False)
def create_image_edit_run(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    return _create_business_run_with_usage(request=request, business_key="image_edit", payload=payload, user=user)


@router.post("/product-design/runs", response_model=dict[str, Any], response_model_by_alias=False)
def create_product_design_run(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    return _create_business_run_with_usage(request=request, business_key="product_design", payload=payload, user=user)


@router.get("/image-edit/component-config", response_model=dict[str, Any], response_model_by_alias=False)
def get_image_edit_component_config(
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    _ = user
    _business_key_allowed_for_api_key(request, "image_edit")
    payload = {
        "businessKey": "image_edit",
        "businessName": "图编辑",
        "defaultVersion": "gpt-image2-editor-v1",
        "component": {
            "type": "image-edit-workbench",
            "componentVersion": "2026.05.25-v1",
            "configVersion": 2,
            "minSourceComponentVersion": "2026.05.25-v1",
            "hostedMode": True,
            "sourceMode": True,
            "auth": "business_api_key",
            "hostedPath": "/image-edit",
            "title": "图编辑",
            "defaultSkill": "local_modify",
            "defaultSize": "auto",
            "defaultQuality": "auto",
        },
        "updatePolicy": {
            "recommended": "hosted",
            "hosted": "业务方使用中台托管页时，中台发版后自动获得最新交互和能力配置。",
            "source": "业务方源码集成时，应启动时读取 component-config，不要硬编码技能、尺寸、质量、输出格式和文案。",
            "configurableKeys": ["skills", "outpaint", "sizes", "customSizeConstraints", "qualityLevels", "outputFormats", "copy"],
            "breakingChange": "涉及 selectionHints/mask/referenceImages 等协议结构变化时，会升级 componentVersion，并需要业务方更新源码组件。",
        },
        "skills": [
            {
                "value": "local_modify",
                "label": "局部修改",
                "description": "对主图中指定对象或区域做小范围改动。",
                "requiresReference": False,
                "requiresTargetHint": False,
            },
            {
                "value": "reference_element_transfer",
                "label": "参考图替换",
                "description": "用参考图的对象、材质或风格替换主图指定区域。",
                "requiresReference": True,
                "requiresTargetHint": False,
            },
            {
                "value": "remove_inpaint",
                "label": "删除修补",
                "description": "删除指定对象并补齐背景。",
                "requiresReference": False,
                "requiresTargetHint": True,
            },
            {
                "value": "color_reference_correction",
                "label": "补色校正",
                "description": "按参考图修正主图局部或整体颜色关系。",
                "requiresReference": True,
                "requiresTargetHint": False,
            },
            {
                "value": "canvas_outpaint",
                "label": "扩展画布",
                "description": "把原图放进更大的目标画布，只让模型补全外扩区域。",
                "requiresReference": False,
                "requiresTargetHint": False,
            },
        ],
        "outpaint": {
            "defaultExpand": 256,
            "rounding": "向上取整到 16 的倍数",
            "preserveOriginalDefault": True,
            "anchors": ["center", "left", "right", "top", "bottom", "top_left", "top_right", "bottom_left", "bottom_right", "custom"],
        },
        "sizes": [
            {"value": "auto", "label": "跟随原图/自动", "costLevel": "normal"},
            {"value": "1024x1024", "label": "1K 方图", "costLevel": "normal"},
            {"value": "1536x1024", "label": "1K 横图", "costLevel": "normal"},
            {"value": "1024x1536", "label": "1K 竖图", "costLevel": "normal"},
            {"value": "2048x2048", "label": "2K 方图", "costLevel": "high"},
            {"value": "2048x1152", "label": "2K 横图", "costLevel": "high"},
            {"value": "3840x2160", "label": "4K 横图", "costLevel": "very_high"},
            {"value": "2160x3840", "label": "4K 竖图", "costLevel": "very_high"},
        ],
        "customSizeConstraints": IMAGE_EDIT_CUSTOM_SIZE_CONSTRAINTS,
        "qualityLevels": [
            {"value": "auto", "label": "自动"},
            {"value": "preview", "label": "快速预览"},
            {"value": "production", "label": "正式候选"},
            {"value": "premium", "label": "高质量"},
        ],
        "outputFormats": IMAGE_EDIT_OUTPUT_FORMAT_VALUES,
        "copy": {
            "instructionPlaceholder": "例如：把左侧杯子改成蓝色陶瓷材质，保持背景和光照不变。",
            "maskHint": "蒙版只允许一个最终 alpha mask，多次涂抹请在组件内合并。",
            "referenceHint": "参考图只在技能需要或用户明确引用时传入模型。",
        },
    }
    _record_business_api_key_usage(request, status_code=200, business_key="image_edit", request_payload={"config": True})
    return payload


@router.post(
    "/image-edit-chat/sessions",
    response_model=dict[str, Any],
    response_model_by_alias=False,
)
@router.post(
    "/agents/image-edit/sessions",
    response_model=dict[str, Any],
    response_model_by_alias=False,
)
def create_image_edit_agent_session(
    payload: schemas.BusinessAgentSessionCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    request_payload = payload.model_dump(exclude_none=True)
    try:
        _business_agent_allowed_for_api_key(request)
        result = get_business_agent_service().create_session(payload, user=user)
    except HTTPException as exc:
        _record_business_api_key_usage(
            request,
            status_code=exc.status_code,
            business_key=AGENT_BUSINESS_KEY,
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    except Exception:
        _record_business_api_key_usage(
            request,
            status_code=500,
            business_key=AGENT_BUSINESS_KEY,
            error_code="AGENT_SESSION_CREATE_FAILED",
            request_payload=request_payload,
        )
        raise
    _record_business_api_key_usage(request, status_code=200, business_key=AGENT_BUSINESS_KEY, request_payload=request_payload)
    return result


@router.get(
    "/image-edit-chat/sessions/{session_id}",
    response_model=schemas.BusinessAgentSessionResponse,
    response_model_by_alias=False,
)
@router.get(
    "/agents/image-edit/sessions/{session_id}",
    response_model=schemas.BusinessAgentSessionResponse,
    response_model_by_alias=False,
)
def get_image_edit_agent_session(
    session_id: str,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    try:
        _business_agent_allowed_for_api_key(request)
        session = get_business_agent_service().get_session(session_id, user=user)
    except HTTPException as exc:
        _record_business_api_key_usage(
            request,
            status_code=exc.status_code,
            business_key=AGENT_BUSINESS_KEY,
            error_code=str(exc.detail or ""),
        )
        raise
    _record_business_api_key_usage(request, status_code=200, business_key=AGENT_BUSINESS_KEY)
    return {"session": session}


@router.post(
    "/image-edit-chat/sessions/{session_id}/messages",
    response_model=schemas.BusinessAgentPlanResponse,
    response_model_by_alias=False,
)
@router.post(
    "/agents/image-edit/sessions/{session_id}/messages",
    response_model=schemas.BusinessAgentPlanResponse,
    response_model_by_alias=False,
)
def send_image_edit_agent_message(
    session_id: str,
    payload: schemas.BusinessAgentMessageRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    request_payload = payload.model_dump(exclude_none=True)
    try:
        _business_agent_allowed_for_api_key(request)
        result = get_business_agent_service().send_message(session_id, payload, user=user)
    except HTTPException as exc:
        _record_business_api_key_usage(
            request,
            status_code=exc.status_code,
            business_key=AGENT_BUSINESS_KEY,
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    except Exception:
        _record_business_api_key_usage(
            request,
            status_code=500,
            business_key=AGENT_BUSINESS_KEY,
            error_code="AGENT_MESSAGE_FAILED",
            request_payload=request_payload,
        )
        raise
    _record_business_api_key_usage(request, status_code=200, business_key=AGENT_BUSINESS_KEY, request_payload=request_payload)
    return result


@router.post(
    "/image-edit-chat/sessions/{session_id}/plans/{plan_id}/confirm",
    response_model=schemas.BusinessAgentConfirmResponse,
    response_model_by_alias=False,
)
@router.post(
    "/agents/image-edit/sessions/{session_id}/plans/{plan_id}/confirm",
    response_model=schemas.BusinessAgentConfirmResponse,
    response_model_by_alias=False,
)
def confirm_image_edit_agent_plan(
    session_id: str,
    plan_id: str,
    payload: schemas.BusinessAgentConfirmRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    request_payload = payload.model_dump(exclude_none=True)
    try:
        _business_agent_allowed_for_api_key(request)
        result = get_business_agent_service().confirm_plan(session_id, plan_id, payload, user=user)
    except HTTPException as exc:
        _record_business_api_key_usage(
            request,
            status_code=exc.status_code,
            business_key=AGENT_BUSINESS_KEY,
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    except Exception:
        _record_business_api_key_usage(
            request,
            status_code=500,
            business_key=AGENT_BUSINESS_KEY,
            error_code="AGENT_PLAN_CONFIRM_FAILED",
            request_payload=request_payload,
        )
        raise
    run_payload = result.get("run") if isinstance(result, dict) else {}
    _record_business_api_key_usage(
        request,
        status_code=200,
        business_key=AGENT_BUSINESS_KEY,
        run_id=str(run_payload.get("runId") or "") or None,
        request_payload=request_payload,
    )
    return result


@router.post(
    "/image-edit-chat/sessions/{session_id}/confirm",
    response_model=schemas.BusinessAgentConfirmResponse,
    response_model_by_alias=False,
)
def confirm_image_edit_chat_latest_plan(
    session_id: str,
    payload: schemas.BusinessAgentConfirmRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    request_payload = payload.model_dump(exclude_none=True)
    try:
        _business_agent_allowed_for_api_key(request)
        result = get_business_agent_service().confirm_latest_plan(session_id, payload, user=user)
    except HTTPException as exc:
        _record_business_api_key_usage(
            request,
            status_code=exc.status_code,
            business_key=AGENT_BUSINESS_KEY,
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    except Exception:
        _record_business_api_key_usage(
            request,
            status_code=500,
            business_key=AGENT_BUSINESS_KEY,
            error_code="AGENT_PLAN_CONFIRM_FAILED",
            request_payload=request_payload,
        )
        raise
    run_payload = result.get("run") if isinstance(result, dict) else {}
    _record_business_api_key_usage(
        request,
        status_code=200,
        business_key=AGENT_BUSINESS_KEY,
        run_id=str(run_payload.get("runId") or "") or None,
        request_payload=request_payload,
    )
    return result


@router.post("/projects", response_model=schemas.BusinessProjectRead, response_model_by_alias=False)
def create_business_project(
    payload: schemas.BusinessProjectCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessProjectRead:
    request_payload = payload.model_dump(exclude_none=True)
    try:
        result = get_business_project_service().create_project(payload, user=user)
    except HTTPException as exc:
        _record_project_api_usage(
            request,
            status_code=exc.status_code,
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    _record_project_api_usage(request, status_code=200, request_payload=request_payload)
    return result


@router.get("/projects", response_model=schemas.BusinessProjectListResponse, response_model_by_alias=False)
def list_business_projects(
    request: Request,
    scenario: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessProjectListResponse:
    total, items = get_business_project_service().list_projects(
        user=user,
        scenario=scenario,
        status=status,
        limit=limit,
        offset=offset,
    )
    _record_project_api_usage(request, status_code=200)
    return schemas.BusinessProjectListResponse(total=total, items=items)


@router.get("/projects/{project_id}", response_model=schemas.BusinessProjectDetailResponse, response_model_by_alias=False)
def get_business_project(
    project_id: str,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessProjectDetailResponse:
    try:
        result = get_business_project_service().get_project_detail(project_id, user=user)
    except HTTPException as exc:
        _record_project_api_usage(request, status_code=exc.status_code, error_code=str(exc.detail or ""))
        raise
    _record_project_api_usage(request, status_code=200)
    return result


@router.patch("/projects/{project_id}", response_model=schemas.BusinessProjectRead, response_model_by_alias=False)
def update_business_project(
    project_id: str,
    payload: schemas.BusinessProjectUpdateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessProjectRead:
    request_payload = payload.model_dump(exclude_none=True)
    try:
        result = get_business_project_service().update_project(project_id, payload, user=user)
    except HTTPException as exc:
        _record_project_api_usage(
            request,
            status_code=exc.status_code,
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    _record_project_api_usage(request, status_code=200, request_payload=request_payload)
    return result


@router.post(
    "/projects/{project_id}/assets",
    response_model=schemas.BusinessProjectAssetRead,
    response_model_by_alias=False,
)
def create_business_project_asset(
    project_id: str,
    payload: schemas.BusinessProjectAssetCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessProjectAssetRead:
    request_payload = payload.model_dump(exclude_none=True)
    try:
        result = get_business_project_service().create_asset(project_id, payload, user=user)
    except HTTPException as exc:
        _record_project_api_usage(
            request,
            status_code=exc.status_code,
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    _record_project_api_usage(request, status_code=200, request_payload=request_payload)
    return result


@router.get(
    "/projects/{project_id}/assets",
    response_model=schemas.BusinessProjectAssetListResponse,
    response_model_by_alias=False,
)
def list_business_project_assets(
    project_id: str,
    request: Request,
    asset_type: str | None = Query(default=None),
    selected: bool | None = Query(default=None),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessProjectAssetListResponse:
    total, items = get_business_project_service().list_assets(
        project_id,
        user=user,
        asset_type=asset_type,
        selected=selected,
    )
    _record_project_api_usage(request, status_code=200)
    return schemas.BusinessProjectAssetListResponse(total=total, items=items)


@router.get(
    "/projects/{project_id}/runs",
    response_model=schemas.BusinessProjectRunLinkListResponse,
    response_model_by_alias=False,
)
def list_business_project_runs(
    project_id: str,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessProjectRunLinkListResponse:
    total, items = get_business_project_service().list_project_runs(project_id, user=user)
    _record_project_api_usage(request, status_code=200)
    return schemas.BusinessProjectRunLinkListResponse(total=total, items=items)


@router.post(
    "/projects/{project_id}/selections",
    response_model=list[schemas.BusinessProjectSelectionRead],
    response_model_by_alias=False,
)
def create_business_project_selection(
    project_id: str,
    payload: schemas.BusinessProjectSelectionCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> list[schemas.BusinessProjectSelectionRead]:
    request_payload = payload.model_dump(exclude_none=True)
    try:
        result = get_business_project_service().create_selection(project_id, payload, user=user)
    except HTTPException as exc:
        _record_project_api_usage(
            request,
            status_code=exc.status_code,
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    _record_project_api_usage(request, status_code=200, request_payload=request_payload)
    return result


@router.post(
    "/projects/{project_id}/exports",
    response_model=schemas.BusinessExportPackageRead,
    response_model_by_alias=False,
)
def create_business_project_export_package(
    project_id: str,
    payload: schemas.BusinessExportPackageCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessExportPackageRead:
    request_payload = payload.model_dump(exclude_none=True)
    try:
        result = get_business_project_service().create_export_package(
            project_id,
            payload,
            user=user,
            base_url=str(request.base_url).rstrip("/"),
        )
    except HTTPException as exc:
        _record_project_api_usage(
            request,
            status_code=exc.status_code,
            error_code=str(exc.detail or ""),
            request_payload=request_payload,
        )
        raise
    _record_project_api_usage(request, status_code=200, request_payload=request_payload)
    return result


@router.get(
    "/projects/{project_id}/exports/{package_id}",
    response_model=schemas.BusinessExportPackageRead,
    response_model_by_alias=False,
)
def get_business_project_export_package(
    project_id: str,
    package_id: str,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessExportPackageRead:
    try:
        result = get_business_project_service().get_export_package(project_id, package_id, user=user)
    except HTTPException as exc:
        _record_project_api_usage(request, status_code=exc.status_code, error_code=str(exc.detail or ""))
        raise
    _record_project_api_usage(request, status_code=200)
    return result


@router.get("/projects/{project_id}/exports/{package_id}/download")
def download_business_project_export_package(
    project_id: str,
    package_id: str,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> FileResponse:
    try:
        file_path, file_name = get_business_project_service().get_export_package_file(
            project_id,
            package_id,
            user=user,
        )
    except HTTPException as exc:
        _record_project_api_usage(request, status_code=exc.status_code, error_code=str(exc.detail or ""))
        raise
    _record_project_api_usage(request, status_code=200)
    return FileResponse(path=file_path, filename=file_name, media_type="application/zip")


@router.post("/pattern-extract/runs", response_model=dict[str, Any], response_model_by_alias=False)
def create_pattern_extract_run(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    return _create_business_run_with_usage(request=request, business_key="pattern_extract", payload=payload, user=user)


@router.post("/fission/route-preview", response_model=schemas.BusinessRoutePreviewResponse, response_model_by_alias=False)
def preview_fission_route(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRoutePreviewResponse:
    return _preview_business_route_with_usage(request=request, business_key="fission", payload=payload, user=user)


@router.post("/outpaint/route-preview", response_model=schemas.BusinessRoutePreviewResponse, response_model_by_alias=False)
def preview_outpaint_route(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRoutePreviewResponse:
    return _preview_business_route_with_usage(request=request, business_key="outpaint", payload=payload, user=user)


@router.post("/product-design/route-preview", response_model=schemas.BusinessRoutePreviewResponse, response_model_by_alias=False)
def preview_product_design_route(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRoutePreviewResponse:
    return _preview_business_route_with_usage(request=request, business_key="product_design", payload=payload, user=user)


@router.post("/pattern-extract/route-preview", response_model=schemas.BusinessRoutePreviewResponse, response_model_by_alias=False)
def preview_pattern_extract_route(
    payload: schemas.BusinessRunCreateRequest,
    request: Request,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRoutePreviewResponse:
    return _preview_business_route_with_usage(request=request, business_key="pattern_extract", payload=payload, user=user)


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
            request_payload=body,
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
        request_payload=body,
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
    submit_response_schema = {
        "type": "object",
        "description": "提交任务后的轻量回执。业务方保存 runId 后使用 /api/business/runs/get 轮询结果。",
        "properties": {
            "runId": {"type": "string", "description": "业务任务 ID；后续轮询必须使用。"},
            "taskId": {"type": "string", "nullable": True, "description": "底层能力任务 ID，可能为空，仅用于排查。"},
            "businessKey": {"type": "string", "description": "业务能力类型，例如 fission。"},
            "version": {"type": "string", "nullable": True, "description": "本次命中的业务版本。"},
            "status": {
                "type": "string",
                "description": "提交后的状态，通常是 queued 或 running。",
                "enum": BUSINESS_TASK_STATUS_VALUES,
            },
            "taskStatus": {
                "type": "string",
                "description": "兼容 Coze 的状态字段，值与 status 一致。",
                "enum": BUSINESS_TASK_STATUS_VALUES,
            },
            "traceId": {"type": "string", "nullable": True, "description": "链路追踪 ID。"},
            "requestId": {"type": "string", "nullable": True, "description": "业务方请求 ID。"},
            "debugUrl": {"type": "string", "nullable": True, "description": "内部排障链接。"},
            "debugResponse": {"type": "string", "nullable": True, "description": "提交阶段轻量排障提示。"},
            "retryAfterSeconds": {"type": "integer", "nullable": True, "description": "建议首次轮询等待秒数。"},
            "error": {"type": "string", "nullable": True},
            "errorMessage": {"type": "string", "nullable": True},
            "errorCode": {"type": "string", "nullable": True},
            "createdAt": {"type": "string", "nullable": True},
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
                "enum": BUSINESS_TASK_STATUS_VALUES,
            },
            "taskStatus": {
                "type": "string",
                "description": "兼容 Coze 轮询字段，值与 status 保持一致。",
                "enum": BUSINESS_TASK_STATUS_VALUES,
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
            "selectedStatus": {
                "type": "string",
                "description": "命中版本状态。",
                "enum": BUSINESS_ROUTE_SELECTED_STATUS_VALUES,
            },
            "selectedIsDefault": {"type": "boolean"},
            "selectedBy": {
                "type": "string",
                "description": "版本选择原因：显式指定、默认版本、白名单灰度或比例灰度。",
                "enum": BUSINESS_ROUTE_SELECTED_BY_VALUES,
            },
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
        "tenantId": {
            "type": "string",
            "nullable": True,
            "description": "租户/业务方 ID。通常不需要业务方传入，由业务 API Key 绑定；显式传入时必须与 Key 或账号范围一致。",
        },
        "clientId": {
            "type": "string",
            "nullable": True,
            "description": "客户端/应用 ID。通常不需要业务方传入，由业务 API Key 绑定；显式传入时必须与 Key 或账号范围一致。",
        },
        "callbackUrl": {"type": "string", "nullable": True, "description": "可选 Webhook 地址；常规链路仍是提交后拿 runId 轮询 /api/business/runs/get。"},
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
                "description": "图裂变重绘幅度；值越大重绘越强、变化越明显。可传 `80` 或 `80%`。ComfyUI 智能路由版会结合 VL 图案类型换算实际 denoise，不做硬区间拦截。",
            },
            "width": {"type": "integer", "nullable": True, "description": "输出宽度。"},
            "height": {"type": "integer", "nullable": True, "description": "输出高度。"},
            "profile": {
                "type": "string",
                "nullable": True,
                "description": "裂变配置；ComfyUI 智能路由版默认 pattern_risk_routed_v4，旧版可继续兼容 pattern_default_v1。",
                "enum": COMFYUI_FISSION_PROFILE_VALUES,
            },
            "mode": {"type": "string", "nullable": True, "description": "执行模式；当前图裂变固定使用 fission。", "enum": ["fission"]},
            "variation_preset": {
                "type": "string",
                "nullable": True,
                "description": "测评/业务侧参数预设名称；用于日志和排查，不会覆盖显式传入的 bili/reference_lock/color_lock。",
                "enum": COMFYUI_FISSION_VARIATION_PRESET_VALUES,
            },
            "reference_lock": {
                "type": "number",
                "nullable": True,
                "description": "原图结构保留度，建议 0.34-0.50，不做硬限制；越高越像原图，裂变感更弱。",
            },
            "color_lock": {
                "type": "number",
                "nullable": True,
                "description": "颜色锁定强度，建议 0.75-1.00，不做硬限制；越高越不容易偏色。",
            },
            "vl_result": {
                "oneOf": [{"type": "object"}, {"type": "string"}],
                "nullable": True,
                "description": "上游 VL 控制卡 JSON；通常由中台 VL 组件自动生成，包含 pattern_risk_type、palette_card 等。",
            },
            "pattern_risk_type": {
                "type": "string",
                "nullable": True,
                "description": "VL 图案风险类型；通常由中台自动生成，业务方一般不需要传。",
                "enum": FISSION_PATTERN_RISK_TYPE_VALUES,
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
                "enum": GPT_IMAGE2_VARIATION_STRENGTH_VALUES,
            },
            "quality": {
                "type": "string",
                "nullable": True,
                "description": "商业模型质量档位：preview / candidate / premium。",
                "enum": GPT_IMAGE2_QUALITY_VALUES,
            },
            "size": {
                "type": "string",
                "nullable": True,
                "description": "GPT Image 2 比例尺寸预设；默认 auto，高分辨率档位成本和耗时更高。",
                "enum": GPT_IMAGE2_SIZE_VALUES,
            },
            "output_format": {"type": "string", "nullable": True, "description": "GPT Image 2 输出格式，默认 png。", "enum": ["png", "jpeg", "webp"]},
            "maskUrl": {"type": "string", "nullable": True, "description": "可选蒙版 URL；用于局部编辑。"},
        },
    }
    image_edit_submit_schema = {
        "type": "object",
        "required": ["imageUrl"],
        "properties": {
            **base_submit_properties,
            "editSkill": {
                "type": "string",
                "nullable": True,
                "description": "改图技能。默认 local_modify；canvas_outpaint 为扩展画布；参考图替换和补色校正必须提供 referenceImages。",
                "enum": IMAGE_EDIT_SKILL_VALUES,
                "default": "local_modify",
            },
            "instruction": {
                "type": "string",
                "nullable": True,
                "description": "用户编辑指令。普通改图必填；扩展画布可不填，不填时按原图自然补全外扩区域。",
            },
            "selectionHints": {
                "oneOf": [{"type": "array", "items": {"type": "object"}}, {"type": "object"}, {"type": "string"}],
                "nullable": True,
                "description": "点选、框选、圆选或手绘区域提示；中台会自动生成红色编号定位图帮助模型理解位置，但它仍不等同于蒙版。",
            },
            "referenceImages": {
                "oneOf": [{"type": "array", "items": {"type": "object"}}, {"type": "array", "items": {"type": "string"}}, {"type": "string"}],
                "nullable": True,
                "description": "参考图列表；reference_element_transfer 和 color_reference_correction 必填。",
            },
            "maskUrl": {
                "type": "string",
                "nullable": True,
                "description": "高级模式使用的单个 alpha mask。尺寸必须与主图一致；多个笔刷区域应在前端合并成一个蒙版。",
            },
            "maskMeta": {
                "type": "object",
                "nullable": True,
                "description": "蒙版元信息，可包含 sourceWidth/sourceHeight/width/height，便于后端提前校验。",
            },
            "targetWidth": {
                "type": "integer",
                "nullable": True,
                "description": "扩展画布目标宽度；中台会向上取整到 16 的倍数。",
            },
            "targetHeight": {
                "type": "integer",
                "nullable": True,
                "description": "扩展画布目标高度；中台会向上取整到 16 的倍数。",
            },
            "placementX": {
                "type": "integer",
                "nullable": True,
                "description": "原图放入目标画布的 X 坐标；不传时按 anchor 或扩展像素计算。",
            },
            "placementY": {
                "type": "integer",
                "nullable": True,
                "description": "原图放入目标画布的 Y 坐标；不传时按 anchor 或扩展像素计算。",
            },
            "anchor": {
                "type": "string",
                "nullable": True,
                "description": "扩展画布锚点；默认 center。",
                "enum": ["center", "left", "right", "top", "bottom", "top_left", "top_right", "bottom_left", "bottom_right", "custom"],
                "default": "center",
            },
            "preserveOriginal": {
                "type": "boolean",
                "nullable": True,
                "description": "扩展画布时是否尽量保持原图区域不变；默认 true。",
                "default": True,
            },
            "expand_left": {"type": "integer", "nullable": True, "description": "扩展画布向左扩展像素；会参与 16 倍数取整。"},
            "expand_right": {"type": "integer", "nullable": True, "description": "扩展画布向右扩展像素；会参与 16 倍数取整。"},
            "expand_top": {"type": "integer", "nullable": True, "description": "扩展画布向上扩展像素；会参与 16 倍数取整。"},
            "expand_bottom": {"type": "integer", "nullable": True, "description": "扩展画布向下扩展像素；会参与 16 倍数取整。"},
            "size": {
                "type": "string",
                "nullable": True,
                "description": "输出尺寸。默认 auto=跟随原图/自动；自定义尺寸必须满足最大边、16 倍数、长短边比例和像素总量约束。",
                "default": "auto",
                "examples": IMAGE_EDIT_SIZE_VALUES,
                "pattern": r"^(auto|[1-9]\d*x[1-9]\d*)$",
                "x-podi-presets": IMAGE_EDIT_SIZE_VALUES,
            },
            "quality": {
                "type": "string",
                "nullable": True,
                "description": "质量档位：auto / preview / production / premium；2K 以上建议 production 或 premium。",
                "enum": IMAGE_EDIT_QUALITY_VALUES,
                "default": "auto",
            },
            "output_format": {
                "type": "string",
                "nullable": True,
                "description": "输出格式，默认 png。",
                "enum": IMAGE_EDIT_OUTPUT_FORMAT_VALUES,
                "default": "png",
            },
        },
        "x-podi-custom-size-constraints": IMAGE_EDIT_CUSTOM_SIZE_CONSTRAINTS,
    }
    product_design_submit_schema = {
        "type": "object",
        "required": ["imageUrl", "designBrief"],
        "properties": {
            **base_submit_properties,
            "productType": {
                "type": "string",
                "nullable": True,
                "description": "产品设计载体；默认 apparel。业务侧可按产品线选择，后续中台可按该字段分流。",
                "enum": PRODUCT_DESIGN_PRODUCT_TYPE_VALUES,
                "default": "apparel",
            },
            "designBrief": {
                "type": "string",
                "description": "产品设计要求。说明产品方向、视觉目标、必须保留或避免的内容。",
            },
            "scene": {
                "type": "string",
                "nullable": True,
                "description": "展示场景；默认 studio_product。",
                "enum": PRODUCT_DESIGN_SCENE_VALUES,
                "default": "studio_product",
            },
            "referenceImages": {
                "oneOf": [{"type": "array", "items": {"type": "object"}}, {"type": "array", "items": {"type": "string"}}, {"type": "string"}],
                "nullable": True,
                "description": "可选参考图列表，用于补充版型、材质或风格。",
            },
            "clientContextId": {
                "type": "string",
                "nullable": True,
                "description": "客户端调用上下文 ID；用于跨能力链路回溯和排查。",
            },
            "inputAssetIds": {
                "type": "array",
                "items": {"type": "string"},
                "nullable": True,
                "description": "客户端侧输入资产 ID 列表，便于结果回溯。",
            },
            "size": {
                "type": "string",
                "nullable": True,
                "description": "输出尺寸。默认 auto=跟随原图/自动；自定义尺寸沿用图编辑官方约束。",
                "default": "auto",
                "examples": IMAGE_EDIT_SIZE_VALUES,
                "pattern": r"^(auto|[1-9]\d*x[1-9]\d*)$",
                "x-podi-presets": IMAGE_EDIT_SIZE_VALUES,
            },
            "quality": {
                "type": "string",
                "nullable": True,
                "description": "质量档位：auto / preview / production / premium。",
                "enum": IMAGE_EDIT_QUALITY_VALUES,
                "default": "production",
            },
            "output_format": {
                "type": "string",
                "nullable": True,
                "description": "输出格式，默认 png。",
                "enum": IMAGE_EDIT_OUTPUT_FORMAT_VALUES,
                "default": "png",
            },
        },
        "x-podi-custom-size-constraints": IMAGE_EDIT_CUSTOM_SIZE_CONSTRAINTS,
    }
    image_edit_chat_create_schema = {
        "type": "object",
        "description": "创建 AI 图片助手会话；可带首轮 message 直接生成结构化计划。",
        "properties": {
            "agentKey": {
                "type": "string",
                "nullable": True,
                "description": "固定为 agent.image_edit_assistant；一般不需要业务方传。",
                "default": "agent.image_edit_assistant",
            },
            "imageUrl": {"type": "string", "nullable": True, "description": "会话主图 URL；也可在后续消息中补充。"},
            "message": {"type": "string", "nullable": True, "description": "首轮用户消息；传入后会生成最新建议。"},
            "editSkill": {"type": "string", "nullable": True, "description": "可选默认改图技能。", "enum": IMAGE_EDIT_SKILL_VALUES},
            "quality": {"type": "string", "nullable": True, "description": "质量档位。", "enum": IMAGE_EDIT_QUALITY_VALUES},
            "size": {"type": "string", "nullable": True, "description": "输出尺寸，默认 auto。", "examples": IMAGE_EDIT_SIZE_VALUES},
            "outputFormat": {"type": "string", "nullable": True, "description": "输出格式。", "enum": IMAGE_EDIT_OUTPUT_FORMAT_VALUES},
            "maskUrl": {"type": "string", "nullable": True, "description": "可选蒙版 URL。"},
            "referenceImages": {
                "oneOf": [{"type": "array", "items": {"type": "object"}}, {"type": "array", "items": {"type": "string"}}],
                "nullable": True,
                "description": "参考图列表。",
            },
            "selectionHints": {"type": "array", "items": {"type": "object"}, "nullable": True, "description": "标注区域提示。"},
            "title": {"type": "string", "nullable": True, "description": "会话标题。"},
            "context": {"type": "object", "nullable": True, "description": "上下文，如用户目标、商品类目、品牌要求。"},
            "metadata": {"type": "object", "nullable": True, "description": "业务上下文。"},
            "source": {"type": "string", "nullable": True, "description": "调用来源，例如 eval / client。"},
            "channel": {"type": "string", "nullable": True},
            "traceId": {"type": "string", "nullable": True},
            "requestId": {"type": "string", "nullable": True, "description": "创建会话幂等键。"},
            "tenantId": {"type": "string", "nullable": True},
            "clientId": {"type": "string", "nullable": True},
            "projectId": {"type": "string", "nullable": True},
        },
    }
    image_edit_chat_message_schema = {
        "type": "object",
        "required": ["message"],
        "description": "向已有 AI 图片助手会话追加用户消息，并生成新的最新计划。",
        "properties": {
            "message": {"type": "string", "description": "用户本轮自然语言图片处理目标。"},
            "imageUrl": {"type": "string", "nullable": True, "description": "补充或覆盖会话主图 URL。"},
            "editSkill": {"type": "string", "nullable": True, "description": "可选改图技能。", "enum": IMAGE_EDIT_SKILL_VALUES},
            "quality": {"type": "string", "nullable": True, "description": "质量档位。", "enum": IMAGE_EDIT_QUALITY_VALUES},
            "size": {"type": "string", "nullable": True, "description": "输出尺寸。", "examples": IMAGE_EDIT_SIZE_VALUES},
            "outputFormat": {"type": "string", "nullable": True, "description": "输出格式。", "enum": IMAGE_EDIT_OUTPUT_FORMAT_VALUES},
            "maskUrl": {"type": "string", "nullable": True, "description": "可选蒙版 URL。"},
            "referenceImages": {
                "oneOf": [{"type": "array", "items": {"type": "object"}}, {"type": "array", "items": {"type": "string"}}],
                "nullable": True,
                "description": "参考图列表。",
            },
            "selectionHints": {"type": "array", "items": {"type": "object"}, "nullable": True, "description": "标注区域提示。"},
            "context": {"type": "object", "nullable": True, "description": "补充上下文。"},
            "metadata": {"type": "object", "nullable": True, "description": "业务上下文。"},
        },
    }
    image_edit_chat_confirm_schema = {
        "type": "object",
        "description": "提交最新计划或指定 planId 进入后端幂等执行边界；接口名 confirm 为兼容历史协议。",
        "properties": {
            "planId": {"type": "string", "nullable": True, "description": "可选计划 ID；不传则提交当前最新计划。"},
            "overrides": {"type": "object", "nullable": True, "description": "执行前覆盖项，如 quality/size/callbackUrl。"},
            "callbackUrl": {"type": "string", "nullable": True, "description": "可选终态回调地址。"},
            "callbackHeaders": {"type": "object", "nullable": True, "description": "终态回调请求头。"},
            "requestId": {"type": "string", "nullable": True, "description": "确认动作幂等键。"},
        },
    }
    image_edit_chat_session_response_schema = {
        "type": "object",
        "properties": {
            "session": {"type": "object", "description": "会话详情，包含 messages/plans/latestPlan/toolCalls、workingMemory、assetState 和 routeEvidence 等字段。"},
        },
    }
    image_edit_chat_plan_response_schema = {
        "type": "object",
        "properties": {
            "session": {"type": "object", "description": "会话详情。"},
            "plan": {"type": "object", "description": "最新可执行计划，包含 editPlan/toolPayload/warnings/routeEvidence/workingMemory/assetState/methodology。"},
        },
    }
    image_edit_chat_confirm_response_schema = {
        "type": "object",
        "properties": {
            "session": {"type": "object", "description": "会话详情。"},
            "plan": {"type": "object", "description": "已确认方案。"},
            "toolCall": {"type": "object", "description": "工具调用记录。"},
            "run": {"type": "object", "description": "底层 image_edit 业务任务回执，包含 runId/status/retryAfterSeconds。"},
        },
    }
    text_fission_prompt_schema = {
        "type": "object",
        "required": ["imageUrl"],
        "properties": {
            **base_submit_properties,
            "provider": {"type": "string", "nullable": True, "description": "VL 模型来源；默认使用中台配置的 Doubao-Seed-2.0-lite。"},
            "prompt": {"type": "string", "nullable": True, "description": "可选补充说明；不填时按系统提示词生成可编辑文生图提示词。"},
        },
    }
    text_fission_submit_schema = {
        "type": "object",
        "required": ["imageUrl", "editable_prompt"],
        "properties": {
            **base_submit_properties,
            "editable_prompt": {
                "type": "string",
                "description": "用户确认后的最终生成提示词；会原样送入 ComfyUI 文生图节点。",
            },
            "editable_negative_prompt": {
                "type": "string",
                "nullable": True,
                "description": "反向提示词；默认不会禁用文字、字母和数字。",
            },
            "promptDraftId": {"type": "string", "nullable": True, "description": "第一步 prompts 接口返回的草稿 ID，用于链路追踪。"},
            "routeDecision": {
                "type": "string",
                "nullable": True,
                "description": "第一步返回的路线判断；兼容字段，不传不影响旧调用。建议原样带回用于链路排查。",
                "enum": ["text2img_rebuild", "deterministic_text_rebuild", "general_pattern_fission", "reject_text2img"],
            },
            "textItems": {
                "type": "array",
                "nullable": True,
                "description": "用户确认后的识别文字列表；可修改文字、角色和是否保留。旧调用方可不传。",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "nullable": True, "description": "文字序号"},
                        "text": {"type": "string", "description": "用户确认后的文字"},
                        "role": {"type": "string", "nullable": True, "description": "文字角色，如 main_title/subtitle/body/decoration"},
                        "keep": {"type": "boolean", "nullable": True, "description": "是否保留该文字"},
                    },
                },
            },
            "width": {"type": "integer", "nullable": True, "description": "输出宽度；不传则跟随原图宽度，手动传入时覆盖。"},
            "height": {"type": "integer", "nullable": True, "description": "输出高度；不传则跟随原图高度，手动传入时覆盖。"},
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

    capability_items: list[Any] = []
    if str(request.query_params.get("includeDynamicSchema") or "").strip().lower() in {"1", "true", "yes"}:
        try:
            capability_items = get_business_run_service().list_capabilities()
        except Exception:
            capability_items = []

    def _capability_value(item: Any, *keys: str) -> Any:
        if not isinstance(item, dict):
            return None
        for key in keys:
            if key in item:
                return item.get(key)
        return None

    def _field_name_for_business_api(raw_name: Any) -> str:
        name = str(raw_name or "").strip()
        aliases = {
            "url": "imageUrl",
            "image_url": "imageUrl",
            "original_image": "originalImageUrl",
            "generated_image": "generatedImageUrl",
        }
        return aliases.get(name, name)

    def _business_schema_field_to_openapi(field: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
        name = _field_name_for_business_api(field.get("name"))
        if not name:
            return None
        field_type = str(field.get("type") or "text").strip().lower()
        if field_type in {"number", "float", "decimal"}:
            schema: dict[str, Any] = {"type": "number"}
        elif field_type in {"integer", "int"}:
            schema = {"type": "integer"}
        elif field_type in {"array", "list"}:
            schema = {"type": "array", "items": {"type": "string"}}
        elif field_type in {"object", "json"}:
            schema = {"type": "object"}
        elif field_type in {"switch", "boolean", "bool"}:
            schema = {"type": "boolean"}
        else:
            schema = {"type": "string"}
        schema["nullable"] = not bool(field.get("required"))
        label = str(field.get("label") or "").strip()
        description = str(field.get("description") or "").strip()
        if label:
            schema["title"] = label
        if description:
            schema["description"] = description
        elif label:
            schema["description"] = label
        default_value = field.get("defaultValue", field.get("default"))
        if default_value is not None:
            schema["default"] = default_value
        options = field.get("options")
        if isinstance(options, list):
            enum_values: list[str] = []
            for option in options:
                if isinstance(option, dict):
                    value = option.get("value")
                else:
                    value = option
                text = str(value or "").strip()
                if text and text not in enum_values:
                    enum_values.append(text)
            if enum_values:
                schema["enum"] = enum_values
        return name, schema

    def _merge_business_capability_schema(
        business_key: str,
        fallback_schema: dict[str, Any],
        *,
        required_override: list[str] | None = None,
    ) -> dict[str, Any]:
        merged = deepcopy(fallback_schema)
        properties = deepcopy(merged.get("properties") if isinstance(merged.get("properties"), dict) else {})
        required_list = [str(item) for item in (merged.get("required") or []) if item]
        required_seen = set(required_list)
        matched = 0
        for item in capability_items:
            if str(_capability_value(item, "business_key", "businessKey") or "").strip() != business_key:
                continue
            if str(_capability_value(item, "status") or "").strip().lower() != "active":
                continue
            input_schema = _capability_value(item, "input_schema", "inputSchema")
            fields = input_schema.get("fields") if isinstance(input_schema, dict) else None
            if not isinstance(fields, list):
                continue
            matched += 1
            for field in fields:
                if not isinstance(field, dict):
                    continue
                converted = _business_schema_field_to_openapi(field)
                if not converted:
                    continue
                name, schema = converted
                existing = properties.get(name) if isinstance(properties.get(name), dict) else {}
                merged_property = {**schema, **existing}
                for optional_key in ("enum", "default", "title"):
                    if optional_key in schema and optional_key not in existing:
                        merged_property[optional_key] = schema[optional_key]
                properties[name] = merged_property
                if field.get("required") and name not in required_seen:
                    required_list.append(name)
                    required_seen.add(name)
        merged["properties"] = properties
        merged["required"] = required_override if required_override is not None else required_list
        if matched:
            merged["x-podi-source"] = "business_capabilities.input_schema"
        return merged

    pattern_extract_submit_schema = _merge_business_capability_schema("pattern_extract", pattern_extract_submit_schema)
    pattern_extract_route_preview_schema = _merge_business_capability_schema(
        "pattern_extract",
        pattern_extract_route_preview_schema,
        required_override=[],
    )
    fission_submit_schema = _merge_business_capability_schema("fission", fission_submit_schema)
    fission_route_preview_schema = _merge_business_capability_schema("fission", fission_route_preview_schema, required_override=[])
    image_edit_submit_schema = _merge_business_capability_schema("image_edit", image_edit_submit_schema)
    image_edit_submit_schema["required"] = ["imageUrl"]
    image_edit_size_schema = image_edit_submit_schema.get("properties", {}).get("size")
    if isinstance(image_edit_size_schema, dict):
        image_edit_size_schema.pop("enum", None)
        image_edit_size_schema["examples"] = IMAGE_EDIT_SIZE_VALUES
        image_edit_size_schema["x-podi-presets"] = IMAGE_EDIT_SIZE_VALUES
        image_edit_size_schema["pattern"] = r"^(auto|[1-9]\d*x[1-9]\d*)$"
    product_design_submit_schema = _merge_business_capability_schema("product_design", product_design_submit_schema)
    product_design_submit_schema["required"] = ["imageUrl", "designBrief"]
    product_design_route_preview_schema = _merge_business_capability_schema(
        "product_design",
        {**product_design_submit_schema, "required": []},
        required_override=[],
    )
    text_fission_submit_schema = _merge_business_capability_schema("text_fission", text_fission_submit_schema)
    fission_evaluate_submit_schema = _merge_business_capability_schema("fission_evaluate", fission_evaluate_submit_schema)
    outpaint_submit_schema = _merge_business_capability_schema("outpaint", outpaint_submit_schema)
    outpaint_route_preview_schema = _merge_business_capability_schema("outpaint", outpaint_route_preview_schema, required_override=[])

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
                "bili": "80%",
                "width": 2000,
                "height": 2000,
                "profile": "pattern_risk_routed_v4",
                "reference_lock": 0.42,
                "color_lock": 0.9,
                "source": "partner-api",
                "channel": "open-api",
                "requestId": "biz-request-002",
            },
        },
    }
    image_edit_examples = {
        "local_modify": {
            "summary": "局部修改",
            "value": {
                "imageUrl": "https://example.com/product.png",
                "version": "gpt-image2-editor-v1",
                "editSkill": "local_modify",
                "instruction": "把左侧杯子改成蓝色陶瓷材质，保持桌面、阴影和背景不变。",
                "selectionHints": [
                    {
                        "type": "rect",
                        "label": "杯子区域",
                        "bbox": {"x": 120, "y": 180, "width": 260, "height": 320},
                        "imageSize": {"width": 1024, "height": 1024},
                    }
                ],
                "size": "auto",
                "quality": "preview",
                "output_format": "png",
                "source": "partner-api",
                "channel": "open-api",
                "requestId": "biz-image-edit-001",
            },
        },
        "reference_transfer": {
            "summary": "参考图替换",
            "value": {
                "imageUrl": "https://example.com/product.png",
                "editSkill": "reference_element_transfer",
                "instruction": "把主图里选中的装饰贴片替换成参考图的花朵元素，保持产品透视和光照。",
                "selectionHints": [{"type": "point", "label": "贴片中心", "points": [{"x": 512, "y": 420}]}],
                "referenceImages": [{"url": "https://example.com/reference-flower.png", "label": "花朵参考"}],
                "quality": "production",
                "size": "auto",
            },
        },
        "canvas_outpaint": {
            "summary": "扩展画布",
            "value": {
                "imageUrl": "https://example.com/product.png",
                "version": "gpt-image2-editor-v1",
                "editSkill": "canvas_outpaint",
                "instruction": "向外自然延展背景和纹理，保持原图主体不变。",
                "expand_left": 300,
                "expand_right": 300,
                "expand_top": 300,
                "expand_bottom": 300,
                "anchor": "center",
                "preserveOriginal": True,
                "quality": "preview",
                "output_format": "png",
                "source": "partner-api",
                "channel": "open-api",
                "requestId": "biz-image-edit-outpaint-001",
            },
        },
    }
    product_design_examples = {
        "apparel_product_design": {
            "summary": "服装产品设计",
            "value": {
                "imageUrl": "https://example.com/pattern.png",
                "version": "product-design-gpt-image2-v1",
                "productType": "apparel",
                "designBrief": "把主图花纹应用到一款适合夏季电商展示的连衣裙产品图，保持花纹识别度，整体干净高级。",
                "scene": "studio_product",
                "quality": "production",
                "size": "auto",
                "output_format": "png",
                "source": "partner-api",
                "channel": "open-api",
                "requestId": "biz-product-design-001",
            },
        },
        "home_textile_mockup": {
            "summary": "家纺上品 mockup",
            "value": {
                "imageUrl": "https://example.com/floral-pattern.png",
                "productType": "home_textile",
                "designBrief": "生成一张抱枕产品设计图，图案自然铺在面料上，保留原花纹颜色关系和层次。",
                "scene": "print_mockup",
                "referenceImages": [{"url": "https://example.com/pillow-shape.png", "label": "抱枕版型参考"}],
                "quality": "preview",
                "size": "1024x1024",
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
    text_fission_prompt_examples = {
        "prepare_prompt": {
            "summary": "第一步：生成可编辑提示词",
            "value": {
                "imageUrl": "https://example.com/input.png",
                "source": "partner-api",
                "channel": "open-api",
                "requestId": "biz-text-fission-prompt-001",
            },
        }
    }
    text_fission_submit_examples = {
        "submit_after_edit": {
            "summary": "第二步：用确认后的提示词生成图片",
            "value": {
                "imageUrl": "https://example.com/input.png",
                "version": "qwen2512-text2img-v1",
                "editable_prompt": "一张白底平面印花图，包含清晰可读的 HAPPY SUMMER 英文字样，周围搭配热带花朵和贝壳元素，清爽商业插画风。",
                "editable_negative_prompt": "blurry, low quality, broken composition, watermark",
                "promptDraftId": "vl-draft-request-id",
                "routeDecision": "text2img_rebuild",
                "textItems": [
                    {"index": 1, "text": "HAPPY SUMMER", "role": "main_title", "keep": True}
                ],
                "source": "partner-api",
                "channel": "open-api",
                "requestId": "biz-text-fission-run-001",
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
            "FISSION_ASPECT_SOURCE_IMAGE_LOAD_FAILED",
            "FISSION_ASPECT_RECOMPOSE_GUIDE_FAILED",
            "IMAGE_EDIT_INSTRUCTION_REQUIRED",
            "IMAGE_EDIT_SKILL_INVALID",
            "IMAGE_EDIT_REFERENCE_REQUIRED",
            "IMAGE_EDIT_TARGET_REQUIRED",
            "IMAGE_EDIT_SIZE_INVALID",
            "IMAGE_EDIT_CANVAS_TOO_SMALL",
            "IMAGE_EDIT_CANVAS_PLACEMENT_INVALID",
            "IMAGE_EDIT_CANVAS_BUILD_FAILED",
            "IMAGE_EDIT_MASK_SIZE_MISMATCH",
            "IMAGE_EDIT_MASK_ALPHA_REQUIRED",
            "IMAGE_EDIT_QUALITY_INVALID",
            "IMAGE_EDIT_OUTPUT_FORMAT_INVALID",
            "PRODUCT_DESIGN_BRIEF_REQUIRED",
            "PRODUCT_DESIGN_PRODUCT_TYPE_INVALID",
            "PRODUCT_DESIGN_SCENE_INVALID",
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
    agent_errors = {
        **submit_errors,
        "400": [
            "AGENT_MESSAGE_REQUIRED",
            "AGENT_IMAGE_URL_REQUIRED",
            "AGENT_PLAN_REQUIRED",
            "AGENT_PLAN_STALE",
            "AGENT_PLAN_NOT_CONFIRMABLE",
            *submit_errors["400"],
        ],
        "404": ["AGENT_CAPABILITY_NOT_FOUND", "AGENT_SESSION_NOT_FOUND", "AGENT_PLAN_NOT_FOUND"],
        "409": ["AGENT_PLAN_CONFIRM_IN_PROGRESS", "AGENT_PLAN_REQUIRES_CLARIFICATION"],
        "500": ["AGENT_SESSION_CREATE_FAILED", "AGENT_MESSAGE_FAILED", "AGENT_PLAN_CONFIRM_FAILED", "AGENT_TOOL_CALL_FAILED"],
    }
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "PODI Business APIs",
            "version": "0.1.0",
            "description": "业务层稳定入口：花纹提取、图裂变、产品设计、直接图编辑、AI 图片助手、文字强化裂变、裂变生成图评估、扩图、任务查询。Coze 只需要调用这些扁平 API。",
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
                    "responses": _business_responses(
                        success_description="Business run accepted",
                        errors_by_status=submit_errors,
                        success_schema=submit_response_schema,
                    ),
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
                    "responses": _business_responses(
                        success_description="Business run accepted",
                        errors_by_status=submit_errors,
                        success_schema=submit_response_schema,
                    ),
                }
            },
            "/api/business/image-edit/runs": {
                "post": {
                    "operationId": "podi_business_image_edit_run",
                    "summary": "PODI · 直接图编辑",
                    "description": "提交图编辑业务任务。业务方或托管组件传主图、编辑指令、标注、参考图和可选蒙版；中台编译后调用 GPT Image 2 图片编辑。",
                    "security": business_api_key_security,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": image_edit_submit_schema,
                                "examples": image_edit_examples,
                            }
                        },
                    },
                    "x-codeSamples": [
                        {
                            "lang": "curl",
                            "label": "提交图编辑任务",
                            "source": "curl -X POST \"$PODI_BASE_URL/api/business/image-edit/runs\" \\\n  -H \"X-PODI-API-Key: $PODI_API_KEY\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"imageUrl\":\"https://example.com/product.png\",\"editSkill\":\"local_modify\",\"instruction\":\"把左侧杯子改成蓝色陶瓷材质，保持背景不变\",\"size\":\"auto\",\"quality\":\"preview\"}'",
                        }
                    ],
                    "responses": _business_responses(
                        success_description="Business run accepted",
                        errors_by_status=submit_errors,
                        success_schema=submit_response_schema,
                    ),
                }
            },
            "/api/business/product-design/runs": {
                "post": {
                    "operationId": "podi_business_product_design_run",
                    "summary": "PODI · 产品设计",
                    "description": "提交产品设计业务任务。业务方只传素材/花纹图、产品类型、设计要求和展示场景；中台负责 prompt 编译、版本路由和结果回填。",
                    "security": business_api_key_security,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": product_design_submit_schema,
                                "examples": product_design_examples,
                            }
                        },
                    },
                    "x-codeSamples": [
                        {
                            "lang": "curl",
                            "label": "提交产品设计任务",
                            "source": "curl -X POST \"$PODI_BASE_URL/api/business/product-design/runs\" \\\n  -H \"X-PODI-API-Key: $PODI_API_KEY\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"imageUrl\":\"https://example.com/pattern.png\",\"productType\":\"apparel\",\"designBrief\":\"把主图花纹应用到一款适合电商展示的连衣裙产品图\",\"scene\":\"studio_product\",\"quality\":\"production\"}'",
                        }
                    ],
                    "responses": _business_responses(
                        success_description="Business run accepted",
                        errors_by_status=submit_errors,
                        success_schema=submit_response_schema,
                    ),
                }
            },
            "/api/business/image-edit-chat/sessions": {
                "post": {
                    "operationId": "podi_business_image_edit_chat_create_session",
                    "summary": "PODI · AI 图片助手 · 创建会话",
                    "description": "创建 AI 图片助手会话。它是独立 Agent 入口，不是 /api/business/image-edit/runs 的别名；后端会按白名单、schema、置信度、风险和成本校验后路由到图片业务能力。当前普通单张图片任务默认走 image_edit/GPT Image 2 质量优先路径，明确批量、快速、低成本或固定 SOP 时才分流到 pattern_extract 等专项能力。",
                    "security": business_api_key_security,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": image_edit_chat_create_schema,
                                "examples": {
                                    "create_with_first_message": {
                                        "summary": "创建会话并生成首个建议",
                                        "value": {
                                            "imageUrl": "https://example.com/product.png",
                                            "message": "把主图调整成更干净的电商商品图，保留原始花纹主体。",
                                            "quality": "preview",
                                            "size": "auto",
                                            "source": "partner-api",
                                            "channel": "image-edit-agent",
                                            "requestId": "biz-image-edit-chat-001",
                                        },
                                    }
                                },
                            }
                        },
                    },
                    "responses": _business_responses(
                        success_description="Image edit chat session created",
                        errors_by_status=agent_errors,
                        success_schema=image_edit_chat_plan_response_schema,
                    ),
                }
            },
            "/api/business/image-edit-chat/sessions/{sessionId}": {
                "get": {
                    "operationId": "podi_business_image_edit_chat_get_session",
                    "summary": "PODI · AI 图片助手 · 查询会话",
                    "description": "查询 AI 图片助手会话、消息、计划和工具调用记录。",
                    "security": business_api_key_security,
                    "parameters": [
                        {"name": "sessionId", "in": "path", "required": True, "schema": {"type": "string"}},
                    ],
                    "responses": _business_responses(
                        success_description="Image edit chat session",
                        errors_by_status=agent_errors,
                        success_schema=image_edit_chat_session_response_schema,
                    ),
                }
            },
            "/api/business/image-edit-chat/sessions/{sessionId}/messages": {
                "post": {
                    "operationId": "podi_business_image_edit_chat_send_message",
                    "summary": "PODI · AI 图片助手 · 发送消息",
                    "description": "向已有会话追加用户消息，并生成新的最新计划。后端不会隐藏续聊，调用方必须显式传 sessionId。",
                    "security": business_api_key_security,
                    "parameters": [
                        {"name": "sessionId", "in": "path", "required": True, "schema": {"type": "string"}},
                    ],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": image_edit_chat_message_schema}}},
                    "responses": _business_responses(
                        success_description="Image edit chat plan prepared",
                        errors_by_status=agent_errors,
                        success_schema=image_edit_chat_plan_response_schema,
                    ),
                }
            },
            "/api/business/image-edit-chat/sessions/{sessionId}/confirm": {
                "post": {
                    "operationId": "podi_business_image_edit_chat_confirm_latest",
                    "summary": "PODI · AI 图片助手 · 执行最新计划",
                    "description": "提交当前最新计划进入后端幂等执行边界。会话还没有计划时返回 AGENT_PLAN_REQUIRED。",
                    "security": business_api_key_security,
                    "parameters": [
                        {"name": "sessionId", "in": "path", "required": True, "schema": {"type": "string"}},
                    ],
                    "requestBody": {"required": False, "content": {"application/json": {"schema": image_edit_chat_confirm_schema}}},
                    "responses": _business_responses(
                        success_description="Image edit chat plan confirmed",
                        errors_by_status=agent_errors,
                        success_schema=image_edit_chat_confirm_response_schema,
                    ),
                }
            },
            "/api/business/image-edit-chat/sessions/{sessionId}/plans/{planId}/confirm": {
                "post": {
                    "operationId": "podi_business_image_edit_chat_confirm_plan",
                    "summary": "PODI · AI 图片助手 · 执行指定计划",
                    "description": "提交指定计划版本进入后端幂等执行边界。指定的计划不是最新计划时返回 AGENT_PLAN_STALE。",
                    "security": business_api_key_security,
                    "parameters": [
                        {"name": "sessionId", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "planId", "in": "path", "required": True, "schema": {"type": "string"}},
                    ],
                    "requestBody": {"required": False, "content": {"application/json": {"schema": image_edit_chat_confirm_schema}}},
                    "responses": _business_responses(
                        success_description="Image edit chat plan confirmed",
                        errors_by_status=agent_errors,
                        success_schema=image_edit_chat_confirm_response_schema,
                    ),
                }
            },
            "/api/business/image-edit/component-config": {
                "get": {
                    "operationId": "podi_business_image_edit_component_config",
                    "summary": "PODI · 图编辑组件配置",
                    "description": "返回托管组件和源码组件共用的技能、尺寸、质量档位、文案和约束。业务方不要硬编码这些枚举。",
                    "security": business_api_key_security,
                    "responses": {
                        "200": {
                            "description": "Image edit component config",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "businessKey": {"type": "string", "enum": ["image_edit"]},
                                            "defaultVersion": {"type": "string"},
                                            "skills": {"type": "array", "items": {"type": "object"}},
                                            "sizes": {"type": "array", "items": {"type": "object"}},
                                            "customSizeConstraints": {"type": "object"},
                                            "qualityLevels": {"type": "array", "items": {"type": "object"}},
                                            "outputFormats": {"type": "array", "items": {"type": "string"}},
                                        },
                                    }
                                }
                            },
                        },
                        "401": {"description": "未认证"},
                        "403": {"description": "API Key 不允许访问 image_edit"},
                    },
                }
            },
            "/api/business/text-fission/prompts": {
                "post": {
                    "operationId": "podi_business_text_fission_prompt",
                    "summary": "PODI · 文字强化裂变 · 生成可编辑提示词",
                    "description": "第一步接口：输入原图，让 VL 生成可编辑文生图提示词。业务方应把 editablePrompt 展示给用户确认或修改。",
                    "security": business_api_key_security,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": text_fission_prompt_schema,
                                "examples": text_fission_prompt_examples,
                            }
                        },
                    },
                    "responses": _business_responses(
                        success_description="Text fission editable prompt prepared",
                        errors_by_status={
                            **submit_errors,
                            "400": [*submit_errors["400"], "VL_IMAGE_REQUIRED", "VL_IMAGE_UNREACHABLE"],
                            "503": [*submit_errors.get("503", []), "VL_PROVIDER_FAILED"],
                            "500": [*submit_errors["500"], "TEXT_FISSION_PROMPT_EMPTY", "TEXT_FISSION_PROMPT_PREPARE_FAILED"],
                        },
                        success_schema={
                            "type": "object",
                            "properties": {
                                "promptDraftId": {"type": "string", "description": "提示词草稿 ID。"},
                                "status": {"type": "string", "description": "VL 调用状态。"},
                                "imageUrl": {"type": "string", "description": "原图 URL。"},
                                "editablePrompt": {"type": "string", "description": "用户可编辑的生成提示词。"},
                                "editableNegativePrompt": {"type": "string", "nullable": True, "description": "用户可编辑的反向提示词。"},
                                "vlResult": {"type": "object", "description": "完整 VL 结构化结果，用于排查和复盘。"},
                            },
                        },
                    ),
                }
            },
            "/api/business/text-fission/runs": {
                "post": {
                    "operationId": "podi_business_text_fission_run",
                    "summary": "PODI · 文字强化裂变 · 文生图",
                    "description": "第二步接口：提交用户确认后的 editable_prompt，创建文生图任务并返回 runId。该接口固定一次生成 1 张图。",
                    "security": business_api_key_security,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": text_fission_submit_schema,
                                "examples": text_fission_submit_examples,
                            }
                        },
                    },
                    "responses": _business_responses(
                        success_description="Business run accepted",
                        errors_by_status={
                            **submit_errors,
                            "400": [*submit_errors["400"], "TEXT_FISSION_PROMPT_REQUIRED", "COMFYUI_PROMPT_REQUIRED"],
                        },
                        success_schema=submit_response_schema,
                    ),
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
                    "responses": _business_responses(
                        success_description="Business run accepted",
                        errors_by_status=submit_errors,
                        success_schema=submit_response_schema,
                    ),
                }
            },
            "/api/business/outpaint/runs": {
                "post": {
                    "operationId": "podi_business_outpaint_run",
                    "summary": "PODI · 扩图",
                    "description": "提交扩图业务任务。宽高、上下左右扩展量从 inputs 传入，底层版本由中台路由。",
                    "security": business_api_key_security,
                    "requestBody": {"required": True, "content": {"application/json": {"schema": outpaint_submit_schema}}},
                    "responses": _business_responses(
                        success_description="Business run accepted",
                        errors_by_status=submit_errors,
                        success_schema=submit_response_schema,
                    ),
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
            "/api/business/product-design/route-preview": {
                "post": {
                    "operationId": "podi_business_product_design_route_preview",
                    "summary": "PODI · 产品设计路由预览",
                    "description": "不提交真实任务，只预览当前 tenantId/clientId/grayKey 会命中哪个产品设计版本。",
                    "security": business_api_key_security,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": product_design_route_preview_schema,
                                "examples": product_design_examples,
                            }
                        },
                    },
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


FEATURE_RELEASE_AUDIT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "image-edit-gpt-image2",
        "name": "图编辑 · GPT Image 2 通用改图",
        "entry": "/api/business/image-edit/runs",
        "businessKey": "image_edit",
        "version": "gpt-image2-editor-v1",
        "deliveryKey": "image-edit-gpt-image2",
        "expectedResult": "image",
        "costSensitive": True,
        "mustCheck": [
            "参数：imageUrl、editSkill、instruction、selectionHints、referenceImages、maskUrl、size、quality",
            "模式：局部修改、参考图替换、删除修补、补色校正均有明确错误码",
            "结果：默认轻量返回，detail=full 才返回编译提示词和步骤详情",
            "页面：测评端是组件工作台，不用普通表单堆字段",
        ],
        "releaseEvidence": "图编辑组件任务 runId + GPT Image 2 能力调用记录 + OSS 结果图",
        "currentRisk": "图编辑质量依赖用户标注和提示词；平台重点确认编译、尺寸、mask、参考图和回填链路。",
    },
    {
        "key": "gpt-image2-fission",
        "name": "GPT Image 2 + VL 受控裂变",
        "entry": "/api/business/fission/runs",
        "businessKey": "fission",
        "version": "gpt-image2-vl-v2",
        "deliveryKey": "gpt-image2-fission",
        "expectedResult": "image",
        "costSensitive": True,
        "mustCheck": [
            "参数：imageUrl、variation_strength、quality、size、maskUrl",
            "默认：一次请求固定一张图，多图必须提交多次",
            "结果：默认轻量返回，detail=full 才看底层步骤",
            "页面：名称不随版本改动，尺寸默认跟原图走",
        ],
        "releaseEvidence": "交付目录 01 + 业务任务 runId + OpenAI 能力调用记录",
        "currentRisk": "商业模型质量波动属于模型侧；平台重点确认入参、出参、轮询和错误码。",
    },
    {
        "key": "comfyui-colorlock-fission",
        "name": "ComfyUI 颜色锁定裂变",
        "entry": "/api/business/fission/runs",
        "businessKey": "fission",
        "version": "comfyui-vl-control-v2",
        "deliveryKey": "comfyui-colorlock-fission",
        "expectedResult": "image",
        "requiresGpuRun": True,
        "mustCheck": [
            "参数：bili、width、height、profile、variation_preset、reference_lock、color_lock",
            "默认：bili 是重绘幅度，按约定映射 denoise，不叫相似度",
            "节点：158/233 都要通过 workflow 兼容检查",
            "结果：OSS 回填，测评端能并排或滑块查看原图/结果图",
        ],
        "releaseEvidence": "交付目录 02 + ComfyUI workflow 兼容检查 + 业务样本包",
        "currentRisk": "如果执行节点缺自定义节点，必须先修服务器同构；只有止血时才临时限路由。",
    },
    {
        "key": "fission-score",
        "name": "裂变生成图评估",
        "entry": "/api/business/fission-evaluate/runs",
        "businessKey": "fission_evaluate",
        "version": "v1",
        "deliveryKey": "fission-score",
        "expectedResult": "text",
        "mustCheck": [
            "参数：originalImageUrl、generatedImageUrl、context",
            "枚举：decision 必须能解释通过、需复核、不通过",
            "结果：评分文本和结构化 JSON 都能被业务读取",
            "错误：缺原图或结果图返回 VL_EVAL_IMAGE_REQUIRED",
        ],
        "releaseEvidence": "交付目录 03 + 裂变任务结果图 + 评分 runId",
        "currentRisk": "评分只给判断，不自动二次裂变；业务编排自行决定是否重跑。",
    },
    {
        "key": "legacy-seamless-fission",
        "name": "旧四方连续裂变",
        "entry": "Coze 工具箱 / 既有工作流",
        "businessKey": "legacy_coze",
        "version": None,
        "deliveryKey": None,
        "expectedResult": "image",
        "requiresGpuRun": True,
        "externalEvidenceOnly": True,
        "mustCheck": [
            "节点：String、KSampler、SaveImage 等必需节点在目标机器存在",
            "路由：158/233 不应长期只命中一台机器",
            "失败：队列满或节点缺失要给可读错误",
            "回填：生图完成后必须能进入任务查询结果",
        ],
        "releaseEvidence": "Coze 工作流巡检 + ComfyUI 兼容检查 + 能力调用记录",
        "currentRisk": "该类仍依赖旧工作流，优先用 workflow-compatibility 检查节点差异。",
    },
)


def _audit_value(row: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    if not isinstance(row, dict):
        return default
    for key in keys:
        if key in row:
            return row.get(key)
    return default


def _audit_first_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except Exception:
        return 0


def _find_capability_for_feature(
    capabilities: list[dict[str, Any]],
    *,
    business_key: str,
    version: str | None,
) -> dict[str, Any] | None:
    for item in capabilities:
        if not isinstance(item, dict):
            continue
        if str(_audit_value(item, "business_key", "businessKey") or "").strip() != business_key:
            continue
        item_version = str(_audit_value(item, "version") or "").strip()
        if version is None:
            if _audit_value(item, "is_default", "isDefault") is True:
                return item
            continue
        if item_version == version:
            return item
    return None


def _feature_release_evidence(
    *,
    key: str,
    title: str,
    status: str,
    detail: str,
    action: str,
) -> dict[str, str]:
    return {
        "key": key,
        "title": title,
        "status": status,
        "detail": detail,
        "action": action,
    }


def _build_feature_release_checks(
    *,
    delivery_items: list[dict[str, Any]],
    capabilities: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    capabilities = capabilities or []
    delivery_by_key = {str(item.get("key") or ""): item for item in delivery_items if isinstance(item, dict)}
    checks: list[dict[str, Any]] = []
    for spec in FEATURE_RELEASE_AUDIT_SPECS:
        blockers: list[str] = []
        warnings: list[str] = []
        evidence: list[dict[str, str]] = []

        delivery_key = str(spec.get("deliveryKey") or "")
        delivery_item = delivery_by_key.get(delivery_key) if delivery_key else None
        docs_ok = (
            bool(delivery_item.get("ok"))
            if isinstance(delivery_item, dict)
            else bool(spec.get("externalEvidenceOnly"))
        )
        if delivery_key and not docs_ok:
            blockers.append("交付材料缺请求、响应、错误或枚举证据。")
        evidence.append(
            _feature_release_evidence(
                key="delivery_docs",
                title="交付材料",
                status="done" if docs_ok else "todo",
                detail=(
                    delivery_item.get("summary")
                    if isinstance(delivery_item, dict)
                    else "依赖 Coze 巡检和 workflow compatibility 记录。"
                )
                or "交付材料已检查。",
                action="新增或改参数时，先补独立 README、6 类 JSON 样例、枚举和错误码。",
            )
        )

        capability = None
        if not spec.get("externalEvidenceOnly"):
            capability = _find_capability_for_feature(
                capabilities,
                business_key=str(spec.get("businessKey") or ""),
                version=str(spec.get("version") or "") if spec.get("version") is not None else None,
            )
        if spec.get("externalEvidenceOnly"):
            evidence.append(
                _feature_release_evidence(
                    key="legacy_workflow",
                    title="旧 Coze 工作流",
                    status="doing",
                    detail="该功能不属于中台自有业务版本，必须由 Coze 巡检和 ComfyUI 兼容检查提供证据。",
                    action="上线前跑 Coze 主线巡检，并确认回填和任务查询。",
                )
            )
            warnings.append("旧 Coze 链路需看巡检报告，不能只看业务版本列表。")
        elif capability is None:
            blockers.append("没有找到对应业务版本，页面、接口和门禁无法统一。")
            evidence.append(
                _feature_release_evidence(
                    key="business_version",
                    title="业务版本",
                    status="todo",
                    detail=f"缺少 businessKey={spec.get('businessKey')} version={spec.get('version')} 的业务版本。",
                    action="先补业务版本配方，再补测评入口和文档。",
                )
            )
        else:
            status = str(_audit_value(capability, "status") or "").strip().lower()
            release_gate = _audit_value(capability, "release_gate", "releaseGate", default={})
            latest_run = _audit_value(capability, "latest_run", "latestRun", default={})
            latest_acceptance = _audit_value(capability, "latest_acceptance", "latestAcceptance", default={})
            primary_ability_id = str(_audit_value(capability, "primary_ability_id", "primaryAbilityId") or "").strip()
            display_name = str(
                _audit_value(capability, "display_name", "displayName") or spec.get("name") or ""
            ).strip()

            if status != "active":
                blockers.append(f"业务版本未启用：{status or '-'}。")
            if not primary_ability_id:
                blockers.append("缺少主执行能力，业务入口只是配置壳。")
            evidence.append(
                _feature_release_evidence(
                    key="business_version",
                    title="业务版本",
                    status="done" if status == "active" and primary_ability_id else "todo",
                    detail=f"{display_name} · {status or '-'} · 主能力 {primary_ability_id or '-'}",
                    action="版本升级必须保持业务名稳定，只用版本族和更新时间表达变化。",
                )
            )

            latest_run_status = str(_audit_value(latest_run, "status") or "").strip().lower()
            image_count = _audit_first_int(_audit_value(latest_run, "image_count", "imageCount"))
            video_count = _audit_first_int(_audit_value(latest_run, "video_count", "videoCount"))
            text_count = _audit_first_int(_audit_value(latest_run, "text_count", "textCount"))
            result_total = image_count + video_count + text_count
            run_id = str(_audit_value(latest_run, "id", "runId") or "").strip()
            expected_result = str(spec.get("expectedResult") or "").strip()
            if not run_id:
                if spec.get("costSensitive"):
                    warnings.append("商业模型真实调用可因成本跳过，但必须记录未跑原因。")
                else:
                    blockers.append("缺少真实运行记录，无法证明参数、执行和回填闭环。")
            elif latest_run_status != "succeeded":
                blockers.append(f"最近真实运行不是成功状态：{latest_run_status or '-'}。")
            elif expected_result == "image" and image_count <= 0:
                blockers.append("最近成功运行没有图片结果。")
            elif expected_result == "text" and result_total <= 0:
                blockers.append("最近成功运行没有文字或结构化结果。")
            evidence.append(
                _feature_release_evidence(
                    key="real_run",
                    title="真实运行",
                    status=(
                        "done"
                        if run_id
                        and latest_run_status == "succeeded"
                        and (result_total > 0 or expected_result not in {"image", "text"})
                        else "doing"
                    ),
                    detail=(
                        f"runId={run_id or '-'} status={latest_run_status or '-'} "
                        f"结果={image_count} 图/{video_count} 视频/{text_count} 文本"
                    ),
                    action="GPU 自有能力必须真实跑；第三方能力跳过时要写清成本原因。",
                )
            )

            gate_status = str(_audit_value(release_gate, "status") or "").strip().lower()
            acceptance_status = str(_audit_value(latest_acceptance, "status") or "").strip().lower()
            gate_blockers = _audit_value(release_gate, "blockers", default=[])
            gate_warnings = _audit_value(release_gate, "warnings", default=[])
            if gate_status == "blocked":
                blockers.append(f"业务版本门禁未通过：{gate_blockers or ['blocked']}。")
            elif gate_status == "warning":
                warnings.append(f"业务版本门禁有提醒：{gate_warnings or ['warning']}。")
            evidence.append(
                _feature_release_evidence(
                    key="release_gate",
                    title="验收与门禁",
                    status="done" if gate_status == "ready" and acceptance_status == "passed" else "todo",
                    detail=f"门禁={gate_status or '-'} 验收={acceptance_status or '-'}",
                    action="真实链路通过后登记人工验收；没有验收记录不能标记可交付。",
                )
            )

        status = "done"
        if blockers:
            status = "todo"
        elif warnings:
            status = "doing"
        checks.append(
            {
                "key": spec["key"],
                "name": spec["name"],
                "entry": spec["entry"],
                "businessKey": spec.get("businessKey"),
                "version": spec.get("version"),
                "mustCheck": list(spec.get("mustCheck") or []),
                "releaseEvidence": spec.get("releaseEvidence") or "",
                "currentRisk": spec.get("currentRisk") or "",
                "status": status,
                "summary": "可交付证据已闭环。" if status == "done" else "；".join(blockers or warnings),
                "blockers": blockers,
                "warnings": warnings,
                "evidence": evidence,
                "requiresGpuRun": bool(spec.get("requiresGpuRun")),
                "costSensitive": bool(spec.get("costSensitive")),
            }
        )
    return checks


def _business_delivery_contract_audit() -> dict[str, Any]:
    """Expose the same delivery contract evidence used by release smoke."""
    try:
        from scripts import podi_release_smoke as smoke
    except Exception as exc:  # pragma: no cover - defensive for stripped deployments
        return {
            "ok": False,
            "summary": f"无法加载发布检查脚本：{exc}",
            "items": [],
            "checkedAt": datetime.utcnow().isoformat(),
        }

    root = smoke._repo_root()
    examples_base = root / "docs" / "api" / "examples"
    enum_doc = root / "docs" / "standards" / "business-api-enums.md"
    error_catalog = root / "docs" / "standards" / "error-catalog.md"
    enum_text = enum_doc.read_text(encoding="utf-8") if enum_doc.exists() else ""
    error_text = error_catalog.read_text(encoding="utf-8") if error_catalog.exists() else ""
    sample_names = list(smoke.REQUIRED_BUSINESS_DELIVERY_SAMPLE_FILES)
    ui_key_aliases = {
        "image_edit_gpt_image2_editor": "image-edit-gpt-image2",
        "gpt_image2_controlled_fission": "gpt-image2-fission",
        "comfyui_colorlock_fission": "comfyui-colorlock-fission",
        "fission_generated_image_score": "fission-score",
    }
    items: list[dict[str, Any]] = []
    for spec in smoke.BUSINESS_DELIVERY_DOC_SPECS:
        key = ui_key_aliases.get(str(spec["key"]), str(spec["key"]))
        label = str(spec["label"])
        base = examples_base / str(spec.get("base_folder") or "fission-business-delivery")
        folder = base / str(spec["folder"])
        readme = folder / "README.md"
        readme_text = readme.read_text(encoding="utf-8") if readme.exists() else ""
        missing_samples = [name for name in sample_names if not (folder / name).exists()]
        missing_enums = [str(field) for field in spec["enum_fields"] if str(field) not in readme_text]
        missing_enum_source = [str(field) for field in spec["enum_fields"] if enum_text and str(field) not in enum_text]
        missing_error_codes = [str(code) for code in spec["error_codes"] if str(code) not in readme_text]
        missing_error_catalog = [str(code) for code in spec["error_codes"] if error_text and str(code) not in error_text]
        missing_doc_refs = [
            token
            for token in ("docs/standards/business-api-enums.md", "docs/standards/error-catalog.md")
            if token not in readme_text
        ]
        ok = (
            readme.exists()
            and not missing_samples
            and not missing_enums
            and not missing_enum_source
            and not missing_error_codes
            and not missing_error_catalog
            and not missing_doc_refs
        )
        gap_messages: list[str] = []
        if not readme.exists():
            gap_messages.append("缺 README")
        if missing_samples:
            gap_messages.append(f"缺样例 {len(missing_samples)} 类")
        if missing_enums or missing_enum_source:
            gap_messages.append("枚举未对齐")
        if missing_error_codes or missing_error_catalog:
            gap_messages.append("错误码未对齐")
        if missing_doc_refs:
            gap_messages.append("缺真源引用")
        items.append(
            {
                "key": key,
                "name": label,
                "path": str(spec["path"]),
                "docsPath": str((folder / "README.md").relative_to(root)),
                "sampleFiles": sample_names,
                "enumFields": list(spec["enum_fields"]),
                "errorCodes": list(spec["error_codes"]),
                "missingSamples": missing_samples,
                "missingEnums": missing_enums,
                "missingEnumSource": missing_enum_source,
                "missingErrorCodes": missing_error_codes,
                "missingErrorCatalog": missing_error_catalog,
                "missingDocRefs": missing_doc_refs,
                "ok": ok,
                "status": "done" if ok else "todo",
                "summary": "交付文档、样例、枚举和错误码已对齐。" if ok else "；".join(gap_messages),
                "requiredEvidence": [
                    f"文档：{(folder / 'README.md').relative_to(root)}",
                    f"样例：{'、'.join(sample_names)}",
                    "枚举真源：docs/standards/business-api-enums.md",
                    "错误码真源：docs/standards/error-catalog.md",
                ],
            }
        )
    try:
        capabilities = get_business_run_service().list_capabilities()
    except Exception:
        capabilities = []
    feature_release_checks = _build_feature_release_checks(delivery_items=items, capabilities=capabilities)
    ok, detail = smoke._validate_business_delivery_docs(root)
    contract_payload = business_api_contract_payload()
    return {
        "ok": ok,
        "summary": detail,
        "items": items,
        "featureReleaseChecks": feature_release_checks,
        "enumDocs": contract_payload["enumDocs"],
        "requiredEnumFields": contract_payload["requiredEnumFields"],
        "enumValues": contract_payload["values"],
        "contractSource": contract_payload["source"],
        "contractVersion": contract_payload["version"],
        "checkedAt": datetime.utcnow().isoformat(),
    }


@admin_router.get("/capabilities", response_model=schemas.BusinessCapabilityListResponse, response_model_by_alias=False)
def admin_list_business_capabilities(
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return list_business_capabilities(user=user)


@admin_router.get("/delivery-contracts")
def admin_get_business_delivery_contracts(
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return _business_delivery_contract_audit()


@admin_router.get("/component-catalog")
def admin_get_business_component_catalog(
    user: User = Depends(_resolve_business_user),
) -> dict[str, Any]:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return business_component_catalog_payload()


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


def _build_business_api_key_usage_filters(
    *,
    api_key_id: str | None = None,
    business_key: str | None = None,
    tenant_id: str | None = None,
    client_id: str | None = None,
    method: str | None = None,
    path: str | None = None,
    endpoint_kind: str | None = None,
    status_code: int | None = None,
    status_group: str | None = None,
    error_code: str | None = None,
    run_id: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    window_hours: int | None = 24,
) -> dict[str, Any]:
    filters = []
    if api_key_id:
        filters.append(BusinessApiKeyUsageLog.api_key_id == api_key_id)
    if business_key:
        filters.append(BusinessApiKeyUsageLog.business_key == business_key)
    if tenant_id:
        filters.append(BusinessApiKeyUsageLog.tenant_id == tenant_id)
    if client_id:
        filters.append(BusinessApiKeyUsageLog.client_id == client_id)
    if method:
        filters.append(BusinessApiKeyUsageLog.method == method.upper()[:16])
    if path:
        filters.append(BusinessApiKeyUsageLog.path.contains(path.strip()))
    if status_code is not None:
        filters.append(BusinessApiKeyUsageLog.status_code == status_code)
    if error_code:
        filters.append(BusinessApiKeyUsageLog.error_code == error_code.strip())
    if run_id:
        filters.append(BusinessApiKeyUsageLog.run_id == run_id.strip())
    if request_id:
        filters.append(BusinessApiKeyUsageLog.request_id == request_id.strip())
    if trace_id:
        filters.append(BusinessApiKeyUsageLog.trace_id == trace_id.strip())
    if window_hours:
        filters.append(BusinessApiKeyUsageLog.created_at >= datetime.utcnow() - timedelta(hours=window_hours))

    poll_filter = BusinessApiKeyUsageLog.path == "/api/business/runs/get"
    callback_filter = BusinessApiKeyUsageLog.path.contains("callback")
    submit_filter = and_(
        BusinessApiKeyUsageLog.method == "POST",
        BusinessApiKeyUsageLog.path.like("%/runs"),
        BusinessApiKeyUsageLog.path != "/api/business/runs/get",
    )
    endpoint_kind_value = str(endpoint_kind or "").strip().lower()
    if endpoint_kind_value == "submit":
        filters.append(submit_filter)
    elif endpoint_kind_value == "poll":
        filters.append(poll_filter)
    elif endpoint_kind_value == "callback":
        filters.append(callback_filter)

    error_filter = or_(BusinessApiKeyUsageLog.status_code >= 400, BusinessApiKeyUsageLog.error_code.is_not(None))
    success_filter = and_(
        BusinessApiKeyUsageLog.status_code >= 200,
        BusinessApiKeyUsageLog.status_code < 400,
        BusinessApiKeyUsageLog.error_code.is_(None),
    )
    status_group_value = str(status_group or "").strip().lower()
    if status_group_value == "success":
        filters.append(success_filter)
    elif status_group_value == "error":
        filters.append(error_filter)

    return {
        "filters": filters,
        "submit_filter": submit_filter,
        "poll_filter": poll_filter,
        "callback_filter": callback_filter,
        "error_filter": error_filter,
        "success_filter": success_filter,
    }


def _list_business_api_key_usage_uncached(
    *,
    api_key_id: str | None = None,
    business_key: str | None = None,
    tenant_id: str | None = None,
    client_id: str | None = None,
    method: str | None = None,
    path: str | None = None,
    endpoint_kind: str | None = None,
    status_code: int | None = None,
    status_group: str | None = None,
    error_code: str | None = None,
    run_id: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    window_hours: int = 24,
    offset: int = 0,
    limit: int = 50,
    group_limit: int = 30,
) -> schemas.BusinessApiKeyUsageLogListResponse:
    with get_session() as session:
        query_parts = _build_business_api_key_usage_filters(
            api_key_id=api_key_id,
            business_key=business_key,
            tenant_id=tenant_id,
            client_id=client_id,
            method=method,
            path=path,
            endpoint_kind=endpoint_kind,
            status_code=status_code,
            status_group=status_group,
            error_code=error_code,
            run_id=run_id,
            request_id=request_id,
            trace_id=trace_id,
            window_hours=window_hours,
        )
        filters = query_parts["filters"]
        submit_filter = query_parts["submit_filter"]
        poll_filter = query_parts["poll_filter"]
        callback_filter = query_parts["callback_filter"]
        error_filter = query_parts["error_filter"]
        success_filter = query_parts["success_filter"]

        base_stmt = select(BusinessApiKeyUsageLog)
        if filters:
            base_stmt = base_stmt.where(*filters)

        total = int(session.execute(select(func.count()).select_from(BusinessApiKeyUsageLog).where(*filters)).scalar() or 0)
        rows = (
            session.execute(
                base_stmt.order_by(BusinessApiKeyUsageLog.created_at.desc()).offset(offset).limit(limit)
            )
            .scalars()
            .all()
        )

        submit_count_expr = func.coalesce(func.sum(case((submit_filter, 1), else_=0)), 0)
        poll_count_expr = func.coalesce(func.sum(case((poll_filter, 1), else_=0)), 0)
        callback_count_expr = func.coalesce(func.sum(case((callback_filter, 1), else_=0)), 0)
        error_count_expr = func.coalesce(func.sum(case((error_filter, 1), else_=0)), 0)
        success_count_expr = func.coalesce(func.sum(case((success_filter, 1), else_=0)), 0)
        summary_row = session.execute(
            select(
                success_count_expr,
                error_count_expr,
                submit_count_expr,
                poll_count_expr,
                callback_count_expr,
                func.count(func.distinct(BusinessApiKeyUsageLog.run_id)),
                func.avg(BusinessApiKeyUsageLog.duration_ms),
            )
            .select_from(BusinessApiKeyUsageLog)
            .where(*filters)
        ).one()
        summary = schemas.BusinessApiKeyUsageSummary(
            total=total,
            success_count=int(summary_row[0] or 0),
            error_count=int(summary_row[1] or 0),
            submit_count=int(summary_row[2] or 0),
            poll_count=int(summary_row[3] or 0),
            callback_count=int(summary_row[4] or 0),
            unique_run_count=int(summary_row[5] or 0),
            average_duration_ms=float(summary_row[6]) if summary_row[6] is not None else None,
        )

        groups: list[schemas.BusinessApiKeyUsageRunGroup] = []
        if group_limit > 0:
            group_rows = session.execute(
                select(
                    BusinessApiKeyUsageLog.run_id,
                    func.max(BusinessApiKeyUsageLog.business_key),
                    func.max(BusinessApiKeyUsageLog.api_key_name),
                    func.max(BusinessApiKeyUsageLog.api_key_preview),
                    func.max(BusinessApiKeyUsageLog.request_id),
                    func.max(BusinessApiKeyUsageLog.trace_id),
                    func.max(BusinessApiKeyUsageLog.tenant_id),
                    func.max(BusinessApiKeyUsageLog.client_id),
                    func.count(),
                    submit_count_expr,
                    poll_count_expr,
                    callback_count_expr,
                    error_count_expr,
                    func.max(BusinessApiKeyUsageLog.status_code),
                    func.max(BusinessApiKeyUsageLog.error_code),
                    func.min(BusinessApiKeyUsageLog.created_at),
                    func.max(BusinessApiKeyUsageLog.created_at),
                )
                .select_from(BusinessApiKeyUsageLog)
                .where(*filters, BusinessApiKeyUsageLog.run_id.is_not(None))
                .group_by(BusinessApiKeyUsageLog.run_id)
                .order_by(func.max(BusinessApiKeyUsageLog.created_at).desc())
                .limit(group_limit)
            ).all()
            run_ids = [str(row[0]) for row in group_rows if row[0]]
            run_map: dict[str, dict[str, Any]] = {}
            if run_ids:
                run_map = {
                    str(row["id"]): dict(row)
                    for row in session.execute(
                        select(
                            BusinessRun.id,
                            BusinessRun.status,
                            BusinessRun.version,
                            BusinessRun.business_version_id,
                            BusinessRun.image_urls,
                            BusinessRun.video_urls,
                            BusinessRun.texts,
                            BusinessRun.error_message,
                            BusinessRun.finished_at,
                        ).where(BusinessRun.id.in_(run_ids))
                    )
                    .mappings()
                    .all()
                }
            for row in group_rows:
                linked_run = run_map.get(str(row[0] or ""))
                image_count = len(linked_run.get("image_urls") or []) if linked_run else 0
                video_count = len(linked_run.get("video_urls") or []) if linked_run else 0
                text_count = len(linked_run.get("texts") or []) if linked_run else 0
                submit_count = int(row[9] or 0)
                poll_count = int(row[10] or 0)
                error_count = int(row[12] or 0)
                needs_attention, issue_code, issue_hint = _business_api_usage_group_issue(
                    submit_count=submit_count,
                    poll_count=poll_count,
                    error_count=error_count,
                )
                if linked_run is None and row[0]:
                    needs_attention = True
                    issue_code = issue_code or "BUSINESS_RUN_NOT_FOUND"
                    issue_hint = "接口日志里有 runId，但业务任务表里没有对应记录；需要核对是否为旧数据或异常清理。"
                elif linked_run and linked_run.get("status") in {"failed", "cancelled", "timeout"} and not needs_attention:
                    needs_attention = True
                    issue_code = "BUSINESS_RUN_FAILED"
                    issue_hint = linked_run.get("error_message") or "接口提交成功，但业务任务最终失败；请打开业务详情查看失败步骤。"
                groups.append(
                    schemas.BusinessApiKeyUsageRunGroup(
                        run_id=row[0],
                        business_key=row[1],
                        run_status=linked_run.get("status") if linked_run else None,
                        run_version=linked_run.get("version") if linked_run else None,
                        business_version_id=linked_run.get("business_version_id") if linked_run else None,
                        result_image_count=image_count,
                        result_video_count=video_count,
                        result_text_count=text_count,
                        run_error=linked_run.get("error_message") if linked_run else None,
                        run_finished_at=linked_run.get("finished_at") if linked_run else None,
                        api_key_name=row[2],
                        api_key_preview=row[3],
                        request_id=row[4],
                        trace_id=row[5],
                        tenant_id=row[6],
                        client_id=row[7],
                        total_count=int(row[8] or 0),
                        submit_count=submit_count,
                        poll_count=poll_count,
                        callback_count=int(row[11] or 0),
                        error_count=error_count,
                        needs_attention=needs_attention,
                        issue_code=issue_code,
                        issue_hint=issue_hint,
                        last_status_code=int(row[13]) if row[13] is not None else None,
                        last_error_code=row[14],
                        first_seen_at=row[15],
                        last_seen_at=row[16],
                    )
                )

        return schemas.BusinessApiKeyUsageLogListResponse(
            items=rows,
            total=total,
            offset=offset,
            limit=limit,
            pagination=schemas.BusinessApiKeyUsagePagination(
                total=total,
                offset=offset,
                limit=limit,
                has_more=offset + len(rows) < total,
                next_offset=offset + len(rows) if offset + len(rows) < total else None,
            ),
            summary=summary,
            groups=groups,
        )


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
    method: str | None = Query(default=None),
    path: str | None = Query(default=None),
    endpoint_kind: str | None = Query(default=None, description="submit/poll/callback"),
    status_code: int | None = Query(default=None),
    status_group: str | None = Query(default=None, description="success/error"),
    error_code: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    window_hours: int = Query(default=24, ge=0, le=24 * 90),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    group_limit: int = Query(default=30, ge=0, le=100),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessApiKeyUsageLogListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    cache_key = _business_admin_read_cache_key(
        "api_key_usage",
        api_key_id,
        business_key,
        tenant_id,
        client_id,
        method,
        path,
        endpoint_kind,
        status_code,
        status_group,
        error_code,
        run_id,
        request_id,
        trace_id,
        window_hours,
        offset,
        limit,
        group_limit,
    )
    return _business_admin_read_cached(
        cache_key,
        lambda: _list_business_api_key_usage_uncached(
            api_key_id=api_key_id,
            business_key=business_key,
            tenant_id=tenant_id,
            client_id=client_id,
            method=method,
            path=path,
            endpoint_kind=endpoint_kind,
            status_code=status_code,
            status_group=status_group,
            error_code=error_code,
            run_id=run_id,
            request_id=request_id,
            trace_id=trace_id,
            window_hours=window_hours,
            offset=offset,
            limit=limit,
            group_limit=group_limit,
        ),
    )


@admin_router.get("/api-key-usage/export")
def admin_export_business_api_key_usage(
    api_key_id: str | None = Query(default=None),
    business_key: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    method: str | None = Query(default=None),
    path: str | None = Query(default=None),
    endpoint_kind: str | None = Query(default=None, description="submit/poll/callback"),
    status_code: int | None = Query(default=None),
    status_group: str | None = Query(default=None, description="success/error"),
    error_code: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    window_hours: int = Query(default=24, ge=0, le=24 * 90),
    limit: int = Query(default=5000, ge=1, le=10000),
    user: User = Depends(_resolve_business_user),
) -> Response:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    query_parts = _build_business_api_key_usage_filters(
        api_key_id=api_key_id,
        business_key=business_key,
        tenant_id=tenant_id,
        client_id=client_id,
        method=method,
        path=path,
        endpoint_kind=endpoint_kind,
        status_code=status_code,
        status_group=status_group,
        error_code=error_code,
        run_id=run_id,
        request_id=request_id,
        trace_id=trace_id,
        window_hours=window_hours,
    )
    with get_session() as session:
        rows = (
            session.execute(
                select(BusinessApiKeyUsageLog)
                .where(*query_parts["filters"])
                .order_by(BusinessApiKeyUsageLog.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
    return Response(
        content="\ufeff" + _business_api_key_usage_to_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="business-api-key-usage.csv"'},
    )


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
    "/capabilities/{capability_id}/drafts",
    response_model=schemas.BusinessCapabilityRead,
    response_model_by_alias=False,
)
def admin_create_business_capability_draft(
    capability_id: str,
    payload: schemas.BusinessCapabilityDraftCreateRequest | None = None,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().create_capability_draft(capability_id, payload, actor=user)


@admin_router.patch(
    "/capability-drafts/{draft_id}/recipe",
    response_model=schemas.BusinessCapabilityRead,
    response_model_by_alias=False,
)
def admin_update_business_capability_draft_recipe(
    draft_id: str,
    payload: schemas.BusinessCapabilityDraftRecipeUpdateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().update_capability_draft_recipe(draft_id, payload, actor=user)


@admin_router.post(
    "/capability-drafts/{draft_id}/validate",
    response_model=schemas.BusinessCapabilityDraftValidateResponse,
    response_model_by_alias=False,
)
def admin_validate_business_capability_draft(
    draft_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityDraftValidateResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().validate_capability_draft(draft_id)


@admin_router.post(
    "/capability-drafts/{draft_id}/publish",
    response_model=schemas.BusinessCapabilityRead,
    response_model_by_alias=False,
)
def admin_publish_business_capability_draft(
    draft_id: str,
    payload: schemas.BusinessCapabilityDraftPublishRequest | None = None,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessCapabilityRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().publish_capability_draft(draft_id, payload, actor=user)


@admin_router.post("/capabilities/{capability_id}/draft-run", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def admin_run_business_capability_draft(
    capability_id: str,
    payload: schemas.BusinessRunCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().create_run_for_capability(
        capability_id=capability_id,
        payload=payload,
        user=user,
        source="admin-draft-run",
    )


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
    window_hours: int | None = Query(default=24, ge=1, le=2160),
    detail: str = Query(default="summary", pattern="^(summary|full)$"),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    total, items = get_business_run_service().list_runs(
        limit=limit,
        window_hours=window_hours,
        detail=detail,
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


@admin_router.get("/runs/{run_id}", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def admin_get_business_run(
    run_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().get_run(run_id=run_id, user=user)


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
    window_hours: int | None = Query(default=24, ge=1, le=2160),
    limit: int = Query(default=1000, ge=1, le=1000),
    user: User = Depends(_resolve_business_user),
) -> Response:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    _, items = get_business_run_service().list_runs(
        limit=limit,
        window_hours=window_hours,
        detail="summary",
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


@admin_router.post("/runs/{run_id}/retest", response_model=schemas.BusinessRunRead, response_model_by_alias=False)
def admin_retest_business_run(
    run_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessRunRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().retest_run(run_id, actor=user)


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
    "/quality-samples",
    response_model=schemas.BusinessQualitySampleListResponse,
    response_model_by_alias=False,
)
def admin_list_business_quality_samples(
    business_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessQualitySampleListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().list_quality_samples(
        business_key=business_key,
        status=status,
        include_archived=include_archived,
        limit=limit,
    )


@admin_router.post(
    "/quality-samples",
    response_model=schemas.BusinessQualitySampleRead,
    response_model_by_alias=False,
)
def admin_create_business_quality_sample(
    payload: schemas.BusinessQualitySampleCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessQualitySampleRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().create_quality_sample(payload, actor=user)


@admin_router.post(
    "/quality-samples/import",
    response_model=schemas.BusinessQualitySampleImportResponse,
    response_model_by_alias=False,
)
def admin_import_business_quality_samples(
    payload: schemas.BusinessQualitySampleImportRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessQualitySampleImportResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().import_quality_samples(payload, actor=user)


@admin_router.get(
    "/quality-samples/{sample_id}/versions",
    response_model=schemas.BusinessQualitySampleVersionListResponse,
    response_model_by_alias=False,
)
def admin_list_business_quality_sample_versions(
    sample_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessQualitySampleVersionListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().list_quality_sample_versions(sample_id, limit=limit)


@admin_router.patch(
    "/quality-samples/{sample_id}",
    response_model=schemas.BusinessQualitySampleRead,
    response_model_by_alias=False,
)
def admin_update_business_quality_sample(
    sample_id: str,
    payload: schemas.BusinessQualitySampleUpdateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessQualitySampleRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().update_quality_sample(sample_id, payload, actor=user)


@admin_router.delete(
    "/quality-samples/{sample_id}",
    response_model=schemas.BusinessQualitySampleRead,
    response_model_by_alias=False,
)
def admin_archive_business_quality_sample(
    sample_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessQualitySampleRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().archive_quality_sample(sample_id, actor=user)


@admin_router.get(
    "/quality-action-rules",
    response_model=schemas.BusinessQualityActionRuleListResponse,
    response_model_by_alias=False,
)
def admin_list_business_quality_action_rules(
    business_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    action_type: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessQualityActionRuleListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().list_quality_action_rules(
        business_key=business_key,
        status=status,
        action_type=action_type,
        include_archived=include_archived,
        limit=limit,
    )


@admin_router.post(
    "/quality-action-rules",
    response_model=schemas.BusinessQualityActionRuleRead,
    response_model_by_alias=False,
)
def admin_create_business_quality_action_rule(
    payload: schemas.BusinessQualityActionRuleCreateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessQualityActionRuleRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().create_quality_action_rule(payload, actor=user)


@admin_router.patch(
    "/quality-action-rules/{rule_id}",
    response_model=schemas.BusinessQualityActionRuleRead,
    response_model_by_alias=False,
)
def admin_update_business_quality_action_rule(
    rule_id: str,
    payload: schemas.BusinessQualityActionRuleUpdateRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessQualityActionRuleRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().update_quality_action_rule(rule_id, payload, actor=user)


@admin_router.delete(
    "/quality-action-rules/{rule_id}",
    response_model=schemas.BusinessQualityActionRuleRead,
    response_model_by_alias=False,
)
def admin_archive_business_quality_action_rule(
    rule_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessQualityActionRuleRead:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().archive_quality_action_rule(rule_id, actor=user)


@admin_router.get(
    "/runs/{run_id}/output-reviews",
    response_model=schemas.BusinessOutputReviewListResponse,
    response_model_by_alias=False,
)
def admin_list_business_output_reviews(
    run_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessOutputReviewListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().list_output_reviews(run_id=run_id, actor=user)


@admin_router.post(
    "/runs/{run_id}/output-reviews",
    response_model=schemas.BusinessOutputReviewListResponse,
    response_model_by_alias=False,
)
def admin_upsert_business_output_reviews(
    run_id: str,
    payload: schemas.BusinessOutputReviewUpsertRequest,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessOutputReviewListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().upsert_output_reviews(run_id=run_id, payload=payload, actor=user)


@admin_router.get(
    "/output-reviews/summary",
    response_model=schemas.BusinessOutputReviewSummaryResponse,
    response_model_by_alias=False,
)
def admin_business_output_review_summary(
    window_hours: int = Query(default=168, ge=1, le=2160),
    business_key: str | None = Query(default=None),
    version: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessOutputReviewSummaryResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_run_service().output_review_summary(
        window_hours=window_hours,
        business_key=business_key,
        version=version,
        limit=limit,
    )


@admin_router.get("/output-reviews/export")
def admin_export_business_output_reviews(
    window_hours: int = Query(default=168, ge=1, le=2160),
    business_key: str | None = Query(default=None),
    version: str | None = Query(default=None),
    batch_id: str | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=10000),
    user: User = Depends(_resolve_business_user),
) -> Response:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    result = get_business_run_service().export_output_reviews(
        window_hours=window_hours,
        business_key=business_key,
        version=version,
        batch_id=batch_id,
        limit=limit,
    )
    filename = "business-output-reviews.csv"
    if batch_id:
        safe_batch_id = re.sub(r"[^A-Za-z0-9._-]+", "-", str(batch_id).strip())[:80] or "batch"
        filename = f"business-output-reviews-{safe_batch_id}.csv"
    return Response(
        content="\ufeff" + _business_output_reviews_to_csv(result["items"]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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


@admin_router.get("/projects", response_model=schemas.BusinessProjectListResponse, response_model_by_alias=False)
def admin_list_business_projects(
    scenario: str | None = Query(default=None),
    status: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessProjectListResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    total, items = get_business_project_service().list_projects(
        user=user,
        scenario=scenario,
        status=status,
        tenant_id=tenant_id,
        client_id=client_id,
        limit=limit,
        offset=offset,
    )
    return schemas.BusinessProjectListResponse(total=total, items=items)


@admin_router.get(
    "/projects/{project_id}",
    response_model=schemas.BusinessProjectDetailResponse,
    response_model_by_alias=False,
)
def admin_get_business_project(
    project_id: str,
    user: User = Depends(_resolve_business_user),
) -> schemas.BusinessProjectDetailResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_ONLY")
    return get_business_project_service().get_project_detail(project_id, user=user)


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
