import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

import test_support  # noqa: F401 - installs the user-data path redirect
from fake_dialog_gateway import FakeDialogGateway
from src.file_selection_service import FileSelectionService
from src.frame_main import ArmyPainter
from src.render_settings import RenderSettings
from src.texture_renderer import TextureRenderer
from src.texture_set import TextureSet


class NormalSaveWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.diffuse = Image.new("RGBA", (8, 4), (80, 120, 160, 128))
        self.team_color = Image.new("RGBA", (8, 4), (255, 0, 0, 0))
        self.textures = TextureSet(self.diffuse, self.team_color)
        self.settings = RenderSettings(
            primary_color="#cc2020",
            brightness=85,
            contrast=120,
            apply_alpha=True,
            tem_selected=(0,),
        )
        self.destination = Path("rendered.png")
        self.rendered = Image.new("RGBA", (8, 4), (10, 20, 30, 40))
        self.renderer = Mock(render=Mock(return_value=self.rendered))
        self.painter = SimpleNamespace(
            og_filename="unit_dif.png",
            file_selection=Mock(
                choose_image_save_destination=Mock(
                    return_value=self.destination
                )
            ),
            sync_render_settings=Mock(),
            active_texture_set=self.textures,
            render_settings=self.settings,
            texture_renderer=self.renderer,
            dialogs=Mock(),
        )

    @patch("src.frame_main.save_image")
    def test_save_uses_full_resolution_texture_set_and_current_settings(
        self, save_rendered
    ):
        current_settings = RenderSettings(
            primary_color="#2040cc",
            brightness=25,
        )

        def synchronize():
            self.painter.render_settings = current_settings

        self.painter.sync_render_settings.side_effect = synchronize

        ArmyPainter.save(self.painter)

        self.painter.sync_render_settings.assert_called_once_with()
        self.renderer.render.assert_called_once_with(
            self.textures,
            current_settings,
        )
        save_rendered.assert_called_once_with(self.rendered, self.destination)
        self.assertEqual(self.renderer.render.call_args.args[0].dimensions, (8, 4))

    @patch("src.frame_main.save_image")
    def test_save_does_not_require_or_use_a_preview_result(self, save_rendered):
        self.painter.preview_output = Image.new("RGBA", (1, 1), "magenta")

        ArmyPainter.save(self.painter)

        save_rendered.assert_called_once_with(self.rendered, self.destination)
        self.assertIsNot(save_rendered.call_args.args[0], self.painter.preview_output)

    @patch("src.frame_main.save_image")
    def test_cancellation_does_not_sync_render_or_write(self, save_rendered):
        self.painter.file_selection.choose_image_save_destination.return_value = None

        ArmyPainter.save(self.painter)

        self.painter.sync_render_settings.assert_not_called()
        self.renderer.render.assert_not_called()
        save_rendered.assert_not_called()

    @patch("src.frame_main.save_image")
    def test_save_without_active_texture_stops_before_dialog_or_render(
        self, save_rendered
    ):
        self.painter.active_texture_set = None

        ArmyPainter.save(self.painter)

        self.painter.dialogs.show_error.assert_called_once_with(
            title="Cannot Save Image",
            message="Load a diffuse texture before saving.",
        )
        self.painter.file_selection.choose_image_save_destination.assert_not_called()
        self.renderer.render.assert_not_called()
        save_rendered.assert_not_called()

    @patch("src.frame_main.save_image")
    def test_render_failure_does_not_write_and_has_distinct_message(
        self, save_rendered
    ):
        error = RuntimeError("render failed")
        self.renderer.render.side_effect = error

        ArmyPainter.save(self.painter)

        save_rendered.assert_not_called()
        self.painter.dialogs.show_error.assert_called_once_with(
            title="Cannot Render Image",
            message="Could not render the current texture.",
        )

    @patch("src.frame_main.save_image", side_effect=OSError("disk failure"))
    def test_write_failure_preserves_sources_and_has_distinct_message(
        self, save_rendered
    ):
        diffuse_before = self.diffuse.tobytes()
        team_before = self.team_color.tobytes()

        ArmyPainter.save(self.painter)

        self.renderer.render.assert_called_once_with(self.textures, self.settings)
        save_rendered.assert_called_once_with(self.rendered, self.destination)
        self.assertEqual(self.diffuse.tobytes(), diffuse_before)
        self.assertEqual(self.team_color.tobytes(), team_before)
        self.painter.dialogs.show_error.assert_called_once_with(
            title="Cannot Save Image",
            message=f"Could not write the output image to:\n{self.destination}",
        )

    @patch("src.frame_main.save_image", side_effect=KeyError("extension"))
    def test_wrong_extension_preserves_existing_user_message(self, save_rendered):
        ArmyPainter.save(self.painter)

        self.painter.dialogs.show_error.assert_called_once_with(
            title="Wrong File Extension",
            message="Error: wrong extension,"
            + 'choose an extension from the "Save as type" list',
        )

    def test_saved_pixels_dimensions_mode_and_alpha_match_direct_baseline(self):
        renderer = TextureRenderer()
        expected = renderer.render(self.textures, self.settings)

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "rendered.png"
            painter = SimpleNamespace(
                og_filename="unit_dif.png",
                file_selection=Mock(
                    choose_image_save_destination=Mock(
                        return_value=destination
                    )
                ),
                sync_render_settings=Mock(),
                active_texture_set=self.textures,
                render_settings=self.settings,
                texture_renderer=renderer,
                dialogs=Mock(),
            )

            ArmyPainter.save(painter)

            with Image.open(destination) as saved:
                saved.load()
                self.assertEqual(saved.size, self.diffuse.size)
                self.assertEqual(saved.mode, "RGBA")
                self.assertEqual(saved.getpixel((0, 0))[3], 0)
                self.assertEqual(saved.tobytes(), expected.tobytes())

    @patch("src.frame_main.save_image")
    def test_successful_image_save_remembers_export_directory(
        self, save_rendered
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "rendered.png"
            dialogs = FakeDialogGateway()
            dialogs.save_file_result = destination
            settings = Mock()
            settings.get_last_image_export_directory.return_value = root
            file_selection = FileSelectionService(
                settings,
                dialogs,
                home_directory=root,
            )
            self.painter.file_selection = file_selection

            ArmyPainter.save(self.painter)

        settings.set_last_image_export_directory.assert_called_once_with(root)
        save_rendered.assert_called_once_with(self.rendered, destination)

    @patch("src.frame_main.save_image", side_effect=OSError("disk failure"))
    def test_failed_image_save_does_not_remember_export_directory(
        self, _save_rendered
    ):
        ArmyPainter.save(self.painter)

        self.painter.file_selection.remember_successful_image_export.assert_not_called()


if __name__ == "__main__":
    unittest.main()
