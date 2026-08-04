import os
import logging
import queue
import re
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
    PatternImportConflictDialog,
    PatternCollectionImportConfirmationDialog,
    PatternCollectionConflictDialog,
    pattern_action_states,
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
    InvalidPatternError,
    PatternError,
    PatternNotFoundError,
    get_pattern_colors,
    normalize_pattern_name,
    normalize_pattern_colors,
)
from src.image_process import ImageWorkbench, TextureValidationError
from src.pattern_exchange import (
    PATTERN_COLLECTION_EXCHANGE_SUFFIX,
    PATTERN_EXCHANGE_SUFFIX,
    BuiltinPatternImportConflictError,
    EmptyUserPatternCollectionError,
    DuplicatePatternNameInCollectionError,
    InvalidImportedPatternColorsError,
    InvalidImportedPatternNameError,
    InvalidPatternFileError,
    InvalidPatternJsonError,
    InvalidPatternImportNameError,
    InvalidPatternCollectionNameError,
    InvalidPatternCollectionError,
    InvalidPatternCollectionFormatError,
    PatternExportError,
    PatternExportPermissionDeniedError,
    PatternFileNotFoundError,
    PatternImportReadError,
    PatternCollectionImportError,
    PatternPermissionDeniedError,
    UnsupportedPatternVersionError,
    UnsupportedPatternCollectionVersionError,
    UserPatternImportConflictError,
    export_pattern,
    export_user_pattern_collection,
    analyze_pattern_collection_import,
    import_analyzed_pattern_collection,
    import_pattern as persist_imported_pattern,
    read_pattern_file,
    read_pattern_collection_file,
)
from src.settings_handler import SettingsHandler
from pathlib import Path

from importlib.resources import as_file, files

PATTERN_LIST_DEFAULT_WIDTH = 166
VERSION = "0.1"
PREVIEW_DEBOUNCE_MS = 120
WINDOW_INITIAL_SCALE = 1.4
WINDOW_SCREEN_FRACTION = 0.9
WINDOW_CONTENT_PADDING = 16
PATTERN_IMPORT_MENU_LABEL = "Import Pattern…"
PATTERN_EXPORT_MENU_LABEL = "Export Selected Pattern…"
PATTERN_COLLECTION_IMPORT_MENU_LABEL = "Import Pattern Collection…"
PATTERN_COLLECTION_EXPORT_MENU_LABEL = "Export All User Patterns…"
PATTERN_FILETYPES = (
    ("Pattern files", f"*{PATTERN_EXCHANGE_SUFFIX}"),
    ("JSON files", "*.json"),
    ("All files", "*.*"),
)
PATTERN_COLLECTION_FILETYPES = (
    ("Pattern Collections", f"*{PATTERN_COLLECTION_EXCHANGE_SUFFIX}"),
    ("JSON files", "*.json"),
    ("All files", "*.*"),
)
LOGGER = logging.getLogger(__name__)

WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def suggested_exchange_filename(name, suffix, fallback_name):
    """Return a portable exchange filename for the supplied canonical suffix."""
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    safe_name = safe_name.rstrip(" .")
    if not safe_name:
        safe_name = fallback_name
    windows_stem = safe_name.split(".", 1)[0].rstrip(" .").upper()
    if windows_stem in WINDOWS_RESERVED_FILENAMES:
        safe_name = f"_{safe_name}"
    if not safe_name.casefold().endswith(suffix.casefold()):
        safe_name += suffix
    return safe_name


def suggested_pattern_filename(pattern_name):
    """Return a portable filename while preserving the internal pattern name."""
    return suggested_exchange_filename(
        pattern_name, PATTERN_EXCHANGE_SUFFIX, "pattern"
    )


def suggested_pattern_collection_filename(collection_name):
    """Return a portable filename for a Pattern Collection."""
    return suggested_exchange_filename(
        collection_name,
        PATTERN_COLLECTION_EXCHANGE_SUFFIX,
        "pattern-collection",
    )


def format_collection_import_result(result):
    """Build a compact result summary containing only relevant counts."""
    changed_count = result.imported_count + result.overwritten_count
    if changed_count == 0:
        lines = ["No Patterns were imported."]
    else:
        lines = ["Collection imported."]
    summaries = (
        (result.imported_count, "new pattern", "new patterns", "imported"),
        (
            result.overwritten_count,
            "user pattern",
            "user patterns",
            "overwritten",
        ),
        (
            result.skipped_user_conflict_count,
            "user conflict",
            "user conflicts",
            "skipped",
        ),
        (
            result.skipped_builtin_conflict_count,
            "built-in conflict",
            "built-in conflicts",
            "skipped",
        ),
    )
    for count, singular, plural, action in summaries:
        if count:
            label = singular if count == 1 else plural
            lines.append(f"{count} {label} {action}.")
    if len(lines) == 1:
        return lines[0]
    return "\n\n".join((lines[0], "\n".join(lines[1:])))


def collection_selection_was_overwritten(
    selected_pattern_name, analysis, overwrite_user_conflicts
):
    """Return whether Collection import replaced the selected Pattern data."""
    if selected_pattern_name is None or not overwrite_user_conflicts:
        return False
    return any(
        pattern.name == selected_pattern_name for pattern in analysis.user_conflicts
    )


def resolve_pattern_import_conflicts(
    imported_pattern,
    persist,
    choose_conflict,
    request_rename,
    report_invalid_name,
):
    """Resolve import conflicts iteratively without coupling policy to Tk."""
    target_name = None
    overwrite = False
    while True:
        try:
            return persist(
                imported_pattern,
                target_name=target_name,
                overwrite=overwrite,
            )
        except BuiltinPatternImportConflictError:
            conflict_type = "builtin"
        except UserPatternImportConflictError:
            conflict_type = "user"

        effective_name = target_name or imported_pattern.name
        decision = choose_conflict(conflict_type, effective_name)
        if decision == "cancel":
            return None
        if decision == "overwrite" and conflict_type == "user":
            overwrite = True
            continue
        if decision != "rename":
            return None

        while True:
            replacement_name = request_rename(effective_name)
            if replacement_name is None:
                return None
            try:
                target_name = normalize_pattern_name(replacement_name)
            except InvalidPatternError as exc:
                report_invalid_name(str(exc))
                continue
            overwrite = False
            break


def calculate_initial_window_size(
    min_width, min_height, screen_width, screen_height
):
    """Scale the initial size and keep it within a sensible screen area."""
    scaled_width = round(min_width * WINDOW_INITIAL_SCALE)
    scaled_height = round(min_height * WINDOW_INITIAL_SCALE)
    available_width = max(
        min_width, round(screen_width * WINDOW_SCREEN_FRACTION)
    )
    available_height = max(
        min_height, round(screen_height * WINDOW_SCREEN_FRACTION)
    )
    return (
        min(scaled_width, available_width),
        min(scaled_height, available_height),
    )


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
    available_width = max(
        min_width, round(screen_width * WINDOW_SCREEN_FRACTION)
    )
    available_height = max(
        min_height, round(screen_height * WINDOW_SCREEN_FRACTION)
    )
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


def is_window_maximized(window):
    """Recognize the maximized state exposed by different Tk window managers."""
    if window.state() == "zoomed":
        return True
    try:
        return bool(window.attributes("-zoomed"))
    except tk.TclError:
        return False


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
        initial_width, initial_height = calculate_initial_window_size(
            min_width,
            min_height,
            self.winfo_screenwidth(),
            self.winfo_screenheight(),
        )
        self.geometry(f"{initial_width}x{initial_height}")
        icon_resource = files("src.resources").joinpath("icon_64x64.png")
        with as_file(icon_resource) as icon_path:
            self.icon_img = tk.PhotoImage(file=str(icon_path))
        self.iconphoto(False, self.icon_img)
        self.minsize(min_width, min_height)
        self.title(f"Army Painter {VERSION}")

        self.img_wbench = ImageWorkbench()
        self.settings = SettingsHandler()
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
        self.frame_army_pattern.state_change_callback = (
            self.update_pattern_action_states
        )
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

        def define_patternmenu():
            self.pattern_menu = tk.Menu(menubar, tearoff=0)
            self.pattern_menu.add_command(
                label=PATTERN_IMPORT_MENU_LABEL,
                command=self.import_pattern,
            )
            self.pattern_menu.add_command(
                label=PATTERN_EXPORT_MENU_LABEL,
                command=self.export_selected_pattern,
            )
            self.pattern_menu.add_separator()
            self.pattern_menu.add_command(
                label=PATTERN_COLLECTION_IMPORT_MENU_LABEL,
                command=self.import_pattern_collection,
            )
            self.pattern_menu.add_command(
                label=PATTERN_COLLECTION_EXPORT_MENU_LABEL,
                command=self.export_all_user_patterns,
            )
            menubar.add_cascade(label="Patterns", menu=self.pattern_menu)
            self.update_pattern_action_states()

        def define_toolmenu():
            toolmenu = tk.Menu(menubar, tearoff=0)
            toolmenu.add_command(
                label="Batch Edit Tools",
                command=self.open_batch_edit_tools,
            )
            menubar.add_cascade(label="Tools", menu=toolmenu)

        define_filemenu()
        define_editmenu()
        define_patternmenu()
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
        self.img_wbench.colors = self.get_current_pattern_colors()
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

    def on_pattern_select(self, Event=None):
        # TODO: Refactor following code so with frame color class
        selection = self.frame_army_pattern.get_selected_pattern()
        self.update_pattern_action_states(selection)
        if selection is None:
            return

        try:
            color_list = get_pattern_colors(selection.name)
        except PatternNotFoundError:
            return

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
        self.resize_for_diffuse(self.img_wbench.img_og_dif.size)

    def resize_for_diffuse(self, texture_size):
        """Apply one texture-specific resize without disturbing maximized windows."""
        if is_window_maximized(self):
            return

        min_width, min_height = self.minsize()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        target_width, target_height = calculate_diffuse_window_size(
            texture_size[0],
            texture_size[1],
            min_width,
            min_height,
            screen_width,
            screen_height,
        )
        target_x, target_y = clamp_window_position(
            self.winfo_x(),
            self.winfo_y(),
            target_width,
            target_height,
            screen_width,
            screen_height,
        )
        self.geometry(f"{target_width}x{target_height}+{target_x}+{target_y}")

    def load_channel_packed_file(self, filepath: str):
        self.img_wbench.load_team_colour_file(filepath)
        self.select_channel()

    def load_dirt_file(self, filepath: str):
        self.img_wbench.load_dirt_file(filepath)

    def load_spec_file(self, filepath: str):
        self.img_wbench.load_specular_file(filepath)

    def open_diffuse(self, Event=None):
        filepath = filedialog.askopenfilename(
            initialdir=self.settings.get_diffuse_initial_directory(),
            filetypes=OPEN_FILETYPES,
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
            return
        try:
            self.settings.remember_diffuse_file(filepath)
        except OSError:
            LOGGER.exception("Could not update settings file: %s", self.settings.path)

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

        colors = self.get_current_pattern_colors()
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

        self.frame_army_pattern.load_pattern_list(pattern_name)
        self.update_pattern_action_states()

    def get_current_pattern_colors(self) -> list[str]:
        """Return current GUI colors in canonical Pattern order."""
        return normalize_pattern_colors(
            color["bg"] for color in self.frame_color_chooser.color_boxes
        )

    def update_selected_pattern(self):
        """Placeholder for the selected-Pattern update workflow."""

    def rename_selected_pattern(self):
        """Placeholder for the selected-Pattern rename workflow."""

    def delete_pattern(self):
        selection = self.frame_army_pattern.get_selected_pattern()
        if selection is None:
            return
        pattern_name = selection.name

        if not selection.is_user:
            self.update_pattern_action_states(selection)
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

        self.frame_army_pattern.load_pattern_list(neighboring_name)
        self.update_pattern_action_states()

    def update_pattern_action_states(self, selection=None):
        if selection is None:
            selection = self.frame_army_pattern.get_selected_pattern()
        states = pattern_action_states(selection)
        self.frame_army_pattern.set_pattern_action_states(states)
        self.pattern_menu.entryconfig(
            PATTERN_EXPORT_MENU_LABEL, state=states.export_selected
        )
        export_all_state = (
            tk.NORMAL
            if src.color_pattern_handler.has_user_patterns()
            else tk.DISABLED
        )
        self.pattern_menu.entryconfig(
            PATTERN_COLLECTION_EXPORT_MENU_LABEL,
            state=export_all_state,
        )

    def import_pattern_collection(self):
        source = filedialog.askopenfilename(
            initialdir=self.settings.get_last_pattern_import_directory(),
            filetypes=PATTERN_COLLECTION_FILETYPES,
            title="Import Pattern Collection",
        )
        if not source:
            return

        try:
            collection = read_pattern_collection_file(source)
        except PatternFileNotFoundError as exc:
            self._show_pattern_import_error("Collection File Not Found", exc)
            return
        except PatternPermissionDeniedError as exc:
            self._show_pattern_import_error("Permission Denied", exc)
            return
        except PatternImportReadError as exc:
            self._show_pattern_import_error("Unreadable Collection File", exc)
            return
        except InvalidPatternJsonError as exc:
            self._show_pattern_import_error("Malformed Collection JSON", exc)
            return
        except UnsupportedPatternCollectionVersionError as exc:
            self._show_pattern_import_error(
                "Unsupported Collection Version", exc
            )
            return
        except DuplicatePatternNameInCollectionError as exc:
            self._show_pattern_import_error("Duplicate Pattern Names", exc)
            return
        except InvalidPatternCollectionFormatError as exc:
            self._show_pattern_import_error("Wrong Collection Format", exc)
            return
        except InvalidPatternCollectionError as exc:
            self._show_pattern_import_error("Invalid Pattern Collection", exc)
            return

        try:
            self.settings.set_last_pattern_import_directory(Path(source).parent)
        except OSError:
            LOGGER.exception(
                "Could not remember Pattern Collection import directory: %s",
                Path(source).parent,
            )

        analysis = analyze_pattern_collection_import(collection)
        overwrite_user_conflicts = False
        if analysis.user_conflict_count or analysis.builtin_conflict_count:
            confirmation = PatternCollectionConflictDialog(self, analysis)
            if not confirmation.result:
                return
            overwrite_user_conflicts = confirmation.overwrite_user_conflicts
        else:
            confirmation = PatternCollectionImportConfirmationDialog(
                self,
                analysis.collection_name,
                analysis.total_pattern_count,
                analysis.new_pattern_count,
            )
            if not confirmation.result:
                return

        selection = self.frame_army_pattern.get_selected_pattern()
        selected_name = selection.name if selection else None
        try:
            result = import_analyzed_pattern_collection(
                analysis,
                overwrite_user_conflicts=overwrite_user_conflicts,
            )
        except (PatternCollectionImportError, PatternError, OSError) as exc:
            LOGGER.exception(
                "Could not persist Pattern Collection imported from %s", source
            )
            showerror(
                "Cannot Import Pattern Collection",
                f"The Pattern Collection could not be saved:\n{exc}",
                parent=self,
            )
            return

        self.frame_army_pattern.load_pattern_list(selected_name)
        if collection_selection_was_overwritten(
            selected_name, analysis, overwrite_user_conflicts
        ):
            self.on_pattern_select()
        showinfo(
            "Pattern Collection Imported",
            format_collection_import_result(result),
            parent=self,
        )

    def export_all_user_patterns(self):
        if not src.color_pattern_handler.has_user_patterns():
            showinfo(
                "No User Patterns",
                "There are no user-created Patterns to export.",
                parent=self,
            )
            return

        collection_name = askstring(
            "Export Pattern Collection",
            "Collection name:",
            initialvalue="My Patterns",
            parent=self,
        )
        if collection_name is None:
            return
        collection_name = collection_name.strip()
        if not collection_name:
            showerror(
                "Invalid Collection Name",
                "Collection name cannot be empty.",
                parent=self,
            )
            return

        destination = filedialog.asksaveasfilename(
            initialdir=self.settings.get_last_pattern_export_directory(),
            initialfile=suggested_pattern_collection_filename(collection_name),
            filetypes=PATTERN_COLLECTION_FILETYPES,
            defaultextension=PATTERN_COLLECTION_EXCHANGE_SUFFIX,
            title="Export Pattern Collection",
        )
        if not destination:
            return

        try:
            export_user_pattern_collection(collection_name, destination)
        except EmptyUserPatternCollectionError:
            LOGGER.exception("No user-created Patterns remained for collection export")
            showinfo(
                "No User Patterns",
                "There are no user-created Patterns to export.",
                parent=self,
            )
            return
        except InvalidPatternCollectionNameError as exc:
            LOGGER.exception("Invalid Pattern Collection name: %s", collection_name)
            showerror("Invalid Collection Name", str(exc), parent=self)
            return
        except PatternExportPermissionDeniedError as exc:
            LOGGER.exception(
                "Permission denied exporting Pattern Collection '%s' to %s",
                collection_name,
                destination,
            )
            showerror(
                "Permission Denied",
                f"Permission was denied exporting '{collection_name}' to:\n"
                f"{destination}",
                parent=self,
            )
            return
        except PatternExportError as exc:
            LOGGER.exception(
                "Could not export Pattern Collection '%s' to %s",
                collection_name,
                destination,
            )
            showerror(
                "Cannot Export Pattern Collection",
                f"Could not export '{collection_name}' to:\n"
                f"{destination}\n\n{exc}",
                parent=self,
            )
            return

        try:
            self.settings.set_last_pattern_export_directory(
                Path(destination).parent
            )
        except OSError:
            LOGGER.exception(
                "Could not remember Pattern Collection export directory: %s",
                Path(destination).parent,
            )

    def import_pattern(self):
        source = filedialog.askopenfilename(
            initialdir=self.settings.get_last_pattern_import_directory(),
            filetypes=PATTERN_FILETYPES,
            title="Import Pattern",
        )
        if not source:
            return

        try:
            imported_pattern = read_pattern_file(source)
        except PatternFileNotFoundError as exc:
            self._show_pattern_import_error(
                "Pattern File Not Found",
                exc,
                f"The Pattern file was not found:\n{source}",
            )
            return
        except PatternPermissionDeniedError as exc:
            self._show_pattern_import_error(
                "Permission Denied",
                exc,
                f"Permission was denied reading:\n{source}",
            )
            return
        except PatternImportReadError as exc:
            self._show_pattern_import_error(
                "Unreadable Pattern File",
                exc,
                f"The Pattern file could not be read:\n{source}",
            )
            return
        except InvalidPatternJsonError as exc:
            self._show_pattern_import_error(
                "Malformed Pattern JSON",
                exc,
                f"The file contains malformed JSON:\n{source}",
            )
            return
        except UnsupportedPatternVersionError as exc:
            self._show_pattern_import_error(
                "Unsupported Pattern Version",
                exc,
                f"The Pattern version is not supported:\n{source}\n\n{exc}",
            )
            return
        except InvalidImportedPatternNameError as exc:
            self._show_pattern_import_error(
                "Invalid Pattern Name",
                exc,
                f"The Pattern name is invalid:\n{source}\n\n{exc}",
            )
            return
        except InvalidImportedPatternColorsError as exc:
            self._show_pattern_import_error(
                "Invalid Pattern Colors",
                exc,
                f"The Pattern colors are invalid:\n{source}\n\n{exc}",
            )
            return
        except InvalidPatternFileError as exc:
            self._show_pattern_import_error(
                "Wrong Pattern Format",
                exc,
                f"The file is not a supported Pattern file:\n{source}\n\n{exc}",
            )
            return

        try:
            imported_name = resolve_pattern_import_conflicts(
                imported_pattern,
                persist_imported_pattern,
                self._choose_pattern_import_conflict,
                self._request_pattern_import_name,
                self._report_invalid_pattern_import_name,
            )
        except InvalidPatternImportNameError as exc:
            self._show_pattern_import_error("Invalid Pattern Name", exc)
            return
        except (PatternError, OSError) as exc:
            self._show_pattern_import_error(
                "Cannot Import Pattern",
                exc,
                f"The Pattern could not be saved:\n{exc}",
            )
            return
        if imported_name is None:
            return

        self.frame_army_pattern.load_pattern_list(imported_name)
        self.on_pattern_select()

        try:
            self.settings.set_last_pattern_import_directory(
                Path(source).parent
            )
        except OSError:
            LOGGER.exception(
                "Could not remember pattern import directory: %s",
                Path(source).parent,
            )

    def _show_pattern_import_error(self, title, error, message=None):
        LOGGER.exception("Pattern import failed: %s", error)
        showerror(title, message or str(error))

    def _choose_pattern_import_conflict(self, conflict_type, pattern_name):
        dialog = PatternImportConflictDialog(
            self,
            pattern_name,
            user_conflict=conflict_type == "user",
        )
        return dialog.result

    def _request_pattern_import_name(self, current_name):
        return askstring(
            "Rename Imported Pattern",
            "Choose a replacement pattern name:",
            initialvalue=current_name,
            parent=self,
        )

    def _report_invalid_pattern_import_name(self, message):
        showerror("Invalid Pattern Name", message, parent=self)

    def export_selected_pattern(self):
        selection = self.frame_army_pattern.get_selected_pattern()
        if selection is None:
            return
        pattern_name = selection.name

        destination = filedialog.asksaveasfilename(
            initialdir=self.settings.get_last_pattern_export_directory(),
            initialfile=suggested_pattern_filename(pattern_name),
            filetypes=PATTERN_FILETYPES,
            defaultextension=PATTERN_EXCHANGE_SUFFIX,
            title="Export Pattern",
        )
        if not destination:
            return

        try:
            export_pattern(pattern_name, destination)
        except PatternExportPermissionDeniedError as exc:
            LOGGER.exception(
                "Could not export pattern '%s' to %s",
                pattern_name,
                destination,
            )
            showerror(
                "Permission Denied",
                f"Permission was denied exporting '{pattern_name}' to:\n"
                f"{destination}",
            )
            return
        except (PatternNotFoundError, PatternExportError) as exc:
            LOGGER.exception(
                "Could not export pattern '%s' to %s",
                pattern_name,
                destination,
            )
            showerror(
                "Cannot Export Pattern",
                f"Could not export '{pattern_name}' to:\n{destination}\n\n{exc}",
            )
            return

        try:
            self.settings.set_last_pattern_export_directory(
                Path(destination).parent
            )
        except OSError:
            LOGGER.exception(
                "Could not remember pattern export directory: %s",
                Path(destination).parent,
            )

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
