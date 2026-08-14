from typing import TypeAlias

RGBColor: TypeAlias = tuple[int, int, int]
RecentColors: TypeAlias = tuple[RGBColor, ...]

MAX_RECENT_COLORS = 12


def add_recent_color(colors: RecentColors, color: RGBColor) -> RecentColors:
    """Return newest-first, duplicate-free confirmed colour history."""
    return (color,) + tuple(
        existing for existing in colors if existing != color
    )[: MAX_RECENT_COLORS - 1]


def validate_recent_colors(value: object) -> RecentColors:
    """Validate persisted RGB entries independently and preserve their order."""
    if not isinstance(value, list):
        return ()

    colors: list[RGBColor] = []
    for entry in value:
        if (
            not isinstance(entry, list)
            or len(entry) != 3
            or any(type(channel) is not int for channel in entry)
            or any(channel < 0 or channel > 255 for channel in entry)
        ):
            continue
        color = entry[0], entry[1], entry[2]
        if color not in colors:
            colors.append(color)
        if len(colors) == MAX_RECENT_COLORS:
            break
    return tuple(colors)
