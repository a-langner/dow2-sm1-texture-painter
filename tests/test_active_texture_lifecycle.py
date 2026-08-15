import inspect
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.preview_controller import PreviewController
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

        painter.request_workspace_preview = lambda **options: (
            ArmyPainter.request_workspace_preview(painter, **options)
        )

        ArmyPainter.refresh_workspace(painter)

        painter.preview_controller.invalidate.assert_called_once_with()
        painter.preview_controller.request_preview_immediately.assert_not_called()
        painter.sync_render_settings.assert_not_called()

    def test_debounced_request_without_active_texture_is_not_submitted(self):
        painter = SimpleNamespace(
            active_texture_set=None,
            preview_controller=Mock(),
            sync_render_settings=Mock(),
        )

        ArmyPainter.request_workspace_preview(painter)

        painter.preview_controller.invalidate.assert_called_once_with()
        painter.preview_controller.request_preview.assert_not_called()
        painter.sync_render_settings.assert_not_called()

    def test_loaded_texture_allows_debounced_and_immediate_previews(self):
        painter = SimpleNamespace(
            active_texture_set=Mock(spec=TextureSet),
            preview_controller=Mock(),
            sync_render_settings=Mock(),
        )

        ArmyPainter.request_workspace_preview(painter)
        ArmyPainter.request_workspace_preview(painter, immediate=True)

        self.assertEqual(painter.sync_render_settings.call_count, 2)
        painter.preview_controller.request_preview.assert_called_once_with()
        painter.preview_controller.request_preview_immediately.assert_called_once_with()
        painter.preview_controller.invalidate.assert_not_called()

    def test_loaded_texture_slider_and_color_changes_still_schedule(self):
        painter = SimpleNamespace(
            active_texture_set=Mock(spec=TextureSet),
            preview_controller=Mock(),
            sync_render_settings=Mock(),
            update_pattern_action_states=Mock(),
        )
        painter.request_workspace_preview = lambda **options: (
            ArmyPainter.request_workspace_preview(painter, **options)
        )
        painter.refresh_workspace = lambda: ArmyPainter.refresh_workspace(painter)

        ArmyPainter.on_slider_update(painter, 80.0, 110.0)
        ArmyPainter.on_color_changed(painter, 0, "#102030")

        painter.preview_controller.request_preview.assert_called_once_with()
        painter.preview_controller.request_preview_immediately.assert_called_once_with()

    def test_slider_initialization_without_texture_is_silent(self):
        painter = SimpleNamespace(request_workspace_preview=Mock())

        ArmyPainter.on_slider_update(painter, 75.0, 100.0)

        painter.request_workspace_preview.assert_called_once_with()

    def test_color_change_without_texture_uses_guarded_preview_boundary(self):
        painter = SimpleNamespace(
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )

        ArmyPainter.on_color_changed(painter, 0, "#808080")

        painter.refresh_workspace.assert_called_once_with()

    def test_pattern_application_without_texture_uses_guarded_preview_boundary(self):
        color_boxes = [{"bg": None} for _ in range(4)]
        painter = SimpleNamespace(
            frame_color_chooser=SimpleNamespace(
                color_boxes=color_boxes,
                draw_rgb_value=Mock(),
            ),
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )

        ArmyPainter._apply_pattern_colors(
            painter,
            ("#101010", "#202020", "#303030", "#404040"),
        )

        painter.refresh_workspace.assert_called_once_with()

    def test_startup_reset_without_texture_never_submits_preview(self):
        painter = SimpleNamespace(
            active_texture_set=None,
            preview_controller=Mock(),
            sync_render_settings=Mock(),
            frame_color_chooser=SimpleNamespace(
                color_boxes=[{"bg": None} for _ in range(4)]
            ),
            frame_sliders=SimpleNamespace(
                brightness_slider=SimpleNamespace(set=Mock()),
                contrast_slider=SimpleNamespace(set=Mock()),
            ),
            frame_channel_select=SimpleNamespace(
                lb=SimpleNamespace(selection_set=Mock())
            ),
            update_pattern_action_states=Mock(),
            after_idle=Mock(),
            show_user_pattern_load_warning=Mock(),
        )
        painter.request_workspace_preview = lambda **options: (
            ArmyPainter.request_workspace_preview(painter, **options)
        )
        painter.refresh_workspace = lambda: ArmyPainter.refresh_workspace(painter)
        painter.select_channel = lambda: ArmyPainter.select_channel(painter)
        painter.reset_workspace = lambda: ArmyPainter.reset_workspace(painter)

        ArmyPainter._initialize_view_state(painter)

        painter.preview_controller.invalidate.assert_called()
        painter.preview_controller.request_preview.assert_not_called()
        painter.preview_controller.request_preview_immediately.assert_not_called()
        painter.sync_render_settings.assert_not_called()

    @patch("src.frame_main.ImageTk.PhotoImage", side_effect=lambda image: image)
    @patch("src.frame_main.create_placeholder_img", side_effect=(object(), object()))
    def test_pending_debounce_then_close_never_calls_snapshot_provider(
        self, create_placeholder, photo_image
    ):
        callbacks = {}
        snapshot_provider = Mock()

        def schedule_after(delay, callback):
            callbacks[1] = callback
            return 1

        controller = PreviewController(
            renderer=Mock(),
            snapshot_provider=snapshot_provider,
            executor=Mock(),
            schedule_after=schedule_after,
            cancel_scheduled=lambda callback_id: callbacks.pop(callback_id, None),
            on_preview_ready=Mock(),
            on_preview_error=Mock(),
            debounce_ms=120,
        )
        painter = SimpleNamespace(
            active_texture_set=Mock(spec=TextureSet),
            preview_controller=controller,
            sync_render_settings=Mock(),
            label_img_dif=Mock(),
            label_img_tem=Mock(),
        )

        ArmyPainter.request_workspace_preview(painter)
        self.assertEqual(len(callbacks), 1)
        ArmyPainter.close(painter)

        self.assertEqual(callbacks, {})
        self.assertIsNone(painter.active_texture_set)
        snapshot_provider.assert_not_called()

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
            team_color_mask_error=None,
            team_color_mask_path=Path("marine_tem.png"),
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
