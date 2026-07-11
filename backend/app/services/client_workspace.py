"""Product client data facade.

This service keeps the ordinary client API in business language while reusing
the current mid-platform project, asset, wallet, and package tables underneath.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.db import get_session
from app.models.integration import BusinessProject, BusinessProjectAsset, BusinessProjectRunLink, BusinessRun
from app.models.user import User
from app.models.wallet import PackageBalance
from app.services.business_projects import PROJECT_ASSET_TYPES
from app.services.wallet import wallet_service


CLIENT_DEFAULT_SCENARIO = "client_default_workspace"
PRODUCT_COUPON_BUSINESS_KEYS = {"sample_request", "product_sample", "product_coupon", "podi_product_coupon"}


class ClientWorkspaceService:
    def get_me(self, *, user: User) -> dict[str, Any]:
        workspace = self.ensure_default_workspace(user=user)
        return {
            "user": self._user_to_client_dict(user),
            "workspace": workspace,
        }

    def ensure_default_workspace(self, *, user: User) -> dict[str, Any]:
        with get_session() as session:
            row = self._get_or_create_default_workspace(session, user=user)
            session.commit()
            session.refresh(row)
            return self._workspace_to_dict(row, session=session)

    def list_assets(
        self,
        *,
        user: User,
        asset_type: str | None = None,
        selected: bool | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        with get_session() as session:
            workspace = self._get_or_create_default_workspace(session, user=user)
            stmt = select(BusinessProjectAsset).where(BusinessProjectAsset.project_id == workspace.id)
            if asset_type:
                stmt = stmt.where(BusinessProjectAsset.asset_type == self._normalize_asset_type(asset_type))
            if selected is not None:
                stmt = stmt.where(BusinessProjectAsset.selected.is_(bool(selected)))
            total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
            rows = (
                session.execute(
                    stmt.order_by(BusinessProjectAsset.created_at.desc(), BusinessProjectAsset.id.desc()).limit(
                        max(1, min(int(limit), 200))
                    )
                )
                .scalars()
                .all()
            )
            session.commit()
            return {"total": int(total), "items": [self._asset_to_client_dict(row) for row in rows]}

    def create_asset(self, *, user: User, payload: Any) -> dict[str, Any]:
        asset_type = self._normalize_asset_type(getattr(payload, "assetType", None))
        url = self._validate_asset_url(getattr(payload, "url", None))
        metadata = self._clean_metadata(getattr(payload, "metadata", None))
        now = datetime.utcnow()
        with get_session() as session:
            workspace = self._get_or_create_default_workspace(session, user=user)
            row = BusinessProjectAsset(
                id=f"asset_{uuid4().hex[:16]}",
                project_id=workspace.id,
                asset_type=asset_type,
                url=url,
                content_type=self._short_text(getattr(payload, "contentType", None), 64),
                file_name=self._short_text(getattr(payload, "fileName", None), 255),
                source_flow_step_key=self._short_text(getattr(payload, "flowStepKey", None), 64),
                input_tags=self._normalize_text_list(getattr(payload, "inputTags", None)),
                issue_tags=self._normalize_text_list(getattr(payload, "issueTags", None)),
                selected=False,
                extra_metadata={**metadata, "clientSource": metadata.get("clientSource") or "client-api"},
                created_at=now,
                updated_at=now,
            )
            session.add(workspace)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._asset_to_client_dict(row)

    def get_wallet(self, *, user: User) -> dict[str, Any]:
        balance = wallet_service.balance(user.id)
        ledger = wallet_service.ledger(user.id, page=1, page_size=20)
        product_coupons = self._list_product_coupons(user_id=user.id)
        return {
            "pointBalance": int(balance.get("balance") or 0),
            "frozenPoints": int(balance.get("frozenBalance") or 0),
            "currency": balance.get("currency") or "CNY",
            "productCouponCount": sum(int(item["remainingUnits"] or 0) for item in product_coupons),
            "productCoupons": product_coupons,
            "ledger": [self._ledger_to_client_dict(item) for item in (ledger.get("items") or [])],
        }

    def _get_or_create_default_workspace(self, session, *, user: User) -> BusinessProject:  # noqa: ANN001
        user_id = self._required_user_id(user)
        row = (
            session.execute(
                select(BusinessProject).where(
                    BusinessProject.owner_user_id == user_id,
                    BusinessProject.scenario == CLIENT_DEFAULT_SCENARIO,
                )
            )
            .scalars()
            .first()
        )
        if row:
            return row
        now = datetime.utcnow()
        row = BusinessProject(
            id=f"proj_{uuid4().hex[:16]}",
            name="默认素材工作区",
            scenario=CLIENT_DEFAULT_SCENARIO,
            status="active",
            tenant_id=self._short_text(getattr(user, "tenant_id", None), 64),
            client_id=self._short_text(getattr(user, "client_id", None), 64),
            owner_user_id=user_id,
            owner_user_name=self._actor_username(user),
            current_flow_step_key="client_workspace",
            flow_template_id="client_p0_workspace",
            extra_metadata={"source": "client-api", "purpose": "ordinary-user-default-workspace"},
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        return row

    def _list_product_coupons(self, *, user_id: str) -> list[dict[str, Any]]:
        now = datetime.utcnow()
        with get_session() as session:
            rows = (
                session.execute(
                    select(PackageBalance)
                    .where(PackageBalance.user_id == user_id)
                    .order_by(PackageBalance.expires_at.is_(None), PackageBalance.expires_at.asc(), PackageBalance.id.asc())
                )
                .scalars()
                .all()
            )
            return [
                self._package_to_coupon_dict(row, now=now)
                for row in rows
                if self._is_product_coupon(row) and self._package_remaining(row) > 0
            ]

    @staticmethod
    def _workspace_to_dict(row: BusinessProject, *, session=None) -> dict[str, Any]:
        asset_count = run_count = 0
        latest_run_status = None
        if session is not None:
            asset_count = (
                session.execute(select(func.count(BusinessProjectAsset.id)).where(BusinessProjectAsset.project_id == row.id))
                .scalar_one()
                or 0
            )
            run_count = (
                session.execute(select(func.count(BusinessProjectRunLink.id)).where(BusinessProjectRunLink.project_id == row.id))
                .scalar_one()
                or 0
            )
            latest_link = (
                session.execute(
                    select(BusinessProjectRunLink)
                    .where(BusinessProjectRunLink.project_id == row.id)
                    .order_by(BusinessProjectRunLink.created_at.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if latest_link:
                latest_run = session.get(BusinessRun, latest_link.run_id)
                latest_run_status = latest_run.status if latest_run else None
        return {
            "id": row.id,
            "name": row.name,
            "scenario": row.scenario,
            "status": row.status,
            "assetCount": int(asset_count or 0),
            "runCount": int(run_count or 0),
            "latestRunStatus": latest_run_status,
            "createdAt": row.created_at,
            "updatedAt": row.updated_at,
        }

    @staticmethod
    def _asset_to_client_dict(row: BusinessProjectAsset) -> dict[str, Any]:
        metadata = row.extra_metadata or {}
        title = metadata.get("title") or metadata.get("name") or row.file_name
        return {
            "id": row.id,
            "assetType": row.asset_type,
            "url": row.url,
            "contentType": row.content_type,
            "fileName": row.file_name,
            "title": title,
            "sourceRunId": row.source_run_id,
            "sourceBusinessKey": row.source_business_key,
            "sourceFlowStepKey": row.source_flow_step_key,
            "qualityGrade": row.quality_grade,
            "inputTags": row.input_tags or [],
            "issueTags": row.issue_tags or [],
            "selected": bool(row.selected),
            "metadata": metadata,
            "createdAt": row.created_at,
            "updatedAt": row.updated_at,
        }

    @staticmethod
    def _package_to_coupon_dict(row: PackageBalance, *, now: datetime) -> dict[str, Any]:
        remaining = ClientWorkspaceService._package_remaining(row)
        status = row.status or "active"
        if row.expires_at and row.expires_at <= now:
            status = "expired"
        return {
            "id": f"pkg_balance_{row.id}",
            "packageKey": row.package_key,
            "name": row.package_name or row.package_key,
            "businessKey": row.business_key,
            "totalUnits": int(row.total_units or 0),
            "usedUnits": int(row.used_units or 0),
            "frozenUnits": int(row.frozen_units or 0),
            "remainingUnits": remaining,
            "unitName": row.unit_name or "次",
            "status": status,
            "source": row.source,
            "expiresAt": row.expires_at,
            "metadata": row.extra_metadata or {},
        }

    @staticmethod
    def _ledger_to_client_dict(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(item.get("id") or ""),
            "points": int(item.get("points") or 0),
            "description": item.get("description"),
            "createdAt": item.get("createdAt"),
            "traceId": item.get("traceId"),
            "taskId": item.get("taskId"),
        }

    @staticmethod
    def _user_to_client_dict(user: User) -> dict[str, Any]:
        return {
            "id": str(user.id),
            "username": str(user.username),
            "email": str(user.email),
            "displayName": getattr(user, "display_name", None),
            "role": str(user.role),
            "status": str(user.status),
            "tenantId": getattr(user, "tenant_id", None),
            "clientId": getattr(user, "client_id", None),
        }

    @staticmethod
    def _is_product_coupon(row: PackageBalance) -> bool:
        metadata = row.extra_metadata if isinstance(row.extra_metadata, dict) else {}
        coupon_type = str(metadata.get("couponType") or metadata.get("coupon_type") or "").strip().lower()
        if coupon_type in {"product", "sample", "product_coupon"}:
            return True
        business_key = str(row.business_key or "").strip().lower()
        package_key = str(row.package_key or "").strip().lower()
        unit_name = str(row.unit_name or "").strip()
        return (
            business_key in PRODUCT_COUPON_BUSINESS_KEYS
            or "coupon" in package_key
            or "产品券" in unit_name
            or unit_name == "张"
        )

    @staticmethod
    def _package_remaining(row: PackageBalance) -> int:
        return max(0, int(row.total_units or 0) - int(row.used_units or 0) - int(row.frozen_units or 0))

    @staticmethod
    def _normalize_asset_type(value: str | None) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in PROJECT_ASSET_TYPES:
            raise HTTPException(status_code=400, detail="PROJECT_ASSET_TYPE_INVALID")
        return normalized

    @staticmethod
    def _validate_asset_url(value: str | None) -> str:
        text = str(value or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="PROJECT_ASSET_URL_REQUIRED")
        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="PROJECT_ASSET_URL_INVALID")
        return text

    @staticmethod
    def _clean_metadata(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _normalize_text_list(values: list[str] | None) -> list[str]:
        return [str(item).strip() for item in values or [] if str(item).strip()][:50]

    @staticmethod
    def _short_text(value: str | None, max_length: int) -> str | None:
        text = str(value or "").strip()
        return text[:max_length] if text else None

    @staticmethod
    def _required_user_id(user: User) -> str:
        user_id = str(getattr(user, "id", "") or "").strip()
        if not user_id:
            raise HTTPException(status_code=401, detail="AUTHORIZATION_REQUIRED")
        return user_id

    @staticmethod
    def _actor_username(user: User) -> str | None:
        return (
            getattr(user, "username", None)
            or getattr(user, "display_name", None)
            or getattr(user, "email", None)
            or getattr(user, "id", None)
        )


client_workspace_service = ClientWorkspaceService()
