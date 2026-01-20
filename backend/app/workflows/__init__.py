"""Workflow helpers for built-in ComfyUI graphs."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

WORKFLOW_ROOT = Path(__file__).resolve().parent
_CACHE: dict[str, dict[str, Any]] = {}


def load_comfy_workflow(workflow_key: str) -> dict[str, Any]:
    """Return a deepcopy of the stored workflow graph."""

    if workflow_key not in _CACHE:
        path = WORKFLOW_ROOT / "comfyui" / f"{workflow_key}.json"
        if not path.exists():
            raise FileNotFoundError(f"Workflow '{workflow_key}' not found")
        # Be explicit about encoding; production servers may run under GBK locales.
        _CACHE[workflow_key] = json.loads(path.read_text(encoding="utf-8"))
    return deepcopy(_CACHE[workflow_key])
