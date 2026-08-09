import unittest
from dataclasses import replace

from PIL import Image

import test_support  # noqa: F401 - installs the user-data path redirect
from src.constant import ColorOps
from src.image_process import ImageWorkbench
from src.preview_controller import render_preview
from src.texture_renderer import TextureRenderer

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


def image_from_pixels(mode, pixels):
    image = Image.new(mode, (2, 2))
    image.putdata(pixels)
    return image


def pixels(image):
    return tuple(
        image.getpixel((x, y)) for y in range(image.height) for x in range(image.width)
    )


class ImageWorkbenchRenderingTests(unittest.TestCase):
    """Pixel baselines captured from the renderer before its decomposition."""

    def make_workbench(self):
        workbench = ImageWorkbench()
        workbench.img_og_dif = image_from_pixels("RGBA", DIFFUSE_PIXELS)
        workbench.tem_channels = [
            image_from_pixels("L", channel) for channel in CHANNEL_PIXELS
        ]
        workbench.img_og_tem = Image.merge("RGBA", tuple(workbench.tem_channels))
        workbench.colors = []
        workbench.brightness = 100
        workbench.contrast = 100
        workbench.tem_selected = (0, 1, 2, 3)
        return workbench

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
        actual = workbench.refresh_workspace()
        direct = TextureRenderer().render(
            workbench.texture_set,
            workbench.render_settings,
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
        workbench.brightness = 50

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
        workbench.contrast = 50

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
        workbench.brightness = 50
        workbench.contrast = 150

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
        workbench.apply_alpha = True
        workbench.tem_selected = (0, 2)

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
        self.assert_images_equal(workbench.refresh_team_colour_img(), expected_team)

    def test_each_supported_color_operation(self):
        expected_by_operation = {
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
        }

        for operation, expected in expected_by_operation.items():
            with self.subTest(operation=operation):
                workbench = self.make_workbench()
                workbench.colors = [PATTERN_COLORS[0]]
                workbench.color_op = operation
                self.assert_render_pixels(workbench, expected)

    def make_optional_maps_workbench(self):
        workbench = self.make_workbench()
        workbench.img_dirt = image_from_pixels("RGBA", DIRT_PIXELS)
        workbench.img_spec = image_from_pixels("RGBA", SPECULAR_PIXELS)
        return workbench

    def test_dirt_disabled(self):
        workbench = self.make_optional_maps_workbench()
        workbench.apply_dirt = False

        self.assert_render_pixels(workbench, DIFFUSE_ONLY)

    def test_dirt_enabled(self):
        workbench = self.make_optional_maps_workbench()
        workbench.apply_dirt = True

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
        workbench.apply_spec = False

        self.assert_render_pixels(workbench, DIFFUSE_ONLY)

    def test_specular_enabled(self):
        workbench = self.make_optional_maps_workbench()
        workbench.apply_spec = True

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
        workbench.apply_dirt = True
        workbench.apply_spec = True

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
        workbench.brightness = 85
        workbench.contrast = 120
        workbench.color_op = ColorOps.MULTIPLY.value
        workbench.apply_alpha = True
        workbench.apply_dirt = True
        workbench.apply_spec = True

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
        workbench.apply_alpha = True
        workbench.apply_dirt = True
        workbench.apply_spec = True
        sources = (
            workbench.img_og_dif,
            workbench.img_og_tem,
            *workbench.tem_channels,
            workbench.img_dirt,
            workbench.img_spec,
        )
        source_copies = tuple(image.copy() for image in sources)

        workbench.refresh_workspace()
        workbench.refresh_team_colour_img()

        for source, original in zip(sources, source_copies):
            self.assert_images_equal(source, original)

    def test_repeated_rendering_is_pixel_identical(self):
        workbench = self.make_optional_maps_workbench()
        workbench.colors = list(PATTERN_COLORS)
        workbench.apply_alpha = True
        workbench.apply_dirt = True
        workbench.apply_spec = True

        first = workbench.refresh_workspace().copy()
        second = workbench.refresh_workspace()

        self.assert_images_equal(first, second)

    def test_render_settings_snapshots_are_independent(self):
        workbench = self.make_workbench()
        original = workbench.get_render_settings()
        changed = replace(
            original,
            primary_color=PATTERN_COLORS[0],
            secondary_color=PATTERN_COLORS[1],
            tint_color=PATTERN_COLORS[2],
            extra_color=PATTERN_COLORS[3],
            brightness=40,
            color_op=ColorOps.SCREEN,
        )

        workbench.apply_render_settings(changed)
        workbench.refresh_workspace()

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
        workbench.brightness = 85
        workbench.contrast = 120
        workbench.apply_alpha = True
        workbench.apply_dirt = True
        workbench.apply_spec = True
        direct_output = workbench.refresh_workspace().copy()
        direct_team = workbench.refresh_team_colour_img().copy()

        preview_output, preview_team = render_preview(workbench.render_snapshot())

        self.assert_images_equal(preview_output, direct_output)
        self.assert_images_equal(preview_team, direct_team)


if __name__ == "__main__":
    unittest.main()
