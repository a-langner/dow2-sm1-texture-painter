import unittest

from src.recent_colors import (
    MAX_RECENT_COLORS,
    add_recent_color,
    validate_recent_colors,
)


class RecentColorsTests(unittest.TestCase):
    def test_confirmed_colors_are_newest_first_deduplicated_and_capped(self):
        colors = ()
        for value in range(MAX_RECENT_COLORS + 3):
            colors = add_recent_color(colors, (value, value, value))

        self.assertEqual(len(colors), MAX_RECENT_COLORS)
        self.assertEqual(colors[0], (MAX_RECENT_COLORS + 2,) * 3)
        self.assertEqual(colors[-1], (3, 3, 3))

        moved = add_recent_color(colors, (8, 8, 8))

        self.assertEqual(moved[0], (8, 8, 8))
        self.assertEqual(moved.count((8, 8, 8)), 1)
        self.assertEqual(len(moved), MAX_RECENT_COLORS)

    def test_persisted_entries_are_validated_deduplicated_and_capped(self):
        persisted = [
            [150, 12, 9],
            "malformed",
            [150, 12, 9],
            [-1, 0, 0],
            [0, 256, 0],
            [True, 0, 0],
            [1, 2],
        ]
        persisted.extend([[value, value, value] for value in range(20)])

        colors = validate_recent_colors(persisted)

        self.assertEqual(len(colors), MAX_RECENT_COLORS)
        self.assertEqual(colors[0], (150, 12, 9))
        self.assertEqual(colors[1:], tuple((value, value, value) for value in range(11)))

    def test_missing_or_malformed_history_uses_empty_history(self):
        for value in (None, "invalid", {}, ["invalid"]):
            with self.subTest(value=value):
                self.assertEqual(validate_recent_colors(value), ())
