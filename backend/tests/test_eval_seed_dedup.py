from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.eval import EvalWorkflowVersion
from app.services.eval_seed import ensure_default_eval_workflow_versions


def test_eval_seed_does_not_reinsert_general_workflow_after_category_normalization() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    EvalWorkflowVersion.__table__.create(engine)

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
