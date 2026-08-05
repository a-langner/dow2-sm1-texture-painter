import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.widget import (
    BatchEditTopLevel,
    FrameChannelList,
    FrameColorOps,
    FrameSlider,
)


class ValueVariable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeScale:
    def __init__(self, parent, **options):
        self.parent = parent
        self.options = options

    def pack(self, **options):
        self.pack_options = options


class RemainingWidgetCallbackTests(unittest.TestCase):
    def test_alpha_toggle_forwards_boolean_value(self):
        frame = object.__new__(FrameChannelList)
        frame.apply_alpha = ValueVariable(1)
        frame._on_apply_alpha_changed = Mock()

        frame._notify_apply_alpha_changed()

        frame._on_apply_alpha_changed.assert_called_once_with(True)

    def test_color_operation_forwards_selected_value(self):
        frame = object.__new__(FrameColorOps)
        frame.var = ValueVariable("multiply")
        frame._on_operation_changed = Mock()

        frame._notify_operation_changed()

        frame._on_operation_changed.assert_called_once_with("multiply")

    @patch("src.widget.tk.Scale", side_effect=FakeScale)
    @patch("src.widget.tk.Frame.__init__", return_value=None)
    def test_slider_constructs_with_minimal_parent_and_forwards_values(
        self, _frame_init, _scale_type
    ):
        callback = Mock()

        frame = FrameSlider(object(), on_value_changed=callback)
        frame.brightness_slider.options["command"]("75")
        frame.contrast_slider.options["command"]("100")

        self.assertEqual(callback.call_args_list[0].args, ("75",))
        self.assertEqual(callback.call_args_list[1].args, ("100",))

    @patch.object(BatchEditTopLevel, "initialize")
    @patch("src.widget.tk.Toplevel.title")
    @patch("src.widget.tk.Toplevel.resizable")
    @patch("src.widget.tk.Toplevel.__init__", return_value=None)
    def test_batch_widget_constructs_without_application_root(
        self, _toplevel_init, _resizable, _title, _initialize
    ):
        edit = Mock()
        convert = Mock()
        cancel = Mock()

        frame = BatchEditTopLevel(
            object(),
            on_batch_edit=edit,
            on_batch_convert=convert,
            on_cancel=cancel,
        )
        frame._on_batch_edit()
        frame._on_batch_convert()
        frame._on_cancel()

        edit.assert_called_once_with()
        convert.assert_called_once_with()
        cancel.assert_called_once_with()

    def test_controller_receives_alpha_and_color_operation_values(self):
        painter = type(
            "Painter",
            (),
            {
                "img_wbench": type("Workbench", (), {})(),
                "refresh_workspace": Mock(),
            },
        )()

        ArmyPainter.on_apply_alpha_toggle(painter, True)
        ArmyPainter.color_operation_update(painter, "screen")

        self.assertIs(painter.img_wbench.apply_alpha, True)
        self.assertEqual(painter.img_wbench.color_op, "screen")
        self.assertEqual(painter.refresh_workspace.call_count, 2)

    def test_widget_module_has_no_implicit_controller_lookup(self):
        source = (
            Path(__file__).resolve().parents[1] / "src" / "widget.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("self._root()", source)
        self.assertNotIn("winfo_toplevel()", source)
        self.assertNotIn("ArmyPainter", source)


if __name__ == "__main__":
    unittest.main()
