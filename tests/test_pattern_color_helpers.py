import unittest
from collections import OrderedDict

import test_support  # noqa: F401 - installs the user-data path redirect
import src.color_pattern_handler as pattern_handler
from src.color_pattern_handler import (
    InvalidPatternError,
    PatternNotFoundError,
    get_pattern_colors,
    pattern_colors_equal,
)
from src.frame_main import ArmyPainter


class PatternColorHelperTests(unittest.TestCase):
    def setUp(self):
        self.original_users = OrderedDict(pattern_handler.user_color_patterns)
        self.original_all = OrderedDict(pattern_handler.army_color_pattern)

    def tearDown(self):
        pattern_handler.user_color_patterns.clear()
        pattern_handler.user_color_patterns.update(self.original_users)
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(self.original_all)

    def test_stored_colors_follow_shared_key_order_not_mapping_order(self):
        pattern = OrderedDict(
            [
                ("extra_colour_name", "#aabbcc"),
                ("tint_colour_name", "#778899"),
                ("secondary_colour_name", "#445566"),
                ("primary_colour_name", "#112233"),
            ]
        )
        pattern_handler.user_color_patterns["Ordered"] = pattern
        pattern_handler.army_color_pattern["Ordered"] = pattern

        result = get_pattern_colors("  Ordered  ")

        self.assertEqual(result, ["#112233", "#445566", "#778899", "#aabbcc"])

    def test_unknown_stored_pattern_is_rejected(self):
        with self.assertRaisesRegex(PatternNotFoundError, "not found"):
            get_pattern_colors("Unknown")

    def test_comparison_normalizes_hexadecimal_letter_case(self):
        self.assertTrue(
            pattern_colors_equal(
                ["#AABBCC", "#DDEEFF", "#ABCDEF", "#FEDCBA"],
                ["#aabbcc", "#ddeeff", "#abcdef", "#fedcba"],
            )
        )
        self.assertFalse(
            pattern_colors_equal(
                ["#aabbcc", "#ddeeff", "#abcdef", "#fedcba"],
                ["#000000", "#ddeeff", "#abcdef", "#fedcba"],
            )
        )

    def test_comparison_reuses_persistence_validation(self):
        with self.assertRaises(InvalidPatternError):
            pattern_colors_equal(
                ["invalid", "#ddeeff", "#abcdef", "#fedcba"],
                ["#aabbcc", "#ddeeff", "#abcdef", "#fedcba"],
            )

    def test_gui_helper_returns_current_boxes_in_canonical_order(self):
        painter = type(
            "FakePainter",
            (),
            {
                "frame_color_chooser": type(
                    "Chooser",
                    (),
                    {
                        "color_boxes": [
                            {"bg": "#112233"},
                            {"bg": "#445566"},
                            {"bg": "#778899"},
                            {"bg": "#aabbcc"},
                        ]
                    },
                )()
            },
        )()

        self.assertEqual(
            ArmyPainter.get_current_pattern_colors(painter),
            ["#112233", "#445566", "#778899", "#aabbcc"],
        )


if __name__ == "__main__":
    unittest.main()
