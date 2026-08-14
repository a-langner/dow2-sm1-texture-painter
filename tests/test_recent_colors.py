import unittest

from src.recent_colors import MAX_RECENT_COLORS, add_recent_color


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
