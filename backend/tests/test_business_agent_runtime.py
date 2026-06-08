from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.business_agents as business_agents_module
from app.core.db import Base
from app.models.integration import BusinessAgentMessage, BusinessAgentPlan, BusinessAgentSession, BusinessAgentToolCall, BusinessRun
from app.models.user import User
from app.schemas.business import (
    BusinessAgentConfirmRequest,
    BusinessAgentMessageRequest,
    BusinessAgentSessionCreateRequest,
)
from app.services.business_agents import BusinessAgentService
from app.services.business_runs import BusinessRunService


def _install_agent_db(monkeypatch):
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

    monkeypatch.setattr(business_agents_module, "get_session", fake_get_session)
    monkeypatch.setattr(
        business_agents_module,
        "get_settings",
        lambda: SimpleNamespace(
            business_agent_planner_enabled=False,
            business_agent_openai_api_key=None,
            business_agent_openai_base_url="https://api.openai.com",
            business_agent_planner_model="gpt-5.5",
            business_agent_planner_timeout_seconds=30,
        ),
    )
    return testing_session


def _client_user() -> User:
    return User(
        id="business-api-key:test-agent",
        email="agent@example.com",
        username="Agent Tester",
        password_hash="",
        role="client",
        status="active",
        tenant_id="tenant-a",
        client_id="eval",
    )


def test_image_edit_agent_generates_plan_without_running_tool(monkeypatch) -> None:
    testing_session = _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()

    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="把这张图改得更高级一些，适合连衣裙面料。",
            source="eval",
        ),
        user=user,
    )

    assert result["session"]["status"] == "awaiting_confirmation"
    assert result["plan"]["toolName"] == "business.image_edit"
    assert result["plan"]["status"] == "awaiting_confirmation"
    assert result["plan"]["toolPayload"]["imageUrl"].endswith("/source.png")
    assert result["plan"]["toolPayload"]["editSkill"] == "local_modify"
    assert result["plan"]["routeEvidence"]["targetAbility"] == "business.image_edit"
    assert result["plan"]["routeEvidence"]["baseImageRole"] == "source_image"
    assert result["plan"]["routeEvidence"]["confidence"] >= 0.65
    assert result["plan"]["workingMemory"]["activeSkill"] == "local_modify"
    assert result["plan"]["assetState"]["currentBaseImageUrl"].endswith("/source.png")
    assert result["plan"]["methodology"]["id"] == "image_edit_chat_mvp"

    with testing_session() as session:
        db_session = session.get(BusinessAgentSession, result["session"]["id"])
        plans = session.execute(select(BusinessAgentPlan)).scalars().all()
        tool_calls = session.execute(select(BusinessAgentToolCall)).scalars().all()
    assert db_session.user_id is None
    assert db_session.user_name == "Agent Tester"
    assert len(plans) == 1
    assert tool_calls == []


def test_image_agent_uses_image2_quality_first_for_pattern_extract_by_default(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()

    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/tablecloth.png",
            message="把这个桌布的花纹提取出来",
            source="eval",
        ),
        user=user,
    )

    plan = result["plan"]
    evidence = plan["routeEvidence"]
    assert plan["intent"] == "image_edit"
    assert plan["toolName"] == "business.image_edit"
    assert plan["toolPayload"]["imageUrl"].endswith("/tablecloth.png")
    assert plan["toolPayload"]["instruction"]
    assert plan["toolPayload"]["editSkill"] == "local_modify"
    assert evidence["routeType"] == "image2_quality_first"
    assert evidence["targetAbility"] == "business.image_edit"
    assert evidence["targetBusinessKey"] == "image_edit"
    assert evidence["primaryExecutionEngine"] == "gpt-image-2"
    assert evidence["specializedAbilityCandidate"]["targetAbility"] == "business.pattern_extract"
    assert evidence["requiresClarification"] is False


def test_image_agent_routes_explicit_batch_pattern_extract_to_specialized_ability(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()

    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/tablecloth.png",
            message="批量快速把这个桌布的花纹提取出来，走花纹提取能力",
            source="eval",
        ),
        user=user,
    )

    plan = result["plan"]
    evidence = plan["routeEvidence"]
    assert plan["intent"] == "pattern_extract"
    assert plan["toolName"] == "business.pattern_extract"
    assert plan["toolPayload"]["imageUrl"].endswith("/tablecloth.png")
    assert plan["toolPayload"]["prompt"]
    assert "editSkill" not in plan["toolPayload"]
    assert evidence["routeType"] == "ability_accelerated"
    assert evidence["targetAbility"] == "business.pattern_extract"
    assert evidence["targetBusinessKey"] == "pattern_extract"
    assert evidence["primaryExecutionEngine"] == "podi-specialized-ability"
    assert evidence["requiresClarification"] is False


def test_image_agent_backend_overrides_model_pattern_extract_to_image2_quality_default(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()

    def fake_generate_plan(*, message, image_url, request_context, session_context):  # noqa: ANN001, ARG001
        return {
            "intent": "pattern_extract",
            "title": "模型误判测试",
            "summary": "模型误判成专项花纹提取。",
            "editPlan": [{"step": "错误路由", "reason": "测试后端覆盖。"}],
            "toolPayload": {
                "imageUrl": image_url,
                "prompt": message,
                "batch": 1,
                "quality": "preview",
                "size": "auto",
                "output_format": "png",
            },
            "estimatedCostLevel": "low",
            "riskLevel": "low",
            "routeEvidence": {
                "intent": "pattern_extract",
                "routeType": "ability_accelerated",
                "targetAbility": "business.pattern_extract",
                "targetBusinessKey": "pattern_extract",
                "confidence": 0.91,
                "threshold": 0.65,
                "missingFields": [],
                "routeReason": "模型误判为专项花纹提取。",
                "rejectedAbilities": [],
                "requiresClarification": False,
            },
            "warnings": [],
            "plannerMode": "test",
            "plannerModel": "test-planner",
            "rawResponse": {"test": True},
        }

    monkeypatch.setattr(service.planner, "generate_plan", fake_generate_plan)
    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/tablecloth.png",
            message="把这个桌布的花纹提取出来",
            source="eval",
        ),
        user=user,
    )

    plan = result["plan"]
    assert plan["intent"] == "image_edit"
    assert plan["toolName"] == "business.image_edit"
    assert plan["toolPayload"]["instruction"] == "把这个桌布的花纹提取出来"
    assert plan["toolPayload"]["editSkill"] == "local_modify"
    assert plan["routeEvidence"]["routeType"] == "image2_quality_first"
    assert plan["routeEvidence"]["targetAbility"] == "business.image_edit"
    assert plan["routeEvidence"]["targetBusinessKey"] == "image_edit"
    assert plan["routeEvidence"]["specializedAbilityCandidate"]["targetAbility"] == "business.pattern_extract"


def test_image_agent_quality_first_pattern_confirm_submits_image_edit_run(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    captured: dict[str, object] = {}

    def fake_create_run(*, business_key, payload, user, source):  # noqa: ANN001, ARG001
        captured["business_key"] = business_key
        captured["payload"] = payload
        captured["source"] = source
        return SimpleNamespace(id="run_image2_pattern_agent", business_key=business_key, status="queued")

    monkeypatch.setattr(
        business_agents_module,
        "get_business_run_service",
        lambda: SimpleNamespace(create_run=fake_create_run),
    )
    service = BusinessAgentService()
    user = _client_user()
    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/tablecloth.png",
            message="把这个桌布的花纹提取出来",
        ),
        user=user,
    )

    confirmed = service.confirm_plan(
        result["session"]["id"],
        result["plan"]["id"],
        BusinessAgentConfirmRequest(),
        user=user,
    )

    assert captured["business_key"] == "image_edit"
    assert captured["source"] == "image-edit-chat"
    payload = captured["payload"]
    assert payload.imageUrl.endswith("/tablecloth.png")
    assert payload.instruction
    assert payload.editSkill == "local_modify"
    assert payload.prompt is None
    assert payload.batch is None
    assert payload.flowStepKey == "image_edit_chat"
    assert payload.metadata["agentRouteEvidence"]["routeType"] == "image2_quality_first"
    assert payload.metadata["agentRouteEvidence"]["specializedAbilityCandidate"]["targetAbility"] == "business.pattern_extract"
    assert confirmed["tool_call"]["businessKey"] == "image_edit"
    assert confirmed["run"]["businessKey"] == "image_edit"


def test_image_agent_pattern_extract_confirm_submits_pattern_run(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    captured: dict[str, object] = {}

    def fake_create_run(*, business_key, payload, user, source):  # noqa: ANN001, ARG001
        captured["business_key"] = business_key
        captured["payload"] = payload
        captured["source"] = source
        return SimpleNamespace(id="run_pattern_agent", business_key=business_key, status="queued")

    monkeypatch.setattr(
        business_agents_module,
        "get_business_run_service",
        lambda: SimpleNamespace(create_run=fake_create_run),
    )
    service = BusinessAgentService()
    user = _client_user()
    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/tablecloth.png",
            message="批量快速把这个桌布的花纹提取出来，走花纹提取能力",
        ),
        user=user,
    )

    confirmed = service.confirm_plan(
        result["session"]["id"],
        result["plan"]["id"],
        BusinessAgentConfirmRequest(),
        user=user,
    )

    assert captured["business_key"] == "pattern_extract"
    assert captured["source"] == "image-edit-chat"
    payload = captured["payload"]
    assert payload.imageUrl.endswith("/tablecloth.png")
    assert payload.prompt
    assert payload.flowStepKey == "pattern_extract_chat"
    assert confirmed["tool_call"]["businessKey"] == "pattern_extract"
    assert confirmed["run"]["businessKey"] == "pattern_extract"


def test_image_edit_agent_create_session_reuses_request_id(monkeypatch) -> None:
    testing_session = _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()
    payload = BusinessAgentSessionCreateRequest(
        imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
        message="把这张图改得更高级一些，适合连衣裙面料。",
        requestId="agent-session-request-1",
        source="eval",
    )

    first = service.create_session(payload, user=user)
    second = service.create_session(payload, user=user)

    assert second["session"]["id"] == first["session"]["id"]
    assert second["plan"]["id"] == first["plan"]["id"]
    with testing_session() as session:
        sessions = session.execute(select(BusinessAgentSession)).scalars().all()
        plans = session.execute(select(BusinessAgentPlan)).scalars().all()
    assert len(sessions) == 1
    assert len(plans) == 1


def test_image_edit_agent_create_session_uses_initial_editor_context(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()

    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="把框选区域的污点去掉。",
            editSkill="remove_inpaint",
            quality="production",
            size="1024x1024",
            outputFormat="webp",
            maskUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/mask.png",
            selectionHints=[{"type": "rect", "x": 10, "y": 20, "width": 120, "height": 90}],
        ),
        user=user,
    )

    tool_payload = result["plan"]["toolPayload"]
    assert tool_payload["editSkill"] == "remove_inpaint"
    assert tool_payload["quality"] == "production"
    assert tool_payload["size"] == "1024x1024"
    assert tool_payload["output_format"] == "webp"
    assert tool_payload["maskUrl"].endswith("/mask.png")
    assert tool_payload["selectionHints"] == [{"type": "rect", "x": 10, "y": 20, "width": 120, "height": 90}]


def test_image_edit_agent_confirm_submits_business_run(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    fake_run_service = SimpleNamespace(last_payload=None)

    def fake_create_run(*, business_key, payload, user, source):  # noqa: ANN001
        fake_run_service.last_payload = payload
        assert business_key == "image_edit"
        assert source == "image-edit-chat"
        assert user.username == "Agent Tester"
        return SimpleNamespace(
            id="run_agent_confirmed",
            business_key="image_edit",
            status="queued",
            version="gpt-image2-editor-v1",
            trace_id=payload.traceId,
            request_id=payload.requestId,
        )

    monkeypatch.setattr(
        business_agents_module,
        "get_business_run_service",
        lambda: SimpleNamespace(create_run=fake_create_run),
    )
    service = BusinessAgentService()
    user = _client_user()
    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="自然提升质感，背景不要乱改。",
        ),
        user=user,
    )

    confirmed = service.confirm_plan(
        result["session"]["id"],
        result["plan"]["id"],
        BusinessAgentConfirmRequest(),
        user=user,
    )

    assert confirmed["run"]["runId"] == "run_agent_confirmed"
    assert confirmed["session"]["status"] == "running"
    assert confirmed["tool_call"]["status"] == "submitted"
    assert fake_run_service.last_payload.imageUrl.endswith("/source.png")
    assert fake_run_service.last_payload.metadata["agentPlanId"] == result["plan"]["id"]
    assert fake_run_service.last_payload.metadata["agentRouteEvidence"]["targetAbility"] == "business.image_edit"
    assert fake_run_service.last_payload.metadata["agentBaseImageRole"] == "source_image"
    assert fake_run_service.last_payload.metadata["agentMethodologyId"] == "image_edit_chat_mvp"


def test_image_edit_agent_next_message_uses_previous_successful_output(monkeypatch) -> None:
    testing_session = _install_agent_db(monkeypatch)

    def fake_create_run(*, business_key, payload, user, source):  # noqa: ANN001, ARG001
        return SimpleNamespace(
            id="run_agent_first",
            business_key="image_edit",
            status="queued",
            version="gpt-image2-editor-v1",
            trace_id=payload.traceId,
            request_id=payload.requestId,
        )

    monkeypatch.setattr(
        business_agents_module,
        "get_business_run_service",
        lambda: SimpleNamespace(create_run=fake_create_run),
    )
    service = BusinessAgentService()
    user = _client_user()
    first = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="把这张图改得更高级一些，适合连衣裙面料。",
        ),
        user=user,
    )
    service.confirm_plan(
        first["session"]["id"],
        first["plan"]["id"],
        BusinessAgentConfirmRequest(),
        user=user,
    )
    with testing_session() as session:
        session.add(
            BusinessRun(
                id="run_agent_first",
                business_key="image_edit",
                status="succeeded",
                source="image-edit-chat",
                image_urls=["https://podi.oss-cn-hangzhou.aliyuncs.com/generated.png"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        session.commit()

    second = service.send_message(
        first["session"]["id"],
        BusinessAgentMessageRequest(message="继续基于刚才生成的结果，把颜色压低一点。"),
        user=user,
    )

    assert second["plan"]["toolPayload"]["imageUrl"].endswith("/generated.png")
    assert second["plan"]["routeEvidence"]["baseImageRole"] == "previous_result"
    assert second["plan"]["routeEvidence"]["parentRunId"] == "run_agent_first"
    assert second["plan"]["assetState"]["sourceImageUrl"].endswith("/source.png")
    assert second["plan"]["assetState"]["currentBaseImageUrl"].endswith("/generated.png")
    assert second["plan"]["workingMemory"]["baseImageRole"] == "previous_result"


def test_image_edit_agent_confirm_is_idempotent_for_executed_plan(monkeypatch) -> None:
    testing_session = _install_agent_db(monkeypatch)
    fake_run_service = SimpleNamespace(call_count=0)

    def fake_create_run(*, business_key, payload, user, source):  # noqa: ANN001, ARG001
        fake_run_service.call_count += 1
        return SimpleNamespace(
            id="run_agent_idempotent",
            business_key="image_edit",
            status="queued",
            version="gpt-image2-editor-v1",
            trace_id=payload.traceId,
            request_id=payload.requestId,
        )

    monkeypatch.setattr(
        business_agents_module,
        "get_business_run_service",
        lambda: SimpleNamespace(create_run=fake_create_run),
    )
    service = BusinessAgentService()
    user = _client_user()
    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="自然提升质感，背景不要乱改。",
        ),
        user=user,
    )

    first = service.confirm_plan(result["session"]["id"], result["plan"]["id"], BusinessAgentConfirmRequest(), user=user)
    second = service.confirm_plan(result["session"]["id"], result["plan"]["id"], BusinessAgentConfirmRequest(), user=user)

    assert first["run"]["runId"] == "run_agent_idempotent"
    assert second["run"]["runId"] == "run_agent_idempotent"
    assert fake_run_service.call_count == 1
    with testing_session() as session:
        tool_calls = session.execute(select(BusinessAgentToolCall)).scalars().all()
    assert len(tool_calls) == 1


def test_image_edit_agent_confirm_latest_plan_for_chat_endpoint(monkeypatch) -> None:
    _install_agent_db(monkeypatch)

    def fake_create_run(*, business_key, payload, user, source):  # noqa: ANN001, ARG001
        return {
            "runId": "run_chat_confirm_latest",
            "businessKey": business_key,
            "status": "queued",
            "version": "gpt-image2-editor-v1",
            "traceId": payload.traceId,
            "requestId": payload.requestId,
        }

    monkeypatch.setattr(
        business_agents_module,
        "get_business_run_service",
        lambda: SimpleNamespace(create_run=fake_create_run),
    )
    service = BusinessAgentService()
    user = _client_user()
    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="把这张图改成更干净的商品图。",
        ),
        user=user,
    )

    confirmed = service.confirm_latest_plan(
        result["session"]["id"],
        BusinessAgentConfirmRequest(),
        user=user,
    )

    assert confirmed["plan"]["id"] == result["plan"]["id"]
    assert confirmed["run"]["runId"] == "run_chat_confirm_latest"
    assert confirmed["tool_call"]["businessKey"] == "image_edit"


def test_image_edit_agent_confirm_latest_requires_plan(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()
    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
        ),
        user=user,
    )

    with pytest.raises(HTTPException) as exc:
        service.confirm_latest_plan(result["session"]["id"], BusinessAgentConfirmRequest(), user=user)

    assert exc.value.status_code == 400
    assert exc.value.detail == "AGENT_PLAN_REQUIRED"


def test_image_edit_agent_business_run_detail_includes_agent_trace(monkeypatch) -> None:
    testing_session = _install_agent_db(monkeypatch)

    def fake_create_run(*, business_key, payload, user, source):  # noqa: ANN001, ARG001
        return SimpleNamespace(
            id="run_agent_trace",
            business_key="image_edit",
            status="queued",
            version="gpt-image2-editor-v1",
            trace_id=payload.traceId,
            request_id=payload.requestId,
        )

    monkeypatch.setattr(
        business_agents_module,
        "get_business_run_service",
        lambda: SimpleNamespace(create_run=fake_create_run),
    )
    service = BusinessAgentService()
    user = _client_user()
    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="自然提升质感，背景不要乱改。",
            requestId="agent-run-trace-session",
        ),
        user=user,
    )
    confirmed = service.confirm_plan(
        result["session"]["id"],
        result["plan"]["id"],
        BusinessAgentConfirmRequest(requestId="agent-run-trace-confirm"),
        user=user,
    )

    with testing_session() as session:
        now = datetime.utcnow()
        session.add(
            BusinessRun(
                id=confirmed["run"]["runId"],
                business_key="image_edit",
                version="gpt-image2-editor-v1",
                status="queued",
                source="image-edit-chat",
                channel="image-edit-chat",
                trace_id=confirmed["run"]["traceId"],
                request_id=confirmed["run"]["requestId"],
                request_payload={"metadata": {"agentSessionId": result["session"]["id"], "agentPlanId": result["plan"]["id"]}},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        row = session.get(BusinessRun, confirmed["run"]["runId"])
        detail = object.__new__(BusinessRunService)._run_to_dict(row, session=session)

    trace = detail["agent_trace"]
    assert trace["source"] == "image-edit-chat"
    assert trace["sessionId"] == result["session"]["id"]
    assert trace["planId"] == result["plan"]["id"]
    assert trace["toolCallStatus"] == "submitted"
    assert trace["runId"] == "run_agent_trace"
    assert trace["instruction"]


def test_image_edit_agent_rejects_stale_plan_confirmation(monkeypatch) -> None:
    testing_session = _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()
    first = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="做一个轻量质感优化。",
        ),
        user=user,
    )
    second = service.send_message(
        first["session"]["id"],
        BusinessAgentMessageRequest(message="不要改背景，只提升布料质感。"),
        user=user,
    )

    with pytest.raises(HTTPException) as exc:
        service.confirm_plan(first["session"]["id"], first["plan"]["id"], BusinessAgentConfirmRequest(), user=user)

    assert exc.value.detail == "AGENT_PLAN_STALE"
    assert second["plan"]["id"] != first["plan"]["id"]
    with testing_session() as session:
        tool_calls = session.execute(select(BusinessAgentToolCall)).scalars().all()
    assert tool_calls == []


def test_image_edit_agent_message_request_id_is_idempotent(monkeypatch) -> None:
    testing_session = _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()
    session_result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
        ),
        user=user,
    )
    payload = BusinessAgentMessageRequest(
        message="只提升花朵纹理质感，背景不要改。",
        requestId="agent-message-request-1",
    )

    first = service.send_message(session_result["session"]["id"], payload, user=user)
    second = service.send_message(session_result["session"]["id"], payload, user=user)

    assert second["plan"]["id"] == first["plan"]["id"]
    assert second["session"]["latestPlanId"] == first["plan"]["id"]
    with testing_session() as session:
        messages = session.execute(select(BusinessAgentMessage)).scalars().all()
        plans = session.execute(select(BusinessAgentPlan)).scalars().all()

    assert len(plans) == 1
    assert [item.role for item in messages] == ["user", "assistant"]
    assert messages[0].request_id == "agent-message-request-1"
    assert messages[0].plan_id == first["plan"]["id"]


def test_image_edit_agent_message_request_id_is_scoped_to_session(monkeypatch) -> None:
    testing_session = _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()
    first_session = service.create_session(
        BusinessAgentSessionCreateRequest(imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source-a.png"),
        user=user,
    )
    second_session = service.create_session(
        BusinessAgentSessionCreateRequest(imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source-b.png"),
        user=user,
    )

    first = service.send_message(
        first_session["session"]["id"],
        BusinessAgentMessageRequest(message="做轻量高级感优化。", requestId="shared-message-request"),
        user=user,
    )
    second = service.send_message(
        second_session["session"]["id"],
        BusinessAgentMessageRequest(message="做轻量高级感优化。", requestId="shared-message-request"),
        user=user,
    )

    assert second["session"]["id"] != first["session"]["id"]
    assert second["plan"]["id"] != first["plan"]["id"]
    assert second["plan"]["toolPayload"]["imageUrl"].endswith("/source-b.png")
    with testing_session() as session:
        messages = session.execute(select(BusinessAgentMessage)).scalars().all()
        plans = session.execute(select(BusinessAgentPlan)).scalars().all()

    assert len(plans) == 2
    assert len([item for item in messages if item.role == "user" and item.request_id == "shared-message-request"]) == 2


@pytest.mark.parametrize(
    ("message", "extra_payload", "expected_skill", "requires_clarification"),
    [
        (
            "自然提升布料质感，适合服装面料，背景不要乱改。",
            {},
            "local_modify",
            False,
        ),
        (
            "把画面左右自然外扩，延续原来的花纹密度和光照。",
            {},
            "canvas_outpaint",
            False,
        ),
        (
            "去掉框选区域里的水印和杂点。",
            {"selectionHints": [{"type": "rect", "x": 12, "y": 18, "width": 80, "height": 60}]},
            "remove_inpaint",
            False,
        ),
        (
            "参考这张配色图，把花朵颜色调整得更柔和。",
            {"referenceImages": [{"url": "https://podi.oss-cn-hangzhou.aliyuncs.com/reference.png"}]},
            "color_reference_correction",
            False,
        ),
        (
            "改一下",
            {},
            "local_modify",
            True,
        ),
    ],
)
def test_image_edit_agent_rule_planner_golden_cases_are_stable(
    monkeypatch,
    message: str,
    extra_payload: dict[str, object],
    expected_skill: str,
    requires_clarification: bool,
) -> None:
    _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()

    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message=message,
            requestId=f"golden-{expected_skill}-{str(requires_clarification).lower()}",
            **extra_payload,
        ),
        user=user,
    )

    evidence = result["plan"]["routeEvidence"]
    assert result["plan"]["toolPayload"]["editSkill"] == expected_skill
    assert evidence["targetAbility"] == "business.image_edit"
    assert evidence["baseImageRole"] == "source_image"
    assert evidence["requiresClarification"] is requires_clarification
    if requires_clarification:
        assert "editGoal" in evidence["missingFields"]
    else:
        assert evidence["confidence"] >= evidence["threshold"]


def test_image_edit_agent_second_turn_records_previous_result_context(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()
    first = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="把这张图改得更高级一些，适合连衣裙面料。",
        ),
        user=user,
    )

    second = service.send_message(
        first["session"]["id"],
        BusinessAgentMessageRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/generated.png",
            message="第二轮让颜色更清爽，其他保持上一轮效果。",
            context={"baseImageRole": "previous_result", "previousRunId": "run_first_round"},
        ),
        user=user,
    )

    evidence = second["plan"]["routeEvidence"]
    assert second["plan"]["toolPayload"]["imageUrl"].endswith("/generated.png")
    assert evidence["baseImageRole"] == "previous_result"
    assert evidence["parentRunId"] == "run_first_round"
    assert evidence["targetAbility"] == "business.image_edit"
    assert second["plan"]["assetState"]["currentBaseImageRole"] == "previous_result"
    assert second["session"]["context"]["assetState"]["parentRunId"] == "run_first_round"


def test_image_edit_agent_vague_plan_requires_clarification(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    fake_run_service = SimpleNamespace(call_count=0)

    def fake_create_run(*, business_key, payload, user, source):  # noqa: ANN001, ARG001
        fake_run_service.call_count += 1
        return SimpleNamespace(id="should_not_run", business_key="image_edit", status="queued")

    monkeypatch.setattr(
        business_agents_module,
        "get_business_run_service",
        lambda: SimpleNamespace(create_run=fake_create_run),
    )
    service = BusinessAgentService()
    user = _client_user()
    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="改一下",
        ),
        user=user,
    )

    assert result["plan"]["routeEvidence"]["requiresClarification"] is True
    assert "editGoal" in result["plan"]["routeEvidence"]["missingFields"]
    with pytest.raises(HTTPException) as exc:
        service.confirm_plan(result["session"]["id"], result["plan"]["id"], BusinessAgentConfirmRequest(), user=user)

    assert exc.value.status_code == 409
    assert exc.value.detail == "AGENT_PLAN_REQUIRES_CLARIFICATION"
    assert fake_run_service.call_count == 0


def test_image_edit_agent_low_confidence_plan_requires_clarification(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    fake_run_service = SimpleNamespace(call_count=0)

    def fake_create_run(*, business_key, payload, user, source):  # noqa: ANN001, ARG001
        fake_run_service.call_count += 1
        return SimpleNamespace(id="should_not_run", business_key="image_edit", status="queued")

    monkeypatch.setattr(
        business_agents_module,
        "get_business_run_service",
        lambda: SimpleNamespace(create_run=fake_create_run),
    )
    service = BusinessAgentService()

    def fake_generate_plan(*, message, image_url, request_context, session_context):  # noqa: ANN001, ARG001
        return {
            "intent": "image_edit",
            "title": "低置信度测试计划",
            "summary": "用户目标不够明确。",
            "editPlan": [{"step": "追问目标", "reason": "缺少明确改图目标。"}],
            "toolPayload": {
                "imageUrl": image_url,
                "editSkill": "local_modify",
                "instruction": "保持主体结构，等待用户补充明确目标。",
            },
            "estimatedCostLevel": "low",
            "riskLevel": "low",
            "routeEvidence": {
                "confidence": 0.42,
                "threshold": 0.65,
                "missingFields": ["editGoal"],
                "routeReason": "用户只说要调整，但没有说明目标。",
                "requiresClarification": False,
                "clarificationReasons": [],
            },
            "warnings": [],
            "plannerMode": "test",
            "plannerModel": "test-planner",
            "rawResponse": {"test": True},
        }

    monkeypatch.setattr(service.planner, "generate_plan", fake_generate_plan)
    user = _client_user()
    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="帮我做一下",
        ),
        user=user,
    )

    evidence = result["plan"]["routeEvidence"]
    assert evidence["requiresClarification"] is True
    assert "missing_required_fields" in evidence["clarificationReasons"]
    assert "low_route_confidence" in evidence["clarificationReasons"]
    with pytest.raises(HTTPException) as exc:
        service.confirm_plan(result["session"]["id"], result["plan"]["id"], BusinessAgentConfirmRequest(), user=user)

    assert exc.value.status_code == 409
    assert exc.value.detail == "AGENT_PLAN_REQUIRES_CLARIFICATION"
    assert fake_run_service.call_count == 0


def test_image_edit_agent_confirm_marks_failed_when_business_run_fails(monkeypatch) -> None:
    testing_session = _install_agent_db(monkeypatch)

    def fake_create_run(*, business_key, payload, user, source):  # noqa: ANN001, ARG001
        raise HTTPException(status_code=502, detail="IMAGE_EDIT_PROVIDER_TIMEOUT")

    monkeypatch.setattr(
        business_agents_module,
        "get_business_run_service",
        lambda: SimpleNamespace(create_run=fake_create_run),
    )
    service = BusinessAgentService()
    user = _client_user()
    result = service.create_session(
        BusinessAgentSessionCreateRequest(
            imageUrl="https://podi.oss-cn-hangzhou.aliyuncs.com/source.png",
            message="把背景轻微扩出去。",
        ),
        user=user,
    )

    with pytest.raises(HTTPException) as exc:
        service.confirm_plan(
            result["session"]["id"],
            result["plan"]["id"],
            BusinessAgentConfirmRequest(),
            user=user,
        )

    assert exc.value.detail == "IMAGE_EDIT_PROVIDER_TIMEOUT"
    with testing_session() as session:
        db_session = session.get(BusinessAgentSession, result["session"]["id"])
        db_plan = session.get(BusinessAgentPlan, result["plan"]["id"])
        db_tool_call = session.execute(select(BusinessAgentToolCall)).scalar_one()

    assert db_session.status == "failed"
    assert db_plan.status == "failed"
    assert db_plan.error_code == "IMAGE_EDIT_PROVIDER_TIMEOUT"
    assert db_tool_call.status == "failed"
    assert db_tool_call.error_code == "IMAGE_EDIT_PROVIDER_TIMEOUT"


def test_image_edit_agent_confirm_requires_image(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()
    result = service.create_session(
        BusinessAgentSessionCreateRequest(message="帮我去掉瑕疵。"),
        user=user,
    )

    with pytest.raises(HTTPException) as exc:
        service.confirm_plan(result["session"]["id"], result["plan"]["id"], BusinessAgentConfirmRequest(), user=user)
    assert exc.value.detail == "AGENT_IMAGE_URL_REQUIRED"


def test_image_edit_agent_rejects_empty_message(monkeypatch) -> None:
    _install_agent_db(monkeypatch)
    service = BusinessAgentService()
    user = _client_user()
    result = service.create_session(BusinessAgentSessionCreateRequest(), user=user)

    with pytest.raises(HTTPException) as exc:
        service.send_message(result["session"]["id"], BusinessAgentMessageRequest(message="  "), user=user)
    assert exc.value.detail == "AGENT_MESSAGE_REQUIRED"
