import unittest
from unittest.mock import Mock, patch

from src.paint_color_analysis import ColorGroup, VISUAL_GROUP_ORDER
from src.widget import (
    COLOR_PICKER_DEFAULT_HEIGHT,
    COLOR_PICKER_DEFAULT_WIDTH,
    COLOR_PICKER_MIN_HEIGHT,
    COLOR_PICKER_MIN_WIDTH,
    COLOR_PICKER_GROUP_ENTRIES,
    COLOR_SPACE_MODES,
    DEFAULT_COLOR_SPACE_MODE,
    ColorPickerDialog,
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


class ColorPickerDialogTests(unittest.TestCase):
    @patch("src.widget.tk.Toplevel.wait_window")
    @patch("src.widget.tk.Toplevel.grab_set")
    @patch("src.widget.tk.Toplevel.bind")
    @patch("src.widget.tk.Toplevel.protocol")
    @patch.object(ColorPickerDialog, "_build_editor_placeholders")
    @patch.object(ColorPickerDialog, "_build_group_navigation")
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

        dialog.set_current_color("#abcdef")

        self.assertEqual(dialog.current_color, "#abcdef")

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
