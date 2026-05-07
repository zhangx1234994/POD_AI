from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models.integration import Workflow
from app.services.workflow_seed import DEFAULT_WORKFLOW_SEEDS, ensure_default_workflows


def test_ensure_default_workflows_refreshes_existing_definition() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Workflow.__table__.create(engine)

    with TestingSession() as session:
        stale_workflow = Workflow(
            id="workflow_comfyui_duotu_ronghe_v1",
            action="multi_image_fusion",
            name="多图融合 · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            definition={
                "workflow_key": "duotu_ronghe",
                "graph": {
                    "371": {"inputs": {"width": 512, "height": 512, "batch_size": 1}},
                },
            },
            extra_metadata={"workflow_key": "duotu_ronghe", "output_node_ids": ["999"]},
        )
        session.add(stale_workflow)
        session.commit()

        changed = ensure_default_workflows(session)
        assert changed is True

        refreshed = session.get(Workflow, "workflow_comfyui_duotu_ronghe_v1")
        assert refreshed is not None
        definition = deepcopy(refreshed.definition)
        assert definition["workflow_key"] == "duotu_ronghe"
        assert "112" in definition["graph"]
        assert "371" not in definition["graph"]
        assert refreshed.extra_metadata == {
            "workflow_key": "duotu_ronghe",
            "description": "ComfyUI workflow for multi-image fusion / compositing.",
            "output_node_ids": ["357"],
        }


def test_ensure_default_workflows_is_safe_under_parallel_startup(tmp_path) -> None:
    db_path = tmp_path / "workflow_seed.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}?check_same_thread=false",
        future=True,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Workflow.__table__.create(engine)

    def run_seed() -> bool:
        with TestingSession() as session:
            return ensure_default_workflows(session)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: run_seed(), range(4)))

    with TestingSession() as session:
        workflow_count = session.scalar(select(func.count()).select_from(Workflow))

    assert workflow_count == len(DEFAULT_WORKFLOW_SEEDS)
    assert any(results)
