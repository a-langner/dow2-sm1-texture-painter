import inspect
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_processing_settings import ColorProcessingSettings
from src.constant import ColorOps
from src.frame_main import ArmyPainter
from src.preview_controller import PreviewController
from src.processing_mode import ProcessingMode
from src.render_settings import DEFAULT_RENDER_SETTINGS
from src.texture_set import TextureSet
from src.team_color_mask_variant import TeamColorMaskVariant


class ActiveTextureLifecycleTests(unittest.TestCase):
    @patch("src.frame_main.ImageTk.PhotoImage", side_effect=lambda image: image)
    def test_original_preview_hold_switches_cached_display_without_rendering(
        self, photo_image
    ):
        original = object()
        processed = object()
        painter = SimpleNamespace(
            active_texture_set=SimpleNamespace(diffuse=original),
            original_preview_image=None,
            processed_preview_image=processed,
            show_original_preview=False,
            img_dif=processed,
            label_img_dif=Mock(),
            preview_controller=Mock(),
        )

        ArmyPainter.begin_show_original_preview(painter)

        self.assertTrue(painter.show_original_preview)
        self.assertIs(painter.img_dif, original)
        painter.label_img_dif.config.assert_called_with(image=original)

        ArmyPainter.end_show_original_preview(painter)

        self.assertFalse(painter.show_original_preview)
        self.assertIs(painter.img_dif, processed)
        painter.label_img_dif.config.assert_called_with(image=processed)
        photo_image.assert_called_once_with(original)
        painter.preview_controller.assert_not_called()

    def test_interrupted_original_preview_cleanup_is_idempotent(self):
        original = object()
        processed = object()
        painter = SimpleNamespace(
            show_original_preview=True,
            original_preview_image=original,
            processed_preview_image=processed,
            img_dif=original,
            label_img_dif=Mock(),
        )

        ArmyPainter.reset_original_preview_state(painter)
        ArmyPainter.end_show_original_preview(painter)

        self.assertFalse(painter.show_original_preview)
        self.assertIsNone(painter.original_preview_image)
        self.assertIs(painter.img_dif, processed)
        painter.label_img_dif.config.assert_called_once_with(image=processed)

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
            available_team_color_mask_variants=(Mock(),),
            active_team_color_mask_variant=Mock(),
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

        ArmyPainter.on_slider_update(painter, 80.0, 110.0, 100.0, 100.0)
        ArmyPainter.on_color_changed(painter, 0, "#102030")

        painter.preview_controller.request_preview.assert_called_once_with()
        painter.preview_controller.request_preview_immediately.assert_called_once_with()

    def test_slider_initialization_without_texture_is_silent(self):
        painter = SimpleNamespace(request_workspace_preview=Mock())

        ArmyPainter.on_slider_update(painter, 75.0, 100.0, 100.0, 100.0)

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

    def test_builtin_pattern_restores_global_default_processing(self):
        import src.color_pattern_handler as pattern_handler

        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        settings = DEFAULT_RENDER_SETTINGS.with_processing_mode(
            ProcessingMode.PER_COLOR
        ).with_color_processing(
            0, ColorProcessingSettings(ColorOps.HARD_LIGHT, 25.0, 150.0)
        )
        painter = SimpleNamespace(
            render_settings=settings,
            frame_color_chooser=SimpleNamespace(
                color_boxes=[{"bg": None} for _ in range(4)],
                draw_rgb_value=Mock(),
            ),
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )

        ArmyPainter._apply_pattern_colors(
            painter,
            pattern_handler.get_pattern_colors(builtin_name),
            SimpleNamespace(name=builtin_name),
        )

        self.assertIs(
            painter.render_settings.processing_mode,
            ProcessingMode.GLOBAL,
        )
        self.assertEqual(
            painter.render_settings.global_processing,
            ColorProcessingSettings(ColorOps.OVERLAY, 75.0, 100.0),
        )
        self.assertEqual(
            painter.render_settings.per_color_processing,
            (painter.render_settings.global_processing,) * 4,
        )

    def test_startup_reset_without_texture_never_submits_preview(self):
        painter = SimpleNamespace(
            active_texture_set=None,
            show_original_preview=True,
            available_team_color_mask_variants=(),
            active_team_color_mask_variant=None,
            preview_controller=Mock(),
            sync_render_settings=Mock(),
            render_settings=DEFAULT_RENDER_SETTINGS.with_processing_mode(
                ProcessingMode.PER_COLOR
            ).with_active_processing(
                ColorProcessingSettings(ColorOps.MULTIPLY, 40, 130, 60, 170)
            ),
            frame_color_op_option=SimpleNamespace(
                var=SimpleNamespace(set=Mock()),
                set_processing_context=Mock(),
            ),
            frame_color_chooser=SimpleNamespace(
                color_boxes=[{"bg": None} for _ in range(4)]
            ),
            frame_army_pattern=SimpleNamespace(clear_selection=Mock()),
            frame_sliders=SimpleNamespace(
                brightness_slider=SimpleNamespace(set=Mock()),
                contrast_slider=SimpleNamespace(set=Mock()),
                saturation_slider=SimpleNamespace(set=Mock()),
                opacity_slider=SimpleNamespace(set=Mock()),
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
        painter.frame_sliders.opacity_slider.set.assert_called_once_with(100.0)
        painter.frame_sliders.saturation_slider.set.assert_called_once_with(100.0)
        painter.frame_army_pattern.clear_selection.assert_called_once_with()
        self.assertIs(
            painter.render_settings.processing_mode,
            ProcessingMode.GLOBAL,
        )
        self.assertFalse(painter.show_original_preview)
        self.assertEqual(
            painter.render_settings.global_processing,
            DEFAULT_RENDER_SETTINGS.global_processing,
        )
        self.assertEqual(
            painter.render_settings.per_color_processing,
            (DEFAULT_RENDER_SETTINGS.global_processing,) * 4,
        )
        painter.frame_color_op_option.var.set.assert_called_with("Overlay")

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
            show_original_preview=True,
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
        self.assertFalse(painter.show_original_preview)
        self.assertEqual(painter.available_team_color_mask_variants, ())
        self.assertIsNone(painter.active_team_color_mask_variant)
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
            show_original_preview=True,
            available_team_color_mask_variants=(Mock(),),
            active_team_color_mask_variant=Mock(),
            preview_controller=Mock(),
            label_img_dif=Mock(),
            label_img_tem=Mock(),
        )

        ArmyPainter.close(painter)

        self.assertIsNone(painter.active_texture_set)
        self.assertFalse(painter.show_original_preview)
        self.assertEqual(painter.available_team_color_mask_variants, ())
        self.assertIsNone(painter.active_team_color_mask_variant)
        painter.preview_controller.invalidate.assert_called_once_with()
        painter.label_img_dif.config.assert_called_once_with(
            image=diffuse_placeholder
        )
        painter.label_img_tem.config.assert_called_once_with(
            image=channel_placeholder
        )
        self.assertEqual(
            create_placeholder.call_args_list[-1].args,
            ("Select Team Color Mask", "L"),
        )

    def test_loading_diffuse_replaces_the_authoritative_reference(self):
        replacement = Mock(spec=TextureSet)
        variant = TeamColorMaskVariant(None, Path("marine_tem.png"))
        render_settings = object()
        selected_pattern = object()
        result = SimpleNamespace(
            texture_set=replacement,
            available_team_color_mask_variants=(variant,),
            active_team_color_mask_variant=variant,
            team_color_mask_error=None,
            team_color_mask_path=Path("marine_tem.png"),
            warnings=(),
            width=8,
            height=4,
        )
        painter = SimpleNamespace(
            active_texture_set=Mock(spec=TextureSet),
            show_original_preview=True,
            texture_loading=Mock(
                load_diffuse_and_companions=Mock(return_value=result)
            ),
            preview_controller=Mock(),
            select_channel=Mock(),
            open_channel=Mock(),
            dialogs=Mock(),
            refresh_workspace=Mock(),
            resize_for_diffuse=Mock(),
            render_settings=render_settings,
            selected_pattern=selected_pattern,
        )

        ArmyPainter.load_file(painter, "marine_dif.png")

        self.assertIs(painter.active_texture_set, replacement)
        self.assertFalse(painter.show_original_preview)
        self.assertEqual(painter.available_team_color_mask_variants, (variant,))
        self.assertIs(painter.active_team_color_mask_variant, variant)
        self.assertIs(painter.render_settings, render_settings)
        self.assertIs(painter.selected_pattern, selected_pattern)
        painter.preview_controller.invalidate.assert_called_once_with()

    def test_manual_mask_load_clears_discovered_variant_state(self):
        replacement = Mock(spec=TextureSet)
        result = SimpleNamespace(texture_set=replacement)
        painter = SimpleNamespace(
            active_texture_set=Mock(spec=TextureSet),
            available_team_color_mask_variants=(Mock(), Mock()),
            active_team_color_mask_variant=Mock(),
            file_selection=SimpleNamespace(
                choose_channel_file=Mock(return_value=Path("manual_mask.dds"))
            ),
            texture_loading=SimpleNamespace(
                load_channel_file=Mock(return_value=result)
            ),
            preview_controller=Mock(),
            select_channel=Mock(),
            dialogs=Mock(),
        )

        ArmyPainter.open_channel(painter)

        self.assertIs(painter.active_texture_set, replacement)
        self.assertEqual(painter.available_team_color_mask_variants, ())
        self.assertIsNone(painter.active_team_color_mask_variant)
        painter.select_channel.assert_called_once_with()

    def test_loading_diffuse_without_mask_clears_previous_variant_state(self):
        replacement = Mock(spec=TextureSet)
        result = SimpleNamespace(
            texture_set=replacement,
            available_team_color_mask_variants=(),
            active_team_color_mask_variant=None,
            team_color_mask_error=None,
            team_color_mask_path=None,
            warnings=(),
            width=8,
            height=4,
        )
        painter = SimpleNamespace(
            texture_naming_profile=Mock(),
            active_texture_set=Mock(spec=TextureSet),
            available_team_color_mask_variants=(Mock(),),
            active_team_color_mask_variant=Mock(),
            texture_loading=SimpleNamespace(
                load_diffuse_and_companions=Mock(return_value=result)
            ),
            preview_controller=Mock(),
            select_game_profile=Mock(),
            select_channel=Mock(),
            open_channel=Mock(),
            dialogs=Mock(),
            refresh_workspace=Mock(),
            resize_for_diffuse=Mock(),
        )

        with patch("src.frame_main.detect_texture_naming_profile", return_value=None):
            ArmyPainter.load_file(painter, "replacement_dif.dds")

        self.assertIs(painter.active_texture_set, replacement)
        self.assertEqual(painter.available_team_color_mask_variants, ())
        self.assertIsNone(painter.active_team_color_mask_variant)
        painter.open_channel.assert_called_once_with()

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
