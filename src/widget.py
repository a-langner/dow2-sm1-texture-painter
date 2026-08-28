import tkinter as tk
import logging
from tkinter.constants import HORIZONTAL
from tkinter import ttk
from tkinter import font as tkfont
from tkinter.ttk import Progressbar
import os
import math
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
import colorsys
from tkinter import filedialog
from functools import partial
from typing import Callable, Optional
from PIL import Image, ImageTk
from src.app_identity import APP_NAME, APP_VERSION
from src.color_pattern_handler import (
    PatternMarkerColor,
    get_all_patterns,
    get_pattern_marker_color,
    is_user_pattern,
)
from src.color_slot import ColorSlot
from src.color_slot_state import CustomFavoriteIdentity
from src.favorite_color import (
    CitadelFavoriteColor,
    CustomFavoriteColor,
    FavoriteColorLibrary,
    FavoritePaletteColor,
    resolve_exact_citadel_favorite,
)
from src.action_state import PatternActionContext, derive_pattern_action_state
from src.constant import (
    APP_SELECTION_BACKGROUND,
    APP_SELECTION_FOREGROUND,
    OPEN_FILETYPES,
    SAVE_EXT_LIST,
    ColorOps,
)
from src.blend_mode import IMPLEMENTED_BLEND_MODES
from src.paint_catalog import PaintCatalog, PaintColor, load_citadel_catalog
from src.paint_color_matching import ClosestPaintMatch, find_closest_paints
from src.platform_tools import open_url_in_default_browser
from src.processing_mode import ProcessingMode
from src.color_picker_visual import (
    ColorVisualizationMode,
    color_wheel_geometry,
    color_wheel_hue_from_position,
    color_wheel_hue_position,
    color_wheel_sv_from_position,
    color_wheel_sv_position,
    classic_hs_from_position,
    classic_hs_position,
    classic_value_from_position,
    classic_value_position,
    contrasting_text_color,
    hsl_field_position,
    hsl_from_field_position,
    hsl_to_rgb_hex,
    hsv_field_position,
    hsv_from_field_position,
    hsv_to_rgb_hex,
    hue_from_slider_position,
    hue_slider_position,
    normalize_rgb_hex,
    rgb_channels_to_hex,
    rgb_hex_to_channels,
    rgb_hex_to_hsl,
    rgb_hex_to_hsv,
)
from src.paint_color_analysis import (
    ColorGroup,
    PaletteSortMode,
    VISUAL_GROUP_ORDER,
    get_paints_for_group,
    sort_palette_paints,
)
from src.recent_colors import MAX_RECENT_COLORS, RecentColors, add_recent_color
from src.render_settings import (
    MAX_BRIGHTNESS,
    MAX_CONTRAST,
    MAX_OPACITY,
    MAX_SATURATION,
    MIN_BRIGHTNESS,
    MIN_CONTRAST,
    MIN_OPACITY,
    MIN_SATURATION,
)
from src.window_geometry import safe_window_geometry, safe_window_position
from src.update_check import (
    UPDATE_FAILURE_MESSAGE,
    UpdateCheckResult,
    UpdateStatus,
    check_for_updates,
)

ABOUT_DESCRIPTION = (
    "A GUI application for easily colorizing Dawn of War II and "
    "Warhammer 40,000: Space Marine textures."
)
ABOUT_MAINTAINER = "a-langner (Andreas Langner)"
ABOUT_ORIGINAL_AUTHOR = "Jaccouille (Marc Szilagyi)"
ABOUT_CITADEL_ATTRIBUTION = "Arcturus5404/miniature-paints — MIT License"
ABOUT_MAINTAINER_URL = "https://github.com/a-langner/dow2-sm1-texture-painter"
ABOUT_ORIGINAL_AUTHOR_URL = "https://github.com/Jaccouille/dow2-texture-painter"
ABOUT_CITADEL_DATA_URL = "https://github.com/Arcturus5404/miniature-paints"
ABOUT_LICENSE = "Army Painter is licensed under the MIT License."
ABOUT_DISCLAIMER = (
    "Army Painter is an unofficial community tool and is not affiliated with, "
    "endorsed by, or associated with Games Workshop, Citadel, Relic "
    "Entertainment, or their respective owners."
)
ABOUT_LINK_EXTRA_BOTTOM_GAP = 8

COLOR_BOX_SIZE = 90
COLOR_BTN_HEIGHT = 26
PATTERN_MARKER_COLUMN_WIDTH = 28
PATTERN_DRAG_THRESHOLD = 6
PATTERN_MARKER_COLORS = {
    PatternMarkerColor.YELLOW: ("#efd80e", "#ffd864"),
    PatternMarkerColor.RED: ("#e92525", "#f74d4d"),
    PatternMarkerColor.GREEN: ("#17D443", "#61d378"),
    PatternMarkerColor.BLUE: ("#1b77df", "#76bdfe"),
    PatternMarkerColor.PURPLE: ("#9d19d5", "#c057f0"),
}
DEFAULT_PATTERN_MARKER_COLORS = ("#202020", "#505050")
HEADER_SEPARATOR_STARTUP_RETRIES = 3
COLOR_PICKER_DEFAULT_WIDTH = 1196
COLOR_PICKER_DEFAULT_HEIGHT = 760
COLOR_PICKER_SCREEN_MARGIN = 80
COLOR_PICKER_GROUP_PANE_WIDTH = 140
COLOR_PICKER_PALETTE_PANE_WIDTH = 636
COLOR_PICKER_EDITOR_PANE_WIDTH = 400
class PaletteSpecialGroup(Enum):
    """Stable identities for navigation groups outside color families."""

    FAVORITES = "favorites"


COLOR_PICKER_GROUP_ENTRIES = (
    (PaletteSpecialGroup.FAVORITES, "★ Favorites"),
    (None, "🌈 All Colors"),
) + tuple(
    (color_group, color_group.value) for color_group in VISUAL_GROUP_ORDER
)
COLOR_GROUP_INDICATORS = {
    ColorGroup.RED: "#d32f2f",
    ColorGroup.ORANGE: "#f57c00",
    ColorGroup.YELLOW: "#fbc02d",
    ColorGroup.GREEN: "#388e3c",
    ColorGroup.TEAL_CYAN: "#0097a7",
    ColorGroup.BLUE: "#1976d2",
    ColorGroup.PURPLE: "#7b1fa2",
    ColorGroup.PINK: "#d81b60",
    ColorGroup.BROWN: "#795548",
    ColorGroup.NEUTRAL: "#757575",
}
ALL_COLOR_INDICATORS = (
    "#d32f2f",
    "#f57c00",
    "#fbc02d",
    "#388e3c",
    "#1976d2",
    "#7b1fa2",
)
COLOR_SPACE_MODES = (
    ColorVisualizationMode.HSV_HSB.value,
    ColorVisualizationMode.HSL.value,
    ColorVisualizationMode.COLOR_WHEEL.value,
    ColorVisualizationMode.CLASSIC.value,
)
DEFAULT_COLOR_SPACE_MODE = COLOR_SPACE_MODES[0]
PALETTE_SORT_DISPLAY_NAMES = tuple(mode.display_name for mode in PaletteSortMode)
PAINT_SWATCH_TARGET_WIDTH = 96
PAINT_SWATCH_PREVIEW_SIZE = 60
PAINT_SWATCH_NAME_WRAP = 88
PAINT_SWATCH_CORNER_RADIUS = 20
PAINT_NAME_ELLIPSIS = "…"
PAINT_SEARCH_PLACEHOLDER = "Search Citadel colors..."
NO_CITADEL_COLORS_MESSAGE = "No Citadel colors found."
NO_FAVORITE_COLORS_MESSAGE = "No favorite colors yet."
PAINT_TOOLTIP_DELAY_MS = 400
COLOR_PREVIEW_BORDER = "#707070"
COLOR_EDITOR_SECTION_GAP = 8
COLOR_EDITOR_GROUP_PADDING = (8, 6)
COLOR_MODEL_GROUP_PADDING = (4, 6)
COLOR_MODEL_CONTROL_WIDTH = 3
PAINT_SWATCH_OUTLINE = "#606060"
PAINT_SWATCH_SELECTED_OUTLINE = APP_SELECTION_BACKGROUND
FAVORITE_STAR_COLOR = "#E6B800"
FAVORITE_STAR_MARGIN = 3
FAVORITE_GROUP_INDICATOR_BACKGROUND = "#FFFFFF"


def calculate_centered_five_point_star(
    center_x: float,
    center_y: float,
    outer_radius: float,
) -> tuple[float, ...]:
    """Return a regular five-point star centered by its visible bounds."""
    inner_radius = outer_radius * ((3 - math.sqrt(5)) / 2)
    coordinates: list[float] = []
    for index in range(10):
        radius = outer_radius if index % 2 == 0 else inner_radius
        angle = -math.pi / 2 + index * math.pi / 5
        coordinates.extend((radius * math.cos(angle), radius * math.sin(angle)))
    xs = coordinates[0::2]
    ys = coordinates[1::2]
    offset_x = center_x - (min(xs) + max(xs)) / 2
    offset_y = center_y - (min(ys) + max(ys)) / 2
    return tuple(
        coordinate + (offset_x if index % 2 == 0 else offset_y)
        for index, coordinate in enumerate(coordinates)
    )


FAVORITE_GROUP_STAR_POINTS = calculate_centered_five_point_star(7, 7, 5)
COLOR_SLOT_DROP_TARGET_OUTLINE = "#00a6d6"
COLOR_SLOT_DRAG_THRESHOLD = 6
COLOR_SLOT_DRAG_GHOST_ALPHA = 0.65
COLOR_SLOT_DRAG_GHOST_OFFSET = 12
COLOR_FIELD_PREFERRED_HEIGHT = 240
VISUAL_RESIZE_DELAY_MS = 40
APP_COMBOBOX_STYLE = "AppSelection.TCombobox"
APP_ENTRY_STYLE = "AppSelection.TEntry"
APP_SPINBOX_STYLE = "AppSelection.TSpinbox"

ActionCallback = Callable[[], None]
PatternMarkerCallback = Callable[[str, PatternMarkerColor], object]
PatternReorderCallback = Callable[[str, int], object]
AvailabilityCallback = Callable[[], bool]
BooleanChangedCallback = Callable[[bool], None]
ColorChangedCallback = Callable[[int, str], None]
ColorSlotSelectedCallback = Callable[[int], None]
ColorSlotActionCallback = Callable[[int], object]
ColorSlotsSwappedCallback = Callable[[int, int], object]
ColorPickerCallback = Callable[[str], Optional[str]]
PaintSelectedCallback = Callable[[PaintColor], None]
PaintFavoriteLabelCallback = Callable[[PaintColor], Optional[str]]
PaintFavoriteToggleCallback = Callable[[PaintColor], object]
PaintFavoriteCheckCallback = Callable[[PaintColor], bool]
CustomFavoriteActionCallback = Callable[[FavoritePaletteColor], object]
RecentColorSelectedCallback = Callable[[str], None]
LevelsChangedCallback = Callable[[float, float, float, float], None]
StringChangedCallback = Callable[[str], None]
LOGGER = logging.getLogger(__name__)


class SelectedColor(str):
    """String-compatible picker result with optional stable slot metadata."""

    custom_favorite: CustomFavoriteIdentity | None

    def __new__(
        cls,
        color: str,
        custom_favorite: CustomFavoriteIdentity | None = None,
    ) -> "SelectedColor":
        instance = str.__new__(cls, color)
        instance.custom_favorite = custom_favorite
        return instance


class ColorSlotDragGhost:
    """Own the short-lived borderless window used for slot drag feedback."""

    def __init__(
        self,
        master: tk.Misc,
        slot_index: int,
        color: str,
        transient_owner: Optional[tk.Misc] = None,
    ):
        normalized_color = normalize_rgb_hex(color)
        self._window = tk.Toplevel(master, takefocus=False)
        self._window.withdraw()
        self._window.wm_overrideredirect(True)
        self.content = tk.Frame(
            self._window,
            width=COLOR_BOX_SIZE,
            height=COLOR_BOX_SIZE,
            bg=normalized_color,
            bd=2,
            relief=tk.RAISED,
            highlightthickness=2,
            highlightbackground=PAINT_SWATCH_SELECTED_OUTLINE,
        )
        self.content.pack(fill=tk.BOTH, expand=True)
        self.content.pack_propagate(False)
        tk.Label(
            self.content,
            text=f"Color {slot_index + 1}\n{normalized_color}",
            bg=normalized_color,
            fg=contrasting_text_color(normalized_color),
            font=("Arial", 10, "bold"),
            justify=tk.CENTER,
            bd=0,
        ).place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        if transient_owner is not None:
            try:
                self._window.transient(transient_owner)
            except tk.TclError:
                pass
        try:
            self._window.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            self._window.attributes("-alpha", COLOR_SLOT_DRAG_GHOST_ALPHA)
        except tk.TclError:
            # Opaque drag feedback is preferable to disabling dragging on a
            # window manager that does not implement per-window alpha.
            pass
        try:
            self._window.attributes("-disabled", True)
        except tk.TclError:
            # Not all Tk window managers expose the Windows disabled flag.
            pass

    def show_at_pointer(self, pointer_x: int, pointer_y: int) -> None:
        """Show the ghost beside a pointer expressed in screen coordinates."""
        self.move_to_pointer(pointer_x, pointer_y)
        self._window.deiconify()
        self._window.lift()

    def move_to_pointer(self, pointer_x: int, pointer_y: int) -> None:
        """Keep the existing ghost offset from the screen-coordinate pointer."""
        ghost_x = pointer_x + COLOR_SLOT_DRAG_GHOST_OFFSET
        ghost_y = pointer_y + COLOR_SLOT_DRAG_GHOST_OFFSET
        self._window.geometry(f"+{ghost_x}+{ghost_y}")

    def destroy(self) -> None:
        """Destroy the ghost window; repeated cleanup is harmless."""
        window = self._window
        self._window = None
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass


def configure_app_selection_styles(widget: tk.Misc) -> None:
    """Apply the shared accent to explicit app text-selection surfaces."""
    style = ttk.Style(widget)
    for style_name in (APP_ENTRY_STYLE, APP_SPINBOX_STYLE):
        style.configure(
            style_name,
            selectbackground=APP_SELECTION_BACKGROUND,
            selectforeground=APP_SELECTION_FOREGROUND,
        )
    style.configure(
        APP_COMBOBOX_STYLE,
        selectbackground=APP_SELECTION_BACKGROUND,
        selectforeground=APP_SELECTION_FOREGROUND,
    )
    style.map(
        APP_COMBOBOX_STYLE,
        selectbackground=[
            ("readonly focus", APP_SELECTION_BACKGROUND),
            ("focus", APP_SELECTION_BACKGROUND),
            ("readonly", APP_SELECTION_BACKGROUND),
        ],
        selectforeground=[
            ("readonly focus", APP_SELECTION_FOREGROUND),
            ("focus", APP_SELECTION_FOREGROUND),
            ("readonly", APP_SELECTION_FOREGROUND),
        ],
    )
    widget.option_add(
        "*TCombobox*Listbox.selectBackground",
        APP_SELECTION_BACKGROUND,
    )
    widget.option_add(
        "*TCombobox*Listbox.selectForeground",
        APP_SELECTION_FOREGROUND,
    )


def clear_readonly_combobox_text_selection(combobox: ttk.Combobox) -> None:
    """Suppress the native inner text highlight on readonly Comboboxes."""

    def clear_selection(Event=None) -> None:
        def clear_after_idle() -> None:
            try:
                combobox.selection_clear()
            except tk.TclError:
                pass

        try:
            combobox.after_idle(clear_after_idle)
        except tk.TclError:
            pass

    combobox.bind("<FocusIn>", clear_selection, add="+")
    combobox.bind("<<ComboboxSelected>>", clear_selection, add="+")


def show_readonly_combobox_value(combobox: ttk.Combobox, value: str) -> None:
    """Set and repaint a readonly Combobox value before user interaction."""
    combobox.configure(state="normal")
    combobox.set(value)
    combobox.configure(state="readonly")


@dataclass(frozen=True)
class PatternSelection:
    name: str
    is_user: bool


@dataclass(frozen=True)
class PaintSwatchPresentation:
    name: str
    color: str


@dataclass(frozen=True)
class ColorSlotPresentation:
    text: str
    foreground: str
    tooltip: Optional[str]


def calculate_paint_swatch_columns(
    available_width: int,
    target_width: int = PAINT_SWATCH_TARGET_WIDTH,
) -> int:
    """Return a responsive column count without requiring horizontal scrolling."""
    return max(1, available_width // target_width)


def calculate_paint_swatch_cell_bounds(
    available_width: int,
    column_count: int,
    column: int,
) -> tuple[int, int]:
    """Partition a responsive row into device-aligned canvas coordinates."""
    return (
        column * available_width // column_count,
        (column + 1) * available_width // column_count,
    )


def paint_swatch_presentation(paint: PaintColor) -> PaintSwatchPresentation:
    """Preserve a paint's complete name and exact RGB display value."""
    return PaintSwatchPresentation(
        name=paint.name,
        color=f"#{paint.r:02x}{paint.g:02x}{paint.b:02x}",
    )


def filter_paints_by_name(paints, query: str) -> tuple[PaintColor, ...]:
    """Return case-insensitive complete-name substring matches in input order."""
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return tuple(paints)
    return tuple(
        paint for paint in paints if normalized_query in paint.name.casefold()
    )


def format_visible_paint_count(count: int) -> str:
    return f"{count} color" if count == 1 else f"{count} colors"


def paint_tooltip_text(paint: PaintColor) -> str:
    return f"{paint.name}\nRGB: {paint.r}, {paint.g}, {paint.b}"


def recent_color_tooltip_text(color, paint_catalog: PaintCatalog) -> str:
    """Describe an RGB history entry, including an exact catalog match."""
    hex_color = normalize_rgb_hex(rgb_channels_to_hex(*color))
    paint = paint_catalog.find_exact_rgb(color)
    rgb_text = f"RGB: {color[0]}, {color[1]}, {color[2]}"
    if paint is not None:
        return f"{paint.name}\n{hex_color}\n{rgb_text}"
    return f"{hex_color}\n{rgb_text}"


def _longest_fitting_prefix(
    text: str, max_width: float, measure: Callable[[str], int]
) -> str:
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if measure(text[:middle]) <= max_width:
            low = middle
        else:
            high = middle - 1
    return text[:low]


def format_paint_name_for_swatch(
    name: str, max_width: float, measure: Callable[[str], int]
) -> str:
    """Fit a paint name into at most two measured display lines."""
    if measure(name) <= max_width:
        return name

    words = name.split()
    first_line = ""
    consumed_words = 0
    for index, word in enumerate(words):
        candidate = f"{first_line} {word}".strip()
        if measure(candidate) > max_width:
            break
        first_line = candidate
        consumed_words = index + 1

    if not first_line:
        first_line = _longest_fitting_prefix(name, max_width, measure)
        remainder = name[len(first_line) :].lstrip()
    else:
        remainder = " ".join(words[consumed_words:])
    if not remainder:
        return first_line
    if measure(remainder) <= max_width:
        return f"{first_line}\n{remainder}"

    available_width = max(0.0, max_width - measure(PAINT_NAME_ELLIPSIS))
    second_line = _longest_fitting_prefix(
        remainder, available_width, measure
    ).rstrip()
    return f"{first_line}\n{second_line}{PAINT_NAME_ELLIPSIS}"


def color_slot_presentation(
    color: str,
    paint_catalog: PaintCatalog,
    max_width: float,
    measure: Callable[[str], int],
    custom_favorite: CustomFavoriteIdentity | None = None,
) -> ColorSlotPresentation:
    """Return main-window text and exact-match details for one colour slot."""
    normalized = normalize_rgb_hex(color)
    channels = rgb_hex_to_channels(normalized)
    paint = paint_catalog.find_exact_rgb(channels)
    if paint is None and custom_favorite is not None:
        return ColorSlotPresentation(
            text=format_paint_name_for_swatch(
                custom_favorite.name, max_width, measure
            ),
            foreground=contrasting_text_color(normalized),
            tooltip=(
                f"{custom_favorite.name}\n{normalized}\n"
                f"RGB: {channels[0]}, {channels[1]}, {channels[2]}"
            ),
        )
    if paint is None:
        return ColorSlotPresentation(
            text=normalized,
            foreground=contrasting_text_color(normalized),
            tooltip=None,
        )
    return ColorSlotPresentation(
        text=format_paint_name_for_swatch(paint.name, max_width, measure),
        foreground=contrasting_text_color(normalized),
        tooltip=(
            f"{paint.name}\n{normalized}\n"
            f"RGB: {channels[0]}, {channels[1]}, {channels[2]}"
        ),
    )


def draw_rounded_swatch(
    canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    fill: str,
    outline: str,
    width: int,
    corner_radius: float = PAINT_SWATCH_CORNER_RADIUS,
) -> int:
    """Draw one subtly rounded canvas swatch and return its item id."""
    radius = min(corner_radius, (x2 - x1) / 2, (y2 - y1) / 2)
    return canvas.create_polygon(
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
        fill=fill,
        outline=outline,
        width=width,
        smooth=True,
        splinesteps=20,
        tags="paint",
    )


RECENT_COLOR_SWATCH_SIZE = 24
RECENT_COLOR_SWATCH_GAP = 4
RECENT_COLOR_SWATCH_CORNER_RADIUS = 4
RECENT_COLOR_ROW_HEIGHT = RECENT_COLOR_SWATCH_SIZE + RECENT_COLOR_SWATCH_GAP


class RecentColorSwatchRow(ttk.Frame):
    """Compact confirmed-colour history with click and tooltip interaction."""

    def __init__(
        self,
        parent,
        *,
        colors: RecentColors,
        paint_catalog: PaintCatalog,
        on_color_selected: RecentColorSelectedCallback,
    ) -> None:
        super().__init__(parent)
        configure_app_selection_styles(self)
        self.colors = colors[:MAX_RECENT_COLORS]
        self.paint_catalog = paint_catalog
        self._on_color_selected = on_color_selected
        self._regions = []
        self._hovered_index = None
        self._tooltip_after_id = None
        self._tooltip_window = None
        self._tooltip_root_position = (0, 0)

        ttk.Label(self, text="Recent Colors").pack(anchor=tk.W)
        self.canvas = tk.Canvas(
            self,
            height=RECENT_COLOR_ROW_HEIGHT if colors else 1,
            bd=0,
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.X)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        self._draw_swatches()

    def _draw_swatches(self) -> None:
        self.canvas.delete("all")
        self._regions = []
        for index, color in enumerate(self.colors):
            x1 = index * (RECENT_COLOR_SWATCH_SIZE + RECENT_COLOR_SWATCH_GAP) + 1
            y1 = 1
            x2 = x1 + RECENT_COLOR_SWATCH_SIZE
            y2 = y1 + RECENT_COLOR_SWATCH_SIZE
            hovered = index == self._hovered_index
            draw_rounded_swatch(
                self.canvas,
                x1,
                y1,
                x2,
                y2,
                fill=rgb_channels_to_hex(*color),
                outline=(
                    PAINT_SWATCH_SELECTED_OUTLINE
                    if hovered
                    else COLOR_PREVIEW_BORDER
                ),
                width=2 if hovered else 1,
                corner_radius=RECENT_COLOR_SWATCH_CORNER_RADIUS,
            )
            self._regions.append((x1, y1, x2, y2))

    def _index_at(self, x: float, y: float) -> Optional[int]:
        for index, (x1, y1, x2, y2) in enumerate(self._regions):
            if x1 <= x <= x2 and y1 <= y <= y2:
                return index
        return None

    def _on_click(self, Event) -> None:
        index = self._index_at(Event.x, Event.y)
        if index is not None:
            self._on_color_selected(rgb_channels_to_hex(*self.colors[index]))

    def _on_motion(self, Event) -> None:
        index = self._index_at(Event.x, Event.y)
        self._tooltip_root_position = (Event.x_root, Event.y_root)
        if index == self._hovered_index:
            return
        self._hide_tooltip()
        self._hovered_index = index
        self._draw_swatches()
        self.canvas.configure(cursor="hand2" if index is not None else "")
        if index is not None:
            self._tooltip_after_id = self.after(
                PAINT_TOOLTIP_DELAY_MS,
                partial(self._show_tooltip, index),
            )

    def _on_leave(self, Event=None) -> None:
        self._hovered_index = None
        self.canvas.configure(cursor="")
        self._draw_swatches()
        self._hide_tooltip()

    def _show_tooltip(self, index: int) -> None:
        self._tooltip_after_id = None
        root_x, root_y = self._tooltip_root_position
        tooltip = tk.Toplevel(self)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{root_x + 20}+{root_y + 20}")
        tk.Label(
            tooltip,
            text=recent_color_tooltip_text(self.colors[index], self.paint_catalog),
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            padx=5,
            pady=3,
        ).pack()
        self._tooltip_window = tooltip

    def _hide_tooltip(self) -> None:
        if self._tooltip_after_id is not None:
            self.after_cancel(self._tooltip_after_id)
            self._tooltip_after_id = None
        if self._tooltip_window is not None:
            self._tooltip_window.destroy()
            self._tooltip_window = None


class PaintSwatchGrid(ttk.Frame):
    """Vertically scrollable canvas grid that reflows paints on resize."""

    def __init__(
        self,
        parent,
        *,
        on_paint_selected: PaintSelectedCallback,
        favorite_action_label: Optional[PaintFavoriteLabelCallback] = None,
        is_paint_favorite: Optional[PaintFavoriteCheckCallback] = None,
        on_favorite_toggled: Optional[PaintFavoriteToggleCallback] = None,
        on_custom_favorite_renamed: Optional[CustomFavoriteActionCallback] = None,
        on_custom_favorite_removed: Optional[CustomFavoriteActionCallback] = None,
    ):
        super().__init__(parent)
        self._on_paint_selected = on_paint_selected
        self._favorite_action_label = favorite_action_label
        self._is_paint_favorite = is_paint_favorite
        self._on_favorite_toggled = on_favorite_toggled
        self._on_custom_favorite_renamed = on_custom_favorite_renamed
        self._on_custom_favorite_removed = on_custom_favorite_removed
        self.paints = ()
        self.empty_message = NO_CITADEL_COLORS_MESSAGE
        self.selected_paint_id = None
        self._paint_regions = []
        self._truncated_paint_ids = set()
        self._hovered_paint = None
        self._tooltip_root_position = (0, 0)
        self._column_count = 1
        self._configured_column_count = 0
        self._relayout_after_id = None
        self._tooltip_after_id = None
        self._tooltip_window = None
        self._paint_name_font = tkfont.Font(
            root=self,
            name="TkDefaultFont",
            exists=True,
        )

        self.vertical_scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.vertical_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(
            self,
            bd=0,
            highlightthickness=1,
            highlightbackground="#707070",
            highlightcolor="#2f80ed",
            takefocus=True,
            yscrollcommand=self.vertical_scrollbar.set,
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vertical_scrollbar.configure(command=self.canvas.yview)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Up>", partial(self._on_scroll_key, -1, "units"))
        self.canvas.bind("<Down>", partial(self._on_scroll_key, 1, "units"))
        self.canvas.bind("<Prior>", partial(self._on_scroll_key, -1, "pages"))
        self.canvas.bind("<Next>", partial(self._on_scroll_key, 1, "pages"))
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Button-3>", self._on_canvas_context_menu)
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<Leave>", self._on_canvas_leave)

    def _on_scroll_key(self, amount: int, what: str, Event=None) -> str:
        self.canvas.yview_scroll(amount, what)
        return "break"

    def set_paints(self, paints) -> None:
        paints = tuple(paints)
        if paints == self.paints:
            return
        self.paints = paints
        self._rebuild_items()

    def set_empty_message(self, message: str) -> None:
        """Set the contextual message used when the current data source is empty."""
        if message == self.empty_message:
            return
        self.empty_message = message
        if not self.paints:
            self._rebuild_items()

    def _rebuild_items(self) -> None:
        self._hide_tooltip()
        self._schedule_relayout()

    def _select_paint(self, paint: PaintColor, Event=None) -> None:
        self._on_paint_selected(paint)

    def set_selected_paint(self, paint_id: Optional[str]) -> None:
        self.selected_paint_id = paint_id
        self._apply_selection_highlight()

    def refresh_favorite_indicators(self) -> None:
        """Redraw stars when Favorite membership changes without new paints."""
        self._schedule_relayout()

    def _apply_selection_highlight(self) -> None:
        self._schedule_relayout()

    def _on_canvas_configure(self, Event) -> None:
        column_count = calculate_paint_swatch_columns(Event.width)
        if column_count != self._column_count:
            self._column_count = column_count
            self._schedule_relayout()

    def _schedule_relayout(self) -> None:
        if self._relayout_after_id is None:
            self._relayout_after_id = self.after_idle(self._relayout)

    def _relayout(self) -> None:
        self._relayout_after_id = None
        width = self.canvas.winfo_width()
        if width <= 1:
            return
        self.canvas.delete("paint")
        self._paint_regions = []
        self._truncated_paint_ids = set()
        self._configured_column_count = self._column_count
        if not self.paints:
            self.canvas.create_text(
                width / 2,
                24,
                text=self.empty_message,
                anchor=tk.N,
                tags="paint",
            )
            self.canvas.configure(scrollregion=(0, 0, width, 64))
            return

        line_height = self._paint_name_font.metrics("linespace")
        row_height = PAINT_SWATCH_PREVIEW_SIZE + 16 + 2 * line_height
        for index, paint in enumerate(self.paints):
            row, column = divmod(index, self._column_count)
            cell_x1, cell_x2 = calculate_paint_swatch_cell_bounds(
                width, self._column_count, column
            )
            x1 = cell_x1 + 2
            y1 = row * row_height + 2
            x2 = cell_x2 - 2
            y2 = y1 + row_height - 4
            selected = paint.id == self.selected_paint_id
            outline = PAINT_SWATCH_SELECTED_OUTLINE if selected else ""
            self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline=outline,
                width=3 if selected else 0,
                tags="paint",
            )
            preview_x1 = (x1 + x2 - PAINT_SWATCH_PREVIEW_SIZE) // 2
            preview_y1 = y1 + 4
            draw_rounded_swatch(
                self.canvas,
                preview_x1,
                preview_y1,
                preview_x1 + PAINT_SWATCH_PREVIEW_SIZE,
                preview_y1 + PAINT_SWATCH_PREVIEW_SIZE,
                fill=paint_swatch_presentation(paint).color,
                outline=(
                    PAINT_SWATCH_SELECTED_OUTLINE
                    if selected
                    else PAINT_SWATCH_OUTLINE
                ),
                width=3 if selected else 1,
            )
            favorite_check = getattr(self, "_is_paint_favorite", None)
            if favorite_check is not None and favorite_check(paint):
                self.canvas.create_text(
                    preview_x1 + PAINT_SWATCH_PREVIEW_SIZE - FAVORITE_STAR_MARGIN,
                    preview_y1 + FAVORITE_STAR_MARGIN,
                    text="★",
                    fill=FAVORITE_STAR_COLOR,
                    font=("TkDefaultFont", 12, "bold"),
                    anchor=tk.NE,
                    tags="paint",
                )
            name_width = min(PAINT_SWATCH_NAME_WRAP, max(1, x2 - x1 - 4))
            display_name = format_paint_name_for_swatch(
                paint.name,
                name_width,
                self._paint_name_font.measure,
            )
            if PAINT_NAME_ELLIPSIS in display_name:
                self._truncated_paint_ids.add(paint.id)
            self.canvas.create_text(
                (x1 + x2) / 2,
                preview_y1 + PAINT_SWATCH_PREVIEW_SIZE + 4,
                text=display_name,
                font=self._paint_name_font,
                anchor=tk.N,
                justify=tk.CENTER,
                tags="paint",
            )
            self._paint_regions.append((paint, x1, y1, x2, y2))
        rows = (len(self.paints) + self._column_count - 1) // self._column_count
        self.canvas.configure(scrollregion=(0, 0, width, rows * row_height))

    def _paint_at(self, x: float, y: float) -> Optional[PaintColor]:
        canvas_y = self.canvas.canvasy(y)
        for paint, x1, y1, x2, y2 in self._paint_regions:
            if x1 <= x <= x2 and y1 <= canvas_y <= y2:
                return paint
        return None

    def _on_canvas_click(self, Event) -> None:
        paint = self._paint_at(Event.x, Event.y)
        if paint is not None:
            self._select_paint(paint)

    def _on_canvas_context_menu(self, Event) -> None:
        """Open the exact hit tile's Favorite action without selecting it."""
        paint = self._paint_at(Event.x, Event.y)
        if paint is None:
            return
        if (
            isinstance(paint, FavoritePaletteColor)
            and isinstance(paint.favorite, CustomFavoriteColor)
            and self._on_custom_favorite_renamed is not None
            and self._on_custom_favorite_removed is not None
        ):
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(
                label="Rename Favorite...",
                command=partial(self._on_custom_favorite_renamed, paint),
            )
            menu.add_command(
                label="Remove from Favorites",
                command=partial(self._on_custom_favorite_removed, paint),
            )
            try:
                menu.tk_popup(Event.x_root, Event.y_root)
            finally:
                menu.grab_release()
            return
        if self._favorite_action_label is None or self._on_favorite_toggled is None:
            return
        label = self._favorite_action_label(paint)
        if label is None:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label=label,
            command=partial(self._on_favorite_toggled, paint),
        )
        try:
            menu.tk_popup(Event.x_root, Event.y_root)
        finally:
            menu.grab_release()

    def _on_canvas_motion(self, Event) -> None:
        paint = self._paint_at(Event.x, Event.y)
        self._tooltip_root_position = (Event.x_root, Event.y_root)
        if paint is self._hovered_paint:
            return
        self._hide_tooltip()
        self._hovered_paint = paint
        if paint is not None and paint.id in self._truncated_paint_ids:
            self._schedule_tooltip(paint, Event)

    def _on_canvas_leave(self, Event=None) -> None:
        self._hovered_paint = None
        self._hide_tooltip()

    def _on_mousewheel(self, Event):
        self.canvas.yview_scroll(int(-Event.delta / 120), "units")
        return "break"

    def _schedule_tooltip(self, paint: PaintColor, Event) -> None:
        self._hide_tooltip()
        self._tooltip_root_position = (Event.x_root, Event.y_root)
        self._tooltip_after_id = self.after(
            PAINT_TOOLTIP_DELAY_MS,
            partial(self._show_tooltip, paint),
        )

    def _show_tooltip(self, paint: PaintColor) -> None:
        self._tooltip_after_id = None
        root_x, root_y = self._tooltip_root_position
        tooltip = tk.Toplevel(self)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{root_x + 20}+{root_y + 20}")
        tk.Label(
            tooltip,
            text=paint_tooltip_text(paint),
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            padx=5,
            pady=3,
        ).pack()
        self._tooltip_window = tooltip

    def _hide_tooltip(self, Event=None) -> None:
        if self._tooltip_after_id is not None:
            self.after_cancel(self._tooltip_after_id)
            self._tooltip_after_id = None
        if self._tooltip_window is not None:
            self._tooltip_window.destroy()
            self._tooltip_window = None


class AboutDialog(tk.Toplevel):
    """Compact application identity, credits, and update entry point."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.settings = getattr(parent, "settings", None)
        self._update_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="about-update-check",
        )
        self._update_future: Future[UpdateCheckResult] | None = None
        self._update_poll_after_id: str | None = None
        self.title(f"About {APP_NAME}")
        self.transient(parent)
        self.resizable(False, False)

        content = ttk.Frame(self, padding=16)
        content.pack(fill=tk.BOTH, expand=True)
        self._about_link_font = tkfont.Font(self, font="TkDefaultFont")
        self._about_link_font.configure(underline=False)
        ttk.Label(
            content,
            text=f"{APP_NAME} {APP_VERSION}",
            font=("TkDefaultFont", 14, "bold"),
        ).pack(pady=(0, ABOUT_LINK_EXTRA_BOTTOM_GAP))
        ttk.Label(
            content,
            text=ABOUT_DESCRIPTION,
            justify=tk.CENTER,
            wraplength=410,
        ).pack(pady=(10, 14))

        ttk.Label(content, text="Developed and maintained by:").pack()
        self.maintainer_label = self._create_link_label(
            content,
            ABOUT_MAINTAINER,
            ABOUT_MAINTAINER_URL,
        )
        self.maintainer_label.pack(
            pady=(1, 10 + ABOUT_LINK_EXTRA_BOTTOM_GAP)
        )

        ttk.Label(content, text="Based on the original application by:").pack()
        self.original_author_label = self._create_link_label(
            content,
            ABOUT_ORIGINAL_AUTHOR,
            ABOUT_ORIGINAL_AUTHOR_URL,
        )
        self.original_author_label.pack(
            pady=(1, 10 + ABOUT_LINK_EXTRA_BOTTOM_GAP)
        )

        ttk.Label(content, text="Citadel color data:").pack()
        attribution_row = ttk.Frame(content)
        attribution_row.pack(
            pady=(1, 14 + ABOUT_LINK_EXTRA_BOTTOM_GAP)
        )
        self.citadel_attribution_label = self._create_link_label(
            attribution_row,
            "Arcturus5404/miniature-paints",
            ABOUT_CITADEL_DATA_URL,
        )
        self.citadel_attribution_label.pack(side=tk.LEFT)
        ttk.Label(attribution_row, text=" — MIT License").pack(side=tk.LEFT)

        ttk.Label(
            content,
            text=ABOUT_DISCLAIMER,
            justify=tk.CENTER,
            wraplength=410,
            foreground="#606060",
        ).pack(pady=(0, 12))
        ttk.Label(
            content,
            text=ABOUT_LICENSE,
            foreground="#606060",
        ).pack(pady=(0, 12))
        ttk.Label(content, text=f"Version {APP_VERSION}").pack()

        self.update_button = ttk.Button(
            content,
            text="Check for Updates",
            command=self.request_update_check,
        )
        self.update_button.pack(pady=(12, 0))
        self.update_check_in_progress = False
        self.update_status_label = ttk.Label(content, text="", justify=tk.CENTER)
        self.update_status_label.pack(pady=(8, 0))
        self.update_download_url: str | None = None
        self.download_button = ttk.Button(
            content,
            text="Open Download Page",
            command=self.open_update_download_page,
        )

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", self.close)
        self._restore_position()
        self.grab_set()
        self.wait_window()

    @classmethod
    def show(cls, parent: tk.Misc) -> None:
        cls(parent)

    def _create_link_label(
        self,
        parent: tk.Misc,
        text: str,
        url: str,
    ) -> ttk.Label:
        label = ttk.Label(
            parent,
            text=text,
            foreground="#0563C1",
            cursor="hand2",
            font=self._about_link_font,
            takefocus=True,
        )
        label.bind("<Button-1>", lambda Event: self.open_link(url))
        label.bind("<Return>", lambda Event: self.open_link(url))
        return label

    @staticmethod
    def open_link(url: str) -> None:
        try:
            open_url_in_default_browser(url)
        except (OSError, ValueError):
            LOGGER.exception("Could not open About link: %s", url)

    def request_update_check(self) -> bool:
        """Begin one manual request and reject simultaneous duplicates."""
        if self.update_check_in_progress:
            return False
        self.update_check_in_progress = True
        self.update_button.configure(state=tk.DISABLED)
        self.update_status_label.configure(text="Checking...")
        self.update_download_url = None
        self.download_button.pack_forget()
        self._start_update_check()
        return True

    def _start_update_check(self) -> None:
        self._update_future = self._update_executor.submit(check_for_updates)
        self._schedule_update_poll()

    def _schedule_update_poll(self) -> None:
        self._update_poll_after_id = self.after(50, self._poll_update_result)

    def _poll_update_result(self) -> None:
        self._update_poll_after_id = None
        future = self._update_future
        if future is None:
            return
        if not future.done():
            self._schedule_update_poll()
            return
        self._update_future = None
        try:
            result = future.result()
        except Exception:
            LOGGER.exception("Unexpected update-check worker failure")
            result = UpdateCheckResult(UpdateStatus.FAILURE, UPDATE_FAILURE_MESSAGE)
        self.show_update_result(result)

    def show_update_result(self, result: UpdateCheckResult) -> None:
        """Show one concise result and only expose downloads for newer releases."""
        self.update_check_in_progress = False
        self.update_button.configure(state=tk.NORMAL)
        self.update_status_label.configure(text=result.message)
        self.update_download_url = result.download_url
        if result.download_url is None:
            self.download_button.pack_forget()
        else:
            self.download_button.pack(pady=(8, 0))

    def open_update_download_page(self) -> None:
        if self.update_download_url is not None:
            self.open_link(self.update_download_url)

    def close(self, Event=None) -> None:
        if self._update_poll_after_id is not None:
            try:
                self.after_cancel(self._update_poll_after_id)
            except tk.TclError:
                pass
            self._update_poll_after_id = None
        if self._update_future is not None:
            self._update_future.cancel()
            self._update_future = None
        self._update_executor.shutdown(wait=False, cancel_futures=True)
        self._save_position()
        self.destroy()

    def _restore_position(self) -> None:
        self.update_idletasks()
        position = safe_window_position(
            getattr(self.settings, "about_dialog_position", None),
            self.winfo_width(),
            self.winfo_height(),
            self.winfo_vrootx(),
            self.winfo_vrooty(),
            self.winfo_vrootwidth(),
            self.winfo_vrootheight(),
        )
        if position is not None:
            self.geometry(f"{position[0]:+d}{position[1]:+d}")

    def _save_position(self) -> None:
        setter = getattr(self.settings, "set_about_dialog_position", None)
        if setter is not None:
            try:
                setter((self.winfo_x(), self.winfo_y()))
            except OSError:
                LOGGER.exception("Could not save About dialog position")


class FactoryResetDialog(tk.Toplevel):
    """Modal first confirmation for restoring persistent application settings."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.result: Optional[bool] = None
        self.delete_user_patterns = tk.BooleanVar(value=False)
        self.title("Factory Reset")
        self.transient(parent)
        self.resizable(False, False)

        content = ttk.Frame(self, padding=16)
        content.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            content,
            text=(
                "This will restore Army Painter's settings and preferences\n"
                "to their default values."
            ),
            justify=tk.LEFT,
        ).pack(anchor=tk.W)
        ttk.Label(
            content,
            text=(
                "Your user-created Patterns will be kept unless you choose\n"
                "to delete them below."
            ),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(12, 0))
        ttk.Checkbutton(
            content,
            text="Delete all user-created Patterns",
            variable=self.delete_user_patterns,
        ).pack(anchor=tk.W, pady=(12, 0))
        ttk.Label(
            content,
            text=(
                "Pattern order and Pattern marker colors will otherwise\n"
                "remain unchanged."
            ),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(12, 0))

        buttons = ttk.Frame(content)
        buttons.pack(fill=tk.X, pady=(16, 0))
        reset_button = ttk.Button(
            buttons,
            text="Factory Reset",
            command=self.confirm,
        )
        reset_button.pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(
            side=tk.RIGHT, padx=(0, 8)
        )

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", self.cancel)
        self.bind("<Return>", self.confirm)
        reset_button.focus_set()
        self.grab_set()
        self.wait_window()

    @classmethod
    def show(cls, parent: tk.Misc) -> Optional[bool]:
        """Return deletion choice after confirmation, or None after cancellation."""
        return cls(parent).result

    def confirm(self, Event=None) -> None:
        self.result = bool(self.delete_user_patterns.get())
        self.destroy()

    def cancel(self, Event=None) -> None:
        self.result = None
        self.destroy()


class FactoryResetPatternDeletionDialog(tk.Toplevel):
    """Second modal confirmation for deleting every user-created Pattern."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.result = False
        self.title("Delete all User Patterns?")
        self.transient(parent)
        self.resizable(False, False)

        content = ttk.Frame(self, padding=16)
        content.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            content,
            text=(
                "This will permanently delete all user-created Patterns.\n"
                "This action cannot be undone."
            ),
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        buttons = ttk.Frame(content)
        buttons.pack(fill=tk.X, pady=(16, 0))
        delete_button = ttk.Button(
            buttons,
            text="Delete Patterns and Reset",
            command=self.confirm,
        )
        delete_button.pack(side=tk.RIGHT)
        cancel_button = ttk.Button(buttons, text="Cancel", command=self.cancel)
        cancel_button.pack(side=tk.RIGHT, padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", self.cancel)
        cancel_button.focus_set()
        self.grab_set()
        self.wait_window()

    @classmethod
    def show(cls, parent: tk.Misc) -> bool:
        return cls(parent).result

    def confirm(self) -> None:
        self.result = True
        self.destroy()

    def cancel(self, Event=None) -> None:
        self.result = False
        self.destroy()


class CustomFavoriteNameDialog(tk.Toplevel):
    """Small modal editor for the optional name of one Custom Favorite."""

    def __init__(
        self,
        parent: tk.Misc,
        color: str,
        initial_name: str = "",
        title: str = "Save Favorite Color",
    ):
        super().__init__(parent)
        self.settings = getattr(parent, "settings", None)
        self._position_setting = (
            "favorite_rename_dialog_position"
            if title == "Rename Favorite"
            else "favorite_save_dialog_position"
        )
        self._position_setter = (
            "set_favorite_rename_dialog_position"
            if title == "Rename Favorite"
            else "set_favorite_save_dialog_position"
        )
        self.color = normalize_rgb_hex(color)
        self.result: Optional[str] = None
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)

        content = ttk.Frame(self, padding=12)
        content.pack(fill=tk.BOTH, expand=True)
        ttk.Label(content, text="Name:").grid(row=0, column=0, sticky=tk.W)
        self.name_entry = ttk.Entry(content, width=28, style=APP_ENTRY_STYLE)
        self.name_entry.grid(
            row=1,
            column=0,
            columnspan=3,
            sticky=tk.EW,
            pady=(2, 10),
        )
        if initial_name:
            self.name_entry.insert(0, initial_name)
        ttk.Label(content, text="Color:").grid(row=2, column=0, sticky=tk.W)
        self.color_preview = self._create_swatch(content, self.color)
        self.color_preview.grid(row=3, column=0, sticky=tk.W, pady=(2, 12))
        ttk.Label(content, text=self.color).grid(
            row=3,
            column=1,
            sticky=tk.W,
            padx=(6, 0),
            pady=(2, 12),
        )
        ttk.Button(content, text="Cancel", command=self.cancel).grid(
            row=4,
            column=1,
            sticky=tk.E,
            padx=(0, 6),
        )
        ttk.Button(content, text="Save", command=self.save).grid(
            row=4,
            column=2,
            sticky=tk.E,
        )
        content.grid_columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Return>", self.save)
        self.bind("<Escape>", self.cancel)
        self._restore_position()
        self.name_entry.focus_set()
        self.grab_set()
        self.wait_window()

    @classmethod
    def show(
        cls,
        parent: tk.Misc,
        color: str,
        initial_name: str = "",
        title: str = "Save Favorite Color",
    ) -> Optional[str]:
        """Show the modal and return a trimmed optional name or cancellation."""
        return cls(parent, color, initial_name, title).result

    def save(self, Event=None) -> None:
        self.result = self.name_entry.get().strip()
        self._save_position()
        self.destroy()

    def cancel(self, Event=None) -> None:
        self.result = None
        self._save_position()
        self.destroy()

    @staticmethod
    def _create_swatch(parent: tk.Misc, color: str) -> tk.Canvas:
        canvas = tk.Canvas(
            parent,
            width=22,
            height=22,
            bd=0,
            highlightthickness=0,
        )
        draw_rounded_swatch(
            canvas,
            1,
            1,
            21,
            21,
            fill=color,
            outline=PAINT_SWATCH_OUTLINE,
            width=1,
            corner_radius=RECENT_COLOR_SWATCH_CORNER_RADIUS,
        )
        return canvas

    def _restore_position(self) -> None:
        self.update_idletasks()
        position = safe_window_position(
            getattr(
                getattr(self, "settings", None),
                getattr(
                    self,
                    "_position_setting",
                    "favorite_save_dialog_position",
                ),
                None,
            ),
            self.winfo_width(),
            self.winfo_height(),
            self.winfo_vrootx(),
            self.winfo_vrooty(),
            self.winfo_vrootwidth(),
            self.winfo_vrootheight(),
        )
        if position is not None:
            self.geometry(f"{position[0]:+d}{position[1]:+d}")

    def _save_position(self) -> None:
        setter = getattr(
            getattr(self, "settings", None),
            getattr(
                self,
                "_position_setter",
                "set_favorite_save_dialog_position",
            ),
            None,
        )
        if setter is None:
            return
        try:
            setter((self.winfo_x(), self.winfo_y()))
        except OSError:
            LOGGER.exception("Could not save Custom Favorite dialog position")


class ClosestCitadelColorDialog(tk.Toplevel):
    """Compact modal selector for the three closest predefined paints."""

    def __init__(
        self,
        parent: tk.Misc,
        current_color: str,
        matches: tuple[ClosestPaintMatch, ...],
    ):
        super().__init__(parent)
        self.settings = getattr(parent, "settings", None)
        self.current_color = normalize_rgb_hex(current_color)
        self.matches = matches
        self.result: PaintColor | None = None
        self.title("Closest Citadel Colors")
        self.transient(parent)
        self.resizable(False, False)

        content = ttk.Frame(self, padding=12)
        content.pack(fill=tk.BOTH, expand=True)
        current_area = ttk.LabelFrame(content, text="Current Color", padding=8)
        current_area.pack(fill=tk.X)
        self.current_swatch = self._create_swatch(current_area, self.current_color)
        self.current_swatch.grid(row=0, column=0, sticky=tk.W)
        ttk.Label(current_area, text=self.current_color).grid(
            row=0, column=1, sticky=tk.W, padx=(8, 0)
        )

        matches_area = ttk.LabelFrame(content, text="Closest Matches", padding=8)
        matches_area.pack(fill=tk.X, pady=(10, 0))
        initial_id = matches[0].paint.id if matches else ""
        self.selected_paint_id = tk.StringVar(self, value=initial_id)
        self.match_buttons = []
        self.match_swatches = []
        for rank, match in enumerate(matches, start=1):
            button = ttk.Radiobutton(
                matches_area,
                text=f"{rank}.",
                value=match.paint.id,
                variable=self.selected_paint_id,
            )
            button.grid(row=rank - 1, column=0, sticky=tk.W, pady=3)
            swatch = self._create_swatch(
                matches_area,
                paint_swatch_presentation(match.paint).color,
            )
            swatch.grid(row=rank - 1, column=1, padx=(6, 8), pady=3)
            ttk.Label(matches_area, text=match.paint.name, width=24).grid(
                row=rank - 1, column=2, sticky=tk.W, padx=(0, 8)
            )
            ttk.Label(
                matches_area,
                text=paint_swatch_presentation(match.paint).color,
            ).grid(row=rank - 1, column=3, sticky=tk.W, padx=(0, 8))
            ttk.Label(matches_area, text=f"ΔE00 {match.delta_e:.2f}").grid(
                row=rank - 1, column=4, sticky=tk.E
            )
            self.match_buttons.append(button)
            self.match_swatches.append(swatch)

        actions = ttk.Frame(content)
        actions.pack(fill=tk.X, pady=(12, 0))
        self.close_button = ttk.Button(actions, text="Close", command=self.close)
        self.close_button.pack(side=tk.RIGHT)
        self.use_button = ttk.Button(
            actions,
            text="Use Selected",
            command=self.use_selected,
            state=tk.NORMAL if matches else tk.DISABLED,
        )
        self.use_button.pack(side=tk.RIGHT, padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Return>", self.use_selected)
        self.bind("<Escape>", self.close)
        self._restore_position()
        self.grab_set()
        self.wait_window()

    @staticmethod
    def _create_swatch(parent: tk.Misc, color: str) -> tk.Canvas:
        canvas = tk.Canvas(
            parent,
            width=28,
            height=22,
            bd=0,
            highlightthickness=0,
        )
        draw_rounded_swatch(
            canvas,
            1,
            1,
            27,
            21,
            fill=color,
            outline=PAINT_SWATCH_OUTLINE,
            width=1,
            corner_radius=RECENT_COLOR_SWATCH_CORNER_RADIUS,
        )
        return canvas

    @classmethod
    def show(
        cls,
        parent: tk.Misc,
        current_color: str,
        matches: tuple[ClosestPaintMatch, ...],
    ) -> PaintColor | None:
        """Show the modal and return the chosen predefined paint."""
        return cls(parent, current_color, matches).result

    def use_selected(self, Event=None) -> None:
        selected_id = self.selected_paint_id.get()
        self.result = next(
            (match.paint for match in self.matches if match.paint.id == selected_id),
            None,
        )
        self._save_position()
        self.destroy()

    def close(self, Event=None) -> None:
        self.result = None
        self._save_position()
        self.destroy()

    def _restore_position(self) -> None:
        self.update_idletasks()
        position = safe_window_position(
            getattr(self.settings, "closest_citadel_dialog_position", None),
            self.winfo_width(),
            self.winfo_height(),
            self.winfo_vrootx(),
            self.winfo_vrooty(),
            self.winfo_vrootwidth(),
            self.winfo_vrootheight(),
        )
        if position is not None:
            self.geometry(f"{position[0]:+d}{position[1]:+d}")

    def _save_position(self) -> None:
        setter = getattr(
            self.settings,
            "set_closest_citadel_dialog_position",
            None,
        )
        if setter is not None:
            try:
                setter((self.winfo_x(), self.winfo_y()))
            except OSError:
                LOGGER.exception("Could not save Closest Citadel dialog position")


class ColorPickerDialog(tk.Toplevel):
    """Modal Citadel browser and RGB/HSV/HSL color editor."""

    def __init__(
        self,
        parent: tk.Misc,
        initial_color: str,
        paint_catalog: Optional[PaintCatalog] = None,
        settings=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.original_color = initial_color
        self.current_color = initial_color
        self.current_custom_favorite: CustomFavoriteIdentity | None = None
        self._updating_color_representations = False
        self._hsv_field_cache = None
        self._hsl_field_cache = None
        self._displayed_field_mode = None
        self._hue_slider_cache = None
        self._color_wheel_cache = None
        self._color_wheel_ring_cache = None
        self._color_wheel_hue_table = None
        self._classic_field_cache = None
        self._classic_field_base_cache = None
        self._classic_value_slider_cache = None
        self._classic_field_indicator_items = ()
        self._classic_value_indicator_items = ()
        self._color_wheel_drag_target = None
        self._color_wheel_hue_indicator_items = ()
        self._color_wheel_sv_indicator_items = ()
        self._visual_resize_after_id = None
        self._field_indicator_items = ()
        self._hue_indicator_items = ()
        self._achromatic_hue = rgb_hex_to_hsv(initial_color)[0]
        self.accepted_color: Optional[str] = None
        self.recent_colors: RecentColors = getattr(
            settings, "color_picker_recent_colors", ()
        )
        saved_mode = getattr(settings, "color_picker_color_space", None)
        self.color_space_mode = ColorVisualizationMode(
            saved_mode if saved_mode in COLOR_SPACE_MODES else DEFAULT_COLOR_SPACE_MODE
        )
        saved_group = getattr(settings, "color_picker_group", None)
        self.selected_color_group = (
            PaletteSpecialGroup.FAVORITES
            if saved_group == PaletteSpecialGroup.FAVORITES.value
            else next(
                (group for group in VISUAL_GROUP_ORDER if group.value == saved_group),
                None,
            )
        )
        saved_sort_mode = getattr(settings, "color_picker_sort_mode", None)
        self.palette_sort_mode = next(
            (mode for mode in PaletteSortMode if mode.value == saved_sort_mode),
            PaletteSortMode.COLOR,
        )
        self.paint_catalog = (
            load_citadel_catalog() if paint_catalog is None else paint_catalog
        )
        self.favorite_library = FavoriteColorLibrary(
            self.paint_catalog,
            getattr(settings, "favorite_colors", ()),
        )
        self.palette_paints = ()
        self.closest_citadel_matches: tuple[ClosestPaintMatch, ...] = ()
        self.closest_citadel_selection: PaintColor | None = None
        self.selected_paint_id: Optional[str] = None
        self.search_query = ""

        self._configure_window(parent)
        self._build_main_layout()
        self._build_palette_search()
        self._build_palette_grid()
        self._build_group_navigation()
        self._build_color_editor()
        # Create actions last so native Tab traversal follows the visual layout.
        self._build_actions()
        if hasattr(self, "tk"):
            self.update_idletasks()
            self._restore_pane_sashes()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Return>", self.accept)
        self.bind("<Escape>", self.cancel)
        self.grab_set()
        self.wait_window()

    @classmethod
    def show(
        cls,
        parent: tk.Misc,
        initial_color: str,
        paint_catalog: Optional[PaintCatalog] = None,
        settings=None,
    ) -> Optional[str]:
        """Show the modal dialog and return its accepted color or cancellation."""
        if settings is None:
            dialog = cls(parent, initial_color, paint_catalog)
        else:
            dialog = cls(parent, initial_color, paint_catalog, settings)
        return dialog.get_accepted_color()

    def _configure_window(self, parent: tk.Misc) -> None:
        self.title("Select Color")
        self.transient(parent)
        self.resizable(True, True)

        available_width = max(1, self.winfo_screenwidth() - COLOR_PICKER_SCREEN_MARGIN)
        available_height = max(1, self.winfo_screenheight() - COLOR_PICKER_SCREEN_MARGIN)
        width = min(COLOR_PICKER_DEFAULT_WIDTH, available_width)
        height = min(COLOR_PICKER_DEFAULT_HEIGHT, available_height)
        geometry = None
        saved_geometry = getattr(
            getattr(self, "settings", None), "color_picker_geometry", None
        )
        if saved_geometry is not None:
            geometry = safe_window_geometry(
                saved_geometry,
                width,
                height,
                self.winfo_vrootx(),
                self.winfo_vrooty(),
                self.winfo_vrootwidth(),
                self.winfo_vrootheight(),
            )
        self.geometry(geometry or f"{width}x{height}")
        self.minsize(width, height)

    def _build_actions(self) -> None:
        actions = ttk.Frame(self, padding=COLOR_EDITOR_SECTION_GAP)
        actions.pack(side=tk.BOTTOM, fill=tk.X)
        self.ok_button = ttk.Button(actions, text="OK", command=self.accept)
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self.cancel)
        self.cancel_button.pack(side=tk.RIGHT)
        self.ok_button.pack(
            side=tk.RIGHT, padx=(0, COLOR_EDITOR_SECTION_GAP)
        )

    def _build_main_layout(self) -> None:
        self.dialog_content = ttk.Frame(self, padding=(8, 8, 8, 0))
        self.dialog_content.pack(fill=tk.BOTH, expand=True)

        self.main_panes = ttk.Panedwindow(
            self.dialog_content,
            orient=tk.HORIZONTAL,
        )
        self.main_panes.pack(fill=tk.BOTH, expand=True)

        self.group_navigation = ttk.LabelFrame(
            self.main_panes,
            text="Groups",
            padding=8,
            width=COLOR_PICKER_GROUP_PANE_WIDTH,
        )
        self.palette_area = ttk.LabelFrame(
            self.main_panes,
            text="Citadel Colors",
            padding=8,
            width=COLOR_PICKER_PALETTE_PANE_WIDTH,
        )
        self.editor_area = ttk.LabelFrame(
            self.main_panes,
            text="Color Editor",
            padding=8,
            width=COLOR_PICKER_EDITOR_PANE_WIDTH,
        )
        self.palette_area.pack_propagate(False)
        self.editor_area.pack_propagate(False)
        self.main_panes.add(self.group_navigation, weight=0)
        self.main_panes.add(self.palette_area, weight=3)
        self.main_panes.add(self.editor_area, weight=1)

        self.palette_header_area = ttk.Frame(self.palette_area)
        self.palette_header_area.pack(fill=tk.X)
        self.palette_count_area = ttk.Frame(self.palette_header_area)
        self.palette_count_area.pack(side=tk.RIGHT)
        self.palette_sort_area = ttk.Frame(self.palette_header_area)
        self.palette_sort_area.pack(side=tk.RIGHT, padx=(8, 0))
        self.palette_search_area = ttk.Frame(self.palette_header_area)
        self.palette_search_area.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.palette_grid_area = ttk.Frame(self.palette_area)
        self.palette_grid_area.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.editor_color_space_area = ttk.Frame(self.editor_area)
        self.editor_color_space_area.pack(fill=tk.X)
        self.editor_visualization_area = ttk.Frame(self.editor_area)
        self.editor_color_field_area = ttk.Frame(self.editor_visualization_area)
        self.editor_slider_area = ttk.Frame(self.editor_visualization_area, width=28)
        self.editor_slider_area.pack(
            side=tk.RIGHT,
            fill=tk.Y,
            padx=(COLOR_EDITOR_SECTION_GAP, 0),
        )
        self.editor_color_field_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.editor_numeric_area = ttk.Frame(self.editor_area)
        self.editor_rgb_area = ttk.LabelFrame(
            self.editor_numeric_area,
            text="RGB",
            padding=COLOR_EDITOR_GROUP_PADDING,
        )
        self.editor_rgb_area.pack(fill=tk.X)
        self.editor_alternate_color_space_area = ttk.LabelFrame(
            self.editor_numeric_area,
            text=getattr(self, "color_space_mode", DEFAULT_COLOR_SPACE_MODE),
            padding=COLOR_MODEL_GROUP_PADDING,
        )
        self.editor_alternate_color_space_area.pack(
            fill=tk.X,
            pady=(COLOR_EDITOR_SECTION_GAP, 0),
        )
        self.editor_color_model_controls_area = ttk.Frame(
            self.editor_alternate_color_space_area
        )
        self.editor_color_model_controls_area.grid(
            row=0,
            column=0,
            sticky=tk.EW,
        )
        self.editor_hex_area = ttk.Frame(self.editor_alternate_color_space_area)
        self.editor_hex_area.grid(
            row=1,
            column=0,
            sticky=tk.EW,
            pady=(COLOR_EDITOR_SECTION_GAP, 0),
        )
        self.editor_recent_colors_area = ttk.Frame(self.editor_area)
        self.editor_preview_area = ttk.Frame(self.editor_area)
        # Allocate fixed-height controls from the bottom before giving the
        # remaining vertical space to the visualization. This keeps preview
        # canvases at their requested height when the dialog is constrained.
        self.editor_preview_area.pack(
            side=tk.BOTTOM,
            fill=tk.X,
            pady=(COLOR_EDITOR_SECTION_GAP, 0),
        )
        self.editor_recent_colors_area.pack(
            side=tk.BOTTOM,
            fill=tk.X,
            pady=(COLOR_EDITOR_SECTION_GAP, 0),
        )
        self.editor_numeric_area.pack(
            side=tk.BOTTOM,
            fill=tk.X,
            pady=(COLOR_EDITOR_SECTION_GAP, 0),
        )
        self.editor_visualization_area.pack(
            fill=tk.BOTH,
            expand=True,
            pady=(COLOR_EDITOR_SECTION_GAP, 0),
        )
        self.editor_preview_area.grid_columnconfigure(0, weight=1, uniform="preview")
        self.editor_preview_area.grid_columnconfigure(1, weight=1, uniform="preview")
        self.original_color_preview_area = ttk.Frame(self.editor_preview_area)
        self.original_color_preview_area.grid(row=0, column=0, sticky=tk.EW, padx=(0, 4))
        self.current_color_preview_area = ttk.Frame(self.editor_preview_area)
        self.current_color_preview_area.grid(row=0, column=1, sticky=tk.EW, padx=(4, 0))

    def _build_palette_grid(self) -> None:
        self.palette_grid = PaintSwatchGrid(
            self.palette_grid_area,
            on_paint_selected=self.select_paint,
            favorite_action_label=self._citadel_favorite_action_label,
            is_paint_favorite=self._is_palette_color_favorite,
            on_favorite_toggled=self.toggle_citadel_favorite,
            on_custom_favorite_renamed=self.rename_custom_favorite,
            on_custom_favorite_removed=self.remove_custom_favorite,
        )
        self.palette_grid.pack(fill=tk.BOTH, expand=True)

    def _build_palette_search(self) -> None:
        self.search_entry = ttk.Entry(
            self.palette_search_area,
            style=APP_ENTRY_STYLE,
        )
        self.search_entry.insert(0, PAINT_SEARCH_PLACEHOLDER)
        self.search_entry.pack(fill=tk.X, expand=True)
        self.search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_search_focus_out)
        self.search_entry.bind("<KeyRelease>", self._on_search_key_released)
        self.palette_sort_label = ttk.Label(self.palette_sort_area, text="Sort:")
        self.palette_sort_label.pack(side=tk.LEFT, padx=(0, 4))
        self.palette_sort_selector = ttk.Combobox(
            self.palette_sort_area,
            values=PALETTE_SORT_DISPLAY_NAMES,
            state="readonly",
            style=APP_COMBOBOX_STYLE,
            width=12,
        )
        self.palette_sort_selector.pack(side=tk.LEFT)
        self.palette_sort_selector.bind(
            "<<ComboboxSelected>>", self._on_palette_sort_selected
        )
        clear_readonly_combobox_text_selection(self.palette_sort_selector)
        show_readonly_combobox_value(
            self.palette_sort_selector,
            self.palette_sort_mode.display_name,
        )
        self.palette_count_label = ttk.Label(
            self.palette_count_area,
            text=format_visible_paint_count(0),
        )
        self.palette_count_label.pack(padx=(8, 0))

    def _on_search_focus_in(self, Event=None) -> None:
        if self.search_entry.get() == PAINT_SEARCH_PLACEHOLDER:
            self.search_entry.delete(0, tk.END)

    def _on_search_focus_out(self, Event=None) -> None:
        if not self.search_entry.get():
            self.search_entry.insert(0, PAINT_SEARCH_PLACEHOLDER)

    def _on_search_key_released(self, Event=None) -> None:
        query = self.search_entry.get()
        if query == PAINT_SEARCH_PLACEHOLDER:
            query = ""
        self.set_paint_search(query)

    def set_paint_search(self, query: str) -> None:
        """Apply a live name search within the currently selected group."""
        normalized_query = query.strip()
        if normalized_query == self.search_query:
            return
        self.search_query = normalized_query
        self._refresh_palette_data_source()

    def set_palette_sort_mode(self, mode: PaletteSortMode) -> None:
        """Reorder visible paints without changing canonical colour state."""
        if not isinstance(mode, PaletteSortMode):
            raise ValueError(f"Unsupported palette sort mode: {mode!r}")
        selector = getattr(self, "palette_sort_selector", None)
        if selector is not None and selector.get() != mode.display_name:
            selector.set(mode.display_name)
        if mode is getattr(self, "palette_sort_mode", PaletteSortMode.COLOR):
            return
        self.palette_sort_mode = mode
        self._refresh_palette_data_source()

    def _on_palette_sort_selected(self, Event=None) -> None:
        self.set_palette_sort_mode(
            PaletteSortMode.from_display_name(self.palette_sort_selector.get())
        )

    def _build_group_navigation(self) -> None:
        style = ttk.Style(self)
        style.configure("ColorPickerGroup.TButton", anchor=tk.W)
        style.map(
            "ColorPickerGroup.TButton",
            relief=[("selected", tk.SUNKEN)],
        )

        self.group_buttons = {}
        self.group_button_labels = {}
        for color_group, label in COLOR_PICKER_GROUP_ENTRIES:
            row = ttk.Frame(self.group_navigation)
            row.pack(fill=tk.X, pady=1)
            indicator = tk.Canvas(
                row,
                width=14,
                height=14,
                bd=0,
                highlightthickness=1,
                highlightbackground="#606060",
            )
            indicator.pack(side=tk.LEFT, padx=(0, 5))
            self._draw_group_indicator(indicator, color_group)

            button = ttk.Button(
                row,
                text=label,
                style="ColorPickerGroup.TButton",
                command=partial(self.select_color_group, color_group),
            )
            button.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.group_buttons[color_group] = button
            self.group_button_labels[color_group] = label

        self.select_color_group(self.selected_color_group)

    def _draw_group_indicator(self, indicator, color_group) -> None:
        if color_group is PaletteSpecialGroup.FAVORITES:
            indicator.configure(background=FAVORITE_GROUP_INDICATOR_BACKGROUND)
            indicator.create_polygon(
                FAVORITE_GROUP_STAR_POINTS,
                fill=FAVORITE_STAR_COLOR,
                outline="",
            )
            return
        if isinstance(color_group, ColorGroup):
            indicator.configure(background=COLOR_GROUP_INDICATORS[color_group])
            return

        stripe_width = 14 / len(ALL_COLOR_INDICATORS)
        for index, color in enumerate(ALL_COLOR_INDICATORS):
            indicator.create_rectangle(
                index * stripe_width,
                0,
                (index + 1) * stripe_width,
                14,
                fill=color,
                outline="",
            )

    def select_color_group(self, color_group) -> None:
        """Select a navigation group for the palette filter."""
        self.selected_color_group = color_group
        for candidate, button in self.group_buttons.items():
            selected = candidate is color_group
            button.state(["selected"] if selected else ["!selected"])
            marker = "▸ " if selected else "  "
            button.configure(text=f"{marker}{self.group_button_labels[candidate]}")
        palette_area = getattr(self, "palette_area", None)
        if palette_area is not None:
            palette_area.configure(
                text=(
                    "Favorites"
                    if color_group is PaletteSpecialGroup.FAVORITES
                    else "Citadel Colors"
                )
            )
        self._refresh_palette_data_source()

    def _refresh_palette_data_source(self) -> None:
        paints = self.paint_catalog.paints
        if self.selected_color_group is PaletteSpecialGroup.FAVORITES:
            paints = self.favorite_library.palette_colors()
        elif self.selected_color_group is not None:
            paints = get_paints_for_group(paints, self.selected_color_group)
        paints = filter_paints_by_name(paints, self.search_query)
        self.palette_paints = sort_palette_paints(
            paints,
            getattr(self, "palette_sort_mode", PaletteSortMode.COLOR),
        )
        self._refresh_palette_display()

    def _refresh_palette_display(self) -> None:
        self.palette_grid.set_empty_message(
            NO_FAVORITE_COLORS_MESSAGE
            if self.selected_color_group is PaletteSpecialGroup.FAVORITES
            else NO_CITADEL_COLORS_MESSAGE
        )
        self.palette_grid.set_paints(self.palette_paints)
        self.palette_count_label.configure(
            text=format_visible_paint_count(len(self.palette_paints))
        )
        self.event_generate("<<ColorPickerPaletteChanged>>")

    def select_paint(self, paint: PaintColor) -> None:
        """Use a catalog paint as the editable color without locking it."""
        self.selected_paint_id = paint.id
        self.set_current_color(paint_swatch_presentation(paint).color)
        self.palette_grid.set_selected_paint(paint.id)

    def _citadel_id_for_palette_color(self, paint: PaintColor) -> Optional[str]:
        if isinstance(paint, FavoritePaletteColor):
            if isinstance(paint.favorite, CitadelFavoriteColor):
                return paint.favorite.citadel_id
            return None
        return paint.id if self.paint_catalog.find_by_id(paint.id) is not None else None

    def _citadel_favorite_action_label(self, paint: PaintColor) -> Optional[str]:
        citadel_id = self._citadel_id_for_palette_color(paint)
        if citadel_id is None:
            return None
        return (
            "Remove from Favorites"
            if self.favorite_library.has_citadel(citadel_id)
            else "Add to Favorites"
        )

    def _is_palette_color_favorite(self, paint: PaintColor) -> bool:
        if (
            getattr(self, "selected_color_group", None)
            is PaletteSpecialGroup.FAVORITES
        ):
            return False
        if isinstance(paint, FavoritePaletteColor):
            return True
        return self.favorite_library.has_citadel(paint.id)

    def toggle_citadel_favorite(self, paint: PaintColor) -> bool:
        """Toggle one exact Citadel tile through the shared Favorite library."""
        citadel_id = self._citadel_id_for_palette_color(paint)
        if citadel_id is None:
            return False
        was_favorite = self.favorite_library.has_citadel(citadel_id)
        if was_favorite:
            self.favorite_library.remove_citadel(citadel_id)
        else:
            self.favorite_library.add_color(
                f"#{paint.r:02X}{paint.g:02X}{paint.b:02X}",
                explicit_citadel_id=citadel_id,
            )
        settings = getattr(self, "settings", None)
        if settings is not None:
            try:
                settings.set_favorite_colors(self.favorite_library.favorites)
            except OSError:
                LOGGER.exception("Could not save Citadel Favorite change")
                if was_favorite:
                    self.favorite_library.add_color(
                        f"#{paint.r:02X}{paint.g:02X}{paint.b:02X}",
                        explicit_citadel_id=citadel_id,
                    )
                else:
                    self.favorite_library.remove_citadel(citadel_id)
                self._refresh_favorite_button()
                return False
        self._refresh_palette_data_source()
        palette_grid = getattr(self, "palette_grid", None)
        if palette_grid is not None:
            palette_grid.refresh_favorite_indicators()
        self._refresh_favorite_button()
        return True

    @staticmethod
    def _custom_favorite_for_palette_color(
        paint: FavoritePaletteColor,
    ) -> Optional[CustomFavoriteColor]:
        favorite = paint.favorite
        return favorite if isinstance(favorite, CustomFavoriteColor) else None

    def rename_custom_favorite(self, paint: FavoritePaletteColor) -> bool:
        """Rename one exact Custom Favorite without changing its RGB or ID."""
        favorite = self._custom_favorite_for_palette_color(paint)
        if favorite is None:
            return False
        name = CustomFavoriteNameDialog.show(
            self,
            favorite.color,
            favorite.name,
            "Rename Favorite",
        )
        if name is None:
            return False
        renamed = self.favorite_library.rename_custom(favorite.id, name)
        if renamed is None:
            return False
        settings = getattr(self, "settings", None)
        if settings is not None:
            try:
                settings.set_favorite_colors(self.favorite_library.favorites)
            except OSError:
                LOGGER.exception("Could not save Custom Favorite rename")
                self.favorite_library.rename_custom(favorite.id, favorite.name)
                return False
        current_identity = getattr(self, "current_custom_favorite", None)
        if current_identity is not None and current_identity.id == renamed.id:
            self.current_custom_favorite = CustomFavoriteIdentity(
                renamed.id, renamed.name
            )
        self._refresh_palette_data_source()
        return True

    def remove_custom_favorite(self, paint: FavoritePaletteColor) -> bool:
        """Remove one exact Custom Favorite without touching applied colors."""
        favorite = self._custom_favorite_for_palette_color(paint)
        if favorite is None:
            return False
        removed = self.favorite_library.remove_custom(favorite.id)
        if removed is None:
            return False
        settings = getattr(self, "settings", None)
        if settings is not None:
            try:
                settings.set_favorite_colors(self.favorite_library.favorites)
            except OSError:
                LOGGER.exception("Could not save Custom Favorite removal")
                self.favorite_library = FavoriteColorLibrary(
                    self.paint_catalog,
                    self.favorite_library.favorites + (removed,),
                )
                return False
        current_identity = getattr(self, "current_custom_favorite", None)
        if current_identity is not None and current_identity.id == removed.id:
            self.current_custom_favorite = None
        self._refresh_palette_data_source()
        self._refresh_favorite_button()
        return True

    def _build_color_editor(self) -> None:
        ttk.Label(self.editor_color_space_area, text="Color Space:").pack(
            side=tk.LEFT, padx=(0, 6)
        )
        self.color_space_selector = ttk.Combobox(
            self.editor_color_space_area,
            values=COLOR_SPACE_MODES,
            state="readonly",
            style=APP_COMBOBOX_STYLE,
            width=12,
        )
        self.color_space_selector.pack(side=tk.LEFT)
        self.color_space_selector.bind(
            "<<ComboboxSelected>>", self._on_color_space_selected
        )
        clear_readonly_combobox_text_selection(self.color_space_selector)
        show_readonly_combobox_value(
            self.color_space_selector,
            self.color_space_mode,
        )

        self.hsv_color_field = tk.Canvas(
            self.editor_color_field_area,
            height=COLOR_FIELD_PREFERRED_HEIGHT,
            highlightthickness=1,
            cursor="crosshair",
        )
        self.hsv_color_field.pack(fill=tk.BOTH, expand=True)
        self.hue_slider = tk.Canvas(
            self.editor_slider_area, width=28, highlightthickness=1, cursor="sb_v_double_arrow"
        )
        self.hue_slider.pack(fill=tk.BOTH, expand=True)
        self.color_wheel_canvas = tk.Canvas(
            self.editor_visualization_area,
            height=COLOR_FIELD_PREFERRED_HEIGHT,
            highlightthickness=1,
        )
        self.classic_visualization_area = ttk.Frame(self.editor_visualization_area)
        self.classic_color_field = tk.Canvas(
            self.classic_visualization_area,
            height=COLOR_FIELD_PREFERRED_HEIGHT,
            highlightthickness=1,
        )
        self.classic_value_slider = tk.Canvas(
            self.classic_visualization_area,
            width=28,
            highlightthickness=1,
        )
        self.classic_value_slider.pack(
            side=tk.RIGHT,
            fill=tk.Y,
            padx=(COLOR_EDITOR_SECTION_GAP, 0),
        )
        self.classic_color_field.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for event_name in ("<Button-1>", "<B1-Motion>"):
            self.hsv_color_field.bind(event_name, self._on_color_field_input)
            self.hue_slider.bind(event_name, self._on_hue_slider_input)
        self.hsv_color_field.bind("<Configure>", self._on_visualization_resized)
        self.hue_slider.bind("<Configure>", self._on_visualization_resized)
        self.color_wheel_canvas.bind("<Configure>", self._on_visualization_resized)
        self.color_wheel_canvas.bind("<Button-1>", self._on_color_wheel_press)
        self.color_wheel_canvas.bind("<B1-Motion>", self._on_color_wheel_drag)
        self.color_wheel_canvas.bind("<ButtonRelease-1>", self._on_color_wheel_release)
        self.classic_color_field.bind("<Configure>", self._on_visualization_resized)
        self.classic_value_slider.bind("<Configure>", self._on_visualization_resized)
        for event_name in ("<Button-1>", "<B1-Motion>"):
            self.classic_color_field.bind(event_name, self._on_classic_field_input)
            self.classic_value_slider.bind(
                event_name, self._on_classic_value_slider_input
            )

        self.rgb_controls = {}
        self.rgb_control_labels = {}
        validation = (self.register(self._validate_rgb_input), "%P")
        for index, (label, channel) in enumerate(
            (("Red", "red"), ("Green", "green"), ("Blue", "blue"))
        ):
            label_column = index * 2
            control_column = label_column + 1
            self.editor_rgb_area.grid_columnconfigure(
                control_column,
                weight=1,
                uniform="rgb-control",
            )
            channel_label = ttk.Label(self.editor_rgb_area, text=f"{label}:")
            channel_label.grid(
                row=0,
                column=label_column,
                sticky=tk.W,
                padx=(0, 4),
            )
            control = ttk.Spinbox(
                self.editor_rgb_area,
                from_=0,
                to=255,
                width=4,
                validate="key",
                validatecommand=validation,
                command=self._on_rgb_control_changed,
                style=APP_SPINBOX_STYLE,
            )
            control.grid(
                row=0,
                column=control_column,
                sticky=tk.W,
                padx=(0, 12 if index < 2 else 0),
            )
            control.bind("<KeyRelease>", self._on_rgb_control_changed)
            control.bind("<FocusOut>", self._on_rgb_control_changed)
            control.bind("<Return>", self._on_rgb_control_return)
            self.rgb_control_labels[channel] = channel_label
            self.rgb_controls[channel] = control
        self.color_model_labels = {}
        self.color_model_controls = {}
        self.color_model_spacers = []
        for index, (name, label, maximum) in enumerate(
            (
                ("hue", "Hue", 359),
                ("saturation", "Saturation", 100),
                ("component", "Value", 100),
            )
        ):
            component_label = ttk.Label(
                self.editor_color_model_controls_area,
                text=f"{label}:",
            )
            component_label.pack(side=tk.LEFT)
            validation = (
                self.register(self._validate_model_input),
                "%P",
                str(maximum),
            )
            control = ttk.Spinbox(
                self.editor_color_model_controls_area,
                from_=0,
                to=maximum,
                width=COLOR_MODEL_CONTROL_WIDTH,
                validate="key",
                validatecommand=validation,
                command=self._on_color_model_control_changed,
                style=APP_SPINBOX_STYLE,
            )
            control.pack(side=tk.LEFT, padx=(1, 0))
            control.bind("<KeyRelease>", self._on_color_model_control_changed)
            control.bind("<FocusOut>", self._on_color_model_control_changed)
            control.bind("<Return>", self._on_color_model_control_return)
            self.color_model_labels[name] = component_label
            self.color_model_controls[name] = control
            if index < 2:
                spacer = ttk.Frame(self.editor_color_model_controls_area)
                spacer.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.color_model_spacers.append(spacer)
        self.editor_hex_area.grid_columnconfigure(1, weight=1)
        self.hex_input_label = ttk.Label(self.editor_hex_area, text="Hex:")
        self.hex_input_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self.hex_input = ttk.Entry(
            self.editor_hex_area,
            width=9,
            style=APP_ENTRY_STYLE,
        )
        self.hex_input.grid(row=0, column=1, sticky=tk.W)
        self.hex_input.bind("<Return>", self._on_hex_input_return)
        self.hex_input.bind("<FocusOut>", self._on_hex_input_focus_out)
        self.favorite_button = ttk.Button(
            self.editor_hex_area,
            text="★ Add Favorite",
            command=self.toggle_current_favorite,
        )
        self.favorite_button.grid(row=0, column=2, sticky=tk.E, padx=(8, 0))
        self.closest_citadel_button = ttk.Button(
            self.editor_hex_area,
            text="Closest Color",
            command=self.find_closest_citadel_color,
        )
        self.closest_citadel_button.grid(
            row=0,
            column=3,
            sticky=tk.E,
            padx=(8, 0),
        )

        self.recent_color_row = RecentColorSwatchRow(
            self.editor_recent_colors_area,
            colors=self.recent_colors,
            paint_catalog=self.paint_catalog,
            on_color_selected=self.set_current_color,
        )
        self.recent_color_row.pack(fill=tk.X)

        self.original_color_preview_label = ttk.Label(
            self.original_color_preview_area, text="Original"
        )
        self.original_color_preview_label.pack(anchor=tk.W)
        self.original_color_preview = tk.Canvas(
            self.original_color_preview_area,
            height=32,
            background=self.original_color,
            bd=0,
            highlightthickness=1,
            highlightbackground=COLOR_PREVIEW_BORDER,
            highlightcolor=COLOR_PREVIEW_BORDER,
        )
        self.original_color_preview.pack(fill=tk.X)
        self.current_color_preview_label = ttk.Label(
            self.current_color_preview_area, text="Current"
        )
        self.current_color_preview_label.pack(anchor=tk.W)
        self.current_color_preview = tk.Canvas(
            self.current_color_preview_area,
            height=32,
            background=self.current_color,
            bd=0,
            highlightthickness=1,
            highlightbackground=COLOR_PREVIEW_BORDER,
            highlightcolor=COLOR_PREVIEW_BORDER,
        )
        self.current_color_preview.pack(fill=tk.X)
        self._refresh_rgb_controls()
        self._refresh_hex_control()
        self._refresh_favorite_button()
        self._refresh_closest_citadel_button()
        self.select_color_space(self.color_space_mode)

    def _on_color_space_selected(self, Event=None) -> None:
        self.select_color_space(self.color_space_selector.get())

    def select_color_space(self, mode: str) -> None:
        """Update structural editor mode without creating a second color state."""
        try:
            visualization_mode = ColorVisualizationMode(mode)
        except ValueError:
            raise ValueError(f"Unsupported color space: {mode}")
        if visualization_mode.value not in COLOR_SPACE_MODES:
            raise ValueError(f"Unsupported color space: {mode}")
        self.color_space_mode = visualization_mode
        selector = getattr(self, "color_space_selector", None)
        if selector is not None and selector.get() != visualization_mode.value:
            selector.set(visualization_mode.value)
        self.editor_alternate_color_space_area.configure(
            text=visualization_mode.numeric_model_title
        )
        self.color_model_labels["component"].configure(
            text=visualization_mode.component_label
        )
        self._show_visualization_mode(visualization_mode)
        self._refresh_color_model_controls()
        self._refresh_visual_picker()

    def _show_visualization_mode(self, mode: ColorVisualizationMode) -> None:
        """Show only the canvas arrangement owned by the selected visualization."""
        field_area = getattr(self, "editor_color_field_area", None)
        slider_area = getattr(self, "editor_slider_area", None)
        wheel = getattr(self, "color_wheel_canvas", None)
        classic = getattr(self, "classic_visualization_area", None)
        if (
            field_area is None
            or slider_area is None
            or wheel is None
            or classic is None
        ):
            return
        if mode is ColorVisualizationMode.COLOR_WHEEL:
            field_area.pack_forget()
            slider_area.pack_forget()
            classic.pack_forget()
            wheel.pack(fill=tk.BOTH, expand=True)
            return
        if mode is ColorVisualizationMode.CLASSIC:
            field_area.pack_forget()
            slider_area.pack_forget()
            wheel.pack_forget()
            classic.pack(fill=tk.BOTH, expand=True)
            return
        wheel.pack_forget()
        classic.pack_forget()
        slider_area.pack(
            side=tk.RIGHT,
            fill=tk.Y,
            padx=(COLOR_EDITOR_SECTION_GAP, 0),
        )
        field_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def set_current_color(self, color: str) -> None:
        """Set the canonical working color and synchronize every representation."""
        if getattr(self, "_updating_color_representations", False):
            return

        self.current_color = color
        self.current_custom_favorite = self._resolve_custom_favorite_identity(
            color
        )
        self._updating_color_representations = True
        try:
            self._refresh_color_representations()
        finally:
            self._updating_color_representations = False

    def _resolve_custom_favorite_identity(
        self, color: str
    ) -> CustomFavoriteIdentity | None:
        """Resolve exact slot identity with Citadel taking precedence."""
        paint_catalog = getattr(self, "paint_catalog", None)
        if paint_catalog is not None and resolve_exact_citadel_favorite(
            paint_catalog, color
        ) is not None:
            return None
        favorite_library = getattr(self, "favorite_library", None)
        if favorite_library is None:
            return None
        custom = favorite_library.custom_for_color(color)
        if custom is None:
            return None
        return CustomFavoriteIdentity(custom.id, custom.name)

    def _refresh_color_representations(self) -> None:
        """Fan the canonical color out to all editor controls."""
        self._refresh_rgb_controls()
        self._refresh_color_model_controls()
        self._refresh_hex_control()
        self._refresh_visual_picker()
        self._refresh_current_color_preview()
        self._refresh_favorite_button()
        self._refresh_closest_citadel_button()

    def _refresh_rgb_controls(self) -> None:
        controls = getattr(self, "rgb_controls", None)
        if controls is None:
            return
        for channel, value in zip(
            ("red", "green", "blue"), rgb_hex_to_channels(self.current_color)
        ):
            control = controls[channel]
            self._replace_control_text(control, str(value))

    def _refresh_color_model_controls(self) -> None:
        controls = getattr(self, "color_model_controls", None)
        if controls is None:
            return
        if self._visualization_mode().uses_hsl_model:
            hue, saturation, component = rgb_hex_to_hsl(self.current_color)
        else:
            hue, saturation, component = rgb_hex_to_hsv(self.current_color)
        if saturation > 0.0:
            self._achromatic_hue = hue
        else:
            hue = getattr(self, "_achromatic_hue", 0.0)
        values = {
            "hue": round(hue * 360) % 360,
            "saturation": round(saturation * 100),
            "component": round(component * 100),
        }
        for name, value in values.items():
            control = controls[name]
            self._replace_control_text(control, str(value))

    def _refresh_hex_control(self) -> None:
        control = getattr(self, "hex_input", None)
        if control is not None:
            self._replace_control_text(control, normalize_rgb_hex(self.current_color))

    def _resolved_current_citadel_favorite(self) -> Optional[CitadelFavoriteColor]:
        return resolve_exact_citadel_favorite(
            self.paint_catalog,
            self.current_color,
            getattr(self, "selected_paint_id", None),
        )

    def current_favorite_action_label(self) -> str:
        """Return the universal action for the exact current color identity."""
        citadel = self._resolved_current_citadel_favorite()
        is_favorite = (
            self.favorite_library.has_citadel(citadel.citadel_id)
            if citadel is not None
            else self.favorite_library.custom_for_color(self.current_color) is not None
        )
        return "★ Remove Favorite" if is_favorite else "★ Add Favorite"

    def _refresh_favorite_button(self) -> None:
        button = getattr(self, "favorite_button", None)
        if button is not None:
            button.configure(text=self.current_favorite_action_label())

    def can_find_closest_citadel_color(self) -> bool:
        """Return whether the canonical editor color is not a Citadel paint."""
        return self._resolved_current_citadel_favorite() is None

    def _refresh_closest_citadel_button(self) -> None:
        button = getattr(self, "closest_citadel_button", None)
        if button is not None:
            button.configure(
                state=(
                    tk.NORMAL
                    if self.can_find_closest_citadel_color()
                    else tk.DISABLED
                )
            )

    def find_closest_citadel_color(self) -> None:
        """Request matching for the current canonical Color Editor value."""
        if self.can_find_closest_citadel_color():
            self.closest_citadel_matches = find_closest_paints(
                self.current_color,
                self.paint_catalog,
            )
            self.closest_citadel_selection = ClosestCitadelColorDialog.show(
                self,
                self.current_color,
                self.closest_citadel_matches,
            )
            if self.closest_citadel_selection is not None:
                self.select_paint(self.closest_citadel_selection)

    def toggle_current_favorite(self) -> bool:
        """Toggle the exact current Citadel or Custom Color Favorite."""
        citadel = self._resolved_current_citadel_favorite()
        if citadel is not None:
            paint = self.paint_catalog.find_by_id(citadel.citadel_id)
            return paint is not None and self.toggle_citadel_favorite(paint)

        existing = self.favorite_library.custom_for_color(self.current_color)
        if existing is None:
            custom_name = CustomFavoriteNameDialog.show(self, self.current_color)
            if custom_name is None:
                return False
            result = self.favorite_library.add_color(
                self.current_color,
                custom_name=custom_name,
            )
            custom = result.favorite
            added = True
        else:
            custom = self.favorite_library.remove_custom(existing.id)
            added = False
        if custom is None:
            return False
        settings = getattr(self, "settings", None)
        if settings is not None:
            try:
                settings.set_favorite_colors(self.favorite_library.favorites)
            except OSError:
                LOGGER.exception("Could not save Custom Favorite change")
                if added:
                    self.favorite_library.remove_custom(custom.id)
                else:
                    self.favorite_library = FavoriteColorLibrary(
                        self.paint_catalog,
                        self.favorite_library.favorites + (custom,),
                    )
                self._refresh_favorite_button()
                return False
        if added:
            self.current_custom_favorite = CustomFavoriteIdentity(
                custom.id, custom.name
            )
        else:
            current_identity = getattr(self, "current_custom_favorite", None)
            if current_identity is not None and current_identity.id == custom.id:
                self.current_custom_favorite = None
        self._refresh_palette_data_source()
        self._refresh_favorite_button()
        return True

    @staticmethod
    def _replace_control_text(control, value: str) -> None:
        """Replace synchronized text without stealing focus, caret, or selection."""
        insert_index = None
        selection = None
        if hasattr(control, "focus_get"):
            try:
                if control.focus_get() is control:
                    insert_index = int(control.index(tk.INSERT))
                    if control.selection_present():
                        selection = (
                            int(control.index(tk.SEL_FIRST)),
                            int(control.index(tk.SEL_LAST)),
                        )
            except tk.TclError:
                pass
        control.delete(0, tk.END)
        control.insert(0, value)
        if insert_index is not None:
            control.icursor(min(insert_index, len(value)))
        if selection is not None:
            start, end = selection
            control.selection_range(min(start, len(value)), min(end, len(value)))

    def _commit_hex_input(self) -> bool:
        """Commit valid Hex input or restore the canonical color display."""
        try:
            color = normalize_rgb_hex(self.hex_input.get())
        except ValueError:
            self._refresh_hex_control()
            return False
        self.set_current_color(color)
        return True

    def _on_hex_input_return(self, Event=None) -> str:
        self._commit_hex_input()
        return "break"

    def _on_hex_input_focus_out(self, Event=None) -> None:
        self._commit_hex_input()

    @staticmethod
    def _validate_rgb_input(proposed: str) -> bool:
        """Allow an editable blank or a decimal RGB value in range."""
        return proposed == "" or (proposed.isdecimal() and int(proposed) <= 255)

    @staticmethod
    def _validate_model_input(proposed: str, maximum: str) -> bool:
        """Allow an editable blank or a decimal component within its UI range."""
        return proposed == "" or (
            proposed.isdecimal() and int(proposed) <= int(maximum)
        )

    def _on_rgb_control_changed(self, Event=None) -> None:
        if getattr(self, "_updating_color_representations", False):
            return
        values = tuple(
            self.rgb_controls[channel].get()
            for channel in ("red", "green", "blue")
        )
        if not all(value.isdecimal() and 0 <= int(value) <= 255 for value in values):
            return
        self.set_current_color(rgb_channels_to_hex(*(int(value) for value in values)))

    def _on_rgb_control_return(self, Event=None) -> str:
        self._on_rgb_control_changed(Event)
        return "break"

    def _on_color_model_control_changed(self, Event=None) -> None:
        if getattr(self, "_updating_color_representations", False):
            return
        values = tuple(
            self.color_model_controls[name].get()
            for name in ("hue", "saturation", "component")
        )
        maximums = (359, 100, 100)
        if not all(
            value.isdecimal() and 0 <= int(value) <= maximum
            for value, maximum in zip(values, maximums)
        ):
            return
        hue = int(values[0]) / 360.0
        saturation = int(values[1]) / 100.0
        component = int(values[2]) / 100.0
        self._achromatic_hue = hue
        if self._visualization_mode().uses_hsl_model:
            color = hsl_to_rgb_hex(hue, saturation, component)
        else:
            color = hsv_to_rgb_hex(hue, saturation, component)
        self.set_current_color(color)

    def _visualization_mode(self) -> ColorVisualizationMode:
        """Return the active typed mode, including for narrow test doubles."""
        return ColorVisualizationMode(
            getattr(self, "color_space_mode", DEFAULT_COLOR_SPACE_MODE)
        )

    def _on_color_model_control_return(self, Event=None) -> str:
        self._on_color_model_control_changed(Event)
        return "break"

    def _refresh_visual_picker(self) -> None:
        """Refresh HSV gradients when needed and always reposition indicators."""
        mode = self._visualization_mode()
        if mode is ColorVisualizationMode.COLOR_WHEEL:
            wheel = getattr(self, "color_wheel_canvas", None)
            if wheel is None or not hasattr(wheel, "winfo_width"):
                return
            hue, saturation, value = rgb_hex_to_hsv(self.current_color)
            if saturation > 0.0:
                self._achromatic_hue = hue
            else:
                hue = getattr(self, "_achromatic_hue", 0.0)
            self._render_color_wheel(hue)
            self._draw_color_wheel_indicators(hue, saturation, value)
            return
        if mode is ColorVisualizationMode.CLASSIC:
            field = getattr(self, "classic_color_field", None)
            slider = getattr(self, "classic_value_slider", None)
            if (
                field is None
                or slider is None
                or not hasattr(field, "winfo_width")
            ):
                return
            hue, saturation, value = rgb_hex_to_hsv(self.current_color)
            if saturation > 0.0:
                self._achromatic_hue = hue
            else:
                hue = getattr(self, "_achromatic_hue", 0.0)
            self._render_classic_field(value)
            self._render_classic_value_slider(hue, saturation)
            self._draw_classic_indicators(hue, saturation, value)
            return
        field = getattr(self, "hsv_color_field", None)
        slider = getattr(self, "hue_slider", None)
        if (
            field is None
            or slider is None
            or not hasattr(field, "winfo_width")
        ):
            return
        if mode.uses_hsl_model:
            hue, saturation, component = rgb_hex_to_hsl(self.current_color)
        else:
            hue, saturation, component = rgb_hex_to_hsv(self.current_color)
        if saturation > 0.0:
            self._achromatic_hue = hue
        else:
            hue = getattr(self, "_achromatic_hue", 0.0)
        if mode.uses_hsl_model:
            self._render_hsl_field(hue)
        else:
            self._render_hsv_field(hue)
        self._render_hue_slider()
        self._draw_hsv_indicators(hue, saturation, component)

    def _render_color_wheel(self, hue: float) -> None:
        """Render a clockwise hue ring and an HSV saturation/value square."""
        width = self.color_wheel_canvas.winfo_width()
        height = self.color_wheel_canvas.winfo_height()
        cache_key = (width, height, hue)
        cached = self._color_wheel_cache
        if width <= 1 or height <= 1:
            return
        if cached is not None and cached[:2] == cache_key[:2]:
            hue_distance = abs(cached[2] - hue)
            if min(hue_distance, 1.0 - hue_distance) < 1 / 1024:
                return

        geometry = color_wheel_geometry(width, height)
        ring_cache = getattr(self, "_color_wheel_ring_cache", None)
        if ring_cache is None or ring_cache[:2] != (width, height):
            scale = 2
            ring_image = Image.new(
                "RGBA", (width * scale, height * scale), (0, 0, 0, 0)
            )
            ring_pixels = ring_image.load()
            outer_radius_squared = geometry.outer_radius**2
            inner_radius_squared = geometry.ring_inner_radius**2
            top = max(
                0, math.floor((geometry.center_y - geometry.outer_radius) * scale)
            )
            bottom = min(
                height * scale,
                math.ceil((geometry.center_y + geometry.outer_radius) * scale) + 1,
            )
            hue_table_size = 4096
            hue_table = getattr(self, "_color_wheel_hue_table", None)
            if hue_table is None:
                hue_table = tuple(
                    tuple(
                        round(channel * 255)
                        for channel in colorsys.hsv_to_rgb(
                            index / hue_table_size, 1.0, 1.0
                        )
                    )
                    + (255,)
                    for index in range(hue_table_size)
                )
                self._color_wheel_hue_table = hue_table
            for pixel_y in range(top, bottom):
                canvas_y = (pixel_y + 0.5) / scale
                delta_y = canvas_y - geometry.center_y
                outer_span = math.sqrt(
                    max(0.0, outer_radius_squared - delta_y**2)
                )
                outer_left = max(
                    0,
                    math.ceil(
                        (geometry.center_x - outer_span) * scale - 0.5
                    ),
                )
                outer_right = min(
                    width * scale - 1,
                    math.floor(
                        (geometry.center_x + outer_span) * scale - 0.5
                    ),
                )
                pixel_ranges = ((outer_left, outer_right),)
                if abs(delta_y) <= geometry.ring_inner_radius:
                    inner_span = math.sqrt(
                        max(0.0, inner_radius_squared - delta_y**2)
                    )
                    inner_left = math.ceil(
                        (geometry.center_x - inner_span) * scale - 0.5
                    )
                    inner_right = math.floor(
                        (geometry.center_x + inner_span) * scale - 0.5
                    )
                    pixel_ranges = (
                        (outer_left, inner_left - 1),
                        (inner_right + 1, outer_right),
                    )
                for range_left, range_right in pixel_ranges:
                    for pixel_x in range(range_left, range_right + 1):
                        canvas_x = (pixel_x + 0.5) / scale
                        ring_hue = color_wheel_hue_from_position(
                            canvas_x, canvas_y, geometry
                        )
                        color_index = round(ring_hue * hue_table_size) % hue_table_size
                        ring_pixels[pixel_x, pixel_y] = hue_table[color_index]
            ring_image = ring_image.resize(
                (width, height), Image.Resampling.LANCZOS
            )
            self._color_wheel_ring_cache = (width, height, ring_image)
        else:
            ring_image = ring_cache[2]

        image = ring_image.copy()
        field_left = round(geometry.field_left)
        field_top = round(geometry.field_top)
        field_width = max(2, round(geometry.field_right) - field_left + 1)
        field_height = max(2, round(geometry.field_bottom) - field_top + 1)
        pixels = []
        for y in range(field_height):
            value = 1.0 - y / (field_height - 1)
            for x in range(field_width):
                saturation = x / (field_width - 1)
                rgb = colorsys.hsv_to_rgb(hue, saturation, value)
                pixels.append(tuple(round(channel * 255) for channel in rgb))
        field_image = Image.new("RGB", (field_width, field_height))
        field_image.putdata(pixels)
        image.paste(field_image, (field_left, field_top))
        self._color_wheel_image = ImageTk.PhotoImage(image)
        self.color_wheel_canvas.delete("gradient")
        self.color_wheel_canvas.create_image(
            0, 0, anchor=tk.NW, image=self._color_wheel_image, tags="gradient"
        )
        self.color_wheel_canvas.tag_lower("gradient")
        self._color_wheel_cache = cache_key

    def _render_classic_field(self, value: float) -> None:
        """Render Hue horizontally and Saturation vertically at current Value."""
        width = self.classic_color_field.winfo_width()
        height = self.classic_color_field.winfo_height()
        cache_key = (width, height, value)
        cached = self._classic_field_cache
        if width <= 1 or height <= 1:
            return
        if cached is not None and cached[:2] == cache_key[:2]:
            if abs(cached[2] - value) < 1 / 1024:
                return
        base_cache = getattr(self, "_classic_field_base_cache", None)
        if base_cache is None or base_cache[:2] != (width, height):
            pixels = []
            for y in range(height):
                saturation = 1.0 - y / (height - 1)
                for x in range(width):
                    hue = x / width
                    rgb = colorsys.hsv_to_rgb(hue, saturation, 1.0)
                    pixels.append(tuple(round(channel * 255) for channel in rgb))
            base_image = Image.new("RGB", (width, height))
            base_image.putdata(pixels)
            self._classic_field_base_cache = (width, height, base_image)
        else:
            base_image = base_cache[2]
        value_lut = [round(channel * value) for channel in range(256)] * 3
        image = base_image.point(value_lut)
        self._classic_field_image = ImageTk.PhotoImage(image)
        self.classic_color_field.delete("gradient")
        self.classic_color_field.create_image(
            0, 0, anchor=tk.NW, image=self._classic_field_image, tags="gradient"
        )
        self.classic_color_field.tag_lower("gradient")
        self._classic_field_cache = cache_key

    def _render_classic_value_slider(self, hue: float, saturation: float) -> None:
        """Render Value from bright at top to black in the current Hue/Saturation."""
        width = self.classic_value_slider.winfo_width()
        height = self.classic_value_slider.winfo_height()
        cache_key = (width, height, hue, saturation)
        cached = self._classic_value_slider_cache
        if width <= 1 or height <= 1:
            return
        if cached is not None and cached[:2] == cache_key[:2]:
            hue_distance = abs(cached[2] - hue)
            if (
                min(hue_distance, 1.0 - hue_distance) < 1 / 1024
                and abs(cached[3] - saturation) < 1 / 1024
            ):
                return
        pixels = []
        for y in range(height):
            value = 1.0 - y / (height - 1)
            rgb = colorsys.hsv_to_rgb(hue, saturation, value)
            color = tuple(round(channel * 255) for channel in rgb)
            pixels.extend((color,) * width)
        image = Image.new("RGB", (width, height))
        image.putdata(pixels)
        self._classic_value_slider_image = ImageTk.PhotoImage(image)
        self.classic_value_slider.delete("gradient")
        self.classic_value_slider.create_image(
            0,
            0,
            anchor=tk.NW,
            image=self._classic_value_slider_image,
            tags="gradient",
        )
        self.classic_value_slider.tag_lower("gradient")
        self._classic_value_slider_cache = cache_key

    def _on_classic_field_input(self, Event) -> None:
        hue, saturation = classic_hs_from_position(
            Event.x,
            Event.y,
            self.classic_color_field.winfo_width(),
            self.classic_color_field.winfo_height(),
        )
        self._achromatic_hue = hue
        _, _, value = rgb_hex_to_hsv(self.current_color)
        self.set_current_color(hsv_to_rgb_hex(hue, saturation, value))

    def _on_classic_value_slider_input(self, Event) -> None:
        hue, saturation, _ = rgb_hex_to_hsv(self.current_color)
        if saturation == 0.0:
            hue = getattr(self, "_achromatic_hue", 0.0)
        value = classic_value_from_position(
            Event.y, self.classic_value_slider.winfo_height()
        )
        self.set_current_color(hsv_to_rgb_hex(hue, saturation, value))

    def _draw_classic_indicators(
        self, hue: float, saturation: float, value: float
    ) -> None:
        field_x, field_y = classic_hs_position(
            hue,
            saturation,
            self.classic_color_field.winfo_width(),
            self.classic_color_field.winfo_height(),
        )
        slider_y = classic_value_position(
            value, self.classic_value_slider.winfo_height()
        )
        if not getattr(self, "_classic_field_indicator_items", ()):
            self._classic_field_indicator_items = tuple(
                self.classic_color_field.create_oval(
                    0, 0, 0, 0, outline=outline, width=2, tags="indicator"
                )
                for outline in ("black", "white")
            )
        if not getattr(self, "_classic_value_indicator_items", ()):
            self._classic_value_indicator_items = tuple(
                self.classic_value_slider.create_line(
                    0, 0, 0, 0, fill=fill, width=width, tags="indicator"
                )
                for fill, width in (("black", 4), ("white", 2))
            )
        for item, radius in zip(self._classic_field_indicator_items, (6, 4)):
            self.classic_color_field.coords(
                item,
                field_x - radius,
                field_y - radius,
                field_x + radius,
                field_y + radius,
            )
        slider_width = self.classic_value_slider.winfo_width()
        for item in self._classic_value_indicator_items:
            self.classic_value_slider.coords(item, 0, slider_y, slider_width, slider_y)

    def _on_color_wheel_press(self, Event) -> None:
        geometry = color_wheel_geometry(
            self.color_wheel_canvas.winfo_width(),
            self.color_wheel_canvas.winfo_height(),
        )
        radius = math.hypot(Event.x - geometry.center_x, Event.y - geometry.center_y)
        if geometry.ring_inner_radius <= radius <= geometry.outer_radius:
            self._color_wheel_drag_target = "hue"
        elif (
            geometry.field_left <= Event.x <= geometry.field_right
            and geometry.field_top <= Event.y <= geometry.field_bottom
        ):
            self._color_wheel_drag_target = "sv"
        else:
            self._color_wheel_drag_target = None
            return
        self._apply_color_wheel_input(Event)

    def _on_color_wheel_drag(self, Event) -> None:
        if getattr(self, "_color_wheel_drag_target", None) is not None:
            self._apply_color_wheel_input(Event)

    def _on_color_wheel_release(self, Event=None) -> None:
        self._color_wheel_drag_target = None

    def _apply_color_wheel_input(self, Event) -> None:
        geometry = color_wheel_geometry(
            self.color_wheel_canvas.winfo_width(),
            self.color_wheel_canvas.winfo_height(),
        )
        hue, saturation, value = rgb_hex_to_hsv(self.current_color)
        if saturation == 0.0:
            hue = getattr(self, "_achromatic_hue", 0.0)
        if self._color_wheel_drag_target == "hue":
            hue = color_wheel_hue_from_position(Event.x, Event.y, geometry)
            self._achromatic_hue = hue
        elif self._color_wheel_drag_target == "sv":
            saturation, value = color_wheel_sv_from_position(
                Event.x, Event.y, geometry
            )
        else:
            return
        self.set_current_color(hsv_to_rgb_hex(hue, saturation, value))

    def _draw_color_wheel_indicators(
        self, hue: float, saturation: float, value: float
    ) -> None:
        geometry = color_wheel_geometry(
            self.color_wheel_canvas.winfo_width(),
            self.color_wheel_canvas.winfo_height(),
        )
        hue_x, hue_y = color_wheel_hue_position(hue, geometry)
        sv_x, sv_y = color_wheel_sv_position(saturation, value, geometry)
        if not getattr(self, "_color_wheel_hue_indicator_items", ()):
            self._color_wheel_hue_indicator_items = tuple(
                self.color_wheel_canvas.create_oval(
                    0, 0, 0, 0, outline=outline, width=2, tags="indicator"
                )
                for outline in ("black", "white")
            )
        if not getattr(self, "_color_wheel_sv_indicator_items", ()):
            self._color_wheel_sv_indicator_items = tuple(
                self.color_wheel_canvas.create_oval(
                    0, 0, 0, 0, outline=outline, width=2, tags="indicator"
                )
                for outline in ("black", "white")
            )
        for items, x, y in (
            (self._color_wheel_hue_indicator_items, hue_x, hue_y),
            (self._color_wheel_sv_indicator_items, sv_x, sv_y),
        ):
            for item, radius in zip(items, (6, 4)):
                self.color_wheel_canvas.coords(
                    item, x - radius, y - radius, x + radius, y + radius
                )

    def _on_visualization_resized(self, Event=None) -> None:
        pending = self._visual_resize_after_id
        if pending is not None:
            self.after_cancel(pending)
        self._visual_resize_after_id = self.after(
            VISUAL_RESIZE_DELAY_MS, self._refresh_visualization_after_resize
        )

    def _refresh_visualization_after_resize(self) -> None:
        self._visual_resize_after_id = None
        self._refresh_visual_picker()

    def _on_color_field_input(self, Event) -> None:
        width = self.hsv_color_field.winfo_width()
        height = self.hsv_color_field.winfo_height()
        if self._visualization_mode().uses_hsl_model:
            hue, saturation, _ = rgb_hex_to_hsl(self.current_color)
            if saturation == 0.0:
                hue = getattr(self, "_achromatic_hue", 0.0)
            components = hsl_from_field_position(Event.x, Event.y, width, height, hue)
            color = hsl_to_rgb_hex(*components)
        else:
            hue, saturation, _ = rgb_hex_to_hsv(self.current_color)
            if saturation == 0.0:
                hue = getattr(self, "_achromatic_hue", 0.0)
            components = hsv_from_field_position(Event.x, Event.y, width, height, hue)
            color = hsv_to_rgb_hex(*components)
        self.set_current_color(color)

    def _on_hsv_field_input(self, Event) -> None:
        """Retain the Block 4.2 callback name as a compatibility wrapper."""
        self._on_color_field_input(Event)

    def _on_hue_slider_input(self, Event) -> None:
        hue = hue_from_slider_position(Event.y, self.hue_slider.winfo_height())
        self._achromatic_hue = hue
        if self._visualization_mode().uses_hsl_model:
            _, saturation, component = rgb_hex_to_hsl(self.current_color)
            color = hsl_to_rgb_hex(hue, saturation, component)
        else:
            _, saturation, component = rgb_hex_to_hsv(self.current_color)
            color = hsv_to_rgb_hex(hue, saturation, component)
        self.set_current_color(color)

    def _render_hsv_field(self, hue: float) -> None:
        width = self.hsv_color_field.winfo_width()
        height = self.hsv_color_field.winfo_height()
        cache_key = (width, height, hue)
        cached = self._hsv_field_cache
        if width <= 1 or height <= 1:
            return
        if (
            getattr(self, "_displayed_field_mode", None) == DEFAULT_COLOR_SPACE_MODE
            and cached is not None
            and cached[:2] == cache_key[:2]
        ):
            hue_distance = abs(cached[2] - hue)
            if min(hue_distance, 1.0 - hue_distance) < 1 / 1024:
                return
        pixels = []
        for y in range(height):
            value = 1.0 - y / (height - 1)
            for x in range(width):
                saturation = x / (width - 1)
                rgb = colorsys.hsv_to_rgb(hue, saturation, value)
                pixels.append(tuple(round(channel * 255) for channel in rgb))
        image = Image.new("RGB", (width, height))
        image.putdata(pixels)
        self._hsv_field_image = ImageTk.PhotoImage(image)
        self.hsv_color_field.delete("gradient")
        self.hsv_color_field.create_image(
            0, 0, anchor=tk.NW, image=self._hsv_field_image, tags="gradient"
        )
        self.hsv_color_field.tag_lower("gradient")
        self._hsv_field_cache = cache_key
        self._displayed_field_mode = DEFAULT_COLOR_SPACE_MODE

    def _render_hsl_field(self, hue: float) -> None:
        width = self.hsv_color_field.winfo_width()
        height = self.hsv_color_field.winfo_height()
        cache_key = (width, height, hue)
        cached = self._hsl_field_cache
        if width <= 1 or height <= 1:
            return
        if (
            getattr(self, "_displayed_field_mode", None) == "HSL"
            and cached is not None
            and cached[:2] == cache_key[:2]
        ):
            hue_distance = abs(cached[2] - hue)
            if min(hue_distance, 1.0 - hue_distance) < 1 / 1024:
                return
        pixels = []
        for y in range(height):
            lightness = 1.0 - y / (height - 1)
            for x in range(width):
                saturation = x / (width - 1)
                rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
                pixels.append(tuple(round(channel * 255) for channel in rgb))
        image = Image.new("RGB", (width, height))
        image.putdata(pixels)
        self._hsv_field_image = ImageTk.PhotoImage(image)
        self.hsv_color_field.delete("gradient")
        self.hsv_color_field.create_image(
            0, 0, anchor=tk.NW, image=self._hsv_field_image, tags="gradient"
        )
        self.hsv_color_field.tag_lower("gradient")
        self._hsl_field_cache = cache_key
        self._displayed_field_mode = "HSL"

    def _render_hue_slider(self) -> None:
        width = self.hue_slider.winfo_width()
        height = self.hue_slider.winfo_height()
        cache_key = (width, height)
        if width <= 1 or height <= 1 or self._hue_slider_cache == cache_key:
            return
        pixels = []
        for y in range(height):
            rgb = colorsys.hsv_to_rgb(y / (height - 1), 1.0, 1.0)
            color = tuple(round(channel * 255) for channel in rgb)
            pixels.extend((color,) * width)
        image = Image.new("RGB", (width, height))
        image.putdata(pixels)
        self._hue_slider_image = ImageTk.PhotoImage(image)
        self.hue_slider.delete("gradient")
        self.hue_slider.create_image(0, 0, anchor=tk.NW, image=self._hue_slider_image, tags="gradient")
        self.hue_slider.tag_lower("gradient")
        self._hue_slider_cache = cache_key

    def _draw_hsv_indicators(self, hue: float, saturation: float, value: float) -> None:
        width = self.hsv_color_field.winfo_width()
        height = self.hsv_color_field.winfo_height()
        x, y = hsv_field_position(saturation, value, width, height)
        if not self._field_indicator_items:
            self._field_indicator_items = tuple(
                self.hsv_color_field.create_oval(
                    0, 0, 0, 0, outline=outline, width=2, tags="indicator"
                )
                for outline in ("black", "white")
            )
        for item, radius in zip(self._field_indicator_items, (6, 4)):
            self.hsv_color_field.coords(
                item, x - radius, y - radius, x + radius, y + radius
            )
        slider_y = hue_slider_position(hue, self.hue_slider.winfo_height())
        if not self._hue_indicator_items:
            self._hue_indicator_items = tuple(
                self.hue_slider.create_line(
                    0, 0, 0, 0, fill=fill, width=width, tags="indicator"
                )
                for fill, width in (("black", 4), ("white", 2))
            )
        slider_width = self.hue_slider.winfo_width()
        for item in self._hue_indicator_items:
            self.hue_slider.coords(item, 0, slider_y, slider_width, slider_y)

    def _refresh_current_color_preview(self) -> None:
        preview = getattr(self, "current_color_preview", None)
        if preview is not None:
            preview.configure(background=self.current_color)

    def get_accepted_color(self) -> Optional[str]:
        """Return the accepted working color, or ``None`` after cancellation."""
        return self.accepted_color

    def accept(self, Event=None) -> None:
        self.accepted_color = SelectedColor(
            self.current_color,
            getattr(self, "current_custom_favorite", None),
        )
        self._remember_accepted_color()
        self._save_geometry()
        self.destroy()

    def cancel(self, Event=None) -> None:
        self.accepted_color = None
        self._save_geometry()
        self.destroy()

    def _remember_accepted_color(self) -> None:
        settings = getattr(self, "settings", None)
        if settings is None:
            return
        recent_colors = add_recent_color(
            getattr(self, "recent_colors", ()),
            rgb_hex_to_channels(self.current_color),
        )
        try:
            settings.set_color_picker_recent_colors(recent_colors)
        except OSError:
            LOGGER.exception("Could not save confirmed recent colour")
            return
        self.recent_colors = recent_colors

    def _save_geometry(self) -> None:
        settings = getattr(self, "settings", None)
        if settings is None:
            return
        try:
            selected_group = getattr(self, "selected_color_group", None)
            main_panes = getattr(self, "main_panes", None)
            sashes = (
                (main_panes.sashpos(0), main_panes.sashpos(1))
                if main_panes is not None
                else (0, 0)
            )
            settings.set_color_picker_ui_state(
                self.geometry(),
                (
                    selected_group.value
                    if selected_group is not None
                    else None
                ),
                getattr(self, "color_space_mode", DEFAULT_COLOR_SPACE_MODE),
                getattr(self, "palette_sort_mode", PaletteSortMode.COLOR).value,
                sashes,
            )
        except OSError:
            LOGGER.exception("Could not save Color Picker window geometry")

    def _restore_pane_sashes(self) -> None:
        sashes = getattr(getattr(self, "settings", None), "color_picker_sashes", None)
        if sashes is None:
            return
        pane_width = self.main_panes.winfo_width()
        first, second = sashes
        if 0 < first < second < pane_width:
            self.main_panes.sashpos(0, first)
            self.main_panes.sashpos(1, second)


def pattern_name_to_restore(preferred_name, current_name, available_names):
    """Choose a refresh selection by internal name, never by row position."""
    candidate = preferred_name if preferred_name is not None else current_name
    return candidate if candidate in available_names else None


def pattern_marker_display_color(marker_color, selected):
    """Return a readable assigned star colour for the row background."""
    colors = PATTERN_MARKER_COLORS.get(marker_color)
    if colors is None:
        colors = DEFAULT_PATTERN_MARKER_COLORS
    return colors[1 if selected else 0]


def pattern_item_has_marker(metadata):
    """Keep built-in rows undecorated while marking every user row."""
    return bool(metadata and metadata.get("is_user"))


def clipped_pattern_marker_height(y, height, tree_height, border_width):
    """Keep frame-owned marker overlays inside the Treeview's lower border."""
    available_height = tree_height - border_width - y
    return max(0, min(height, available_height))


def pattern_drop_destination(
    user_items, source_item, target_item, pointer_y, target_bbox
):
    """Return the final user index and insertion-line y for a valid row."""
    if source_item not in user_items or target_item not in user_items:
        return None
    _x, row_y, _width, row_height = target_bbox
    target_position = user_items.index(target_item)
    source_position = user_items.index(source_item)
    insert_after = pointer_y >= row_y + row_height / 2
    gap_index = target_position + (1 if insert_after else 0)
    final_index = gap_index - 1 if gap_index > source_position else gap_index
    final_index = max(0, min(final_index, len(user_items) - 1))
    line_y = row_y + row_height if insert_after else row_y
    return final_index, line_y


def first_user_pattern_item(items, is_user_item):
    """Return the real first user row without introducing a separator row."""
    return next((item for item in items if is_user_item(item)), None)


def calculate_pattern_separator_x(tree_x, tree_width, marker_width, border_width=0):
    """Return the marker-column boundary within the Treeview parent."""
    return max(tree_x, tree_x + tree_width - marker_width - border_width)


def find_treeview_body_boundary(tree):
    """Find the first body pixel using the active Treeview theme's hit testing."""
    tree_width = tree.winfo_width()
    tree_height = tree.winfo_height()
    if tree_width <= 1 or tree_height <= 1:
        return None

    sample_x = min(max(tree_width // 3, 1), tree_width - 1)
    heading_seen = False
    for sample_y in range(tree_height):
        region = tree.identify_region(sample_x, sample_y)
        if region in ("heading", "separator"):
            heading_seen = True
        elif heading_seen:
            return sample_y
    return None


def build_pattern_rows(patterns=None):
    """Build GUI-independent rows while keeping decoration out of names."""
    if patterns is None:
        patterns = get_all_patterns()

    rows = []
    for pattern_name in patterns:
        user_created = is_user_pattern(pattern_name)
        rows.append(
            {
                "name": pattern_name,
                "is_user": user_created,
                "marker": "★" if user_created else "",
                "marker_color": get_pattern_marker_color(pattern_name),
            }
        )
    return rows


class FrameChannelList(tk.LabelFrame):
    """RGBA channel controls that report the selected alpha state."""

    def __init__(
        self,
        master=None,
        cnf={},
        *,
        on_alpha_changed: BooleanChangedCallback,
        **kw,
    ):
        super(FrameChannelList, self).__init__(master=master, cnf={}, **kw)
        self._on_alpha_changed = on_alpha_changed

        # Channel List Box
        self.lb = tk.Listbox(
            self,
            selectmode=tk.MULTIPLE,
            activestyle="none",
            exportselection=False,
            selectbackground=APP_SELECTION_BACKGROUND,
            selectforeground=APP_SELECTION_FOREGROUND,
            height=4,
            width=9,
        )
        self.lb.insert(0, "0 Red")
        self.lb.insert(1, "1 Green")
        self.lb.insert(2, "2 Blue")
        self.lb.insert(3, "3 Alpha")
        self.lb.pack(side=tk.TOP, padx=6, pady=(4, 0))

        # Add alpha BTN
        self.apply_alpha = tk.BooleanVar()
        self.add_alpha = tk.Checkbutton(
            self,
            text="Apply alpha",
            variable=self.apply_alpha,
            onvalue=1,
            offvalue=0,
            height=2,
            command=self._notify_apply_alpha_changed,
        )
        self.add_alpha.pack(
            side=tk.TOP,
            anchor=tk.W,
            padx=4,
            pady=(6, 4),
        )

    def _notify_apply_alpha_changed(self):
        self._on_alpha_changed(bool(self.apply_alpha.get()))


class FrameColorChooser(tk.Frame):
    """Four color slots that report the changed slot index and hex value."""

    def __init__(
        self,
        master=None,
        cnf={},
        *,
        on_color_changed: ColorChangedCallback,
        on_slot_selected: ColorSlotSelectedCallback,
        on_slots_swapped: Optional[ColorSlotsSwappedCallback] = None,
        on_color_copied: Optional[ColorSlotActionCallback] = None,
        on_color_and_settings_copied: Optional[ColorSlotActionCallback] = None,
        on_color_pasted: Optional[ColorSlotActionCallback] = None,
        on_color_and_settings_pasted: Optional[ColorSlotActionCallback] = None,
        on_color_reset: Optional[ColorSlotActionCallback] = None,
        color_paste_available: Optional[AvailabilityCallback] = None,
        color_and_settings_paste_available: Optional[AvailabilityCallback] = None,
        color_picker: Optional[ColorPickerCallback] = None,
        paint_catalog: Optional[PaintCatalog] = None,
        settings=None,
        drag_binding_owner: Optional[tk.Misc] = None,
        **kw,
    ):
        super(FrameColorChooser, self).__init__(master=master, cnf={}, **kw)
        self._on_color_changed = on_color_changed
        self._on_slot_selected = on_slot_selected
        self._on_slots_swapped = on_slots_swapped
        self._on_color_copied = on_color_copied
        self._on_color_and_settings_copied = on_color_and_settings_copied
        self._on_color_pasted = on_color_pasted
        self._on_color_and_settings_pasted = on_color_and_settings_pasted
        self._on_color_reset = on_color_reset
        self._color_paste_available = color_paste_available
        self._color_and_settings_paste_available = (
            color_and_settings_paste_available
        )
        self._color_picker = (
            self._open_color_picker if color_picker is None else color_picker
        )
        self.paint_catalog = (
            load_citadel_catalog() if paint_catalog is None else paint_catalog
        )
        self.settings = settings
        self._color_text_font = tkfont.Font(
            root=self,
            font=("Arial", 10, "bold"),
        )
        self._color_tooltips = [None] * 4
        self._color_identities = [None] * 4
        self._color_tooltip_window = None
        self.color_slots = []
        self.color_boxes = []
        self.color_buttons = []
        self.active_slot_index = 0
        self._drag_source_index = None
        self._drag_start_position = None
        self._drag_target_index = None
        self._drag_started = False
        self._drag_ghost = None
        self.initialize()
        self._drag_cancel_binding_owner = drag_binding_owner
        self._drag_cancel_binding = None
        if self._drag_cancel_binding_owner is not None:
            self._drag_cancel_binding = self._drag_cancel_binding_owner.bind(
                "<Escape>", self._on_slot_drag_cancel, add="+"
            )
            self.bind("<Destroy>", self._on_color_chooser_destroy, add="+")

    def _open_color_picker(self, initial_color: str) -> Optional[str]:
        """Open the production custom picker with the slot's current color."""
        settings = getattr(self, "settings", None)
        if settings is None:
            return ColorPickerDialog.show(self, initial_color, self.paint_catalog)
        return ColorPickerDialog.show(self, initial_color, self.paint_catalog, settings)

    def initialize(self):
        for i in range(0, 4):
            slot = tk.Frame(
                self,
                width=COLOR_BOX_SIZE,
                height=COLOR_BOX_SIZE + COLOR_BTN_HEIGHT,
                bd=0,
                highlightthickness=0,
            )
            slot.place(
                anchor=tk.NW,
                x=(COLOR_BOX_SIZE + 3) * i,
                y=0,
            )
            slot.pack_propagate(False)
            slot.grid_propagate(False)
            self.color_slots.append(slot)
            self.color_boxes.append(
                tk.Canvas(
                    slot,
                    bg="#808080",
                    relief=tk.RAISED,
                    bd=2,
                    highlightthickness=2,
                    highlightbackground=slot.cget("bg"),
                )
            )
            self.color_boxes[i].bind(
                "<ButtonPress-1>", partial(self._on_slot_pointer_press, i)
            )
            self.color_boxes[i].bind("<B1-Motion>", self._on_slot_pointer_motion)
            self.color_boxes[i].bind(
                "<ButtonRelease-1>", self._on_slot_pointer_release
            )
            self.color_boxes[i].bind(
                "<Button-3>", partial(self._show_slot_context_menu, i)
            )
            self.color_boxes[i].bind(
                "<Enter>", partial(self._show_color_tooltip, i)
            )
            self.color_boxes[i].bind("<Leave>", self._hide_color_tooltip)
            self.color_boxes[i].place(
                anchor=tk.NW,
                x=0,
                y=COLOR_BTN_HEIGHT,
                width=COLOR_BOX_SIZE,
                height=COLOR_BOX_SIZE,
            )
            self.color_buttons.append(
                tk.Button(
                    slot,
                    text=f"Edit Color {i + 1}",
                    wraplength=COLOR_BOX_SIZE,
                    relief=tk.RAISED,
                    bd=2,
                    command=partial(self.apply_color, i),
                )
            )
            self.color_buttons[i].place(
                anchor=tk.NW,
                x=0,
                y=0,
                width=COLOR_BOX_SIZE,
                height=COLOR_BTN_HEIGHT,
            )
        self._draw_active_slot()
        self.draw_rgb_value()

    def _on_slot_pointer_press(self, slot_index: int, Event=None):
        """Select a slot and remember it as a potential drag source."""
        self._finish_slot_drag()
        self._drag_source_index = slot_index
        self._drag_start_position = (
            (Event.x_root, Event.y_root) if Event is not None else None
        )
        self._drag_target_index = None
        self._drag_started = False
        self.select_slot(slot_index)

    def _on_slot_pointer_motion(self, Event=None):
        """Mark pointer movement from a swatch as an active drag."""
        try:
            self._update_slot_drag(Event)
        except Exception:
            self._finish_slot_drag()
            raise

    def _update_slot_drag(self, Event=None):
        """Advance an active drag while leaving failure cleanup centralized."""
        if (
            self._drag_source_index is not None
            and self._drag_start_position is not None
            and Event is not None
        ):
            if not self._drag_started:
                start_x, start_y = self._drag_start_position
                distance_squared = (Event.x_root - start_x) ** 2 + (
                    Event.y_root - start_y
                ) ** 2
                if distance_squared <= COLOR_SLOT_DRAG_THRESHOLD**2:
                    return
                self._drag_started = True
                source_box = self.color_boxes[self._drag_source_index]
                source_box.configure(cursor="fleur")
                self._drag_ghost = ColorSlotDragGhost(
                    self,
                    self._drag_source_index,
                    str(source_box["bg"]),
                    transient_owner=self._drag_cancel_binding_owner,
                )
                self._drag_ghost.show_at_pointer(Event.x_root, Event.y_root)
            elif self._drag_ghost is not None:
                self._drag_ghost.move_to_pointer(Event.x_root, Event.y_root)
            target_index = None
            if Event is not None:
                target_index = self._slot_index_at_pointer(Event.x_root, Event.y_root)
            if target_index == self._drag_source_index:
                target_index = None
            if target_index != self._drag_target_index:
                self._drag_target_index = target_index
                self._draw_active_slot()

    def _on_slot_pointer_release(self, Event=None):
        """Swap with the slot under the pointer, or cancel an invalid drop."""
        source_index = self._drag_source_index
        dragging = self._drag_started
        target_index = self._drag_target_index
        try:
            if dragging and Event is not None:
                target_index = self._slot_index_at_pointer(Event.x_root, Event.y_root)
        finally:
            self._finish_slot_drag()
        if source_index is None or not dragging:
            return
        if target_index is not None and target_index != source_index:
            self._request_slot_swap(source_index, target_index)

    def _on_slot_drag_cancel(self, Event=None):
        """Cancel any pending or active drag without changing slot contents."""
        self._finish_slot_drag()

    def _finish_slot_drag(self, *, redraw: bool = True) -> None:
        """Clear every transient drag resource and restore slot presentation."""
        self._drag_source_index = None
        self._drag_start_position = None
        self._drag_target_index = None
        self._drag_started = False
        ghost = self._drag_ghost
        self._drag_ghost = None
        if ghost is not None:
            ghost.destroy()
        for color_box in self.color_boxes:
            try:
                color_box.configure(cursor="")
            except tk.TclError:
                pass
        if redraw:
            try:
                self._draw_active_slot()
            except tk.TclError:
                pass

    def _on_color_chooser_destroy(self, Event=None) -> None:
        """Release drag resources if this chooser is destroyed mid-drag."""
        if Event is not None and Event.widget is not self:
            return
        self._finish_slot_drag(redraw=False)
        binding = self._drag_cancel_binding
        self._drag_cancel_binding = None
        binding_owner = self._drag_cancel_binding_owner
        self._drag_cancel_binding_owner = None
        if binding is not None and binding_owner is not None:
            try:
                binding_owner.unbind("<Escape>", binding)
            except tk.TclError:
                pass

    def _show_slot_context_menu(self, slot_index: int, Event=None):
        """Offer actions for the right-clicked fixed Color Slot."""
        if Event is None:
            return
        self.select_slot(slot_index)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Edit Color...",
            command=partial(self.apply_color, slot_index),
        )
        menu.add_separator()
        menu.add_command(
            label="Copy Color",
            command=partial(self._request_color_copy, slot_index),
        )
        menu.add_command(
            label="Paste Color",
            command=partial(self._request_color_paste, slot_index),
            state=(
                tk.NORMAL
                if self._color_paste_available is not None
                and self._color_paste_available()
                else tk.DISABLED
            ),
        )
        menu.add_command(
            label="Copy Color + Settings",
            command=partial(self._request_color_and_settings_copy, slot_index),
        )
        menu.add_command(
            label="Paste Color + Settings",
            command=partial(self._request_color_and_settings_paste, slot_index),
            state=(
                tk.NORMAL
                if self._color_and_settings_paste_available is not None
                and self._color_and_settings_paste_available()
                else tk.DISABLED
            ),
        )
        menu.add_separator()
        for target_index in range(len(self.color_slots)):
            if target_index == slot_index:
                continue
            menu.add_command(
                label=f"Swap with Color {target_index + 1}",
                command=partial(self._request_slot_swap, slot_index, target_index),
            )
        menu.add_separator()
        menu.add_command(
            label="Reset Color",
            command=partial(self._request_color_reset, slot_index),
        )
        try:
            menu.tk_popup(Event.x_root, Event.y_root)
        finally:
            menu.grab_release()

    def _request_color_copy(self, slot_index: int):
        """Delegate a colour-only copy for one fixed Color Slot."""
        if self._on_color_copied is not None:
            return self._on_color_copied(slot_index)
        return None

    def _request_color_paste(self, slot_index: int):
        """Delegate a colour-only paste for one fixed Color Slot."""
        if self._on_color_pasted is not None:
            return self._on_color_pasted(slot_index)
        return None

    def _request_color_and_settings_copy(self, slot_index: int):
        """Delegate a complete slot-state copy for one fixed Color Slot."""
        if self._on_color_and_settings_copied is not None:
            return self._on_color_and_settings_copied(slot_index)
        return None

    def _request_color_and_settings_paste(self, slot_index: int):
        """Delegate a complete slot-state paste for one fixed Color Slot."""
        if self._on_color_and_settings_pasted is not None:
            return self._on_color_and_settings_pasted(slot_index)
        return None

    def _request_color_reset(self, slot_index: int):
        """Delegate a reset for one fixed Color Slot."""
        if self._on_color_reset is not None:
            return self._on_color_reset(slot_index)
        return None

    def _request_slot_swap(self, source_index: int, target_index: int):
        """Delegate one UI swap request to the application operation."""
        if self._on_slots_swapped is not None:
            return self._on_slots_swapped(source_index, target_index)
        return None

    def _slot_index_at_pointer(self, root_x: int, root_y: int) -> Optional[int]:
        """Resolve a root-window pointer position to a fixed Color Slot."""
        for index, slot in enumerate(self.color_slots):
            left = slot.winfo_rootx()
            top = slot.winfo_rooty()
            if (
                left <= root_x < left + slot.winfo_width()
                and top <= root_y < top + slot.winfo_height()
            ):
                return index
        return None

    def select_slot(self, slot_index: int, Event=None):
        """Select a slot without opening its Color Picker."""
        if not 0 <= slot_index < len(self.color_boxes):
            raise ValueError("slot_index must identify one of the four color slots.")
        self.active_slot_index = slot_index
        self._draw_active_slot()
        self._on_slot_selected(slot_index)

    def _draw_active_slot(self):
        for index, color_box in enumerate(self.color_boxes):
            active = index == self.active_slot_index
            dragging = self._drag_started and index == self._drag_source_index
            drop_target = self._drag_started and index == self._drag_target_index
            outline = (
                COLOR_SLOT_DROP_TARGET_OUTLINE
                if drop_target
                else (
                    PAINT_SWATCH_SELECTED_OUTLINE
                    if active
                    else self.color_slots[index].cget("bg")
                )
            )
            color_box.configure(
                relief=tk.FLAT if dragging else (tk.SUNKEN if active else tk.RAISED),
                bd=2,
                highlightthickness=2,
                highlightbackground=outline,
                highlightcolor=outline,
            )

    def apply_color(self, btn_idx: int, Event=None):
        color = self._color_picker(str(self.color_boxes[btn_idx]["bg"]))
        if color is not None:
            if not hasattr(self, "_color_identities"):
                self._color_identities = [None] * 4
            self._color_identities[btn_idx] = getattr(
                color, "custom_favorite", None
            )
            self.color_boxes[btn_idx]["bg"] = color
            self.draw_rgb_value()
            self._on_color_changed(btn_idx, color)

    def draw_rgb_value(self):
        for index, color_box in enumerate(self.color_boxes):
            color = str(color_box["bg"])
            presentation = color_slot_presentation(
                color,
                self.paint_catalog,
                COLOR_BOX_SIZE - 8,
                self._color_text_font.measure,
                self._color_identities[index],
            )
            self._color_tooltips[index] = presentation.tooltip
            color_box.delete("all")
            color_box.create_text(
                COLOR_BOX_SIZE / 2,
                COLOR_BOX_SIZE / 2,
                text=presentation.text,
                fill=presentation.foreground,
                font=self._color_text_font,
                justify=tk.CENTER,
            )

    def _show_color_tooltip(self, index: int, Event) -> None:
        self._hide_color_tooltip()
        text = self._color_tooltips[index]
        if text is None:
            return
        tooltip = tk.Toplevel(self)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(
            f"+{Event.widget.winfo_rootx() + 12}"
            f"+{Event.widget.winfo_rooty() + Event.widget.winfo_height() + 4}"
        )
        tk.Label(
            tooltip,
            text=text,
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            padx=5,
            pady=3,
        ).pack()
        self._color_tooltip_window = tooltip

    def _hide_color_tooltip(self, Event=None) -> None:
        if self._color_tooltip_window is not None:
            self._color_tooltip_window.destroy()
            self._color_tooltip_window = None


class FrameSlider(tk.Frame):
    """Level controls for team-colour processing."""

    def __init__(
        self,
        master=None,
        cnf={},
        *,
        on_levels_changed: LevelsChangedCallback,
        on_interaction_started: Optional[ActionCallback] = None,
        on_interaction_finished: Optional[ActionCallback] = None,
        **kw,
    ):
        super(FrameSlider, self).__init__(master=master, cnf={}, **kw)
        self._on_levels_changed = on_levels_changed
        self._on_interaction_started = on_interaction_started
        self._on_interaction_finished = on_interaction_finished
        self._slider_values = []
        self.brightness_slider = self._create_slider_block(
            "Brightness", 75, MIN_BRIGHTNESS, MAX_BRIGHTNESS
        )
        self.contrast_slider = self._create_slider_block(
            "Contrast", 100, MIN_CONTRAST, MAX_CONTRAST
        )
        self.saturation_slider = self._create_slider_block(
            "Saturation", 100, MIN_SATURATION, MAX_SATURATION
        )
        self.opacity_slider = self._create_slider_block(
            "Opacity", 100, MIN_OPACITY, MAX_OPACITY
        )

        for slider in (
            self.brightness_slider,
            self.contrast_slider,
            self.saturation_slider,
            self.opacity_slider,
        ):
            slider.bind("<ButtonPress-1>", self._notify_interaction_started)
            slider.bind("<ButtonRelease-1>", self._notify_interaction_finished)

    def _create_slider_block(self, label, initial_value, minimum, maximum):
        value = tk.IntVar(self, value=initial_value)
        self._slider_values.append(value)
        block = tk.Frame(self)
        block.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(0, 3))
        header = tk.Frame(block)
        header.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(header, text=label).pack(side=tk.LEFT)
        ttk.Label(header, textvariable=value).pack(side=tk.RIGHT)
        slider = tk.Scale(
            block,
            variable=value,
            showvalue=False,
            length=300,
            from_=minimum,
            to=maximum,
            orient=tk.HORIZONTAL,
            command=self._notify_levels_changed,
        )
        slider.pack(side=tk.TOP, fill=tk.X, pady=(1, 0))
        return slider

    def _notify_levels_changed(self, value=None):
        self._on_levels_changed(
            float(self.brightness_slider.get()),
            float(self.contrast_slider.get()),
            float(self.saturation_slider.get()),
            float(self.opacity_slider.get()),
        )

    def _notify_interaction_started(self, Event=None):
        if self._on_interaction_started is not None:
            self._on_interaction_started()

    def _notify_interaction_finished(self, Event=None):
        if self._on_interaction_finished is not None:
            self._on_interaction_finished()


class FrameColorOps(tk.LabelFrame):
    """Compact blend-mode selector that reports a stable operation ID."""

    def __init__(
        self,
        master=None,
        cnf={},
        *,
        on_operation_changed: StringChangedCallback,
        on_processing_mode_changed: StringChangedCallback,
        initial_operation: ColorOps,
        **kw,
    ):
        super(FrameColorOps, self).__init__(master=master, cnf={}, **kw)
        configure_app_selection_styles(self)
        self._on_operation_changed = on_operation_changed
        self._on_processing_mode_changed = on_processing_mode_changed
        display_names = tuple(op.display_name for op in IMPLEMENTED_BLEND_MODES)
        self.processing_mode_var = tk.StringVar(value=ProcessingMode.GLOBAL.value)
        self.settings_label = ttk.Label(self, text="Settings:")
        self.settings_label.pack(side=tk.LEFT, padx=(4, 2), pady=4)
        self.global_mode_button = ttk.Radiobutton(
            self,
            text=ProcessingMode.GLOBAL.display_name,
            value=ProcessingMode.GLOBAL.value,
            variable=self.processing_mode_var,
            command=self._notify_processing_mode_changed,
        )
        self.global_mode_button.pack(side=tk.LEFT, padx=(0, 1), pady=4)
        self.per_color_mode_button = ttk.Radiobutton(
            self,
            text=ProcessingMode.PER_COLOR.display_name,
            value=ProcessingMode.PER_COLOR.value,
            variable=self.processing_mode_var,
            command=self._notify_processing_mode_changed,
        )
        self.per_color_mode_button.pack(side=tk.LEFT, padx=(0, 6), pady=4)
        self.editing_label = ttk.Label(self, text="Editing: Color 1")
        self._editing_indicator_visible = False
        self.var = tk.StringVar(value=initial_operation.display_name)
        self.blend_mode_label = ttk.Label(self, text="Blend Mode:")
        self.blend_mode_label.pack(side=tk.LEFT, padx=(4, 4), pady=4)
        self.blend_mode_selector = ttk.Combobox(
            self,
            textvariable=self.var,
            values=display_names,
            state="readonly",
            style=APP_COMBOBOX_STYLE,
            width=max(len(name) for name in display_names),
            height=len(display_names),
        )
        self.blend_mode_selector.pack(side=tk.LEFT, padx=(0, 4), pady=4)
        self.blend_mode_selector.bind(
            "<<ComboboxSelected>>",
            self._notify_operation_changed,
        )
        clear_readonly_combobox_text_selection(self.blend_mode_selector)
        show_readonly_combobox_value(self.blend_mode_selector, self.var.get())

    def _notify_operation_changed(self, Event=None):
        self._on_operation_changed(ColorOps.parse(self.var.get()).value)

    def _notify_processing_mode_changed(self):
        mode = ProcessingMode.parse(self.processing_mode_var.get())
        self._on_processing_mode_changed(mode.value)

    def set_processing_context(
        self,
        mode: ProcessingMode,
        active_slot: ColorSlot,
    ):
        """Show the selected mode and active-slot editing context."""
        if not isinstance(mode, ProcessingMode):
            raise TypeError("mode must be a ProcessingMode value.")
        if not isinstance(active_slot, ColorSlot):
            raise TypeError("active_slot must be a ColorSlot value.")
        self.processing_mode_var.set(mode.value)
        if mode is ProcessingMode.PER_COLOR:
            self.editing_label.configure(
                text=f"Editing: {active_slot.display_name}"
            )
            if not self._editing_indicator_visible:
                self.editing_label.pack(
                    side=tk.LEFT,
                    padx=(8, 6),
                    pady=4,
                )
                self._editing_indicator_visible = True
        elif self._editing_indicator_visible:
            self.editing_label.pack_forget()
            self._editing_indicator_visible = False


class PatternTreeview(ttk.Treeview):
    """Treeview that keeps pattern identity separate from visible values."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.pattern_metadata = {}
        self.item_by_pattern_name = {}

    def clear_patterns(self):
        children = self.get_children()
        if children:
            self.delete(*children)
        self.pattern_metadata.clear()
        self.item_by_pattern_name.clear()

    def insert_pattern(
        self,
        pattern_name,
        user_created,
        marker_color=PatternMarkerColor.DEFAULT,
    ):
        item_id = self.insert(
            "",
            tk.END,
            values=(pattern_name, ""),
        )
        self.pattern_metadata[item_id] = {
            "name": pattern_name,
            "is_user": user_created,
        }
        self.item_by_pattern_name[pattern_name] = item_id
        self.set_pattern_marker(item_id, marker_color)
        return item_id

    def set_pattern_marker(self, item_id, marker_color):
        metadata = self.pattern_metadata.get(item_id)
        if metadata is None or not metadata["is_user"]:
            return
        metadata["marker_color"] = marker_color
        self.item(item_id, tags=(f"marker-{marker_color.value}",))

    def get_pattern_name(self, item_id):
        metadata = self.pattern_metadata.get(item_id)
        return metadata["name"] if metadata is not None else None

    def is_user_item(self, item_id):
        metadata = self.pattern_metadata.get(item_id)
        return bool(metadata and metadata["is_user"])

    def get_pattern_marker(self, item_id):
        metadata = self.pattern_metadata.get(item_id)
        if metadata is None or not metadata["is_user"]:
            return PatternMarkerColor.DEFAULT
        return metadata.get("marker_color", PatternMarkerColor.DEFAULT)

    def get_pattern_item_id(self, pattern_name):
        return self.item_by_pattern_name.get(pattern_name)


class FramePatternList(tk.Frame):
    """Pattern display that forwards user intent through explicit callbacks.

    Selection and state callbacks are optional. They remain disabled until
    ``enable_external_callbacks`` is called after controller assignment.
    """

    def __init__(
        self,
        master=None,
        cnf={},
        *,
        on_save_new: ActionCallback,
        on_update: ActionCallback,
        on_rename: ActionCallback,
        on_delete: ActionCallback,
        on_selection_changed: Optional[ActionCallback] = None,
        on_state_changed: Optional[ActionCallback] = None,
        on_marker_changed: Optional[PatternMarkerCallback] = None,
        on_pattern_reordered: Optional[PatternReorderCallback] = None,
        **kw,
    ):
        super(FramePatternList, self).__init__(master=master, cnf={}, **kw)
        self._on_save_new = on_save_new
        self._on_update = on_update
        self._on_rename = on_rename
        self._on_delete = on_delete
        self._on_selection_changed = on_selection_changed
        self._on_state_changed = on_state_changed
        self._on_marker_changed = on_marker_changed
        self._on_pattern_reordered = on_pattern_reordered
        self._external_callbacks_enabled = False
        self.pattern_style = ttk.Style(self)
        heading_font = (
            self.pattern_style.lookup("Treeview.Heading", "font") or "TkHeadingFont"
        )
        self.pattern_heading_font = tkfont.Font(root=self, font=heading_font)
        self.pattern_heading_font.configure(weight=tkfont.BOLD)
        self.pattern_style.configure(
            "Pattern.Treeview.Heading", font=self.pattern_heading_font
        )
        self.pattern_style.map(
            "Pattern.Treeview",
            background=[("selected", APP_SELECTION_BACKGROUND)],
            foreground=[("selected", APP_SELECTION_FOREGROUND)],
        )
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tree_frame = tk.Frame(self)
        self.tree_frame.grid(row=0, column=0, sticky=tk.NSEW)

        self.scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = PatternTreeview(
            self.tree_frame,
            columns=("pattern_name", "marker"),
            show="headings",
            selectmode="browse",
            style="Pattern.Treeview",
            yscrollcommand=self._set_pattern_scroll,
        )
        self.tree.heading("pattern_name", text="Pattern", anchor=tk.W)
        self.tree.heading("marker", text="", anchor=tk.E)
        self.tree.column("pattern_name", anchor=tk.W, stretch=True)
        self.tree.column(
            "marker",
            anchor=tk.E,
            width=PATTERN_MARKER_COLUMN_WIDTH,
            minwidth=PATTERN_MARKER_COLUMN_WIDTH,
            stretch=False,
        )
        self.scrollbar.config(command=self._scroll_pattern_tree)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.marker_labels = []
        self.marker_menu = tk.Menu(self, tearoff=False)
        self._marker_menu_background = self.marker_menu.cget("background")
        self._marker_menu_active_background = self.marker_menu.cget(
            "activebackground"
        )
        self._marker_menu_active_foreground = self.marker_menu.cget(
            "activeforeground"
        )
        self._marker_menu_disabled_foreground = self.marker_menu.cget(
            "disabledforeground"
        )
        self._marker_menu_action_indices = {}
        for label, callback in (
            ("Save New", self._on_save_new),
            ("Update", self._on_update),
            ("Rename", self._on_rename),
            ("Delete", self._on_delete),
        ):
            self.marker_menu.add_command(label=label, command=callback)
            self._marker_menu_action_indices[label] = self.marker_menu.index(tk.END)
        self.marker_menu.add_separator()
        self.marker_menu.add_command(label="Marker Color", state=tk.DISABLED)
        self._marker_menu_heading_index = self.marker_menu.index(tk.END)
        self.marker_menu.entryconfigure(
            self._marker_menu_heading_index,
            activebackground=self._marker_menu_background,
            activeforeground=self._marker_menu_disabled_foreground,
        )
        self.marker_menu.bind("<<MenuSelect>>", self._suppress_marker_menu_heading)
        self.marker_menu.bind("<Motion>", self._suppress_marker_menu_heading, add="+")
        self.marker_menu.add_separator()
        self._marker_menu_marker_indices = []
        self._marker_menu_color = tk.StringVar(
            self, value=PatternMarkerColor.DEFAULT.value
        )
        for marker_color in PatternMarkerColor:
            self.marker_menu.add_radiobutton(
                label=marker_color.name.title(),
                variable=self._marker_menu_color,
                value=marker_color.value,
                accelerator="★",
                command=partial(self._assign_context_marker, marker_color),
            )
            menu_index = self.marker_menu.index(tk.END)
            self._marker_menu_marker_indices.append(menu_index)
            self.marker_menu.entryconfigure(
                menu_index,
                foreground=pattern_marker_display_color(marker_color, False),
                activeforeground=pattern_marker_display_color(marker_color, True),
            )
        self._context_pattern_item = None
        self._drag_pattern_item = None
        self._drag_pattern_start = None
        self._drag_pattern_target = None
        self._drag_pattern_target_index = None
        self._pattern_drag_started = False
        self.tree.bind("<Button-3>", self._show_pattern_context_menu, add="+")
        self.tree.bind("<ButtonPress-1>", self._on_pattern_drag_press, add="+")
        self.tree.bind("<B1-Motion>", self._on_pattern_drag_motion, add="+")
        self.tree.bind(
            "<ButtonRelease-1>", self._on_pattern_drag_release, add="+"
        )
        self.bind("<Escape>", self._cancel_pattern_drag, add="+")
        self.header_separator_pressed = False
        self.tree.bind("<Button-1>", self._block_header_separator_press, add="+")
        self.tree.bind("<B1-Motion>", self._block_header_separator_drag, add="+")
        self.tree.bind(
            "<ButtonRelease-1>",
            self._block_header_separator_release,
            add="+",
        )
        self.tree.bind("<Motion>", self._update_header_separator_cursor, add="+")
        self.tree.bind("<Leave>", self._restore_tree_cursor, add="+")

        self.column_separator = ttk.Separator(
            self.tree_frame, orient=tk.VERTICAL, takefocus=False
        )
        self.header_separator = ttk.Separator(
            self.tree_frame, orient=tk.HORIZONTAL, takefocus=False
        )
        self.pattern_drop_indicator = ttk.Separator(
            self.tree_frame, orient=tk.HORIZONTAL, takefocus=False
        )
        self.user_block_separator = ttk.Separator(
            self.tree_frame, orient=tk.HORIZONTAL, takefocus=False
        )
        self.user_block_separator.bind(
            "<ButtonPress-1>", self._block_user_separator_drag_start
        )
        self.user_block_separator.bind(
            "<B1-Motion>", self._on_pattern_drag_motion
        )
        self.user_block_separator.bind(
            "<ButtonRelease-1>", self._on_pattern_drag_release
        )
        self.user_block_separator.bind(
            "<MouseWheel>", self._scroll_tree_through_separator
        )
        self.user_block_separator.bind(
            "<Button-4>", self._scroll_tree_up_through_separator
        )
        self.user_block_separator.bind(
            "<Button-5>", self._scroll_tree_down_through_separator
        )
        self.header_separator_startup_retries = HEADER_SEPARATOR_STARTUP_RETRIES
        self.header_separator_startup_after_id = None
        self.header_separator_map_binding_id = self.tree.bind(
            "<Map>", self._on_tree_mapped, add="+"
        )
        self.tree.bind("<Configure>", self._position_column_separator, add="+")
        self.tree.bind("<Configure>", self._position_header_separator, add="+")
        self.tree.bind("<<ThemeChanged>>", self._schedule_separator_position, add="+")
        self.column_separator.bind("<Button-1>", self._select_row_through_separator)
        self.column_separator.bind("<MouseWheel>", self._scroll_tree_through_separator)
        self.column_separator.bind("<Button-4>", self._scroll_tree_up_through_separator)
        self.column_separator.bind(
            "<Button-5>", self._scroll_tree_down_through_separator
        )
        self.header_separator.bind("<MouseWheel>", self._scroll_tree_through_separator)
        self.header_separator.bind("<Button-4>", self._scroll_tree_up_through_separator)
        self.header_separator.bind(
            "<Button-5>", self._scroll_tree_down_through_separator
        )
        self.after_idle(self._position_column_separator)

        self.load_pattern_list(notify_state=False)
        self._create_action_buttons()
        self.set_pattern_action_states(
            derive_pattern_action_state(
                PatternActionContext(False, False, False, False)
            )
        )

    def enable_external_callbacks(self):
        """Enable controller notifications after widget assignment completes."""
        if self._external_callbacks_enabled:
            return
        self.tree.bind("<<TreeviewSelect>>", self._notify_selection_changed, add="+")
        self._external_callbacks_enabled = True

    def _create_action_buttons(self):
        self.action_frame = tk.Frame(self)
        self.action_frame.grid(row=1, column=0, sticky=tk.EW)
        self.action_frame.grid_columnconfigure(0, weight=1)
        self.action_frame.grid_columnconfigure(1, weight=1)

        self.modified_label = ttk.Label(
            self.action_frame,
            text="",
            anchor=tk.W,
        )
        self.save_new_button = tk.Button(
            self.action_frame,
            text="Save New",
            command=self._on_save_new,
        )
        self.update_button = tk.Button(
            self.action_frame,
            text="Update",
            command=self._on_update,
            state=tk.DISABLED,
        )
        self.rename_button = tk.Button(
            self.action_frame,
            text="Rename",
            command=self._on_rename,
            state=tk.DISABLED,
        )
        self.delete_button = tk.Button(
            self.action_frame,
            text="Delete",
            command=self._on_delete,
            state=tk.DISABLED,
        )

        self.modified_label.grid(
            row=0, column=0, columnspan=2, sticky=tk.EW, padx=2, pady=(2, 0)
        )
        self.save_new_button.grid(row=1, column=0, sticky=tk.EW, padx=2, pady=2)
        self.update_button.grid(row=1, column=1, sticky=tk.EW, padx=2, pady=2)
        self.rename_button.grid(row=2, column=0, sticky=tk.EW, padx=2, pady=2)
        self.delete_button.grid(row=2, column=1, sticky=tk.EW, padx=2, pady=2)

    def _notify_selection_changed(self, Event=None):
        if hasattr(self, "marker_labels"):
            self._update_pattern_marker_selection()
        if self._external_callbacks_enabled and self._on_selection_changed is not None:
            self._on_selection_changed()

    def _set_pattern_scroll(self, first, last):
        self.scrollbar.set(first, last)
        if hasattr(self, "marker_labels"):
            self._redraw_pattern_markers()
        if hasattr(self, "user_block_separator"):
            self._position_user_block_separator()

    def _scroll_pattern_tree(self, *args):
        self.tree.yview(*args)

    def _show_pattern_context_menu(self, Event):
        item_id = self.tree.identify_row(Event.y)
        return FramePatternList._show_pattern_item_context_menu(
            self,
            item_id,
            getattr(Event, "x_root", 0),
            getattr(Event, "y_root", 0),
        )

    def _suppress_marker_menu_heading(self, Event=None):
        hovered_index = (
            self.marker_menu.index(f"@{Event.y}") if Event is not None else None
        )
        if (
            hovered_index == self._marker_menu_heading_index
            or self.marker_menu.index(tk.ACTIVE) == self._marker_menu_heading_index
        ):
            self.marker_menu.activate(tk.NONE)
            self.marker_menu.after_idle(
                partial(self.marker_menu.activate, tk.NONE)
            )

    def _show_pattern_item_context_menu(self, item_id, x_root, y_root):
        if not item_id:
            self._context_pattern_item = None
            return
        self._context_pattern_item = item_id
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self.update_idletasks()
        is_user_pattern = self.tree.is_user_item(item_id)
        self._marker_menu_color.set(self.tree.get_pattern_marker(item_id).value)
        marker_state = tk.NORMAL if is_user_pattern else tk.DISABLED
        for marker_color, menu_index in zip(
            PatternMarkerColor, self._marker_menu_marker_indices
        ):
            options = {
                "state": marker_state,
                "activebackground": (
                    self._marker_menu_active_background
                    if is_user_pattern
                    else self._marker_menu_background
                ),
                "activeforeground": (
                    pattern_marker_display_color(marker_color, True)
                    if is_user_pattern
                    else self._marker_menu_disabled_foreground
                ),
            }
            self.marker_menu.entryconfigure(menu_index, **options)
        self.marker_menu.tk_popup(x_root, y_root)
        return "break"

    def _assign_context_marker(self, marker_color):
        item_id = self._context_pattern_item
        self._context_pattern_item = None
        if item_id is None or not self.tree.is_user_item(item_id):
            return
        pattern_name = self.tree.get_pattern_name(item_id)
        if pattern_name is None or self._on_marker_changed is None:
            return
        if self._on_marker_changed(pattern_name, marker_color) is False:
            return
        self.tree.set_pattern_marker(item_id, marker_color)
        if hasattr(self, "marker_labels"):
            self._redraw_pattern_markers()

    def _select_pattern_item(self, item_id):
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        return "break"

    def _on_pattern_drag_press(self, Event, item_id=None):
        self._cancel_pattern_drag()
        if item_id is None:
            item_id = self.tree.identify_row(Event.y)
        if not item_id or not self.tree.is_user_item(item_id):
            return
        self._drag_pattern_item = item_id
        self._drag_pattern_start = (Event.x_root, Event.y_root)

    def _block_user_separator_drag_start(self, Event=None):
        self._cancel_pattern_drag()
        return "break"

    def _on_pattern_drag_motion(self, Event):
        if self._drag_pattern_item is None or self._drag_pattern_start is None:
            return
        if not self._pattern_drag_started:
            start_x, start_y = self._drag_pattern_start
            distance_squared = (Event.x_root - start_x) ** 2 + (
                Event.y_root - start_y
            ) ** 2
            if distance_squared < PATTERN_DRAG_THRESHOLD**2:
                return
            self._pattern_drag_started = True
        tree_y = Event.y_root - self.tree.winfo_rooty()
        target_item = self.tree.identify_row(tree_y)
        user_items = [
            item
            for item in self.tree.get_children()
            if self.tree.is_user_item(item)
        ]
        destination = (
            pattern_drop_destination(
                user_items,
                self._drag_pattern_item,
                target_item,
                tree_y,
                self.tree.bbox(target_item),
            )
            if target_item and self.tree.is_user_item(target_item)
            else None
        )
        if destination is None:
            self._drag_pattern_target = None
            self._drag_pattern_target_index = None
            self.pattern_drop_indicator.place_forget()
            return
        self._drag_pattern_target = target_item
        self._drag_pattern_target_index, line_y = destination
        self.pattern_drop_indicator.place(
            x=self.tree.winfo_x(),
            y=self.tree.winfo_y() + line_y - 1,
            width=self.tree.winfo_width(),
        )
        self.pattern_drop_indicator.lift()

    def _on_pattern_drag_release(self, Event=None):
        source_item = self._drag_pattern_item
        target_item = self._drag_pattern_target
        target_index = self._drag_pattern_target_index
        dragging = self._pattern_drag_started
        self._cancel_pattern_drag()
        if (
            not dragging
            or source_item is None
            or target_item is None
            or target_index is None
            or self._on_pattern_reordered is None
        ):
            return
        source_name = self.tree.get_pattern_name(source_item)
        user_items = [
            item
            for item in self.tree.get_children()
            if self.tree.is_user_item(item)
        ]
        if source_name is None or target_item not in user_items:
            return
        if self._on_pattern_reordered(source_name, target_index) is False:
            return
        self.load_pattern_list(source_name)

    def _cancel_pattern_drag(self, Event=None):
        self._drag_pattern_item = None
        self._drag_pattern_start = None
        self._drag_pattern_target = None
        self._drag_pattern_target_index = None
        self._pattern_drag_started = False
        if hasattr(self, "pattern_drop_indicator"):
            self.pattern_drop_indicator.place_forget()

    def _on_marker_drag_press(self, Event, item_id):
        self._select_pattern_item(item_id)
        self._on_pattern_drag_press(Event, item_id)

    def _redraw_pattern_markers(self):
        for label in self.marker_labels:
            label.destroy()
        self.marker_labels.clear()

        selected_items = set(self.tree.selection())
        tree_font = self.pattern_style.lookup("Pattern.Treeview", "font")
        normal_background = (
            self.pattern_style.lookup("Pattern.Treeview", "background") or "white"
        )
        for item_id in self.tree.get_children():
            metadata = self.tree.pattern_metadata.get(item_id)
            if not pattern_item_has_marker(metadata):
                continue
            marker_color = metadata.get(
                "marker_color", PatternMarkerColor.DEFAULT
            )
            bbox = self.tree.bbox(item_id, "marker")
            if not bbox:
                continue
            x, y, width, height = bbox
            visible_height = clipped_pattern_marker_height(
                y,
                height,
                self.tree.winfo_height(),
                max(self._tree_border_width(), 1),
            )
            if visible_height <= 0:
                continue
            selected = item_id in selected_items
            label = tk.Label(
                self.tree_frame,
                text="★",
                anchor=tk.CENTER,
                borderwidth=0,
                highlightthickness=0,
                font=tree_font or "TkDefaultFont",
                foreground=pattern_marker_display_color(marker_color, selected),
                background=(
                    APP_SELECTION_BACKGROUND if selected else normal_background
                ),
            )
            label.pattern_item_id = item_id
            label.place(
                x=self.tree.winfo_x() + x,
                y=self.tree.winfo_y() + y,
                width=width,
                height=visible_height,
            )
            label.bind(
                "<ButtonPress-1>",
                lambda Event, item=item_id: self._on_marker_drag_press(Event, item),
            )
            label.bind("<B1-Motion>", self._on_pattern_drag_motion)
            label.bind("<ButtonRelease-1>", self._on_pattern_drag_release)
            label.bind(
                "<Button-3>",
                lambda Event, item=item_id: self._show_pattern_item_context_menu(
                    item, Event.x_root, Event.y_root
                ),
            )
            label.bind("<MouseWheel>", self._scroll_tree_through_separator)
            label.bind("<Button-4>", self._scroll_tree_up_through_separator)
            label.bind("<Button-5>", self._scroll_tree_down_through_separator)
            label.lift()
            self.marker_labels.append(label)
        if hasattr(self, "column_separator"):
            self.column_separator.lift()
        if hasattr(self, "header_separator"):
            self.header_separator.lift()
        if hasattr(self, "user_block_separator"):
            self._position_user_block_separator()

    def _update_pattern_marker_selection(self):
        selected_items = set(self.tree.selection())
        normal_background = (
            self.pattern_style.lookup("Pattern.Treeview", "background") or "white"
        )
        for label in self.marker_labels:
            item_id = getattr(label, "pattern_item_id", None)
            metadata = self.tree.pattern_metadata.get(item_id)
            if not pattern_item_has_marker(metadata):
                continue
            selected = item_id in selected_items
            marker_color = metadata.get(
                "marker_color", PatternMarkerColor.DEFAULT
            )
            label.configure(
                foreground=pattern_marker_display_color(marker_color, selected),
                background=(
                    APP_SELECTION_BACKGROUND if selected else normal_background
                ),
            )

    def _tree_border_width(self):
        border_width = self.pattern_style.lookup(
            "Pattern.Treeview", "borderwidth", default=0
        )
        try:
            return round(float(border_width))
        except (TypeError, ValueError):
            return 0

    def _is_header_separator(self, Event):
        return self.tree.identify_region(Event.x, Event.y) == "separator"

    def _block_header_separator_press(self, Event):
        self.header_separator_pressed = self._is_header_separator(Event)
        if self.header_separator_pressed:
            self.tree.configure(cursor="arrow")
            return "break"

    def _block_header_separator_drag(self, Event):
        if self.header_separator_pressed or self._is_header_separator(Event):
            self.tree.configure(cursor="arrow")
            return "break"

    def _block_header_separator_release(self, Event):
        block_release = self.header_separator_pressed or self._is_header_separator(
            Event
        )
        self.header_separator_pressed = False
        if block_release:
            self.tree.configure(cursor="arrow")
            return "break"

    def _update_header_separator_cursor(self, Event):
        if self._is_header_separator(Event):
            self.tree.configure(cursor="arrow")
            return "break"
        self._restore_tree_cursor()

    def _restore_tree_cursor(self, Event=None):
        self.tree.configure(cursor="")

    def _position_column_separator(self, Event=None):
        tree_width = self.tree.winfo_width()
        tree_height = self.tree.winfo_height()
        if tree_width <= 1 or tree_height <= 1:
            return

        separator_x = calculate_pattern_separator_x(
            self.tree.winfo_x(),
            tree_width,
            PATTERN_MARKER_COLUMN_WIDTH,
            self._tree_border_width(),
        )
        self.column_separator.place(
            x=separator_x,
            y=self.tree.winfo_y(),
            height=tree_height,
        )
        self.column_separator.lift()

    def _schedule_separator_position(self, Event=None):
        self.after_idle(self._position_column_separator)
        self.after_idle(self._position_header_separator)
        self.after_idle(self._position_user_block_separator)
        self.after_idle(self._redraw_pattern_markers)

    def _on_tree_mapped(self, Event=None):
        self._schedule_initial_header_separator_position()

    def _schedule_initial_header_separator_position(self):
        if self.header_separator_startup_after_id is not None:
            return
        self.header_separator_startup_after_id = self.after_idle(
            self._position_initial_header_separator
        )

    def _position_initial_header_separator(self):
        self.header_separator_startup_after_id = None
        try:
            if not self.tree.winfo_exists():
                return
            self.tree.update_idletasks()
        except tk.TclError:
            return

        if self._position_header_separator():
            self.header_separator_startup_retries = 0
            if self.header_separator_map_binding_id is not None:
                self.tree.unbind("<Map>", self.header_separator_map_binding_id)
                self.header_separator_map_binding_id = None
            return

        self.header_separator_startup_retries -= 1
        if self.header_separator_startup_retries > 0:
            self._schedule_initial_header_separator_position()

    def _position_header_separator(self, Event=None):
        boundary_y = find_treeview_body_boundary(self.tree)
        if boundary_y is None:
            return False

        separator_height = max(self.header_separator.winfo_reqheight(), 1)
        separator_y = self.tree.winfo_y() + max(boundary_y - separator_height, 0)
        self.header_separator.place(
            x=self.tree.winfo_x(),
            y=separator_y,
            width=self.tree.winfo_width(),
        )
        self.header_separator.lift()
        return True

    def _position_user_block_separator(self, Event=None):
        first_user_item = first_user_pattern_item(
            self.tree.get_children(), self.tree.is_user_item
        )
        if first_user_item is None:
            self.user_block_separator.place_forget()
            return False
        bbox = self.tree.bbox(first_user_item)
        if not bbox:
            self.user_block_separator.place_forget()
            return False
        _x, row_y, _width, _height = bbox
        self.user_block_separator.place(
            x=self.tree.winfo_x(),
            y=self.tree.winfo_y() + max(row_y - 1, 0),
            width=self.tree.winfo_width(),
        )
        self.user_block_separator.lift()
        return True

    def _select_row_through_separator(self, Event):
        tree_y = Event.y_root - self.tree.winfo_rooty()
        item_id = self.tree.identify_row(tree_y)
        if item_id:
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)
        return "break"

    def _scroll_tree_through_separator(self, Event):
        tree_x = Event.x_root - self.tree.winfo_rootx()
        tree_y = Event.y_root - self.tree.winfo_rooty()
        self.tree.event_generate(
            "<MouseWheel>",
            x=tree_x,
            y=tree_y,
            delta=Event.delta,
        )
        return "break"

    def _scroll_tree_up_through_separator(self, Event):
        self.tree.yview_scroll(-1, "units")
        return "break"

    def _scroll_tree_down_through_separator(self, Event):
        self.tree.yview_scroll(1, "units")
        return "break"

    def load_pattern_list(self, preferred_pattern_name=None, notify_state=True):
        selection = self.get_selected_pattern()
        current_pattern_name = selection.name if selection else None
        self.tree.clear_patterns()
        rows = build_pattern_rows()
        for row in rows:
            self.tree.insert_pattern(
                row["name"],
                user_created=row["is_user"],
                marker_color=row["marker_color"],
            )
        pattern_name = pattern_name_to_restore(
            preferred_pattern_name,
            current_pattern_name,
            {row["name"] for row in rows},
        )
        if pattern_name is not None:
            self.select_pattern(pattern_name)
        if hasattr(self, "header_separator"):
            self.after_idle(self._position_header_separator)
        if hasattr(self, "user_block_separator"):
            self.after_idle(self._position_user_block_separator)
        if hasattr(self, "marker_labels"):
            self.after_idle(self._redraw_pattern_markers)
        if (
            notify_state
            and self._external_callbacks_enabled
            and self._on_state_changed is not None
        ):
            self._on_state_changed()

    def get_selected_item_id(self):
        selection = self.tree.selection()
        return selection[0] if selection else None

    def get_selected_pattern_name(self):
        selection = self.get_selected_pattern()
        return selection.name if selection else None

    def is_selected_pattern_user(self):
        selection = self.get_selected_pattern()
        return bool(selection and selection.is_user)

    def get_selected_pattern(self):
        item_id = self.get_selected_item_id()
        pattern_name = self.tree.get_pattern_name(item_id)
        if pattern_name is None:
            return None
        return PatternSelection(pattern_name, self.tree.is_user_item(item_id))

    def get_pattern_item_id(self, pattern_name):
        return self.tree.get_pattern_item_id(pattern_name)

    def get_selected_neighbor_pattern_name(self):
        selected_item = self.get_selected_item_id()
        if selected_item is None:
            return None

        items = list(self.tree.get_children())
        selected_index = items.index(selected_item)
        if selected_index + 1 < len(items):
            neighbor_item = items[selected_index + 1]
        elif selected_index > 0:
            neighbor_item = items[selected_index - 1]
        else:
            return None

        return self.tree.get_pattern_name(neighbor_item)

    def set_pattern_action_states(self, states):
        """Apply centralized Pattern action policy to buttons and row menu."""
        action_states = (
            ("Save New", self.save_new_button, states.save_new_enabled),
            ("Update", self.update_button, states.update_enabled),
            ("Rename", self.rename_button, states.rename_enabled),
            ("Delete", self.delete_button, states.delete_enabled),
        )
        for label, button, enabled in action_states:
            state = tk.NORMAL if enabled else tk.DISABLED
            button.config(state=state)
            self.marker_menu.entryconfigure(
                self._marker_menu_action_indices[label],
                state=state,
                activebackground=(
                    self._marker_menu_active_background
                    if enabled
                    else self._marker_menu_background
                ),
                activeforeground=(
                    self._marker_menu_active_foreground
                    if enabled
                    else self._marker_menu_disabled_foreground
                ),
            )
        self.modified_label.config(
            text="Modified" if states.modified_indicator_visible else ""
        )

    def select_pattern(self, pattern_name):
        item_id = self.get_pattern_item_id(pattern_name)
        if item_id is None:
            return None

        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self.tree.see(item_id)
        return item_id

    def clear_selection(self):
        """Remove the active Pattern row and its keyboard focus."""
        selected_items = self.tree.selection()
        if selected_items:
            self.tree.selection_remove(*selected_items)
        self.tree.focus("")


class PatternImportConflictDialog(tk.Toplevel):
    """Small modal dialog for explicit imported-pattern conflict choices."""

    def __init__(self, parent, pattern_name, user_conflict):
        super().__init__(parent)
        self.result = "cancel"
        self.title("Pattern Name Conflict")
        self.transient(parent)
        self.resizable(False, False)
        conflict_source = "user-created" if user_conflict else "built-in"
        ttk.Label(
            self,
            text=(
                f"A {conflict_source} pattern named '{pattern_name}' already " "exists."
            ),
            justify=tk.LEFT,
            wraplength=360,
            padding=(16, 16, 16, 8),
        ).pack(fill=tk.X)

        button_frame = ttk.Frame(self, padding=(12, 8, 12, 12))
        button_frame.pack(fill=tk.X)
        rename_button = ttk.Button(
            button_frame,
            text="Rename",
            command=lambda: self._finish("rename"),
        )
        rename_button.pack(side=tk.LEFT, padx=4)
        if user_conflict:
            ttk.Button(
                button_frame,
                text="Overwrite",
                command=lambda: self._finish("overwrite"),
            ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            button_frame,
            text="Cancel",
            command=lambda: self._finish("cancel"),
        ).pack(side=tk.RIGHT, padx=4)

        self.protocol("WM_DELETE_WINDOW", lambda: self._finish("cancel"))
        self.bind("<Escape>", lambda Event: self._finish("cancel"))
        self.bind("<Return>", lambda Event: self._finish("rename"))
        rename_button.focus_set()
        self.grab_set()
        self.wait_window()

    def _finish(self, result):
        self.result = result
        try:
            if self.winfo_exists():
                self.grab_release()
                self.destroy()
        except tk.TclError:
            # The parent may have destroyed this modal while it was open.
            pass


class PatternCollectionImportConfirmationDialog(tk.Toplevel):
    """Modal Import/Cancel confirmation for an all-new Pattern Collection."""

    def __init__(self, parent, collection_name, total_count, new_count):
        super().__init__(parent)
        self.result = False
        self.title("Import Pattern Collection")
        self.transient(parent)
        self.resizable(False, False)
        ttk.Label(
            self,
            text=(
                f"Collection: {collection_name}\n"
                f"Total Patterns: {total_count}\n"
                f"New Patterns: {new_count}"
            ),
            justify=tk.LEFT,
            padding=(16, 16, 16, 8),
        ).pack(fill=tk.X)

        button_frame = ttk.Frame(self, padding=(12, 8, 12, 12))
        button_frame.pack(fill=tk.X)
        import_button = ttk.Button(
            button_frame, text="Import", command=lambda: self._finish(True)
        )
        import_button.pack(side=tk.LEFT, padx=4)
        ttk.Button(
            button_frame, text="Cancel", command=lambda: self._finish(False)
        ).pack(side=tk.RIGHT, padx=4)

        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(False))
        self.bind("<Escape>", lambda Event: self._finish(False))
        self.bind("<Return>", lambda Event: self._finish(True))
        import_button.focus_set()
        self.grab_set()
        self.wait_window()

    def _finish(self, result):
        self.result = result
        try:
            if self.winfo_exists():
                self.grab_release()
                self.destroy()
        except tk.TclError:
            pass


class PatternCollectionConflictDialog(tk.Toplevel):
    """Modal summary and conflict policy for one Pattern Collection import."""

    def __init__(self, parent, analysis):
        super().__init__(parent)
        self.result = False
        self.overwrite_user_conflicts = False
        self.strategy = tk.StringVar(value="skip")
        self.title("Pattern Collection Conflicts")
        self.transient(parent)
        self.resizable(False, False)

        ttk.Label(
            self,
            text=(
                f"Collection: {analysis.collection_name}\n"
                f"Total Patterns: {analysis.total_pattern_count}\n"
                f"New Patterns: {analysis.new_pattern_count}\n"
                f"Existing user-Pattern conflicts: {analysis.user_conflict_count}\n"
                f"Built-in conflicts: {analysis.builtin_conflict_count}"
            ),
            justify=tk.LEFT,
            padding=(16, 16, 16, 8),
        ).pack(fill=tk.X)

        if analysis.user_conflict_count:
            strategy_frame = ttk.LabelFrame(
                self, text="Existing user Patterns", padding=(12, 8)
            )
            strategy_frame.pack(fill=tk.X, padx=16, pady=(4, 8))
            ttk.Radiobutton(
                strategy_frame,
                text="Skip existing user patterns",
                variable=self.strategy,
                value="skip",
            ).pack(anchor=tk.W)
            ttk.Radiobutton(
                strategy_frame,
                text="Overwrite existing user patterns",
                variable=self.strategy,
                value="overwrite",
            ).pack(anchor=tk.W)

        if analysis.builtin_conflict_count:
            ttk.Label(
                self,
                text="Built-in Patterns cannot be overwritten and will be skipped.",
                justify=tk.LEFT,
                wraplength=420,
                padding=(16, 0, 16, 8),
            ).pack(fill=tk.X)

        button_frame = ttk.Frame(self, padding=(12, 8, 12, 12))
        button_frame.pack(fill=tk.X)
        import_button = ttk.Button(button_frame, text="Import", command=self._import)
        import_button.pack(side=tk.LEFT, padx=4)
        ttk.Button(
            button_frame, text="Cancel", command=lambda: self._finish(False)
        ).pack(side=tk.RIGHT, padx=4)

        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(False))
        self.bind("<Escape>", lambda Event: self._finish(False))
        self.bind("<Return>", lambda Event: self._import())
        import_button.focus_set()
        self.grab_set()
        self.wait_window()

    def _import(self):
        self.overwrite_user_conflicts = self.strategy.get() == "overwrite"
        self._finish(True)

    def _finish(self, result):
        self.result = result
        try:
            if self.winfo_exists():
                self.grab_release()
                self.destroy()
        except tk.TclError:
            pass


class BatchEditTopLevel(tk.Toplevel):
    """Batch controls that forward edit, convert, and cancel intent."""

    def __init__(
        self,
        master=None,
        cnf={},
        *,
        on_batch_edit: ActionCallback,
        on_batch_convert: ActionCallback,
        on_cancel: ActionCallback,
        settings=None,
        **kw,
    ):
        super(BatchEditTopLevel, self).__init__(master=master, cnf={}, **kw)
        self._on_batch_edit = on_batch_edit
        self._on_batch_convert = on_batch_convert
        self._on_cancel = on_cancel
        self.settings = settings
        self.resizable(width=False, height=False)
        self.initialize()
        self.title("Batch Edit")
        self._restore_position()

    def _restore_position(self) -> None:
        self.update_idletasks()
        position = safe_window_position(
            getattr(self.settings, "batch_editor_position", None),
            self.winfo_width(),
            self.winfo_height(),
            self.winfo_vrootx(),
            self.winfo_vrooty(),
            self.winfo_vrootwidth(),
            self.winfo_vrootheight(),
        )
        if position is not None:
            self.geometry(f"{position[0]:+d}{position[1]:+d}")

    def destroy(self) -> None:
        self._save_position()
        super().destroy()

    def _save_position(self) -> None:
        setter = getattr(
            getattr(self, "settings", None),
            "set_batch_editor_position",
            None,
        )
        if setter is not None:
            try:
                setter((self.winfo_x(), self.winfo_y()))
            except OSError:
                LOGGER.exception("Could not save Batch Editor window position")

    def get_source_format_selected(self):
        source_format_selected = [
            chk_btn.cget("text").lower()
            for chk_btn, state in self.source_format_list
            if state.get()
        ]
        return source_format_selected

    def initialize(self):
        # Source format Checkbox list
        self.source_format_list = []
        self.frame_source_format = tk.LabelFrame(self, text="Source formats")
        self.frame_source_format.pack(side=tk.TOP, fill=tk.BOTH)
        # Tuple list to save btn widget & the checkbox state variable
        for idx, filetype in enumerate(OPEN_FILETYPES[1:]):
            checkbox_state = tk.IntVar()
            self.source_format_list.append(
                (
                    tk.Checkbutton(
                        self.frame_source_format,
                        text=filetype[1][1:].upper(),
                        variable=checkbox_state,
                        onvalue=True,
                        offvalue=False,
                    ),
                    checkbox_state,
                )
            )
            self.source_format_list[idx][0].pack(side=tk.LEFT)
        # Setting default input format
        self.source_format_list[0][0].toggle()

        # Destination Format Option Menu
        self.frame_destination_format = tk.Frame(self)
        self.frame_destination_format.pack(side=tk.TOP, fill=tk.X)
        tk.Label(self.frame_destination_format, text="Destination format:").pack(
            side=tk.LEFT
        )
        self.dest_format = tk.StringVar(self)
        self.dest_format.set(SAVE_EXT_LIST[0].upper())
        self.dest_menu = tk.OptionMenu(
            self.frame_destination_format,
            self.dest_format,
            *[fmt.upper() for fmt in SAVE_EXT_LIST],
        )
        self.dest_menu.pack(side=tk.LEFT)

        self.frame_actions = tk.Frame(self)
        self.batch_edit_button = tk.Button(
            self.frame_actions,
            text="Process Batch Edit",
            command=self._on_batch_edit,
        )
        self.batch_edit_button.pack(side=tk.LEFT)

        self.batch_convert_button = tk.Button(
            self.frame_actions,
            text="Process Batch Convert",
            command=self._on_batch_convert,
        )
        self.batch_convert_button.pack(side=tk.LEFT)

        self.cancel_button = tk.Button(
            self.frame_actions,
            text="Cancel",
            command=self._on_cancel,
            state=tk.DISABLED,
        )
        self.cancel_button.pack(side=tk.LEFT)

        def _select_folder(folder_path, Event=None):
            folder_path.set(filedialog.askdirectory(initialdir=os.curdir))
            self.focus()

        def widget_entry_template(
            frame,
            label,
            starting_value="",
            entry_width=60,
            label_width=len("Destination folder:"),
        ):
            entry_frame = tk.Frame(frame)
            entry_frame.pack(side=tk.TOP, fill=tk.X)
            tk.Label(entry_frame, text=label, width=label_width, anchor=tk.W).pack(
                side=tk.LEFT
            )
            entry_frame.entry_value = tk.StringVar(value=starting_value)
            entry_path = tk.Entry(
                entry_frame,
                textvariable=entry_frame.entry_value,
                width=60,
                exportselection=0,
            )
            entry_frame.entry_path = entry_path
            entry_path.pack(side=tk.LEFT)
            entry_button = tk.Button(
                entry_frame,
                text="...",
                command=lambda: (_select_folder(entry_frame.entry_value)),
            )
            entry_frame.entry_button = entry_button
            entry_button.pack(side=tk.LEFT)
            return entry_frame

        self.frame_folders = tk.Frame(self)
        self.frame_folders.pack(side=tk.TOP, fill=tk.X)
        self.frame_batch_src_path = widget_entry_template(
            self.frame_folders, "Source folder:"
        )
        self.frame_batch_dest_path = widget_entry_template(
            self.frame_folders, "Destination folder:"
        )

        self.frame_progress_bar = tk.LabelFrame(
            self, relief=tk.RIDGE, bd=2, text="Awaiting process"
        )
        self.frame_progress_bar.pack(side=tk.TOP, fill=tk.BOTH)

        self.progress_bar = Progressbar(
            self.frame_progress_bar,
            orient=HORIZONTAL,
            length=self.cget("width"),
            mode="determinate",
        )
        self.progress_bar.pack(side=tk.LEFT)
        self.frame_actions.pack(side=tk.TOP, fill=tk.X)

    def update_progress_bar_label(self, current: int):
        maximum = self.progress_bar["maximum"]
        self.progress_bar["value"] = current
        self.frame_progress_bar.configure(text=f"Completed {current}/{maximum} file(s)")

    def set_running(self, running):
        normal_state = tk.DISABLED if running else tk.NORMAL
        self.batch_edit_button.configure(state=normal_state)
        self.batch_convert_button.configure(state=normal_state)
        self.dest_menu.configure(state=normal_state)
        for checkbox, _ in self.source_format_list:
            checkbox.configure(state=normal_state)
        for entry_frame in (
            self.frame_batch_src_path,
            self.frame_batch_dest_path,
        ):
            entry_frame.entry_path.configure(state=normal_state)
            entry_frame.entry_button.configure(state=normal_state)
        self.cancel_button.configure(state=tk.NORMAL if running else tk.DISABLED)
