"""Admin endpoints for managing executors, workflows, bindings, and API keys."""

from __future__ import annotations

import json
import logging
import time
from urllib.parse import urlparse
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
import httpx
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.db import get_session
from app.deps.auth import require_admin
from app.models.integration import (
    Ability,
    ApiKey,
    ComfyuiLora,
    ComfyuiModelCatalog,
    ComfyuiPluginCatalog,
    ComfyuiVersionCatalog,
    ComfyuiServerDiffLog,
    Executor,
    ExecutorApiKey,
    Workflow,
    WorkflowBinding,
)
from app.schemas import admin_integrations as schemas
from app.schemas import admin_tests, admin_workflows
from app.services.ability_logs import AbilityLogStartParams, ability_log_service
from app.services.ability_invocation import ability_invocation_service
from app.services.executor_seed import ensure_default_executors
from app.services.integration_test import integration_test_service
from app.services.workflow_seed import ensure_default_bindings, ensure_default_workflows

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)


def _generate_id(existing_id: str | None) -> str:
    return existing_id or uuid4().hex


def _build_log_params(
    payload: Any,
    *,
    provider: str,
    capability_key: str,
    request_payload: dict[str, Any],
) -> AbilityLogStartParams:
    ability_id = getattr(payload, "abilityId", None)
    ability_name = getattr(payload, "abilityName", None)
    ability_provider = getattr(payload, "abilityProvider", None) or provider
    ability_capability = getattr(payload, "capabilityKey", None) or capability_key
    executor_id = getattr(payload, "executorId", None)
    return AbilityLogStartParams(
        ability_id=ability_id,
        ability_name=ability_name,
        provider=ability_provider,
        capability_key=ability_capability,
        executor_id=executor_id,
        source="admin-test",
        request_payload=request_payload,
    )


def _extract_error_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, str):
            return detail
        try:
            return json.dumps(detail, ensure_ascii=False)
        except TypeError:  # pragma: no cover - defensive
            return str(detail)
    return str(exc)


def _extract_error_payload(exc: Exception) -> dict[str, Any] | None:
    if isinstance(exc, HTTPException):
        return {"status_code": exc.status_code, "detail": exc.detail}
    return None


def _normalize_comfyui_lora_payload(data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return data
    base_models_raw = data.get("base_models")
    if base_models_raw is not None:
        if isinstance(base_models_raw, (list, tuple, set)):
            base_models = [str(item).strip() for item in base_models_raw if str(item).strip()]
        else:
            trimmed = str(base_models_raw).strip()
            base_models = [trimmed] if trimmed else []
        data["base_models"] = base_models or None
        if len(base_models) == 1:
            data["base_model"] = base_models[0]
        else:
            data["base_model"] = None
    else:
        base_model = str(data.get("base_model") or "").strip()
        if base_model:
            data["base_model"] = base_model
            data["base_models"] = [base_model]
        else:
            data.pop("base_model", None)
    return data


def _normalize_comfyui_model_payload(data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return data
    for key in ("file_name", "display_name", "model_type"):
        if key in data and isinstance(data[key], str):
            data[key] = data[key].strip()
    tags = data.get("tags")
    if tags is not None:
        if isinstance(tags, (list, tuple, set)):
            cleaned = [str(item).strip() for item in tags if str(item).strip()]
        else:
            trimmed = str(tags).strip()
            cleaned = [trimmed] if trimmed else []
        data["tags"] = cleaned or None
    return data


def _normalize_comfyui_plugin_payload(data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return data
    for key in ("node_key", "display_name", "package_name", "version"):
        if key in data and isinstance(data[key], str):
            data[key] = data[key].strip()
    tags = data.get("tags")
    if tags is not None:
        if isinstance(tags, (list, tuple, set)):
            cleaned = [str(item).strip() for item in tags if str(item).strip()]
        else:
            trimmed = str(tags).strip()
            cleaned = [trimmed] if trimmed else []
        data["tags"] = cleaned or None
    return data


def _normalize_comfyui_version_payload(data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return data
    for key in ("version", "commit_sha", "repo_url", "source_url", "download_url", "notes", "status"):
        if key in data and isinstance(data[key], str):
            data[key] = data[key].strip()
    return data


def _parse_github_repo(repo_url: str) -> tuple[str, str]:
    parsed = urlparse(repo_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="COMFYUI_VERSION_SOURCE_INVALID")
    if "github.com" not in parsed.netloc:
        raise HTTPException(status_code=400, detail="COMFYUI_VERSION_SOURCE_INVALID")
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="COMFYUI_VERSION_SOURCE_INVALID")
    return parts[0], parts[1]


def _fetch_github_tags(repo_url: str, *, limit: int) -> list[dict[str, Any]]:
    owner, repo = _parse_github_repo(repo_url)
    settings = get_settings()
    api_base = settings.comfyui_repo_api_base.rstrip("/")
    headers = {"User-Agent": "podi-comfyui-version-sync/1.0"}
    if settings.comfyui_repo_api_token:
        headers["Authorization"] = f"Bearer {settings.comfyui_repo_api_token}"

    tags: list[dict[str, Any]] = []
    per_page = min(100, max(1, limit))
    page = 1
    while len(tags) < limit:
        url = f"{api_base}/repos/{owner}/{repo}/tags"
        try:
            response = httpx.get(url, headers=headers, params={"per_page": per_page, "page": page}, timeout=15)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("ComfyUI version sync failed: %s", exc)
            raise HTTPException(status_code=502, detail="COMFYUI_VERSION_SYNC_FAILED") from exc
        payload = response.json()
        if not isinstance(payload, list):
            raise HTTPException(status_code=502, detail="COMFYUI_VERSION_SYNC_FAILED")
        if not payload:
            break
        tags.extend(payload)
        if len(payload) < per_page:
            break
        page += 1
    return tags[:limit]

def _run_with_logging(
    payload: Any,
    *,
    provider: str,
    capability_key: str,
    request_payload: dict[str, Any],
    runner: Callable[[], dict[str, Any]],
) -> tuple[dict[str, Any], int | None]:
    params = _build_log_params(payload, provider=provider, capability_key=capability_key, request_payload=request_payload)
    log_id = ability_log_service.start_log(params)
    start_time = time.perf_counter()
    try:
        result = runner()
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        ability_log_service.finish_failure(
            log_id,
            error_message=_extract_error_message(exc),
            response_payload=_extract_error_payload(exc),
            duration_ms=duration_ms,
        )
        raise
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    ability_log_service.finish_success(log_id, response_payload=result, duration_ms=duration_ms)
    return result, log_id


def _find_comfyui_ability(workflow_key: str | None, ability_id: str | None) -> Ability | None:
    if not ability_id and not workflow_key:
        return None
    with get_session() as session:
        if ability_id:
            ability = session.get(Ability, ability_id)
            if ability:
                return ability
        if workflow_key:
            stmt = select(Ability).where(
                Ability.provider == "comfyui",
                Ability.capability_key == workflow_key,
            )
            ability = session.execute(stmt).scalar_one_or_none()
            if ability:
                return ability
    return None


@router.get("/executors", response_model=list[schemas.ExecutorRead])
def list_executors() -> list[Executor]:
    with get_session() as session:
        ensure_default_executors(session)
        stmt = (
            select(Executor)
            .options(selectinload(Executor.api_key_links))
            .order_by(Executor.created_at.desc())
        )
        return session.execute(stmt).scalars().all()


@router.post("/executors", response_model=schemas.ExecutorRead)
def create_executor(payload: schemas.ExecutorCreate) -> Executor:
    with get_session() as session:
        executor = Executor(
            id=_generate_id(payload.id),
            name=payload.name,
            type=payload.type,
            base_url=payload.base_url,
            status=payload.status,
            weight=payload.weight,
            max_concurrency=payload.max_concurrency,
            config=payload.config or {},
        )
        session.add(executor)
        session.flush()
        _apply_executor_api_keys(session, executor, payload.api_key_ids)
        session.commit()
        session.refresh(executor)
        # preload api key links to avoid detached lazy load
        _ = list(executor.api_key_links)
        ability_invocation_service.invalidate_executor_slot(executor.id)
        return executor


@router.get("/executors/{executor_id}", response_model=schemas.ExecutorRead)
def get_executor(executor_id: str) -> Executor:
    with get_session() as session:
        stmt = (
            select(Executor)
            .options(selectinload(Executor.api_key_links))
            .where(Executor.id == executor_id)
        )
        executor = session.execute(stmt).scalar_one_or_none()
        if not executor:
            raise HTTPException(status_code=404, detail="EXECUTOR_NOT_FOUND")
        return executor


@router.put("/executors/{executor_id}", response_model=schemas.ExecutorRead)
def update_executor(executor_id: str, payload: schemas.ExecutorUpdate) -> Executor:
    with get_session() as session:
        executor = session.get(Executor, executor_id)
        if not executor:
            raise HTTPException(status_code=404, detail="EXECUTOR_NOT_FOUND")
        data = payload.model_dump(exclude_unset=True, exclude={"api_key_ids"})
        for key, value in data.items():
            setattr(executor, key, value)
        if payload.api_key_ids is not None:
            _apply_executor_api_keys(session, executor, payload.api_key_ids)
        session.add(executor)
        session.commit()
        session.refresh(executor)
        _ = list(executor.api_key_links)
        ability_invocation_service.invalidate_executor_slot(executor.id)
        return executor


@router.delete("/executors/{executor_id}")
def delete_executor(executor_id: str) -> dict[str, str]:
    with get_session() as session:
        executor = session.get(Executor, executor_id)
        if not executor:
            raise HTTPException(status_code=404, detail="EXECUTOR_NOT_FOUND")
        session.delete(executor)
        session.commit()
        ability_invocation_service.invalidate_executor_slot(executor_id)
        return {"status": "deleted"}


@router.get("/workflows", response_model=list[schemas.WorkflowRead])
def list_workflows() -> list[Workflow]:
    with get_session() as session:
        ensure_default_workflows(session)
        stmt = select(Workflow).order_by(Workflow.created_at.desc())
        return session.execute(stmt).scalars().all()


@router.post("/workflows", response_model=schemas.WorkflowRead)
def create_workflow(payload: schemas.WorkflowCreate) -> Workflow:
    with get_session() as session:
        workflow = Workflow(
            id=_generate_id(payload.id),
            action=payload.action,
            name=payload.name,
            version=payload.version,
            type=payload.type,
            definition=payload.definition,
            status=payload.status,
            extra_metadata=payload.metadata,
        )
        session.add(workflow)
        session.commit()
        session.refresh(workflow)
        return workflow


@router.get("/workflows/{workflow_id}", response_model=schemas.WorkflowRead)
def get_workflow(workflow_id: str) -> Workflow:
    with get_session() as session:
        workflow = session.get(Workflow, workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="WORKFLOW_NOT_FOUND")
        return workflow


@router.put("/workflows/{workflow_id}", response_model=schemas.WorkflowRead)
def update_workflow(workflow_id: str, payload: schemas.WorkflowUpdate) -> Workflow:
    with get_session() as session:
        workflow = session.get(Workflow, workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="WORKFLOW_NOT_FOUND")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(workflow, key, value)
        session.add(workflow)
        session.commit()
        session.refresh(workflow)
        return workflow


@router.delete("/workflows/{workflow_id}")
def delete_workflow(workflow_id: str) -> dict[str, str]:
    with get_session() as session:
        workflow = session.get(Workflow, workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="WORKFLOW_NOT_FOUND")
        session.delete(workflow)
        session.commit()
        return {"status": "deleted"}


@router.get("/workflow-bindings", response_model=list[schemas.WorkflowBindingRead])
def list_bindings() -> list[WorkflowBinding]:
    with get_session() as session:
        ensure_default_executors(session)
        ensure_default_workflows(session)
        ensure_default_bindings(session)
        stmt = select(WorkflowBinding).order_by(WorkflowBinding.created_at.desc())
        return session.execute(stmt).scalars().all()


@router.post("/workflow-bindings", response_model=schemas.WorkflowBindingRead)
def create_binding(payload: schemas.WorkflowBindingCreate) -> WorkflowBinding:
    with get_session() as session:
        workflow = session.get(Workflow, payload.workflow_id)
        executor = session.get(Executor, payload.executor_id)
        if not workflow or not executor:
            raise HTTPException(status_code=400, detail="INVALID_WORKFLOW_OR_EXECUTOR")
        binding = WorkflowBinding(
            id=_generate_id(payload.id),
            action=payload.action,
            workflow_id=payload.workflow_id,
            executor_id=payload.executor_id,
            priority=payload.priority,
            enabled=payload.enabled,
            extra_metadata=payload.metadata,
        )
        session.add(binding)
        session.commit()
        session.refresh(binding)
        return binding


@router.put("/workflow-bindings/{binding_id}", response_model=schemas.WorkflowBindingRead)
def update_binding(binding_id: str, payload: schemas.WorkflowBindingUpdate) -> WorkflowBinding:
    with get_session() as session:
        binding = session.get(WorkflowBinding, binding_id)
        if not binding:
            raise HTTPException(status_code=404, detail="BINDING_NOT_FOUND")
        data = payload.model_dump(exclude_unset=True)
        if "workflow_id" in data:
            workflow = session.get(Workflow, data["workflow_id"])
            if not workflow:
                raise HTTPException(status_code=400, detail="WORKFLOW_NOT_FOUND")
        if "executor_id" in data:
            executor = session.get(Executor, data["executor_id"])
            if not executor:
                raise HTTPException(status_code=400, detail="EXECUTOR_NOT_FOUND")
        for key, value in data.items():
            setattr(binding, key, value)
        session.add(binding)
        session.commit()
        session.refresh(binding)
        return binding


@router.delete("/workflow-bindings/{binding_id}")
def delete_binding(binding_id: str) -> dict[str, str]:
    with get_session() as session:
        binding = session.get(WorkflowBinding, binding_id)
        if not binding:
            raise HTTPException(status_code=404, detail="BINDING_NOT_FOUND")
        session.delete(binding)
        session.commit()
        return {"status": "deleted"}


@router.get("/api-keys", response_model=list[schemas.ApiKeyRead])
def list_api_keys() -> list[ApiKey]:
    with get_session() as session:
        stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
        return session.execute(stmt).scalars().all()


@router.post("/api-keys", response_model=schemas.ApiKeyRead)
def create_api_key(payload: schemas.ApiKeyCreate) -> ApiKey:
    with get_session() as session:
        api_key = ApiKey(
            id=_generate_id(payload.id),
            provider=payload.provider,
            name=payload.name,
            key=payload.key,
            status=payload.status,
            daily_quota=payload.daily_quota,
            expire_at=payload.expire_at,
            extra_metadata=payload.metadata,
        )
        session.add(api_key)
        session.commit()
        session.refresh(api_key)
        return api_key


@router.put("/api-keys/{key_id}", response_model=schemas.ApiKeyRead)
def update_api_key(key_id: str, payload: schemas.ApiKeyUpdate) -> ApiKey:
    with get_session() as session:
        api_key = session.get(ApiKey, key_id)
        if not api_key:
            raise HTTPException(status_code=404, detail="API_KEY_NOT_FOUND")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(api_key, key, value)
        session.add(api_key)
        session.commit()
        session.refresh(api_key)
        return api_key


@router.delete("/api-keys/{key_id}")
def delete_api_key(key_id: str) -> dict[str, str]:
    with get_session() as session:
        api_key = session.get(ApiKey, key_id)
        if not api_key:
            raise HTTPException(status_code=404, detail="API_KEY_NOT_FOUND")
        session.delete(api_key)
        session.commit()
        return {"status": "deleted"}


@router.post("/tests/baidu/quality-upgrade", response_model=admin_tests.BaiduQualityUpgradeTestResponse)
def test_baidu_quality_upgrade(payload: admin_tests.BaiduQualityUpgradeTestRequest):
    capability_key = payload.capabilityKey or "quality_upgrade"
    request_payload = {
        "resolution": payload.resolution,
        "upscaleType": payload.upscaleType,
        "imageUrl": payload.imageUrl,
        "hasImageBase64": bool(payload.imageBase64),
    }
    result, log_id = _run_with_logging(
        payload,
        provider="baidu",
        capability_key=capability_key,
        request_payload=request_payload,
        runner=lambda: integration_test_service.run_baidu_quality_upgrade(
            executor_id=payload.executorId,
            image_base64=payload.imageBase64,
            image_url=payload.imageUrl,
            resolution=payload.resolution,
            upscale_type=payload.upscaleType,
        ),
    )
    return admin_tests.BaiduQualityUpgradeTestResponse(**result, logId=log_id)


@router.post("/tests/baidu/image-process", response_model=admin_tests.BaiduImageProcessTestResponse)
def test_baidu_image_process(payload: admin_tests.BaiduImageProcessTestRequest):
    capability_key = payload.capabilityKey or payload.operation.value
    request_payload = {
        "operation": payload.operation.value,
        "imageUrl": payload.imageUrl,
        "hasImageBase64": bool(payload.imageBase64),
        "params": payload.params or {},
    }
    result, log_id = _run_with_logging(
        payload,
        provider="baidu",
        capability_key=capability_key,
        request_payload=request_payload,
        runner=lambda: integration_test_service.run_baidu_image_process(
            executor_id=payload.executorId,
            operation=payload.operation.value,
            image_base64=payload.imageBase64,
            image_url=payload.imageUrl,
            params=payload.params or {},
        ),
    )
    return admin_tests.BaiduImageProcessTestResponse(**result, logId=log_id)


@router.post("/tests/volcengine/chat", response_model=admin_tests.VolcengineChatTestResponse)
def test_volcengine_chat(payload: admin_tests.VolcengineChatTestRequest):
    capability_key = payload.capabilityKey or payload.model
    request_payload = {
        "model": payload.model,
        "prompt": payload.prompt,
        "imageUrl": payload.imageUrl,
        "params": payload.params or {},
    }
    result, log_id = _run_with_logging(
        payload,
        provider="volcengine",
        capability_key=capability_key,
        request_payload=request_payload,
        runner=lambda: integration_test_service.run_volcengine_chat_completion(
            executor_id=payload.executorId,
            model=payload.model,
            prompt=payload.prompt,
            image_url=payload.imageUrl,
            params=payload.params or {},
        ),
    )
    return admin_tests.VolcengineChatTestResponse(**result, logId=log_id)


@router.post("/tests/volcengine/image", response_model=admin_tests.VolcengineImageTestResponse)
def test_volcengine_image(payload: admin_tests.VolcengineImageTestRequest):
    capability_key = payload.capabilityKey or payload.model
    request_payload = {
        "model": payload.model,
        "prompt": payload.prompt,
        "negativePrompt": payload.negativePrompt,
        "size": payload.size,
        "responseFormat": payload.responseFormat,
        "params": payload.params or {},
    }
    result, log_id = _run_with_logging(
        payload,
        provider="volcengine",
        capability_key=capability_key,
        request_payload=request_payload,
        runner=lambda: integration_test_service.run_volcengine_image_generation(
            executor_id=payload.executorId,
            model=payload.model,
            prompt=payload.prompt,
            negative_prompt=payload.negativePrompt,
            size=payload.size,
            response_format=payload.responseFormat,
            params=payload.params or {},
        ),
    )
    return admin_tests.VolcengineImageTestResponse(
        provider=result.get("provider", "volcengine"),
        model=result.get("model", payload.model),
        logId=log_id,
        imageUrl=result.get("imageUrl"),
        imageBase64=result.get("imageBase64"),
        storedUrl=result.get("storedUrl"),
        assets=result.get("assets"),
        raw=result.get("raw"),
    )


@router.post("/tests/kie/market", response_model=admin_tests.KieMarketTestResponse)
def test_kie_market(payload: admin_tests.KieMarketTestRequest):
    capability_key = payload.capabilityKey or payload.model
    request_payload = {
        "model": payload.model,
        "endpoint": payload.endpoint,
        "callBackUrl": payload.callBackUrl,
        "input": payload.input,
        "extra": payload.extra,
        "pollTimeout": payload.pollTimeout,
    }
    result, log_id = _run_with_logging(
        payload,
        provider="kie",
        capability_key=capability_key,
        request_payload=request_payload,
        runner=lambda: integration_test_service.run_kie_market_task(
            executor_id=payload.executorId,
            endpoint=payload.endpoint,
            model=payload.model,
            input_payload=payload.input,
            call_back_url=payload.callBackUrl,
            extra_payload=payload.extra,
            poll_timeout=payload.pollTimeout or 75,
        ),
    )
    return admin_tests.KieMarketTestResponse(**result, logId=log_id)


@router.post("/tests/comfyui/workflow", response_model=admin_tests.ComfyuiWorkflowTestResponse)
def test_comfyui_workflow(payload: admin_tests.ComfyuiWorkflowTestRequest):
    capability_key = payload.capabilityKey or payload.workflowKey
    ability = _find_comfyui_ability(payload.workflowKey, None)
    # Guardrail: some ComfyUI graphs require custom nodes only installed on specific servers.
    # Even if the frontend picks the wrong executor, keep the test running on a compatible node.
    if ability and isinstance(ability.extra_metadata, dict):
        allowed = ability.extra_metadata.get("allowed_executor_ids")
        if isinstance(allowed, list):
            allowed_ids = [str(x).strip() for x in allowed if isinstance(x, str) and x.strip()]
            if allowed_ids and payload.executorId not in allowed_ids:
                payload.executorId = allowed_ids[0]
    request_payload = {
        "workflowKey": payload.workflowKey,
        "workflowParams": payload.workflowParams,
    }
    submit_only = bool(payload.submitOnly)
    if submit_only:
        result, log_id = _run_with_logging(
            payload,
            provider="comfyui",
            capability_key=capability_key,
            request_payload=request_payload,
            runner=lambda: integration_test_service.submit_comfyui_workflow(
                executor_id=payload.executorId,
                workflow_key=payload.workflowKey,
                workflow_params=payload.workflowParams or {},
            ),
        )
        return admin_tests.ComfyuiWorkflowTestResponse(**result, logId=log_id, state="submitted")
    result, log_id = _run_with_logging(
        payload,
        provider="comfyui",
        capability_key=capability_key,
        request_payload=request_payload,
        runner=lambda: integration_test_service.run_comfyui_workflow(
            executor_id=payload.executorId,
            workflow_key=payload.workflowKey,
            workflow_params=payload.workflowParams or {},
        ),
    )
    return admin_tests.ComfyuiWorkflowTestResponse(**result, logId=log_id)


@router.post("/workflows/comfyui/trigger", response_model=admin_workflows.ComfyuiWorkflowTriggerResponse)
def trigger_comfyui_workflow(payload: admin_workflows.ComfyuiWorkflowTriggerRequest, request: Request):
    ability = _find_comfyui_ability(payload.workflowKey, payload.abilityId)
    if ability and isinstance(ability.extra_metadata, dict):
        allowed = ability.extra_metadata.get("allowed_executor_ids")
        if isinstance(allowed, list):
            allowed_ids = [str(x).strip() for x in allowed if isinstance(x, str) and x.strip()]
            if allowed_ids and payload.executorId not in allowed_ids:
                payload.executorId = allowed_ids[0]
    request_payload = {
        "workflowKey": payload.workflowKey,
        "workflowParams": payload.workflowParams,
        "workflowRunId": payload.workflowRunId,
    }
    workflow_run_id = payload.workflowRunId or request.headers.get("X-Podi-Workflow-Run-Id")
    params = AbilityLogStartParams(
        ability_id=getattr(ability, "id", None),
        ability_name=getattr(ability, "display_name", None),
        provider="comfyui",
        capability_key=payload.workflowKey,
        executor_id=payload.executorId,
        source=payload.source or "workflow-trigger",
        request_payload=request_payload,
        workflow_run_id=workflow_run_id,
    )
    log_id = ability_log_service.start_log(params)
    start_time = time.perf_counter()
    try:
        result = integration_test_service.run_comfyui_workflow(
            executor_id=payload.executorId,
            workflow_key=payload.workflowKey,
            workflow_params=payload.workflowParams or {},
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        ability_log_service.finish_failure(
            log_id,
            error_message=_extract_error_message(exc),
            response_payload=_extract_error_payload(exc),
            duration_ms=duration_ms,
        )
        raise
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    ability_log_service.finish_success(log_id, response_payload=result, duration_ms=duration_ms)
    return admin_workflows.ComfyuiWorkflowTriggerResponse(
        **result, logId=log_id, workflowRunId=workflow_run_id
    )


@router.get("/comfyui/models", response_model=admin_tests.ComfyuiModelCatalogResponse)
def list_comfyui_models(
    executor_id: str = Query(..., alias="executorId"),
    include_nodes: bool = Query(False, alias="includeNodes"),
):
    result = integration_test_service.get_comfyui_model_catalog(
        executor_id=executor_id,
        include_nodes=include_nodes,
    )
    return admin_tests.ComfyuiModelCatalogResponse(**result)


@router.get("/comfyui/loras", response_model=schemas.ComfyuiLoraCatalogResponse)
def list_comfyui_loras(
    executor_id: str | None = Query(None, alias="executorId"),
    query: str | None = Query(None, alias="q"),
    status: str | None = Query(None),
    include_untracked: bool = Query(True, alias="includeUntracked"),
):
    with get_session() as session:
        loras: list[ComfyuiLora] = []
        try:
            stmt = select(ComfyuiLora)
            if status:
                stmt = stmt.where(ComfyuiLora.status == status)
            if query:
                keyword = f"%{query.strip()}%"
                stmt = stmt.where(
                    or_(
                        ComfyuiLora.file_name.like(keyword),
                        ComfyuiLora.display_name.like(keyword),
                    )
                )
            loras = session.execute(stmt.order_by(ComfyuiLora.updated_at.desc())).scalars().all()
        except SQLAlchemyError as exc:
            logger.warning("comfyui lora catalog query failed: %s", exc)
            loras = []

        file_set: set[str] = set()
        base_url: str | None = None
        installed_files: list[str] | None = None
        if executor_id:
            try:
                catalog = integration_test_service.get_comfyui_model_catalog(executor_id=executor_id)
                raw_files = catalog.get("models", {}).get("lora") or []
                file_set = {str(item) for item in raw_files if str(item).strip()}
                installed_files = sorted(file_set)
                base_url = catalog.get("baseUrl")
            except HTTPException as exc:
                logger.warning("comfyui lora catalog fetch failed: %s", exc.detail)
                file_set = set()
                installed_files = None
                base_url = None

        items: list[schemas.ComfyuiLoraRead] = []
        for row in loras:
            item = schemas.ComfyuiLoraRead.model_validate(row)
            if executor_id:
                item = item.model_copy(update={"installed": row.file_name in file_set})
            items.append(item)

        untracked_files: list[str] | None = None
        if executor_id and include_untracked:
            tracked = {row.file_name for row in loras}
            untracked_files = sorted(file_set - tracked)

        return schemas.ComfyuiLoraCatalogResponse(
            executorId=executor_id,
            baseUrl=base_url,
            installedFiles=installed_files,
            untrackedFiles=untracked_files,
            items=items,
        )


@router.post("/comfyui/loras", response_model=schemas.ComfyuiLoraRead)
def create_comfyui_lora(payload: schemas.ComfyuiLoraCreate) -> ComfyuiLora:
    data = payload.model_dump(exclude_unset=True, exclude={"id"})
    data = _normalize_comfyui_lora_payload(data)
    with get_session() as session:
        existing = session.execute(
            select(ComfyuiLora).where(ComfyuiLora.file_name == payload.file_name)
        ).scalar_one_or_none()
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing
        lora = ComfyuiLora(**data)
        session.add(lora)
        session.commit()
        session.refresh(lora)
        return lora


@router.put("/comfyui/loras/{lora_id}", response_model=schemas.ComfyuiLoraRead)
def update_comfyui_lora(lora_id: int, payload: schemas.ComfyuiLoraUpdate) -> ComfyuiLora:
    data = payload.model_dump(exclude_unset=True)
    data.pop("file_name", None)
    data = _normalize_comfyui_lora_payload(data)
    with get_session() as session:
        lora = session.get(ComfyuiLora, lora_id)
        if not lora:
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        for key, value in data.items():
            setattr(lora, key, value)
        session.add(lora)
        session.commit()
        session.refresh(lora)
        return lora


@router.delete("/comfyui/loras/{lora_id}")
def delete_comfyui_lora(lora_id: int) -> dict[str, str]:
    with get_session() as session:
        lora = session.get(ComfyuiLora, lora_id)
        if not lora:
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        session.delete(lora)
        session.commit()
        return {"status": "deleted"}


@router.get("/comfyui/model-catalog", response_model=schemas.ComfyuiModelCatalogResponse)
def list_comfyui_model_catalog(
    query: str | None = Query(None, alias="q"),
    model_type: str | None = Query(None, alias="type"),
    status: str | None = Query(None),
):
    with get_session() as session:
        stmt = select(ComfyuiModelCatalog)
        if status:
            stmt = stmt.where(ComfyuiModelCatalog.status == status)
        if model_type:
            stmt = stmt.where(ComfyuiModelCatalog.model_type == model_type)
        if query:
            keyword = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    ComfyuiModelCatalog.file_name.like(keyword),
                    ComfyuiModelCatalog.display_name.like(keyword),
                )
            )
        items = session.execute(stmt.order_by(ComfyuiModelCatalog.updated_at.desc())).scalars().all()
        return schemas.ComfyuiModelCatalogResponse(
            items=[schemas.ComfyuiModelCatalogRead.model_validate(item) for item in items]
        )


@router.post("/comfyui/model-catalog", response_model=schemas.ComfyuiModelCatalogRead)
def create_comfyui_model_catalog(payload: schemas.ComfyuiModelCatalogCreate) -> ComfyuiModelCatalog:
    data = payload.model_dump(exclude_unset=True, exclude={"id"})
    data = _normalize_comfyui_model_payload(data)
    with get_session() as session:
        existing = session.execute(
            select(ComfyuiModelCatalog).where(
                ComfyuiModelCatalog.file_name == payload.file_name,
                ComfyuiModelCatalog.model_type == payload.model_type,
            )
        ).scalar_one_or_none()
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing
        row = ComfyuiModelCatalog(**data)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


@router.put("/comfyui/model-catalog/{model_id}", response_model=schemas.ComfyuiModelCatalogRead)
def update_comfyui_model_catalog(
    model_id: int, payload: schemas.ComfyuiModelCatalogUpdate
) -> ComfyuiModelCatalog:
    data = payload.model_dump(exclude_unset=True)
    data = _normalize_comfyui_model_payload(data)
    with get_session() as session:
        row = session.get(ComfyuiModelCatalog, model_id)
        if not row:
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        for key, value in data.items():
            setattr(row, key, value)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


@router.delete("/comfyui/model-catalog/{model_id}")
def delete_comfyui_model_catalog(model_id: int) -> dict[str, str]:
    with get_session() as session:
        row = session.get(ComfyuiModelCatalog, model_id)
        if not row:
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        session.delete(row)
        session.commit()
        return {"status": "deleted"}


@router.get("/comfyui/plugin-catalog", response_model=schemas.ComfyuiPluginCatalogResponse)
def list_comfyui_plugin_catalog(
    query: str | None = Query(None, alias="q"),
    status: str | None = Query(None),
):
    with get_session() as session:
        stmt = select(ComfyuiPluginCatalog)
        if status:
            stmt = stmt.where(ComfyuiPluginCatalog.status == status)
        if query:
            keyword = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    ComfyuiPluginCatalog.node_key.like(keyword),
                    ComfyuiPluginCatalog.display_name.like(keyword),
                    ComfyuiPluginCatalog.package_name.like(keyword),
                )
            )
        items = session.execute(stmt.order_by(ComfyuiPluginCatalog.updated_at.desc())).scalars().all()
        return schemas.ComfyuiPluginCatalogResponse(
            items=[schemas.ComfyuiPluginCatalogRead.model_validate(item) for item in items]
        )


@router.post("/comfyui/plugin-catalog", response_model=schemas.ComfyuiPluginCatalogRead)
def create_comfyui_plugin_catalog(payload: schemas.ComfyuiPluginCatalogCreate) -> ComfyuiPluginCatalog:
    data = payload.model_dump(exclude_unset=True, exclude={"id"})
    data = _normalize_comfyui_plugin_payload(data)
    with get_session() as session:
        existing = session.execute(
            select(ComfyuiPluginCatalog).where(ComfyuiPluginCatalog.node_key == payload.node_key)
        ).scalar_one_or_none()
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing
        row = ComfyuiPluginCatalog(**data)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


@router.put("/comfyui/plugin-catalog/{plugin_id}", response_model=schemas.ComfyuiPluginCatalogRead)
def update_comfyui_plugin_catalog(
    plugin_id: int, payload: schemas.ComfyuiPluginCatalogUpdate
) -> ComfyuiPluginCatalog:
    data = payload.model_dump(exclude_unset=True)
    data = _normalize_comfyui_plugin_payload(data)
    with get_session() as session:
        row = session.get(ComfyuiPluginCatalog, plugin_id)
        if not row:
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        for key, value in data.items():
            setattr(row, key, value)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


@router.delete("/comfyui/plugin-catalog/{plugin_id}")
def delete_comfyui_plugin_catalog(plugin_id: int) -> dict[str, str]:
    with get_session() as session:
        row = session.get(ComfyuiPluginCatalog, plugin_id)
        if not row:
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        session.delete(row)
        session.commit()
        return {"status": "deleted"}


@router.get("/comfyui/version-catalog", response_model=schemas.ComfyuiVersionCatalogResponse)
def list_comfyui_version_catalog(
    query: str | None = Query(None, alias="q"),
    status: str | None = Query(None),
):
    with get_session() as session:
        stmt = select(ComfyuiVersionCatalog)
        if status:
            stmt = stmt.where(ComfyuiVersionCatalog.status == status)
        if query:
            keyword = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    ComfyuiVersionCatalog.version.like(keyword),
                    ComfyuiVersionCatalog.commit_sha.like(keyword),
                    ComfyuiVersionCatalog.repo_url.like(keyword),
                )
            )
        items = session.execute(stmt.order_by(ComfyuiVersionCatalog.updated_at.desc())).scalars().all()
        return schemas.ComfyuiVersionCatalogResponse(
            items=[schemas.ComfyuiVersionCatalogRead.model_validate(item) for item in items]
        )


@router.post("/comfyui/version-catalog", response_model=schemas.ComfyuiVersionCatalogRead)
def create_comfyui_version_catalog(payload: schemas.ComfyuiVersionCatalogCreate) -> ComfyuiVersionCatalog:
    data = payload.model_dump(exclude_unset=True, exclude={"id"})
    data = _normalize_comfyui_version_payload(data)
    with get_session() as session:
        existing = session.execute(
            select(ComfyuiVersionCatalog).where(ComfyuiVersionCatalog.version == payload.version)
        ).scalar_one_or_none()
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing
        row = ComfyuiVersionCatalog(**data)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


@router.put("/comfyui/version-catalog/{version_id}", response_model=schemas.ComfyuiVersionCatalogRead)
def update_comfyui_version_catalog(
    version_id: int, payload: schemas.ComfyuiVersionCatalogUpdate
) -> ComfyuiVersionCatalog:
    data = payload.model_dump(exclude_unset=True)
    data.pop("version", None)
    data = _normalize_comfyui_version_payload(data)
    with get_session() as session:
        row = session.get(ComfyuiVersionCatalog, version_id)
        if not row:
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        for key, value in data.items():
            setattr(row, key, value)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


@router.delete("/comfyui/version-catalog/{version_id}")
def delete_comfyui_version_catalog(version_id: int) -> dict[str, str]:
    with get_session() as session:
        row = session.get(ComfyuiVersionCatalog, version_id)
        if not row:
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        session.delete(row)
        session.commit()
        return {"status": "deleted"}


@router.post("/comfyui/version-catalog/sync", response_model=schemas.ComfyuiVersionCatalogSyncResponse)
def sync_comfyui_version_catalog(limit: int = Query(50, ge=1, le=200)):
    settings = get_settings()
    repo_url = (settings.comfyui_repo_url or "").strip()
    if not repo_url:
        raise HTTPException(status_code=400, detail="COMFYUI_VERSION_SOURCE_INVALID")
    tags = _fetch_github_tags(repo_url, limit=limit)
    created = 0
    updated = 0
    with get_session() as session:
        for item in tags:
            if not isinstance(item, dict):
                continue
            version = str(item.get("name") or "").strip()
            if not version:
                continue
            commit_sha = None
            commit = item.get("commit")
            if isinstance(commit, dict):
                commit_sha = str(commit.get("sha") or "").strip() or None
            download_url = str(item.get("zipball_url") or "").strip() or None
            source_url = f"{repo_url.rstrip('/')}/tree/{version}"
            row = session.execute(
                select(ComfyuiVersionCatalog).where(ComfyuiVersionCatalog.version == version)
            ).scalar_one_or_none()
            if row:
                changed = False
                if commit_sha and not row.commit_sha:
                    row.commit_sha = commit_sha
                    changed = True
                if repo_url and not row.repo_url:
                    row.repo_url = repo_url
                    changed = True
                if source_url and not row.source_url:
                    row.source_url = source_url
                    changed = True
                if download_url and not row.download_url:
                    row.download_url = download_url
                    changed = True
                if changed:
                    session.add(row)
                    updated += 1
                continue
            row = ComfyuiVersionCatalog(
                version=version,
                commit_sha=commit_sha,
                repo_url=repo_url,
                source_url=source_url,
                download_url=download_url,
                status="active",
            )
            session.add(row)
            created += 1
        session.commit()
    return schemas.ComfyuiVersionCatalogSyncResponse(
        repo_url=repo_url,
        fetched_at=datetime.utcnow(),
        total=len(tags),
        created=created,
        updated=updated,
    )


@router.post("/comfyui/server-diff", response_model=schemas.ComfyuiServerDiffRead)
def create_comfyui_server_diff(payload: schemas.ComfyuiServerDiffCreate) -> ComfyuiServerDiffLog:
    data = payload.model_dump(exclude_unset=True)
    with get_session() as session:
        row = ComfyuiServerDiffLog(**data)
        session.add(row)
        session.commit()
        session.refresh(row)

        baseline_id = payload.baseline_executor_id
        now = datetime.utcnow().isoformat(timespec="seconds")
        servers = payload.payload.get("servers") if isinstance(payload.payload, dict) else None
        if isinstance(servers, list):
            for entry in servers:
                if not isinstance(entry, dict):
                    continue
                server = entry.get("server") if isinstance(entry.get("server"), dict) else {}
                executor_id = server.get("id") if isinstance(server, dict) else None
                if not executor_id:
                    continue
                executor = session.get(Executor, executor_id)
                if not executor:
                    continue
                config = executor.config or {}
                if executor_id == baseline_id:
                    config["sync_role"] = "master"
                    config["last_sync_at"] = now
                else:
                    config["sync_role"] = "worker"
                    missing = entry.get("missing")
                    if isinstance(missing, dict):
                        empty = all(
                            isinstance(missing.get(key), list) and len(missing.get(key)) == 0
                            for key in ("unet", "clip", "vae", "lora", "nodes")
                        )
                        if empty:
                            config["last_sync_at"] = now
                executor.config = config
                session.add(executor)
            session.commit()
        return row


@router.get("/comfyui/server-diff", response_model=list[schemas.ComfyuiServerDiffRead])
def list_comfyui_server_diff(limit: int = Query(10, ge=1, le=50)):
    with get_session() as session:
        items = (
            session.execute(select(ComfyuiServerDiffLog).order_by(ComfyuiServerDiffLog.id.desc()).limit(limit))
            .scalars()
            .all()
        )
        return [schemas.ComfyuiServerDiffRead.model_validate(item) for item in items]


@router.get("/comfyui/queue-status", response_model=admin_tests.ComfyuiQueueStatusResponse)
def get_comfyui_queue_status(executor_id: str = Query(..., alias="executorId")):
    result = integration_test_service.get_comfyui_queue_status(executor_id=executor_id)
    return admin_tests.ComfyuiQueueStatusResponse(**result)


@router.get("/comfyui/queue-summary", response_model=admin_tests.ComfyuiQueueSummaryResponse)
def get_comfyui_queue_summary(executor_ids: list[str] | None = Query(None, alias="executorIds")):
    result = integration_test_service.get_comfyui_queue_summary(executor_ids=executor_ids)
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    return admin_tests.ComfyuiQueueSummaryResponse(**result)


@router.get("/comfyui/system-stats", response_model=admin_tests.ComfyuiSystemStatsResponse)
def get_comfyui_system_stats(executor_id: str = Query(..., alias="executorId")):
    result = integration_test_service.get_comfyui_system_stats(executor_id=executor_id)
    return admin_tests.ComfyuiSystemStatsResponse(**result)


def _apply_executor_api_keys(session, executor: Executor, api_key_ids: list[str] | None) -> None:
    desired = {key_id for key_id in (api_key_ids or []) if key_id}
    existing_links = list(executor.api_key_links)
    for link in existing_links:
        if link.api_key_id not in desired:
            session.delete(link)
    existing_ids = {link.api_key_id for link in existing_links}
    for api_key_id in desired - existing_ids:
        session.add(ExecutorApiKey(executor_id=executor.id, api_key_id=api_key_id))
