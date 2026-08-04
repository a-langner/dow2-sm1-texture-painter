import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.widget import (
    FramePatternList,
    calculate_pattern_separator_x,
    find_treeview_body_boundary,
)


class FakeTree:
    def __init__(self):
        self.scroll_calls = []
        self.region = "cell"
        self.cursor = None

    def yview_scroll(self, number, what):
        self.scroll_calls.append((number, what))

    def identify_region(self, x, y):
        return self.region

    def configure(self, cursor):
        self.cursor = cursor


class FakeEvent:
    x = 10
    y = 5


class FakeRegionTree:
    def __init__(self, boundary, body_region):
        self.boundary = boundary
        self.body_region = body_region

    def winfo_width(self):
        return 300

    def winfo_height(self):
        return 200

    def identify_region(self, x, y):
        return "heading" if y < self.boundary else self.body_region


class PatternTreeviewLayoutTests(unittest.TestCase):
    def test_header_boundary_uses_populated_tree_hit_testing(self):
        tree = FakeRegionTree(boundary=24, body_region="cell")

        self.assertEqual(find_treeview_body_boundary(tree), 24)

    def test_header_boundary_uses_empty_tree_hit_testing(self):
        tree = FakeRegionTree(boundary=27, body_region="nothing")

        self.assertEqual(find_treeview_body_boundary(tree), 27)

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

    def test_header_separator_press_drag_and_release_are_blocked(self):
        frame = object.__new__(FramePatternList)
        frame.tree = FakeTree()
        frame.tree.region = "separator"
        frame.header_separator_pressed = False
        event = FakeEvent()

        self.assertEqual(frame._block_header_separator_press(event), "break")
        frame.tree.region = "heading"
        self.assertEqual(frame._block_header_separator_drag(event), "break")
        self.assertEqual(frame._block_header_separator_release(event), "break")
        self.assertFalse(frame.header_separator_pressed)
        self.assertEqual(frame.tree.cursor, "arrow")

    def test_normal_tree_interactions_are_not_blocked(self):
        frame = object.__new__(FramePatternList)
        frame.tree = FakeTree()
        frame.header_separator_pressed = False
        event = FakeEvent()

        self.assertIsNone(frame._block_header_separator_press(event))
        self.assertIsNone(frame._block_header_separator_drag(event))
        self.assertIsNone(frame._block_header_separator_release(event))

    def test_cursor_is_local_and_restored_outside_separator(self):
        frame = object.__new__(FramePatternList)
        frame.tree = FakeTree()
        event = FakeEvent()
        frame.tree.region = "separator"

        self.assertEqual(frame._update_header_separator_cursor(event), "break")
        self.assertEqual(frame.tree.cursor, "arrow")

        frame.tree.region = "cell"
        self.assertIsNone(frame._update_header_separator_cursor(event))
        self.assertEqual(frame.tree.cursor, "")


if __name__ == "__main__":
    unittest.main()
