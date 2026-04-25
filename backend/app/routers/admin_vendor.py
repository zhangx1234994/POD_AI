"""Admin proxy endpoints for vendor-api-ops."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import get_settings
from app.core.db import get_session
from app.deps.auth import require_admin
from app.models.integration import VendorModelCatalog
from app.schemas import admin_vendor as schemas
from app.services.vendor_admin_client import vendor_admin_client

router = APIRouter(prefix="/admin/vendor-api", dependencies=[Depends(require_admin)])


@router.get("/providers", response_model=schemas.VendorProviderListResponse)
def list_vendor_providers() -> dict[str, Any]:
    return vendor_admin_client.list_providers()


@router.post("/providers/{provider}/egress-check", response_model=schemas.VendorEgressCheckResponse)
def check_vendor_provider_egress(provider: str, payload: schemas.VendorEgressCheckRequest) -> dict[str, Any]:
    return vendor_admin_client.check_egress(provider, payload.model_dump())


@router.get("/keys", response_model=schemas.VendorKeyListResponse)
def list_vendor_keys(provider: str | None = None) -> dict[str, Any]:
    return vendor_admin_client.list_keys(provider)


@router.get("/usage/summary", response_model=schemas.VendorUsageSummaryResponse)
def get_vendor_usage_summary(windowHours: int = 24) -> dict[str, Any]:
    return vendor_admin_client.usage_summary(window_hours=max(1, int(windowHours or 24)))


@router.post("/keys", response_model=schemas.VendorKeyRead)
def create_vendor_key(payload: schemas.VendorKeyCreateRequest) -> dict[str, Any]:
    return vendor_admin_client.create_key(payload.model_dump(mode="json", exclude_none=True))


@router.patch("/keys/{key_id}", response_model=schemas.VendorKeyRead)
def update_vendor_key(key_id: str, payload: schemas.VendorKeyUpdateRequest) -> dict[str, Any]:
    return vendor_admin_client.update_key(key_id, payload.model_dump(mode="json", exclude_none=True))


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
