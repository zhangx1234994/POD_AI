from __future__ import annotations

from copy import deepcopy

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.integration import Workflow
from app.services.workflow_seed import ensure_default_workflows


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
