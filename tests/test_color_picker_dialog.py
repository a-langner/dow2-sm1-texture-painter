import unittest
from unittest.mock import Mock, patch

from src.widget import (
    COLOR_PICKER_DEFAULT_HEIGHT,
    COLOR_PICKER_DEFAULT_WIDTH,
    COLOR_PICKER_MIN_HEIGHT,
    COLOR_PICKER_MIN_WIDTH,
    ColorPickerDialog,
)


class ColorPickerDialogTests(unittest.TestCase):
    @patch("src.widget.tk.Toplevel.wait_window")
    @patch("src.widget.tk.Toplevel.grab_set")
    @patch("src.widget.tk.Toplevel.bind")
    @patch("src.widget.tk.Toplevel.protocol")
    @patch.object(ColorPickerDialog, "_build_actions")
    @patch.object(ColorPickerDialog, "_configure_window")
    @patch("src.widget.tk.Toplevel.__init__", return_value=None)
    def test_construction_preserves_original_and_initializes_working_color(
        self,
        _toplevel_init,
        _configure_window,
        _build_actions,
        _protocol,
        _bind,
        grab_set,
        wait_window,
    ):
        dialog = ColorPickerDialog(object(), "#123456")

        self.assertEqual(dialog.original_color, "#123456")
        self.assertEqual(dialog.current_color, "#123456")
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
