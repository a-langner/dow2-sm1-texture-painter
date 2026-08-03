import unittest
from collections import OrderedDict
from unittest.mock import patch

from src.frame_main import ArmyPainter


class FakePatternFrame:
    def __init__(self, selected_name):
        self.selected_name = selected_name
        self.delete_state_update_count = 0

    def get_selected_pattern_name(self):
        return self.selected_name

    def update_delete_button_state(self):
        self.delete_state_update_count += 1


class FakeColorChooser:
    def __init__(self):
        self.color_boxes = [{"bg": "#000000"} for _ in range(4)]
        self.draw_count = 0

    def draw_rgb_value(self):
        self.draw_count += 1


class FakePainter:
    def __init__(self, selected_name):
        self.frame_army_pattern = FakePatternFrame(selected_name)
        self.frame_color_chooser = FakeColorChooser()
        self.refresh_count = 0

    def refresh_workspace(self):
        self.refresh_count += 1


class PatternSelectionTests(unittest.TestCase):
    def test_applies_selected_pattern_colors_and_refreshes(self):
        colors = ["#112233", "#445566", "#778899", "#aabbcc"]
        patterns = {
            "Internal Name": OrderedDict(
                zip(
                    [
                        "primary_colour_name",
                        "secondary_colour_name",
                        "tint_colour_name",
                        "extra_colour_name",
                    ],
                    colors,
                )
            )
        }
        painter = FakePainter("Internal Name")

        with patch("src.frame_main.army_color_pattern", patterns):
            ArmyPainter.on_pattern_select(painter)

        self.assertEqual(
            [box["bg"] for box in painter.frame_color_chooser.color_boxes],
            colors,
        )
        self.assertEqual(painter.frame_color_chooser.draw_count, 1)
        self.assertEqual(painter.refresh_count, 1)
        self.assertEqual(
            painter.frame_army_pattern.delete_state_update_count, 1
        )

    def test_empty_selection_is_ignored(self):
        painter = FakePainter(None)

        ArmyPainter.on_pattern_select(painter)

        self.assertEqual(painter.frame_color_chooser.draw_count, 0)
        self.assertEqual(painter.refresh_count, 0)
        self.assertEqual(
            painter.frame_army_pattern.delete_state_update_count, 1
        )


if __name__ == "__main__":
    unittest.main()
