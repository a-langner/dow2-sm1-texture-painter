"""Pure window-size and position policy for the application GUI."""

import re

from src.constant import FRAME_TOOL_HEIGHT

PATTERN_LIST_DEFAULT_WIDTH = 166
WINDOW_INITIAL_SCALE = 1.4
WINDOW_SCREEN_FRACTION = 0.9
WINDOW_CONTENT_PADDING = 16
TK_GEOMETRY_PATTERN = re.compile(
    r"^(?P<width>\d+)x(?P<height>\d+)(?P<x>[+-]\d+)(?P<y>[+-]\d+)$"
)


def calculate_initial_window_size(min_width, min_height, screen_width, screen_height):
    """Scale the initial size and keep it within a sensible screen area."""
    scaled_width = round(min_width * WINDOW_INITIAL_SCALE)
    scaled_height = round(min_height * WINDOW_INITIAL_SCALE)
    available_width = max(min_width, round(screen_width * WINDOW_SCREEN_FRACTION))
    available_height = max(min_height, round(screen_height * WINDOW_SCREEN_FRACTION))
    return min(scaled_width, available_width), min(scaled_height, available_height)


def calculate_diffuse_window_size(
    texture_width,
    texture_height,
    min_width,
    min_height,
    screen_width,
    screen_height,
):
    """Size two texture previews and the tools within the screen margin."""
    content_width = (
        texture_width * 2 + PATTERN_LIST_DEFAULT_WIDTH + WINDOW_CONTENT_PADDING
    )
    content_height = texture_height + FRAME_TOOL_HEIGHT + WINDOW_CONTENT_PADDING
    available_width = max(min_width, round(screen_width * WINDOW_SCREEN_FRACTION))
    available_height = max(min_height, round(screen_height * WINDOW_SCREEN_FRACTION))
    return (
        min(max(content_width, min_width), available_width),
        min(max(content_height, min_height), available_height),
    )


def clamp_window_position(
    current_x, current_y, window_width, window_height, screen_width, screen_height
):
    """Keep the resized window visible while retaining its position if possible."""
    return (
        min(max(current_x, 0), max(screen_width - window_width, 0)),
        min(max(current_y, 0), max(screen_height - window_height, 0)),
    )


def safe_window_geometry(
    geometry,
    min_width,
    min_height,
    desktop_x,
    desktop_y,
    desktop_width,
    desktop_height,
):
    """Return usable Tk geometry constrained to the current virtual desktop."""
    if not isinstance(geometry, str) or desktop_width <= 0 or desktop_height <= 0:
        return None
    match = TK_GEOMETRY_PATTERN.fullmatch(geometry)
    if match is None:
        return None

    width = min(max(int(match["width"]), min_width), desktop_width)
    height = min(max(int(match["height"]), min_height), desktop_height)
    x = min(
        max(int(match["x"]), desktop_x),
        desktop_x + desktop_width - width,
    )
    y = min(
        max(int(match["y"]), desktop_y),
        desktop_y + desktop_height - height,
    )
    return f"{width}x{height}{x:+d}{y:+d}"
