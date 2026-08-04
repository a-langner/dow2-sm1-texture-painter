import unittest
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_pattern_handler import (
    InvalidPatternError,
    PatternAlreadyExistsError,
    PatternNameConflictError,
)
from src.frame_main import ArmyPainter


class FakePatternFrame:
    def __init__(self):
        self.load_count = 0
        self.selected_names = []

    def load_pattern_list(self, preferred_pattern_name=None):
        self.load_count += 1
        if preferred_pattern_name is not None:
            self.select_pattern(preferred_pattern_name)

    def select_pattern(self, pattern_name):
        self.selected_names.append(pattern_name)
        return "new-item"


class FakePainter:
    def __init__(self):
        self.frame_color_chooser = type(
            "ColorChooser",
            (),
            {
                "color_boxes": [
                    {"bg": "#112233"},
                    {"bg": "#445566"},
                    {"bg": "#778899"},
                    {"bg": "#aabbcc"},
                ]
            },
        )()
        self.frame_army_pattern = FakePatternFrame()

    def update_pattern_menu_state(self):
        pass

    def update_pattern_command_states(self, selection=None):
        pass


class PatternSavingGuiTests(unittest.TestCase):
    @patch("src.frame_main.showerror")
    @patch("src.frame_main.src.color_pattern_handler.save")
    @patch("src.frame_main.askstring", return_value=None)
    def test_cancel_does_nothing(self, ask, save, showerror):
        painter = FakePainter()

        ArmyPainter.save_pattern(painter)

        save.assert_not_called()
        showerror.assert_not_called()
        self.assertEqual(painter.frame_army_pattern.load_count, 0)

    @patch("src.frame_main.showerror")
    @patch("src.frame_main.src.color_pattern_handler.save")
    @patch("src.frame_main.askstring", return_value="   ")
    def test_empty_name_shows_error(self, ask, save, showerror):
        painter = FakePainter()

        ArmyPainter.save_pattern(painter)

        save.assert_not_called()
        showerror.assert_called_once_with(
            "Cannot Save Pattern", "Pattern name cannot be empty."
        )
        self.assertEqual(painter.frame_army_pattern.load_count, 0)

    def test_expected_handler_errors_are_shown(self):
        errors = [
            InvalidPatternError("Invalid colors"),
            PatternAlreadyExistsError("Already exists"),
            PatternNameConflictError("Built-in name"),
        ]

        for error in errors:
            with self.subTest(error=type(error).__name__):
                painter = FakePainter()
                with patch(
                    "src.frame_main.askstring", return_value="Name"
                ), patch(
                    "src.frame_main.src.color_pattern_handler.save",
                    side_effect=error,
                ), patch(
                    "src.frame_main.showerror"
                ) as showerror:
                    ArmyPainter.save_pattern(painter)

                showerror.assert_called_once_with(
                    "Cannot Save Pattern", str(error)
                )
                self.assertEqual(painter.frame_army_pattern.load_count, 0)

    @patch("src.frame_main.showerror")
    @patch("src.frame_main.src.color_pattern_handler.save")
    @patch("src.frame_main.askstring", return_value="  Custom Pattern  ")
    def test_success_reloads_and_selects_internal_name(
        self, ask, save, showerror
    ):
        painter = FakePainter()
        colors_before = [
            box["bg"] for box in painter.frame_color_chooser.color_boxes
        ]

        ArmyPainter.save_pattern(painter)

        save.assert_called_once_with(
            name="Custom Pattern", colors=colors_before
        )
        showerror.assert_not_called()
        self.assertEqual(painter.frame_army_pattern.load_count, 1)
        self.assertEqual(
            painter.frame_army_pattern.selected_names, ["Custom Pattern"]
        )
        self.assertEqual(
            [box["bg"] for box in painter.frame_color_chooser.color_boxes],
            colors_before,
        )

    @patch("src.frame_main.LOGGER.exception")
    @patch("src.frame_main.showerror")
    @patch(
        "src.frame_main.src.color_pattern_handler.save",
        side_effect=PermissionError("access denied"),
    )
    @patch("src.frame_main.askstring", return_value="Custom Pattern")
    def test_persistence_failure_explains_pattern_was_not_saved(
        self, ask, save, showerror, log_exception
    ):
        painter = FakePainter()

        ArmyPainter.save_pattern(painter)

        showerror.assert_called_once_with(
            "Cannot Save Pattern",
            "The user-pattern file could not be updated.\n\n"
            "The pattern was not saved.",
        )
        self.assertEqual(painter.frame_army_pattern.load_count, 0)
        log_exception.assert_called_once()


if __name__ == "__main__":
    unittest.main()
