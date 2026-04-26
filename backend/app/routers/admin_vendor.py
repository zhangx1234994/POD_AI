"""Admin proxy endpoints for vendor-api-ops."""

from __future__ import annotations

from datetime import datetime, timezone
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
    return vendor_admin_client.usage_summary(window_hours=max(1, int(windowHours or 24)))


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
        with get_session() as session:
            _ensure_builtin_model_catalog(session, providers)
            stmt = select(VendorModelCatalog).order_by(VendorModelCatalog.provider, VendorModelCatalog.model)
            items = session.execute(stmt).scalars().all()
            return {"baseUrl": base_url, "items": [_model_to_payload(item) for item in items]}
    except SQLAlchemyError:
        items = _build_builtin_model_items(providers)
        return {"baseUrl": base_url, "items": items}


@router.post("/models", response_model=schemas.VendorModelRead, status_code=status.HTTP_201_CREATED)
def create_vendor_model(payload: schemas.VendorModelCreateRequest) -> dict[str, Any]:
    data = _normalize_model_payload(_camel_model_to_snake(payload.model_dump()))
    try:
        with get_session() as session:
            item = VendorModelCatalog(**data)
            session.add(item)
            session.commit()
            session.refresh(item)
            return _model_to_payload(item)
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
    try:
        with get_session() as session:
            item = session.get(VendorModelCatalog, model_id)
            if not item:
                raise HTTPException(status_code=404, detail="VENDOR_MODEL_NOT_FOUND")
            for key, value in data.items():
                setattr(item, key, value)
            session.commit()
            session.refresh(item)
            return _model_to_payload(item)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="VENDOR_MODEL_DUPLICATED") from exc


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
        elif status_value:
            summary_by_provider[provider]["failedCalls"] += count
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
        item["runtimeKeyConfigured"] = bool(item["envKeyConfigured"] or item["activeStoredKeyCount"] > 0)
        if (item["activeModelCount"] or item["activeAbilityCount"]) and not item["runtimeKeyConfigured"]:
            item["issues"].append("VENDOR_API_KEY_MISSING")
            item["suggestions"].append("在中台 Key 池新增可用密钥；中台调用时会把 Key 随请求带给能力服务。")
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
        "runtimeKeyConfigured": False,
        "keyCount": 0,
        "activeStoredKeyCount": 0,
        "disabledKeyCount": 0,
        "cooldownKeyCount": 0,
        "exhaustedKeyCount": 0,
        "errorKeyCount": 0,
        "modelCount": 0,
        "activeModelCount": 0,
        "abilityCount": 0,
        "activeAbilityCount": 0,
        "succeededCalls": 0,
        "failedCalls": 0,
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
        else:
            data[key] = value if isinstance(value, dict) else {}
    return data


def _model_to_payload(item: VendorModelCatalog) -> dict[str, Any]:
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
        "metadata": item.extra_metadata or {},
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
