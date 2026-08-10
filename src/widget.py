import tkinter as tk
from tkinter.constants import HORIZONTAL
from tkinter import ttk
from tkinter import font as tkfont
from tkinter.ttk import Progressbar
import os
from dataclasses import dataclass
from tkinter import colorchooser, filedialog
from functools import partial
from typing import Callable, Optional
from src.color_pattern_handler import get_all_patterns, is_user_pattern
from src.action_state import PatternActionContext, derive_pattern_action_state
from src.constant import OPEN_FILETYPES, SAVE_EXT_LIST, ColorOps
from src.render_settings import (
    MAX_BRIGHTNESS,
    MAX_CONTRAST,
    MIN_BRIGHTNESS,
    MIN_CONTRAST,
)

COLOR_BOX_SIZE = 90
COLOR_BTN_HEIGHT = 26
PATTERN_MARKER_COLUMN_WIDTH = 28
HEADER_SEPARATOR_STARTUP_RETRIES = 3
COLOR_PICKER_DEFAULT_WIDTH = 960
COLOR_PICKER_DEFAULT_HEIGHT = 680
COLOR_PICKER_MIN_WIDTH = 700
COLOR_PICKER_MIN_HEIGHT = 480
COLOR_PICKER_SCREEN_MARGIN = 80

ActionCallback = Callable[[], None]
BooleanChangedCallback = Callable[[bool], None]
ColorChangedCallback = Callable[[int, str], None]
ColorPickerCallback = Callable[[str], Optional[str]]
LevelsChangedCallback = Callable[[float, float], None]
StringChangedCallback = Callable[[str], None]


@dataclass(frozen=True)
class PatternSelection:
    name: str
    is_user: bool


def choose_native_color(initial_color: str) -> Optional[str]:
    """Return the native Tk picker selection as a hex value, or cancellation."""
    _, selected_color = colorchooser.askcolor(initial_color)
    return selected_color


class ColorPickerDialog(tk.Toplevel):
    """Modal foundation for the future application color picker."""

    def __init__(self, parent: tk.Misc, initial_color: str):
        super().__init__(parent)
        self.original_color = initial_color
        self.current_color = initial_color
        self.accepted_color: Optional[str] = None

        self._configure_window(parent)
        self._build_actions()
        self._build_main_layout()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Return>", self.accept)
        self.bind("<Escape>", self.cancel)
        self.grab_set()
        self.wait_window()

    @classmethod
    def show(cls, parent: tk.Misc, initial_color: str) -> Optional[str]:
        """Show the modal dialog and return its accepted color or cancellation."""
        return cls(parent, initial_color).get_accepted_color()

    def _configure_window(self, parent: tk.Misc) -> None:
        self.title("Select Color")
        self.transient(parent)
        self.resizable(True, True)

        available_width = max(1, self.winfo_screenwidth() - COLOR_PICKER_SCREEN_MARGIN)
        available_height = max(1, self.winfo_screenheight() - COLOR_PICKER_SCREEN_MARGIN)
        width = min(COLOR_PICKER_DEFAULT_WIDTH, available_width)
        height = min(COLOR_PICKER_DEFAULT_HEIGHT, available_height)
        self.geometry(f"{width}x{height}")
        self.minsize(
            min(COLOR_PICKER_MIN_WIDTH, width),
            min(COLOR_PICKER_MIN_HEIGHT, height),
        )

    def _build_actions(self) -> None:
        actions = ttk.Frame(self, padding=8)
        actions.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(actions, text="OK", command=self.accept).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Cancel", command=self.cancel).pack(
            side=tk.RIGHT, padx=(0, 8)
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
            width=140,
        )
        self.palette_area = ttk.LabelFrame(
            self.main_panes,
            text="Citadel Colors",
            padding=8,
        )
        self.editor_area = ttk.LabelFrame(
            self.main_panes,
            text="Color Editor",
            padding=8,
        )
        self.main_panes.add(self.group_navigation, weight=0)
        self.main_panes.add(self.palette_area, weight=3)
        self.main_panes.add(self.editor_area, weight=2)

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
        self.editor_visualization_area.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.editor_color_field_area = ttk.Frame(self.editor_visualization_area)
        self.editor_color_field_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.editor_slider_area = ttk.Frame(self.editor_visualization_area, width=28)
        self.editor_slider_area.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        self.editor_numeric_area = ttk.Frame(self.editor_area)
        self.editor_numeric_area.pack(fill=tk.X, pady=(8, 0))
        self.editor_rgb_area = ttk.Frame(self.editor_numeric_area)
        self.editor_rgb_area.pack(fill=tk.X)
        self.editor_alternate_color_space_area = ttk.Frame(self.editor_numeric_area)
        self.editor_alternate_color_space_area.pack(fill=tk.X)
        self.editor_hex_area = ttk.Frame(self.editor_numeric_area)
        self.editor_hex_area.pack(fill=tk.X)
        self.editor_preview_area = ttk.Frame(self.editor_area)
        self.editor_preview_area.pack(fill=tk.X, pady=(8, 0))
        self.original_color_preview_area = ttk.Frame(self.editor_preview_area)
        self.original_color_preview_area.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.current_color_preview_area = ttk.Frame(self.editor_preview_area)
        self.current_color_preview_area.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def set_current_color(self, color: str) -> None:
        """Update the one working color shared by future editor controls."""
        self.current_color = color

    def get_accepted_color(self) -> Optional[str]:
        """Return the accepted working color, or ``None`` after cancellation."""
        return self.accepted_color

    def accept(self, Event=None) -> None:
        self.accepted_color = self.current_color
        self.destroy()

    def cancel(self, Event=None) -> None:
        self.accepted_color = None
        self.destroy()


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
        color_picker: ColorPickerCallback = choose_native_color,
        **kw,
    ):
        super(FrameColorChooser, self).__init__(master=master, cnf={}, **kw)
        self._on_color_changed = on_color_changed
        self._color_picker = color_picker
        self.color_boxes = []
        self.color_buttons = []
        self.initialize()

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
        for color_box in self.color_boxes:
            color = str(color_box["bg"])
            color_box.delete("all")
            color_box.create_text(
                COLOR_BOX_SIZE / 2,
                COLOR_BOX_SIZE / 2,
                text=color,
                font=("Arial", 10, "bold"),
            )


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
