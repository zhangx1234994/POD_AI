"""vendor-api-ops FastAPI app."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status

from app.config import get_settings
from app.invocations import ERR_INVOCATION_NOT_FOUND, invocation_store
from app.providers import check_provider_egress, list_providers
from app.schemas import (
    ErrorPayload,
    EgressCheckRequest,
    EgressCheckResponse,
    InvocationRequest,
    InvocationResponse,
    ProvidersResponse,
    UsageSummaryResponse,
    VendorKeyCreateRequest,
    VendorKeyListResponse,
    VendorKeyRead,
    VendorKeyUpdateRequest,
)

app = FastAPI(title="PODI Vendor API Ops", version="0.1.0")


def require_service_token(authorization: str | None = Header(default=None)) -> None:
    token = get_settings().admin_token
    if not token:
        return
    expected = f"Bearer {token}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorPayload(
                errorCode="VENDOR_API_AUTH_REQUIRED",
                message="vendor-api-ops requires a valid service token.",
            ).model_dump(),
        )


@app.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "service": settings.service_name}


@app.get("/v1/providers", response_model=ProvidersResponse)
def providers() -> ProvidersResponse:
    settings = get_settings()
    return ProvidersResponse(service=settings.service_name, providers=list_providers(settings))


@app.post("/v1/providers/{provider}/egress-check", response_model=EgressCheckResponse, dependencies=[Depends(require_service_token)])
async def provider_egress_check(provider: str, payload: EgressCheckRequest | None = None) -> EgressCheckResponse:
    settings = get_settings()
    request = payload or EgressCheckRequest()
    return await check_provider_egress(
        settings=settings,
        provider=provider,
        check=request.check,
        include_auth=request.includeAuth,
    )


@app.post("/v1/invocations", response_model=InvocationResponse, dependencies=[Depends(require_service_token)])
def create_invocation(payload: InvocationRequest) -> InvocationResponse:
    return invocation_store.submit(payload)


@app.get("/v1/invocations/{vendor_invocation_id}", response_model=InvocationResponse, dependencies=[Depends(require_service_token)])
def get_invocation(vendor_invocation_id: str) -> InvocationResponse:
    item = invocation_store.get(vendor_invocation_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorPayload(
                errorCode=ERR_INVOCATION_NOT_FOUND,
                message=f"Invocation not found: {vendor_invocation_id}",
            ).model_dump(),
        )
    return item


@app.post("/v1/keys", response_model=VendorKeyRead, dependencies=[Depends(require_service_token)])
def create_key(payload: VendorKeyCreateRequest) -> VendorKeyRead:
    return invocation_store.create_key(payload)


@app.get("/v1/keys", response_model=VendorKeyListResponse, dependencies=[Depends(require_service_token)])
def list_keys(provider: str | None = None) -> VendorKeyListResponse:
    return VendorKeyListResponse(items=invocation_store.list_keys(provider=provider))


@app.get("/v1/usage/summary", response_model=UsageSummaryResponse, dependencies=[Depends(require_service_token)])
def usage_summary(windowHours: int = 24) -> UsageSummaryResponse:
    rows = invocation_store.usage_summary(window_hours=windowHours)
    return UsageSummaryResponse(windowHours=max(1, int(windowHours or 24)), items=rows)


@app.patch("/v1/keys/{key_id}", response_model=VendorKeyRead, dependencies=[Depends(require_service_token)])
def update_key(key_id: str, payload: VendorKeyUpdateRequest) -> VendorKeyRead:
    item = invocation_store.update_key(key_id, payload)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorPayload(
                errorCode="VENDOR_API_KEY_NOT_FOUND",
                message=f"Key not found: {key_id}",
            ).model_dump(),
        )
    return item


@app.post("/v1/keys/{key_id}/check", response_model=EgressCheckResponse, dependencies=[Depends(require_service_token)])
async def check_key(key_id: str, payload: EgressCheckRequest | None = None) -> EgressCheckResponse:
    request = payload or EgressCheckRequest()
    check_name = request.check if payload and "check" in payload.model_fields_set else None
    item, result = await invocation_store.check_key(key_id, check=check_name)
    if item is None or result is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorPayload(
                errorCode="VENDOR_API_KEY_NOT_FOUND",
                message=f"Key not found: {key_id}",
            ).model_dump(),
        )
    return result
