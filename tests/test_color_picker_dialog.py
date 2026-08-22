import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from src.color_picker_visual import (
    color_wheel_geometry,
    hsv_to_rgb_hex,
    rgb_hex_to_hsl,
    rgb_hex_to_hsv,
)
from src.constant import APP_SELECTION_FOREGROUND
from src.paint_catalog import PaintCatalog, PaintColor
from src.favorite_color import (
    CitadelFavoriteColor,
    CustomFavoriteColor,
    FavoriteColorLibrary,
)
from src.paint_color_analysis import ColorGroup, PaletteSortMode, VISUAL_GROUP_ORDER
from src.paint_color_analysis import get_paints_for_group, sort_paints_visually
from src.widget import (
    COLOR_FIELD_PREFERRED_HEIGHT,
    COLOR_EDITOR_GROUP_PADDING,
    COLOR_EDITOR_SECTION_GAP,
    COLOR_MODEL_GROUP_PADDING,
    COLOR_MODEL_CONTROL_WIDTH,
    COLOR_PICKER_EDITOR_PANE_WIDTH,
    COLOR_PREVIEW_BORDER,
    FAVORITE_STAR_COLOR,
    COLOR_PICKER_GROUP_PANE_WIDTH,
    COLOR_PICKER_GROUP_ENTRIES,
    COLOR_PICKER_PALETTE_PANE_WIDTH,
    COLOR_SPACE_MODES,
    DEFAULT_COLOR_SPACE_MODE,
    NO_CITADEL_COLORS_MESSAGE,
    NO_FAVORITE_COLORS_MESSAGE,
    PAINT_SEARCH_PLACEHOLDER,
    PALETTE_SORT_DISPLAY_NAMES,
    PAINT_SWATCH_OUTLINE,
    PAINT_SWATCH_CORNER_RADIUS,
    PAINT_SWATCH_PREVIEW_SIZE,
    PAINT_SWATCH_SELECTED_OUTLINE,
    RECENT_COLOR_SWATCH_CORNER_RADIUS,
    ColorPickerDialog,
    CustomFavoriteNameDialog,
    PaintSwatchGrid,
    PaletteSpecialGroup,
    RecentColorSwatchRow,
    calculate_paint_swatch_cell_bounds,
    calculate_paint_swatch_columns,
    color_slot_presentation,
    draw_rounded_swatch,
    filter_paints_by_name,
    format_paint_name_for_swatch,
    format_visible_paint_count,
    paint_tooltip_text,
    paint_swatch_presentation,
    recent_color_tooltip_text,
)


class FakeWidget:
    def __init__(self, parent=None, **options):
        self.parent = parent
        self.options = options
        self.pack_options = None
        self.grid_options = None
        self.grid_columns = {}
        self.packed_children = []
        self.panes = []
        self.value = None
        self.bindings = {}

    def pack(self, **options):
        self.pack_options = options
        if hasattr(self.parent, "packed_children"):
            self.parent.packed_children.append(self)

    def pack_forget(self):
        self.pack_options = None
        if hasattr(self.parent, "packed_children") and self in self.parent.packed_children:
            self.parent.packed_children.remove(self)

    def pack_propagate(self, enabled):
        self.pack_propagate_enabled = enabled

    def grid(self, **options):
        self.grid_options = options

    def grid_columnconfigure(self, column, **options):
        self.grid_columns[column] = options

    def add(self, child, **options):
        self.panes.append((child, options))

    def set(self, value):
        self.value = value

    def get(self):
        return self.value

    def bind(self, event, callback, add=None):
        if add == "+" and event in self.bindings:
            return
        self.bindings[event] = callback

    def delete(self, first, last=None):
        self.value = ""

    def insert(self, index, value):
        self.value = value

    def configure(self, **options):
        self.options.update(options)


class FocusedFakeWidget(FakeWidget):
    def __init__(self, value, insert_index, selection):
        super().__init__()
        self.value = value
        self.insert_index = insert_index
        self.selection = selection

    def focus_get(self):
        return self

    def index(self, position):
        if position == "insert":
            return self.insert_index
        if position == "sel.first":
            return self.selection[0]
        if position == "sel.last":
            return self.selection[1]
        raise AssertionError(position)

    def selection_present(self):
        return self.selection is not None

    def icursor(self, index):
        self.insert_index = index

    def selection_range(self, start, end):
        self.selection = (start, end)


class FakeGroupButton:
    def __init__(self):
        self.states = []
        self.text = None

    def state(self, states):
        self.states = states

    def configure(self, *, text):
        self.text = text


class FakePaletteGrid:
    def __init__(self):
        self.paints = ()
        self.selected_paint_id = None
        self.empty_message = None

    def set_paints(self, paints):
        self.paints = tuple(paints)

    def set_empty_message(self, message):
        self.empty_message = message

    def set_selected_paint(self, paint_id):
        self.selected_paint_id = paint_id


class ColorPickerDialogTests(unittest.TestCase):
    def test_window_size_stays_within_a_constrained_screen(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.title = Mock()
        dialog.transient = Mock()
        dialog.resizable = Mock()
        dialog.winfo_screenwidth = Mock(return_value=800)
        dialog.winfo_screenheight = Mock(return_value=600)
        dialog.geometry = Mock()
        dialog.minsize = Mock()

        dialog._configure_window(object())

        dialog.geometry.assert_called_once_with("720x520")
        dialog.minsize.assert_called_once_with(720, 520)

    @patch("src.widget.tk.Toplevel.wait_window")
    @patch("src.widget.tk.Toplevel.grab_set")
    @patch("src.widget.tk.Toplevel.bind")
    @patch("src.widget.tk.Toplevel.protocol")
    @patch.object(ColorPickerDialog, "_build_color_editor")
    @patch.object(ColorPickerDialog, "_build_group_navigation")
    @patch.object(ColorPickerDialog, "_build_palette_grid")
    @patch.object(ColorPickerDialog, "_build_palette_search")
    @patch.object(ColorPickerDialog, "_build_main_layout")
    @patch.object(ColorPickerDialog, "_build_actions")
    @patch.object(ColorPickerDialog, "_configure_window")
    @patch("src.widget.tk.Toplevel.__init__", return_value=None)
    def test_construction_preserves_original_and_initializes_working_color(
        self,
        _toplevel_init,
        _configure_window,
        _build_actions,
        _build_main_layout,
        _build_palette_search,
        _build_palette_grid,
        _build_group_navigation,
        _build_color_editor,
        _protocol,
        _bind,
        grab_set,
        wait_window,
    ):
        settings = SimpleNamespace(
            color_picker_recent_colors=((150, 12, 9), (138, 31, 39))
        )
        dialog = ColorPickerDialog(object(), "#123456", settings=settings)

        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(dialog.current_color, "#123456")
        self.assertEqual(
            dialog.recent_colors,
            ((150, 12, 9), (138, 31, 39)),
        )
        self.assertEqual(dialog.color_space_mode, DEFAULT_COLOR_SPACE_MODE)
        self.assertIs(dialog.palette_sort_mode, PaletteSortMode.COLOR)
        self.assertEqual(dialog.search_query, "")
        self.assertIsNone(dialog.get_accepted_color())
        grab_set.assert_called_once_with()
        wait_window.assert_called_once_with()
        _bind.assert_any_call("<Return>", dialog.accept)
        _bind.assert_any_call("<Escape>", dialog.cancel)

    def test_accept_returns_current_color_and_preserves_original(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#abcdef"
        dialog.accepted_color = None
        dialog.destroy = Mock()

        dialog.accept()

        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(dialog.get_accepted_color(), "#abcdef")
        dialog.destroy.assert_called_once_with()

    def test_cancel_returns_none_and_preserves_color_state(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#abcdef"
        dialog.accepted_color = "#abcdef"
        dialog.destroy = Mock()

        dialog.cancel()

        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(dialog.current_color, "#abcdef")
        self.assertIsNone(dialog.get_accepted_color())
        dialog.destroy.assert_called_once_with()

    def test_only_accept_records_the_final_color_in_recent_history(self):
        settings = Mock()
        dialog = object.__new__(ColorPickerDialog)
        dialog.settings = settings
        dialog.current_color = "#8A1F27"
        dialog.accepted_color = None
        dialog.recent_colors = ((150, 12, 9),)
        dialog.destroy = Mock()
        dialog._refresh_color_representations = Mock()
        dialog._save_geometry = Mock()

        dialog.set_current_color("#123456")
        settings.set_color_picker_recent_colors.assert_not_called()
        dialog.cancel()
        settings.set_color_picker_recent_colors.assert_not_called()

        dialog.current_color = "#8A1F27"
        dialog.accept()

        settings.set_color_picker_recent_colors.assert_called_once_with(
            ((138, 31, 39), (150, 12, 9))
        )
        self.assertEqual(dialog.recent_colors[0], (138, 31, 39))

    def test_live_editor_interactions_never_write_recent_history(self):
        settings = Mock()
        dialog = object.__new__(ColorPickerDialog)
        dialog.settings = settings
        dialog.current_color = "#ff0000"
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog._updating_color_representations = False
        dialog._achromatic_hue = 0.0
        dialog.set_current_color = Mock()
        dialog.hsv_color_field = Mock()
        dialog.hsv_color_field.winfo_width.return_value = 101
        dialog.hsv_color_field.winfo_height.return_value = 101
        dialog.hue_slider = Mock()
        dialog.hue_slider.winfo_height.return_value = 101
        dialog.rgb_controls = {
            name: FakeWidget() for name in ("red", "green", "blue")
        }
        for name, value in zip(("red", "green", "blue"), ("1", "2", "3")):
            dialog.rgb_controls[name].value = value
        dialog.palette_grid = FakePaletteGrid()

        dialog._on_color_field_input(SimpleNamespace(x=50, y=25))
        dialog._on_hue_slider_input(SimpleNamespace(y=50))
        dialog._on_rgb_control_changed()
        dialog.select_paint(PaintColor("paint", "Paint", 150, 12, 9))

        self.assertEqual(dialog.set_current_color.call_count, 4)
        settings.set_color_picker_recent_colors.assert_not_called()

    def test_duplicate_confirmation_moves_one_color_to_front(self):
        settings = Mock()
        dialog = object.__new__(ColorPickerDialog)
        dialog.settings = settings
        dialog.current_color = "#8A1F27"
        dialog.accepted_color = None
        dialog.recent_colors = ((1, 2, 3), (138, 31, 39), (4, 5, 6))
        dialog._save_geometry = Mock()
        dialog.destroy = Mock()

        dialog.accept()

        settings.set_color_picker_recent_colors.assert_called_once_with(
            ((138, 31, 39), (1, 2, 3), (4, 5, 6))
        )

    def test_current_color_has_one_public_update_path(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.current_color = "#123456"
        dialog._refresh_color_representations = Mock()

        dialog.set_current_color("#abcdef")

        self.assertEqual(dialog.current_color, "#abcdef")
        dialog._refresh_color_representations.assert_called_once_with()

    def test_color_synchronization_guard_prevents_recursive_updates(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.current_color = "#123456"
        refresh_count = 0

        def refresh_representations():
            nonlocal refresh_count
            refresh_count += 1
            dialog.set_current_color("#000000")

        dialog._refresh_color_representations = refresh_representations

        dialog.set_current_color("#abcdef")

        self.assertEqual(dialog.current_color, "#abcdef")
        self.assertEqual(refresh_count, 1)
        self.assertFalse(dialog._updating_color_representations)

    def test_setting_current_color_refreshes_every_dependent_representation(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.current_color = "#123456"
        refreshers = (
            "_refresh_rgb_controls",
            "_refresh_color_model_controls",
            "_refresh_hex_control",
            "_refresh_visual_picker",
            "_refresh_current_color_preview",
        )
        for refresher in refreshers:
            setattr(dialog, refresher, Mock())

        dialog.set_current_color("#abcdef")

        for refresher in refreshers:
            with self.subTest(refresher=refresher):
                getattr(dialog, refresher).assert_called_once_with()

    def test_hsv_visual_interaction_updates_canonical_current_color(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog.current_color = "#ff0000"
        dialog.hsv_color_field = Mock()
        dialog.hsv_color_field.winfo_width.return_value = 101
        dialog.hsv_color_field.winfo_height.return_value = 101
        dialog.set_current_color = Mock()

        dialog._on_hsv_field_input(SimpleNamespace(x=50, y=25))

        dialog.set_current_color.assert_called_once_with("#bf6060")

    def test_programmatic_color_change_repositions_hsv_indicators(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog.current_color = "#00ff00"
        dialog.hsv_color_field = Mock()
        dialog.hue_slider = Mock()
        dialog._render_hsv_field = Mock()
        dialog._render_hue_slider = Mock()
        dialog._draw_hsv_indicators = Mock()

        dialog._refresh_visual_picker()

        dialog._render_hsv_field.assert_called_once_with(1 / 3)
        dialog._render_hue_slider.assert_called_once_with()
        dialog._draw_hsv_indicators.assert_called_once_with(1 / 3, 1.0, 1.0)

    def test_hsl_visual_interaction_updates_canonical_current_color(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.color_space_mode = "HSL"
        dialog.current_color = "#ff0000"
        dialog.hsv_color_field = Mock()
        dialog.hsv_color_field.winfo_width.return_value = 101
        dialog.hsv_color_field.winfo_height.return_value = 101
        dialog.set_current_color = Mock()

        dialog._on_color_field_input(SimpleNamespace(x=50, y=25))

        dialog.set_current_color.assert_called_once_with("#df9f9f")

    def test_color_space_switch_updates_component_label_and_preserves_exact_rgb(self):
        colors = (
            "#000000",
            "#FFFFFF",
            "#808080",
            "#FF0000",
            "#00FF00",
            "#0000FF",
            "#123005",
            "#F2A6D8",
            "#960C09",  # Citadel Mephiston Red
            "#2A7FD4",  # Custom non-Citadel colour
        )
        transitions = (
            (DEFAULT_COLOR_SPACE_MODE, "HSV / HSB", "Value:"),
            ("HSL", "HSL", "Lightness:"),
            ("Color Wheel", "HSV / HSB", "Value:"),
            ("Classic", "HSV / HSB", "Value:"),
            (DEFAULT_COLOR_SPACE_MODE, "HSV / HSB", "Value:"),
            ("Color Wheel", "HSV / HSB", "Value:"),
            ("HSL", "HSL", "Lightness:"),
            ("Classic", "HSV / HSB", "Value:"),
        )
        for color in colors:
            with self.subTest(color=color):
                dialog = object.__new__(ColorPickerDialog)
                dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
                dialog.current_color = color
                dialog.color_space_selector = FakeWidget()
                dialog.color_space_selector.set(DEFAULT_COLOR_SPACE_MODE)
                dialog.editor_alternate_color_space_area = FakeWidget()
                dialog.color_model_labels = {"component": FakeWidget()}
                dialog._refresh_color_model_controls = Mock()
                dialog._refresh_visual_picker = Mock()

                dialog.color_model_labels["component"].configure(text="Value:")
                self.assertEqual(
                    dialog.color_model_labels["component"].options["text"],
                    "Value:",
                )
                for mode, expected_title, expected_label in transitions:
                    dialog.select_color_space(mode)
                    self.assertEqual(dialog.color_space_mode, mode)
                    self.assertEqual(dialog.color_space_selector.get(), mode)
                    self.assertEqual(
                        dialog.editor_alternate_color_space_area.options["text"],
                        expected_title,
                    )
                    self.assertEqual(
                        dialog.color_model_labels["component"].options["text"],
                        expected_label,
                    )
                    self.assertEqual(dialog.current_color, color)

                self.assertEqual(dialog._refresh_color_model_controls.call_count, 8)
                self.assertEqual(dialog._refresh_visual_picker.call_count, 8)

    def test_each_mode_loads_its_own_visualization_and_markers_without_stale_views(
        self,
    ):
        dialog = object.__new__(ColorPickerDialog)
        dialog.current_color = "#2A7FD4"
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog._achromatic_hue = 0.0
        dialog.color_space_selector = FakeWidget()
        dialog.editor_alternate_color_space_area = FakeWidget()
        dialog.color_model_labels = {"component": FakeWidget()}
        dialog.editor_color_field_area = FakeWidget()
        dialog.editor_slider_area = FakeWidget()
        dialog.color_wheel_canvas = FakeWidget()
        dialog.classic_visualization_area = FakeWidget()
        dialog.hsv_color_field = Mock()
        dialog.hue_slider = Mock()
        dialog.classic_color_field = Mock()
        dialog.classic_value_slider = Mock()
        for canvas in (
            dialog.hsv_color_field,
            dialog.hue_slider,
            dialog.classic_color_field,
            dialog.classic_value_slider,
        ):
            canvas.winfo_width.return_value = 101
            canvas.winfo_height.return_value = 101
        dialog.color_wheel_canvas.winfo_width = lambda: 101
        dialog.color_wheel_canvas.winfo_height = lambda: 101
        dialog._refresh_color_model_controls = Mock()
        dialog._render_hsv_field = Mock()
        dialog._render_hsl_field = Mock()
        dialog._render_hue_slider = Mock()
        dialog._draw_hsv_indicators = Mock()
        dialog._render_color_wheel = Mock()
        dialog._draw_color_wheel_indicators = Mock()
        dialog._render_classic_field = Mock()
        dialog._render_classic_value_slider = Mock()
        dialog._draw_classic_indicators = Mock()

        expectations = (
            (
                DEFAULT_COLOR_SPACE_MODE,
                dialog._render_hsv_field,
                dialog._draw_hsv_indicators,
            ),
            ("HSL", dialog._render_hsl_field, dialog._draw_hsv_indicators),
            (
                "Color Wheel",
                dialog._render_color_wheel,
                dialog._draw_color_wheel_indicators,
            ),
            ("Classic", dialog._render_classic_field, dialog._draw_classic_indicators),
        )
        for mode, renderer, marker_drawer in expectations:
            with self.subTest(mode=mode):
                renderer.reset_mock()
                marker_drawer.reset_mock()
                dialog.select_color_space(mode)
                renderer.assert_called_once()
                marker_drawer.assert_called_once()
                if mode == "Color Wheel":
                    self.assertIsNotNone(dialog.color_wheel_canvas.pack_options)
                    self.assertIsNone(dialog.classic_visualization_area.pack_options)
                    self.assertIsNone(dialog.editor_color_field_area.pack_options)
                elif mode == "Classic":
                    self.assertIsNone(dialog.color_wheel_canvas.pack_options)
                    self.assertIsNotNone(dialog.classic_visualization_area.pack_options)
                    self.assertIsNone(dialog.editor_color_field_area.pack_options)
                else:
                    self.assertIsNone(dialog.color_wheel_canvas.pack_options)
                    self.assertIsNone(dialog.classic_visualization_area.pack_options)
                    self.assertIsNotNone(dialog.editor_color_field_area.pack_options)

    def test_all_modes_keep_coherent_numeric_model_titles_and_field_labels(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.current_color = "#2A7FD4"
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog.color_space_selector = FakeWidget()
        dialog.editor_alternate_color_space_area = FakeWidget()
        dialog.color_model_labels = {
            "hue": FakeWidget(text="Hue:"),
            "saturation": FakeWidget(text="Saturation:"),
            "component": FakeWidget(text="Value:"),
        }
        dialog._refresh_color_model_controls = Mock()
        dialog._refresh_visual_picker = Mock()

        expected = (
            (DEFAULT_COLOR_SPACE_MODE, "HSV / HSB", "Value:"),
            ("HSL", "HSL", "Lightness:"),
            ("Color Wheel", "HSV / HSB", "Value:"),
            ("Classic", "HSV / HSB", "Value:"),
            ("HSL", "HSL", "Lightness:"),
            ("Classic", "HSV / HSB", "Value:"),
        )
        for mode, title, component_label in expected:
            dialog.select_color_space(mode)
            self.assertEqual(
                dialog.editor_alternate_color_space_area.options["text"], title
            )
            self.assertEqual(dialog.color_model_labels["hue"].options["text"], "Hue:")
            self.assertEqual(
                dialog.color_model_labels["saturation"].options["text"],
                "Saturation:",
            )
            self.assertEqual(
                dialog.color_model_labels["component"].options["text"],
                component_label,
            )

    def test_color_model_validation_enforces_hue_and_percent_boundaries(self):
        for proposed, maximum in (("0", "359"), ("359", "359"), ("100", "100")):
            self.assertTrue(ColorPickerDialog._validate_model_input(proposed, maximum))
        for proposed, maximum in (("360", "359"), ("101", "100"), ("-1", "100")):
            self.assertFalse(ColorPickerDialog._validate_model_input(proposed, maximum))

    def test_hsv_numeric_edit_updates_canonical_color_and_dependents(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog.original_color = "#123456"
        dialog.current_color = "#123456"
        dialog._updating_color_representations = False
        dialog.color_model_controls = {
            name: FakeWidget() for name in ("hue", "saturation", "component")
        }
        for name, value in zip(
            ("hue", "saturation", "component"), ("120", "100", "100")
        ):
            dialog.color_model_controls[name].value = value
        dialog._refresh_color_representations = Mock()

        dialog._on_color_model_control_changed()

        self.assertEqual(dialog.current_color, "#00ff00")
        self.assertEqual(dialog.original_color, "#123456")
        dialog._refresh_color_representations.assert_called_once_with()

    def test_hsl_numeric_edit_updates_canonical_color(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.color_space_mode = "HSL"
        dialog.original_color = "#123456"
        dialog.current_color = "#123456"
        dialog._updating_color_representations = False
        dialog.color_model_controls = {
            name: FakeWidget() for name in ("hue", "saturation", "component")
        }
        for name, value in zip(
            ("hue", "saturation", "component"), ("240", "100", "50")
        ):
            dialog.color_model_controls[name].value = value
        dialog._refresh_color_representations = Mock()

        dialog._on_color_model_control_changed()

        self.assertEqual(dialog.current_color, "#0000ff")
        self.assertEqual(dialog.original_color, "#123456")

    def test_achromatic_color_preserves_last_editing_hue(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog.current_color = "#808080"
        dialog._achromatic_hue = 2 / 3
        dialog.color_model_controls = {
            name: FakeWidget() for name in ("hue", "saturation", "component")
        }

        dialog._refresh_color_model_controls()

        self.assertEqual(dialog.color_model_controls["hue"].get(), "240")
        self.assertEqual(dialog.color_model_controls["saturation"].get(), "0")
        self.assertEqual(dialog.color_model_controls["component"].get(), "50")

    def test_programmatic_color_change_repositions_hsl_indicators(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.color_space_mode = "HSL"
        dialog.current_color = "#00ff00"
        dialog.hsv_color_field = Mock()
        dialog.hue_slider = Mock()
        dialog._render_hsl_field = Mock()
        dialog._render_hue_slider = Mock()
        dialog._draw_hsv_indicators = Mock()

        dialog._refresh_visual_picker()

        dialog._render_hsl_field.assert_called_once_with(1 / 3)
        dialog._render_hue_slider.assert_called_once_with()
        dialog._draw_hsv_indicators.assert_called_once_with(1 / 3, 1.0, 0.5)

    def test_color_synchronization_guard_is_released_after_refresh_failure(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.current_color = "#123456"
        dialog._refresh_color_representations = Mock(
            side_effect=RuntimeError("refresh failed")
        )

        with self.assertRaisesRegex(RuntimeError, "refresh failed"):
            dialog.set_current_color("#abcdef")

        self.assertFalse(dialog._updating_color_representations)

    def test_window_size_keeps_palette_and_editor_usable(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.title = Mock()
        dialog.transient = Mock()
        dialog.resizable = Mock()
        dialog.winfo_screenwidth = Mock(return_value=1920)
        dialog.winfo_screenheight = Mock(return_value=1080)
        dialog.geometry = Mock()
        dialog.minsize = Mock()
        parent = object()

        dialog._configure_window(parent)

        dialog.title.assert_called_once_with("Select Color")
        dialog.transient.assert_called_once_with(parent)
        dialog.resizable.assert_called_once_with(True, True)
        dialog.geometry.assert_called_once_with("1196x760")
        dialog.minsize.assert_called_once_with(900, 760)

    def test_saved_window_geometry_is_restored_before_display(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.settings = SimpleNamespace(
            color_picker_geometry="1000x650-1800+120"
        )
        dialog.title = Mock()
        dialog.transient = Mock()
        dialog.resizable = Mock()
        dialog.winfo_screenwidth = Mock(return_value=1920)
        dialog.winfo_screenheight = Mock(return_value=1080)
        dialog.winfo_vrootx = Mock(return_value=-1920)
        dialog.winfo_vrooty = Mock(return_value=0)
        dialog.winfo_vrootwidth = Mock(return_value=3840)
        dialog.winfo_vrootheight = Mock(return_value=1080)
        dialog.geometry = Mock()
        dialog.minsize = Mock()

        dialog._configure_window(object())

        dialog.geometry.assert_called_once_with("1000x760-1800+120")

    def test_invalid_saved_window_geometry_uses_current_default_size(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.settings = SimpleNamespace(color_picker_geometry="invalid")
        dialog.title = Mock()
        dialog.transient = Mock()
        dialog.resizable = Mock()
        dialog.winfo_screenwidth = Mock(return_value=1920)
        dialog.winfo_screenheight = Mock(return_value=1080)
        dialog.winfo_vrootx = Mock(return_value=0)
        dialog.winfo_vrooty = Mock(return_value=0)
        dialog.winfo_vrootwidth = Mock(return_value=1920)
        dialog.winfo_vrootheight = Mock(return_value=1080)
        dialog.geometry = Mock()
        dialog.minsize = Mock()

        dialog._configure_window(object())

        dialog.geometry.assert_called_once_with("1196x760")
        dialog.minsize.assert_called_once_with(900, 760)

    def test_saved_window_geometry_enforces_each_picker_minimum_dimension(self):
        cases = (
            ("1200x900+200+100", "1200x900+200+100"),
            ("1000x600+200+100", "1000x760+200+100"),
            ("700x900+200+100", "900x900+200+100"),
            ("700x600+200+100", "900x760+200+100"),
            ("1000x800+2500+1200", "1000x800+920+280"),
            ("1100x760+120+80", "1100x760+120+80"),
        )
        for saved_geometry, expected_geometry in cases:
            with self.subTest(saved_geometry=saved_geometry):
                dialog = object.__new__(ColorPickerDialog)
                dialog.settings = SimpleNamespace(
                    color_picker_geometry=saved_geometry
                )
                dialog.title = Mock()
                dialog.transient = Mock()
                dialog.resizable = Mock()
                dialog.winfo_screenwidth = Mock(return_value=1920)
                dialog.winfo_screenheight = Mock(return_value=1080)
                dialog.winfo_vrootx = Mock(return_value=0)
                dialog.winfo_vrooty = Mock(return_value=0)
                dialog.winfo_vrootwidth = Mock(return_value=1920)
                dialog.winfo_vrootheight = Mock(return_value=1080)
                dialog.geometry = Mock()
                dialog.minsize = Mock()

                dialog._configure_window(object())

                dialog.geometry.assert_called_once_with(expected_geometry)
                dialog.minsize.assert_called_once_with(900, 760)

    def test_closing_picker_saves_current_geometry(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.settings = Mock()
        dialog.geometry = Mock(return_value="1050x680+140+90")
        dialog.selected_color_group = ColorGroup.BLUE
        dialog.color_space_mode = "HSL"
        dialog.palette_sort_mode = PaletteSortMode.ALPHABETICAL
        dialog.main_panes = Mock()
        dialog.main_panes.sashpos.side_effect = (140, 700)
        dialog.destroy = Mock()
        dialog.accepted_color = None

        dialog.cancel()

        dialog.settings.set_color_picker_ui_state.assert_called_once_with(
            "1050x680+140+90", "Blues", "HSL", "alphabetical", (140, 700)
        )
        dialog.destroy.assert_called_once_with()

    def test_saved_picker_modes_are_validated_without_restoring_search_or_color(self):
        settings = SimpleNamespace(
            color_picker_group="Blues",
            color_picker_color_space="HSL",
            color_picker_sort_mode="alphabetical",
        )
        with patch("src.widget.tk.Toplevel.__init__", return_value=None), patch.object(
            ColorPickerDialog, "_configure_window"
        ), patch.object(ColorPickerDialog, "_build_main_layout"), patch.object(
            ColorPickerDialog, "_build_palette_search"
        ), patch.object(ColorPickerDialog, "_build_palette_grid"), patch.object(
            ColorPickerDialog, "_build_group_navigation"
        ), patch.object(ColorPickerDialog, "_build_color_editor"), patch.object(
            ColorPickerDialog, "_build_actions"
        ), patch.object(ColorPickerDialog, "protocol"), patch.object(
            ColorPickerDialog, "bind"
        ), patch.object(ColorPickerDialog, "grab_set"), patch.object(
            ColorPickerDialog, "wait_window"
        ):
            dialog = ColorPickerDialog(object(), "#123456", settings=settings)

        self.assertIs(dialog.selected_color_group, ColorGroup.BLUE)
        self.assertEqual(dialog.color_space_mode, "HSL")
        self.assertIs(dialog.palette_sort_mode, PaletteSortMode.ALPHABETICAL)
        self.assertEqual(dialog.search_query, "")
        self.assertEqual(dialog.current_color, "#123456")

    def test_saved_color_wheel_mode_is_restored_for_central_application(self):
        settings = SimpleNamespace(
            color_picker_group=None,
            color_picker_color_space="Color Wheel",
        )
        with patch("src.widget.tk.Toplevel.__init__", return_value=None), patch.object(
            ColorPickerDialog, "_configure_window"
        ), patch.object(ColorPickerDialog, "_build_main_layout"), patch.object(
            ColorPickerDialog, "_build_palette_search"
        ), patch.object(ColorPickerDialog, "_build_palette_grid"), patch.object(
            ColorPickerDialog, "_build_group_navigation"
        ), patch.object(ColorPickerDialog, "_build_color_editor"), patch.object(
            ColorPickerDialog, "_build_actions"
        ), patch.object(ColorPickerDialog, "protocol"), patch.object(
            ColorPickerDialog, "bind"
        ), patch.object(ColorPickerDialog, "grab_set"), patch.object(
            ColorPickerDialog, "wait_window"
        ):
            dialog = ColorPickerDialog(object(), "#123456", settings=settings)

        self.assertEqual(dialog.color_space_mode, "Color Wheel")
        self.assertIn(str(dialog.color_space_mode), COLOR_SPACE_MODES)

    def test_invalid_saved_picker_modes_use_defaults(self):
        settings = SimpleNamespace(
            color_picker_group="Unknown",
            color_picker_color_space="LAB",
            color_picker_sort_mode="obsolete",
        )
        dialog = object.__new__(ColorPickerDialog)
        saved_group = getattr(settings, "color_picker_group", None)
        dialog.selected_color_group = next(
            (group for group in VISUAL_GROUP_ORDER if group.value == saved_group),
            None,
        )
        saved_mode = settings.color_picker_color_space
        dialog.color_space_mode = (
            saved_mode if saved_mode in COLOR_SPACE_MODES else DEFAULT_COLOR_SPACE_MODE
        )

        self.assertIsNone(dialog.selected_color_group)
        self.assertEqual(dialog.color_space_mode, DEFAULT_COLOR_SPACE_MODE)

        saved_sort_mode = settings.color_picker_sort_mode
        dialog.palette_sort_mode = next(
            (mode for mode in PaletteSortMode if mode.value == saved_sort_mode),
            PaletteSortMode.COLOR,
        )
        self.assertIs(dialog.palette_sort_mode, PaletteSortMode.COLOR)

    def test_valid_saved_sashes_restore_within_current_picker_width(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.settings = SimpleNamespace(color_picker_sashes=(150, 700))
        dialog.main_panes = Mock()
        dialog.main_panes.winfo_width.return_value = 1100

        dialog._restore_pane_sashes()

        self.assertEqual(
            dialog.main_panes.sashpos.call_args_list,
            [call(0, 150), call(1, 700)],
        )

    @patch("src.widget.ttk.LabelFrame", side_effect=FakeWidget)
    @patch("src.widget.ttk.Panedwindow", side_effect=FakeWidget)
    @patch("src.widget.ttk.Frame", side_effect=FakeWidget)
    def test_main_layout_has_three_weighted_areas_and_editor_containers(
        self, _frame_type, _paned_type, _label_frame_type
    ):
        dialog = object.__new__(ColorPickerDialog)

        dialog._build_main_layout()

        pane_names = [pane.options["text"] for pane, _ in dialog.main_panes.panes]
        pane_weights = [options["weight"] for _, options in dialog.main_panes.panes]
        self.assertEqual(pane_names, ["Groups", "Citadel Colors", "Color Editor"])
        self.assertEqual(pane_weights, [0, 3, 1])
        self.assertEqual(
            [pane.options["width"] for pane, _ in dialog.main_panes.panes],
            [
                COLOR_PICKER_GROUP_PANE_WIDTH,
                COLOR_PICKER_PALETTE_PANE_WIDTH,
                COLOR_PICKER_EDITOR_PANE_WIDTH,
            ],
        )
        self.assertFalse(dialog.palette_area.pack_propagate_enabled)
        self.assertFalse(dialog.editor_area.pack_propagate_enabled)
        self.assertEqual(dialog.editor_rgb_area.options["text"], "RGB")
        self.assertEqual(
            dialog.editor_rgb_area.options["padding"],
            COLOR_EDITOR_GROUP_PADDING,
        )
        self.assertEqual(
            dialog.editor_alternate_color_space_area.options["text"],
            DEFAULT_COLOR_SPACE_MODE,
        )
        self.assertEqual(
            dialog.editor_alternate_color_space_area.options["padding"],
            COLOR_MODEL_GROUP_PADDING,
        )
        self.assertEqual(
            dialog.editor_color_model_controls_area.grid_options,
            {"row": 0, "column": 0, "sticky": "ew"},
        )
        self.assertEqual(
            dialog.editor_hex_area.grid_options,
            {
                "row": 1,
                "column": 0,
                "sticky": "ew",
                "pady": (COLOR_EDITOR_SECTION_GAP, 0),
            },
        )
        for area in (
            dialog.editor_visualization_area,
            dialog.editor_numeric_area,
            dialog.editor_alternate_color_space_area,
            dialog.editor_recent_colors_area,
            dialog.editor_preview_area,
        ):
            with self.subTest(spaced_area=area):
                self.assertEqual(
                    area.pack_options["pady"],
                    (COLOR_EDITOR_SECTION_GAP, 0),
                )
        for area in (
            dialog.editor_numeric_area,
            dialog.editor_recent_colors_area,
            dialog.editor_preview_area,
        ):
            with self.subTest(fixed_height_area=area):
                self.assertEqual(area.pack_options["side"], "bottom")
                self.assertFalse(area.pack_options.get("expand", False))
        self.assertEqual(
            dialog.editor_area.packed_children,
            [
                dialog.editor_color_space_area,
                dialog.editor_preview_area,
                dialog.editor_recent_colors_area,
                dialog.editor_numeric_area,
                dialog.editor_visualization_area,
            ],
        )
        self.assertEqual(
            dialog.palette_header_area.packed_children,
            [
                dialog.palette_count_area,
                dialog.palette_sort_area,
                dialog.palette_search_area,
            ],
        )
        self.assertEqual(
            dialog.palette_sort_area.pack_options,
            {"side": "right", "padx": (8, 0)},
        )
        self.assertEqual(
            dialog.editor_visualization_area.packed_children,
            [dialog.editor_slider_area, dialog.editor_color_field_area],
        )
        self.assertEqual(dialog.editor_slider_area.options["width"], 28)
        self.assertEqual(
            dialog.editor_preview_area.grid_columns,
            {
                0: {"weight": 1, "uniform": "preview"},
                1: {"weight": 1, "uniform": "preview"},
            },
        )
        self.assertEqual(
            dialog.original_color_preview_area.grid_options,
            {"row": 0, "column": 0, "sticky": "ew", "padx": (0, 4)},
        )
        self.assertEqual(
            dialog.current_color_preview_area.grid_options,
            {"row": 0, "column": 1, "sticky": "ew", "padx": (4, 0)},
        )
        self.assertTrue(dialog.dialog_content.pack_options["expand"])
        self.assertTrue(dialog.main_panes.pack_options["expand"])
        for attribute in (
            "palette_search_area",
            "palette_sort_area",
            "palette_count_area",
            "palette_grid_area",
            "editor_color_space_area",
            "editor_visualization_area",
            "editor_color_field_area",
            "editor_slider_area",
            "editor_numeric_area",
            "editor_rgb_area",
            "editor_alternate_color_space_area",
            "editor_color_model_controls_area",
            "editor_hex_area",
            "editor_recent_colors_area",
            "editor_preview_area",
            "original_color_preview_area",
            "current_color_preview_area",
        ):
            with self.subTest(container=attribute):
                self.assertIsInstance(getattr(dialog, attribute), FakeWidget)

    @patch("src.widget.ttk.Entry", side_effect=FakeWidget)
    @patch("src.widget.ttk.Combobox", side_effect=FakeWidget)
    @patch("src.widget.ttk.Label", side_effect=FakeWidget)
    def test_palette_header_builds_compact_sort_selector_beside_search(
        self, _label_type, _combobox_type, _entry_type
    ):
        dialog = object.__new__(ColorPickerDialog)
        dialog.palette_sort_mode = PaletteSortMode.COLOR
        dialog.palette_search_area = FakeWidget()
        dialog.palette_sort_area = FakeWidget()
        dialog.palette_count_area = FakeWidget()

        dialog._build_palette_search()

        self.assertEqual(
            dialog.palette_sort_selector.options["values"],
            PALETTE_SORT_DISPLAY_NAMES,
        )
        self.assertEqual(PALETTE_SORT_DISPLAY_NAMES, ("Color", "Alphabetical"))
        self.assertEqual(dialog.palette_sort_selector.options["state"], "readonly")
        self.assertEqual(dialog.palette_sort_selector.options["width"], 12)
        self.assertEqual(dialog.palette_sort_selector.get(), "Color")
        self.assertEqual(dialog.palette_sort_label.options["text"], "Sort:")
        self.assertIn(
            "<<ComboboxSelected>>", dialog.palette_sort_selector.bindings
        )
        self.assertTrue(dialog.search_entry.pack_options["expand"])
        self.assertEqual(dialog.palette_count_label.options["text"], "0 colors")

    def test_navigation_entries_reuse_all_runtime_color_groups(self):
        groups = tuple(color_group for color_group, _ in COLOR_PICKER_GROUP_ENTRIES)
        labels = tuple(label for _, label in COLOR_PICKER_GROUP_ENTRIES)

        self.assertEqual(
            groups,
            (PaletteSpecialGroup.FAVORITES, None) + VISUAL_GROUP_ORDER,
        )
        self.assertEqual(labels[:2], ("★ Favorites", "🌈 All Colors"))
        self.assertNotIn("Custom Favorites", labels)
        self.assertNotIn("Metallic", labels)

    def test_favorites_navigation_is_permanent_and_safely_empty_before_contents(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(
            paints=(PaintColor("red", "Red", 255, 0, 0),)
        )
        dialog.search_query = ""
        dialog.palette_sort_mode = PaletteSortMode.COLOR
        dialog.favorite_library = FavoriteColorLibrary(dialog.paint_catalog)
        dialog.group_buttons = {
            group: FakeGroupButton() for group, _ in COLOR_PICKER_GROUP_ENTRIES
        }
        dialog.group_button_labels = dict(COLOR_PICKER_GROUP_ENTRIES)
        dialog._refresh_palette_display = Mock()

        dialog.select_color_group(PaletteSpecialGroup.FAVORITES)

        self.assertIs(
            dialog.selected_color_group,
            PaletteSpecialGroup.FAVORITES,
        )
        self.assertEqual(dialog.palette_paints, ())
        self.assertEqual(
            dialog.group_buttons[PaletteSpecialGroup.FAVORITES].states,
            ["selected"],
        )

    def test_favorites_combines_citadel_and_custom_while_normal_groups_exclude_custom(self):
        red = PaintColor("red", "Catalog Red", 255, 0, 0)
        blue = PaintColor("blue", "Catalog Blue", 0, 0, 255)
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=(red, blue))
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog,
            (
                CitadelFavoriteColor("red"),
                CustomFavoriteColor("custom-1", "My Green", "#00FF00"),
            ),
        )
        dialog.search_query = ""
        dialog.palette_sort_mode = PaletteSortMode.ALPHABETICAL
        dialog.group_buttons = {
            group: FakeGroupButton() for group, _ in COLOR_PICKER_GROUP_ENTRIES
        }
        dialog.group_button_labels = dict(COLOR_PICKER_GROUP_ENTRIES)
        dialog._refresh_palette_display = Mock()

        dialog.select_color_group(PaletteSpecialGroup.FAVORITES)
        favorite_names = {color.name for color in dialog.palette_paints}
        dialog.select_color_group(None)
        all_names = {color.name for color in dialog.palette_paints}
        dialog.select_color_group(ColorGroup.GREEN)
        green_names = {color.name for color in dialog.palette_paints}

        self.assertEqual(favorite_names, {"Catalog Red", "My Green"})
        self.assertEqual(all_names, {"Catalog Red", "Catalog Blue"})
        self.assertNotIn("My Green", green_names)

    def test_favorites_search_filters_citadel_and_custom_names_and_clears(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(
            paints=(
                PaintColor("blue", "Macragge Blue", 0, 0, 255),
                PaintColor("red", "Mephiston Red", 255, 0, 0),
            )
        )
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog,
            (
                CitadelFavoriteColor("blue"),
                CitadelFavoriteColor("red"),
                CustomFavoriteColor(
                    "custom-blue", "My Armor Blue", "#123456"
                ),
                CustomFavoriteColor("custom-green", "My Green", "#00FF00"),
            ),
        )
        dialog.selected_color_group = PaletteSpecialGroup.FAVORITES
        dialog.search_query = ""
        dialog.palette_sort_mode = PaletteSortMode.ALPHABETICAL
        dialog._refresh_palette_display = Mock()

        dialog._refresh_palette_data_source()
        all_favorites = tuple(color.name for color in dialog.palette_paints)
        dialog.set_paint_search("BLUE")
        blue_favorites = tuple(color.name for color in dialog.palette_paints)
        dialog.set_paint_search("")
        restored_favorites = tuple(color.name for color in dialog.palette_paints)

        self.assertEqual(
            all_favorites,
            ("Macragge Blue", "Mephiston Red", "My Armor Blue", "My Green"),
        )
        self.assertEqual(blue_favorites, ("Macragge Blue", "My Armor Blue"))
        self.assertEqual(restored_favorites, all_favorites)

    def test_favorites_use_existing_sort_modes_across_both_types(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(
            paints=(
                PaintColor("z-red", "Zulu Red", 240, 10, 10),
                PaintColor("a-blue", "Alpha Blue", 10, 10, 240),
            )
        )
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog,
            (
                CitadelFavoriteColor("z-red"),
                CitadelFavoriteColor("a-blue"),
                CustomFavoriteColor("custom-green", "Mike Green", "#00C040"),
                CustomFavoriteColor("custom-yellow", "Bravo Yellow", "#E0D000"),
            ),
        )
        dialog.selected_color_group = PaletteSpecialGroup.FAVORITES
        dialog.search_query = ""
        dialog.palette_sort_mode = PaletteSortMode.COLOR
        dialog._refresh_palette_display = Mock()
        dialog._refresh_palette_data_source()
        projected = dialog.favorite_library.palette_colors()

        color_order = tuple(color.id for color in dialog.palette_paints)
        dialog.set_palette_sort_mode(PaletteSortMode.ALPHABETICAL)
        alphabetical_names = tuple(color.name for color in dialog.palette_paints)

        self.assertEqual(
            color_order,
            tuple(color.id for color in sort_paints_visually(projected)),
        )
        self.assertEqual(
            alphabetical_names,
            ("Alpha Blue", "Bravo Yellow", "Mike Green", "Zulu Red"),
        )
        self.assertEqual(
            PALETTE_SORT_DISPLAY_NAMES,
            ("Color", "Alphabetical"),
        )

    def test_citadel_favorite_toggle_adds_removes_persists_and_refreshes(self):
        paint = PaintColor("red", "Red", 255, 0, 0)
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=(paint,))
        dialog.favorite_library = FavoriteColorLibrary(dialog.paint_catalog)
        dialog.settings = Mock()
        dialog._refresh_palette_data_source = Mock()

        self.assertEqual(
            dialog._citadel_favorite_action_label(paint),
            "Add to Favorites",
        )
        self.assertTrue(dialog.toggle_citadel_favorite(paint))
        self.assertEqual(
            dialog._citadel_favorite_action_label(paint),
            "Remove from Favorites",
        )
        self.assertTrue(dialog.toggle_citadel_favorite(paint))

        self.assertEqual(dialog.favorite_library.favorites, ())
        self.assertEqual(dialog.settings.set_favorite_colors.call_count, 2)
        self.assertEqual(dialog._refresh_palette_data_source.call_count, 2)

    def test_universal_button_uses_exact_citadel_resolution_and_shared_toggle(self):
        canonical = PaintColor("canonical", "Canonical", 10, 20, 30)
        explicit = PaintColor("explicit", "Explicit", 10, 20, 30)
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=(canonical, explicit))
        dialog.favorite_library = FavoriteColorLibrary(dialog.paint_catalog)
        dialog.current_color = "#0A141E"
        dialog.selected_paint_id = "explicit"
        dialog.toggle_citadel_favorite = Mock(return_value=True)

        self.assertEqual(dialog.current_favorite_action_label(), "★ Add Favorite")
        self.assertTrue(dialog.toggle_current_favorite())

        dialog.toggle_citadel_favorite.assert_called_once_with(explicit)

    @patch.object(CustomFavoriteNameDialog, "show", return_value="My Armor Blue")
    def test_universal_button_adds_and_removes_true_custom_color(self, show_name):
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=())
        dialog.favorite_library = FavoriteColorLibrary(dialog.paint_catalog)
        dialog.current_color = "#395C71"
        dialog.selected_paint_id = None
        dialog.settings = Mock()
        dialog.favorite_button = FakeWidget()
        dialog._refresh_palette_data_source = Mock()

        self.assertEqual(dialog.current_favorite_action_label(), "★ Add Favorite")
        self.assertTrue(dialog.toggle_current_favorite())
        added = dialog.favorite_library.custom_for_color("#395C71")
        self.assertIsNotNone(added)
        self.assertEqual(added.name, "My Armor Blue")
        show_name.assert_called_once_with(dialog, "#395C71")
        self.assertEqual(dialog.favorite_button.options["text"], "★ Remove Favorite")

        self.assertTrue(dialog.toggle_current_favorite())

        self.assertIsNone(dialog.favorite_library.custom_for_color("#395C71"))
        self.assertEqual(dialog.favorite_button.options["text"], "★ Add Favorite")
        self.assertEqual(dialog.settings.set_favorite_colors.call_count, 2)
        self.assertEqual(dialog._refresh_palette_data_source.call_count, 2)

    @patch.object(CustomFavoriteNameDialog, "show", return_value="   ")
    def test_blank_custom_favorite_name_falls_back_to_normalized_hex(self, _show):
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=())
        dialog.favorite_library = FavoriteColorLibrary(dialog.paint_catalog)
        dialog.current_color = "#395c71"
        dialog.selected_paint_id = None
        dialog.settings = Mock()
        dialog._refresh_palette_data_source = Mock()

        self.assertTrue(dialog.toggle_current_favorite())

        favorite = dialog.favorite_library.custom_for_color("#395C71")
        self.assertEqual(favorite.name, "#395C71")
        self.assertEqual(dialog.current_color, "#395c71")

    @patch.object(CustomFavoriteNameDialog, "show", return_value=None)
    def test_canceling_custom_favorite_name_preserves_color_and_library(self, _show):
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=())
        dialog.favorite_library = FavoriteColorLibrary(dialog.paint_catalog)
        dialog.current_color = "#395C71"
        dialog.selected_paint_id = None
        dialog.settings = Mock()
        dialog._refresh_palette_data_source = Mock()

        self.assertFalse(dialog.toggle_current_favorite())

        self.assertEqual(dialog.current_color, "#395C71")
        self.assertEqual(dialog.favorite_library.favorites, ())
        dialog.settings.set_favorite_colors.assert_not_called()
        dialog._refresh_palette_data_source.assert_not_called()

    def test_custom_favorite_name_dialog_save_trims_and_cancel_is_distinct(self):
        dialog = object.__new__(CustomFavoriteNameDialog)
        dialog.name_entry = FakeWidget()
        dialog.name_entry.value = "  My Armor Blue  "
        dialog.destroy = Mock()

        dialog.save()

        self.assertEqual(dialog.result, "My Armor Blue")
        dialog.cancel()
        self.assertIsNone(dialog.result)
        self.assertEqual(dialog.destroy.call_count, 2)

    def test_manual_color_change_refreshes_universal_favorite_action(self):
        favorite = CustomFavoriteColor("custom-1", "Custom", "#395C71")
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=())
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog,
            (favorite,),
        )
        dialog.current_color = "#395C71"
        dialog.selected_paint_id = None
        dialog.favorite_button = FakeWidget()
        dialog._updating_color_representations = False
        dialog._refresh_rgb_controls = Mock()
        dialog._refresh_color_model_controls = Mock()
        dialog._refresh_hex_control = Mock()
        dialog._refresh_visual_picker = Mock()
        dialog._refresh_current_color_preview = Mock()

        dialog._refresh_favorite_button()
        self.assertEqual(dialog.favorite_button.options["text"], "★ Remove Favorite")
        dialog.set_current_color("#395C72")

        self.assertEqual(dialog.favorite_button.options["text"], "★ Add Favorite")

    def test_custom_favorite_tile_has_no_citadel_context_action(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=())
        custom = CustomFavoriteColor("custom-1", "Custom", "#010203")
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog,
            (custom,),
        )
        custom_tile = dialog.favorite_library.palette_colors()[0]

        self.assertIsNone(dialog._citadel_favorite_action_label(custom_tile))
        self.assertFalse(dialog.toggle_citadel_favorite(custom_tile))

    @patch.object(CustomFavoriteNameDialog, "show", return_value="  Renamed  ")
    def test_custom_favorite_rename_preserves_identity_rgb_and_refreshes(self, show):
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=())
        favorite = CustomFavoriteColor("custom-1", "Original", "#010203")
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog,
            (favorite,),
        )
        tile = dialog.favorite_library.palette_colors()[0]
        dialog.settings = Mock()
        dialog._refresh_palette_data_source = Mock()

        self.assertTrue(dialog.rename_custom_favorite(tile))

        renamed = dialog.favorite_library.custom_for_color("#010203")
        self.assertEqual(
            renamed,
            CustomFavoriteColor("custom-1", "Renamed", "#010203"),
        )
        show.assert_called_once_with(
            dialog,
            "#010203",
            "Original",
            "Rename Favorite",
        )
        dialog.settings.set_favorite_colors.assert_called_once_with((renamed,))
        dialog._refresh_palette_data_source.assert_called_once_with()

    @patch.object(CustomFavoriteNameDialog, "show", return_value=" ")
    def test_blank_custom_rename_uses_hex_fallback(self, _show):
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=())
        favorite = CustomFavoriteColor("custom-1", "Original", "#010203")
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog,
            (favorite,),
        )
        tile = dialog.favorite_library.palette_colors()[0]
        dialog.settings = Mock()
        dialog._refresh_palette_data_source = Mock()

        self.assertTrue(dialog.rename_custom_favorite(tile))

        self.assertEqual(
            dialog.favorite_library.custom_for_color("#010203").name,
            "#010203",
        )

    def test_custom_favorite_remove_leaves_current_color_untouched(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=())
        favorite = CustomFavoriteColor("custom-1", "Original", "#010203")
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog,
            (favorite,),
        )
        tile = dialog.favorite_library.palette_colors()[0]
        dialog.current_color = "#010203"
        dialog.selected_paint_id = tile.id
        dialog.settings = Mock()
        dialog._refresh_palette_data_source = Mock()
        dialog._refresh_favorite_button = Mock()

        self.assertTrue(dialog.remove_custom_favorite(tile))

        self.assertEqual(dialog.current_color, "#010203")
        self.assertEqual(dialog.favorite_library.favorites, ())
        dialog.settings.set_favorite_colors.assert_called_once_with(())
        dialog._refresh_palette_data_source.assert_called_once_with()

    @patch("src.widget.tk.Menu")
    def test_custom_tile_context_menu_has_only_rename_and_remove(self, menu):
        catalog = PaintCatalog(paints=())
        library = FavoriteColorLibrary(
            catalog,
            (CustomFavoriteColor("custom-1", "Custom", "#010203"),),
        )
        tile = library.palette_colors()[0]
        grid = object.__new__(PaintSwatchGrid)
        grid._paint_at = Mock(return_value=tile)
        grid._on_custom_favorite_renamed = Mock()
        grid._on_custom_favorite_removed = Mock()
        grid._favorite_action_label = Mock()
        grid._on_favorite_toggled = Mock()
        event = SimpleNamespace(x=1, y=2, x_root=101, y_root=102)

        grid._on_canvas_context_menu(event)

        commands = menu.return_value.add_command.call_args_list
        self.assertEqual(
            [command.kwargs["label"] for command in commands],
            ["Rename Favorite...", "Remove from Favorites"],
        )
        commands[0].kwargs["command"]()
        commands[1].kwargs["command"]()
        grid._on_custom_favorite_renamed.assert_called_once_with(tile)
        grid._on_custom_favorite_removed.assert_called_once_with(tile)
        grid._favorite_action_label.assert_not_called()

    def test_favorite_status_covers_catalog_and_unified_custom_tiles(self):
        red = PaintColor("red", "Red", 255, 0, 0)
        blue = PaintColor("blue", "Blue", 0, 0, 255)
        custom = CustomFavoriteColor("custom-1", "Custom", "#010203")
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=(red, blue))
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog,
            (CitadelFavoriteColor("red"), custom),
        )
        custom_tile = next(
            color
            for color in dialog.favorite_library.palette_colors()
            if color.id == "custom:custom-1"
        )

        self.assertTrue(dialog._is_palette_color_favorite(red))
        self.assertFalse(dialog._is_palette_color_favorite(blue))
        self.assertTrue(dialog._is_palette_color_favorite(custom_tile))

    def test_grid_draws_gold_star_only_for_favorite_without_resizing_tiles(self):
        favorite = PaintColor("favorite", "Favorite", 255, 0, 0)
        ordinary = PaintColor("ordinary", "Ordinary", 0, 0, 255)
        grid = object.__new__(PaintSwatchGrid)
        grid._relayout_after_id = "pending"
        grid._configured_column_count = 2
        grid._column_count = 2
        grid.paints = (favorite, ordinary)
        grid.selected_paint_id = None
        grid._is_paint_favorite = lambda paint: paint.id == "favorite"
        grid.canvas = Mock()
        grid.canvas.winfo_width.return_value = 192
        grid._paint_name_font = Mock()
        grid._paint_name_font.metrics.return_value = 16
        grid._paint_name_font.measure.side_effect = lambda text: len(text) * 6

        grid._relayout()

        star_calls = [
            call
            for call in grid.canvas.create_text.call_args_list
            if call.kwargs.get("text") == "★"
        ]
        self.assertEqual(len(star_calls), 1)
        self.assertEqual(star_calls[0].kwargs["fill"], FAVORITE_STAR_COLOR)
        self.assertEqual(star_calls[0].kwargs["anchor"], "ne")
        grid.canvas.configure.assert_called_once_with(
            scrollregion=(0, 0, 192, PAINT_SWATCH_PREVIEW_SIZE + 48)
        )

    def test_selected_favorite_keeps_gold_star_independent_of_selection_outline(self):
        favorite = PaintColor("favorite", "Favorite", 255, 0, 0)
        grid = object.__new__(PaintSwatchGrid)
        grid._relayout_after_id = "pending"
        grid._configured_column_count = 1
        grid._column_count = 1
        grid.paints = (favorite,)
        grid.selected_paint_id = favorite.id
        grid._is_paint_favorite = lambda paint: paint.id == favorite.id
        grid.canvas = Mock()
        grid.canvas.winfo_width.return_value = 96
        grid._paint_name_font = Mock()
        grid._paint_name_font.metrics.return_value = 16
        grid._paint_name_font.measure.side_effect = lambda text: len(text) * 6

        grid._relayout()

        selected_tile = grid.canvas.create_rectangle.call_args
        self.assertEqual(selected_tile.kwargs["outline"], PAINT_SWATCH_SELECTED_OUTLINE)
        self.assertEqual(selected_tile.kwargs["width"], 3)
        star = next(
            call
            for call in grid.canvas.create_text.call_args_list
            if call.kwargs.get("text") == "★"
        )
        self.assertEqual(star.kwargs["fill"], FAVORITE_STAR_COLOR)
        self.assertNotEqual(star.kwargs["fill"], APP_SELECTION_FOREGROUND)

    def test_normal_paint_selection_does_not_change_favorite_membership(self):
        favorite = PaintColor("favorite", "Favorite", 255, 0, 0)
        ordinary = PaintColor("ordinary", "Ordinary", 0, 0, 255)
        dialog = object.__new__(ColorPickerDialog)
        dialog.favorite_library = FavoriteColorLibrary(
            PaintCatalog((favorite, ordinary)),
            (CitadelFavoriteColor(favorite.id),),
        )
        dialog.current_color = "#000000"
        dialog.current_color_preview = FakeWidget()
        dialog.palette_grid = FakePaletteGrid()
        favorites_before = dialog.favorite_library.favorites

        dialog.select_paint(favorite)
        dialog.select_paint(ordinary)

        self.assertEqual(dialog.favorite_library.favorites, favorites_before)
        self.assertTrue(dialog.favorite_library.has_citadel(favorite.id))
        self.assertFalse(dialog.favorite_library.has_citadel(ordinary.id))

    def test_tile_favorite_check_delegates_to_indexed_library_membership(self):
        paint = PaintColor("paint-id", "Paint", 1, 2, 3)
        dialog = object.__new__(ColorPickerDialog)
        dialog.favorite_library = Mock()
        dialog.favorite_library.has_citadel.return_value = True

        self.assertTrue(dialog._is_palette_color_favorite(paint))
        dialog.favorite_library.has_citadel.assert_called_once_with("paint-id")

    @patch("src.widget.tk.Menu")
    def test_right_click_targets_exact_hit_tile_without_left_click_selection(self, menu):
        red = PaintColor("red", "Red", 255, 0, 0)
        blue = PaintColor("blue", "Blue", 0, 0, 255)
        grid = object.__new__(PaintSwatchGrid)
        grid._paint_at = Mock(return_value=blue)
        grid._favorite_action_label = Mock(return_value="Add to Favorites")
        grid._on_favorite_toggled = Mock()
        grid._on_paint_selected = Mock()
        event = SimpleNamespace(x=12, y=34, x_root=112, y_root=134)

        grid._on_canvas_context_menu(event)

        grid._paint_at.assert_called_once_with(12, 34)
        grid._favorite_action_label.assert_called_once_with(blue)
        command = menu.return_value.add_command.call_args.kwargs["command"]
        command()
        grid._on_favorite_toggled.assert_called_once_with(blue)
        grid._on_paint_selected.assert_not_called()
        menu.return_value.tk_popup.assert_called_once_with(112, 134)
        menu.return_value.grab_release.assert_called_once_with()

    def test_all_colors_is_default_and_selection_updates_button_state(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(
            paints=(
                PaintColor("red", "Red", 255, 0, 0),
                PaintColor("blue", "Blue", 0, 0, 255),
            )
        )
        dialog.search_query = ""
        dialog._refresh_palette_display = Mock()
        dialog.group_buttons = {
            color_group: FakeGroupButton()
            for color_group, _ in COLOR_PICKER_GROUP_ENTRIES
        }
        dialog.group_button_labels = dict(COLOR_PICKER_GROUP_ENTRIES)

        dialog.select_color_group(None)

        self.assertIsNone(dialog.selected_color_group)
        self.assertEqual(dialog.group_buttons[None].states, ["selected"])
        self.assertTrue(dialog.group_buttons[None].text.startswith("▸"))

        dialog.select_color_group(ColorGroup.BLUE)

        self.assertIs(dialog.selected_color_group, ColorGroup.BLUE)
        self.assertEqual(dialog.group_buttons[None].states, ["!selected"])
        self.assertEqual(dialog.group_buttons[ColorGroup.BLUE].states, ["selected"])

    def test_group_filtering_reuses_catalog_and_visual_analysis_apis(self):
        catalog_paints = (
            PaintColor("blue", "Blue", 0, 0, 255),
            PaintColor("dark-red", "Dark Red", 150, 10, 10),
            PaintColor("orange", "Orange", 255, 128, 0),
            PaintColor("bright-red", "Bright Red", 255, 0, 0),
            PaintColor("grey", "Grey", 128, 128, 128),
        )
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(paints=catalog_paints)
        dialog.search_query = ""
        dialog.group_buttons = {
            color_group: FakeGroupButton()
            for color_group, _ in COLOR_PICKER_GROUP_ENTRIES
        }
        dialog.group_button_labels = dict(COLOR_PICKER_GROUP_ENTRIES)
        dialog._refresh_palette_display = Mock()

        dialog.select_color_group(None)

        expected_all = sort_paints_visually(catalog_paints)
        self.assertEqual(dialog.palette_paints, expected_all)
        self.assertEqual(len(dialog.palette_paints), len(catalog_paints))

        dialog.select_color_group(ColorGroup.RED)

        expected_reds = sort_paints_visually(
            get_paints_for_group(catalog_paints, ColorGroup.RED)
        )
        self.assertEqual(dialog.palette_paints, expected_reds)
        self.assertLess(len(dialog.palette_paints), len(catalog_paints))
        self.assertEqual(dialog.palette_paints, sort_paints_visually(expected_reds))

        dialog.select_color_group(None)

        self.assertEqual(dialog.palette_paints, expected_all)
        self.assertEqual(dialog.paint_catalog.paints, catalog_paints)
        self.assertEqual(dialog._refresh_palette_display.call_count, 3)

    @patch("src.widget.ttk.Button", side_effect=FakeWidget)
    @patch("src.widget.tk.Canvas", side_effect=FakeWidget)
    @patch("src.widget.RecentColorSwatchRow", side_effect=FakeWidget)
    @patch("src.widget.ttk.Frame", side_effect=FakeWidget)
    @patch("src.widget.ttk.Entry", side_effect=FakeWidget)
    @patch("src.widget.ttk.Spinbox", side_effect=FakeWidget)
    @patch("src.widget.ttk.Combobox", side_effect=FakeWidget)
    @patch("src.widget.ttk.Label", side_effect=FakeWidget)
    def test_color_editor_controls_share_mode_and_color_state(
        self,
        _label_type,
        _combobox_type,
        _spinbox_type,
        _entry_type,
        _frame_type,
        _recent_color_row_type,
        _canvas_type,
        _button_type,
    ):
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#abcdef"
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog.recent_colors = ((150, 12, 9),)
        dialog.paint_catalog = PaintCatalog(paints=())
        dialog.favorite_library = FavoriteColorLibrary(dialog.paint_catalog)
        dialog.selected_paint_id = None
        dialog.register = Mock(return_value="rgb-validation-command")
        for attribute in (
            "editor_color_space_area",
            "editor_visualization_area",
            "editor_color_field_area",
            "editor_slider_area",
            "editor_rgb_area",
            "editor_alternate_color_space_area",
            "editor_color_model_controls_area",
            "editor_hex_area",
            "editor_recent_colors_area",
            "original_color_preview_area",
            "current_color_preview_area",
        ):
            setattr(dialog, attribute, FakeWidget())

        dialog._build_color_editor()

        self.assertEqual(dialog.color_space_selector.options["values"], COLOR_SPACE_MODES)
        self.assertEqual(dialog.color_space_selector.options["state"], "readonly")
        self.assertEqual(dialog.color_space_selector.get(), DEFAULT_COLOR_SPACE_MODE)
        self.assertEqual(dialog.color_space_mode, DEFAULT_COLOR_SPACE_MODE)
        self.assertEqual(
            dialog.color_model_labels["component"].options["text"], "Value:"
        )
        self.assertEqual(dialog.current_color, "#abcdef")
        self.assertEqual(dialog.original_color_preview.options["background"], "#123456")
        self.assertEqual(dialog.current_color_preview.options["background"], "#abcdef")
        self.assertEqual(
            dialog.hsv_color_field.options["height"], COLOR_FIELD_PREFERRED_HEIGHT
        )
        self.assertEqual(dialog.original_color_preview_label.options["text"], "Original")
        self.assertEqual(dialog.current_color_preview_label.options["text"], "Current")
        self.assertEqual(
            dialog.recent_color_row.options["colors"],
            ((150, 12, 9),),
        )
        self.assertIs(
            dialog.recent_color_row.options["on_color_selected"].__self__,
            dialog,
        )
        self.assertEqual(
            dialog.editor_rgb_area.grid_columns,
            {
                1: {"weight": 1, "uniform": "rgb-control"},
                3: {"weight": 1, "uniform": "rgb-control"},
                5: {"weight": 1, "uniform": "rgb-control"},
            },
        )
        for index, (channel, label) in enumerate(
            (("red", "Red:"), ("green", "Green:"), ("blue", "Blue:"))
        ):
            self.assertEqual(dialog.rgb_control_labels[channel].options["text"], label)
            self.assertEqual(
                dialog.rgb_control_labels[channel].grid_options,
                {
                    "row": 0,
                    "column": index * 2,
                    "sticky": "w",
                    "padx": (0, 4),
                },
            )
            self.assertEqual(dialog.rgb_controls[channel].options["width"], 4)
            self.assertEqual(dialog.rgb_controls[channel].options["from_"], 0)
            self.assertEqual(dialog.rgb_controls[channel].options["to"], 255)
            self.assertEqual(
                dialog.rgb_controls[channel].grid_options,
                {
                    "row": 0,
                    "column": index * 2 + 1,
                    "sticky": "w",
                    "padx": (0, 12 if index < 2 else 0),
                },
            )
        self.assertEqual(len(dialog.color_model_spacers), 2)
        for spacer in dialog.color_model_spacers:
            self.assertEqual(
                spacer.pack_options,
                {"side": "left", "fill": "x", "expand": True},
            )
        for index, (name, label, maximum) in enumerate(
            (
                ("hue", "Hue:", 359),
                ("saturation", "Saturation:", 100),
                ("component", "Value:", 100),
            )
        ):
            self.assertEqual(dialog.color_model_labels[name].options["text"], label)
            self.assertEqual(
                dialog.color_model_labels[name].pack_options,
                {"side": "left"},
            )
            self.assertEqual(
                dialog.color_model_controls[name].options["width"],
                COLOR_MODEL_CONTROL_WIDTH,
            )
            self.assertEqual(dialog.color_model_controls[name].options["to"], maximum)
            self.assertEqual(
                dialog.color_model_controls[name].pack_options,
                {"side": "left", "padx": (1, 0)},
            )
        self.assertEqual(dialog.hex_input_label.options["text"], "Hex:")
        self.assertEqual(
            dialog.hex_input_label.grid_options,
            {"row": 0, "column": 0, "sticky": "w", "padx": (0, 4)},
        )
        self.assertEqual(
            dialog.hex_input.grid_options,
            {"row": 0, "column": 1, "sticky": "w"},
        )
        self.assertEqual(dialog.favorite_button.options["text"], "★ Add Favorite")
        self.assertEqual(
            dialog.favorite_button.grid_options,
            {"row": 0, "column": 2, "sticky": "e", "padx": (8, 0)},
        )
        for preview in (dialog.original_color_preview, dialog.current_color_preview):
            self.assertEqual(preview.options["height"], 32)
            self.assertEqual(preview.pack_options, {"fill": "x"})
            self.assertEqual(preview.options["highlightbackground"], COLOR_PREVIEW_BORDER)
            self.assertEqual(preview.options["highlightcolor"], COLOR_PREVIEW_BORDER)
            self.assertEqual(preview.options["highlightthickness"], 1)

        dialog.select_color_space("HSL")
        dialog.set_current_color("#fedcba")

        self.assertEqual(dialog.color_space_mode, "HSL")
        self.assertEqual(dialog.editor_alternate_color_space_area.options["text"], "HSL")
        self.assertEqual(
            dialog.color_model_labels["component"].options["text"], "Lightness:"
        )
        self.assertTrue(
            all(
                dialog.color_model_labels[name].parent
                is dialog.editor_color_model_controls_area
                for name in ("hue", "saturation", "component")
            )
        )
        self.assertEqual(
            {
                dialog.color_model_controls[name].options["width"]
                for name in ("hue", "saturation", "component")
            },
            {COLOR_MODEL_CONTROL_WIDTH},
        )
        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(dialog.current_color, "#fedcba")
        self.assertEqual(dialog.current_color_preview.options["background"], "#fedcba")
        self.assertEqual(dialog.hex_input.get(), "#FEDCBA")

    @patch("src.widget.ttk.Button", side_effect=FakeWidget)
    @patch("src.widget.tk.Canvas", side_effect=FakeWidget)
    @patch("src.widget.RecentColorSwatchRow", side_effect=FakeWidget)
    @patch("src.widget.ttk.Frame", side_effect=FakeWidget)
    @patch("src.widget.ttk.Entry", side_effect=FakeWidget)
    @patch("src.widget.ttk.Spinbox", side_effect=FakeWidget)
    @patch("src.widget.ttk.Combobox", side_effect=FakeWidget)
    @patch("src.widget.ttk.Label", side_effect=FakeWidget)
    def test_color_editor_applies_restored_mode_during_build(
        self,
        _label_type,
        _combobox_type,
        _spinbox_type,
        _entry_type,
        _frame_type,
        _recent_color_row_type,
        _canvas_type,
        _button_type,
    ):
        initial_color = "#808080"
        for restored_mode, expected_title, expected_label in (
            ("HSL", "HSL", "Lightness:"),
            ("Color Wheel", "HSV / HSB", "Value:"),
            ("Classic", "HSV / HSB", "Value:"),
            (DEFAULT_COLOR_SPACE_MODE, "HSV / HSB", "Value:"),
        ):
            with self.subTest(restored_mode=restored_mode):
                dialog = object.__new__(ColorPickerDialog)
                dialog.original_color = initial_color
                dialog.current_color = initial_color
                dialog.color_space_mode = restored_mode
                dialog.recent_colors = ()
                dialog.paint_catalog = PaintCatalog(paints=())
                dialog.favorite_library = FavoriteColorLibrary(dialog.paint_catalog)
                dialog.selected_paint_id = None
                dialog.register = Mock(return_value="validation-command")
                for attribute in (
                    "editor_color_space_area",
                    "editor_visualization_area",
                    "editor_color_field_area",
                    "editor_slider_area",
                    "editor_rgb_area",
                    "editor_alternate_color_space_area",
                    "editor_color_model_controls_area",
                    "editor_hex_area",
                    "editor_recent_colors_area",
                    "original_color_preview_area",
                    "current_color_preview_area",
                ):
                    setattr(dialog, attribute, FakeWidget())

                dialog._build_color_editor()

                self.assertEqual(dialog.color_space_mode, restored_mode)
                self.assertEqual(dialog.color_space_selector.get(), restored_mode)
                self.assertEqual(
                    dialog.editor_alternate_color_space_area.options["text"],
                    expected_title,
                )
                self.assertEqual(
                    dialog.color_model_labels["component"].options["text"],
                    expected_label,
                )
                if restored_mode == "Color Wheel":
                    self.assertIsNotNone(dialog.color_wheel_canvas.pack_options)
                    self.assertIsNone(dialog.classic_visualization_area.pack_options)
                    self.assertIsNone(dialog.editor_color_field_area.pack_options)
                    self.assertIsNone(dialog.editor_slider_area.pack_options)
                elif restored_mode == "Classic":
                    self.assertIsNone(dialog.color_wheel_canvas.pack_options)
                    self.assertIsNotNone(dialog.classic_visualization_area.pack_options)
                    self.assertIsNone(dialog.editor_color_field_area.pack_options)
                    self.assertIsNone(dialog.editor_slider_area.pack_options)
                else:
                    self.assertIsNone(dialog.color_wheel_canvas.pack_options)
                    self.assertIsNone(dialog.classic_visualization_area.pack_options)
                    self.assertIsNotNone(dialog.editor_color_field_area.pack_options)
                    self.assertIsNotNone(dialog.editor_slider_area.pack_options)
                self.assertEqual(dialog.current_color, initial_color)
                self.assertEqual(
                    tuple(
                        dialog.color_model_controls[name].get()
                        for name in ("hue", "saturation", "component")
                    ),
                    ("0", "0", "50"),
                )

                if restored_mode == "HSL":
                    for mode, label in (
                        (DEFAULT_COLOR_SPACE_MODE, "Value:"),
                        ("HSL", "Lightness:"),
                    ):
                        dialog.select_color_space(mode)
                        self.assertEqual(
                            dialog.color_model_labels["component"].options["text"],
                            label,
                        )
                        self.assertEqual(dialog.current_color, initial_color)

    def test_valid_hex_edit_normalizes_and_refreshes_all_representations(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#123456"
        dialog._updating_color_representations = False
        dialog.hex_input = FakeWidget()
        dialog.hex_input.value = "960c09"
        refreshers = (
            "_refresh_rgb_controls",
            "_refresh_color_model_controls",
            "_refresh_hex_control",
            "_refresh_visual_picker",
            "_refresh_current_color_preview",
        )
        for refresher in refreshers:
            setattr(dialog, refresher, Mock())

        self.assertTrue(dialog._commit_hex_input())

        self.assertEqual(dialog.current_color, "#960C09")
        self.assertEqual(dialog.original_color, "#123456")
        for refresher in refreshers:
            getattr(dialog, refresher).assert_called_once_with()

    def test_invalid_or_incomplete_hex_restores_last_valid_value(self):
        for invalid in ("#12345", "#1234567", "#12GG56"):
            with self.subTest(invalid=invalid):
                dialog = object.__new__(ColorPickerDialog)
                dialog.current_color = "#123456"
                dialog.hex_input = FakeWidget()
                dialog.hex_input.value = invalid

                self.assertFalse(dialog._commit_hex_input())

                self.assertEqual(dialog.current_color, "#123456")
                self.assertEqual(dialog.hex_input.get(), "#123456")

    def test_non_hex_color_change_updates_hex_display(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.current_color = "#123456"
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog.hex_input = FakeWidget()

        dialog.set_current_color("#00ff00")

        self.assertEqual(dialog.hex_input.get(), "#00FF00")

    def test_current_preview_follows_every_input_while_original_stays_fixed(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#123456"
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog._updating_color_representations = False
        dialog._achromatic_hue = 0.0
        dialog.original_color_preview = FakeWidget(background="#123456")
        dialog.current_color_preview = FakeWidget(background="#123456")
        dialog.palette_grid = FakePaletteGrid()
        dialog.rgb_controls = {
            name: FakeWidget() for name in ("red", "green", "blue")
        }
        dialog.color_model_controls = {
            name: FakeWidget() for name in ("hue", "saturation", "component")
        }
        dialog.hex_input = FakeWidget()
        dialog._refresh_visual_picker = Mock()

        dialog.select_paint(PaintColor("red", "Red", 255, 0, 0))
        self.assertEqual(dialog.current_color_preview.options["background"], "#ff0000")

        for name, value in zip(("red", "green", "blue"), ("0", "255", "0")):
            dialog.rgb_controls[name].value = value
        dialog._on_rgb_control_changed()
        self.assertEqual(dialog.current_color_preview.options["background"], "#00ff00")

        for name, value in zip(
            ("hue", "saturation", "component"), ("240", "100", "100")
        ):
            dialog.color_model_controls[name].value = value
        dialog._on_color_model_control_changed()
        self.assertEqual(dialog.current_color_preview.options["background"], "#0000ff")

        dialog.color_space_mode = "HSL"
        for name, value in zip(
            ("hue", "saturation", "component"), ("60", "100", "50")
        ):
            dialog.color_model_controls[name].value = value
        dialog._on_color_model_control_changed()
        self.assertEqual(dialog.current_color_preview.options["background"], "#ffff00")

        dialog.hex_input.value = "#FFFFFF"
        dialog._commit_hex_input()
        self.assertEqual(dialog.current_color_preview.options["background"], "#FFFFFF")

        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog.hsv_color_field = Mock()
        dialog.hsv_color_field.winfo_width.return_value = 101
        dialog.hsv_color_field.winfo_height.return_value = 101
        dialog._on_color_field_input(SimpleNamespace(x=100, y=100))
        self.assertEqual(dialog.current_color_preview.options["background"], "#000000")

        dialog.set_current_color("#ff0000")
        dialog.hue_slider = Mock()
        dialog.hue_slider.winfo_height.return_value = 101
        dialog._on_hue_slider_input(SimpleNamespace(y=2 / 3 * 100))
        self.assertEqual(dialog.current_color_preview.options["background"], "#0000ff")

        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(dialog.original_color_preview.options["background"], "#123456")

    def test_visual_resize_events_are_debounced(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog._visual_resize_after_id = None
        dialog.after = Mock(return_value="first")
        dialog.after_cancel = Mock()

        dialog._on_visualization_resized()
        dialog.after.return_value = "second"
        dialog._on_visualization_resized()

        dialog.after_cancel.assert_called_once_with("first")
        self.assertEqual(dialog._visual_resize_after_id, "second")

    def test_visual_indicators_move_without_recreating_canvas_items(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog._field_indicator_items = ()
        dialog._hue_indicator_items = ()
        dialog.hsv_color_field = Mock()
        dialog.hue_slider = Mock()
        dialog.hsv_color_field.winfo_width.return_value = 101
        dialog.hsv_color_field.winfo_height.return_value = 101
        dialog.hue_slider.winfo_width.return_value = 28
        dialog.hue_slider.winfo_height.return_value = 101
        dialog.hsv_color_field.create_oval.side_effect = (1, 2)
        dialog.hue_slider.create_line.side_effect = (3, 4)

        dialog._draw_hsv_indicators(0.0, 0.0, 1.0)
        dialog._draw_hsv_indicators(0.5, 1.0, 0.0)

        self.assertEqual(dialog.hsv_color_field.create_oval.call_count, 2)
        self.assertEqual(dialog.hue_slider.create_line.call_count, 2)
        self.assertEqual(dialog.hsv_color_field.coords.call_count, 4)
        self.assertEqual(dialog.hue_slider.coords.call_count, 4)
        self.assertEqual(
            [call.kwargs["width"] for call in dialog.hue_slider.create_line.call_args_list],
            [4, 2],
        )
        for call in dialog.hue_slider.coords.call_args_list:
            self.assertEqual(call.args[2], call.args[4])

    def test_unchanged_gradient_inputs_reuse_cached_images(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.hsv_color_field = Mock()
        dialog.hue_slider = Mock()
        dialog.hsv_color_field.winfo_width.return_value = 101
        dialog.hsv_color_field.winfo_height.return_value = 101
        dialog.hue_slider.winfo_width.return_value = 28
        dialog.hue_slider.winfo_height.return_value = 101
        dialog._hsv_field_cache = (101, 101, 0.5)
        dialog._hsl_field_cache = (101, 101, 0.5)
        dialog._hue_slider_cache = (28, 101)
        dialog._displayed_field_mode = DEFAULT_COLOR_SPACE_MODE

        dialog._render_hsv_field(0.5001)
        dialog._displayed_field_mode = "HSL"
        dialog._render_hsl_field(0.5001)
        dialog._render_hue_slider()

        dialog.hsv_color_field.delete.assert_not_called()
        dialog.hue_slider.delete.assert_not_called()

    @patch("src.widget.ImageTk.PhotoImage")
    @patch("src.widget.Image.new")
    def test_switching_mode_redraws_a_cached_field(self, image_new, _photo_image):
        dialog = object.__new__(ColorPickerDialog)
        dialog.hsv_color_field = Mock()
        dialog.hsv_color_field.winfo_width.return_value = 2
        dialog.hsv_color_field.winfo_height.return_value = 2
        dialog._hsv_field_cache = (2, 2, 0.5)
        dialog._displayed_field_mode = "HSL"

        dialog._render_hsv_field(0.5)

        image_new.assert_called_once_with("RGB", (2, 2))
        dialog.hsv_color_field.delete.assert_called_once_with("gradient")
        self.assertEqual(dialog._displayed_field_mode, DEFAULT_COLOR_SPACE_MODE)

    @patch("src.widget.ImageTk.PhotoImage", side_effect=lambda image: image)
    def test_color_wheel_renders_clockwise_ring_and_hsv_inner_square(
        self, photo_image_type
    ):
        dialog = object.__new__(ColorPickerDialog)
        dialog.color_wheel_canvas = Mock()
        dialog.color_wheel_canvas.winfo_width.return_value = 101
        dialog.color_wheel_canvas.winfo_height.return_value = 101
        dialog._color_wheel_cache = None

        dialog._render_color_wheel(0.0)
        rendered = photo_image_type.call_args.args[0]

        top = rendered.getpixel((50, 5))
        right = rendered.getpixel((95, 50))
        inner_top_left = rendered.getpixel((27, 27))
        inner_top_right = rendered.getpixel((73, 27))
        inner_bottom = rendered.getpixel((50, 73))
        self.assertGreater(top[0], 240)
        self.assertLess(max(top[1], top[2]), 40)
        self.assertGreater(right[1], right[0])
        self.assertGreater(inner_top_left[0], 200)
        self.assertLess(inner_top_right[1], inner_top_left[1])
        self.assertLess(max(inner_bottom[:3]), 40)

        geometry = color_wheel_geometry(101, 101)
        ring_width = geometry.outer_radius - geometry.ring_inner_radius
        for radius_fraction in (0.25, 0.5, 0.75):
            sample_radius = geometry.ring_inner_radius + ring_width * radius_fraction
            for degrees in range(360):
                angle = degrees / 360.0 * 2.0 * math.pi
                x = round(geometry.center_x + math.sin(angle) * sample_radius)
                y = round(geometry.center_y - math.cos(angle) * sample_radius)
                self.assertGreater(
                    rendered.getpixel((x, y))[3],
                    240,
                    f"transparent seam at {degrees} degrees",
                )

        before_wrap = rendered.getpixel((50, 5))
        after_wrap = rendered.getpixel((49, 5))
        self.assertLess(
            max(abs(first - second) for first, second in zip(before_wrap, after_wrap)),
            20,
        )

        dialog._render_color_wheel(0.0)
        photo_image_type.assert_called_once()
        ring_image = dialog._color_wheel_ring_cache[2]
        dialog._render_color_wheel(0.25)
        self.assertIs(dialog._color_wheel_ring_cache[2], ring_image)
        self.assertEqual(photo_image_type.call_count, 2)

    def test_color_wheel_ring_and_clamped_sv_drag_update_canonical_color(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.current_color = "#df9f9f"
        dialog._achromatic_hue = 0.0
        dialog._color_wheel_drag_target = None
        dialog.color_wheel_canvas = Mock()
        dialog.color_wheel_canvas.winfo_width.return_value = 301
        dialog.color_wheel_canvas.winfo_height.return_value = 301
        dialog.set_current_color = Mock()
        geometry = color_wheel_geometry(301, 301)
        _, saturation, value = rgb_hex_to_hsv(dialog.current_color)

        dialog._on_color_wheel_press(
            SimpleNamespace(x=geometry.center_x + 130, y=geometry.center_y)
        )
        dialog.set_current_color.assert_called_once_with(
            hsv_to_rgb_hex(0.25, saturation, value)
        )

        dialog.set_current_color.reset_mock()
        dialog._color_wheel_drag_target = "sv"
        dialog._on_color_wheel_drag(SimpleNamespace(x=1000, y=1000))
        dialog.set_current_color.assert_called_once_with("#000000")
        dialog._on_color_wheel_release()
        self.assertIsNone(dialog._color_wheel_drag_target)

    def test_color_wheel_indicators_move_without_recreating_items(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.color_wheel_canvas = Mock()
        dialog.color_wheel_canvas.winfo_width.return_value = 301
        dialog.color_wheel_canvas.winfo_height.return_value = 301
        dialog.color_wheel_canvas.create_oval.side_effect = (1, 2, 3, 4)
        dialog._color_wheel_hue_indicator_items = ()
        dialog._color_wheel_sv_indicator_items = ()

        dialog._draw_color_wheel_indicators(0.0, 0.0, 1.0)
        dialog._draw_color_wheel_indicators(0.5, 1.0, 0.0)

        self.assertEqual(dialog.color_wheel_canvas.create_oval.call_count, 4)
        self.assertEqual(dialog.color_wheel_canvas.coords.call_count, 8)

    @patch("src.widget.ImageTk.PhotoImage", side_effect=lambda image: image)
    def test_classic_renders_hue_saturation_field_and_contextual_value_slider(
        self, photo_image_type
    ):
        dialog = object.__new__(ColorPickerDialog)
        dialog.classic_color_field = Mock()
        dialog.classic_value_slider = Mock()
        dialog.classic_color_field.winfo_width.return_value = 101
        dialog.classic_color_field.winfo_height.return_value = 101
        dialog.classic_value_slider.winfo_width.return_value = 12
        dialog.classic_value_slider.winfo_height.return_value = 101
        dialog._classic_field_cache = None
        dialog._classic_field_base_cache = None
        dialog._classic_value_slider_cache = None

        dialog._render_classic_field(0.5)
        field_image = photo_image_type.call_args.args[0]
        dialog._render_classic_value_slider(0.0, 1.0)
        slider_image = photo_image_type.call_args.args[0]

        self.assertEqual(field_image.getpixel((0, 0)), (128, 0, 0))
        self.assertGreater(field_image.getpixel((33, 0))[1], 120)
        self.assertEqual(field_image.getpixel((50, 100)), (128, 128, 128))
        self.assertEqual(slider_image.getpixel((6, 0)), (255, 0, 0))
        self.assertEqual(slider_image.getpixel((6, 100)), (0, 0, 0))

        dialog._render_classic_field(0.5)
        dialog._render_classic_value_slider(0.0, 1.0)
        self.assertEqual(photo_image_type.call_count, 2)
        base_image = dialog._classic_field_base_cache[2]
        dialog._render_classic_field(0.75)
        self.assertIs(dialog._classic_field_base_cache[2], base_image)
        self.assertEqual(photo_image_type.call_count, 3)

    def test_classic_field_and_value_interactions_update_canonical_color(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.current_color = "#ff0000"
        dialog._achromatic_hue = 0.0
        dialog.classic_color_field = Mock()
        dialog.classic_value_slider = Mock()
        dialog.classic_color_field.winfo_width.return_value = 101
        dialog.classic_color_field.winfo_height.return_value = 101
        dialog.classic_value_slider.winfo_height.return_value = 101
        dialog.set_current_color = Mock()

        dialog._on_classic_field_input(SimpleNamespace(x=2 / 3 * 101, y=-50))
        dialog.set_current_color.assert_called_once_with("#0000ff")

        dialog.set_current_color.reset_mock()
        dialog._on_classic_value_slider_input(SimpleNamespace(y=500))
        dialog.set_current_color.assert_called_once_with("#000000")

    def test_programmatic_color_change_moves_classic_markers_without_changing_original(
        self,
    ):
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#ff0000"
        dialog.color_space_mode = "Classic"
        dialog._updating_color_representations = False
        dialog._achromatic_hue = 0.0
        dialog.classic_color_field = Mock()
        dialog.classic_value_slider = Mock()
        dialog.classic_color_field.winfo_width.return_value = 101
        dialog.classic_color_field.winfo_height.return_value = 101
        dialog.classic_value_slider.winfo_width.return_value = 28
        dialog.classic_value_slider.winfo_height.return_value = 101
        dialog.classic_color_field.create_oval.side_effect = (1, 2)
        dialog.classic_value_slider.create_line.side_effect = (3, 4)
        dialog._classic_field_indicator_items = ()
        dialog._classic_value_indicator_items = ()
        dialog._render_classic_field = Mock()
        dialog._render_classic_value_slider = Mock()

        dialog.set_current_color("#00ff00")
        dialog.set_current_color("#000080")

        self.assertEqual(dialog.current_color, "#000080")
        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(dialog.classic_color_field.create_oval.call_count, 2)
        self.assertEqual(dialog.classic_value_slider.create_line.call_count, 2)
        self.assertEqual(dialog.classic_color_field.coords.call_count, 4)
        self.assertEqual(dialog.classic_value_slider.coords.call_count, 4)

    def test_rgb_validation_accepts_only_blank_or_values_from_zero_to_255(self):
        for accepted in ("", "0", "1", "127", "255"):
            with self.subTest(accepted=accepted):
                self.assertTrue(ColorPickerDialog._validate_rgb_input(accepted))
        for rejected in ("-1", "256", "1.5", "red", " 1"):
            with self.subTest(rejected=rejected):
                self.assertFalse(ColorPickerDialog._validate_rgb_input(rejected))

    def test_numeric_return_handlers_commit_without_accepting_dialog(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog._on_rgb_control_changed = Mock()
        dialog._on_color_model_control_changed = Mock()
        event = object()

        self.assertEqual(dialog._on_rgb_control_return(event), "break")
        self.assertEqual(dialog._on_color_model_control_return(event), "break")

        dialog._on_rgb_control_changed.assert_called_once_with(event)
        dialog._on_color_model_control_changed.assert_called_once_with(event)

    def test_synchronized_text_preserves_focused_caret_and_selection(self):
        control = FocusedFakeWidget("123", insert_index=2, selection=(1, 3))

        ColorPickerDialog._replace_control_text(control, "9876")

        self.assertEqual(control.get(), "9876")
        self.assertEqual(control.insert_index, 2)
        self.assertEqual(control.selection, (1, 3))

    def test_palette_keyboard_scrolling_consumes_navigation_key(self):
        grid = object.__new__(PaintSwatchGrid)
        grid.canvas = Mock()

        result = grid._on_scroll_key(1, "pages")

        self.assertEqual(result, "break")
        grid.canvas.yview_scroll.assert_called_once_with(1, "pages")

    @patch("src.widget.ttk.Button", side_effect=FakeWidget)
    @patch("src.widget.ttk.Frame", side_effect=FakeWidget)
    def test_dialog_actions_are_named_focusable_controls(self, _frame, _button):
        dialog = object.__new__(ColorPickerDialog)

        dialog._build_actions()

        self.assertEqual(dialog.ok_button.options["text"], "OK")
        self.assertEqual(dialog.cancel_button.options["text"], "Cancel")
        self.assertIs(dialog.ok_button.options["command"].__self__, dialog)
        self.assertIs(dialog.cancel_button.options["command"].__self__, dialog)
        self.assertEqual(
            dialog.ok_button.parent.packed_children,
            [dialog.cancel_button, dialog.ok_button],
        )
        self.assertEqual(dialog.cancel_button.pack_options, {"side": "right"})
        self.assertEqual(
            dialog.ok_button.pack_options,
            {"side": "right", "padx": (0, COLOR_EDITOR_SECTION_GAP)},
        )

    def test_rgb_channel_boundaries_update_canonical_color(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#123456"
        dialog._updating_color_representations = False
        dialog.rgb_controls = {
            channel: FakeWidget() for channel in ("red", "green", "blue")
        }
        for channel, value in zip(("red", "green", "blue"), ("0", "255", "0")):
            dialog.rgb_controls[channel].value = value
        dialog._refresh_color_representations = Mock()

        dialog._on_rgb_control_changed()

        self.assertEqual(dialog.current_color, "#00ff00")
        self.assertEqual(dialog.original_color, "#123456")
        dialog._refresh_color_representations.assert_called_once_with()

    def test_rgb_edit_refreshes_all_dependent_representations(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#123456"
        dialog._updating_color_representations = False
        dialog.rgb_controls = {
            channel: FakeWidget() for channel in ("red", "green", "blue")
        }
        for channel, value in zip(("red", "green", "blue"), ("18", "52", "87")):
            dialog.rgb_controls[channel].value = value
        for refresher in (
            "_refresh_rgb_controls",
            "_refresh_color_model_controls",
            "_refresh_hex_control",
            "_refresh_visual_picker",
            "_refresh_current_color_preview",
        ):
            setattr(dialog, refresher, Mock())

        dialog._on_rgb_control_changed()

        self.assertEqual(dialog.current_color, "#123457")
        self.assertEqual(dialog.original_color, "#123456")
        for refresher in (
            "_refresh_rgb_controls",
            "_refresh_color_model_controls",
            "_refresh_hex_control",
            "_refresh_visual_picker",
            "_refresh_current_color_preview",
        ):
            getattr(dialog, refresher).assert_called_once_with()

    def test_swatch_column_count_adapts_without_horizontal_scrolling(self):
        self.assertEqual(calculate_paint_swatch_columns(80), 1)
        self.assertEqual(calculate_paint_swatch_columns(192), 2)
        self.assertEqual(calculate_paint_swatch_columns(480), 5)
        self.assertGreater(
            calculate_paint_swatch_columns(960),
            calculate_paint_swatch_columns(480),
        )

    def test_swatch_cells_use_integer_edges_around_column_transition(self):
        for width in (479, 480, 575, 576, 577):
            column_count = calculate_paint_swatch_columns(width)
            bounds = [
                calculate_paint_swatch_cell_bounds(width, column_count, column)
                for column in range(column_count)
            ]

            self.assertEqual(bounds[0][0], 0)
            self.assertEqual(bounds[-1][1], width)
            self.assertTrue(
                all(left[1] == right[0] for left, right in zip(bounds, bounds[1:]))
            )
            self.assertTrue(
                all(isinstance(edge, int) for bound in bounds for edge in bound)
            )

    def test_swatch_preview_edges_are_integer_aligned_at_fractional_cell_width(self):
        grid = object.__new__(PaintSwatchGrid)
        grid._relayout_after_id = "pending"
        grid._configured_column_count = 0
        grid._column_count = 5
        grid.paints = tuple(
            PaintColor(str(index), str(index), index, index, index)
            for index in range(5)
        )
        grid.selected_paint_id = None
        grid.canvas = Mock()
        grid.canvas.winfo_width.return_value = 577
        grid._paint_name_font = Mock()
        grid._paint_name_font.metrics.return_value = 16
        grid._paint_name_font.measure.side_effect = lambda text: len(text) * 6

        grid._relayout()

        for call in grid.canvas.create_polygon.call_args_list:
            coordinates = call.args
            self.assertTrue(
                all(isinstance(coordinate, int) for coordinate in coordinates)
            )

    def test_swatch_presentation_preserves_full_name_and_exact_rgb(self):
        paint = PaintColor(
            "long-name",
            "A Complete Citadel Paint Name That Must Wrap",
            1,
            128,
            255,
        )

        presentation = paint_swatch_presentation(paint)

        self.assertEqual(presentation.name, paint.name)
        self.assertNotIn("...", presentation.name)
        self.assertEqual(presentation.color, "#0180ff")

    def test_swatch_grid_retains_every_item_and_skips_identical_rebuild(self):
        paints = (
            PaintColor("red", "Red", 255, 0, 0),
            PaintColor("white", "White", 255, 255, 255),
        )
        grid = object.__new__(PaintSwatchGrid)
        grid.paints = ()
        grid._rebuild_items = Mock()

        grid.set_paints(paints)

        self.assertEqual(grid.paints, paints)
        grid._rebuild_items.assert_called_once_with()

        grid.set_paints(paints)

        grid._rebuild_items.assert_called_once_with()

    def test_empty_grid_message_changes_only_for_favorites_context(self):
        grid = object.__new__(PaintSwatchGrid)
        grid.paints = ()
        grid.empty_message = NO_CITADEL_COLORS_MESSAGE
        grid._rebuild_items = Mock()

        grid.set_empty_message(NO_FAVORITE_COLORS_MESSAGE)
        grid.set_empty_message(NO_FAVORITE_COLORS_MESSAGE)

        self.assertEqual(grid.empty_message, "No favorite colors yet.")
        grid._rebuild_items.assert_called_once_with()

    def test_empty_favorites_refresh_uses_contextual_nonmodal_message(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.selected_color_group = PaletteSpecialGroup.FAVORITES
        dialog.palette_paints = ()
        dialog.palette_grid = FakePaletteGrid()
        dialog.palette_count_label = FakeWidget()
        dialog.event_generate = Mock()

        dialog._refresh_palette_display()

        self.assertEqual(
            dialog.palette_grid.empty_message,
            "No favorite colors yet.",
        )
        self.assertEqual(dialog.palette_grid.paints, ())
        dialog.event_generate.assert_called_once_with(
            "<<ColorPickerPaletteChanged>>"
        )

    def test_swatch_relayout_draws_paints_without_child_widgets(self):
        grid = object.__new__(PaintSwatchGrid)
        grid._relayout_after_id = "pending"
        grid._configured_column_count = 5
        grid._column_count = 2
        grid.paints = (
            PaintColor("red", "Red", 255, 0, 0),
            PaintColor("white", "White", 255, 255, 255),
        )
        grid.selected_paint_id = "red"
        grid.canvas = Mock()
        grid.canvas.winfo_width.return_value = 192
        grid._paint_name_font = Mock()
        grid._paint_name_font.metrics.return_value = 16
        grid._paint_name_font.measure.side_effect = lambda text: len(text) * 6

        grid._relayout()

        self.assertEqual(grid._configured_column_count, 2)
        self.assertEqual(len(grid._paint_regions), 2)
        self.assertEqual(grid.canvas.create_rectangle.call_count, 2)
        self.assertEqual(grid.canvas.create_polygon.call_count, 2)
        self.assertEqual(grid.canvas.create_text.call_count, 2)
        selected_swatch, light_swatch = grid.canvas.create_polygon.call_args_list
        self.assertEqual(selected_swatch.kwargs["fill"], "#ff0000")
        self.assertEqual(selected_swatch.kwargs["outline"], PAINT_SWATCH_SELECTED_OUTLINE)
        self.assertEqual(selected_swatch.kwargs["width"], 3)
        self.assertEqual(light_swatch.kwargs["fill"], "#ffffff")
        self.assertEqual(light_swatch.kwargs["outline"], PAINT_SWATCH_OUTLINE)
        self.assertEqual(light_swatch.kwargs["width"], 1)
        grid.canvas.configure.assert_called_once_with(
            scrollregion=(0, 0, 192, PAINT_SWATCH_PREVIEW_SIZE + 48)
        )

    def test_short_paint_name_remains_on_one_line(self):
        measure = lambda text: len(text) * 5

        self.assertEqual(
            format_paint_name_for_swatch("Mephiston", 60, measure),
            "Mephiston",
        )

    def test_paint_name_wraps_naturally_to_two_lines(self):
        measure = lambda text: len(text) * 5

        self.assertEqual(
            format_paint_name_for_swatch("Alpha Beta", 30, measure),
            "Alpha\nBeta",
        )

    def test_long_paint_name_uses_measured_second_line_ellipsis(self):
        measured = []

        def measure(text):
            measured.append(text)
            return sum(10 if character == "W" else 5 for character in text)

        display_name = format_paint_name_for_swatch(
            "Alpha Beta WWWWWWW",
            30,
            measure,
        )

        self.assertEqual(display_name, "Alpha\nBeta…")
        self.assertLessEqual(len(display_name.splitlines()), 2)
        self.assertIn("Beta W", measured)

    def test_swatch_name_formatting_preserves_full_catalog_name(self):
        paint = PaintColor(
            "long",
            "A Complete Citadel Paint Name",
            1,
            2,
            3,
        )

        display_name = format_paint_name_for_swatch(
            paint.name,
            40,
            lambda text: len(text) * 5,
        )

        self.assertTrue(display_name.endswith("…"))
        self.assertEqual(paint.name, "A Complete Citadel Paint Name")
        self.assertIn(paint.name, paint_tooltip_text(paint))

    def test_recent_color_tooltip_uses_exact_catalog_lookup(self):
        paint = PaintColor("mephiston-red", "Mephiston Red", 150, 12, 9)
        catalog = PaintCatalog(paints=(paint,))

        self.assertEqual(
            recent_color_tooltip_text((150, 12, 9), catalog),
            "Mephiston Red\n#960C09\nRGB: 150, 12, 9",
        )
        self.assertEqual(
            recent_color_tooltip_text((138, 31, 39), catalog),
            "#8A1F27\nRGB: 138, 31, 39",
        )

    def test_recent_color_click_updates_color_without_mutating_history(self):
        row = object.__new__(RecentColorSwatchRow)
        row.colors = ((150, 12, 9), (138, 31, 39))
        row._regions = [(1, 1, 25, 25), (29, 1, 53, 25)]
        row._on_color_selected = Mock()

        row._on_click(SimpleNamespace(x=40, y=12))

        row._on_color_selected.assert_called_once_with("#8a1f27")
        self.assertEqual(row.colors, ((150, 12, 9), (138, 31, 39)))

    def test_recent_color_click_synchronizes_rgb_model_hex_and_preview(self):
        for mode, converter in (
            (DEFAULT_COLOR_SPACE_MODE, rgb_hex_to_hsv),
            ("HSL", rgb_hex_to_hsl),
        ):
            with self.subTest(mode=mode):
                dialog = object.__new__(ColorPickerDialog)
                dialog.current_color = "#000000"
                dialog.color_space_mode = mode
                dialog._updating_color_representations = False
                dialog._achromatic_hue = 0.0
                dialog.rgb_controls = {
                    name: FakeWidget() for name in ("red", "green", "blue")
                }
                dialog.color_model_controls = {
                    name: FakeWidget()
                    for name in ("hue", "saturation", "component")
                }
                dialog.hex_input = FakeWidget()
                dialog.current_color_preview = FakeWidget()
                dialog._refresh_visual_picker = Mock()
                row = object.__new__(RecentColorSwatchRow)
                row.colors = ((138, 31, 39),)
                row._regions = [(1, 1, 25, 25)]
                row._on_color_selected = dialog.set_current_color

                row._on_click(SimpleNamespace(x=12, y=12))

                hue, saturation, component = converter("#8A1F27")
                self.assertEqual(dialog.current_color, "#8a1f27")
                self.assertEqual(
                    tuple(
                        dialog.rgb_controls[name].get()
                        for name in ("red", "green", "blue")
                    ),
                    ("138", "31", "39"),
                )
                self.assertEqual(
                    tuple(
                        dialog.color_model_controls[name].get()
                        for name in ("hue", "saturation", "component")
                    ),
                    (
                        str(round(hue * 360) % 360),
                        str(round(saturation * 100)),
                        str(round(component * 100)),
                    ),
                )
                self.assertEqual(dialog.hex_input.get(), "#8A1F27")
                self.assertEqual(
                    dialog.current_color_preview.options["background"],
                    "#8a1f27",
                )

    @patch("src.widget.configure_app_selection_styles")
    @patch("src.widget.tk.Canvas")
    @patch("src.widget.ttk.Label")
    @patch("src.widget.ttk.Frame.__init__", return_value=None)
    def test_recent_color_row_caps_entries_and_keeps_empty_state_compact(
        self,
        _frame_init,
        _label_type,
        canvas_type,
        _configure_selection_styles,
    ):
        colors = tuple((value, value, value) for value in range(15))

        row = RecentColorSwatchRow(
            object(),
            colors=colors,
            paint_catalog=PaintCatalog(paints=()),
            on_color_selected=Mock(),
        )

        self.assertEqual(len(row.colors), 12)
        self.assertEqual(canvas_type.call_args.kwargs["height"], 28)
        self.assertEqual(len(row._regions), 12)

        RecentColorSwatchRow(
            object(),
            colors=(),
            paint_catalog=PaintCatalog(paints=()),
            on_color_selected=Mock(),
        )

        self.assertEqual(canvas_type.call_args.kwargs["height"], 1)

    @patch("src.widget.configure_app_selection_styles")
    @patch("src.widget.tk.Canvas")
    @patch("src.widget.ttk.Label")
    @patch("src.widget.ttk.Frame.__init__", return_value=None)
    def test_recent_color_swatches_use_small_rounded_square_geometry(
        self,
        _frame_init,
        _label_type,
        canvas_type,
        _configure_selection_styles,
    ):
        RecentColorSwatchRow(
            object(),
            colors=((0, 0, 0), (255, 255, 255), (255, 0, 0)),
            paint_catalog=PaintCatalog(paints=()),
            on_color_selected=Mock(),
        )

        calls = canvas_type.return_value.create_polygon.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(
            [call.kwargs["fill"] for call in calls],
            ["#000000", "#ffffff", "#ff0000"],
        )
        first = calls[0]
        self.assertEqual(
            first.args[:4],
            (
                1 + RECENT_COLOR_SWATCH_CORNER_RADIUS,
                1,
                1 + 24 - RECENT_COLOR_SWATCH_CORNER_RADIUS,
                1,
            ),
        )
        self.assertEqual(first.kwargs["outline"], COLOR_PREVIEW_BORDER)
        self.assertEqual(first.kwargs["width"], 1)
        self.assertTrue(first.kwargs["smooth"])

    def test_rounded_swatch_uses_subtle_corner_radius(self):
        canvas = Mock()
        canvas.create_polygon.return_value = 42

        item = draw_rounded_swatch(
            canvas,
            10,
            20,
            70,
            80,
            fill="#0180ff",
            outline=PAINT_SWATCH_OUTLINE,
            width=1,
        )

        self.assertEqual(item, 42)
        call = canvas.create_polygon.call_args
        self.assertEqual(
            call.args[:4],
            (
                10 + PAINT_SWATCH_CORNER_RADIUS,
                20,
                70 - PAINT_SWATCH_CORNER_RADIUS,
                20,
            ),
        )
        self.assertEqual(call.kwargs["fill"], "#0180ff")
        self.assertTrue(call.kwargs["smooth"])

    def test_selecting_paints_updates_exact_current_color_and_identity(self):
        first = PaintColor("first", "First", 1, 128, 255)
        second = PaintColor("second", "Second", 254, 16, 0)
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#123456"
        dialog.current_color_preview = FakeWidget()
        dialog.palette_grid = FakePaletteGrid()

        dialog.select_paint(first)

        self.assertEqual(dialog.selected_paint_id, "first")
        self.assertEqual(dialog.palette_grid.selected_paint_id, "first")
        self.assertEqual(dialog.current_color, "#0180ff")
        self.assertEqual(dialog.original_color, "#123456")

        dialog.select_paint(second)

        self.assertEqual(dialog.selected_paint_id, "second")
        self.assertEqual(dialog.palette_grid.selected_paint_id, "second")
        self.assertEqual(dialog.current_color, "#fe1000")
        self.assertEqual(dialog.original_color, "#123456")

    def test_manual_edit_after_paint_selection_uses_working_color_pipeline(self):
        paint = PaintColor("first", "First", 1, 128, 255)
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#123456"
        dialog.current_color_preview = FakeWidget()
        dialog.palette_grid = FakePaletteGrid()

        dialog.select_paint(paint)
        dialog.set_current_color("#fedcba")

        self.assertEqual(dialog.selected_paint_id, "first")
        self.assertEqual(dialog.current_color, "#fedcba")
        self.assertEqual(
            dialog.current_color_preview.options["background"], "#fedcba"
        )
        self.assertEqual(dialog.original_color, "#123456")

    def test_accept_after_paint_selection_returns_subsequent_manual_edit(self):
        paint = PaintColor("first", "First", 1, 128, 255)
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#123456"
        dialog.current_color_preview = FakeWidget()
        dialog.palette_grid = FakePaletteGrid()
        dialog.destroy = Mock()
        dialog.accepted_color = None

        dialog.select_paint(paint)
        dialog.set_current_color("#fedcba")
        dialog.accept()

        self.assertEqual(dialog.get_accepted_color(), "#fedcba")
        self.assertNotEqual(dialog.get_accepted_color(), "#0180ff")
        self.assertEqual(dialog.original_color, "#123456")

    def test_filtering_out_selected_paint_preserves_color_and_identity(self):
        red = PaintColor("red", "Red", 255, 0, 0)
        blue = PaintColor("blue", "Blue", 0, 0, 255)
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#123456"
        dialog.paint_catalog = PaintCatalog(paints=(red, blue))
        dialog.search_query = ""
        dialog.palette_grid = FakePaletteGrid()
        dialog.palette_count_label = FakeWidget()
        dialog.event_generate = Mock()
        dialog.group_buttons = {
            color_group: FakeGroupButton()
            for color_group, _ in COLOR_PICKER_GROUP_ENTRIES
        }
        dialog.group_button_labels = dict(COLOR_PICKER_GROUP_ENTRIES)

        dialog.select_paint(blue)
        dialog.select_color_group(ColorGroup.RED)

        self.assertNotIn(blue, dialog.palette_grid.paints)
        self.assertEqual(dialog.selected_paint_id, "blue")
        self.assertEqual(dialog.palette_grid.selected_paint_id, "blue")
        self.assertEqual(dialog.current_color, "#0000ff")
        self.assertEqual(dialog.original_color, "#123456")

        dialog.select_color_group(None)

        self.assertIn(blue, dialog.palette_grid.paints)
        self.assertEqual(dialog.palette_grid.selected_paint_id, "blue")

    def test_grid_click_callback_and_highlight_track_selected_identity(self):
        dark = PaintColor("dark", "Dark", 0, 0, 0)
        grid = object.__new__(PaintSwatchGrid)
        grid._on_paint_selected = Mock()
        grid.selected_paint_id = None
        grid._schedule_relayout = Mock()

        grid._select_paint(dark)
        grid.set_selected_paint("dark")

        grid._on_paint_selected.assert_called_once_with(dark)
        self.assertEqual(grid.selected_paint_id, "dark")
        grid._schedule_relayout.assert_called_once_with()

    def test_canvas_hit_testing_accounts_for_vertical_scroll(self):
        paint = PaintColor("red", "Red", 255, 0, 0)
        grid = object.__new__(PaintSwatchGrid)
        grid.canvas = Mock()
        grid.canvas.canvasy.side_effect = lambda y: y + 100
        grid._paint_regions = [(paint, 0, 100, 96, 216)]
        grid._select_paint = Mock()

        grid._on_canvas_click(SimpleNamespace(x=40, y=20))

        grid._select_paint.assert_called_once_with(paint)

    def test_name_filter_is_case_insensitive_substring_and_preserves_order(self):
        paints = (
            PaintColor("other", "Other Color", 0, 0, 0),
            PaintColor("mephiston", "Mephiston Red", 150, 12, 9),
            PaintColor("green", "Warpstone Green", 0, 128, 0),
        )

        self.assertEqual(filter_paints_by_name(paints, "MEPHI"), (paints[1],))
        self.assertEqual(filter_paints_by_name(paints, "stone gre"), (paints[2],))
        self.assertEqual(filter_paints_by_name(paints, ""), paints)

    def test_live_search_combines_with_groups_and_zero_results_preserve_color(self):
        red = PaintColor("mephiston", "Mephiston Red", 200, 0, 0)
        green = PaintColor("warpstone", "Warpstone Green", 0, 200, 0)
        named_green = PaintColor("blue", "Blue Green Horror", 0, 0, 200)
        paints = (named_green, red, green)
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#abcdef"
        dialog.paint_catalog = PaintCatalog(paints=paints)
        dialog.palette_grid = FakePaletteGrid()
        dialog.palette_count_label = FakeWidget()
        dialog.event_generate = Mock()
        dialog.search_query = ""
        dialog.group_buttons = {
            color_group: FakeGroupButton()
            for color_group, _ in COLOR_PICKER_GROUP_ENTRIES
        }
        dialog.group_button_labels = dict(COLOR_PICKER_GROUP_ENTRIES)

        dialog.select_color_group(None)
        dialog.set_paint_search("GREEN")

        expected_all_search = filter_paints_by_name(
            sort_paints_visually(paints), "green"
        )
        self.assertEqual(dialog.palette_paints, expected_all_search)

        dialog.select_color_group(ColorGroup.GREEN)

        self.assertEqual(dialog.search_query, "GREEN")
        self.assertEqual(dialog.palette_paints, (green,))

        dialog.set_paint_search("")

        expected_greens = sort_paints_visually(
            get_paints_for_group(paints, ColorGroup.GREEN)
        )
        self.assertEqual(dialog.palette_paints, expected_greens)

        dialog.set_paint_search("no matches anywhere")

        self.assertEqual(dialog.palette_paints, ())
        self.assertEqual(dialog.palette_grid.paints, ())
        self.assertEqual(dialog.palette_count_label.options["text"], "0 colors")
        self.assertEqual(dialog.current_color, "#abcdef")
        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(NO_CITADEL_COLORS_MESSAGE, "No Citadel colors found.")
        self.assertEqual(PAINT_SEARCH_PLACEHOLDER, "Search Citadel colors...")

    def test_palette_sort_mode_applies_after_group_and_search_without_color_change(self):
        alpha_red = PaintColor("alpha-red", "Alpha Red", 210, 5, 5)
        zeta_red = PaintColor("zeta-red", "zeta red", 170, 15, 15)
        amber_red = PaintColor("amber-red", "amber Red", 190, 10, 10)
        green = PaintColor("green", "Beta Green", 0, 180, 0)
        paints = (zeta_red, green, amber_red, alpha_red)
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#abcdef"
        dialog.paint_catalog = PaintCatalog(paints=paints)
        dialog.palette_grid = FakePaletteGrid()
        dialog.palette_grid.selected_paint_id = alpha_red.id
        dialog.palette_count_label = FakeWidget()
        dialog.event_generate = Mock()
        dialog.search_query = ""
        dialog.palette_sort_mode = PaletteSortMode.COLOR
        dialog.group_buttons = {
            color_group: FakeGroupButton()
            for color_group, _ in COLOR_PICKER_GROUP_ENTRIES
        }
        dialog.group_button_labels = dict(COLOR_PICKER_GROUP_ENTRIES)

        dialog.select_color_group(ColorGroup.RED)
        expected_color_order = sort_paints_visually(
            get_paints_for_group(paints, ColorGroup.RED)
        )
        self.assertEqual(dialog.palette_paints, expected_color_order)

        dialog.set_palette_sort_mode(PaletteSortMode.ALPHABETICAL)
        self.assertEqual(
            tuple(paint.name for paint in dialog.palette_paints),
            ("Alpha Red", "amber Red", "zeta red"),
        )

        dialog.set_paint_search("red")
        self.assertEqual(
            tuple(paint.name for paint in dialog.palette_paints),
            ("Alpha Red", "amber Red", "zeta red"),
        )
        self.assertEqual(dialog.current_color, "#abcdef")
        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(dialog.palette_grid.selected_paint_id, alpha_red.id)

        dialog.palette_sort_selector = FakeWidget()
        dialog.palette_sort_selector.set("Color")
        dialog._on_palette_sort_selected()
        self.assertIs(dialog.palette_sort_mode, PaletteSortMode.COLOR)
        self.assertEqual(dialog.palette_paints, expected_color_order)
        self.assertEqual(dialog.search_query, "red")
        self.assertEqual(dialog.current_color, "#abcdef")
        self.assertEqual(dialog.palette_grid.selected_paint_id, alpha_red.id)

    def test_both_palette_sort_modes_preserve_every_group_and_search_membership(self):
        paints = (
            PaintColor("z-red", "Zulu Red Shade", 220, 10, 10),
            PaintColor("a-red", "Alpha Red Shade", 170, 20, 20),
            PaintColor("z-green", "Zulu Green Shade", 10, 180, 20),
            PaintColor("a-green", "Alpha Green Shade", 20, 130, 30),
            PaintColor("z-blue", "Zulu Blue Shade", 10, 20, 210),
            PaintColor("a-blue", "Alpha Blue Shade", 20, 30, 150),
            PaintColor("z-brown", "Zulu Brown Shade", 115, 65, 25),
            PaintColor("a-brown", "Alpha Brown Shade", 85, 50, 25),
            PaintColor("z-neutral", "Zulu Neutral Shade", 150, 150, 150),
            PaintColor("a-neutral", "Alpha Neutral Shade", 70, 70, 70),
        )
        dialog = object.__new__(ColorPickerDialog)
        dialog.current_color = "#abcdef"
        dialog.paint_catalog = PaintCatalog(paints=paints)
        dialog.palette_grid = FakePaletteGrid()
        dialog.palette_count_label = FakeWidget()
        dialog.event_generate = Mock()
        dialog.search_query = ""
        dialog.palette_sort_mode = PaletteSortMode.COLOR
        dialog.group_buttons = {
            color_group: FakeGroupButton()
            for color_group, _ in COLOR_PICKER_GROUP_ENTRIES
        }
        dialog.group_button_labels = dict(COLOR_PICKER_GROUP_ENTRIES)

        for query in ("", "shade"):
            dialog.set_paint_search(query)
            for color_group in (
                None,
                ColorGroup.RED,
                ColorGroup.GREEN,
                ColorGroup.BLUE,
                ColorGroup.BROWN,
                ColorGroup.NEUTRAL,
            ):
                dialog.select_color_group(color_group)
                group_members = (
                    paints
                    if color_group is None
                    else get_paints_for_group(paints, color_group)
                )
                expected_members = {
                    paint.id
                    for paint in filter_paints_by_name(group_members, query)
                }
                self.assertTrue(expected_members)

                dialog.set_palette_sort_mode(PaletteSortMode.ALPHABETICAL)
                alphabetical = dialog.palette_paints
                self.assertEqual(
                    tuple(paint.name for paint in alphabetical),
                    tuple(
                        sorted(
                            (paint.name for paint in alphabetical), key=str.casefold
                        )
                    ),
                )
                self.assertEqual(
                    {paint.id for paint in alphabetical}, expected_members
                )

                dialog.set_palette_sort_mode(PaletteSortMode.COLOR)
                self.assertEqual(
                    dialog.palette_paints,
                    sort_paints_visually(
                        filter_paints_by_name(group_members, query)
                    ),
                )
                self.assertEqual(
                    {paint.id for paint in dialog.palette_paints}, expected_members
                )

        self.assertEqual(dialog.current_color, "#abcdef")

    def test_palette_sorting_preserves_selected_paint_preview_and_visualization(self):
        selected = PaintColor("selected", "Zulu Red", 210, 5, 5)
        paints = (
            selected,
            PaintColor("alpha", "Alpha Red", 170, 15, 15),
        )
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#123456"
        dialog.current_color_preview = FakeWidget()
        dialog.paint_catalog = PaintCatalog(paints=paints)
        dialog.palette_grid = FakePaletteGrid()
        dialog.palette_count_label = FakeWidget()
        dialog.event_generate = Mock()
        dialog.search_query = ""
        dialog.palette_sort_mode = PaletteSortMode.COLOR
        dialog.selected_color_group = None

        dialog.select_paint(selected)
        expected_color = dialog.current_color
        expected_preview = dialog.current_color_preview.options["background"]
        expected_match = dialog.selected_paint_id

        for visualization in COLOR_SPACE_MODES:
            dialog.color_space_mode = visualization
            for sort_mode in (
                PaletteSortMode.ALPHABETICAL,
                PaletteSortMode.COLOR,
            ):
                dialog.set_palette_sort_mode(sort_mode)
                self.assertEqual(dialog.color_space_mode, visualization)
                self.assertEqual(dialog.current_color, expected_color)
                self.assertEqual(
                    dialog.current_color_preview.options["background"],
                    expected_preview,
                )
                self.assertEqual(dialog.selected_paint_id, expected_match)
                self.assertEqual(
                    dialog.palette_grid.selected_paint_id, expected_match
                )
                self.assertIn(selected, dialog.palette_grid.paints)

    def test_visible_count_uses_filtered_size_and_english_pluralization(self):
        self.assertEqual(format_visible_paint_count(0), "0 colors")
        self.assertEqual(format_visible_paint_count(1), "1 color")
        self.assertEqual(format_visible_paint_count(367), "367 colors")

    def test_paint_tooltip_contains_only_complete_catalog_color_details(self):
        paint = PaintColor("mephiston", "Mephiston Red", 150, 12, 9)

        self.assertEqual(
            paint_tooltip_text(paint),
            "Mephiston Red\nRGB: 150, 12, 9",
        )

    def test_palette_tooltip_uses_hover_screen_coordinates(self):
        paint = PaintColor("complete", "Complete Name", 12, 34, 56)
        grid = object.__new__(PaintSwatchGrid)
        grid._tooltip_after_id = None
        grid._tooltip_window = None
        grid.after = Mock(return_value="tooltip-after")
        grid.after_cancel = Mock()

        grid._schedule_tooltip(
            paint,
            SimpleNamespace(x_root=640, y_root=360),
        )

        self.assertEqual(grid._tooltip_after_id, "tooltip-after")
        callback = grid.after.call_args.args[1]
        with patch("src.widget.tk.Toplevel") as toplevel_type, patch(
            "src.widget.tk.Label"
        ):
            callback()

        toplevel_type.return_value.wm_geometry.assert_called_once_with("+660+380")

    def test_palette_tooltip_uses_latest_pointer_position_before_delay(self):
        paint = PaintColor("long", "A Truncated Paint Name", 12, 34, 56)
        grid = object.__new__(PaintSwatchGrid)
        grid._tooltip_after_id = None
        grid._tooltip_window = None
        grid._tooltip_root_position = (0, 0)
        grid.after = Mock(return_value="tooltip-after")
        grid.after_cancel = Mock()

        grid._schedule_tooltip(paint, SimpleNamespace(x_root=100, y_root=100))
        callback = grid.after.call_args.args[1]
        grid._tooltip_root_position = (140, 125)
        with patch("src.widget.tk.Toplevel") as toplevel_type, patch(
            "src.widget.tk.Label"
        ):
            callback()

        toplevel_type.return_value.wm_geometry.assert_called_once_with("+160+145")

    def test_palette_schedules_tooltip_only_for_truncated_names(self):
        short = PaintColor("short", "Short", 1, 2, 3)
        truncated = PaintColor("long", "A Very Long Truncated Name", 4, 5, 6)
        grid = object.__new__(PaintSwatchGrid)
        grid._hovered_paint = None
        grid._truncated_paint_ids = {truncated.id}
        grid._paint_at = Mock(side_effect=(short, truncated))
        grid._hide_tooltip = Mock()
        grid._schedule_tooltip = Mock()

        first_event = SimpleNamespace(x=10, y=10, x_root=100, y_root=100)
        grid._on_canvas_motion(first_event)
        grid._schedule_tooltip.assert_not_called()

        second_event = SimpleNamespace(x=20, y=20, x_root=120, y_root=120)
        grid._on_canvas_motion(second_event)
        grid._schedule_tooltip.assert_called_once_with(truncated, second_event)

    def test_exact_catalog_color_uses_paint_name_and_detailed_tooltip(self):
        paint = PaintColor("mephiston", "Mephiston Red", 150, 12, 9)
        catalog = PaintCatalog((paint,))

        presentation = color_slot_presentation(
            "#960c09", catalog, 200, lambda text: len(text) * 5
        )

        self.assertEqual(presentation.text, "Mephiston Red")
        self.assertEqual(presentation.foreground, "#ffffff")
        self.assertEqual(
            presentation.tooltip,
            "Mephiston Red\n#960C09\nRGB: 150, 12, 9",
        )

    def test_modified_catalog_color_returns_to_hex_display(self):
        catalog = PaintCatalog(
            (PaintColor("mephiston", "Mephiston Red", 150, 12, 9),)
        )

        presentation = color_slot_presentation(
            "#970c09", catalog, 200, lambda text: len(text) * 5
        )

        self.assertEqual(presentation.text, "#970C09")
        self.assertEqual(presentation.foreground, "#ffffff")
        self.assertIsNone(presentation.tooltip)

    def test_light_hex_slot_uses_dark_text(self):
        presentation = color_slot_presentation(
            "#ffff00", PaintCatalog(()), 200, lambda text: len(text) * 5
        )

        self.assertEqual(presentation.text, "#FFFF00")
        self.assertEqual(presentation.foreground, "#000000")

    def test_modified_color_can_match_another_catalog_paint(self):
        second = PaintColor("second", "Second Paint", 1, 2, 3)
        catalog = PaintCatalog(
            (
                PaintColor("mephiston", "Mephiston Red", 150, 12, 9),
                second,
            )
        )

        presentation = color_slot_presentation(
            "#010203", catalog, 200, lambda text: len(text) * 5
        )

        self.assertEqual(presentation.text, "Second Paint")

    def test_long_slot_name_uses_ellipsis_but_tooltip_keeps_full_name(self):
        paint = PaintColor(
            "long",
            "A Complete Citadel Paint Name",
            1,
            2,
            3,
        )

        presentation = color_slot_presentation(
            "#010203", PaintCatalog((paint,)), 40, lambda text: len(text) * 5
        )

        self.assertTrue(presentation.text.endswith("…"))
        self.assertLessEqual(len(presentation.text.splitlines()), 2)
        self.assertTrue(presentation.tooltip.startswith(paint.name))

    @patch.object(ColorPickerDialog, "get_accepted_color", return_value="#abcdef")
    @patch.object(ColorPickerDialog, "__init__", return_value=None)
    def test_show_returns_the_dialog_result(self, initialize, get_accepted_color):
        parent = object()

        result = ColorPickerDialog.show(parent, "#123456")

        self.assertEqual(result, "#abcdef")
        initialize.assert_called_once_with(parent, "#123456", None)
        get_accepted_color.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
