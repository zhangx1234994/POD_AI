from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.task_dispatcher as dispatcher_module
from app.models.integration import Executor, Workflow, WorkflowBinding
from app.models.task import Task, TaskEvent
from app.services.executors import ExecutionResult
from app.services.executors.kie import KieMarketExecutorAdapter
from app.services.task_dispatcher import TaskDispatcherService


def _install_dispatcher_db(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        Executor.__table__,
        Workflow.__table__,
        WorkflowBinding.__table__,
        Task.__table__,
        TaskEvent.__table__,
    ):
        table.create(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def fake_get_session():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(dispatcher_module, "get_session", fake_get_session)
    monkeypatch.setattr(dispatcher_module.api_key_service, "acquire", lambda provider: None)
    return testing_session


def test_dispatcher_keeps_async_executor_result_running(monkeypatch) -> None:
    testing_session = _install_dispatcher_db(monkeypatch)

    class RunningAdapter:
        def execute(self, context):
            return ExecutionResult(
                success=True,
                status="running",
                progress=0,
                result_payload={"taskId": "kie_task_1", "executorId": context.executor.id},
            )

    monkeypatch.setattr(dispatcher_module.registry, "get", lambda executor_type: RunningAdapter())
    with testing_session() as session:
        session.add(Executor(id="executor_kie", name="KIE", type="kie", status="active", weight=1, config={}))
        session.add(Workflow(id="workflow_kie", action="kie_run", name="KIE", definition={}, status="active"))
        session.add(
            WorkflowBinding(
                id="binding_kie",
                action="kie_run",
                workflow_id="workflow_kie",
                executor_id="executor_kie",
                priority=10,
                enabled=True,
            )
        )
        session.add(
            Task(
                id="task_1",
                user_id="user_1",
                channel="api",
                tool_action="kie_run",
                status="pending",
                input_payload={"prompt": "test"},
            )
        )
        session.commit()

    reports = TaskDispatcherService().dispatch_pending(limit=1)

    assert reports[0].status == "running"
    with testing_session() as session:
        task = session.get(Task, "task_1")
        assert task is not None
        assert task.status == "running"
        assert task.finished_at is None
        assert task.result_payload == {"taskId": "kie_task_1", "executorId": "executor_kie"}
        events = session.execute(select(TaskEvent).where(TaskEvent.task_id == "task_1")).scalars().all()
        assert [event.event_type for event in events] == ["started", "progress"]


def test_dispatcher_filters_binding_by_required_executor_tags(monkeypatch) -> None:
    testing_session = _install_dispatcher_db(monkeypatch)

    class EchoAdapter:
        def execute(self, context):
            return ExecutionResult(
                success=True,
                status="completed",
                progress=100,
                result_payload={"executorId": context.executor.id},
            )

    monkeypatch.setattr(dispatcher_module.registry, "get", lambda executor_type: EchoAdapter())
    with testing_session() as session:
        session.add(Executor(id="executor_general", name="General", type="mock", status="active", weight=10, config={}))
        session.add(
            Executor(
                id="executor_high_mem",
                name="High Mem",
                type="mock",
                status="active",
                weight=1,
                config={"tags": ["upscale", "high-mem"]},
            )
        )
        session.add(Workflow(id="workflow_general", action="upscale", name="General", definition={}, status="active"))
        session.add(Workflow(id="workflow_high_mem", action="upscale", name="High Mem", definition={}, status="active"))
        session.add(
            WorkflowBinding(
                id="binding_general",
                action="upscale",
                workflow_id="workflow_general",
                executor_id="executor_general",
                priority=100,
                enabled=True,
            )
        )
        session.add(
            WorkflowBinding(
                id="binding_high_mem",
                action="upscale",
                workflow_id="workflow_high_mem",
                executor_id="executor_high_mem",
                priority=50,
                enabled=True,
            )
        )
        session.add(
            Task(
                id="task_2",
                user_id="user_1",
                channel="api",
                tool_action="upscale",
                status="pending",
                input_payload={"required_executor_tags": ["high-mem"]},
            )
        )
        session.commit()

    reports = TaskDispatcherService().dispatch_pending(limit=1)

    assert reports[0].status == "completed"
    with testing_session() as session:
        task = session.get(Task, "task_2")
        assert task is not None
        assert task.result_payload == {"executorId": "executor_high_mem"}


def test_kie_adapter_wraps_market_helper(monkeypatch) -> None:
    from app.services.integration_test import integration_test_service

    captured = {}

    def fake_run_kie_market_task(**kwargs):
        captured.update(kwargs)
        return {
            "status": "succeeded",
            "taskId": "upstream_1",
            "resultUrls": ["https://oss.example/out.png"],
        }

    monkeypatch.setattr(integration_test_service, "run_kie_market_task", fake_run_kie_market_task)
    context = SimpleNamespace(
        task=SimpleNamespace(id="task_3"),
        workflow=SimpleNamespace(
            definition={
                "model": "flux-2-pro",
                "input_array_target": "input_urls",
                "defaults": {"resolution": "1K"},
                "poll_timeout": 2,
            }
        ),
        executor=SimpleNamespace(id="executor_kie"),
        payload={"prompt": "生成图片", "image_urls": ["https://example.com/a.png"]},
    )

    result = KieMarketExecutorAdapter().execute(context)

    assert result.success is True
    assert result.status == "completed"
    assert captured["executor_id"] == "executor_kie"
    assert captured["model"] == "flux-2-pro"
    assert captured["input_array_target"] == "input_urls"
    assert captured["input_payload"]["resolution"] == "1K"
    assert captured["input_payload"]["prompt"] == "生成图片"
    assert captured["input_payload"]["image_urls"] == ["https://example.com/a.png"]


def test_kie_adapter_preserves_running_state(monkeypatch) -> None:
    from app.services.integration_test import integration_test_service

    monkeypatch.setattr(
        integration_test_service,
        "run_kie_market_task",
        lambda **kwargs: {"status": "running", "taskId": "upstream_2"},
    )
    context = SimpleNamespace(
        task=SimpleNamespace(id="task_4"),
        workflow=SimpleNamespace(definition={"model": "nano-banana-2"}),
        executor=SimpleNamespace(id="executor_kie"),
        payload={},
    )

    result = KieMarketExecutorAdapter().execute(context)

    assert result.success is True
    assert result.status == "running"
    assert result.result_payload == {"status": "running", "taskId": "upstream_2"}
