from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.models.eval import EvalRun, EvalWorkflowVersion
from app.services.eval_operations_health import build_eval_operations_health


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _workflow(**overrides):
    data = {
        "id": "wf_v1",
        "category": "图裂变",
        "name": "图裂变主线",
        "version": "v1",
        "workflow_id": "7631838631375667200",
        "status": "active",
    }
    data.update(overrides)
    return EvalWorkflowVersion(**data)


def _run(**overrides):
    now = datetime.utcnow()
    data = {
        "id": "run_1",
        "workflow_version_id": "wf_v1",
        "dataset_item_id": None,
        "input_oss_urls_json": ["https://oss.example/input.png"],
        "parameters_json": {},
        "status": "succeeded",
        "result_image_urls_json": ["https://oss.example/out.png"],
        "created_by": "tester",
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return EvalRun(**data)


def test_eval_operations_health_detects_stale_and_output_issues():
    session = _session()
    now = datetime.utcnow()
    session.add(_workflow())
    session.add_all(
        [
            _run(
                id="stale",
                status="running",
                coze_execute_id="exec_1",
                result_image_urls_json=None,
                created_at=now - timedelta(minutes=45),
                updated_at=now - timedelta(minutes=40),
            ),
            _run(
                id="submit_stalled",
                status="running",
                coze_execute_id=None,
                podi_task_id=None,
                result_image_urls_json=None,
                created_at=now - timedelta(minutes=8),
                updated_at=now - timedelta(minutes=8),
            ),
            _run(
                id="empty_success",
                status="succeeded",
                result_image_urls_json=[],
                result_output_json=None,
                created_at=now - timedelta(minutes=3),
                updated_at=now - timedelta(minutes=3),
            ),
            _run(
                id="failed",
                status="failed",
                result_image_urls_json=None,
                error_message="COZE_WORKFLOW_ERROR: execute tool failed",
                created_at=now - timedelta(minutes=2),
                updated_at=now - timedelta(minutes=2),
            ),
        ]
    )
    session.commit()

    report = build_eval_operations_health(
        session,
        stale_minutes=30,
        submit_grace_minutes=5,
        recent_hours=24,
    )

    assert report["status"] == "critical"
    issue_codes = {item["code"] for item in report["issues"]}
    assert "EVAL_RUN_STALE" in issue_codes
    assert "EVAL_SUBMIT_STALLED" in issue_codes
    assert "EVAL_SUCCESS_WITHOUT_OUTPUT" in issue_codes
    assert "EVAL_RECENT_FAILURES" in issue_codes
    assert report["errorCounts"]["COZE_WORKFLOW_ERROR"] == 1


def test_eval_operations_health_is_healthy_for_recent_completed_output():
    session = _session()
    session.add(_workflow())
    session.add(_run(id="ok"))
    session.commit()

    report = build_eval_operations_health(session)

    assert report["status"] == "healthy"
    assert report["issues"] == []
    assert report["activeWorkflowCount"] == 1
    assert report["recentStatusCounts"]["succeeded"] == 1
    assert report["recentRunTotal"] == 1
    assert report["recentSuccessCount"] == 1
    assert report["recentFailureCount"] == 0


def test_eval_operations_health_warns_when_no_recent_runs():
    session = _session()
    session.add(_workflow())
    session.commit()

    report = build_eval_operations_health(session)

    assert report["status"] == "warning"
    assert report["recentRunTotal"] == 0
    issue_codes = {item["code"] for item in report["issues"]}
    assert "EVAL_NO_RECENT_RUNS" in issue_codes


def test_eval_operations_health_is_critical_when_recent_runs_have_no_success():
    session = _session()
    now = datetime.utcnow()
    session.add(_workflow())
    session.add(
        _run(
            id="failed_only",
            status="failed",
            result_image_urls_json=None,
            error_message="COZE_WORKFLOW_ERROR: execute tool failed",
            created_at=now - timedelta(minutes=2),
            updated_at=now - timedelta(minutes=2),
        )
    )
    session.commit()

    report = build_eval_operations_health(session)

    assert report["status"] == "critical"
    assert report["recentRunTotal"] == 1
    assert report["recentSuccessCount"] == 0
    assert report["recentFailureCount"] == 1
    issue_codes = {item["code"] for item in report["issues"]}
    assert "EVAL_NO_RECENT_SUCCESS" in issue_codes
    assert "EVAL_RECENT_FAILURES" in issue_codes


def test_eval_operations_health_ignores_manual_patrol_abort_failures():
    session = _session()
    now = datetime.utcnow()
    session.add(_workflow())
    session.add(
        _run(
            id="patrol_abort",
            status="failed",
            result_image_urls_json=None,
            error_message="EVAL_PATROL_ABORTED: operator stopped the patrol",
            created_at=now - timedelta(minutes=2),
            updated_at=now - timedelta(minutes=2),
        )
    )
    session.commit()

    report = build_eval_operations_health(session)

    assert report["status"] == "healthy"
    assert report["issues"] == []
    assert report["recentFailures"] == []
    assert report["recentStatusCounts"]["failed"] == 1


def test_eval_operations_health_ignores_prompt_required_failures():
    session = _session()
    now = datetime.utcnow()
    session.add(_workflow())
    session.add(
        _run(
            id="prompt_missing",
            status="failed",
            result_image_urls_json=None,
            error_message="PROMPT_REQUIRED",
            created_at=now - timedelta(minutes=2),
            updated_at=now - timedelta(minutes=2),
        )
    )
    session.commit()

    report = build_eval_operations_health(session)

    assert report["status"] == "healthy"
    assert report["issues"] == []
    assert report["recentFailures"] == []
    assert report["recentStatusCounts"]["failed"] == 1


def test_eval_operations_health_warns_when_one_comfyui_executor_is_unreachable():
    session = _session()
    session.add(_workflow())
    session.add(_run(id="ok"))
    session.commit()

    report = build_eval_operations_health(
        session,
        comfyui_queue_summary={
            "totalCount": 3,
            "servers": [
                {"executorId": "executor_a", "supported": True, "queueMaxSize": 10},
                {"executorId": "executor_b", "supported": False, "message": "COMFYUI_QUEUE_STATUS_ERROR"},
            ]
        },
    )

    assert report["status"] == "warning"
    issue_codes = {item["code"] for item in report["issues"]}
    assert "COMFYUI_EXECUTOR_UNREACHABLE" in issue_codes
    assert report["concurrency"]["comfyuiAvailableExecutors"] == 1
    assert report["concurrency"]["comfyuiQueueCapacity"] == 10
    assert report["concurrency"]["comfyuiQueueTotal"] == 3
    assert report["concurrency"]["comfyuiQueueUtilization"] == 0.3


def test_eval_operations_health_is_critical_when_all_comfyui_executors_are_unreachable():
    session = _session()
    session.add(_workflow())
    session.add(_run(id="ok"))
    session.commit()

    report = build_eval_operations_health(
        session,
        comfyui_queue_summary={
            "servers": [
                {"executorId": "executor_a", "supported": False, "message": "COMFYUI_QUEUE_STATUS_ERROR"},
                {"executorId": "executor_b", "supported": False, "message": "COMFYUI_QUEUE_STATUS_ERROR"},
            ]
        },
    )

    assert report["status"] == "critical"
    issue_codes = {item["code"] for item in report["issues"]}
    assert "COMFYUI_NO_AVAILABLE_EXECUTOR" in issue_codes
