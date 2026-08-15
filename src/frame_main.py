import os
import logging
import queue
import threading
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from PIL import (
    ImageTk,
)
import tkinter as tk
from tkinter.messagebox import showerror
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
)
from src.action_state import PatternActionContext, derive_pattern_action_state
from src.batch_processing_service import (
    batch_convert_worker,
    BatchProcessingRequest,
    BatchProcessingResult,
    BatchProcessingService,
    is_batch_diffuse,
)
from src.constant import (
    DEFAULT_IMG_SIZE,
    COLOR_BOX_SIZE,
    COLOR_BTN_HEIGHT,
    FRAME_TOOL_HEIGHT,
    ColorOps,
)
import src.color_pattern_handler
from src.dialog_gateway import DialogGateway
from src.file_selection_service import FileSelectionService
from src.color_pattern_handler import (
    InvalidPatternError,
    PatternError,
    PatternNotFoundError,
    UserPatternPersistenceError,
    get_pattern_colors,
    normalize_pattern_colors,
    pattern_colors_equal,
)
from src.image_process import (
    TextureValidationError,
    create_placeholder_img,
    save_image,
)
from src.logging_setup import configure_application_logging, log_application_startup
from src.pattern_exchange import (
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
    export_pattern,
    export_user_pattern_collection,
    analyze_pattern_collection_import,
    import_analyzed_pattern_collection,
    import_pattern as persist_imported_pattern,
    read_pattern_file,
    read_pattern_collection_file,
    suggested_pattern_collection_filename,
    suggested_pattern_filename,
)
from src.platform_tools import open_directory_in_file_manager
from src.pattern_controller import PatternController
from src.preview_controller import PreviewController, PreviewRequest, PreviewResult
from src.render_settings import DEFAULT_RENDER_SETTINGS
from src.settings_handler import SettingsHandler
from src.texture_naming import (
    DEFAULT_TEXTURE_NAMING,
    TEXTURE_NAMING_PROFILES,
    TextureKind,
    texture_naming_profile_for_id,
)
from src.texture_renderer import TextureRenderer
from src.texture_loading_service import (
    TextureLoadingService,
    detect_texture_naming_profile,
)
from src.window_geometry import (
    PATTERN_LIST_DEFAULT_WIDTH,
    calculate_diffuse_window_size,
    calculate_initial_window_size,
    clamp_window_position,
    safe_window_position,
)
from pathlib import Path

from importlib.resources import as_file, files

VERSION = "0.1"
PREVIEW_DEBOUNCE_MS = 120
PATTERN_SAVE_MENU_LABEL = "Save Current as New Pattern…"
PATTERN_UPDATE_MENU_LABEL = "Update Selected Pattern"
PATTERN_RESET_MENU_LABEL = "Reset to Selected Pattern"
PATTERN_RENAME_MENU_LABEL = "Rename Selected Pattern…"
PATTERN_DUPLICATE_MENU_LABEL = "Duplicate Selected Pattern…"
PATTERN_DELETE_MENU_LABEL = "Delete Selected Pattern"
PATTERN_IMPORT_MENU_LABEL = "Import Pattern…"
PATTERN_EXPORT_MENU_LABEL = "Export Selected Pattern…"
PATTERN_COLLECTION_IMPORT_MENU_LABEL = "Import Pattern Collection…"
PATTERN_COLLECTION_EXPORT_MENU_LABEL = "Export All User Patterns…"
LOGGER = logging.getLogger(__name__)


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


def is_window_maximized(window):
    """Recognize the maximized state exposed by different Tk window managers."""
    if window.state() == "zoomed":
        return True
    try:
        return bool(window.attributes("-zoomed"))
    except tk.TclError:
        return False


class ArmyPainter(tk.Tk):
    def __init__(self, application_log_path=None):
        super().__init__()
        self._initialize_application_state(application_log_path)
        self._configure_main_window()
        self._initialize_services_and_controllers()
        self._create_application_widgets()
        self._initialize_view_state()

    def _initialize_application_state(self, application_log_path):
        """Create application-level state that has no widget dependencies."""
        self.application_log_path = application_log_path
        self.texture_naming_profile = DEFAULT_TEXTURE_NAMING
        self.dialogs = DialogGateway(self)
        self.frame_batch_tools = None
        self.batch_future = None
        self.batch_cancel = threading.Event()
        self.batch_events = queue.Queue()
        self.closing = False
        self._handling_callback_exception = False
        self.user_pattern_warning_shown = False

    def _configure_main_window(self):
        """Configure root-window geometry, identity, and lifecycle hook."""
        min_width = 256 * 2 + PATTERN_LIST_DEFAULT_WIDTH
        min_height = DEFAULT_IMG_SIZE + FRAME_TOOL_HEIGHT
        initial_width, initial_height = calculate_initial_window_size(
            min_width,
            min_height,
            self.winfo_screenwidth(),
            self.winfo_screenheight(),
        )
        self.settings = SettingsHandler()
        restored_profile = texture_naming_profile_for_id(
            getattr(
                self.settings,
                "game_profile_id",
                DEFAULT_TEXTURE_NAMING.profile_id,
            )
        )
        self.texture_naming_profile = restored_profile or DEFAULT_TEXTURE_NAMING
        position = safe_window_position(
            self.settings.main_window_position,
            initial_width,
            initial_height,
            self.winfo_vrootx(),
            self.winfo_vrooty(),
            self.winfo_vrootwidth(),
            self.winfo_vrootheight(),
        )
        geometry = f"{initial_width}x{initial_height}"
        if position is not None:
            geometry += f"{position[0]:+d}{position[1]:+d}"
        self.geometry(geometry)
        icon_resource = files("src.resources").joinpath("icon_64x64.png")
        with as_file(icon_resource) as icon_path:
            self.icon_img = tk.PhotoImage(file=str(icon_path))
        self.iconphoto(False, self.icon_img)
        self.minsize(min_width, min_height)
        self.title(f"Army Painter {VERSION}")
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

    def _initialize_services_and_controllers(self):
        """Construct and wire non-widget application dependencies.

        ArmyPainter owns both executors and shuts them down. PreviewController
        submits to the preview executor but does not own it; batch work uses a
        separate executor so the two workloads cannot block one another.
        """
        self.active_texture_set = None
        self.texture_renderer = TextureRenderer()
        self.render_settings = DEFAULT_RENDER_SETTINGS
        if not hasattr(self, "settings"):
            self.settings = SettingsHandler()
        self.file_selection = FileSelectionService(self.settings, self.dialogs)
        self.pattern_controller = ArmyPainter._create_pattern_controller(self)
        self.texture_loading = TextureLoadingService(self.texture_naming_profile)
        self.preview_executor = ThreadPoolExecutor(max_workers=1)
        self.preview_controller = PreviewController(
            renderer=self.texture_renderer,
            snapshot_provider=self.create_preview_request,
            executor=self.preview_executor,
            schedule_after=self.after,
            cancel_scheduled=self.after_cancel,
            on_preview_ready=self.apply_preview_result,
            on_preview_error=self.show_preview_error,
            debounce_ms=PREVIEW_DEBOUNCE_MS,
        )
        self.batch_executor = ThreadPoolExecutor(max_workers=1)
        self.batch_processing = BatchProcessingService(renderer=self.texture_renderer)

    def create_preview_request(self):
        """Capture one shallow, read-only preview request on the Tk thread."""
        if self.active_texture_set is None:
            raise RuntimeError("No active texture is available for preview.")
        return PreviewRequest(
            textures=self.active_texture_set.copy_for_render(),
            settings=self.render_settings,
        )

    def _create_application_widgets(self):
        """Build widgets and menus, then explicitly activate callbacks."""
        self.frame_img_tools = tk.Frame(
            self,
            width=DEFAULT_IMG_SIZE * 2,
            height=COLOR_BOX_SIZE + COLOR_BTN_HEIGHT,
            bd=2,
            relief=tk.RIDGE,
        )
        self.frame_img_tools.pack(side=tk.TOP, fill=tk.BOTH)

        self.define_frame_workspace_tool()

        self.frame_img = tk.Frame(self)
        self.frame_img.pack(side=tk.BOTTOM, fill=tk.X, expand=True)

        self.define_frame_workspace()
        self.frame_army_pattern = FramePatternList(
            self.frame_img,
            on_save_new=self.save_pattern,
            on_update=self.update_selected_pattern,
            on_rename=self.rename_selected_pattern,
            on_delete=self.delete_pattern,
            on_selection_changed=self.on_pattern_select,
            on_state_changed=self.update_pattern_action_states,
        )
        self.frame_army_pattern.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.frame_channel_select.lb.bind("<<ListboxSelect>>", self.select_channel)
        self.define_menu()
        self.activate_pattern_panel_callbacks()

    def _initialize_view_state(self):
        """Initialize previews and deferred warnings after complete wiring."""
        self.reset_workspace()
        self.after_idle(self.show_user_pattern_load_warning)

    def _create_pattern_controller(self):
        """Compose Pattern workflows from the existing persistence APIs."""
        return PatternController(
            file_selection=getattr(self, "file_selection", None),
            store=src.color_pattern_handler,
            get_colors=lambda name: get_pattern_colors(name),
            read_single=lambda path: read_pattern_file(path),
            persist_single_import=lambda pattern, **options: (
                persist_imported_pattern(pattern, **options)
            ),
            export_single=lambda name, path: export_pattern(name, path),
            read_collection=lambda path: read_pattern_collection_file(path),
            analyze_collection=lambda collection: (
                analyze_pattern_collection_import(collection)
            ),
            persist_collection=lambda analysis, **options: (
                import_analyzed_pattern_collection(analysis, **options)
            ),
            export_collection=lambda name, path: (
                export_user_pattern_collection(name, path)
            ),
        )

    def _pattern_workflows(self):
        """Use the injected controller, composing one only for legacy test doubles."""
        controller = getattr(self, "pattern_controller", None)
        if controller is not None:
            return controller
        return ArmyPainter._create_pattern_controller(self)

    def activate_pattern_panel_callbacks(self):
        """Activate Pattern callbacks only after assignment and menu creation."""
        self.frame_army_pattern.enable_external_callbacks()
        self.update_pattern_action_states()

    def define_frame_workspace_tool(self):
        # Setting color boxes frame
        self.frame_color_chooser = FrameColorChooser(
            self.frame_img_tools,
            on_color_changed=self.on_color_changed,
            settings=self.settings,
            width=COLOR_BOX_SIZE * 4 + 12,
            height=COLOR_BOX_SIZE + COLOR_BTN_HEIGHT,
            bd=0,
            relief=tk.RIDGE,
        )
        self.frame_color_chooser.pack(side=tk.LEFT, fill=tk.Y)

        self.frame_color_op_option = FrameColorOps(
            self.frame_img_tools,
            on_operation_changed=self.color_operation_update,
            text="Color Operation",
        )
        self.frame_color_op_option.pack(side=tk.TOP, fill=tk.X)

        # Setting channel list frame
        self.frame_channel_select = FrameChannelList(
            self.frame_img_tools,
            on_alpha_changed=self.on_apply_alpha_toggle,
            text="RGBA Channel",
            relief=tk.RIDGE,
            bd=2,
        )
        self.frame_channel_select.pack(side=tk.LEFT, fill=tk.Y)

        # Setting sliders
        self.frame_sliders = FrameSlider(
            self.frame_img_tools,
            on_levels_changed=self.on_slider_update,
            relief=tk.RIDGE,
            bd=2,
        )
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
                label="Open Team Color Mask",
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
                label=PATTERN_SAVE_MENU_LABEL,
                command=self.save_pattern,
            )
            self.pattern_menu.add_command(
                label=PATTERN_UPDATE_MENU_LABEL,
                command=self.update_selected_pattern,
            )
            self.pattern_menu.add_command(
                label=PATTERN_RESET_MENU_LABEL,
                command=self.reset_to_selected_pattern,
            )
            self.pattern_menu.add_command(
                label=PATTERN_RENAME_MENU_LABEL,
                command=self.rename_selected_pattern,
            )
            self.pattern_menu.add_command(
                label=PATTERN_DUPLICATE_MENU_LABEL,
                command=self.duplicate_selected_pattern,
            )
            self.pattern_menu.add_command(
                label=PATTERN_DELETE_MENU_LABEL,
                command=self.delete_pattern,
            )
            self.pattern_menu.add_separator()
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

        def define_gamemenu():
            gamemenu = tk.Menu(menubar, tearoff=0)
            self.game_profile_id = tk.StringVar(
                value=self.texture_naming_profile.profile_id
            )
            for profile in TEXTURE_NAMING_PROFILES:
                gamemenu.add_radiobutton(
                    label=profile.display_name,
                    variable=self.game_profile_id,
                    value=profile.profile_id,
                    command=lambda profile_id=profile.profile_id: self.select_game_profile(
                        profile_id
                    ),
                )
            menubar.add_cascade(label="Game", menu=gamemenu)

        def define_toolmenu():
            toolmenu = tk.Menu(menubar, tearoff=0)
            toolmenu.add_command(
                label="Batch Edit Tools",
                command=self.open_batch_edit_tools,
            )
            menubar.add_cascade(label="Tools", menu=toolmenu)

        def define_helpmenu():
            helpmenu = tk.Menu(menubar, tearoff=0)
            helpmenu.add_command(
                label="Open Log Folder",
                command=self.open_log_folder,
            )
            menubar.add_cascade(label="Help", menu=helpmenu)

        define_filemenu()
        define_editmenu()
        define_gamemenu()
        define_patternmenu()
        define_toolmenu()
        define_helpmenu()

        # Define Menu binding
        self.bind("<Control-o>", self.open_diffuse)
        self.bind("<Control-a>", self.open_channel)
        self.bind("<Control-s>", self.save)
        self.bind("<Control-e>", self.close)
        self.bind("<Control-d>", self.batch_edit)
        self.bind("<Control-r>", self.reset_workspace)

    def select_game_profile(self, profile_id: str):
        """Persist and activate the naming policy selected in the Game menu."""
        profile = texture_naming_profile_for_id(profile_id)
        if profile is None:
            raise ValueError(f"Unknown game profile ID: {profile_id}")
        try:
            self.settings.set_game_profile_id(profile.profile_id)
        except OSError:
            LOGGER.exception("Could not update settings file: %s", self.settings.path)
            self.game_profile_id.set(self.texture_naming_profile.profile_id)
            return
        self.texture_naming_profile = profile
        self.texture_loading = TextureLoadingService(profile)
        self.game_profile_id.set(profile.profile_id)

    def define_frame_workspace(self):
        self.img_dif = ImageTk.PhotoImage(
            create_placeholder_img("Select Diffuse Texture", "RGBA")
        )
        self.label_img_dif = tk.Label(
            self.frame_img, image=self.img_dif, relief=tk.RAISED
        )
        self.label_img_dif.pack(side=tk.LEFT, fill=tk.Y)

        self.img_tem = ImageTk.PhotoImage(
            create_placeholder_img("Select Team Color Mask", "L")
        )
        self.label_img_tem = tk.Label(
            self.frame_img, image=self.img_tem, relief=tk.RAISED
        )
        self.label_img_tem.pack(side=tk.LEFT, fill=tk.Y)

    def open_batch_edit_tools(self, Event=None):
        if self.frame_batch_tools is not None and self.frame_batch_tools.winfo_exists():
            self.frame_batch_tools.deiconify()
            self.frame_batch_tools.lift()
            self.frame_batch_tools.focus_force()
            return

        # Frame containing the batch operation tools
        self.frame_batch_tools = BatchEditTopLevel(
            self,
            on_batch_edit=self.batch_edit,
            on_batch_convert=self.batch_convert,
            on_cancel=self.cancel_batch,
            width=DEFAULT_IMG_SIZE * 2,
            height=COLOR_BOX_SIZE + COLOR_BTN_HEIGHT,
            bd=2,
            relief=tk.RIDGE,
        )
        self.frame_batch_tools.iconphoto(False, self.icon_img)
        self.frame_batch_tools.protocol("WM_DELETE_WINDOW", self.close_batch_edit_tools)
        if self.batch_future is not None and not self.batch_future.done():
            self.frame_batch_tools.set_running(True)
            self.frame_batch_tools.frame_progress_bar.configure(text="Batch running...")

    def close_batch_edit_tools(self):
        self.batch_cancel.set()
        if self.frame_batch_tools is not None:
            self.frame_batch_tools.destroy()
            self.frame_batch_tools = None

    def on_slider_update(self, brightness: float, contrast: float):
        self.request_workspace_preview()

    def on_color_changed(self, slot_index: int, color: str):
        self.update_pattern_action_states()
        self.refresh_workspace()

    def save(self, Event=None):
        """Save image from current workspace

        :param Event: widget triggered event, defaults to None
        :type Event: [type], optional
        """
        if self.active_texture_set is None:
            self.dialogs.show_error(
                title="Cannot Save Image",
                message="Load a diffuse texture before saving.",
            )
            return

        filename = self.file_selection.choose_image_save_destination(self.og_filename)
        if not filename:
            return

        self.sync_render_settings()
        settings = self.render_settings
        try:
            rendered = self.texture_renderer.render(
                self.active_texture_set,
                settings,
            )
        except Exception:
            LOGGER.exception("Could not render the current texture for saving")
            self.dialogs.show_error(
                title="Cannot Render Image",
                message="Could not render the current texture.",
            )
            return

        try:
            save_image(rendered, Path(filename))
        except KeyError:
            LOGGER.exception("Unsupported image save extension: %s", filename)
            self.dialogs.show_error(
                title="Wrong File Extension",
                message="Error: wrong extension,"
                + 'choose an extension from the "Save as type" list',
            )
        except (OSError, ValueError):
            LOGGER.exception("Could not write rendered image to %s", filename)
            self.dialogs.show_error(
                title="Cannot Save Image",
                message=f"Could not write the output image to:\n{filename}",
            )

    def close(self, Event=None):
        self.preview_controller.invalidate()
        self.active_texture_set = None
        self.img_dif = ImageTk.PhotoImage(
            create_placeholder_img("Select Diffuse Texture", "RGBA")
        )
        self.label_img_dif.config(image=self.img_dif)
        self.img_tem = ImageTk.PhotoImage(
            create_placeholder_img("Select Team Color Mask", "L")
        )
        self.label_img_tem.config(image=self.img_tem)

    def sync_render_settings(self) -> None:
        colors = self.get_current_pattern_colors()
        self.render_settings = replace(
            self.render_settings,
            primary_color=colors[0],
            secondary_color=colors[1],
            tint_color=colors[2],
            extra_color=colors[3],
            brightness=float(self.frame_sliders.brightness_slider.get()),
            contrast=float(self.frame_sliders.contrast_slider.get()),
            tem_selected=tuple(self.frame_channel_select.lb.curselection()),
        )

    def request_workspace_preview(self, *, immediate=False):
        """Schedule a preview only when an active texture can be snapshotted."""
        if self.active_texture_set is None:
            self.preview_controller.invalidate()
            return
        self.sync_render_settings()
        if immediate:
            self.preview_controller.request_preview_immediately()
        else:
            self.preview_controller.request_preview()

    def refresh_workspace(self):
        """Schedule an immediate background workspace refresh."""
        self.request_workspace_preview(immediate=True)

    def apply_preview_result(self, result: PreviewResult):
        """Apply a completed preview on Tk's event thread."""
        self.img_dif = ImageTk.PhotoImage(result.workspace)
        self.label_img_dif.config(image=self.img_dif)
        self.img_tem = ImageTk.PhotoImage(result.team_colour)
        self.label_img_tem.config(image=self.img_tem)

    def show_preview_error(self, error):
        """Present an expected background-render failure at the GUI boundary."""
        self.dialogs.show_error(title="Preview error", message=str(error))

    def color_operation_update(self, color_op: str):
        self.render_settings = replace(
            self.render_settings,
            color_op=ColorOps(color_op),
        )
        self.refresh_workspace()

    def on_apply_alpha_toggle(self, apply_alpha: bool):
        self.render_settings = replace(
            self.render_settings,
            apply_alpha=apply_alpha,
        )
        self.refresh_workspace()

    def on_dirt_toggle(self):
        self.render_settings = replace(
            self.render_settings,
            apply_dirt=bool(self.apply_dirt.get()),
        )
        self.refresh_workspace()

    def on_spec_toggle(self):
        self.render_settings = replace(
            self.render_settings,
            apply_spec=bool(self.apply_spec.get()),
        )
        self.refresh_workspace()

    def on_pattern_select(self, Event=None):
        selection = self.frame_army_pattern.get_selected_pattern()
        self.apply_selected_pattern_colors(selection)

    def apply_selected_pattern_colors(self, selection=None):
        """Apply one selected Pattern's stored colors and refresh its preview."""
        if selection is None:
            selection = self.frame_army_pattern.get_selected_pattern()
        if selection is None:
            self.update_pattern_action_states(selection)
            return False

        try:
            color_list = ArmyPainter._pattern_workflows(self).get_colors(selection.name)
        except PatternNotFoundError:
            self.update_pattern_action_states(selection)
            return False

        ArmyPainter._apply_pattern_colors(self, color_list, selection)
        return True

    def _apply_pattern_colors(self, color_list, selection=None):
        """Apply controller-provided colors while retaining GUI ownership."""
        for color, color_box in zip(color_list, self.frame_color_chooser.color_boxes):
            color_box["bg"] = color
        self.frame_color_chooser.draw_rgb_value()
        self.update_pattern_action_states(selection)
        self.refresh_workspace()

    def select_channel(self, Event=None):
        """Register channel selected from the Channel list listbox

        :param Event: event triggered from widget, defaults to None
        :type Event: [type], optional
        """
        self.refresh_workspace()

    def load_file(self, filepath: str):
        """Load one diffuse set, then perform its GUI-only follow-up actions."""
        detected_profile = detect_texture_naming_profile(Path(filepath))
        if (
            detected_profile is not None
            and detected_profile is not self.texture_naming_profile
        ):
            self.select_game_profile(detected_profile.profile_id)
        result = self.texture_loading.load_diffuse_and_companions(Path(filepath))
        self.preview_controller.invalidate()
        self.active_texture_set = result.texture_set

        if result.team_color_mask_error is not None:
            self.dialogs.show_error(
                title="Invalid team-colour mask",
                message=result.team_color_mask_error,
            )
        elif result.team_color_mask_path is not None:
            self.select_channel()
        else:
            self.open_channel()

        for warning in result.warnings:
            label = "Dirt" if warning.kind is TextureKind.DIRT else "Specular"
            self.dialogs.show_warning(
                title=f"Invalid {label.casefold()} texture",
                message=warning.message,
            )

        self.refresh_workspace()
        self.resize_for_diffuse((result.width, result.height))

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

    def open_diffuse(self, Event=None):
        filepath = self.file_selection.choose_diffuse_file()
        if not filepath:
            return
        # Saving the filename just to set it as default file name on the save
        # file dialog, truncate the file extension because it is automatically
        # set by the save dialog
        self.og_filename = Path(filepath).stem
        try:
            self.load_file(filepath)
        except TextureValidationError as exc:
            self.dialogs.show_error(title="Invalid diffuse texture", message=str(exc))
            return
        try:
            self.file_selection.remember_successful_diffuse(filepath)
        except OSError:
            LOGGER.exception("Could not update settings file: %s", self.settings.path)

    def open_channel(self, Event=None):
        filepath = self.file_selection.choose_channel_file()
        if not filepath:
            return
        try:
            result = self.texture_loading.load_channel_file(
                self.active_texture_set, Path(filepath)
            )
            self.preview_controller.invalidate()
            self.active_texture_set = result.texture_set
            self.select_channel()
        except TextureValidationError as exc:
            self.dialogs.show_error(
                title="Invalid team-colour mask", message=str(exc)
            )

    def _check_batch_path(self, source: str, dest: str):
        if not source:
            raise OSError("Please select a source directory.")
        elif not dest:
            raise OSError("Please select a destination directory.")
        elif not os.path.exists(source):
            raise OSError(f"{source} does not exist.")
        elif not os.path.exists(dest):
            raise OSError(f"{dest} does not exist.")

    def _check_diffuse_format(self, filename: str, src_format: list):
        return is_batch_diffuse(Path(filename), src_format, self.texture_naming_profile)

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
            self.dialogs.show_error(title="Path Error", message=str(e))
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
            worker_result = self.batch_future.result()
            if isinstance(worker_result, BatchProcessingResult):
                errors = list(worker_result.errors)
                warnings = list(worker_result.warnings)
                cancelled = worker_result.cancelled
            else:
                errors, warnings, cancelled = worker_result
        except Exception as exc:
            LOGGER.exception("Batch worker failed unexpectedly")
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
            self.dialogs.show_warning(
                title="Batch results", message="\n\n".join(messages)
            )
        elif not cancelled:
            self.dialogs.show_info(
                title="Batch complete", message="Batch processing completed."
            )

    def batch_convert(self, Event=None):
        batch_input = self.get_batch_edit_input()
        if batch_input is None:
            return
        src, dest, dest_format, src_format = batch_input
        self.start_batch_job(
            batch_convert_worker,
            src,
            dest,
            dest_format,
            src_format,
            self.texture_naming_profile,
        )

    def batch_edit(self, Event=None):
        batch_input = self.get_batch_edit_input()
        if batch_input is None:
            return
        src, dest, dest_format, src_format = batch_input
        self.sync_render_settings()
        settings = self.render_settings
        request = BatchProcessingRequest(
            source_directory=src,
            destination_directory=dest,
            source_formats=tuple(src_format),
            destination_format=dest_format,
            settings=settings,
            naming_profile=self.texture_naming_profile,
            overwrite_existing=True,
        )
        self.start_batch_job(
            self.batch_processing.process_to_queue,
            request,
        )

    def reset_workspace(self, Event=None):
        for color_box in self.frame_color_chooser.color_boxes:
            color_box["bg"] = "#808080"
        self.frame_sliders.brightness_slider.set(DEFAULT_RENDER_SETTINGS.brightness)
        self.frame_sliders.contrast_slider.set(DEFAULT_RENDER_SETTINGS.contrast)
        self.frame_channel_select.lb.selection_set(first=0, last=3)
        self.select_channel()
        self.update_pattern_action_states()
        self.refresh_workspace()

    def save_pattern(self):
        pattern_name = self.dialogs.ask_text(
            title="Pattern Name", prompt="Choose a pattern name"
        )
        if pattern_name is None:
            return

        pattern_name = pattern_name.strip()
        if not pattern_name:
            self.dialogs.show_error(
                title="Cannot Save Pattern", message="Pattern name cannot be empty."
            )
            return

        try:
            result = ArmyPainter._pattern_workflows(self).save_new_pattern(
                pattern_name, self.get_current_pattern_colors()
            )
        except PatternError as exc:
            self.dialogs.show_error(title="Cannot Save Pattern", message=str(exc))
            return
        except OSError:
            LOGGER.exception("Could not save user pattern '%s'", pattern_name)
            self.dialogs.show_error(
                title="Cannot Save Pattern",
                message="The user-pattern file could not be updated.\n\n"
                "The pattern was not saved.",
            )
            return

        self.frame_army_pattern.load_pattern_list(result.selected_name)
        self.update_pattern_action_states()

    def get_current_pattern_colors(self) -> list[str]:
        """Return current GUI colors in canonical Pattern order."""
        return normalize_pattern_colors(
            color["bg"] for color in self.frame_color_chooser.color_boxes
        )

    def update_selected_pattern(self):
        """Replace the selected user Pattern with the current GUI colors."""
        selection = self.frame_army_pattern.get_selected_pattern()
        if selection is None:
            return
        if not selection.is_user:
            self.update_pattern_action_states(selection)
            return

        pattern_name = selection.name
        try:
            current_colors = self.get_current_pattern_colors()
            colors_match = not ArmyPainter._pattern_workflows(self).pattern_is_modified(
                pattern_name, current_colors
            )
        except PatternError as exc:
            LOGGER.debug(
                "Could not compare user Pattern '%s' for update",
                pattern_name,
                exc_info=True,
            )
            self.dialogs.show_error(title="Cannot Update Pattern", message=str(exc))
            self.update_pattern_action_states(selection)
            return

        if colors_match:
            self.update_pattern_action_states(selection)
            return

        confirmed = self.dialogs.confirm(
            title="Update Pattern",
            message=f'Update pattern "{pattern_name}" with the current colors?',
            default="no",
        )
        if not confirmed:
            return

        try:
            ArmyPainter._pattern_workflows(self).update_pattern(
                pattern_name, current_colors
            )
        except UserPatternPersistenceError as exc:
            LOGGER.exception("Could not update user Pattern '%s'", pattern_name)
            self.dialogs.show_error(
                title="Cannot Update Pattern",
                message=f"The Pattern could not be saved:\n{exc}",
            )
            self.update_pattern_action_states(selection)
            return
        except PatternError as exc:
            LOGGER.debug(
                "Could not update user Pattern '%s'", pattern_name, exc_info=True
            )
            self.dialogs.show_error(title="Cannot Update Pattern", message=str(exc))
            self.update_pattern_action_states(selection)
            return
        except OSError as exc:
            LOGGER.exception("Could not update user Pattern '%s'", pattern_name)
            self.dialogs.show_error(
                title="Cannot Update Pattern",
                message=f"The Pattern could not be saved:\n{exc}",
            )
            self.update_pattern_action_states(selection)
            return

        self.update_pattern_action_states(selection)

    def reset_to_selected_pattern(self):
        """Discard current color changes by applying the selected Pattern."""
        selection = self.frame_army_pattern.get_selected_pattern()
        if selection is None:
            self.update_pattern_action_states(selection)
            return
        try:
            result = ArmyPainter._pattern_workflows(self).reset_pattern(selection.name)
        except PatternNotFoundError:
            self.update_pattern_action_states(selection)
            return
        ArmyPainter._apply_pattern_colors(self, result.colors_to_apply, selection)

    def rename_selected_pattern(self):
        """Rename the selected user Pattern while preserving its GUI state."""
        selection = self.frame_army_pattern.get_selected_pattern()
        if selection is None:
            return
        if not selection.is_user:
            self.update_pattern_action_states(selection)
            return

        old_name = selection.name
        requested_name = self.dialogs.ask_text(
            title="Rename Pattern",
            prompt="Pattern name:",
            initial_value=old_name,
        )
        if requested_name is None:
            return

        try:
            result = ArmyPainter._pattern_workflows(self).rename_pattern(
                old_name, requested_name
            )
        except InvalidPatternError as exc:
            LOGGER.debug(
                "Invalid replacement name for user Pattern '%s': %s",
                old_name,
                exc,
                exc_info=True,
            )
            self.dialogs.show_error(title="Cannot Rename Pattern", message=str(exc))
            self.update_pattern_action_states(selection)
            return
        except UserPatternPersistenceError as exc:
            LOGGER.exception("Could not rename user Pattern '%s'", old_name)
            self.dialogs.show_error(
                title="Cannot Rename Pattern",
                message=f"The Pattern could not be saved:\n{exc}",
            )
            self.update_pattern_action_states(selection)
            return
        except PatternError as exc:
            LOGGER.debug("Could not rename user Pattern '%s'", old_name, exc_info=True)
            self.dialogs.show_error(title="Cannot Rename Pattern", message=str(exc))
            self.update_pattern_action_states(selection)
            return
        except OSError as exc:
            LOGGER.exception("Could not rename user Pattern '%s'", old_name)
            self.dialogs.show_error(
                title="Cannot Rename Pattern",
                message=f"The Pattern could not be saved:\n{exc}",
            )
            self.update_pattern_action_states(selection)
            return

        if not result.changed:
            self.update_pattern_action_states(selection)
            return

        self.frame_army_pattern.load_pattern_list(result.selected_name)
        self.update_pattern_action_states()

    def duplicate_selected_pattern(self):
        """Save the selected Pattern's stored colors under a new user name."""
        selection = self.frame_army_pattern.get_selected_pattern()
        if selection is None:
            return

        try:
            ArmyPainter._pattern_workflows(self).get_colors(selection.name)
        except PatternError as exc:
            self.dialogs.show_error(title="Cannot Duplicate Pattern", message=str(exc))
            return

        requested_name = self.dialogs.ask_text(
            title="Duplicate Pattern",
            prompt="Pattern name:",
            initial_value=f"{selection.name} Copy",
        )
        if requested_name is None:
            return

        try:
            result = ArmyPainter._pattern_workflows(self).duplicate_pattern(
                selection.name, requested_name
            )
        except PatternError as exc:
            self.dialogs.show_error(title="Cannot Duplicate Pattern", message=str(exc))
            return
        except OSError as exc:
            LOGGER.exception("Could not duplicate Pattern '%s'", selection.name)
            self.dialogs.show_error(
                title="Cannot Duplicate Pattern",
                message=f"The Pattern could not be saved:\n{exc}",
            )
            return

        self.frame_army_pattern.load_pattern_list(result.selected_name)
        self.on_pattern_select()

    def delete_pattern(self):
        selection = self.frame_army_pattern.get_selected_pattern()
        if selection is None:
            return
        pattern_name = selection.name

        if not selection.is_user:
            self.update_pattern_action_states(selection)
            return

        confirmed = self.dialogs.confirm(
            title="Delete Pattern",
            message=f"Permanently delete the pattern '{pattern_name}'?",
        )
        if not confirmed:
            return

        neighboring_name = self.frame_army_pattern.get_selected_neighbor_pattern_name()
        try:
            result = ArmyPainter._pattern_workflows(self).delete_pattern(
                pattern_name, neighboring_name
            )
        except PatternError as exc:
            LOGGER.debug(
                "Could not delete user Pattern '%s'", pattern_name, exc_info=True
            )
            self.dialogs.show_error(title="Cannot Delete Pattern", message=str(exc))
            self.update_pattern_action_states(selection)
            return
        except OSError:
            LOGGER.exception(
                "Could not persist deletion of user pattern '%s'",
                pattern_name,
            )
            self.dialogs.show_error(
                title="Cannot Delete Pattern",
                message="The user-pattern file could not be updated.\n\n"
                "The pattern was not deleted.",
            )
            self.update_pattern_action_states(selection)
            return

        self.frame_army_pattern.load_pattern_list(result.selected_name)
        self.on_pattern_select()

    def update_pattern_action_states(self, selection=None):
        if selection is None:
            selection = self.frame_army_pattern.get_selected_pattern()
        context = PatternActionContext(
            has_selection=selection is not None,
            selected_is_user_pattern=bool(selection and selection.is_user),
            selected_is_dirty=self.is_selected_pattern_dirty(selection),
            has_any_user_patterns=(src.color_pattern_handler.has_user_patterns()),
        )
        ArmyPainter._apply_pattern_action_state(
            self, derive_pattern_action_state(context)
        )

    def _apply_pattern_action_state(self, states):
        """Apply one policy result to the sidebar and Patterns menu."""
        self.frame_army_pattern.set_pattern_action_states(states)
        menu_states = (
            (PATTERN_SAVE_MENU_LABEL, states.save_new_enabled),
            (PATTERN_UPDATE_MENU_LABEL, states.update_enabled),
            (PATTERN_RESET_MENU_LABEL, states.reset_enabled),
            (PATTERN_RENAME_MENU_LABEL, states.rename_enabled),
            (PATTERN_DUPLICATE_MENU_LABEL, states.duplicate_enabled),
            (PATTERN_DELETE_MENU_LABEL, states.delete_enabled),
            (PATTERN_EXPORT_MENU_LABEL, states.export_selected_enabled),
            (
                PATTERN_COLLECTION_EXPORT_MENU_LABEL,
                states.export_all_enabled,
            ),
        )
        for label, enabled in menu_states:
            self.pattern_menu.entryconfig(
                label, state=tk.NORMAL if enabled else tk.DISABLED
            )

    def is_selected_pattern_dirty(self, selection=None):
        """Compare current GUI colors with the selected in-memory Pattern."""
        if selection is None:
            selection = self.frame_army_pattern.get_selected_pattern()
        if selection is None:
            return False
        try:
            current_colors = self.get_current_pattern_colors()
            stored_colors = get_pattern_colors(selection.name)
            return not pattern_colors_equal(current_colors, stored_colors)
        except PatternError:
            return False

    def import_pattern_collection(self):
        source = self.file_selection.choose_pattern_collection_import_file()
        if not source:
            return

        try:
            preparation = ArmyPainter._pattern_workflows(
                self
            ).prepare_collection_import(source)
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
            self._show_pattern_import_error("Unsupported Collection Version", exc)
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

        analysis = preparation.analysis
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
            operation, result = ArmyPainter._pattern_workflows(self).import_collection(
                preparation,
                selected_name=selected_name,
                overwrite_user_conflicts=overwrite_user_conflicts,
            )
        except (PatternCollectionImportError, PatternError, OSError) as exc:
            LOGGER.exception(
                "Could not persist Pattern Collection imported from %s", source
            )
            self.dialogs.show_error(
                title="Cannot Import Pattern Collection",
                message=f"The Pattern Collection could not be saved:\n{exc}",
            )
            return

        self.frame_army_pattern.load_pattern_list(operation.selected_name)
        if operation.colors_to_apply is not None:
            restored = self.frame_army_pattern.get_selected_pattern()
            ArmyPainter._apply_pattern_colors(self, operation.colors_to_apply, restored)
        elif operation.selected_data_changed:
            self.on_pattern_select()
        else:
            self.update_pattern_action_states()
        self.dialogs.show_info(
            title="Pattern Collection Imported",
            message=format_collection_import_result(result),
        )

    def export_all_user_patterns(self):
        if not src.color_pattern_handler.has_user_patterns():
            self.dialogs.show_info(
                title="No User Patterns",
                message="There are no user-created Patterns to export.",
            )
            return

        collection_name = self.dialogs.ask_text(
            title="Export Pattern Collection",
            prompt="Collection name:",
            initial_value="My Patterns",
        )
        if collection_name is None:
            return
        collection_name = collection_name.strip()
        if not collection_name:
            self.dialogs.show_error(
                title="Invalid Collection Name",
                message="Collection name cannot be empty.",
            )
            return

        destination = self.file_selection.choose_pattern_collection_export_destination(
            suggested_pattern_collection_filename(collection_name)
        )
        if not destination:
            return

        try:
            ArmyPainter._pattern_workflows(self).export_user_collection(
                collection_name, destination
            )
        except EmptyUserPatternCollectionError:
            LOGGER.exception("No user-created Patterns remained for collection export")
            self.dialogs.show_info(
                title="No User Patterns",
                message="There are no user-created Patterns to export.",
            )
            return
        except InvalidPatternCollectionNameError as exc:
            LOGGER.exception("Invalid Pattern Collection name: %s", collection_name)
            self.dialogs.show_error(title="Invalid Collection Name", message=str(exc))
            return
        except PatternExportPermissionDeniedError as exc:
            LOGGER.exception(
                "Permission denied exporting Pattern Collection '%s' to %s",
                collection_name,
                destination,
            )
            self.dialogs.show_error(
                title="Permission Denied",
                message=f"Permission was denied exporting '{collection_name}' to:\n"
                f"{destination}",
            )
            return
        except PatternExportError as exc:
            LOGGER.exception(
                "Could not export Pattern Collection '%s' to %s",
                collection_name,
                destination,
            )
            self.dialogs.show_error(
                title="Cannot Export Pattern Collection",
                message=f"Could not export '{collection_name}' to:\n"
                f"{destination}\n\n{exc}",
            )
            return

    def import_pattern(self):
        source = self.file_selection.choose_pattern_import_file()
        if not source:
            return

        try:
            preparation = ArmyPainter._pattern_workflows(self).prepare_single_import(
                source
            )
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

        selection = self.frame_army_pattern.get_selected_pattern()
        selected_name = selection.name if selection else None

        try:
            operation = ArmyPainter._pattern_workflows(self).import_single(
                preparation,
                selected_name=selected_name,
                choose_conflict=self._choose_pattern_import_conflict,
                request_rename=self._request_pattern_import_name,
                report_invalid_name=self._report_invalid_pattern_import_name,
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
        if not operation.changed:
            return

        self.frame_army_pattern.load_pattern_list(operation.selected_name)
        if operation.colors_to_apply is not None:
            restored = self.frame_army_pattern.get_selected_pattern()
            ArmyPainter._apply_pattern_colors(self, operation.colors_to_apply, restored)
        else:
            self.update_pattern_action_states()

    def _show_pattern_import_error(self, title, error, message=None):
        LOGGER.exception("Pattern import failed: %s", error)
        self.dialogs.show_error(title=title, message=message or str(error))

    def _choose_pattern_import_conflict(self, conflict_type, pattern_name):
        dialog = PatternImportConflictDialog(
            self,
            pattern_name,
            user_conflict=conflict_type == "user",
        )
        return dialog.result

    def _request_pattern_import_name(self, current_name):
        return self.dialogs.ask_text(
            title="Rename Imported Pattern",
            prompt="Choose a replacement pattern name:",
            initial_value=current_name,
        )

    def _report_invalid_pattern_import_name(self, message):
        self.dialogs.show_error(title="Invalid Pattern Name", message=message)

    def export_selected_pattern(self):
        selection = self.frame_army_pattern.get_selected_pattern()
        if selection is None:
            return
        pattern_name = selection.name

        destination = self.file_selection.choose_pattern_export_destination(
            suggested_pattern_filename(pattern_name)
        )
        if not destination:
            return

        try:
            ArmyPainter._pattern_workflows(self).export_selected(
                pattern_name, destination
            )
        except PatternExportPermissionDeniedError as exc:
            LOGGER.exception(
                "Could not export pattern '%s' to %s",
                pattern_name,
                destination,
            )
            self.dialogs.show_error(
                title="Permission Denied",
                message=f"Permission was denied exporting '{pattern_name}' to:\n"
                f"{destination}",
            )
            return
        except (PatternNotFoundError, PatternExportError) as exc:
            LOGGER.exception(
                "Could not export pattern '%s' to %s",
                pattern_name,
                destination,
            )
            self.dialogs.show_error(
                title="Cannot Export Pattern",
                message=f"Could not export '{pattern_name}' to:\n{destination}\n\n{exc}",
            )
            return

    def show_user_pattern_load_warning(self):
        if self.user_pattern_warning_shown:
            return

        issue = src.color_pattern_handler.user_pattern_load_issue
        if issue is None:
            return

        self.user_pattern_warning_shown = True
        self.dialogs.show_warning(
            title="User Patterns Not Loaded",
            message="The user-pattern file could not be loaded:\n"
            f"{issue.path}\n\n"
            "Built-in patterns are still available. The file was not changed.",
        )

    def open_log_folder(self):
        """Open the directory containing the persistent application log."""
        if self.application_log_path is None:
            self.dialogs.show_info(
                title="Application Log Unavailable",
                message="A persistent application log is not available.",
            )
            return

        log_directory = Path(self.application_log_path).parent
        try:
            log_directory.mkdir(parents=True, exist_ok=True)
            open_directory_in_file_manager(log_directory)
        except OSError as exc:
            LOGGER.exception(
                "Could not open application log directory: %s", log_directory
            )
            self.dialogs.show_error(
                title="Cannot Open Log Folder",
                message=f"The application log folder could not be opened:\n"
                f"{log_directory}\n\n{exc}",
            )

    def report_callback_exception(self, exc, val, tb):
        exception_info = (exc, val, tb)
        if getattr(self, "_handling_callback_exception", False):
            LOGGER.error(
                "Additional unhandled Tk callback exception while reporting an error",
                exc_info=exception_info,
            )
            return

        self._handling_callback_exception = True
        try:
            LOGGER.error(
                "Unhandled Tk callback exception",
                exc_info=exception_info,
            )
            message = (
                "An unexpected error occurred.\n\n"
                "The operation could not be completed.\n\n"
            )
            if self.application_log_path is not None:
                message += (
                    "Technical details were written to:\n\n"
                    f"{self.application_log_path}"
                )
            else:
                message += (
                    "Technical details could not be written to the application log."
                )
            try:
                showerror("Unexpected Error", message=message, parent=self)
            except Exception:
                LOGGER.exception("Could not display the unexpected-error dialog")
        finally:
            self._handling_callback_exception = False

    def on_exit(self):
        if self.closing:
            return
        self.closing = True
        try:
            settings = getattr(self, "settings", None)
            if settings is not None:
                settings.set_main_window_position((self.winfo_x(), self.winfo_y()))
        except OSError:
            LOGGER.exception("Could not save main-window position")
        self.batch_cancel.set()
        self._shutdown_owned_background_workers()
        self.destroy()

    def _shutdown_owned_background_workers(self):
        """Stop controllers before shutting down ArmyPainter-owned executors."""
        self.preview_controller.shutdown()
        self.preview_executor.shutdown(wait=False, cancel_futures=True)
        self.batch_executor.shutdown(wait=False, cancel_futures=True)


def main():
    application_log_path = configure_application_logging()
    log_application_startup(application_log_path, VERSION)
    army_painter = ArmyPainter(application_log_path=application_log_path)
    army_painter.mainloop()
    LOGGER.info("Clean application shutdown")


if __name__ == "__main__":
    main()
