import inspect
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import weakref

from PIL import Image

import test_support  # noqa: F401 - installs the user-data path redirect
from src.batch_processing_service import (
    BatchItemStatus,
    BatchProcessingRequest,
    BatchProcessingService,
    discover_batch_diffuses,
    load_batch_texture_set,
)
from src.render_settings import RenderSettings
from src.texture_renderer import TextureRenderer
from src.texture_naming import DEFAULT_TEXTURE_NAMING


class BatchProcessingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()
        self.destination.mkdir()
        self.settings = RenderSettings()
        self.service = BatchProcessingService()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def create_texture_set(self, stem, color=(80, 100, 120, 255)):
        diffuse = self.source / f"{stem}_dif.png"
        team = self.source / f"{stem}_tem.png"
        Image.new("RGBA", (4, 4), color).save(diffuse)
        Image.new("RGBA", (4, 4), (0, 0, 0, 0)).save(team)
        return diffuse, team

    def request(self, overwrite=False):
        return BatchProcessingRequest(
            self.source,
            self.destination,
            ("png",),
            "png",
            self.settings,
            DEFAULT_TEXTURE_NAMING,
            overwrite,
        )

    def test_discovery_excludes_companions_and_is_deterministic(self):
        second, _ = self.create_texture_set("zulu")
        first, _ = self.create_texture_set("Alpha")
        Image.new("RGBA", (4, 4)).save(self.source / "dirt_drt.png")
        (self.source / "nested_dif.png").mkdir()

        discovered = discover_batch_diffuses(
            self.source, ("PNG",), DEFAULT_TEXTURE_NAMING
        )

        self.assertEqual(discovered, (first, second))

    def test_valid_processing_matches_existing_render_path(self):
        diffuse, _ = self.create_texture_set("marine")
        textures, _ = load_batch_texture_set(
            diffuse, DEFAULT_TEXTURE_NAMING
        )
        expected = TextureRenderer().render(textures, self.settings)

        result = self.service.process(self.request())

        self.assertEqual(result.processed_count, 1)
        self.assertEqual(result.failed_count, 0)
        output = self.destination / "marine_dif.png"
        with Image.open(output) as actual:
            self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_missing_optional_companions_are_not_warnings(self):
        self.create_texture_set("marine")
        result = self.service.process(self.request())

        self.assertEqual(result.items[0].warnings, ())
        self.assertEqual(result.items[0].status, BatchItemStatus.PROCESSED)

    def test_multiple_valid_items_are_processed_in_deterministic_order(self):
        second, _ = self.create_texture_set("zulu")
        first, _ = self.create_texture_set("Alpha")

        result = self.service.process(self.request())

        self.assertEqual(result.processed_count, 2)
        self.assertEqual(
            tuple(item.source for item in result.items),
            (first, second),
        )

    def test_invalid_item_does_not_abort_later_valid_item(self):
        (self.source / "alpha_dif.png").write_text("not an image")
        Image.new("RGBA", (4, 4)).save(self.source / "alpha_tem.png")
        self.create_texture_set("bravo")

        result = self.service.process(self.request())

        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.processed_count, 1)
        self.assertTrue((self.destination / "bravo_dif.png").exists())

    def test_output_naming_and_overwrite_policy(self):
        self.create_texture_set("marine")
        output = self.destination / "marine_dif.jpg"
        Image.new("RGB", (4, 4), "red").save(output)
        request = BatchProcessingRequest(
            self.source,
            self.destination,
            ("png",),
            "jpg",
            self.settings,
        )

        skipped = self.service.process(request)
        overwritten = self.service.process(
            BatchProcessingRequest(
                self.source,
                self.destination,
                ("png",),
                "jpg",
                self.settings,
                overwrite_existing=True,
            )
        )

        self.assertEqual(skipped.skipped_count, 1)
        self.assertEqual(overwritten.processed_count, 1)
        self.assertEqual(overwritten.items[0].destination, output)

    def test_cancellation_before_processing(self):
        self.create_texture_set("marine")
        result = self.service.process(
            self.request(), cancellation_requested=lambda: True
        )

        self.assertTrue(result.cancelled)
        self.assertEqual(result.processed_count, 0)
        self.assertEqual(result.items, ())

    def test_cancellation_between_items_and_progress(self):
        self.create_texture_set("alpha")
        self.create_texture_set("bravo")
        cancelled = False
        progress = []

        def report(event):
            nonlocal cancelled
            progress.append(event)
            if event.completed == 1:
                cancelled = True

        result = self.service.process(self.request(), lambda: cancelled, report)

        self.assertTrue(result.cancelled)
        self.assertEqual(result.processed_count, 1)
        self.assertEqual((progress[0].completed, progress[0].total), (0, 2))
        self.assertEqual((progress[1].completed, progress[1].total), (1, 2))
        self.assertEqual(len(progress), 2)

    def test_source_image_handles_are_closed(self):
        diffuse, team = self.create_texture_set("marine")
        self.service.process(self.request())

        diffuse.rename(self.source / "renamed_dif.png")
        team.rename(self.source / "renamed_tem.png")

    def test_atomic_failure_preserves_existing_output(self):
        self.create_texture_set("marine")
        output = self.destination / "marine_dif.png"
        output.write_bytes(b"previous output")

        with patch(
            "src.batch_processing_service.os.replace",
            side_effect=OSError("disk failure"),
        ):
            result = self.service.process(self.request(overwrite=True))

        self.assertEqual(result.failed_count, 1)
        self.assertEqual(output.read_bytes(), b"previous output")
        self.assertEqual(list(self.destination.glob(".marine_dif.*")), [])

    def test_renderer_failure_is_one_structured_item_failure(self):
        self.create_texture_set("marine")
        renderer = Mock()
        renderer.render.side_effect = ValueError("render failure")
        service = BatchProcessingService(renderer=renderer)

        result = service.process(self.request())

        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.items[0].status, BatchItemStatus.FAILED)
        self.assertEqual(result.items[0].error_message, "render failure")
        renderer.render.assert_called_once()

    def test_batch_does_not_mutate_unrelated_interactive_textures(self):
        self.create_texture_set("marine")
        interactive_diffuse = Image.new("RGBA", (4, 4), "magenta")
        interactive_team = Image.new("RGBA", (4, 4), "cyan")
        diffuse_before = interactive_diffuse.tobytes()
        team_before = interactive_team.tobytes()

        self.service.process(self.request())

        self.assertEqual(interactive_diffuse.tobytes(), diffuse_before)
        self.assertEqual(interactive_team.tobytes(), team_before)

    def test_item_texture_set_is_released_after_processing(self):
        diffuse, _ = self.create_texture_set("marine")
        textures, warnings = load_batch_texture_set(diffuse)
        texture_reference = weakref.ref(textures)

        class ReferenceOnlyRenderer:
            def render(self, item_textures, settings):
                nonlocal texture_reference
                texture_reference = weakref.ref(item_textures)
                return Image.new("RGBA", item_textures.dimensions)

        with patch(
            "src.batch_processing_service.load_batch_texture_set",
            return_value=(textures, warnings),
        ):
            service = BatchProcessingService(renderer=ReferenceOnlyRenderer())
            service.process(self.request())

        del textures
        gc.collect()
        self.assertIsNone(texture_reference())

    def test_module_has_no_tk_widget_or_armypainter_dependency(self):
        import src.batch_processing_service as module

        source = inspect.getsource(module)
        self.assertNotIn("tkinter", source)
        self.assertNotIn("src.widget", source)
        self.assertNotIn("ArmyPainter", source)
        self.assertNotIn("ImageWorkbench", source)
        self.assertNotIn("refresh_workspace", source)
        self.assertNotIn("apply_render_settings", source)


if __name__ == "__main__":
    unittest.main()
