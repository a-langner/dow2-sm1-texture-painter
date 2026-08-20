import unittest

from PIL import Image

import test_support  # noqa: F401 - installs the user-data path redirect
from src.blend_mode import BlendMode
from src.render_settings import RenderSettings
from src.texture_renderer import TextureRenderer
from src.texture_set import TextureSet

ASYMMETRIC_BASE = (50, 100, 200)
ASYMMETRIC_BLEND = (200, 80, 40)

FULL_MASK_EXPECTED = {
    BlendMode.NORMAL: (200, 80, 40),
    BlendMode.MULTIPLY: (39, 31, 31),
    BlendMode.SCREEN: (211, 149, 209),
    BlendMode.OVERLAY: (78, 62, 162),
    BlendMode.SOFT_LIGHT: (72, 76, 169),
    BlendMode.HARD_LIGHT: (167, 62, 62),
    BlendMode.COLOR: (184, 64, 24),
    BlendMode.LINEAR_BURN: (0, 0, 0),
    BlendMode.LINEAR_DODGE: (250, 180, 240),
    BlendMode.DARKEN: (50, 80, 40),
    BlendMode.LIGHTEN: (200, 100, 200),
}

# Pillow's 8-bit paste interpolation at mask strength 128 determines rounding.
PARTIAL_MASK_EXPECTED = {
    BlendMode.NORMAL: (125, 90, 120),
    BlendMode.MULTIPLY: (44, 65, 115),
    BlendMode.SCREEN: (131, 125, 205),
    BlendMode.OVERLAY: (64, 81, 181),
    BlendMode.SOFT_LIGHT: (61, 88, 184),
    BlendMode.HARD_LIGHT: (109, 81, 131),
    BlendMode.COLOR: (117, 82, 112),
    BlendMode.LINEAR_BURN: (25, 50, 100),
    BlendMode.LINEAR_DODGE: (150, 140, 220),
    BlendMode.DARKEN: (50, 90, 120),
    BlendMode.LIGHTEN: (125, 100, 200),
}

EDGE_EXPECTED = {
    BlendMode.NORMAL: ((200, 80, 40), (200, 80, 40), (0, 0, 0), (255, 255, 255), (127, 127, 127)),
    BlendMode.MULTIPLY: ((0, 0, 0), (200, 80, 40), (0, 0, 0), (50, 100, 200), (63, 63, 63)),
    BlendMode.SCREEN: ((200, 80, 40), (255, 255, 255), (50, 100, 200), (255, 255, 255), (192, 192, 192)),
    BlendMode.OVERLAY: ((0, 0, 0), (255, 255, 255), (0, 0, 145), (100, 200, 255), (127, 127, 127)),
    BlendMode.SOFT_LIGHT: ((0, 0, 0), (255, 255, 255), (9, 39, 156), (89, 160, 242), (127, 127, 127)),
    BlendMode.HARD_LIGHT: ((145, 0, 0), (255, 160, 80), (0, 0, 0), (255, 255, 255), (128, 128, 128)),
    BlendMode.COLOR: ((0, 0, 0), (255, 255, 255), (96, 96, 96), (96, 96, 96), (128, 128, 128)),
    BlendMode.LINEAR_BURN: ((0, 0, 0), (200, 80, 40), (0, 0, 0), (50, 100, 200), (0, 0, 0)),
    BlendMode.LINEAR_DODGE: ((200, 80, 40), (255, 255, 255), (50, 100, 200), (255, 255, 255), (255, 255, 255)),
    BlendMode.DARKEN: ((0, 0, 0), (200, 80, 40), (0, 0, 0), (50, 100, 200), (127, 127, 127)),
    BlendMode.LIGHTEN: ((200, 80, 40), (255, 255, 255), (50, 100, 200), (255, 255, 255), (128, 128, 128)),
}


def render_pixel(base, blend, mode, mask=255):
    diffuse = Image.new("RGBA", (1, 1), (*base, 255))
    selected = Image.new("L", (1, 1), mask)
    empty = Image.new("L", (1, 1), 0)
    textures = TextureSet(
        diffuse,
        Image.merge("RGBA", (selected, empty, empty, empty)),
    )
    settings = RenderSettings(
        primary_color="#{:02x}{:02x}{:02x}".format(*blend),
        brightness=100,
        contrast=100,
        color_op=mode,
    )
    return TextureRenderer().render(textures, settings).getpixel((0, 0))[:3]


class BlendModeMathematicalTests(unittest.TestCase):
    def test_asymmetric_full_mask_has_fixed_numerical_results(self):
        for mode, expected in FULL_MASK_EXPECTED.items():
            with self.subTest(mode=mode):
                self.assertEqual(
                    render_pixel(ASYMMETRIC_BASE, ASYMMETRIC_BLEND, mode),
                    expected,
                )

    def test_zero_and_partial_masks_cover_every_mode(self):
        for mode, partial_expected in PARTIAL_MASK_EXPECTED.items():
            with self.subTest(mode=mode, mask="zero"):
                self.assertEqual(
                    render_pixel(ASYMMETRIC_BASE, ASYMMETRIC_BLEND, mode, 0),
                    ASYMMETRIC_BASE,
                )
            with self.subTest(mode=mode, mask="partial"):
                self.assertEqual(
                    render_pixel(ASYMMETRIC_BASE, ASYMMETRIC_BLEND, mode, 128),
                    partial_expected,
                )

    def test_black_white_and_gray_edges_have_fixed_results(self):
        inputs = (
            ((0, 0, 0), ASYMMETRIC_BLEND),
            ((255, 255, 255), ASYMMETRIC_BLEND),
            (ASYMMETRIC_BASE, (0, 0, 0)),
            (ASYMMETRIC_BASE, (255, 255, 255)),
            ((128, 128, 128), (127, 127, 127)),
        )
        for mode, expected_values in EDGE_EXPECTED.items():
            for (base, blend), expected in zip(inputs, expected_values):
                with self.subTest(mode=mode, base=base, blend=blend):
                    actual = render_pixel(base, blend, mode)
                    self.assertEqual(actual, expected)
                    self.assertTrue(all(0 <= channel <= 255 for channel in actual))

    def test_existing_multiply_screen_overlay_regression_fixture(self):
        expected = {
            BlendMode.MULTIPLY: (39, 31, 31),
            BlendMode.SCREEN: (211, 149, 209),
            BlendMode.OVERLAY: (78, 62, 162),
        }
        for mode, pixels in expected.items():
            with self.subTest(mode=mode):
                self.assertEqual(
                    render_pixel(ASYMMETRIC_BASE, ASYMMETRIC_BLEND, mode),
                    pixels,
                )

    def test_color_mode_preserves_luminosity_with_byte_rounding_tolerance(self):
        result = render_pixel(ASYMMETRIC_BASE, ASYMMETRIC_BLEND, BlendMode.COLOR)
        base_luminosity = sum(
            weight * channel
            for weight, channel in zip((0.3, 0.59, 0.11), ASYMMETRIC_BASE)
        )
        result_luminosity = sum(
            weight * channel
            for weight, channel in zip((0.3, 0.59, 0.11), result)
        )
        self.assertAlmostEqual(result_luminosity, base_luminosity, delta=1.0)
        self.assertGreater(result[0], result[1])
        self.assertGreater(result[1], result[2])
