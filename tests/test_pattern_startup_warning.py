import unittest
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_pattern_handler import (
    InvalidUserPatternFileError,
    UserPatternLoadIssue,
)
from src.frame_main import ArmyPainter


class FakePainter:
    def __init__(self):
        self.user_pattern_warning_shown = False


class PatternStartupWarningTests(unittest.TestCase):
    @patch("src.frame_main.showwarning")
    def test_warning_is_concise_contains_path_and_is_shown_once(
        self, showwarning
    ):
        affected_path = Path("C:/Users/Test/AppData/user_patterns.json")
        issue = UserPatternLoadIssue(
            affected_path,
            InvalidUserPatternFileError("detailed parser error"),
        )
        painter = FakePainter()

        with patch(
            "src.frame_main.src.color_pattern_handler.user_pattern_load_issue",
            issue,
        ):
            ArmyPainter.show_user_pattern_load_warning(painter)
            ArmyPainter.show_user_pattern_load_warning(painter)

        showwarning.assert_called_once()
        title, message = showwarning.call_args.args
        self.assertEqual(title, "User Patterns Not Loaded")
        self.assertIn(str(affected_path), message)
        self.assertIn("Built-in patterns are still available", message)
        self.assertNotIn("Traceback", message)
        self.assertNotIn("detailed parser error", message)

    @patch("src.frame_main.showwarning")
    def test_no_warning_without_startup_issue(self, showwarning):
        painter = FakePainter()

        with patch(
            "src.frame_main.src.color_pattern_handler.user_pattern_load_issue",
            None,
        ):
            ArmyPainter.show_user_pattern_load_warning(painter)

        showwarning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
