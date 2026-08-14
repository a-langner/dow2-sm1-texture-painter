import tkinter as tk
import logging
from tkinter.constants import HORIZONTAL
from tkinter import ttk
from tkinter import font as tkfont
from tkinter.ttk import Progressbar
import os
import math
from dataclasses import dataclass
import colorsys
from tkinter import filedialog
from functools import partial
from typing import Callable, Optional
from PIL import Image, ImageTk
from src.color_pattern_handler import get_all_patterns, is_user_pattern
from src.action_state import PatternActionContext, derive_pattern_action_state
from src.constant import OPEN_FILETYPES, SAVE_EXT_LIST, ColorOps
from src.paint_catalog import PaintCatalog, PaintColor, load_citadel_catalog
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
    VISUAL_GROUP_ORDER,
    get_paints_for_group,
    sort_paints_visually,
)
from src.recent_colors import MAX_RECENT_COLORS, RecentColors, add_recent_color
from src.render_settings import (
    MAX_BRIGHTNESS,
    MAX_CONTRAST,
    MIN_BRIGHTNESS,
    MIN_CONTRAST,
)
from src.window_geometry import safe_window_geometry

COLOR_BOX_SIZE = 90
COLOR_BTN_HEIGHT = 26
PATTERN_MARKER_COLUMN_WIDTH = 28
HEADER_SEPARATOR_STARTUP_RETRIES = 3
COLOR_PICKER_DEFAULT_WIDTH = 1196
COLOR_PICKER_DEFAULT_HEIGHT = 760
COLOR_PICKER_MIN_WIDTH = 900
COLOR_PICKER_MIN_HEIGHT = 760
COLOR_PICKER_SCREEN_MARGIN = 80
COLOR_PICKER_GROUP_PANE_WIDTH = 140
COLOR_PICKER_PALETTE_PANE_WIDTH = 636
COLOR_PICKER_EDITOR_PANE_WIDTH = 400
COLOR_PICKER_GROUP_ENTRIES = ((None, "All Colors"),) + tuple(
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
PAINT_SWATCH_TARGET_WIDTH = 96
PAINT_SWATCH_PREVIEW_SIZE = 60
PAINT_SWATCH_NAME_WRAP = 88
PAINT_SWATCH_CORNER_RADIUS = 20
PAINT_NAME_ELLIPSIS = "…"
PAINT_SEARCH_PLACEHOLDER = "Search Citadel colors..."
NO_CITADEL_COLORS_MESSAGE = "No Citadel colors found."
PAINT_TOOLTIP_DELAY_MS = 400
COLOR_PREVIEW_BORDER = "#707070"
COLOR_EDITOR_SECTION_GAP = 8
COLOR_EDITOR_GROUP_PADDING = (8, 6)
COLOR_MODEL_GROUP_PADDING = (4, 6)
COLOR_MODEL_CONTROL_WIDTH = 3
PAINT_SWATCH_OUTLINE = "#606060"
PAINT_SWATCH_SELECTED_OUTLINE = "#2f80ed"
COLOR_FIELD_PREFERRED_HEIGHT = 240
VISUAL_RESIZE_DELAY_MS = 40

ActionCallback = Callable[[], None]
BooleanChangedCallback = Callable[[bool], None]
ColorChangedCallback = Callable[[int, str], None]
ColorPickerCallback = Callable[[str], Optional[str]]
PaintSelectedCallback = Callable[[PaintColor], None]
RecentColorSelectedCallback = Callable[[str], None]
LevelsChangedCallback = Callable[[float, float], None]
StringChangedCallback = Callable[[str], None]
LOGGER = logging.getLogger(__name__)


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
) -> ColorSlotPresentation:
    """Return main-window text and exact-match details for one colour slot."""
    normalized = normalize_rgb_hex(color)
    channels = rgb_hex_to_channels(normalized)
    paint = paint_catalog.find_exact_rgb(channels)
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

    def __init__(self, parent, *, on_paint_selected: PaintSelectedCallback):
        super().__init__(parent)
        self._on_paint_selected = on_paint_selected
        self.paints = ()
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

    def _rebuild_items(self) -> None:
        self._hide_tooltip()
        self._schedule_relayout()

    def _select_paint(self, paint: PaintColor, Event=None) -> None:
        self._on_paint_selected(paint)

    def set_selected_paint(self, paint_id: Optional[str]) -> None:
        self.selected_paint_id = paint_id
        self._apply_selection_highlight()

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
                text=NO_CITADEL_COLORS_MESSAGE,
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
        self._updating_color_representations = False
        self._hsv_field_cache = None
        self._hsl_field_cache = None
        self._displayed_field_mode = None
        self._hue_slider_cache = None
        self._color_wheel_cache = None
        self._classic_field_cache = None
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
        self.selected_color_group = next(
            (group for group in VISUAL_GROUP_ORDER if group.value == saved_group),
            None,
        )
        self.paint_catalog = (
            load_citadel_catalog() if paint_catalog is None else paint_catalog
        )
        self.palette_paints = ()
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
                min(COLOR_PICKER_MIN_WIDTH, width),
                min(COLOR_PICKER_MIN_HEIGHT, height),
                self.winfo_vrootx(),
                self.winfo_vrooty(),
                self.winfo_vrootwidth(),
                self.winfo_vrootheight(),
            )
        self.geometry(geometry or f"{width}x{height}")
        self.minsize(
            min(COLOR_PICKER_MIN_WIDTH, width),
            min(COLOR_PICKER_MIN_HEIGHT, height),
        )

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
        self.palette_search_area = ttk.Frame(self.palette_header_area)
        self.palette_search_area.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.palette_count_area = ttk.Frame(self.palette_header_area)
        self.palette_count_area.pack(side=tk.RIGHT)
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
        )
        self.palette_grid.pack(fill=tk.BOTH, expand=True)

    def _build_palette_search(self) -> None:
        self.search_entry = ttk.Entry(self.palette_search_area)
        self.search_entry.insert(0, PAINT_SEARCH_PLACEHOLDER)
        self.search_entry.pack(fill=tk.X, expand=True)
        self.search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_search_focus_out)
        self.search_entry.bind("<KeyRelease>", self._on_search_key_released)
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
        if color_group is not None:
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

    def select_color_group(self, color_group: Optional[ColorGroup]) -> None:
        """Select a navigation group for the palette filter."""
        self.selected_color_group = color_group
        for candidate, button in self.group_buttons.items():
            selected = candidate is color_group
            button.state(["selected"] if selected else ["!selected"])
            marker = "▸ " if selected else "  "
            button.configure(text=f"{marker}{self.group_button_labels[candidate]}")
        self._refresh_palette_data_source()

    def _refresh_palette_data_source(self) -> None:
        paints = self.paint_catalog.paints
        if self.selected_color_group is not None:
            paints = get_paints_for_group(paints, self.selected_color_group)
        paints = sort_paints_visually(paints)
        self.palette_paints = filter_paints_by_name(paints, self.search_query)
        self._refresh_palette_display()

    def _refresh_palette_display(self) -> None:
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

    def _build_color_editor(self) -> None:
        ttk.Label(self.editor_color_space_area, text="Color Space:").pack(
            side=tk.LEFT, padx=(0, 6)
        )
        self.color_space_selector = ttk.Combobox(
            self.editor_color_space_area,
            values=COLOR_SPACE_MODES,
            state="readonly",
            width=12,
        )
        self.color_space_selector.set(self.color_space_mode)
        self.color_space_selector.pack(side=tk.LEFT)
        self.color_space_selector.bind(
            "<<ComboboxSelected>>", self._on_color_space_selected
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
        self.hex_input = ttk.Entry(self.editor_hex_area, width=9)
        self.hex_input.grid(row=0, column=1, sticky=tk.W)
        self.hex_input.bind("<Return>", self._on_hex_input_return)
        self.hex_input.bind("<FocusOut>", self._on_hex_input_focus_out)

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
        self._updating_color_representations = True
        try:
            self._refresh_color_representations()
        finally:
            self._updating_color_representations = False

    def _refresh_color_representations(self) -> None:
        """Fan the canonical color out to all editor controls."""
        self._refresh_rgb_controls()
        self._refresh_color_model_controls()
        self._refresh_hex_control()
        self._refresh_visual_picker()
        self._refresh_current_color_preview()

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

        scale = 2
        render_width = width * scale
        render_height = height * scale
        geometry = color_wheel_geometry(width, height)
        field_width = max(1.0, geometry.field_right - geometry.field_left)
        field_height = max(1.0, geometry.field_bottom - geometry.field_top)
        pixels = []
        for y in range(render_height):
            canvas_y = y / scale
            dy = canvas_y - geometry.center_y
            for x in range(render_width):
                canvas_x = x / scale
                dx = canvas_x - geometry.center_x
                radius = (dx * dx + dy * dy) ** 0.5
                if geometry.ring_inner_radius <= radius <= geometry.outer_radius:
                    ring_hue = color_wheel_hue_from_position(
                        canvas_x, canvas_y, geometry
                    )
                    rgb = colorsys.hsv_to_rgb(ring_hue, 1.0, 1.0)
                    pixels.append(
                        tuple(round(channel * 255) for channel in rgb) + (255,)
                    )
                elif (
                    geometry.field_left <= canvas_x <= geometry.field_right
                    and geometry.field_top <= canvas_y <= geometry.field_bottom
                ):
                    saturation = (canvas_x - geometry.field_left) / field_width
                    value = 1.0 - (canvas_y - geometry.field_top) / field_height
                    rgb = colorsys.hsv_to_rgb(hue, saturation, value)
                    pixels.append(
                        tuple(round(channel * 255) for channel in rgb) + (255,)
                    )
                else:
                    pixels.append((0, 0, 0, 0))
        image = Image.new("RGBA", (render_width, render_height))
        image.putdata(pixels)
        image = image.resize((width, height), Image.Resampling.LANCZOS)
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
        pixels = []
        for y in range(height):
            saturation = 1.0 - y / (height - 1)
            for x in range(width):
                hue = x / width
                rgb = colorsys.hsv_to_rgb(hue, saturation, value)
                pixels.append(tuple(round(channel * 255) for channel in rgb))
        image = Image.new("RGB", (width, height))
        image.putdata(pixels)
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
        self.accepted_color = self.current_color
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
        self.lb = tk.Listbox(self, selectmode=tk.MULTIPLE, height=4, width=9)
        self.lb.insert(0, "0 Red")
        self.lb.insert(1, "1 Green")
        self.lb.insert(2, "2 Blue")
        self.lb.insert(3, "3 Alpha")
        self.lb.pack(side=tk.TOP, fill=tk.Y)

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
        self.add_alpha.pack(side=tk.TOP, fill=tk.X)

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
        color_picker: Optional[ColorPickerCallback] = None,
        paint_catalog: Optional[PaintCatalog] = None,
        settings=None,
        **kw,
    ):
        super(FrameColorChooser, self).__init__(master=master, cnf={}, **kw)
        self._on_color_changed = on_color_changed
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
        self._color_tooltip_window = None
        self.color_boxes = []
        self.color_buttons = []
        self.initialize()

    def _open_color_picker(self, initial_color: str) -> Optional[str]:
        """Open the production custom picker with the slot's current color."""
        settings = getattr(self, "settings", None)
        if settings is None:
            return ColorPickerDialog.show(self, initial_color, self.paint_catalog)
        return ColorPickerDialog.show(self, initial_color, self.paint_catalog, settings)

    def initialize(self):
        for i in range(0, 4):
            self.color_boxes.append(
                tk.Canvas(
                    self,
                    bg="#808080",
                    relief=tk.RAISED,
                    bd=2,
                    height=COLOR_BOX_SIZE,
                    width=COLOR_BOX_SIZE,
                )
            )
            self.color_boxes[i].bind("<Button-1>", partial(self.apply_color, i))
            self.color_boxes[i].bind(
                "<Enter>", partial(self._show_color_tooltip, i)
            )
            self.color_boxes[i].bind("<Leave>", self._hide_color_tooltip)
            self.color_boxes[i].place(
                anchor=tk.NW, x=COLOR_BOX_SIZE * i, y=COLOR_BTN_HEIGHT
            )
            self.color_buttons.append(
                tk.Button(
                    self,
                    text=f"Choose Color {i + 1}",
                    wraplength=COLOR_BOX_SIZE,
                    relief=tk.RAISED,
                    bd=2,
                    command=partial(self.apply_color, i),
                )
            )
            self.color_buttons[i].place(anchor=tk.NW, x=COLOR_BOX_SIZE * i + i * 1, y=0)
        self.draw_rgb_value()

    def apply_color(self, btn_idx: int, Event=None):
        color = self._color_picker(str(self.color_boxes[btn_idx]["bg"]))
        if color is not None:
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
    """Brightness and contrast controls that report both current levels."""

    def __init__(
        self,
        master=None,
        cnf={},
        *,
        on_levels_changed: LevelsChangedCallback,
        **kw,
    ):
        super(FrameSlider, self).__init__(master=master, cnf={}, **kw)
        self._on_levels_changed = on_levels_changed

        # Brightness slider
        self.brightness_slider = tk.Scale(
            self,
            label="Brightness",
            length=150,
            from_=MIN_BRIGHTNESS,
            to=MAX_BRIGHTNESS,
            orient=tk.HORIZONTAL,
            command=self._notify_levels_changed,
        )
        self.brightness_slider.pack(side=tk.TOP, fill=tk.X)

        # Contrast slider
        self.contrast_slider = tk.Scale(
            self,
            label="Contrast",
            length=200,
            from_=MIN_CONTRAST,
            to=MAX_CONTRAST,
            orient=tk.HORIZONTAL,
            command=self._notify_levels_changed,
        )
        self.contrast_slider.pack(side=tk.TOP, fill=tk.X)

    def _notify_levels_changed(self, value=None):
        self._on_levels_changed(
            float(self.brightness_slider.get()),
            float(self.contrast_slider.get()),
        )


class FrameColorOps(tk.LabelFrame):
    """Color-operation controls that report the selected operation name."""

    def __init__(
        self,
        master=None,
        cnf={},
        *,
        on_operation_changed: StringChangedCallback,
        **kw,
    ):
        super(FrameColorOps, self).__init__(master=master, cnf={}, **kw)
        self._on_operation_changed = on_operation_changed
        self.color_operation_btn = {op.value: None for op in ColorOps}
        self.var = tk.StringVar(value=ColorOps.OVERLAY.value)
        for op_name, value in self.color_operation_btn.items():
            value = tk.Radiobutton(
                self,
                text=op_name,
                variable=self.var,
                value=op_name,
                command=self._notify_operation_changed,
            )
            value.pack(side=tk.LEFT)

    def _notify_operation_changed(self):
        self._on_operation_changed(self.var.get())


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

    def insert_pattern(self, pattern_name, user_created):
        item_id = self.insert(
            "",
            tk.END,
            values=(pattern_name, "★" if user_created else ""),
        )
        self.pattern_metadata[item_id] = {
            "name": pattern_name,
            "is_user": user_created,
        }
        self.item_by_pattern_name[pattern_name] = item_id
        return item_id

    def get_pattern_name(self, item_id):
        metadata = self.pattern_metadata.get(item_id)
        return metadata["name"] if metadata is not None else None

    def is_user_item(self, item_id):
        metadata = self.pattern_metadata.get(item_id)
        return bool(metadata and metadata["is_user"])

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
        **kw,
    ):
        super(FramePatternList, self).__init__(master=master, cnf={}, **kw)
        self._on_save_new = on_save_new
        self._on_update = on_update
        self._on_rename = on_rename
        self._on_delete = on_delete
        self._on_selection_changed = on_selection_changed
        self._on_state_changed = on_state_changed
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

        self.tree_frame = tk.Frame(self)
        self.tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = PatternTreeview(
            self.tree_frame,
            columns=("pattern_name", "marker"),
            show="headings",
            selectmode="browse",
            style="Pattern.Treeview",
            yscrollcommand=self.scrollbar.set,
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
        self.scrollbar.config(command=self.tree.yview)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
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
        self.action_frame.pack(side=tk.TOP, fill=tk.X)
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
        if self._external_callbacks_enabled and self._on_selection_changed is not None:
            self._on_selection_changed()

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
            self.tree.insert_pattern(row["name"], user_created=row["is_user"])
        pattern_name = pattern_name_to_restore(
            preferred_pattern_name,
            current_pattern_name,
            {row["name"] for row in rows},
        )
        if pattern_name is not None:
            self.select_pattern(pattern_name)
        if hasattr(self, "header_separator"):
            self.after_idle(self._position_header_separator)
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
        """Apply centralized Pattern action policy to this widget's buttons."""
        self.save_new_button.config(
            state=tk.NORMAL if states.save_new_enabled else tk.DISABLED
        )
        self.update_button.config(
            state=tk.NORMAL if states.update_enabled else tk.DISABLED
        )
        self.rename_button.config(
            state=tk.NORMAL if states.rename_enabled else tk.DISABLED
        )
        self.delete_button.config(
            state=tk.NORMAL if states.delete_enabled else tk.DISABLED
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
        **kw,
    ):
        super(BatchEditTopLevel, self).__init__(master=master, cnf={}, **kw)
        self._on_batch_edit = on_batch_edit
        self._on_batch_convert = on_batch_convert
        self._on_cancel = on_cancel
        self.resizable(width=False, height=False)
        self.initialize()
        self.title("Batch Edit")

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
        self.batch_edit_button = tk.Button(
            self.frame_destination_format,
            text="Process Batch Edit",
            command=self._on_batch_edit,
        )
        self.batch_edit_button.pack(side=tk.LEFT)

        self.batch_convert_button = tk.Button(
            self.frame_destination_format,
            text="Process Batch Convert",
            command=self._on_batch_convert,
        )
        self.batch_convert_button.pack(side=tk.LEFT)

        self.cancel_button = tk.Button(
            self.frame_destination_format,
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

        self.frame_batch_src_path = widget_entry_template(self, "Source folder:")
        self.frame_batch_dest_path = widget_entry_template(self, "Destination folder:")

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
