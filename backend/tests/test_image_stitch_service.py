from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image

from app.services.image_stitch import normalize_image_stitch_options, render_image_stitch


def _payload(**values):
    base = {
        "mode": "count",
        "columns": 1,
        "rows": 1,
        "targetWidth": None,
        "target_width": None,
        "targetHeight": None,
        "target_height": None,
    }
    base.update(values)
    return SimpleNamespace(**base)


def test_image_stitch_count_mode_tiles_source_without_scaling() -> None:
    source = Image.new("RGBA", (20, 10), (255, 0, 0, 255))
    options = normalize_image_stitch_options(_payload(columns=3, rows=2), {})

    result = render_image_stitch(source, options)

    assert result.width == 60
    assert result.height == 20
    assert result.intermediate_width == 60
    assert result.intermediate_height == 20
    assert result.image.getpixel((40, 15)) == (255, 0, 0, 255)


def test_image_stitch_size_mode_scales_after_intermediate_stitch() -> None:
    source = Image.new("RGBA", (20, 10), (0, 255, 0, 255))
    options = normalize_image_stitch_options(
        _payload(mode="size", columns=2, rows=2, targetWidth=120, targetHeight=110),
        {},
    )

    result = render_image_stitch(source, options)

    assert result.width == 120
    assert result.height == 110
    assert result.intermediate_width == 40
    assert result.intermediate_height == 20


def test_image_stitch_rejects_invalid_count_and_output_size() -> None:
    with pytest.raises(HTTPException) as invalid_count:
        normalize_image_stitch_options(_payload(columns=11, rows=1), {})
    assert invalid_count.value.detail == "IMAGE_STITCH_COUNT_INVALID"

    options = normalize_image_stitch_options(_payload(columns=10, rows=10), {})
    with pytest.raises(HTTPException) as too_large:
        render_image_stitch(Image.new("RGBA", (1000, 1000), (0, 0, 0, 0)), options)
    assert too_large.value.detail == "IMAGE_STITCH_OUTPUT_TOO_LARGE"
