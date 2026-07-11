from PIL import Image

from app.services.seamless_normalizer import lock_periodic_edges, measure_opposite_edges


def _non_periodic_image() -> Image.Image:
    image = Image.new("RGBA", (8, 6), (255, 255, 255, 255))
    for y in range(image.height):
        image.putpixel((0, y), (255, 0, 0, 255))
        image.putpixel((image.width - 1, y), (0, 0, 255, 255))
    for x in range(image.width):
        image.putpixel((x, 0), (0, 255, 0, 255))
        image.putpixel((x, image.height - 1), (255, 255, 0, 255))
    return image


def test_measure_opposite_edges_reports_non_periodic_borders():
    horizontal, vertical = measure_opposite_edges(_non_periodic_image())

    assert horizontal.max_abs > 0
    assert vertical.max_abs > 0


def test_lock_periodic_edges_makes_all_requested_boundaries_identical():
    result = lock_periodic_edges(_non_periodic_image(), horizontal=True, vertical=True)

    assert result.horizontal_before is not None
    assert result.vertical_before is not None
    assert result.horizontal_before.max_abs > 0
    assert result.vertical_before.max_abs > 0
    assert result.horizontal_after is not None
    assert result.vertical_after is not None
    assert result.horizontal_after.max_abs == 0
    assert result.vertical_after.max_abs == 0
    assert result.locked_axes == ("horizontal", "vertical")


def test_lock_periodic_edges_leaves_unrequested_axis_unchanged():
    source = _non_periodic_image()
    _, vertical_before = measure_opposite_edges(source)

    result = lock_periodic_edges(source, horizontal=True, vertical=False)

    assert result.horizontal_after is not None
    assert result.horizontal_after.max_abs == 0
    assert result.vertical_after == vertical_before
    assert result.locked_axes == ("horizontal",)
