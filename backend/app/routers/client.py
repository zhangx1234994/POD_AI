"""Ordinary product client API.

The routes here expose business-language resources for the user-facing client.
They intentionally hide mid-platform terms such as project, run, executor, and
workflow from the frontend contract.
"""

from fastapi import APIRouter, Depends, Query

from app.deps.auth import get_current_user
from app.models.user import User
from app.schemas import client as schemas
from app.services.client_workspace import client_workspace_service


router = APIRouter(prefix="/api/client", tags=["client"])


@router.get("/me", response_model=schemas.ClientMeResponse, response_model_by_alias=False)
def get_client_me(user: User = Depends(get_current_user)) -> schemas.ClientMeResponse:
    return schemas.ClientMeResponse(**client_workspace_service.get_me(user=user))


@router.get("/workspace", response_model=schemas.ClientWorkspaceRead, response_model_by_alias=False)
def get_client_workspace(user: User = Depends(get_current_user)) -> schemas.ClientWorkspaceRead:
    return schemas.ClientWorkspaceRead(**client_workspace_service.ensure_default_workspace(user=user))


@router.get("/assets", response_model=schemas.ClientAssetListResponse, response_model_by_alias=False)
def list_client_assets(
    asset_type: str | None = Query(default=None),
    selected: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    user: User = Depends(get_current_user),
) -> schemas.ClientAssetListResponse:
    return schemas.ClientAssetListResponse(
        **client_workspace_service.list_assets(
            user=user,
            asset_type=asset_type,
            selected=selected,
            limit=limit,
        )
    )


@router.post("/assets", response_model=schemas.ClientAssetRead, response_model_by_alias=False)
def create_client_asset(
    payload: schemas.ClientAssetCreateRequest,
    user: User = Depends(get_current_user),
) -> schemas.ClientAssetRead:
    return schemas.ClientAssetRead(**client_workspace_service.create_asset(user=user, payload=payload))


@router.get("/wallet", response_model=schemas.ClientWalletResponse, response_model_by_alias=False)
def get_client_wallet(user: User = Depends(get_current_user)) -> schemas.ClientWalletResponse:
    return schemas.ClientWalletResponse(**client_workspace_service.get_wallet(user=user))
