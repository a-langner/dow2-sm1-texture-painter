import unittest
from unittest.mock import patch

from src.color_pattern_handler import PatternNotFoundError
from src.frame_main import ArmyPainter


class FakePatternFrame:
    def __init__(self, selected_name, user_created, neighbor="Neighbor"):
        self.selected_name = selected_name
        self.user_created = user_created
        self.neighbor = neighbor
        self.load_count = 0
        self.selected_names = []
        self.delete_state_update_count = 0

    def get_selected_pattern_name(self):
        return self.selected_name

    def is_selected_pattern_user(self):
        return self.user_created

    def get_selected_neighbor_pattern_name(self):
        return self.neighbor

    def load_pattern_list(self):
        self.load_count += 1

    def select_pattern(self, pattern_name):
        self.selected_names.append(pattern_name)

    def update_delete_button_state(self):
        self.delete_state_update_count += 1


class FakePainter:
    def __init__(self, selected_name, user_created, neighbor="Neighbor"):
        self.frame_army_pattern = FakePatternFrame(
            selected_name, user_created, neighbor
        )


class PatternDeletionGuiTests(unittest.TestCase):
    @patch("src.frame_main.src.color_pattern_handler.delete")
    @patch("src.frame_main.askyesno")
    def test_no_selection_does_nothing(self, askyesno, delete):
        painter = FakePainter(None, False)

        ArmyPainter.delete_pattern(painter)

        askyesno.assert_not_called()
        delete.assert_not_called()

    @patch("src.frame_main.src.color_pattern_handler.delete")
    @patch("src.frame_main.askyesno")
    def test_builtin_selection_cannot_be_deleted(self, askyesno, delete):
        painter = FakePainter("Blood Ravens", False)

        ArmyPainter.delete_pattern(painter)

        askyesno.assert_not_called()
        delete.assert_not_called()
        self.assertEqual(
            painter.frame_army_pattern.delete_state_update_count, 1
        )

    @patch("src.frame_main.src.color_pattern_handler.delete")
    @patch("src.frame_main.askyesno", return_value=False)
    def test_cancelled_confirmation_keeps_pattern(self, askyesno, delete):
        painter = FakePainter("Custom", True)

        ArmyPainter.delete_pattern(painter)

        delete.assert_not_called()
        self.assertEqual(painter.frame_army_pattern.load_count, 0)

    @patch("src.frame_main.showerror")
    @patch("src.frame_main.src.color_pattern_handler.delete")
    @patch("src.frame_main.askyesno", return_value=True)
    def test_success_reloads_and_selects_neighbor(
        self, askyesno, delete, showerror
    ):
        painter = FakePainter("Custom", True, neighbor="Next Pattern")

        ArmyPainter.delete_pattern(painter)

        delete.assert_called_once_with("Custom")
        showerror.assert_not_called()
        self.assertEqual(painter.frame_army_pattern.load_count, 1)
        self.assertEqual(
            painter.frame_army_pattern.selected_names, ["Next Pattern"]
        )

    @patch("src.frame_main.showerror")
    @patch(
        "src.frame_main.src.color_pattern_handler.delete",
        side_effect=PatternNotFoundError("Pattern was not found"),
    )
    @patch("src.frame_main.askyesno", return_value=True)
    def test_expected_delete_error_is_shown(
        self, askyesno, delete, showerror
    ):
        painter = FakePainter("Missing", True)

        ArmyPainter.delete_pattern(painter)

        showerror.assert_called_once_with(
            "Cannot Delete Pattern", "Pattern was not found"
        )
        self.assertEqual(painter.frame_army_pattern.load_count, 0)

    @patch("src.frame_main.LOGGER.exception")
    @patch("src.frame_main.showerror")
    @patch(
        "src.frame_main.src.color_pattern_handler.delete",
        side_effect=PermissionError("access denied"),
    )
    @patch("src.frame_main.askyesno", return_value=True)
    def test_persistence_failure_keeps_pattern_visible(
        self, askyesno, delete, showerror, log_exception
    ):
        painter = FakePainter("Still Visible", True)

        ArmyPainter.delete_pattern(painter)

        showerror.assert_called_once_with(
            "Cannot Delete Pattern",
            "The user-pattern file could not be updated.\n\n"
            "The pattern was not deleted.",
        )
        self.assertEqual(painter.frame_army_pattern.load_count, 0)
        self.assertEqual(painter.frame_army_pattern.selected_names, [])
        log_exception.assert_called_once()


if __name__ == "__main__":
    unittest.main()
