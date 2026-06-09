"""Business capability orchestration service."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from io import BytesIO
import hashlib
import json
import logging
import math
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException
from PIL import Image, ImageDraw
from pydantic import ValidationError
from sqlalchemy import and_, case, func, inspect, not_, or_, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import load_only

from app.core.config import get_settings
from app.core.db import get_session
from app.models.integration import (
    Ability,
    AbilityInvocationLog,
    AbilityTask,
    ApiKey,
    BusinessCapability,
    BusinessClient,
    BusinessAgentPlan,
    BusinessAgentSession,
    BusinessAgentToolCall,
    BusinessApiKeyUsageLog,
    BusinessDefaultApproval,
    BusinessOperationLog,
    BusinessOutputReview,
    BusinessQualityActionRule,
    BusinessQualitySample,
    BusinessQualitySampleVersion,
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
    BusinessCapabilityDraftCreateRequest,
    BusinessCapabilityDraftPublishRequest,
    BusinessCapabilityDraftRecipeUpdateRequest,
    BusinessCapabilityPromoteRequest,
    BusinessCapabilityRollbackRequest,
    BusinessCapabilityUpdateRequest,
    BusinessClientCreateRequest,
    BusinessClientUpdateRequest,
    BusinessDefaultApprovalCreateRequest,
    BusinessDefaultApprovalDecisionRequest,
    BusinessOutputReviewUpsertRequest,
    BusinessQualityActionRuleCreateRequest,
    BusinessQualityActionRuleUpdateRequest,
    BusinessQualitySampleCreateRequest,
    BusinessQualitySampleImportRequest,
    BusinessQualitySampleUpdateRequest,
    BusinessRunCreateRequest,
    ProductCommercializationRequest,
    TextFissionPromptRequest,
)
from app.constants.business_api_contract import (
    COMFYUI_FISSION_VARIATION_PRESET_CONFIGS,
    IMAGE_EDIT_CUSTOM_SIZE_CONSTRAINTS,
    IMAGE_EDIT_OUTPUT_FORMAT_VALUES,
    IMAGE_EDIT_QUALITY_VALUES,
    IMAGE_EDIT_SIZE_VALUES,
    IMAGE_EDIT_SKILL_VALUES,
    PRODUCT_DESIGN_PRODUCT_TYPE_VALUES,
    PRODUCT_DESIGN_SCENE_VALUES,
)
from app.services.api_key_selector import is_usable
from app.services.ability_seed import ensure_default_abilities
from app.services.ability_invocation import ability_invocation_service
from app.services.ability_task_service import get_ability_task_service
from app.services.business_seed import ensure_default_business_capabilities
from app.services.business_projects import get_business_project_service
from app.services.product_commercialization import product_commercialization_service
from app.services.fission_control_prompt import compile_comfyui_v4_image_desc
from app.services.fission_control_prompt import compile_comfyui_v4_prompt
from app.services.fission_control_prompt import extract_fission_control_card
from app.services.media_ingest import media_ingest_service
from app.services.pattern_fission_prompt import LEGACY_TEMPLATE_ALIASES as PATTERN_FISSION_LEGACY_TEMPLATE_ALIASES
from app.services.pattern_fission_prompt import TEMPLATE_ALIASES as PATTERN_FISSION_TEMPLATE_ALIASES
from app.services.pattern_fission_prompt import TEMPLATE_ID as PATTERN_FISSION_TEMPLATE_ID
from app.services.pattern_fission_prompt import compile_pattern_fission_prompt
from app.services.routing_governance import normalize_ability_routing
from app.services.runtime_safety import log_background_worker_decision, suppress_background_threads_for_tests
from app.services.oss import oss_service
from app.services.task_id_codec import encode_task_id
from app.services.wallet import wallet_service


logger = logging.getLogger(__name__)
FINALIZE_INTERVAL_SECONDS = 6
FINALIZE_BATCH_SIZE = 30
BUSINESS_DASHBOARD_CACHE_TTL_SECONDS = 12
BUSINESS_DASHBOARD_CACHE_MAX_ITEMS = 64
BUSINESS_USAGE_FLOW_EVIDENCE_RUN_LIMIT = 5
_BUSINESS_DASHBOARD_CACHE_LOCK = threading.RLock()
_BUSINESS_DASHBOARD_CACHE: dict[tuple[Any, ...], tuple[float, Any]] = {}
VENDOR_KEY_CHECK_STALE_DAYS = 7
RECIPE_EXECUTABLE_STEP_TYPES = {"ability_task", "comfyui_workflow", "vendor_api", "vl_analyze", "vl_analyze_image"}
RECIPE_PASSIVE_STEP_TYPES = {"input_mapping", "output_mapping", "prompt_template", "note"}
INTERNAL_NO_CHARGE_SOURCES = {"business-api-patrol"}
COMFYUI_COLORLOCK_FISSION_ABILITY_IDS = {"comfyui_flux_strong_hq_softstyle_fission_colorlock_v2"}
COMFYUI_FISSION_VARIATION_PRESET_VALUES_BY_KEY = {
    str(item.get("key")): dict(item.get("values") or {})
    for item in COMFYUI_FISSION_VARIATION_PRESET_CONFIGS
    if item.get("key") and isinstance(item.get("values"), dict)
}
FISSION_ASPECT_RECOMPOSE_TARGET_ABILITIES = {"comfyui_flux_strong_hq_softstyle_fission_colorlock_v2"}
FISSION_ASPECT_RECOMPOSE_RATIO_MIN = 0.75
FISSION_ASPECT_RECOMPOSE_RATIO_MAX = 1.33
FISSION_ASPECT_RECOMPOSE_EXTREME_MIN = 0.20
FISSION_ASPECT_RECOMPOSE_EXTREME_MAX = 5.00
FISSION_ASPECT_RECOMPOSE_SOURCE_SHAPE_MIN = 0.15
FISSION_ASPECT_RECOMPOSE_PROMPT_SUFFIX = (
    "Safe full-pattern aspect-ratio recompose mode. The input is a repeatable textile/print pattern "
    "with no single main subject. Generate a native full-canvas pattern for the target ratio. "
    "Avoid crop feeling, pasted patches, hard tile seams, and blurry side bands. Preserve motif categories, "
    "color palette, density rhythm, average motif scale, line/material style, and empty-space distribution. "
    "Allow visible object-level fission changes while keeping a clean repeatable print pattern."
)
INTERNAL_NO_CHARGE_TENANTS = {"podi-internal-patrol", "podi-internal-realtest"}
INTERNAL_NO_CHARGE_CLIENTS = {"business-api-patrol", "codex-realtest"}
NO_CHARGE_BILLING_MODES = {"no_charge", "no-charge", "free", "internal", "internal_patrol", "patrol", "test"}
IMAGE_EDIT_REFERENCE_REQUIRED_SKILLS = {"reference_element_transfer", "color_reference_correction"}
IMAGE_EDIT_TARGET_HINT_REQUIRED_SKILLS = {"remove_inpaint"}
IMAGE_EDIT_SKILL_LABELS = {
    "local_modify": "局部修改",
    "reference_element_transfer": "参考图替换",
    "remove_inpaint": "删除修补",
    "color_reference_correction": "补色校正",
    "canvas_outpaint": "扩展画布",
}
IMAGE_EDIT_QUALITY_MAP = {
    "auto": "auto",
    "preview": "low",
    "production": "medium",
    "candidate": "medium",
    "premium": "high",
    "low": "low",
    "medium": "medium",
    "high": "high",
}
PRODUCT_DESIGN_PRODUCT_TYPE_LABELS = {
    "apparel": "服装/面料",
    "home_textile": "家纺/软装",
    "bag": "箱包",
    "shoe": "鞋履",
    "stationery": "文具/小商品",
    "packaging": "包装",
    "generic": "通用产品",
}
PRODUCT_DESIGN_SCENE_LABELS = {
    "studio_product": "棚拍产品图",
    "flat_lay": "平铺产品图",
    "ecommerce": "电商主图",
    "lifestyle": "生活方式场景",
    "print_mockup": "印花/图案上产品 mockup",
    "generic": "通用场景",
}
BUSINESS_OUTPUT_REVIEW_GRADES = {"pending", "excellent", "usable", "borderline", "bad", "blocked"}
BUSINESS_OUTPUT_REVIEW_ACTIONS = {
    "accept",
    "tune_params",
    "route_split",
    "switch_lora",
    "manual_review",
    "pause_recommendation",
}
BUSINESS_QUALITY_ACTION_TYPES = {
    "watch_only",
    "tune_params",
    "route_split",
    "switch_lora",
    "switch_workflow",
    "pause_recommendation",
}
BUSINESS_QUALITY_ACTION_STATUSES = {"draft", "candidate", "validated", "default", "paused", "rejected", "archived"}
BUSINESS_QUALITY_GATE_KEYS = {"pattern_extract", "fission", "image_edit", "outpaint", "text_fission", "product_design"}
BUSINESS_QUALITY_ACCEPTED_GRADES = {"excellent", "usable"}
BUSINESS_QUALITY_RISK_GRADES = {"borderline", "bad", "blocked"}
BUSINESS_QUALITY_GATE_WINDOW_HOURS = 168
BUSINESS_FLOW_STAGE_ORDER = [
    "entry",
    "version",
    "preprocess",
    "routing",
    "primary",
    "output",
    "callback-billing",
]
BUSINESS_FLOW_STAGE_LABELS = {
    "entry": "提交入口",
    "version": "版本命中",
    "preprocess": "输入预处理",
    "routing": "路由/分流",
    "primary": "主执行",
    "output": "结果入库",
    "callback-billing": "回调/计费",
}
BUSINESS_FLOW_CANDIDATE_SELECTORS = {
    "admin_draft",
    "candidate",
    "quality_rule",
    "route_split",
    "rollout_allowlist",
    "rollout_percent",
    "switch_lora",
    "switch_workflow",
}
BUSINESS_FLOW_LORA_KEYS = {
    "lora",
    "loras",
    "loraname",
    "lora_name",
    "lorafile",
    "lora_file",
    "lorafilename",
    "lora_filename",
    "loramodel",
    "lora_model",
}
BUSINESS_FLOW_WORKFLOW_KEYS = {
    "workflow",
    "workflowid",
    "workflow_id",
    "workflowkey",
    "workflow_key",
    "workflowname",
    "workflow_name",
    "comfyuiworkflowkey",
    "comfyui_workflow_key",
}
IMAGE_EDIT_OUTPAINT_ANCHORS = {
    "center",
    "left",
    "right",
    "top",
    "bottom",
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
    "custom",
}


class BusinessRunService:
    def __init__(self) -> None:
        worker_decision = log_background_worker_decision("BusinessRunService")
        self._background_workers_enabled = worker_decision.enabled
        self._thread_started = False
        self._product_commercialization_active_run_ids: set[str] = set()
        self._product_commercialization_lock = threading.Lock()
        if self._background_workers_enabled and not suppress_background_threads_for_tests():
            self._start_finalize_thread()

    @staticmethod
    def _dashboard_cache_enabled() -> bool:
        return not suppress_background_threads_for_tests()

    @staticmethod
    def _dashboard_cache_key(*parts: Any) -> tuple[Any, ...]:
        return tuple("" if part is None else part for part in parts)

    @classmethod
    def _clear_dashboard_cache(cls) -> None:
        with _BUSINESS_DASHBOARD_CACHE_LOCK:
            _BUSINESS_DASHBOARD_CACHE.clear()

    @classmethod
    def _dashboard_cached(cls, key: tuple[Any, ...], producer) -> Any:
        if not cls._dashboard_cache_enabled():
            return producer()
        now = time.monotonic()
        with _BUSINESS_DASHBOARD_CACHE_LOCK:
            cached = _BUSINESS_DASHBOARD_CACHE.get(key)
            if cached and cached[0] > now:
                return deepcopy(cached[1])

        value = producer()
        with _BUSINESS_DASHBOARD_CACHE_LOCK:
            if len(_BUSINESS_DASHBOARD_CACHE) >= BUSINESS_DASHBOARD_CACHE_MAX_ITEMS:
                oldest_key = min(_BUSINESS_DASHBOARD_CACHE.items(), key=lambda item: item[1][0])[0]
                _BUSINESS_DASHBOARD_CACHE.pop(oldest_key, None)
            _BUSINESS_DASHBOARD_CACHE[key] = (time.monotonic() + BUSINESS_DASHBOARD_CACHE_TTL_SECONDS, deepcopy(value))
        return value

    def list_capabilities(self) -> list[BusinessCapability]:
        return self._dashboard_cached(
            self._dashboard_cache_key("list_capabilities"),
            self._list_capabilities_uncached,
        )

    def _list_capabilities_uncached(self) -> list[BusinessCapability]:
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

    @staticmethod
    def _optional_table_exists(session, table_name: str) -> bool:
        # Use the current transactional connection. Inspecting the engine can
        # borrow the same raw connection under StaticPool and roll back pending
        # writes in isolated tests.
        return inspect(session.connection()).has_table(table_name)

    @staticmethod
    def _empty_output_review_summary(*, window_hours: int, filters: dict[str, Any]) -> dict[str, Any]:
        return {
            "window_hours": window_hours,
            "filters": filters,
            "total": 0,
            "by_grade": [],
            "by_business": [],
            "by_version": [],
            "by_batch": [],
            "top_issue_tags": [],
            "top_input_tags": [],
            "recent_reviews": [],
        }

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
            recipe_touched = payload.recipe is not None or payload.primaryAbilityId is not None
            if payload.recipe is not None or payload.primaryAbilityId is not None:
                next_recipe = self._build_recipe(
                    base_recipe=payload.recipe if payload.recipe is not None else row.recipe,
                    primary_ability_id=payload.primaryAbilityId,
                )
                self._validate_recipe(session=session, recipe=next_recipe)
                if was_default and next_recipe != (row.recipe or {}):
                    raise HTTPException(status_code=409, detail="BUSINESS_DEFAULT_VERSION_CONTROL_FIELDS_IMMUTABLE")
                row.recipe = next_recipe
            next_status = self._normalize_status(payload.status) if payload.status is not None else row.status
            next_is_default = bool(payload.isDefault) if payload.isDefault is not None else row.is_default
            self._validate_default_status(is_default=next_is_default, status=next_status)
            if was_default and not next_is_default:
                raise HTTPException(status_code=409, detail="BUSINESS_DEFAULT_VERSION_CONTROL_FIELDS_IMMUTABLE")
            input_schema_touched = "inputSchema" in payload.model_fields_set or "input_schema" in payload.model_fields_set
            output_schema_touched = "outputSchema" in payload.model_fields_set or "output_schema" in payload.model_fields_set
            if was_default:
                business_identity_changed = next_business_key != row.business_key or next_version != row.version
                input_schema_changed = input_schema_touched and payload.inputSchema != row.input_schema
                output_schema_changed = output_schema_touched and payload.outputSchema != row.output_schema
                if business_identity_changed or input_schema_changed or output_schema_changed:
                    raise HTTPException(status_code=409, detail="BUSINESS_DEFAULT_VERSION_CONTROL_FIELDS_IMMUTABLE")
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
                    or recipe_touched
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

    def create_capability_draft(
        self,
        capability_id: str,
        payload: BusinessCapabilityDraftCreateRequest | None = None,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        request = payload or BusinessCapabilityDraftCreateRequest()
        with get_session() as session:
            source = session.get(BusinessCapability, capability_id)
            if not source:
                raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
            recipe = deepcopy(source.recipe or {})
            self._validate_recipe(session=session, recipe=recipe)
            version = self._required_text(
                request.version or self._next_draft_version(session=session, source=source),
                "BUSINESS_VERSION_REQUIRED",
            )
            duplicate = (
                session.execute(
                    select(BusinessCapability).where(
                        BusinessCapability.business_key == source.business_key,
                        BusinessCapability.version == version,
                    )
                )
                .scalars()
                .first()
            )
            if duplicate:
                raise HTTPException(status_code=409, detail="BUSINESS_CAPABILITY_VERSION_DUPLICATED")
            now = datetime.utcnow()
            metadata = deepcopy(source.extra_metadata or {})
            if isinstance(request.metadata, dict):
                metadata.update(deepcopy(request.metadata))
            metadata["draftInfo"] = {
                **(metadata.get("draftInfo") if isinstance(metadata.get("draftInfo"), dict) else {}),
                "sourceCapabilityId": source.id,
                "sourceVersion": source.version,
                "createdAt": now.isoformat(),
                "createdBy": self._actor_username(actor),
                "note": self._clean_optional_text(request.note),
            }
            metadata["versionLineage"] = {
                **(metadata.get("versionLineage") if isinstance(metadata.get("versionLineage"), dict) else {}),
                "parentVersionId": source.id,
                "supersedesVersionId": source.id,
                "changeSummary": self._clean_optional_text(request.note) or "从线上或既有版本复制出的草稿，待验证后再发布。",
                "breakingChange": False,
                "decision": "version_upgrade",
                "decisionNote": "同一业务入口下的草稿版本，不新增业务分类。",
            }
            row = BusinessCapability(
                id=f"biz_{source.business_key}_{version}_{uuid4().hex[:8]}",
                business_key=source.business_key,
                version=version,
                display_name=self._short_text(request.displayName, 128) or f"{source.display_name} 草稿",
                description=source.description,
                status="draft",
                is_default=False,
                release_time=None,
                recipe=recipe,
                input_schema=deepcopy(source.input_schema),
                output_schema=deepcopy(source.output_schema),
                extra_metadata=metadata,
            )
            session.add(row)
            session.flush()
            self._record_business_operation(
                session=session,
                action="create_capability_draft",
                target_type="business_capability",
                target_id=row.id,
                business_key=row.business_key,
                actor=actor,
                note=request.note,
                before_payload=self._json_safe_payload(self._capability_to_dict(source, session=session)),
                after_payload=self._json_safe_payload(self._capability_to_dict(row, session=session)),
            )
            session.commit()
            session.refresh(row)
            return self._capability_to_dict(row, session=session)

    def update_capability_draft_recipe(
        self,
        draft_id: str,
        payload: BusinessCapabilityDraftRecipeUpdateRequest,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        with get_session() as session:
            row = session.get(BusinessCapability, draft_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
            if row.is_default or row.status != "draft":
                raise HTTPException(status_code=409, detail="BUSINESS_DRAFT_ONLY_EDITABLE")
            before_recipe = deepcopy(row.recipe or {})
            next_recipe = self._build_recipe(
                base_recipe=payload.recipe,
                primary_ability_id=payload.primaryAbilityId,
            )
            self._validate_recipe(session=session, recipe=next_recipe)
            diff_summary = self._recipe_diff_summary(before_recipe, next_recipe)
            metadata = deepcopy(row.extra_metadata or {})
            draft_info = metadata.get("draftInfo") if isinstance(metadata.get("draftInfo"), dict) else {}
            history = draft_info.get("recipeChangeHistory") if isinstance(draft_info.get("recipeChangeHistory"), list) else []
            draft_info = {
                **draft_info,
                "updatedAt": datetime.utcnow().isoformat(),
                "updatedBy": self._actor_username(actor),
                "lastRecipeDiff": diff_summary,
                "lastRecipeNote": self._clean_optional_text(payload.note),
                "recipeChangeHistory": [
                    {
                        "changedAt": datetime.utcnow().isoformat(),
                        "changedBy": self._actor_username(actor),
                        "note": self._clean_optional_text(payload.note),
                        "diff": diff_summary,
                    },
                    *history,
                ][:20],
            }
            metadata["draftInfo"] = draft_info
            before_payload = self._json_safe_payload(
                {
                    "recipe": before_recipe,
                    "draftInfo": (row.extra_metadata or {}).get("draftInfo") if isinstance(row.extra_metadata, dict) else None,
                }
            )
            row.recipe = next_recipe
            row.extra_metadata = metadata
            session.add(row)
            self._record_business_operation(
                session=session,
                action="update_draft_recipe",
                target_type="business_capability",
                target_id=row.id,
                business_key=row.business_key,
                actor=actor,
                note=payload.note,
                before_payload=before_payload,
                after_payload=self._json_safe_payload({"recipe": next_recipe, "draftInfo": draft_info}),
            )
            session.commit()
            session.refresh(row)
            return self._capability_to_dict(row, session=session)

    def validate_capability_draft(self, draft_id: str) -> dict[str, Any]:
        with get_session() as session:
            row = session.get(BusinessCapability, draft_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
            if row.is_default or row.status != "draft":
                raise HTTPException(status_code=409, detail="BUSINESS_DRAFT_ONLY_EDITABLE")
            draft_payload = self._capability_to_dict(row, session=session)
            default_row = (
                session.execute(
                    select(BusinessCapability)
                    .where(
                        BusinessCapability.business_key == row.business_key,
                        BusinessCapability.is_default.is_(True),
                        BusinessCapability.id != row.id,
                    )
                    .order_by(BusinessCapability.updated_at.desc(), BusinessCapability.created_at.desc())
                )
                .scalars()
                .first()
            )
            default_payload = self._capability_to_dict(default_row, session=session) if default_row else None
            before_recipe = default_row.recipe if default_row and isinstance(default_row.recipe, dict) else {}
            after_recipe = row.recipe if isinstance(row.recipe, dict) else {}
            diff_summary = self._recipe_diff_summary(before_recipe, after_recipe)
            checks = self._build_draft_publish_checks(draft_payload)
            can_publish = all(bool(item.get("passed")) for item in checks if item.get("level") == "blocker")
            next_action = None
            for item in checks:
                if item.get("level") == "blocker" and not item.get("passed"):
                    next_action = str(item.get("action") or "")
                    break
            return {
                "draft": draft_payload,
                "default_capability": default_payload,
                "can_publish": can_publish,
                "checks": checks,
                "diff_summary": diff_summary,
                "release_gate": {
                    "status": "ready" if can_publish else "blocked",
                    "label": "草稿可发布" if can_publish else "草稿暂不能发布",
                    "canPublish": can_publish,
                    "blockers": [item["code"] for item in checks if item.get("level") == "blocker" and not item.get("passed")],
                    "warnings": [item["code"] for item in checks if item.get("level") == "warning" and not item.get("passed")],
                },
                "next_action": next_action,
            }

    def publish_capability_draft(
        self,
        draft_id: str,
        payload: BusinessCapabilityDraftPublishRequest | None = None,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        request = payload or BusinessCapabilityDraftPublishRequest()
        validation = self.validate_capability_draft(draft_id)
        if not validation.get("can_publish"):
            raise HTTPException(status_code=409, detail="BUSINESS_RELEASE_GATE_BLOCKED")
        return self.promote_capability(
            draft_id,
            BusinessCapabilityPromoteRequest(activate=True, note=request.note or "草稿验证通过，发布为默认版本"),
            actor=actor,
        )

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

    def prepare_text_fission_prompt(
        self,
        *,
        payload: TextFissionPromptRequest,
        user: User | None,
    ) -> dict[str, Any]:
        image_url = self._first_string(payload.imageUrl, payload.url)
        if not image_url:
            raise HTTPException(status_code=400, detail="BUSINESS_IMAGE_URL_REQUIRED")
        metadata = dict(payload.metadata or {})
        if payload.source:
            metadata["source"] = payload.source
        if payload.channel:
            metadata["channel"] = payload.channel
        if payload.traceId:
            metadata["traceId"] = payload.traceId
        if payload.requestId:
            metadata["requestId"] = payload.requestId
        if payload.tenantId:
            metadata["tenantId"] = payload.tenantId
        if payload.clientId:
            metadata["clientId"] = payload.clientId
        metadata.update(
            {
                "businessKey": "text_fission",
                "businessStep": "prompt_draft",
                "interfacePack": "19_2026-05-19_text2img_user_editable_vl_pack_v2",
            }
        )
        inputs: dict[str, Any] = {"image_url": image_url}
        if payload.provider:
            inputs["provider"] = payload.provider
        if payload.prompt:
            inputs["instruction"] = payload.prompt
        try:
            response = ability_invocation_service.invoke(
                ability_id="vl_text2img_prompt_draft",
                payload=AbilityInvokeRequest(inputs=inputs, imageUrl=image_url, metadata=metadata),
                user=user,
                source="business:text_fission_prompt",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Text fission prompt preparation failed")
            raise HTTPException(status_code=500, detail="TEXT_FISSION_PROMPT_PREPARE_FAILED") from exc

        structured = self._extract_text_fission_structured_response(response.raw, response.texts)
        text_items = self._normalize_text_fission_items(
            structured.get("text_items"),
            structured.get("textItems"),
            structured.get("text_content"),
            structured.get("textContent"),
            (structured.get("text2imgPromptDraft") or {}).get("text_items")
            if isinstance(structured.get("text2imgPromptDraft"), dict)
            else None,
        )
        route_decision = self._resolve_text_fission_route_decision(structured=structured, text_items=text_items)
        can_use_text2img = self._resolve_text_fission_can_use_text2img(
            structured=structured,
            route_decision=route_decision,
        )
        editable_prompt_cn = self._first_string(
            structured.get("editable_prompt_cn"),
            structured.get("editablePromptCn"),
            (structured.get("text2imgPromptDraft") or {}).get("editable_prompt_cn")
            if isinstance(structured.get("text2imgPromptDraft"), dict)
            else None,
        )
        editable_prompt = self._first_string(
            editable_prompt_cn,
            structured.get("editable_prompt"),
            structured.get("editablePrompt"),
            (structured.get("text2imgPromptDraft") or {}).get("editable_prompt")
            if isinstance(structured.get("text2imgPromptDraft"), dict)
            else None,
        )
        if not editable_prompt:
            raise HTTPException(status_code=500, detail="TEXT_FISSION_PROMPT_EMPTY")
        editable_negative_cn = self._first_string(
            structured.get("editable_negative_prompt_cn"),
            structured.get("editableNegativePromptCn"),
            (structured.get("text2imgPromptDraft") or {}).get("editable_negative_prompt_cn")
            if isinstance(structured.get("text2imgPromptDraft"), dict)
            else None,
        )
        editable_negative = self._first_string(
            editable_negative_cn,
            structured.get("editable_negative_prompt"),
            structured.get("editableNegativePrompt"),
            (structured.get("text2imgPromptDraft") or {}).get("editable_negative_prompt")
            if isinstance(structured.get("text2imgPromptDraft"), dict)
            else None,
        )
        return {
            "promptDraftId": response.requestId,
            "status": response.status,
            "imageUrl": image_url,
            "editablePrompt": editable_prompt,
            "editablePromptCn": editable_prompt_cn,
            "editableNegativePrompt": editable_negative,
            "editableNegativePromptCn": editable_negative_cn,
            "textContent": self._display_text_content(
                [item.get("text") for item in text_items],
                structured.get("text_content"),
                structured.get("textContent"),
            ),
            "textItems": text_items,
            "routeDecision": route_decision,
            "routeReason": self._resolve_text_fission_route_reason(
                structured=structured,
                route_decision=route_decision,
                text_count=len(text_items),
            ),
            "canUseText2Img": can_use_text2img,
            "textCount": self._resolve_text_fission_text_count(structured=structured, text_items=text_items),
            "promptProfile": structured.get("prompt_profile") or structured.get("promptProfile"),
            "layoutCard": structured.get("layout_card") or structured.get("layoutCard"),
            "paletteCard": structured.get("palette_card") or structured.get("paletteCard"),
            "riskNotes": structured.get("risk_notes") or structured.get("riskNotes"),
            "vlResult": structured,
            "traceId": response.requestId,
        }

    def list_runs(
        self,
        *,
        limit: int = 50,
        window_hours: int | None = None,
        detail: str = "summary",
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
    ) -> tuple[int, list[dict[str, Any]]]:
        with get_session() as session:
            id_stmt = select(BusinessRun.id)
            count_stmt = select(func.count(BusinessRun.id))
            filters = []
            normalized_issue_category = self._normalize_issue_category(issue_category)
            if window_hours:
                since = datetime.utcnow() - timedelta(hours=max(1, min(int(window_hours), 24 * 90)))
                filters.append(BusinessRun.created_at >= since)
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
                id_stmt = id_stmt.where(*filters)
                count_stmt = count_stmt.where(*filters)
            if billing_status:
                status_filter = self._billing_status_filter(billing_status)
                if status_filter is not None:
                    id_stmt = id_stmt.where(status_filter)
                    count_stmt = count_stmt.where(status_filter)
            normalized_limit = max(1, min(limit, 1000))
            if normalized_issue_category:
                # Issue category is derived from payloads, so first scan recent narrow IDs
                # instead of sorting full JSON rows. This avoids MySQL sort buffer errors.
                scan_limit = min(max(normalized_limit * 10, 200), 2000)
                run_ids = (
                    session.execute(id_stmt.order_by(BusinessRun.created_at.desc()).limit(scan_limit))
                    .scalars()
                    .all()
                )
                rows = self._load_runs_by_ids(session, run_ids)
                matched_rows = [
                    row
                    for row in rows
                    if self._build_run_issue_summary(row, session=session)["category"] == normalized_issue_category
                ]
                items = [
                    self._run_to_dict(row, session=session)
                    for row in matched_rows
                ]
                if detail != "full":
                    return len(items), [
                        self._run_to_summary_dict(row, session=session)
                        for row in matched_rows[:normalized_limit]
                    ]
                return len(items), items[:normalized_limit]
            total = int(session.scalar(count_stmt) or 0)
            run_ids = (
                session.execute(id_stmt.order_by(BusinessRun.created_at.desc()).limit(normalized_limit))
                .scalars()
                .all()
            )
            if detail == "full":
                rows = self._load_runs_by_ids(session, run_ids)
                return total, [self._run_to_dict(row, session=session) for row in rows]
            rows = self._load_run_summaries_by_ids(session, run_ids)
            return total, [self._run_to_summary_dict(row, session=session) for row in rows]

    def _load_runs_by_ids(self, session, run_ids: list[str]) -> list[BusinessRun]:
        rows: list[BusinessRun] = []
        for run_id in run_ids:
            row = session.get(BusinessRun, run_id)
            if row:
                rows.append(row)
        return rows

    def _load_run_summaries_by_ids(self, session, run_ids: list[str]) -> list[BusinessRun]:
        if not run_ids:
            return []
        rows = (
            session.execute(
                select(BusinessRun)
                .options(
                    load_only(
                        BusinessRun.id,
                        BusinessRun.business_key,
                        BusinessRun.business_version_id,
                        BusinessRun.version,
                        BusinessRun.status,
                        BusinessRun.source,
                        BusinessRun.channel,
                        BusinessRun.trace_id,
                        BusinessRun.request_id,
                        BusinessRun.tenant_id,
                        BusinessRun.client_id,
                        BusinessRun.user_id,
                        BusinessRun.user_name,
                        BusinessRun.ability_id,
                        BusinessRun.ability_task_id,
                        BusinessRun.ability_log_id,
                        BusinessRun.request_payload,
                        BusinessRun.result_payload,
                        BusinessRun.image_urls,
                        BusinessRun.video_urls,
                        BusinessRun.texts,
                        BusinessRun.error_message,
                        BusinessRun.duration_ms,
                        BusinessRun.billing_unit,
                        BusinessRun.unit_price,
                        BusinessRun.currency,
                        BusinessRun.cost_amount,
                        BusinessRun.quota_units,
                        BusinessRun.cost_breakdown,
                        BusinessRun.callback_url,
                        BusinessRun.callback_status,
                        BusinessRun.callback_http_status,
                        BusinessRun.callback_error,
                        BusinessRun.debug_url,
                        BusinessRun.created_at,
                        BusinessRun.updated_at,
                        BusinessRun.started_at,
                        BusinessRun.finished_at,
                    )
                )
                .where(BusinessRun.id.in_(run_ids))
            )
            .scalars()
            .all()
        )
        by_id = {row.id: row for row in rows}
        return [by_id[run_id] for run_id in run_ids if run_id in by_id]

    def _load_usage_run_summaries_by_ids(self, session, run_ids: list[str]) -> list[BusinessRun]:
        if not run_ids:
            return []
        rows = (
            session.execute(
                select(BusinessRun)
                .options(
                    load_only(
                        BusinessRun.id,
                        BusinessRun.business_key,
                        BusinessRun.business_version_id,
                        BusinessRun.version,
                        BusinessRun.status,
                        BusinessRun.source,
                        BusinessRun.channel,
                        BusinessRun.trace_id,
                        BusinessRun.request_id,
                        BusinessRun.tenant_id,
                        BusinessRun.client_id,
                        BusinessRun.user_id,
                        BusinessRun.user_name,
                        BusinessRun.ability_id,
                        BusinessRun.ability_task_id,
                        BusinessRun.ability_log_id,
                        BusinessRun.image_urls,
                        BusinessRun.video_urls,
                        BusinessRun.texts,
                        BusinessRun.error_message,
                        BusinessRun.duration_ms,
                        BusinessRun.billing_unit,
                        BusinessRun.unit_price,
                        BusinessRun.currency,
                        BusinessRun.cost_amount,
                        BusinessRun.quota_units,
                        BusinessRun.callback_url,
                        BusinessRun.callback_status,
                        BusinessRun.callback_http_status,
                        BusinessRun.callback_error,
                        BusinessRun.debug_url,
                        BusinessRun.created_at,
                        BusinessRun.updated_at,
                        BusinessRun.started_at,
                        BusinessRun.finished_at,
                    )
                )
                .where(BusinessRun.id.in_(run_ids))
            )
            .scalars()
            .all()
        )
        by_id = {row.id: row for row in rows}
        return [by_id[run_id] for run_id in run_ids if run_id in by_id]

    def _load_usage_steps_by_run(self, session, run_ids: list[str]) -> dict[str, list[BusinessRunStep]]:
        if not run_ids:
            return {}
        steps_by_run: dict[str, list[BusinessRunStep]] = {}
        chunk_size = 900
        for offset in range(0, len(run_ids), chunk_size):
            chunk = run_ids[offset : offset + chunk_size]
            rows = (
                session.execute(
                    select(BusinessRunStep)
                    .options(
                        load_only(
                            BusinessRunStep.id,
                            BusinessRunStep.run_id,
                            BusinessRunStep.step_order,
                            BusinessRunStep.step_id,
                            BusinessRunStep.step_type,
                            BusinessRunStep.role,
                            BusinessRunStep.display_name,
                            BusinessRunStep.status,
                            BusinessRunStep.ability_id,
                            BusinessRunStep.ability_name,
                            BusinessRunStep.ability_provider,
                            BusinessRunStep.ability_task_id,
                            BusinessRunStep.request_payload,
                            BusinessRunStep.result_payload,
                            BusinessRunStep.error_message,
                            BusinessRunStep.duration_ms,
                            BusinessRunStep.started_at,
                            BusinessRunStep.finished_at,
                            BusinessRunStep.created_at,
                        )
                    )
                    .where(BusinessRunStep.run_id.in_(chunk))
                    .order_by(BusinessRunStep.run_id.asc(), BusinessRunStep.step_order.asc(), BusinessRunStep.id.asc())
                )
                .scalars()
                .all()
            )
            for row in rows:
                steps_by_run.setdefault(row.run_id, []).append(row)
        return steps_by_run

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
        key = self._dashboard_cache_key(
            "usage_summary",
            max(1, min(int(window_hours or 24), 24 * 90)),
            business_key,
            status,
            issue_category,
            version,
            source,
            tenant_id,
            client_id,
            trace_id,
        )
        return self._dashboard_cached(
            key,
            lambda: self._usage_summary_uncached(
                window_hours=window_hours,
                business_key=business_key,
                status=status,
                issue_category=issue_category,
                version=version,
                source=source,
                tenant_id=tenant_id,
                client_id=client_id,
                trace_id=trace_id,
            ),
        )

    def _usage_summary_uncached(
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
        unresolved_by_business: list[dict[str, Any]] = []
        recent_unresolved_issues: list[dict[str, Any]] = []
        normalized_issue_category = self._normalize_issue_category(issue_category)
        with get_session() as session:
            id_stmt = select(BusinessRun.id).where(BusinessRun.created_at >= since)
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
                id_stmt = id_stmt.where(*filters)
            run_ids = (
                session.execute(id_stmt.order_by(BusinessRun.created_at.desc()).limit(10000))
                .scalars()
                .all()
            )
            rows = self._load_usage_run_summaries_by_ids(session, run_ids)
            issue_summaries = {
                row.id: self._build_usage_run_issue_summary(row)
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
            unresolved_by_business = self._usage_unresolved_business_buckets(
                rows,
                issue_summaries,
                session=session,
            )
            recent_unresolved_issues = self._recent_unresolved_issue_items(
                rows,
                issue_summaries,
                session=session,
            )
            flow_run_ids = [row.id for row in rows[:BUSINESS_USAGE_FLOW_EVIDENCE_RUN_LIMIT]]
            flow_rows = self._load_run_summaries_by_ids(session, flow_run_ids)
            steps_by_run = self._load_usage_steps_by_run(session, flow_run_ids)
            flow_evidence = self._usage_flow_evidence(flow_rows, steps_by_run)

        usage_billing_status = self._business_billing_status_for_usage_summary
        summary = self._summarize_usage_bucket(
            "all",
            "全部业务",
            rows,
            billing_status_func=usage_billing_status,
        )
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
            "by_business": self._usage_buckets(
                rows,
                lambda row: row.business_key or "unknown",
                billing_status_func=usage_billing_status,
            ),
            "by_source": self._usage_buckets(
                rows,
                lambda row: row.source or "business-api",
                billing_status_func=usage_billing_status,
            ),
            "by_tenant": self._usage_buckets(
                rows,
                lambda row: row.tenant_id or "未标记业务方",
                billing_status_func=usage_billing_status,
            ),
            "by_client": self._usage_buckets(
                rows,
                lambda row: row.client_id or "未标记客户端",
                billing_status_func=usage_billing_status,
            ),
            "by_version": self._usage_buckets(
                rows,
                lambda row: f"{row.business_key or 'unknown'}:{row.version or '未标记版本'}",
                label_func=lambda key: key.replace(":", " · ", 1),
                billing_status_func=usage_billing_status,
            ),
            "by_issue": self._usage_issue_buckets(
                rows,
                issue_summaries,
                billing_status_func=usage_billing_status,
            ),
            "unresolved_issues": unresolved_issues,
            "unresolved_by_business": unresolved_by_business,
            "recent_unresolved_issues": recent_unresolved_issues,
            "recent_failures": recent_failures,
            "flow_evidence": flow_evidence,
        }

    def _usage_buckets(
        self,
        rows: list[BusinessRun],
        key_func,
        label_func=None,
        billing_status_func=None,
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[BusinessRun]] = {}
        for row in rows:
            key = str(key_func(row) or "unknown").strip() or "unknown"
            groups.setdefault(key, []).append(row)
        buckets = [
            self._summarize_usage_bucket(
                key,
                str(label_func(key) if label_func else key),
                group,
                billing_status_func=billing_status_func,
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
        *,
        billing_status_func=None,
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[BusinessRun]] = {}
        for row in rows:
            summary = issue_summaries.get(row.id) or self._build_run_issue_summary(row)
            key = str(summary.get("category") or "none")
            groups.setdefault(key, []).append(row)
        buckets: list[dict[str, Any]] = []
        for key, group in groups.items():
            issue = self._issue_category_meta(key)
            bucket = self._summarize_usage_bucket(
                key,
                issue["label"],
                group,
                billing_status_func=billing_status_func,
            )
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

    def _usage_flow_evidence(
        self,
        rows: list[BusinessRun],
        steps_by_run: dict[str, list[BusinessRunStep]],
    ) -> dict[str, Any]:
        stage_events: dict[str, list[dict[str, Any]]] = {key: [] for key in BUSINESS_FLOW_STAGE_ORDER}
        route_groups: dict[str, dict[str, Any]] = {}
        candidate_groups: dict[str, dict[str, Any]] = {}
        lora_groups: dict[str, dict[str, Any]] = {}
        workflow_groups: dict[str, dict[str, Any]] = {}

        for row in rows:
            steps = steps_by_run.get(row.id, [])
            route = self._usage_flow_route_info(row)
            selected_by = self._first_string(route.get("selectedBy")) or "default"
            selected_capability_id = self._first_string(route.get("selectedCapabilityId"), route.get("businessVersionId"))
            selected_version = self._first_string(route.get("version"), row.version)
            lora_name = self._usage_flow_extract_value(
                [route, row.request_payload, row.result_payload, *self._usage_flow_step_payloads(steps)],
                BUSINESS_FLOW_LORA_KEYS,
            )
            workflow_key = self._usage_flow_extract_value(
                [route, row.request_payload, row.result_payload, *self._usage_flow_step_payloads(steps)],
                BUSINESS_FLOW_WORKFLOW_KEYS,
            )

            duration_by_stage: dict[str, int] = {}
            step_counts_by_stage: dict[str, int] = {}
            for step in steps:
                stage_key = self._usage_flow_stage_for_step(step)
                if not stage_key:
                    continue
                step_counts_by_stage[stage_key] = step_counts_by_stage.get(stage_key, 0) + 1
                duration_ms = self._usage_flow_duration_ms(
                    self._first_int(step.duration_ms),
                    self._calculate_duration_ms(step.started_at, step.finished_at),
                )
                if duration_ms is not None:
                    duration_by_stage[stage_key] = duration_by_stage.get(stage_key, 0) + duration_ms

            queue_duration_ms = self._usage_flow_duration_ms(
                self._calculate_duration_ms(row.created_at, row.started_at)
            )
            primary_duration_ms = duration_by_stage.get("primary")
            if primary_duration_ms is None:
                primary_duration_ms = self._usage_flow_duration_ms(self._first_int(row.duration_ms))
            output_state = self._usage_flow_output_state(row)
            callback_state = self._usage_flow_callback_state(row)
            billing_state = self._business_billing_status(row)

            common_evidence = {
                "businessKey": row.business_key,
                "version": selected_version,
                "selectedBy": selected_by,
                "selectedCapabilityId": selected_capability_id,
                "loraName": lora_name,
                "workflowKey": workflow_key,
            }
            stage_events["entry"].append(
                self._usage_flow_record(
                    row,
                    duration_ms=queue_duration_ms,
                    evidence={**common_evidence, "source": row.source, "tenantId": row.tenant_id, "clientId": row.client_id},
                )
            )
            stage_events["version"].append(
                self._usage_flow_record(
                    row,
                    evidence={**common_evidence, "businessVersionId": row.business_version_id},
                )
            )
            stage_events["preprocess"].append(
                self._usage_flow_record(
                    row,
                    duration_ms=duration_by_stage.get("preprocess"),
                    evidence={**common_evidence, "stepCount": step_counts_by_stage.get("preprocess", 0)},
                )
            )
            stage_events["routing"].append(
                self._usage_flow_record(
                    row,
                    evidence=common_evidence,
                )
            )
            stage_events["primary"].append(
                self._usage_flow_record(
                    row,
                    duration_ms=primary_duration_ms,
                    evidence={**common_evidence, "stepCount": step_counts_by_stage.get("primary", 0)},
                )
            )
            stage_events["output"].append(
                self._usage_flow_record(
                    row,
                    duration_ms=duration_by_stage.get("output"),
                    evidence={
                        **common_evidence,
                        "outputState": output_state,
                        "imageCount": len(row.image_urls or []),
                        "videoCount": len(row.video_urls or []),
                        "textCount": len(row.texts or []),
                    },
                )
            )
            stage_events["callback-billing"].append(
                self._usage_flow_record(
                    row,
                    duration_ms=duration_by_stage.get("callback-billing"),
                    evidence={**common_evidence, "callbackState": callback_state, "billingState": billing_state},
                )
            )

            self._add_usage_flow_group(
                route_groups,
                selected_by,
                selected_by,
                row,
                duration_ms=primary_duration_ms,
                evidence=common_evidence,
            )
            if self._usage_flow_is_candidate_selector(selected_by):
                candidate_key = selected_capability_id or selected_version or selected_by
                candidate_label = f"{selected_by} · {selected_version or selected_capability_id or row.business_key}"
                self._add_usage_flow_group(
                    candidate_groups,
                    candidate_key,
                    candidate_label,
                    row,
                    duration_ms=primary_duration_ms,
                    evidence=common_evidence,
                )
            if lora_name:
                self._add_usage_flow_group(
                    lora_groups,
                    lora_name,
                    lora_name,
                    row,
                    duration_ms=primary_duration_ms,
                    evidence=common_evidence,
                )
            if workflow_key:
                self._add_usage_flow_group(
                    workflow_groups,
                    workflow_key,
                    workflow_key,
                    row,
                    duration_ms=primary_duration_ms,
                    evidence=common_evidence,
                )

        return {
            "stage_evidence": [
                self._summarize_usage_flow_records(key, BUSINESS_FLOW_STAGE_LABELS.get(key, key), stage_events.get(key, []))
                for key in BUSINESS_FLOW_STAGE_ORDER
            ],
            "route_hits": self._usage_flow_group_buckets(route_groups),
            "candidate_hits": self._usage_flow_group_buckets(candidate_groups),
            "lora_hits": self._usage_flow_group_buckets(lora_groups),
            "workflow_hits": self._usage_flow_group_buckets(workflow_groups),
        }

    def _usage_flow_group_buckets(self, groups: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        buckets = [
            self._summarize_usage_flow_records(
                key,
                str(group.get("label") or key),
                group.get("events") or [],
            )
            for key, group in groups.items()
        ]
        return sorted(
            buckets,
            key=lambda item: (int(item.get("total") or 0), item.get("latest_at") or datetime.min),
            reverse=True,
        )[:20]

    def _summarize_usage_flow_records(
        self,
        key: str,
        label: str,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        statuses = {
            "succeeded": 0,
            "failed": 0,
            "running": 0,
            "queued": 0,
            "cancelled": 0,
        }
        durations: list[int] = []
        latest_at: datetime | None = None
        sample_run_ids: list[str] = []
        evidence_counts: dict[str, dict[str, int]] = {}
        for event in events:
            row = event.get("row")
            if not isinstance(row, BusinessRun):
                continue
            status = str(row.status or "").strip().lower()
            if status in statuses:
                statuses[status] += 1
            duration_ms = self._usage_flow_duration_ms(event.get("duration_ms"))
            if duration_ms is not None:
                durations.append(duration_ms)
            if row.created_at and (latest_at is None or row.created_at > latest_at):
                latest_at = row.created_at
            if len(sample_run_ids) < 3 and row.id:
                sample_run_ids.append(row.id)
            evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else {}
            for field in ("businessKey", "selectedBy", "version", "loraName", "workflowKey", "outputState", "callbackState", "billingState"):
                value = self._usage_flow_text(evidence.get(field))
                if not value:
                    continue
                field_counts = evidence_counts.setdefault(field, {})
                field_counts[value] = field_counts.get(value, 0) + 1

        total = len(events)
        durations_sorted = sorted(durations)
        p95_duration_ms = None
        if durations_sorted:
            index = min(len(durations_sorted) - 1, max(0, math.ceil(len(durations_sorted) * 0.95) - 1))
            p95_duration_ms = durations_sorted[index]
        return {
            "key": key,
            "label": label,
            "total": total,
            **statuses,
            "success_rate": round(statuses["succeeded"] / total, 4) if total else None,
            "avg_duration_ms": int(sum(durations) / len(durations)) if durations else None,
            "p95_duration_ms": p95_duration_ms,
            "latest_at": latest_at,
            "evidence": {
                "durationSamples": len(durations),
                "sampleRunIds": sample_run_ids,
                "top": {
                    field: self._usage_flow_top_counts(counts)
                    for field, counts in evidence_counts.items()
                    if counts
                },
            },
        }

    @staticmethod
    def _usage_flow_top_counts(counts: dict[str, int]) -> list[dict[str, Any]]:
        return [
            {"key": key, "total": total}
            for key, total in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:5]
        ]

    @staticmethod
    def _usage_flow_record(
        row: BusinessRun,
        *,
        duration_ms: Any | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"row": row, "duration_ms": duration_ms, "evidence": evidence or {}}

    def _add_usage_flow_group(
        self,
        groups: dict[str, dict[str, Any]],
        key: str | None,
        label: str | None,
        row: BusinessRun,
        *,
        duration_ms: Any | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        normalized_key = self._usage_flow_text(key)
        if not normalized_key:
            return
        group = groups.setdefault(normalized_key, {"label": label or normalized_key, "events": []})
        group["events"].append(self._usage_flow_record(row, duration_ms=duration_ms, evidence=evidence))

    @staticmethod
    def _usage_flow_is_candidate_selector(selected_by: str | None) -> bool:
        normalized = str(selected_by or "").strip().lower()
        return normalized in BUSINESS_FLOW_CANDIDATE_SELECTORS or "candidate" in normalized or "draft" in normalized

    def _usage_flow_route_info(self, row: BusinessRun) -> dict[str, Any]:
        request_payload = row.request_payload if isinstance(row.request_payload, dict) else {}
        result_payload = row.result_payload if isinstance(row.result_payload, dict) else {}
        route: dict[str, Any] = {}
        for payload in (request_payload, result_payload):
            for key in ("_route", "routeInfo", "route_info", "routing", "route"):
                value = payload.get(key)
                if isinstance(value, dict):
                    route.update(value)
        selected_capability_id = self._first_string(
            route.get("selectedCapabilityId"),
            route.get("selected_capability_id"),
            route.get("businessVersionId"),
            route.get("business_version_id"),
            row.business_version_id,
        )
        return {
            **route,
            "businessKey": self._first_string(route.get("businessKey"), route.get("business_key"), row.business_key),
            "businessVersionId": self._first_string(
                route.get("businessVersionId"),
                route.get("business_version_id"),
                row.business_version_id,
                selected_capability_id,
            ),
            "selectedCapabilityId": selected_capability_id,
            "version": self._first_string(route.get("version"), route.get("selectedVersion"), route.get("selected_version"), row.version),
            "selectedBy": self._first_string(route.get("selectedBy"), route.get("selected_by")) or "default",
        }

    def _usage_flow_stage_for_step(self, step: BusinessRunStep) -> str | None:
        normalized_type = str(step.step_type or "").strip().lower()
        normalized_role = str(step.role or "").strip().lower()
        trace_type = self._trace_step_type(normalized_type, normalized_role)
        if trace_type == "vl":
            return "preprocess"
        if trace_type == "generation":
            return "primary"
        if trace_type == "score" or normalized_role in {"output", "result"}:
            return "output"
        if trace_type == "callback" or normalized_role in {"callback", "billing"} or normalized_type in {"billing", "settlement"}:
            return "callback-billing"
        if any(token in normalized_type for token in ("oss", "ingest", "result", "output")):
            return "output"
        return None

    @staticmethod
    def _usage_flow_step_payloads(steps: list[BusinessRunStep]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for step in steps:
            if isinstance(step.request_payload, dict):
                payloads.append(step.request_payload)
            if isinstance(step.result_payload, dict):
                payloads.append(step.result_payload)
        return payloads

    def _usage_flow_extract_value(self, values: list[Any], target_keys: set[str]) -> str | None:
        normalized_targets = {self._usage_flow_key(key) for key in target_keys}
        for value in values:
            found = self._usage_flow_find_nested_value(value, normalized_targets)
            text = self._usage_flow_text(found)
            if text:
                return text
        return None

    def _usage_flow_find_nested_value(self, value: Any, target_keys: set[str], depth: int = 0) -> Any | None:
        if value in (None, "", []):
            return None
        if depth > 5:
            return None
        if isinstance(value, dict):
            for key, item in value.items():
                if self._usage_flow_key(key) in target_keys:
                    text = self._usage_flow_text(item)
                    if text:
                        return text
                    nested = self._usage_flow_find_nested_value(item, target_keys, depth + 1)
                    if nested not in (None, "", []):
                        return nested
            for item in value.values():
                nested = self._usage_flow_find_nested_value(item, target_keys, depth + 1)
                if nested not in (None, "", []):
                    return nested
        if isinstance(value, list):
            for item in value:
                nested = self._usage_flow_find_nested_value(item, target_keys, depth + 1)
                if nested not in (None, "", []):
                    return nested
        return None

    @staticmethod
    def _usage_flow_key(value: Any) -> str:
        return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())

    @staticmethod
    def _usage_flow_text(value: Any) -> str | None:
        if value in (None, "", []):
            return None
        if isinstance(value, (list, tuple)):
            for item in value:
                text = BusinessRunService._usage_flow_text(item)
                if text:
                    return text
            return None
        if isinstance(value, dict):
            for key in ("name", "file", "filename", "value", "key", "id"):
                text = BusinessRunService._usage_flow_text(value.get(key))
                if text:
                    return text
            return None
        text = str(value).strip()
        if not text or text.lower() in {"none", "null", "undefined"}:
            return None
        return text[:160]

    @staticmethod
    def _usage_flow_duration_ms(*values: Any) -> int | None:
        for value in values:
            if value in (None, ""):
                continue
            try:
                duration = int(float(value))
            except (TypeError, ValueError):
                continue
            if duration >= 0:
                return duration
        return None

    def _usage_flow_output_state(self, row: BusinessRun) -> str:
        if (row.image_urls or []) or (row.video_urls or []) or (row.texts or []):
            return "stored"
        result_payload = row.result_payload if isinstance(row.result_payload, dict) else {}
        if self._count_structured_outputs(result_payload) or self._count_resource_outputs(result_payload):
            return "structured"
        if str(row.status or "").lower() == "succeeded":
            return "missing"
        return "pending"

    @staticmethod
    def _usage_flow_callback_state(row: BusinessRun) -> str:
        callback_status = str(row.callback_status or "").strip().lower()
        if callback_status:
            return callback_status
        if row.callback_error:
            return "failed"
        if row.callback_url:
            return "missing"
        return "none"

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
            if self._has_later_successful_business_run(row, rows):
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

    def _usage_unresolved_business_buckets(
        self,
        rows: list[BusinessRun],
        issue_summaries: dict[str, dict[str, Any]],
        *,
        session,
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[BusinessRun]] = {}
        category_counts_by_business: dict[str, dict[str, int]] = {}
        for row in rows:
            summary = issue_summaries.get(row.id) or self._build_run_issue_summary(row, session=session)
            category = str(summary.get("category") or "none")
            if category == "none" or self._extract_retest_source_run_id(row):
                continue
            if self._has_later_successful_business_run(row, rows):
                continue
            if self._build_retest_summary(row, session=session).get("recovered"):
                continue
            key = str(row.business_key or "unknown").strip() or "unknown"
            groups.setdefault(key, []).append(row)
            category_counts = category_counts_by_business.setdefault(key, {})
            category_counts[category] = category_counts.get(category, 0) + 1

        buckets: list[dict[str, Any]] = []
        for key, group in groups.items():
            bucket = self._summarize_usage_bucket(key, key, group)
            category_counts = category_counts_by_business.get(key) or {}
            top_category = max(category_counts.items(), key=lambda item: item[1])[0] if category_counts else "none"
            issue = self._issue_category_meta(top_category)
            bucket.update(
                {
                    "severity": issue["severity"],
                    "action": issue["action"],
                }
            )
            buckets.append(bucket)
        return sorted(
            buckets,
            key=lambda item: (int(item.get("total") or 0), item.get("latest_at") or datetime.min),
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
            if self._has_later_successful_business_run(row, rows):
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

    def _has_later_successful_business_run(self, row: BusinessRun, rows: list[BusinessRun]) -> bool:
        """Treat an old failed sample as recovered when the same business version later succeeds."""
        if not row.created_at:
            return False
        business_key = str(row.business_key or "").strip()
        version = str(row.version or "").strip()
        if not business_key or not version:
            return False
        for candidate in rows:
            if candidate.id == row.id:
                continue
            if str(candidate.business_key or "").strip() != business_key:
                continue
            if str(candidate.version or "").strip() != version:
                continue
            if not candidate.created_at or candidate.created_at <= row.created_at:
                continue
            if str(candidate.status or "").lower() != "succeeded":
                continue
            if (candidate.image_urls or []) or (candidate.video_urls or []) or (candidate.texts or []):
                return True
        return False

    def _has_later_successful_business_run_in_db(self, row: BusinessRun, *, session=None) -> bool:
        """DB-backed version of the recovery check used by list metrics.

        The capabilities list can be called often from admin pages. Avoid
        loading every recent run just to find whether a failed sample later
        recovered.
        """
        if session is None or not row.created_at:
            return False
        business_key = str(row.business_key or "").strip()
        version = str(row.version or "").strip()
        if not business_key or not version:
            return False
        candidates = (
            session.execute(
                select(BusinessRun)
                .options(
                    load_only(
                        BusinessRun.id,
                        BusinessRun.image_urls,
                        BusinessRun.video_urls,
                        BusinessRun.texts,
                    )
                )
                .where(
                    BusinessRun.id != row.id,
                    BusinessRun.business_key == business_key,
                    BusinessRun.version == version,
                    BusinessRun.status == "succeeded",
                    BusinessRun.created_at > row.created_at,
                )
                .limit(50)
            )
            .scalars()
            .all()
        )
        return any((item.image_urls or []) or (item.video_urls or []) or (item.texts or []) for item in candidates)

    def _summarize_usage_bucket(
        self,
        key: str,
        label: str,
        rows: list[BusinessRun],
        *,
        billing_status_func=None,
    ) -> dict[str, Any]:
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
            billing_status = (billing_status_func or self._business_billing_status)(row)
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
        if not getattr(self, "_background_workers_enabled", True):
            raise HTTPException(status_code=503, detail="BACKGROUND_WORKERS_DISABLED")
        return self._create_run_internal(
            business_key=business_key,
            capability_id=None,
            payload=payload,
            user=user,
            source=source,
            allow_non_active_capability=False,
            selected_by="default",
        )

    def create_product_commercialization_run(
        self,
        *,
        payload: ProductCommercializationRequest,
        user: User | None,
        source: str = "business-api",
    ) -> dict[str, Any]:
        """Create a unified business run for the explicit product video cost action."""
        if not getattr(self, "_background_workers_enabled", True):
            raise HTTPException(status_code=503, detail="BACKGROUND_WORKERS_DISABLED")
        image_url = self._first_string(payload.productImageUrl)
        if not image_url:
            raise HTTPException(status_code=400, detail="PRODUCT_COMMERCIALIZATION_IMAGE_REQUIRED")

        request_payload = payload.model_dump(exclude_none=True, by_alias=False)
        run_id = uuid4().hex
        business_key = "product_commercialization"
        business_payload = BusinessRunCreateRequest(
            imageUrl=image_url,
            inputs=request_payload,
            source=payload.source or source,
            traceId=payload.traceId,
            requestId=payload.requestId,
            metadata={
                "source": payload.source or source,
                "productCommercialization": {
                    "action": "video_generate",
                    "contract": "business_run_v1",
                    "queryEndpoint": "/api/business/runs/get",
                },
            },
        )
        trace_context = self._resolve_trace_context(
            run_id=run_id,
            business_key=business_key,
            payload=business_payload,
            source=source,
            user=user,
        )
        request_payload["_trace"] = trace_context
        request_payload["_productCommercialization"] = {
            "action": "video_generate",
            "contract": "business_run_v1",
            "queryEndpoint": "/api/business/runs/get",
        }

        with get_session() as session:
            client_policy = self._check_business_client_policy(
                session=session,
                business_key=business_key,
                payload=business_payload,
                trace_context=trace_context,
            )
            if client_policy:
                request_payload["_businessClient"] = client_policy
            run = BusinessRun(
                id=run_id,
                business_key=business_key,
                business_version_id=None,
                version="product-commercialization-mvp-v1",
                status="queued",
                source=trace_context["source"],
                channel=trace_context.get("channel"),
                trace_id=trace_context["traceId"],
                request_id=trace_context["requestId"],
                tenant_id=trace_context.get("tenantId"),
                client_id=trace_context.get("clientId"),
                user_id=self._resolve_business_user_id(user=user, payload=business_payload, trace_context=trace_context),
                user_name=self._resolve_business_user_name(user=user, payload=business_payload),
                ability_id=None,
                request_payload=self._omit_large_fields(request_payload),
            )
            session.add(run)
            session.add(
                BusinessRunStep(
                    id=uuid4().hex,
                    run_id=run.id,
                    step_order=1,
                    step_id="product_commercialization_video",
                    step_type="product_commercialization_video",
                    role="primary",
                    display_name="产品商业化视频生成",
                    enabled=True,
                    status="queued",
                    request_payload=self._omit_large_fields(request_payload),
                )
            )
            project_context = get_business_project_service().link_run_to_project(
                session=session,
                run=run,
                payload=business_payload,
                trace_context=trace_context,
                user=user,
            )
            if project_context and isinstance(request_payload, dict):
                request_payload["_projectContext"] = project_context
                run.request_payload = self._omit_large_fields(request_payload)
            session.commit()
            session.refresh(run)
            result = self._run_to_dict(run, session=session)

        self._enqueue_product_commercialization_run(run_id=run_id, user_id=getattr(user, "id", None))
        return result

    def create_run_for_capability(
        self,
        *,
        capability_id: str,
        payload: BusinessRunCreateRequest,
        user: User | None,
        source: str = "admin-draft-run",
    ) -> BusinessRun:
        if not getattr(self, "_background_workers_enabled", True):
            raise HTTPException(status_code=503, detail="BACKGROUND_WORKERS_DISABLED")
        return self._create_run_internal(
            business_key=None,
            capability_id=capability_id,
            payload=payload,
            user=user,
            source=source,
            allow_non_active_capability=True,
            selected_by="admin_draft",
        )

    def _create_run_internal(
        self,
        *,
        business_key: str | None,
        capability_id: str | None,
        payload: BusinessRunCreateRequest,
        user: User | None,
        source: str,
        allow_non_active_capability: bool,
        selected_by: str,
    ) -> BusinessRun:
        payload_inputs = payload.inputs or {}

        with get_session() as session:
            ensure_default_abilities(session)
            ensure_default_business_capabilities(session)
            capability: BusinessCapability | None = None
            if capability_id:
                capability = session.get(BusinessCapability, capability_id)
                if not capability:
                    raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
                if business_key and capability.business_key != business_key:
                    raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
                if allow_non_active_capability:
                    if capability.status in {"disabled", "deprecated"}:
                        raise HTTPException(status_code=409, detail="BUSINESS_CAPABILITY_NOT_RUNNABLE")
                elif capability.status != "active":
                    raise HTTPException(status_code=404, detail="BUSINESS_CAPABILITY_NOT_FOUND")
                business_key = capability.business_key
            business_key = self._required_text(business_key, "BUSINESS_KEY_REQUIRED")

            if business_key == "fission_evaluate":
                image_url = self._first_string(
                    payload.originalImageUrl,
                    payload.imageUrl,
                    payload.url,
                    payload_inputs.get("original_image"),
                    payload_inputs.get("originalImageUrl"),
                    payload_inputs.get("imageUrl"),
                    payload_inputs.get("url"),
                )
                generated_image_url = self._first_string(
                    payload.generatedImageUrl,
                    payload_inputs.get("generated_image"),
                    payload_inputs.get("generatedImageUrl"),
                )
                if not image_url or not generated_image_url:
                    raise HTTPException(status_code=400, detail="VL_EVAL_IMAGE_REQUIRED")
            else:
                image_url = self._first_string(
                    payload.imageUrl,
                    payload.url,
                    payload_inputs.get("imageUrl"),
                    payload_inputs.get("url"),
                )
            if not image_url:
                raise HTTPException(status_code=400, detail="BUSINESS_IMAGE_URL_REQUIRED")
            if business_key == "text_fission":
                editable_prompt = self._first_string(
                    payload_inputs.get("editable_prompt"),
                    payload_inputs.get("editablePrompt"),
                    payload.editable_prompt,
                    payload.editablePrompt,
                    payload.prompt,
                    payload_inputs.get("prompt"),
                )
                if not editable_prompt:
                    raise HTTPException(status_code=400, detail="TEXT_FISSION_PROMPT_REQUIRED")
            if business_key == "image_edit":
                self._compile_image_edit_inputs(payload=payload, image_url=image_url, validate_media=True)
            if business_key == "product_design":
                self._compile_product_design_inputs(payload=payload, image_url=image_url)

            if capability is not None:
                route_info = self._route_info(capability, selected_by=selected_by)
            else:
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
            self._create_run_steps(session=session, run=run, recipe=recipe, payload=payload, business_key=business_key)
            project_context = get_business_project_service().link_run_to_project(
                session=session,
                run=run,
                payload=payload,
                trace_context=trace_context,
                user=user,
            )
            if project_context and isinstance(request_payload, dict):
                request_payload["_projectContext"] = project_context
                run.request_payload = request_payload
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
            recipe=recipe,
            include_image_edit_visual_hint=True,
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

    def _create_run_steps(
        self,
        *,
        session,
        run: BusinessRun,
        recipe: dict[str, Any],
        payload: BusinessRunCreateRequest | None = None,
        business_key: str | None = None,
    ) -> None:
        for order, step in enumerate(self._normalized_recipe_steps(recipe), start=1):
            ability_id = step.get("abilityId")
            ability = session.get(Ability, ability_id) if isinstance(ability_id, str) and ability_id else None
            enabled = step.get("enabled") is not False
            status = "planned" if enabled else "skipped"
            started_at = None
            finished_at = None
            duration_ms = None
            request_payload = None
            result_payload = None
            if enabled and self._is_text_fission_confirmed_prompt_step(
                business_key=business_key,
                payload=payload,
                step=step,
            ):
                status = "succeeded"
                now = datetime.utcnow()
                started_at = now
                finished_at = now
                duration_ms = 0
                request_payload = self._text_fission_prompt_step_request(payload)
                result_payload = self._text_fission_prompt_step_result(payload)
            row = BusinessRunStep(
                id=uuid4().hex,
                run_id=run.id,
                step_order=order,
                step_id=self._first_string(step.get("id")),
                step_type=self._first_string(step.get("type")) or "ability_task",
                role=self._first_string(step.get("role")),
                display_name=self._first_string(step.get("displayName")),
                enabled=enabled,
                status=status,
                ability_id=ability_id if isinstance(ability_id, str) else None,
                ability_name=ability.display_name if ability else None,
                ability_provider=ability.provider if ability else None,
                request_payload=request_payload,
                result_payload=result_payload,
                duration_ms=duration_ms,
                started_at=started_at,
                finished_at=finished_at,
            )
            session.add(row)

    def _is_text_fission_confirmed_prompt_step(
        self,
        *,
        business_key: str | None,
        payload: BusinessRunCreateRequest | None,
        step: dict[str, Any],
    ) -> bool:
        if business_key != "text_fission" or payload is None:
            return False
        step_id = str(step.get("id") or "").strip()
        step_type = str(step.get("type") or "").strip().lower()
        role = str(step.get("role") or "").strip().lower()
        if step_id != "prompt_draft" and step_type not in {"vl_analyze", "vl_analyze_image"} and role != "preprocess":
            return False
        payload_inputs = payload.inputs if isinstance(payload.inputs, dict) else {}
        editable_prompt = self._first_string(
            payload.editable_prompt,
            payload.editablePrompt,
            payload.prompt,
            payload_inputs.get("editable_prompt"),
            payload_inputs.get("editablePrompt"),
            payload_inputs.get("prompt"),
        )
        return bool(editable_prompt)

    def _text_fission_prompt_step_request(self, payload: BusinessRunCreateRequest | None) -> dict[str, Any] | None:
        if payload is None:
            return None
        payload_inputs = payload.inputs if isinstance(payload.inputs, dict) else {}
        route_decision = self._first_string(
            payload.routeDecision,
            payload.route_decision,
            payload_inputs.get("routeDecision"),
            payload_inputs.get("route_decision"),
        )
        request_payload = {
            "promptDraftId": self._first_string(payload.promptDraftId, payload_inputs.get("promptDraftId")),
            "routeDecision": route_decision,
            "textItems": self._normalize_text_fission_items(
                payload.textItems,
                payload.text_items,
                payload_inputs.get("textItems"),
                payload_inputs.get("text_items"),
            ),
        }
        return {key: value for key, value in request_payload.items() if value not in (None, "", [])}

    def _text_fission_prompt_step_result(self, payload: BusinessRunCreateRequest | None) -> dict[str, Any]:
        payload_inputs = payload.inputs if payload is not None and isinstance(payload.inputs, dict) else {}
        prompt = self._first_string(
            payload.editable_prompt if payload else None,
            payload.editablePrompt if payload else None,
            payload.prompt if payload else None,
            payload_inputs.get("editable_prompt"),
            payload_inputs.get("editablePrompt"),
            payload_inputs.get("prompt"),
        )
        negative_prompt = self._first_string(
            payload.editable_negative_prompt if payload else None,
            payload.editableNegativePrompt if payload else None,
            payload_inputs.get("editable_negative_prompt"),
            payload_inputs.get("editableNegativePrompt"),
        )
        route_decision = self._first_string(
            payload.routeDecision if payload else None,
            payload.route_decision if payload else None,
            payload_inputs.get("routeDecision"),
            payload_inputs.get("route_decision"),
        )
        result = {
            "status": "confirmed",
            "message": "用户已确认或直接提供生成提示词，本次出图不再重复执行 VL。",
            "editablePrompt": prompt,
            "editableNegativePrompt": negative_prompt,
            "routeDecision": route_decision,
            "textItems": self._normalize_text_fission_items(
                payload.textItems if payload else None,
                payload.text_items if payload else None,
                payload_inputs.get("textItems"),
                payload_inputs.get("text_items"),
            ),
        }
        return {key: value for key, value in result.items() if value not in (None, "", [])}

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

    def _enqueue_product_commercialization_run(self, *, run_id: str, user_id: str | None = None) -> bool:
        normalized_run_id = str(run_id or "").strip()
        if not normalized_run_id:
            return False
        with self._product_commercialization_lock:
            if normalized_run_id in self._product_commercialization_active_run_ids:
                return False
            self._product_commercialization_active_run_ids.add(normalized_run_id)

        def _target() -> None:
            try:
                self._execute_product_commercialization_run(run_id=normalized_run_id, user_id=user_id)
            except Exception as exc:  # pragma: no cover - defensive, execution should self-record
                logger.warning("product commercialization run worker failed: run_id=%s error=%s", normalized_run_id, exc)
            finally:
                with self._product_commercialization_lock:
                    self._product_commercialization_active_run_ids.discard(normalized_run_id)

        threading.Thread(target=_target, daemon=True).start()
        return True

    def _execute_product_commercialization_run(self, *, run_id: str, user_id: str | None = None) -> None:
        started_at = datetime.utcnow()
        with get_session() as session:
            run = session.get(BusinessRun, run_id)
            if not run or run.business_key != "product_commercialization":
                return
            if run.status in {"succeeded", "failed", "cancelled"}:
                return
            request_payload = dict(run.request_payload) if isinstance(run.request_payload, dict) else {}
            run.status = "running"
            run.started_at = run.started_at or started_at
            step = self._find_product_commercialization_step(session=session, run=run)
            if step:
                step.status = "running"
                step.started_at = step.started_at or run.started_at
                session.add(step)
            session.add(run)
            session.commit()

        clean_payload = {key: value for key, value in request_payload.items() if not str(key).startswith("_")}
        try:
            payload = ProductCommercializationRequest.model_validate(clean_payload)
        except ValidationError as exc:
            self._finish_product_commercialization_run(
                run_id=run_id,
                status="failed",
                started_at=started_at,
                error_message="PRODUCT_COMMERCIALIZATION_CONTEXT_INVALID",
                result_payload={"error": "PRODUCT_COMMERCIALIZATION_CONTEXT_INVALID", "validation": str(exc)[:500]},
            )
            return

        try:
            target_duration = int(payload.targetDurationSeconds or payload.durationSeconds or 8)
            segment_duration = int(payload.durationSeconds or 8)
            if target_duration > segment_duration:
                result = product_commercialization_service.generate_composed_video(payload, user_id=user_id)
            else:
                result = product_commercialization_service.generate_video(payload, user_id=user_id)
            video_urls = self._extract_product_commercialization_video_urls(result)
            result_status = str(result.get("status") or "").strip().lower()
            if result_status != "succeeded" or not video_urls:
                raise HTTPException(status_code=502, detail="PRODUCT_COMMERCIALIZATION_VIDEO_GENERATION_FAILED")
            self._finish_product_commercialization_run(
                run_id=run_id,
                status="succeeded",
                started_at=started_at,
                result_payload=result,
                video_urls=video_urls,
                texts=self._extract_product_commercialization_texts(result),
            )
        except Exception as exc:
            error_message = self._extract_error_message(exc)
            error_payload: dict[str, Any] = {"error": error_message}
            detail = getattr(exc, "detail", None)
            if isinstance(detail, dict):
                error_payload["detail"] = detail
            self._finish_product_commercialization_run(
                run_id=run_id,
                status="failed",
                started_at=started_at,
                error_message=error_message,
                result_payload=error_payload,
            )

    def _finish_product_commercialization_run(
        self,
        *,
        run_id: str,
        status: str,
        started_at: datetime,
        result_payload: dict[str, Any] | None = None,
        video_urls: list[str] | None = None,
        texts: list[str] | None = None,
        error_message: str | None = None,
    ) -> None:
        finished_at = datetime.utcnow()
        with get_session() as session:
            run = session.get(BusinessRun, run_id)
            if not run:
                return
            run.status = status
            run.result_payload = self._omit_large_fields(result_payload if isinstance(result_payload, dict) else {})
            run.video_urls = video_urls or None
            run.texts = texts or None
            run.error_message = error_message
            run.started_at = run.started_at or started_at
            run.finished_at = finished_at
            run.duration_ms = self._calculate_duration_ms(run.started_at, finished_at)
            step = self._find_product_commercialization_step(session=session, run=run)
            if step:
                step.status = status
                step.result_payload = run.result_payload
                step.error_message = error_message
                step.started_at = step.started_at or run.started_at
                step.finished_at = finished_at
                step.duration_ms = run.duration_ms
                session.add(step)
            session.add(run)
            session.commit()
        if status in {"succeeded", "failed", "cancelled"}:
            get_business_project_service().sync_run_outputs_to_project_assets(run_id)
            self._auto_settle_run_if_needed(run_id)
            self._deliver_callback(run_id)

    def _find_product_commercialization_step(self, *, session, run: BusinessRun) -> BusinessRunStep | None:
        return (
            session.execute(
                select(BusinessRunStep)
                .where(
                    BusinessRunStep.run_id == run.id,
                    BusinessRunStep.step_id == "product_commercialization_video",
                )
                .order_by(BusinessRunStep.step_order.asc())
            )
            .scalars()
            .first()
        )

    def _extract_product_commercialization_video_urls(self, result: dict[str, Any]) -> list[str]:
        urls: list[str] = []

        def add(value: Any) -> None:
            if isinstance(value, str) and value.strip().startswith(("http://", "https://")):
                urls.append(value.strip())
            elif isinstance(value, dict):
                for key in ("ossUrl", "storedUrl", "url"):
                    candidate = value.get(key)
                    if isinstance(candidate, str) and candidate.strip().startswith(("http://", "https://")):
                        urls.append(candidate.strip())
            elif isinstance(value, list):
                for item in value:
                    add(item)

        if isinstance(result, dict):
            video_result = result.get("videoResult")
            if isinstance(video_result, dict):
                add(video_result.get("videoUrls"))
                add(video_result.get("video_urls"))
                add(video_result.get("storedAssets"))
                add(video_result.get("stored_assets"))
            if not urls:
                add(result.get("videoUrls"))
                add(result.get("video_urls"))
        seen: set[str] = set()
        out: list[str] = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            out.append(url)
        return out

    @staticmethod
    def _extract_product_commercialization_texts(result: dict[str, Any]) -> list[str]:
        copy_package = result.get("copyPackage") if isinstance(result, dict) else None
        if not isinstance(copy_package, dict):
            return []
        values: list[str] = []
        for key in ("listingTitle", "detailDescription"):
            value = copy_package.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        for key in ("bulletPoints", "adShortCopy", "keywordPack"):
            value = copy_package.get(key)
            if isinstance(value, list):
                values.extend(str(item).strip() for item in value if str(item).strip())
        return values[:20]

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
            include_image_edit_visual_hint=True,
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
        try:
            self.finalize_run(run_id)
            with get_session() as session:
                row = session.get(BusinessRun, run_id)
                if not row:
                    raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
                if user and not self._can_user_access_run(row, user):
                    raise HTTPException(status_code=403, detail="BUSINESS_RUN_FORBIDDEN")
                return self._run_to_dict(row, session=session, include_api_usage=True)
        except HTTPException:
            raise
        except OperationalError:
            logger.exception("business run query temporarily unavailable: run_id=%s", run_id)
            raise HTTPException(status_code=503, detail="BUSINESS_RUN_TEMPORARY_UNAVAILABLE")

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
            should_resume_product_commercialization = (
                run.business_key == "product_commercialization"
                and not run.ability_task_id
                and run.status in {"queued", "running"}
            )
            should_submit_primary = (
                not should_resume_product_commercialization
                and not run.ability_task_id
                and run.status not in {"failed", "cancelled"}
            )
            session.commit()
            run_status = run.status
            terminal_after_sync = run.status in {"succeeded", "failed", "cancelled"}
        if should_resume_product_commercialization:
            self._enqueue_product_commercialization_run(run_id=run_id, user_id=None)
        if should_submit_primary:
            self._submit_primary_after_vl_if_ready(run_id=run_id, user=None)
            with get_session() as session:
                run = session.get(BusinessRun, run_id)
                run_status = run.status if run else run_status
                terminal_after_sync = bool(run and run.status in {"succeeded", "failed", "cancelled"})
        if terminal_after_sync:
            get_business_project_service().sync_run_outputs_to_project_assets(run_id)
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
            product_commercialization_ids = [
                row.id
                for row in rows
                if row.business_key == "product_commercialization"
                and not row.ability_task_id
                and row.status in {"queued", "running"}
            ]
            waiting_primary_ids = [
                row.id
                for row in rows
                if not row.ability_task_id and row.status not in {"failed", "cancelled", "succeeded"}
                and row.business_key != "product_commercialization"
            ]
        self._finalize_pending_steps()
        for run_id in product_commercialization_ids:
            self._enqueue_product_commercialization_run(run_id=run_id, user_id=None)
        for run_id in waiting_primary_ids:
            self._submit_primary_after_vl_if_ready(run_id=run_id, user=None)
        for run_id in terminal_ids:
            get_business_project_service().sync_run_outputs_to_project_assets(run_id)
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
        if status == "succeeded":
            processed_payload = self._postprocess_image_edit_canvas_outpaint_payload(task=task, payload=payload)
            if processed_payload is not payload:
                payload = processed_payload
                task.result_payload = processed_payload
                session.add(task)
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

    def _postprocess_image_edit_canvas_outpaint_payload(self, *, task: AbilityTask, payload: dict[str, Any]) -> dict[str, Any]:
        request_payload = task.request_payload if isinstance(task.request_payload, dict) else {}
        request_meta = request_payload.get("metadata") if isinstance(request_payload.get("metadata"), dict) else {}
        compiler = request_meta.get("imageEditCompiler") if isinstance(request_meta.get("imageEditCompiler"), dict) else {}
        if compiler.get("editSkill") != "canvas_outpaint" or not self._truthy_policy_flag(compiler.get("preserveOriginal")):
            return payload
        postprocess = payload.get("_imageEditPostprocess") if isinstance(payload.get("_imageEditPostprocess"), dict) else {}
        if postprocess.get("status") in {"succeeded", "failed"}:
            return payload

        generated_urls = self._extract_urls(payload, keys=("images", "assets", "resultUrls", "imageUrls"))
        generated_url = generated_urls[0] if generated_urls else None
        source_url = self._first_string(compiler.get("sourceImageUrl"))
        placement = compiler.get("placement") if isinstance(compiler.get("placement"), dict) else {}
        placement_x = self._first_int(placement.get("x"))
        placement_y = self._first_int(placement.get("y"))
        if not generated_url or not source_url or placement_x is None or placement_y is None:
            return payload

        try:
            generated_image = self._load_image_edit_rgba(generated_url)
            source_image = self._load_image_edit_rgba(source_url)
            if (
                placement_x < 0
                or placement_y < 0
                or placement_x + source_image.width > generated_image.width
                or placement_y + source_image.height > generated_image.height
            ):
                raise ValueError("source placement is outside generated canvas")
            final_image = generated_image.copy()
            final_image.alpha_composite(source_image, (placement_x, placement_y))
            upload = self._upload_image_edit_png(
                final_image,
                filename=f"image-edit-outpaint-final-{uuid4().hex[:10]}.png",
                trace_context=request_meta if isinstance(request_meta, dict) else None,
                apply_output_dpi=True,
            )
            final_url = str(upload.get("url") or "")
            if not final_url:
                raise ValueError("final image upload returned empty url")
            final_asset = {
                "url": final_url,
                "ossUrl": final_url,
                "sourceUrl": generated_url,
                "contentType": "image/png",
                "tag": "image_edit_canvas_outpaint_final",
                "metadata": {
                    "postprocess": "paste_original_region",
                    "placement": {"x": placement_x, "y": placement_y},
                    "sourceImageUrl": source_url,
                    "modelOutputUrl": generated_url,
                },
            }
            next_payload = deepcopy(payload)
            next_payload["images"] = [final_asset]
            next_payload["assets"] = [final_asset]
            next_payload["imageUrls"] = [final_url]
            next_payload["resultUrls"] = [final_url]
            next_payload["_imageEditPostprocess"] = {
                "status": "succeeded",
                "mode": "canvas_outpaint_preserve_original",
                "finalImageUrl": final_url,
                "modelOutputUrl": generated_url,
                "sourceImageUrl": source_url,
                "placement": {"x": placement_x, "y": placement_y},
            }
            return next_payload
        except Exception as exc:
            logger.warning("image_edit canvas outpaint postprocess failed: task=%s error=%s", task.id, exc)
            next_payload = deepcopy(payload)
            next_payload["_imageEditPostprocess"] = {
                "status": "failed",
                "mode": "canvas_outpaint_preserve_original",
                "error": str(exc)[:300],
            }
            return next_payload

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

    def list_output_reviews(
        self,
        *,
        run_id: str,
        actor: User | None = None,
    ) -> dict[str, Any]:
        del actor
        with get_session() as session:
            run = session.get(BusinessRun, run_id)
            if not run:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            if not self._optional_table_exists(session, "business_output_reviews"):
                return {"total": 0, "items": []}
            rows = (
                session.execute(
                    select(BusinessOutputReview)
                    .where(BusinessOutputReview.run_id == run_id)
                    .order_by(BusinessOutputReview.output_index.asc())
                )
                .scalars()
                .all()
            )
            return {"total": len(rows), "items": [self._output_review_to_dict(row) for row in rows]}

    def upsert_output_reviews(
        self,
        *,
        run_id: str,
        payload: BusinessOutputReviewUpsertRequest,
        actor: User | None = None,
    ) -> dict[str, Any]:
        if not payload.items:
            raise HTTPException(status_code=400, detail="BUSINESS_OUTPUT_REVIEW_ITEMS_REQUIRED")
        if len(payload.items) > 100:
            raise HTTPException(status_code=400, detail="BUSINESS_OUTPUT_REVIEW_LIMIT_EXCEEDED")
        now = datetime.utcnow()
        with get_session() as session:
            run = session.get(BusinessRun, run_id)
            if not run:
                raise HTTPException(status_code=404, detail="BUSINESS_RUN_NOT_FOUND")
            output_indexes = [int(item.outputIndex) for item in payload.items]
            existing = (
                session.execute(
                    select(BusinessOutputReview).where(
                        BusinessOutputReview.run_id == run_id,
                        BusinessOutputReview.output_index.in_(output_indexes),
                    )
                )
                .scalars()
                .all()
            )
            existing_by_index = {int(row.output_index): row for row in existing}
            touched: list[BusinessOutputReview] = []
            before_payload: list[dict[str, Any]] = []
            after_payload: list[dict[str, Any]] = []
            for item in payload.items:
                output_index = int(item.outputIndex)
                grade = self._normalize_output_review_grade(item.qualityGrade)
                next_action = self._normalize_output_review_action(item.nextAction)
                input_tags = self._normalize_output_review_tags(item.inputTags)
                issue_tags = self._normalize_output_review_tags(item.issueTags)
                output_url = self._clean_optional_text(item.outputUrl) or self._business_run_output_url(run, output_index)
                sample_meta = self._output_review_sample_meta_from_run(run)
                sample_key = self._short_text(item.sampleKey, 64) or sample_meta.get("sample_key")
                sample_label = self._short_text(item.sampleLabel, 128) or sample_meta.get("sample_label")
                batch_id = self._short_text(item.batchId, 64) or sample_meta.get("batch_id")
                note = self._short_text(item.note, 4000) if item.note else None
                row = existing_by_index.get(output_index)
                if row is None:
                    row = BusinessOutputReview(
                        id=f"bizreview_{uuid4().hex}",
                        run_id=run.id,
                        business_key=run.business_key,
                        business_version_id=run.business_version_id,
                        version=run.version,
                        output_index=output_index,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(row)
                    existing_by_index[output_index] = row
                    before_payload.append({"outputIndex": output_index, "created": True})
                else:
                    before_payload.append(self._output_review_to_dict(row))
                row.business_key = run.business_key
                row.business_version_id = run.business_version_id
                row.version = run.version
                row.output_url = output_url
                row.sample_key = sample_key
                row.sample_label = sample_label
                row.batch_id = batch_id
                row.quality_grade = grade
                row.input_tags = input_tags
                row.issue_tags = issue_tags
                row.next_action = next_action
                row.note = note
                row.reviewer_user_id = self._safe_user_id(actor)
                row.reviewer_username = self._actor_username(actor)
                row.updated_at = now
                session.add(row)
                touched.append(row)
                after_payload.append(
                    {
                        "outputIndex": output_index,
                        "qualityGrade": grade,
                        "sampleKey": sample_key,
                        "sampleLabel": sample_label,
                        "batchId": batch_id,
                        "inputTags": input_tags,
                        "issueTags": issue_tags,
                        "nextAction": next_action,
                    }
                )
            self._record_business_operation(
                session=session,
                action="upsert_output_review",
                target_type="business_run",
                target_id=run.id,
                business_key=run.business_key,
                tenant_id=run.tenant_id,
                client_id=run.client_id,
                actor=actor,
                note=f"更新业务输出质量复盘：{len(touched)} 条。",
                before_payload={"items": before_payload},
                after_payload={"items": after_payload},
            )
            session.commit()
            for row in touched:
                session.refresh(row)
            touched.sort(key=lambda row: int(row.output_index))
            return {"total": len(touched), "items": [self._output_review_to_dict(row) for row in touched]}

    def output_review_summary(
        self,
        *,
        window_hours: int = 168,
        business_key: str | None = None,
        version: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        normalized_window = max(1, min(int(window_hours or 168), 2160))
        normalized_limit = max(1, min(int(limit or 20), 100))
        since = datetime.utcnow() - timedelta(hours=normalized_window)
        filters = {
            "window_hours": normalized_window,
            "business_key": business_key,
            "version": version,
            "limit": normalized_limit,
        }
        with get_session() as session:
            if not self._optional_table_exists(session, "business_output_reviews"):
                return self._empty_output_review_summary(window_hours=normalized_window, filters=filters)
            stmt = select(BusinessOutputReview).where(BusinessOutputReview.created_at >= since)
            if business_key:
                stmt = stmt.where(BusinessOutputReview.business_key == business_key)
            if version:
                stmt = stmt.where(BusinessOutputReview.version == version)
            rows = (
                session.execute(stmt.order_by(BusinessOutputReview.created_at.desc()).limit(5000))
                .scalars()
                .all()
            )
        recent = sorted(rows, key=lambda row: row.updated_at or row.created_at, reverse=True)[:normalized_limit]
        return {
            "window_hours": normalized_window,
            "filters": filters,
            "total": len(rows),
            "by_grade": self._output_review_grade_buckets(rows),
            "by_business": self._output_review_business_summaries(rows),
            "by_version": self._output_review_version_summaries(rows),
            "by_batch": self._output_review_batch_summaries(rows),
            "top_issue_tags": self._output_review_tag_buckets(rows, "issue_tags"),
            "top_input_tags": self._output_review_tag_buckets(rows, "input_tags"),
            "recent_reviews": [self._output_review_to_dict(row) for row in recent],
        }

    def export_output_reviews(
        self,
        *,
        window_hours: int = 168,
        business_key: str | None = None,
        version: str | None = None,
        batch_id: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        normalized_window = max(1, min(int(window_hours or 168), 2160))
        normalized_limit = max(1, min(int(limit or 5000), 10000))
        since = datetime.utcnow() - timedelta(hours=normalized_window)
        with get_session() as session:
            if not self._optional_table_exists(session, "business_output_reviews"):
                return {
                    "window_hours": normalized_window,
                    "filters": {
                        "window_hours": normalized_window,
                        "business_key": business_key,
                        "version": version,
                        "batch_id": batch_id,
                        "limit": normalized_limit,
                    },
                    "total": 0,
                    "items": [],
                }
            stmt = select(BusinessOutputReview).where(BusinessOutputReview.created_at >= since)
            if business_key:
                stmt = stmt.where(BusinessOutputReview.business_key == str(business_key).strip())
            if version:
                stmt = stmt.where(BusinessOutputReview.version == str(version).strip())
            if batch_id:
                stmt = stmt.where(BusinessOutputReview.batch_id == str(batch_id).strip())
            rows = (
                session.execute(
                    stmt.order_by(
                        BusinessOutputReview.batch_id.asc(),
                        BusinessOutputReview.sample_key.asc(),
                        BusinessOutputReview.business_key.asc(),
                        BusinessOutputReview.version.asc(),
                        BusinessOutputReview.output_index.asc(),
                        BusinessOutputReview.updated_at.desc(),
                    ).limit(normalized_limit)
                )
                .scalars()
                .all()
            )
        return {
            "window_hours": normalized_window,
            "filters": {
                "window_hours": normalized_window,
                "business_key": business_key,
                "version": version,
                "batch_id": batch_id,
                "limit": normalized_limit,
            },
            "total": len(rows),
            "items": [self._output_review_to_dict(row) for row in rows],
        }

    def list_quality_samples(
        self,
        *,
        business_key: str | None = None,
        status: str | None = None,
        include_archived: bool = False,
        limit: int = 200,
    ) -> dict[str, Any]:
        normalized_limit = max(1, min(int(limit or 200), 500))
        with get_session() as session:
            if not self._optional_table_exists(session, "business_quality_samples"):
                return {"total": 0, "items": []}
            stmt = select(BusinessQualitySample)
            if business_key:
                stmt = stmt.where(BusinessQualitySample.business_key == str(business_key).strip())
            if status:
                stmt = stmt.where(BusinessQualitySample.status == self._normalize_quality_sample_status(status))
            elif not include_archived:
                stmt = stmt.where(BusinessQualitySample.status != "archived")
            rows = (
                session.execute(
                    stmt.order_by(
                        BusinessQualitySample.business_key.asc(),
                        BusinessQualitySample.sort_order.asc(),
                        BusinessQualitySample.created_at.desc(),
                    ).limit(normalized_limit)
                )
                .scalars()
                .all()
            )
            return {"total": len(rows), "items": [self._quality_sample_to_dict(row) for row in rows]}

    def list_quality_sample_versions(
        self,
        sample_id: str,
        *,
        limit: int = 50,
    ) -> dict[str, Any]:
        normalized_limit = max(1, min(int(limit or 50), 100))
        with get_session() as session:
            sample = session.get(BusinessQualitySample, sample_id)
            if not sample:
                raise HTTPException(status_code=404, detail="BUSINESS_QUALITY_SAMPLE_NOT_FOUND")
            rows = (
                session.execute(
                    select(BusinessQualitySampleVersion)
                    .where(BusinessQualitySampleVersion.sample_id == sample_id)
                    .order_by(BusinessQualitySampleVersion.version_no.desc(), BusinessQualitySampleVersion.created_at.desc())
                    .limit(normalized_limit)
                )
                .scalars()
                .all()
            )
            return {"total": len(rows), "items": [self._quality_sample_version_to_dict(row) for row in rows]}

    def create_quality_sample(
        self,
        payload: BusinessQualitySampleCreateRequest,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        now = datetime.utcnow()
        business_key = self._required_text(payload.businessKey, "BUSINESS_QUALITY_SAMPLE_BUSINESS_KEY_REQUIRED")
        sample_key = self._normalize_quality_sample_key(payload.sampleKey) or f"sample_{uuid4().hex[:10]}"
        label = self._required_text(payload.label, "BUSINESS_QUALITY_SAMPLE_LABEL_REQUIRED")[:128]
        image_url = self._normalize_quality_sample_url(payload.imageUrl, required=True)
        generated_image_url = self._normalize_quality_sample_url(payload.generatedImageUrl, required=False)
        status = self._normalize_quality_sample_status(payload.status)
        with get_session() as session:
            duplicate = (
                session.execute(
                    select(BusinessQualitySample).where(
                        BusinessQualitySample.business_key == business_key,
                        BusinessQualitySample.sample_key == sample_key,
                    )
                )
                .scalars()
                .first()
            )
            if duplicate:
                raise HTTPException(status_code=409, detail="BUSINESS_QUALITY_SAMPLE_KEY_DUPLICATED")
            row = BusinessQualitySample(
                id=f"bizsample_{uuid4().hex}",
                business_key=business_key,
                sample_key=sample_key,
                label=label,
                description=self._short_text(payload.description, 1000),
                image_url=image_url,
                prompt=self._short_text(payload.prompt, 4000),
                generated_image_url=generated_image_url,
                input_tags=self._normalize_output_review_tags(payload.inputTags),
                default_params=self._json_safe_record(payload.defaultParams),
                status=status,
                sort_order=int(payload.sortOrder or 0),
                created_by_user_id=self._safe_user_id(actor),
                created_by_username=self._actor_username(actor),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            self._record_quality_sample_version(
                session=session,
                row=row,
                change_type="create",
                actor=actor,
                note=payload.changeNote or "新增固定质量样例",
            )
            self._record_business_operation(
                session=session,
                action="create_quality_sample",
                target_type="business_quality_sample",
                target_id=row.id,
                business_key=row.business_key,
                actor=actor,
                note=f"新增固定质量样例：{row.label}",
                after_payload=self._json_safe_payload(self._quality_sample_to_dict(row)),
            )
            session.commit()
            session.refresh(row)
            return self._quality_sample_to_dict(row)

    def update_quality_sample(
        self,
        sample_id: str,
        payload: BusinessQualitySampleUpdateRequest,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        with get_session() as session:
            row = session.get(BusinessQualitySample, sample_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_QUALITY_SAMPLE_NOT_FOUND")
            before = self._json_safe_payload(self._quality_sample_to_dict(row))
            if "sampleKey" in payload.model_fields_set or "sample_key" in payload.model_fields_set:
                sample_key = self._normalize_quality_sample_key(payload.sampleKey)
                if not sample_key:
                    raise HTTPException(status_code=400, detail="BUSINESS_QUALITY_SAMPLE_KEY_REQUIRED")
                duplicate = (
                    session.execute(
                        select(BusinessQualitySample).where(
                            BusinessQualitySample.business_key == row.business_key,
                            BusinessQualitySample.sample_key == sample_key,
                            BusinessQualitySample.id != row.id,
                        )
                    )
                    .scalars()
                    .first()
                )
                if duplicate:
                    raise HTTPException(status_code=409, detail="BUSINESS_QUALITY_SAMPLE_KEY_DUPLICATED")
                row.sample_key = sample_key
            if payload.label is not None:
                row.label = self._required_text(payload.label, "BUSINESS_QUALITY_SAMPLE_LABEL_REQUIRED")[:128]
            if "description" in payload.model_fields_set:
                row.description = self._short_text(payload.description, 1000)
            if payload.imageUrl is not None:
                row.image_url = self._normalize_quality_sample_url(payload.imageUrl, required=True)
            if "prompt" in payload.model_fields_set:
                row.prompt = self._short_text(payload.prompt, 4000)
            if "generatedImageUrl" in payload.model_fields_set or "generated_image_url" in payload.model_fields_set:
                row.generated_image_url = self._normalize_quality_sample_url(payload.generatedImageUrl, required=False)
            if payload.inputTags is not None:
                row.input_tags = self._normalize_output_review_tags(payload.inputTags)
            if payload.defaultParams is not None:
                row.default_params = self._json_safe_record(payload.defaultParams)
            if payload.status is not None:
                row.status = self._normalize_quality_sample_status(payload.status)
            if payload.sortOrder is not None:
                row.sort_order = int(payload.sortOrder)
            row.updated_at = datetime.utcnow()
            session.add(row)
            after = self._json_safe_payload(self._quality_sample_to_dict(row))
            self._record_quality_sample_version(
                session=session,
                row=row,
                change_type="update",
                actor=actor,
                note=payload.changeNote or "更新固定质量样例",
            )
            self._record_business_operation(
                session=session,
                action="update_quality_sample",
                target_type="business_quality_sample",
                target_id=row.id,
                business_key=row.business_key,
                actor=actor,
                note=f"更新固定质量样例：{row.label}",
                before_payload=before,
                after_payload=after,
            )
            session.commit()
            session.refresh(row)
            return self._quality_sample_to_dict(row)

    def archive_quality_sample(
        self,
        sample_id: str,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        with get_session() as session:
            row = session.get(BusinessQualitySample, sample_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_QUALITY_SAMPLE_NOT_FOUND")
            before = self._json_safe_payload(self._quality_sample_to_dict(row))
            row.status = "archived"
            row.updated_at = datetime.utcnow()
            session.add(row)
            self._record_quality_sample_version(
                session=session,
                row=row,
                change_type="archive",
                actor=actor,
                note="归档固定质量样例",
            )
            self._record_business_operation(
                session=session,
                action="archive_quality_sample",
                target_type="business_quality_sample",
                target_id=row.id,
                business_key=row.business_key,
                actor=actor,
                note=f"归档固定质量样例：{row.label}",
                before_payload=before,
                after_payload=self._json_safe_payload(self._quality_sample_to_dict(row)),
            )
            session.commit()
            session.refresh(row)
            return self._quality_sample_to_dict(row)

    def import_quality_samples(
        self,
        payload: BusinessQualitySampleImportRequest,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        raw_items = list(payload.items or [])
        if not raw_items:
            raise HTTPException(status_code=400, detail="BUSINESS_QUALITY_SAMPLE_IMPORT_EMPTY")
        if len(raw_items) > 200:
            raise HTTPException(status_code=400, detail="BUSINESS_QUALITY_SAMPLE_IMPORT_LIMIT_EXCEEDED")
        dry_run = bool(payload.dryRun)
        results: list[dict[str, Any]] = []
        created = 0
        updated = 0
        skipped = 0
        failed = 0
        seen_keys: set[tuple[str, str]] = set()
        now = datetime.utcnow()
        with get_session() as session:
            for index, item in enumerate(raw_items):
                try:
                    business_key = self._required_text(
                        item.businessKey or payload.businessKey,
                        "BUSINESS_QUALITY_SAMPLE_BUSINESS_KEY_REQUIRED",
                    )
                    sample_key = self._normalize_quality_sample_key(item.sampleKey)
                    if not sample_key:
                        raise HTTPException(status_code=400, detail="BUSINESS_QUALITY_SAMPLE_KEY_REQUIRED")
                    signature = (business_key, sample_key)
                    if signature in seen_keys:
                        raise HTTPException(status_code=409, detail="BUSINESS_QUALITY_SAMPLE_KEY_DUPLICATED")
                    seen_keys.add(signature)
                    label = self._required_text(item.label, "BUSINESS_QUALITY_SAMPLE_LABEL_REQUIRED")[:128]
                    image_url = self._normalize_quality_sample_url(item.imageUrl, required=True)
                    generated_image_url = self._normalize_quality_sample_url(item.generatedImageUrl, required=False)
                    normalized_status = self._normalize_quality_sample_status(item.status)
                    description = self._short_text(item.description, 1000)
                    prompt = self._short_text(item.prompt, 4000)
                    input_tags = self._normalize_output_review_tags(item.inputTags)
                    default_params = self._json_safe_record(item.defaultParams)
                    sort_order = int(item.sortOrder or 0)
                    existing = (
                        session.execute(
                            select(BusinessQualitySample).where(
                                BusinessQualitySample.business_key == business_key,
                                BusinessQualitySample.sample_key == sample_key,
                            )
                        )
                        .scalars()
                        .first()
                    )
                    action = "update" if existing else "create"
                    if dry_run:
                        skipped += 1
                        results.append(
                            {
                                "index": index,
                                "action": f"dry_run_{action}",
                                "sample_id": existing.id if existing else None,
                                "business_key": business_key,
                                "sample_key": sample_key,
                                "label": label,
                                "message": "预检查通过，未写入数据库",
                            }
                        )
                        continue
                    if existing:
                        existing.label = label
                        existing.description = description
                        existing.image_url = image_url
                        existing.prompt = prompt
                        existing.generated_image_url = generated_image_url
                        existing.input_tags = input_tags
                        existing.default_params = default_params
                        existing.status = normalized_status
                        existing.sort_order = sort_order
                        existing.updated_at = now
                        session.add(existing)
                        self._record_quality_sample_version(
                            session=session,
                            row=existing,
                            change_type="import_update",
                            actor=actor,
                            note=item.changeNote or payload.changeNote or "批量导入更新固定质量样例",
                        )
                        updated += 1
                        row = existing
                    else:
                        row = BusinessQualitySample(
                            id=f"bizsample_{uuid4().hex}",
                            business_key=business_key,
                            sample_key=sample_key,
                            label=label,
                            description=description,
                            image_url=image_url,
                            prompt=prompt,
                            generated_image_url=generated_image_url,
                            input_tags=input_tags,
                            default_params=default_params,
                            status=normalized_status,
                            sort_order=sort_order,
                            created_by_user_id=self._safe_user_id(actor),
                            created_by_username=self._actor_username(actor),
                            created_at=now,
                            updated_at=now,
                        )
                        session.add(row)
                        self._record_quality_sample_version(
                            session=session,
                            row=row,
                            change_type="import_create",
                            actor=actor,
                            note=item.changeNote or payload.changeNote or "批量导入新增固定质量样例",
                        )
                        created += 1
                    results.append(
                        {
                            "index": index,
                            "action": "updated" if existing else "created",
                            "sample_id": row.id,
                            "business_key": row.business_key,
                            "sample_key": row.sample_key,
                            "label": row.label,
                            "message": "已更新" if existing else "已新增",
                        }
                    )
                except HTTPException as exc:
                    failed += 1
                    results.append(
                        {
                            "index": index,
                            "action": "error",
                            "business_key": getattr(item, "businessKey", None) or payload.businessKey,
                            "sample_key": getattr(item, "sampleKey", None),
                            "label": getattr(item, "label", None),
                            "error_code": str(exc.detail or "BUSINESS_QUALITY_SAMPLE_IMPORT_ITEM_INVALID"),
                            "message": str(exc.detail or "固定质量样例导入项非法"),
                        }
                    )
            if not dry_run:
                self._record_business_operation(
                    session=session,
                    action="import_quality_samples",
                    target_type="business_quality_sample",
                    target_id=None,
                    business_key=str(payload.businessKey or ""),
                    actor=actor,
                    note=f"批量导入固定质量样例：新增 {created}，更新 {updated}，失败 {failed}",
                    after_payload=self._json_safe_payload(
                        {
                            "created": created,
                            "updated": updated,
                            "failed": failed,
                            "total": len(raw_items),
                        }
                    ),
                )
                session.commit()
        return {
            "total": len(raw_items),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "dry_run": dry_run,
            "items": results,
        }

    def list_quality_action_rules(
        self,
        *,
        business_key: str | None = None,
        status: str | None = None,
        action_type: str | None = None,
        include_archived: bool = False,
        limit: int = 200,
    ) -> dict[str, Any]:
        normalized_limit = max(1, min(int(limit or 200), 500))
        with get_session() as session:
            if not self._optional_table_exists(session, "business_quality_action_rules"):
                return {"total": 0, "items": []}
            stmt = select(BusinessQualityActionRule)
            if business_key:
                stmt = stmt.where(BusinessQualityActionRule.business_key == str(business_key).strip())
            if status:
                stmt = stmt.where(BusinessQualityActionRule.status == self._normalize_quality_action_status(status))
            elif not include_archived:
                stmt = stmt.where(BusinessQualityActionRule.status != "archived")
            if action_type:
                stmt = stmt.where(BusinessQualityActionRule.action_type == self._normalize_quality_action_type(action_type))
            rows = (
                session.execute(
                    stmt.order_by(
                        BusinessQualityActionRule.business_key.asc(),
                        BusinessQualityActionRule.priority.asc(),
                        BusinessQualityActionRule.created_at.desc(),
                    ).limit(normalized_limit)
                )
                .scalars()
                .all()
            )
            target_ids = [row.target_business_version_id for row in rows if row.target_business_version_id]
            target_map: dict[str, BusinessCapability] = {}
            if target_ids:
                target_rows = (
                    session.execute(select(BusinessCapability).where(BusinessCapability.id.in_(target_ids)))
                    .scalars()
                    .all()
                )
                target_map = {row.id: row for row in target_rows}
            return {
                "total": len(rows),
                "items": [
                    self._quality_action_rule_to_dict(row, target=target_map.get(row.target_business_version_id or ""))
                    for row in rows
                ],
            }

    def create_quality_action_rule(
        self,
        payload: BusinessQualityActionRuleCreateRequest,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        now = datetime.utcnow()
        business_key = self._required_text(payload.businessKey, "BUSINESS_QUALITY_ACTION_BUSINESS_KEY_REQUIRED")
        rule_key = self._normalize_quality_action_key(payload.ruleKey or payload.title) or f"rule_{uuid4().hex[:10]}"
        title = self._required_text(payload.title, "BUSINESS_QUALITY_ACTION_TITLE_REQUIRED")[:128]
        action_type = self._normalize_quality_action_type(payload.actionType)
        status = self._normalize_quality_action_status(payload.status)
        target_ref = self._short_text(payload.targetRef, 128)
        target_params = self._json_safe_record(payload.targetParams)
        with get_session() as session:
            duplicate = (
                session.execute(
                    select(BusinessQualityActionRule).where(
                        BusinessQualityActionRule.business_key == business_key,
                        BusinessQualityActionRule.rule_key == rule_key,
                    )
                )
                .scalars()
                .first()
            )
            if duplicate:
                raise HTTPException(status_code=409, detail="BUSINESS_QUALITY_ACTION_KEY_DUPLICATED")
            target = self._resolve_quality_action_target(
                session,
                business_key=business_key,
                target_business_version_id=payload.targetBusinessVersionId,
            )
            row = BusinessQualityActionRule(
                id=f"bizqar_{uuid4().hex}",
                business_key=business_key,
                rule_key=rule_key,
                title=title,
                description=self._short_text(payload.description, 1000),
                issue_tags=self._normalize_output_review_tags(payload.issueTags),
                input_tags=self._normalize_output_review_tags(payload.inputTags),
                action_type=action_type,
                target_business_version_id=target.id if target else None,
                target_version=target.version if target else None,
                target_label=target.display_name if target else None,
                target_ref=target_ref,
                target_params=target_params,
                sample_batch_id=self._short_text(payload.sampleBatchId, 64),
                evidence_review_ids=self._normalize_quality_action_evidence_ids(payload.evidenceReviewIds),
                status=status,
                priority=int(payload.priority or 0),
                owner_user_id=self._safe_user_id(actor),
                owner_username=self._actor_username(actor),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            self._record_business_operation(
                session=session,
                action="create_quality_action_rule",
                target_type="business_quality_action_rule",
                target_id=row.id,
                business_key=row.business_key,
                actor=actor,
                note=f"新增质量治理台账：{row.title}",
                after_payload=self._json_safe_payload(self._quality_action_rule_to_dict(row, target=target)),
            )
            session.commit()
            session.refresh(row)
            return self._quality_action_rule_to_dict(row, target=target)

    def update_quality_action_rule(
        self,
        rule_id: str,
        payload: BusinessQualityActionRuleUpdateRequest,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        with get_session() as session:
            row = session.get(BusinessQualityActionRule, rule_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_QUALITY_ACTION_NOT_FOUND")
            target = self._resolve_quality_action_target(
                session,
                business_key=row.business_key,
                target_business_version_id=row.target_business_version_id,
                allow_empty=True,
            )
            before = self._json_safe_payload(self._quality_action_rule_to_dict(row, target=target))
            if "ruleKey" in payload.model_fields_set or "rule_key" in payload.model_fields_set:
                rule_key = self._normalize_quality_action_key(payload.ruleKey)
                if not rule_key:
                    raise HTTPException(status_code=400, detail="BUSINESS_QUALITY_ACTION_KEY_REQUIRED")
                duplicate = (
                    session.execute(
                        select(BusinessQualityActionRule).where(
                            BusinessQualityActionRule.business_key == row.business_key,
                            BusinessQualityActionRule.rule_key == rule_key,
                            BusinessQualityActionRule.id != row.id,
                        )
                    )
                    .scalars()
                    .first()
                )
                if duplicate:
                    raise HTTPException(status_code=409, detail="BUSINESS_QUALITY_ACTION_KEY_DUPLICATED")
                row.rule_key = rule_key
            if payload.title is not None:
                row.title = self._required_text(payload.title, "BUSINESS_QUALITY_ACTION_TITLE_REQUIRED")[:128]
            if "description" in payload.model_fields_set:
                row.description = self._short_text(payload.description, 1000)
            if payload.issueTags is not None:
                row.issue_tags = self._normalize_output_review_tags(payload.issueTags)
            if payload.inputTags is not None:
                row.input_tags = self._normalize_output_review_tags(payload.inputTags)
            if payload.actionType is not None:
                row.action_type = self._normalize_quality_action_type(payload.actionType)
            if "targetBusinessVersionId" in payload.model_fields_set or "target_business_version_id" in payload.model_fields_set:
                target = self._resolve_quality_action_target(
                    session,
                    business_key=row.business_key,
                    target_business_version_id=payload.targetBusinessVersionId,
                    allow_empty=True,
                )
                row.target_business_version_id = target.id if target else None
                row.target_version = target.version if target else None
                row.target_label = target.display_name if target else None
            if "targetRef" in payload.model_fields_set or "target_ref" in payload.model_fields_set:
                row.target_ref = self._short_text(payload.targetRef, 128)
            if payload.targetParams is not None:
                row.target_params = self._json_safe_record(payload.targetParams)
            if "sampleBatchId" in payload.model_fields_set or "sample_batch_id" in payload.model_fields_set:
                row.sample_batch_id = self._short_text(payload.sampleBatchId, 64)
            if payload.evidenceReviewIds is not None:
                row.evidence_review_ids = self._normalize_quality_action_evidence_ids(payload.evidenceReviewIds)
            if payload.status is not None:
                row.status = self._normalize_quality_action_status(payload.status)
            if payload.priority is not None:
                row.priority = int(payload.priority)
            row.updated_at = datetime.utcnow()
            session.add(row)
            after = self._json_safe_payload(self._quality_action_rule_to_dict(row, target=target))
            self._record_business_operation(
                session=session,
                action="update_quality_action_rule",
                target_type="business_quality_action_rule",
                target_id=row.id,
                business_key=row.business_key,
                actor=actor,
                note=f"更新质量治理台账：{row.title}",
                before_payload=before,
                after_payload=after,
            )
            session.commit()
            session.refresh(row)
            return self._quality_action_rule_to_dict(row, target=target)

    def archive_quality_action_rule(
        self,
        rule_id: str,
        *,
        actor: User | None = None,
    ) -> dict[str, Any]:
        with get_session() as session:
            row = session.get(BusinessQualityActionRule, rule_id)
            if not row:
                raise HTTPException(status_code=404, detail="BUSINESS_QUALITY_ACTION_NOT_FOUND")
            target = self._resolve_quality_action_target(
                session,
                business_key=row.business_key,
                target_business_version_id=row.target_business_version_id,
                allow_empty=True,
            )
            before = self._json_safe_payload(self._quality_action_rule_to_dict(row, target=target))
            row.status = "archived"
            row.updated_at = datetime.utcnow()
            session.add(row)
            self._record_business_operation(
                session=session,
                action="archive_quality_action_rule",
                target_type="business_quality_action_rule",
                target_id=row.id,
                business_key=row.business_key,
                actor=actor,
                note=f"归档质量治理台账：{row.title}",
                before_payload=before,
                after_payload=self._json_safe_payload(self._quality_action_rule_to_dict(row, target=target)),
            )
            session.commit()
            session.refresh(row)
            return self._quality_action_rule_to_dict(row, target=target)

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
        public_task_id = (
            encode_task_id(task_id=run.ability_task_id, provider=run.business_key, executor_id=None)
            if run.ability_task_id
            else None
        )
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
            "taskId": public_task_id,
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
    def _business_billing_status_for_usage_summary(row: BusinessRun) -> str:
        status = str(row.status or "").strip().lower()
        if status in {"queued", "running", "pending", "planned"}:
            return "billing_pending"
        if status in {"failed", "cancelled", "timeout"}:
            return "no_charge"
        if status == "succeeded":
            source = str(row.source or "").strip()
            tenant_id = str(row.tenant_id or "").strip()
            client_id = str(row.client_id or "").strip()
            if (
                source in INTERNAL_NO_CHARGE_SOURCES
                or tenant_id in INTERNAL_NO_CHARGE_TENANTS
                or client_id in INTERNAL_NO_CHARGE_CLIENTS
            ):
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
            for key in (
                "grayKey",
                "gray_key",
                "routeKey",
                "route_key",
                "clientContextId",
                "client_context_id",
                "tenantId",
                "tenant_id",
                "userId",
                "user_id",
                "traceId",
                "trace_id",
            ):
                value = source.get(key)
                if isinstance(value, (str, int, float)) and str(value).strip():
                    return str(value).strip()
        if payload:
            for value in (payload.clientContextId, payload.tenantId, payload.clientId, payload.traceId, payload.requestId):
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
    def _next_draft_version(*, session, source: BusinessCapability) -> str:
        base = str(source.version or "v1").strip() or "v1"
        if base.endswith("-draft") or "-draft-" in base:
            base = base.split("-draft", 1)[0] or "v1"
        for index in range(1, 100):
            suffix = "-draft" if index == 1 else f"-draft-{index}"
            candidate = f"{base[: max(1, 32 - len(suffix))]}{suffix}"
            exists = (
                session.execute(
                    select(BusinessCapability.id).where(
                        BusinessCapability.business_key == source.business_key,
                        BusinessCapability.version == candidate,
                    )
                )
                .scalars()
                .first()
            )
            if not exists:
                return candidate
        return f"{base[:16]}-draft-{uuid4().hex[:6]}"

    @staticmethod
    def _recipe_diff_summary(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
        changes: list[str] = []
        before_primary = str(before.get("primaryAbilityId") or before.get("primary_ability_id") or "").strip()
        after_primary = str(after.get("primaryAbilityId") or after.get("primary_ability_id") or "").strip()
        if before_primary != after_primary:
            changes.append(f"主执行能力：{before_primary or '-'} -> {after_primary or '-'}")
        before_mode = str(before.get("mode") or "").strip()
        after_mode = str(after.get("mode") or "").strip()
        if before_mode != after_mode:
            changes.append(f"执行模式：{before_mode or '-'} -> {after_mode or '-'}")
        before_steps = before.get("steps") if isinstance(before.get("steps"), list) else []
        after_steps = after.get("steps") if isinstance(after.get("steps"), list) else []
        if len(before_steps) != len(after_steps):
            changes.append(f"处理步骤数量：{len(before_steps)} -> {len(after_steps)}")

        def step_map(steps: list[Any]) -> dict[str, dict[str, Any]]:
            result: dict[str, dict[str, Any]] = {}
            for index, raw in enumerate(steps, start=1):
                if not isinstance(raw, dict):
                    continue
                key = str(raw.get("id") or f"step_{index}").strip()
                result[key] = raw
            return result

        before_map = step_map(before_steps)
        after_map = step_map(after_steps)
        removed = sorted(set(before_map) - set(after_map))
        added = sorted(set(after_map) - set(before_map))
        if added:
            changes.append(f"新增步骤：{', '.join(added[:5])}")
        if removed:
            changes.append(f"删除步骤：{', '.join(removed[:5])}")
        for key in sorted(set(before_map) & set(after_map)):
            before_step = before_map[key]
            after_step = after_map[key]
            before_ability = BusinessRunService._extract_step_ability_id(before_step) or "-"
            after_ability = BusinessRunService._extract_step_ability_id(after_step) or "-"
            if before_ability != after_ability:
                changes.append(f"步骤 {key} 能力：{before_ability} -> {after_ability}")
            before_enabled = before_step.get("enabled", True)
            after_enabled = after_step.get("enabled", True)
            if before_enabled != after_enabled:
                changes.append(f"步骤 {key} 启用状态：{before_enabled} -> {after_enabled}")
        return changes or ["配方结构未变化，仅更新了格式或说明。"]

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
            if compiler in PATTERN_FISSION_TEMPLATE_ALIASES.union(PATTERN_FISSION_LEGACY_TEMPLATE_ALIASES):
                compiled = compile_pattern_fission_prompt(vl_summary=vl_summary, user_inputs=inputs, template_id=compiler)
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
                for internal_field in (
                    "count",
                    "n",
                    "batch_size",
                    "preserve_layout",
                    "preserve_border",
                    "preserve_count_density",
                    "style_shift",
                ):
                    inputs.pop(internal_field, None)
                for field, value in compiled_inputs.items():
                    if field in pass_keys and value not in (None, "", []):
                        if overwrite or not inputs.get(field):
                            inputs[field] = value
                return
            if compiler in {"comfyui_fission_control_card_v1", "comfyui_fission_control_card_v2"}:
                card = vl_summary.get("fissionControlCard") if isinstance(vl_summary.get("fissionControlCard"), dict) else None
                if not card and isinstance(vl_summary.get("vlCard"), dict):
                    card = vl_summary.get("vlCard")
                if not isinstance(card, dict):
                    card = {}
                business_extra_prompt = self._first_string(inputs.get("prompt"))
                prompt_main = self._first_string(
                    card.get("prompt_main"),
                    card.get("promptMain"),
                    vl_summary.get("prompt_main"),
                    vl_summary.get("promptMain"),
                    vl_summary.get("positivePrompt"),
                )
                prompt_control = self._first_string(
                    card.get("prompt_control"),
                    card.get("promptControl"),
                    card.get("image_desc"),
                    card.get("imageDesc"),
                    vl_summary.get("prompt_control"),
                    vl_summary.get("promptControl"),
                    vl_summary.get("image_desc"),
                    vl_summary.get("promptControl"),
                    vl_summary.get("imageDesc"),
                )
                palette_card = None
                for candidate in (
                    card.get("palette_card"),
                    card.get("paletteCard"),
                    vl_summary.get("palette_card"),
                    vl_summary.get("paletteCard"),
                ):
                    if isinstance(candidate, dict):
                        palette_card = candidate
                        break
                profile_hint = self._first_string(
                    card.get("profile_hint"),
                    card.get("profileHint"),
                    vl_summary.get("profileHint"),
                    inputs.get("profile"),
                    inputs.get("profile_id"),
                )
                pattern_risk_type = self._first_value(
                    card.get("pattern_risk_type"),
                    vl_summary.get("pattern_risk_type"),
                    card.get("patternRiskType"),
                    vl_summary.get("patternRiskType"),
                    card.get("pattern_type"),
                    vl_summary.get("patternType"),
                )
                object_variation_level = self._first_value(
                    card.get("object_variation_level"),
                    vl_summary.get("object_variation_level"),
                    card.get("objectVariationLevel"),
                    vl_summary.get("objectVariationLevel"),
                )
                if compiler == "comfyui_fission_control_card_v2":
                    profile_hint = profile_hint or "pattern_risk_routed_v4"
                    prompt_main = compile_comfyui_v4_prompt(
                        prompt_main=prompt_main,
                        business_extra_prompt=business_extra_prompt,
                        pattern_risk_type=pattern_risk_type,
                        object_variation_level=object_variation_level,
                        bili=inputs.get("bili"),
                    )
                    color_lock_lines = []
                    if palette_card:
                        color_lock_lines.append(
                            f"Palette card: {json.dumps(palette_card, ensure_ascii=False, separators=(',', ':'))}"
                        )
                    color_lock_lines.append(
                        "Color control priority: strictly keep the source image main colors, secondary colors, accent colors, saturation level, and light/dark area ratio. Do not introduce a new dominant palette."
                    )
                    color_lock_lines.append(
                        "Negative constraints: no new dominant color palette, no red brown dominance unless present in source, no orange yellow dominance unless present in source, no high saturation, no harsh contrast, no random white holes, no black block dominance, no photorealistic carpet scene, no perspective room render."
                    )
                    prompt_control = compile_comfyui_v4_image_desc(prompt_control)
                    prompt_control = "\n".join([part for part in [prompt_control, *color_lock_lines] if part])
                compiled_inputs = {
                    "prompt": prompt_main,
                    "image_desc": prompt_control,
                    "vl_result": card or vl_summary,
                    "profile": profile_hint or "pattern_default_v1",
                    "profile_id": profile_hint or "pattern_default_v1",
                    "bili_mapping": (
                        "variation_percent_045_080_colorlock_v2"
                        if compiler == "comfyui_fission_control_card_v2"
                        else "variation_percent_045_080"
                    ),
                }
                if compiler == "comfyui_fission_control_card_v2":
                    compiled_inputs["bili_mapping"] = "pattern_risk_routed_v4"
                    for field, *aliases in (
                        ("pattern_risk_type", "patternRiskType", "pattern_type", "patternType"),
                        ("object_variation_level", "objectVariationLevel"),
                        ("density_risk_level", "densityRiskLevel"),
                        ("max_denoise", "maxDenoise"),
                        ("recommended_reference_lock", "recommendedReferenceLock"),
                        ("recommended_color_lock", "recommendedColorLock"),
                    ):
                        value = self._first_value(card.get(field), vl_summary.get(field), *[card.get(alias) for alias in aliases], *[vl_summary.get(alias) for alias in aliases])
                        if value not in (None, "", []):
                            compiled_inputs[field] = value
                    if inputs.get("reference_lock") in (None, "") and compiled_inputs.get("recommended_reference_lock") not in (None, ""):
                        compiled_inputs["reference_lock"] = compiled_inputs["recommended_reference_lock"]
                    if inputs.get("color_lock") in (None, "") and compiled_inputs.get("recommended_color_lock") not in (None, ""):
                        compiled_inputs["color_lock"] = compiled_inputs["recommended_color_lock"]
                    reference_lock_value = self._first_value(
                        inputs.get("reference_lock"),
                        compiled_inputs.get("reference_lock"),
                        compiled_inputs.get("recommended_reference_lock"),
                    )
                    if reference_lock_value not in (None, "", []):
                        compiled_inputs["reference_lock"] = reference_lock_value
                        compiled_inputs["ipadapter_weight"] = reference_lock_value
                    color_lock_value = self._first_value(
                        inputs.get("color_lock"),
                        compiled_inputs.get("color_lock"),
                        compiled_inputs.get("recommended_color_lock"),
                    )
                    if color_lock_value not in (None, "", []):
                        compiled_inputs["color_lock"] = color_lock_value
                        compiled_inputs["colormatch_strength"] = color_lock_value
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

    @staticmethod
    def _enforce_single_output_fission_inputs(inputs: dict[str, Any], *, keep_internal_n: bool = False) -> None:
        """Business fission returns one output per runId."""

        blocked_keys = [
            "count",
            "batch_size",
            "batchSize",
            "generate_count",
            "generateCount",
            "variant_count",
            "variantCount",
            "preserve_layout",
            "preserveLayout",
            "preserve_border",
            "preserveBorder",
            "preserve_count_density",
            "preserveCountDensity",
            "style_shift",
            "styleShift",
        ]
        if not keep_internal_n:
            blocked_keys.append("n")
        for key in blocked_keys:
            inputs.pop(key, None)
        if keep_internal_n and "n" in inputs:
            inputs["n"] = 1

    def _apply_fission_variation_preset(self, inputs: dict[str, Any], *, recipe: dict[str, Any] | None) -> None:
        """Expand user-facing fission presets at the business-control layer.

        The preset list lives in the public business API contract. This method only
        materializes it for the ComfyUI color-lock fission line and never overrides
        fields the caller explicitly supplied.
        """

        preset_key = self._first_string(inputs.get("variation_preset"), inputs.get("variationPreset"))
        if not preset_key:
            return
        values = COMFYUI_FISSION_VARIATION_PRESET_VALUES_BY_KEY.get(preset_key)
        if not values:
            return
        try:
            primary_ability_id = self._extract_primary_ability_id(recipe or {})
        except HTTPException:
            return
        if primary_ability_id not in COMFYUI_COLORLOCK_FISSION_ABILITY_IDS:
            return
        profile_explicit = inputs.get("profile") not in (None, "", []) or inputs.get("profile_id") not in (None, "", [])
        for key, value in values.items():
            if key in {"profile", "profile_id"} and profile_explicit:
                continue
            if inputs.get(key) in (None, "", []):
                inputs[key] = value

    def _maybe_apply_fission_aspect_recompose(
        self,
        *,
        inputs: dict[str, Any],
        image_url: str,
        recipe: dict[str, Any] | None,
        vl_summary: dict[str, Any] | None,
        trace_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Route large aspect-ratio changes through a guide image instead of crop-resize.

        This is intentionally scoped to the self-owned ComfyUI business line. Coze
        workflow/toolbox contracts remain unchanged.
        """

        try:
            primary_ability_id = self._extract_primary_ability_id(recipe or {})
        except HTTPException:
            return None
        if primary_ability_id not in FISSION_ASPECT_RECOMPOSE_TARGET_ABILITIES:
            return None
        target_w_raw = self._coerce_positive_int(inputs.get("output_width") or inputs.get("width"))
        target_h_raw = self._coerce_positive_int(inputs.get("output_height") or inputs.get("height"))
        if not target_w_raw or not target_h_raw:
            return None
        target_w = self._normalize_fission_aspect_dim(target_w_raw)
        target_h = self._normalize_fission_aspect_dim(target_h_raw)
        if not target_w or not target_h:
            return None

        try:
            source_image = self._load_image_edit_rgba(image_url).convert("RGB")
        except HTTPException as exc:
            raise HTTPException(status_code=400, detail="FISSION_ASPECT_SOURCE_IMAGE_LOAD_FAILED") from exc
        source_w, source_h = source_image.size
        if source_w <= 0 or source_h <= 0:
            return {"route": "keep_original_ratio", "reason": "source_size_invalid"}

        source_shape = min(source_w, source_h) / max(source_w, source_h)
        source_aspect = source_w / source_h
        target_aspect = target_w / target_h
        aspect_ratio_delta = target_aspect / source_aspect
        base_meta = {
            "sourceSize": {"width": source_w, "height": source_h},
            "requestedTargetSize": {"width": target_w_raw, "height": target_h_raw},
            "normalizedTargetSize": {"width": target_w, "height": target_h},
            "sourceAspect": round(source_aspect, 6),
            "targetAspect": round(target_aspect, 6),
            "aspectRatioDelta": round(aspect_ratio_delta, 6),
        }
        if source_shape < FISSION_ASPECT_RECOMPOSE_SOURCE_SHAPE_MIN:
            self._apply_fission_original_ratio_fallback(inputs, source_width=source_w, source_height=source_h)
            return {**base_meta, "route": "keep_original_ratio", "reason": "source_shape_too_extreme"}
        if FISSION_ASPECT_RECOMPOSE_RATIO_MIN <= aspect_ratio_delta <= FISSION_ASPECT_RECOMPOSE_RATIO_MAX:
            return {**base_meta, "route": "keep_original_ratio", "reason": "aspect_close_enough"}
        if (
            aspect_ratio_delta < FISSION_ASPECT_RECOMPOSE_EXTREME_MIN
            or aspect_ratio_delta > FISSION_ASPECT_RECOMPOSE_EXTREME_MAX
        ):
            self._apply_fission_original_ratio_fallback(inputs, source_width=source_w, source_height=source_h)
            return {**base_meta, "route": "keep_original_ratio", "reason": "aspect_change_too_extreme"}

        router = self._extract_fission_aspect_router(vl_summary)
        if not self._is_fission_aspect_router_allowed(router):
            self._apply_fission_original_ratio_fallback(inputs, source_width=source_w, source_height=source_h)
            return {
                **base_meta,
                "route": "keep_original_ratio",
                "reason": "vl_router_not_allowed",
                "vlRouter": router,
            }

        guide_image = self._build_fission_aspect_guide_image(source_image, width=target_w, height=target_h)
        try:
            upload = self._upload_image_edit_png(
                guide_image,
                filename=f"fission-aspect-recompose-guide-{uuid4().hex[:10]}.png",
                trace_context=trace_context,
            )
        except Exception as exc:  # noqa: BLE001 - convert to a clear business error.
            raise HTTPException(status_code=400, detail="FISSION_ASPECT_RECOMPOSE_GUIDE_FAILED") from exc
        guide_url = self._first_string(upload.get("url"), upload.get("ossUrl"), upload.get("storedUrl"))
        if not guide_url:
            raise HTTPException(status_code=400, detail="FISSION_ASPECT_RECOMPOSE_GUIDE_FAILED")

        inputs["image_url"] = guide_url
        inputs["imageUrl"] = guide_url
        inputs["width"] = target_w
        inputs["height"] = target_h
        inputs["profile"] = "pattern_risk_routed_v4"
        inputs["profile_id"] = "pattern_risk_routed_v4"
        inputs["bili_mapping"] = "pattern_risk_routed_v4"
        inputs["aspect_recompose_route"] = "pattern_recompose"
        inputs["aspect_recompose_denoise"] = 0.68
        inputs["guide_mode"] = "contain_tile"
        inputs["reference_lock"] = 0.34
        inputs["color_lock"] = 0.95
        inputs["ipadapter_weight"] = 0.34
        inputs["colormatch_method"] = "mkl"
        inputs["colormatch_strength"] = 0.95
        inputs["batch_size"] = 1
        inputs["steps"] = 8
        inputs["cfg"] = 1.0
        inputs["prompt"] = self._append_text_once(inputs.get("prompt"), FISSION_ASPECT_RECOMPOSE_PROMPT_SUFFIX)
        return {
            **base_meta,
            "route": "pattern_recompose",
            "reason": "aspect_mismatch_full_pattern_allowed",
            "guideMode": "contain_tile",
            "guideImageUrl": guide_url,
            "vlRouter": router,
            "fixedParams": {
                "steps": 8,
                "cfg": 1.0,
                "denoise": 0.68,
                "batch_size": 1,
                "ipadapter_weight": 0.34,
                "colormatch_method": "mkl",
                "colormatch_strength": 0.95,
            },
        }

    @staticmethod
    def _normalize_fission_aspect_dim(value: int | None) -> int | None:
        if not value or value <= 0:
            return None
        return max(16, int(value) - (int(value) % 16))

    @classmethod
    def _apply_fission_original_ratio_fallback(
        cls,
        inputs: dict[str, Any],
        *,
        source_width: int,
        source_height: int,
    ) -> None:
        width = cls._normalize_fission_aspect_dim(source_width)
        height = cls._normalize_fission_aspect_dim(source_height)
        if width and height:
            inputs["width"] = width
            inputs["height"] = height
        inputs["aspect_recompose_route"] = "keep_original_ratio"
        inputs["guide_mode"] = "fallback_keep_original_ratio"

    @staticmethod
    def _append_text_once(base: Any, addition: str) -> str:
        base_text = str(base or "").strip()
        addition_text = str(addition or "").strip()
        if not addition_text or addition_text in base_text:
            return base_text
        return "\n\n".join(part for part in (base_text, addition_text) if part)

    @staticmethod
    def _extract_fission_aspect_router(vl_summary: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(vl_summary, dict):
            return {}
        candidates: list[dict[str, Any]] = [vl_summary]
        for key in ("fissionControlCard", "vlCard", "vl_result", "vlResult"):
            value = vl_summary.get(key)
            if isinstance(value, dict):
                candidates.append(value)
        merged: dict[str, Any] = {}
        for candidate in candidates:
            for key in (
                "aspect_recompose_route",
                "aspectRecomposeRoute",
                "route",
                "aspect_recompose_allowed",
                "aspectRecomposeAllowed",
                "layout_type",
                "layoutType",
                "is_dense_small_repeat",
                "isDenseSmallRepeat",
                "is_scale_safe",
                "isScaleSafe",
                "aspect_recompose_reason",
                "aspectRecomposeReason",
            ):
                if key in candidate and candidate.get(key) not in (None, "", []):
                    merged[key] = candidate.get(key)
            risk = candidate.get("aspect_recompose_risk_flags") or candidate.get("aspectRecomposeRiskFlags")
            if isinstance(risk, dict):
                merged["riskFlags"] = risk
        return merged

    @staticmethod
    def _is_fission_aspect_router_allowed(router: dict[str, Any]) -> bool:
        if not isinstance(router, dict) or not router:
            return False
        route = str(router.get("aspect_recompose_route") or router.get("aspectRecomposeRoute") or router.get("route") or "").strip()
        layout_type = str(router.get("layout_type") or router.get("layoutType") or "").strip()
        allowed = BusinessRunService._truthy_policy_flag(
            router.get("aspect_recompose_allowed") or router.get("aspectRecomposeAllowed")
        )
        dense = BusinessRunService._truthy_policy_flag(router.get("is_dense_small_repeat") or router.get("isDenseSmallRepeat"))
        scale_safe = BusinessRunService._truthy_policy_flag(router.get("is_scale_safe") or router.get("isScaleSafe"))
        risk_flags = router.get("riskFlags") if isinstance(router.get("riskFlags"), dict) else {}
        has_blocking_risk = any(BusinessRunService._truthy_policy_flag(value) for value in risk_flags.values())
        return (
            route == "pattern_recompose"
            and layout_type == "full_pattern"
            and allowed
            and dense
            and scale_safe
            and not has_blocking_risk
        )

    @staticmethod
    def _build_fission_aspect_guide_image(source_image: Image.Image, *, width: int, height: int) -> Image.Image:
        fit = source_image.convert("RGB")
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        fit.thumbnail((width, height), resampling)
        if fit.width <= 0 or fit.height <= 0:
            raise HTTPException(status_code=400, detail="FISSION_ASPECT_RECOMPOSE_GUIDE_FAILED")
        canvas = Image.new("RGB", (width, height))
        offset_x = -((fit.width - (width % fit.width)) // 2) if fit.width else 0
        offset_y = -((fit.height - (height % fit.height)) // 2) if fit.height else 0
        y = offset_y
        while y < height:
            x = offset_x
            while x < width:
                canvas.paste(fit, (x, y))
                x += fit.width
            y += fit.height
        return canvas

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
        include_image_edit_visual_hint: bool = False,
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
                "variation_preset",
                "reference_lock",
                "color_lock",
                "ipadapter_weight",
                "colormatch_method",
                "colormatch_strength",
                "image_desc",
                "vl_result",
                "bili_mapping",
                "pattern_risk_type",
                "object_variation_level",
                "density_risk_level",
                "max_denoise",
                "recommended_reference_lock",
                "recommended_color_lock",
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
                "aspect_recompose_route",
                "aspect_recompose_denoise",
                "aspect_recompose_guide_url",
                "guide_mode",
                "denoise",
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
        elif capability_key == "fission_evaluate":
            pass_keys = {
                "original_image",
                "generated_image",
                "context",
                "provider",
                "coze_workflow_id",
                "cozeWorkflowId",
            }
        elif capability_key == "text_fission":
            pass_keys = {
                "image_url",
                "imageUrl",
                "url",
                "editable_prompt",
                "editablePrompt",
                "prompt",
                "editable_negative_prompt",
                "editableNegativePrompt",
                "negative_prompt",
                "negativePrompt",
                "width",
                "height",
                "promptDraftId",
                "prompt_draft_id",
                "route_decision",
                "routeDecision",
                "text_items",
                "textItems",
                "vl_result",
                "text_content",
                "prompt_profile",
                "layout_card",
                "palette_card",
                "risk_notes",
            }
        elif capability_key in {"image_edit", "product_design"}:
            pass_keys = {
                "image_url",
                "imageUrl",
                "image_urls",
                "imageUrls",
                "input_urls",
                "prompt",
                "model",
                "size",
                "quality",
                "background",
                "output_format",
                "output_compression",
                "n",
                "mask_url",
                "maskUrl",
            }
        else:
            pass_keys = set(inputs)
        flat_payload = payload.model_dump(exclude_none=True, by_alias=True)
        for key in pass_keys:
            if key not in inputs and key in flat_payload:
                inputs[key] = flat_payload[key]
        if capability_key == "fission":
            self._apply_fission_variation_preset(inputs, recipe=recipe)
            self._enforce_single_output_fission_inputs(inputs)
        if capability_key == "fission_evaluate":
            original_image = self._first_string(
                inputs.get("original_image"),
                inputs.get("originalImageUrl"),
                payload.originalImageUrl,
                image_url,
            )
            generated_image = self._first_string(
                inputs.get("generated_image"),
                inputs.get("generatedImageUrl"),
                payload.generatedImageUrl,
            )
            if original_image:
                inputs["original_image"] = original_image
            if generated_image:
                inputs["generated_image"] = generated_image
            if payload.context is not None and "context" not in inputs:
                inputs["context"] = payload.context
        if capability_key == "pattern_extract" and "batch" not in inputs and "batch_size" in inputs:
            inputs["batch"] = inputs.pop("batch_size")
        if payload.prompt and "prompt" not in inputs:
            inputs["prompt"] = payload.prompt
        if capability_key == "text_fission":
            editable_prompt = self._first_string(
                inputs.get("editable_prompt"),
                inputs.get("editablePrompt"),
                payload.editable_prompt,
                payload.editablePrompt,
                payload.prompt,
                inputs.get("prompt"),
            )
            if not editable_prompt:
                raise HTTPException(status_code=400, detail="TEXT_FISSION_PROMPT_REQUIRED")
            inputs["editable_prompt"] = editable_prompt
            inputs["prompt"] = editable_prompt
            editable_negative = self._first_string(
                inputs.get("editable_negative_prompt"),
                inputs.get("editableNegativePrompt"),
                payload.editable_negative_prompt,
                payload.editableNegativePrompt,
                payload.negative_prompt,
                inputs.get("negative_prompt"),
            )
            if editable_negative:
                inputs["editable_negative_prompt"] = editable_negative
                inputs["negative_prompt"] = editable_negative
            prompt_draft_id = self._first_string(
                inputs.get("promptDraftId"),
                inputs.get("prompt_draft_id"),
                payload.promptDraftId,
                payload.prompt_draft_id,
            )
            if prompt_draft_id:
                inputs["promptDraftId"] = prompt_draft_id
            route_decision = self._first_string(
                inputs.get("route_decision"),
                inputs.get("routeDecision"),
                payload.route_decision,
                payload.routeDecision,
            )
            if route_decision:
                inputs["route_decision"] = route_decision
            text_items = self._normalize_text_fission_items(
                inputs.get("text_items"),
                inputs.get("textItems"),
                payload.text_items,
                payload.textItems,
            )
            if text_items:
                inputs["text_items"] = text_items
            self._fill_text_fission_original_size(inputs=inputs, image_url=image_url)
            # 本业务接口固定单次产出 1 张，避免一个 runId 对多张图造成回填和验收歧义。
            for noisy_key in ("count", "batch", "batch_size", "n", "steps", "cfg", "seed"):
                inputs.pop(noisy_key, None)
        image_edit_compiled: dict[str, Any] | None = None
        if capability_key == "image_edit":
            image_edit_compiled = self._compile_image_edit_inputs(
                payload=payload,
                image_url=image_url,
                validate_media=False,
                include_visual_hint=include_image_edit_visual_hint,
                trace_context=trace_context,
            )
            inputs.update(image_edit_compiled["ability_inputs"])
        product_design_compiled: dict[str, Any] | None = None
        if capability_key == "product_design":
            product_design_compiled = self._compile_product_design_inputs(
                payload=payload,
                image_url=image_url,
                include_visual_hint=include_image_edit_visual_hint,
                trace_context=trace_context,
            )
            image_edit_compiled = product_design_compiled.get("image_edit_compiler")
            inputs.update(product_design_compiled["ability_inputs"])
        if vl_summary and self._should_apply_vl_to_primary(recipe or {}):
            self._apply_vl_summary_to_inputs(
                capability_key=capability_key,
                inputs=inputs,
                pass_keys=pass_keys,
                recipe=recipe or {},
                vl_summary=vl_summary,
            )
        fission_aspect_recompose: dict[str, Any] | None = None
        if capability_key == "fission" and vl_summary:
            fission_aspect_recompose = self._maybe_apply_fission_aspect_recompose(
                inputs=inputs,
                image_url=image_url,
                recipe=recipe or {},
                vl_summary=vl_summary,
                trace_context=trace_context,
            )
            if fission_aspect_recompose and fission_aspect_recompose.get("guideImageUrl"):
                inputs["aspect_recompose_guide_url"] = fission_aspect_recompose.get("guideImageUrl")
        if capability_key == "fission":
            self._enforce_single_output_fission_inputs(inputs, keep_internal_n=True)
        project_context = self._project_context_metadata_from_payload(payload)
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
                **({"projectContext": project_context} if project_context else {}),
                **({"fissionAspectRecompose": fission_aspect_recompose} if fission_aspect_recompose else {}),
                **({"imageEditCompiler": image_edit_compiled.get("metadata")} if image_edit_compiled else {}),
                **({"productDesignCompiler": product_design_compiled.get("metadata")} if product_design_compiled else {}),
            },
        )

    def _project_context_metadata_from_payload(self, payload: BusinessRunCreateRequest) -> dict[str, Any] | None:
        metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
        nested = metadata.get("projectContext") if isinstance(metadata.get("projectContext"), dict) else {}
        inputs = payload.inputs if isinstance(payload.inputs, dict) else {}
        project_id = self._short_text(
            self._first_string(
                payload.projectId,
                metadata.get("projectId"),
                metadata.get("project_id"),
                nested.get("projectId"),
                nested.get("project_id"),
                inputs.get("projectId"),
                inputs.get("project_id"),
            ),
            64,
        )
        if not project_id:
            return None
        input_asset_ids = self._first_value(
            payload.inputAssetIds,
            metadata.get("inputAssetIds"),
            metadata.get("input_asset_ids"),
            nested.get("inputAssetIds"),
            nested.get("input_asset_ids"),
            inputs.get("inputAssetIds"),
            inputs.get("input_asset_ids"),
        )
        return {
            "projectId": project_id,
            "flowStepKey": self._short_text(
                self._first_string(
                    payload.flowStepKey,
                    metadata.get("flowStepKey"),
                    metadata.get("flow_step_key"),
                    nested.get("flowStepKey"),
                    nested.get("flow_step_key"),
                    inputs.get("flowStepKey"),
                    inputs.get("flow_step_key"),
                ),
                64,
            ),
            "flowStepName": self._short_text(
                self._first_string(
                    payload.flowStepName,
                    metadata.get("flowStepName"),
                    metadata.get("flow_step_name"),
                    nested.get("flowStepName"),
                    nested.get("flow_step_name"),
                    inputs.get("flowStepName"),
                    inputs.get("flow_step_name"),
                ),
                128,
            ),
            "flowTemplateId": self._short_text(
                self._first_string(
                    payload.flowTemplateId,
                    metadata.get("flowTemplateId"),
                    metadata.get("flow_template_id"),
                    nested.get("flowTemplateId"),
                    nested.get("flow_template_id"),
                    inputs.get("flowTemplateId"),
                    inputs.get("flow_template_id"),
                ),
                64,
            ),
            "clientRequestId": self._short_text(
                self._first_string(
                    payload.clientRequestId,
                    metadata.get("clientRequestId"),
                    metadata.get("client_request_id"),
                    nested.get("clientRequestId"),
                    nested.get("client_request_id"),
                    inputs.get("clientRequestId"),
                    inputs.get("client_request_id"),
                ),
                128,
            ),
            "inputAssetIds": self._normalize_business_key_list(
                input_asset_ids if isinstance(input_asset_ids, list) else [input_asset_ids] if input_asset_ids else []
            ),
        }

    def _compile_product_design_inputs(
        self,
        *,
        payload: BusinessRunCreateRequest,
        image_url: str,
        include_visual_hint: bool = False,
        trace_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_inputs = payload.inputs if isinstance(payload.inputs, dict) else {}
        design_brief = self._first_string(
            payload.designBrief,
            payload.design_brief,
            payload.prompt,
            request_inputs.get("designBrief"),
            request_inputs.get("design_brief"),
            request_inputs.get("brief"),
            request_inputs.get("prompt"),
        )
        if not design_brief:
            raise HTTPException(status_code=400, detail="PRODUCT_DESIGN_BRIEF_REQUIRED")

        product_type = (
            self._first_string(
                payload.productType,
                payload.product_type,
                request_inputs.get("productType"),
                request_inputs.get("product_type"),
                request_inputs.get("category"),
            )
            or "generic"
        ).strip()
        if product_type not in PRODUCT_DESIGN_PRODUCT_TYPE_VALUES:
            raise HTTPException(status_code=400, detail="PRODUCT_DESIGN_PRODUCT_TYPE_INVALID")

        scene = (
            self._first_string(
                payload.scene,
                request_inputs.get("scene"),
                request_inputs.get("usageScene"),
                request_inputs.get("usage_scene"),
            )
            or "studio_product"
        ).strip()
        if scene not in PRODUCT_DESIGN_SCENE_VALUES:
            raise HTTPException(status_code=400, detail="PRODUCT_DESIGN_SCENE_INVALID")

        reference_images = self._normalize_image_edit_reference_images(
            payload.referenceImages,
            payload.reference_images,
            request_inputs.get("referenceImages"),
            request_inputs.get("reference_images"),
            request_inputs.get("image_urls"),
            request_inputs.get("imageUrls"),
            request_inputs.get("input_urls"),
        )
        reference_mentions = "、".join(f"#参考图{idx}" for idx in range(1, len(reference_images) + 1))
        user_constraints = self._first_string(
            request_inputs.get("constraints"),
            request_inputs.get("brandGuideline"),
            request_inputs.get("brand_guideline"),
            request_inputs.get("style"),
        )
        client_context_id = self._first_string(
            payload.clientContextId,
            request_inputs.get("clientContextId"),
            request_inputs.get("client_context_id"),
            (payload.metadata or {}).get("clientContextId") if isinstance(payload.metadata, dict) else None,
        )
        compiled_instruction = self._build_product_design_instruction(
            design_brief=design_brief,
            product_type=product_type,
            scene=scene,
            reference_mentions=reference_mentions,
            constraints=user_constraints,
        )
        nested_inputs = {
            **request_inputs,
            "editSkill": "local_modify",
            "instruction": compiled_instruction,
            "referenceImages": reference_images,
        }
        if payload.quality is not None:
            nested_inputs["quality"] = payload.quality
        if payload.size is not None:
            nested_inputs["size"] = payload.size
        if payload.output_format is not None:
            nested_inputs["output_format"] = payload.output_format
        if payload.outputFormat is not None:
            nested_inputs["outputFormat"] = payload.outputFormat
        edit_payload = payload.model_copy(
            update={
                "editSkill": "local_modify",
                "instruction": compiled_instruction,
                "referenceImages": reference_images,
                "inputs": nested_inputs,
            }
        )
        image_edit_compiler = self._compile_image_edit_inputs(
            payload=edit_payload,
            image_url=image_url,
            validate_media=False,
            include_visual_hint=include_visual_hint,
            trace_context=trace_context,
        )
        return {
            "ability_inputs": image_edit_compiler["ability_inputs"],
            "image_edit_compiler": image_edit_compiler,
            "metadata": {
                "productType": product_type,
                "productTypeLabel": PRODUCT_DESIGN_PRODUCT_TYPE_LABELS.get(product_type, product_type),
                "scene": scene,
                "sceneLabel": PRODUCT_DESIGN_SCENE_LABELS.get(scene, scene),
                "designBrief": design_brief,
                "constraints": user_constraints,
                "clientContextId": client_context_id,
                "referenceImages": reference_images,
                "compiledInstruction": compiled_instruction,
                "compilerVersion": "product_design_prompt_compiler_v1",
            },
        }

    @staticmethod
    def _build_product_design_instruction(
        *,
        design_brief: str,
        product_type: str,
        scene: str,
        reference_mentions: str,
        constraints: str | None = None,
    ) -> str:
        product_label = PRODUCT_DESIGN_PRODUCT_TYPE_LABELS.get(product_type, product_type)
        scene_label = PRODUCT_DESIGN_SCENE_LABELS.get(scene, scene)
        lines = [
            f"基于主图生成一张{product_label}方向的产品设计图。",
            f"设计目标：{design_brief.strip()}",
            f"展示方式：{scene_label}。",
            "保留主图中最核心的花纹、图案语言、色彩关系或视觉资产，不要把它当成普通背景随意弱化。",
            "输出应像真实可交付的产品设计效果图：产品结构清晰，材质合理，图案贴合产品曲面或平面透视，光照、比例和边缘自然。",
            "不要生成多宫格、文字说明、过程图、界面截图、水印、价格牌或无关装饰文案。",
        ]
        if reference_mentions:
            lines.append(f"如果参考图存在，请结合 {reference_mentions} 的材质、形态或版式约束，但不要生硬拼贴。")
        if constraints:
            lines.append(f"附加约束：{constraints.strip()}")
        return "\n".join(lines)

    def _compile_image_edit_inputs(
        self,
        *,
        payload: BusinessRunCreateRequest,
        image_url: str,
        validate_media: bool = False,
        include_visual_hint: bool = False,
        trace_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_inputs = payload.inputs or {}
        skill = self._first_string(
            payload.editSkill,
            payload.edit_skill,
            request_inputs.get("editSkill"),
            request_inputs.get("edit_skill"),
            request_inputs.get("skill"),
            request_inputs.get("mode"),
        ) or "local_modify"
        skill = skill.strip()
        if skill not in IMAGE_EDIT_SKILL_VALUES:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_SKILL_INVALID")

        instruction = self._first_string(
            payload.instruction,
            request_inputs.get("instruction"),
            request_inputs.get("editInstruction"),
            request_inputs.get("edit_instruction"),
            payload.prompt,
            request_inputs.get("prompt"),
        )
        if skill == "canvas_outpaint":
            return self._compile_image_edit_canvas_outpaint_inputs(
                payload=payload,
                image_url=image_url,
                instruction=instruction or "",
                request_inputs=request_inputs,
                trace_context=trace_context,
            )
        if not instruction:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_INSTRUCTION_REQUIRED")

        selection_hints = self._normalize_image_edit_selection_hints(
            payload.selectionHints,
            payload.selection_hints,
            request_inputs.get("selectionHints"),
            request_inputs.get("selection_hints"),
            request_inputs.get("marks"),
        )
        selection_partition = self._partition_image_edit_selection_hints(
            instruction=instruction,
            selection_hints=selection_hints,
        )
        editable_selection_hints = selection_partition["editable"]
        protected_selection_hints = selection_partition["protected"]
        reference_images = self._normalize_image_edit_reference_images(
            payload.referenceImages,
            payload.reference_images,
            request_inputs.get("referenceImages"),
            request_inputs.get("reference_images"),
            request_inputs.get("image_urls"),
            request_inputs.get("imageUrls"),
            request_inputs.get("input_urls"),
        )
        mask_url = self._first_string(
            payload.maskUrl,
            payload.mask_url,
            request_inputs.get("maskUrl"),
            request_inputs.get("mask_url"),
        )

        if skill in IMAGE_EDIT_REFERENCE_REQUIRED_SKILLS and not reference_images:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_REFERENCE_REQUIRED")
        if (
            selection_hints
            and selection_partition["policy"] == "no_editable_selection_hint"
            and not mask_url
        ):
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_TARGET_REQUIRED")
        if skill in IMAGE_EDIT_TARGET_HINT_REQUIRED_SKILLS and not editable_selection_hints and not mask_url:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_TARGET_REQUIRED")
        selected_reference_images = self._select_image_edit_reference_images(
            skill=skill,
            instruction=instruction,
            reference_images=reference_images,
        )
        annotation_image = (
            self._build_image_edit_annotation_image(
                source_image_url=image_url,
                selection_hints=editable_selection_hints,
                trace_context=trace_context,
            )
            if include_visual_hint and editable_selection_hints
            else None
        )

        size = self._validate_image_edit_size(
            self._first_string(payload.size, request_inputs.get("size")) or "auto"
        )
        quality = str(
            self._first_string(payload.quality, request_inputs.get("quality")) or "auto"
        ).strip()
        if quality not in IMAGE_EDIT_QUALITY_VALUES and quality not in {"low", "medium", "high"}:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_QUALITY_INVALID")
        output_format = str(
            self._first_string(payload.outputFormat, payload.output_format, request_inputs.get("outputFormat"), request_inputs.get("output_format"))
            or "png"
        ).strip().lower()
        if output_format not in IMAGE_EDIT_OUTPUT_FORMAT_VALUES:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_OUTPUT_FORMAT_INVALID")

        mask_meta = self._first_value(payload.maskMeta, payload.mask_meta, request_inputs.get("maskMeta"), request_inputs.get("mask_meta"))
        if mask_url and validate_media:
            self._validate_image_edit_mask(image_url=image_url, mask_url=mask_url, mask_meta=mask_meta)

        auto_mask = None
        effective_mask_url = mask_url
        if not mask_url and editable_selection_hints:
            auto_mask = self._build_image_edit_selection_mask(
                source_image_url=image_url,
                selection_hints=editable_selection_hints,
                trace_context=trace_context,
            )
            if auto_mask and auto_mask.get("url"):
                effective_mask_url = str(auto_mask["url"])

        prompt = self._build_image_edit_compiled_prompt(
            skill=skill,
            instruction=instruction,
            selection_hints=editable_selection_hints,
            protected_selection_hints=protected_selection_hints,
            reference_images=selected_reference_images,
            annotation_image=annotation_image,
            mask_url=effective_mask_url,
            source_image_url=image_url,
        )
        ability_inputs: dict[str, Any] = {
            "image_url": image_url,
            "prompt": prompt,
            "model": "gpt-image-2",
            "size": size,
            "quality": IMAGE_EDIT_QUALITY_MAP.get(quality, "auto"),
            "background": "auto",
            "output_format": output_format,
            "n": 1,
        }
        if selected_reference_images:
            ability_inputs["image_urls"] = [item["url"] for item in selected_reference_images if item.get("url")]
        if annotation_image and annotation_image.get("url"):
            ability_inputs["image_urls"] = [annotation_image["url"], *ability_inputs.get("image_urls", [])]
        if effective_mask_url:
            ability_inputs["mask_url"] = effective_mask_url
        return {
            "ability_inputs": ability_inputs,
            "metadata": {
                "editSkill": skill,
                "editSkillLabel": IMAGE_EDIT_SKILL_LABELS.get(skill, skill),
                "instruction": instruction,
                "selectionHints": editable_selection_hints,
                "allSelectionHints": selection_hints,
                "protectedSelectionHints": protected_selection_hints,
                "selectionHintPolicy": selection_partition["policy"],
                "protectedMentioned": selection_partition.get("protectedMentioned", []),
                "referenceImages": selected_reference_images,
                "availableReferenceImages": reference_images,
                "annotationImage": annotation_image,
                "autoMask": auto_mask,
                "visualHintPolicy": (
                    "generated_annotation_overlay"
                    if annotation_image
                    else ("text_only_fallback" if editable_selection_hints else "no_selection_hint")
                ),
                "modelInputImages": [
                    {"role": "source", "url": image_url, "position": "图1"},
                    *(
                        [{"role": "annotation_overlay", "url": annotation_image["url"], "position": "图2"}]
                        if annotation_image and annotation_image.get("url")
                        else []
                    ),
                    *[
                        {
                            "role": "reference",
                            "url": item.get("url"),
                            "position": f"图{idx + (3 if annotation_image else 2)}",
                            "mention": item.get("mention"),
                        }
                        for idx, item in enumerate(selected_reference_images)
                    ],
                ],
                "referenceFilterPolicy": (
                    "pass_all_required_by_skill"
                    if skill in IMAGE_EDIT_REFERENCE_REQUIRED_SKILLS
                    else "pass_only_explicitly_referenced"
                ),
                "maskUrl": effective_mask_url,
                "userMaskUrl": mask_url,
                "maskMeta": mask_meta if isinstance(mask_meta, dict) else None,
                "maskPolicy": (
                    "user_mask"
                    if mask_url
                    else ("auto_selection_alpha_mask" if auto_mask and auto_mask.get("url") else "no_mask")
                ),
                "size": size,
                "quality": quality,
                "mappedQuality": ability_inputs["quality"],
                "outputFormat": output_format,
                "compiledPrompt": prompt,
                "compilerVersion": "image_edit_prompt_compiler_v1",
            },
        }

    def _compile_image_edit_canvas_outpaint_inputs(
        self,
        *,
        payload: BusinessRunCreateRequest,
        image_url: str,
        instruction: str,
        request_inputs: dict[str, Any],
        trace_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source_image = self._load_image_edit_rgba(image_url)
        source_w, source_h = source_image.size
        if source_w <= 0 or source_h <= 0:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_CANVAS_BUILD_FAILED")

        expand_left_raw = self._first_value(payload.expand_left, request_inputs.get("expand_left"), request_inputs.get("expandLeft"))
        expand_right_raw = self._first_value(payload.expand_right, request_inputs.get("expand_right"), request_inputs.get("expandRight"))
        expand_top_raw = self._first_value(payload.expand_top, request_inputs.get("expand_top"), request_inputs.get("expandTop"))
        expand_bottom_raw = self._first_value(payload.expand_bottom, request_inputs.get("expand_bottom"), request_inputs.get("expandBottom"))
        has_explicit_expand = any(value not in (None, "", []) for value in (expand_left_raw, expand_right_raw, expand_top_raw, expand_bottom_raw))
        if has_explicit_expand:
            expand_left = self._coerce_non_negative_int(expand_left_raw) or 0
            expand_right = self._coerce_non_negative_int(expand_right_raw) or 0
            expand_top = self._coerce_non_negative_int(expand_top_raw) or 0
            expand_bottom = self._coerce_non_negative_int(expand_bottom_raw) or 0
        else:
            expand_left = expand_right = expand_top = expand_bottom = 256

        target_width_input = self._first_int(
            payload.targetWidth,
            payload.target_width,
            request_inputs.get("targetWidth"),
            request_inputs.get("target_width"),
            payload.width,
            request_inputs.get("width"),
        )
        target_height_input = self._first_int(
            payload.targetHeight,
            payload.target_height,
            request_inputs.get("targetHeight"),
            request_inputs.get("target_height"),
            payload.height,
            request_inputs.get("height"),
        )
        if target_width_input is None:
            target_width_input = source_w + expand_left + expand_right
        if target_height_input is None:
            target_height_input = source_h + expand_top + expand_bottom
        if target_width_input < source_w or target_height_input < source_h:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_CANVAS_TOO_SMALL")

        requested_target_w = int(target_width_input)
        requested_target_h = int(target_height_input)
        target_w = self._round_up_to_multiple(requested_target_w, int(IMAGE_EDIT_CUSTOM_SIZE_CONSTRAINTS["multiple_of"]))
        target_h = self._round_up_to_multiple(requested_target_h, int(IMAGE_EDIT_CUSTOM_SIZE_CONSTRAINTS["multiple_of"]))
        size = self._validate_image_edit_size(f"{target_w}x{target_h}")

        placement_x_input = self._first_int(
            payload.placementX,
            payload.placement_x,
            request_inputs.get("placementX"),
            request_inputs.get("placement_x"),
        )
        placement_y_input = self._first_int(
            payload.placementY,
            payload.placement_y,
            request_inputs.get("placementY"),
            request_inputs.get("placement_y"),
        )
        anchor = (
            self._first_string(payload.anchor, request_inputs.get("anchor"))
            or ("custom" if placement_x_input is not None or placement_y_input is not None else "center")
        ).strip().lower()
        if anchor not in IMAGE_EDIT_OUTPAINT_ANCHORS:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_CANVAS_PLACEMENT_INVALID")

        if placement_x_input is not None or placement_y_input is not None:
            placement_x = placement_x_input or 0
            placement_y = placement_y_input or 0
        elif has_explicit_expand:
            min_target_w = source_w + expand_left + expand_right
            min_target_h = source_h + expand_top + expand_bottom
            if target_w < min_target_w or target_h < min_target_h:
                raise HTTPException(status_code=400, detail="IMAGE_EDIT_CANVAS_TOO_SMALL")
            slack_w = target_w - min_target_w
            slack_h = target_h - min_target_h
            if expand_left == expand_right:
                expand_left += slack_w // 2
                expand_right += slack_w - slack_w // 2
            else:
                expand_right += slack_w
            if expand_top == expand_bottom:
                expand_top += slack_h // 2
                expand_bottom += slack_h - slack_h // 2
            else:
                expand_bottom += slack_h
            placement_x = expand_left
            placement_y = expand_top
        elif target_width_input is not None or target_height_input is not None:
            placement_x, placement_y = self._image_edit_anchor_placement(
                anchor=anchor,
                target_w=target_w,
                target_h=target_h,
                source_w=source_w,
                source_h=source_h,
            )
        else:
            placement_x = expand_left
            placement_y = expand_top

        if (
            placement_x < 0
            or placement_y < 0
            or placement_x + source_w > target_w
            or placement_y + source_h > target_h
        ):
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_CANVAS_PLACEMENT_INVALID")

        actual_expand = {
            "left": int(placement_x),
            "right": int(target_w - source_w - placement_x),
            "top": int(placement_y),
            "bottom": int(target_h - source_h - placement_y),
        }
        preserve_original = self._truthy_policy_flag(
            self._first_value(
                payload.preserveOriginal,
                payload.preserve_original,
                request_inputs.get("preserveOriginal"),
                request_inputs.get("preserve_original"),
                True,
            )
        )

        canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        canvas.alpha_composite(source_image, (placement_x, placement_y))
        mask = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(mask)
        draw.rectangle(
            (placement_x, placement_y, placement_x + source_w - 1, placement_y + source_h - 1),
            fill=(0, 0, 0, 255),
        )

        canvas_upload = self._upload_image_edit_png(
            canvas,
            filename=f"image-edit-outpaint-canvas-{uuid4().hex[:10]}.png",
            trace_context=trace_context,
        )
        mask_upload = self._upload_image_edit_png(
            mask,
            filename=f"image-edit-outpaint-mask-{uuid4().hex[:10]}.png",
            trace_context=trace_context,
        )
        canvas_url = str(canvas_upload.get("url") or "")
        mask_url = str(mask_upload.get("url") or "")
        if not canvas_url or not mask_url:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_CANVAS_BUILD_FAILED")

        quality = str(
            self._first_string(payload.quality, request_inputs.get("quality")) or "auto"
        ).strip()
        if quality not in IMAGE_EDIT_QUALITY_VALUES and quality not in {"low", "medium", "high"}:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_QUALITY_INVALID")
        output_format = str(
            self._first_string(payload.outputFormat, payload.output_format, request_inputs.get("outputFormat"), request_inputs.get("output_format"))
            or "png"
        ).strip().lower()
        if output_format not in IMAGE_EDIT_OUTPUT_FORMAT_VALUES:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_OUTPUT_FORMAT_INVALID")

        prompt = self._build_image_edit_outpaint_prompt(
            instruction=instruction,
            source_image_url=image_url,
            canvas_url=canvas_url,
            mask_url=mask_url,
            source_size=(source_w, source_h),
            target_size=(target_w, target_h),
            actual_expand=actual_expand,
            preserve_original=preserve_original,
        )
        ability_inputs: dict[str, Any] = {
            "image_url": canvas_url,
            "prompt": prompt,
            "model": "gpt-image-2",
            "size": size,
            "quality": IMAGE_EDIT_QUALITY_MAP.get(quality, "auto"),
            "background": "auto",
            "output_format": output_format,
            "n": 1,
            "mask_url": mask_url,
        }
        return {
            "ability_inputs": ability_inputs,
            "metadata": {
                "editSkill": "canvas_outpaint",
                "editSkillLabel": IMAGE_EDIT_SKILL_LABELS["canvas_outpaint"],
                "instruction": instruction,
                "sourceImageUrl": image_url,
                "intermediateCanvasUrl": canvas_url,
                "outpaintMaskUrl": mask_url,
                "sourceSize": {"width": source_w, "height": source_h},
                "requestedTargetSize": {"width": requested_target_w, "height": requested_target_h},
                "targetSize": {"width": target_w, "height": target_h},
                "placement": {"x": placement_x, "y": placement_y, "anchor": anchor},
                "actualExpand": actual_expand,
                "preserveOriginal": preserve_original,
                "maskPolicy": "canvas_outpaint_alpha_mask",
                "size": size,
                "quality": quality,
                "mappedQuality": ability_inputs["quality"],
                "outputFormat": output_format,
                "compiledPrompt": prompt,
                "compilerVersion": "image_edit_canvas_outpaint_compiler_v1",
            },
        }

    @staticmethod
    def _round_up_to_multiple(value: int, multiple: int) -> int:
        if multiple <= 1:
            return int(value)
        return int(math.ceil(int(value) / multiple) * multiple)

    @staticmethod
    def _image_edit_anchor_placement(
        *,
        anchor: str,
        target_w: int,
        target_h: int,
        source_w: int,
        source_h: int,
    ) -> tuple[int, int]:
        x_center = max(0, (target_w - source_w) // 2)
        y_center = max(0, (target_h - source_h) // 2)
        right = max(0, target_w - source_w)
        bottom = max(0, target_h - source_h)
        if anchor == "left":
            return 0, y_center
        if anchor == "right":
            return right, y_center
        if anchor == "top":
            return x_center, 0
        if anchor == "bottom":
            return x_center, bottom
        if anchor == "top_left":
            return 0, 0
        if anchor == "top_right":
            return right, 0
        if anchor == "bottom_left":
            return 0, bottom
        if anchor == "bottom_right":
            return right, bottom
        return x_center, y_center

    @staticmethod
    def _coerce_non_negative_int(value: Any) -> int | None:
        if value in (None, "", []):
            return None
        try:
            number = int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None
        return number if number >= 0 else None

    @staticmethod
    def _load_image_edit_rgba(url: str) -> Image.Image:
        target = str(url or "").strip()
        if not target:
            raise HTTPException(status_code=400, detail="BUSINESS_IMAGE_URL_REQUIRED")
        try:
            response = httpx.get(target, timeout=20, follow_redirects=True)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGBA")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_CANVAS_BUILD_FAILED") from exc

    @staticmethod
    def _upload_image_edit_png(
        image: Image.Image,
        *,
        filename: str,
        trace_context: dict[str, Any] | None = None,
        apply_output_dpi: bool = False,
    ) -> dict[str, Any]:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        if apply_output_dpi:
            return media_ingest_service.upload_generated_image_bytes(
                user_id=str((trace_context or {}).get("tenantId") or "system"),
                filename=filename,
                data=buffer.getvalue(),
                content_type="image/png",
                tag="image-edit-generated-result",
            )
        return oss_service.upload_bytes(
            user_id=str((trace_context or {}).get("tenantId") or "system"),
            filename=filename,
            data=buffer.getvalue(),
            content_type="image/png",
        )

    @staticmethod
    def _build_image_edit_outpaint_prompt(
        *,
        instruction: str,
        source_image_url: str,
        canvas_url: str,
        mask_url: str,
        source_size: tuple[int, int],
        target_size: tuple[int, int],
        actual_expand: dict[str, int],
        preserve_original: bool,
    ) -> str:
        user_instruction = instruction.strip() or "自然补全透明/空白扩展区域，让画面从原图自然延展。"
        return "\n".join(
            [
                "你是专业图像扩展助手。只输出最终扩展后的图片，不输出说明文字。",
                "任务模式：扩展画布（canvas_outpaint）。",
                f"源图 URL：{source_image_url}",
                f"模型输入画布 URL：{canvas_url}",
                f"蒙版 URL：{mask_url}",
                f"源图尺寸：{source_size[0]}x{source_size[1]}；目标输出尺寸：{target_size[0]}x{target_size[1]}。",
                f"扩展像素：左 {actual_expand['left']}，右 {actual_expand['right']}，上 {actual_expand['top']}，下 {actual_expand['bottom']}。",
                f"用户扩图目标：{user_instruction}",
                "输入图片已经是目标尺寸画布，原图位于画布内部；alpha mask 的透明区域是需要补全的外扩区域，不透明区域是原图保护区。",
                "只补全外扩透明区域，不要缩放、移动、裁切或重新构图原图。",
                "补全内容必须延续原图的光照、透视、纹理、边缘、图案密度和材质逻辑，不能出现明显接缝。",
                "如果原图包含文字、商标、人物或产品主体，不要在扩展区域复制出新的主体，除非用户指令明确要求。",
                "保护原图区域：必须尽量逐像素保持原图内容、颜色、锐度和细节不变。" if preserve_original else "原图区域允许轻微融合，但不得改变主体结构。",
            ]
        )

    @staticmethod
    def _normalize_image_edit_selection_hints(*values: Any) -> list[dict[str, Any]]:
        hints: list[dict[str, Any]] = []

        def add(raw: Any, index: int | None = None) -> None:
            if raw in (None, "", []):
                return
            if isinstance(raw, str):
                text = raw.strip()
                if not text:
                    return
                if text.startswith("[") or text.startswith("{"):
                    try:
                        add(json.loads(text), index=index)
                        return
                    except Exception:
                        pass
                hints.append({"type": "text", "label": f"标注{index or len(hints) + 1}", "description": text})
                return
            if isinstance(raw, list):
                for idx, item in enumerate(raw, start=1):
                    add(item, index=idx)
                return
            if isinstance(raw, dict):
                if isinstance(raw.get("items"), list):
                    add(raw.get("items"), index=index)
                    return
                item = {
                    "type": str(raw.get("type") or raw.get("shape") or "region").strip(),
                    "label": str(raw.get("label") or raw.get("name") or f"标注{index or len(hints) + 1}").strip(),
                }
                for key in (
                    "mention",
                    "geometryText",
                    "geometry_text",
                    "points",
                    "bbox",
                    "bounds",
                    "center",
                    "radius",
                    "description",
                    "imageSize",
                    "image_size",
                ):
                    if raw.get(key) not in (None, "", []):
                        item[key] = raw.get(key)
                hints.append(item)

        for value in values:
            add(value)
        return hints[:20]

    @staticmethod
    def _normalize_image_edit_reference_images(*values: Any) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(raw: Any, index: int | None = None) -> None:
            if raw in (None, "", []):
                return
            if isinstance(raw, str):
                text = raw.strip()
                if not text:
                    return
                if text.startswith("[") or text.startswith("{"):
                    try:
                        add(json.loads(text), index=index)
                        return
                    except Exception:
                        pass
                for part in text.replace(",", "\n").splitlines():
                    url = part.strip()
                    if url:
                        add({"url": url}, index=index)
                return
            if isinstance(raw, list):
                for idx, item in enumerate(raw, start=1):
                    add(item, index=idx)
                return
            if isinstance(raw, dict):
                nested = raw.get("items") or raw.get("images") or raw.get("referenceImages") or raw.get("reference_images")
                if isinstance(nested, list):
                    add(nested, index=index)
                    return
                url = str(raw.get("url") or raw.get("imageUrl") or raw.get("image_url") or raw.get("ossUrl") or raw.get("sourceUrl") or "").strip()
                if not url or url in seen:
                    return
                seen.add(url)
                refs.append(
                    {
                        "url": url,
                        "role": str(raw.get("role") or "reference").strip(),
                        "label": str(raw.get("label") or raw.get("name") or f"参考图{len(refs) + 1}").strip(),
                        "mention": str(raw.get("mention") or f"#参考图{len(refs) + 1}").strip(),
                        "use_scope": str(raw.get("use_scope") or raw.get("useScope") or "").strip() or None,
                    }
                )

        for value in values:
            add(value)
        return refs[:8]

    @staticmethod
    def _partition_image_edit_selection_hints(
        *,
        instruction: str,
        selection_hints: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not selection_hints:
            return {"editable": [], "protected": [], "policy": "no_selection_hint", "mentioned": []}
        mention_intents = BusinessRunService._extract_image_edit_instruction_mention_intents(instruction)
        editable_mentions = mention_intents["editable"]
        protected_mentions = mention_intents["protected"]
        mentioned = [*editable_mentions, *protected_mentions]
        prepared: list[dict[str, Any]] = []
        for index, hint in enumerate(selection_hints, start=1):
            item = dict(hint)
            item.setdefault("_selectionIndex", index)
            prepared.append(item)
        if not mentioned:
            return {
                "editable": prepared,
                "protected": [],
                "policy": "all_selected_editable_no_explicit_mention",
                "mentioned": [],
            }

        editable: list[dict[str, Any]] = []
        protected: list[dict[str, Any]] = []
        editable_mentioned_set = set(editable_mentions)
        protected_mentioned_set = set(protected_mentions)
        for item in prepared:
            identities = BusinessRunService._image_edit_hint_identities(item)
            if identities & protected_mentioned_set:
                protected.append(item)
            elif identities & editable_mentioned_set:
                editable.append(item)
            else:
                protected.append(item)
        if not editable:
            return {
                "editable": [],
                "protected": protected or prepared,
                "policy": "no_editable_selection_hint",
                "mentioned": mentioned,
                "protectedMentioned": protected_mentions,
            }
        return {
            "editable": editable,
            "protected": protected,
            "policy": "only_instruction_referenced_editable",
            "mentioned": mentioned,
            "protectedMentioned": protected_mentions,
        }

    @staticmethod
    def _extract_image_edit_instruction_mention_intents(instruction: str) -> dict[str, list[str]]:
        text = str(instruction or "")
        editable: list[str] = []
        protected: list[str] = []
        seen_editable: set[str] = set()
        seen_protected: set[str] = set()
        for match in re.finditer(r"@(标注|标记)\s*(\d+)", text):
            number = str(int(match.group(2)))
            token_pair = (f"@标注{number}", f"@标记{number}")
            clause = BusinessRunService._image_edit_instruction_clause(text, match.start(), match.end())
            is_protected = BusinessRunService._image_edit_clause_is_protection_only(clause)
            target = protected if is_protected else editable
            seen = seen_protected if is_protected else seen_editable
            for token in token_pair:
                if token not in seen:
                    seen.add(token)
                    target.append(token)
        return {"editable": editable, "protected": protected}

    @staticmethod
    def _image_edit_instruction_clause(text: str, start: int, end: int) -> str:
        left = max(text.rfind(mark, 0, start) for mark in ("，", ",", "。", "；", ";", "\n"))
        right_candidates = [text.find(mark, end) for mark in ("，", ",", "。", "；", ";", "\n")]
        right_values = [item for item in right_candidates if item >= 0]
        right = min(right_values) if right_values else len(text)
        return text[left + 1 : right]

    @staticmethod
    def _image_edit_clause_is_protection_only(clause: str) -> bool:
        text = str(clause or "")
        protect_terms = (
            "保持不变",
            "不要改",
            "不要修改",
            "不修改",
            "别改",
            "禁止修改",
            "不处理",
            "保留",
            "不动",
            "维持原样",
        )
        edit_terms = ("改成", "改为", "换成", "替换", "删除", "删掉", "去掉", "变成", "调整", "优化", "修补", "补色")
        has_protect = any(term in text for term in protect_terms) or re.search(r"(?<!保持)不变", text) is not None
        has_edit = any(term in text for term in edit_terms)
        return bool(has_protect and not has_edit)

    @staticmethod
    def _image_edit_hint_identities(item: dict[str, Any]) -> set[str]:
        identities: set[str] = set()
        for key in ("mention", "label", "name"):
            raw = str(item.get(key) or "").strip()
            if not raw:
                continue
            normalized = raw if raw.startswith("@") else f"@{raw}"
            identities.add(normalized)
            match = re.search(r"(标注|标记)\s*(\d+)", raw)
            if match:
                number = str(int(match.group(2)))
                identities.add(f"@标注{number}")
                identities.add(f"@标记{number}")
        selection_index = item.get("_selectionIndex")
        try:
            number = int(selection_index)
        except (TypeError, ValueError):
            number = 0
        if number > 0:
            identities.add(f"@标注{number}")
            identities.add(f"@标记{number}")
        return identities

    def _build_image_edit_selection_mask(
        self,
        *,
        source_image_url: str,
        selection_hints: list[dict[str, Any]],
        trace_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Build an alpha mask from editable marks.

        OpenAI image edits use transparent mask pixels as the editable area.
        Everything else stays opaque so unmentioned regions are protected by
        the API contract, not just by prompt wording.
        """

        if not source_image_url or not selection_hints:
            return None
        try:
            response = httpx.get(source_image_url, timeout=20, follow_redirects=True)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGBA")
            width, height = image.size
            if width <= 0 or height <= 0:
                return None

            mask = Image.new("RGBA", image.size, (0, 0, 0, 255))
            draw = ImageDraw.Draw(mask)
            transparent = (0, 0, 0, 0)
            base_padding = max(8, round(min(width, height) * 0.012))
            point_radius = max(28, round(min(width, height) * 0.035))

            for hint in selection_hints[:20]:
                shape = str(hint.get("type") or "region").strip().lower()
                center = self._image_edit_hint_center(hint, width=width, height=height)
                bounds = self._image_edit_hint_bounds(hint, width=width, height=height)
                if shape == "point" and center:
                    x, y = center
                    draw.ellipse(
                        (x - point_radius, y - point_radius, x + point_radius, y + point_radius),
                        fill=transparent,
                    )
                    continue
                if bounds:
                    padded = self._pad_image_edit_bounds(
                        bounds,
                        width=width,
                        height=height,
                        padding=base_padding,
                    )
                    if shape in {"circle", "ellipse"}:
                        draw.ellipse(padded, fill=transparent)
                    else:
                        draw.rectangle(padded, fill=transparent)
                    continue
                if center:
                    x, y = center
                    draw.ellipse(
                        (x - point_radius, y - point_radius, x + point_radius, y + point_radius),
                        fill=transparent,
                    )

            buffer = BytesIO()
            mask.save(buffer, format="PNG")
            upload = oss_service.upload_bytes(
                user_id=str((trace_context or {}).get("tenantId") or "system"),
                filename=f"image-edit-mask-{uuid4().hex[:10]}.png",
                data=buffer.getvalue(),
                content_type="image/png",
            )
            return {
                "url": upload.get("url"),
                "ossKey": upload.get("objectKey"),
                "role": "selection_alpha_mask",
                "label": "自动标注蒙版",
                "editableSelectionCount": len(selection_hints),
                "description": "透明区域为本次允许编辑的标注范围；不透明区域保持不变。",
            }
        except Exception as exc:  # noqa: BLE001 - fall back to prompt/annotation if mask generation fails.
            logger.warning("image_edit selection mask generation failed: %s", exc)
            return None

    def _build_image_edit_annotation_image(
        self,
        *,
        source_image_url: str,
        selection_hints: list[dict[str, Any]],
        trace_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Render user marks into a visible locator image for the editing model.

        Coordinates in text are weak. The extra image gives GPT Image 2 a visual
        reference for which object each @标注 points at, while the prompt tells it
        not to copy red circles or labels into the output.
        """

        if not source_image_url or not selection_hints:
            return None
        try:
            response = httpx.get(source_image_url, timeout=20, follow_redirects=True)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGBA")
            width, height = image.size
            if width <= 0 or height <= 0:
                return None

            overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            line_width = max(6, round(min(width, height) * 0.004))
            point_radius = max(22, round(min(width, height) * 0.022))
            red = (239, 68, 68, 255)
            red_fill = (239, 68, 68, 45)
            label_bg = (220, 38, 38, 245)
            white = (255, 255, 255, 255)

            for index, hint in enumerate(selection_hints[:20], start=1):
                shape = str(hint.get("type") or "region").strip().lower()
                label = str(index)
                bounds = self._image_edit_hint_bounds(hint, width=width, height=height)
                center = self._image_edit_hint_center(hint, width=width, height=height)
                if shape == "point" and center:
                    x, y = center
                    draw.ellipse(
                        (x - point_radius, y - point_radius, x + point_radius, y + point_radius),
                        outline=red,
                        width=line_width,
                    )
                    draw.line((x - point_radius, y, x + point_radius, y), fill=red, width=max(2, line_width // 2))
                    draw.line((x, y - point_radius, x, y + point_radius), fill=red, width=max(2, line_width // 2))
                    self._draw_image_edit_annotation_label(
                        draw,
                        label=label,
                        x=x + point_radius + 8,
                        y=y - point_radius - 8,
                        fill=label_bg,
                        text_fill=white,
                    )
                    continue
                if shape in {"rect", "rectangle", "box", "circle", "ellipse", "freehand", "path", "region"} and bounds:
                    left, top, right, bottom = bounds
                    if shape in {"circle", "ellipse"}:
                        draw.ellipse((left, top, right, bottom), outline=red, width=line_width, fill=red_fill)
                    else:
                        draw.rectangle((left, top, right, bottom), outline=red, width=line_width, fill=red_fill)
                    self._draw_image_edit_annotation_label(
                        draw,
                        label=label,
                        x=left + 8,
                        y=max(8, top - point_radius - 8),
                        fill=label_bg,
                        text_fill=white,
                    )
                    continue
                if center:
                    x, y = center
                    draw.ellipse(
                        (x - point_radius, y - point_radius, x + point_radius, y + point_radius),
                        outline=red,
                        width=line_width,
                    )
                    self._draw_image_edit_annotation_label(
                        draw,
                        label=label,
                        x=x + point_radius + 8,
                        y=y - point_radius - 8,
                        fill=label_bg,
                        text_fill=white,
                    )

            composed = Image.alpha_composite(image, overlay).convert("RGB")
            buffer = BytesIO()
            composed.save(buffer, format="PNG")
            upload = oss_service.upload_bytes(
                user_id=str((trace_context or {}).get("tenantId") or "system"),
                filename=f"image-edit-annotation-{uuid4().hex[:10]}.png",
                data=buffer.getvalue(),
                content_type="image/png",
            )
            return {
                "url": upload.get("url"),
                "ossKey": upload.get("objectKey"),
                "role": "annotation_overlay",
                "label": "标注定位图",
                "description": "红色编号只用于定位 @标注，不应出现在最终结果图。",
            }
        except Exception as exc:  # noqa: BLE001 - visual hints must not block editing fallback.
            logger.warning("image_edit annotation overlay generation failed: %s", exc)
            return None

    @staticmethod
    def _draw_image_edit_annotation_label(
        draw: ImageDraw.ImageDraw,
        *,
        label: str,
        x: float,
        y: float,
        fill: tuple[int, int, int, int],
        text_fill: tuple[int, int, int, int],
    ) -> None:
        x = max(6, float(x))
        y = max(6, float(y))
        text = str(label or "")
        pad_x = 10
        pad_y = 7
        try:
            bbox = draw.textbbox((0, 0), text)
            text_w = max(16, bbox[2] - bbox[0])
            text_h = max(16, bbox[3] - bbox[1])
        except Exception:
            text_w = 18
            text_h = 18
        box = (x, y, x + text_w + pad_x * 2, y + text_h + pad_y * 2)
        draw.rounded_rectangle(box, radius=8, fill=fill)
        draw.text((x + pad_x, y + pad_y), text, fill=text_fill)

    @staticmethod
    def _image_edit_hint_center(hint: dict[str, Any], *, width: int, height: int) -> tuple[float, float] | None:
        points = hint.get("points")
        if isinstance(points, list) and points:
            first = points[0]
            if isinstance(first, dict):
                x = BusinessRunService._first_number(first.get("x"))
                y = BusinessRunService._first_number(first.get("y"))
                if x is not None and y is not None:
                    return BusinessRunService._clamp_point(x, y, width=width, height=height)
        center = hint.get("center")
        if isinstance(center, dict):
            x = BusinessRunService._first_number(center.get("x"))
            y = BusinessRunService._first_number(center.get("y"))
            if x is not None and y is not None:
                return BusinessRunService._clamp_point(x, y, width=width, height=height)
        bounds = BusinessRunService._image_edit_hint_bounds(hint, width=width, height=height)
        if bounds:
            left, top, right, bottom = bounds
            return ((left + right) / 2, (top + bottom) / 2)
        return None

    @staticmethod
    def _image_edit_hint_bounds(hint: dict[str, Any], *, width: int, height: int) -> tuple[float, float, float, float] | None:
        bbox = hint.get("bbox") or hint.get("bounds")
        if isinstance(bbox, dict):
            x = BusinessRunService._first_number(bbox.get("x"), bbox.get("left"))
            y = BusinessRunService._first_number(bbox.get("y"), bbox.get("top"))
            w = BusinessRunService._first_number(bbox.get("width"), bbox.get("w"))
            h = BusinessRunService._first_number(bbox.get("height"), bbox.get("h"))
            right = BusinessRunService._first_number(bbox.get("right"))
            bottom = BusinessRunService._first_number(bbox.get("bottom"))
            if x is not None and y is not None:
                if w is not None and h is not None:
                    return BusinessRunService._clamp_bounds(x, y, x + w, y + h, width=width, height=height)
                if right is not None and bottom is not None:
                    return BusinessRunService._clamp_bounds(x, y, right, bottom, width=width, height=height)
        points = hint.get("points")
        if isinstance(points, list) and len(points) >= 2:
            coords: list[tuple[float, float]] = []
            for item in points:
                if not isinstance(item, dict):
                    continue
                x = BusinessRunService._first_number(item.get("x"))
                y = BusinessRunService._first_number(item.get("y"))
                if x is not None and y is not None:
                    coords.append(BusinessRunService._clamp_point(x, y, width=width, height=height))
            if coords:
                xs = [item[0] for item in coords]
                ys = [item[1] for item in coords]
                return BusinessRunService._clamp_bounds(min(xs), min(ys), max(xs), max(ys), width=width, height=height)
        return None

    @staticmethod
    def _clamp_point(x: float, y: float, *, width: int, height: int) -> tuple[float, float]:
        return (
            max(0.0, min(float(width - 1), float(x))),
            max(0.0, min(float(height - 1), float(y))),
        )

    @staticmethod
    def _clamp_bounds(
        left: float,
        top: float,
        right: float,
        bottom: float,
        *,
        width: int,
        height: int,
    ) -> tuple[float, float, float, float]:
        x1, y1 = BusinessRunService._clamp_point(left, top, width=width, height=height)
        x2, y2 = BusinessRunService._clamp_point(right, bottom, width=width, height=height)
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    @staticmethod
    def _pad_image_edit_bounds(
        bounds: tuple[float, float, float, float],
        *,
        width: int,
        height: int,
        padding: int,
    ) -> tuple[float, float, float, float]:
        left, top, right, bottom = bounds
        return BusinessRunService._clamp_bounds(
            left - padding,
            top - padding,
            right + padding,
            bottom + padding,
            width=width,
            height=height,
        )

    @staticmethod
    def _select_image_edit_reference_images(
        *,
        skill: str,
        instruction: str,
        reference_images: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not reference_images:
            return []
        if skill in IMAGE_EDIT_REFERENCE_REQUIRED_SKILLS:
            return reference_images
        text = str(instruction or "")
        indexes: set[int] = set()
        for match in re.finditer(r"#(?:参考图)?\s*(\d+)", text):
            try:
                value = int(match.group(1))
            except ValueError:
                continue
            if value > 0:
                indexes.add(value - 1)
        for idx, item in enumerate(reference_images):
            label = str(item.get("label") or "").strip()
            mention = str(item.get("mention") or "").strip()
            if label and (f"#{label}" in text or label in text):
                indexes.add(idx)
            if mention and mention in text:
                indexes.add(idx)
        if not indexes:
            return []
        # Preserve original order and include earlier references when needed so
        # user-visible #1/#2 numbering still matches model image order.
        max_index = min(max(indexes), len(reference_images) - 1)
        return reference_images[: max_index + 1]

    def _validate_image_edit_size(self, value: str) -> str:
        size = str(value or "auto").strip().lower()
        if size == "auto" or size in IMAGE_EDIT_SIZE_VALUES:
            return size
        if "x" not in size:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_SIZE_INVALID")
        left, right = size.split("x", 1)
        try:
            width = int(left)
            height = int(right)
        except ValueError:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_SIZE_INVALID") from None
        constraints = IMAGE_EDIT_CUSTOM_SIZE_CONSTRAINTS
        if width <= 0 or height <= 0:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_SIZE_INVALID")
        if max(width, height) > int(constraints["max_edge"]):
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_SIZE_INVALID")
        if width % int(constraints["multiple_of"]) != 0 or height % int(constraints["multiple_of"]) != 0:
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_SIZE_INVALID")
        if max(width, height) / max(1, min(width, height)) > float(constraints["max_aspect_ratio"]):
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_SIZE_INVALID")
        pixels = width * height
        if pixels < int(constraints["min_pixels"]) or pixels > int(constraints["max_pixels"]):
            raise HTTPException(status_code=400, detail="IMAGE_EDIT_SIZE_INVALID")
        return f"{width}x{height}"

    def _validate_image_edit_mask(self, *, image_url: str, mask_url: str, mask_meta: Any | None) -> None:
        source_size: tuple[int, int] | None = None
        if isinstance(mask_meta, dict):
            source_w = self._coerce_positive_int(mask_meta.get("sourceWidth") or mask_meta.get("source_width"))
            source_h = self._coerce_positive_int(mask_meta.get("sourceHeight") or mask_meta.get("source_height"))
            mask_w = self._coerce_positive_int(mask_meta.get("width") or mask_meta.get("maskWidth") or mask_meta.get("mask_width"))
            mask_h = self._coerce_positive_int(mask_meta.get("height") or mask_meta.get("maskHeight") or mask_meta.get("mask_height"))
            if source_w and source_h and mask_w and mask_h and (source_w != mask_w or source_h != mask_h):
                raise HTTPException(status_code=400, detail="IMAGE_EDIT_MASK_SIZE_MISMATCH")
        source_info = self._read_remote_image_info(image_url)
        mask_info = self._read_remote_image_info(mask_url)
        if source_info:
            source_size = (int(source_info["width"]), int(source_info["height"]))
        if mask_info:
            if source_size and (int(mask_info["width"]), int(mask_info["height"])) != source_size:
                raise HTTPException(status_code=400, detail="IMAGE_EDIT_MASK_SIZE_MISMATCH")
            if mask_info.get("has_alpha") is False:
                raise HTTPException(status_code=400, detail="IMAGE_EDIT_MASK_ALPHA_REQUIRED")

    @staticmethod
    def _coerce_positive_int(value: Any) -> int | None:
        if value in (None, "", []):
            return None
        try:
            number = int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _build_image_edit_compiled_prompt(
        *,
        skill: str,
        instruction: str,
        selection_hints: list[dict[str, Any]],
        protected_selection_hints: list[dict[str, Any]],
        reference_images: list[dict[str, Any]],
        annotation_image: dict[str, Any] | None,
        mask_url: str | None,
        source_image_url: str,
    ) -> str:
        skill_label = IMAGE_EDIT_SKILL_LABELS.get(skill, skill)

        hint_lines = [
            BusinessRunService._format_image_edit_hint_line(item, index=idx)
            for idx, item in enumerate(selection_hints, start=1)
        ] or ["无；如果没有标注，请按用户指令作用于最合理的目标区域。"]
        protected_lines = [
            BusinessRunService._format_image_edit_hint_line(item, index=int(item.get("_selectionIndex") or idx))
            for idx, item in enumerate(protected_selection_hints, start=1)
        ]
        extra_rules = BusinessRunService._build_image_edit_extra_rules(instruction)
        ref_offset = 2 if annotation_image else 1
        ref_lines = [
            f"图{idx + ref_offset}={item.get('mention') or item.get('label') or f'参考图{idx}'}：{item.get('url')}"
            for idx, item in enumerate(reference_images, start=1)
        ] or ["无"]
        image_order = "图1 是主图。"
        if annotation_image:
            image_order += " 图2 是红色编号标注定位图，只用于理解 @标注 的位置，不要把红圈、编号或文字画进最终结果。"
            if reference_images:
                image_order += " 图3 及之后是用户参考图。"
        elif reference_images:
            image_order += " 图2 及之后是用户参考图。"
        return "\n".join(
            [
                "你是专业图像编辑助手。只输出最终编辑后的图片，不输出说明文字。",
                f"任务模式：{skill_label}（{skill}）。",
                f"图像顺序：{image_order} 所有编辑只作用于图1；后续图片只作为定位或参考，不要直接拼贴。",
                f"主图 URL：{source_image_url}",
                f"用户编辑指令：{instruction.strip()}",
                "标注/区域提示：",
                *hint_lines,
                *(
                    ["未被本次指令引用的标注（禁止修改）：", *protected_lines]
                    if protected_lines
                    else []
                ),
                "执行规则：只允许修改用户编辑指令中明确引用的 @标注；如果用户说“改成/换成”，请替换对应 @标注 所在的完整对象，不要在旁边额外新增对象；多个 @标注 要分别处理，不要把一个标注的颜色或对象扩散到其他区域。",
                "保护规则：未被用户编辑指令明确引用的标注、相同或相似对象、背景、文字、边框和装饰元素都必须保持不变。",
                *extra_rules,
                "参考图：",
                *ref_lines,
                f"标注定位图：{'已提供红色编号辅助图，红色编号 1/2/3... 与 @标注1/@标注2/@标注3... 一一对应。' if annotation_image else '未提供，只能按文字坐标理解。'}",
                f"蒙版：{'已提供；只允许修改 alpha mask 的透明区域，不透明区域必须保持不变。' if mask_url else '未提供，按标注提示和用户指令判断目标区域。'}",
                "编辑要求：保持未指定区域不变，保持整体光照、透视、材质和风格一致；参考图只提取对象、颜色或材质特征，不可生硬拼贴；不要改变画面比例，除非请求参数显式指定尺寸。",
            ]
        )

    @staticmethod
    def _format_image_edit_hint_line(item: dict[str, Any], *, index: int) -> str:
        mention = str(item.get("mention") or f"@标注{index}").strip()
        label = str(item.get("label") or mention).strip()
        shape = str(item.get("type") or "region").strip()
        geometry = str(item.get("geometryText") or item.get("geometry_text") or "").strip()
        if not geometry:
            points = item.get("points")
            if isinstance(points, list) and points:
                geometry = f"{len(points)} 个点"
            elif item.get("bbox") or item.get("bounds"):
                geometry = "框选区域"
        return f"{index}. {mention}：红色编号 {index}；类型={shape}；名称={label}；位置={geometry or '见标注定位图'}。"

    @staticmethod
    def _build_image_edit_extra_rules(instruction: str) -> list[str]:
        text = str(instruction or "")
        rules: list[str] = []
        if "乒乓球" in text or "兵乓球" in text:
            rules.append("特别约束：如果目标是乒乓球，只生成单独的乒乓球；不要生成球拍、手、人物、球网、文字或任何额外运动装备。")
        if "删掉" in text or "删除" in text or "去掉" in text:
            rules.append("删除约束：只清除被明确引用的目标对象，并用周围背景自然补齐；不要删除其他相似对象。")
        return rules

    def _fill_text_fission_original_size(self, *, inputs: dict[str, Any], image_url: str) -> None:
        """Text-to-image fission should keep source aspect by default.

        Callers may still override width/height explicitly. If either dimension is
        omitted, read the source image once and fill the missing dimension before
        the ComfyUI adapter applies its 8px-safe normalization.
        """

        width_explicit = self._is_positive_dimension(inputs.get("width"))
        height_explicit = self._is_positive_dimension(inputs.get("height"))
        if width_explicit and height_explicit:
            return
        source_size = self._read_remote_image_size(image_url)
        if not source_size:
            return
        width, height = source_size
        if not width_explicit:
            inputs["width"] = width
        if not height_explicit:
            inputs["height"] = height

    @staticmethod
    def _is_positive_dimension(value: Any) -> bool:
        if value in (None, "", []):
            return False
        try:
            return int(float(str(value).strip())) > 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _read_remote_image_size(url: str) -> tuple[int, int] | None:
        target = str(url or "").strip()
        if not target:
            return None
        try:
            response = httpx.get(target, timeout=15, follow_redirects=True)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            width, height = image.size
            if width > 0 and height > 0:
                return int(width), int(height)
        except Exception:
            return None
        return None

    @staticmethod
    def _read_remote_image_info(url: str) -> dict[str, Any] | None:
        target = str(url or "").strip()
        if not target:
            return None
        try:
            response = httpx.get(target, timeout=15, follow_redirects=True)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            width, height = image.size
            if width <= 0 or height <= 0:
                return None
            has_alpha = "A" in image.getbands() or "transparency" in image.info
            return {"width": int(width), "height": int(height), "has_alpha": bool(has_alpha)}
        except Exception:
            return None

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

    @classmethod
    def _recipe_control_issues(cls, *, recipe: dict[str, Any], session=None) -> list[dict[str, Any]]:
        """Return structural recipe issues that would otherwise surface only at runtime."""

        issues: list[dict[str, Any]] = []
        normalized_steps = cls._normalized_recipe_steps(recipe)
        seen_step_ids: set[str] = set()
        duplicate_step_ids: list[str] = []
        primary_ability_id: str | None = None
        try:
            primary_ability_id = cls._extract_primary_ability_id(recipe)
        except HTTPException:
            primary_ability_id = None

        for step in normalized_steps:
            if step.get("enabled") is False:
                continue
            step_id = str(step.get("id") or "").strip()
            if step_id:
                if step_id in seen_step_ids and step_id not in duplicate_step_ids:
                    duplicate_step_ids.append(step_id)
                seen_step_ids.add(step_id)

            step_type = str(step.get("type") or "").strip()
            ability_id = cls._extract_step_ability_id(step)
            is_executable = step_type in RECIPE_EXECUTABLE_STEP_TYPES or bool(ability_id)
            if not is_executable:
                continue
            if not ability_id:
                issues.append(
                    {
                        "code": "BUSINESS_GOVERNANCE_STEP_ABILITY_MISSING",
                        "stepId": step_id,
                        "detail": "可执行步骤缺少 abilityId。",
                    }
                )
                continue
            if session is None:
                continue
            ability = session.get(Ability, ability_id)
            if ability is None:
                issues.append(
                    {
                        "code": "BUSINESS_GOVERNANCE_STEP_ABILITY_NOT_FOUND",
                        "stepId": step_id,
                        "abilityId": ability_id,
                        "detail": "配方引用的能力在能力目录中不存在。",
                    }
                )
            elif ability.status != "active":
                issues.append(
                    {
                        "code": "BUSINESS_GOVERNANCE_STEP_ABILITY_INACTIVE",
                        "stepId": step_id,
                        "abilityId": ability_id,
                        "detail": "配方引用的能力未启用。",
                    }
                )

        if duplicate_step_ids:
            issues.append(
                {
                    "code": "BUSINESS_GOVERNANCE_RECIPE_STEP_ID_DUPLICATED",
                    "stepIds": duplicate_step_ids,
                    "detail": "配方步骤编号重复，编排图和运行步骤可能无法一一对应。",
                }
            )

        primary_steps = [
            step
            for step in normalized_steps
            if step.get("enabled") is not False
            and (str(step.get("role") or "").strip() == "primary" or str(step.get("id") or "").strip() == "primary")
        ]
        mismatched_primary_steps = [
            step
            for step in primary_steps
            if primary_ability_id and cls._extract_step_ability_id(step) and cls._extract_step_ability_id(step) != primary_ability_id
        ]
        if mismatched_primary_steps:
            issues.append(
                {
                    "code": "BUSINESS_GOVERNANCE_RECIPE_PRIMARY_STEP_MISMATCH",
                    "primaryAbilityId": primary_ability_id,
                    "stepIds": [str(step.get("id") or "").strip() for step in mismatched_primary_steps],
                    "detail": "primaryAbilityId 与主步骤绑定的能力不一致。",
                }
            )
        return issues

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
                "inputSchema": self._summarize_ability_input_schema(ability.input_schema, ability=ability)
                if ability
                else None,
                "defaultParams": self._compact_graph_json(ability.default_params) if ability else None,
                "routing": self._ability_routing_summary(ability) if ability else None,
                "recipeInputs": self._compact_graph_json(self._extract_step_inputs(step)),
                "recipeOutputs": self._compact_graph_json(step.get("outputs") if isinstance(step.get("outputs"), dict) else None),
            }
            rows.append({key: value for key, value in item.items() if value is not None})
        return rows

    @staticmethod
    def _recipe_step_runtime_evidence(
        *,
        session,
        business_version_id: str | None,
        steps: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        if session is None or not business_version_id or not steps:
            return {}
        step_ids = {
            str(step.get("id") or "").strip()
            for step in steps
            if str(step.get("id") or "").strip()
        }
        ability_ids = {
            str(step.get("abilityId") or "").strip()
            for step in steps
            if str(step.get("abilityId") or "").strip()
        }
        if not step_ids and not ability_ids:
            return {}

        conditions = []
        if step_ids:
            conditions.append(BusinessRunStep.step_id.in_(step_ids))
        if ability_ids:
            conditions.append(BusinessRunStep.ability_id.in_(ability_ids))
        if not conditions:
            return {}

        # Keep this query index-friendly. Sorting joined step rows across all
        # historical runs has triggered MySQL "Out of sort memory" on 114 even
        # with modest data volume, so first narrow by recent runs and only sort
        # the small in-memory result set.
        recent_runs = (
            session.execute(
                select(
                    BusinessRun.id,
                    BusinessRun.status,
                    BusinessRun.created_at,
                    BusinessRun.error_message,
                )
                .where(BusinessRun.business_version_id == business_version_id)
                .order_by(BusinessRun.created_at.desc())
                .limit(240)
            )
            .all()
        )
        run_by_id = {str(row.id): row for row in recent_runs if row.id}
        if not run_by_id:
            return {}
        step_rows = (
            session.execute(
                select(
                    BusinessRunStep.id,
                    BusinessRunStep.run_id,
                    BusinessRunStep.step_id,
                    BusinessRunStep.ability_id,
                    BusinessRunStep.status,
                    BusinessRunStep.created_at,
                    BusinessRunStep.finished_at,
                    BusinessRunStep.duration_ms,
                    BusinessRunStep.ability_task_id,
                    BusinessRunStep.ability_log_id,
                    BusinessRunStep.error_message,
                )
                .where(BusinessRunStep.run_id.in_(run_by_id.keys()))
                .limit(1200)
            )
            .all()
        )
        step_id_set = set(step_ids)
        ability_id_set = set(ability_ids)
        rows = [
            (step_row, run_by_id[str(step_row.run_id)])
            for step_row in step_rows
            if step_row.run_id and str(step_row.run_id) in run_by_id
            and (
                (step_row.step_id and str(step_row.step_id).strip() in step_id_set)
                or (step_row.ability_id and str(step_row.ability_id).strip() in ability_id_set)
            )
        ]
        rows.sort(key=lambda item: item[0].created_at or item[1].created_at or datetime.min, reverse=True)
        rows = rows[:240]
        if not rows:
            return {}

        now = datetime.utcnow()
        window_hours = 24
        since = now - timedelta(hours=window_hours)
        evidence: dict[str, dict[str, Any]] = {}
        step_id_to_node = {
            str(step.get("id") or "").strip(): BusinessRunService._graph_node_id(
                step.get("id"), fallback=f"step_{step.get('order') or index + 1}"
            )
            for index, step in enumerate(steps)
            if str(step.get("id") or "").strip()
        }
        ability_to_nodes: dict[str, list[str]] = {}
        for index, step in enumerate(steps):
            ability_id = str(step.get("abilityId") or "").strip()
            if not ability_id:
                continue
            node_id = BusinessRunService._graph_node_id(
                step.get("id"),
                fallback=f"step_{step.get('order') or index + 1}",
            )
            ability_to_nodes.setdefault(ability_id, []).append(node_id)

        def sample(step_row: BusinessRunStep, run_row: BusinessRun) -> dict[str, Any]:
            return {
                key: value
                for key, value in {
                    "runId": run_row.id,
                    "status": step_row.status,
                    "runStatus": run_row.status,
                    "createdAt": step_row.created_at,
                    "finishedAt": step_row.finished_at,
                    "durationMs": step_row.duration_ms,
                    "abilityTaskId": step_row.ability_task_id,
                    "abilityLogId": step_row.ability_log_id,
                    "error": step_row.error_message or run_row.error_message,
                }.items()
                if value not in (None, "", [])
            }

        for step_row, run_row in rows:
            candidate_node_ids: list[str] = []
            if step_row.step_id:
                node_id = step_id_to_node.get(str(step_row.step_id).strip())
                if node_id:
                    candidate_node_ids.append(node_id)
            if step_row.ability_id:
                candidate_node_ids.extend(ability_to_nodes.get(str(step_row.ability_id).strip(), []))
            for node_id in dict.fromkeys(candidate_node_ids):
                item = evidence.setdefault(
                    node_id,
                    {
                        "windowHours": window_hours,
                        "total": 0,
                        "succeeded": 0,
                        "failed": 0,
                        "running": 0,
                        "queued": 0,
                        "latest": None,
                        "latestSuccess": None,
                        "latestFailure": None,
                    },
                )
                created_at = step_row.created_at
                if created_at and created_at >= since:
                    item["total"] += 1
                    status = str(step_row.status or "").strip().lower()
                    if status in {"succeeded", "success", "completed"}:
                        item["succeeded"] += 1
                    elif status in {"failed", "error", "timeout", "cancelled"}:
                        item["failed"] += 1
                    elif status == "running":
                        item["running"] += 1
                    elif status in {"queued", "pending"}:
                        item["queued"] += 1
                current_sample = sample(step_row, run_row)
                if item["latest"] is None:
                    item["latest"] = current_sample
                status = str(step_row.status or "").strip().lower()
                if item["latestSuccess"] is None and status in {"succeeded", "success", "completed"}:
                    item["latestSuccess"] = current_sample
                if item["latestFailure"] is None and status in {"failed", "error", "timeout", "cancelled"}:
                    item["latestFailure"] = current_sample

        return {
            node_id: {key: value for key, value in item.items() if value not in (None, "", [])}
            for node_id, item in evidence.items()
        }

    def _build_recipe_orchestration_graph(
        self,
        recipe: dict[str, Any],
        *,
        session=None,
        business_key: str | None = None,
        business_version_id: str | None = None,
        business_version: str | None = None,
        business_display_name: str | None = None,
    ) -> dict[str, Any]:
        steps = self._recipe_steps_to_dict(recipe, session=session)
        runtime_evidence = self._recipe_step_runtime_evidence(
            session=session,
            business_version_id=business_version_id,
            steps=steps,
        )
        nodes: list[dict[str, Any]] = [
            {
                "id": "entry",
                "type": "entry",
                "role": "entry",
                "label": "业务入口",
                "order": 0,
                "status": "planned",
                "businessKey": business_key,
                "version": business_version,
                "displayName": business_display_name,
            }
        ]
        edges: list[dict[str, Any]] = []
        previous_id = "entry"
        executable_count = 0
        for step in steps:
            node_id = self._graph_node_id(step.get("id"), fallback=f"step_{step.get('order') or len(nodes)}")
            enabled = step.get("enabled") is not False
            if enabled and str(step.get("type") or "").strip() in RECIPE_EXECUTABLE_STEP_TYPES:
                executable_count += 1
            nodes.append(
                self._compact_graph_node(
                    {
                        "id": node_id,
                        "type": step.get("type") or "ability_task",
                        "role": step.get("role"),
                        "label": step.get("displayName") or step.get("abilityName") or node_id,
                        "order": step.get("order"),
                        "status": "planned" if enabled else "skipped",
                        "enabled": enabled,
                        "abilityId": step.get("abilityId"),
                        "abilityName": step.get("abilityName"),
                        "abilityProvider": step.get("abilityProvider"),
                        "inputSchema": step.get("inputSchema"),
                        "defaultParams": step.get("defaultParams"),
                        "routing": step.get("routing"),
                        "recipeInputs": step.get("recipeInputs"),
                        "recipeOutputs": step.get("recipeOutputs"),
                        "runtimeEvidence": runtime_evidence.get(node_id),
                    }
                )
            )
            edges.append({"id": f"{previous_id}->{node_id}", "source": previous_id, "target": node_id})
            previous_id = node_id
        nodes.append(
            {
                "id": "result",
                "type": "result",
                "role": "result",
                "label": "结果回填",
                "order": len(nodes),
                "status": "planned",
            }
        )
        edges.append({"id": f"{previous_id}->result", "source": previous_id, "target": "result"})
        return {
            "version": 1,
            "mode": "recipe",
            "businessKey": business_key,
            "businessVersionId": business_version_id,
            "businessVersion": business_version,
            "businessDisplayName": business_display_name,
            "nodes": nodes,
            "edges": edges,
            "summary": {
                "stepCount": len(steps),
                "executableStepCount": executable_count,
                "hasVlStep": any(str(step.get("type") or "").startswith("vl_") for step in steps),
                "hasPrimaryStep": any(str(step.get("role") or "") == "primary" for step in steps),
            },
        }

    def _build_run_orchestration_graph(
        self,
        row: BusinessRun,
        *,
        steps: list[dict[str, Any]],
        route_info: dict[str, Any] | None,
        flow_summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        route = route_info if isinstance(route_info, dict) else {}
        flow = flow_summary if isinstance(flow_summary, dict) else {}
        output = flow.get("output") if isinstance(flow.get("output"), dict) else {}
        nodes: list[dict[str, Any]] = [
            {
                "id": "entry",
                "type": "entry",
                "role": "entry",
                "label": "业务入口",
                "order": 0,
                "status": "succeeded" if steps or row.status not in {"queued", "running"} else row.status,
                "businessKey": row.business_key,
                "version": row.version,
            }
        ]
        edges: list[dict[str, Any]] = []
        previous_id = "entry"
        active_node_id: str | None = None
        for index, step in enumerate(steps, start=1):
            node_id = self._graph_node_id(
                step.get("step_id") or step.get("id"),
                fallback=f"step_{step.get('step_order') or index}",
            )
            status = str(step.get("status") or "").strip().lower()
            if active_node_id is None and status in {"failed", "running", "queued"}:
                active_node_id = node_id
            evidence = step.get("execution_evidence") if isinstance(step.get("execution_evidence"), dict) else {}
            result_summary = step.get("result_summary") if isinstance(step.get("result_summary"), dict) else {}
            nodes.append(
                self._compact_graph_node(
                    {
                        "id": node_id,
                        "type": step.get("step_type") or "ability_task",
                        "role": step.get("role"),
                        "label": step.get("display_name") or step.get("ability_name") or step.get("step_id") or node_id,
                        "order": step.get("step_order") or index,
                        "status": step.get("status"),
                        "enabled": step.get("enabled"),
                        "abilityId": step.get("ability_id"),
                        "abilityName": step.get("ability_name"),
                        "abilityProvider": step.get("ability_provider"),
                        "abilityTaskId": step.get("ability_task_id"),
                        "abilityLogId": step.get("ability_log_id"),
                        "executorId": step.get("executor_id"),
                        "executorName": step.get("executor_name"),
                        "executorType": step.get("executor_type"),
                        "durationMs": step.get("duration_ms"),
                        "error": step.get("error_message"),
                        "hasOssOutput": evidence.get("hasOssOutput"),
                        "output": {
                            key: value
                            for key, value in {
                                "imageCount": result_summary.get("imageCount"),
                                "videoCount": result_summary.get("videoCount"),
                                "textCount": result_summary.get("textCount"),
                                "structuredCount": result_summary.get("structuredCount"),
                                "resourceCount": result_summary.get("resourceCount"),
                            }.items()
                            if value not in (None, "", [])
                        },
                    }
                )
            )
            edges.append({"id": f"{previous_id}->{node_id}", "source": previous_id, "target": node_id})
            previous_id = node_id
        if active_node_id is None and steps:
            last_step = steps[-1]
            active_node_id = self._graph_node_id(
                last_step.get("step_id") or last_step.get("id"),
                fallback=f"step_{last_step.get('step_order') or len(steps)}",
            )
        result_status = "succeeded" if row.status == "succeeded" and output.get("hasOutput") else row.status
        nodes.append(
            self._compact_graph_node(
                {
                    "id": "result",
                    "type": "result",
                    "role": "result",
                    "label": "结果回填",
                    "order": len(nodes),
                    "status": result_status,
                    "imageCount": len(row.image_urls or []),
                    "videoCount": len(row.video_urls or []),
                    "textCount": len(row.texts or []),
                    "callbackStatus": row.callback_status,
                    "callbackHttpStatus": row.callback_http_status,
                    "error": row.error_message or row.callback_error,
                }
            )
        )
        edges.append({"id": f"{previous_id}->result", "source": previous_id, "target": "result"})
        return {
            "version": 1,
            "mode": "run",
            "runId": row.id,
            "businessKey": row.business_key,
            "businessVersionId": row.business_version_id,
            "businessVersion": row.version,
            "route": {
                "selectedBy": route.get("selectedBy") or route.get("selected_by"),
                "selectedCapabilityId": route.get("selectedCapabilityId") or route.get("selected_capability_id"),
            },
            "nodes": nodes,
            "edges": edges,
            "summary": {
                "status": row.status,
                "progressPercent": flow.get("progressPercent"),
                "currentNodeId": active_node_id,
                "issueCategory": flow.get("issueCategory"),
                "issueLabel": flow.get("issueLabel"),
                "stepCount": len(steps),
                "output": output,
            },
        }

    @staticmethod
    def _graph_node_id(value: Any, *, fallback: str | None) -> str:
        raw = str(value or fallback or "").strip()
        if not raw:
            return "node"
        return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in raw)[:96]

    @staticmethod
    def _compact_graph_node(node: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        for key, value in node.items():
            if value in (None, "", []):
                continue
            if isinstance(value, dict):
                nested = {
                    nested_key: nested_value
                    for nested_key, nested_value in value.items()
                    if nested_value not in (None, "", [])
                }
                if nested:
                    compact[key] = nested
            else:
                compact[key] = value
        return compact

    @staticmethod
    def _first_value(*values: Any) -> Any | None:
        for value in values:
            if value not in (None, "", []):
                return value
        return None

    @staticmethod
    def _first_string(*values: Any) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _display_text_content(*values: Any) -> str | None:
        for value in values:
            if value in (None, "", []):
                continue
            if isinstance(value, str):
                text = value.strip()
                if text:
                    return text
                continue
            if isinstance(value, list):
                parts = [str(item).strip() for item in value if str(item).strip()]
                if parts:
                    return "\n".join(parts)
                continue
            try:
                text = json.dumps(value, ensure_ascii=False)
            except Exception:
                text = str(value)
            text = text.strip()
            if text:
                return text
        return None

    @staticmethod
    def _normalize_text_fission_items(*values: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_item(raw: Any, index: int | None = None) -> None:
            if raw in (None, "", []):
                return
            if isinstance(raw, dict):
                text = str(raw.get("text") or raw.get("content") or raw.get("value") or "").strip()
                if not text:
                    return
                item = dict(raw)
            else:
                text = str(raw).strip()
                if not text:
                    return
                item = {"text": text}
            if text in seen:
                return
            seen.add(text)
            item["text"] = text
            item["index"] = int(item.get("index") or index or len(items) + 1)
            item["role"] = str(item.get("role") or "unknown")
            if "confidence" in item:
                try:
                    item["confidence"] = float(item["confidence"])
                except Exception:
                    item.pop("confidence", None)
            item["keep"] = bool(item.get("keep", True))
            items.append(item)

        for value in values:
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                for idx, item in enumerate(value, start=1):
                    add_item(item, idx)
            elif isinstance(value, dict):
                maybe_items = value.get("items") or value.get("text_items") or value.get("textItems")
                if isinstance(maybe_items, list):
                    for idx, item in enumerate(maybe_items, start=1):
                        add_item(item, idx)
                else:
                    add_item(value)
            elif isinstance(value, str):
                for idx, text in enumerate([part.strip() for part in value.splitlines() if part.strip()], start=1):
                    add_item(text, idx)
        return items

    @staticmethod
    def _resolve_text_fission_route_decision(
        *,
        structured: dict[str, Any],
        text_items: list[dict[str, Any]],
    ) -> str:
        allowed = {
            "text2img_rebuild",
            "deterministic_text_rebuild",
            "general_pattern_fission",
            "reject_text2img",
        }
        raw = BusinessRunService._first_string(
            structured.get("route_decision"),
            structured.get("routeDecision"),
            structured.get("task_route"),
        )
        if raw in allowed:
            return raw
        text_count = len(text_items)
        joined_text = "\n".join(str(item.get("text") or "") for item in text_items)
        long_form_keywords = ("路线图", "架构", "表格", "说明", "截图", "模块", "阶段", "流程", "对比", "参数")
        if text_count == 0:
            return "general_pattern_fission"
        if text_count >= 6 or len(joined_text) >= 90 or any(keyword in joined_text for keyword in long_form_keywords):
            return "deterministic_text_rebuild"
        return "text2img_rebuild"

    @staticmethod
    def _resolve_text_fission_can_use_text2img(
        *,
        structured: dict[str, Any],
        route_decision: str,
    ) -> bool:
        raw = structured.get("can_use_text2img", structured.get("canUseText2Img"))
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.strip().lower() in {"true", "false"}:
            return raw.strip().lower() == "true"
        return route_decision == "text2img_rebuild"

    @staticmethod
    def _resolve_text_fission_route_reason(
        *,
        structured: dict[str, Any],
        route_decision: str,
        text_count: int,
    ) -> str:
        explicit = BusinessRunService._first_string(structured.get("route_reason"), structured.get("routeReason"))
        if explicit:
            return explicit
        if route_decision == "text2img_rebuild":
            return "识别到少量明确文字，适合进入文生图重绘链路。"
        if route_decision == "deterministic_text_rebuild":
            return f"识别到 {text_count} 条文字或复杂版式，直接文生图容易改字，建议走确定性文字重建。"
        if route_decision == "reject_text2img":
            return "当前图不适合文字强化裂变，建议先确认业务目标或更换能力。"
        return "没有识别到稳定文字，建议优先走普通图裂变或图案重绘链路。"

    @staticmethod
    def _resolve_text_fission_text_count(
        *,
        structured: dict[str, Any],
        text_items: list[dict[str, Any]],
    ) -> int:
        raw = structured.get("text_count", structured.get("textCount"))
        try:
            if raw is not None:
                return int(raw)
        except Exception:
            pass
        return len(text_items)

    @staticmethod
    def _safe_user_id(user: User | None) -> str | None:
        if not user:
            return None
        user_id = str(getattr(user, "id", "") or "").strip()
        if user_id.startswith("business-api-key:"):
            return None
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

    @staticmethod
    def _normalize_output_review_grade(value: Any) -> str:
        grade = str(value or "pending").strip().lower()
        if grade not in BUSINESS_OUTPUT_REVIEW_GRADES:
            raise HTTPException(status_code=400, detail="BUSINESS_OUTPUT_REVIEW_GRADE_INVALID")
        return grade

    @staticmethod
    def _normalize_output_review_action(value: Any) -> str | None:
        action = str(value or "").strip().lower()
        if not action:
            return None
        if action not in BUSINESS_OUTPUT_REVIEW_ACTIONS:
            raise HTTPException(status_code=400, detail="BUSINESS_OUTPUT_REVIEW_ACTION_INVALID")
        return action

    @staticmethod
    def _normalize_output_review_tags(value: Any) -> list[str]:
        raw_items: list[Any]
        if value is None:
            raw_items = []
        elif isinstance(value, list):
            raw_items = value
        elif isinstance(value, str):
            raw_items = re.split(r"[,，;；\n]+", value)
        else:
            raw_items = [value]
        seen: set[str] = set()
        tags: list[str] = []
        for item in raw_items:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            tags.append(text[:64])
            if len(tags) >= 12:
                break
        return tags

    @staticmethod
    def _normalize_quality_sample_status(value: Any) -> str:
        status = str(value or "active").strip().lower()
        if status not in {"active", "inactive", "archived"}:
            raise HTTPException(status_code=400, detail="BUSINESS_QUALITY_SAMPLE_STATUS_INVALID")
        return status

    @staticmethod
    def _normalize_quality_sample_key(value: Any) -> str | None:
        text = str(value or "").strip().lower()
        if not text:
            return None
        normalized = re.sub(r"[^a-z0-9_-]+", "-", text).strip("-_")
        return normalized[:64] or None

    @staticmethod
    def _normalize_quality_sample_url(value: Any, *, required: bool) -> str | None:
        text = str(value or "").strip()
        if not text:
            if required:
                raise HTTPException(status_code=400, detail="BUSINESS_QUALITY_SAMPLE_IMAGE_URL_REQUIRED")
            return None
        if not (text.startswith("http://") or text.startswith("https://")):
            raise HTTPException(status_code=400, detail="BUSINESS_QUALITY_SAMPLE_IMAGE_URL_INVALID")
        return text[:1024]

    @staticmethod
    def _normalize_quality_action_status(value: Any) -> str:
        status = str(value or "candidate").strip().lower()
        if status not in BUSINESS_QUALITY_ACTION_STATUSES:
            raise HTTPException(status_code=400, detail="BUSINESS_QUALITY_ACTION_STATUS_INVALID")
        return status

    @staticmethod
    def _normalize_quality_action_type(value: Any) -> str:
        action_type = str(value or "watch_only").strip().lower()
        if action_type not in BUSINESS_QUALITY_ACTION_TYPES:
            raise HTTPException(status_code=400, detail="BUSINESS_QUALITY_ACTION_TYPE_INVALID")
        return action_type

    @staticmethod
    def _normalize_quality_action_key(value: Any) -> str | None:
        text = str(value or "").strip().lower()
        if not text:
            return None
        normalized = re.sub(r"[^a-z0-9_-]+", "-", text).strip("-_")
        return normalized[:64] or None

    @staticmethod
    def _normalize_quality_action_evidence_ids(value: Any) -> list[str]:
        raw_items: list[Any]
        if value is None:
            raw_items = []
        elif isinstance(value, list):
            raw_items = value
        else:
            raw_items = [value]
        seen: set[str] = set()
        normalized: list[str] = []
        for item in raw_items:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text[:64])
            if len(normalized) >= 50:
                break
        return normalized

    @staticmethod
    def _quality_action_target_to_dict(target: BusinessCapability | None) -> dict[str, Any] | None:
        if not target:
            return None
        return {
            "id": target.id,
            "version": target.version,
            "display_name": target.display_name,
            "status": target.status,
            "is_default": target.is_default,
        }

    def _resolve_quality_action_target(
        self,
        session: Any,
        *,
        business_key: str,
        target_business_version_id: str | None,
        allow_empty: bool = False,
    ) -> BusinessCapability | None:
        target_id = str(target_business_version_id or "").strip()
        if not target_id:
            return None if allow_empty or target_business_version_id in {None, ""} else None
        target = session.get(BusinessCapability, target_id)
        if not target or str(target.business_key or "").strip() != str(business_key or "").strip():
            raise HTTPException(status_code=404, detail="BUSINESS_QUALITY_ACTION_TARGET_VERSION_NOT_FOUND")
        return target

    @staticmethod
    def _json_safe_record(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        safe = BusinessRunService._json_safe_payload(value)
        return safe if isinstance(safe, dict) else {}

    @staticmethod
    def _business_run_output_url(run: BusinessRun, output_index: int) -> str | None:
        urls: list[str] = []
        for source in (run.image_urls, run.video_urls):
            if isinstance(source, list):
                urls.extend([str(url).strip() for url in source if isinstance(url, str) and str(url).strip()])
        if 0 <= output_index < len(urls):
            return urls[output_index]
        return None

    @staticmethod
    def _output_review_sample_meta_from_run(run: BusinessRun) -> dict[str, str | None]:
        request_payload = run.request_payload if isinstance(run.request_payload, dict) else {}
        metadata = request_payload.get("metadata") if isinstance(request_payload.get("metadata"), dict) else {}
        quality_sample = metadata.get("qualitySample") if isinstance(metadata.get("qualitySample"), dict) else {}
        return {
            "sample_key": BusinessRunService._short_text(
                quality_sample.get("sampleKey") or quality_sample.get("sample_key"),
                64,
            ),
            "sample_label": BusinessRunService._short_text(
                quality_sample.get("sampleLabel") or quality_sample.get("sample_label"),
                128,
            ),
            "batch_id": BusinessRunService._short_text(
                quality_sample.get("batchId") or quality_sample.get("batch_id"),
                64,
            ),
        }

    @staticmethod
    def _output_review_to_dict(row: BusinessOutputReview) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "business_key": row.business_key,
            "business_version_id": row.business_version_id,
            "version": row.version,
            "output_index": row.output_index,
            "output_url": row.output_url,
            "sample_key": row.sample_key,
            "sample_label": row.sample_label,
            "batch_id": row.batch_id,
            "quality_grade": row.quality_grade,
            "input_tags": row.input_tags if isinstance(row.input_tags, list) else [],
            "issue_tags": row.issue_tags if isinstance(row.issue_tags, list) else [],
            "next_action": row.next_action,
            "note": row.note,
            "reviewer_user_id": row.reviewer_user_id,
            "reviewer_username": row.reviewer_username,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _quality_sample_to_dict(row: BusinessQualitySample) -> dict[str, Any]:
        return {
            "id": row.id,
            "business_key": row.business_key,
            "sample_key": row.sample_key,
            "label": row.label,
            "description": row.description,
            "image_url": row.image_url,
            "prompt": row.prompt,
            "generated_image_url": row.generated_image_url,
            "input_tags": row.input_tags if isinstance(row.input_tags, list) else [],
            "default_params": row.default_params if isinstance(row.default_params, dict) else {},
            "status": row.status,
            "sort_order": row.sort_order,
            "created_by_user_id": row.created_by_user_id,
            "created_by_username": row.created_by_username,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _record_quality_sample_version(
        self,
        *,
        session: Any,
        row: BusinessQualitySample,
        change_type: str,
        actor: User | None = None,
        note: str | None = None,
    ) -> None:
        latest_version = (
            session.execute(
                select(func.max(BusinessQualitySampleVersion.version_no)).where(
                    BusinessQualitySampleVersion.sample_id == row.id
                )
            ).scalar()
            or 0
        )
        session.add(
            BusinessQualitySampleVersion(
                id=f"bizsamplever_{uuid4().hex}",
                sample_id=row.id,
                business_key=row.business_key,
                sample_key=row.sample_key,
                label=row.label,
                description=row.description,
                image_url=row.image_url,
                prompt=row.prompt,
                generated_image_url=row.generated_image_url,
                input_tags=row.input_tags if isinstance(row.input_tags, list) else [],
                default_params=row.default_params if isinstance(row.default_params, dict) else {},
                status=row.status,
                sort_order=row.sort_order,
                change_type=str(change_type or "update")[:32],
                change_note=self._short_text(note, 1000),
                version_no=int(latest_version) + 1,
                actor_user_id=self._safe_user_id(actor),
                actor_username=self._actor_username(actor),
                created_at=datetime.utcnow(),
            )
        )

    @staticmethod
    def _quality_sample_version_to_dict(row: BusinessQualitySampleVersion) -> dict[str, Any]:
        return {
            "id": row.id,
            "sample_id": row.sample_id,
            "business_key": row.business_key,
            "sample_key": row.sample_key,
            "label": row.label,
            "description": row.description,
            "image_url": row.image_url,
            "prompt": row.prompt,
            "generated_image_url": row.generated_image_url,
            "input_tags": row.input_tags if isinstance(row.input_tags, list) else [],
            "default_params": row.default_params if isinstance(row.default_params, dict) else {},
            "status": row.status,
            "sort_order": row.sort_order,
            "change_type": row.change_type,
            "change_note": row.change_note,
            "version_no": row.version_no,
            "actor_user_id": row.actor_user_id,
            "actor_username": row.actor_username,
            "created_at": row.created_at,
        }

    @staticmethod
    def _quality_action_rule_to_dict(
        row: BusinessQualityActionRule,
        *,
        target: BusinessCapability | None = None,
    ) -> dict[str, Any]:
        return {
            "id": row.id,
            "business_key": row.business_key,
            "rule_key": row.rule_key,
            "title": row.title,
            "description": row.description,
            "issue_tags": row.issue_tags if isinstance(row.issue_tags, list) else [],
            "input_tags": row.input_tags if isinstance(row.input_tags, list) else [],
            "action_type": row.action_type,
            "target_business_version_id": row.target_business_version_id,
            "target_version": row.target_version,
            "target_label": row.target_label,
            "target_ref": row.target_ref,
            "target_params": row.target_params if isinstance(row.target_params, dict) else {},
            "target_capability": BusinessRunService._quality_action_target_to_dict(target),
            "sample_batch_id": row.sample_batch_id,
            "evidence_review_ids": row.evidence_review_ids if isinstance(row.evidence_review_ids, list) else [],
            "status": row.status,
            "priority": row.priority,
            "owner_user_id": row.owner_user_id,
            "owner_username": row.owner_username,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _output_review_bucket_list(
        counts: dict[str, int],
        *,
        samples_by_key: dict[str, list[BusinessOutputReview]] | None = None,
        limit: int = 20,
        sample_limit: int = 3,
    ) -> list[dict[str, Any]]:
        return [
            {
                "key": key,
                "label": key,
                "total": total,
                "sample_reviews": [
                    BusinessRunService._output_review_to_dict(row)
                    for row in (samples_by_key or {}).get(key, [])[:sample_limit]
                ],
            }
            for key, total in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
        ]

    def _output_review_grade_buckets(self, rows: list[BusinessOutputReview]) -> list[dict[str, Any]]:
        counts: dict[str, int] = {grade: 0 for grade in ["excellent", "usable", "borderline", "bad", "blocked", "pending"]}
        for row in rows:
            grade = str(row.quality_grade or "pending").strip().lower() or "pending"
            counts[grade] = counts.get(grade, 0) + 1
        labels = {
            "excellent": "优秀",
            "usable": "可用",
            "borderline": "临界",
            "bad": "不可用",
            "blocked": "链路阻塞",
            "pending": "待复盘",
        }
        return [
            {"key": key, "label": labels.get(key, key), "total": total}
            for key, total in counts.items()
            if total > 0
        ]

    def _output_review_tag_buckets(
        self,
        rows: list[BusinessOutputReview],
        attr: str,
        *,
        business_key: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        samples_by_key: dict[str, list[BusinessOutputReview]] = {}
        sorted_rows = sorted(rows, key=lambda row: row.updated_at or row.created_at, reverse=True)
        for row in sorted_rows:
            if business_key and row.business_key != business_key:
                continue
            raw = getattr(row, attr, None)
            if not isinstance(raw, list):
                continue
            for item in raw:
                text = str(item or "").strip()
                if not text:
                    continue
                counts[text] = counts.get(text, 0) + 1
                samples = samples_by_key.setdefault(text, [])
                if len(samples) < 3:
                    samples.append(row)
        return self._output_review_bucket_list(counts, samples_by_key=samples_by_key, limit=limit)

    def _output_review_business_summaries(self, rows: list[BusinessOutputReview]) -> list[dict[str, Any]]:
        grouped: dict[str, list[BusinessOutputReview]] = {}
        for row in rows:
            key = str(row.business_key or "-").strip() or "-"
            grouped.setdefault(key, []).append(row)
        summaries: list[dict[str, Any]] = []
        for business_key, business_rows in grouped.items():
            grade_counts = {str(row.quality_grade or "pending").strip().lower() or "pending": 0 for row in business_rows}
            for row in business_rows:
                grade = str(row.quality_grade or "pending").strip().lower() or "pending"
                grade_counts[grade] = grade_counts.get(grade, 0) + 1
            reviewed = sum(count for grade, count in grade_counts.items() if grade != "pending")
            latest = max((row.updated_at or row.created_at for row in business_rows), default=None)
            summaries.append(
                {
                    "business_key": business_key,
                    "label": self._business_key_label(business_key),
                    "total": len(business_rows),
                    "reviewed": reviewed,
                    "excellent": grade_counts.get("excellent", 0),
                    "usable": grade_counts.get("usable", 0),
                    "borderline": grade_counts.get("borderline", 0),
                    "bad": grade_counts.get("bad", 0),
                    "blocked": grade_counts.get("blocked", 0),
                    "pending": grade_counts.get("pending", 0),
                    "latest_at": latest,
                    "top_issue_tags": self._output_review_tag_buckets(business_rows, "issue_tags", limit=5),
                    "top_input_tags": self._output_review_tag_buckets(business_rows, "input_tags", limit=5),
                }
            )
        return sorted(summaries, key=lambda item: (-int(item["total"]), str(item["business_key"])))

    def _output_review_version_summaries(self, rows: list[BusinessOutputReview]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str], list[BusinessOutputReview]] = {}
        for row in rows:
            business_key = str(row.business_key or "-").strip() or "-"
            version = str(row.version or "").strip()
            business_version_id = str(row.business_version_id or "").strip()
            grouped.setdefault((business_key, version, business_version_id), []).append(row)
        summaries: list[dict[str, Any]] = []
        for (business_key, version, business_version_id), version_rows in grouped.items():
            grade_counts = {str(row.quality_grade or "pending").strip().lower() or "pending": 0 for row in version_rows}
            for row in version_rows:
                grade = str(row.quality_grade or "pending").strip().lower() or "pending"
                grade_counts[grade] = grade_counts.get(grade, 0) + 1
            reviewed = sum(count for grade, count in grade_counts.items() if grade != "pending")
            latest = max((row.updated_at or row.created_at for row in version_rows), default=None)
            summaries.append(
                {
                    "business_key": business_key,
                    "business_version_id": business_version_id or None,
                    "version": version or None,
                    "label": f"{self._business_key_label(business_key)} · {version or '未标版本'}",
                    "total": len(version_rows),
                    "reviewed": reviewed,
                    "excellent": grade_counts.get("excellent", 0),
                    "usable": grade_counts.get("usable", 0),
                    "borderline": grade_counts.get("borderline", 0),
                    "bad": grade_counts.get("bad", 0),
                    "blocked": grade_counts.get("blocked", 0),
                    "pending": grade_counts.get("pending", 0),
                    "latest_at": latest,
                    "top_issue_tags": self._output_review_tag_buckets(version_rows, "issue_tags", limit=5),
                    "top_input_tags": self._output_review_tag_buckets(version_rows, "input_tags", limit=5),
                }
            )
        return sorted(
            summaries,
            key=lambda item: (
                str(item.get("business_key") or ""),
                str(item.get("version") or ""),
                str(item.get("business_version_id") or ""),
            ),
        )

    def _output_review_batch_summaries(self, rows: list[BusinessOutputReview]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str, str], list[BusinessOutputReview]] = {}
        for row in rows:
            batch_id = str(row.batch_id or "").strip()
            if not batch_id:
                continue
            business_key = str(row.business_key or "-").strip() or "-"
            sample_key = str(row.sample_key or "").strip()
            sample_label = str(row.sample_label or "").strip()
            grouped.setdefault((batch_id, business_key, sample_key, sample_label), []).append(row)

        summaries: list[dict[str, Any]] = []
        for (batch_id, business_key, sample_key, sample_label), batch_rows in grouped.items():
            latest = max((row.updated_at or row.created_at for row in batch_rows), default=None)
            good, risk, reviewed = self._output_review_good_risk_counts(batch_rows)
            version_groups: dict[tuple[str, str], list[BusinessOutputReview]] = {}
            for row in batch_rows:
                version_groups.setdefault((str(row.business_version_id or ""), str(row.version or "")), []).append(row)
            versions: list[dict[str, Any]] = []
            for (business_version_id, version), version_rows in version_groups.items():
                version_good, version_risk, version_reviewed = self._output_review_good_risk_counts(version_rows)
                version_latest = max((row.updated_at or row.created_at for row in version_rows), default=None)
                versions.append(
                    {
                        "business_version_id": business_version_id or None,
                        "version": version or None,
                        "label": version or business_version_id or "未标版本",
                        "total": len(version_rows),
                        "reviewed": version_reviewed,
                        "good": version_good,
                        "risk": version_risk,
                        "latest_at": version_latest,
                        "sample_reviews": [
                            self._output_review_to_dict(row)
                            for row in sorted(version_rows, key=lambda item: item.updated_at or item.created_at, reverse=True)[:3]
                        ],
                    }
                )
            versions.sort(key=lambda item: (-int(item["good"]), int(item["risk"]), str(item.get("version") or "")))
            sample_reviews = [
                self._output_review_to_dict(row)
                for row in sorted(batch_rows, key=lambda item: item.updated_at or item.created_at, reverse=True)[:6]
            ]
            summaries.append(
                {
                    "batch_id": batch_id,
                    "business_key": business_key,
                    "sample_key": sample_key or None,
                    "sample_label": sample_label or sample_key or "固定样例",
                    "label": f"{self._business_key_label(business_key)} · {sample_label or sample_key or batch_id}",
                    "total": len(batch_rows),
                    "reviewed": reviewed,
                    "good": good,
                    "risk": risk,
                    "latest_at": latest,
                    "versions": versions,
                    "top_issue_tags": self._output_review_tag_buckets(batch_rows, "issue_tags", limit=5),
                    "top_input_tags": self._output_review_tag_buckets(batch_rows, "input_tags", limit=5),
                    "sample_reviews": sample_reviews,
                }
            )
        return sorted(summaries, key=lambda item: item.get("latest_at") or datetime.min, reverse=True)[:50]

    @staticmethod
    def _output_review_good_risk_counts(rows: list[BusinessOutputReview]) -> tuple[int, int, int]:
        good = 0
        risk = 0
        reviewed = 0
        for row in rows:
            grade = str(row.quality_grade or "pending").strip().lower() or "pending"
            if grade == "pending":
                continue
            reviewed += 1
            if grade in {"excellent", "usable"}:
                good += 1
            elif grade in {"borderline", "bad", "blocked"}:
                risk += 1
        return good, risk, reviewed

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
            session=session,
        )
        version_line = self._business_capability_version_line(
            row,
            primary_ability_provider=primary_ability_provider,
            vendor_model_provider=vendor_model_provider,
        )
        version_lineage = self._business_capability_version_lineage(row)
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
            "version_line": version_line,
            "version_lineage": version_lineage,
            "version_family": self._business_capability_version_family(
                row,
                session=session,
                version_line=version_line,
                version_lineage=version_lineage,
            ),
            "recipe_steps": self._recipe_steps_to_dict(recipe, session=session),
            "orchestration_graph": self._build_recipe_orchestration_graph(
                recipe,
                session=session,
                business_key=row.business_key,
                business_version_id=row.id,
                business_version=row.version,
                business_display_name=row.display_name,
            ),
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
    def _business_capability_version_line(
        row: BusinessCapability,
        *,
        primary_ability_provider: str | None = None,
        vendor_model_provider: str | None = None,
    ) -> dict[str, Any]:
        metadata = row.extra_metadata if isinstance(row.extra_metadata, dict) else {}
        explicit_line = metadata.get("versionLine") or metadata.get("version_line")
        if isinstance(explicit_line, dict):
            key = str(explicit_line.get("key") or "").strip() or "standard"
            label = str(explicit_line.get("label") or "").strip() or ("生产主线" if row.is_default else "标准版本")
            detail = str(explicit_line.get("detail") or "").strip() or "同一业务入口下的稳定版本。"
            try:
                priority = int(explicit_line.get("priority") if explicit_line.get("priority") is not None else (10 if row.is_default else 50))
            except (TypeError, ValueError):
                priority = 10 if row.is_default else 50
            return {
                "key": key,
                "label": label,
                "detail": detail,
                "priority": priority,
            }
        version = (row.version or "").lower()
        display_name = (row.display_name or "").lower()
        role = str(metadata.get("role") or "").lower()
        has_vendor_model = bool(vendor_model_provider)
        provider = str(
            metadata.get("provider")
            or primary_ability_provider
            or vendor_model_provider
            or ""
        ).lower()

        if "rollback" in role or metadata.get("rollbackSafety") or "rollback" in version or "保底" in display_name:
            return {
                "key": "rollback",
                "label": "保底回滚",
                "detail": "只在主线异常时切回，不作为新功能入口。",
                "priority": 80,
            }
        if "comfyui" in provider or "comfyui" in version or "comfyui" in display_name:
            return {
                "key": "comfyui",
                "label": "ComfyUI 自研线",
                "detail": "业务仍是同一个入口，底层由 ComfyUI 工作流执行。",
                "priority": 20,
            }
        if "coze" in str(metadata.get("entry") or "").lower() or "coze" in display_name:
            return {
                "key": "coze",
                "label": "Coze 旧链路",
                "detail": "兼容旧业务接入，不作为新功能命名。",
                "priority": 70,
            }
        commercial_provider_tokens = ("openai", "gpt-image", "kie", "volcengine", "doubao", "qwen", "seedream", "vendor-api")
        if has_vendor_model or any(token in provider for token in commercial_provider_tokens) or "gpt-image" in version or "gpt image" in display_name:
            return {
                "key": "commercial-model",
                "label": "商业模型线",
                "detail": "业务仍是同一个入口，底层改用商业模型执行。",
                "priority": 30,
            }
        return {
            "key": "standard",
            "label": "生产主线" if row.is_default else "标准版本",
            "detail": "同一业务入口下的稳定版本。",
            "priority": 10 if row.is_default else 50,
        }

    @staticmethod
    def _business_capability_version_lineage(row: BusinessCapability) -> dict[str, Any]:
        metadata = row.extra_metadata if isinstance(row.extra_metadata, dict) else {}
        raw = metadata.get("versionLineage") or metadata.get("version_lineage")
        if not isinstance(raw, dict):
            raw = {}

        def text_value(*keys: str) -> str | None:
            for key in keys:
                value = raw.get(key)
                if value is None:
                    continue
                text = str(value).strip()
                if text:
                    return text
            return None

        def infer_decision() -> str:
            text = " ".join(
                [
                    str(row.version or ""),
                    str(row.display_name or ""),
                    str(metadata.get("role") or ""),
                ]
            ).lower()
            if (
                "rollback" in text
                or "回滚" in text
                or "保底" in text
                or bool(metadata.get("rollbackSafety"))
            ):
                return "rollback"
            return "version_upgrade"

        decision = text_value("decision", "versionDecision", "version_decision")
        if decision not in {"version_upgrade", "new_feature", "rollback"}:
            decision = infer_decision()
        decision_note = text_value("decisionNote", "decision_note")
        if not decision_note:
            if decision == "rollback":
                decision_note = "保底回滚版本，只在主线异常时切回，不作为新业务入口。"
            elif decision == "version_upgrade":
                decision_note = "同一业务入口下的版本迭代；除非明确新建分类，否则按版本升级处理。"
            elif decision == "new_feature":
                decision_note = "入口含义发生变化，需要作为独立业务管理。"

        return {
            "parentVersionId": text_value("parentVersionId", "parent_version_id", "sourceVersionId", "source_version_id"),
            "supersedesVersionId": text_value("supersedesVersionId", "supersedes_version_id"),
            "changeSummary": text_value("changeSummary", "change_summary", "releaseNote", "release_note"),
            "breakingChange": bool(raw.get("breakingChange") or raw.get("breaking_change")),
            "decision": decision,
            "decisionNote": decision_note,
        }

    @staticmethod
    def _business_key_label(business_key: str | None) -> str:
        labels = {
            "pattern_extract": "花纹提取",
            "image_fission": "图裂变",
            "fission": "图裂变",
            "fission_evaluate": "裂变评分",
            "product_design": "产品设计",
            "image_edit": "图编辑",
            "outpaint": "扩图",
            "text_fission": "文字裂变",
        }
        key = str(business_key or "").strip()
        return labels.get(key, key or "未命名业务")

    @staticmethod
    def _business_version_ref(row: BusinessCapability | None) -> dict[str, Any] | None:
        if row is None:
            return None
        version = str(row.version or "").strip()
        display_name = str(row.display_name or "").strip()
        label_parts = [part for part in (version, display_name) if part]
        return {
            "id": row.id,
            "version": row.version,
            "displayName": row.display_name,
            "label": " · ".join(label_parts) or row.id,
            "status": row.status,
            "isDefault": row.is_default,
        }

    @staticmethod
    def _business_version_decision_label(decision: str | None) -> str:
        if decision == "new_feature":
            return "新业务分类"
        if decision == "rollback":
            return "回滚保底"
        return "同一业务版本升级"

    @staticmethod
    def _business_version_lifecycle(row: BusinessCapability) -> dict[str, str]:
        if row.is_default:
            return {"key": "default", "label": "线上默认"}
        status = str(row.status or "").strip().lower()
        if status == "draft":
            return {"key": "draft", "label": "草稿验证"}
        if status == "active":
            return {"key": "active", "label": "备选验证"}
        if status in {"deprecated", "disabled", "inactive"}:
            return {"key": status, "label": "已停用"}
        return {"key": status or "unknown", "label": status or "未知状态"}

    def _business_capability_version_family(
        self,
        row: BusinessCapability,
        *,
        session,
        version_line: dict[str, Any],
        version_lineage: dict[str, Any],
    ) -> dict[str, Any]:
        parent = None
        supersedes = None
        if session is not None:
            parent_id = version_lineage.get("parentVersionId")
            supersedes_id = version_lineage.get("supersedesVersionId")
            if parent_id:
                parent = session.get(BusinessCapability, str(parent_id))
            if supersedes_id and supersedes_id != parent_id:
                supersedes = session.get(BusinessCapability, str(supersedes_id))
            elif supersedes_id == parent_id:
                supersedes = parent
        lifecycle = self._business_version_lifecycle(row)
        business_label = self._business_key_label(row.business_key)
        version_label = " · ".join(part for part in (str(row.version or "").strip(), str(row.display_name or "").strip()) if part)
        decision = str(version_lineage.get("decision") or "version_upgrade")
        return {
            "businessKey": row.business_key,
            "businessLabel": business_label,
            "versionId": row.id,
            "version": row.version,
            "versionLabel": version_label or row.id,
            "lifecycleKey": lifecycle["key"],
            "lifecycleLabel": lifecycle["label"],
            "lineKey": version_line.get("key") or "standard",
            "lineLabel": version_line.get("label") or "标准版本",
            "lineDetail": version_line.get("detail") or "同一业务入口下的稳定版本。",
            "linePriority": version_line.get("priority"),
            "parent": self._business_version_ref(parent),
            "supersedes": self._business_version_ref(supersedes),
            "parentVersionId": version_lineage.get("parentVersionId"),
            "supersedesVersionId": version_lineage.get("supersedesVersionId"),
            "decision": decision,
            "decisionLabel": self._business_version_decision_label(decision),
            "decisionNote": version_lineage.get("decisionNote"),
            "changeSummary": version_lineage.get("changeSummary"),
            "breakingChange": bool(version_lineage.get("breakingChange")),
            "releaseTime": row.release_time,
            "updatedAt": row.updated_at,
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
        if not release_gate.get("canRequestDefault"):
            raise HTTPException(status_code=409, detail="BUSINESS_RELEASE_GATE_BLOCKED")

    @staticmethod
    def _build_draft_publish_checks(draft_payload: dict[str, Any]) -> list[dict[str, Any]]:
        latest_run = draft_payload.get("latest_run") if isinstance(draft_payload.get("latest_run"), dict) else None
        latest_acceptance = (
            draft_payload.get("latest_acceptance") if isinstance(draft_payload.get("latest_acceptance"), dict) else None
        )
        governance_status = str(draft_payload.get("governance_status") or "").strip().lower()
        image_count = BusinessRunService._first_int(latest_run.get("image_count") if latest_run else None) or 0
        video_count = BusinessRunService._first_int(latest_run.get("video_count") if latest_run else None) or 0
        text_count = BusinessRunService._first_int(latest_run.get("text_count") if latest_run else None) or 0
        latest_status = str(latest_run.get("status") if latest_run else "").strip().lower()
        latest_has_output = bool(image_count or video_count or text_count)
        acceptance_passed = BusinessRunService._acceptance_passed(latest_acceptance)
        quality_evidence = draft_payload.get("release_gate", {}).get("qualityEvidence") if isinstance(draft_payload.get("release_gate"), dict) else None
        quality_ready = isinstance(quality_evidence, dict) and bool(quality_evidence.get("canRequestDefault"))
        return [
            {
                "code": "BUSINESS_DRAFT_IDENTITY",
                "label": "草稿身份",
                "passed": str(draft_payload.get("status") or "").strip().lower() == "draft"
                and not bool(draft_payload.get("is_default")),
                "level": "blocker",
                "message": "只有草稿版本允许进入发布前校验。",
                "action": "先复制线上版本为草稿，再在草稿里调整编排。",
            },
            {
                "code": "BUSINESS_DRAFT_RECIPE_AVAILABLE",
                "label": "编排可用",
                "passed": bool(draft_payload.get("primary_ability_id")) and governance_status != "blocker",
                "level": "blocker",
                "message": "业务配方必须有主执行能力，且底层能力、模型、密钥和执行节点不能存在阻断项。",
                "action": "先处理能力目录、模型弹药库、密钥或执行节点里的阻断问题。",
            },
            {
                "code": "BUSINESS_DRAFT_REAL_RUN_PASSED",
                "label": "真实测试",
                "passed": latest_status == "succeeded" and latest_has_output and not latest_run.get("error") if latest_run else False,
                "level": "blocker",
                "message": "发布前必须至少跑通一次真实业务调用，并产生图片、视频或文字结果。",
                "action": "先用该草稿跑一次真实测试，确认结果能正常回填。",
            },
            {
                "code": "BUSINESS_DRAFT_ACCEPTANCE_PASSED",
                "label": "人工验收",
                "passed": acceptance_passed,
                "level": "blocker",
                "message": "发布前必须记录最近一次人工验收通过。",
                "action": "先登记验收记录，最好带 runId 或样本链接。",
            },
            {
                "code": "BUSINESS_DRAFT_QUALITY_REVIEW_PASSED",
                "label": "质量复盘",
                "passed": quality_ready,
                "level": "blocker",
                "message": "发布前必须至少有一张输出图被标为优秀或可用。",
                "action": "打开 runId 详情，在出图质量标注里保存质量档位和问题标签。",
            },
            {
                "code": "BUSINESS_DRAFT_RECENT_FAILURES",
                "label": "近期失败",
                "passed": not bool((draft_payload.get("latest_run") or {}).get("error")),
                "level": "warning",
                "message": "最近一次调用存在错误时，不建议直接发布。",
                "action": "先打开 runId 详情定位失败阶段。",
            },
        ]

    def _business_capability_release_gate(
        self,
        row: BusinessCapability,
        *,
        governance: dict[str, Any],
        acceptance: dict[str, Any] | None,
        latest_run: dict[str, Any] | None,
        run_metrics: dict[str, Any] | None,
        primary_ability_id: str | None,
        session=None,
    ) -> dict[str, Any]:
        blockers: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []
        governance_status = str(governance.get("status") or "").strip().lower()
        quality_evidence = self._business_capability_quality_evidence(row, session=session)

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
            suggestions.append("发版前补齐成本、模型治理或其他非阻塞信息。")

        acceptance_ok = self._acceptance_passed(acceptance)
        if not acceptance_ok:
            blockers.append("BUSINESS_RELEASE_ACCEPTANCE_REQUIRED")
            suggestions.append("先跑测评端或业务真实链路，并记录人工验收通过。")

        if latest_run and latest_run.get("error"):
            warnings.append("BUSINESS_RELEASE_LATEST_RUN_FAILED")
            suggestions.append("最近一次运行失败，先排查失败原因再放量。")
        if run_metrics and (self._first_int(run_metrics.get("unresolved_failed")) or 0) > 0:
            warnings.append("BUSINESS_RELEASE_RECENT_FAILURES")
            suggestions.append("近窗口有失败样本，先筛选业务调用记录定位问题。")
        for code in quality_evidence.get("blockers") or []:
            blockers.append(str(code))
        for code in quality_evidence.get("warnings") or []:
            warnings.append(str(code))
        for suggestion in quality_evidence.get("suggestions") or []:
            if suggestion:
                suggestions.append(str(suggestion))

        status = "ready"
        label = "门禁通过"
        if blockers:
            status = "blocked"
            label = "门禁阻塞"
        elif warnings:
            status = "warning"
            label = "小流量可用，需复核"
        return {
            "status": status,
            "label": label,
            "canRelease": status == "ready",
            "canRequestDefault": not blockers and acceptance_ok and bool(quality_evidence.get("canRequestDefault")),
            "acceptancePassed": acceptance_ok,
            "blockers": blockers,
            "warnings": warnings,
            "suggestions": suggestions,
            "qualityEvidence": quality_evidence,
        }

    def _business_capability_quality_evidence(self, row: BusinessCapability, *, session=None) -> dict[str, Any]:
        required = row.business_key in BUSINESS_QUALITY_GATE_KEYS and row.status in {"active", "draft"}
        empty = {
            "required": required,
            "windowHours": BUSINESS_QUALITY_GATE_WINDOW_HOURS,
            "total": 0,
            "reviewed": 0,
            "accepted": 0,
            "risky": 0,
            "excellent": 0,
            "usable": 0,
            "borderline": 0,
            "bad": 0,
            "blocked": 0,
            "pending": 0,
            "status": "not_required" if not required else "blocked",
            "label": "不要求质量复盘" if not required else "缺少质量复盘",
            "canRequestDefault": not required,
            "blockers": [] if not required else ["BUSINESS_RELEASE_QUALITY_REVIEW_REQUIRED"],
            "warnings": [],
            "suggestions": [] if not required else ["先打开候选版本的 runId 详情，至少把一张输出标为优秀或可用。"],
            "topIssueTags": [],
            "topInputTags": [],
            "latestAt": None,
        }
        if session is None or not required:
            return empty
        if not self._optional_table_exists(session, "business_output_reviews"):
            return empty

        since = datetime.utcnow() - timedelta(hours=BUSINESS_QUALITY_GATE_WINDOW_HOURS)
        rows = (
            session.execute(
                select(BusinessOutputReview)
                .where(
                    BusinessOutputReview.updated_at >= since,
                    or_(
                        BusinessOutputReview.business_version_id == row.id,
                        and_(
                            BusinessOutputReview.business_key == row.business_key,
                            BusinessOutputReview.version == row.version,
                        ),
                    ),
                )
                .order_by(BusinessOutputReview.updated_at.desc())
                .limit(1000)
            )
            .scalars()
            .all()
        )
        if not rows:
            return empty

        grade_counts = {grade: 0 for grade in BUSINESS_OUTPUT_REVIEW_GRADES}
        for review in rows:
            grade = str(review.quality_grade or "pending").strip().lower()
            if grade in grade_counts:
                grade_counts[grade] += 1
        reviewed = sum(total for grade, total in grade_counts.items() if grade != "pending")
        accepted = sum(grade_counts.get(grade, 0) for grade in BUSINESS_QUALITY_ACCEPTED_GRADES)
        risky = sum(grade_counts.get(grade, 0) for grade in BUSINESS_QUALITY_RISK_GRADES)
        blockers: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []
        status = "ready"
        label = "质量证据通过"
        if reviewed <= 0:
            blockers.append("BUSINESS_RELEASE_QUALITY_REVIEW_REQUIRED")
            suggestions.append("候选版本已有输出但未完成质量标注，先在 runId 详情保存质量档位。")
            status = "blocked"
            label = "缺少质量复盘"
        elif accepted <= 0:
            blockers.append("BUSINESS_RELEASE_QUALITY_REVIEW_POSITIVE_REQUIRED")
            suggestions.append("近 7 天没有优秀或可用样本，不能切默认。")
            status = "blocked"
            label = "缺少可用样本"
        elif risky > 0:
            warnings.append("BUSINESS_RELEASE_QUALITY_REVIEW_RISKY")
            suggestions.append("候选版本有边界/差图样本，切默认前确认问题标签和分流方案。")
            status = "warning"
            label = "质量证据需复核"

        latest_at = max((review.updated_at or review.created_at for review in rows if review.updated_at or review.created_at), default=None)
        return {
            "required": required,
            "windowHours": BUSINESS_QUALITY_GATE_WINDOW_HOURS,
            "total": len(rows),
            "reviewed": reviewed,
            "accepted": accepted,
            "risky": risky,
            "excellent": grade_counts.get("excellent", 0),
            "usable": grade_counts.get("usable", 0),
            "borderline": grade_counts.get("borderline", 0),
            "bad": grade_counts.get("bad", 0),
            "blocked": grade_counts.get("blocked", 0),
            "pending": grade_counts.get("pending", 0),
            "status": status,
            "label": label,
            "canRequestDefault": not blockers,
            "blockers": blockers,
            "warnings": warnings,
            "suggestions": suggestions,
            "topIssueTags": self._output_review_tag_buckets(rows, "issue_tags")[:5],
            "topInputTags": self._output_review_tag_buckets(rows, "input_tags")[:5],
            "latestAt": latest_at.isoformat() if latest_at else None,
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
        recipe_control_issues = self._recipe_control_issues(recipe=recipe, session=session)
        for control_issue in recipe_control_issues:
            code = str(control_issue.get("code") or "").strip()
            if not code or code in issues:
                continue
            issues.append(code)
            if code == "BUSINESS_GOVERNANCE_STEP_ABILITY_MISSING":
                suggestions.append("业务配方里存在缺少能力编号的步骤，先补齐或停用该步骤。")
            elif code == "BUSINESS_GOVERNANCE_STEP_ABILITY_NOT_FOUND":
                suggestions.append("业务配方里引用了不存在的能力，先恢复能力目录或切换到可用能力。")
            elif code == "BUSINESS_GOVERNANCE_STEP_ABILITY_INACTIVE":
                suggestions.append("业务配方里引用了未启用能力，先启用能力或切换到可用能力。")
            elif code == "BUSINESS_GOVERNANCE_RECIPE_STEP_ID_DUPLICATED":
                suggestions.append("业务配方步骤编号重复，先在草稿编排中修正步骤编号。")
            elif code == "BUSINESS_GOVERNANCE_RECIPE_PRIMARY_STEP_MISMATCH":
                suggestions.append("主能力和主步骤绑定不一致，先复制为草稿并重新生成配方。")

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
            "BUSINESS_GOVERNANCE_STEP_ABILITY_MISSING",
            "BUSINESS_GOVERNANCE_STEP_ABILITY_NOT_FOUND",
            "BUSINESS_GOVERNANCE_STEP_ABILITY_INACTIVE",
            "BUSINESS_GOVERNANCE_RECIPE_STEP_ID_DUPLICATED",
            "BUSINESS_GOVERNANCE_RECIPE_PRIMARY_STEP_MISMATCH",
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
        latest = session.execute(
            select(
                BusinessRun.id,
                BusinessRun.status,
                BusinessRun.created_at,
                BusinessRun.finished_at,
                BusinessRun.image_urls,
                BusinessRun.video_urls,
                BusinessRun.texts,
                BusinessRun.result_payload,
                BusinessRun.error_message,
            )
            .where(BusinessRun.business_version_id == row.id)
            .order_by(BusinessRun.created_at.desc())
            .limit(1)
        ).first()
        if not latest:
            return None
        text_count = len(latest.texts or [])
        if text_count <= 0 and isinstance(latest.result_payload, dict) and latest.result_payload:
            if latest.result_payload.get("texts"):
                text_count = len(latest.result_payload.get("texts") or [])
            elif any(key in latest.result_payload for key in ("decision", "score", "normalized", "json", "jsonOutput")):
                text_count = 1
        return {
            "id": latest.id,
            "status": latest.status,
            "created_at": latest.created_at,
            "finished_at": latest.finished_at,
            "image_count": len(latest.image_urls or []),
            "video_count": len(latest.video_urls or []),
            "text_count": text_count,
            "error": latest.error_message,
        }

    def _run_metrics_summary(self, row: BusinessCapability, *, session=None) -> dict[str, Any]:
        since = datetime.utcnow() - timedelta(hours=24)
        metrics = {
            "window_hours": 24,
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "unresolved_failed": 0,
            "running": 0,
            "queued": 0,
            "cancelled": 0,
            "success_rate": None,
        }
        if session is None:
            return metrics
        status_rows = (
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
        for status, count in status_rows:
            key = str(status or "").strip().lower()
            value = int(count or 0)
            if key in metrics:
                metrics[key] = value
            metrics["total"] = int(metrics["total"] or 0) + value
        failed_runs = (
            session.execute(
                select(BusinessRun)
                .options(
                    load_only(
                        BusinessRun.id,
                        BusinessRun.business_key,
                        BusinessRun.version,
                        BusinessRun.status,
                        BusinessRun.request_payload,
                        BusinessRun.created_at,
                    )
                )
                .where(
                    BusinessRun.business_version_id == row.id,
                    BusinessRun.created_at >= since,
                    BusinessRun.status == "failed",
                )
                .limit(200)
            )
            .scalars()
            .all()
        )
        unresolved_failed = 0
        for run in failed_runs:
            if self._has_later_successful_business_run_in_db(run, session=session):
                continue
            if self._build_retest_summary(run, session=session).get("recovered"):
                continue
            unresolved_failed += 1
        metrics["unresolved_failed"] = unresolved_failed
        total = int(metrics["total"] or 0)
        if total > 0:
            metrics["success_rate"] = round(int(metrics["succeeded"] or 0) / total, 4)
        return metrics

    def _run_to_dict(self, row: BusinessRun, *, session=None, include_api_usage: bool = False) -> dict[str, Any]:
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
        flow_summary = self._build_run_flow_summary(row, steps=steps, route_info=route_info, session=session)
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
            "flow_summary": flow_summary,
            "trace_summary": self._build_run_trace_summary(row, steps=steps, flow_summary=flow_summary),
            "agent_trace": self._business_agent_trace(row, session=session),
            "api_usage": self._business_api_usage_evidence(row, session=session) if include_api_usage else None,
            "orchestration_graph": self._build_run_orchestration_graph(
                row,
                steps=steps,
                route_info=route_info,
                flow_summary=flow_summary,
            ),
            "steps": steps,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }

    def _business_agent_trace(self, row: BusinessRun, *, session=None) -> dict[str, Any] | None:
        if session is None:
            return None
        tool_call = (
            session.execute(
                select(BusinessAgentToolCall)
                .where(BusinessAgentToolCall.run_id == row.id)
                .order_by(BusinessAgentToolCall.created_at.desc(), BusinessAgentToolCall.id.desc())
            )
            .scalars()
            .first()
        )
        if not tool_call:
            metadata = row.request_payload.get("metadata") if isinstance(row.request_payload, dict) else None
            if not isinstance(metadata, dict) or not metadata.get("agentSessionId"):
                return None
            session_id = str(metadata.get("agentSessionId") or "").strip()
            plan_id = str(metadata.get("agentPlanId") or "").strip()
            session_obj = session.get(BusinessAgentSession, session_id) if session_id else None
            plan = session.get(BusinessAgentPlan, plan_id) if plan_id else None
            return {
                "source": "image-edit-chat",
                "agentKey": getattr(session_obj, "agent_key", None) or metadata.get("agentKey"),
                "sessionId": session_id or None,
                "sessionStatus": getattr(session_obj, "status", None),
                "sessionTitle": getattr(session_obj, "title", None),
                "planId": plan_id or None,
                "planStatus": getattr(plan, "status", None),
                "planTitle": getattr(plan, "title", None),
                "planSummary": getattr(plan, "summary", None),
                "toolName": "business.image_edit",
                "toolCallStatus": None,
                "runId": row.id,
                "requestId": getattr(session_obj, "request_id", None) or row.request_id,
                "traceId": getattr(session_obj, "trace_id", None) or row.trace_id,
                "createdAt": getattr(session_obj, "created_at", None),
                "updatedAt": getattr(session_obj, "updated_at", None),
            }

        session_obj = session.get(BusinessAgentSession, tool_call.session_id) if tool_call.session_id else None
        plan = session.get(BusinessAgentPlan, tool_call.plan_id) if tool_call.plan_id else None
        tool_payload = plan.tool_payload if plan and isinstance(plan.tool_payload, dict) else {}
        session_metadata = session_obj.extra_metadata if session_obj and isinstance(session_obj.extra_metadata, dict) else {}
        return {
            "source": "image-edit-chat",
            "agentKey": getattr(session_obj, "agent_key", None) or getattr(plan, "agent_key", None),
            "sessionId": tool_call.session_id,
            "sessionStatus": getattr(session_obj, "status", None),
            "sessionTitle": getattr(session_obj, "title", None),
            "planId": tool_call.plan_id,
            "planStatus": getattr(plan, "status", None),
            "planTitle": getattr(plan, "title", None),
            "planSummary": getattr(plan, "summary", None),
            "plannerMode": getattr(plan, "planner_mode", None),
            "plannerModel": getattr(plan, "planner_model", None),
            "estimatedCostLevel": getattr(plan, "estimated_cost_level", None),
            "riskLevel": getattr(plan, "risk_level", None),
            "warnings": getattr(plan, "warnings", None) or [],
            "toolCallId": tool_call.id,
            "toolName": tool_call.tool_name,
            "toolCallStatus": tool_call.status,
            "businessKey": tool_call.business_key,
            "runId": row.id,
            "requestId": getattr(session_obj, "request_id", None) or row.request_id,
            "traceId": getattr(session_obj, "trace_id", None) or row.trace_id,
            "entrySource": session_metadata.get("source"),
            "channel": session_metadata.get("channel") or row.channel,
            "instruction": tool_payload.get("instruction"),
            "editSkill": tool_payload.get("editSkill"),
            "quality": tool_payload.get("quality"),
            "size": tool_payload.get("size"),
            "outputFormat": tool_payload.get("output_format") or tool_payload.get("outputFormat"),
            "confirmedAt": getattr(plan, "confirmed_at", None),
            "executedAt": getattr(plan, "executed_at", None),
            "createdAt": getattr(session_obj, "created_at", None) or tool_call.created_at,
            "updatedAt": getattr(session_obj, "updated_at", None) or tool_call.updated_at,
        }

    def _business_api_usage_evidence(
        self,
        row: BusinessRun,
        *,
        session=None,
        limit: int = 20,
    ) -> dict[str, Any] | None:
        if session is None:
            return None
        match_clauses = [BusinessApiKeyUsageLog.run_id == row.id]
        match_by = ["runId"]
        if row.request_id:
            match_clauses.append(
                and_(
                    BusinessApiKeyUsageLog.business_key == row.business_key,
                    BusinessApiKeyUsageLog.request_id == row.request_id,
                )
            )
            match_by.append("requestId")
        if row.trace_id:
            match_clauses.append(
                and_(
                    BusinessApiKeyUsageLog.business_key == row.business_key,
                    BusinessApiKeyUsageLog.trace_id == row.trace_id,
                )
            )
            match_by.append("traceId")

        scope_filter = or_(*match_clauses)
        submit_filter = self._business_api_usage_submit_filter()
        poll_filter = BusinessApiKeyUsageLog.path == "/api/business/runs/get"
        callback_filter = BusinessApiKeyUsageLog.path.contains("callback")
        error_filter = or_(BusinessApiKeyUsageLog.status_code >= 400, BusinessApiKeyUsageLog.error_code.is_not(None))
        success_filter = and_(
            BusinessApiKeyUsageLog.status_code >= 200,
            BusinessApiKeyUsageLog.status_code < 400,
            BusinessApiKeyUsageLog.error_code.is_(None),
        )
        aggregate = session.execute(
            select(
                func.count(BusinessApiKeyUsageLog.id),
                func.coalesce(func.sum(case((submit_filter, 1), else_=0)), 0),
                func.coalesce(func.sum(case((poll_filter, 1), else_=0)), 0),
                func.coalesce(func.sum(case((callback_filter, 1), else_=0)), 0),
                func.coalesce(func.sum(case((error_filter, 1), else_=0)), 0),
                func.coalesce(func.sum(case((success_filter, 1), else_=0)), 0),
                func.avg(BusinessApiKeyUsageLog.duration_ms),
                func.min(BusinessApiKeyUsageLog.created_at),
                func.max(BusinessApiKeyUsageLog.created_at),
            )
            .select_from(BusinessApiKeyUsageLog)
            .where(scope_filter)
        ).one()
        total = int(aggregate[0] or 0)
        submit_count = int(aggregate[1] or 0)
        poll_count = int(aggregate[2] or 0)
        callback_count = int(aggregate[3] or 0)
        error_count = int(aggregate[4] or 0)
        success_count = int(aggregate[5] or 0)
        issue_code, issue_hint, needs_attention = self._business_api_usage_issue_summary(
            total=total,
            submit_count=submit_count,
            poll_count=poll_count,
            error_count=error_count,
        )
        rows = (
            session.execute(
                select(BusinessApiKeyUsageLog)
                .where(scope_filter)
                .order_by(BusinessApiKeyUsageLog.created_at.desc(), BusinessApiKeyUsageLog.id.desc())
                .limit(max(1, min(int(limit or 20), 100)))
            )
            .scalars()
            .all()
        )
        return {
            "matchBy": match_by,
            "summary": {
                "total": total,
                "successCount": success_count,
                "errorCount": error_count,
                "submitCount": submit_count,
                "pollCount": poll_count,
                "callbackCount": callback_count,
                "averageDurationMs": float(aggregate[6]) if aggregate[6] is not None else None,
                "firstSeenAt": aggregate[7],
                "lastSeenAt": aggregate[8],
                "needsAttention": needs_attention,
                "issueCode": issue_code,
                "issueHint": issue_hint,
            },
            "items": [self._business_api_usage_log_to_dict(item) for item in rows],
        }

    @staticmethod
    def _business_api_usage_submit_filter():
        return and_(
            BusinessApiKeyUsageLog.method == "POST",
            BusinessApiKeyUsageLog.path.like("%/runs"),
            BusinessApiKeyUsageLog.path != "/api/business/runs/get",
        )

    @staticmethod
    def _business_api_usage_endpoint_kind(row: BusinessApiKeyUsageLog) -> str:
        path = str(row.path or "")
        method = str(row.method or "").upper()
        if path == "/api/business/runs/get":
            return "poll"
        if "callback" in path:
            return "callback"
        if method == "POST" and path.endswith("/runs"):
            return "submit"
        if "route-preview" in path:
            return "route_preview"
        return "other"

    @staticmethod
    def _business_api_usage_issue_summary(
        *,
        total: int,
        submit_count: int,
        poll_count: int,
        error_count: int,
    ) -> tuple[str, str, bool]:
        if total <= 0:
            return "NO_ENTRY_LOG", "没有找到入口调用记录；可能是旧数据、后台补录，或调用方没有带 runId/requestId/traceId。", True
        if error_count > 0:
            return "HAS_ERROR", "入口调用记录里存在失败响应，先看下方最近失败的错误码和接口路径。", True
        if submit_count <= 0:
            return "POLL_WITHOUT_SUBMIT", "只看到查询记录，没有看到提交记录；需要确认调用方是否保存并复用了正确的 runId。", True
        if poll_count > max(submit_count, 1) * 30:
            return "POLLING_TOO_FREQUENT", "查询次数明显偏高，建议调用方按 retryAfterSeconds 或 5-10 秒间隔轮询。", True
        return "OK", "入口提交和查询记录匹配，调用侧没有明显异常。", False

    def _business_api_usage_log_to_dict(self, row: BusinessApiKeyUsageLog) -> dict[str, Any]:
        return {
            "id": row.id,
            "apiKeyId": row.api_key_id,
            "apiKeyName": row.api_key_name,
            "apiKeyPreview": row.api_key_preview,
            "method": row.method,
            "path": row.path,
            "endpointKind": self._business_api_usage_endpoint_kind(row),
            "statusCode": row.status_code,
            "businessKey": row.business_key,
            "runId": row.run_id,
            "requestId": row.request_id,
            "traceId": row.trace_id,
            "tenantId": row.tenant_id,
            "clientId": row.client_id,
            "errorCode": row.error_code,
            "durationMs": row.duration_ms,
            "createdAt": row.created_at,
        }

    def _run_to_summary_dict(self, row: BusinessRun, *, session=None) -> dict[str, Any]:
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
        steps = self._run_steps_summary_to_dict(row, session=session)
        billing_status = self._business_billing_status(row)
        issue_summary = self._build_run_issue_summary(
            row,
            session=None,
            steps=steps,
        )
        flow_summary = self._build_run_flow_summary(
            row,
            steps=steps,
            route_info=route_info,
            session=None,
        )
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
            "request_payload": None,
            "result_payload": None,
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
            "cost_breakdown": None,
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
            "retest_source_run_id": None,
            "retest_latest_run_id": None,
            "retest_latest_status": None,
            "retest_attempts": 0,
            "retest_recovered": False,
            "retest_summary": None,
            "flow_summary": flow_summary,
            "trace_summary": self._build_run_trace_summary(row, steps=steps, flow_summary=flow_summary),
            "orchestration_graph": self._build_run_orchestration_graph(
                row,
                steps=steps,
                route_info=route_info,
                flow_summary=flow_summary,
            ),
            "steps": steps,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }

    def _run_steps_to_dict(self, row: BusinessRun, *, session=None) -> list[dict[str, Any]]:
        if session is None:
            return []
        # Avoid sorting wide JSON payload columns in MySQL. First sort only narrow indexed
        # columns, then fetch each step by primary key for detail rendering.
        step_refs = (
            session.execute(
                select(BusinessRunStep.id, BusinessRunStep.step_order)
                .where(BusinessRunStep.run_id == row.id)
                .order_by(BusinessRunStep.step_order.asc(), BusinessRunStep.id.asc())
            )
            .all()
        )
        steps: list[BusinessRunStep] = []
        for step_id, _step_order in step_refs:
            step = session.get(BusinessRunStep, step_id)
            if step:
                steps.append(step)
        log_map = self._load_ability_log_map(
            session,
            [int(step.ability_log_id) for step in steps if step.ability_log_id],
        )
        ability_ids = [str(step.ability_id) for step in steps if step.ability_id]
        ability_map = {
            ability.id: ability
            for ability in (
                session.execute(select(Ability).where(Ability.id.in_(ability_ids))).scalars().all()
                if ability_ids
                else []
            )
        }
        rows: list[dict[str, Any]] = []
        for step in steps:
            log = log_map.get(int(step.ability_log_id)) if step.ability_log_id else None
            ability = ability_map.get(str(step.ability_id or ""))
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
                    "inputSchema": self._summarize_ability_input_schema(ability.input_schema, ability=ability)
                    if ability
                    else None,
                    "defaultParams": self._compact_graph_json(ability.default_params) if ability else None,
                    "routing": self._ability_routing_summary(ability) if ability else None,
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

    @staticmethod
    def _compact_graph_json(value: Any, *, max_items: int = 16, max_text: int = 240) -> Any | None:
        if value in (None, "", []):
            return None
        if isinstance(value, dict):
            compact: dict[str, Any] = {}
            for index, (key, item) in enumerate(value.items()):
                if index >= max_items:
                    compact["..."] = f"还有 {len(value) - max_items} 项"
                    break
                nested = BusinessRunService._compact_graph_json(item, max_items=max_items, max_text=max_text)
                if nested not in (None, "", []):
                    compact[str(key)] = nested
            return compact or None
        if isinstance(value, list):
            items = [
                BusinessRunService._compact_graph_json(item, max_items=max_items, max_text=max_text)
                for item in value[:max_items]
            ]
            compact_items = [item for item in items if item not in (None, "", [])]
            if len(value) > max_items:
                compact_items.append(f"还有 {len(value) - max_items} 项")
            return compact_items or None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            return text if len(text) <= max_text else f"{text[:max_text]}..."
        return value

    @staticmethod
    def _summarize_ability_input_schema(
        schema: dict[str, Any] | None, *, ability: Ability | None = None
    ) -> dict[str, Any] | None:
        if not isinstance(schema, dict):
            return None
        raw_fields = schema.get("fields")
        if not isinstance(raw_fields, list):
            return BusinessRunService._compact_graph_json(schema)
        fields: list[dict[str, Any]] = []
        for field in raw_fields[:16]:
            if not isinstance(field, dict):
                continue
            options = field.get("options")
            if isinstance(options, list):
                options = [
                    {
                        key: item.get(key)
                        for key in ("label", "value")
                        if isinstance(item, dict) and item.get(key) not in (None, "")
                    }
                    if isinstance(item, dict)
                    else item
                    for item in options[:12]
                ]
            field = BusinessRunService._normalize_repaint_strength_schema_field(field, ability=ability)
            item = {
                "name": field.get("name"),
                "label": field.get("label"),
                "type": field.get("type"),
                "required": field.get("required"),
                "default": field.get("default"),
                "description": field.get("description"),
                "options": options,
            }
            fields.append({key: value for key, value in item.items() if value not in (None, "", [])})
        return {
            key: value
            for key, value in {
                "fieldCount": len(raw_fields),
                "fields": fields,
                "schemaVersion": schema.get("schemaVersion") or schema.get("schema_version"),
            }.items()
            if value not in (None, "", [])
        }

    @staticmethod
    def _normalize_repaint_strength_schema_field(
        field: dict[str, Any], *, ability: Ability | None = None
    ) -> dict[str, Any]:
        name = str(field.get("name") or field.get("key") or "").strip().lower()
        label = str(field.get("label") or "").strip()
        ability_text = ""
        if ability is not None:
            ability_text = " ".join(
                str(value or "")
                for value in (
                    ability.id,
                    ability.provider,
                    ability.category,
                    ability.capability_key,
                    ability.display_name,
                    ability.description,
                )
            ).lower()
        repaint_context = any(token in ability_text for token in ("fission", "裂变", "qwen2512", "print_shape"))
        should_normalize = name == "bili" or (name == "similarity" and repaint_context) or (
            repaint_context and ("相似度" in label or "similarity" in label.lower())
        )
        if not should_normalize:
            return field

        item = dict(field)
        item["label"] = "重绘幅度 Repaint Strength"
        description = str(item.get("description") or "").strip()
        if not description or "相似度" in description or "similarity" in description.lower():
            item["description"] = "值越大，画面重绘变化越明显；旧 similarity 字段仅作为兼容字段保留。"
        return item

    @staticmethod
    def _ability_routing_summary(ability: Ability | None) -> dict[str, Any] | None:
        if not ability:
            return None
        metadata = ability.extra_metadata if isinstance(ability.extra_metadata, dict) else {}
        routing = normalize_ability_routing(metadata)
        summary = {
            "selectionPolicy": routing.get("selection_policy"),
            "requiredExecutorTags": routing.get("required_executor_tags"),
            "allowedExecutorIds": routing.get("allowed_executor_ids"),
            "fallbackToDefault": routing.get("fallback_to_default"),
            "action": routing.get("action"),
            "workflowKey": routing.get("workflow_key"),
            "routingNote": metadata.get("routing_note"),
        }
        return BusinessRunService._compact_graph_json(summary)

    def _run_steps_summary_to_dict(self, row: BusinessRun, *, session=None) -> list[dict[str, Any]]:
        if session is None:
            return []
        steps = (
            session.execute(
                select(BusinessRunStep)
                .options(
                    load_only(
                        BusinessRunStep.id,
                        BusinessRunStep.run_id,
                        BusinessRunStep.step_order,
                        BusinessRunStep.step_id,
                        BusinessRunStep.step_type,
                        BusinessRunStep.role,
                        BusinessRunStep.display_name,
                        BusinessRunStep.enabled,
                        BusinessRunStep.status,
                        BusinessRunStep.ability_id,
                        BusinessRunStep.ability_name,
                        BusinessRunStep.ability_provider,
                        BusinessRunStep.ability_task_id,
                        BusinessRunStep.ability_log_id,
                        BusinessRunStep.error_message,
                        BusinessRunStep.duration_ms,
                        BusinessRunStep.billing_unit,
                        BusinessRunStep.unit_price,
                        BusinessRunStep.currency,
                        BusinessRunStep.cost_amount,
                        BusinessRunStep.quota_units,
                        BusinessRunStep.started_at,
                        BusinessRunStep.finished_at,
                        BusinessRunStep.created_at,
                        BusinessRunStep.updated_at,
                    )
                )
                .where(BusinessRunStep.run_id == row.id)
                .order_by(BusinessRunStep.step_order.asc(), BusinessRunStep.id.asc())
            )
            .scalars()
            .all()
        )
        rows: list[dict[str, Any]] = []
        for step in steps:
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
                    "executor_id": None,
                    "executor_name": None,
                    "executor_type": None,
                    "execution_evidence": None,
                    "result_summary": None,
                    "error_message": step.error_message,
                    "duration_ms": step.duration_ms,
                    "billing_unit": step.billing_unit,
                    "unit_price": float(step.unit_price) if step.unit_price is not None else None,
                    "cost_amount": float(step.cost_amount) if step.cost_amount is not None else None,
                    "currency": step.currency,
                    "quota_units": step.quota_units,
                    "cost_breakdown": None,
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
        include_payload_counts: bool = True,
    ) -> dict[str, Any]:
        if steps is None and session is not None:
            steps = self._run_steps_to_dict(row, session=session)
        steps = steps or []
        result_payload = (
            row.result_payload
            if include_payload_counts and isinstance(row.result_payload, dict)
            else {}
        )
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
        structured_count = self._count_structured_outputs(result_payload) if include_payload_counts else 0
        resource_count = self._count_resource_outputs(result_payload) if include_payload_counts else 0
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

    def _build_usage_run_issue_summary(self, row: BusinessRun) -> dict[str, Any]:
        status = str(row.status or "").strip().lower()
        image_count = len(row.image_urls or [])
        video_count = len(row.video_urls or [])
        text_count = len(row.texts or [])
        has_output = bool(image_count or video_count or text_count)
        callback_failed = status == "succeeded" and (
            str(row.callback_status or "").strip().lower() == "failed" or bool(row.callback_error)
        )
        billing_status = self._business_billing_status_for_usage_summary(row)
        billing_issue = status == "succeeded" and billing_status == "unpriced"
        route_missing = not row.business_version_id or not row.version
        error_text = " ".join(str(item or "") for item in [row.error_message, row.callback_error]).lower()
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
        elif status in {"failed", "queued", "running"}:
            category = "executor"
        else:
            category = "none"

        meta = self._issue_category_meta(category)
        evidence = "任务成功但缺少定价，待确认计费口径" if category == "billing" else row.error_message or row.callback_error
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
        include_payload_counts: bool = True,
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
        result_payload = row.result_payload if include_payload_counts and isinstance(row.result_payload, dict) else {}
        structured_count = self._count_structured_outputs(result_payload) if include_payload_counts else 0
        resource_count = self._count_resource_outputs(result_payload) if include_payload_counts else 0
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
        route_sources: list[Any] = [route, row.request_payload, row.result_payload]
        for step in steps:
            if isinstance(step, dict):
                route_sources.extend([step.get("routing"), step.get("defaultParams"), step.get("execution_evidence")])
        route_lora_name = self._usage_flow_extract_value(route_sources, BUSINESS_FLOW_LORA_KEYS)
        route_workflow_key = self._usage_flow_extract_value(route_sources, BUSINESS_FLOW_WORKFLOW_KEYS)
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
                "workflowKey": route_workflow_key,
                "loraName": route_lora_name,
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

    @staticmethod
    def _trace_step_type(step_type: str | None, role: str | None) -> str:
        normalized_type = str(step_type or "").strip().lower()
        normalized_role = str(role or "").strip().lower()
        if normalized_type.startswith("vl") or normalized_role == "preprocess":
            return "vl"
        if normalized_role == "primary" or normalized_type in {"ability_task", "comfyui_workflow", "vendor_api"}:
            return "generation"
        if normalized_type in {"score", "evaluate", "quality_score"}:
            return "score"
        if normalized_type in {"callback", "webhook"}:
            return "callback"
        return "ability"

    @staticmethod
    def _trace_node_status_label(status: str | None) -> str:
        normalized = str(status or "").strip().lower()
        return {
            "queued": "排队中",
            "running": "执行中",
            "succeeded": "成功",
            "failed": "失败",
            "skipped": "跳过",
            "cancelled": "已取消",
            "planned": "待执行",
        }.get(normalized, normalized or "未知")

    def _build_run_trace_summary(
        self,
        row: BusinessRun,
        *,
        steps: list[dict[str, Any]],
        flow_summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        flow = flow_summary if isinstance(flow_summary, dict) else {}
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        def add_node(
            node_id: str,
            *,
            parent_id: str | None,
            node_type: str,
            label: str,
            status: str | None,
            order: int,
            evidence: dict[str, Any] | None = None,
        ) -> None:
            nodes.append(
                {
                    "id": node_id,
                    "parentId": parent_id,
                    "type": node_type,
                    "label": label,
                    "status": status,
                    "statusLabel": self._trace_node_status_label(status),
                    "order": order,
                    "evidence": evidence or {},
                }
            )
            if parent_id:
                edges.append({"from": parent_id, "to": node_id})

        add_node(
            "business_entry",
            parent_id=None,
            node_type="business_entry",
            label="业务入口",
            status="succeeded" if row.status not in {"queued"} else "queued",
            order=0,
            evidence={
                "runId": row.id,
                "businessKey": row.business_key,
                "version": row.version,
                "source": row.source,
                "channel": row.channel,
                "requestId": row.request_id,
                "traceId": row.trace_id,
            },
        )

        previous_id = "business_entry"
        for index, step in enumerate(steps, start=1):
            step_id = str(step.get("step_id") or step.get("id") or f"step_{index}")
            node_id = f"step_{index}_{step_id}"
            label = (
                str(step.get("display_name") or "").strip()
                or str(step.get("ability_name") or "").strip()
                or f"处理步骤 {index}"
            )
            add_node(
                node_id,
                parent_id="business_entry",
                node_type=self._trace_step_type(step.get("step_type"), step.get("role")),
                label=label,
                status=str(step.get("status") or "planned"),
                order=index,
                evidence={
                    "stepId": step.get("step_id"),
                    "role": step.get("role"),
                    "abilityId": step.get("ability_id"),
                    "abilityTaskId": step.get("ability_task_id"),
                    "abilityLogId": step.get("ability_log_id"),
                    "executorId": step.get("executor_id"),
                    "executorName": step.get("executor_name"),
                    "durationMs": step.get("duration_ms"),
                    "error": step.get("error_message"),
                },
            )
            previous_id = node_id

        output = flow.get("output") if isinstance(flow.get("output"), dict) else {}
        add_node(
            "result_fill",
            parent_id=previous_id,
            node_type="result",
            label="结果回填",
            status="succeeded" if output.get("hasOutput") else ("failed" if row.status == "succeeded" else row.status),
            order=len(steps) + 1,
            evidence={
                "hasOutput": output.get("hasOutput"),
                "imageCount": output.get("imageCount"),
                "videoCount": output.get("videoCount"),
                "textCount": output.get("textCount"),
                "firstImageUrl": output.get("firstImageUrl"),
            },
        )

        if row.callback_url or row.callback_status or row.callback_error:
            add_node(
                "callback",
                parent_id="result_fill",
                node_type="callback",
                label="业务回调",
                status=row.callback_status or "planned",
                order=len(steps) + 2,
                evidence={
                    "callbackUrl": row.callback_url,
                    "httpStatus": row.callback_http_status,
                    "error": row.callback_error,
                },
            )

        billing_status = self._business_billing_status(row)
        if row.billing_unit or row.cost_amount is not None or row.quota_units is not None or billing_status != "unpriced":
            add_node(
                "billing",
                parent_id="result_fill",
                node_type="billing",
                label="成本记录",
                status="succeeded" if billing_status in {"billable", "free", "refunded"} else "planned",
                order=len(steps) + 3,
                evidence={
                    "billingStatus": billing_status,
                    "billingUnit": row.billing_unit,
                    "costAmount": float(row.cost_amount) if row.cost_amount is not None else None,
                    "currency": row.currency,
                    "quotaUnits": row.quota_units,
                    "noChargeReason": self._business_no_charge_reason(row),
                },
            )

        failed_node = next((node for node in nodes if str(node.get("status") or "").lower() == "failed"), None)
        active_node = next(
            (node for node in nodes if str(node.get("status") or "").lower() in {"queued", "running", "planned"}),
            None,
        )
        return {
            "runId": row.id,
            "rootId": "business_entry",
            "status": row.status,
            "summary": flow.get("message") or f"业务链路状态：{row.status}",
            "nextAction": flow.get("nextAction"),
            "failedNodeId": failed_node.get("id") if failed_node else None,
            "activeNodeId": active_node.get("id") if active_node else None,
            "nodes": nodes,
            "edges": edges,
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
                control_card = extract_fission_control_card(parsed)
                if isinstance(control_card, dict):
                    summary["fissionControlCard"] = control_card
                    for source_key, target_key in (
                        ("pattern_type", "patternType"),
                        ("profile_hint", "profileHint"),
                        ("prompt_main", "promptMain"),
                        ("prompt_control", "promptControl"),
                        ("image_desc", "imageDesc"),
                        ("pattern_risk_type", "patternRiskType"),
                        ("density_risk_level", "densityRiskLevel"),
                    ):
                        value = control_card.get(source_key)
                        if isinstance(value, (str, int, float)) and str(value).strip():
                            summary[target_key] = str(value).strip()[:1200]
                    if isinstance(control_card.get("prompt_main"), (str, int, float)):
                        summary.setdefault("positivePrompt", str(control_card.get("prompt_main")).strip()[:1200])
                    prompt_control = control_card.get("prompt_control") or control_card.get("image_desc")
                    if isinstance(prompt_control, (str, int, float)):
                        summary.setdefault("imageDesc", str(prompt_control).strip()[:1200])
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
                            summary.setdefault(target_key, str(value).strip()[:800])
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

    def _extract_text_fission_structured_response(
        self,
        raw: dict[str, Any] | None,
        texts: list[str] | None,
    ) -> dict[str, Any]:
        if isinstance(raw, dict):
            structured = raw.get("structured")
            if isinstance(structured, dict):
                return structured
            nested = raw.get("raw")
            if isinstance(nested, dict) and isinstance(nested.get("structured"), dict):
                return nested["structured"]
        for text in texts or []:
            parsed = self._try_parse_json(str(text or ""))
            if isinstance(parsed, dict):
                return parsed
        return {}

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
