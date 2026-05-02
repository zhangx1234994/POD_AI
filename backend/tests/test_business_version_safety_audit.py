from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "business_version_safety_audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("business_version_safety_audit", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_business_keys_ignores_empty_values() -> None:
    module = _load_module()

    assert module._parse_business_keys(" fission, ,outpaint,, ") == ["fission", "outpaint"]
    assert module.DEFAULT_BUSINESS_KEYS == ("pattern_extract", "fission", "outpaint")


def test_report_safe_requires_default_and_rollback_target() -> None:
    module = _load_module()

    assert module._is_report_safe({"ok": True, "currentDefault": {"id": "a"}, "rollbackTarget": {"id": "b"}}) is True
    assert module._is_report_safe({"ok": True, "currentDefault": {"id": "a"}, "rollbackTarget": None}) is False
    assert module._is_report_safe({"ok": False, "currentDefault": {"id": "a"}, "rollbackTarget": {"id": "b"}}) is False
