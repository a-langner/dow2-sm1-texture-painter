import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import (
    WINDOW_INITIAL_SCALE,
    calculate_initial_window_size,
)


class InitialWindowGeometryTests(unittest.TestCase):
    def test_scales_initial_size_when_screen_has_room(self):
        result = calculate_initial_window_size(800, 600, 2560, 1600)

        self.assertEqual(
            result,
            (
                round(800 * WINDOW_INITIAL_SCALE),
                round(600 * WINDOW_INITIAL_SCALE),
            ),
        )

    def test_clamps_initial_size_to_ninety_percent_of_screen(self):
        result = calculate_initial_window_size(1000, 800, 1200, 900)

        self.assertEqual(result, (1080, 810))

    def test_clamping_never_changes_existing_minimum_boundary(self):
        result = calculate_initial_window_size(1000, 800, 900, 700)

        self.assertEqual(result, (1000, 800))


if __name__ == "__main__":
    unittest.main()
