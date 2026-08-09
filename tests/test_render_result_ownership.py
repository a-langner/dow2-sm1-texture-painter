import ast
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from PIL import Image

import test_support  # noqa: F401 - installs the user-data path redirect
from src.image_process import save_image
from src.render_settings import RenderSettings
from src.texture_renderer import TextureRenderer
from src.texture_set import TextureSet


def assert_images_equal(test_case, actual, expected):
    test_case.assertEqual(actual.size, expected.size)
    test_case.assertEqual(actual.mode, expected.mode)
    test_case.assertEqual(actual.tobytes(), expected.tobytes())


class RenderResultOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.diffuse = Image.new("RGBA", (4, 4), (80, 120, 160, 128))
        self.team_color = Image.new("RGBA", (4, 4), (255, 0, 0, 0))
        self.textures = TextureSet(self.diffuse, self.team_color)
        self.settings = RenderSettings(primary_color="#cc2020")
        self.renderer = TextureRenderer()

    def test_rendering_returns_a_caller_owned_image_explicitly(self):
        result = self.renderer.render(self.textures, self.settings)

        self.assertIsInstance(result, Image.Image)
        self.assertIsNot(result, self.diffuse)
        self.assertEqual(vars(self.renderer), {})

    def test_texture_set_contains_source_state_only(self):
        self.assertEqual(
            set(vars(self.textures)),
            {"diffuse", "team_color", "dirt", "specular"},
        )
        source = ast.parse(
            (
                Path(__file__).resolve().parents[1]
                / "src"
                / "texture_set.py"
            ).read_text(encoding="utf-8")
        )
        field_names = {
            target.id
            for node in source.body
            if isinstance(node, ast.ClassDef) and node.name == "TextureSet"
            for statement in node.body
            if isinstance(statement, ast.AnnAssign)
            for target in (statement.target,)
            if isinstance(target, ast.Name)
        }
        self.assertTrue(
            field_names.isdisjoint({"output", "preview", "rendered", "result"})
        )

    def test_later_render_does_not_replace_or_mutate_earlier_result(self):
        first = self.renderer.render(self.textures, self.settings)
        first_pixels = first.tobytes()

        second = self.renderer.render(
            self.textures,
            replace(self.settings, brightness=25),
        )

        self.assertIsNot(first, second)
        self.assertEqual(first.tobytes(), first_pixels)
        self.assertNotEqual(first.tobytes(), second.tobytes())

    def test_parallel_renders_have_no_shared_result_field(self):
        settings = (
            self.settings,
            replace(self.settings, brightness=25),
            replace(self.settings, contrast=150),
            replace(self.settings, apply_alpha=True, tem_selected=(0,)),
        )

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = tuple(
                executor.map(
                    lambda value: self.renderer.render(self.textures, value),
                    settings,
                )
            )

        self.assertEqual(len({id(result) for result in results}), 4)
        self.assertEqual(vars(self.renderer), {})
        self.assertEqual(len({result.tobytes() for result in results}), 4)

    def test_rendering_does_not_change_sources_or_settings(self):
        diffuse = self.diffuse.copy()
        team_color = self.team_color.copy()
        settings = self.settings

        self.renderer.render(self.textures, settings)

        assert_images_equal(self, self.diffuse, diffuse)
        assert_images_equal(self, self.team_color, team_color)
        self.assertIs(self.settings, settings)

    def test_explicit_save_handoff_uses_supplied_result(self):
        result = self.renderer.render(self.textures, self.settings)

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "rendered.png"
            save_image(result, destination)
            with Image.open(destination) as saved:
                saved.load()
                assert_images_equal(self, saved, result)


if __name__ == "__main__":
    unittest.main()
