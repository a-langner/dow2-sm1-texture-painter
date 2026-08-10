"""Pure color conversion and coordinate helpers for the visual color picker."""

from __future__ import annotations

import colorsys


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
