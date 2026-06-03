from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.eval import EvalBatchSession, EvalRun, EvalWorkflowVersion
from app.services.eval_seed import ensure_default_eval_workflow_versions


def test_eval_seed_does_not_reinsert_general_workflow_after_category_normalization() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    EvalWorkflowVersion.__table__.create(engine)
    EvalRun.__table__.create(engine)
    EvalBatchSession.__table__.create(engine)

    with TestingSession() as session:
        session.add(
            EvalWorkflowVersion(
                id="existing-general-row",
                category="通用类",
                name="ComfyUI 回调 · comfyui_huidiao",
                version="v1",
                workflow_id="7597556718159003648",
                status="active",
                notes="existing",
            )
        )
        session.commit()

        ensure_default_eval_workflow_versions(session)

        rows = session.execute(
            select(EvalWorkflowVersion).where(EvalWorkflowVersion.workflow_id == "7597556718159003648")
        ).scalars().all()

        assert len(rows) == 1
        assert rows[0].category == "通用类"


def test_eval_seed_updates_qwen_text_enhance_repaint_wording_without_renaming() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    EvalWorkflowVersion.__table__.create(engine)
    stale_bili_label = "相似" + "度(%)"

    with TestingSession() as session:
        session.add(
            EvalWorkflowVersion(
                id="existing-qwen-row",
                category="文本与提示词",
                name="业务已改名的文字增强入口",
                version="v1",
                workflow_id="7629024620879806464",
                status="active",
                notes="旧说明：相似度",
                parameters_schema={
                    "fields": [
                        {"name": "url", "label": "图片 URL"},
                        {"name": "bili", "label": stale_bili_label, "description": "旧口径：越高越接近原图"},
                    ]
                },
                output_schema={"fields": [{"name": "output", "type": "text"}]},
            )
        )
        session.commit()

        ensure_default_eval_workflow_versions(session)

        row = session.execute(
            select(EvalWorkflowVersion).where(EvalWorkflowVersion.workflow_id == "7629024620879806464")
        ).scalar_one()

        assert row.name == "业务已改名的文字增强入口"
        assert row.category == "图裂变"
        assert "重绘幅度" in str(row.notes)
        assert "相似度" not in str(row.parameters_schema)
        fields = row.parameters_schema.get("fields") or []
        bili = next(field for field in fields if field.get("name") == "bili")
        assert bili.get("label") == "重绘幅度(%)"


def test_eval_seed_dedupes_before_forced_product_design_category_update() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    EvalWorkflowVersion.__table__.create(engine)
    EvalRun.__table__.create(engine)
    EvalBatchSession.__table__.create(engine)

    with TestingSession() as session:
        session.add_all(
            [
                EvalWorkflowVersion(
                    id="existing-product-canonical",
                    category="产品设计",
                    name="产品设计 · 已有入口",
                    version="product-design-gpt-image2-v1",
                    workflow_id="business_product_design_gpt_image2_v1",
                    status="active",
                ),
                EvalWorkflowVersion(
                    id="existing-product-legacy-category",
                    category="图编辑",
                    name="产品设计 · 旧分类入口",
                    version="product-design-gpt-image2-v1",
                    workflow_id="business_product_design_gpt_image2_v1",
                    status="active",
                ),
            ]
        )
        session.commit()

        ensure_default_eval_workflow_versions(session)

        rows = session.execute(
            select(EvalWorkflowVersion).where(EvalWorkflowVersion.workflow_id == "business_product_design_gpt_image2_v1")
        ).scalars().all()

        assert len(rows) == 1
        assert rows[0].id == "existing-product-canonical"
        assert rows[0].category == "产品设计"
