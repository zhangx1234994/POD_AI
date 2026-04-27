from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "business_rollback_drill.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("business_rollback_drill", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_previous_default_ids_are_read_from_recent_release_events() -> None:
    module = _load_module()
    current = SimpleNamespace(
        id="biz_fission_v3",
        extra_metadata={
            "releaseEvents": [
                {"previousDefaultCapabilityId": "biz_fission_v1"},
                {"previousDefaultCapabilityId": "biz_fission_v2"},
                {"previousDefaultCapabilityId": "biz_fission_v2"},
                {"previousDefaultCapabilityId": "biz_fission_v3"},
            ]
        },
    )

    assert module._previous_default_ids(current) == ["biz_fission_v2", "biz_fission_v1"]


def test_capability_summary_hides_metadata_but_keeps_release_identity() -> None:
    module = _load_module()
    row = SimpleNamespace(
        id="biz_outpaint_v2",
        business_key="outpaint",
        version="v2",
        display_name="扩图新版",
        status="active",
        is_default=True,
        release_time=None,
        updated_at=None,
    )

    assert module._capability_summary(row) == {
        "id": "biz_outpaint_v2",
        "businessKey": "outpaint",
        "version": "v2",
        "displayName": "扩图新版",
        "status": "active",
        "isDefault": True,
        "releaseTime": None,
        "updatedAt": None,
    }
