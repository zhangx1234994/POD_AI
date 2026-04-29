from __future__ import annotations

from contextlib import contextmanager
import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.admin_dashboard as admin_dashboard_module
from app.core.db import Base
from app.deps.auth import require_admin
from app.main import app
from app.services.auth_service import auth_service


client = TestClient(app)


def setup_module() -> None:
    app.dependency_overrides[require_admin] = auth_service.build_service_user


def teardown_module() -> None:
    app.dependency_overrides.pop(require_admin, None)


def _install_dashboard_db(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def fake_get_session():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(admin_dashboard_module, "get_session", fake_get_session)
    return fake_get_session


def test_strategy_snapshot_and_weekly_report_records(monkeypatch, tmp_path) -> None:
    _install_dashboard_db(monkeypatch)
    monkeypatch.setattr(admin_dashboard_module, "BACKEND_ROOT", tmp_path)
    monkeypatch.setattr(admin_dashboard_module, "DASHBOARD_RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(admin_dashboard_module, "DASHBOARD_REPORT_DIR", tmp_path / "reports")

    snapshot_resp = client.post(
        "/api/admin/dashboard/strategy-summary/snapshots",
        json={"windowHours": 24, "note": "test"},
    )
    assert snapshot_resp.status_code == 200
    snapshot = snapshot_resp.json()
    assert snapshot["windowHours"] == 24
    assert snapshot["summary"]["business_total"] == 0

    snapshot_list = client.get("/api/admin/dashboard/strategy-summary/snapshots?limit=5")
    assert snapshot_list.status_code == 200
    assert snapshot_list.json()["items"][0]["id"] == snapshot["id"]

    weekly_resp = client.post(
        "/api/admin/dashboard/weekly-report/run",
        json={"windowHours": 24, "send": True, "webhookFormat": "generic"},
    )
    assert weekly_resp.status_code == 200
    weekly = weekly_resp.json()
    assert weekly["sendStatus"] == "failed"
    assert weekly["webhookConfigured"] is False
    assert weekly["reportPath"].startswith("reports/")

    weekly_list = client.get("/api/admin/dashboard/weekly-report/records?limit=5")
    assert weekly_list.status_code == 200
    assert weekly_list.json()["items"][0]["id"] == weekly["id"]


def test_release_preflight_and_patrol_records(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(admin_dashboard_module, "DASHBOARD_RUNTIME_DIR", tmp_path / "runtime")

    def fake_checks(*, base_url: str, expect_server_url: str | None = None):
        return [
            admin_dashboard_module.schemas.ReleasePreflightCheck(
                name="backend_health",
                title="后端存活",
                status="pass",
                blocking=False,
                detail=f"{base_url}|{expect_server_url}",
            ),
            admin_dashboard_module.schemas.ReleasePreflightCheck(
                name="weekly_report_cron",
                title="周报守护",
                status="warn",
                blocking=False,
                detail="人工守护",
            ),
        ]

    monkeypatch.setattr(admin_dashboard_module, "_run_release_preflight_checks", fake_checks)

    preflight_resp = client.post(
        "/api/admin/dashboard/release-preflight/run",
        json={"mode": "light", "baseUrl": "http://127.0.0.1:8099", "expectServerUrl": "http://internal:8099"},
    )
    assert preflight_resp.status_code == 200
    preflight = preflight_resp.json()
    assert preflight["status"] == "warning"
    assert preflight["canRelease"] is True
    assert preflight["warningCount"] == 1
    assert preflight["checks"][0]["name"] == "backend_health"

    preflight_list = client.get("/api/admin/dashboard/release-preflight/snapshots?limit=5")
    assert preflight_list.status_code == 200
    assert preflight_list.json()["items"][0]["id"] == preflight["id"]

    patrol_resp = client.post(
        "/api/admin/dashboard/release-patrol/records",
        json={"status": "passed", "command": "patrol", "reportPath": "reports/x.json", "summary": {"total": 1}},
    )
    assert patrol_resp.status_code == 200
    patrol = patrol_resp.json()
    assert patrol["status"] == "passed"
    assert patrol["summary"]["total"] == 1

    patrol_list = client.get("/api/admin/dashboard/release-patrol/records?limit=5")
    assert patrol_list.status_code == 200
    assert patrol_list.json()["items"][0]["id"] == patrol["id"]

    decision_resp = client.post(
        "/api/admin/dashboard/release-decisions/records",
        json={
            "status": "approved",
            "title": "确认本轮可上线",
            "preflightId": preflight["id"],
            "patrolId": patrol["id"],
            "note": "轻量门禁和完整巡检已确认",
            "summary": {"readiness": "passed"},
        },
    )
    assert decision_resp.status_code == 200
    decision = decision_resp.json()
    assert decision["status"] == "approved"
    assert decision["preflightId"] == preflight["id"]
    assert decision["patrolId"] == patrol["id"]
    assert decision["summary"]["readiness"] == "passed"

    decision_list = client.get("/api/admin/dashboard/release-decisions/records?limit=5")
    assert decision_list.status_code == 200
    assert decision_list.json()["items"][0]["id"] == decision["id"]

    invalid_decision = client.post(
        "/api/admin/dashboard/release-decisions/records",
        json={"status": "unknown"},
    )
    assert invalid_decision.status_code == 400
    assert invalid_decision.json()["detail"] == "RELEASE_DECISION_STATUS_INVALID"


def test_release_patrol_report_import(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(admin_dashboard_module, "DASHBOARD_RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(admin_dashboard_module, "BACKEND_ROOT", tmp_path)
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    report_path = report_dir / "eval_patrol.json"
    report_path.write_text(
        """
        {
          "tag": "eval-patrol-test",
          "items": [
            {
              "name": "图裂变",
              "workflowId": "wf_fission",
              "runId": "run_ok",
              "status": "succeeded",
              "podiTaskId": "task_ok",
              "imageCount": 1,
              "hasOutput": true,
              "issueCode": "OK"
            },
            {
              "name": "扩图",
              "workflowId": "wf_outpaint",
              "runId": "run_no_output",
              "status": "succeeded",
              "podiTaskId": "task_no_output",
              "imageCount": 0,
              "hasOutput": false
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    resp = client.post(
        "/api/admin/dashboard/release-patrol/import-report",
        json={"reportPath": "reports/eval_patrol.json", "command": "patrol"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["reportPath"] == "reports/eval_patrol.json"
    assert body["summary"]["total"] == 2
    assert body["summary"]["succeeded"] == 1
    assert body["summary"]["failedOrUnfinished"] == 1
    assert body["summary"]["noOutput"] == 1
    assert body["summary"]["issueSummary"]["OK"] == 1
    assert body["summary"]["issueSummary"]["EVAL_SUCCEEDED_WITHOUT_OUTPUT"] == 1
    assert body["summary"]["failedItems"][0]["workflowId"] == "wf_outpaint"
    assert body["summary"]["failedItems"][0]["issueCode"] == "EVAL_SUCCEEDED_WITHOUT_OUTPUT"
    assert body["summary"]["abilityHealthEvidence"][0]["healthStatus"] == "healthy"
    assert body["summary"]["abilityHealthEvidence"][1]["healthStatus"] == "failed"
