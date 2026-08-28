import unittest
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from fake_dialog_gateway import make_dialog_gateway
from src.color_pattern_handler import (
    PatternAlreadyExistsError,
    PatternNameConflictError,
    UserPatternPersistenceError,
)
from src.frame_main import ArmyPainter
from src.widget import PatternSelection

COLORS = ["#112233", "#445566", "#778899", "#aabbcc"]


class FakePatternList:
    def __init__(self, selection):
        self.selection = selection
        self.load_calls = []

    def get_selected_pattern(self):
        return self.selection

    def load_pattern_list(self, preferred_pattern_name=None):
        self.load_calls.append(preferred_pattern_name)
        self.selection = PatternSelection(preferred_pattern_name, True)


class FakePainter:
    def __init__(self, selection):
        self.dialogs = make_dialog_gateway(self)
        self.frame_army_pattern = FakePatternList(selection)
        self.frame_color_chooser = type(
            "ColorChooser",
            (),
            {"color_boxes": [{"bg": color} for color in COLORS]},
        )()
        self.state_updates = []

    def update_pattern_action_states(self, selection=None):
        self.state_updates.append(selection)


class PatternRenameGuiTests(unittest.TestCase):
    @patch("src.frame_main.src.color_pattern_handler.rename_user_pattern")
    @patch("src.dialog_gateway.simpledialog.askstring")
    def test_no_selection_does_nothing(self, ask_name, rename):
        painter = FakePainter(None)

        ArmyPainter.rename_selected_pattern(painter)

        ask_name.assert_not_called()
        rename.assert_not_called()

    @patch("src.frame_main.src.color_pattern_handler.rename_user_pattern")
    @patch("src.dialog_gateway.simpledialog.askstring")
    def test_builtin_selection_is_not_renamed(self, ask_name, rename):
        selection = PatternSelection("Built-in", False)
        painter = FakePainter(selection)

        ArmyPainter.rename_selected_pattern(painter)

        ask_name.assert_not_called()
        rename.assert_not_called()
        self.assertEqual(painter.state_updates, [selection])

    @patch("src.frame_main.src.color_pattern_handler.rename_user_pattern")
    @patch("src.dialog_gateway.simpledialog.askstring", return_value=None)
    def test_dialog_is_prefilled_and_cancel_does_nothing(self, ask_name, rename):
        painter = FakePainter(PatternSelection("Current Name", True))

        ArmyPainter.rename_selected_pattern(painter)

        ask_name.assert_called_once_with(
            "Rename Pattern",
            "Pattern name:",
            initialvalue="Current Name",
            parent=painter,
        )
        rename.assert_not_called()
        self.assertEqual(painter.frame_army_pattern.load_calls, [])

    @patch("src.dialog_gateway.messagebox.showerror")
    @patch("src.frame_main.src.color_pattern_handler.rename_user_pattern")
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="   ")
    def test_empty_name_is_rejected(self, ask_name, rename, showerror):
        painter = FakePainter(PatternSelection("Current", True))

        ArmyPainter.rename_selected_pattern(painter)

        rename.assert_not_called()
        showerror.assert_called_once_with(
            "Cannot Rename Pattern",
            "Pattern name must not be empty",
            parent=painter,
        )

    @patch("src.frame_main.src.color_pattern_handler.rename_user_pattern")
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="  Same Name  ")
    def test_same_normalized_name_closes_without_writing(self, ask_name, rename):
        selection = PatternSelection("Same Name", True)
        painter = FakePainter(selection)

        ArmyPainter.rename_selected_pattern(painter)

        rename.assert_not_called()
        self.assertEqual(painter.frame_army_pattern.load_calls, [])
        self.assertEqual(painter.state_updates, [selection])

    @patch(
        "src.frame_main.src.color_pattern_handler.rename_user_pattern",
        return_value="New Name",
    )
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="  New Name  ")
    def test_success_refreshes_once_and_selects_normalized_internal_name(
        self, ask_name, rename
    ):
        painter = FakePainter(PatternSelection("Old Name", True))
        colors_before = [box["bg"] for box in painter.frame_color_chooser.color_boxes]

        ArmyPainter.rename_selected_pattern(painter)

        rename.assert_called_once_with("Old Name", "New Name")
        self.assertEqual(painter.frame_army_pattern.load_calls, ["New Name"])
        self.assertEqual(
            painter.frame_army_pattern.get_selected_pattern(),
            PatternSelection("New Name", True),
        )
        self.assertEqual(
            [box["bg"] for box in painter.frame_color_chooser.color_boxes],
            colors_before,
        )
        self.assertEqual(painter.state_updates, [None])

    @patch("src.frame_main.src.color_pattern_handler.is_user_pattern", return_value=True)
    @patch(
        "src.frame_main.src.color_pattern_handler.rename_user_pattern",
        return_value="Renamed Target",
    )
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="Renamed Target")
    def test_context_rename_preserves_active_pattern(
        self, ask_name, rename, _is_user_pattern
    ):
        painter = FakePainter(PatternSelection("Active Pattern", True))

        ArmyPainter.rename_selected_pattern(painter, "Right Clicked")

        rename.assert_called_once_with("Right Clicked", "Renamed Target")
        self.assertEqual(painter.frame_army_pattern.load_calls, ["Active Pattern"])

    def test_builtin_and_user_conflicts_show_specific_handler_messages(self):
        errors = (
            PatternNameConflictError("'Built-in' is a built-in pattern name"),
            PatternAlreadyExistsError("User pattern 'Existing' already exists"),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__), patch(
                "src.dialog_gateway.simpledialog.askstring", return_value="Replacement"
            ), patch(
                "src.frame_main.src.color_pattern_handler.rename_user_pattern",
                side_effect=error,
            ), patch(
                "src.dialog_gateway.messagebox.showerror"
            ) as showerror:
                painter = FakePainter(PatternSelection("Current", True))

                ArmyPainter.rename_selected_pattern(painter)

                showerror.assert_called_once_with(
                    "Cannot Rename Pattern", str(error), parent=painter
                )
                self.assertEqual(painter.frame_army_pattern.load_calls, [])
                self.assertEqual(
                    painter.frame_army_pattern.selection,
                    PatternSelection("Current", True),
                )
                self.assertEqual(
                    painter.state_updates, [PatternSelection("Current", True)]
                )

    @patch("src.frame_main.LOGGER.exception")
    @patch("src.dialog_gateway.messagebox.showerror")
    @patch(
        "src.frame_main.src.color_pattern_handler.rename_user_pattern",
        side_effect=UserPatternPersistenceError("simulated failure"),
    )
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="New Name")
    def test_persistence_failure_is_logged_without_refreshing(
        self, ask_name, rename, showerror, log_exception
    ):
        selection = PatternSelection("Old Name", True)
        painter = FakePainter(selection)
        colors_before = [
            box["bg"] for box in painter.frame_color_chooser.color_boxes
        ]

        ArmyPainter.rename_selected_pattern(painter)

        log_exception.assert_called_once()
        showerror.assert_called_once_with(
            "Cannot Rename Pattern",
            "The Pattern could not be saved:\nsimulated failure",
            parent=painter,
        )
        self.assertEqual(painter.frame_army_pattern.load_calls, [])
        self.assertIs(painter.frame_army_pattern.selection, selection)
        self.assertEqual(
            [box["bg"] for box in painter.frame_color_chooser.color_boxes],
            colors_before,
        )
        self.assertEqual(painter.state_updates, [selection])

    @patch(
        "src.frame_main.src.color_pattern_handler.rename_user_pattern",
        side_effect=RuntimeError("programming bug"),
    )
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="New Name")
    def test_unexpected_rename_error_is_not_suppressed(self, ask_name, rename):
        painter = FakePainter(PatternSelection("Old Name", True))

        with self.assertRaisesRegex(RuntimeError, "programming bug"):
            ArmyPainter.rename_selected_pattern(painter)


if __name__ == "__main__":
    unittest.main()
