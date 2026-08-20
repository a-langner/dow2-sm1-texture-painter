import unittest

from src.blend_mode import BlendMode, IMPLEMENTED_BLEND_MODES
from src.constant import ColorOps


class BlendModeTests(unittest.TestCase):
    def test_all_modes_have_stable_ids_and_display_names(self):
        expected = {
            "normal": "Normal",
            "multiply": "Multiply",
            "screen": "Screen",
            "overlay": "Overlay",
            "soft_light": "Soft Light",
            "hard_light": "Hard Light",
            "color": "Color",
            "linear_burn": "Linear Burn",
            "linear_dodge": "Linear Dodge (Add)",
            "darken": "Darken",
            "lighten": "Lighten",
            "color_burn": "Color Burn",
        }
        self.assertEqual(
            {mode.value: mode.display_name for mode in BlendMode},
            expected,
        )

    def test_parser_accepts_stable_ids_and_legacy_display_names(self):
        for mode in BlendMode:
            with self.subTest(mode=mode):
                self.assertIs(BlendMode.parse(mode.value), mode)
                self.assertIs(BlendMode.parse(mode.display_name), mode)
                self.assertIs(BlendMode.parse(mode), mode)

    def test_parser_is_case_insensitive_and_rejects_unknown_values(self):
        self.assertIs(BlendMode.parse(" OVERLAY "), BlendMode.OVERLAY)
        self.assertIs(BlendMode.parse("linear dodge (add)"), BlendMode.LINEAR_DODGE)
        with self.assertRaisesRegex(ValueError, "Unknown blend mode"):
            BlendMode.parse("difference")

    def test_legacy_color_ops_name_is_the_authoritative_enum(self):
        self.assertIs(ColorOps, BlendMode)

    def test_only_implemented_pixel_modes_are_exposed(self):
        self.assertEqual(
            IMPLEMENTED_BLEND_MODES,
            (
                BlendMode.OVERLAY,
                BlendMode.SCREEN,
                BlendMode.MULTIPLY,
                BlendMode.NORMAL,
                BlendMode.SOFT_LIGHT,
                BlendMode.HARD_LIGHT,
                BlendMode.COLOR,
                BlendMode.LINEAR_BURN,
                BlendMode.LINEAR_DODGE,
            ),
        )
