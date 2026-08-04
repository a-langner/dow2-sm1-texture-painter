import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import (
    PATTERN_COLLECTION_EXPORT_MENU_LABEL,
    PATTERN_EXPORT_MENU_LABEL,
    ArmyPainter,
)
from src.widget import (
    FramePatternList,
    PatternSelection,
    pattern_action_states,
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

    def set_pattern_action_states(self, states):
        self.action_states = states


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
        no_selection = pattern_action_states(None)
        self.assertEqual(
            (
                no_selection.save_new,
                no_selection.update,
                no_selection.rename,
                no_selection.delete,
                no_selection.export_selected,
            ),
            ("normal", "disabled", "disabled", "disabled", "disabled"),
        )

        builtin = pattern_action_states(PatternSelection("Built-in", False))
        self.assertEqual(
            (builtin.update, builtin.rename, builtin.delete, builtin.export_selected),
            ("disabled", "disabled", "disabled", "normal"),
        )

        user = pattern_action_states(PatternSelection("Custom", True))
        self.assertEqual(
            (user.update, user.rename, user.delete, user.export_selected),
            ("disabled", "normal", "normal", "normal"),
        )

        modified_user = pattern_action_states(
            PatternSelection("Custom", True), modified=True
        )
        self.assertEqual(modified_user.update, "normal")

    def test_refresh_selection_uses_internal_name_and_handles_removal(self):
        names = {"Built-in", "Custom"}
        self.assertEqual(pattern_name_to_restore(None, "Built-in", names), "Built-in")
        self.assertEqual(pattern_name_to_restore("Custom", "Built-in", names), "Custom")
        self.assertIsNone(pattern_name_to_restore(None, "Deleted", names))

    def test_export_is_disabled_without_selection(self):
        painter = FakePainter()

        ArmyPainter.update_pattern_action_states(painter)

        self.assertEqual(
            painter.pattern_menu.configurations,
            [
                (PATTERN_EXPORT_MENU_LABEL, {"state": "disabled"}),
                (
                    PATTERN_COLLECTION_EXPORT_MENU_LABEL,
                    {"state": "disabled"},
                ),
            ],
        )
        self.assertEqual(painter.frame_army_pattern.action_states.delete, "disabled")

    def test_export_is_enabled_for_any_internal_pattern_name(self):
        for pattern_name in ("Built-in", "User-created"):
            with self.subTest(pattern_name=pattern_name):
                painter = FakePainter(pattern_name)

                ArmyPainter.update_pattern_action_states(painter)

                self.assertEqual(
                    painter.pattern_menu.configurations[0],
                    (PATTERN_EXPORT_MENU_LABEL, {"state": "normal"}),
                )
                expected_delete = (
                    "normal" if pattern_name == "User-created" else "disabled"
                )
                self.assertEqual(
                    painter.frame_army_pattern.action_states.delete,
                    expected_delete,
                )

    def test_export_returns_to_disabled_when_selection_is_cleared(self):
        painter = FakePainter("Selected")
        ArmyPainter.update_pattern_action_states(painter)
        painter.frame_army_pattern.selected_name = None

        ArmyPainter.update_pattern_action_states(painter)

        self.assertEqual(
            painter.pattern_menu.configurations[-2],
            (PATTERN_EXPORT_MENU_LABEL, {"state": "disabled"}),
        )
        self.assertEqual(painter.frame_army_pattern.action_states.delete, "disabled")

    def test_export_all_state_depends_on_user_patterns_not_selection(self):
        for selected_name in (None, "Built-in"):
            with self.subTest(selected_name=selected_name), patch(
                "src.frame_main.src.color_pattern_handler.has_user_patterns",
                return_value=True,
            ):
                painter = FakePainter(selected_name)

                ArmyPainter.update_pattern_action_states(painter)

                self.assertEqual(
                    painter.pattern_menu.configurations[-1],
                    (
                        PATTERN_COLLECTION_EXPORT_MENU_LABEL,
                        {"state": "normal"},
                    ),
                )

    def test_pattern_list_refresh_invokes_state_change_callback(self):
        tree = SimpleNamespace(clear_patterns=Mock(), insert_pattern=Mock())
        callback = Mock()
        frame = SimpleNamespace(
            tree=tree,
            state_change_callback=callback,
            get_selected_pattern=Mock(return_value=None),
        )

        with patch("src.widget.build_pattern_rows", return_value=[]):
            FramePatternList.load_pattern_list(frame)

        callback.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
