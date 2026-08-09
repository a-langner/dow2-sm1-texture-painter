import inspect
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.render_settings import DEFAULT_RENDER_SETTINGS
from src.texture_set import TextureSet


class ActiveTextureLifecycleTests(unittest.TestCase):
    def test_preview_request_requires_an_active_texture(self):
        painter = SimpleNamespace(
            active_texture_set=None,
            render_settings=DEFAULT_RENDER_SETTINGS,
        )

        with self.assertRaisesRegex(RuntimeError, "No active texture"):
            ArmyPainter.create_preview_request(painter)

    def test_refresh_without_active_texture_only_invalidates_preview(self):
        painter = SimpleNamespace(
            active_texture_set=None,
            preview_controller=Mock(),
            sync_render_settings=Mock(),
        )

        ArmyPainter.refresh_workspace(painter)

        painter.preview_controller.invalidate.assert_called_once_with()
        painter.preview_controller.request_preview_immediately.assert_not_called()
        painter.sync_render_settings.assert_not_called()

    @patch("src.frame_main.ImageTk.PhotoImage", side_effect=lambda image: image)
    @patch("src.frame_main.create_placeholder_img")
    def test_close_releases_sources_invalidates_preview_and_sets_ui_placeholders(
        self, create_placeholder, photo_image
    ):
        diffuse_placeholder = object()
        channel_placeholder = object()
        create_placeholder.side_effect = (diffuse_placeholder, channel_placeholder)
        painter = SimpleNamespace(
            active_texture_set=Mock(spec=TextureSet),
            preview_controller=Mock(),
            label_img_dif=Mock(),
            label_img_tem=Mock(),
        )

        ArmyPainter.close(painter)

        self.assertIsNone(painter.active_texture_set)
        painter.preview_controller.invalidate.assert_called_once_with()
        painter.label_img_dif.config.assert_called_once_with(
            image=diffuse_placeholder
        )
        painter.label_img_tem.config.assert_called_once_with(
            image=channel_placeholder
        )

    def test_loading_diffuse_replaces_the_authoritative_reference(self):
        replacement = Mock(spec=TextureSet)
        result = SimpleNamespace(
            texture_set=replacement,
            team_color_error=None,
            team_color_path=Path("marine_tem.png"),
            warnings=(),
            width=8,
            height=4,
        )
        painter = SimpleNamespace(
            active_texture_set=Mock(spec=TextureSet),
            texture_loading=Mock(
                load_diffuse_and_companions=Mock(return_value=result)
            ),
            preview_controller=Mock(),
            select_channel=Mock(),
            open_channel=Mock(),
            dialogs=Mock(),
            refresh_workspace=Mock(),
            resize_for_diffuse=Mock(),
        )

        ArmyPainter.load_file(painter, "marine_dif.png")

        self.assertIs(painter.active_texture_set, replacement)
        painter.preview_controller.invalidate.assert_called_once_with()

    def test_no_production_image_workbench_reference_remains(self):
        source_root = Path(__file__).resolve().parents[1] / "src"
        references = []
        for path in source_root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "ImageWorkbench" in source or "img_wbench" in source:
                references.append(path.name)

        self.assertEqual(references, [])
        self.assertNotIn("ImageWorkbench", inspect.getsource(ArmyPainter))


if __name__ == "__main__":
    unittest.main()
