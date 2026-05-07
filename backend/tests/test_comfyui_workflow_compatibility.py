from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

import app.services.integration_test as integration_test_module
from app.core.db import Base
from app.models.integration import Ability, Executor, Workflow, WorkflowBinding
from app.services.integration_test import IntegrationTestService


def test_comfyui_graph_compatibility_reports_missing_node_and_model() -> None:
    graph = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "missing-model.safetensors"},
        },
        "2": {
            "class_type": "MissingCustomNode",
            "inputs": {},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "普通提示词不应该被当成模型文件"},
        },
    }
    object_info = {
        "UNETLoader": {
            "input": {"required": {"unet_name": [["present-model.safetensors"], {}]}},
        },
        "CLIPTextEncode": {
            "input": {"required": {"text": ["STRING", {"multiline": True}]}},
        },
    }

    result = IntegrationTestService._check_comfyui_graph_compatibility(graph, object_info)

    assert result["compatible"] is False
    assert result["missingNodes"] == [{"nodeId": "2", "classType": "MissingCustomNode"}]
    assert result["missingModels"] == [
        {
            "nodeId": "1",
            "classType": "UNETLoader",
            "inputName": "unet_name",
            "value": "missing-model.safetensors",
        }
    ]


def test_comfyui_graph_compatibility_ignores_runtime_image_and_method_choices() -> None:
    graph = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "__INPUT_IMAGE__"},
        },
        "2": {
            "class_type": "ColorMatch",
            "inputs": {"method": "__COLORMATCH_METHOD__"},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {},
        },
    }
    object_info = {
        "LoadImage": {
            "input": {"required": {"image": [["existing.png"], {}]}},
        },
        "ColorMatch": {
            "input": {"required": {"method": [["LAB", "HSV"], {}]}},
        },
        "SaveImage": {"input": {"required": {}}},
    }

    result = IntegrationTestService._check_comfyui_graph_compatibility(graph, object_info)

    assert result["compatible"] is True
    assert result["missingNodes"] == []
    assert result["missingModels"] == []


def test_comfyui_workflow_compatibility_checks_allowed_executors(monkeypatch) -> None:
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
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(integration_test_module, "get_session", fake_get_session)

    workflow_definition = {
        "workflow_key": "demo_workflow",
        "graph": {
            "1": {
                "class_type": "UNETLoader",
                "inputs": {"unet_name": "required-model.safetensors"},
            },
            "2": {"class_type": "SaveImage", "inputs": {}},
        },
    }
    with testing_session() as session:
        session.add_all(
            [
                Executor(
                    id="executor_a",
                    name="ComfyUI A",
                    type="comfyui",
                    base_url="http://a.example",
                    status="active",
                    max_concurrency=10,
                    config={"tags": ["comfyui-general"]},
                ),
                Executor(
                    id="executor_b",
                    name="ComfyUI B",
                    type="comfyui",
                    base_url="http://b.example",
                    status="active",
                    max_concurrency=10,
                    config={"tags": ["comfyui-general"]},
                ),
                Workflow(
                    id="workflow_demo",
                    action="image_fission",
                    name="演示工作流",
                    version="v1",
                    type="comfyui",
                    definition=workflow_definition,
                    status="active",
                    extra_metadata={"workflow_key": "demo_workflow"},
                ),
                WorkflowBinding(
                    id="binding_demo_a",
                    action="image_fission",
                    workflow_id="workflow_demo",
                    executor_id="executor_a",
                    priority=100,
                    enabled=True,
                    extra_metadata={},
                ),
                Ability(
                    id="comfyui_demo",
                    provider="comfyui",
                    category="image_generation",
                    capability_key="demo_workflow",
                    display_name="演示能力",
                    description="",
                    status="active",
                    ability_type="workflow",
                    workflow_id="workflow_demo",
                    default_params={"workflow_key": "demo_workflow"},
                    input_schema={},
                    extra_metadata={
                        "workflow_key": "demo_workflow",
                        "action": "image_fission",
                        "allowed_executor_ids": ["executor_a", "executor_b"],
                    },
                ),
            ]
        )
        session.commit()

    def fake_fetch_object_info(executor: Executor, *, timeout_seconds: float = 8.0):
        if executor.id == "executor_a":
            return executor.base_url, {
                "UNETLoader": {
                    "input": {"required": {"unet_name": [["required-model.safetensors"], {}]}},
                },
                "SaveImage": {"input": {"required": {}}},
            }
        return executor.base_url, {
            "UNETLoader": {
                "input": {"required": {"unet_name": [["other-model.safetensors"], {}]}},
            },
            "SaveImage": {"input": {"required": {}}},
        }

    service = IntegrationTestService()
    monkeypatch.setattr(service, "_fetch_comfyui_object_info", fake_fetch_object_info)

    result = service.get_comfyui_workflow_compatibility()

    assert result["totalWorkflows"] == 1
    assert result["warningCount"] == 1
    item = result["workflows"][0]
    assert item["status"] == "warning"
    assert item["compatibleExecutorIds"] == ["executor_a"]
    assert item["incompatibleExecutorIds"] == ["executor_b"]
    assert item["servers"][1]["missingModels"][0]["value"] == "required-model.safetensors"
    assert item["diagnostics"][0]["code"] == "COMFYUI_ROUTING_BINDING_MISMATCH"


def test_comfyui_workflow_compatibility_fails_when_graph_or_route_missing(monkeypatch) -> None:
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
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(integration_test_module, "get_session", fake_get_session)
    monkeypatch.setattr(
        integration_test_module,
        "load_comfy_workflow",
        lambda workflow_key: (_ for _ in ()).throw(FileNotFoundError(workflow_key)),
    )

    with testing_session() as session:
        session.add(
            Ability(
                id="comfyui_missing_graph",
                provider="comfyui",
                category="image_generation",
                capability_key="missing_graph",
                display_name="缺失工作流",
                description="",
                status="active",
                ability_type="workflow",
                workflow_id=None,
                default_params={"workflow_key": "missing_graph"},
                input_schema={},
                extra_metadata={"workflow_key": "missing_graph", "action": "image_fission"},
            )
        )
        session.commit()

    result = IntegrationTestService().get_comfyui_workflow_compatibility()

    assert result["failedCount"] == 1
    item = result["workflows"][0]
    assert item["status"] == "failed"
    assert [diag["code"] for diag in item["diagnostics"]] == [
        "COMFYUI_WORKFLOW_GRAPH_MISSING",
        "COMFYUI_NO_ROUTED_EXECUTOR",
    ]


def test_comfyui_workflow_compatibility_keeps_partial_result_when_executor_unreachable(monkeypatch) -> None:
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
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(integration_test_module, "get_session", fake_get_session)

    with testing_session() as session:
        session.add_all(
            [
                Executor(
                    id="executor_down",
                    name="ComfyUI Down",
                    type="comfyui",
                    base_url="http://down.example",
                    status="active",
                    max_concurrency=10,
                    config={"tags": ["comfyui-general"]},
                ),
                Workflow(
                    id="workflow_demo",
                    action="image_fission",
                    name="演示工作流",
                    version="v1",
                    type="comfyui",
                    definition={"workflow_key": "demo_workflow", "graph": {"1": {"class_type": "SaveImage", "inputs": {}}}},
                    status="active",
                    extra_metadata={"workflow_key": "demo_workflow"},
                ),
                WorkflowBinding(
                    id="binding_demo_down",
                    action="image_fission",
                    workflow_id="workflow_demo",
                    executor_id="executor_down",
                    priority=100,
                    enabled=True,
                    extra_metadata={},
                ),
                Ability(
                    id="comfyui_demo_down",
                    provider="comfyui",
                    category="image_generation",
                    capability_key="demo_workflow",
                    display_name="演示能力",
                    description="",
                    status="active",
                    ability_type="workflow",
                    workflow_id="workflow_demo",
                    default_params={"workflow_key": "demo_workflow"},
                    input_schema={},
                    extra_metadata={"workflow_key": "demo_workflow", "action": "image_fission"},
                ),
            ]
        )
        session.commit()

    service = IntegrationTestService()
    monkeypatch.setattr(
        service,
        "_fetch_comfyui_object_info",
        lambda executor, *, timeout_seconds=8.0: (_ for _ in ()).throw(
            HTTPException(status_code=502, detail="COMFYUI_OBJECT_INFO_ERROR")
        ),
    )

    result = service.get_comfyui_workflow_compatibility()

    assert result["failedCount"] == 1
    assert result["servers"] == [
        {
            "executorId": "executor_down",
            "executorName": "ComfyUI Down",
            "baseUrl": "http://down.example",
            "status": "active",
            "reachable": False,
            "nodeCount": None,
            "message": "COMFYUI_OBJECT_INFO_ERROR",
        }
    ]
    item = result["workflows"][0]
    assert item["status"] == "failed"
    assert item["servers"][0]["reachable"] is False
    assert item["servers"][0]["message"] == "执行节点不可访问或 object_info 读取失败"
