from __future__ import annotations

from datetime import datetime

from app.models.eval import EvalWorkflowVersion
from app.routers.evals_public import _dedupe_workflow_versions


def _workflow(row_id: str, *, category: str, workflow_id: str) -> EvalWorkflowVersion:
    return EvalWorkflowVersion(
        id=row_id,
        category=category,
        name="四方连续裂变",
        version="v1",
        workflow_id=workflow_id,
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_public_workflow_dedupe_uses_workflow_id_across_categories() -> None:
    rows = [
        _workflow("row_1", category="四方/两方连续图类", workflow_id="7629026792103215104"),
        _workflow("row_2", category="图裂变", workflow_id="7629026792103215104"),
        _workflow("row_3", category="图裂变", workflow_id="7631838631375667200"),
    ]

    deduped = _dedupe_workflow_versions(rows)

    assert [row.id for row in deduped] == ["row_1", "row_3"]

