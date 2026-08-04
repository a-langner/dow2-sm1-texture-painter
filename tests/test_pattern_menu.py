import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import (
    PATTERN_EXPORT_MENU_LABEL,
    ArmyPainter,
)
from src.widget import (
    PatternSelection,
    pattern_command_states,
    pattern_name_to_restore,
)


class FakePatternList:
    def __init__(self, selected_name=None):
        self.selected_name = selected_name

    def get_selected_pattern_name(self):
        return self.selected_name

    def get_selected_pattern(self):
        if self.selected_name is None:
            return None
        return PatternSelection(
            self.selected_name, self.selected_name == "User-created"
        )

    def update_delete_button_state(self, selection=None):
        self.delete_state = pattern_command_states(selection)[1]


class FakeMenu:
    def __init__(self):
        self.configurations = []

    def entryconfig(self, entry, **options):
        self.configurations.append((entry, options))


class FakePainter:
    def __init__(self, selected_name=None):
        self.frame_army_pattern = FakePatternList(selected_name)
        self.pattern_menu = FakeMenu()


class PatternMenuStateTests(unittest.TestCase):
    def test_command_policy_covers_no_builtin_and_user_selection(self):
        self.assertEqual(pattern_command_states(None), ("disabled", "disabled"))
        self.assertEqual(
            pattern_command_states(PatternSelection("Built-in", False)),
            ("normal", "disabled"),
        )
        self.assertEqual(
            pattern_command_states(PatternSelection("Custom", True)),
            ("normal", "normal"),
        )

    def test_refresh_selection_uses_internal_name_and_handles_removal(self):
        names = {"Built-in", "Custom"}
        self.assertEqual(pattern_name_to_restore(None, "Built-in", names), "Built-in")
        self.assertEqual(pattern_name_to_restore("Custom", "Built-in", names), "Custom")
        self.assertIsNone(pattern_name_to_restore(None, "Deleted", names))

    def test_export_is_disabled_without_selection(self):
        painter = FakePainter()

        ArmyPainter.update_pattern_command_states(painter)

        self.assertEqual(
            painter.pattern_menu.configurations,
            [(PATTERN_EXPORT_MENU_LABEL, {"state": "disabled"})],
        )
        self.assertEqual(painter.frame_army_pattern.delete_state, "disabled")

    def test_export_is_enabled_for_any_internal_pattern_name(self):
        for pattern_name in ("Built-in", "User-created"):
            with self.subTest(pattern_name=pattern_name):
                painter = FakePainter(pattern_name)

                ArmyPainter.update_pattern_command_states(painter)

                self.assertEqual(
                    painter.pattern_menu.configurations,
                    [(PATTERN_EXPORT_MENU_LABEL, {"state": "normal"})],
                )
                expected_delete = (
                    "normal" if pattern_name == "User-created" else "disabled"
                )
                self.assertEqual(
                    painter.frame_army_pattern.delete_state, expected_delete
                )

    def test_export_returns_to_disabled_when_selection_is_cleared(self):
        painter = FakePainter("Selected")
        ArmyPainter.update_pattern_command_states(painter)
        painter.frame_army_pattern.selected_name = None

        ArmyPainter.update_pattern_command_states(painter)

        self.assertEqual(
            painter.pattern_menu.configurations[-1],
            (PATTERN_EXPORT_MENU_LABEL, {"state": "disabled"}),
        )
        self.assertEqual(painter.frame_army_pattern.delete_state, "disabled")


if __name__ == "__main__":
    unittest.main()
