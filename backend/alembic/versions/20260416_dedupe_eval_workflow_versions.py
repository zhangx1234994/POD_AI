"""dedupe eval workflow versions and add unique constraint

Revision ID: 20260416_dedupe_eval_workflow_versions
Revises: 20260304_add_task_cost_snapshots
Create Date: 2026-04-16 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260416_dedupe_eval_workflow_versions"
down_revision: Union[str, Sequence[str], None] = "20260304_add_task_cost_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FISSION_WORKFLOW_IDS = {
    "7598841920114130944",
    "7598820684801769472",
    "7622193261276299264",
    "7622190276932534272",
    "7601077530077954048",
    "7598848725942796288",
    "7629024620879806464",
    "7629026792103215104",
    "7598844004557389824",
}

DUAL_CATEGORY_FISSION_WORKFLOW_IDS = {
    "7629026792103215104",
}

CATEGORY_FIX_WORKFLOW_IDS = {
    "7597701996124045312": "通用类",
    "7597702948247830528": "通用类",
    "7597659369861283840": "通用类",
}

OUTPAINTING_WORKFLOW_IDS = {
    "7597723984687267840",
    "7598587935331450880",
}


def _normalize_eval_category(category: str | None) -> str:
    c = (category or "").strip()
    if not c:
        return "通用类"
    if c in {"花纹提取类", "图延伸类", "四方/两方连续图类", "图裂变", "通用类"}:
        return c
    if c in {"pattern_extract", "pattern", "pattern-extract"}:
        return "花纹提取类"
    if c in {"image_extend", "image_extension", "image_extend_v1", "图扩展", "图延伸"}:
        return "图延伸类"
    if c in {"continuous", "lianxu", "seamless"}:
        return "四方/两方连续图类"
    if c in {"图裂变", "liebiam", "liebain", "variation", "image_variation"}:
        return "图裂变"
    if c in {"general", "common"}:
        return "通用类"
    return "通用类"


def _resolve_eval_category(workflow_id: str | None, category: str | None) -> str:
    workflow_id = (workflow_id or "").strip()
    normalized = _normalize_eval_category(category)
    if workflow_id in CATEGORY_FIX_WORKFLOW_IDS:
        return CATEGORY_FIX_WORKFLOW_IDS[workflow_id]
    if workflow_id in OUTPAINTING_WORKFLOW_IDS:
        return "图延伸类"
    if workflow_id in FISSION_WORKFLOW_IDS and workflow_id not in DUAL_CATEGORY_FISSION_WORKFLOW_IDS:
        return "图裂变"
    return normalized


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "eval_workflow_version" not in tables:
        return

    eval_workflow = sa.table(
        "eval_workflow_version",
        sa.column("id", sa.String(64)),
        sa.column("workflow_id", sa.String(64)),
        sa.column("category", sa.String(64)),
        sa.column("status", sa.String(32)),
        sa.column("created_at", sa.DateTime()),
    )
    eval_run = sa.table(
        "eval_run",
        sa.column("workflow_version_id", sa.String(64)),
    )
    eval_batch_session = sa.table(
        "eval_batch_session",
        sa.column("workflow_version_id", sa.String(64)),
    )

    rows = bind.execute(
        sa.select(
            eval_workflow.c.id,
            eval_workflow.c.workflow_id,
            eval_workflow.c.category,
            eval_workflow.c.status,
            eval_workflow.c.created_at,
        ).order_by(eval_workflow.c.created_at.asc(), eval_workflow.c.id.asc())
    ).mappings().all()

    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        workflow_id = str(row["workflow_id"] or "").strip()
        desired_category = _resolve_eval_category(workflow_id, str(row["category"] or "").strip())
        grouped.setdefault((workflow_id, desired_category), []).append(dict(row))

    for (_, desired_category), bucket in grouped.items():
        bucket.sort(
            key=lambda row: (
                0 if str(row.get("status") or "") == "active" else 1,
                str(row.get("created_at") or ""),
                str(row.get("id") or ""),
            )
        )
        canonical = bucket[0]
        if str(canonical.get("category") or "") != desired_category:
            bind.execute(
                sa.update(eval_workflow)
                .where(eval_workflow.c.id == canonical["id"])
                .values(category=desired_category)
            )
        for duplicate in bucket[1:]:
            duplicate_id = str(duplicate.get("id") or "")
            if not duplicate_id:
                continue
            bind.execute(
                sa.update(eval_run)
                .where(eval_run.c.workflow_version_id == duplicate_id)
                .values(workflow_version_id=canonical["id"])
            )
            if "eval_batch_session" in tables:
                bind.execute(
                    sa.update(eval_batch_session)
                    .where(eval_batch_session.c.workflow_version_id == duplicate_id)
                    .values(workflow_version_id=canonical["id"])
                )
            bind.execute(sa.delete(eval_workflow).where(eval_workflow.c.id == duplicate_id))

    unique_constraints = {item["name"] for item in inspector.get_unique_constraints("eval_workflow_version")}
    if "uq_eval_workflow_version_workflow_category" not in unique_constraints:
        op.create_unique_constraint(
            "uq_eval_workflow_version_workflow_category",
            "eval_workflow_version",
            ["workflow_id", "category"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    unique_constraints = {item["name"] for item in inspector.get_unique_constraints("eval_workflow_version")}
    if "uq_eval_workflow_version_workflow_category" in unique_constraints:
        op.drop_constraint(
            "uq_eval_workflow_version_workflow_category",
            "eval_workflow_version",
            type_="unique",
        )
