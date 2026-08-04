import tkinter as tk
import unittest
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_pattern_handler import (
    PatternNotFoundError,
    UserPatternPersistenceError,
)
from src.frame_main import ArmyPainter
from src.widget import PatternSelection

STORED_COLORS = ["#112233", "#445566", "#778899", "#aabbcc"]
UPDATED_COLORS = ["#010203", "#141516", "#272829", "#3a3b3c"]


class FakePatternList:
    def __init__(self, selection):
        self.selection = selection

    def get_selected_pattern(self):
        return self.selection


class FakePainter:
    def __init__(self, selection, colors=UPDATED_COLORS):
        self.frame_army_pattern = FakePatternList(selection)
        self.frame_color_chooser = type(
            "ColorChooser",
            (),
            {"color_boxes": [{"bg": color} for color in colors]},
        )()
        self.state_updates = []

    def get_current_pattern_colors(self):
        return ArmyPainter.get_current_pattern_colors(self)

    def update_pattern_action_states(self, selection=None):
        self.state_updates.append(selection)


class PatternUpdateGuiTests(unittest.TestCase):
    @patch("src.frame_main.src.color_pattern_handler.update_user_pattern")
    @patch("src.frame_main.askyesno")
    def test_no_selection_does_nothing(self, confirm, update):
        painter = FakePainter(None)

        ArmyPainter.update_selected_pattern(painter)

        confirm.assert_not_called()
        update.assert_not_called()

    @patch("src.frame_main.src.color_pattern_handler.update_user_pattern")
    @patch("src.frame_main.askyesno")
    def test_builtin_selection_is_not_updated(self, confirm, update):
        selection = PatternSelection("Built-in", False)
        painter = FakePainter(selection)

        ArmyPainter.update_selected_pattern(painter)

        confirm.assert_not_called()
        update.assert_not_called()
        self.assertEqual(painter.state_updates, [selection])

    @patch("src.frame_main.src.color_pattern_handler.update_user_pattern")
    @patch("src.frame_main.askyesno")
    @patch("src.frame_main.get_pattern_colors", return_value=STORED_COLORS)
    def test_unchanged_colors_do_not_prompt_or_write(self, get_colors, confirm, update):
        selection = PatternSelection("Custom", True)
        painter = FakePainter(selection, colors=STORED_COLORS)

        ArmyPainter.update_selected_pattern(painter)

        get_colors.assert_called_once_with("Custom")
        confirm.assert_not_called()
        update.assert_not_called()
        self.assertEqual(painter.state_updates, [selection])

    @patch("src.frame_main.src.color_pattern_handler.update_user_pattern")
    @patch("src.frame_main.askyesno", return_value=False)
    @patch("src.frame_main.get_pattern_colors", return_value=STORED_COLORS)
    def test_cancelled_confirmation_does_not_write(self, get_colors, confirm, update):
        painter = FakePainter(PatternSelection("Custom", True))

        ArmyPainter.update_selected_pattern(painter)

        confirm.assert_called_once_with(
            "Update Pattern",
            'Update pattern "Custom" with the current colors?',
            default=tk.NO,
            parent=painter,
        )
        update.assert_not_called()
        self.assertEqual(painter.state_updates, [])

    @patch("src.frame_main.src.color_pattern_handler.update_user_pattern")
    @patch("src.frame_main.askyesno", return_value=True)
    @patch("src.frame_main.get_pattern_colors", return_value=STORED_COLORS)
    def test_confirmed_update_preserves_selection_and_current_gui_state(
        self, get_colors, confirm, update
    ):
        selection = PatternSelection("Custom", True)
        painter = FakePainter(selection)

        ArmyPainter.update_selected_pattern(painter)

        update.assert_called_once_with("Custom", UPDATED_COLORS)
        self.assertIs(painter.frame_army_pattern.selection, selection)
        self.assertEqual(
            [box["bg"] for box in painter.frame_color_chooser.color_boxes],
            UPDATED_COLORS,
        )
        self.assertEqual(painter.state_updates, [selection])

    @patch("src.frame_main.showerror")
    @patch(
        "src.frame_main.get_pattern_colors",
        side_effect=PatternNotFoundError("Pattern was not found"),
    )
    def test_expected_lookup_error_is_shown(self, get_colors, showerror):
        painter = FakePainter(PatternSelection("Missing", True))

        ArmyPainter.update_selected_pattern(painter)

        showerror.assert_called_once_with(
            "Cannot Update Pattern", "Pattern was not found", parent=painter
        )

    @patch("src.frame_main.LOGGER.exception")
    @patch("src.frame_main.showerror")
    @patch(
        "src.frame_main.src.color_pattern_handler.update_user_pattern",
        side_effect=UserPatternPersistenceError("simulated failure"),
    )
    @patch("src.frame_main.askyesno", return_value=True)
    @patch("src.frame_main.get_pattern_colors", return_value=STORED_COLORS)
    def test_persistence_failure_is_logged_and_reported(
        self, get_colors, confirm, update, showerror, log_exception
    ):
        painter = FakePainter(PatternSelection("Custom", True))

        ArmyPainter.update_selected_pattern(painter)

        log_exception.assert_called_once()
        showerror.assert_called_once_with(
            "Cannot Update Pattern",
            "The Pattern could not be saved:\nsimulated failure",
            parent=painter,
        )
        self.assertEqual(painter.state_updates, [])


if __name__ == "__main__":
    unittest.main()
