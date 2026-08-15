import unittest
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.color_slot import ColorSlot
from src.render_settings import RenderSettings
from src.widget import ColorPickerDialog, FrameColorChooser, PatternSelection

STORED_COLORS = ["#112233", "#445566", "#778899", "#aabbcc"]


class FakePatternList:
    def __init__(self, selection):
        self.selection = selection

    def get_selected_pattern(self):
        return self.selection


class FakePainter:
    def __init__(self, selection, colors):
        self.frame_army_pattern = FakePatternList(selection)
        self.frame_color_chooser = type(
            "ColorChooser",
            (),
            {"color_boxes": [{"bg": color} for color in colors]},
        )()

    def get_current_pattern_colors(self):
        return ArmyPainter.get_current_pattern_colors(self)


class PatternDirtyStateTests(unittest.TestCase):
    @patch("src.frame_main.get_pattern_colors", return_value=STORED_COLORS)
    def test_selected_pattern_is_clean_when_four_colors_match(self, get_colors):
        painter = FakePainter(PatternSelection("Selected", True), list(STORED_COLORS))

        self.assertFalse(ArmyPainter.is_selected_pattern_dirty(painter))
        get_colors.assert_called_once_with("Selected")

    @patch("src.frame_main.get_pattern_colors", return_value=STORED_COLORS)
    def test_selected_pattern_is_dirty_when_one_color_differs(self, get_colors):
        current_colors = list(STORED_COLORS)
        current_colors[2] = "#000000"
        painter = FakePainter(PatternSelection("Selected", False), current_colors)

        self.assertTrue(ArmyPainter.is_selected_pattern_dirty(painter))

    @patch("src.frame_main.get_pattern_colors", return_value=STORED_COLORS)
    def test_hexadecimal_case_does_not_create_dirty_state(self, get_colors):
        painter = FakePainter(
            PatternSelection("Selected", True),
            [color.upper() for color in STORED_COLORS],
        )

        self.assertFalse(ArmyPainter.is_selected_pattern_dirty(painter))

    def test_cleared_selection_is_never_dirty(self):
        painter = FakePainter(None, ["#000000"] * 4)

        self.assertFalse(ArmyPainter.is_selected_pattern_dirty(painter))

    def test_color_picker_change_resynchronizes_actions(self):
        chooser = object.__new__(FrameColorChooser)
        chooser.color_boxes = [{"bg": "#000000"} for _ in range(4)]
        chooser.draw_rgb_value = Mock()
        chooser._on_color_changed = Mock()
        chooser._color_picker = Mock(return_value="#010203")

        FrameColorChooser.apply_color(chooser, 1)

        chooser._color_picker.assert_called_once_with("#000000")
        self.assertEqual(chooser.color_boxes[1]["bg"], "#010203")
        chooser._on_color_changed.assert_called_once_with(1, "#010203")

    def test_swatch_click_selects_and_highlights_without_opening_picker(self):
        chooser = object.__new__(FrameColorChooser)
        chooser.color_boxes = [Mock() for _ in range(4)]
        chooser.active_slot_index = 0
        chooser._on_slot_selected = Mock()
        chooser._color_picker = Mock()

        FrameColorChooser.select_slot(chooser, 2)

        self.assertEqual(chooser.active_slot_index, 2)
        chooser._on_slot_selected.assert_called_once_with(2)
        chooser._color_picker.assert_not_called()
        self.assertEqual(
            chooser.color_boxes[2].configure.call_args.kwargs["relief"],
            "sunken",
        )
        self.assertEqual(
            chooser.color_boxes[0].configure.call_args.kwargs["relief"],
            "raised",
        )

    def test_slot_selection_updates_state_without_changing_color(self):
        painter = type(
            "Painter",
            (),
            {"render_settings": RenderSettings()},
        )()

        ArmyPainter.on_color_slot_selected(painter, 3)

        self.assertIs(painter.render_settings.active_color_slot, ColorSlot.COLOR_4)
        self.assertEqual(painter.render_settings.colors, RenderSettings().colors)

    @patch.object(ColorPickerDialog, "show", return_value="#010203")
    def test_production_picker_opens_with_current_color_and_returns_acceptance(
        self, show
    ):
        chooser = object.__new__(FrameColorChooser)
        chooser.paint_catalog = Mock()

        self.assertEqual(chooser._open_color_picker("#000000"), "#010203")

        show.assert_called_once_with(chooser, "#000000", chooser.paint_catalog)

    @patch.object(ColorPickerDialog, "show", return_value=None)
    def test_production_picker_returns_cancellation(self, show):
        chooser = object.__new__(FrameColorChooser)
        chooser.paint_catalog = Mock()

        self.assertIsNone(chooser._open_color_picker("#112233"))

        show.assert_called_once_with(chooser, "#112233", chooser.paint_catalog)

    def test_cancelled_picker_leaves_slot_and_downstream_state_unchanged(self):
        chooser = object.__new__(FrameColorChooser)
        chooser.color_boxes = [{"bg": "#000000"} for _ in range(4)]
        chooser.draw_rgb_value = Mock()
        chooser._on_color_changed = Mock()
        chooser._color_picker = Mock(return_value=None)

        FrameColorChooser.apply_color(chooser, 2)

        self.assertEqual(chooser.color_boxes[2]["bg"], "#000000")
        chooser.draw_rgb_value.assert_not_called()
        chooser._on_color_changed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
