import unittest
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.widget import FrameColorChooser, PatternSelection, choose_native_color

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

    @patch("src.widget.colorchooser.askcolor", return_value=((1, 2, 3), "#010203"))
    def test_native_color_picker_preserves_hex_result(self, ask_color):
        self.assertEqual(choose_native_color("#000000"), "#010203")

        ask_color.assert_called_once_with("#000000")


if __name__ == "__main__":
    unittest.main()
