import tempfile
import unittest
from pathlib import Path

from PIL import Image

import test_support  # noqa: F401 - installs the user-data path redirect
from src.batch_processing_service import (
    BatchProcessingRequest,
    BatchProcessingService,
    load_batch_texture_set,
)
from src.constant import ColorOps
from src.render_settings import RenderSettings
from src.texture_renderer import TextureRenderer


def image_from_pixels(mode, pixels):
    image = Image.new(mode, (2, 2))
    image.putdata(pixels)
    return image


class BatchRenderParityTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()
        self.destination.mkdir()
        image_from_pixels(
            "RGBA",
            (
                (0, 0, 0, 0),
                (255, 255, 255, 255),
                (64, 128, 192, 128),
                (200, 100, 50, 255),
            ),
        ).save(self.source / "marine_dif.png")
        image_from_pixels(
            "RGBA",
            (
                (255, 0, 0, 0),
                (0, 255, 0, 0),
                (0, 0, 255, 0),
                (64, 64, 64, 255),
            ),
        ).save(self.source / "marine_tem.png")
        image_from_pixels(
            "RGBA",
            (
                (255, 0, 0, 0),
                (255, 0, 0, 64),
                (255, 0, 0, 128),
                (255, 0, 0, 255),
            ),
        ).save(self.source / "marine_drt.png")
        image_from_pixels(
            "RGBA",
            (
                (0, 0, 255, 255),
                (0, 0, 255, 128),
                (0, 0, 255, 64),
                (0, 0, 255, 0),
            ),
        ).save(self.source / "marine_spc.png")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_batch_pixels_match_interactive_renderer_for_all_major_settings(self):
        colors = {
            "primary_color": "#cc2020",
            "secondary_color": "#20cc40",
            "tint_color": "#2040cc",
            "extra_color": "#d0a020",
        }
        scenarios = {
            "diffuse_only": RenderSettings(),
            "all_four_colors": RenderSettings(**colors),
            "brightness_contrast": RenderSettings(
                **colors,
                brightness=50,
                contrast=150,
            ),
            "alpha": RenderSettings(apply_alpha=True, tem_selected=(0, 2)),
            "dirt": RenderSettings(apply_dirt=True),
            "specular": RenderSettings(apply_spec=True),
            "full_pipeline": RenderSettings(
                **colors,
                brightness=85,
                contrast=120,
                apply_alpha=True,
                apply_dirt=True,
                apply_spec=True,
                color_op=ColorOps.MULTIPLY,
                tem_selected=(0, 1, 2, 3),
            ),
        }
        renderer = TextureRenderer()
        service = BatchProcessingService(renderer=renderer)
        textures, _ = load_batch_texture_set(self.source / "marine_dif.png")

        for name, settings in scenarios.items():
            with self.subTest(name=name):
                expected = renderer.render(textures, settings)
                request = BatchProcessingRequest(
                    source_directory=self.source,
                    destination_directory=self.destination,
                    source_formats=("png",),
                    destination_format="png",
                    settings=settings,
                    overwrite_existing=True,
                )

                result = service.process(request)

                self.assertEqual(result.processed_count, 1)
                with Image.open(self.destination / "marine_dif.png") as actual:
                    actual.load()
                    self.assertEqual(actual.size, expected.size)
                    self.assertEqual(actual.mode, expected.mode)
                    self.assertEqual(actual.tobytes(), expected.tobytes())


if __name__ == "__main__":
    unittest.main()
