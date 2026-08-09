import ast
import unittest
from dataclasses import replace
from pathlib import Path

from PIL import Image

import test_support  # noqa: F401 - installs the user-data path redirect
from src.constant import ColorOps
from src.image_process import ImageWorkbench
from src.render_settings import RenderSettings
from src.texture_renderer import TextureRenderer
from src.texture_set import TextureSet


def image_from_pixels(mode, size, values):
    image = Image.new(mode, size)
    image.putdata(values)
    return image


def assert_images_equal(test_case, actual, expected):
    test_case.assertEqual(actual.size, expected.size)
    test_case.assertEqual(actual.mode, expected.mode)
    for y in range(actual.height):
        for x in range(actual.width):
            test_case.assertEqual(
                actual.getpixel((x, y)),
                expected.getpixel((x, y)),
                f"pixel differs at ({x}, {y})",
            )


class TextureRendererTests(unittest.TestCase):
    def make_textures(self, diffuse_color=(80, 120, 160, 128)):
        diffuse = Image.new("RGBA", (2, 2), diffuse_color)
        team_color = image_from_pixels(
            "RGBA",
            (2, 2),
            (
                (255, 0, 0, 0),
                (0, 255, 0, 0),
                (0, 0, 255, 0),
                (64, 64, 64, 255),
            ),
        )
        dirt = image_from_pixels(
            "RGBA",
            (2, 2),
            ((255, 0, 0, 0), (255, 0, 0, 64), (255, 0, 0, 128), (255, 0, 0, 255)),
        )
        specular = image_from_pixels(
            "RGBA",
            (2, 2),
            ((0, 0, 255, 255), (0, 0, 255, 128), (0, 0, 255, 64), (0, 0, 255, 0)),
        )
        return TextureSet(diffuse, team_color, dirt, specular)

    def full_settings(self):
        return RenderSettings(
            primary_color="#cc2020",
            secondary_color="#20cc40",
            tint_color="#2040cc",
            extra_color="#d0a020",
            brightness=85,
            contrast=120,
            apply_alpha=True,
            apply_dirt=True,
            apply_spec=True,
            color_op=ColorOps.MULTIPLY,
            tem_selected=(0, 1, 2, 3),
        )

    def test_direct_and_compatibility_rendering_are_identical(self):
        workbench = ImageWorkbench()
        workbench.texture_set = self.make_textures()
        workbench.apply_render_settings(self.full_settings())

        compatibility = workbench.refresh_workspace()
        direct = TextureRenderer().render(
            workbench.texture_set,
            workbench.render_settings,
        )

        assert_images_equal(self, direct, compatibility)

    def test_rendering_does_not_mutate_any_source_image(self):
        textures = self.make_textures()
        sources = (
            textures.diffuse,
            textures.team_color,
            textures.dirt,
            textures.specular,
        )
        originals = tuple(image.copy() for image in sources)

        TextureRenderer().render(textures, self.full_settings())

        for source, original in zip(sources, originals):
            assert_images_equal(self, source, original)

    def test_repeated_rendering_is_deterministic(self):
        renderer = TextureRenderer()
        textures = self.make_textures()
        settings = self.full_settings()

        first = renderer.render(textures, settings)
        second = renderer.render(textures, settings)

        self.assertIsNot(first, second)
        assert_images_equal(self, first, second)

    def test_independent_settings_do_not_affect_each_other(self):
        renderer = TextureRenderer()
        textures = self.make_textures()
        first_settings = self.full_settings()
        second_settings = replace(
            first_settings,
            brightness=25,
            apply_dirt=False,
            apply_spec=False,
        )

        first = renderer.render(textures, first_settings)
        second = renderer.render(textures, second_settings)
        repeated_first = renderer.render(textures, first_settings)

        self.assertNotEqual(first.tobytes(), second.tobytes())
        assert_images_equal(self, first, repeated_first)
        self.assertEqual(first_settings.brightness, 85)
        self.assertTrue(first_settings.apply_dirt)

    def test_one_renderer_is_reusable_across_texture_sets(self):
        renderer = TextureRenderer()
        first_textures = self.make_textures((40, 60, 80, 255))
        second_textures = self.make_textures((180, 160, 140, 255))
        settings = RenderSettings()

        first = renderer.render(first_textures, settings)
        second = renderer.render(second_textures, settings)
        repeated_first = renderer.render(first_textures, settings)

        self.assertNotEqual(first.tobytes(), second.tobytes())
        assert_images_equal(self, first, repeated_first)
        self.assertEqual(vars(renderer), {})

    def test_diffuse_only_texture_set_is_renderable(self):
        diffuse = Image.new("RGBA", (3, 2), (20, 40, 60, 128))

        output = TextureRenderer().render(
            TextureSet(diffuse),
            RenderSettings(),
        )

        self.assertEqual(output.size, (3, 2))
        self.assertEqual(output.mode, "RGBA")
        self.assertEqual(output.getpixel((0, 0)), (10, 20, 30, 255))

    def test_renderer_has_no_gui_filesystem_or_workbench_dependency(self):
        source_path = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "texture_renderer.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )

        self.assertNotIn("tkinter", imports)
        self.assertNotIn("pathlib", imports)
        self.assertNotIn("os", imports)
        self.assertNotIn("src.frame_main", imports)
        self.assertNotIn("src.image_process", imports)


if __name__ == "__main__":
    unittest.main()
