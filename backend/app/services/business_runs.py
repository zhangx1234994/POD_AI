"""Business capability orchestration service."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import logging
import math
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import and_, func, not_, or_, select, update

from app.core.config import get_settings
from app.core.db import get_session
from app.models.integration import (
    Ability,
    AbilityInvocationLog,
    AbilityTask,
    ApiKey,
    BusinessCapability,
    BusinessClient,
    BusinessDefaultApproval,
    BusinessOperationLog,
    BusinessRun,
    BusinessRunStep,
    VendorModelCatalog,
)
from app.models.user import User
from app.models.wallet import PackageBalance, PackageLedger
from app.schemas.abilities import AbilityInvokeRequest
from app.schemas.business import (
    BusinessAcceptanceRecordRequest,
    BusinessCapabilityCreateRequest,
    BusinessCapabilityPromoteRequest,
    BusinessCapabilityRollbackRequest,
    BusinessCapabilityUpdateRequest,
    BusinessClientCreateRequest,
    BusinessClientUpdateRequest,
    BusinessDefaultApprovalCreateRequest,
    BusinessDefaultApprovalDecisionRequest,
    BusinessRunCreateRequest,
)
from app.services.api_key_selector import is_usable
from app.services.ability_seed import ensure_default_abilities
from app.services.ability_task_service import get_ability_task_service
from app.services.business_seed import ensure_default_business_capabilities
from app.services.pattern_fission_prompt import TEMPLATE_ID as PATTERN_FISSION_TEMPLATE_ID
from app.services.pattern_fission_prompt import compile_pattern_fission_prompt
from app.services.task_id_codec import encode_task_id
from app.services.wallet import wallet_service


logger = logging.getLogger(__name__)
FINALIZE_INTERVAL_SECONDS = 6
FINALIZE_BATCH_SIZE = 30
VENDOR_KEY_CHECK_STALE_DAYS = 7
RECIPE_EXECUTABLE_STEP_TYPES = {"ability_task", "comfyui_workflow", "vendor_api", "vl_analyze", "vl_analyze_image"}
RECIPE_PASSIVE_STEP_TYPES = {"input_mapping", "output_mapping", "prompt_template", "note"}
INTERNAL_NO_CHARGE_SOURCES = {"business-api-patrol"}
INTERNAL_NO_CHARGE_TENANTS = {"podi-internal-patrol"}
INTERNAL_NO_CHARGE_CLIENTS = {"business-api-patrol"}
NO_CHARGE_BILLING_MODES = {"no_charge", "no-charge", "free", "internal", "internal_patrol", "patrol", "test"}


class BusinessRunService:
    def __init__(self) -> None:
        self._thread_started = False
        self._start_finalize_thread()

    def list_capabilities(self) -> list[BusinessCapability]:
        with get_session() as session:
            ensure_default_abilities(session)
            ensure_default_business_capabilities(session)
            rows = (
                session.execute(
                    select(BusinessCapability)
                    .order_by(
                        BusinessCapability.business_key.asc(),
                        BusinessCapability.is_default.desc(),
                        BusinessCapability.release_time.desc(),
                    )
                )
                .scalars()
                .all()
            )
            return [self._capability_to_dict(row, session=session) for row in rows]

    def list_clients(
        self,
        *,
        tenant_id: str | None = None,
        client_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        with get_session() as session:
            stmt = select(BusinessClient)
            if tenant_id:
                stmt = stmt.where(BusinessClient.tenant_id == tenant_id)
            if client_id:
                stmt = stmt.where(BusinessClient.client_id == client_id)
            if status:
                stmt = stmt.where(BusinessClient.status == status)
            rows = session.execute(
                stmt.order_by(BusinessClient.updated_at.desc(), BusinessClient.created_at.desc())
            ).scalars().all()
            return [self._business_client_to_dict(row) for row in rows]

    def create_client(self, payload: BusinessClientCreateRequest) -> dict[str, Any]:
        tenant_id = self._required_text(payload.tenantId, "BUSINESS_CLIENT_TENANT_REQUIRED")
        client_id = self._short_text(payload.clientId, 64)
        display_name = self._required_text(
            payload.displayName or client_id or tenant_id,
            "BUSINESS_CLIENT_DISPLAY_NAME_REQUIRED",
        )
        status = self._normalize_client_status(payload.status)
        with get_session() as session:
            duplicate = self._find_business_client(
                session,
                tenant_id=tenant_id,
                client_id=client_id,
                include_tenant_default=False,
            )
            if duplicate:
                raise HTTPException(status_code=409, detail="BUSINESS_CLIENT_DUPLICATED")
            row = BusinessClient(
                id=self._required_text(payload.id, "BUSINESS_CLIENT_ID_REQUIRED")
                if payload.id
                else f"bizclient_{uuid4().hex[:12]}",
                tenant_id=tenant_id,
                client_id=client_id,
                display_name=display_name,
                status=status,
                allowed_business_keys=self._normalize_business_key_list(payload.allowedBusinessKeys),
                daily_run_limit=payload.dailyRunLimit,
                daily_quota_units=payload.dailyQuotaUnits,
                concurrent_run_limit=payload.concurrentRunLimit,
                extra_metadata=payload.metadata,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._business_client_to_dict(row)

    def update_client(self, client_config_id: str, payload: BusinessClientUpdateRequest) -> dict[str, Any]:
        with get_session() as session:
            row = session.get(BusinessClient, client_config_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_CLIENT_NOT_FOUND")
            next_tenant_id = (
                self._required_text(payload.tenantId, "BUSINESS_CLIENT_TENANT_REQUIRED")
                if payload.tenantId is not None
                else row.tenant_id
            )
            next_client_id = self._short_text(payload.clientId, 64) if "clientId" in payload.model_fields_set else row.client_id
            duplicate = self._find_business_client(
                session,
                tenant_id=next_tenant_id,
                client_id=next_client_id,
                exclude_id=row.id,
                include_tenant_default=False,
            )
            if duplicate:
                raise HTTPException(status_code=409, detail="BUSINESS_CLIENT_DUPLICATED")
            row.tenant_id = next_tenant_id
            row.client_id = next_client_id
            if payload.displayName is not None:
                row.display_name = self._required_text(payload.displayName, "BUSINESS_CLIENT_DISPLAY_NAME_REQUIRED")
            if payload.status is not None:
                row.status = self._normalize_client_status(payload.status)
            if "allowedBusinessKeys" in payload.model_fields_set or "allowed_business_keys" in payload.model_fields_set:
                row.allowed_business_keys = self._normalize_business_key_list(payload.allowedBusinessKeys)
            if "dailyRunLimit" in payload.model_fields_set or "daily_run_limit" in payload.model_fields_set:
                row.daily_run_limit = payload.dailyRunLimit
            if "dailyQuotaUnits" in payload.model_fields_set or "daily_quota_units" in payload.model_fields_set:
                row.daily_quota_units = payload.dailyQuotaUnits
            if "concurrentRunLimit" in payload.model_fields_set or "concurrent_run_limit" in payload.model_fields_set:
                row.concurrent_run_limit = payload.concurrentRunLimit
            if "metadata" in payload.model_fields_set or "extra_metadata" in payload.model_fields_set:
                row.extra_metadata = payload.metadata
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._business_client_to_dict(row)

    def create_capability(self, payload: BusinessCapabilityCreateRequest) -> dict[str, Any]:
        business_key = self._required_text(payload.businessKey, "BUSINESS_KEY_REQUIRED")
        version = self._required_text(payload.version, "BUSINESS_VERSION_REQUIRED")
        display_name = self._required_text(payload.displayName, "BUSINESS_DISPLAY_NAME_REQUIRED")
        with get_session() as session:
            existing = (
                session.execute(
                    select(BusinessCapability).where(
                        BusinessCapability.business_key == business_key,
                        BusinessCapability.version == version,
                    )
                )
                .scalars()
                .first()
            )
            if existing:
                raise HTTPException(status_code=409, detail="BUSINESS_CAPABILITY_VERSION_DUPLICATED")
            recipe = self._build_recipe(
                base_recipe=payload.recipe,
                primary_ability_id=payload.primaryAbilityId,
            )
            self._validate_recipe(session=session, recipe=recipe)
            status = self._normalize_status(payload.status)
            self._validate_default_status(is_default=payload.isDefault, status=status)
            row = BusinessCapability(
                id=self._required_text(payload.id, "BUSINESS_CAPABILITY_ID_REQUIRED")
                if payload.id
                else f"biz_{business_key}_{version}_{uuid4().hex[:8]}",
                business_key=business_key,
                version=version,
                display_name=display_name,
                description=payload.description,
                status=status,
                is_default=bool(payload.isDefault),
                release_time=payload.releaseTime,
                recipe=recipe,
                input_schema=payload.inputSchema,
                output_schema=payload.outputSchema,
                extra_metadata=payload.metadata,
            )
            if row.is_default:
                session.add(row)
                session.flush()
                self._ensure_default_release_ready(row, session)
                session.execute(
                    update(BusinessCapability)
                    .where(
                        BusinessCapability.business_key == row.business_key,
                        BusinessCapability.id != row.id,
                    )
                    .values(is_default=False)
                )
            else:
                session.add(row)
            session.commit()
            session.refresh(row)
            return self._capability_to_dict(row, session=session)

    def update_capability(self, capability_id: str, payload: BusinessCapabilityUpdateRequest) -> dict[str, Any]:
        with get_session() as session:
            row = session.get(BusinessCapability, capability_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
            was_default = bool(row.is_default)
            next_business_key = self._required_text(payload.businessKey, "BUSINESS_KEY_REQUIRED") if payload.businessKey is not None else row.business_key
            next_version = self._required_text(payload.version, "BUSINESS_VERSION_REQUIRED") if payload.version is not None else row.version
            duplicate = (
                session.execute(
                    select(BusinessCapability).where(
                        BusinessCapability.business_key == next_business_key,
                        BusinessCapability.version == next_version,
                        BusinessCapability.id != row.id,
                    )
                )
                .scalars()
                .first()
            )
            if duplicate:
                raise HTTPException(status_code=409, detail="BUSINESS_CAPABILITY_VERSION_DUPLICATED")
            if payload.recipe is not None or payload.primaryAbilityId is not None:
                row.recipe = self._build_recipe(
                    base_recipe=payload.recipe if payload.recipe is not None else row.recipe,
                    primary_ability_id=payload.primaryAbilityId,
                )
                self._validate_recipe(session=session, recipe=row.recipe)
            next_status = self._normalize_status(payload.status) if payload.status is not None else row.status
            next_is_default = bool(payload.isDefault) if payload.isDefault is not None else row.is_default
            self._validate_default_status(is_default=next_is_default, status=next_status)
            row.business_key = next_business_key
            row.version = next_version
            if payload.displayName is not None:
                row.display_name = self._required_text(payload.displayName, "BUSINESS_DISPLAY_NAME_REQUIRED")
            if payload.description is not None:
                row.description = payload.description
            row.status = next_status
            row.is_default = next_is_default
            if "releaseTime" in payload.model_fields_set or "release_time" in payload.model_fields_set:
                row.release_time = payload.releaseTime
            if "inputSchema" in payload.model_fields_set or "input_schema" in payload.model_fields_set:
                row.input_schema = payload.inputSchema
            if "outputSchema" in payload.model_fields_set or "output_schema" in payload.model_fields_set:
                row.output_schema = payload.outputSchema
            if "metadata" in payload.model_fields_set or "extra_metadata" in payload.model_fields_set:
                row.extra_metadata = payload.metadata
            if row.is_default:
                session.add(row)
                session.flush()
                default_gate_required = (
                    not was_default
                    or payload.isDefault is not None
                    or payload.status is not None
                    or payload.recipe is not None
                    or payload.primaryAbilityId is not None
                )
                if default_gate_required:
                    self._ensure_default_release_ready(row, session)
                session.execute(
                    update(BusinessCapability)
                    .where(
                        BusinessCapability.business_key == row.business_key,
                        BusinessCapability.id != row.id,
                    )
                    .values(is_default=False)
                )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._capability_to_dict(row, session=session)

    def record_acceptance(
        self,
        capability_id: str,
        payload: BusinessAcceptanceRecordRequest | None = None,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        request = payload or BusinessAcceptanceRecordRequest()
        status = self._normalize_acceptance_status(request.status)
        note = self._clean_optional_text(request.note)
        evidence_run_id = self._clean_optional_text(request.evidenceRunId)
        evidence_url = self._clean_optional_text(request.evidenceUrl)
        with get_session() as session:
            row = session.get(BusinessCapability, capability_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
            before = self._capability_to_dict(row, session=session)
            metadata = dict(row.extra_metadata or {})
            existing_records = metadata.get("acceptanceRecords")
            records = existing_records if isinstance(existing_records, list) else []
            record = {
                "id": f"bizacc_{uuid4().hex[:12]}",
                "status": status,
                "note": note,
                "evidenceRunId": evidence_run_id,
                "evidenceUrl": evidence_url,
                "checklist": request.checklist if isinstance(request.checklist, dict) else {},
                "metadata": request.metadata if isinstance(request.metadata, dict) else {},
                "actorUserId": self._safe_user_id(actor),
                "actorUsername": self._actor_username(actor),
                "actorRole": (str(getattr(actor, "role", "") or "").strip() or None) if actor else None,
                "createdAt": datetime.utcnow().isoformat(),
            }
            metadata["latestAcceptance"] = record
            metadata["acceptanceRecords"] = [record, *records][:20]
            row.extra_metadata = metadata
            session.add(row)
            self._record_business_operation(
                session=session,
                action="record_acceptance",
                target_type="business_capability",
                target_id=row.id,
                business_key=row.business_key,
                actor=actor,
                note=note,
                before_payload={
                    "latestAcceptance": before.get("latest_acceptance") or before.get("latestAcceptance"),
                },
                after_payload={"latestAcceptance": record},
            )
            session.commit()
            session.refresh(row)
            return self._capability_to_dict(row, session=session)

    def promote_capability(
        self,
        capability_id: str,
        payload: BusinessCapabilityPromoteRequest | None = None,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        request = payload or BusinessCapabilityPromoteRequest()
        with get_session() as session:
            row = session.get(BusinessCapability, capability_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
            if row.status != "active":
                if not request.activate:
                    raise HTTPException(status_code=400, detail="BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE")
                row.status = "active"
            session.add(row)
            session.flush()
            self._ensure_default_release_ready(row, session)
            current_default = (
                session.execute(
                    select(BusinessCapability).where(
                        BusinessCapability.business_key == row.business_key,
                        BusinessCapability.is_default.is_(True),
                        BusinessCapability.id != row.id,
                    )
                )
                .scalars()
                .first()
            )
            row.is_default = True
            row.extra_metadata = self._append_release_event(
                row.extra_metadata,
                action="promote_default",
                note=request.note,
                actor=actor,
                previous_default=current_default,
            )
            session.execute(
                update(BusinessCapability)
                .where(
                    BusinessCapability.business_key == row.business_key,
                    BusinessCapability.id != row.id,
                )
                .values(is_default=False)
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._capability_to_dict(row, session=session)

    def rollback_default(
        self,
        business_key: str,
        payload: BusinessCapabilityRollbackRequest | None = None,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        normalized_key = self._required_text(business_key, "BUSINESS_KEY_REQUIRED")
        request = payload or BusinessCapabilityRollbackRequest()
        with get_session() as session:
            current_default = (
                session.execute(
                    select(BusinessCapability)
                    .where(
                        BusinessCapability.business_key == normalized_key,
                        BusinessCapability.is_default.is_(True),
                    )
                    .order_by(BusinessCapability.updated_at.desc(), BusinessCapability.created_at.desc())
                )
                .scalars()
                .first()
            )
            target = self._resolve_rollback_target(
                session=session,
                business_key=normalized_key,
                current_default=current_default,
                target_capability_id=request.targetCapabilityId,
            )
            if not target:
                raise HTTPException(status_code=409, detail="BUSINESS_ROLLBACK_TARGET_NOT_FOUND")
            if target.status != "active":
                if not request.activate:
                    raise HTTPException(status_code=400, detail="BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE")
                target.status = "active"
            target.is_default = True
            target.extra_metadata = self._append_release_event(
                target.extra_metadata,
                action="rollback_default",
                note=request.note,
                actor=actor,
                previous_default=current_default if current_default and current_default.id != target.id else None,
            )
            session.execute(
                update(BusinessCapability)
                .where(
                    BusinessCapability.business_key == normalized_key,
                    BusinessCapability.id != target.id,
                )
                .values(is_default=False)
            )
            session.add(target)
            session.commit()
            session.refresh(target)
            return self._capability_to_dict(target, session=session)

    def create_default_approval(
        self,
        capability_id: str,
        payload: BusinessDefaultApprovalCreateRequest | None = None,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        request = payload or BusinessDefaultApprovalCreateRequest()
        with get_session() as session:
            target = session.get(BusinessCapability, capability_id)
            if not target:
                raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
            if target.status != "active":
                raise HTTPException(status_code=400, detail="BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE")
            self._ensure_default_release_ready(target, session)
            if target.is_default:
                raise HTTPException(status_code=409, detail="BUSINESS_DEFAULT_ALREADY_ACTIVE")
            current_default = (
                session.execute(
                    select(BusinessCapability)
                    .where(
                        BusinessCapability.business_key == target.business_key,
                        BusinessCapability.is_default.is_(True),
                    )
                    .order_by(BusinessCapability.updated_at.desc(), BusinessCapability.created_at.desc())
                )
                .scalars()
                .first()
            )
            pending = (
                session.execute(
                    select(BusinessDefaultApproval).where(
                        BusinessDefaultApproval.target_capability_id == target.id,
                        BusinessDefaultApproval.status == "pending",
                    )
                )
                .scalars()
                .first()
            )
            if pending:
                raise HTTPException(status_code=409, detail="BUSINESS_DEFAULT_APPROVAL_PENDING")
            row = BusinessDefaultApproval(
                id=f"bizappr_{uuid4().hex}",
                business_key=target.business_key,
                source_capability_id=current_default.id if current_default else None,
                target_capability_id=target.id,
                status="pending",
                requester_user_id=self._safe_user_id(actor),
                requester_username=self._actor_username(actor),
                request_note=self._clean_optional_text(request.note),
                before_payload=self._json_safe_payload(
                    self._capability_to_dict(current_default, session=session) if current_default else None
                ),
                after_payload=self._json_safe_payload(self._capability_to_dict(target, session=session)),
            )
            session.add(row)
            self._record_business_operation(
                session=session,
                action="request_default_approval",
                target_type="business_default_approval",
                target_id=row.id,
                business_key=row.business_key,
                actor=actor,
                note=row.request_note,
                before_payload=row.before_payload,
                after_payload=row.after_payload,
            )
            session.commit()
            session.refresh(row)
            return self._default_approval_to_dict(row, session=session)

    def list_default_approvals(
        self,
        *,
        status: str | None = None,
        business_key: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with get_session() as session:
            stmt = select(BusinessDefaultApproval)
            if status:
                stmt = stmt.where(BusinessDefaultApproval.status == status)
            if business_key:
                stmt = stmt.where(BusinessDefaultApproval.business_key == business_key)
            rows = (
                session.execute(
                    stmt.order_by(BusinessDefaultApproval.created_at.desc()).limit(max(1, min(limit, 200)))
                )
                .scalars()
                .all()
            )
            return [self._default_approval_to_dict(row, session=session) for row in rows]

    def decide_default_approval(
        self,
        approval_id: str,
        payload: BusinessDefaultApprovalDecisionRequest | None = None,
        *,
        actor: User | None = None,
        approve: bool,
    ) -> dict[str, Any]:
        request = payload or BusinessDefaultApprovalDecisionRequest()
        now = datetime.utcnow()
        with get_session() as session:
            row = session.get(BusinessDefaultApproval, approval_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_DEFAULT_APPROVAL_NOT_FOUND")
            if row.status != "pending":
                raise HTTPException(status_code=409, detail="BUSINESS_DEFAULT_APPROVAL_ALREADY_DECIDED")
            target = session.get(BusinessCapability, row.target_capability_id)
            if not target:
                raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
            row.approver_user_id = self._safe_user_id(actor)
            row.approver_username = self._actor_username(actor)
            row.decision_note = self._clean_optional_text(request.note)
            row.decided_at = now
            if not approve:
                row.status = "rejected"
                self._record_business_operation(
                    session=session,
                    action="reject_default_approval",
                    target_type="business_default_approval",
                    target_id=row.id,
                    business_key=row.business_key,
                    actor=actor,
                    note=row.decision_note,
                    before_payload=row.before_payload,
                    after_payload=row.after_payload,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                return self._default_approval_to_dict(row, session=session)
            if target.status != "active":
                raise HTTPException(status_code=400, detail="BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE")
            self._ensure_default_release_ready(target, session)
            current_default = (
                session.execute(
                    select(BusinessCapability)
                    .where(
                        BusinessCapability.business_key == row.business_key,
                        BusinessCapability.is_default.is_(True),
                        BusinessCapability.id != target.id,
                    )
                    .order_by(BusinessCapability.updated_at.desc(), BusinessCapability.created_at.desc())
                )
                .scalars()
                .first()
            )
            target.is_default = True
            target.extra_metadata = self._append_release_event(
                target.extra_metadata,
                action="approve_default",
                note=row.decision_note,
                actor=actor,
                previous_default=current_default,
            )
            session.execute(
                update(BusinessCapability)
                .where(
                    BusinessCapability.business_key == row.business_key,
                    BusinessCapability.id != target.id,
                )
                .values(is_default=False)
            )
            row.status = "approved"
            row.applied_at = now
            row.after_payload = self._json_safe_payload(self._capability_to_dict(target, session=session))
            session.add(row)
            session.add(target)
            self._record_business_operation(
                session=session,
                action="approve_default_approval",
                target_type="business_default_approval",
                target_id=row.id,
                business_key=row.business_key,
                actor=actor,
                note=row.decision_note,
                before_payload=row.before_payload,
                after_payload=row.after_payload,
            )
            session.commit()
            session.refresh(row)
            return self._default_approval_to_dict(row, session=session)

    def list_operation_logs(
        self,
        *,
        action: str | None = None,
        target_type: str | None = None,
        business_key: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        actor_user_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with get_session() as session:
            stmt = select(BusinessOperationLog)
            if action:
                stmt = stmt.where(BusinessOperationLog.action == action)
            if target_type:
                stmt = stmt.where(BusinessOperationLog.target_type == target_type)
            if business_key:
                stmt = stmt.where(BusinessOperationLog.business_key == business_key)
            if tenant_id:
                stmt = stmt.where(BusinessOperationLog.tenant_id == tenant_id)
            if client_id:
                stmt = stmt.where(BusinessOperationLog.client_id == client_id)
            if actor_user_id:
                stmt = stmt.where(BusinessOperationLog.actor_user_id == actor_user_id)
            rows = (
                session.execute(stmt.order_by(BusinessOperationLog.created_at.desc()).limit(max(1, min(limit, 200))))
                .scalars()
                .all()
            )
            return [self._operation_log_to_dict(row) for row in rows]

    def preview_route(
        self,
        *,
        business_key: str,
        payload: BusinessRunCreateRequest,
        user: User | None,
    ) -> dict[str, Any]:
        with get_session() as session:
            ensure_default_abilities(session)
            ensure_default_business_capabilities(session)
            image_url = self._first_string(
                payload.imageUrl,
                payload.url,
                (payload.inputs or {}).get("imageUrl"),
                (payload.inputs or {}).get("url"),
            )
            selected, route_info = self._select_capability(
                session,
                business_key=business_key,
                version=payload.version,
                payload=payload,
                user=user,
                image_url=image_url,
            )
            active_rows = (
                session.execute(
                    select(BusinessCapability)
                    .where(
                        BusinessCapability.business_key == business_key,
                        BusinessCapability.status == "active",
                    )
                    .order_by(
                        BusinessCapability.is_default.desc(),
                        BusinessCapability.release_time.desc(),
                        BusinessCapability.created_at.desc(),
                    )
                )
                .scalars()
                .all()
            )
            default = next((row for row in active_rows if row.is_default), None)
            return {
                "business_key": business_key,
                "requested_version": payload.version,
                "selected_capability_id": selected.id,
                "selected_version": selected.version,
                "selected_display_name": selected.display_name,
                "selected_status": selected.status,
                "selected_is_default": selected.is_default,
                "selected_by": route_info.get("selectedBy") or "default",
                "route_info": route_info,
                "default_capability_id": default.id if default else None,
                "default_version": default.version if default else None,
                "active_versions": [
                    {
                        "id": row.id,
                        "version": row.version,
                        "displayName": row.display_name,
                        "isDefault": row.is_default,
                        "hasRollout": bool(self._extract_rollout_config(row)),
                    }
                    for row in active_rows
                ],
            }

    def list_runs(
        self,
        *,
        limit: int = 50,
        business_key: str | None = None,
        status: str | None = None,
        billing_status: str | None = None,
        callback_status: str | None = None,
        issue_category: str | None = None,
        version: str | None = None,
        source: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        trace_id: str | None = None,
    ) -> tuple[int, list[BusinessRun]]:
        with get_session() as session:
            stmt = select(BusinessRun)
            count_stmt = select(func.count(BusinessRun.id))
            filters = []
            normalized_issue_category = self._normalize_issue_category(issue_category)
            if business_key:
                filters.append(BusinessRun.business_key == business_key)
            if status:
                filters.append(BusinessRun.status == status)
            if callback_status:
                filters.append(BusinessRun.callback_status == callback_status)
            if version:
                filters.append(BusinessRun.version == version)
            if source:
                filters.append(BusinessRun.source == source)
            if tenant_id:
                filters.append(BusinessRun.tenant_id == tenant_id)
            if client_id:
                filters.append(BusinessRun.client_id == client_id)
            if trace_id:
                filters.append(BusinessRun.trace_id == trace_id)
            if filters:
                stmt = stmt.where(*filters)
                count_stmt = count_stmt.where(*filters)
            if billing_status:
                status_filter = self._billing_status_filter(billing_status)
                if status_filter is not None:
                    stmt = stmt.where(status_filter)
                    count_stmt = count_stmt.where(status_filter)
            if normalized_issue_category:
                rows = session.execute(stmt.order_by(BusinessRun.created_at.desc())).scalars().all()
                items = [
                    self._run_to_dict(row, session=session)
                    for row in rows
                    if self._build_run_issue_summary(row, session=session)["category"] == normalized_issue_category
                ]
                return len(items), items[: max(1, min(limit, 1000))]
            total = int(session.scalar(count_stmt) or 0)
            rows = (
                session.execute(stmt.order_by(BusinessRun.created_at.desc()).limit(max(1, min(limit, 1000))))
                .scalars()
                .all()
            )
            return total, [self._run_to_dict(row, session=session) for row in rows]

    def usage_summary(
        self,
        *,
        window_hours: int = 24,
        business_key: str | None = None,
        status: str | None = None,
        issue_category: str | None = None,
        version: str | None = None,
        source: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_window_hours = max(1, min(int(window_hours or 24), 24 * 90))
        since = datetime.utcnow() - timedelta(hours=normalized_window_hours)
        issue_summaries: dict[str, dict[str, Any]] = {}
        unresolved_issues: list[dict[str, Any]] = []
        recent_unresolved_issues: list[dict[str, Any]] = []
        normalized_issue_category = self._normalize_issue_category(issue_category)
        with get_session() as session:
            stmt = select(BusinessRun).where(BusinessRun.created_at >= since)
            filters = []
            if business_key:
                filters.append(BusinessRun.business_key == business_key)
            if status:
                filters.append(BusinessRun.status == status)
            if version:
                filters.append(BusinessRun.version == version)
            if source:
                filters.append(BusinessRun.source == source)
            if tenant_id:
                filters.append(BusinessRun.tenant_id == tenant_id)
            if client_id:
                filters.append(BusinessRun.client_id == client_id)
            if trace_id:
                filters.append(BusinessRun.trace_id == trace_id)
            if filters:
                stmt = stmt.where(*filters)
            rows = session.execute(stmt.order_by(BusinessRun.created_at.desc())).scalars().all()
            issue_summaries = {
                row.id: self._build_run_issue_summary(row, session=session)
                for row in rows
            }
            if normalized_issue_category:
                rows = [
                    row
                    for row in rows
                    if issue_summaries.get(row.id, {}).get("category") == normalized_issue_category
                ]
            unresolved_issues = self._usage_unresolved_issue_buckets(
                rows,
                issue_summaries,
                session=session,
            )
            recent_unresolved_issues = self._recent_unresolved_issue_items(
                rows,
                issue_summaries,
                session=session,
            )

        summary = self._summarize_usage_bucket("all", "全部业务", rows)
        recent_failures = [
            {
                "id": row.id,
                "business_key": row.business_key,
                "version": row.version,
                "status": row.status,
                "source": row.source,
                "channel": row.channel,
                "tenant_id": row.tenant_id,
                "client_id": row.client_id,
                "trace_id": row.trace_id,
                "error_message": row.error_message,
                "created_at": row.created_at,
            }
            for row in rows
            if str(row.status or "").lower() == "failed" or row.error_message
        ][:10]
        return {
            "window_hours": normalized_window_hours,
            "filters": {
                "business_key": business_key,
                "status": status,
                "issue_category": issue_category,
                "version": version,
                "source": source,
                "tenant_id": tenant_id,
                "client_id": client_id,
                "trace_id": trace_id,
            },
            **{key: value for key, value in summary.items() if key not in {"key", "label", "latest_at"}},
            "by_business": self._usage_buckets(rows, lambda row: row.business_key or "unknown"),
            "by_source": self._usage_buckets(rows, lambda row: row.source or "business-api"),
            "by_tenant": self._usage_buckets(rows, lambda row: row.tenant_id or "未标记业务方"),
            "by_client": self._usage_buckets(rows, lambda row: row.client_id or "未标记客户端"),
            "by_version": self._usage_buckets(
                rows,
                lambda row: f"{row.business_key or 'unknown'}:{row.version or '未标记版本'}",
                label_func=lambda key: key.replace(":", " · ", 1),
            ),
            "by_issue": self._usage_issue_buckets(rows, issue_summaries),
            "unresolved_issues": unresolved_issues,
            "recent_unresolved_issues": recent_unresolved_issues,
            "recent_failures": recent_failures,
        }

    def _usage_buckets(self, rows: list[BusinessRun], key_func, label_func=None) -> list[dict[str, Any]]:
        groups: dict[str, list[BusinessRun]] = {}
        for row in rows:
            key = str(key_func(row) or "unknown").strip() or "unknown"
            groups.setdefault(key, []).append(row)
        buckets = [
            self._summarize_usage_bucket(
                key,
                str(label_func(key) if label_func else key),
                group,
            )
            for key, group in groups.items()
        ]
        return sorted(
            buckets,
            key=lambda item: (int(item.get("total") or 0), item.get("latest_at") or datetime.min),
            reverse=True,
        )[:50]

    def _usage_issue_buckets(
        self,
        rows: list[BusinessRun],
        issue_summaries: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[BusinessRun]] = {}
        for row in rows:
            summary = issue_summaries.get(row.id) or self._build_run_issue_summary(row)
            key = str(summary.get("category") or "none")
            groups.setdefault(key, []).append(row)
        buckets: list[dict[str, Any]] = []
        for key, group in groups.items():
            issue = self._issue_category_meta(key)
            bucket = self._summarize_usage_bucket(key, issue["label"], group)
            bucket.update(
                {
                    "severity": issue["severity"],
                    "action": issue["action"],
                }
            )
            buckets.append(bucket)
        return sorted(
            buckets,
            key=lambda item: (0 if item.get("key") == "none" else 1, int(item.get("total") or 0)),
            reverse=True,
        )

    def _usage_unresolved_issue_buckets(
        self,
        rows: list[BusinessRun],
        issue_summaries: dict[str, dict[str, Any]],
        *,
        session,
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[BusinessRun]] = {}
        retest_by_run: dict[str, dict[str, Any]] = {}
        for row in rows:
            summary = issue_summaries.get(row.id) or self._build_run_issue_summary(row, session=session)
            category = str(summary.get("category") or "none")
            if category == "none" or self._extract_retest_source_run_id(row):
                continue
            retest_summary = self._build_retest_summary(row, session=session)
            if retest_summary.get("recovered"):
                continue
            groups.setdefault(category, []).append(row)
            retest_by_run[row.id] = retest_summary

        buckets: list[dict[str, Any]] = []
        for key, group in groups.items():
            issue = self._issue_category_meta(key)
            bucket = self._summarize_usage_bucket(key, issue["label"], group)
            retested = sum(1 for row in group if int((retest_by_run.get(row.id) or {}).get("attempts") or 0) > 0)
            retest_attempts = sum(int((retest_by_run.get(row.id) or {}).get("attempts") or 0) for row in group)
            bucket.update(
                {
                    "severity": issue["severity"],
                    "action": issue["action"],
                    "retested": retested,
                    "retest_attempts": retest_attempts,
                }
            )
            buckets.append(bucket)
        return sorted(
            buckets,
            key=lambda item: (int(item.get("total") or 0), int(item.get("retest_attempts") or 0)),
            reverse=True,
        )

    def _recent_unresolved_issue_items(
        self,
        rows: list[BusinessRun],
        issue_summaries: dict[str, dict[str, Any]],
        *,
        session,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for row in rows:
            summary = issue_summaries.get(row.id) or self._build_run_issue_summary(row, session=session)
            category = str(summary.get("category") or "none")
            if category == "none" or self._extract_retest_source_run_id(row):
                continue
            retest_summary = self._build_retest_summary(row, session=session)
            if retest_summary.get("recovered"):
                continue
            items.append(
                {
                    "id": row.id,
                    "business_key": row.business_key,
                    "version": row.version,
                    "status": row.status,
                    "source": row.source,
                    "tenant_id": row.tenant_id,
                    "client_id": row.client_id,
                    "trace_id": row.trace_id,
                    "issue_category": category,
                    "issue_label": str(summary.get("label") or self._issue_category_meta(category)["label"]),
                    "issue_action": summary.get("action"),
                    "retest_attempts": int(retest_summary.get("attempts") or 0),
                    "retest_latest_run_id": retest_summary.get("latestRunId"),
                    "retest_latest_status": retest_summary.get("latestStatus"),
                    "created_at": row.created_at,
                }
            )
        return sorted(items, key=lambda item: item["created_at"], reverse=True)[:10]

    def _summarize_usage_bucket(self, key: str, label: str, rows: list[BusinessRun]) -> dict[str, Any]:
        statuses = {
            "succeeded": 0,
            "failed": 0,
            "running": 0,
            "queued": 0,
            "cancelled": 0,
        }
        durations: list[int] = []
        cost_by_currency: dict[str, float] = {}
        actual_cost_by_currency: dict[str, float] = {}
        quota_units = 0
        actual_quota_units = 0
        billable = 0
        unpriced = 0
        no_charge = 0
        billing_pending = 0
        callback_success = 0
        callback_failed = 0
        callback_running = 0
        callback_missing = 0
        latest_at: datetime | None = None
        for row in rows:
            status = str(row.status or "").strip().lower()
            if status in statuses:
                statuses[status] += 1
            callback_status = str(row.callback_status or "").strip().lower()
            if callback_status == "success":
                callback_success += 1
            elif callback_status == "failed" or row.callback_error:
                callback_failed += 1
            elif callback_status == "running":
                callback_running += 1
            elif row.callback_url:
                callback_missing += 1
            if isinstance(row.duration_ms, int):
                durations.append(row.duration_ms)
            cost_amount = self._first_number(row.cost_amount)
            if cost_amount is not None:
                currency = str(row.currency or "UNKNOWN").strip() or "UNKNOWN"
                actual_cost_by_currency[currency] = round(actual_cost_by_currency.get(currency, 0.0) + cost_amount, 4)
            actual_quota_units += int(row.quota_units or 0)
            billing_status = self._business_billing_status(row)
            if billing_status == "billable":
                billable += 1
                if cost_amount is not None:
                    currency = str(row.currency or "UNKNOWN").strip() or "UNKNOWN"
                    cost_by_currency[currency] = round(cost_by_currency.get(currency, 0.0) + cost_amount, 4)
                quota_units += int(row.quota_units or 0)
            elif billing_status == "unpriced":
                unpriced += 1
            elif billing_status == "no_charge":
                no_charge += 1
            elif billing_status == "billing_pending":
                billing_pending += 1
            if row.created_at and (latest_at is None or row.created_at > latest_at):
                latest_at = row.created_at
        total = len(rows)
        success_rate = round(statuses["succeeded"] / total, 4) if total else None
        avg_duration_ms = int(sum(durations) / len(durations)) if durations else None
        return {
            "key": key,
            "label": label,
            "total": total,
            **statuses,
            "success_rate": success_rate,
            "avg_duration_ms": avg_duration_ms,
            "cost_by_currency": cost_by_currency,
            "actual_cost_by_currency": actual_cost_by_currency,
            "quota_units": quota_units,
            "actual_quota_units": actual_quota_units,
            "billable": billable,
            "unpriced": unpriced,
            "no_charge": no_charge,
            "billing_pending": billing_pending,
            "callback_success": callback_success,
            "callback_failed": callback_failed,
            "callback_running": callback_running,
            "callback_missing": callback_missing,
            "latest_at": latest_at,
        }

    def create_run(
        self,
        *,
        business_key: str,
        payload: BusinessRunCreateRequest,
        user: User | None,
        source: str = "business-api",
    ) -> BusinessRun:
        image_url = self._first_string(payload.imageUrl, payload.url, (payload.inputs or {}).get("imageUrl"), (payload.inputs or {}).get("url"))
        if not image_url:
            raise HTTPException(status_code=400, detail="BUSINESS_IMAGE_URL_REQUIRED")

        with get_session() as session:
            ensure_default_abilities(session)
            ensure_default_business_capabilities(session)
            capability, route_info = self._select_capability(
                session,
                business_key=business_key,
                version=payload.version,
                payload=payload,
                user=user,
                image_url=image_url,
            )
            recipe = capability.recipe if isinstance(capability.recipe, dict) else {}
            ability_id = self._extract_primary_ability_id(recipe)
            ability = session.get(Ability, ability_id)
            if not ability or ability.status != "active":
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE")
            request_payload = self._omit_large_fields(payload.model_dump(exclude_none=True))
            if isinstance(request_payload, dict):
                request_payload["_route"] = route_info
            run_id = uuid4().hex
            trace_context = self._resolve_trace_context(
                run_id=run_id,
                business_key=business_key,
                payload=payload,
                source=source,
                user=user,
            )
            request_payload["_trace"] = trace_context
            client_policy = self._check_business_client_policy(
                session=session,
                business_key=business_key,
                payload=payload,
                trace_context=trace_context,
            )
            if client_policy:
                request_payload["_businessClient"] = client_policy

            run = BusinessRun(
                id=run_id,
                business_key=capability.business_key,
                business_version_id=capability.id,
                version=capability.version,
                status="queued",
                source=trace_context["source"],
                channel=trace_context.get("channel"),
                trace_id=trace_context["traceId"],
                request_id=trace_context["requestId"],
                tenant_id=trace_context.get("tenantId"),
                client_id=trace_context.get("clientId"),
                user_id=self._resolve_business_user_id(user=user, payload=payload, trace_context=trace_context),
                user_name=self._resolve_business_user_name(user=user, payload=payload),
                ability_id=ability.id,
                request_payload=request_payload,
                callback_url=payload.callbackUrl,
                callback_headers=payload.callbackHeaders,
            )
            session.add(run)
            self._create_run_steps(session=session, run=run, recipe=recipe)
            session.commit()
            session.refresh(run)
            run_id = run.id

        if self._should_wait_for_vl(recipe):
            self._enqueue_sidecar_steps(
                run_id=run_id,
                recipe=recipe,
                business_key=business_key,
                payload=payload,
                user=user,
                image_url=image_url,
                route_info=route_info,
                trace_context=trace_context,
            )
            self._submit_primary_after_vl_if_ready(run_id=run_id, user=user)
            with get_session() as session:
                db_run = session.get(BusinessRun, run_id)
                if not db_run:
                    raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
                self._sync_run_steps(session=session, run=db_run)
                return self._run_to_dict(db_run, session=session)

        ability_payload = self._build_ability_payload(
            capability_key=business_key,
            payload=payload,
            image_url=image_url,
            route_info=route_info,
            trace_context=trace_context,
        )
        self._submit_primary_ability(
            run_id=run_id,
            ability_id=ability_id,
            ability_payload=ability_payload,
            user=user,
        )

        self._enqueue_sidecar_steps(
            run_id=run_id,
            recipe=recipe,
            business_key=business_key,
            payload=payload,
            user=user,
            image_url=image_url,
            route_info=route_info,
            trace_context=trace_context,
        )
        with get_session() as session:
            db_run = session.get(BusinessRun, run_id)
            if not db_run:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            self._sync_run_steps(session=session, run=db_run)
            return self._run_to_dict(db_run, session=session)

    def _create_run_steps(self, *, session, run: BusinessRun, recipe: dict[str, Any]) -> None:
        for order, step in enumerate(self._normalized_recipe_steps(recipe), start=1):
            ability_id = step.get("abilityId")
            ability = session.get(Ability, ability_id) if isinstance(ability_id, str) and ability_id else None
            enabled = step.get("enabled") is not False
            row = BusinessRunStep(
                id=uuid4().hex,
                run_id=run.id,
                step_order=order,
                step_id=self._first_string(step.get("id")),
                step_type=self._first_string(step.get("type")) or "ability_task",
                role=self._first_string(step.get("role")),
                display_name=self._first_string(step.get("displayName")),
                enabled=enabled,
                status="planned" if enabled else "skipped",
                ability_id=ability_id if isinstance(ability_id, str) else None,
                ability_name=ability.display_name if ability else None,
                ability_provider=ability.provider if ability else None,
            )
            session.add(row)

    def _mark_primary_step_submitted(
        self,
        *,
        session,
        run: BusinessRun,
        task: dict[str, Any],
        request_payload: dict[str, Any],
    ) -> None:
        step = self._find_primary_step(session=session, run=run, task_id=None)
        if not step:
            return
        step.status = str(task.get("status") or "queued")
        step.ability_task_id = str(task.get("id") or "") or None
        step.request_payload = self._omit_large_fields(request_payload)
        step.started_at = run.started_at or datetime.utcnow()
        session.add(step)

    def _enqueue_sidecar_steps(
        self,
        *,
        run_id: str,
        recipe: dict[str, Any],
        business_key: str,
        payload: BusinessRunCreateRequest,
        user: User | None,
        image_url: str,
        route_info: dict[str, Any],
        trace_context: dict[str, Any],
    ) -> None:
        snapshots: list[dict[str, Any]] = []
        normalized_steps = self._normalized_recipe_steps(recipe)
        with get_session() as session:
            run = session.get(BusinessRun, run_id)
            if not run:
                return
            for order, step_config in enumerate(normalized_steps, start=1):
                if not self._is_sidecar_step(step_config):
                    continue
                row = (
                    session.execute(
                        select(BusinessRunStep).where(
                            BusinessRunStep.run_id == run.id,
                            BusinessRunStep.step_order == order,
                            BusinessRunStep.status == "planned",
                            BusinessRunStep.enabled.is_(True),
                        )
                    )
                    .scalars()
                    .first()
                )
                if not row or not row.ability_id:
                    continue
                snapshots.append(
                    {
                        "row_id": row.id,
                        "ability_id": row.ability_id,
                        "step_id": row.step_id,
                        "step_type": row.step_type,
                        "role": row.role,
                        "config": step_config,
                    }
                )

        for step in snapshots:
            step_payload = self._build_step_ability_payload(
                step=step,
                business_key=business_key,
                payload=payload,
                image_url=image_url,
                route_info=route_info,
                run_id=run_id,
                trace_context=trace_context,
            )
            try:
                task = get_ability_task_service().enqueue(
                    ability_id=str(step["ability_id"]),
                    payload=step_payload,
                    user=user,
                )
            except Exception as exc:
                self._mark_step_submit_failed(row_id=str(step["row_id"]), detail=self._extract_error_message(exc))
                continue
            self._mark_step_submitted(
                row_id=str(step["row_id"]),
                task=task,
                request_payload=step_payload.model_dump(exclude_none=True),
            )

    @staticmethod
    def _is_sidecar_step(step: dict[str, Any]) -> bool:
        if step.get("enabled") is False:
            return False
        role = str(step.get("role") or "").strip().lower()
        if role == "primary":
            return False
        step_type = str(step.get("type") or "").strip().lower()
        return step_type in {"vl_analyze", "vl_analyze_image"}

    def _mark_step_submitted(self, *, row_id: str, task: dict[str, Any], request_payload: dict[str, Any]) -> None:
        with get_session() as session:
            step = session.get(BusinessRunStep, row_id)
            if not step:
                return
            step.status = str(task.get("status") or "queued")
            step.ability_task_id = str(task.get("id") or "") or None
            step.request_payload = self._omit_large_fields(request_payload)
            step.started_at = datetime.utcnow()
            session.add(step)
            session.commit()

    def _mark_step_submit_failed(self, *, row_id: str, detail: Any) -> None:
        with get_session() as session:
            step = session.get(BusinessRunStep, row_id)
            if not step:
                return
            step.status = "failed"
            step.error_message = str(detail)[:500]
            step.finished_at = datetime.utcnow()
            session.add(step)
            session.commit()

    def _find_primary_step(self, *, session, run: BusinessRun, task_id: str | None) -> BusinessRunStep | None:
        if task_id:
            row = (
                session.execute(
                    select(BusinessRunStep).where(
                        BusinessRunStep.run_id == run.id,
                        BusinessRunStep.ability_task_id == task_id,
                    )
                )
                .scalars()
                .first()
            )
            if row:
                return row
        if run.ability_id:
            row = (
                session.execute(
                    select(BusinessRunStep)
                    .where(
                        BusinessRunStep.run_id == run.id,
                        BusinessRunStep.ability_id == run.ability_id,
                        BusinessRunStep.enabled.is_(True),
                    )
                    .order_by(
                        BusinessRunStep.role.desc(),
                        BusinessRunStep.step_order.asc(),
                    )
                )
                .scalars()
                .first()
            )
            if row:
                return row
        return (
            session.execute(
                select(BusinessRunStep)
                .where(
                    BusinessRunStep.run_id == run.id,
                    BusinessRunStep.enabled.is_(True),
                    BusinessRunStep.step_type.in_(["ability_task", "comfyui_workflow", "vendor_api"]),
                )
                .order_by(BusinessRunStep.step_order.asc())
            )
            .scalars()
            .first()
        )

    def _mark_run_submit_failed(self, run_id: str, detail: Any) -> None:
        with get_session() as session:
            db_run = session.get(BusinessRun, run_id)
            if not db_run:
                return
            db_run.status = "failed"
            db_run.error_message = str(detail)[:500]
            db_run.finished_at = datetime.utcnow()
            step = self._find_primary_step(session=session, run=db_run, task_id=None)
            if step:
                step.status = "failed"
                step.error_message = str(detail)[:500]
                step.finished_at = db_run.finished_at
                session.add(step)
            session.add(db_run)
            session.commit()

    def _submit_primary_ability(
        self,
        *,
        run_id: str,
        ability_id: str,
        ability_payload: AbilityInvokeRequest,
        user: User | None,
        raise_on_error: bool = True,
    ) -> bool:
        try:
            task = get_ability_task_service().enqueue(ability_id=ability_id, payload=ability_payload, user=user)
        except HTTPException as exc:
            self._mark_run_submit_failed(run_id, exc.detail)
            if raise_on_error:
                raise
            return False
        except Exception as exc:
            self._mark_run_submit_failed(run_id, f"RUN_CREATE_FAILED:{exc}")
            if raise_on_error:
                raise HTTPException(status_code=500, detail="RUN_CREATE_FAILED") from exc
            return False

        with get_session() as session:
            db_run = session.get(BusinessRun, run_id)
            if not db_run:
                if raise_on_error:
                    raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
                return False
            db_run.ability_task_id = str(task.get("id") or "")
            db_run.status = str(task.get("status") or "queued")
            db_run.started_at = db_run.started_at or datetime.utcnow()
            self._mark_primary_step_submitted(
                session=session,
                run=db_run,
                task=task,
                request_payload=ability_payload.model_dump(exclude_none=True),
            )
            session.add(db_run)
            session.commit()
        return True

    def _submit_primary_after_vl_if_ready(self, *, run_id: str, user: User | None) -> bool:
        with get_session() as session:
            run = session.get(BusinessRun, run_id)
            if not run or run.ability_task_id:
                return False
            capability = session.get(BusinessCapability, run.business_version_id) if run.business_version_id else None
            recipe = capability.recipe if capability and isinstance(capability.recipe, dict) else {}
            if not self._should_wait_for_vl(recipe):
                return False
            self._sync_run_steps(session=session, run=run)
            vl_step = self._find_blocking_vl_step(session=session, run=run)
            if not vl_step:
                return False
            if vl_step.status in {"failed", "cancelled"}:
                detail = vl_step.error_message or "BUSINESS_VL_PREPROCESS_FAILED"
                run.status = "failed"
                run.error_message = str(detail)[:500]
                run.finished_at = datetime.utcnow()
                primary_step = self._find_primary_step(session=session, run=run, task_id=None)
                if primary_step and primary_step.status == "planned":
                    primary_step.status = "failed"
                    primary_step.error_message = run.error_message
                    primary_step.finished_at = run.finished_at
                    session.add(primary_step)
                session.add(run)
                session.commit()
                return False
            if vl_step.status != "succeeded":
                return False
            if not run.ability_id:
                run.status = "failed"
                run.error_message = "BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE"
                run.finished_at = datetime.utcnow()
                session.add(run)
                session.commit()
                return False
            business_key = run.business_key
            ability_id = run.ability_id
            request_payload = dict(run.request_payload) if isinstance(run.request_payload, dict) else {}
            clean_payload = {key: value for key, value in request_payload.items() if not str(key).startswith("_")}
            route_info = request_payload.get("_route") if isinstance(request_payload.get("_route"), dict) else {}
            trace_context = request_payload.get("_trace") if isinstance(request_payload.get("_trace"), dict) else {}
            vl_summary = self._build_step_result_summary(vl_step)

        try:
            payload = BusinessRunCreateRequest.model_validate(clean_payload)
        except Exception:
            self._mark_run_submit_failed(run_id, "BUSINESS_REQUEST_PAYLOAD_INVALID")
            return False
        image_url = self._first_string(payload.imageUrl, payload.url, (payload.inputs or {}).get("imageUrl"), (payload.inputs or {}).get("url"))
        if not image_url:
            self._mark_run_submit_failed(run_id, "BUSINESS_IMAGE_URL_REQUIRED")
            return False
        ability_payload = self._build_ability_payload(
            capability_key=str(business_key),
            payload=payload,
            image_url=image_url,
            route_info=route_info,
            trace_context=trace_context,
            recipe=recipe,
            vl_summary=vl_summary,
        )
        return self._submit_primary_ability(
            run_id=run_id,
            ability_id=str(ability_id),
            ability_payload=ability_payload,
            user=user,
            raise_on_error=False,
        )

    @staticmethod
    def _find_blocking_vl_step(*, session, run: BusinessRun) -> BusinessRunStep | None:
        return (
            session.execute(
                select(BusinessRunStep)
                .where(
                    BusinessRunStep.run_id == run.id,
                    BusinessRunStep.enabled.is_(True),
                    BusinessRunStep.step_type.in_(["vl_analyze", "vl_analyze_image"]),
                )
                .order_by(BusinessRunStep.step_order.asc())
            )
            .scalars()
            .first()
        )

    def get_run(self, *, run_id: str, user: User | None = None) -> BusinessRun:
        self.finalize_run(run_id)
        with get_session() as session:
            row = session.get(BusinessRun, run_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            if user and not self._can_user_access_run(row, user):
                raise HTTPException(status_code=403, detail="BUSINESS_RUN_FORBIDDEN")
            return self._run_to_dict(row, session=session)

    def finalize_run(self, run_id: str) -> None:
        with get_session() as session:
            run = session.get(BusinessRun, run_id)
            if not run:
                return
            self._sync_run_steps(session=session, run=run)
            if run.ability_task_id and run.status not in {"succeeded", "failed", "cancelled"}:
                task = session.get(AbilityTask, run.ability_task_id)
                if task:
                    self._copy_task_to_run(session=session, run=run, task=task)
            should_submit_primary = not run.ability_task_id and run.status not in {"failed", "cancelled"}
            session.commit()
            run_status = run.status
            terminal_after_sync = run.status in {"succeeded", "failed", "cancelled"}
        if should_submit_primary:
            self._submit_primary_after_vl_if_ready(run_id=run_id, user=None)
            with get_session() as session:
                run = session.get(BusinessRun, run_id)
                run_status = run.status if run else run_status
                terminal_after_sync = bool(run and run.status in {"succeeded", "failed", "cancelled"})
        if terminal_after_sync:
            self._auto_settle_run_if_needed(run_id)
            self._deliver_callback(run_id)

    def _start_finalize_thread(self) -> None:
        if self._thread_started:
            return
        self._thread_started = True

        def _loop() -> None:
            while True:
                try:
                    self._finalize_pending_runs()
                except Exception as exc:  # pragma: no cover - background best effort
                    logger.warning("business run finalize loop failed: %s", exc)
                time.sleep(FINALIZE_INTERVAL_SECONDS)

        threading.Thread(target=_loop, daemon=True).start()

    def _finalize_pending_runs(self) -> None:
        with get_session() as session:
            rows = (
                session.execute(
                    select(BusinessRun)
                    .where(BusinessRun.status.in_(["queued", "running"]))
                    .order_by(BusinessRun.updated_at.asc())
                    .limit(FINALIZE_BATCH_SIZE)
                )
                .scalars()
                .all()
            )
            for run in rows:
                task = session.get(AbilityTask, run.ability_task_id) if run.ability_task_id else None
                self._sync_run_steps(session=session, run=run)
                if task:
                    self._copy_task_to_run(session=session, run=run, task=task)
            session.commit()
            terminal_ids = [row.id for row in rows if row.status in {"succeeded", "failed", "cancelled"}]
            waiting_primary_ids = [
                row.id
                for row in rows
                if not row.ability_task_id and row.status not in {"failed", "cancelled", "succeeded"}
            ]
        self._finalize_pending_steps()
        for run_id in waiting_primary_ids:
            self._submit_primary_after_vl_if_ready(run_id=run_id, user=None)
        for run_id in terminal_ids:
            self._auto_settle_run_if_needed(run_id)
            self._deliver_callback(run_id)

    def _auto_settle_run_if_needed(self, run_id: str) -> None:
        if not bool(getattr(get_settings(), "wallet_auto_expense_enabled", True)):
            return
        try:
            with get_session() as session:
                run = session.get(BusinessRun, run_id)
                if not run:
                    return
                if self._business_billing_status(run) != "billable":
                    return
                existing = self._billing_settlement_from_run(run)
                if existing and str(existing.get("status") or "").lower() in {"settled", "refunded"}:
                    return
            self.retry_billing(run_id)
        except HTTPException as exc:
            if exc.detail in {"BUSINESS_RUN_UNPRICED", "BUSINESS_RUN_USER_REQUIRED", "BUSINESS_RUN_NOT_BILLABLE"}:
                return
            logger.warning("business run auto billing failed: run_id=%s detail=%s", run_id, exc.detail)
        except Exception as exc:  # pragma: no cover - background best effort
            logger.warning("business run auto billing failed: run_id=%s error=%s", run_id, exc)

    def _finalize_pending_steps(self) -> None:
        with get_session() as session:
            rows = (
                session.execute(
                    select(BusinessRunStep)
                    .where(
                        BusinessRunStep.status.in_(["queued", "running"]),
                        BusinessRunStep.ability_task_id.is_not(None),
                    )
                    .order_by(BusinessRunStep.updated_at.asc())
                    .limit(FINALIZE_BATCH_SIZE)
                )
                .scalars()
                .all()
            )
            for step in rows:
                if not step.ability_task_id:
                    continue
                task = session.get(AbilityTask, step.ability_task_id)
                if task:
                    self._copy_task_to_step(session=session, step=step, task=task)
            session.commit()

    def _sync_run_steps(self, *, session, run: BusinessRun) -> None:
        rows = (
            session.execute(
                select(BusinessRunStep)
                .where(
                    BusinessRunStep.run_id == run.id,
                    BusinessRunStep.status.in_(["queued", "running"]),
                    BusinessRunStep.ability_task_id.is_not(None),
                )
                .order_by(BusinessRunStep.step_order.asc())
            )
            .scalars()
            .all()
        )
        for step in rows:
            if not step.ability_task_id:
                continue
            task = session.get(AbilityTask, step.ability_task_id)
            if task:
                self._copy_task_to_step(session=session, step=step, task=task)

    def _copy_task_to_step(self, *, session, step: BusinessRunStep, task: AbilityTask) -> None:
        status = str(task.status or "running")
        step.status = status
        step.ability_task_id = task.id
        step.ability_log_id = task.log_id
        step.result_payload = self._omit_large_fields(task.result_payload if isinstance(task.result_payload, dict) else {})
        step.error_message = task.error_message
        step.started_at = task.started_at or step.started_at
        step.duration_ms = task.duration_ms or self._calculate_duration_ms(step.started_at, task.finished_at or step.finished_at)
        self._copy_cost_fields_from_task(session=session, target=step, task=task)
        if status in {"succeeded", "failed", "cancelled"}:
            step.finished_at = task.finished_at or datetime.utcnow()

    def _copy_task_to_run(self, *, session, run: BusinessRun, task: AbilityTask) -> None:
        payload = task.result_payload if isinstance(task.result_payload, dict) else {}
        status = str(task.status or "running")
        run.status = status
        run.ability_log_id = task.log_id
        run.result_payload = self._omit_large_fields(payload)
        run.image_urls = self._extract_urls(payload, keys=("images", "assets", "resultUrls", "imageUrls"))
        run.video_urls = self._extract_urls(payload, keys=("videos", "videoUrls"))
        texts = payload.get("texts") if isinstance(payload, dict) else None
        run.texts = [str(x) for x in texts if isinstance(x, (str, int, float))] if isinstance(texts, list) else None
        run.error_message = task.error_message
        run.duration_ms = task.duration_ms or self._calculate_duration_ms(run.started_at or task.started_at, task.finished_at or run.finished_at)
        self._copy_cost_fields_from_task(session=session, target=run, task=task)
        if task.started_at and not run.started_at:
            run.started_at = task.started_at
        if status in {"succeeded", "failed", "cancelled"}:
            run.finished_at = task.finished_at or datetime.utcnow()
        step = self._find_primary_step(session=session, run=run, task_id=task.id)
        if step:
            self._copy_task_to_step(session=session, step=step, task=task)
            session.add(step)
        session.add(run)

    def retry_callback(self, run_id: str, *, actor: User | None = None) -> dict[str, Any]:
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            raise HTTPException(status_code=400, detail="BUSINESS_RUN_ID_REQUIRED")
        with get_session() as session:
            run = session.get(BusinessRun, normalized_run_id)
            if not run:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            if not run.callback_url:
                raise HTTPException(status_code=409, detail="BUSINESS_CALLBACK_NOT_CONFIGURED")
            if str(run.status or "").lower() in {"queued", "running"}:
                raise HTTPException(status_code=409, detail="BUSINESS_RUN_NOT_FINISHED")
            before = {
                "callbackStatus": run.callback_status,
                "callbackHttpStatus": run.callback_http_status,
                "callbackError": run.callback_error,
            }
            run.callback_status = None
            run.callback_http_status = None
            run.callback_error = None
            run.callback_response = None
            self._record_business_operation(
                session=session,
                action="retry_callback",
                target_type="business_run",
                target_id=run.id,
                business_key=run.business_key,
                tenant_id=run.tenant_id,
                client_id=run.client_id,
                actor=actor,
                before_payload=before,
            )
            session.add(run)
            session.commit()

        self._deliver_callback(normalized_run_id, force=True)
        return self.get_run(run_id=normalized_run_id, user=None)

    @staticmethod
    def _package_remaining(row: PackageBalance) -> int:
        return max(0, int(row.total_units or 0) - int(row.used_units or 0) - int(row.frozen_units or 0))

    def _record_package_consumption(
        self,
        *,
        user_id: str,
        business_key: str,
        units: int,
        run_id: str,
        trace_id: str,
    ) -> dict[str, Any] | None:
        now = datetime.utcnow()
        with get_session() as session:
            existing = (
                session.execute(
                    select(PackageLedger).where(
                        PackageLedger.user_id == user_id,
                        PackageLedger.trace_id == trace_id,
                    )
                )
                .scalars()
                .first()
            )
            if existing:
                balance = session.get(PackageBalance, existing.package_balance_id)
                return {
                    "status": "settled",
                    "method": "package",
                    "traceId": trace_id,
                    "packageBalanceId": str(existing.package_balance_id),
                    "packageKey": existing.package_key,
                    "businessKey": existing.business_key,
                    "units": int(existing.units or 0),
                    "remainingUnits": int(existing.balance_after or 0),
                    "ledgerId": f"pkg_txn_{existing.id}",
                    "idempotent": True,
                    "settledAt": existing.created_at.isoformat() if existing.created_at else now.isoformat(),
                    "packageName": balance.package_name if balance else None,
                }
            rows = (
                session.execute(
                    select(PackageBalance).where(
                        PackageBalance.user_id == user_id,
                        PackageBalance.status == "active",
                    )
                )
                .scalars()
                .all()
            )
            candidates: list[PackageBalance] = []
            for row in rows:
                if row.business_key not in {None, business_key}:
                    continue
                if row.expires_at and row.expires_at < now:
                    continue
                if self._package_remaining(row) < units:
                    continue
                candidates.append(row)
            if not candidates:
                return None
            candidates.sort(
                key=lambda row: (
                    0 if row.business_key == business_key else 1,
                    row.expires_at or datetime.max,
                    row.created_at or now,
                )
            )
            balance = candidates[0]
            balance.used_units = int(balance.used_units or 0) + units
            balance.updated_at = now
            remaining = self._package_remaining(balance)
            ledger = PackageLedger(
                package_balance_id=int(balance.id),
                user_id=user_id,
                package_key=balance.package_key,
                business_key=balance.business_key,
                direction="out",
                units=units,
                balance_after=remaining,
                related_task_id=run_id,
                trace_id=trace_id,
                source="business-run",
                remark=f"business run consume:{run_id}",
                created_at=now,
            )
            session.add(balance)
            session.add(ledger)
            session.commit()
            return {
                "status": "settled",
                "method": "package",
                "traceId": trace_id,
                "packageBalanceId": str(balance.id),
                "packageKey": balance.package_key,
                "packageName": balance.package_name,
                "businessKey": balance.business_key,
                "units": units,
                "remainingUnits": remaining,
                "ledgerId": f"pkg_txn_{ledger.id}",
                "idempotent": False,
                "settledAt": now.isoformat(),
            }

    def _refund_package_consumption(
        self,
        *,
        user_id: str,
        settlement: dict[str, Any],
        run_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        units = self._first_int(settlement.get("units"), settlement.get("deducted"))
        balance_id = self._first_int(settlement.get("packageBalanceId"), settlement.get("package_balance_id"))
        if units is None or units <= 0 or balance_id is None:
            raise HTTPException(status_code=409, detail="BUSINESS_PACKAGE_SETTLEMENT_INVALID")
        now = datetime.utcnow()
        with get_session() as session:
            existing = (
                session.execute(
                    select(PackageLedger).where(
                        PackageLedger.user_id == user_id,
                        PackageLedger.trace_id == trace_id,
                    )
                )
                .scalars()
                .first()
            )
            if existing:
                return {
                    "refundTraceId": trace_id,
                    "refundLedgerId": f"pkg_txn_{existing.id}",
                    "refundIdempotent": True,
                    "refundRemainingUnits": int(existing.balance_after or 0),
                    "refundedAt": existing.created_at.isoformat() if existing.created_at else now.isoformat(),
                }
            balance = session.get(PackageBalance, balance_id)
            if not balance or balance.user_id != user_id:
                raise HTTPException(status_code=409, detail="BUSINESS_PACKAGE_SETTLEMENT_NOT_FOUND")
            balance.used_units = max(0, int(balance.used_units or 0) - units)
            balance.updated_at = now
            remaining = self._package_remaining(balance)
            ledger = PackageLedger(
                package_balance_id=int(balance.id),
                user_id=user_id,
                package_key=balance.package_key,
                business_key=balance.business_key,
                direction="in",
                units=units,
                balance_after=remaining,
                related_task_id=run_id,
                trace_id=trace_id,
                source="business-run-refund",
                remark=f"business run package refund:{run_id}",
                created_at=now,
            )
            session.add(balance)
            session.add(ledger)
            session.commit()
            return {
                "refundTraceId": trace_id,
                "refundLedgerId": f"pkg_txn_{ledger.id}",
                "refundIdempotent": False,
                "refundRemainingUnits": remaining,
                "refundedAt": now.isoformat(),
            }

    def retry_billing(self, run_id: str, *, actor: User | None = None) -> dict[str, Any]:
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            raise HTTPException(status_code=400, detail="BUSINESS_RUN_ID_REQUIRED")
        with get_session() as session:
            run = session.get(BusinessRun, normalized_run_id)
            if not run:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            if str(run.status or "").lower() in {"queued", "running", "pending", "planned"}:
                raise HTTPException(status_code=409, detail="BUSINESS_RUN_NOT_FINISHED")
            billing_status = self._business_billing_status(run)
            if billing_status == "no_charge":
                raise HTTPException(status_code=409, detail="BUSINESS_RUN_NOT_BILLABLE")
            if billing_status == "unpriced":
                raise HTTPException(status_code=409, detail="BUSINESS_RUN_UNPRICED")
            if billing_status != "billable":
                raise HTTPException(status_code=409, detail="BUSINESS_RUN_NOT_BILLABLE")
            user_id = str(run.user_id or "").strip()
            if not user_id:
                raise HTTPException(status_code=400, detail="BUSINESS_RUN_USER_REQUIRED")
            points = self._business_wallet_points(run)
            quota_units = self._business_quota_units(run)
            before_settlement = self._billing_settlement_from_run(run)
            billing_attempt = self._next_billing_attempt(before_settlement)
            trace_id = self._business_billing_trace("business_run", run.id, billing_attempt)
            package_trace_id = self._business_billing_trace("business_run_package", run.id, billing_attempt)
            provider = run.business_key
            model_key = self._first_string(run.version, run.business_version_id, run.ability_task_id)

        existing_method = str((before_settlement or {}).get("method") or "").strip().lower()
        existing_status = str((before_settlement or {}).get("status") or "").strip().lower()
        existing_is_wallet = existing_method == "wallet" or bool((before_settlement or {}).get("transactionId"))
        allow_package = not (existing_is_wallet and existing_status in {"settled", "refunded"})
        settlement = (
            self._record_package_consumption(
                user_id=user_id,
                business_key=provider,
                units=quota_units,
                run_id=normalized_run_id,
                trace_id=package_trace_id,
            )
            if allow_package
            else None
        )
        settlement_kind = "package" if settlement else "wallet"
        if settlement is None:
            try:
                wallet_result = wallet_service.record_expense(
                    user_id=user_id,
                    points=points,
                    task_id=normalized_run_id,
                    trace_id=trace_id,
                    provider=provider,
                    model_key=model_key,
                    description=f"business run settle:{normalized_run_id}",
                )
                settlement = {
                    "status": "settled",
                    "method": "wallet",
                    "traceId": trace_id,
                    "points": points,
                    "balance": wallet_result.get("balance"),
                    "transactionId": wallet_result.get("transactionId"),
                    "idempotent": bool(wallet_result.get("idempotent")),
                    "billingAttempt": billing_attempt,
                    "settledAt": datetime.utcnow().isoformat(),
                }
            except HTTPException as exc:
                settlement = {
                    "status": "failed",
                    "method": "wallet",
                    "traceId": trace_id,
                    "points": points,
                    "billingAttempt": billing_attempt,
                    "error": str(exc.detail),
                    "failedAt": datetime.utcnow().isoformat(),
                }
        if isinstance(settlement, dict):
            settlement["billingAttempt"] = billing_attempt

        with get_session() as session:
            run = session.get(BusinessRun, normalized_run_id)
            if not run:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            cost_breakdown = dict(run.cost_breakdown or {})
            cost_breakdown["billingSettlement"] = settlement
            if settlement_kind == "package":
                cost_breakdown["packageSettlement"] = settlement
            else:
                cost_breakdown["walletSettlement"] = settlement
            run.cost_breakdown = self._json_safe_payload(cost_breakdown)
            run.updated_at = datetime.utcnow()
            self._record_business_operation(
                session=session,
                action="retry_billing",
                target_type="business_run",
                target_id=run.id,
                business_key=run.business_key,
                tenant_id=run.tenant_id,
                client_id=run.client_id,
                actor=actor,
                before_payload=before_settlement if isinstance(before_settlement, dict) else None,
                after_payload=settlement,
            )
            session.add(run)
            session.commit()
        return self.get_run(run_id=normalized_run_id, user=None)

    def refund_billing(self, run_id: str, *, actor: User | None = None) -> dict[str, Any]:
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            raise HTTPException(status_code=400, detail="BUSINESS_RUN_ID_REQUIRED")
        with get_session() as session:
            run = session.get(BusinessRun, normalized_run_id)
            if not run:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            if str(run.status or "").lower() in {"queued", "running", "pending", "planned"}:
                raise HTTPException(status_code=409, detail="BUSINESS_RUN_NOT_FINISHED")
            user_id = str(run.user_id or "").strip()
            if not user_id:
                raise HTTPException(status_code=400, detail="BUSINESS_RUN_USER_REQUIRED")
            package_settlement = self._package_settlement_from_run(run)
            before_settlement = package_settlement or self._wallet_settlement_from_run(run)
            if not before_settlement:
                raise HTTPException(status_code=409, detail="BUSINESS_WALLET_SETTLEMENT_NOT_FOUND")
            if package_settlement:
                billing_attempt = self._settlement_billing_attempt(package_settlement)
                trace_id = str(
                    package_settlement.get("refundTraceId")
                    or self._business_billing_trace("business_run_package_refund", run.id, billing_attempt)
                )[:64]
                refund_result = self._refund_package_consumption(
                    user_id=user_id,
                    settlement=package_settlement,
                    run_id=normalized_run_id,
                    trace_id=trace_id,
                )
                settlement = {
                    **package_settlement,
                    "status": "refunded",
                    **refund_result,
                }
                with get_session() as session:
                    run = session.get(BusinessRun, normalized_run_id)
                    if not run:
                        raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
                    cost_breakdown = dict(run.cost_breakdown or {})
                    cost_breakdown["packageSettlement"] = settlement
                    cost_breakdown["billingSettlement"] = settlement
                    run.cost_breakdown = self._json_safe_payload(cost_breakdown)
                    run.updated_at = datetime.utcnow()
                    self._record_business_operation(
                        session=session,
                        action="refund_billing",
                        target_type="business_run",
                        target_id=run.id,
                        business_key=run.business_key,
                        tenant_id=run.tenant_id,
                        client_id=run.client_id,
                        actor=actor,
                        before_payload=before_settlement,
                        after_payload=settlement,
                    )
                    session.add(run)
                    session.commit()
                return self.get_run(run_id=normalized_run_id, user=None)
            points = self._first_int(before_settlement.get("points"), before_settlement.get("deducted"))
            if points is None or points <= 0:
                raise HTTPException(status_code=409, detail="BUSINESS_WALLET_SETTLEMENT_NOT_FOUND")
            billing_attempt = self._settlement_billing_attempt(before_settlement)
            trace_id = str(
                before_settlement.get("refundTraceId")
                or self._business_billing_trace("business_run_refund", run.id, billing_attempt)
            )[:64]
            provider = run.business_key
            model_key = self._first_string(run.version, run.business_version_id, run.ability_task_id)

        wallet_result = wallet_service.record_adjustment(
            user_id=user_id,
            direction="increase",
            points=points,
            task_id=normalized_run_id,
            trace_id=trace_id,
            provider=provider,
            model_key=model_key,
            description=f"business run refund:{normalized_run_id}",
        )
        settlement = {
            **before_settlement,
            "status": "refunded",
            "refundTraceId": trace_id,
            "refundTransactionId": wallet_result.get("transactionId"),
            "refundBalance": wallet_result.get("balance"),
            "refundIdempotent": bool(wallet_result.get("idempotent")),
            "refundedAt": datetime.utcnow().isoformat(),
        }

        with get_session() as session:
            run = session.get(BusinessRun, normalized_run_id)
            if not run:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            cost_breakdown = dict(run.cost_breakdown or {})
            cost_breakdown["walletSettlement"] = settlement
            cost_breakdown["billingSettlement"] = settlement
            run.cost_breakdown = self._json_safe_payload(cost_breakdown)
            run.updated_at = datetime.utcnow()
            self._record_business_operation(
                session=session,
                action="refund_billing",
                target_type="business_run",
                target_id=run.id,
                business_key=run.business_key,
                tenant_id=run.tenant_id,
                client_id=run.client_id,
                actor=actor,
                before_payload=before_settlement,
                after_payload=settlement,
            )
            session.add(run)
            session.commit()
        return self.get_run(run_id=normalized_run_id, user=None)

    def retest_run(self, run_id: str, *, actor: User | None = None) -> dict[str, Any]:
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            raise HTTPException(status_code=400, detail="BUSINESS_RUN_ID_REQUIRED")
        with get_session() as session:
            run = session.get(BusinessRun, normalized_run_id)
            if not run:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            if str(run.status or "").lower() in {"queued", "running"}:
                raise HTTPException(status_code=409, detail="BUSINESS_RUN_NOT_FINISHED")
            business_key = run.business_key
            payload_data = self._build_retest_payload(run, actor=actor)
            before = {
                "runId": run.id,
                "status": run.status,
                "issue": self._build_run_issue_summary(run, session=session),
            }

        try:
            payload = BusinessRunCreateRequest.model_validate(payload_data)
        except Exception as exc:
            raise HTTPException(status_code=409, detail="BUSINESS_RUN_RETEST_PAYLOAD_INVALID") from exc

        created = self.create_run(
            business_key=business_key,
            payload=payload,
            user=actor,
            source="admin-retest",
        )
        with get_session() as session:
            self._record_business_operation(
                session=session,
                action="retest_run",
                target_type="business_run",
                target_id=normalized_run_id,
                business_key=business_key,
                tenant_id=created.get("tenant_id"),
                client_id=created.get("client_id"),
                actor=actor,
                before_payload=before,
                after_payload={
                    "newRunId": created.get("id"),
                    "newStatus": created.get("status"),
                    "newTaskId": created.get("ability_task_id"),
                },
            )
            session.commit()
        return created

    def bulk_retest_runs(
        self,
        run_ids: list[str],
        *,
        actor: User | None = None,
        only_failed: bool = True,
    ) -> dict[str, Any]:
        unique_run_ids = self._normalize_bulk_run_ids(run_ids)
        items: list[dict[str, Any]] = []
        for run_id in unique_run_ids:
            try:
                if only_failed:
                    with get_session() as session:
                        run = session.get(BusinessRun, run_id)
                        if not run:
                            raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
                        issue = self._build_run_issue_summary(run, session=session)
                        has_problem = str(run.status or "").lower() in {"failed", "cancelled"} or issue["category"] != "none"
                        if not has_problem:
                            items.append(
                                {
                                    "run_id": run_id,
                                    "ok": False,
                                    "status": "skipped",
                                    "message": "当前记录没有明显链路问题，已跳过。",
                                }
                            )
                            continue
                        retest_summary = self._build_retest_summary(run, session=session)
                        if retest_summary.get("recovered"):
                            items.append(
                                {
                                    "run_id": run_id,
                                    "ok": False,
                                    "status": "skipped",
                                    "message": "当前问题已有复测成功记录，已跳过。",
                                }
                            )
                            continue
                next_run = self.retest_run(run_id, actor=actor)
                items.append(
                    {
                        "run_id": run_id,
                        "new_run_id": next_run.get("id"),
                        "ok": True,
                        "status": str(next_run.get("status") or "queued"),
                        "message": "已创建新的复测任务。",
                    }
                )
            except HTTPException as exc:
                items.append(
                    {
                        "run_id": run_id,
                        "ok": False,
                        "status": "failed",
                        "message": str(exc.detail),
                    }
                )
            except Exception as exc:  # pragma: no cover - defensive
                items.append(
                    {
                        "run_id": run_id,
                        "ok": False,
                        "status": "failed",
                        "message": str(exc)[:500],
                    }
                )
        return self._bulk_action_response(action="retest", items=items)

    def bulk_retry_callbacks(
        self,
        run_ids: list[str],
        *,
        actor: User | None = None,
        only_failed: bool = True,
    ) -> dict[str, Any]:
        unique_run_ids = self._normalize_bulk_run_ids(run_ids)
        items: list[dict[str, Any]] = []
        for run_id in unique_run_ids:
            try:
                if only_failed:
                    with get_session() as session:
                        run = session.get(BusinessRun, run_id)
                        if not run:
                            raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
                        callback_failed = str(run.callback_status or "").lower() == "failed" or bool(run.callback_error)
                        if not callback_failed:
                            items.append(
                                {
                                    "run_id": run_id,
                                    "ok": False,
                                    "status": "skipped",
                                    "message": "当前不是回调失败状态，已跳过。",
                                }
                            )
                            continue
                next_run = self.retry_callback(run_id, actor=actor)
                items.append(
                    {
                        "run_id": run_id,
                        "ok": True,
                        "status": str(next_run.get("callback_status") or next_run.get("status") or "submitted"),
                        "message": next_run.get("callback_error"),
                    }
                )
            except HTTPException as exc:
                items.append(
                    {
                        "run_id": run_id,
                        "ok": False,
                        "status": "failed",
                        "message": str(exc.detail),
                    }
                )
            except Exception as exc:  # pragma: no cover - defensive
                items.append(
                    {
                        "run_id": run_id,
                        "ok": False,
                        "status": "failed",
                        "message": str(exc)[:500],
                    }
                )
        return self._bulk_action_response(action="callback_retry", items=items)

    def mark_issues_ignored(
        self,
        run_ids: list[str],
        *,
        note: str | None = None,
        actor: User | None = None,
    ) -> dict[str, Any]:
        unique_run_ids = self._normalize_bulk_run_ids(run_ids)
        now = datetime.utcnow()
        items: list[dict[str, Any]] = []
        with get_session() as session:
            for run_id in unique_run_ids:
                run = session.get(BusinessRun, run_id)
                if not run:
                    items.append(
                        {
                            "run_id": run_id,
                            "ok": False,
                            "status": "failed",
                            "message": "BUSINESS_RUN_NOT_FOUND",
                        }
                    )
                    continue
                payload = run.result_payload if isinstance(run.result_payload, dict) else {}
                before = payload.get("_adminIssueResolution") or payload.get("_admin_issue_resolution")
                resolution = {
                    "status": "ignored",
                    "note": self._clean_optional_text(note),
                    "actor": self._actor_username(actor),
                    "at": now.isoformat(),
                }
                payload = dict(payload)
                payload["_adminIssueResolution"] = resolution
                run.result_payload = payload
                run.updated_at = now
                self._record_business_operation(
                    session=session,
                    action="mark_issue_ignored",
                    target_type="business_run",
                    target_id=run.id,
                    business_key=run.business_key,
                    tenant_id=run.tenant_id,
                    client_id=run.client_id,
                    actor=actor,
                    note=note,
                    before_payload=before if isinstance(before, dict) else None,
                    after_payload=resolution,
                )
                session.add(run)
                items.append(
                    {
                        "run_id": run_id,
                        "ok": True,
                        "status": "ignored",
                        "message": resolution["note"],
                    }
                )
            session.commit()
        return self._bulk_action_response(action="mark_issue_ignored", items=items)

    def generate_issue_checklist(
        self,
        run_ids: list[str],
        *,
        only_failed: bool = True,
        actor: User | None = None,
    ) -> dict[str, Any]:
        unique_run_ids = self._normalize_bulk_run_ids(run_ids)
        generated_at = datetime.utcnow().isoformat()
        items: list[dict[str, Any]] = []
        skipped_count = 0
        with get_session() as session:
            for run_id in unique_run_ids:
                row = session.get(BusinessRun, run_id)
                if not row:
                    skipped_count += 1
                    continue
                issue = self._build_run_issue_summary(row, session=session)
                status = str(row.status or "").strip().lower()
                has_issue = issue["category"] != "none" or status in {"failed", "cancelled"}
                if only_failed and not has_issue:
                    skipped_count += 1
                    continue
                items.append(self._build_issue_checklist_item(row, issue=issue, session=session))
            markdown = self._issue_checklist_markdown(items, generated_at=generated_at, skipped_count=skipped_count)
            self._record_business_operation(
                session=session,
                action="generate_issue_checklist",
                target_type="business_run",
                actor=actor,
                note=f"生成业务排障清单：{len(items)} 条，跳过 {skipped_count} 条。",
                after_payload={
                    "runIds": unique_run_ids,
                    "issueCount": len(items),
                    "skippedCount": skipped_count,
                    "byCategory": self._count_by(items, "issue_category"),
                    "bySeverity": self._count_by(items, "issue_severity"),
                },
            )
            session.commit()
        return {
            "generated_at": generated_at,
            "total": len(unique_run_ids),
            "issue_count": len(items),
            "skipped_count": skipped_count,
            "by_category": self._count_by(items, "issue_category"),
            "by_severity": self._count_by(items, "issue_severity"),
            "markdown": markdown,
            "items": items,
        }

    def _build_retest_payload(self, run: BusinessRun, *, actor: User | None = None) -> dict[str, Any]:
        request_payload = dict(run.request_payload) if isinstance(run.request_payload, dict) else {}
        clean_payload = {key: value for key, value in request_payload.items() if not str(key).startswith("_")}
        clean_payload.pop("callbackUrl", None)
        clean_payload.pop("callbackHeaders", None)
        clean_payload.pop("callback_url", None)
        clean_payload.pop("callback_headers", None)
        clean_payload.setdefault("version", run.version)
        if run.tenant_id:
            clean_payload.setdefault("tenantId", run.tenant_id)
        if run.client_id:
            clean_payload.setdefault("clientId", run.client_id)

        metadata = dict(clean_payload.get("metadata") or {})
        metadata["adminRetest"] = {
            "sourceRunId": run.id,
            "sourceStatus": run.status,
            "sourceTraceId": run.trace_id,
            "sourceRequestId": run.request_id,
            "actor": self._actor_username(actor),
            "at": datetime.utcnow().isoformat(),
        }
        clean_payload["metadata"] = metadata
        clean_payload["source"] = "admin-retest"
        clean_payload["channel"] = "manual-retest"
        clean_payload["traceId"] = f"retest_{run.id[:12]}_{uuid4().hex[:8]}"[:64]
        clean_payload["requestId"] = f"retest_{uuid4().hex[:16]}"[:64]
        return clean_payload

    def _build_retest_summary(self, run: BusinessRun, *, session=None) -> dict[str, Any]:
        source_run_id = self._extract_retest_source_run_id(run)
        summary: dict[str, Any] = {
            "sourceRunId": source_run_id,
            "attempts": 0,
            "latestRunId": None,
            "latestStatus": None,
            "latestIssueCategory": None,
            "latestIssueLabel": None,
            "recovered": False,
            "history": [],
        }
        if session is None:
            return summary

        if source_run_id:
            source = session.get(BusinessRun, source_run_id)
            if source:
                source_issue = self._build_run_issue_summary(source, session=session)
                summary.update(
                    {
                        "sourceStatus": source.status,
                        "sourceIssueCategory": source_issue.get("category"),
                        "sourceIssueLabel": source_issue.get("label"),
                    }
                )
            return summary

        logs = (
            session.execute(
                select(BusinessOperationLog)
                .where(
                    BusinessOperationLog.action == "retest_run",
                    BusinessOperationLog.target_type == "business_run",
                    BusinessOperationLog.target_id == run.id,
                )
                .order_by(BusinessOperationLog.created_at.desc())
            )
            .scalars()
            .all()
        )
        history: list[dict[str, Any]] = []
        recovered = False
        for log in logs:
            after_payload = log.after_payload if isinstance(log.after_payload, dict) else {}
            new_run_id = str(after_payload.get("newRunId") or after_payload.get("new_run_id") or "").strip()
            if not new_run_id:
                continue
            retest_run = session.get(BusinessRun, new_run_id)
            issue = self._build_run_issue_summary(retest_run, session=session) if retest_run else {}
            has_business_output = bool(
                retest_run and ((retest_run.image_urls or []) or (retest_run.video_urls or []) or (retest_run.texts or []))
            )
            is_recovered = bool(retest_run and retest_run.status == "succeeded" and has_business_output)
            recovered = recovered or is_recovered
            history.append(
                {
                    "runId": new_run_id,
                    "status": retest_run.status if retest_run else str(after_payload.get("newStatus") or ""),
                    "issueCategory": "none" if is_recovered else issue.get("category"),
                    "issueLabel": "暂无明显问题" if is_recovered else issue.get("label"),
                    "recovered": is_recovered,
                    "createdAt": log.created_at.isoformat() if log.created_at else None,
                }
            )

        latest = history[0] if history else {}
        summary.update(
            {
                "attempts": len(history),
                "latestRunId": latest.get("runId"),
                "latestStatus": latest.get("status"),
                "latestIssueCategory": latest.get("issueCategory"),
                "latestIssueLabel": latest.get("issueLabel"),
                "recovered": recovered,
                "history": history[:10],
            }
        )
        return summary

    @staticmethod
    def _extract_retest_source_run_id(run: BusinessRun) -> str | None:
        request_payload = run.request_payload if isinstance(run.request_payload, dict) else {}
        metadata = request_payload.get("metadata") if isinstance(request_payload.get("metadata"), dict) else {}
        retest = metadata.get("adminRetest") or metadata.get("admin_retest")
        if not isinstance(retest, dict):
            return None
        source_run_id = str(retest.get("sourceRunId") or retest.get("source_run_id") or "").strip()
        return source_run_id or None

    def _deliver_callback(self, run_id: str, *, force: bool = False) -> None:
        with get_session() as session:
            run = session.get(BusinessRun, run_id)
            if not run or not run.callback_url:
                return
            if not force and run.callback_status in {"success", "failed"}:
                return
            payload = self._callback_payload(run)
            callback_url = str(run.callback_url)
            callback_headers = dict(run.callback_headers or {})
            run.callback_status = "running"
            run.callback_error = None
            run.callback_http_status = None
            run.callback_response = None
            run.callback_payload = payload
            session.add(run)
            session.commit()

        try:
            response = httpx.post(
                callback_url,
                json=payload,
                headers=callback_headers,
                timeout=15,
            )
            body: dict[str, Any] = {}
            try:
                parsed = response.json()
                if isinstance(parsed, dict):
                    body = parsed
                else:
                    body = {"body": str(parsed)[:1000]}
            except Exception:
                body = {"body": response.text[:1000]}
            with get_session() as session:
                db_run = session.get(BusinessRun, run_id)
                if db_run:
                    db_run.callback_http_status = response.status_code
                    db_run.callback_response = body
                    db_run.callback_status = "success" if response.status_code < 400 else "failed"
                    db_run.callback_error = None if response.status_code < 400 else f"HTTP_{response.status_code}"
                    session.add(db_run)
                    session.commit()
        except Exception as exc:
            with get_session() as session:
                db_run = session.get(BusinessRun, run_id)
                if db_run:
                    db_run.callback_status = "failed"
                    db_run.callback_error = str(exc)[:500]
                    session.add(db_run)
                    session.commit()

    def _callback_payload(self, run: BusinessRun) -> dict[str, Any]:
        return {
            "runId": run.id,
            "businessKey": run.business_key,
            "version": run.version,
            "status": run.status,
            "traceId": run.trace_id,
            "requestId": run.request_id,
            "tenantId": run.tenant_id,
            "clientId": run.client_id,
            "channel": run.channel,
            "taskId": run.ability_task_id,
            "imageUrls": run.image_urls or [],
            "videoUrls": run.video_urls or [],
            "texts": run.texts or [],
            "error": run.error_message,
            "durationMs": run.duration_ms,
            "costAmount": float(run.cost_amount) if run.cost_amount is not None else None,
            "currency": run.currency,
            "debugUrl": run.debug_url,
        }

    def _check_business_client_policy(
        self,
        *,
        session,
        business_key: str,
        payload: BusinessRunCreateRequest,
        trace_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        tenant_id = self._short_text(trace_context.get("tenantId"), 64)
        client_id = self._short_text(trace_context.get("clientId"), 64)
        if not tenant_id:
            return None
        client = self._find_business_client(session, tenant_id=tenant_id, client_id=client_id)
        if not client:
            return None
        if client.status != "active":
            raise HTTPException(status_code=403, detail="BUSINESS_CLIENT_DISABLED")
        allowed_keys = self._normalize_business_key_list(client.allowed_business_keys)
        if allowed_keys and business_key not in allowed_keys:
            raise HTTPException(status_code=403, detail="BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED")

        running_statuses = {"queued", "running"}
        scope_filters = self._business_client_run_filters(client)
        if client.concurrent_run_limit:
            running_count = (
                session.execute(
                    select(func.count(BusinessRun.id)).where(
                        *scope_filters,
                        BusinessRun.status.in_(running_statuses),
                    )
                ).scalar_one()
                or 0
            )
            if int(running_count) >= int(client.concurrent_run_limit):
                raise HTTPException(status_code=429, detail="BUSINESS_CLIENT_CONCURRENCY_LIMITED")

        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if client.daily_run_limit:
            today_count = (
                session.execute(
                    select(func.count(BusinessRun.id)).where(
                        *scope_filters,
                        BusinessRun.created_at >= day_start,
                    )
                ).scalar_one()
                or 0
            )
            if int(today_count) >= int(client.daily_run_limit):
                raise HTTPException(status_code=429, detail="BUSINESS_CLIENT_DAILY_RUN_LIMITED")

        estimated_quota_units = self._estimate_quota_units(payload)
        if client.daily_quota_units:
            today_rows = (
                session.execute(
                    select(BusinessRun.quota_units).where(
                        *scope_filters,
                        BusinessRun.created_at >= day_start,
                    )
                )
                .scalars()
                .all()
            )
            used_units = sum(max(1, int(value or 1)) for value in today_rows)
            if used_units + estimated_quota_units > int(client.daily_quota_units):
                raise HTTPException(status_code=429, detail="BUSINESS_CLIENT_DAILY_QUOTA_LIMITED")

        return {
            "id": client.id,
            "tenantId": client.tenant_id,
            "clientId": client.client_id,
            "displayName": client.display_name,
            "allowedBusinessKeys": allowed_keys,
            "dailyRunLimit": client.daily_run_limit,
            "dailyQuotaUnits": client.daily_quota_units,
            "concurrentRunLimit": client.concurrent_run_limit,
            "estimatedQuotaUnits": estimated_quota_units,
        }

    def _find_business_client(
        self,
        session,
        *,
        tenant_id: str,
        client_id: str | None,
        exclude_id: str | None = None,
        include_tenant_default: bool = True,
    ) -> BusinessClient | None:
        normalized_tenant = self._short_text(tenant_id, 64)
        normalized_client = self._short_text(client_id, 64)
        if not normalized_tenant:
            return None
        candidates: list[BusinessClient] = []
        if normalized_client:
            stmt = select(BusinessClient).where(
                BusinessClient.tenant_id == normalized_tenant,
                BusinessClient.client_id == normalized_client,
            )
            if exclude_id:
                stmt = stmt.where(BusinessClient.id != exclude_id)
            exact = session.execute(stmt).scalars().first()
            if exact:
                candidates.append(exact)
        if include_tenant_default or not normalized_client:
            stmt = select(BusinessClient).where(
                BusinessClient.tenant_id == normalized_tenant,
                BusinessClient.client_id.is_(None),
            )
            if exclude_id:
                stmt = stmt.where(BusinessClient.id != exclude_id)
            tenant_default = session.execute(stmt).scalars().first()
            if tenant_default:
                candidates.append(tenant_default)
        return candidates[0] if candidates else None

    @staticmethod
    def _business_client_run_filters(client: BusinessClient) -> list[Any]:
        filters: list[Any] = [BusinessRun.tenant_id == client.tenant_id]
        if client.client_id:
            filters.append(BusinessRun.client_id == client.client_id)
        return filters

    def _estimate_quota_units(self, payload: BusinessRunCreateRequest) -> int:
        metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
        inputs = payload.inputs if isinstance(payload.inputs, dict) else {}
        value = self._first_int(
            metadata.get("quotaUnits"),
            metadata.get("quota_units"),
            inputs.get("quotaUnits"),
            inputs.get("quota_units"),
        )
        return max(1, int(value or 1))

    def _resolve_trace_context(
        self,
        *,
        run_id: str,
        business_key: str,
        payload: BusinessRunCreateRequest,
        source: str | None,
        user: User | None = None,
    ) -> dict[str, Any]:
        metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
        inputs = payload.inputs if isinstance(payload.inputs, dict) else {}
        source_value = self._short_text(
            self._first_string(
                payload.source,
                metadata.get("source"),
                metadata.get("entry"),
                source,
                "business-api",
            ),
            64,
        )
        channel = self._short_text(
            self._first_string(
                payload.channel,
                metadata.get("channel"),
                metadata.get("scene"),
                inputs.get("channel"),
            ),
            64,
        )
        explicit_tenant_id = self._short_text(
            self._first_string(
                payload.tenantId,
                metadata.get("tenantId"),
                metadata.get("tenant_id"),
                metadata.get("grayKey"),
                metadata.get("gray_key"),
                inputs.get("tenantId"),
                inputs.get("tenant_id"),
            ),
            64,
        )
        explicit_client_id = self._short_text(
            self._first_string(
                payload.clientId,
                metadata.get("clientId"),
                metadata.get("client_id"),
                inputs.get("clientId"),
                inputs.get("client_id"),
                payload.profile_id,
            ),
            64,
        )
        user_tenant_id = self._short_text(getattr(user, "tenant_id", None), 64)
        user_client_id = self._short_text(getattr(user, "client_id", None), 64)
        if user is not None and not self._is_privileged_business_user(user):
            if getattr(user, "role", "") == "client" and not user_tenant_id:
                raise HTTPException(status_code=403, detail="BUSINESS_USER_SCOPE_REQUIRED")
            if explicit_tenant_id and user_tenant_id and explicit_tenant_id != user_tenant_id:
                raise HTTPException(status_code=403, detail="BUSINESS_USER_SCOPE_FORBIDDEN")
            if explicit_client_id and user_client_id and explicit_client_id != user_client_id:
                raise HTTPException(status_code=403, detail="BUSINESS_USER_SCOPE_FORBIDDEN")
        trace_id = self._short_text(
            self._first_string(
                payload.traceId,
                metadata.get("traceId"),
                metadata.get("trace_id"),
                inputs.get("traceId"),
                inputs.get("trace_id"),
                run_id,
            ),
            64,
        )
        request_id = self._short_text(
            self._first_string(
                payload.requestId,
                metadata.get("requestId"),
                metadata.get("request_id"),
                inputs.get("requestId"),
                inputs.get("request_id"),
                run_id,
            ),
            64,
        )
        tenant_id = self._short_text(
            self._first_string(
                user_tenant_id if user is not None and not self._is_privileged_business_user(user) else None,
                explicit_tenant_id,
                getattr(user, "tenant_id", None),
            ),
            64,
        )
        client_id = self._short_text(
            self._first_string(
                user_client_id if user is not None and not self._is_privileged_business_user(user) else None,
                explicit_client_id,
                getattr(user, "client_id", None),
            ),
            64,
        )
        return {
            "businessKey": business_key,
            "source": source_value or "business-api",
            "channel": channel,
            "traceId": trace_id or run_id,
            "requestId": request_id or run_id,
            "tenantId": tenant_id,
            "clientId": client_id,
        }

    def _resolve_business_user_id(
        self,
        *,
        user: User | None,
        payload: BusinessRunCreateRequest,
        trace_context: dict[str, Any],
    ) -> str | None:
        user_id = self._safe_user_id(user)
        if user_id:
            return self._short_text(user_id, 64)
        # business_runs.user_id is a foreign key to platform users. External
        # business identifiers stay in tenant_id/client_id/metadata instead.
        return None

    def _resolve_business_user_name(self, *, user: User | None, payload: BusinessRunCreateRequest) -> str | None:
        metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
        inputs = payload.inputs if isinstance(payload.inputs, dict) else {}
        explicit = self._first_string(
            getattr(payload, "userName", None),
            metadata.get("userName"),
            metadata.get("user_name"),
            inputs.get("userName"),
            inputs.get("user_name"),
        )
        if explicit:
            return self._short_text(explicit, 128)
        return getattr(user, "username", None) if user else None

    @staticmethod
    def _short_text(value: Any, max_length: int) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        return text[:max_length]

    @staticmethod
    def _calculate_duration_ms(started_at: datetime | None, finished_at: datetime | None) -> int | None:
        if not started_at or not finished_at:
            return None
        try:
            return max(0, int((finished_at - started_at).total_seconds() * 1000))
        except Exception:
            return None

    def _copy_cost_fields_from_task(self, *, session, target: BusinessRun | BusinessRunStep, task: AbilityTask) -> None:
        payload = task.result_payload if isinstance(task.result_payload, dict) else {}
        log = session.get(AbilityInvocationLog, int(task.log_id)) if task.log_id else None
        cost_payload = payload.get("cost") if isinstance(payload.get("cost"), dict) else {}
        usage_payload = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        cost_policy, cost_policy_source = self._resolve_task_cost_policy(session=session, task=task)
        billing_unit = self._first_string(
            getattr(log, "billing_unit", None),
            cost_payload.get("billingUnit"),
            cost_payload.get("billing_unit"),
            usage_payload.get("unit"),
            cost_policy.get("billingUnit"),
            cost_policy.get("billing_unit"),
            cost_policy.get("unit"),
        )
        unit_price = self._first_number(
            getattr(log, "unit_price", None),
            cost_payload.get("unitPrice"),
            cost_payload.get("unit_price"),
            cost_policy.get("unitPrice"),
            cost_policy.get("unit_price"),
            cost_policy.get("discountPrice"),
            cost_policy.get("discount_price"),
            cost_policy.get("listPrice"),
            cost_policy.get("list_price"),
            cost_policy.get("price"),
        )
        cost_amount = self._first_number(
            getattr(log, "cost_amount", None),
            cost_payload.get("costAmount"),
            cost_payload.get("cost_amount"),
            cost_payload.get("total"),
            cost_payload.get("amount"),
        )
        cost_quantity = self._cost_policy_quantity(policy=cost_policy, billing_unit=billing_unit, payload=payload, usage=usage_payload)
        if cost_amount is None and unit_price is not None and cost_policy:
            cost_amount = round(float(unit_price) * max(1, cost_quantity), 4)
        currency = self._first_string(
            getattr(log, "currency", None),
            cost_payload.get("currency"),
            usage_payload.get("currency"),
            cost_policy.get("currency"),
        )
        quota_units = self._first_int(
            cost_payload.get("quotaUnits"),
            cost_payload.get("quota_units"),
            usage_payload.get("total_tokens"),
            usage_payload.get("totalTokens"),
            usage_payload.get("output_count"),
            cost_policy.get("quotaUnits"),
            cost_policy.get("quota_units"),
            cost_policy.get("quotaPerRun"),
            cost_policy.get("quota_per_run"),
        )
        if quota_units is None and cost_policy:
            quota_units = 1
        target.billing_unit = billing_unit
        target.unit_price = unit_price
        target.cost_amount = cost_amount
        target.currency = currency
        target.quota_units = quota_units
        target.cost_breakdown = self._omit_large_fields(
            {
                "abilityTaskId": task.id,
                "abilityLogId": task.log_id,
                "provider": task.ability_provider,
                "capabilityKey": task.capability_key,
                "cost": cost_payload or None,
                "usage": usage_payload or None,
                "costPolicy": cost_policy or None,
                "costPolicySource": cost_policy_source,
                "costPolicyQuantity": cost_quantity if cost_policy else None,
                "pricingVersion": cost_policy.get("pricingVersion") or cost_policy.get("pricing_version") if cost_policy else None,
            }
        )

    def _resolve_task_cost_policy(self, *, session, task: AbilityTask) -> tuple[dict[str, Any], str | None]:
        ability = session.get(Ability, task.ability_id) if task.ability_id else None
        policy: dict[str, Any] = {}
        sources: list[str] = []
        if ability and ability.vendor_model_id:
            vendor_model = session.get(VendorModelCatalog, ability.vendor_model_id)
            if vendor_model and isinstance(vendor_model.cost_policy, dict) and vendor_model.cost_policy:
                policy.update(vendor_model.cost_policy)
                sources.append("vendor_model")
        ability_metadata = ability.extra_metadata if ability and isinstance(ability.extra_metadata, dict) else {}
        for key in ("costPolicy", "cost_policy", "pricing"):
            raw = ability_metadata.get(key)
            if isinstance(raw, dict) and raw:
                policy.update(raw)
                sources.append(f"ability_metadata.{key}")
        return policy, "+".join(sources) if sources else None

    def _cost_policy_quantity(
        self,
        *,
        policy: dict[str, Any],
        billing_unit: str | None,
        payload: dict[str, Any],
        usage: dict[str, Any],
    ) -> int:
        explicit = self._first_int(
            policy.get("quantity"),
            policy.get("billableUnits"),
            policy.get("billable_units"),
            policy.get("unitsPerRun"),
            policy.get("units_per_run"),
        )
        if explicit is not None and explicit > 0:
            return explicit
        unit = str(billing_unit or policy.get("unit") or "").strip().lower()
        if unit in {"image", "images", "output_image", "output_images"}:
            images = payload.get("images") if isinstance(payload.get("images"), list) else []
            return max(1, len(images))
        if unit in {"video", "videos", "output_video", "output_videos"}:
            videos = payload.get("videos") if isinstance(payload.get("videos"), list) else []
            return max(1, len(videos))
        if unit in {"token", "tokens"}:
            tokens = self._first_int(usage.get("total_tokens"), usage.get("totalTokens"))
            return max(1, int(tokens or 1))
        return 1

    @staticmethod
    def _business_billing_status(row: BusinessRun) -> str:
        status = str(row.status or "").strip().lower()
        if status in {"queued", "running", "pending", "planned"}:
            return "billing_pending"
        if status in {"failed", "cancelled", "timeout"}:
            return "no_charge"
        if status == "succeeded":
            if BusinessRunService._business_no_charge_policy_reason(row):
                return "no_charge"
            cost_amount = BusinessRunService._first_number(row.cost_amount)
            quota_units = BusinessRunService._first_int(row.quota_units)
            if (cost_amount is not None and cost_amount > 0) or (quota_units is not None and quota_units > 0):
                return "billable"
            return "unpriced"
        return "billing_pending"

    @staticmethod
    def _truthy_policy_flag(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        return text in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _business_no_charge_policy_reason(row: BusinessRun) -> str | None:
        request_payload = row.request_payload if isinstance(row.request_payload, dict) else {}
        metadata = request_payload.get("metadata") if isinstance(request_payload.get("metadata"), dict) else {}
        inputs = request_payload.get("inputs") if isinstance(request_payload.get("inputs"), dict) else {}
        trace = request_payload.get("_trace") if isinstance(request_payload.get("_trace"), dict) else {}
        client = request_payload.get("_businessClient") if isinstance(request_payload.get("_businessClient"), dict) else {}
        cost_breakdown = row.cost_breakdown if isinstance(row.cost_breakdown, dict) else {}

        billing_mode = BusinessRunService._first_string(
            metadata.get("billingMode"),
            metadata.get("billing_mode"),
            inputs.get("billingMode"),
            inputs.get("billing_mode"),
            client.get("billingMode"),
            client.get("billing_mode"),
            cost_breakdown.get("billingMode"),
            cost_breakdown.get("billing_mode"),
        )
        if str(billing_mode or "").strip().lower() in NO_CHARGE_BILLING_MODES:
            return "调用已标记为免计费，不进入业务收费账单"

        source = str(row.source or trace.get("source") or metadata.get("source") or "").strip()
        tenant_id = str(row.tenant_id or trace.get("tenantId") or metadata.get("tenantId") or "").strip()
        client_id = str(row.client_id or trace.get("clientId") or metadata.get("clientId") or "").strip()
        if (
            source in INTERNAL_NO_CHARGE_SOURCES
            or tenant_id in INTERNAL_NO_CHARGE_TENANTS
            or client_id in INTERNAL_NO_CHARGE_CLIENTS
            or BusinessRunService._truthy_policy_flag(metadata.get("patrol"))
        ):
            return "内部巡检任务，不进入业务收费账单"
        return None

    @staticmethod
    def _business_no_charge_reason(row: BusinessRun) -> str | None:
        billing_status = BusinessRunService._business_billing_status(row)
        status = str(row.status or "").strip().lower()
        if billing_status == "no_charge":
            if status == "failed":
                return "任务失败，不向业务方计费"
            if status == "cancelled":
                return "任务已取消，不向业务方计费"
            if status == "timeout":
                return "任务超时，不向业务方计费"
            policy_reason = BusinessRunService._business_no_charge_policy_reason(row)
            if policy_reason:
                return policy_reason
            return "非成功任务，不向业务方计费"
        if billing_status == "billing_pending":
            return "任务未终态，暂不计费"
        if billing_status == "unpriced":
            return "任务成功但缺少定价，待确认计费口径"
        return None

    @staticmethod
    def _wallet_settlement_from_run(row: BusinessRun) -> dict[str, Any] | None:
        cost_breakdown = row.cost_breakdown if isinstance(row.cost_breakdown, dict) else {}
        value = cost_breakdown.get("walletSettlement") or cost_breakdown.get("wallet_settlement")
        return dict(value) if isinstance(value, dict) else None

    @staticmethod
    def _package_settlement_from_run(row: BusinessRun) -> dict[str, Any] | None:
        cost_breakdown = row.cost_breakdown if isinstance(row.cost_breakdown, dict) else {}
        value = cost_breakdown.get("packageSettlement") or cost_breakdown.get("package_settlement")
        return dict(value) if isinstance(value, dict) else None

    @staticmethod
    def _billing_settlement_from_run(row: BusinessRun) -> dict[str, Any] | None:
        cost_breakdown = row.cost_breakdown if isinstance(row.cost_breakdown, dict) else {}
        value = (
            cost_breakdown.get("billingSettlement")
            or cost_breakdown.get("billing_settlement")
            or cost_breakdown.get("packageSettlement")
            or cost_breakdown.get("package_settlement")
            or cost_breakdown.get("walletSettlement")
            or cost_breakdown.get("wallet_settlement")
        )
        return dict(value) if isinstance(value, dict) else None

    @staticmethod
    def _business_quota_units(row: BusinessRun) -> int:
        quota_units = BusinessRunService._first_int(row.quota_units)
        if quota_units is not None and quota_units > 0:
            return max(1, int(quota_units))
        return 1

    @staticmethod
    def _settlement_billing_attempt(settlement: dict[str, Any] | None) -> int:
        attempt = BusinessRunService._first_int(
            (settlement or {}).get("billingAttempt"),
            (settlement or {}).get("billing_attempt"),
            (settlement or {}).get("attempt"),
        )
        return max(1, int(attempt or 1))

    @staticmethod
    def _next_billing_attempt(settlement: dict[str, Any] | None) -> int:
        current = BusinessRunService._settlement_billing_attempt(settlement)
        status = str((settlement or {}).get("status") or "").strip().lower()
        return current + 1 if status == "refunded" else current

    @staticmethod
    def _business_billing_trace(prefix: str, run_id: str, attempt: int) -> str:
        base = f"{prefix}:{run_id}"
        if attempt <= 1:
            return base[:64]
        raw = f"{base}:a{attempt}"
        if len(raw) <= 64:
            return raw
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
        suffix = f":a{attempt}:{digest}"
        head_len = max(8, 64 - len(prefix) - 1 - len(suffix))
        return f"{prefix}:{str(run_id)[:head_len]}{suffix}"[:64]

    @staticmethod
    def _business_wallet_points(row: BusinessRun) -> int:
        cost_amount = BusinessRunService._first_number(row.cost_amount)
        currency = str(row.currency or "").strip().upper()
        if cost_amount is not None and cost_amount > 0:
            if currency == "USD":
                rate = max(1, int(getattr(get_settings(), "wallet_points_per_usd", 100) or 100))
                return max(1, int(math.ceil(cost_amount * rate)))
            return max(1, int(math.ceil(cost_amount)))
        quota_units = BusinessRunService._first_int(row.quota_units)
        if quota_units is not None and quota_units > 0:
            return max(1, int(quota_units))
        raise HTTPException(status_code=409, detail="BUSINESS_RUN_UNPRICED")

    @staticmethod
    def _billing_no_charge_policy_filter():
        return or_(
            BusinessRun.source.in_(sorted(INTERNAL_NO_CHARGE_SOURCES)),
            BusinessRun.tenant_id.in_(sorted(INTERNAL_NO_CHARGE_TENANTS)),
            BusinessRun.client_id.in_(sorted(INTERNAL_NO_CHARGE_CLIENTS)),
        )

    @staticmethod
    def _billing_not_no_charge_policy_filter():
        return and_(
            or_(BusinessRun.source.is_(None), not_(BusinessRun.source.in_(sorted(INTERNAL_NO_CHARGE_SOURCES)))),
            or_(BusinessRun.tenant_id.is_(None), not_(BusinessRun.tenant_id.in_(sorted(INTERNAL_NO_CHARGE_TENANTS)))),
            or_(BusinessRun.client_id.is_(None), not_(BusinessRun.client_id.in_(sorted(INTERNAL_NO_CHARGE_CLIENTS)))),
        )

    @staticmethod
    def _billing_status_filter(billing_status: str):
        normalized = str(billing_status or "").strip()
        policy_filter = BusinessRunService._billing_no_charge_policy_filter()
        not_policy_filter = BusinessRunService._billing_not_no_charge_policy_filter()
        if normalized == "billable":
            return and_(
                BusinessRun.status == "succeeded",
                or_(
                    BusinessRun.cost_amount > 0,
                    BusinessRun.quota_units > 0,
                ),
                not_policy_filter,
            )
        if normalized == "unpriced":
            return and_(
                BusinessRun.status == "succeeded",
                or_(
                    BusinessRun.cost_amount.is_(None),
                    BusinessRun.cost_amount <= 0,
                ),
                or_(
                    BusinessRun.quota_units.is_(None),
                    BusinessRun.quota_units <= 0,
                ),
                not_policy_filter,
            )
        if normalized == "no_charge":
            return or_(
                BusinessRun.status.in_(["failed", "cancelled", "timeout"]),
                and_(BusinessRun.status == "succeeded", policy_filter),
            )
        if normalized == "billing_pending":
            return BusinessRun.status.in_(["queued", "running", "pending", "planned"])
        return None

    @staticmethod
    def _first_number(*values: Any) -> float | None:
        for value in values:
            if value in (None, ""):
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _first_int(*values: Any) -> int | None:
        for value in values:
            if value in (None, ""):
                continue
            try:
                return int(float(value))
            except (TypeError, ValueError):
                continue
        return None

    def _select_capability(
        self,
        session,
        *,
        business_key: str,
        version: str | None,
        payload: BusinessRunCreateRequest | None = None,
        user: User | None = None,
        image_url: str | None = None,
    ) -> tuple[BusinessCapability, dict[str, Any]]:
        stmt = select(BusinessCapability).where(
            BusinessCapability.business_key == business_key,
            BusinessCapability.status == "active",
        )
        if version:
            row = session.execute(stmt.where(BusinessCapability.version == version)).scalars().first()
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
            return row, self._route_info(row, selected_by="explicit")

        rows = (
            session.execute(
                stmt.order_by(
                    BusinessCapability.is_default.desc(),
                    BusinessCapability.release_time.desc(),
                    BusinessCapability.created_at.desc(),
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
        default = next((row for row in rows if row.is_default), rows[0])
        route_key = self._resolve_route_key(payload=payload, user=user, image_url=image_url)
        for row in rows:
            if row.id == default.id:
                continue
            decision = self._rollout_decision(row=row, business_key=business_key, route_key=route_key)
            if decision.get("matched"):
                return row, self._route_info(row, route_key=route_key, **decision)
        return default, self._route_info(default, selected_by="default", route_key=route_key)

    def _rollout_decision(self, *, row: BusinessCapability, business_key: str, route_key: str | None) -> dict[str, Any]:
        rollout = self._extract_rollout_config(row)
        if not rollout:
            return {"matched": False}
        enabled = bool(rollout.get("enabled"))
        if not enabled:
            return {"matched": False}
        if not route_key:
            return {"matched": False, "selected_by": "rollout_no_key"}
        blocklist = set(self._string_list(rollout.get("blocklist") or rollout.get("excludeKeys") or rollout.get("exclude_keys")))
        if route_key in blocklist:
            return {"matched": False, "selected_by": "rollout_blocklist"}
        allowlist = set(
            self._string_list(
                rollout.get("allowlist")
                or rollout.get("includeKeys")
                or rollout.get("include_keys")
                or rollout.get("whitelist")
            )
        )
        if route_key in allowlist:
            return {
                "matched": True,
                "selected_by": "rollout_allowlist",
                "rollout_percent": self._safe_percent(rollout.get("percent")),
            }
        percent = self._safe_percent(rollout.get("percent"))
        if percent <= 0:
            return {"matched": False, "selected_by": "rollout_zero_percent", "rollout_percent": percent}
        bucket = self._rollout_bucket(
            business_key=business_key,
            capability_id=row.id,
            route_key=route_key,
            salt=str(rollout.get("salt") or ""),
        )
        if bucket < percent:
            return {
                "matched": True,
                "selected_by": "rollout_percent",
                "rollout_percent": percent,
                "rollout_bucket": bucket,
            }
        return {
            "matched": False,
            "selected_by": "rollout_percent_miss",
            "rollout_percent": percent,
            "rollout_bucket": bucket,
        }

    @staticmethod
    def _extract_rollout_config(row: BusinessCapability) -> dict[str, Any]:
        for source in (row.extra_metadata, row.recipe):
            if not isinstance(source, dict):
                continue
            rollout = source.get("rollout")
            if isinstance(rollout, dict):
                return rollout
        return {}

    @staticmethod
    def _resolve_route_key(
        *,
        payload: BusinessRunCreateRequest | None,
        user: User | None,
        image_url: str | None,
    ) -> str | None:
        metadata = payload.metadata if payload and isinstance(payload.metadata, dict) else {}
        inputs = payload.inputs if payload and isinstance(payload.inputs, dict) else {}
        for source in (metadata, inputs):
            for key in ("grayKey", "gray_key", "routeKey", "route_key", "tenantId", "tenant_id", "userId", "user_id", "traceId", "trace_id"):
                value = source.get(key)
                if isinstance(value, (str, int, float)) and str(value).strip():
                    return str(value).strip()
        if payload:
            for value in (payload.tenantId, payload.clientId, payload.traceId, payload.requestId):
                if isinstance(value, (str, int, float)) and str(value).strip():
                    return str(value).strip()
        user_id = BusinessRunService._safe_user_id(user)
        if user_id:
            return user_id
        if image_url and image_url.strip():
            return image_url.strip()
        return None

    @staticmethod
    def _rollout_bucket(*, business_key: str, capability_id: str, route_key: str, salt: str) -> float:
        raw = f"{business_key}:{capability_id}:{salt}:{route_key}".encode("utf-8")
        value = int(hashlib.sha256(raw).hexdigest()[:8], 16)
        return round((value / 0xFFFFFFFF) * 100, 4)

    @staticmethod
    def _route_key_hash(route_key: str | None) -> str | None:
        if not route_key:
            return None
        return hashlib.sha256(route_key.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _safe_percent(value: Any) -> float:
        try:
            percent = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(100.0, percent))

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if isinstance(item, (str, int, float)) and str(item).strip()]

    @staticmethod
    def _append_release_event(
        metadata: dict[str, Any] | None,
        *,
        action: str,
        note: str | None,
        actor: User | None,
        previous_default: BusinessCapability | None = None,
    ) -> dict[str, Any]:
        next_metadata = dict(metadata or {})
        raw_events = next_metadata.get("releaseEvents")
        events = list(raw_events) if isinstance(raw_events, list) else []
        actor_name = getattr(actor, "username", None) or getattr(actor, "email", None) or getattr(actor, "id", None)
        event = {
            "action": action,
            "note": str(note or "").strip() or None,
            "actor": str(actor_name) if actor_name else None,
            "at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        if previous_default:
            event.update(
                {
                    "previousDefaultCapabilityId": previous_default.id,
                    "previousDefaultVersion": previous_default.version,
                    "previousDefaultDisplayName": previous_default.display_name,
                }
            )
        events.append(event)
        next_metadata["releaseEvents"] = events[-20:]
        return next_metadata

    def _resolve_rollback_target(
        self,
        *,
        session,
        business_key: str,
        current_default: BusinessCapability | None,
        target_capability_id: str | None,
    ) -> BusinessCapability | None:
        explicit_target_id = str(target_capability_id or "").strip()
        if explicit_target_id:
            target = session.get(BusinessCapability, explicit_target_id)
            if target and target.business_key == business_key:
                return target
            return None

        if current_default and isinstance(current_default.extra_metadata, dict):
            raw_events = current_default.extra_metadata.get("releaseEvents")
            if isinstance(raw_events, list):
                for event in reversed(raw_events):
                    if not isinstance(event, dict):
                        continue
                    previous_id = str(event.get("previousDefaultCapabilityId") or "").strip()
                    if not previous_id or previous_id == current_default.id:
                        continue
                    previous = session.get(BusinessCapability, previous_id)
                    if previous and previous.business_key == business_key:
                        return previous

        return (
            session.execute(
                select(BusinessCapability)
                .where(
                    BusinessCapability.business_key == business_key,
                    BusinessCapability.status == "active",
                    BusinessCapability.is_default.is_(False),
                )
                .order_by(
                    BusinessCapability.release_time.desc(),
                    BusinessCapability.updated_at.desc(),
                    BusinessCapability.created_at.desc(),
                )
            )
            .scalars()
            .first()
        )

    def _route_info(
        self,
        row: BusinessCapability,
        *,
        selected_by: str,
        route_key: str | None = None,
        rollout_percent: float | None = None,
        rollout_bucket: float | None = None,
        matched: bool | None = None,
    ) -> dict[str, Any]:
        _ = matched
        info: dict[str, Any] = {
            "businessVersionId": row.id,
            "version": row.version,
            "selectedBy": selected_by,
            "routeKeyHash": self._route_key_hash(route_key),
        }
        if rollout_percent is not None:
            info["rolloutPercent"] = rollout_percent
        if rollout_bucket is not None:
            info["rolloutBucket"] = rollout_bucket
        return info

    @staticmethod
    def _build_recipe(*, base_recipe: dict[str, Any] | None, primary_ability_id: str | None) -> dict[str, Any]:
        recipe = dict(base_recipe or {})
        normalized_primary = str(primary_ability_id or "").strip()
        raw_steps = recipe.get("steps")
        steps = [dict(step) if isinstance(step, dict) else step for step in raw_steps] if isinstance(raw_steps, list) else raw_steps
        if normalized_primary:
            recipe["primaryAbilityId"] = normalized_primary
            if not isinstance(steps, list):
                recipe["steps"] = [
                    {
                        "id": "primary",
                        "type": "ability_task",
                        "role": "primary",
                        "abilityId": normalized_primary,
                    }
                ]
            else:
                target_index: int | None = None
                for index, step in enumerate(steps):
                    if not isinstance(step, dict):
                        continue
                    step_id = str(step.get("id") or "").strip()
                    role = str(step.get("role") or "").strip()
                    if step_id == "primary" or role == "primary":
                        target_index = index
                        break
                if target_index is None:
                    for index, step in enumerate(steps):
                        if not isinstance(step, dict):
                            continue
                        step_type = str(step.get("type") or "ability_task").strip()
                        if step_type in {"ability_task", "comfyui_workflow", "vendor_api"}:
                            target_index = index
                            break
                primary_step = {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "abilityId": normalized_primary,
                }
                if target_index is None:
                    steps.append(primary_step)
                else:
                    existing = steps[target_index]
                    if isinstance(existing, dict):
                        steps[target_index] = {
                            **existing,
                            "id": existing.get("id") or "primary",
                            "type": existing.get("type") or "ability_task",
                            "role": existing.get("role") or "primary",
                            "abilityId": normalized_primary,
                        }
                recipe["steps"] = steps
        elif isinstance(steps, list):
            recipe["steps"] = steps
        if "mode" not in recipe:
            recipe["mode"] = "single_ability_task"
        return recipe

    def _validate_recipe(self, *, session, recipe: dict[str, Any]) -> None:
        primary_ability_id = self._extract_primary_ability_id(recipe)
        ability_ids = [primary_ability_id]
        raw_steps = recipe.get("steps")
        if raw_steps is not None and not isinstance(raw_steps, list):
            raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
        for raw_step in raw_steps or []:
            if not isinstance(raw_step, dict):
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
            if raw_step.get("enabled") is False:
                continue
            step_type = str(raw_step.get("type") or "ability_task").strip()
            if not step_type:
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
            ability_id = self._extract_step_ability_id(raw_step)
            if step_type in RECIPE_EXECUTABLE_STEP_TYPES or ability_id:
                if not ability_id:
                    raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
                ability_ids.append(ability_id)
            elif step_type not in RECIPE_PASSIVE_STEP_TYPES:
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
        vl_assist = recipe.get("vlAssist") or recipe.get("vl_assist")
        if vl_assist is not None and not isinstance(vl_assist, dict):
            raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
        if isinstance(vl_assist, dict) and vl_assist.get("enabled"):
            vl_ability_id = self._first_string(vl_assist.get("abilityId"), vl_assist.get("ability_id"), "vl_analyze_image")
            if not vl_ability_id:
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")
            ability_ids.append(vl_ability_id)
        for ability_id in dict.fromkeys(ability_ids):
            ability = session.get(Ability, ability_id)
            if not ability:
                raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE")
        vendor_model_id = self._extract_recipe_vendor_model_id(recipe)
        if vendor_model_id is not None and not session.get(VendorModelCatalog, vendor_model_id):
            raise HTTPException(status_code=400, detail="VENDOR_MODEL_NOT_FOUND")

    @staticmethod
    def _extract_recipe_vendor_model_id(recipe: dict[str, Any]) -> int | None:
        raw = recipe.get("vendorModelId") or recipe.get("vendor_model_id")
        if raw in (None, ""):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="VENDOR_MODEL_NOT_FOUND")

    @staticmethod
    def _normalize_status(value: str | None) -> str:
        status = str(value or "inactive").strip().lower()
        allowed = {"active", "inactive", "draft", "disabled", "deprecated"}
        if status not in allowed:
            raise HTTPException(status_code=400, detail="BUSINESS_STATUS_INVALID")
        return status

    @staticmethod
    def _normalize_client_status(value: str | None) -> str:
        status = str(value or "active").strip().lower()
        allowed = {"active", "inactive", "disabled"}
        if status not in allowed:
            raise HTTPException(status_code=400, detail="BUSINESS_CLIENT_STATUS_INVALID")
        return status

    @staticmethod
    def _normalize_business_key_list(value: Any) -> list[str]:
        if value is None:
            return []
        items = BusinessRunService._string_list(value)
        seen: set[str] = set()
        normalized: list[str] = []
        for item in items:
            key = item.strip()
            if key and key not in seen:
                seen.add(key)
                normalized.append(key)
        return normalized

    @staticmethod
    def _validate_default_status(*, is_default: bool, status: str) -> None:
        if is_default and status != "active":
            raise HTTPException(status_code=400, detail="BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE")

    @staticmethod
    def _normalize_acceptance_status(value: str | None) -> str:
        normalized = str(value or "passed").strip().lower()
        allowed = {"passed", "failed", "warning", "waived"}
        if normalized not in allowed:
            raise HTTPException(status_code=400, detail="BUSINESS_ACCEPTANCE_STATUS_INVALID")
        return normalized

    @staticmethod
    def _required_text(value: str | None, error_code: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail=error_code)
        return text

    @staticmethod
    def _extract_primary_ability_id(recipe: dict[str, Any]) -> str:
        candidate = recipe.get("primaryAbilityId")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        steps = recipe.get("steps")
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict) or step.get("enabled") is False:
                    continue
                role = str(step.get("role") or "").strip()
                step_id = str(step.get("id") or "").strip()
                if role == "primary" or step_id == "primary":
                    ability_id = BusinessRunService._extract_step_ability_id(step)
                    if ability_id:
                        return ability_id
            for step in steps:
                if not isinstance(step, dict) or step.get("enabled") is False:
                    continue
                step_type = str(step.get("type") or "ability_task").strip()
                if step_type in {"ability_task", "comfyui_workflow", "vendor_api"}:
                    ability_id = BusinessRunService._extract_step_ability_id(step)
                    if ability_id:
                        return ability_id
        raise HTTPException(status_code=400, detail="BUSINESS_RECIPE_INVALID")

    @staticmethod
    def _extract_step_ability_id(step: dict[str, Any]) -> str | None:
        for key in ("abilityId", "ability_id"):
            value = step.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _should_wait_for_vl(recipe: dict[str, Any]) -> bool:
        mode = str(recipe.get("mode") or "").strip().lower()
        vl_assist = recipe.get("vlAssist") or recipe.get("vl_assist")
        if not isinstance(vl_assist, dict) or not vl_assist.get("enabled"):
            return False
        if mode in {"vl_then_primary", "vl-first", "vl_first", "preprocess_then_primary"}:
            return True
        for key in (
            "waitForResult",
            "wait_for_result",
            "blocking",
            "blockPrimary",
            "block_primary",
            "applyToPrimary",
            "apply_to_primary",
        ):
            if key in vl_assist and vl_assist.get(key) is not False:
                return bool(vl_assist.get(key))
        return False

    def _should_apply_vl_to_primary(self, recipe: dict[str, Any]) -> bool:
        vl_assist = recipe.get("vlAssist") or recipe.get("vl_assist")
        if not isinstance(vl_assist, dict) or not vl_assist.get("enabled"):
            return False
        for key in ("applyToPrimary", "apply_to_primary", "useResultForPrimary", "use_result_for_primary"):
            if key in vl_assist:
                return vl_assist.get(key) is not False
        return self._should_wait_for_vl(recipe)

    def _apply_vl_summary_to_inputs(
        self,
        *,
        capability_key: str,
        inputs: dict[str, Any],
        pass_keys: set[str],
        recipe: dict[str, Any],
        vl_summary: dict[str, Any],
    ) -> None:
        vl_assist = recipe.get("vlAssist") or recipe.get("vl_assist")
        apply_config = {}
        if isinstance(vl_assist, dict):
            raw_apply_config = vl_assist.get("applyToPrimary") or vl_assist.get("apply_to_primary")
            if isinstance(raw_apply_config, dict):
                apply_config = raw_apply_config
        overwrite = bool(apply_config.get("overwrite") or (isinstance(vl_assist, dict) and vl_assist.get("overwritePrimary")))

        def first_text(*keys: str) -> str | None:
            for key in keys:
                value = vl_summary.get(key)
                if isinstance(value, (str, int, float)) and str(value).strip():
                    return str(value).strip()
            return None

        def assign(field: str, value: str | None) -> None:
            if field not in pass_keys or not value:
                return
            if overwrite or not inputs.get(field):
                inputs[field] = value

        if capability_key == "fission":
            compiler = self._first_string(
                apply_config.get("compiler"),
                apply_config.get("promptCompiler"),
                (recipe.get("promptCompiler") or {}).get("id") if isinstance(recipe.get("promptCompiler"), dict) else None,
            )
            if compiler in {PATTERN_FISSION_TEMPLATE_ID, "pattern_fission_v21", "gpt_image2_pattern_fission_v21"}:
                compiled = compile_pattern_fission_prompt(vl_summary=vl_summary, user_inputs=inputs)
                compiled_inputs = {
                    "prompt": compiled.compiled_prompt,
                    "model": compiled.openai_params.get("model"),
                    "quality": compiled.openai_params.get("quality"),
                    "size": compiled.openai_params.get("size"),
                    "output_format": compiled.openai_params.get("output_format"),
                    "n": compiled.openai_params.get("n"),
                    "background": compiled.openai_params.get("background"),
                    "prompt_template_id": compiled.template_id,
                    "route_id": compiled.route_id,
                    "pattern_type": compiled.pattern_type,
                    "vl_card": compiled.vl_card,
                    "pattern_fission_user_params": compiled.user_params,
                }
                for field, value in compiled_inputs.items():
                    if field in pass_keys and value not in (None, "", []):
                        if overwrite or not inputs.get(field):
                            inputs[field] = value
                return
            if compiler == "comfyui_fission_control_card_v1":
                card = vl_summary.get("fissionControlCard") if isinstance(vl_summary.get("fissionControlCard"), dict) else None
                if not card and isinstance(vl_summary.get("vlCard"), dict):
                    card = vl_summary.get("vlCard")
                if not isinstance(card, dict):
                    card = {}
                prompt_main = self._first_string(
                    card.get("prompt_main"),
                    card.get("promptMain"),
                    vl_summary.get("promptMain"),
                    vl_summary.get("positivePrompt"),
                )
                prompt_control = self._first_string(
                    card.get("prompt_control"),
                    card.get("promptControl"),
                    vl_summary.get("promptControl"),
                    vl_summary.get("imageDesc"),
                )
                profile_hint = self._first_string(
                    card.get("profile_hint"),
                    card.get("profileHint"),
                    vl_summary.get("profileHint"),
                    inputs.get("profile"),
                    inputs.get("profile_id"),
                )
                compiled_inputs = {
                    "prompt": prompt_main,
                    "image_desc": prompt_control,
                    "vl_result": card or vl_summary,
                    "profile": profile_hint or "pattern_default_v1",
                    "profile_id": profile_hint or "pattern_default_v1",
                    "bili_mapping": "variation_percent_045_080",
                }
                for field, value in compiled_inputs.items():
                    if field in pass_keys and value not in (None, "", []):
                        if overwrite or not inputs.get(field):
                            inputs[field] = value
                return
            assign("image_desc", first_text("imageDesc", "summary", "textPreview"))
            assign("prompt", first_text("positivePrompt"))
        elif capability_key == "outpaint":
            assign("prompt", first_text("positivePrompt", "imageDesc", "summary"))
        else:
            assign("prompt", first_text("positivePrompt", "summary"))

    def _build_ability_payload(
        self,
        *,
        capability_key: str,
        payload: BusinessRunCreateRequest,
        image_url: str,
        route_info: dict[str, Any] | None = None,
        trace_context: dict[str, Any] | None = None,
        recipe: dict[str, Any] | None = None,
        vl_summary: dict[str, Any] | None = None,
    ) -> AbilityInvokeRequest:
        inputs: dict[str, Any] = dict(payload.inputs or {})
        if capability_key == "fission":
            pass_keys = {
                "prompt",
                "bili",
                "width",
                "height",
                "batch_size",
                "seed",
                "steps",
                "cfg",
                "profile_id",
                "profile",
                "mode",
                "ipadapter_weight",
                "colormatch_method",
                "colormatch_strength",
                "image_desc",
                "vl_result",
                "bili_mapping",
                "prompt_main",
                "prompt_control",
                "variation_strength",
                "quality",
                "count",
                "preserve_layout",
                "preserve_border",
                "preserve_count_density",
                "style_shift",
                "size",
                "output_format",
                "output_compression",
                "input_fidelity",
                "background",
                "n",
                "model",
                "mask_url",
                "maskUrl",
                "image_url",
                "imageUrl",
                "image_urls",
                "imageUrls",
                "input_urls",
                "prompt_template_id",
                "route_id",
                "pattern_type",
                "vl_card",
                "pattern_fission_user_params",
            }
        elif capability_key == "pattern_extract":
            pass_keys = {
                "prompt",
                "negative_prompt",
                "width",
                "height",
                "batch",
                "batch_size",
                "lora",
                "seed",
                "timeout",
            }
        elif capability_key == "outpaint":
            pass_keys = {
                "prompt",
                "expand_left",
                "expand_right",
                "expand_top",
                "expand_bottom",
                "width",
                "height",
                "seed",
                "timeout",
            }
        else:
            pass_keys = set(inputs)
        flat_payload = payload.model_dump(exclude_none=True, by_alias=True)
        for key in pass_keys:
            if key not in inputs and key in flat_payload:
                inputs[key] = flat_payload[key]
        if capability_key == "pattern_extract" and "batch" not in inputs and "batch_size" in inputs:
            inputs["batch"] = inputs.pop("batch_size")
        if payload.prompt and "prompt" not in inputs:
            inputs["prompt"] = payload.prompt
        if vl_summary and self._should_apply_vl_to_primary(recipe or {}):
            self._apply_vl_summary_to_inputs(
                capability_key=capability_key,
                inputs=inputs,
                pass_keys=pass_keys,
                recipe=recipe or {},
                vl_summary=vl_summary,
            )
        ability_inputs = {key: value for key, value in inputs.items() if key in pass_keys and value not in (None, "", [])}
        return AbilityInvokeRequest(
            inputs=ability_inputs,
            imageUrl=image_url,
            metadata={
                **(payload.metadata or {}),
                "businessKey": capability_key,
                "businessVersion": (route_info or {}).get("version"),
                "businessRoute": route_info or {},
                "businessTrace": trace_context or {},
                "traceId": (trace_context or {}).get("traceId"),
                "requestId": (trace_context or {}).get("requestId"),
                "tenantId": (trace_context or {}).get("tenantId"),
                "clientId": (trace_context or {}).get("clientId"),
                "channel": (trace_context or {}).get("channel"),
                "source": (trace_context or {}).get("source"),
            },
        )

    def _build_step_ability_payload(
        self,
        *,
        step: dict[str, Any],
        business_key: str,
        payload: BusinessRunCreateRequest,
        image_url: str,
        route_info: dict[str, Any],
        run_id: str,
        trace_context: dict[str, Any],
    ) -> AbilityInvokeRequest:
        step_config = step.get("config") if isinstance(step.get("config"), dict) else {}
        step_inputs = self._extract_step_inputs(step_config)
        request_inputs = payload.inputs if isinstance(payload.inputs, dict) else {}
        step_type = str(step.get("step_type") or step_config.get("type") or "").strip().lower()
        inputs: dict[str, Any] = dict(step_inputs)
        if step_type in {"vl_analyze", "vl_analyze_image"}:
            prompt = self._first_string(
                request_inputs.get("vl_prompt"),
                request_inputs.get("analysis_prompt"),
                request_inputs.get("analysisPrompt"),
                step_inputs.get("prompt"),
            )
            if not prompt and step_config.get("useBusinessPrompt") is True:
                prompt = payload.prompt
            provider = self._first_string(
                request_inputs.get("vl_provider"),
                request_inputs.get("vlProvider"),
                step_inputs.get("provider"),
            )
            coze_workflow_id = self._first_string(
                request_inputs.get("coze_vl_workflow_id"),
                request_inputs.get("cozeWorkflowId"),
                request_inputs.get("coze_workflow_id"),
                step_inputs.get("coze_workflow_id"),
                step_inputs.get("cozeWorkflowId"),
            )
            inputs = {"image_url": image_url, **inputs}
            if prompt:
                inputs["prompt"] = prompt
            if provider:
                inputs["provider"] = provider
            if coze_workflow_id:
                inputs["coze_workflow_id"] = coze_workflow_id
        else:
            inputs.setdefault("image_url", image_url)
        metadata = {
            **(payload.metadata or {}),
            "businessKey": business_key,
            "businessVersion": route_info.get("version"),
            "businessRoute": route_info,
            "businessRunId": run_id,
            "businessStepId": step.get("step_id"),
            "businessStepRole": step.get("role"),
            "businessStepType": step_type,
            "businessTrace": trace_context,
            "traceId": trace_context.get("traceId"),
            "requestId": trace_context.get("requestId"),
            "tenantId": trace_context.get("tenantId"),
            "clientId": trace_context.get("clientId"),
            "channel": trace_context.get("channel"),
            "source": trace_context.get("source"),
        }
        return AbilityInvokeRequest(
            inputs={key: value for key, value in inputs.items() if value not in (None, "", [])},
            imageUrl=image_url,
            metadata=metadata,
        )

    @staticmethod
    def _extract_step_inputs(step_config: dict[str, Any]) -> dict[str, Any]:
        inputs: dict[str, Any] = {}
        nested_config = step_config.get("config")
        if isinstance(nested_config, dict):
            for key in ("defaultInputs", "default_inputs", "inputs", "params"):
                value = nested_config.get(key)
                if isinstance(value, dict):
                    inputs.update(value)
        for key in ("defaultInputs", "default_inputs", "inputs", "params"):
            value = step_config.get(key)
            if isinstance(value, dict):
                inputs.update(value)
        return inputs

    @staticmethod
    def _extract_error_message(exc: Exception) -> str:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict):
            for key in ("message", "detail", "error", "code"):
                value = detail.get(key)
                if isinstance(value, (str, int, float)) and str(value).strip():
                    return str(value).strip()
            return str(detail)[:500]
        if isinstance(detail, (str, int, float)) and str(detail).strip():
            return str(detail).strip()
        return str(exc)[:500]

    @staticmethod
    def _extract_urls(payload: dict[str, Any] | None, *, keys: tuple[str, ...]) -> list[str]:
        if not isinstance(payload, dict):
            return []
        urls: list[str] = []

        def add(value: Any) -> None:
            if isinstance(value, str) and value.strip().startswith(("http://", "https://")):
                urls.append(value.strip())
            elif isinstance(value, dict):
                for key in ("storedUrl", "stored_url", "ossUrl", "url", "sourceUrl"):
                    candidate = value.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        urls.append(candidate.strip())
                        break
            elif isinstance(value, list):
                for item in value:
                    add(item)

        for key in keys:
            add(payload.get(key))
        seen: set[str] = set()
        out: list[str] = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            out.append(url)
        return out

    @staticmethod
    def _classify_output_url(url: str) -> str:
        value = str(url or "").split("?", 1)[0].split("#", 1)[0].lower()
        if value.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg")):
            return "image"
        if value.endswith((".mp4", ".mov", ".webm", ".m4v", ".avi", ".mkv")):
            return "video"
        return "resource"

    @classmethod
    def _count_resource_outputs(cls, payload: dict[str, Any] | None) -> int:
        if not isinstance(payload, dict):
            return 0
        urls: list[str] = []
        urls.extend(cls._extract_urls(payload, keys=("resourceUrls", "resource_urls", "resources", "files", "attachments")))
        assets = payload.get("assets")
        if isinstance(assets, list):
            for asset in assets:
                if not isinstance(asset, dict):
                    continue
                asset_type = str(asset.get("type") or asset.get("kind") or asset.get("mediaType") or asset.get("media_type") or "").lower()
                asset_url = cls._extract_urls({"asset": asset}, keys=("asset",))
                if asset_type and asset_type not in {"image", "video"}:
                    urls.extend(asset_url)
                elif asset_url and cls._classify_output_url(asset_url[0]) == "resource":
                    urls.extend(asset_url)
        return len(set(urls))

    @staticmethod
    def _normalized_recipe_steps(recipe: dict[str, Any]) -> list[dict[str, Any]]:
        raw_steps = recipe.get("steps")
        normalized: list[dict[str, Any]] = []
        if isinstance(raw_steps, list):
            for index, raw_step in enumerate(raw_steps):
                if not isinstance(raw_step, dict):
                    continue
                ability_id = BusinessRunService._extract_step_ability_id(raw_step)
                step_type = str(raw_step.get("type") or "ability_task").strip() or "ability_task"
                step: dict[str, Any] = {
                    "id": BusinessRunService._first_string(raw_step.get("id")) or f"step_{index + 1}",
                    "type": step_type,
                    "enabled": raw_step.get("enabled") is not False,
                }
                role = BusinessRunService._first_string(raw_step.get("role"))
                name = BusinessRunService._first_string(raw_step.get("displayName"), raw_step.get("name"), raw_step.get("title"))
                if role:
                    step["role"] = role
                if name:
                    step["displayName"] = name
                if ability_id:
                    step["abilityId"] = ability_id
                for config_key in ("config", "defaultInputs", "default_inputs", "inputs", "params", "useBusinessPrompt"):
                    config_value = raw_step.get(config_key)
                    if isinstance(config_value, dict):
                        step[config_key] = dict(config_value)
                    elif config_value is not None and config_key == "useBusinessPrompt":
                        step[config_key] = config_value
                normalized.append(step)

        vl_assist = recipe.get("vlAssist") or recipe.get("vl_assist")
        if isinstance(vl_assist, dict) and vl_assist.get("enabled"):
            vl_ability_id = BusinessRunService._first_string(
                vl_assist.get("abilityId"),
                vl_assist.get("ability_id"),
                "vl_analyze_image",
            )
            has_vl_step = any(
                step.get("type") in {"vl_analyze", "vl_analyze_image"} or step.get("abilityId") == vl_ability_id
                for step in normalized
            )
            if vl_ability_id and not has_vl_step:
                normalized.insert(
                    0,
                    {
                        "id": "vl_analyze",
                        "type": "vl_analyze",
                        "role": "preprocess",
                        "displayName": "VL 图像理解",
                        "abilityId": vl_ability_id,
                        "enabled": True,
                    },
                )

        try:
            primary_ability_id = BusinessRunService._extract_primary_ability_id(recipe)
        except HTTPException:
            primary_ability_id = None
        if primary_ability_id:
            has_primary = False
            for step in normalized:
                if step.get("abilityId") == primary_ability_id and step.get("enabled") is not False:
                    has_primary = True
                    step.setdefault("role", "primary")
            if not has_primary:
                normalized.append(
                    {
                        "id": "primary",
                        "type": "ability_task",
                        "role": "primary",
                        "displayName": "主执行能力",
                        "abilityId": primary_ability_id,
                        "enabled": True,
                    }
                )
        return normalized

    def _recipe_steps_to_dict(self, recipe: dict[str, Any], *, session=None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for order, step in enumerate(self._normalized_recipe_steps(recipe), start=1):
            ability_id = step.get("abilityId")
            ability = session.get(Ability, ability_id) if session is not None and isinstance(ability_id, str) else None
            item = {
                "order": order,
                "id": step.get("id"),
                "type": step.get("type"),
                "role": step.get("role"),
                "displayName": step.get("displayName"),
                "enabled": step.get("enabled") is not False,
                "abilityId": ability_id,
                "abilityName": ability.display_name if ability else None,
                "abilityProvider": ability.provider if ability else None,
            }
            rows.append({key: value for key, value in item.items() if value is not None})
        return rows

    @staticmethod
    def _first_string(*values: Any) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _safe_user_id(user: User | None) -> str | None:
        if not user:
            return None
        user_id = str(getattr(user, "id", "") or "").strip()
        return None if user_id == "service" else user_id or None

    @staticmethod
    def _is_privileged_business_user(user: User | None) -> bool:
        if not user:
            return False
        if str(getattr(user, "id", "") or "").strip() == "service":
            return True
        return str(getattr(user, "role", "") or "").strip() == "admin"

    def _can_user_access_run(self, row: BusinessRun, user: User | None) -> bool:
        if user is None or self._is_privileged_business_user(user):
            return True
        uid = self._safe_user_id(user)
        if row.user_id and uid and row.user_id == uid:
            return True
        user_tenant_id = self._short_text(getattr(user, "tenant_id", None), 64)
        user_client_id = self._short_text(getattr(user, "client_id", None), 64)
        if user_tenant_id and row.tenant_id == user_tenant_id:
            if user_client_id and row.client_id and row.client_id != user_client_id:
                return False
            return True
        if row.user_id and uid and row.user_id != uid:
            return False
        return not row.user_id and not row.tenant_id

    @staticmethod
    def _actor_username(user: User | None) -> str | None:
        if not user:
            return None
        value = getattr(user, "username", None) or getattr(user, "email", None) or getattr(user, "id", None)
        return str(value).strip() if value else None

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _normalize_bulk_run_ids(run_ids: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for item in run_ids or []:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        if not normalized:
            raise HTTPException(status_code=400, detail="BUSINESS_RUN_IDS_REQUIRED")
        if len(normalized) > 100:
            raise HTTPException(status_code=400, detail="BUSINESS_RUN_BULK_LIMIT_EXCEEDED")
        return normalized

    @staticmethod
    def _bulk_action_response(*, action: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        succeeded = sum(1 for item in items if item.get("ok"))
        failed = len(items) - succeeded
        return {
            "action": action,
            "total": len(items),
            "succeeded": succeeded,
            "failed": failed,
            "items": items,
        }

    @staticmethod
    def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            value = str(item.get(key) or "-").strip() or "-"
            counts[value] = counts.get(value, 0) + 1
        return counts

    @staticmethod
    def _json_safe_payload(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {str(key): BusinessRunService._json_safe_payload(item) for key, item in value.items()}
        if isinstance(value, list):
            return [BusinessRunService._json_safe_payload(item) for item in value]
        return value

    def _record_business_operation(
        self,
        *,
        session,
        action: str,
        target_type: str,
        target_id: str | None = None,
        business_key: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        actor: User | None = None,
        note: str | None = None,
        before_payload: dict[str, Any] | None = None,
        after_payload: dict[str, Any] | None = None,
    ) -> None:
        session.add(
            BusinessOperationLog(
                id=f"bizop_{uuid4().hex}",
                action=action,
                target_type=target_type,
                target_id=target_id,
                business_key=business_key,
                tenant_id=tenant_id,
                client_id=client_id,
                actor_user_id=self._safe_user_id(actor),
                actor_username=self._actor_username(actor),
                actor_role=str(getattr(actor, "role", "") or "").strip() or None if actor else None,
                note=self._clean_optional_text(note),
                before_payload=before_payload,
                after_payload=after_payload,
            )
        )

    def _default_approval_to_dict(self, row: BusinessDefaultApproval, *, session=None) -> dict[str, Any]:
        source = session.get(BusinessCapability, row.source_capability_id) if session is not None and row.source_capability_id else None
        target = session.get(BusinessCapability, row.target_capability_id) if session is not None and row.target_capability_id else None
        return {
            "id": row.id,
            "business_key": row.business_key,
            "source_capability_id": row.source_capability_id,
            "target_capability_id": row.target_capability_id,
            "status": row.status,
            "requester_user_id": row.requester_user_id,
            "requester_username": row.requester_username,
            "approver_user_id": row.approver_user_id,
            "approver_username": row.approver_username,
            "request_note": row.request_note,
            "decision_note": row.decision_note,
            "before_payload": row.before_payload,
            "after_payload": row.after_payload,
            "source_capability": self._capability_to_dict(source, session=session) if source else None,
            "target_capability": self._capability_to_dict(target, session=session) if target else None,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "decided_at": row.decided_at,
            "applied_at": row.applied_at,
        }

    @staticmethod
    def _operation_log_to_dict(row: BusinessOperationLog) -> dict[str, Any]:
        return {
            "id": row.id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "business_key": row.business_key,
            "tenant_id": row.tenant_id,
            "client_id": row.client_id,
            "actor_user_id": row.actor_user_id,
            "actor_username": row.actor_username,
            "actor_role": row.actor_role,
            "note": row.note,
            "before_payload": row.before_payload,
            "after_payload": row.after_payload,
            "created_at": row.created_at,
        }

    def _business_client_to_dict(self, row: BusinessClient) -> dict[str, Any]:
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "client_id": row.client_id,
            "display_name": row.display_name,
            "status": row.status,
            "allowed_business_keys": self._normalize_business_key_list(row.allowed_business_keys),
            "daily_run_limit": row.daily_run_limit,
            "daily_quota_units": row.daily_quota_units,
            "concurrent_run_limit": row.concurrent_run_limit,
            "extra_metadata": row.extra_metadata,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _capability_to_dict(self, row: BusinessCapability, *, session=None) -> dict[str, Any]:
        recipe = row.recipe if isinstance(row.recipe, dict) else {}
        primary_ability_id: str | None = None
        primary_ability_name: str | None = None
        primary_ability_provider: str | None = None
        vendor_model_id: int | None = None
        vendor_model_name: str | None = None
        vendor_model_provider: str | None = None
        latest_run = self._latest_run_summary(row, session=session)
        run_metrics = self._run_metrics_summary(row, session=session)
        acceptance = self._acceptance_summary(row.extra_metadata)
        try:
            primary_ability_id = self._extract_primary_ability_id(recipe)
        except HTTPException:
            primary_ability_id = None
        ability = session.get(Ability, primary_ability_id) if session is not None and primary_ability_id else None
        if ability:
            primary_ability_name = ability.display_name
            primary_ability_provider = ability.provider
            try:
                vendor_model_id = self._extract_recipe_vendor_model_id(recipe) or ability.vendor_model_id
            except HTTPException:
                vendor_model_id = ability.vendor_model_id
        else:
            try:
                vendor_model_id = self._extract_recipe_vendor_model_id(recipe)
            except HTTPException:
                vendor_model_id = None
        vendor_model = session.get(VendorModelCatalog, vendor_model_id) if session is not None and vendor_model_id else None
        if vendor_model:
            vendor_model_name = vendor_model.display_name
            vendor_model_provider = vendor_model.provider
        governance = self._business_capability_governance(
            row,
            recipe=recipe,
            ability=ability,
            vendor_model=vendor_model,
            vendor_model_id=vendor_model_id,
            session=session,
        )
        release_gate = self._business_capability_release_gate(
            row,
            governance=governance,
            acceptance=acceptance["latest"],
            latest_run=latest_run,
            run_metrics=run_metrics,
            primary_ability_id=primary_ability_id,
        )
        return {
            "id": row.id,
            "business_key": row.business_key,
            "version": row.version,
            "display_name": row.display_name,
            "description": row.description,
            "status": row.status,
            "is_default": row.is_default,
            "release_time": row.release_time,
            "recipe": self._omit_large_fields(row.recipe),
            "input_schema": row.input_schema,
            "output_schema": row.output_schema,
            "extra_metadata": row.extra_metadata,
            "primary_ability_id": primary_ability_id,
            "primary_ability_name": primary_ability_name,
            "primary_ability_provider": primary_ability_provider,
            "vendor_model_id": vendor_model_id,
            "vendor_model_name": vendor_model_name,
            "vendor_model_provider": vendor_model_provider,
            "recipe_steps": self._recipe_steps_to_dict(recipe, session=session),
            "governance_status": governance["status"],
            "governance_issues": governance["issues"],
            "governance_suggestions": governance["suggestions"],
            "runtime_key_configured": governance["runtime_key_configured"],
            "model_cost_configured": governance["model_cost_configured"],
            "egress_verified": governance["egress_verified"],
            "latest_acceptance": acceptance["latest"],
            "acceptance_records": acceptance["records"],
            "release_gate": release_gate,
            "latest_run": latest_run,
            "run_metrics": run_metrics,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _acceptance_summary(metadata: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            return {"latest": None, "records": []}
        raw_records = metadata.get("acceptanceRecords")
        records = [item for item in raw_records if isinstance(item, dict)] if isinstance(raw_records, list) else []
        latest = metadata.get("latestAcceptance")
        if not isinstance(latest, dict):
            latest = records[0] if records else None
        return {"latest": latest, "records": records[:5]}

    @staticmethod
    def _acceptance_passed(acceptance: dict[str, Any] | None) -> bool:
        return isinstance(acceptance, dict) and str(acceptance.get("status") or "").strip().lower() == "passed"

    def _ensure_release_acceptance(self, row: BusinessCapability) -> None:
        acceptance = self._acceptance_summary(row.extra_metadata)["latest"]
        if not self._acceptance_passed(acceptance):
            raise HTTPException(status_code=409, detail="BUSINESS_ACCEPTANCE_REQUIRED")

    def _ensure_default_release_ready(self, row: BusinessCapability, session) -> None:
        self._ensure_release_acceptance(row)
        release_payload = self._capability_to_dict(row, session=session)
        release_gate = release_payload.get("release_gate") if isinstance(release_payload, dict) else None
        if not isinstance(release_gate, dict) or not release_gate.get("canRelease"):
            raise HTTPException(status_code=409, detail="BUSINESS_RELEASE_GATE_BLOCKED")

    def _business_capability_release_gate(
        self,
        row: BusinessCapability,
        *,
        governance: dict[str, Any],
        acceptance: dict[str, Any] | None,
        latest_run: dict[str, Any] | None,
        run_metrics: dict[str, Any] | None,
        primary_ability_id: str | None,
    ) -> dict[str, Any]:
        blockers: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []
        governance_status = str(governance.get("status") or "").strip().lower()

        if row.status != "active":
            blockers.append("BUSINESS_RELEASE_VERSION_INACTIVE")
            suggestions.append("先启用该业务版本，或切换到已启用版本。")
        if not primary_ability_id:
            blockers.append("BUSINESS_RELEASE_PRIMARY_ABILITY_REQUIRED")
            suggestions.append("先绑定真实主能力，避免业务入口只剩配置壳。")
        if governance_status == "blocker":
            blockers.append("BUSINESS_RELEASE_GOVERNANCE_BLOCKED")
            suggestions.append("先补齐底层能力、模型、执行节点或第三方密钥。")
        elif governance_status == "warning":
            warnings.append("BUSINESS_RELEASE_GOVERNANCE_WARNING")
            suggestions.append("上线前补齐成本、模型治理或其他非阻塞信息。")

        acceptance_ok = self._acceptance_passed(acceptance)
        if not acceptance_ok:
            blockers.append("BUSINESS_RELEASE_ACCEPTANCE_REQUIRED")
            suggestions.append("先跑测评端或业务真实链路，并记录人工验收通过。")

        if latest_run and latest_run.get("error"):
            warnings.append("BUSINESS_RELEASE_LATEST_RUN_FAILED")
            suggestions.append("最近一次运行失败，先排查失败原因再放量。")
        if run_metrics and (self._first_int(run_metrics.get("failed")) or 0) > 0:
            warnings.append("BUSINESS_RELEASE_RECENT_FAILURES")
            suggestions.append("近窗口有失败样本，先筛选业务调用记录定位问题。")

        status = "ready"
        label = "可上线"
        if blockers:
            status = "blocked"
            label = "暂不能上线"
        elif warnings:
            status = "warning"
            label = "可小流量，需复核"
        return {
            "status": status,
            "label": label,
            "canRelease": status == "ready",
            "canRequestDefault": not blockers and acceptance_ok,
            "acceptancePassed": acceptance_ok,
            "blockers": blockers,
            "warnings": warnings,
            "suggestions": suggestions,
        }

    def _business_capability_governance(
        self,
        row: BusinessCapability,
        *,
        recipe: dict[str, Any],
        ability: Ability | None,
        vendor_model: VendorModelCatalog | None,
        vendor_model_id: int | None,
        session=None,
    ) -> dict[str, Any]:
        issues: list[str] = []
        suggestions: list[str] = []
        status_scope = "blocker" if row.status == "active" or row.is_default else "warning"
        runtime_key_configured: bool | None = None
        model_cost_configured: bool | None = None
        egress_verified: bool | None = None

        try:
            primary_ability_id = self._extract_primary_ability_id(recipe)
        except HTTPException:
            primary_ability_id = None

        if not primary_ability_id:
            issues.append("BUSINESS_GOVERNANCE_PRIMARY_ABILITY_MISSING")
            suggestions.append("编辑业务版本，绑定真实主能力后再发布或设为默认。")
        elif not ability:
            issues.append("BUSINESS_GOVERNANCE_PRIMARY_ABILITY_NOT_FOUND")
            suggestions.append("主能力编号在能力目录中不存在，先修正配方或恢复能力。")
        elif ability.status != "active":
            issues.append("BUSINESS_GOVERNANCE_PRIMARY_ABILITY_INACTIVE")
            suggestions.append("主能力未启用，先在能力管理中启用或切换到可用能力。")

        executable_steps = [
            step
            for step in self._normalized_recipe_steps(recipe)
            if step.get("enabled") is not False and str(step.get("type") or "").strip() in RECIPE_EXECUTABLE_STEP_TYPES
        ]
        if not executable_steps:
            issues.append("BUSINESS_GOVERNANCE_EXECUTABLE_STEP_MISSING")
            suggestions.append("业务配方没有可执行步骤，当前只是配置壳，不能作为线上入口。")

        provider = str(
            (vendor_model.provider if vendor_model else None)
            or (ability.provider if ability else None)
            or ""
        ).strip().lower()

        if vendor_model_id and not vendor_model:
            issues.append("BUSINESS_GOVERNANCE_VENDOR_MODEL_NOT_FOUND")
            suggestions.append("业务版本引用的模型目录不存在，先修正模型绑定。")
        if vendor_model:
            model_cost_configured = self._has_vendor_model_cost_policy(vendor_model.cost_policy)
            vendor_acceptance = self._acceptance_summary(vendor_model.extra_metadata)["latest"]
            if vendor_model.status != "active":
                issues.append("BUSINESS_GOVERNANCE_VENDOR_MODEL_INACTIVE")
                suggestions.append("绑定的第三方模型未启用，先启用模型或切到其他模型。")
            if self._is_vendor_provider(provider) and not self._acceptance_passed(vendor_acceptance):
                issues.append("BUSINESS_GOVERNANCE_VENDOR_MODEL_ACCEPTANCE_REQUIRED")
                suggestions.append("第三方模型缺少验收通过记录，先在模型弹药库跑通并记录验收。")
            if self._is_vendor_provider(provider) and not model_cost_configured:
                issues.append("BUSINESS_GOVERNANCE_VENDOR_MODEL_COST_MISSING")
                suggestions.append("第三方模型缺少计价策略，正式收费前必须补成本口径。")

        if session is not None and self._is_vendor_provider(provider):
            runtime_key_configured = self._provider_runtime_key_configured(session, provider)
            if not runtime_key_configured:
                issues.append("BUSINESS_GOVERNANCE_VENDOR_KEY_MISSING")
                suggestions.append("该业务版本依赖第三方模型，但没有可用密钥；先到模型弹药库配置并验证 Key。")
            if vendor_model and self._vendor_model_requires_verified_egress(vendor_model):
                egress_verified = self._provider_recent_successful_key_check(session, provider)
                if not egress_verified:
                    issues.append("BUSINESS_GOVERNANCE_VENDOR_EGRESS_NOT_VERIFIED")
                    suggestions.append("该模型需要出网能力，先在模型弹药库做一次带密钥出网检查。")

        blocker_codes = {
            "BUSINESS_GOVERNANCE_PRIMARY_ABILITY_MISSING",
            "BUSINESS_GOVERNANCE_PRIMARY_ABILITY_NOT_FOUND",
            "BUSINESS_GOVERNANCE_PRIMARY_ABILITY_INACTIVE",
            "BUSINESS_GOVERNANCE_EXECUTABLE_STEP_MISSING",
            "BUSINESS_GOVERNANCE_VENDOR_MODEL_NOT_FOUND",
            "BUSINESS_GOVERNANCE_VENDOR_MODEL_INACTIVE",
            "BUSINESS_GOVERNANCE_VENDOR_MODEL_ACCEPTANCE_REQUIRED",
            "BUSINESS_GOVERNANCE_VENDOR_MODEL_COST_MISSING",
            "BUSINESS_GOVERNANCE_VENDOR_KEY_MISSING",
            "BUSINESS_GOVERNANCE_VENDOR_EGRESS_NOT_VERIFIED",
        }
        if not issues:
            governance_status = "ready"
        elif any(issue in blocker_codes for issue in issues):
            governance_status = status_scope
        else:
            governance_status = "warning"

        return {
            "status": governance_status,
            "issues": issues,
            "suggestions": suggestions,
            "runtime_key_configured": runtime_key_configured,
            "model_cost_configured": model_cost_configured,
            "egress_verified": egress_verified,
        }

    @staticmethod
    def _is_vendor_provider(provider: str | None) -> bool:
        return str(provider or "").strip().lower() in {"openai", "openai_compatible", "volcengine", "baidu", "kie"}

    @staticmethod
    def _has_vendor_model_cost_policy(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        for key in ("unitPrice", "unit_price", "discountPrice", "discount_price", "listPrice", "list_price", "price"):
            raw = value.get(key)
            if raw in (None, ""):
                continue
            try:
                if float(raw) > 0:
                    return True
            except (TypeError, ValueError):
                return False
        return False

    def _provider_runtime_key_configured(self, session, provider: str) -> bool:
        normalized = str(provider or "").strip().lower()
        if self._provider_env_key_configured(normalized):
            return True
        rows = session.execute(select(ApiKey).where(ApiKey.provider == normalized)).scalars().all()
        return any(is_usable(row) for row in rows)

    def _provider_recent_successful_key_check(self, session, provider: str) -> bool:
        normalized = str(provider or "").strip().lower()
        rows = session.execute(select(ApiKey).where(ApiKey.provider == normalized)).scalars().all()
        return any(is_usable(row) and self._key_recent_successful_check(row) for row in rows)

    @staticmethod
    def _key_recent_successful_check(api_key: ApiKey) -> bool:
        metadata = api_key.extra_metadata if isinstance(api_key.extra_metadata, dict) else {}
        last_check = metadata.get("lastCheck") if isinstance(metadata, dict) else None
        if not isinstance(last_check, dict) or last_check.get("success") is not True:
            return False
        checked_at = BusinessRunService._parse_key_checked_at(last_check.get("checkedAt"))
        if not checked_at:
            return False
        return checked_at >= datetime.utcnow() - timedelta(days=VENDOR_KEY_CHECK_STALE_DAYS)

    @staticmethod
    def _parse_key_checked_at(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    @staticmethod
    def _vendor_model_requires_verified_egress(vendor_model: VendorModelCatalog) -> bool:
        return bool(getattr(vendor_model, "requires_global_egress", False))

    @staticmethod
    def _provider_env_key_configured(provider: str) -> bool:
        settings = get_settings()
        if provider == "baidu":
            return bool(settings.baidu_api_key and settings.baidu_secret_key)
        if provider == "volcengine":
            return bool(settings.volcengine_api_key)
        return False

    @staticmethod
    def _latest_run_summary(row: BusinessCapability, *, session=None) -> dict[str, Any] | None:
        if session is None:
            return None
        latest = (
            session.execute(
                select(BusinessRun)
                .where(BusinessRun.business_version_id == row.id)
                .order_by(BusinessRun.created_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if not latest:
            return None
        return {
            "id": latest.id,
            "status": latest.status,
            "created_at": latest.created_at,
            "finished_at": latest.finished_at,
            "image_count": len(latest.image_urls or []),
            "video_count": len(latest.video_urls or []),
            "error": latest.error_message,
        }

    @staticmethod
    def _run_metrics_summary(row: BusinessCapability, *, session=None) -> dict[str, Any]:
        since = datetime.utcnow() - timedelta(hours=24)
        metrics = {
            "window_hours": 24,
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "running": 0,
            "queued": 0,
            "cancelled": 0,
            "success_rate": None,
        }
        if session is None:
            return metrics
        rows = (
            session.execute(
                select(BusinessRun.status, func.count(BusinessRun.id))
                .where(
                    BusinessRun.business_version_id == row.id,
                    BusinessRun.created_at >= since,
                )
                .group_by(BusinessRun.status)
            )
            .all()
        )
        for status, count in rows:
            key = str(status or "").strip().lower()
            value = int(count or 0)
            if key in metrics:
                metrics[key] = value
            metrics["total"] = int(metrics["total"] or 0) + value
        total = int(metrics["total"] or 0)
        if total > 0:
            metrics["success_rate"] = round(int(metrics["succeeded"] or 0) / total, 4)
        return metrics

    def _run_to_dict(self, row: BusinessRun, *, session=None) -> dict[str, Any]:
        ability_name: str | None = None
        ability_provider: str | None = None
        vendor_model_id: int | None = None
        vendor_model_name: str | None = None
        vendor_model_provider: str | None = None
        ability = session.get(Ability, row.ability_id) if session is not None and row.ability_id else None
        if ability:
            ability_name = ability.display_name
            ability_provider = ability.provider
            vendor_model_id = ability.vendor_model_id
        vendor_model = session.get(VendorModelCatalog, vendor_model_id) if session is not None and vendor_model_id else None
        if vendor_model:
            vendor_model_name = vendor_model.display_name
            vendor_model_provider = vendor_model.provider
        route_info = (row.request_payload or {}).get("_route") if isinstance(row.request_payload, dict) else None
        steps = self._run_steps_to_dict(row, session=session)
        billing_status = self._business_billing_status(row)
        issue_summary = self._build_run_issue_summary(row, session=session, steps=steps)
        retest_summary = self._build_retest_summary(row, session=session)
        return {
            "id": row.id,
            "business_key": row.business_key,
            "business_version_id": row.business_version_id,
            "version": row.version,
            "status": row.status,
            "source": row.source,
            "channel": row.channel,
            "trace_id": row.trace_id,
            "request_id": row.request_id,
            "tenant_id": row.tenant_id,
            "client_id": row.client_id,
            "user_id": row.user_id,
            "user_name": row.user_name,
            "ability_id": row.ability_id,
            "ability_name": ability_name,
            "ability_provider": ability_provider,
            "vendor_model_id": vendor_model_id,
            "vendor_model_name": vendor_model_name,
            "vendor_model_provider": vendor_model_provider,
            "ability_task_id": (
                encode_task_id(task_id=row.ability_task_id, provider=row.business_key, executor_id=None)
                if row.ability_task_id
                else None
            ),
            "ability_log_id": row.ability_log_id,
            "request_payload": self._omit_large_fields(row.request_payload),
            "result_payload": self._omit_large_fields(row.result_payload),
            "image_urls": row.image_urls,
            "video_urls": row.video_urls,
            "texts": row.texts,
            "error_message": row.error_message,
            "duration_ms": row.duration_ms,
            "billing_unit": row.billing_unit,
            "unit_price": float(row.unit_price) if row.unit_price is not None else None,
            "cost_amount": float(row.cost_amount) if row.cost_amount is not None else None,
            "currency": row.currency,
            "quota_units": row.quota_units,
            "cost_breakdown": row.cost_breakdown,
            "billing_status": billing_status,
            "chargeable": billing_status == "billable",
            "no_charge_reason": self._business_no_charge_reason(row),
            "callback_status": row.callback_status,
            "callback_http_status": row.callback_http_status,
            "callback_error": row.callback_error,
            "debug_url": row.debug_url,
            "route_info": route_info,
            "issue_category": issue_summary["category"],
            "issue_label": issue_summary["label"],
            "issue_severity": issue_summary["severity"],
            "issue_action": issue_summary["action"],
            "issue_evidence": issue_summary["evidence"],
            "retest_source_run_id": retest_summary.get("sourceRunId"),
            "retest_latest_run_id": retest_summary.get("latestRunId"),
            "retest_latest_status": retest_summary.get("latestStatus"),
            "retest_attempts": int(retest_summary.get("attempts") or 0),
            "retest_recovered": bool(retest_summary.get("recovered")),
            "retest_summary": retest_summary,
            "flow_summary": self._build_run_flow_summary(row, steps=steps, route_info=route_info, session=session),
            "steps": steps,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }

    def _run_steps_to_dict(self, row: BusinessRun, *, session=None) -> list[dict[str, Any]]:
        if session is None:
            return []
        steps = (
            session.execute(
                select(BusinessRunStep)
                .where(BusinessRunStep.run_id == row.id)
                .order_by(BusinessRunStep.step_order.asc(), BusinessRunStep.created_at.asc())
            )
            .scalars()
            .all()
        )
        log_map = self._load_ability_log_map(
            session,
            [int(step.ability_log_id) for step in steps if step.ability_log_id],
        )
        rows: list[dict[str, Any]] = []
        for step in steps:
            log = log_map.get(int(step.ability_log_id)) if step.ability_log_id else None
            rows.append(
                {
                    "id": step.id,
                    "run_id": step.run_id,
                    "step_order": step.step_order,
                    "step_id": step.step_id,
                    "step_type": step.step_type,
                    "role": step.role,
                    "display_name": step.display_name,
                    "enabled": step.enabled,
                    "status": step.status,
                    "ability_id": step.ability_id,
                    "ability_name": step.ability_name,
                    "ability_provider": step.ability_provider,
                    "ability_task_id": (
                        encode_task_id(task_id=step.ability_task_id, provider=row.business_key, executor_id=None)
                        if step.ability_task_id
                        else None
                    ),
                    "ability_log_id": step.ability_log_id,
                    "executor_id": log.executor_id if log else None,
                    "executor_name": log.executor_name if log else None,
                    "executor_type": log.executor_type if log else None,
                    "execution_evidence": self._build_execution_evidence(log),
                    "result_summary": self._build_step_result_summary(step),
                    "error_message": step.error_message,
                    "duration_ms": step.duration_ms,
                    "billing_unit": step.billing_unit,
                    "unit_price": float(step.unit_price) if step.unit_price is not None else None,
                    "cost_amount": float(step.cost_amount) if step.cost_amount is not None else None,
                    "currency": step.currency,
                    "quota_units": step.quota_units,
                    "cost_breakdown": step.cost_breakdown,
                    "started_at": step.started_at,
                    "finished_at": step.finished_at,
                    "created_at": step.created_at,
                    "updated_at": step.updated_at,
                }
            )
        return rows

    def _load_ability_log_map(self, session, log_ids: list[int]) -> dict[int, AbilityInvocationLog]:
        if not session or not log_ids:
            return {}
        unique_ids = sorted({int(item) for item in log_ids if item})
        if not unique_ids:
            return {}
        rows = (
            session.execute(select(AbilityInvocationLog).where(AbilityInvocationLog.id.in_(unique_ids)))
            .scalars()
            .all()
        )
        return {int(row.id): row for row in rows}

    def _build_execution_evidence(self, log: AbilityInvocationLog | None) -> dict[str, Any] | None:
        if not log:
            return None
        assets = log.result_assets if isinstance(log.result_assets, list) else []
        return {
            "abilityLogId": log.id,
            "executorId": log.executor_id,
            "executorName": log.executor_name,
            "executorType": log.executor_type,
            "status": log.status,
            "storedUrl": log.stored_url,
            "assetCount": len(assets),
            "hasOssOutput": bool(log.stored_url or assets),
            "callbackStatus": log.callback_status,
            "callbackHttpStatus": log.callback_http_status,
            "callbackError": log.callback_error,
            "durationMs": log.duration_ms,
        }

    @staticmethod
    def _normalize_issue_category(value: str | None) -> str | None:
        text = str(value or "").strip().lower()
        if not text or text == "all":
            return None
        aliases = {
            "ok": "none",
            "normal": "none",
            "no_issue": "none",
            "route": "version",
            "routing": "version",
            "ability": "executor",
            "execution": "executor",
            "comfyui": "executor",
            "oss": "output",
            "result": "output",
        }
        text = aliases.get(text, text)
        return text if text in {"none", "version", "parameter", "executor", "output", "callback", "billing"} else None

    @staticmethod
    def _issue_category_meta(category: str | None) -> dict[str, str]:
        key = BusinessRunService._normalize_issue_category(category) or "none"
        mapping = {
            "version": {
                "label": "版本/路由问题",
                "severity": "warning",
                "action": "检查默认版本、灰度命中和 route-preview。",
            },
            "parameter": {
                "label": "参数问题",
                "severity": "warning",
                "action": "核对业务入参、图片地址、尺寸和必填字段。",
            },
            "executor": {
                "label": "执行节点问题",
                "severity": "danger",
                "action": "检查执行节点连通性、队列、模型依赖和能力日志。",
            },
            "output": {
                "label": "结果回填问题",
                "severity": "danger",
                "action": "检查输出解析、OSS 落盘和结果字段映射。",
            },
            "callback": {
                "label": "业务回调问题",
                "severity": "warning",
                "action": "重试回调；仍失败时确认业务方地址、鉴权和签名。",
            },
            "billing": {
                "label": "计费扣减问题",
                "severity": "warning",
                "action": "检查价格规则、套餐/钱包扣减和结算流水。",
            },
            "none": {
                "label": "暂无明显问题",
                "severity": "success",
                "action": "继续观察，可作为稳定样本。",
            },
        }
        return mapping[key]

    @staticmethod
    def _issue_recommended_actions(category: str, *, run: BusinessRun) -> list[str]:
        key = BusinessRunService._normalize_issue_category(category) or "none"
        if key == "version":
            return [
                "先运行 route-preview，确认当前业务方会命中哪个版本。",
                "检查默认版本、灰度名单、版本启停状态是否符合预期。",
                "如果刚切版本，先回滚到上一稳定版本再复测。",
            ]
        if key == "parameter":
            return [
                "核对原图 URL 是否可访问，尺寸、必填字段、提示词格式是否正确。",
                "用同一请求参数在管理端复测一条，不要先改业务方代码。",
                "如果是字段变更，补接口文档和错误码说明后再通知业务方。",
            ]
        if key == "executor":
            return [
                "检查执行节点健康、队列长度、模型文件和工作流依赖。",
                "如果某台 ComfyUI 不通，先标记离线或修复依赖，不要让任务继续打过去。",
                "节点恢复后对这条记录发起复测，确认结果能回填。",
            ]
        if key == "output":
            return [
                "检查能力日志中的原始输出、storedUrl 和 resultAssets。",
                "确认 OSS 下载、上传、结果字段映射是否正常。",
                "同一任务不要只看 ComfyUI 成功，要以业务 run 的 imageUrls/videoUrls/texts 为准。",
            ]
        if key == "callback":
            return [
                "先使用“重试回调”，观察 HTTP 状态和业务方响应。",
                "确认业务方回调地址、鉴权头、签名和白名单是否仍有效。",
                "如果业务方已收到结果但中台显示失败，需要补回调幂等或状态同步说明。",
            ]
        if key == "billing":
            return [
                "先确认业务或模型是否已经配置价格规则。",
                "如果已定价但没有扣减流水，检查套餐、钱包余额和结算日志。",
                "计费修复后使用业务详情里的计费重试能力补齐扣减证据。",
            ]
        return ["当前没有明显链路问题，可作为稳定样本保留。"]

    def _build_issue_checklist_item(
        self,
        row: BusinessRun,
        *,
        issue: dict[str, Any],
        session,
    ) -> dict[str, Any]:
        steps = self._run_steps_to_dict(row, session=session)
        route_info = (row.request_payload or {}).get("_route") if isinstance(row.request_payload, dict) else {}
        route_info = route_info if isinstance(route_info, dict) else {}
        flow = self._build_run_flow_summary(row, steps=steps, route_info=route_info, session=session)
        ability = flow.get("ability") if isinstance(flow.get("ability"), dict) else {}
        executor = flow.get("executor") if isinstance(flow.get("executor"), dict) else {}
        output = flow.get("output") if isinstance(flow.get("output"), dict) else {}
        callback = flow.get("callback") if isinstance(flow.get("callback"), dict) else {}
        diagnostics = [
            f"任务状态：{row.status}",
            f"业务版本：{row.version or '-'}",
            f"原子能力：{ability.get('name') or ability.get('id') or row.ability_id or '-'}",
            f"执行节点：{executor.get('name') or executor.get('id') or '-'}",
            (
                "输出回填："
                f"图片 {output.get('imageCount') or len(row.image_urls or [])}，"
                f"视频 {output.get('videoCount') or len(row.video_urls or [])}，"
                f"文字 {output.get('textCount') or len(row.texts or [])}"
            ),
            f"回调状态：{callback.get('status') or row.callback_status or '-'}",
        ]
        if issue.get("evidence"):
            diagnostics.append(f"问题证据：{issue.get('evidence')}")
        retest_summary = self._build_retest_summary(row, session=session)
        return {
            "run_id": row.id,
            "business_key": row.business_key,
            "version": row.version,
            "status": row.status,
            "issue_category": issue.get("category") or "none",
            "issue_label": issue.get("label") or self._issue_category_meta(issue.get("category"))["label"],
            "issue_severity": issue.get("severity") or self._issue_category_meta(issue.get("category"))["severity"],
            "issue_action": issue.get("action"),
            "issue_evidence": issue.get("evidence"),
            "recommended_actions": self._issue_recommended_actions(str(issue.get("category") or "none"), run=row),
            "diagnostics": diagnostics,
            "ability_id": ability.get("id") or row.ability_id,
            "ability_name": ability.get("name"),
            "executor_id": executor.get("id"),
            "executor_name": executor.get("name"),
            "callback_status": callback.get("status") or row.callback_status,
            "retest_latest_run_id": retest_summary.get("latestRunId"),
            "retest_latest_status": retest_summary.get("latestStatus"),
            "created_at": row.created_at,
        }

    @staticmethod
    def _issue_checklist_markdown(
        items: list[dict[str, Any]],
        *,
        generated_at: str,
        skipped_count: int,
    ) -> str:
        lines = [
            "# 业务运行排障清单",
            "",
            f"- 生成时间：{generated_at}",
            f"- 待处理记录：{len(items)} 条",
            f"- 已跳过记录：{skipped_count} 条",
            "",
        ]
        if not items:
            lines.append("当前选择范围内没有需要处理的问题记录。")
            return "\n".join(lines)
        for index, item in enumerate(items, start=1):
            lines.extend(
                [
                    f"## {index}. {item.get('business_key') or '-'} / {item.get('run_id')}",
                    "",
                    f"- 问题类型：{item.get('issue_label') or '-'}",
                    f"- 当前状态：{item.get('status') or '-'}",
                    f"- 业务版本：{item.get('version') or '-'}",
                    f"- 原子能力：{item.get('ability_name') or item.get('ability_id') or '-'}",
                    f"- 执行节点：{item.get('executor_name') or item.get('executor_id') or '-'}",
                    f"- 证据：{item.get('issue_evidence') or '-'}",
                    "",
                    "处理动作：",
                ]
            )
            for action in item.get("recommended_actions") or []:
                lines.append(f"- {action}")
            lines.extend(["", "诊断信息："])
            for diagnostic in item.get("diagnostics") or []:
                lines.append(f"- {diagnostic}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _build_run_issue_summary(
        self,
        row: BusinessRun,
        *,
        session=None,
        steps: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if steps is None and session is not None:
            steps = self._run_steps_to_dict(row, session=session)
        steps = steps or []
        result_payload = row.result_payload if isinstance(row.result_payload, dict) else {}
        resolution = result_payload.get("_adminIssueResolution") or result_payload.get("_admin_issue_resolution")
        if isinstance(resolution, dict) and resolution.get("status") == "ignored":
            note = self._clean_optional_text(str(resolution.get("note") or ""))
            return {
                "category": "none",
                "label": "已标记无需处理",
                "severity": "success",
                "action": note or "运营已确认这条记录暂不需要继续处理。",
                "evidence": note,
            }
        status = str(row.status or "").strip().lower()
        image_count = len(row.image_urls or [])
        video_count = len(row.video_urls or [])
        text_count = len(row.texts or [])
        structured_count = self._count_structured_outputs(result_payload)
        resource_count = self._count_resource_outputs(result_payload)
        has_output = bool(image_count or video_count or text_count or structured_count or resource_count)
        callback_failed = status == "succeeded" and (
            str(row.callback_status or "").strip().lower() == "failed" or bool(row.callback_error)
        )
        billing_status = self._business_billing_status(row)
        wallet_settlement = self._billing_settlement_from_run(row)
        package_settlement = self._package_settlement_from_run(row)
        settlement = wallet_settlement or package_settlement
        settlement_status = str((settlement or {}).get("status") or "").strip().lower()
        billing_evidence: str | None = None
        billing_issue = False
        if status == "succeeded" and billing_status == "unpriced":
            billing_issue = True
            billing_evidence = self._business_no_charge_reason(row) or "任务成功但缺少定价，待确认计费口径"
        elif status == "succeeded" and settlement_status == "failed":
            billing_issue = True
            billing_evidence = str((settlement or {}).get("error") or "计费扣减失败")
        elif status == "succeeded" and billing_status == "billable" and row.user_id and not settlement:
            billing_issue = True
            billing_evidence = "任务应计费但未发现套餐或钱包扣减流水"
        route_missing = not row.business_version_id or not row.version
        error_text = " ".join(
            str(item or "")
            for item in [
                row.error_message,
                row.callback_error,
                *(step.get("error_message") for step in steps if isinstance(step, dict)),
            ]
        ).lower()
        parameter_markers = (
            "missing",
            "invalid",
            "required",
            "schema",
            "validation",
            "参数",
            "缺少",
            "必填",
            "格式",
            "无效",
        )
        failed_step = next((step for step in steps if str(step.get("status") or "").lower() == "failed"), None)
        active_step = next(
            (step for step in steps if str(step.get("status") or "").lower() in {"queued", "running"}),
            None,
        )

        if callback_failed:
            category = "callback"
        elif status == "succeeded" and not has_output:
            category = "output"
        elif billing_issue:
            category = "billing"
        elif route_missing:
            category = "version"
        elif status == "failed" and any(marker in error_text for marker in parameter_markers):
            category = "parameter"
        elif status in {"failed", "queued", "running"} or failed_step or active_step:
            category = "executor"
        else:
            category = "none"

        meta = self._issue_category_meta(category)
        evidence_step = failed_step or active_step or (steps[-1] if steps else None)
        evidence = billing_evidence if category == "billing" else row.error_message or (evidence_step or {}).get("error_message") or row.callback_error
        return {
            "category": category,
            "label": meta["label"],
            "severity": meta["severity"],
            "action": meta["action"],
            "evidence": str(evidence) if evidence else None,
        }

    def _build_run_flow_summary(
        self,
        row: BusinessRun,
        *,
        steps: list[dict[str, Any]],
        route_info: dict[str, Any] | None,
        session=None,
    ) -> dict[str, Any]:
        counts = {
            "total": len(steps),
            "succeeded": 0,
            "failed": 0,
            "running": 0,
            "queued": 0,
            "planned": 0,
            "skipped": 0,
            "cancelled": 0,
        }
        active_step: dict[str, Any] | None = None
        primary_step: dict[str, Any] | None = None
        for step in steps:
            status = str(step.get("status") or "").lower()
            if status in counts:
                counts[status] += 1
            if not active_step and status in {"failed", "running", "queued"}:
                active_step = step
            if not primary_step and step.get("role") == "primary":
                primary_step = step
        if not active_step and steps:
            active_step = steps[-1]
        if not primary_step and steps:
            primary_step = steps[-1]

        total = int(counts["total"] or 0)
        finished = counts["succeeded"] + counts["failed"] + counts["skipped"] + counts["cancelled"]
        progress = round((finished / total) * 100) if total else None
        route = route_info if isinstance(route_info, dict) else {}
        run_log = None
        if session is not None and row.ability_log_id:
            run_log = session.get(AbilityInvocationLog, int(row.ability_log_id))
        if not run_log and primary_step and primary_step.get("ability_log_id") and session is not None:
            run_log = session.get(AbilityInvocationLog, int(primary_step["ability_log_id"]))

        image_count = len(row.image_urls or [])
        video_count = len(row.video_urls or [])
        text_count = len(row.texts or [])
        structured_count = self._count_structured_outputs(row.result_payload if isinstance(row.result_payload, dict) else {})
        resource_count = self._count_resource_outputs(row.result_payload if isinstance(row.result_payload, dict) else {})
        has_output = bool(image_count or video_count or text_count or structured_count or resource_count)
        failed = counts["failed"] > 0 or row.status == "failed"
        if failed:
            message = "业务链路执行失败"
            next_action = row.error_message or (active_step or {}).get("error_message") or "查看失败步骤和执行日志"
        elif row.status in {"queued", "running"}:
            message = "业务链路执行中"
            next_action = "等待任务终态，必要时查看执行节点队列"
        elif row.status == "succeeded" and not has_output:
            message = "业务执行成功但未发现结果回填"
            next_action = "优先检查原子能力结果解析和 OSS 落盘"
        elif row.status == "succeeded":
            message = "业务链路执行成功"
            next_action = "结果已回填，可继续检查回调状态"
        else:
            message = f"业务链路状态：{row.status}"
            next_action = None

        issue_summary = self._build_run_issue_summary(row, session=session, steps=steps)
        return {
            **counts,
            "progressPercent": progress,
            "issueCategory": issue_summary["category"],
            "issueLabel": issue_summary["label"],
            "issueSeverity": issue_summary["severity"],
            "issueAction": issue_summary["action"],
            "issueEvidence": issue_summary["evidence"],
            "currentStepOrder": (active_step or {}).get("step_order"),
            "currentStepLabel": (active_step or {}).get("display_name")
            or (active_step or {}).get("ability_name")
            or (active_step or {}).get("step_id"),
            "currentStepStatus": (active_step or {}).get("status"),
            "currentStepError": (active_step or {}).get("error_message"),
            "message": message,
            "nextAction": next_action,
            "route": {
                "businessKey": row.business_key,
                "businessVersionId": row.business_version_id,
                "version": row.version,
                "selectedBy": route.get("selectedBy") or route.get("selected_by"),
                "selectedCapabilityId": route.get("selectedCapabilityId") or route.get("selected_capability_id"),
            },
            "ability": {
                "id": row.ability_id or (primary_step or {}).get("ability_id"),
                "name": (primary_step or {}).get("ability_name") or row.ability_id,
                "provider": (primary_step or {}).get("ability_provider"),
                "taskId": row.ability_task_id or (primary_step or {}).get("ability_task_id"),
                "logId": row.ability_log_id or (primary_step or {}).get("ability_log_id"),
            },
            "executor": self._build_flow_executor_summary(run_log, primary_step),
            "output": {
                "hasOutput": has_output,
                "imageCount": image_count,
                "videoCount": video_count,
                "textCount": text_count,
                "structuredCount": structured_count,
                "resourceCount": resource_count,
                "firstImageUrl": (row.image_urls or [None])[0],
                "firstVideoUrl": (row.video_urls or [None])[0],
                "hasOssOutput": bool((row.image_urls or []) or (run_log and (run_log.stored_url or run_log.result_assets))),
            },
            "callback": {
                "status": row.callback_status,
                "httpStatus": row.callback_http_status,
                "error": row.callback_error,
            },
        }

    def _build_flow_executor_summary(
        self,
        log: AbilityInvocationLog | None,
        primary_step: dict[str, Any] | None,
    ) -> dict[str, Any]:
        evidence = primary_step.get("execution_evidence") if isinstance(primary_step, dict) else None
        evidence = evidence if isinstance(evidence, dict) else {}
        return {
            "id": (log.executor_id if log else None) or (primary_step.get("executor_id") if primary_step else None),
            "name": (log.executor_name if log else None) or (primary_step.get("executor_name") if primary_step else None),
            "type": (log.executor_type if log else None) or (primary_step.get("executor_type") if primary_step else None),
            "abilityLogId": (log.id if log else None) or evidence.get("abilityLogId"),
            "storedUrl": (log.stored_url if log else None) or evidence.get("storedUrl"),
            "assetCount": len(log.result_assets) if log and isinstance(log.result_assets, list) else evidence.get("assetCount"),
        }

    @staticmethod
    def _count_structured_outputs(payload: dict[str, Any] | None) -> int:
        if not isinstance(payload, dict):
            return 0
        count = 0
        for key in ("jsonOutput", "json_output", "structured", "structuredOutput", "structured_output", "json"):
            value = payload.get(key)
            if isinstance(value, dict) and value:
                count += 1
            elif isinstance(value, list) and value:
                count += len(value)
        return count

    def _build_step_result_summary(self, step: BusinessRunStep) -> dict[str, Any] | None:
        payload = step.result_payload if isinstance(step.result_payload, dict) else {}
        if not payload:
            return None
        summary: dict[str, Any] = {}
        image_urls = self._extract_urls(payload, keys=("images", "assets", "resultUrls", "imageUrls"))
        video_urls = self._extract_urls(payload, keys=("videos", "videoUrls"))
        resource_urls = self._extract_urls(payload, keys=("resourceUrls", "resource_urls", "resources", "files", "attachments"))
        if image_urls:
            summary["imageCount"] = len(image_urls)
            summary["firstImageUrl"] = image_urls[0]
        if video_urls:
            summary["videoCount"] = len(video_urls)
            summary["firstVideoUrl"] = video_urls[0]
        if resource_urls:
            summary["resourceCount"] = len(resource_urls)
            summary["firstResourceUrl"] = resource_urls[0]

        texts = payload.get("texts")
        first_text = None
        if isinstance(texts, list):
            for item in texts:
                if isinstance(item, (str, int, float)) and str(item).strip():
                    first_text = str(item).strip()
                    break
        if first_text:
            parsed = self._try_parse_json(first_text)
            if isinstance(parsed, dict):
                control_card = (
                    parsed.get("fissionControlCard") if isinstance(parsed.get("fissionControlCard"), dict) else None
                )
                if not control_card:
                    control_markers = {"route_mode", "pattern_type", "profile_hint", "prompt_main", "prompt_control"}
                    if len(control_markers.intersection(parsed)) >= 3:
                        control_card = parsed
                if isinstance(control_card, dict):
                    summary["fissionControlCard"] = control_card
                    for source_key, target_key in (
                        ("pattern_type", "patternType"),
                        ("profile_hint", "profileHint"),
                        ("prompt_main", "promptMain"),
                        ("prompt_control", "promptControl"),
                    ):
                        value = control_card.get(source_key)
                        if isinstance(value, (str, int, float)) and str(value).strip():
                            summary[target_key] = str(value).strip()[:1200]
                    if isinstance(control_card.get("prompt_main"), (str, int, float)):
                        summary.setdefault("positivePrompt", str(control_card.get("prompt_main")).strip()[:1200])
                    if isinstance(control_card.get("prompt_control"), (str, int, float)):
                        summary.setdefault("imageDesc", str(control_card.get("prompt_control")).strip()[:1200])
                vl_card = parsed.get("vlCard") if isinstance(parsed.get("vlCard"), dict) else None
                if not vl_card:
                    card_markers = {
                        "image_type",
                        "composition",
                        "motifs",
                        "preserve_locks",
                        "change_targets",
                        "fission_brief",
                    }
                    if len(card_markers.intersection(parsed)) >= 3:
                        vl_card = parsed
                if isinstance(vl_card, dict):
                    summary["vlCard"] = vl_card
                    for source_key, target_key in (
                        ("pattern_type", "patternType"),
                        ("image_type", "imageType"),
                        ("style_family", "styleFamily"),
                        ("fission_brief", "fissionBrief"),
                    ):
                        value = vl_card.get(source_key)
                        if isinstance(value, (str, int, float)) and str(value).strip():
                            summary[target_key] = str(value).strip()[:800]
                    if isinstance(vl_card.get("fission_brief"), (str, int, float)):
                        summary.setdefault("imageDesc", str(vl_card.get("fission_brief")).strip()[:800])
                if isinstance(parsed.get("summary"), (str, int, float)):
                    summary["summary"] = str(parsed.get("summary"))[:500]
                if isinstance(parsed.get("style"), (str, int, float)):
                    summary["style"] = str(parsed.get("style"))[:160]
                if isinstance(parsed.get("composition"), (str, int, float)):
                    summary["composition"] = str(parsed.get("composition"))[:200]
                for key in ("subjects", "colors", "riskFlags"):
                    value = parsed.get(key)
                    if isinstance(value, list):
                        summary[key] = [str(item)[:80] for item in value[:8]]
                prompt_card = parsed.get("promptCard")
                if isinstance(prompt_card, dict):
                    for source_key, target_key in (
                        ("imageDesc", "imageDesc"),
                        ("positivePrompt", "positivePrompt"),
                        ("negativePrompt", "negativePrompt"),
                    ):
                        value = prompt_card.get(source_key)
                        if isinstance(value, (str, int, float)) and str(value).strip():
                            summary[target_key] = str(value).strip()[:800]
            else:
                summary["textPreview"] = first_text[:800]

        return summary or None

    @staticmethod
    def _try_parse_json(value: str) -> Any:
        text = str(value or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").strip()
            if text.endswith("```"):
                text = text[:-3].strip()
        try:
            return json.loads(text)
        except Exception:
            return None

    def _omit_large_fields(self, payload: Any, depth: int = 0) -> Any:
        if depth > 6:
            return "[truncated]"
        if isinstance(payload, dict):
            out: dict[str, Any] = {}
            for key, value in payload.items():
                key_lower = str(key).lower()
                if key_lower in {"imagebase64", "image_base64"} or key_lower.endswith("base64"):
                    out[key] = "[omitted]"
                else:
                    out[key] = self._omit_large_fields(value, depth + 1)
            return out
        if isinstance(payload, list):
            return [self._omit_large_fields(item, depth + 1) for item in payload[:50]]
        return payload


@lru_cache
def get_business_run_service() -> BusinessRunService:
    return BusinessRunService()
