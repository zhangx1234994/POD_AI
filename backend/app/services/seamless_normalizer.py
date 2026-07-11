"""Deterministic post-processing for production-bound repeat artwork.

Generative workflows can create visually plausible repeat candidates, but they
cannot guarantee that opposite edge pixels are identical. This module owns the
last deterministic gate: it measures the edge mismatch and can lock selected
axes to identical edge pixels. It deliberately does not claim that a locked
edge is automatically visually seamless; callers must still review a tiled
preview before marking an asset production-ready.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageChops, ImageStat


@dataclass(frozen=True)
class EdgeDifference:
    """Absolute channel difference between two opposite image borders."""

    mean_abs: float
    max_abs: int


@dataclass(frozen=True)
class SeamlessNormalizationResult:
    """Normalized image with before/after evidence for the production gate."""

    image: Image.Image
    horizontal_before: EdgeDifference | None
    vertical_before: EdgeDifference | None
    horizontal_after: EdgeDifference | None
    vertical_after: EdgeDifference | None
    locked_axes: tuple[str, ...]


def measure_opposite_edges(image: Image.Image) -> tuple[EdgeDifference, EdgeDifference]:
    """Return left/right and top/bottom differences using RGBA channel values."""

    normalized = image.convert("RGBA")
    width, height = normalized.size
    if width < 2 or height < 2:
        raise ValueError("SEAMLESS_IMAGE_TOO_SMALL")
    horizontal = _difference(
        normalized.crop((0, 0, 1, height)),
        normalized.crop((width - 1, 0, width, height)),
    )
    vertical = _difference(
        normalized.crop((0, 0, width, 1)),
        normalized.crop((0, height - 1, width, height)),
    )
    return horizontal, vertical


def lock_periodic_edges(
    image: Image.Image,
    *,
    horizontal: bool,
    vertical: bool,
) -> SeamlessNormalizationResult:
    """Lock requested edge pairs to an identical averaged RGBA border.

    This is intentionally a final deterministic operation. It never generates
    visual content and therefore cannot repair a composition with an obvious
    semantic seam. Use it only after a candidate has passed a tiled-preview
    review, then require a zero-difference assertion before production export.
    """

    result = image.convert("RGBA").copy()
    before_horizontal, before_vertical = measure_opposite_edges(result)
    width, height = result.size
    locked_axes: list[str] = []

    if horizontal:
        edge = Image.blend(
            result.crop((0, 0, 1, height)),
            result.crop((width - 1, 0, width, height)),
            0.5,
        )
        result.paste(edge, (0, 0))
        result.paste(edge, (width - 1, 0))
        locked_axes.append("horizontal")

    if vertical:
        edge = Image.blend(
            result.crop((0, 0, width, 1)),
            result.crop((0, height - 1, width, height)),
            0.5,
        )
        result.paste(edge, (0, 0))
        result.paste(edge, (0, height - 1))
        locked_axes.append("vertical")

    after_horizontal, after_vertical = measure_opposite_edges(result)
    return SeamlessNormalizationResult(
        image=result,
        horizontal_before=before_horizontal,
        vertical_before=before_vertical,
        horizontal_after=after_horizontal,
        vertical_after=after_vertical,
        locked_axes=tuple(locked_axes),
    )


def _difference(first: Image.Image, second: Image.Image) -> EdgeDifference:
    delta = ImageChops.difference(first, second)
    channel_means = ImageStat.Stat(delta).mean
    extrema = delta.getextrema()
    max_abs = max(int(maximum) for _minimum, maximum in extrema)
    return EdgeDifference(
        mean_abs=sum(float(value) for value in channel_means) / len(channel_means),
        max_abs=max_abs,
    )
