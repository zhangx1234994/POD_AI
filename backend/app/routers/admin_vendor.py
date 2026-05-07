"""Admin proxy endpoints for vendor-api-ops."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import get_settings
from app.core.db import get_session
from app.deps.auth import require_admin
from app.models.integration import Ability, ApiKey, VendorModelCatalog
from app.schemas import admin_vendor as schemas
from app.services.api_key_selector import build_vendor_credentials, pick_provider_api_key
from app.services.vendor_admin_client import vendor_admin_client

router = APIRouter(prefix="/admin/vendor-api", dependencies=[Depends(require_admin)])
VENDOR_KEY_CHECK_STALE_DAYS = 7


@router.get("/providers", response_model=schemas.VendorProviderListResponse)
def list_vendor_providers() -> dict[str, Any]:
    return vendor_admin_client.list_providers()


@router.post("/providers/{provider}/egress-check", response_model=schemas.VendorEgressCheckResponse)
def check_vendor_provider_egress(provider: str, payload: schemas.VendorEgressCheckRequest) -> dict[str, Any]:
    request_payload = payload.model_dump()
    if payload.includeAuth:
        with get_session() as session:
            api_key = pick_provider_api_key(session, provider=provider.strip().lower())
            if api_key:
                request_payload["credentials"] = build_vendor_credentials(api_key)
    return vendor_admin_client.check_egress(provider, request_payload)


@router.get("/keys", response_model=schemas.VendorKeyListResponse)
def list_vendor_keys(provider: str | None = None) -> dict[str, Any]:
    return {"baseUrl": get_settings().vendor_api_base_url, "items": _list_backend_vendor_keys(provider)}


@router.get("/usage/summary", response_model=schemas.VendorUsageSummaryResponse)
def get_vendor_usage_summary(windowHours: int = 24) -> dict[str, Any]:
    window_hours = max(1, int(windowHours or 24))
    try:
        return vendor_admin_client.usage_summary(window_hours=window_hours)
    except HTTPException:
        # 管理端总览不能因为 vendor-api-ops 未授权/临时离线而整体报错；
        # 详细问题仍由治理摘要接口统一展示。
        return {"baseUrl": get_settings().vendor_api_base_url, "windowHours": window_hours, "items": []}


@router.get("/governance/summary", response_model=schemas.VendorGovernanceSummaryResponse)
def get_vendor_governance_summary(windowHours: int = 24) -> dict[str, Any]:
    return _build_vendor_governance_summary(window_hours=max(1, int(windowHours or 24)))


@router.post("/keys", response_model=schemas.VendorKeyRead)
def create_vendor_key(payload: schemas.VendorKeyCreateRequest) -> dict[str, Any]:
    metadata = dict(payload.metadata or {})
    if payload.secret:
        metadata["secretKey"] = payload.secret
    if payload.model:
        metadata["model"] = payload.model
    if payload.monthlyQuota is not None:
        metadata["monthlyQuota"] = payload.monthlyQuota
    metadata["maxConcurrency"] = max(1, int(payload.maxConcurrency or 1))
    item = ApiKey(
        id=f"apikey_{uuid4().hex}",
        provider=payload.provider.strip().lower(),
        name=payload.alias.strip(),
        key=payload.key,
        status=payload.status,
        daily_quota=payload.dailyQuota,
        extra_metadata=metadata,
    )
    with get_session() as session:
        session.add(item)
        session.commit()
        session.refresh(item)
        return _api_key_to_vendor_payload(item)


@router.patch("/keys/{key_id}", response_model=schemas.VendorKeyRead)
def update_vendor_key(key_id: str, payload: schemas.VendorKeyUpdateRequest) -> dict[str, Any]:
    with get_session() as session:
        item = session.get(ApiKey, key_id)
        if not item:
            raise HTTPException(status_code=404, detail="VENDOR_API_KEY_NOT_FOUND")
        metadata = dict(item.extra_metadata or {})
        if payload.status is not None:
            item.status = payload.status
        if payload.cooldownUntil is not None:
            metadata["cooldown_until"] = payload.cooldownUntil.isoformat()
        if payload.lastError is not None:
            metadata["last_error"] = payload.lastError
        if payload.metadata is not None:
            metadata.update(payload.metadata)
        item.extra_metadata = metadata
        session.add(item)
        session.commit()
        session.refresh(item)
        return _api_key_to_vendor_payload(item)


@router.post("/keys/{key_id}/check", response_model=schemas.VendorEgressCheckResponse)
def check_vendor_key(key_id: str, payload: schemas.VendorEgressCheckRequest) -> dict[str, Any]:
    with get_session() as session:
        item = session.get(ApiKey, key_id)
        if not item:
            raise HTTPException(status_code=404, detail="VENDOR_API_KEY_NOT_FOUND")
        provider = item.provider
        request_payload = payload.model_dump(mode="json", exclude_none=True)
        request_payload["includeAuth"] = True
        request_payload["credentials"] = build_vendor_credentials(item)
    result = vendor_admin_client.check_egress(provider, request_payload)
    with get_session() as session:
        item = session.get(ApiKey, key_id)
        if item:
            metadata = dict(item.extra_metadata or {})
            metadata["lastCheck"] = {
                "success": bool(result.get("success")),
                "check": result.get("check"),
                "httpStatus": result.get("httpStatus"),
                "latencyMs": result.get("latencyMs"),
                "errorCode": result.get("errorCode"),
                "message": result.get("message"),
                "checkedAt": datetime.now(timezone.utc).isoformat(),
            }
            if result.get("success"):
                metadata.pop("last_error", None)
            else:
                metadata["last_error"] = result.get("errorCode") or result.get("message") or "VENDOR_API_AUTH_FAILED"
            item.extra_metadata = metadata
            session.add(item)
            session.commit()
    return result


@router.get("/models", response_model=schemas.VendorModelListResponse)
def list_vendor_models() -> dict[str, Any]:
    providers: dict[str, Any] = {"baseUrl": get_settings().vendor_api_base_url, "providers": []}
    try:
        providers = vendor_admin_client.list_providers()
    except HTTPException:
        # Model catalog is control-plane data. Keep it readable even when
        # vendor-api-ops is temporarily unavailable.
        providers = {"baseUrl": get_settings().vendor_api_base_url, "providers": []}
    base_url = str(providers.get("baseUrl") or get_settings().vendor_api_base_url)
    try:
        keys = _list_backend_vendor_keys()
    except SQLAlchemyError:
        keys = []
    provider_index = _vendor_provider_index(providers)
    keys_by_provider = _vendor_keys_by_provider(keys)
    try:
        with get_session() as session:
            _ensure_builtin_model_catalog(session, providers)
            stmt = select(VendorModelCatalog).order_by(VendorModelCatalog.provider, VendorModelCatalog.model)
            items = session.execute(stmt).scalars().all()
            return {
                "baseUrl": base_url,
                "items": [
                    _model_to_payload(item, provider_index=provider_index, keys_by_provider=keys_by_provider)
                    for item in items
                ],
            }
    except SQLAlchemyError:
        items = _build_builtin_model_items(providers)
        return {"baseUrl": base_url, "items": items}


@router.post("/models", response_model=schemas.VendorModelRead, status_code=status.HTTP_201_CREATED)
def create_vendor_model(payload: schemas.VendorModelCreateRequest) -> dict[str, Any]:
    data = _normalize_model_payload(_camel_model_to_snake(payload.model_dump()))
    provider_index, keys_by_provider = _safe_vendor_model_payload_context()
    try:
        with get_session() as session:
            item = VendorModelCatalog(**data)
            session.add(item)
            session.commit()
            session.refresh(item)
            return _model_to_payload(item, provider_index=provider_index, keys_by_provider=keys_by_provider)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="VENDOR_MODEL_DUPLICATED") from exc


@router.post("/models/sync/volcengine")
def sync_volcengine_models() -> dict[str, Any]:
    settings = get_settings()
    api_key = settings.volcengine_api_key
    try:
        with get_session() as session:
            stored_key = pick_provider_api_key(session, provider="volcengine")
            if stored_key:
                api_key = stored_key.key
    except SQLAlchemyError:
        # Some lightweight tests/tools create only the model catalog table. In
        # that case, keep env-based model sync available.
        pass
    if not api_key:
        raise HTTPException(status_code=400, detail="VOLCENGINE_API_KEY_MISSING")
    base_url = (settings.volcengine_base_url or "https://ark.cn-beijing.volces.com").rstrip("/")
    url = f"{base_url}/api/v3/models"
    try:
        response = httpx.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=20)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"VOLCENGINE_MODEL_SYNC_HTTP_ERROR:{exc}") from exc
    if response.status_code >= 400:
        snippet = (response.text or "")[:300]
        raise HTTPException(status_code=502, detail=f"VOLCENGINE_MODEL_SYNC_HTTP_{response.status_code}:{snippet}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="VOLCENGINE_MODEL_SYNC_RESPONSE_INVALID") from exc
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise HTTPException(status_code=502, detail="VOLCENGINE_MODEL_SYNC_DATA_INVALID")

    now = datetime.utcnow().isoformat()
    created = 0
    updated = 0
    skipped = 0
    with get_session() as session:
        for row in rows:
            normalized = _volcengine_model_to_catalog_payload(row, synced_at=now)
            if not normalized:
                skipped += 1
                continue
            existing = (
                session.execute(
                    select(VendorModelCatalog).where(
                        VendorModelCatalog.provider == normalized["provider"],
                        VendorModelCatalog.model == normalized["model"],
                    )
                )
                .scalars()
                .first()
            )
            data = _normalize_model_payload(_camel_model_to_snake(normalized))
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                session.add(existing)
                updated += 1
            else:
                session.add(VendorModelCatalog(**data))
                created += 1
        session.commit()
    return {
        "provider": "volcengine",
        "sourceUrl": url,
        "total": len(rows),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


@router.patch("/models/{model_id}", response_model=schemas.VendorModelRead)
def update_vendor_model(model_id: int, payload: schemas.VendorModelUpdateRequest) -> dict[str, Any]:
    data = _normalize_model_payload(_camel_model_to_snake(payload.model_dump(exclude_none=True)))
    provider_index, keys_by_provider = _safe_vendor_model_payload_context()
    try:
        with get_session() as session:
            item = session.get(VendorModelCatalog, model_id)
            if not item:
                raise HTTPException(status_code=404, detail="VENDOR_MODEL_NOT_FOUND")
            before = _vendor_model_audit_snapshot(item)
            for key, value in data.items():
                if key == "extra_metadata":
                    value = _merge_vendor_model_metadata(item.extra_metadata, value)
                setattr(item, key, value)
            after = _vendor_model_audit_snapshot(item)
            metadata = dict(item.extra_metadata or {})
            item.extra_metadata = _append_vendor_model_audit(
                metadata,
                action="update",
                note="管理端编辑模型配置",
                before=before,
                after=after,
            )
            session.commit()
            session.refresh(item)
            return _model_to_payload(item, provider_index=provider_index, keys_by_provider=keys_by_provider)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="VENDOR_MODEL_DUPLICATED") from exc


@router.post("/models/bulk-action", response_model=schemas.VendorModelBulkActionResponse)
def bulk_action_vendor_models(payload: schemas.VendorModelBulkActionRequest) -> dict[str, Any]:
    action = str(payload.action or "").strip().lower()
    allowed_actions = {"enable", "disable", "record_acceptance", "apply_cost_policy"}
    if action not in allowed_actions:
        raise HTTPException(status_code=400, detail="VENDOR_MODEL_BULK_ACTION_INVALID")
    model_ids = _unique_ints(payload.modelIds)
    if not model_ids:
        raise HTTPException(status_code=400, detail="VENDOR_MODEL_BULK_MODEL_IDS_REQUIRED")
    normalized_cost_policy: dict[str, Any] | None = None
    if action == "apply_cost_policy":
        normalized_cost_policy = _normalize_cost_policy(payload.costPolicy or {})
        if not _has_vendor_model_cost_policy(normalized_cost_policy):
            raise HTTPException(status_code=400, detail="VENDOR_MODEL_COST_POLICY_INVALID")
    acceptance_payload = payload.acceptance or schemas.VendorModelAcceptanceRecordRequest(
        status="passed",
        note=payload.note or "批量记录：能力测试已跑通，结果回填正常。",
        metadata={"source": "admin-model-bulk-action"},
    )
    if action == "record_acceptance":
        _normalize_acceptance_status(acceptance_payload.status)

    provider_index, keys_by_provider = _safe_vendor_model_payload_context()
    results: list[dict[str, Any]] = []
    updated = 0
    note = str(payload.note or "").strip() or None
    with get_session() as session:
        for model_id in model_ids:
            item = session.get(VendorModelCatalog, model_id)
            if not item:
                results.append({"modelId": model_id, "success": False, "error": "VENDOR_MODEL_NOT_FOUND"})
                continue
            before = _vendor_model_audit_snapshot(item)
            metadata = dict(item.extra_metadata or {})
            if action == "enable":
                item.status = "active"
            elif action == "disable":
                item.status = "disabled"
            elif action == "apply_cost_policy":
                item.cost_policy = dict(normalized_cost_policy or {})
            elif action == "record_acceptance":
                record = _build_vendor_model_acceptance_record(acceptance_payload)
                metadata = _insert_vendor_model_acceptance_record(metadata, record)
            after = _vendor_model_audit_snapshot(item, metadata=metadata)
            item.extra_metadata = _append_vendor_model_audit(
                metadata,
                action=action,
                note=note or _vendor_model_bulk_action_default_note(action),
                before=before,
                after=after,
            )
            session.add(item)
            session.flush()
            updated += 1
            results.append(
                {
                    "modelId": model_id,
                    "success": True,
                    "model": _model_to_payload(
                        item,
                        provider_index=provider_index,
                        keys_by_provider=keys_by_provider,
                    ),
                }
            )
        session.commit()
    failed = len([item for item in results if not item.get("success")])
    return {
        "action": action,
        "total": len(model_ids),
        "updated": updated,
        "failed": failed,
        "items": results,
    }


@router.post("/models/{model_id}/acceptance-records", response_model=schemas.VendorModelRead)
def record_vendor_model_acceptance(
    model_id: int,
    payload: schemas.VendorModelAcceptanceRecordRequest,
) -> dict[str, Any]:
    record = _build_vendor_model_acceptance_record(payload)
    try:
        keys = _list_backend_vendor_keys()
    except SQLAlchemyError:
        keys = []
    try:
        providers = vendor_admin_client.list_providers()
    except HTTPException:
        providers = {"baseUrl": get_settings().vendor_api_base_url, "providers": []}
    with get_session() as session:
        item = session.get(VendorModelCatalog, model_id)
        if not item:
            raise HTTPException(status_code=404, detail="VENDOR_MODEL_NOT_FOUND")
        before = _vendor_model_audit_snapshot(item)
        metadata = dict(item.extra_metadata or {})
        metadata = _insert_vendor_model_acceptance_record(metadata, record)
        item.extra_metadata = _append_vendor_model_audit(
            metadata,
            action="record_acceptance",
            note=record.get("note") or "记录模型验收",
            before=before,
            after=_vendor_model_audit_snapshot(item, metadata=metadata),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return _model_to_payload(
            item,
            provider_index=_vendor_provider_index(providers),
            keys_by_provider=_vendor_keys_by_provider(keys),
        )


def _list_backend_vendor_keys(provider: str | None = None) -> list[dict[str, Any]]:
    normalized = provider.strip().lower() if isinstance(provider, str) and provider.strip() else None
    with get_session() as session:
        stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
        if normalized:
            stmt = stmt.where(ApiKey.provider == normalized)
        else:
            stmt = stmt.where(ApiKey.provider.in_(_known_vendor_providers()))
        return [_api_key_to_vendor_payload(item) for item in session.execute(stmt).scalars().all()]


def _api_key_to_vendor_payload(item: ApiKey) -> dict[str, Any]:
    metadata = item.extra_metadata if isinstance(item.extra_metadata, dict) else {}
    last_check = metadata.get("lastCheck") if isinstance(metadata.get("lastCheck"), dict) else {}
    return {
        "id": item.id,
        "provider": item.provider,
        "alias": item.name,
        "model": metadata.get("model"),
        "status": item.status,
        "keyPreview": _preview_secret(item.key),
        "dailyQuota": item.daily_quota,
        "monthlyQuota": _as_optional_int(metadata.get("monthlyQuota")),
        "usageCount": item.usage_count or 0,
        "maxConcurrency": _as_optional_int(metadata.get("maxConcurrency")) or 1,
        "cooldownUntil": _parse_datetime(metadata.get("cooldown_until")),
        "lastError": metadata.get("last_error"),
        "lastUsedAt": _parse_last_used_at(metadata.get("last_used_at")),
        "metadata": _public_key_metadata(metadata, last_check),
    }


def _public_key_metadata(metadata: dict[str, Any], last_check: dict[str, Any]) -> dict[str, Any]:
    clean = {
        key: value
        for key, value in metadata.items()
        if key not in {"secret", "secretKey", "secret_key", "clientSecret"}
    }
    clean["storage"] = "backend"
    if last_check:
        clean["lastCheck"] = last_check
    return clean


def _preview_secret(value: str | None) -> str:
    raw = str(value or "")
    if len(raw) <= 8:
        return "***" if raw else ""
    return f"{raw[:4]}...{raw[-4:]}"


def _as_optional_int(value: Any) -> int | None:
    if value in (None, "", []):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_last_used_at(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return _parse_datetime(value)


def _build_vendor_governance_summary(*, window_hours: int) -> dict[str, Any]:
    settings = get_settings()
    base_url = settings.vendor_api_base_url
    issues: list[str] = []
    providers_payload: dict[str, Any] = {"baseUrl": base_url, "providers": []}
    provider_available = True

    try:
        providers_payload = vendor_admin_client.list_providers()
        base_url = str(providers_payload.get("baseUrl") or base_url)
    except HTTPException as exc:
        provider_available = False
        issues.append(f"VENDOR_PROVIDER_REGISTRY_UNAVAILABLE:{_http_detail_code(exc)}")

    try:
        keys = _list_backend_vendor_keys()
    except SQLAlchemyError as exc:
        keys = []
        issues.append(f"VENDOR_KEY_STATUS_UNAVAILABLE:{exc.__class__.__name__}")

    try:
        usage_payload = vendor_admin_client.usage_summary(window_hours=window_hours)
        usage_rows = usage_payload.get("items") if isinstance(usage_payload, dict) else []
        if not isinstance(usage_rows, list):
            usage_rows = []
    except HTTPException as exc:
        usage_rows = []
        issues.append(f"VENDOR_USAGE_SUMMARY_UNAVAILABLE:{_http_detail_code(exc)}")

    models: list[VendorModelCatalog] = []
    abilities: list[Ability] = []
    active_model_cost_configured: dict[str, bool] = {}
    unpriced_active_model_count: dict[str, int] = {}
    try:
        with get_session() as session:
            if provider_available:
                _ensure_builtin_model_catalog(session, providers_payload)
            models = session.execute(select(VendorModelCatalog)).scalars().all()
            abilities = (
                session.execute(select(Ability).where(Ability.provider.in_(_known_vendor_providers())))
                .scalars()
                .all()
            )
    except SQLAlchemyError as exc:
        issues.append(f"VENDOR_GOVERNANCE_DB_UNAVAILABLE:{exc.__class__.__name__}")

    provider_index: dict[str, dict[str, Any]] = {}
    for provider in providers_payload.get("providers") or []:
        if not isinstance(provider, dict):
            continue
        key = str(provider.get("provider") or "").strip().lower()
        if not key:
            continue
        provider_index[key] = provider

    all_provider_keys = set(provider_index)
    all_provider_keys.update(
        str(item.provider or "").strip().lower() for item in models if str(item.provider or "").strip()
    )
    all_provider_keys.update(
        str(item.provider or "").strip().lower() for item in abilities if str(item.provider or "").strip()
    )
    all_provider_keys.update(
        str(item.get("provider") or "").strip().lower()
        for item in keys
        if isinstance(item, dict) and str(item.get("provider") or "").strip()
    )
    all_provider_keys.update(
        str(item.get("provider") or "").strip().lower()
        for item in usage_rows
        if isinstance(item, dict) and str(item.get("provider") or "").strip()
    )

    summaries = [
        _empty_provider_governance_item(provider, provider_index.get(provider))
        for provider in sorted(all_provider_keys)
    ]
    summary_by_provider = {item["provider"]: item for item in summaries}

    for model in models:
        provider = str(model.provider or "").strip().lower()
        if provider not in summary_by_provider:
            continue
        summary_by_provider[provider]["modelCount"] += 1
        if model.status == "active":
            summary_by_provider[provider]["activeModelCount"] += 1
            has_cost_policy = _has_vendor_model_cost_policy(model.cost_policy)
            active_model_cost_configured[provider] = active_model_cost_configured.get(provider, False) or has_cost_policy
            if not has_cost_policy:
                unpriced_active_model_count[provider] = unpriced_active_model_count.get(provider, 0) + 1

    for ability in abilities:
        provider = str(ability.provider or "").strip().lower()
        if provider not in summary_by_provider:
            continue
        summary_by_provider[provider]["abilityCount"] += 1
        if ability.status == "active":
            summary_by_provider[provider]["activeAbilityCount"] += 1

    for key in keys:
        if not isinstance(key, dict):
            continue
        provider = str(key.get("provider") or "").strip().lower()
        if provider not in summary_by_provider:
            continue
        item = summary_by_provider[provider]
        item["keyCount"] += 1
        key_status = str(key.get("status") or "").strip().lower()
        if key_status == "active" and not key.get("cooldownUntil"):
            item["activeStoredKeyCount"] += 1
        elif key_status == "disabled":
            item["disabledKeyCount"] += 1
        elif key_status in {"cooldown", "cooling"} or key.get("cooldownUntil"):
            item["cooldownKeyCount"] += 1
        elif key_status == "exhausted":
            item["exhaustedKeyCount"] += 1
        elif key_status == "error":
            item["errorKeyCount"] += 1
        usage_count = _as_int(key.get("usageCount"))
        quota = _first_positive_int(key.get("dailyQuota"), key.get("monthlyQuota"))
        if quota and usage_count >= quota and key_status != "exhausted":
            item["exhaustedKeyCount"] += 1
        elif quota and usage_count >= int(quota * 0.8):
            item.setdefault("_nearQuotaKeyCount", 0)
            item["_nearQuotaKeyCount"] += 1
        if key.get("lastError"):
            item.setdefault("_recentKeyErrorCount", 0)
            item["_recentKeyErrorCount"] += 1
        if key_status == "active":
            last_check = key.get("metadata", {}).get("lastCheck") if isinstance(key.get("metadata"), dict) else None
            if not isinstance(last_check, dict) or not last_check:
                item["uncheckedKeyCount"] += 1
            else:
                checked_at = _parse_datetime(last_check.get("checkedAt"))
                if checked_at and checked_at.tzinfo is None:
                    checked_at = checked_at.replace(tzinfo=timezone.utc)
                if last_check.get("success") is False:
                    item["failedKeyCheckCount"] += 1
                if not checked_at or checked_at < datetime.now(timezone.utc) - timedelta(days=VENDOR_KEY_CHECK_STALE_DAYS):
                    item["staleKeyCheckCount"] += 1

    usage_accumulator: dict[str, dict[str, Any]] = {}
    for row in usage_rows:
        if not isinstance(row, dict):
            continue
        provider = str(row.get("provider") or "").strip().lower()
        if provider not in summary_by_provider:
            continue
        count = _as_int(row.get("count"))
        status_value = str(row.get("status") or "").strip().lower()
        acc = usage_accumulator.setdefault(provider, {"latencyTotal": 0, "latencyCount": 0})
        if status_value in {"succeeded", "success"}:
            summary_by_provider[provider]["succeededCalls"] += count
        elif status_value in {"queued", "pending"}:
            summary_by_provider[provider]["queuedCalls"] += count
        elif status_value in {"running", "processing"}:
            summary_by_provider[provider]["runningCalls"] += count
        elif status_value:
            summary_by_provider[provider]["failedCalls"] += count
            if status_value in {"failed", "failure", "error"} or row.get("errorCode"):
                summary_by_provider[provider].setdefault("_taskFailureCount", 0)
                summary_by_provider[provider]["_taskFailureCount"] += count
        latency = _as_int(row.get("avgLatencyMs"))
        if latency and count:
            acc["latencyTotal"] += latency * count
            acc["latencyCount"] += count
        seen_at = _parse_datetime(row.get("lastSeenAt"))
        current_seen_at = summary_by_provider[provider].get("lastSeenAt")
        if seen_at and (not current_seen_at or seen_at > current_seen_at):
            summary_by_provider[provider]["lastSeenAt"] = seen_at

    for provider, acc in usage_accumulator.items():
        if acc["latencyCount"]:
            summary_by_provider[provider]["avgLatencyMs"] = int(acc["latencyTotal"] / acc["latencyCount"])

    for item in summaries:
        provider = item["provider"]
        item["runtimeKeyConfigured"] = bool(item["envKeyConfigured"] or item["activeStoredKeyCount"] > 0)
        if (item["activeModelCount"] or item["activeAbilityCount"]) and not item["runtimeKeyConfigured"]:
            item["issues"].append("VENDOR_API_KEY_MISSING")
            item["suggestions"].append("在中台 Key 池新增可用密钥；中台调用时会把 Key 随请求带给能力服务。")
        unpriced_count = unpriced_active_model_count.get(provider, 0)
        if unpriced_count and (item["activeAbilityCount"] or item["succeededCalls"]):
            item["issues"].append(f"VENDOR_MODEL_COST_POLICY_MISSING:{unpriced_count}")
            item["suggestions"].append("补齐模型计价策略，否则业务报表只能看到调用，无法准确核算成本。")
        if item["succeededCalls"] and not active_model_cost_configured.get(provider):
            item["issues"].append("VENDOR_API_UNCOSTED_SUCCESS_CALLS")
            item["suggestions"].append("该厂商已有成功调用但没有可用计价模型，上线收费前必须补计价。")
        if item.get("_nearQuotaKeyCount"):
            item["issues"].append(f"VENDOR_API_KEY_QUOTA_NEAR_LIMIT:{item['_nearQuotaKeyCount']}")
            item["suggestions"].append("密钥接近配额上限，先准备备用 Key 或降低该厂商流量。")
        if item["exhaustedKeyCount"] > 0:
            item["issues"].append(f"VENDOR_API_KEY_QUOTA_EXHAUSTED:{item['exhaustedKeyCount']}")
            item["suggestions"].append("有密钥配额已用完，业务发布前需要补额度或切换备用 Key。")
        if item.get("_recentKeyErrorCount"):
            item["issues"].append(f"VENDOR_API_KEY_RECENT_ERROR:{item['_recentKeyErrorCount']}")
            item["suggestions"].append("有密钥最近验证或调用报错，先做单条 Key 验证再放量。")
        if item["uncheckedKeyCount"] > 0:
            item["issues"].append(f"VENDOR_API_KEY_NEVER_CHECKED:{item['uncheckedKeyCount']}")
            item["suggestions"].append("有 active 密钥尚未做过带密钥检查，上线前先逐条验证。")
        if item["staleKeyCheckCount"] > 0:
            item["issues"].append(f"VENDOR_API_KEY_CHECK_STALE:{item['staleKeyCheckCount']}")
            item["suggestions"].append(f"有密钥验证超过 {VENDOR_KEY_CHECK_STALE_DAYS} 天或缺少验证时间，先重新验证再放量。")
        if item["failedKeyCheckCount"] > 0:
            item["issues"].append(f"VENDOR_API_KEY_CHECK_FAILED:{item['failedKeyCheckCount']}")
            item["suggestions"].append("有密钥最近带密钥检查失败，优先替换 Key 或检查上游账号状态。")
        if item["queuedCalls"]:
            item["issues"].append(f"VENDOR_API_TASKS_QUEUED:{item['queuedCalls']}")
            item["suggestions"].append("最近有任务排队，检查厂商并发、Key 并发和业务侧重试节奏。")
        if item["runningCalls"]:
            item["issues"].append(f"VENDOR_API_TASKS_RUNNING_LONG:{item['runningCalls']}")
            item["suggestions"].append("最近有长时间运行任务，优先确认厂商任务是否能正常轮询到终态。")
        if item.get("_taskFailureCount"):
            item["issues"].append(f"VENDOR_API_TASK_FAILURES:{item['_taskFailureCount']}")
            item["suggestions"].append("最近存在第三方任务失败，先看失败样本和上游错误，不要直接切默认版本。")
        if item["failedCalls"] and not item["succeededCalls"]:
            item["issues"].append("VENDOR_API_RECENT_FAILURES")
            item["suggestions"].append("检查供应商余额、密钥状态、网络出口和最近一次上游错误。")
        if item["requiresGlobalEgress"] and not item["runtimeKeyConfigured"]:
            item["suggestions"].append("该供应商需要国际出口，优先部署在 global-egress 能力服务节点。")

    provider_issue_count = sum(len(item["issues"]) for item in summaries)
    totals = {
        "providerCount": len(summaries),
        "modelCount": sum(item["modelCount"] for item in summaries),
        "activeModelCount": sum(item["activeModelCount"] for item in summaries),
        "abilityCount": sum(item["abilityCount"] for item in summaries),
        "activeAbilityCount": sum(item["activeAbilityCount"] for item in summaries),
        "keyCount": sum(item["keyCount"] for item in summaries),
        "activeStoredKeyCount": sum(item["activeStoredKeyCount"] for item in summaries),
        "envKeyProviderCount": sum(1 for item in summaries if item["envKeyConfigured"]),
        "issueCount": provider_issue_count + len(issues),
    }
    return {
        "baseUrl": base_url,
        "windowHours": window_hours,
        "generatedAt": datetime.now(timezone.utc),
        "totals": totals,
        "providers": summaries,
        "issues": issues,
    }


def _known_vendor_providers() -> list[str]:
    return ["openai", "openai_compatible", "volcengine", "baidu", "kie"]


def _empty_provider_governance_item(provider: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    return {
        "provider": provider,
        "displayName": str(payload.get("displayName") or _fallback_provider_name(provider)),
        "providerStatus": str(payload.get("status") or "unknown"),
        "requiresGlobalEgress": bool(payload.get("requiresGlobalEgress")),
        "envKeyConfigured": bool(payload.get("envKeyConfigured")),
        "supportedApiTypes": _normalize_string_list(payload.get("supportedApiTypes")),
        "executionModes": _normalize_string_list(payload.get("executionModes")),
        "runtimeKeyConfigured": False,
        "keyCount": 0,
        "activeStoredKeyCount": 0,
        "disabledKeyCount": 0,
        "cooldownKeyCount": 0,
        "exhaustedKeyCount": 0,
        "errorKeyCount": 0,
        "uncheckedKeyCount": 0,
        "staleKeyCheckCount": 0,
        "failedKeyCheckCount": 0,
        "modelCount": 0,
        "activeModelCount": 0,
        "abilityCount": 0,
        "activeAbilityCount": 0,
        "succeededCalls": 0,
        "failedCalls": 0,
        "queuedCalls": 0,
        "runningCalls": 0,
        "avgLatencyMs": None,
        "lastSeenAt": None,
        "issues": [],
        "suggestions": [],
    }


def _fallback_provider_name(provider: str) -> str:
    return {
        "openai": "OpenAI",
        "openai_compatible": "OpenAI Compatible Relay",
        "volcengine": "火山引擎",
        "baidu": "百度图像处理",
        "kie": "KIE Market",
    }.get(provider, provider)


def _http_detail_code(exc: HTTPException) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        value = detail.get("errorCode") or detail.get("detail") or detail.get("message")
        return str(value or exc.status_code)
    if isinstance(detail, str):
        return detail.split(":", 1)[0]
    return str(exc.status_code)


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _first_positive_int(*values: Any) -> int | None:
    for value in values:
        parsed = _as_int(value)
        if parsed > 0:
            return parsed
    return None


def _has_vendor_model_cost_policy(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    for key in ("unitPrice", "unit_price", "discountPrice", "discount_price", "listPrice", "list_price", "price"):
        if value.get(key) in (None, ""):
            continue
        try:
            if float(value[key]) > 0:
                return True
        except (TypeError, ValueError):
            return False
    return False


def _ensure_builtin_model_catalog(session: Any, providers: dict[str, Any]) -> None:
    builtin_items = _build_builtin_model_items(providers)
    if not builtin_items:
        return
    stmt = select(VendorModelCatalog.provider, VendorModelCatalog.model)
    existing = {(provider, model) for provider, model in session.execute(stmt).all()}
    changed = False
    for item in builtin_items:
        key = (str(item.get("provider") or ""), str(item.get("model") or ""))
        if not key[0] or not key[1] or key in existing:
            continue
        seed_data = _camel_model_to_snake(item)
        for json_key in ("route_policy", "default_task_policy", "input_schema", "cost_policy", "metadata"):
            seed_data.setdefault(json_key, {})
        session.add(VendorModelCatalog(**_normalize_model_payload(seed_data)))
        changed = True
    if changed:
        session.commit()


def _build_builtin_model_items(providers: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for provider in providers.get("providers") or []:
        if not isinstance(provider, dict):
            continue
        provider_key = str(provider.get("provider") or "").strip()
        display_name = str(provider.get("displayName") or provider_key)
        for item in _builtin_models(provider_key, display_name, provider):
            items.append(item)
    return items


def _unique_ints(values: list[int] | None) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for value in values or []:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed <= 0 or parsed in seen:
            continue
        seen.add(parsed)
        out.append(parsed)
    return out


def _build_vendor_model_acceptance_record(payload: schemas.VendorModelAcceptanceRecordRequest) -> dict[str, Any]:
    status_value = _normalize_acceptance_status(payload.status)
    record = {
        "id": f"vmodacc_{uuid4().hex}",
        "status": status_value,
        "note": str(payload.note or "").strip() or None,
        "evidenceRunId": str(payload.evidenceRunId or "").strip() or None,
        "evidenceUrl": str(payload.evidenceUrl or "").strip() or None,
        "checklist": payload.checklist if isinstance(payload.checklist, dict) else {},
        "metadata": payload.metadata if isinstance(payload.metadata, dict) else {},
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    return {key: value for key, value in record.items() if value not in (None, "", {})}


def _insert_vendor_model_acceptance_record(metadata: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    records = metadata.get("acceptanceRecords")
    records = [row for row in records if isinstance(row, dict)] if isinstance(records, list) else []
    metadata["acceptanceRecords"] = [record, *records][:20]
    metadata["latestAcceptance"] = record
    return metadata


def _merge_vendor_model_metadata(existing: dict[str, Any] | None, incoming: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(incoming or {})
    current = existing if isinstance(existing, dict) else {}
    for key in ("acceptanceRecords", "latestAcceptance", "modelAuditRecords"):
        if key not in out and key in current:
            out[key] = current[key]
    return out


def _vendor_model_audit_snapshot(
    item: VendorModelCatalog,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = metadata if isinstance(metadata, dict) else item.extra_metadata or {}
    acceptance = _model_acceptance_summary(metadata)["latest"]
    return {
        "status": item.status,
        "apiTypes": item.api_types or [],
        "executionModes": item.execution_modes or [],
        "requiresGlobalEgress": bool(item.requires_global_egress),
        "costPolicy": item.cost_policy or {},
        "latestAcceptanceStatus": acceptance.get("status") if isinstance(acceptance, dict) else None,
    }


def _append_vendor_model_audit(
    metadata: dict[str, Any],
    *,
    action: str,
    note: str | None,
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    records = metadata.get("modelAuditRecords")
    records = [row for row in records if isinstance(row, dict)] if isinstance(records, list) else []
    record = {
        "id": f"vmodaudit_{uuid4().hex}",
        "action": action,
        "note": str(note or "").strip() or None,
        "before": before,
        "after": after,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    metadata["modelAuditRecords"] = [{key: value for key, value in record.items() if value not in (None, "", {})}, *records][:30]
    return metadata


def _vendor_model_audit_records(metadata: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(metadata, dict):
        return []
    records = metadata.get("modelAuditRecords")
    return [item for item in records if isinstance(item, dict)][:10] if isinstance(records, list) else []


def _vendor_model_bulk_action_default_note(action: str) -> str:
    return {
        "enable": "批量启用模型",
        "disable": "批量停用模型",
        "record_acceptance": "批量记录模型验收",
        "apply_cost_policy": "批量应用计价策略",
    }.get(action, "批量处理模型")


def _normalize_cost_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    policy = dict(value)
    billing_unit = str(policy.get("billingUnit") or policy.get("billing_unit") or "").strip()
    if billing_unit:
        policy["billingUnit"] = billing_unit
        policy.pop("billing_unit", None)
    currency = str(policy.get("currency") or "").strip().upper()
    if currency:
        policy["currency"] = currency
    for key in ("unitPrice", "unit_price", "discountPrice", "discount_price", "listPrice", "list_price", "price"):
        if key not in policy or policy.get(key) in ("", None):
            continue
        try:
            value_float = float(policy[key])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="VENDOR_MODEL_COST_POLICY_INVALID") from exc
        if value_float < 0:
            raise HTTPException(status_code=400, detail="VENDOR_MODEL_COST_POLICY_INVALID")
        if key == "unit_price":
            policy["unitPrice"] = value_float
            policy.pop("unit_price", None)
        else:
            policy[key] = value_float
    for key in ("quotaUnits", "quota_units", "quotaPerRun", "quota_per_run"):
        if key not in policy or policy.get(key) in ("", None):
            continue
        try:
            value_int = int(policy[key])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="VENDOR_MODEL_COST_POLICY_INVALID") from exc
        if value_int < 0:
            raise HTTPException(status_code=400, detail="VENDOR_MODEL_COST_POLICY_INVALID")
        if key == "quota_units":
            policy["quotaUnits"] = value_int
            policy.pop("quota_units", None)
        else:
            policy[key] = value_int
    for key in ("quantityField", "quantity_field", "pricingVersion", "pricing_version"):
        if key in policy and policy.get(key) is not None:
            normalized = str(policy[key]).strip()
            if key == "quantity_field":
                policy["quantityField"] = normalized
                policy.pop("quantity_field", None)
            elif key == "pricing_version":
                policy["pricingVersion"] = normalized
                policy.pop("pricing_version", None)
            else:
                policy[key] = normalized
    return {key: value for key, value in policy.items() if value not in ("", None)}


def _normalize_model_payload(data: dict[str, Any]) -> dict[str, Any]:
    for key in ("provider", "model", "display_name", "status", "source"):
        if key in data and isinstance(data[key], str):
            data[key] = data[key].strip()
    if "api_types" in data:
        data["api_types"] = _normalize_string_list(data.get("api_types"))
    if "execution_modes" in data:
        data["execution_modes"] = _normalize_string_list(data.get("execution_modes"))
    for key in ("route_policy", "default_task_policy", "input_schema", "cost_policy", "metadata"):
        if key not in data:
            continue
        value = data.pop(key, None)
        if key == "metadata":
            data["extra_metadata"] = value if isinstance(value, dict) else {}
        elif key == "cost_policy":
            data[key] = _normalize_cost_policy(value)
        else:
            data[key] = value if isinstance(value, dict) else {}
    return data


def _normalize_acceptance_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    allowed = {"passed", "failed", "warning", "waived"}
    if normalized not in allowed:
        raise HTTPException(status_code=400, detail="VENDOR_MODEL_ACCEPTANCE_STATUS_INVALID")
    return normalized


def _vendor_provider_index(providers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in providers.get("providers") or []:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip().lower()
        if provider:
            out[provider] = item
    return out


def _vendor_keys_by_provider(keys: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for item in keys:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip().lower()
        if provider:
            out.setdefault(provider, []).append(item)
    return out


def _safe_vendor_model_payload_context() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    try:
        providers = vendor_admin_client.list_providers()
    except HTTPException:
        providers = {"baseUrl": get_settings().vendor_api_base_url, "providers": []}
    try:
        keys = _list_backend_vendor_keys()
    except SQLAlchemyError:
        keys = []
    return _vendor_provider_index(providers), _vendor_keys_by_provider(keys)


def _model_acceptance_summary(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {"latest": None, "records": []}
    raw_records = metadata.get("acceptanceRecords")
    records = [item for item in raw_records if isinstance(item, dict)] if isinstance(raw_records, list) else []
    latest = metadata.get("latestAcceptance")
    if not isinstance(latest, dict):
        latest = records[0] if records else None
    return {"latest": latest, "records": records[:5]}


def _model_acceptance_passed(acceptance: dict[str, Any] | None) -> bool:
    return isinstance(acceptance, dict) and str(acceptance.get("status") or "").strip().lower() == "passed"


def _vendor_key_check_risk(keys: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    active_keys = [
        item
        for item in keys
        if str(item.get("status") or "").strip().lower() == "active" and not item.get("cooldownUntil")
    ]
    if not active_keys:
        return blockers, warnings

    unchecked = 0
    stale = 0
    failed = 0
    for item in active_keys:
        last_check = item.get("metadata", {}).get("lastCheck") if isinstance(item.get("metadata"), dict) else None
        if not isinstance(last_check, dict) or not last_check:
            unchecked += 1
            continue
        checked_at = _parse_datetime(last_check.get("checkedAt"))
        if checked_at and checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=timezone.utc)
        if last_check.get("success") is False:
            failed += 1
        if not checked_at or checked_at < datetime.now(timezone.utc) - timedelta(days=VENDOR_KEY_CHECK_STALE_DAYS):
            stale += 1
    if failed and failed >= len(active_keys):
        blockers.append("VENDOR_MODEL_KEY_CHECK_FAILED")
    elif failed:
        warnings.append("VENDOR_MODEL_KEY_CHECK_PARTIAL_FAILED")
    if unchecked:
        warnings.append("VENDOR_MODEL_KEY_NEVER_CHECKED")
    if stale:
        warnings.append("VENDOR_MODEL_KEY_CHECK_STALE")
    return blockers, warnings


def _has_recent_successful_vendor_key_check(keys: list[dict[str, Any]]) -> bool:
    for item in keys:
        if str(item.get("status") or "").strip().lower() != "active" or item.get("cooldownUntil"):
            continue
        last_check = item.get("metadata", {}).get("lastCheck") if isinstance(item.get("metadata"), dict) else None
        if not isinstance(last_check, dict) or last_check.get("success") is not True:
            continue
        checked_at = _parse_datetime(last_check.get("checkedAt"))
        if checked_at and checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=timezone.utc)
        if checked_at and checked_at >= datetime.now(timezone.utc) - timedelta(days=VENDOR_KEY_CHECK_STALE_DAYS):
            return True
    return False


_VENDOR_MODEL_PRIMARY_ACTIONS: tuple[tuple[str, str, str], ...] = (
    ("VENDOR_MODEL_INACTIVE", "启用模型", "先启用模型，或不要把业务能力绑定到该模型。"),
    ("VENDOR_MODEL_RUNTIME_KEY_MISSING", "补密钥", "先配置该厂商可用密钥，再做带密钥验证。"),
    ("VENDOR_MODEL_KEY_CHECK_FAILED", "查密钥", "最近密钥验证失败，先替换密钥或确认厂商账号状态。"),
    ("VENDOR_MODEL_KEY_CHECK_PARTIAL_FAILED", "查密钥", "部分密钥验证失败，先处理异常密钥再放量。"),
    ("VENDOR_MODEL_KEY_NEVER_CHECKED", "验密钥", "上线前先做一次单条密钥验证。"),
    ("VENDOR_MODEL_KEY_CHECK_STALE", "重验密钥", "最近验证超过 7 天，发布前重新做带密钥检查。"),
    ("VENDOR_MODEL_GLOBAL_EGRESS_REQUIRED", "查出网", "该模型需要国际出口，上线前先做一次带密钥出网验证。"),
    ("VENDOR_MODEL_ACCEPTANCE_REQUIRED", "跑验收", "先用能力测试或测评端跑通该模型，并记录一次验收通过。"),
    ("VENDOR_MODEL_API_TYPES_MISSING", "补能力范围", "补齐模型能做图片、视频、文字还是图像理解，避免业务侧选错。"),
    ("VENDOR_MODEL_EXECUTION_MODE_MISSING", "补返回方式", "补齐返回方式，明确同步、异步、轮询或回调。"),
    ("VENDOR_MODEL_COST_POLICY_MISSING", "补计价", "补齐计费单位、币种、单价和定价版本，避免上线后账单不准。"),
)


def _vendor_model_primary_action(blockers: list[str], warnings: list[str]) -> dict[str, Any]:
    issues = [*blockers, *warnings]
    for issue, label, action in _VENDOR_MODEL_PRIMARY_ACTIONS:
        if issue in issues:
            return {
                "primaryIssue": issue,
                "primaryActionLabel": label,
                "primaryAction": action,
                "primarySeverity": "danger" if blockers else "warning",
            }
    return {
        "primaryIssue": None,
        "primaryActionLabel": "可上线",
        "primaryAction": "基础门禁通过，可进入业务绑定和小流量验证。",
        "primarySeverity": "success",
    }


def _vendor_model_release_gate(
    item: VendorModelCatalog,
    *,
    provider_index: dict[str, dict[str, Any]] | None = None,
    keys_by_provider: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    provider = str(item.provider or "").strip().lower()
    provider_payload = (provider_index or {}).get(provider, {})
    provider_keys = (keys_by_provider or {}).get(provider, [])
    env_key_configured = bool(provider_payload.get("envKeyConfigured"))
    active_stored_key_configured = any(
        str(key.get("status") or "").strip().lower() == "active" and not key.get("cooldownUntil")
        for key in provider_keys
    )
    egress_verified = _has_recent_successful_vendor_key_check(provider_keys)
    acceptance = _model_acceptance_summary(item.extra_metadata)["latest"]
    blockers: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []

    if str(item.status or "").strip().lower() != "active":
        blockers.append("VENDOR_MODEL_INACTIVE")
        suggestions.append("先启用模型，或不要把业务能力绑定到该模型。")
    if not _model_acceptance_passed(acceptance):
        blockers.append("VENDOR_MODEL_ACCEPTANCE_REQUIRED")
        suggestions.append("先用能力测试或测评端跑通该模型，并记录一次验收通过。")
    if not env_key_configured and not active_stored_key_configured:
        blockers.append("VENDOR_MODEL_RUNTIME_KEY_MISSING")
        suggestions.append("先在模型弹药库配置可用密钥，并做带密钥验证。")
    key_blockers, key_warnings = _vendor_key_check_risk(provider_keys)
    blockers.extend(key_blockers)
    warnings.extend(key_warnings)
    if key_blockers:
        suggestions.append("最近 Key 验证失败，优先替换 Key 或检查上游账号状态。")
    if key_warnings:
        suggestions.append("上线前重新做一次单条 Key 验证，避免过期验证误导判断。")
    if not item.api_types:
        warnings.append("VENDOR_MODEL_API_TYPES_MISSING")
        suggestions.append("补齐模型能力类型，方便业务侧区分图片、视频、文字或图像理解。")
    if not item.execution_modes:
        warnings.append("VENDOR_MODEL_EXECUTION_MODE_MISSING")
        suggestions.append("补齐返回方式，明确同步、异步、轮询或回调。")
    if not _has_vendor_model_cost_policy(item.cost_policy):
        warnings.append("VENDOR_MODEL_COST_POLICY_MISSING")
        suggestions.append("正式收费或对外开放前补齐成本口径。")
    if item.requires_global_egress and not egress_verified:
        warnings.append("VENDOR_MODEL_GLOBAL_EGRESS_REQUIRED")
        suggestions.append("该模型需要国际出口，上线前先做一次带密钥出网验证。")

    status_value = "ready"
    label = "可上线"
    if blockers:
        status_value = "blocked"
        label = "暂不能上线"
    elif warnings:
        status_value = "warning"
        label = "可小流量，需复核"
    primary_action = _vendor_model_primary_action(blockers, warnings)
    return {
        "status": status_value,
        "label": label,
        "canRelease": status_value == "ready",
        "acceptancePassed": _model_acceptance_passed(acceptance),
        "runtimeKeyConfigured": bool(env_key_configured or active_stored_key_configured),
        "egressVerified": egress_verified,
        "blockers": blockers,
        "warnings": warnings,
        "suggestions": _dedupe_strings([primary_action["primaryAction"], *suggestions]),
        **primary_action,
    }


def _dedupe_strings(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def _model_to_payload(
    item: VendorModelCatalog,
    *,
    provider_index: dict[str, dict[str, Any]] | None = None,
    keys_by_provider: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    metadata = item.extra_metadata or {}
    acceptance = _model_acceptance_summary(metadata)
    return {
        "id": item.id,
        "provider": item.provider,
        "model": item.model,
        "displayName": item.display_name,
        "status": item.status,
        "apiTypes": item.api_types or [],
        "executionModes": item.execution_modes or [],
        "supportsMask": item.supports_mask,
        "supportsMultipleImages": item.supports_multiple_images,
        "supportsVideo": item.supports_video,
        "supportsText": item.supports_text,
        "requiresGlobalEgress": item.requires_global_egress,
        "source": item.source,
        "routePolicy": item.route_policy or {},
        "defaultTaskPolicy": item.default_task_policy or {},
        "inputSchema": item.input_schema or {},
        "costPolicy": item.cost_policy or {},
        "metadata": metadata,
        "latestAcceptance": acceptance["latest"],
        "acceptanceRecords": acceptance["records"],
        "auditRecords": _vendor_model_audit_records(metadata),
        "releaseGate": _vendor_model_release_gate(
            item,
            provider_index=provider_index,
            keys_by_provider=keys_by_provider,
        ),
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


def _camel_model_to_snake(item: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "provider": "provider",
        "model": "model",
        "displayName": "display_name",
        "status": "status",
        "apiTypes": "api_types",
        "executionModes": "execution_modes",
        "supportsMask": "supports_mask",
        "supportsMultipleImages": "supports_multiple_images",
        "supportsVideo": "supports_video",
        "supportsText": "supports_text",
        "requiresGlobalEgress": "requires_global_egress",
        "source": "source",
        "routePolicy": "route_policy",
        "defaultTaskPolicy": "default_task_policy",
        "inputSchema": "input_schema",
        "costPolicy": "cost_policy",
        "metadata": "metadata",
    }
    return {target: item[source] for source, target in mapping.items() if source in item}


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace("；", ",").replace(";", ",").replace("\n", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]
    return [str(item).strip() for item in raw_items if str(item).strip()]


def _volcengine_model_to_catalog_payload(item: Any, *, synced_at: str) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    model_id = str(item.get("id") or item.get("model") or "").strip()
    if not model_id:
        return None
    model_lower = model_id.lower()
    api_types = ["chat_completions"]
    supports_video = False
    supports_multiple_images = False
    if "seedream" in model_lower or "image" in model_lower:
        api_types = ["image_generation", "image_edit"]
        supports_multiple_images = True
    if "seedance" in model_lower or "video" in model_lower:
        api_types = ["video_generation"]
        supports_video = True
    if "vision" in model_lower or "vl" in model_lower or "seed-1-8" in model_lower:
        supports_multiple_images = True
    display_name = str(item.get("name") or item.get("display_name") or model_id).strip()
    metadata = {
        "syncedAt": synced_at,
        "object": item.get("object"),
        "ownedBy": item.get("owned_by") or item.get("owner"),
        "created": item.get("created"),
    }
    return {
        "provider": "volcengine",
        "model": model_id,
        "displayName": display_name,
        "status": "active",
        "apiTypes": api_types,
        "executionModes": ["sync", "sync_then_store"],
        "supportsMask": False,
        "supportsMultipleImages": supports_multiple_images,
        "supportsVideo": supports_video,
        "supportsText": "chat_completions" in api_types,
        "requiresGlobalEgress": False,
        "source": "volcengine-sync",
        "metadata": metadata,
    }


def _builtin_models(provider: str, display_name: str, provider_payload: dict[str, Any]) -> list[dict[str, Any]]:
    requires_global_egress = bool(provider_payload.get("requiresGlobalEgress"))
    execution_modes = [str(x) for x in provider_payload.get("executionModes") or []]
    supported_api_types = [str(x) for x in provider_payload.get("supportedApiTypes") or []]
    if provider == "openai":
        return [
            {
                "provider": provider,
                "model": "gpt-image-2",
                "displayName": "OpenAI · GPT Image 2",
                "status": "active",
                "apiTypes": ["image_generation", "image_edit"],
                "executionModes": execution_modes,
                "supportsMask": True,
                "supportsMultipleImages": True,
                "supportsVideo": False,
                "supportsText": True,
                "requiresGlobalEgress": requires_global_egress,
                "source": "backend-seed",
                "metadata": {
                    "outputSizes": ["1024x1024", "1024x1536", "1536x1024", "auto"],
                    "background": ["auto", "opaque"],
                    "outputFormats": ["png", "jpeg", "webp"],
                },
            }
        ]
    if provider == "kie":
        return [
            {
                "provider": provider,
                "model": "kie-market",
                "displayName": "KIE Market Models",
                "status": "active",
                "apiTypes": supported_api_types,
                "executionModes": execution_modes,
                "supportsMask": False,
                "supportsMultipleImages": True,
                "supportsVideo": True,
                "supportsText": True,
                "requiresGlobalEgress": requires_global_egress,
                "source": "provider",
                "metadata": {"catalog": "backend/constants/kie_model_catalog.py"},
            }
        ]
    if provider == "volcengine":
        return [
            {
                "provider": provider,
                "model": "doubao-seedream",
                "displayName": "Volcengine · Doubao Seedream",
                "status": "active",
                "apiTypes": supported_api_types,
                "executionModes": execution_modes,
                "supportsMask": False,
                "supportsMultipleImages": True,
                "supportsVideo": True,
                "supportsText": True,
                "requiresGlobalEgress": requires_global_egress,
                "source": "provider",
                "metadata": {"baseUrl": "https://ark.cn-beijing.volces.com"},
            }
        ]
    return [
        {
            "provider": provider,
            "model": provider,
            "displayName": display_name,
            "status": "active",
            "apiTypes": supported_api_types,
            "executionModes": execution_modes,
            "supportsMask": False,
            "supportsMultipleImages": False,
            "supportsVideo": "video_generation" in supported_api_types,
            "supportsText": "chat_completions" in supported_api_types,
            "requiresGlobalEgress": requires_global_egress,
            "source": "provider",
            "metadata": {},
        }
    ]
