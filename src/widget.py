import tkinter as tk
from tkinter.constants import HORIZONTAL
from tkinter import ttk
from tkinter.ttk import Progressbar
import os
from tkinter import colorchooser, filedialog
from functools import partial
from src.color_pattern_handler import army_color_pattern, is_user_pattern
from src.constant import OPEN_FILETYPES, SAVE_EXT_LIST, ColorOps


COLOR_BOX_SIZE = 90
COLOR_BTN_HEIGHT = 26


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
    """Pattern Treeview with metadata-backed temporary Listbox adapters."""

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

    # Temporary compatibility for the unchanged save/delete callbacks. These
    # adapters use metadata rather than visible Treeview cell values.
    def curselection(self):
        return self.selection()

    def get(self, item_id):
        return self.get_pattern_name(item_id)

    def selection_set(self, first=None, last=None):
        item_id = first
        if first == "end" or last == "end":
            children = self.get_children()
            item_id = children[-1] if children else None
        if item_id is not None:
            super().selection_set(item_id)


class FramePatternList(tk.Frame):
    def __init__(self, master=None, cnf={}, **kw):
        super(FramePatternList, self).__init__(master=master, cnf={}, **kw)
        self.tree_frame = tk.Frame(self)
        self.tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = PatternTreeview(
            self.tree_frame,
            columns=("pattern_name", "marker"),
            show="headings",
            selectmode="browse",
            yscrollcommand=self.scrollbar.set,
        )
        self.tree.heading("pattern_name", text="Pattern", anchor=tk.W)
        self.tree.heading("marker", text="", anchor=tk.E)
        self.tree.column("pattern_name", anchor=tk.W, stretch=True)
        self.tree.column(
            "marker", anchor=tk.E, width=28, minwidth=28, stretch=False
        )
        self.scrollbar.config(command=self.tree.yview)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Temporary alias for save/delete callbacks updated in a later step.
        self.lb = self.tree

        self.load_pattern_list()
        self.save_pattern = tk.Button(
            self, text="Save pattern", command=self._root().save_pattern
        )
        self.save_pattern.pack(side=tk.TOP, fill=tk.X)

        self.delete_pattern = tk.Button(
            self, text="Delete pattern", command=self._root().delete_pattern
        )
        self.delete_pattern.pack(side=tk.TOP, fill=tk.X)

    def load_pattern_list(self):
        self.tree.clear_patterns()
        for pattern_name in army_color_pattern:
            self.tree.insert_pattern(
                pattern_name, user_created=is_user_pattern(pattern_name)
            )

    def get_selected_item_id(self):
        selection = self.tree.selection()
        return selection[0] if selection else None

    def get_selected_pattern_name(self):
        return self.tree.get_pattern_name(self.get_selected_item_id())

    def is_selected_pattern_user(self):
        return self.tree.is_user_item(self.get_selected_item_id())

    def get_pattern_item_id(self, pattern_name):
        return self.tree.get_pattern_item_id(pattern_name)

    def select_pattern(self, pattern_name):
        item_id = self.get_pattern_item_id(pattern_name)
        if item_id is None:
            return None

        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self.tree.see(item_id)
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
