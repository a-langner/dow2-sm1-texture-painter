"""Pure color conversion and coordinate helpers for the visual color picker."""

from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass
from enum import Enum


DARK_TEXT_COLOR = "#000000"
LIGHT_TEXT_COLOR = "#ffffff"


class ColorVisualizationMode(str, Enum):
    """Identify a picker visualization without introducing another colour state."""

    HSV_HSB = "HSV / HSB"
    HSL = "HSL"
    COLOR_WHEEL = "Color Wheel"
    CLASSIC = "Classic"

    @property
    def uses_hsl_model(self) -> bool:
        """Return whether numeric controls and the shared field use HSL semantics."""
        return self is ColorVisualizationMode.HSL

    @property
    def numeric_model_title(self) -> str:
        """Return the model title shown above the shared numeric controls."""
        return "HSL" if self.uses_hsl_model else "HSV / HSB"

    @property
    def component_label(self) -> str:
        """Return the third shared numeric component label."""
        return "Lightness:" if self.uses_hsl_model else "Value:"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ColorWheelGeometry:
    """Pixel geometry shared by wheel rendering and later interaction mapping."""

    center_x: float
    center_y: float
    outer_radius: float
    ring_inner_radius: float
    field_left: float
    field_top: float
    field_right: float
    field_bottom: float


def color_wheel_geometry(width: int, height: int) -> ColorWheelGeometry:
    """Return centered, unclipped hue-ring and inner-square geometry."""
    center_x = max(0, width - 1) / 2.0
    center_y = max(0, height - 1) / 2.0
    extent = max(0.0, float(min(width, height) - 1))
    padding = max(2.0, extent * 0.025)
    outer_radius = max(0.0, extent / 2.0 - padding)
    ring_width = min(outer_radius, max(8.0, outer_radius * 0.18))
    ring_inner_radius = max(0.0, outer_radius - ring_width)
    field_half_extent = max(0.0, ring_inner_radius * 0.64)
    return ColorWheelGeometry(
        center_x=center_x,
        center_y=center_y,
        outer_radius=outer_radius,
        ring_inner_radius=ring_inner_radius,
        field_left=center_x - field_half_extent,
        field_top=center_y - field_half_extent,
        field_right=center_x + field_half_extent,
        field_bottom=center_y + field_half_extent,
    )


def normalize_rgb_hex(color: str) -> str:
    """Validate six-digit RGB input and return uppercase ``#RRGGBB``."""
    value = color.strip().removeprefix("#")
    if len(value) != 6:
        raise ValueError(f"Expected a six-digit RGB color, got {color!r}")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"Expected a six-digit RGB color, got {color!r}") from exc
    return f"#{value.upper()}"


def rgb_hex_to_channels(color: str) -> tuple[int, int, int]:
    """Convert a six-digit RGB color string to integer channels."""
    value = normalize_rgb_hex(color)[1:]
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def _linearize_srgb_channel(channel: int) -> float:
    value = channel / 255.0
    if value <= 0.04045:
        return value / 12.92
    return math.pow((value + 0.055) / 1.055, 2.4)


def relative_luminance(color: str) -> float:
    """Return WCAG relative luminance for a six-digit RGB color."""
    red, green, blue = (
        _linearize_srgb_channel(channel) for channel in rgb_hex_to_channels(color)
    )
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first_luminance: float, second_luminance: float) -> float:
    """Return the WCAG contrast ratio between two relative luminances."""
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def contrasting_text_color(background: str) -> str:
    """Choose black or white text with the greater WCAG contrast ratio."""
    luminance = relative_luminance(background)
    white_contrast = contrast_ratio(1.0, luminance)
    black_contrast = contrast_ratio(0.0, luminance)
    if white_contrast >= black_contrast:
        return LIGHT_TEXT_COLOR
    return DARK_TEXT_COLOR


def rgb_channels_to_hex(red: int, green: int, blue: int) -> str:
    """Convert integer RGB channels to a canonical lowercase color string."""
    channels = (red, green, blue)
    if any(type(channel) is not int or not 0 <= channel <= 255 for channel in channels):
        raise ValueError("RGB channels must be integers between 0 and 255")
    return "#{:02x}{:02x}{:02x}".format(*channels)


def clamp_coordinate(coordinate: float, extent: int) -> float:
    """Clamp a canvas coordinate to its inclusive drawable range."""
    return min(max(coordinate, 0.0), float(max(0, extent - 1)))


def coordinate_to_unit(coordinate: float, extent: int) -> float:
    """Map an inclusive canvas coordinate to ``0..1``."""
    if extent <= 1:
        return 0.0
    return clamp_coordinate(coordinate, extent) / (extent - 1)


def unit_to_coordinate(value: float, extent: int) -> float:
    """Map a normalized value to an inclusive canvas coordinate."""
    return min(max(value, 0.0), 1.0) * max(0, extent - 1)


def hsv_from_field_position(
    x: float, y: float, width: int, height: int, hue: float
) -> tuple[float, float, float]:
    """Map field position to hue, saturation and value (top is brightest)."""
    return hue % 1.0, coordinate_to_unit(x, width), 1.0 - coordinate_to_unit(y, height)


def hsv_field_position(
    saturation: float, value: float, width: int, height: int
) -> tuple[float, float]:
    """Map saturation and value to a field position."""
    return unit_to_coordinate(saturation, width), unit_to_coordinate(1.0 - value, height)


def hue_from_slider_position(y: float, height: int) -> float:
    """Map the vertical spectrum from red at top through one full hue turn."""
    return coordinate_to_unit(y, height)


def hue_slider_position(hue: float, height: int) -> float:
    """Map normalized hue to the vertical spectrum."""
    return unit_to_coordinate(hue, height)


def rgb_hex_to_hsv(color: str) -> tuple[float, float, float]:
    """Convert a six-digit RGB color string to normalized HSV."""
    red, green, blue = (channel / 255.0 for channel in rgb_hex_to_channels(color))
    return colorsys.rgb_to_hsv(red, green, blue)


def hsv_to_rgb_hex(hue: float, saturation: float, value: float) -> str:
    """Convert normalized HSV to a canonical lowercase RGB color string."""
    red, green, blue = colorsys.hsv_to_rgb(
        hue % 1.0,
        min(max(saturation, 0.0), 1.0),
        min(max(value, 0.0), 1.0),
    )
    channels = (round(channel * 255.0) for channel in (red, green, blue))
    return "#{:02x}{:02x}{:02x}".format(*channels)


def hsl_from_field_position(
    x: float, y: float, width: int, height: int, hue: float
) -> tuple[float, float, float]:
    """Map field position to hue, saturation and lightness."""
    return hue % 1.0, coordinate_to_unit(x, width), 1.0 - coordinate_to_unit(y, height)


def hsl_field_position(
    saturation: float, lightness: float, width: int, height: int
) -> tuple[float, float]:
    """Map saturation and lightness to a field position."""
    return unit_to_coordinate(saturation, width), unit_to_coordinate(
        1.0 - lightness, height
    )


def rgb_hex_to_hsl(color: str) -> tuple[float, float, float]:
    """Convert a six-digit RGB color string to normalized HSL."""
    red, green, blue = (channel / 255.0 for channel in rgb_hex_to_channels(color))
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    return hue, saturation, lightness


def hsl_to_rgb_hex(hue: float, saturation: float, lightness: float) -> str:
    """Convert normalized HSL to a canonical lowercase RGB color string."""
    red, green, blue = colorsys.hls_to_rgb(
        hue % 1.0,
        min(max(lightness, 0.0), 1.0),
        min(max(saturation, 0.0), 1.0),
    )
    channels = (round(channel * 255.0) for channel in (red, green, blue))
    return "#{:02x}{:02x}{:02x}".format(*channels)
