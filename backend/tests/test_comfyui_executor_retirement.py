from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.ability_invocation as ability_invocation_module
import app.services.ability_task_service as ability_task_service_module
from app.core.db import Base
from app.models.integration import Ability, AbilityTask, Executor
from app.schemas.abilities import AbilityInvokeRequest
from app.services.ability_invocation import AbilityInvocationService
from app.services.ability_task_service import AbilityTaskService


@pytest.fixture()
def comfyui_retirement_db(monkeypatch):
    """构造 158 可用、233 停用的固定数据库，供新旧任务边界测试复用。"""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def fake_get_session():
        """让调用服务和任务服务共享同一个内存数据库，避免依赖开发环境数据。"""

        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(ability_invocation_module, "get_session", fake_get_session)
    monkeypatch.setattr(ability_task_service_module, "get_session", fake_get_session)

    with testing_session() as session:
        session.add_all(
            [
                Executor(
                    id="executor_comfyui_pattern_extract_158",
                    name="ComfyUI 158",
                    type="comfyui",
                    base_url="http://158.example:8079",
                    status="active",
                    max_concurrency=10,
                    config={"tags": ["comfyui-general"]},
                ),
                Executor(
                    id="executor_comfyui_seamless_117",
                    name="ComfyUI 233",
                    type="comfyui",
                    base_url="http://233.example:8079",
                    status="inactive",
                    max_concurrency=10,
                    config={"tags": ["comfyui-general"]},
                ),
                Executor(
                    id="executor_comfyui_other",
                    name="ComfyUI other",
                    type="comfyui",
                    base_url="http://other.example:8079",
                    status="active",
                    max_concurrency=10,
                    config={"tags": ["comfyui-general"]},
                ),
                Ability(
                    id="comfyui_retirement_test",
                    provider="comfyui",
                    category="image_generation",
                    capability_key="retirement_test",
                    display_name="节点下线测试能力",
                    description="",
                    status="active",
                    ability_type="workflow",
                    default_params={"workflow_key": "retirement_test"},
                    input_schema={},
                    extra_metadata={
                        "workflow_key": "retirement_test",
                        "action": "image_fission",
                        "allowed_executor_ids": ["executor_comfyui_pattern_extract_158"],
                    },
                ),
            ]
        )
        session.commit()

    return testing_session


def test_new_sync_request_rejects_inactive_explicit_executor(comfyui_retirement_db) -> None:
    """发布后的同步请求显式传 233 时，应在生成调用日志和访问远端前直接拒绝。"""

    service = AbilityInvocationService()

    with pytest.raises(HTTPException) as exc_info:
        service.invoke(
            ability_id="comfyui_retirement_test",
            payload=AbilityInvokeRequest(executorId="executor_comfyui_seamless_117", inputs={}),
            user=None,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "EXECUTOR_INACTIVE"


def test_new_async_task_rejects_233_before_database_insert(comfyui_retirement_db) -> None:
    """新异步任务显式传 233 时不能写入 ability_tasks，避免重启后又被当作历史任务放行。"""

    service = AbilityTaskService.__new__(AbilityTaskService)
    service._executor = SimpleNamespace(submit=lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as exc_info:
        service.enqueue(
            ability_id="comfyui_retirement_test",
            payload=AbilityInvokeRequest(executorId="executor_comfyui_seamless_117", inputs={}),
            user=None,
        )

    assert exc_info.value.detail == "EXECUTOR_INACTIVE"
    with comfyui_retirement_db() as session:
        task_count = session.scalar(select(func.count()).select_from(AbilityTask))
    assert task_count == 0


def test_new_async_task_rejects_stale_ability_default_233(comfyui_retirement_db) -> None:
    """旧能力行默认指向 233 时，新请求即使不传 executorId 也不能把 233 固化进新任务。"""

    with comfyui_retirement_db() as session:
        ability = session.get(Ability, "comfyui_retirement_test")
        assert ability is not None
        ability.executor_id = "executor_comfyui_seamless_117"
        session.add(ability)
        session.commit()

    service = AbilityTaskService.__new__(AbilityTaskService)
    service._executor = SimpleNamespace(submit=lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as exc_info:
        service.enqueue(
            ability_id="comfyui_retirement_test",
            payload=AbilityInvokeRequest(inputs={}),
            user=None,
        )

    assert exc_info.value.detail == "EXECUTOR_INACTIVE"
    with comfyui_retirement_db() as session:
        task_count = session.scalar(select(func.count()).select_from(AbilityTask))
    assert task_count == 0


def test_existing_ability_task_keeps_assigned_233_executor(comfyui_retirement_db, monkeypatch) -> None:
    """发布前已持久化的 ability-task 必须继续使用 233，保证在服务器关机前可以排空。"""

    service = AbilityInvocationService()
    captured: dict[str, str] = {}

    def fake_dispatch_provider(*, executor_id: str, **_kwargs):
        """仅记录最终执行器，不访问真实 ComfyUI 网络。"""

        captured["executor_id"] = executor_id
        return {"status": "succeeded", "executorId": executor_id}

    monkeypatch.setattr(service, "_dispatch_provider", fake_dispatch_provider)
    monkeypatch.setattr(ability_invocation_module.ability_log_service, "start_log", lambda _params: 101)
    monkeypatch.setattr(
        ability_invocation_module.ability_log_service,
        "finish_success",
        lambda *_args, **_kwargs: None,
    )

    response = service.invoke(
        ability_id="comfyui_retirement_test",
        payload=AbilityInvokeRequest(executorId="executor_comfyui_seamless_117", inputs={}),
        user=None,
        task_id="existing-task-1",
        source="ability-task",
    )

    assert response.status == "succeeded"
    assert captured["executor_id"] == "executor_comfyui_seamless_117"


def test_active_158_explicit_executor_is_allowed(comfyui_retirement_db) -> None:
    """能力白名单内且 active 的 158 仍可由内部调用方显式指定。"""

    service = AbilityInvocationService()
    ability = service._get_ability("comfyui_retirement_test")

    executor_id = service.validate_explicit_comfyui_executor(
        ability=ability,
        executor_id="executor_comfyui_pattern_extract_158",
        source="test",
    )

    assert executor_id == "executor_comfyui_pattern_extract_158"


def test_active_executor_outside_ability_allowlist_is_rejected(comfyui_retirement_db) -> None:
    """节点即使 active，只要不在该能力白名单内，也不能被新请求绕过兼容路由显式调用。"""

    service = AbilityInvocationService()

    with pytest.raises(HTTPException) as exc_info:
        service.invoke(
            ability_id="comfyui_retirement_test",
            payload=AbilityInvokeRequest(executorId="executor_comfyui_other", inputs={}),
            user=None,
        )

    assert exc_info.value.detail == "COMFYUI_EXECUTOR_NOT_ALLOWED"
