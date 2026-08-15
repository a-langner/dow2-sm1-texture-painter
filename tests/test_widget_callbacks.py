import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.constant import ColorOps
from src.frame_main import ArmyPainter
from src.processing_mode import ProcessingMode
from src.render_settings import DEFAULT_RENDER_SETTINGS
from src.widget import (
    BatchEditTopLevel,
    FrameChannelList,
    FrameColorChooser,
    FrameColorOps,
    FrameSlider,
)


class ValueVariable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeScale:
    def __init__(self, parent, **options):
        self.parent = parent
        self.options = options
        self.value = 75 if options["label"] == "Brightness" else 100

    def pack(self, **options):
        self.pack_options = options

    def get(self):
        return self.value


class FakeWidget:
    def __init__(self, parent=None, **options):
        self.parent = parent
        self.options = options
        self.bindings = {}

    def insert(self, *args):
        pass

    def __getitem__(self, key):
        return self.options[key]

    def __setitem__(self, key, value):
        self.options[key] = value

    def pack(self, **options):
        self.pack_options = options

    def place(self, **options):
        self.place_options = options

    def configure(self, **options):
        self.options.update(options)

    config = configure

    def delete(self, *args):
        pass

    def create_text(self, *args, **options):
        pass

    def bind(self, event, callback):
        self.bindings[event] = callback


class RemainingWidgetCallbackTests(unittest.TestCase):
    @patch(
        "src.widget.color_slot_presentation",
        return_value=SimpleNamespace(tooltip=None, text="Gray", foreground="white"),
    )
    @patch("src.widget.tk.Button", side_effect=FakeWidget)
    @patch("src.widget.tk.Canvas", side_effect=FakeWidget)
    @patch("src.widget.tkfont.Font")
    @patch("src.widget.tk.Frame.__init__", return_value=None)
    def test_color_slots_select_separately_from_explicit_edit_buttons(
        self,
        _frame_init,
        font_type,
        canvas_type,
        button_type,
        _presentation,
    ):
        font_type.return_value.measure.return_value = 20
        selected = Mock()
        changed = Mock()
        picker = Mock(return_value=None)
        chooser = FrameColorChooser(
            object(),
            on_color_changed=changed,
            on_slot_selected=selected,
            color_picker=picker,
            paint_catalog=Mock(),
        )

        self.assertEqual(canvas_type.call_count, 4)
        self.assertEqual(button_type.call_count, 4)
        self.assertEqual(
            [button.options["text"] for button in chooser.color_buttons],
            ["Edit Color 1", "Edit Color 2", "Edit Color 3", "Edit Color 4"],
        )

        chooser.color_boxes[2].bindings["<Button-1>"](object())
        selected.assert_called_once_with(2)
        picker.assert_not_called()

        chooser.color_buttons[2].options["command"]()
        picker.assert_called_once_with("#808080")
        changed.assert_not_called()

    @patch("src.widget.tk.Checkbutton", side_effect=FakeWidget)
    @patch("src.widget.tk.BooleanVar", return_value=ValueVariable(0))
    @patch("src.widget.tk.Listbox", side_effect=FakeWidget)
    @patch("src.widget.tk.LabelFrame.__init__", return_value=None)
    def test_channel_selection_is_not_exported_to_other_controls(
        self,
        _label_frame_init,
        listbox_type,
        _boolean_var,
        _checkbutton_type,
    ):
        frame = FrameChannelList(object(), on_alpha_changed=Mock())

        listbox_type.assert_called_once()
        self.assertIsInstance(frame.lb, FakeWidget)
        self.assertIs(frame.lb.options["exportselection"], False)
        self.assertEqual(frame.lb.options["selectmode"], "multiple")

    def test_alpha_toggle_forwards_boolean_value(self):
        frame = object.__new__(FrameChannelList)
        frame.apply_alpha = ValueVariable(1)
        frame._on_alpha_changed = Mock()

        frame._notify_apply_alpha_changed()

        frame._on_alpha_changed.assert_called_once_with(True)

    def test_color_operation_forwards_selected_value(self):
        frame = object.__new__(FrameColorOps)
        frame.var = ValueVariable("multiply")
        frame._on_operation_changed = Mock()

        frame._notify_operation_changed()

        frame._on_operation_changed.assert_called_once_with("multiply")

    def test_processing_mode_forwards_stable_selected_value(self):
        frame = object.__new__(FrameColorOps)
        frame.processing_mode_var = ValueVariable("per_color")
        frame._on_processing_mode_changed = Mock()

        frame._notify_processing_mode_changed()

        frame._on_processing_mode_changed.assert_called_once_with("per_color")

    @patch("src.widget.ttk.Radiobutton", side_effect=FakeWidget)
    @patch("src.widget.ttk.Combobox", side_effect=FakeWidget)
    @patch("src.widget.ttk.Label", side_effect=FakeWidget)
    @patch("src.widget.tk.StringVar", side_effect=lambda value: ValueVariable(value))
    @patch("src.widget.tk.LabelFrame.__init__", return_value=None)
    def test_color_operation_builds_compact_readonly_selector(
        self,
        _label_frame_init,
        _string_var,
        _label_type,
        combobox_type,
        radiobutton_type,
    ):
        operation_callback = Mock()
        mode_callback = Mock()

        frame = FrameColorOps(
            object(),
            on_operation_changed=operation_callback,
            on_processing_mode_changed=mode_callback,
        )

        combobox_type.assert_called_once()
        self.assertEqual(radiobutton_type.call_count, 2)
        self.assertEqual(frame.processing_mode_var.get(), "global")
        self.assertEqual(frame.global_mode_button.options["text"], "Global")
        self.assertEqual(frame.global_mode_button.options["value"], "global")
        self.assertEqual(frame.per_color_mode_button.options["text"], "Per Color")
        self.assertEqual(frame.per_color_mode_button.options["value"], "per_color")
        selector = frame.blend_mode_selector
        self.assertEqual(selector.options["state"], "readonly")
        self.assertEqual(
            selector.options["values"],
            (
                "Overlay",
                "Screen",
                "Multiply",
                "Normal",
                "Soft Light",
                "Hard Light",
                "Color",
                "Linear Burn",
                "Linear Dodge (Add)",
            ),
        )
        self.assertEqual(frame.var.get(), "Overlay")
        self.assertIn("<<ComboboxSelected>>", selector.bindings)
        frame.var.set("Linear Dodge (Add)")
        selector.bindings["<<ComboboxSelected>>"](object())
        operation_callback.assert_called_once_with("linear_dodge")
        frame.processing_mode_var.set("per_color")
        frame.per_color_mode_button.options["command"]()
        mode_callback.assert_called_once_with("per_color")

    @patch("src.widget.tk.Scale", side_effect=FakeScale)
    @patch("src.widget.tk.Frame.__init__", return_value=None)
    def test_slider_constructs_with_minimal_parent_and_forwards_values(
        self, _frame_init, _scale_type
    ):
        callback = Mock()

        frame = FrameSlider(object(), on_levels_changed=callback)
        callback.assert_not_called()
        frame.brightness_slider.options["command"]("75")
        frame.contrast_slider.options["command"]("100")

        self.assertEqual(callback.call_args_list[0].args, (75.0, 100.0))
        self.assertEqual(callback.call_args_list[1].args, (75.0, 100.0))

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
        edit.assert_not_called()
        convert.assert_not_called()
        cancel.assert_not_called()
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
                "render_settings": DEFAULT_RENDER_SETTINGS,
                "refresh_workspace": Mock(),
            },
        )()

        ArmyPainter.on_apply_alpha_toggle(painter, True)
        ArmyPainter.color_operation_update(painter, ColorOps.SCREEN.value)
        ArmyPainter.processing_mode_update(painter, ProcessingMode.PER_COLOR.value)

        self.assertIs(painter.render_settings.apply_alpha, True)
        self.assertIs(painter.render_settings.color_op, ColorOps.SCREEN)
        self.assertIs(
            painter.render_settings.processing_mode,
            ProcessingMode.PER_COLOR,
        )
        self.assertEqual(painter.refresh_workspace.call_count, 3)

    def test_controller_receives_both_slider_levels(self):
        painter = type(
            "Painter",
            (),
            {
                "request_workspace_preview": Mock(),
            },
        )()

        ArmyPainter.on_slider_update(painter, 75.0, 100.0)

        painter.request_workspace_preview.assert_called_once_with()

    def test_widget_module_has_no_implicit_controller_lookup(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "widget.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("self._root()", source)
        self.assertNotIn("winfo_toplevel()", source)
        self.assertNotIn("ArmyPainter", source)


if __name__ == "__main__":
    unittest.main()
