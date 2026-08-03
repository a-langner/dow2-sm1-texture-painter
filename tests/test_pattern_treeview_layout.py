import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.widget import FramePatternList, calculate_pattern_separator_x


class FakeTree:
    def __init__(self):
        self.scroll_calls = []

    def yview_scroll(self, number, what):
        self.scroll_calls.append((number, what))


class PatternTreeviewLayoutTests(unittest.TestCase):
    def test_separator_tracks_marker_boundary_when_tree_resizes(self):
        narrow = calculate_pattern_separator_x(0, 200, 28, 1)
        wide = calculate_pattern_separator_x(0, 500, 28, 1)

        self.assertEqual(narrow, 171)
        self.assertEqual(wide, 471)

    def test_separator_position_includes_tree_offset(self):
        result = calculate_pattern_separator_x(6, 300, 28, 1)

        self.assertEqual(result, 277)

    def test_x11_wheel_events_scroll_tree_through_separator(self):
        frame = object.__new__(FramePatternList)
        frame.tree = FakeTree()

        up_result = frame._scroll_tree_up_through_separator(None)
        down_result = frame._scroll_tree_down_through_separator(None)

        self.assertEqual(frame.tree.scroll_calls, [(-1, "units"), (1, "units")])
        self.assertEqual(up_result, "break")
        self.assertEqual(down_result, "break")


if __name__ == "__main__":
    unittest.main()
