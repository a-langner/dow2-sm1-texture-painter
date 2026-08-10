"""Pure color conversion and coordinate helpers for the visual color picker."""

from __future__ import annotations

import colorsys


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
    value = color.removeprefix("#")
    if len(value) != 6:
        raise ValueError(f"Expected a six-digit RGB color, got {color!r}")
    red, green, blue = (int(value[index : index + 2], 16) / 255.0 for index in (0, 2, 4))
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
