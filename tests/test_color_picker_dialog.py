import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.paint_catalog import PaintCatalog, PaintColor
from src.paint_color_analysis import ColorGroup, VISUAL_GROUP_ORDER
from src.paint_color_analysis import get_paints_for_group, sort_paints_visually
from src.widget import (
    COLOR_FIELD_PREFERRED_HEIGHT,
    COLOR_PICKER_EDITOR_PANE_WIDTH,
    COLOR_PREVIEW_BORDER,
    COLOR_PICKER_GROUP_PANE_WIDTH,
    COLOR_PICKER_GROUP_ENTRIES,
    COLOR_PICKER_PALETTE_PANE_WIDTH,
    COLOR_SPACE_MODES,
    DEFAULT_COLOR_SPACE_MODE,
    NO_CITADEL_COLORS_MESSAGE,
    PAINT_SEARCH_PLACEHOLDER,
    PAINT_SWATCH_OUTLINE,
    PAINT_SWATCH_PREVIEW_SIZE,
    PAINT_SWATCH_SELECTED_OUTLINE,
    ColorPickerDialog,
    PaintSwatchGrid,
    calculate_paint_swatch_columns,
    filter_paints_by_name,
    format_visible_paint_count,
    paint_tooltip_text,
    paint_swatch_presentation,
)


class FakeWidget:
    def __init__(self, parent=None, **options):
        self.parent = parent
        self.options = options
        self.pack_options = None
        self.panes = []
        self.value = None
        self.bindings = {}

    def pack(self, **options):
        self.pack_options = options

    def pack_propagate(self, enabled):
        self.pack_propagate_enabled = enabled

    def add(self, child, **options):
        self.panes.append((child, options))

    def set(self, value):
        self.value = value

    def get(self):
        return self.value

    def bind(self, event, callback):
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

    def set_paints(self, paints):
        self.paints = tuple(paints)

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
        dialog = ColorPickerDialog(object(), "#123456")

        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(dialog.current_color, "#123456")
        self.assertEqual(dialog.color_space_mode, DEFAULT_COLOR_SPACE_MODE)
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

    def test_repeated_color_space_switching_preserves_exact_rgb(self):
        dialog = object.__new__(ColorPickerDialog)
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog.current_color = "#960C09"
        dialog.editor_mode_controls_label = FakeWidget()
        dialog.color_model_labels = {"component": FakeWidget()}
        dialog._refresh_color_model_controls = Mock()
        dialog._refresh_visual_picker = Mock()

        for mode in ("HSL", DEFAULT_COLOR_SPACE_MODE, "HSL", DEFAULT_COLOR_SPACE_MODE):
            dialog.select_color_space(mode)
            self.assertEqual(dialog.current_color, "#960C09")

        self.assertEqual(dialog._refresh_visual_picker.call_count, 4)

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
        dialog.geometry.assert_called_once_with("1100x720")
        dialog.minsize.assert_called_once_with(900, 600)

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
        self.assertEqual(pane_weights, [0, 1, 1])
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
        self.assertTrue(dialog.dialog_content.pack_options["expand"])
        self.assertTrue(dialog.main_panes.pack_options["expand"])
        for attribute in (
            "palette_search_area",
            "palette_count_area",
            "palette_grid_area",
            "editor_color_space_area",
            "editor_visualization_area",
            "editor_color_field_area",
            "editor_slider_area",
            "editor_numeric_area",
            "editor_rgb_area",
            "editor_alternate_color_space_area",
            "editor_hex_area",
            "editor_preview_area",
            "original_color_preview_area",
            "current_color_preview_area",
        ):
            with self.subTest(container=attribute):
                self.assertIsInstance(getattr(dialog, attribute), FakeWidget)

    def test_navigation_entries_reuse_all_runtime_color_groups(self):
        groups = tuple(color_group for color_group, _ in COLOR_PICKER_GROUP_ENTRIES)
        labels = tuple(label for _, label in COLOR_PICKER_GROUP_ENTRIES)

        self.assertEqual(groups, (None,) + VISUAL_GROUP_ORDER)
        self.assertEqual(labels[0], "All Colors")
        self.assertNotIn("Metallic", labels)

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

    @patch("src.widget.tk.Canvas", side_effect=FakeWidget)
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
        _canvas_type,
    ):
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#abcdef"
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
        dialog.register = Mock(return_value="rgb-validation-command")
        for attribute in (
            "editor_color_space_area",
            "editor_color_field_area",
            "editor_slider_area",
            "editor_rgb_area",
            "editor_alternate_color_space_area",
            "editor_hex_area",
            "original_color_preview_area",
            "current_color_preview_area",
        ):
            setattr(dialog, attribute, FakeWidget())

        dialog._build_color_editor()

        self.assertEqual(dialog.color_space_selector.options["values"], COLOR_SPACE_MODES)
        self.assertEqual(dialog.color_space_selector.options["state"], "readonly")
        self.assertEqual(dialog.color_space_selector.get(), DEFAULT_COLOR_SPACE_MODE)
        self.assertEqual(dialog.original_color_preview.options["background"], "#123456")
        self.assertEqual(dialog.current_color_preview.options["background"], "#abcdef")
        self.assertEqual(
            dialog.hsv_color_field.options["height"], COLOR_FIELD_PREFERRED_HEIGHT
        )
        self.assertEqual(dialog.original_color_preview_label.options["text"], "Original")
        self.assertEqual(dialog.current_color_preview_label.options["text"], "Current")
        for preview in (dialog.original_color_preview, dialog.current_color_preview):
            self.assertEqual(preview.options["highlightbackground"], COLOR_PREVIEW_BORDER)
            self.assertEqual(preview.options["highlightcolor"], COLOR_PREVIEW_BORDER)
            self.assertEqual(preview.options["highlightthickness"], 1)

        dialog.select_color_space("HSL")
        dialog.set_current_color("#fedcba")

        self.assertEqual(dialog.color_space_mode, "HSL")
        self.assertIn("HSL controls", dialog.editor_mode_controls_label.options["text"])
        self.assertEqual(
            dialog.color_model_labels["component"].options["text"], "Lightness:"
        )
        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(dialog.current_color, "#fedcba")
        self.assertEqual(dialog.current_color_preview.options["background"], "#fedcba")
        self.assertEqual(dialog.hex_input.get(), "#FEDCBA")

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

        dialog._render_hsv_field(0.5001)
        dialog._render_hsl_field(0.5001)
        dialog._render_hue_slider()

        dialog.hsv_color_field.delete.assert_not_called()
        dialog.hue_slider.delete.assert_not_called()

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

        grid._relayout()

        self.assertEqual(grid._configured_column_count, 2)
        self.assertEqual(len(grid._paint_regions), 2)
        self.assertEqual(grid.canvas.create_rectangle.call_count, 4)
        self.assertEqual(grid.canvas.create_text.call_count, 2)
        grid.canvas.configure.assert_called_once_with(
            scrollregion=(0, 0, 192, PAINT_SWATCH_PREVIEW_SIZE + 56)
        )

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

    @patch.object(ColorPickerDialog, "get_accepted_color", return_value="#abcdef")
    @patch.object(ColorPickerDialog, "__init__", return_value=None)
    def test_show_returns_the_dialog_result(self, initialize, get_accepted_color):
        parent = object()

        result = ColorPickerDialog.show(parent, "#123456")

        self.assertEqual(result, "#abcdef")
        initialize.assert_called_once_with(parent, "#123456")
        get_accepted_color.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
