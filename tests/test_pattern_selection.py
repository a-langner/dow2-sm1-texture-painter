import unittest
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.widget import PatternSelection


class FakePatternFrame:
    def __init__(self, selected_name):
        self.selected_name = selected_name
        self.delete_state_update_count = 0

    def get_selected_pattern_name(self):
        return self.selected_name

    def get_selected_pattern(self):
        if self.selected_name is None:
            return None
        return PatternSelection(self.selected_name, False)

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

    def update_pattern_menu_state(self):
        pass

    def update_pattern_command_states(self, selection=None):
        self.frame_army_pattern.update_delete_button_state()


class PatternSelectionTests(unittest.TestCase):
    def test_applies_selected_pattern_colors_and_refreshes(self):
        colors = ["#112233", "#445566", "#778899", "#aabbcc"]
        painter = FakePainter("Internal Name")

        with patch("src.frame_main.get_pattern_colors", return_value=colors):
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
