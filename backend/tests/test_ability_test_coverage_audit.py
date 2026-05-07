from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.db import Base
from app.models.integration import Ability, Executor, VendorModelCatalog
from app.models.user import User  # noqa: F401 - register FK tables
from scripts.audit_ability_test_coverage import build_audit_report


def _schema() -> dict:
    return {"fields": [{"name": "url", "type": "image", "label": "图片 URL Image URL"}]}


def _add_general_comfyui_executors(session: Session) -> None:
    session.add_all(
        [
            Executor(
                id="executor_comfyui_pattern_extract_158",
                name="ComfyUI 5090 · 158 · 117.50.80.158",
                type="comfyui",
                base_url="http://117.50.80.158:8079",
                status="active",
                weight=1,
                max_concurrency=10,
                config={"tags": ["comfyui-general", "gpu:5090", "host:158"]},
            ),
            Executor(
                id="executor_comfyui_seamless_117",
                name="ComfyUI 4090 · 233 · 117.50.216.233",
                type="comfyui",
                base_url="http://117.50.216.233:8079",
                status="active",
                weight=1,
                max_concurrency=10,
                config={"tags": ["comfyui-general", "gpu:4090", "host:233"]},
            ),
        ]
    )


def _add_comfyui_ability(session: Session, allowed_executor_ids: list[str]) -> None:
    session.add(
        Ability(
            id="comfyui_yinhua_tiqu",
            provider="comfyui",
            category="image_generation",
            capability_key="yinhua_tiqu",
            display_name="印花提取",
            description="test",
            status="active",
            ability_type="comfyui",
            default_params={},
            input_schema=_schema(),
            extra_metadata={
                "api_type": "comfyui_workflow",
                "routing_policy": "queue",
                "allowed_executor_ids": allowed_executor_ids,
            },
        )
    )


def test_audit_flags_comfyui_ability_locked_to_single_node() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _add_general_comfyui_executors(session)
        _add_comfyui_ability(session, ["executor_comfyui_pattern_extract_158"])
        session.commit()

        report = build_audit_report(session)

    codes = {issue["code"] for issue in report["issues"]}
    assert "COMFYUI_ROUTE_SINGLE_NODE" in codes


def test_audit_accepts_comfyui_ability_with_two_general_nodes() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _add_general_comfyui_executors(session)
        _add_comfyui_ability(
            session,
            ["executor_comfyui_pattern_extract_158", "executor_comfyui_seamless_117"],
        )
        session.commit()

        report = build_audit_report(session)

    codes = {issue["code"] for issue in report["issues"]}
    assert "COMFYUI_ROUTE_SINGLE_NODE" not in codes
    assert report["summary"]["issueCount"] == 0


def test_audit_flags_active_mock_executor() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Executor(
                id="executor_mock_history_history_success_no_images_62359",
                name="mock-history-history_success_no_images",
                type="comfyui",
                base_url="http://127.0.0.1:62359",
                status="active",
                weight=1,
                max_concurrency=1,
                config={},
            )
        )
        session.commit()

        report = build_audit_report(session)

    codes = {issue["code"] for issue in report["issues"]}
    assert "ACTIVE_MOCK_EXECUTOR" in codes


def test_audit_flags_active_vendor_ability_without_model_acceptance() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        model = VendorModelCatalog(
            provider="openai",
            model="gpt-image-2",
            display_name="GPT Image 2",
            status="active",
            api_types=["image_edit"],
            execution_modes=["sync_then_store"],
            supports_mask=True,
            supports_multiple_images=True,
            supports_text=True,
            requires_global_egress=True,
            cost_policy={"unitPrice": 0.2, "billingUnit": "image"},
            source="test",
        )
        session.add(model)
        session.flush()
        session.add(
            Ability(
                id="ability_openai_edit",
                provider="openai",
                category="image_generation",
                capability_key="gpt_image_2_edit",
                display_name="GPT Image 2 编辑",
                status="active",
                ability_type="api",
                vendor_model_id=model.id,
                input_schema=_schema(),
            )
        )
        session.commit()

        report = build_audit_report(session)

    codes = {issue["code"] for issue in report["issues"]}
    assert "VENDOR_MODEL_ACCEPTANCE_MISSING" in codes


def test_audit_accepts_vendor_model_with_acceptance_and_cost_policy() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        model = VendorModelCatalog(
            provider="openai",
            model="gpt-image-2",
            display_name="GPT Image 2",
            status="active",
            api_types=["image_edit"],
            execution_modes=["sync_then_store"],
            supports_mask=True,
            supports_multiple_images=True,
            supports_text=True,
            requires_global_egress=True,
            cost_policy={"unitPrice": 0.2, "billingUnit": "image"},
            extra_metadata={"latestAcceptance": {"status": "passed", "note": "测试通过"}},
            source="test",
        )
        session.add(model)
        session.flush()
        session.add(
            Ability(
                id="ability_openai_edit",
                provider="openai",
                category="image_generation",
                capability_key="gpt_image_2_edit",
                display_name="GPT Image 2 编辑",
                status="active",
                ability_type="api",
                vendor_model_id=model.id,
                input_schema=_schema(),
            )
        )
        session.commit()

        report = build_audit_report(session)

    codes = {issue["code"] for issue in report["issues"]}
    assert "VENDOR_MODEL_ACCEPTANCE_MISSING" not in codes
    assert "VENDOR_MODEL_COST_POLICY_MISSING" not in codes
    assert report["summary"]["issueCount"] == 0
