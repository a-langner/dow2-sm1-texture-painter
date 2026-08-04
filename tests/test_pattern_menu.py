import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import (
    PATTERN_EXPORT_MENU_LABEL,
    ArmyPainter,
)


class FakePatternList:
    def __init__(self, selected_name=None):
        self.selected_name = selected_name

    def get_selected_pattern_name(self):
        return self.selected_name


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
    def test_export_is_disabled_without_selection(self):
        painter = FakePainter()

        ArmyPainter.update_pattern_menu_state(painter)

        self.assertEqual(
            painter.pattern_menu.configurations,
            [(PATTERN_EXPORT_MENU_LABEL, {"state": "disabled"})],
        )

    def test_export_is_enabled_for_any_internal_pattern_name(self):
        for pattern_name in ("Built-in", "User-created"):
            with self.subTest(pattern_name=pattern_name):
                painter = FakePainter(pattern_name)

                ArmyPainter.update_pattern_menu_state(painter)

                self.assertEqual(
                    painter.pattern_menu.configurations,
                    [(PATTERN_EXPORT_MENU_LABEL, {"state": "normal"})],
                )

    def test_export_returns_to_disabled_when_selection_is_cleared(self):
        painter = FakePainter("Selected")
        ArmyPainter.update_pattern_menu_state(painter)
        painter.frame_army_pattern.selected_name = None

        ArmyPainter.update_pattern_menu_state(painter)

        self.assertEqual(
            painter.pattern_menu.configurations[-1],
            (PATTERN_EXPORT_MENU_LABEL, {"state": "disabled"}),
        )


if __name__ == "__main__":
    unittest.main()
