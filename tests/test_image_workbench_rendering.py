import unittest
from dataclasses import replace

from PIL import Image

import test_support  # noqa: F401 - installs the user-data path redirect
from src.constant import ColorOps
from src.preview_controller import PreviewRequest, render_preview
from src.render_settings import DEFAULT_COLOR, RenderSettings
from src.texture_renderer import TextureRenderer
from src.texture_set import TextureSet

DIFFUSE_PIXELS = (
    (0, 0, 0, 0),
    (255, 255, 255, 255),
    (64, 128, 192, 128),
    (200, 100, 50, 255),
)
CHANNEL_PIXELS = (
    (255, 0, 0, 64),
    (0, 255, 0, 64),
    (0, 0, 255, 64),
    (0, 0, 0, 255),
)
PATTERN_COLORS = ("#cc2020", "#20cc40", "#2040cc", "#d0a020")
DIFFUSE_ONLY = (
    (0, 0, 0, 255),
    (255, 255, 255, 255),
    (32, 64, 96, 255),
    (200, 100, 50, 255),
)
DIRT_PIXELS = (
    (255, 0, 0, 0),
    (255, 0, 0, 64),
    (255, 0, 0, 128),
    (255, 0, 0, 255),
)
SPECULAR_PIXELS = (
    (0, 0, 255, 255),
    (0, 0, 255, 128),
    (0, 0, 255, 64),
    (0, 0, 255, 0),
)


class RenderingCase:
    """Mutable test builder that emits immutable settings for each render."""

    def __init__(self, textures, settings):
        self.textures = textures
        self.settings = settings
        self.renderer = TextureRenderer()

    @property
    def colors(self):
        return self.settings.colors

    @colors.setter
    def colors(self, values):
        values = tuple(values) + (DEFAULT_COLOR,) * (4 - len(values))
        self.settings = replace(
            self.settings,
            primary_color=values[0],
            secondary_color=values[1],
            tint_color=values[2],
            extra_color=values[3],
        )

    def set(self, **values):
        if "color_op" in values and isinstance(values["color_op"], str):
            values["color_op"] = ColorOps(values["color_op"])
        self.settings = replace(self.settings, **values)

    def render(self):
        return self.renderer.render(self.textures, self.settings)

    def render_team_colour(self):
        return self.renderer.render_team_colour(self.textures, self.settings)


def image_from_pixels(mode, pixels):
    image = Image.new(mode, (2, 2))
    image.putdata(pixels)
    return image


def pixels(image):
    return tuple(
        image.getpixel((x, y)) for y in range(image.height) for x in range(image.width)
    )


class TextureRenderingBaselineTests(unittest.TestCase):
    """Pixel baselines captured from the renderer before its decomposition."""

    def make_workbench(self):
        diffuse = image_from_pixels("RGBA", DIFFUSE_PIXELS)
        channels = [
            image_from_pixels("L", channel) for channel in CHANNEL_PIXELS
        ]
        team_color = Image.merge("RGBA", tuple(channels))
        return RenderingCase(
            TextureSet(diffuse, team_color),
            RenderSettings(
                brightness=100,
                contrast=100,
                tem_selected=(0, 1, 2, 3),
            ),
        )

    def assert_images_equal(self, actual, expected):
        self.assertEqual(
            actual.size,
            expected.size,
            f"image dimensions differ: {actual.size} != {expected.size}",
        )
        self.assertEqual(
            actual.mode,
            expected.mode,
            f"image modes differ: {actual.mode} != {expected.mode}",
        )
        for y in range(actual.height):
            for x in range(actual.width):
                actual_pixel = actual.getpixel((x, y))
                expected_pixel = expected.getpixel((x, y))
                if actual_pixel != expected_pixel:
                    self.fail(
                        f"first differing pixel at ({x}, {y}): "
                        f"actual {actual_pixel}, expected {expected_pixel}"
                    )

    def assert_render_pixels(self, workbench, expected_pixels):
        expected = image_from_pixels("RGBA", expected_pixels)
        actual = workbench.render()
        direct = TextureRenderer().render(
            workbench.textures,
            workbench.settings,
        )
        self.assert_images_equal(actual, expected)
        self.assert_images_equal(direct, expected)
        self.assert_images_equal(direct, actual)
        self.assertEqual(actual.mode, "RGBA")
        self.assertEqual(actual.size, (2, 2))

    def test_diffuse_only_rendering_flattens_source_alpha_over_black(self):
        self.assert_render_pixels(self.make_workbench(), DIFFUSE_ONLY)

    def test_each_pattern_color_slot(self):
        expected_by_slot = (
            (
                (0, 0, 0, 255),
                (255, 255, 255, 255),
                (32, 64, 96, 255),
                (208, 81, 40, 255),
            ),
            (
                (0, 0, 0, 255),
                (255, 255, 255, 255),
                (32, 64, 96, 255),
                (190, 115, 44, 255),
            ),
            (
                (0, 0, 0, 255),
                (255, 255, 255, 255),
                (16, 64, 230, 255),
                (190, 87, 58, 255),
            ),
            (
                (0, 0, 0, 255),
                (255, 255, 255, 255),
                (32, 64, 96, 255),
                (235, 125, 12, 255),
            ),
        )
        slot_names = ("primary", "secondary", "tint", "extra")

        for slot, (name, expected) in enumerate(zip(slot_names, expected_by_slot)):
            with self.subTest(slot=name):
                workbench = self.make_workbench()
                colors = ["#808080"] * 4
                colors[slot] = PATTERN_COLORS[slot]
                workbench.colors = colors
                self.assert_render_pixels(workbench, expected)

    def test_all_four_pattern_colors_together(self):
        workbench = self.make_workbench()
        workbench.colors = list(PATTERN_COLORS)

        self.assert_render_pixels(
            workbench,
            (
                (0, 0, 0, 255),
                (255, 255, 255, 255),
                (16, 64, 230, 255),
                (235, 125, 12, 255),
            ),
        )

    def test_brightness_change(self):
        workbench = self.make_workbench()
        workbench.colors = [PATTERN_COLORS[0]]
        workbench.set(brightness=50)

        self.assert_render_pixels(
            workbench,
            (
                (0, 0, 0, 255),
                (255, 255, 255, 255),
                (32, 64, 96, 255),
                (179, 78, 39, 255),
            ),
        )

    def test_contrast_change(self):
        workbench = self.make_workbench()
        workbench.colors = [PATTERN_COLORS[0]]
        workbench.set(contrast=50)

        self.assert_render_pixels(
            workbench,
            (
                (0, 0, 0, 255),
                (255, 255, 255, 255),
                (32, 64, 96, 255),
                (192, 91, 52, 255),
            ),
        )

    def test_brightness_and_contrast_combination(self):
        workbench = self.make_workbench()
        workbench.colors = [PATTERN_COLORS[0]]
        workbench.set(brightness=50, contrast=150)

        self.assert_render_pixels(
            workbench,
            (
                (0, 0, 0, 255),
                (255, 255, 255, 255),
                (32, 64, 96, 255),
                (182, 75, 37, 255),
            ),
        )

    def test_alpha_uses_inverted_selected_channel_image(self):
        workbench = self.make_workbench()
        workbench.set(apply_alpha=True, tem_selected=(0, 2))

        self.assert_render_pixels(
            workbench,
            (
                (0, 0, 0, 0),
                (255, 255, 255, 255),
                (32, 64, 96, 0),
                (200, 100, 50, 227),
            ),
        )
        expected_team = image_from_pixels("L", (255, 0, 255, 28))
        self.assert_images_equal(workbench.render_team_colour(), expected_team)

    def test_each_supported_color_operation(self):
        expected_by_operation = {
            ColorOps.NORMAL.value: (
                (204, 32, 32, 255),
                (255, 255, 255, 255),
                (32, 64, 96, 255),
                (201, 83, 45, 255),
            ),
            ColorOps.OVERLAY.value: (
                (0, 0, 0, 255),
                (255, 255, 255, 255),
                (32, 64, 96, 255),
                (208, 81, 40, 255),
            ),
            ColorOps.SCREEN.value: (
                (204, 32, 32, 255),
                (255, 255, 255, 255),
                (32, 64, 96, 255),
                (211, 105, 57, 255),
            ),
            ColorOps.MULTIPLY.value: (
                (0, 0, 0, 255),
                (255, 255, 255, 255),
                (32, 64, 96, 255),
                (190, 78, 39, 255),
            ),
            ColorOps.SOFT_LIGHT.value: (
                (0, 0, 0, 255),
                (255, 255, 255, 255),
                (32, 64, 96, 255),
                (206, 88, 42, 255),
            ),
        }

        for operation, expected in expected_by_operation.items():
            with self.subTest(operation=operation):
                workbench = self.make_workbench()
                workbench.colors = [PATTERN_COLORS[0]]
                workbench.set(color_op=operation)
                self.assert_render_pixels(workbench, expected)

    def test_normal_uses_mask_once_for_zero_full_and_partial_strength(self):
        diffuse = image_from_pixels(
            "RGBA",
            (
                (10, 20, 30, 255),
                (10, 20, 30, 255),
                (10, 20, 30, 255),
                (0, 0, 0, 255),
            ),
        )
        red = image_from_pixels("L", (0, 255, 128, 0))
        empty = Image.new("L", (2, 2), 0)
        textures = TextureSet(
            diffuse,
            Image.merge("RGBA", (red, empty, empty, empty)),
        )
        settings = RenderSettings(
            primary_color="#6e7882",
            brightness=100,
            contrast=100,
            color_op=ColorOps.NORMAL,
            tem_selected=(0,),
        )

        self.assertEqual(
            pixels(TextureRenderer().render(textures, settings)),
            (
                (10, 20, 30, 255),
                (110, 120, 130, 255),
                (60, 70, 80, 255),
                (0, 0, 0, 255),
            ),
        )

    def test_normal_keeps_established_contrast_brightness_then_alpha_order(self):
        diffuse = Image.new("RGBA", (1, 1), (10, 20, 30, 255))
        full = Image.new("L", (1, 1), 255)
        empty = Image.new("L", (1, 1), 0)
        textures = TextureSet(
            diffuse,
            Image.merge("RGBA", (full, empty, empty, empty)),
        )
        settings = RenderSettings(
            primary_color="#6496c8",
            brightness=50,
            contrast=100,
            apply_alpha=True,
            color_op=ColorOps.NORMAL,
            tem_selected=(0,),
        )

        self.assertEqual(
            TextureRenderer().render(textures, settings).getpixel((0, 0)),
            (50, 75, 100, 0),
        )

    def test_soft_light_known_values_include_edges_and_asymmetric_inputs(self):
        diffuse = image_from_pixels(
            "RGBA",
            (
                (0, 0, 0, 255),
                (64, 64, 64, 255),
                (128, 128, 128, 255),
                (255, 255, 255, 255),
            ),
        )
        full = Image.new("L", (2, 2), 255)
        empty = Image.new("L", (2, 2), 0)
        textures = TextureSet(
            diffuse,
            Image.merge("RGBA", (full, empty, empty, empty)),
        )

        expected_by_colour = {
            "#000000": (0, 16, 64, 255),
            "#c0c0c0": (0, 87, 159, 255),
            "#ffffff": (0, 111, 191, 255),
        }
        for colour, expected in expected_by_colour.items():
            with self.subTest(colour=colour):
                settings = RenderSettings(
                    primary_color=colour,
                    brightness=100,
                    contrast=100,
                    color_op=ColorOps.SOFT_LIGHT,
                )
                actual = pixels(TextureRenderer().render(textures, settings))
                self.assertEqual(tuple(pixel[0] for pixel in actual), expected)
                self.assertTrue(
                    all(0 <= channel <= 255 for pixel in actual for channel in pixel)
                )

    def make_optional_maps_workbench(self):
        workbench = self.make_workbench()
        workbench.textures.dirt = image_from_pixels("RGBA", DIRT_PIXELS)
        workbench.textures.specular = image_from_pixels("RGBA", SPECULAR_PIXELS)
        return workbench

    def test_dirt_disabled(self):
        workbench = self.make_optional_maps_workbench()
        workbench.set(apply_dirt=False)

        self.assert_render_pixels(workbench, DIFFUSE_ONLY)

    def test_dirt_enabled(self):
        workbench = self.make_optional_maps_workbench()
        workbench.set(apply_dirt=True)

        self.assert_render_pixels(
            workbench,
            (
                (0, 0, 0, 255),
                (255, 191, 191, 255),
                (144, 32, 48, 255),
                (255, 0, 0, 255),
            ),
        )

    def test_specular_disabled(self):
        workbench = self.make_optional_maps_workbench()
        workbench.set(apply_spec=False)

        self.assert_render_pixels(workbench, DIFFUSE_ONLY)

    def test_specular_enabled(self):
        workbench = self.make_optional_maps_workbench()
        workbench.set(apply_spec=True)

        self.assert_render_pixels(
            workbench,
            (
                (0, 0, 255, 255),
                (127, 127, 255, 255),
                (24, 48, 136, 255),
                (200, 100, 50, 255),
            ),
        )

    def test_dirt_and_specular_combination_preserves_compositing_order(self):
        workbench = self.make_optional_maps_workbench()
        workbench.set(apply_dirt=True, apply_spec=True)

        self.assert_render_pixels(
            workbench,
            (
                (0, 0, 255, 255),
                (127, 95, 223, 255),
                (108, 24, 100, 255),
                (255, 0, 0, 255),
            ),
        )

    def test_representative_full_pipeline(self):
        workbench = self.make_optional_maps_workbench()
        workbench.colors = list(PATTERN_COLORS)
        workbench.set(
            brightness=85,
            contrast=120,
            color_op=ColorOps.MULTIPLY,
            apply_alpha=True,
            apply_dirt=True,
            apply_spec=True,
        )

        self.assert_render_pixels(
            workbench,
            (
                (0, 0, 255, 255),
                (51, 0, 204, 160),
                (153, 0, 102, 160),
                (255, 0, 0, 255),
            ),
        )

    def test_rendering_does_not_mutate_source_images(self):
        workbench = self.make_optional_maps_workbench()
        workbench.colors = list(PATTERN_COLORS)
        workbench.set(apply_alpha=True, apply_dirt=True, apply_spec=True)
        sources = (
            workbench.textures.diffuse,
            workbench.textures.team_color,
            workbench.textures.dirt,
            workbench.textures.specular,
        )
        source_copies = tuple(image.copy() for image in sources)

        workbench.render()
        workbench.render_team_colour()

        for source, original in zip(sources, source_copies):
            self.assert_images_equal(source, original)

    def test_repeated_rendering_is_pixel_identical(self):
        workbench = self.make_optional_maps_workbench()
        workbench.colors = list(PATTERN_COLORS)
        workbench.set(apply_alpha=True, apply_dirt=True, apply_spec=True)

        first = workbench.render().copy()
        second = workbench.render()

        self.assert_images_equal(first, second)

    def test_render_settings_snapshots_are_independent(self):
        workbench = self.make_workbench()
        original = workbench.settings
        changed = replace(
            original,
            primary_color=PATTERN_COLORS[0],
            secondary_color=PATTERN_COLORS[1],
            tint_color=PATTERN_COLORS[2],
            extra_color=PATTERN_COLORS[3],
            brightness=40,
            color_op=ColorOps.SCREEN,
        )

        workbench.settings = changed
        workbench.render()

        self.assertEqual(
            original,
            replace(
                changed,
                primary_color="#808080",
                secondary_color="#808080",
                tint_color="#808080",
                extra_color="#808080",
                brightness=100,
                color_op=ColorOps.OVERLAY,
            ),
        )
        self.assertNotEqual(original, changed)

    def test_preview_and_direct_output_use_equivalent_core_rendering(self):
        workbench = self.make_optional_maps_workbench()
        workbench.colors = list(PATTERN_COLORS)
        workbench.set(
            brightness=85,
            contrast=120,
            apply_alpha=True,
            apply_dirt=True,
            apply_spec=True,
        )
        direct_output = workbench.render().copy()
        direct_team = workbench.render_team_colour().copy()

        request = PreviewRequest(
            workbench.textures.copy_for_render(),
            workbench.settings,
        )
        preview_result = render_preview(TextureRenderer(), request)

        self.assert_images_equal(preview_result.workspace, direct_output)
        self.assert_images_equal(preview_result.team_colour, direct_team)


if __name__ == "__main__":
    unittest.main()
