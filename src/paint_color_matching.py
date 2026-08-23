"""CIELAB and CIEDE2000 matching for predefined paint catalogs."""

from __future__ import annotations

from dataclasses import dataclass
import math

from src.color_picker_visual import normalize_rgb_hex, rgb_hex_to_channels
from src.paint_catalog import PaintCatalog, PaintColor, RGBColor


@dataclass(frozen=True)
class LabColor:
    lightness: float
    a_axis: float
    b_axis: float


@dataclass(frozen=True)
class ClosestPaintMatch:
    paint: PaintColor
    delta_e: float


def _linearize_srgb(channel: int) -> float:
    value = channel / 255.0
    if value <= 0.04045:
        return value / 12.92
    return math.pow((value + 0.055) / 1.055, 2.4)


def _lab_axis(value: float) -> float:
    delta = 6.0 / 29.0
    if value > delta**3:
        return math.pow(value, 1.0 / 3.0)
    return value / (3.0 * delta**2) + 4.0 / 29.0


def rgb_to_cielab(rgb: RGBColor) -> LabColor:
    """Convert an 8-bit sRGB colour to CIELAB using a D65 reference white."""
    red, green, blue = (_linearize_srgb(channel) for channel in rgb)
    x_value = (0.4124564 * red + 0.3575761 * green + 0.1804375 * blue) / 0.95047
    y_value = 0.2126729 * red + 0.7151522 * green + 0.0721750 * blue
    z_value = (0.0193339 * red + 0.1191920 * green + 0.9503041 * blue) / 1.08883
    x_axis, y_axis, z_axis = (
        _lab_axis(value) for value in (x_value, y_value, z_value)
    )
    return LabColor(
        lightness=116.0 * y_axis - 16.0,
        a_axis=500.0 * (x_axis - y_axis),
        b_axis=200.0 * (y_axis - z_axis),
    )


def ciede2000(first: LabColor, second: LabColor) -> float:
    """Return the CIEDE2000 colour difference with unit weighting factors."""
    l1, a1, b1 = first.lightness, first.a_axis, first.b_axis
    l2, a2, b2 = second.lightness, second.a_axis, second.b_axis
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    mean_c = (c1 + c2) / 2.0
    g_factor = 0.5 * (1.0 - math.sqrt(mean_c**7 / (mean_c**7 + 25.0**7)))
    a1_prime, a2_prime = (1.0 + g_factor) * a1, (1.0 + g_factor) * a2
    c1_prime, c2_prime = math.hypot(a1_prime, b1), math.hypot(a2_prime, b2)
    h1_prime = math.degrees(math.atan2(b1, a1_prime)) % 360.0
    h2_prime = math.degrees(math.atan2(b2, a2_prime)) % 360.0

    delta_l = l2 - l1
    delta_c = c2_prime - c1_prime
    hue_difference = h2_prime - h1_prime
    if c1_prime * c2_prime == 0.0:
        delta_hue = 0.0
    elif abs(hue_difference) <= 180.0:
        delta_hue = hue_difference
    elif hue_difference > 180.0:
        delta_hue = hue_difference - 360.0
    else:
        delta_hue = hue_difference + 360.0
    delta_h = 2.0 * math.sqrt(c1_prime * c2_prime) * math.sin(
        math.radians(delta_hue / 2.0)
    )

    mean_l = (l1 + l2) / 2.0
    mean_c_prime = (c1_prime + c2_prime) / 2.0
    if c1_prime * c2_prime == 0.0:
        mean_h = h1_prime + h2_prime
    elif abs(h1_prime - h2_prime) <= 180.0:
        mean_h = (h1_prime + h2_prime) / 2.0
    elif h1_prime + h2_prime < 360.0:
        mean_h = (h1_prime + h2_prime + 360.0) / 2.0
    else:
        mean_h = (h1_prime + h2_prime - 360.0) / 2.0

    t_factor = (
        1.0
        - 0.17 * math.cos(math.radians(mean_h - 30.0))
        + 0.24 * math.cos(math.radians(2.0 * mean_h))
        + 0.32 * math.cos(math.radians(3.0 * mean_h + 6.0))
        - 0.20 * math.cos(math.radians(4.0 * mean_h - 63.0))
    )
    delta_theta = 30.0 * math.exp(-((mean_h - 275.0) / 25.0) ** 2)
    c_ratio = mean_c_prime**7 / (mean_c_prime**7 + 25.0**7)
    r_term = -2.0 * math.sqrt(c_ratio) * math.sin(math.radians(2.0 * delta_theta))
    l_scale = 1.0 + 0.015 * (mean_l - 50.0) ** 2 / math.sqrt(
        20.0 + (mean_l - 50.0) ** 2
    )
    c_scale = 1.0 + 0.045 * mean_c_prime
    h_scale = 1.0 + 0.015 * mean_c_prime * t_factor
    l_term, c_term, h_term = (
        delta_l / l_scale,
        delta_c / c_scale,
        delta_h / h_scale,
    )
    return math.sqrt(
        l_term**2 + c_term**2 + h_term**2 + r_term * c_term * h_term
    )


def find_closest_paints(
    color: str,
    catalog: PaintCatalog,
    limit: int = 3,
) -> tuple[ClosestPaintMatch, ...]:
    """Return the closest predefined catalog paints in ascending Delta E 2000."""
    if limit < 0:
        raise ValueError("limit must not be negative")
    target = rgb_to_cielab(rgb_hex_to_channels(normalize_rgb_hex(color)))
    ranked = (
        (
            ciede2000(target, rgb_to_cielab((paint.r, paint.g, paint.b))),
            index,
            paint,
        )
        for index, paint in enumerate(catalog.paints)
    )
    return tuple(
        ClosestPaintMatch(paint=paint, delta_e=distance)
        for distance, _, paint in sorted(ranked, key=lambda item: (item[0], item[1]))[
            :limit
        ]
    )
