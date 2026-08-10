import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.paint_catalog import PaintCatalog, PaintColor
from src.paint_color_analysis import ColorGroup, VISUAL_GROUP_ORDER
from src.paint_color_analysis import get_paints_for_group, sort_paints_visually
from src.widget import (
    COLOR_PICKER_DEFAULT_HEIGHT,
    COLOR_PICKER_DEFAULT_WIDTH,
    COLOR_PICKER_MIN_HEIGHT,
    COLOR_PICKER_MIN_WIDTH,
    COLOR_PICKER_GROUP_ENTRIES,
    COLOR_SPACE_MODES,
    DEFAULT_COLOR_SPACE_MODE,
    NO_CITADEL_COLORS_MESSAGE,
    PAINT_SEARCH_PLACEHOLDER,
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

    def add(self, child, **options):
        self.panes.append((child, options))

    def set(self, value):
        self.value = value

    def get(self):
        return self.value

    def bind(self, event, callback):
        self.bindings[event] = callback

    def configure(self, **options):
        self.options.update(options)


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
    @patch("src.widget.tk.Toplevel.wait_window")
    @patch("src.widget.tk.Toplevel.grab_set")
    @patch("src.widget.tk.Toplevel.bind")
    @patch("src.widget.tk.Toplevel.protocol")
    @patch.object(ColorPickerDialog, "_build_editor_placeholders")
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
        _build_editor_placeholders,
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
        dialog._refresh_visual_picker = Mock()

        for mode in ("HSL", DEFAULT_COLOR_SPACE_MODE, "HSL", DEFAULT_COLOR_SPACE_MODE):
            dialog.select_color_space(mode)
            self.assertEqual(dialog.current_color, "#960C09")

        self.assertEqual(dialog._refresh_visual_picker.call_count, 4)

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

    def test_window_is_resizable_and_bounded_to_available_screen(self):
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
        dialog.geometry.assert_called_once_with(
            f"{COLOR_PICKER_DEFAULT_WIDTH}x{COLOR_PICKER_DEFAULT_HEIGHT}"
        )
        dialog.minsize.assert_called_once_with(
            COLOR_PICKER_MIN_WIDTH, COLOR_PICKER_MIN_HEIGHT
        )

    @patch("src.widget.ttk.LabelFrame", side_effect=FakeWidget)
    @patch("src.widget.ttk.Panedwindow", side_effect=FakeWidget)
    @patch("src.widget.ttk.Frame", side_effect=FakeWidget)
    def test_main_layout_has_three_weighted_areas_and_future_containers(
        self, _frame_type, _paned_type, _label_frame_type
    ):
        dialog = object.__new__(ColorPickerDialog)

        dialog._build_main_layout()

        pane_names = [pane.options["text"] for pane, _ in dialog.main_panes.panes]
        pane_weights = [options["weight"] for _, options in dialog.main_panes.panes]
        self.assertEqual(pane_names, ["Groups", "Citadel Colors", "Color Editor"])
        self.assertEqual(pane_weights, [0, 3, 2])
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
    @patch("src.widget.ttk.Combobox", side_effect=FakeWidget)
    @patch("src.widget.ttk.Label", side_effect=FakeWidget)
    def test_editor_placeholders_share_mode_and_color_state(
        self, _label_type, _combobox_type, _canvas_type
    ):
        dialog = object.__new__(ColorPickerDialog)
        dialog.original_color = "#123456"
        dialog.current_color = "#abcdef"
        dialog.color_space_mode = DEFAULT_COLOR_SPACE_MODE
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

        dialog._build_editor_placeholders()

        self.assertEqual(dialog.color_space_selector.options["values"], COLOR_SPACE_MODES)
        self.assertEqual(dialog.color_space_selector.options["state"], "readonly")
        self.assertEqual(dialog.color_space_selector.get(), DEFAULT_COLOR_SPACE_MODE)
        self.assertEqual(dialog.original_color_preview.options["background"], "#123456")
        self.assertEqual(dialog.current_color_preview.options["background"], "#abcdef")

        dialog.select_color_space("HSL")
        dialog.set_current_color("#fedcba")

        self.assertEqual(dialog.color_space_mode, "HSL")
        self.assertIn("HSL controls", dialog.editor_mode_controls_label.options["text"])
        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(dialog.current_color, "#fedcba")
        self.assertEqual(dialog.current_color_preview.options["background"], "#fedcba")

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

    def test_swatch_relayout_releases_columns_after_narrowing(self):
        grid = object.__new__(PaintSwatchGrid)
        grid._relayout_after_id = "pending"
        grid._configured_column_count = 5
        grid._column_count = 2
        grid._swatch_items = []
        grid._empty_label = None
        grid.inner = Mock()

        grid._relayout()

        self.assertEqual(grid._configured_column_count, 2)
        grid.inner.grid_columnconfigure.assert_any_call(0, weight=1)
        grid.inner.grid_columnconfigure.assert_any_call(1, weight=1)
        for obsolete_column in (2, 3, 4):
            grid.inner.grid_columnconfigure.assert_any_call(
                obsolete_column, weight=0
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
        light = PaintColor("light", "Light", 255, 255, 255)
        dark_item = Mock()
        light_item = Mock()
        grid = object.__new__(PaintSwatchGrid)
        grid._on_paint_selected = Mock()
        grid.selected_paint_id = None
        grid._swatch_items = (
            (dark, dark_item, Mock(), Mock()),
            (light, light_item, Mock(), Mock()),
        )

        grid._select_paint(dark)
        grid.set_selected_paint("dark")

        grid._on_paint_selected.assert_called_once_with(dark)
        dark_item.configure.assert_called_with(
            style="Selected.PaintSwatch.TFrame"
        )
        light_item.configure.assert_called_with(style="PaintSwatch.TFrame")

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
