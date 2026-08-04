import unittest
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.widget import PatternSelection

STORED_COLORS = ["#112233", "#445566", "#778899", "#aabbcc"]
DIRTY_COLORS = ["#010203", "#141516", "#272829", "#3a3b3c"]


class FakePatternList:
    def __init__(self, selection):
        self.selection = selection

    def get_selected_pattern(self):
        return self.selection


class FakeColorChooser:
    def __init__(self):
        self.color_boxes = [{"bg": color} for color in DIRTY_COLORS]
        self.draw_count = 0

    def draw_rgb_value(self):
        self.draw_count += 1


class FakePainter:
    def __init__(self, selection):
        self.frame_army_pattern = FakePatternList(selection)
        self.frame_color_chooser = FakeColorChooser()
        self.state_updates = []
        self.refresh_count = 0
        self.brightness = 75
        self.contrast = 100
        self.texture_state = object()
        self.window_geometry = "900x700+20+20"

    def apply_selected_pattern_colors(self, selection=None):
        return ArmyPainter.apply_selected_pattern_colors(self, selection)

    def update_pattern_action_states(self, selection=None):
        self.state_updates.append(selection)

    def refresh_workspace(self):
        self.refresh_count += 1


class PatternResetGuiTests(unittest.TestCase):
    @patch("src.frame_main.get_pattern_colors")
    def test_no_selection_does_nothing(self, get_colors):
        painter = FakePainter(None)

        ArmyPainter.reset_to_selected_pattern(painter)

        get_colors.assert_not_called()
        self.assertEqual(painter.refresh_count, 0)
        self.assertEqual(painter.state_updates, [None])

    @patch("src.frame_main.src.color_pattern_handler.update_user_pattern")
    @patch("src.frame_main.src.color_pattern_handler.save")
    @patch("src.frame_main.get_pattern_colors", return_value=STORED_COLORS)
    def test_reset_applies_stored_colors_without_persisting_or_changing_settings(
        self, get_colors, save, update
    ):
        for user_created in (False, True):
            with self.subTest(user_created=user_created):
                selection = PatternSelection("Selected", user_created)
                painter = FakePainter(selection)
                unchanged_state = (
                    painter.brightness,
                    painter.contrast,
                    painter.texture_state,
                    painter.window_geometry,
                )

                ArmyPainter.reset_to_selected_pattern(painter)

                self.assertEqual(
                    [box["bg"] for box in painter.frame_color_chooser.color_boxes],
                    STORED_COLORS,
                )
                self.assertEqual(painter.frame_color_chooser.draw_count, 1)
                self.assertEqual(painter.refresh_count, 1)
                self.assertEqual(painter.state_updates, [selection])
                self.assertEqual(
                    (
                        painter.brightness,
                        painter.contrast,
                        painter.texture_state,
                        painter.window_geometry,
                    ),
                    unchanged_state,
                )

        save.assert_not_called()
        update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
