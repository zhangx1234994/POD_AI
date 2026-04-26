"""Unified vendor invocation and key management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading
from typing import Any
from uuid import uuid4

from app.baidu import baidu_adapter
from app.config import get_settings
from app.kie import kie_adapter
from app.openai_adapter import openai_adapter
from app.providers import ERR_PROVIDER_NOT_SUPPORTED, PROVIDERS, check_provider_egress
from app.schemas import (
    InvocationError,
    InvocationRequest,
    InvocationResponse,
    InvocationResult,
    VendorKeyCreateRequest,
    VendorKeyRead,
    VendorKeyUpdateRequest,
)
from app.storage import vendor_storage
from app.volcengine import volcengine_adapter


ERR_INVOCATION_NOT_FOUND = "VENDOR_API_INVOCATION_NOT_FOUND"
ERR_CONCURRENCY_LIMITED = "VENDOR_API_CONCURRENCY_LIMITED"
ERR_KEY_CONCURRENCY_LIMITED = "VENDOR_API_KEY_CONCURRENCY_LIMITED"
ERR_KEY_DISABLED = "VENDOR_API_KEY_DISABLED"
ERR_KEY_MISSING = "VENDOR_API_KEY_MISSING"


class InvocationStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_by_scope: dict[str, int] = {}
        self._active_by_key: dict[str, int] = {}

    def submit(self, request: InvocationRequest) -> InvocationResponse:
        provider = request.provider.strip().lower()
        definition = PROVIDERS.get(provider)
        now = _now()
        if not definition:
            return InvocationResponse(
                success=False,
                status="failed",
                provider=provider,
                model=request.model,
                vendorInvocationId=f"vinv_{uuid4().hex}",
                error=InvocationError(
                    code=ERR_PROVIDER_NOT_SUPPORTED,
                    message=f"Provider is not supported: {request.provider}",
                    suggestion="Register the provider adapter before exposing it through backend.",
                ),
                createdAt=now,
                updatedAt=now,
            )

        execution_mode = (request.executionMode or _default_execution_mode(provider, request.apiType)).strip()
        scope = f"{provider}:{request.model or request.capabilityKey}"
        max_concurrency = _as_positive_int(request.taskPolicy.get("maxConcurrency")) or 100
        with self._lock:
            active = self._active_by_scope.get(scope, 0)
            if active >= max_concurrency:
                return InvocationResponse(
                    success=False,
                    status="failed",
                    provider=provider,
                    model=request.model,
                    vendorInvocationId=f"vinv_{uuid4().hex}",
                    error=InvocationError(
                        code=ERR_CONCURRENCY_LIMITED,
                        message=f"Concurrency limit reached for {scope}",
                        retryable=True,
                    ),
                    createdAt=now,
                    updatedAt=now,
                )
            self._active_by_scope[scope] = active + 1
        try:
            return self._submit_with_adapter(request=request, provider=provider, execution_mode=execution_mode)
        finally:
            with self._lock:
                self._active_by_scope[scope] = max(0, self._active_by_scope.get(scope, 1) - 1)

    def get(self, invocation_id: str, *, credentials: dict[str, Any] | None = None) -> InvocationResponse | None:
        record = vendor_storage.get_invocation(invocation_id)
        if not record:
            return None
        if record["provider"] == "kie" and record["status"] == "running" and record.get("vendor_task_id"):
            record = self._refresh_kie(record, credentials=credentials)
        return _response_from_record(record)

    def create_key(self, payload: VendorKeyCreateRequest) -> VendorKeyRead:
        item = vendor_storage.create_key(
            {
                "id": f"vkey_{uuid4().hex}",
                "provider": payload.provider.strip().lower(),
                "alias": payload.alias.strip(),
                "key_value": payload.key,
                "secret_value": payload.secret,
                "model": payload.model,
                "status": payload.status,
                "daily_quota": payload.dailyQuota,
                "monthly_quota": payload.monthlyQuota,
                "max_concurrency": max(1, int(payload.maxConcurrency or 1)),
                "metadata": payload.metadata or {},
            }
        )
        return _read_key(item)

    def list_keys(self, provider: str | None = None) -> list[VendorKeyRead]:
        normalized = provider.strip().lower() if isinstance(provider, str) and provider.strip() else None
        return [_read_key(item) for item in vendor_storage.list_keys(provider=normalized)]

    def update_key(self, key_id: str, payload: VendorKeyUpdateRequest) -> VendorKeyRead | None:
        changes: dict[str, Any] = {}
        if payload.status is not None:
            changes["status"] = payload.status
        if payload.cooldownUntil is not None:
            changes["cooldown_until"] = payload.cooldownUntil
        if payload.lastError is not None:
            changes["last_error"] = payload.lastError
        if payload.metadata is not None:
            changes["metadata"] = payload.metadata
        item = vendor_storage.update_key(key_id, changes)
        return _read_key(item) if item else None

    async def check_key(self, key_id: str, *, check: str | None = None) -> tuple[VendorKeyRead | None, Any | None]:
        item = vendor_storage.get_key(key_id)
        if not item:
            return None, None
        provider = str(item.get("provider") or "").strip().lower()
        definition = PROVIDERS.get(provider)
        check_name = check or (definition.supported_checks[0] if definition and definition.supported_checks else "models")
        result = await check_provider_egress(
            settings=get_settings(),
            provider=provider,
            check=check_name,
            include_auth=True,
            auth_material={"key": item.get("key"), "secret": item.get("secret")},
        )
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        metadata = {
            **metadata,
            "lastCheck": {
                "success": result.success,
                "check": result.check,
                "httpStatus": result.httpStatus,
                "latencyMs": result.latencyMs,
                "errorCode": result.errorCode,
                "message": result.message,
                "checkedAt": datetime.now(timezone.utc).isoformat(),
            },
        }
        updated = vendor_storage.update_key(
            key_id,
            {
                "last_error": None if result.success else (result.errorCode or result.message or "VENDOR_API_AUTH_FAILED"),
                "metadata": metadata,
            },
        )
        return (_read_key(updated) if updated else None), result

    def usage_summary(self, *, window_hours: int = 24) -> list[dict[str, Any]]:
        return [
            {
                "provider": item["provider"],
                "model": item.get("model"),
                "status": item["status"],
                "count": item["count"],
                "errorCode": item.get("error_code"),
                "avgLatencyMs": item.get("avg_latency_ms"),
                "lastSeenAt": item.get("last_seen_at"),
            }
            for item in vendor_storage.usage_summary(window_hours=window_hours)
        ]

    def _submit_with_adapter(self, *, request: InvocationRequest, provider: str, execution_mode: str) -> InvocationResponse:
        invocation_id = f"vinv_{uuid4().hex}"
        base_raw = {
            "requestId": request.requestId,
            "traceId": request.traceId,
            "capabilityKey": request.capabilityKey,
            "apiType": request.apiType,
            "executionMode": execution_mode,
            "adapter": "contract-v2",
        }
        record = vendor_storage.create_invocation(
            {
                "id": invocation_id,
                "provider": provider,
                "model": request.model,
                "capability_key": request.capabilityKey,
                "api_type": request.apiType,
                "execution_mode": execution_mode,
                "status": "queued",
                "success": 0,
                "vendor_task_id": None,
                "request": _safe_invocation_request(request),
                "response": {},
                "error": None,
                "raw": base_raw,
            }
        )
        if provider == "kie":
            return self._submit_kie(record=record, request=request, execution_mode=execution_mode)
        if provider in {"openai", "openai_compatible"}:
            return self._submit_openai(record=record, request=request, provider=provider)
        if provider == "volcengine":
            return self._submit_volcengine(record=record, request=request)
        if provider == "baidu":
            return self._submit_baidu(record=record, request=request)

    def _submit_openai(self, *, record: dict[str, Any], request: InvocationRequest, provider: str) -> InvocationResponse:
        key, key_limited = self._pick_runtime_key(
            provider=provider,
            model=request.model,
            credentials=request.credentials,
            acquire_slot=True,
        )
        if key_limited:
            return self._mark_key_limited(record, provider=provider, model=request.model)
        if not key:
            error = InvocationError(
                code=ERR_KEY_MISSING,
                message=f"{provider} API Key is not configured",
                suggestion="Configure an active key in backend and send it with this invocation.",
            )
            updated = vendor_storage.update_invocation(
                record["id"],
                {
                    "status": "failed",
                    "success": 0,
                    "error": error.model_dump(mode="json"),
                    "raw": record.get("raw", {}),
                },
            )
            return _response_from_record(updated)

        try:
            started = datetime.now(timezone.utc)
            result, error, raw = openai_adapter.run(
                settings=get_settings(),
                provider=provider,
                api_key=str(key["key"]),
                request=request,
            )
            latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            status = "failed" if error else "succeeded"
            self._record_key_usage(key, error)
            vendor_storage.create_usage_log(
                {
                    "id": f"vlog_{uuid4().hex}",
                    "invocation_id": record["id"],
                    "provider": provider,
                    "model": request.model,
                    "key_id": key.get("id"),
                    "status": status,
                    "error_code": error.code if error else None,
                    "latency_ms": latency_ms,
                }
            )
        finally:
            self._release_runtime_key_slot(key)
        updated = vendor_storage.update_invocation(
            record["id"],
            {
                "status": status,
                "success": 0 if error else 1,
                "response": result.model_dump(mode="json", by_alias=True),
                "error": error.model_dump(mode="json") if error else None,
                "raw": raw,
            },
        )
        return _response_from_record(updated)

    def _submit_volcengine(self, *, record: dict[str, Any], request: InvocationRequest) -> InvocationResponse:
        key, key_limited = self._pick_runtime_key(
            provider="volcengine",
            model=request.model,
            credentials=request.credentials,
            acquire_slot=True,
        )
        if key_limited:
            return self._mark_key_limited(record, provider="volcengine", model=request.model)
        if not key:
            error = InvocationError(
                code=ERR_KEY_MISSING,
                message="Volcengine API Key is not configured",
                suggestion="Configure an active Volcengine key in backend and send it with this invocation.",
            )
            updated = vendor_storage.update_invocation(
                record["id"],
                {"status": "failed", "success": 0, "error": error.model_dump(mode="json"), "raw": record.get("raw", {})},
            )
            return _response_from_record(updated)

        try:
            started = datetime.now(timezone.utc)
            result, error, raw = volcengine_adapter.run(settings=get_settings(), api_key=str(key["key"]), request=request)
            latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            status = "failed" if error else "succeeded"
            self._record_key_usage(key, error)
            vendor_storage.create_usage_log(
                {
                    "id": f"vlog_{uuid4().hex}",
                    "invocation_id": record["id"],
                    "provider": "volcengine",
                    "model": request.model,
                    "key_id": key.get("id"),
                    "status": status,
                    "error_code": error.code if error else None,
                    "latency_ms": latency_ms,
                }
            )
        finally:
            self._release_runtime_key_slot(key)
        updated = vendor_storage.update_invocation(
            record["id"],
            {
                "status": status,
                "success": 0 if error else 1,
                "response": result.model_dump(mode="json", by_alias=True),
                "error": error.model_dump(mode="json") if error else None,
                "raw": raw,
            },
        )
        return _response_from_record(updated)

    def _submit_baidu(self, *, record: dict[str, Any], request: InvocationRequest) -> InvocationResponse:
        key, key_limited = self._pick_runtime_key(
            provider="baidu",
            model=request.model,
            credentials=request.credentials,
            acquire_slot=True,
        )
        if key_limited:
            return self._mark_key_limited(record, provider="baidu", model=request.model)
        if not key:
            error = InvocationError(
                code=ERR_KEY_MISSING,
                message="Baidu API Key is not configured",
                suggestion="Configure a Baidu key+secret in backend and send it with this invocation.",
            )
            updated = vendor_storage.update_invocation(
                record["id"],
                {"status": "failed", "success": 0, "error": error.model_dump(mode="json"), "raw": record.get("raw", {})},
            )
            return _response_from_record(updated)

        try:
            started = datetime.now(timezone.utc)
            result, error, raw = baidu_adapter.run(
                settings=get_settings(),
                api_key=str(key["key"]),
                secret_key=key.get("secret"),
                request=request,
            )
            latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            status = "failed" if error else "succeeded"
            self._record_key_usage(key, error)
            vendor_storage.create_usage_log(
                {
                    "id": f"vlog_{uuid4().hex}",
                    "invocation_id": record["id"],
                    "provider": "baidu",
                    "model": request.model,
                    "key_id": key.get("id"),
                    "status": status,
                    "error_code": error.code if error else None,
                    "latency_ms": latency_ms,
                }
            )
        finally:
            self._release_runtime_key_slot(key)
        updated = vendor_storage.update_invocation(
            record["id"],
            {
                "status": status,
                "success": 0 if error else 1,
                "response": result.model_dump(mode="json", by_alias=True),
                "error": error.model_dump(mode="json") if error else None,
                "raw": raw,
            },
        )
        return _response_from_record(updated)

    def _submit_kie(self, *, record: dict[str, Any], request: InvocationRequest, execution_mode: str) -> InvocationResponse:
        key, key_limited = self._pick_runtime_key(
            provider="kie",
            model=request.model,
            credentials=request.credentials,
            acquire_slot=True,
        )
        if key_limited:
            return self._mark_key_limited(record, provider="kie", model=request.model)
        if not key:
            error = InvocationError(
                code=ERR_KEY_MISSING,
                message="KIE API Key is not configured",
                suggestion="Configure an active KIE key in backend and send it with this invocation.",
            )
            updated = vendor_storage.update_invocation(
                record["id"],
                {
                    "status": "failed",
                    "success": 0,
                    "error": error.model_dump(mode="json"),
                    "raw": {**record.get("raw", {}), "executionMode": execution_mode},
                },
            )
            return _response_from_record(updated)

        try:
            started = datetime.now(timezone.utc)
            vendor_task_id, result, error, raw = kie_adapter.submit(settings=get_settings(), api_key=str(key["key"]), request=request)
            latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            status = "running" if vendor_task_id and not error else "failed"
            self._record_key_usage(key, error)
            vendor_storage.create_usage_log(
                {
                    "id": f"vlog_{uuid4().hex}",
                    "invocation_id": record["id"],
                    "provider": "kie",
                    "model": request.model,
                    "key_id": key.get("id"),
                    "status": status,
                    "error_code": error.code if error else None,
                    "latency_ms": latency_ms,
                }
            )
        finally:
            self._release_runtime_key_slot(key)
        updated = vendor_storage.update_invocation(
            record["id"],
            {
                "status": status,
                "success": 1 if status == "running" else 0,
                "vendor_task_id": vendor_task_id,
                "response": result.model_dump(mode="json", by_alias=True),
                "error": error.model_dump(mode="json") if error else None,
                "raw": raw,
            },
        )
        return _response_from_record(updated)

    def _refresh_kie(self, record: dict[str, Any], *, credentials: dict[str, Any] | None = None) -> dict[str, Any]:
        key, key_limited = self._pick_runtime_key(
            provider="kie",
            model=record.get("model"),
            credentials=credentials,
            acquire_slot=True,
        )
        if not key or key_limited:
            return record
        try:
            started = datetime.now(timezone.utc)
            status, result, error, raw = kie_adapter.fetch(
                settings=get_settings(),
                api_key=str(key["key"]),
                task_id=str(record["vendor_task_id"]),
            )
            latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            vendor_storage.create_usage_log(
                {
                    "id": f"vlog_{uuid4().hex}",
                    "invocation_id": record["id"],
                    "provider": "kie",
                    "model": record.get("model"),
                    "key_id": key.get("id"),
                    "status": status,
                    "error_code": error.code if error else None,
                    "latency_ms": latency_ms,
                }
            )
        finally:
            self._release_runtime_key_slot(key)
        if status in {"succeeded", "failed"}:
            return vendor_storage.update_invocation(
                record["id"],
                {
                    "status": status,
                    "success": 1 if status == "succeeded" else 0,
                    "response": result.model_dump(mode="json", by_alias=True),
                    "error": error.model_dump(mode="json") if error else None,
                    "raw": raw,
                },
            ) or record
        return vendor_storage.update_invocation(
            record["id"],
            {
                "status": "running",
                "success": 1,
                "response": result.model_dump(mode="json", by_alias=True),
                "error": error.model_dump(mode="json") if error else None,
                "raw": raw,
            },
        ) or record

    def _pick_runtime_key(
        self,
        *,
        provider: str,
        model: str | None,
        credentials: dict[str, Any] | None = None,
        acquire_slot: bool = False,
    ) -> tuple[dict[str, Any] | None, bool]:
        request_key = _runtime_key_from_credentials(provider=provider, model=model, credentials=credentials)
        if request_key:
            return request_key, False
        limited = False
        for key in _candidate_stored_keys(provider=provider, model=model):
            if acquire_slot and not self._try_acquire_runtime_key_slot(key):
                limited = True
                continue
            return key, False
        settings = get_settings()
        if provider == "kie" and settings.kie_api_key:
            return {"id": "env:kie", "provider": "kie", "key": settings.kie_api_key, "status": "active"}, False
        if provider == "openai" and settings.openai_api_key:
            return {"id": "env:openai", "provider": "openai", "key": settings.openai_api_key, "status": "active"}, False
        if provider == "openai_compatible" and settings.openai_compatible_api_key:
            return {
                "id": "env:openai_compatible",
                "provider": "openai_compatible",
                "key": settings.openai_compatible_api_key,
                "status": "active",
            }, False
        if provider == "volcengine" and settings.volcengine_api_key:
            return {"id": "env:volcengine", "provider": "volcengine", "key": settings.volcengine_api_key, "status": "active"}, False
        if provider == "baidu" and settings.baidu_api_key:
            return {
                "id": "env:baidu",
                "provider": "baidu",
                "key": settings.baidu_api_key,
                "secret": settings.baidu_secret_key,
                "status": "active",
            }, False
        return None, limited

    def _try_acquire_runtime_key_slot(self, key: dict[str, Any]) -> bool:
        key_id = str(key.get("id") or "")
        if not key_id or key_id.startswith("env:") or key_id.startswith("request:"):
            return True
        max_concurrency = _as_positive_int(key.get("max_concurrency")) or 1
        with self._lock:
            active = self._active_by_key.get(key_id, 0)
            if active >= max_concurrency:
                return False
            self._active_by_key[key_id] = active + 1
            return True

    def _release_runtime_key_slot(self, key: dict[str, Any] | None) -> None:
        key_id = str((key or {}).get("id") or "")
        if not key_id or key_id.startswith("env:") or key_id.startswith("request:"):
            return
        with self._lock:
            self._active_by_key[key_id] = max(0, self._active_by_key.get(key_id, 1) - 1)

    def _mark_key_limited(self, record: dict[str, Any], *, provider: str, model: str | None) -> InvocationResponse:
        error = InvocationError(
            code=ERR_KEY_CONCURRENCY_LIMITED,
            message=f"All active keys are busy for {provider}:{model or '*'}",
            retryable=True,
            suggestion="Wait and retry, or increase key maxConcurrency after confirming vendor quota.",
        )
        vendor_storage.create_usage_log(
            {
                "id": f"vlog_{uuid4().hex}",
                "invocation_id": record["id"],
                "provider": provider,
                "model": model,
                "key_id": None,
                "status": "failed",
                "error_code": error.code,
                "latency_ms": 0,
            }
        )
        updated = vendor_storage.update_invocation(
            record["id"],
            {
                "status": "failed",
                "success": 0,
                "error": error.model_dump(mode="json"),
                "raw": {**record.get("raw", {}), "keyLimited": True},
            },
        )
        return _response_from_record(updated)

    @staticmethod
    def _record_key_usage(key: dict[str, Any], error: InvocationError | None) -> None:
        key_id = str(key.get("id") or "")
        if not key_id or key_id.startswith("env:") or key_id.startswith("request:"):
            return
        if error:
            cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=120) if error.code == "VENDOR_API_RATE_LIMITED" else None
            vendor_storage.mark_key_error(key_id, last_error=error.message, cooldown_until=cooldown_until)
        else:
            vendor_storage.bump_key_usage(key_id)


def _default_execution_mode(provider: str, api_type: str | None) -> str:
    api = (api_type or "").lower()
    if provider == "kie":
        return "async_submit_poll"
    if api in {"video_generation", "market_image_to_image", "market_text_to_video"}:
        return "async_submit_poll"
    if provider == "baidu":
        return "sync_then_store"
    return "sync"


def _candidate_stored_keys(*, provider: str, model: str | None) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    candidates: list[dict[str, Any]] = []
    for key in vendor_storage.list_keys(provider=provider):
        if key.get("status") != "active":
            continue
        key_model = key.get("model")
        if key_model and model and str(key_model) != str(model):
            continue
        if key_model and not model:
            continue
        cooldown_until = _parse_dt(key.get("cooldown_until"))
        if cooldown_until and cooldown_until > now:
            continue
        candidates.append(key)
    return sorted(
        candidates,
        key=lambda item: (
            int(item.get("usage_count") or 0),
            str(item.get("last_used_at") or ""),
            str(item.get("id") or ""),
        ),
    )


def _runtime_key_from_credentials(
    *,
    provider: str,
    model: str | None,
    credentials: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(credentials, dict) or not credentials:
        return None
    key = credentials.get("key") or credentials.get("apiKey") or credentials.get("api_key")
    if not key:
        return None
    secret = credentials.get("secret") or credentials.get("secretKey") or credentials.get("secret_key")
    key_id = credentials.get("keyId") or credentials.get("apiKeyId") or credentials.get("id")
    try:
        max_concurrency = int(credentials.get("maxConcurrency") or credentials.get("max_concurrency") or 1)
    except Exception:
        max_concurrency = 1
    return {
        "id": f"request:{provider}:{key_id or 'inline'}",
        "provider": provider,
        "model": model,
        "key": str(key),
        "secret": str(secret) if secret else None,
        "status": "active",
        "max_concurrency": max(1, max_concurrency),
    }


def _safe_invocation_request(request: InvocationRequest) -> dict[str, Any]:
    payload = request.model_dump(mode="json")
    credentials = payload.get("credentials")
    if isinstance(credentials, dict) and credentials:
        key_id = credentials.get("keyId") or credentials.get("apiKeyId") or credentials.get("id")
        payload["credentials"] = {
            "present": True,
            "source": "backend-request",
            "keyId": str(key_id) if key_id else None,
        }
    return payload


def _read_key(item: dict[str, Any]) -> VendorKeyRead:
    return VendorKeyRead(
        id=item["id"],
        provider=item["provider"],
        alias=item["alias"],
        model=item.get("model"),
        status=item["status"],
        keyPreview=_preview_secret(item.get("key") or ""),
        dailyQuota=item.get("daily_quota"),
        monthlyQuota=item.get("monthly_quota"),
        usageCount=item.get("usage_count") or 0,
        maxConcurrency=item.get("max_concurrency") or 1,
        cooldownUntil=_parse_dt(item.get("cooldown_until")),
        lastError=item.get("last_error"),
        lastUsedAt=_parse_dt(item.get("last_used_at")),
        metadata=item.get("metadata") or {},
    )


def _response_from_record(record: dict[str, Any] | None) -> InvocationResponse:
    if not record:
        now = _now()
        return InvocationResponse(
            success=False,
            status="failed",
            provider="unknown",
            vendorInvocationId=f"vinv_{uuid4().hex}",
            error=InvocationError(code=ERR_INVOCATION_NOT_FOUND, message="Invocation not found"),
            createdAt=now,
            updatedAt=now,
        )
    result_payload = record.get("response") if isinstance(record.get("response"), dict) else {}
    error_payload = record.get("error") if isinstance(record.get("error"), dict) else None
    return InvocationResponse(
        success=bool(record.get("success")),
        status=str(record.get("status") or "failed"),
        provider=str(record.get("provider") or ""),
        model=record.get("model"),
        vendorInvocationId=str(record.get("id")),
        vendorTaskId=record.get("vendor_task_id"),
        result=InvocationResult.model_validate(result_payload or {}),
        error=InvocationError.model_validate(error_payload) if error_payload else None,
        raw=record.get("raw") if isinstance(record.get("raw"), dict) else {},
        createdAt=_parse_dt(record.get("created_at")),
        updatedAt=_parse_dt(record.get("updated_at")),
    )


def _preview_secret(value: str) -> str:
    raw = str(value or "")
    if len(raw) <= 8:
        return "***"
    return f"{raw[:4]}...{raw[-4:]}"


def _as_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


invocation_store = InvocationStore()
