"""Admin endpoints for managing executors, workflows, bindings, and API keys."""

from __future__ import annotations

import json
import time
from typing import Any, Callable
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.deps.auth import require_admin
from app.models.integration import Ability, ApiKey, Executor, ExecutorApiKey, Workflow, WorkflowBinding
from app.schemas import admin_integrations as schemas
from app.schemas import admin_tests, admin_workflows
from app.services.ability_logs import AbilityLogStartParams, ability_log_service
from app.services.executor_seed import ensure_default_executors
from app.services.integration_test import integration_test_service
from app.services.workflow_seed import ensure_default_bindings, ensure_default_workflows

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


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
        return executor


@router.delete("/executors/{executor_id}")
def delete_executor(executor_id: str) -> dict[str, str]:
    with get_session() as session:
        executor = session.get(Executor, executor_id)
        if not executor:
            raise HTTPException(status_code=404, detail="EXECUTOR_NOT_FOUND")
        session.delete(executor)
        session.commit()
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
def list_comfyui_models(executor_id: str = Query(..., alias="executorId")):
    result = integration_test_service.get_comfyui_model_catalog(executor_id=executor_id)
    return admin_tests.ComfyuiModelCatalogResponse(**result)


@router.get("/comfyui/queue-status", response_model=admin_tests.ComfyuiQueueStatusResponse)
def get_comfyui_queue_status(executor_id: str = Query(..., alias="executorId")):
    result = integration_test_service.get_comfyui_queue_status(executor_id=executor_id)
    return admin_tests.ComfyuiQueueStatusResponse(**result)


def _apply_executor_api_keys(session, executor: Executor, api_key_ids: list[str] | None) -> None:
    desired = {key_id for key_id in (api_key_ids or []) if key_id}
    existing_links = list(executor.api_key_links)
    for link in existing_links:
        if link.api_key_id not in desired:
            session.delete(link)
    existing_ids = {link.api_key_id for link in existing_links}
    for api_key_id in desired - existing_ids:
        session.add(ExecutorApiKey(executor_id=executor.id, api_key_id=api_key_id))
