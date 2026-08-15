import unittest
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
import src.color_pattern_handler as pattern_handler
from fake_dialog_gateway import make_dialog_gateway
from src.color_pattern_handler import (
    PatternAlreadyExistsError,
    PatternNameConflictError,
)
from src.frame_main import ArmyPainter
from src.widget import PatternSelection

STORED_COLORS = ["#112233", "#445566", "#778899", "#aabbcc"]
DIRTY_COLORS = ["#010203", "#141516", "#272829", "#3a3b3c"]


class FakePatternList:
    def __init__(self, selection):
        self.selection = selection
        self.load_calls = []

    def get_selected_pattern(self):
        return self.selection

    def load_pattern_list(self, preferred_pattern_name=None):
        self.load_calls.append(preferred_pattern_name)
        self.selection = PatternSelection(preferred_pattern_name, True)


class FakeColorChooser:
    def __init__(self):
        self.color_boxes = [{"bg": color} for color in DIRTY_COLORS]
        self.draw_count = 0

    def draw_rgb_value(self):
        self.draw_count += 1


class FakePainter:
    def __init__(self, selection):
        self.dialogs = make_dialog_gateway(self)
        self.frame_army_pattern = FakePatternList(selection)
        self.frame_color_chooser = FakeColorChooser()
        self.state_updates = []
        self.refresh_count = 0

    def update_pattern_action_states(self, selection=None):
        self.state_updates.append(selection)

    def refresh_workspace(self):
        self.refresh_count += 1

    def on_pattern_select(self):
        ArmyPainter.on_pattern_select(self)

    def apply_selected_pattern_colors(self, selection=None):
        return ArmyPainter.apply_selected_pattern_colors(self, selection)


class PatternDuplicateGuiTests(unittest.TestCase):
    @patch("src.frame_main.src.color_pattern_handler.save")
    @patch("src.dialog_gateway.simpledialog.askstring")
    @patch("src.frame_main.get_pattern_colors")
    def test_no_selection_does_nothing(self, get_colors, ask_name, save):
        painter = FakePainter(None)

        ArmyPainter.duplicate_selected_pattern(painter)

        get_colors.assert_not_called()
        ask_name.assert_not_called()
        save.assert_not_called()

    @patch("src.frame_main.src.color_pattern_handler.save")
    @patch("src.dialog_gateway.simpledialog.askstring", return_value=None)
    @patch("src.frame_main.get_pattern_colors", return_value=STORED_COLORS)
    def test_dialog_suggests_copy_name_and_cancel_does_not_save(
        self, get_colors, ask_name, save
    ):
        painter = FakePainter(PatternSelection("Original", False))

        ArmyPainter.duplicate_selected_pattern(painter)

        ask_name.assert_called_once_with(
            "Duplicate Pattern",
            "Pattern name:",
            initialvalue="Original Copy",
            parent=painter,
        )
        save.assert_not_called()

    @patch("src.frame_main.src.color_pattern_handler.save")
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="  Duplicate  ")
    @patch("src.frame_main.get_pattern_colors", return_value=STORED_COLORS)
    def test_success_uses_stored_not_dirty_colors_and_applies_duplicate(
        self, get_colors, ask_name, save
    ):
        painter = FakePainter(PatternSelection("Original", True))

        ArmyPainter.duplicate_selected_pattern(painter)

        save.assert_called_once_with(
            "Duplicate",
            STORED_COLORS,
            processing=pattern_handler.DEFAULT_PATTERN_PROCESSING,
        )
        self.assertEqual(painter.frame_army_pattern.load_calls, ["Duplicate"])
        self.assertEqual(
            painter.frame_army_pattern.selection,
            PatternSelection("Duplicate", True),
        )
        self.assertEqual(
            [box["bg"] for box in painter.frame_color_chooser.color_boxes],
            STORED_COLORS,
        )
        self.assertEqual(painter.frame_color_chooser.draw_count, 1)
        self.assertEqual(painter.refresh_count, 1)
        self.assertEqual(painter.state_updates, [PatternSelection("Duplicate", True)])

    def test_name_conflicts_are_reported_without_refresh(self):
        errors = (
            PatternNameConflictError("'Built-in' is a built-in pattern name"),
            PatternAlreadyExistsError("User pattern 'Existing' already exists"),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__), patch(
                "src.frame_main.get_pattern_colors", return_value=STORED_COLORS
            ), patch("src.dialog_gateway.simpledialog.askstring", return_value="Duplicate"), patch(
                "src.frame_main.src.color_pattern_handler.save", side_effect=error
            ), patch(
                "src.dialog_gateway.messagebox.showerror"
            ) as showerror:
                painter = FakePainter(PatternSelection("Original", True))

                ArmyPainter.duplicate_selected_pattern(painter)

                showerror.assert_called_once_with(
                    "Cannot Duplicate Pattern", str(error), parent=painter
                )
                self.assertEqual(painter.frame_army_pattern.load_calls, [])

    @patch("src.frame_main.LOGGER.exception")
    @patch("src.dialog_gateway.messagebox.showerror")
    @patch(
        "src.frame_main.src.color_pattern_handler.save",
        side_effect=OSError("simulated failure"),
    )
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="Duplicate")
    @patch("src.frame_main.get_pattern_colors", return_value=STORED_COLORS)
    def test_persistence_failure_is_logged_without_refreshing(
        self, get_colors, ask_name, save, showerror, log_exception
    ):
        painter = FakePainter(PatternSelection("Original", True))

        ArmyPainter.duplicate_selected_pattern(painter)

        log_exception.assert_called_once()
        showerror.assert_called_once_with(
            "Cannot Duplicate Pattern",
            "The Pattern could not be saved:\nsimulated failure",
            parent=painter,
        )
        self.assertEqual(painter.frame_army_pattern.load_calls, [])


if __name__ == "__main__":
    unittest.main()
