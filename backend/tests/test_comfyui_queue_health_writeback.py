from __future__ import annotations

from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.integration_test as integration_test_module
from app.models.integration import Executor
from app.services.integration_test import IntegrationTestService


def _install_executor_db(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Executor.__table__.create(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def fake_get_session():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(integration_test_module, "get_session", fake_get_session)
    return testing_session


def test_comfyui_queue_summary_writes_executor_health(monkeypatch) -> None:
    testing_session = _install_executor_db(monkeypatch)
    with testing_session() as session:
        session.add_all(
            [
                Executor(
                    id="executor_ok",
                    name="OK",
                    type="comfyui",
                    base_url="http://ok.example",
                    status="active",
                    max_concurrency=10,
                    config={},
                ),
                Executor(
                    id="executor_down",
                    name="Down",
                    type="comfyui",
                    base_url="http://down.example",
                    status="active",
                    max_concurrency=10,
                    config={},
                ),
            ]
        )
        session.commit()

    service = IntegrationTestService()

    def fake_queue_status(*, executor_id: str):
        if executor_id == "executor_down":
            raise HTTPException(status_code=502, detail="COMFYUI_QUEUE_STATUS_ERROR")
        return {
            "executorId": executor_id,
            "baseUrl": "http://ok.example",
            "runningCount": 1,
            "pendingCount": 2,
            "queueMaxSize": 10,
            "supported": True,
            "raw": {"queue_running": [1], "queue_pending": [1, 2]},
        }

    monkeypatch.setattr(service, "get_comfyui_queue_status", fake_queue_status)
    summary = service.get_comfyui_queue_summary()

    assert summary["totalRunning"] == 1
    assert summary["totalPending"] == 2
    with testing_session() as session:
        ok = session.get(Executor, "executor_ok")
        down = session.get(Executor, "executor_down")
        assert ok is not None
        assert down is not None
        assert ok.health_status == "healthy"
        assert ok.last_heartbeat_at is not None
        assert down.health_status == "failed"
        assert down.last_heartbeat_at is None
