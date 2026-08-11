"""RGB-derived grouping and visual ordering for paint colors."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
import math

from src.paint_catalog import PaintColor


NEUTRAL_MAX_CHROMA = 0.025
BROWN_MIN_HUE = 35.0
BROWN_MAX_HUE = 100.0
BROWN_MIN_LIGHTNESS = 0.25
BROWN_MAX_LIGHTNESS = 0.70
BROWN_MIN_CHROMA = 0.03
BROWN_MAX_CHROMA = 0.15

PINK_RED_BOUNDARY = 10.0
RED_ORANGE_BOUNDARY = 35.0
ORANGE_YELLOW_BOUNDARY = 85.0
YELLOW_GREEN_BOUNDARY = 120.0
GREEN_TEAL_BOUNDARY = 175.0
TEAL_BLUE_BOUNDARY = 225.0
BLUE_PURPLE_BOUNDARY = 285.0
PURPLE_PINK_BOUNDARY = 325.0


class ColorGroup(Enum):
    RED = "Reds"
    ORANGE = "Oranges"
    YELLOW = "Yellows"
    GREEN = "Greens"
    TEAL_CYAN = "Teals / Cyans"
    BLUE = "Blues"
    PURPLE = "Purples"
    PINK = "Pinks"
    BROWN = "Browns"
    NEUTRAL = "Neutrals"


VISUAL_GROUP_ORDER = (
    ColorGroup.RED,
    ColorGroup.ORANGE,
    ColorGroup.YELLOW,
    ColorGroup.GREEN,
    ColorGroup.TEAL_CYAN,
    ColorGroup.BLUE,
    ColorGroup.PURPLE,
    ColorGroup.PINK,
    ColorGroup.BROWN,
    ColorGroup.NEUTRAL,
)
PERCEPTUAL_HUE_BAND_DEGREES = 12.0
PERCEPTUAL_LIGHTNESS_BAND_SIZE = 0.08
PERCEPTUAL_SPECTRUM_START_DEGREES = 20.0


@dataclass(frozen=True)
class PerceptualColorAnalysis:
    """OKLCH coordinates derived from an sRGB paint colour."""

    lightness: float
    chroma: float
    hue: float


def _linearize_srgb(channel: int) -> float:
    normalized = channel / 255.0
    if normalized <= 0.04045:
        return normalized / 12.92
    return math.pow((normalized + 0.055) / 1.055, 2.4)


def _cube_root(value: float) -> float:
    return math.copysign(math.pow(abs(value), 1.0 / 3.0), value)


def analyze_perceptual_color(paint: PaintColor) -> PerceptualColorAnalysis:
    """Convert an sRGB paint colour to perceptually uniform OKLCH."""
    red, green, blue = (
        _linearize_srgb(channel) for channel in (paint.r, paint.g, paint.b)
    )
    l_value = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    m_value = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    s_value = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue
    l_root, m_root, s_root = (
        _cube_root(value) for value in (l_value, m_value, s_value)
    )
    lightness = 0.2104542553 * l_root + 0.7936177850 * m_root - 0.0040720468 * s_root
    a_axis = 1.9779984951 * l_root - 2.4285922050 * m_root + 0.4505937099 * s_root
    b_axis = 0.0259040371 * l_root + 0.7827717662 * m_root - 0.8086757660 * s_root
    hue = math.degrees(math.atan2(b_axis, a_axis)) % 360.0
    return PerceptualColorAnalysis(
        lightness=lightness,
        chroma=math.hypot(a_axis, b_axis),
        hue=hue,
    )


def _is_neutral(analysis: PerceptualColorAnalysis) -> bool:
    return analysis.chroma <= NEUTRAL_MAX_CHROMA


def _is_brown(analysis: PerceptualColorAnalysis) -> bool:
    return (
        BROWN_MIN_HUE <= analysis.hue < BROWN_MAX_HUE
        and BROWN_MIN_LIGHTNESS <= analysis.lightness <= BROWN_MAX_LIGHTNESS
        and BROWN_MIN_CHROMA <= analysis.chroma <= BROWN_MAX_CHROMA
    )


def classify_paint_color(paint: PaintColor) -> ColorGroup:
    """Classify RGB through an ordered OKLCH hierarchy, never by paint name."""
    analysis = analyze_perceptual_color(paint)
    if _is_neutral(analysis):
        return ColorGroup.NEUTRAL
    if _is_brown(analysis):
        return ColorGroup.BROWN

    hue = analysis.hue
    if hue < PINK_RED_BOUNDARY:
        return ColorGroup.PINK
    if hue < RED_ORANGE_BOUNDARY:
        return ColorGroup.RED
    if hue < ORANGE_YELLOW_BOUNDARY:
        return ColorGroup.ORANGE
    if hue < YELLOW_GREEN_BOUNDARY:
        return ColorGroup.YELLOW
    if hue < GREEN_TEAL_BOUNDARY:
        return ColorGroup.GREEN
    if hue < TEAL_BLUE_BOUNDARY:
        return ColorGroup.TEAL_CYAN
    if hue < BLUE_PURPLE_BOUNDARY:
        return ColorGroup.BLUE
    if hue < PURPLE_PINK_BOUNDARY:
        return ColorGroup.PURPLE
    return ColorGroup.PINK


def get_paints_for_group(
    paints: Iterable[PaintColor], color_group: ColorGroup
) -> tuple[PaintColor, ...]:
    """Return paints belonging to one derived visual group."""
    return tuple(
        paint for paint in paints if classify_paint_color(paint) is color_group
    )


def _stable_paint_key(paint: PaintColor) -> tuple[str, str, int, int, int]:
    return (paint.id, paint.name, paint.r, paint.g, paint.b)


def _group_sort_key(
    paint: PaintColor, color_group: ColorGroup
) -> tuple[float, float, float, float, str, str, int, int, int]:
    perceptual = analyze_perceptual_color(paint)
    if color_group is ColorGroup.NEUTRAL:
        return (
            perceptual.lightness,
            perceptual.chroma,
            0.0,
            0.0,
            *_stable_paint_key(paint),
        )
    if color_group is ColorGroup.BROWN:
        return (
            perceptual.lightness,
            perceptual.hue,
            perceptual.chroma,
            0.0,
            *_stable_paint_key(paint),
        )
    lightness_band = math.floor(
        perceptual.lightness / PERCEPTUAL_LIGHTNESS_BAND_SIZE
    )
    group_hue = (
        perceptual.hue - PERCEPTUAL_SPECTRUM_START_DEGREES
    ) % 360.0
    # Filtered chromatic groups have a narrow hue range, so lightness bands
    # prevent isolated dark/light paints while hue and chroma organize peers.
    band_hue = group_hue if lightness_band % 2 == 0 else -group_hue
    return (
        lightness_band,
        band_hue,
        perceptual.chroma,
        perceptual.lightness,
        *_stable_paint_key(paint),
    )


def _spectrum_sort_key(
    paint: PaintColor, color_group: ColorGroup
) -> tuple[int, float, float, float, float, str, str, int, int, int]:
    perceptual = analyze_perceptual_color(paint)
    if color_group is ColorGroup.NEUTRAL:
        return (
            1,
            perceptual.lightness,
            perceptual.chroma,
            0.0,
            0.0,
            *_stable_paint_key(paint),
        )
    spectrum_hue = (
        perceptual.hue - PERCEPTUAL_SPECTRUM_START_DEGREES
    ) % 360.0
    hue_band = math.floor(spectrum_hue / PERCEPTUAL_HUE_BAND_DEGREES)
    band_lightness = (
        perceptual.lightness if hue_band % 2 == 0 else -perceptual.lightness
    )
    return (
        0,
        hue_band,
        band_lightness,
        perceptual.chroma,
        spectrum_hue,
        *_stable_paint_key(paint),
    )


def sort_paints_visually(paints: Iterable[PaintColor]) -> tuple[PaintColor, ...]:
    """Return a deterministic OKLCH-based ordering without mutation."""
    paint_items = tuple(paints)
    classified = tuple(
        (paint, classify_paint_color(paint)) for paint in paint_items
    )
    groups = {color_group for _, color_group in classified}
    if len(groups) == 1:
        color_group = next(iter(groups), ColorGroup.NEUTRAL)
        return tuple(
            sorted(
                paint_items,
                key=lambda paint: _group_sort_key(paint, color_group),
            )
        )
    return tuple(
        paint
        for paint, _ in sorted(
            classified,
            key=lambda item: _spectrum_sort_key(*item),
        )
    )
