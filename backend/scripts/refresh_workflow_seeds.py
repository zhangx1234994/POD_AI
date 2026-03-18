from __future__ import annotations

from app.core.db import get_session
from app.services.ability_seed import ensure_default_abilities
from app.services.executor_seed import ensure_default_executors
from app.services.workflow_seed import ensure_default_bindings, ensure_default_workflows


def main() -> None:
    with get_session() as session:
        executors_changed = ensure_default_executors(session)
        workflows_changed = ensure_default_workflows(session)
        bindings_changed = ensure_default_bindings(session)
        abilities_changed = ensure_default_abilities(session)

    print(
        {
            "executors_changed": executors_changed,
            "workflows_changed": workflows_changed,
            "bindings_changed": bindings_changed,
            "abilities_changed": abilities_changed,
        }
    )


if __name__ == "__main__":
    main()
