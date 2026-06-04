from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
import threading
import time

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.integration_test as integration_test_module
from app.models.integration import Ability, AbilityTask, Executor, VendorModelCatalog, Workflow
from app.models.user import User
from app.services.integration_test import IntegrationTestService


def _install_executor_db(monkeypatch, *, include_tasks: bool = False):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if include_tasks:
        User.__table__.create(engine)
        Executor.__table__.create(engine)
        Workflow.__table__.create(engine)
        VendorModelCatalog.__table__.create(engine)
        Ability.__table__.create(engine)
        AbilityTask.__table__.create(engine)
    else:
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


def test_comfyui_queue_summary_cache_deduplicates_concurrent_refresh(monkeypatch) -> None:
    monkeypatch.setattr(integration_test_module, "suppress_background_threads_for_tests", lambda: False)
    IntegrationTestService._clear_comfyui_queue_summary_cache()

    calls = 0
    call_lock = threading.Lock()

    def producer() -> dict[str, object]:
        nonlocal calls
        with call_lock:
            calls += 1
            value = calls
        time.sleep(0.05)
        return {"totalRunning": value, "servers": [{"value": value}]}

    key = IntegrationTestService._comfyui_queue_summary_cache_key(())
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: IntegrationTestService._comfyui_queue_summary_cached(key, producer), range(8)))

    assert calls == 1
    assert {item["totalRunning"] for item in results} == {1}

    results[0]["servers"][0]["value"] = 99
    assert IntegrationTestService._comfyui_queue_summary_cached(key, producer)["servers"][0]["value"] == 1

    monkeypatch.setattr(integration_test_module, "suppress_background_threads_for_tests", lambda: True)
    assert IntegrationTestService._comfyui_queue_summary_cached(key, producer)["totalRunning"] == 2

    IntegrationTestService._clear_comfyui_queue_summary_cache()


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
    assert summary["totalCapacity"] == 10
    assert summary["unsupportedServers"] == 1
    with testing_session() as session:
        ok = session.get(Executor, "executor_ok")
        down = session.get(Executor, "executor_down")
        assert ok is not None
        assert down is not None
        assert ok.health_status == "healthy"
        assert ok.last_heartbeat_at is not None
        assert down.health_status == "failed"
        assert down.last_heartbeat_at is None


def test_comfyui_queue_summary_exposes_backend_feed_gap(monkeypatch) -> None:
    testing_session = _install_executor_db(monkeypatch)
    with testing_session() as session:
        session.add(
            Executor(
                id="executor_idle",
                name="Idle GPU",
                type="comfyui",
                base_url="http://idle.example",
                status="active",
                max_concurrency=10,
                config={},
            )
        )
        session.commit()

    service = IntegrationTestService()

    monkeypatch.setattr(
        service,
        "get_comfyui_queue_status",
        lambda *, executor_id: {
            "executorId": executor_id,
            "baseUrl": "http://idle.example",
            "runningCount": 0,
            "pendingCount": 0,
            "queueMaxSize": 10,
            "supported": True,
            "raw": {},
        },
    )
    monkeypatch.setattr(
        service,
        "_summarize_backend_comfyui_tasks",
        lambda executor_ids: {
            "executor_idle": {
                "queued": 3,
                "running": 0,
                "oldestQueuedAt": "2026-05-03T10:00:00",
                "oldestRunningAt": None,
            }
        },
    )

    summary = service.get_comfyui_queue_summary()
    server = summary["servers"][0]

    assert summary["backendQueuedTotal"] == 3
    assert summary["feedGapServers"] == 1
    assert summary["diagnostics"][0]["code"] == "COMFYUI_FEED_GAP"
    assert server["backendQueued"] == 3
    assert server["idleSlots"] == 10
    assert server["feedCode"] == "backend_queued_with_idle_capacity"
    assert server["feedDiagnosisLevel"] == "warning"


def test_comfyui_queue_summary_treats_short_invisible_running_as_settling(monkeypatch) -> None:
    testing_session = _install_executor_db(monkeypatch)
    with testing_session() as session:
        session.add(
            Executor(
                id="executor_settling",
                name="Settling GPU",
                type="comfyui",
                base_url="http://settling.example",
                status="active",
                max_concurrency=10,
                config={},
            )
        )
        session.commit()

    service = IntegrationTestService()
    now = datetime.utcnow()
    monkeypatch.setattr(
        service,
        "get_comfyui_queue_status",
        lambda *, executor_id: {
            "executorId": executor_id,
            "baseUrl": "http://settling.example",
            "runningCount": 0,
            "pendingCount": 0,
            "queueMaxSize": 10,
            "supported": True,
            "raw": {},
        },
    )
    monkeypatch.setattr(
        service,
        "_summarize_backend_comfyui_tasks",
        lambda executor_ids: {
            "executor_settling": {
                "queued": 0,
                "running": 1,
                "oldestQueuedAt": None,
                "oldestRunningAt": (now - timedelta(seconds=45)).isoformat(),
            }
        },
    )

    summary = service.get_comfyui_queue_summary()
    server = summary["servers"][0]

    assert summary["backendBlockedServers"] == 0
    assert summary["backendRunningInvisibleServers"] == 1
    assert summary["backendRunningSettlingServers"] == 1
    assert summary["diagnostics"][0]["code"] == "COMFYUI_BACKEND_RUNNING_SETTLING"
    assert server["feedCode"] == "backend_running_settling"
    assert server["feedDiagnosisLevel"] == "warning"
    assert server["feedAction"]


def test_comfyui_queue_summary_blocks_stale_invisible_running(monkeypatch) -> None:
    testing_session = _install_executor_db(monkeypatch)
    with testing_session() as session:
        session.add(
            Executor(
                id="executor_stale",
                name="Stale GPU",
                type="comfyui",
                base_url="http://stale.example",
                status="active",
                max_concurrency=10,
                config={},
            )
        )
        session.commit()

    service = IntegrationTestService()
    now = datetime.utcnow()
    monkeypatch.setattr(
        service,
        "get_comfyui_queue_status",
        lambda *, executor_id: {
            "executorId": executor_id,
            "baseUrl": "http://stale.example",
            "runningCount": 0,
            "pendingCount": 0,
            "queueMaxSize": 10,
            "supported": True,
            "raw": {},
        },
    )
    monkeypatch.setattr(
        service,
        "_summarize_backend_comfyui_tasks",
        lambda executor_ids: {
            "executor_stale": {
                "queued": 0,
                "running": 1,
                "oldestQueuedAt": None,
                "oldestRunningAt": (now - timedelta(minutes=12)).isoformat(),
            }
        },
    )

    summary = service.get_comfyui_queue_summary()
    server = summary["servers"][0]

    assert summary["backendBlockedServers"] == 1
    assert summary["backendRunningInvisibleServers"] == 1
    assert summary["backendRunningSettlingServers"] == 0
    assert summary["diagnostics"][0]["code"] == "COMFYUI_BACKEND_RUNNING_NOT_VISIBLE"
    assert server["feedCode"] == "backend_running_not_visible"
    assert server["feedDiagnosisLevel"] == "danger"
    assert server["backendOldestRunningAgeSeconds"] >= 700


def test_comfyui_queue_summary_exposes_recent_route_evidence(monkeypatch) -> None:
    testing_session = _install_executor_db(monkeypatch, include_tasks=True)
    now = datetime.utcnow()
    with testing_session() as session:
        session.add_all(
            [
                Executor(
                    id="executor_158",
                    name="ComfyUI-158",
                    type="comfyui",
                    base_url="http://158.example",
                    status="active",
                    max_concurrency=10,
                    config={"tags": ["host:158", "gpu:5090", "comfyui-general"]},
                ),
                Executor(
                    id="executor_233",
                    name="ComfyUI-233",
                    type="comfyui",
                    base_url="http://233.example",
                    status="active",
                    max_concurrency=10,
                    config={"tags": ["host:233", "gpu:4090", "comfyui-general"]},
                ),
                Ability(
                    id="ability_fission",
                    provider="comfyui",
                    category="image",
                    capability_key="fission",
                    display_name="图裂变",
                    status="active",
                ),
                AbilityTask(
                    id="task_recent_158",
                    ability_id="ability_fission",
                    ability_name="图裂变",
                    ability_provider="comfyui",
                    capability_key="fission",
                    status="succeeded",
                    request_payload={},
                    result_payload={"metadata": {"executorId": "executor_158"}},
                    created_at=now - timedelta(minutes=10),
                    updated_at=now - timedelta(minutes=8),
                    finished_at=now - timedelta(minutes=8),
                ),
                AbilityTask(
                    id="task_old_233",
                    ability_id="ability_fission",
                    ability_name="图裂变",
                    ability_provider="comfyui",
                    capability_key="fission",
                    status="succeeded",
                    request_payload={"executorId": "executor_233"},
                    result_payload={},
                    created_at=now - timedelta(days=2),
                    updated_at=now - timedelta(days=2),
                    finished_at=now - timedelta(days=2),
                ),
            ]
        )
        session.commit()

    service = IntegrationTestService()

    monkeypatch.setattr(
        service,
        "get_comfyui_queue_status",
        lambda *, executor_id: {
            "executorId": executor_id,
            "baseUrl": f"http://{executor_id}.example",
            "runningCount": 0,
            "pendingCount": 0,
            "queueMaxSize": 10,
            "supported": True,
            "raw": {},
        },
    )

    summary = service.get_comfyui_queue_summary()
    servers = {item["executorId"]: item for item in summary["servers"]}

    assert summary["routeEvidenceTotal"] == 1
    assert summary["routeEvidenceCoveredServers"] == 1
    assert summary["recentRouteMissingServers"] == 1
    assert any(item["code"] == "COMFYUI_ROUTE_EVIDENCE_MISSING" for item in summary["diagnostics"])
    assert servers["executor_158"]["routeEvidence"]["recentSucceeded"] == 1
    assert servers["executor_158"]["routeEvidence"]["latestTaskId"] == "task_recent_158"
    assert servers["executor_233"]["routeEvidence"]["recentTotal"] == 0
    assert servers["executor_233"]["routeDiagnosisLevel"] == "warning"
