import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.widget import calculate_pattern_separator_x


class PatternTreeviewLayoutTests(unittest.TestCase):
    def test_separator_tracks_marker_boundary_when_tree_resizes(self):
        narrow = calculate_pattern_separator_x(0, 200, 28, 1)
        wide = calculate_pattern_separator_x(0, 500, 28, 1)

        self.assertEqual(narrow, 171)
        self.assertEqual(wide, 471)

    def test_separator_position_includes_tree_offset(self):
        result = calculate_pattern_separator_x(6, 300, 28, 1)

        self.assertEqual(result, 277)


if __name__ == "__main__":
    unittest.main()
