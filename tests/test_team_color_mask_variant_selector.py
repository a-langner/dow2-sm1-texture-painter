import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.image_process import TextureValidationError
from src.team_color_mask_variant import TeamColorMaskVariant
from src.texture_set import TextureSet


class TeamColorMaskVariantSelectorTests(unittest.TestCase):
    def make_painter(self, variants, active=None):
        return SimpleNamespace(
            available_team_color_mask_variants=variants,
            active_team_color_mask_variant=active,
            team_color_mask_variant_selector=Mock(),
            team_color_mask_variant_name=Mock(),
            team_color_mask_variant_filename=Mock(),
            frame_team_color_mask_variant=Mock(),
            _team_color_mask_variant_tooltip=None,
        )

    def test_selector_is_hidden_without_variants(self):
        painter = self.make_painter(())

        ArmyPainter.sync_team_color_mask_variant_selector(painter)

        painter.team_color_mask_variant_selector.configure.assert_any_call(values=())
        painter.team_color_mask_variant_selector.configure.assert_called_with(
            state="readonly"
        )
        painter.team_color_mask_variant_name.set.assert_called_once_with("")
        painter.team_color_mask_variant_filename.set.assert_called_once_with("")
        painter.frame_team_color_mask_variant.pack_forget.assert_called_once_with()
        painter.frame_team_color_mask_variant.pack.assert_not_called()

    def test_selector_is_hidden_for_one_variant(self):
        variant = TeamColorMaskVariant(None, Path("marine_tem.dds"))
        painter = self.make_painter((variant,), variant)

        ArmyPainter.sync_team_color_mask_variant_selector(painter)

        painter.team_color_mask_variant_selector.configure.assert_any_call(
            values=("Default",)
        )
        painter.team_color_mask_variant_selector.configure.assert_called_with(
            state="readonly"
        )
        painter.team_color_mask_variant_name.set.assert_called_once_with("Default")
        painter.team_color_mask_variant_filename.set.assert_called_once_with(
            "marine_tem.dds"
        )
        painter.frame_team_color_mask_variant.pack_forget.assert_called_once_with()

    def test_selector_is_shown_for_multiple_variants(self):
        default = TeamColorMaskVariant(None, Path("marine_tem.dds"))
        numbered = TeamColorMaskVariant(2, Path("marine_tem_2.dds"))
        painter = self.make_painter((default, numbered), numbered)

        ArmyPainter.sync_team_color_mask_variant_selector(painter)

        painter.team_color_mask_variant_selector.configure.assert_has_calls(
            [call(values=("Default", "Variant 2"))]
        )
        painter.team_color_mask_variant_name.set.assert_called_once_with("Variant 2")
        painter.team_color_mask_variant_filename.set.assert_called_once_with(
            "marine_tem_2.dds"
        )
        painter.frame_team_color_mask_variant.pack.assert_called_once_with(
            side="left", fill="x", expand=True, padx=(8, 6), pady=4
        )
        painter.frame_team_color_mask_variant.pack_forget.assert_not_called()

    @patch("src.frame_main.tk.Label")
    @patch("src.frame_main.tk.Toplevel")
    def test_tooltip_shows_only_the_active_filename(self, toplevel_type, label_type):
        tooltip = toplevel_type.return_value
        filename = Mock()
        filename.get.return_value = "sm_armour_mp_basic_arm1_pnt_2.dds"
        painter = SimpleNamespace(
            team_color_mask_variant_filename=filename,
            _team_color_mask_variant_tooltip=None,
        )
        event = SimpleNamespace(x_root=100, y_root=200)

        ArmyPainter.show_team_color_mask_variant_tooltip(painter, event)

        toplevel_type.assert_called_once_with(painter)
        tooltip.wm_overrideredirect.assert_called_once_with(True)
        tooltip.wm_geometry.assert_called_once_with("+112+212")
        self.assertEqual(
            label_type.call_args.kwargs["text"],
            "sm_armour_mp_basic_arm1_pnt_2.dds",
        )
        self.assertNotIn("\\", label_type.call_args.kwargs["text"])
        label_type.return_value.pack.assert_called_once_with()
        self.assertIs(painter._team_color_mask_variant_tooltip, tooltip)

    def test_hiding_tooltip_destroys_the_window(self):
        tooltip = Mock()
        painter = SimpleNamespace(_team_color_mask_variant_tooltip=tooltip)

        ArmyPainter.hide_team_color_mask_variant_tooltip(painter)

        tooltip.destroy.assert_called_once_with()
        self.assertIsNone(painter._team_color_mask_variant_tooltip)

    def test_selecting_variant_replaces_only_mask_state_and_refreshes(self):
        default = TeamColorMaskVariant(None, Path("marine_tem.dds"))
        numbered = TeamColorMaskVariant(2, Path("marine_tem_2.dds"))
        original_textures = Mock(spec=TextureSet)
        replacement_textures = Mock(spec=TextureSet)
        render_settings = object()
        selected_pattern = object()
        painter = self.make_painter((default, numbered), default)
        painter.team_color_mask_variant_name.get.return_value = "Variant 2"
        painter.active_texture_set = original_textures
        painter.texture_loading = Mock()
        painter.texture_loading.load_channel_file.return_value = SimpleNamespace(
            texture_set=replacement_textures
        )
        painter.preview_controller = Mock()
        painter.select_channel = Mock()
        painter.dialogs = Mock()
        painter.render_settings = render_settings
        painter.selected_pattern = selected_pattern
        painter.pattern_controller = Mock()
        color_boxes = [{"bg": color} for color in ("one", "two", "three", "four")]
        painter.frame_color_chooser = SimpleNamespace(color_boxes=color_boxes)

        ArmyPainter.select_team_color_mask_variant(painter)

        painter.texture_loading.load_channel_file.assert_called_once_with(
            original_textures, numbered.path
        )
        self.assertIs(painter.active_texture_set, replacement_textures)
        self.assertIs(painter.active_team_color_mask_variant, numbered)
        self.assertIs(painter.render_settings, render_settings)
        self.assertIs(painter.selected_pattern, selected_pattern)
        self.assertEqual(
            [color_box["bg"] for color_box in color_boxes],
            ["one", "two", "three", "four"],
        )
        painter.pattern_controller.assert_not_called()
        painter.preview_controller.invalidate.assert_called_once_with()
        painter.select_channel.assert_called_once_with()
        painter.dialogs.show_error.assert_not_called()
        painter.team_color_mask_variant_name.set.assert_called_with("Variant 2")
        painter.team_color_mask_variant_filename.set.assert_called_with(
            "marine_tem_2.dds"
        )

    def test_failed_variant_load_preserves_previous_state_and_reports_error(self):
        default = TeamColorMaskVariant(None, Path("marine_tem.dds"))
        numbered = TeamColorMaskVariant(2, Path("marine_tem_2.dds"))
        original_textures = Mock(spec=TextureSet)
        painter = self.make_painter((default, numbered), default)
        painter.team_color_mask_variant_name.get.return_value = "Variant 2"
        painter.active_texture_set = original_textures
        painter.texture_loading = Mock()
        painter.texture_loading.load_channel_file.side_effect = (
            TextureValidationError("file disappeared")
        )
        painter.preview_controller = Mock()
        painter.select_channel = Mock()
        painter.dialogs = Mock()

        ArmyPainter.select_team_color_mask_variant(painter)

        self.assertIs(painter.active_texture_set, original_textures)
        self.assertIs(painter.active_team_color_mask_variant, default)
        painter.preview_controller.invalidate.assert_not_called()
        painter.select_channel.assert_not_called()
        painter.dialogs.show_error.assert_called_once_with(
            title="Invalid team-colour mask",
            message="file disappeared",
        )
        painter.team_color_mask_variant_name.set.assert_called_with("Default")
        painter.team_color_mask_variant_filename.set.assert_called_with(
            "marine_tem.dds"
        )

    def test_workspace_reset_restores_default_mask_variant(self):
        default = TeamColorMaskVariant(None, Path("marine_tem.dds"))
        numbered = TeamColorMaskVariant(2, Path("marine_tem_2.dds"))
        original_textures = Mock(spec=TextureSet)
        replacement_textures = Mock(spec=TextureSet)
        painter = self.make_painter((default, numbered), numbered)
        painter.team_color_mask_variant_name.get.return_value = "Default"
        painter.active_texture_set = original_textures
        painter.texture_loading = Mock()
        painter.texture_loading.load_channel_file.return_value = SimpleNamespace(
            texture_set=replacement_textures
        )
        painter.preview_controller = Mock()
        painter.select_channel = Mock()
        painter.dialogs = Mock()

        ArmyPainter.reset_team_color_mask_variant(painter)

        painter.team_color_mask_variant_name.set.assert_any_call("Default")
        painter.texture_loading.load_channel_file.assert_called_once_with(
            original_textures, default.path
        )
        self.assertIs(painter.active_team_color_mask_variant, default)
        self.assertIs(painter.active_texture_set, replacement_textures)
        painter.preview_controller.invalidate.assert_called_once_with()
        painter.select_channel.assert_called_once_with()

    def test_applying_pattern_colors_does_not_change_active_variant(self):
        default = TeamColorMaskVariant(None, Path("marine_tem.dds"))
        numbered = TeamColorMaskVariant(2, Path("marine_tem_2.dds"))
        textures = Mock(spec=TextureSet)
        color_boxes = [{"bg": "old"} for _ in range(4)]
        painter = SimpleNamespace(
            available_team_color_mask_variants=(default, numbered),
            active_team_color_mask_variant=numbered,
            active_texture_set=textures,
            frame_color_chooser=SimpleNamespace(
                color_boxes=color_boxes,
                draw_rgb_value=Mock(),
            ),
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )

        ArmyPainter._apply_pattern_colors(
            painter,
            ["#111111", "#222222", "#333333", "#444444"],
        )

        self.assertIs(painter.active_team_color_mask_variant, numbered)
        self.assertEqual(
            painter.available_team_color_mask_variants,
            (default, numbered),
        )
        self.assertIs(painter.active_texture_set, textures)
        self.assertEqual(
            [color_box["bg"] for color_box in color_boxes],
            ["#111111", "#222222", "#333333", "#444444"],
        )


if __name__ == "__main__":
    unittest.main()
