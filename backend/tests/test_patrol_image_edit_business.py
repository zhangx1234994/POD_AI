from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "patrol_image_edit_business.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("patrol_image_edit_business", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_image_edit_patrol_includes_canvas_outpaint_release_cases() -> None:
    module = _load_module()

    keys = [case.key for case in module.IMAGE_EDIT_CASES]

    assert "local_modify" in keys
    assert "reference_element_transfer" in keys
    assert "remove_inpaint" in keys
    assert "color_reference_correction" in keys
    assert "canvas_outpaint_all_sides" in keys
    assert "canvas_outpaint_left" in keys
    assert "canvas_outpaint_horizontal" in keys
    assert "canvas_outpaint_vertical" in keys


def test_canvas_outpaint_patrol_payload_sets_outpaint_controls() -> None:
    module = _load_module()
    case = module._select_cases("canvas_outpaint_left")[0]

    payload = module._build_payload(
        case,
        image_url="https://example.com/source.png",
        reference_image_url="https://example.com/ref.png",
        size="auto",
        quality="preview",
        tag="t1",
    )

    assert payload["imageUrl"] == "https://example.com/source.png"
    assert payload["editSkill"] == "canvas_outpaint"
    assert payload["quality"] == "preview"
    assert payload["expand_left"] == 384
    assert payload["expand_right"] == 0
    assert payload["anchor"] == "right"
    assert payload["preserveOriginal"] is True
    assert "referenceImages" not in payload
    assert payload["metadata"]["caseKey"] == "canvas_outpaint_left"


def test_image_edit_patrol_rejects_unknown_case() -> None:
    module = _load_module()

    try:
        module._select_cases("canvas_outpaint_left,unknown_case")
    except ValueError as exc:
        assert "unknown_case" in str(exc)
    else:
        raise AssertionError("unknown image edit patrol case should be rejected")
