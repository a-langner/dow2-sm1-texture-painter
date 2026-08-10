"""RGB-derived grouping and visual ordering for paint colors."""

from __future__ import annotations

import colorsys
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from src.paint_catalog import PaintColor


NEUTRAL_MAX_SATURATION = 0.12
BROWN_MIN_HUE = 15.0
BROWN_MAX_HUE = 50.0
BROWN_MIN_SATURATION = 0.20
BROWN_MAX_VALUE = 0.75
BROWN_MAX_LIGHTNESS = 0.55

RED_ORANGE_BOUNDARY = 15.0
ORANGE_YELLOW_BOUNDARY = 45.0
YELLOW_GREEN_BOUNDARY = 70.0
GREEN_TEAL_BOUNDARY = 165.0
TEAL_BLUE_BOUNDARY = 195.0
BLUE_PURPLE_BOUNDARY = 255.0
PURPLE_PINK_BOUNDARY = 300.0
PINK_RED_BOUNDARY = 345.0


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
_GROUP_SORT_INDEX = {
    color_group: index for index, color_group in enumerate(VISUAL_GROUP_ORDER)
}


@dataclass(frozen=True)
class PaintColorAnalysis:
    hue: float
    saturation: float
    value: float
    lightness: float


def analyze_paint_color(paint: PaintColor) -> PaintColorAnalysis:
    """Derive normalized HSV/HSL properties from one paint's RGB channels."""
    red, green, blue = (channel / 255.0 for channel in (paint.r, paint.g, paint.b))
    hsv_hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    _, lightness, _ = colorsys.rgb_to_hls(red, green, blue)
    return PaintColorAnalysis(
        hue=hsv_hue * 360.0,
        saturation=saturation,
        value=value,
        lightness=lightness,
    )


def _is_brown(analysis: PaintColorAnalysis) -> bool:
    return (
        BROWN_MIN_HUE <= analysis.hue < BROWN_MAX_HUE
        and analysis.saturation >= BROWN_MIN_SATURATION
        and analysis.value <= BROWN_MAX_VALUE
        and analysis.lightness <= BROWN_MAX_LIGHTNESS
    )


def classify_paint_color(paint: PaintColor) -> ColorGroup:
    """Classify a paint by derived color properties, independently of its name."""
    analysis = analyze_paint_color(paint)
    if analysis.saturation <= NEUTRAL_MAX_SATURATION:
        return ColorGroup.NEUTRAL
    if _is_brown(analysis):
        return ColorGroup.BROWN

    hue = analysis.hue
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
    if hue < PINK_RED_BOUNDARY:
        return ColorGroup.PINK
    return ColorGroup.RED


def get_paints_for_group(
    paints: Iterable[PaintColor], color_group: ColorGroup
) -> tuple[PaintColor, ...]:
    """Return paints belonging to one derived visual group."""
    return tuple(
        paint for paint in paints if classify_paint_color(paint) is color_group
    )


def _visual_sort_key(
    paint: PaintColor,
) -> tuple[int, float, float, float, str, str, int, int, int]:
    analysis = analyze_paint_color(paint)
    color_group = classify_paint_color(paint)

    if color_group is ColorGroup.NEUTRAL:
        primary, secondary, tertiary = (
            analysis.value,
            analysis.saturation,
            analysis.hue,
        )
    else:
        hue = analysis.hue
        if color_group is ColorGroup.RED and hue < RED_ORANGE_BOUNDARY:
            hue += 360.0
        primary, secondary, tertiary = (
            hue,
            analysis.value,
            analysis.saturation,
        )

    return (
        _GROUP_SORT_INDEX[color_group],
        primary,
        secondary,
        tertiary,
        paint.id,
        paint.name,
        paint.r,
        paint.g,
        paint.b,
    )


def sort_paints_visually(paints: Iterable[PaintColor]) -> tuple[PaintColor, ...]:
    """Return a deterministic spectrum-oriented ordering without mutating input."""
    return tuple(sorted(paints, key=_visual_sort_key))
