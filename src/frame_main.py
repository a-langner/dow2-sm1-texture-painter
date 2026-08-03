import os
import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from PIL import (
    ImageTk,
)
import tkinter as tk
from tkinter import filedialog
from tkinter.simpledialog import askstring
from tkinter.messagebox import askyesno, showerror, showinfo, showwarning
import traceback
from src.widget import (
    FrameColorChooser,
    FrameChannelList,
    FrameColorOps,
    FrameSlider,
    BatchEditTopLevel,
    FramePatternList,
)
from src.constant import (
    DEFAULT_IMG_SIZE,
    COLOR_BOX_SIZE,
    COLOR_BTN_HEIGHT,
    FRAME_TOOL_HEIGHT,
    SAVE_FILETYPES,
    OPEN_FILETYPES,
)
import src.color_pattern_handler
from src.dow1_converter import get_tem_filenames, convert_tem_texture
from src.color_pattern_handler import (
    PatternError,
    get_all_patterns,
)
from src.image_process import ImageWorkbench, TextureValidationError
from pathlib import Path

from importlib.resources import as_file, files

PATTERN_LIST_DEFAULT_WIDTH = 166
VERSION = "0.1"
PREVIEW_DEBOUNCE_MS = 120
LOGGER = logging.getLogger(__name__)


def find_companion_texture(diffuse_filepath, map_suffix):
    """Find a sibling texture derived from a ``*_dif`` filename.

    Filename matching is case-insensitive for consistent behavior on Windows
    and case-sensitive filesystems. The directory and extension are preserved.
    """
    diffuse_path = Path(diffuse_filepath)
    if not diffuse_path.stem.casefold().endswith("_dif"):
        return None

    unit_name = diffuse_path.stem[:-4]
    expected_name = (
        f"{unit_name}_{map_suffix}{diffuse_path.suffix}"
    ).casefold()
    for candidate in diffuse_path.parent.iterdir():
        if candidate.is_file() and candidate.name.casefold() == expected_name:
            return candidate
    return None


def render_preview(snapshot):
    return snapshot.refresh_workspace(), snapshot.refresh_team_colour_img()


def prepare_batch_workbench(diffuse_path, settings):
    """Load one texture set without touching Tk or the displayed workbench."""
    workbench = ImageWorkbench()
    workbench.load_diffuse_file(diffuse_path)
    tem_path = find_companion_texture(diffuse_path, "tem")
    if tem_path is None:
        raise TextureValidationError(
            f'No team-colour texture was found for "{diffuse_path.name}".'
        )
    workbench.load_team_colour_file(tem_path)

    warnings = []
    for suffix, label, loader in (
        ("drt", "Dirt", workbench.load_dirt_file),
        ("spc", "Specular", workbench.load_specular_file),
    ):
        optional_path = find_companion_texture(diffuse_path, suffix)
        if optional_path is None:
            continue
        try:
            loader(optional_path)
        except TextureValidationError as exc:
            warnings.append(f"{label}: {exc}")

    workbench.apply_render_settings(settings)
    return workbench, warnings


def save_processed_image(image, filepath):
    if filepath.suffix.casefold() in (".jpg", ".jpeg"):
        image.convert("RGB").save(filepath)
    else:
        image.save(filepath)


def batch_edit_worker(files, destination, dest_format, settings, cancel, events):
    errors = []
    warnings = []
    for current, diffuse_path in enumerate(files, start=1):
        if cancel.is_set():
            break
        try:
            workbench, item_warnings = prepare_batch_workbench(
                diffuse_path, settings
            )
            output = workbench.refresh_workspace()
            output_path = destination / f"{diffuse_path.stem}.{dest_format}"
            save_processed_image(output, output_path)
            warnings.extend(
                f"{diffuse_path.name}: {warning}" for warning in item_warnings
            )
        except Exception as exc:
            errors.append(f"{diffuse_path.name}: {exc}")
        events.put(("progress", current, len(files)))
    return errors, warnings, cancel.is_set()


def batch_convert_worker(source, destination, dest_format, src_format, cancel, events):
    errors = []
    try:
        files_dict = get_tem_filenames(source, src_format)
    except Exception as exc:
        return [str(exc)], [], cancel.is_set()

    events.put(("total", len(files_dict)))
    for current, (name, textures) in enumerate(files_dict.items(), start=1):
        if cancel.is_set():
            break
        try:
            result = convert_tem_texture(textures, source)
            filename = name.replace("default", "tem", 1)
            save_processed_image(
                result, destination / f"{filename}.{dest_format}"
            )
        except Exception as exc:
            errors.append(f"{name}: {exc}")
        events.put(("progress", current, len(files_dict)))
    return errors, [], cancel.is_set()


class ArmyPainter(tk.Tk):
    def __init__(self):
        super().__init__()

        # Setting main window
        min_width = 256 * 2 + PATTERN_LIST_DEFAULT_WIDTH
        min_height = DEFAULT_IMG_SIZE + FRAME_TOOL_HEIGHT
        dimension = f"{min_width}x{min_height}"
        self.geometry(dimension)
        icon_resource = files("src.resources").joinpath("icon_64x64.png")
        with as_file(icon_resource) as icon_path:
            self.icon_img = tk.PhotoImage(file=str(icon_path))
        self.iconphoto(False, self.icon_img)
        self.minsize(min_width, min_height)
        self.title(f"Army Painter {VERSION}")

        self.img_wbench = ImageWorkbench()
        self.frame_batch_tools = None
        self.preview_executor = ThreadPoolExecutor(max_workers=1)
        self.batch_executor = ThreadPoolExecutor(max_workers=1)
        self.preview_after_id = None
        self.preview_generation = 0
        self.preview_futures = set()
        self.batch_future = None
        self.batch_cancel = threading.Event()
        self.batch_events = queue.Queue()
        self.closing = False
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

        # Frame containing tools to edit the image
        self.frame_img_tools = tk.Frame(
            self,
            width=DEFAULT_IMG_SIZE * 2,
            height=COLOR_BOX_SIZE + COLOR_BTN_HEIGHT,
            bd=2,
            relief=tk.RIDGE,
        )
        self.frame_img_tools.pack(side=tk.TOP, fill=tk.BOTH)

        # Defining slave widget
        self.define_frame_workspace_tool()

        # Frame containing the texture images
        self.frame_img = tk.Frame(self)
        self.frame_img.pack(side=tk.BOTTOM, fill=tk.X, expand=True)

        # Defining slave widget
        self.define_frame_workspace()
        self.frame_army_pattern = FramePatternList(self.frame_img)
        self.frame_army_pattern.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.frame_channel_select.lb.bind(
            "<<ListboxSelect>>", self.select_channel
        )
        self.frame_army_pattern.tree.bind(
            "<<TreeviewSelect>>", self.on_pattern_select
        )

        # Defining menubar
        self.define_menu()

        # Initialize the default workspace
        self.reset_workspace()
        self.user_pattern_warning_shown = False
        self.after_idle(self.show_user_pattern_load_warning)

    def define_frame_workspace_tool(self):
        # Setting color boxes frame
        self.frame_color_chooser = FrameColorChooser(
            self.frame_img_tools,
            width=COLOR_BOX_SIZE * 4 + 12,
            height=COLOR_BOX_SIZE + COLOR_BTN_HEIGHT,
            bd=0,
            relief=tk.RIDGE,
        )
        self.frame_color_chooser.pack(side=tk.LEFT, fill=tk.Y)

        self.frame_color_op_option = FrameColorOps(
            self.frame_img_tools,
            text="Color Operation",
        )
        self.frame_color_op_option.pack(side=tk.TOP, fill=tk.X)

        # Setting channel list frame
        self.frame_channel_select = FrameChannelList(
            self.frame_img_tools, text="RGBA Channel", relief=tk.RIDGE, bd=2
        )
        self.frame_channel_select.pack(side=tk.LEFT, fill=tk.Y)

        # Setting sliders
        self.frame_sliders = FrameSlider(self.frame_img_tools, relief=tk.RIDGE, bd=2)
        self.frame_sliders.pack(side=tk.LEFT, fill=tk.Y)

    def define_menu(self):
        menubar = tk.Menu(self)

        def define_filemenu():
            filemenu = tk.Menu(menubar, tearoff=0)
            filemenu.add_command(
                label="Open diffuse",
                command=self.open_diffuse,
                accelerator="Ctrl+O",
            )
            filemenu.add_command(
                label="Open channel file",
                command=self.open_channel,
                accelerator="Ctrl+A",
            )
            filemenu.add_command(
                label="Save as", command=self.save, accelerator="Ctrl+S"
            )
            filemenu.add_command(
                label="Close", command=self.close, accelerator="Ctrl+E"
            )
            filemenu.add_separator()
            filemenu.add_command(label="Exit", command=self.on_exit)
            menubar.add_cascade(label="File", menu=filemenu)
            self.config(menu=menubar)

        def define_editmenu():
            editmenu = tk.Menu(menubar, tearoff=0)
            editmenu.add_command(
                label="Reset workspace",
                command=self.reset_workspace,
                accelerator="Ctrl+R",
            )
            self.apply_dirt = tk.BooleanVar()
            editmenu.add_checkbutton(
                label="Apply Dirt Texture",
                variable=self.apply_dirt,
                onvalue=1,
                offvalue=0,
                command=self.on_dirt_toggle,
            )
            self.apply_spec = tk.BooleanVar()
            editmenu.add_checkbutton(
                label="Apply Specular Texture",
                variable=self.apply_spec,
                onvalue=1,
                offvalue=0,
                command=self.on_spec_toggle,
            )
            menubar.add_cascade(label="Edit", menu=editmenu)

        def define_toolmenu():
            toolmenu = tk.Menu(menubar, tearoff=0)
            toolmenu.add_command(
                label="Batch Edit Tools",
                command=self.open_batch_edit_tools,
            )
            menubar.add_cascade(label="Tools", menu=toolmenu)

        define_filemenu()
        define_editmenu()
        define_toolmenu()

        # Define Menu binding
        self.bind("<Control-o>", self.open_diffuse)
        self.bind("<Control-a>", self.open_channel)
        self.bind("<Control-s>", self.save)
        self.bind("<Control-e>", self.close)
        self.bind("<Control-d>", self.batch_edit)
        self.bind("<Control-r>", self.reset_workspace)

    def define_frame_workspace(self):
        self.img_dif = ImageTk.PhotoImage(self.img_wbench.img_og_dif)
        self.label_img_dif = tk.Label(
            self.frame_img, image=self.img_dif, relief=tk.RAISED
        )
        self.label_img_dif.pack(side=tk.LEFT, fill=tk.Y)

        self.img_tem = ImageTk.PhotoImage(self.img_wbench.img_og_tem)
        self.label_img_tem = tk.Label(
            self.frame_img, image=self.img_tem, relief=tk.RAISED
        )
        self.label_img_tem.pack(side=tk.LEFT, fill=tk.Y)

    def open_batch_edit_tools(self, Event=None):
        if (
            self.frame_batch_tools is not None
            and self.frame_batch_tools.winfo_exists()
        ):
            self.frame_batch_tools.deiconify()
            self.frame_batch_tools.lift()
            self.frame_batch_tools.focus_force()
            return

        # Frame containing the batch operation tools
        self.frame_batch_tools = BatchEditTopLevel(
            self,
            width=DEFAULT_IMG_SIZE * 2,
            height=COLOR_BOX_SIZE + COLOR_BTN_HEIGHT,
            bd=2,
            relief=tk.RIDGE,
        )
        self.frame_batch_tools.iconphoto(False, self.icon_img)
        self.frame_batch_tools.protocol(
            "WM_DELETE_WINDOW", self.close_batch_edit_tools
        )
        if self.batch_future is not None and not self.batch_future.done():
            self.frame_batch_tools.set_running(True)
            self.frame_batch_tools.frame_progress_bar.configure(
                text="Batch running..."
            )

    def close_batch_edit_tools(self):
        self.batch_cancel.set()
        if self.frame_batch_tools is not None:
            self.frame_batch_tools.destroy()
            self.frame_batch_tools = None

    def on_slider_update(self, value: float):
        self.img_wbench.brightness = self.frame_sliders.brightness_slider.get()
        self.img_wbench.contrast = self.frame_sliders.contrast_slider.get()
        self.schedule_preview_refresh(PREVIEW_DEBOUNCE_MS)

    def save(self, Event=None):
        """Save image from current workspace

        :param Event: widget triggered event, defaults to None
        :type Event: [type], optional
        """
        filename = filedialog.asksaveasfilename(
            initialdir=os.curdir,
            filetypes=SAVE_FILETYPES,
            defaultextension=SAVE_FILETYPES[0],
            initialfile=self.og_filename,
        )
        if filename:
            try:
                self.img_wbench.save(filename)
            except KeyError:
                tk.messagebox.showerror(
                    title="Wrong File Extension",
                    message="Error: wrong extension,"
                    + 'choose an extension from the "Save as type" list',
                )

    def close(self, Event=None):
        self.img_wbench.set_placeholder_img()
        self.img_wbench.tem_channels = []
        self.refresh_workspace()

    def sync_render_settings(self):
        self.img_wbench.colors = [
            color["bg"] for color in self.frame_color_chooser.color_boxes
        ]
        self.img_wbench.brightness = self.frame_sliders.brightness_slider.get()
        self.img_wbench.contrast = self.frame_sliders.contrast_slider.get()
        self.img_wbench.tem_selected = self.frame_channel_select.lb.curselection()

    def refresh_workspace(self):
        """Schedule an immediate background workspace refresh."""
        self.schedule_preview_refresh(0)

    def schedule_preview_refresh(self, delay_ms=0):
        if self.closing:
            return
        self.sync_render_settings()
        self.preview_generation += 1
        if self.preview_after_id is not None:
            self.after_cancel(self.preview_after_id)
        generation = self.preview_generation
        self.preview_after_id = self.after(
            delay_ms, lambda: self.start_preview_refresh(generation)
        )

    def start_preview_refresh(self, generation):
        self.preview_after_id = None
        if self.closing or generation != self.preview_generation:
            return
        for pending in tuple(self.preview_futures):
            if not pending.running():
                pending.cancel()
                self.preview_futures.discard(pending)
        snapshot = self.img_wbench.render_snapshot()
        future = self.preview_executor.submit(render_preview, snapshot)
        self.preview_futures.add(future)
        self.after(20, self.poll_preview_result, generation, future)

    def poll_preview_result(self, generation, future):
        if self.closing:
            return
        if not future.done():
            self.after(20, self.poll_preview_result, generation, future)
            return
        self.preview_futures.discard(future)
        if future.cancelled() or generation != self.preview_generation:
            return
        try:
            workspace, team_colour = future.result()
        except Exception as exc:
            showerror(title="Preview error", message=str(exc))
            return
        self.img_wbench.img_workspace = workspace
        self.img_dif = ImageTk.PhotoImage(workspace)
        self.label_img_dif.config(image=self.img_dif)
        self.img_tem = ImageTk.PhotoImage(team_colour)
        self.label_img_tem.config(image=self.img_tem)
        self.refresh_window_size()

    def color_operation_update(self):
        color_op = self.frame_color_op_option.var.get()
        self.img_wbench.color_op = color_op
        self.refresh_workspace()

    def on_apply_alpha_toggle(self):
        self.img_wbench.apply_alpha = self.frame_channel_select.apply_alpha.get()
        self.refresh_workspace()

    def on_dirt_toggle(self):
        self.img_wbench.apply_dirt = self.apply_dirt.get()
        self.refresh_workspace()

    def on_spec_toggle(self):
        self.img_wbench.apply_spec = self.apply_spec.get()
        self.refresh_workspace()

    def refresh_window_size(self):
        """Refresh window size using current images width"""
        img_dif_size = self.img_wbench.img_workspace.size
        img_tem_size = self.img_wbench.img_og_tem.size
        new_width = img_dif_size[0] + img_tem_size[0] + PATTERN_LIST_DEFAULT_WIDTH

        # Assuming both image got same size
        new_height = img_dif_size[1] + FRAME_TOOL_HEIGHT
        self.geometry(f"{new_width}x{new_height}")
        self.update_idletasks()

    def on_pattern_select(self, Event=None):
        # TODO: Refactor following code so with frame color class
        self.frame_army_pattern.update_delete_button_state()
        pattern_name = self.frame_army_pattern.get_selected_pattern_name()
        if pattern_name is None:
            return

        pattern = get_all_patterns().get(pattern_name)
        if pattern is None:
            return

        color_list = list(pattern.values())
        for color, color_box in zip(
            color_list, self.frame_color_chooser.color_boxes
        ):
            color_box["bg"] = color
        self.frame_color_chooser.draw_rgb_value()
        self.refresh_workspace()

    def select_channel(self, Event=None):
        """Register channel selected from the Channel list listbox

        :param Event: event triggered from widget, defaults to None
        :type Event: [type], optional
        """
        self.img_wbench.tem_selected = self.frame_channel_select.lb.curselection()
        self.refresh_workspace()

    def load_file(self, filepath: str):
        """Load diffuse and tem texture and set it as workspace image,
        both texture have to be located in the same directory

        :param filepath: path to file
        :type filepath: str
        """
        self.img_wbench.load_diffuse_file(filepath)

        # Load associated tem file
        tem_filepath = find_companion_texture(filepath, "tem")
        if tem_filepath is not None:
            print(tem_filepath)
            try:
                self.load_channel_packed_file(tem_filepath)
            except TextureValidationError as exc:
                showerror(title="Invalid team-colour texture", message=str(exc))
        else:
            self.open_channel()

        # Load associated dirt file
        dirt_filepath = find_companion_texture(filepath, "drt")
        if dirt_filepath is not None:
            try:
                self.load_dirt_file(dirt_filepath)
            except TextureValidationError as exc:
                showwarning(title="Invalid dirt texture", message=str(exc))

        # Load associated spec file
        spec_filepath = find_companion_texture(filepath, "spc")
        if spec_filepath is not None:
            try:
                self.load_spec_file(spec_filepath)
            except TextureValidationError as exc:
                showwarning(title="Invalid specular texture", message=str(exc))

        self.refresh_workspace()

    def load_channel_packed_file(self, filepath: str):
        self.img_wbench.load_team_colour_file(filepath)
        self.select_channel()

    def load_dirt_file(self, filepath: str):
        self.img_wbench.load_dirt_file(filepath)

    def load_spec_file(self, filepath: str):
        self.img_wbench.load_specular_file(filepath)

    def open_diffuse(self, Event=None):
        filepath = filedialog.askopenfilename(
            initialdir=os.curdir, filetypes=OPEN_FILETYPES
        )
        if not filepath:
            return
        # Saving the filename just to set it as default file name on the save
        # file dialog, truncate the file extension because it is automatically
        # set by the save dialog
        self.og_filename = Path(filepath).stem
        try:
            self.load_file(filepath)
        except TextureValidationError as exc:
            showerror(title="Invalid diffuse texture", message=str(exc))

    def open_channel(self, Event=None):
        filepath = filedialog.askopenfilename(
            initialdir=os.curdir,
            filetypes=OPEN_FILETYPES,
            title="Open channel file",
        )
        if not filepath:
            return
        try:
            self.load_channel_packed_file(filepath)
        except TextureValidationError as exc:
            showerror(title="Invalid team-colour texture", message=str(exc))

    def _check_batch_path(self, source: str, dest: str):
        if not source:
            raise OSError("Please select a source directory.")
        elif not dest:
            raise OSError("Please select a destination directory.")
        elif not os.path.exists(source):
            raise OSError(f"{source} does not exist.")
        elif not os.path.exists(dest):
            raise OSError(f"{dest} does not exist.")

    def _check_dif_format(self, filename: str, src_format: list):
        name, ext = os.path.splitext(filename)
        if (
            ext[1:].casefold() in src_format
            and name.casefold().endswith("_dif")
        ):
            return True
        return False

    def get_batch_edit_input(self):
        if self.frame_batch_tools is None:
            return None
        source_value = self.frame_batch_tools.frame_batch_src_path.entry_value.get()
        dest_value = self.frame_batch_tools.frame_batch_dest_path.entry_value.get()
        dest_format = self.frame_batch_tools.dest_format.get().lower()
        try:
            # Checking if source & dest exist
            self._check_batch_path(source_value, dest_value)
            src_format = self.frame_batch_tools.get_source_format_selected()
            if not src_format:
                raise OSError("Please select at least one source format.")
        except OSError as e:
            showerror(title="Path Error", message=str(e))
        else:
            return (
                Path(source_value),
                Path(dest_value),
                dest_format,
                [value.casefold() for value in src_format],
            )

    def start_batch_job(self, worker, *args):
        if self.batch_future is not None and not self.batch_future.done():
            return
        self.batch_cancel = threading.Event()
        self.batch_events = queue.Queue()
        self.frame_batch_tools.set_running(True)
        self.frame_batch_tools.progress_bar["value"] = 0
        self.frame_batch_tools.frame_progress_bar.configure(text="Starting...")
        self.batch_future = self.batch_executor.submit(
            worker, *args, self.batch_cancel, self.batch_events
        )
        self.after(50, self.poll_batch_job)

    def cancel_batch(self):
        if self.batch_future is not None and not self.batch_future.done():
            self.batch_cancel.set()
            if self.frame_batch_tools is not None:
                self.frame_batch_tools.frame_progress_bar.configure(
                    text="Cancelling after current file..."
                )

    def poll_batch_job(self):
        if self.closing:
            return
        while True:
            try:
                event = self.batch_events.get_nowait()
            except queue.Empty:
                break
            if self.frame_batch_tools is None:
                continue
            if event[0] == "total":
                self.frame_batch_tools.progress_bar["maximum"] = event[1]
                self.frame_batch_tools.update_progress_bar_label(0)
            elif event[0] == "progress":
                _, current, maximum = event
                self.frame_batch_tools.progress_bar["maximum"] = maximum
                self.frame_batch_tools.update_progress_bar_label(current)

        if self.batch_future is None or not self.batch_future.done():
            self.after(50, self.poll_batch_job)
            return

        try:
            errors, warnings, cancelled = self.batch_future.result()
        except Exception as exc:
            errors, warnings, cancelled = [str(exc)], [], False
        self.batch_future = None
        if self.frame_batch_tools is not None:
            self.frame_batch_tools.set_running(False)
            if cancelled:
                self.frame_batch_tools.frame_progress_bar.configure(
                    text="Batch cancelled"
                )
            elif errors:
                self.frame_batch_tools.frame_progress_bar.configure(
                    text="Batch completed with errors"
                )
            else:
                self.frame_batch_tools.frame_progress_bar.configure(
                    text="Batch completed"
                )
            self.frame_batch_tools.lift()
            self.frame_batch_tools.focus_force()

        messages = []
        if errors:
            messages.append("Errors:\n" + "\n".join(errors))
        if warnings:
            messages.append("Warnings:\n" + "\n".join(warnings))
        if messages:
            showwarning(title="Batch results", message="\n\n".join(messages))
        elif not cancelled:
            showinfo(title="Batch complete", message="Batch processing completed.")

    def batch_convert(self, Event=None):
        batch_input = self.get_batch_edit_input()
        if batch_input is None:
            return
        src, dest, dest_format, src_format = batch_input
        self.start_batch_job(
            batch_convert_worker, src, dest, dest_format, src_format
        )

    def batch_edit(self, Event=None):
        batch_input = self.get_batch_edit_input()
        if batch_input is None:
            return
        src, dest, dest_format, src_format = batch_input
        files = [
            src / filename
            for filename in os.listdir(src)
            if self._check_dif_format(filename, src_format)
        ]
        self.sync_render_settings()
        settings = self.img_wbench.get_render_settings()
        self.frame_batch_tools.progress_bar["maximum"] = len(files)
        self.start_batch_job(
            batch_edit_worker, files, dest, dest_format, settings
        )

    def reset_workspace(self, Event=None):
        self.img_wbench.img_workspace = self.img_wbench.img_og_dif
        for color_box in self.frame_color_chooser.color_boxes:
            color_box["bg"] = "#808080"
        self.frame_sliders.brightness_slider.set(75)
        self.frame_sliders.contrast_slider.set(100)
        self.frame_channel_select.lb.selection_set(first=0, last=3)
        self.select_channel()
        self.refresh_workspace()

    def save_pattern(self):
        pattern_name = askstring("Pattern Name", "Choose a pattern name")
        if pattern_name is None:
            return

        pattern_name = pattern_name.strip()
        if not pattern_name:
            showerror("Cannot Save Pattern", "Pattern name cannot be empty.")
            return

        colors = [
            color["bg"] for color in self.frame_color_chooser.color_boxes
        ]
        try:
            src.color_pattern_handler.save(name=pattern_name, colors=colors)
        except PatternError as exc:
            showerror("Cannot Save Pattern", str(exc))
            return
        except OSError:
            LOGGER.exception("Could not save user pattern '%s'", pattern_name)
            showerror(
                "Cannot Save Pattern",
                "The user-pattern file could not be updated.\n\n"
                "The pattern was not saved.",
            )
            return

        self.frame_army_pattern.load_pattern_list()
        self.frame_army_pattern.select_pattern(pattern_name)

    def delete_pattern(self):
        pattern_name = self.frame_army_pattern.get_selected_pattern_name()
        if pattern_name is None:
            return

        if not self.frame_army_pattern.is_selected_pattern_user():
            self.frame_army_pattern.update_delete_button_state()
            return

        confirmed = askyesno(
            "Delete Pattern",
            f"Permanently delete the pattern '{pattern_name}'?",
        )
        if not confirmed:
            return

        neighboring_name = (
            self.frame_army_pattern.get_selected_neighbor_pattern_name()
        )
        try:
            src.color_pattern_handler.delete(pattern_name)
        except PatternError as exc:
            showerror("Cannot Delete Pattern", str(exc))
            return
        except OSError:
            LOGGER.exception(
                "Could not persist deletion of user pattern '%s'",
                pattern_name,
            )
            showerror(
                "Cannot Delete Pattern",
                "The user-pattern file could not be updated.\n\n"
                "The pattern was not deleted.",
            )
            return

        self.frame_army_pattern.load_pattern_list()
        if neighboring_name is not None:
            self.frame_army_pattern.select_pattern(neighboring_name)
        else:
            self.frame_army_pattern.update_delete_button_state()

    def show_user_pattern_load_warning(self):
        if self.user_pattern_warning_shown:
            return

        issue = src.color_pattern_handler.user_pattern_load_issue
        if issue is None:
            return

        self.user_pattern_warning_shown = True
        showwarning(
            "User Patterns Not Loaded",
            "The user-pattern file could not be loaded:\n"
            f"{issue.path}\n\n"
            "Built-in patterns are still available. The file was not changed.",
        )

    def report_callback_exception(self, exc, val, tb):
        showerror("Error", message=traceback.format_exc())

    def on_exit(self):
        if self.closing:
            return
        self.closing = True
        self.batch_cancel.set()
        if self.preview_after_id is not None:
            self.after_cancel(self.preview_after_id)
            self.preview_after_id = None
        for future in self.preview_futures:
            future.cancel()
        self.preview_executor.shutdown(wait=False, cancel_futures=True)
        self.batch_executor.shutdown(wait=False, cancel_futures=True)
        self.destroy()


def main():
    army_painter = ArmyPainter()
    army_painter.mainloop()


if __name__ == "__main__":
    main()
