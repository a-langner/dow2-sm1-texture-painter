import tkinter as tk
from tkinter.constants import HORIZONTAL
from tkinter import ttk
from tkinter import font as tkfont
from tkinter.ttk import Progressbar
import os
from tkinter import colorchooser, filedialog
from functools import partial
from src.color_pattern_handler import get_all_patterns, is_user_pattern
from src.constant import OPEN_FILETYPES, SAVE_EXT_LIST, ColorOps


COLOR_BOX_SIZE = 90
COLOR_BTN_HEIGHT = 26
PATTERN_MARKER_COLUMN_WIDTH = 28
HEADER_SEPARATOR_STARTUP_RETRIES = 3


def calculate_pattern_separator_x(
    tree_x, tree_width, marker_width, border_width=0
):
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
    def __init__(self, master=None, cnf={}, **kw):
        super(FrameChannelList, self).__init__(master=master, cnf={}, **kw)

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
            command=self._root().on_apply_alpha_toggle,
        )
        self.add_alpha.pack(side=tk.TOP, fill=tk.X)


class FrameColorChooser(tk.Frame):
    def __init__(self, master=None, cnf={}, **kw):
        super(FrameColorChooser, self).__init__(master=master, cnf={}, **kw)
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
            self.color_boxes[i].bind(
                "<Button-1>", partial(self.apply_color, i)
            )
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
            self.color_buttons[i].place(
                anchor=tk.NW, x=COLOR_BOX_SIZE * i + i * 1, y=0
            )
        self.draw_rgb_value()

    def apply_color(self, btn_idx: int, Event=None):
        # Color Dialog that open upon btn click
        _, color = colorchooser.askcolor(self.color_boxes[btn_idx]["bg"])
        if color is not None:
            self.color_boxes[btn_idx]["bg"] = color
            self.draw_rgb_value()
            self._root().refresh_workspace()

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
    def __init__(self, master=None, cnf={}, **kw):
        super(FrameSlider, self).__init__(master=master, cnf={}, **kw)

        # Brightness slider
        self.brightness_slider = tk.Scale(
            self,
            label="Brightness",
            length=150,
            from_=0.0,
            to=150.0,
            orient=tk.HORIZONTAL,
            command=self._root().on_slider_update,
        )
        self.brightness_slider.pack(side=tk.TOP, fill=tk.X)

        # Contrast slider
        self.contrast_slider = tk.Scale(
            self,
            label="Contrast",
            length=200,
            from_=0.0,
            to=200.0,
            orient=tk.HORIZONTAL,
            command=self._root().on_slider_update,
        )
        self.contrast_slider.pack(side=tk.TOP, fill=tk.X)


class FrameColorOps(tk.LabelFrame):
    def __init__(self, master=None, cnf={}, **kw):
        super(FrameColorOps, self).__init__(master=master, cnf={}, **kw)
        self.color_operation_btn = {op.value: None for op in ColorOps}
        self.var = tk.StringVar(value=ColorOps.OVERLAY.value)
        for op_name, value in self.color_operation_btn.items():
            value = tk.Radiobutton(
                self,
                text=op_name,
                variable=self.var,
                value=op_name,
                command=self._root().color_operation_update,
            )
            value.pack(side=tk.LEFT)


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
    def __init__(self, master=None, cnf={}, **kw):
        super(FramePatternList, self).__init__(master=master, cnf={}, **kw)
        self.pattern_style = ttk.Style(self)
        heading_font = self.pattern_style.lookup(
            "Treeview.Heading", "font"
        ) or "TkHeadingFont"
        self.pattern_heading_font = tkfont.Font(
            root=self, font=heading_font
        )
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
        self.tree.bind(
            "<Button-1>", self._block_header_separator_press, add="+"
        )
        self.tree.bind(
            "<B1-Motion>", self._block_header_separator_drag, add="+"
        )
        self.tree.bind(
            "<ButtonRelease-1>",
            self._block_header_separator_release,
            add="+",
        )
        self.tree.bind(
            "<Motion>", self._update_header_separator_cursor, add="+"
        )
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
        self.tree.bind(
            "<Configure>", self._position_column_separator, add="+"
        )
        self.tree.bind(
            "<Configure>", self._position_header_separator, add="+"
        )
        self.tree.bind(
            "<<ThemeChanged>>", self._schedule_separator_position, add="+"
        )
        self.column_separator.bind(
            "<Button-1>", self._select_row_through_separator
        )
        self.column_separator.bind(
            "<MouseWheel>", self._scroll_tree_through_separator
        )
        self.column_separator.bind(
            "<Button-4>", self._scroll_tree_up_through_separator
        )
        self.column_separator.bind(
            "<Button-5>", self._scroll_tree_down_through_separator
        )
        self.header_separator.bind(
            "<MouseWheel>", self._scroll_tree_through_separator
        )
        self.header_separator.bind(
            "<Button-4>", self._scroll_tree_up_through_separator
        )
        self.header_separator.bind(
            "<Button-5>", self._scroll_tree_down_through_separator
        )
        self.after_idle(self._position_column_separator)

        self.load_pattern_list()
        self.save_pattern = tk.Button(
            self, text="Save pattern", command=self._root().save_pattern
        )
        self.save_pattern.pack(side=tk.TOP, fill=tk.X)

        self.delete_pattern = tk.Button(
            self,
            text="Delete pattern",
            command=self._root().delete_pattern,
            state=tk.DISABLED,
        )
        self.delete_pattern.pack(side=tk.TOP, fill=tk.X)
        self.update_delete_button_state()

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
        block_release = (
            self.header_separator_pressed or self._is_header_separator(Event)
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
                self.tree.unbind(
                    "<Map>", self.header_separator_map_binding_id
                )
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
        separator_y = self.tree.winfo_y() + max(
            boundary_y - separator_height, 0
        )
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

    def load_pattern_list(self):
        self.tree.clear_patterns()
        for row in build_pattern_rows():
            self.tree.insert_pattern(
                row["name"], user_created=row["is_user"]
            )
        if hasattr(self, "delete_pattern"):
            self.update_delete_button_state()
        if hasattr(self, "header_separator"):
            self.after_idle(self._position_header_separator)

    def get_selected_item_id(self):
        selection = self.tree.selection()
        return selection[0] if selection else None

    def get_selected_pattern_name(self):
        return self.tree.get_pattern_name(self.get_selected_item_id())

    def is_selected_pattern_user(self):
        return self.tree.is_user_item(self.get_selected_item_id())

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

    def update_delete_button_state(self):
        state = tk.NORMAL if self.is_selected_pattern_user() else tk.DISABLED
        self.delete_pattern.config(state=state)

    def select_pattern(self, pattern_name):
        item_id = self.get_pattern_item_id(pattern_name)
        if item_id is None:
            return None

        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self.tree.see(item_id)
        self.update_delete_button_state()
        return item_id


class BatchEditTopLevel(tk.Toplevel):
    def __init__(self, master=None, cnf={}, **kw):
        super(BatchEditTopLevel, self).__init__(master=master, cnf={}, **kw)
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
        tk.Label(
            self.frame_destination_format, text="Destination format:"
        ).pack(side=tk.LEFT)
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
            command=self._root().batch_edit,
        )
        self.batch_edit_button.pack(side=tk.LEFT)

        self.batch_convert_button = tk.Button(
            self.frame_destination_format,
            text="Process Batch Convert",
            command=self._root().batch_convert,
        )
        self.batch_convert_button.pack(side=tk.LEFT)

        self.cancel_button = tk.Button(
            self.frame_destination_format,
            text="Cancel",
            command=self._root().cancel_batch,
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
            tk.Label(
                entry_frame, text=label, width=label_width, anchor=tk.W
            ).pack(side=tk.LEFT)
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

        self.frame_batch_src_path = widget_entry_template(
            self, "Source folder:"
        )
        self.frame_batch_dest_path = widget_entry_template(
            self, "Destination folder:"
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

    def update_progress_bar_label(self, current: int):
        maximum = self.progress_bar["maximum"]
        self.progress_bar["value"] = current
        self.frame_progress_bar.configure(
            text=f"Completed {current}/{maximum} file(s)"
        )

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
        self.cancel_button.configure(
            state=tk.NORMAL if running else tk.DISABLED
        )
