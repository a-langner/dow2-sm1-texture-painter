import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.constant import ColorOps
from src.color_processing_settings import ColorProcessingSettings
from src.color_slot import ColorSlot
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
        self.is_packed = True

    def pack_forget(self):
        self.is_packed = False

    def place(self, **options):
        self.place_options = options

    def pack_propagate(self, enabled):
        self.pack_propagate_enabled = enabled

    def grid_propagate(self, enabled):
        self.grid_propagate_enabled = enabled

    def cget(self, key):
        return self.options.get(key, "SystemButtonFace")

    def configure(self, **options):
        self.options.update(options)

    config = configure

    def delete(self, *args):
        pass

    def create_text(self, *args, **options):
        pass

    def bind(self, event, callback, add=None):
        if add == "+" and event in self.bindings:
            return
        self.bindings[event] = callback


class RemainingWidgetCallbackTests(unittest.TestCase):
    @patch(
        "src.widget.color_slot_presentation",
        return_value=SimpleNamespace(tooltip=None, text="Gray", foreground="white"),
    )
    @patch("src.widget.tk.Button", side_effect=FakeWidget)
    @patch("src.widget.tk.Canvas", side_effect=FakeWidget)
    @patch("src.widget.tk.Frame", side_effect=FakeWidget)
    @patch("src.widget.tkfont.Font")
    @patch("src.widget.tk.Frame.__init__", return_value=None)
    def test_color_slots_select_separately_from_explicit_edit_buttons(
        self,
        _frame_init,
        font_type,
        frame_type,
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
        self.assertEqual(frame_type.call_count, 4)
        self.assertEqual(
            [button.options["text"] for button in chooser.color_buttons],
            ["Edit Color 1", "Edit Color 2", "Edit Color 3", "Edit Color 4"],
        )

        chooser.color_boxes[2].bindings["<ButtonPress-1>"](
            SimpleNamespace(x_root=10, y_root=10)
        )
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

    @patch("src.widget.configure_app_selection_styles")
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
        _configure_selection_styles,
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
        self.assertFalse(frame._editing_indicator_visible)
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

        frame.set_processing_context(ProcessingMode.PER_COLOR, ColorSlot.COLOR_3)
        self.assertTrue(frame._editing_indicator_visible)
        self.assertTrue(frame.editing_label.is_packed)
        self.assertEqual(frame.editing_label.options["text"], "Editing: Color 3")

        frame.set_processing_context(ProcessingMode.GLOBAL, ColorSlot.COLOR_3)
        self.assertFalse(frame._editing_indicator_visible)
        self.assertFalse(frame.editing_label.is_packed)

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

    def test_processing_controls_follow_mode_and_active_slot_without_leakage(self):
        global_processing = ColorProcessingSettings(ColorOps.OVERLAY, 75, 100)
        color_two = ColorProcessingSettings(ColorOps.COLOR, 80, 95)
        settings = DEFAULT_RENDER_SETTINGS.with_global_processing(global_processing)
        settings = settings.with_processing_mode(ProcessingMode.PER_COLOR)
        settings = settings.with_active_color_slot(ColorSlot.COLOR_2)
        settings = settings.with_active_processing(color_two)
        settings = settings.with_processing_mode(ProcessingMode.GLOBAL)
        settings = settings.with_active_color_slot(ColorSlot.COLOR_1)
        painter = SimpleNamespace(
            render_settings=settings,
            frame_color_op_option=SimpleNamespace(
                var=ValueVariable("Overlay"),
                set_processing_context=Mock(),
            ),
            frame_sliders=SimpleNamespace(
                brightness_slider=ValueVariable(75),
                contrast_slider=ValueVariable(100),
            ),
            refresh_workspace=Mock(),
            request_workspace_preview=Mock(),
            _processing_controls_refreshing=False,
        )

        ArmyPainter.processing_mode_update(painter, "per_color")
        ArmyPainter.on_color_slot_selected(painter, 1)

        self.assertEqual(painter.frame_color_op_option.var.get(), "Color")
        self.assertEqual(painter.frame_sliders.brightness_slider.get(), 80)
        self.assertEqual(painter.frame_sliders.contrast_slider.get(), 95)

        painter.frame_color_op_option.var.set("Hard Light")
        ArmyPainter.color_operation_update(painter, "hard_light")
        painter.frame_sliders.brightness_slider.set(55)
        painter.frame_sliders.contrast_slider.set(130)
        ArmyPainter.on_slider_update(painter, 55, 130)
        ArmyPainter.on_color_slot_selected(painter, 0)

        self.assertEqual(painter.frame_color_op_option.var.get(), "Overlay")
        self.assertEqual(painter.frame_sliders.brightness_slider.get(), 75)
        self.assertEqual(painter.frame_sliders.contrast_slider.get(), 100)
        self.assertEqual(
            painter.render_settings.per_color_processing[1],
            ColorProcessingSettings(ColorOps.HARD_LIGHT, 55, 130),
        )
        self.assertEqual(
            painter.render_settings.per_color_processing[0],
            global_processing,
        )
        self.assertEqual(painter.render_settings.global_processing, global_processing)
        painter.frame_color_op_option.set_processing_context.assert_called_with(
            ProcessingMode.PER_COLOR,
            ColorSlot.COLOR_1,
        )
        self.assertEqual(painter.refresh_workspace.call_count, 2)
        painter.request_workspace_preview.assert_called_once_with()

    def test_current_pattern_processing_contains_global_and_every_color_slot(self):
        global_processing = ColorProcessingSettings(ColorOps.SCREEN, 80, 120)
        per_color = (
            ColorProcessingSettings(ColorOps.OVERLAY, 10, 20),
            ColorProcessingSettings(ColorOps.MULTIPLY, 30, 40),
            ColorProcessingSettings(ColorOps.COLOR, 50, 60),
            ColorProcessingSettings(ColorOps.HARD_LIGHT, 70, 80),
        )
        settings = DEFAULT_RENDER_SETTINGS.with_processing_state(
            ProcessingMode.PER_COLOR, global_processing, per_color
        ).with_active_color_slot(ColorSlot.COLOR_3)
        painter = SimpleNamespace(
            render_settings=settings,
            frame_color_op_option=SimpleNamespace(var=ValueVariable("Color")),
            frame_sliders=SimpleNamespace(
                brightness_slider=ValueVariable(50),
                contrast_slider=ValueVariable(60),
            ),
            _processing_controls_refreshing=False,
        )

        state = ArmyPainter.get_current_pattern_processing(painter)

        self.assertIs(state.processing_mode, ProcessingMode.PER_COLOR)
        self.assertEqual(state.global_processing, global_processing)
        self.assertEqual(state.per_color_processing, per_color)

    def test_widget_module_has_no_implicit_controller_lookup(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "widget.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("self._root()", source)
        self.assertNotIn("winfo_toplevel()", source)
        self.assertNotIn("ArmyPainter", source)


if __name__ == "__main__":
    unittest.main()
