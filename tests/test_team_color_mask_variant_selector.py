import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.team_color_mask_variant import TeamColorMaskVariant


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

        painter.team_color_mask_variant_selector.configure.assert_called_once_with(
            values=()
        )
        painter.team_color_mask_variant_name.set.assert_called_once_with("")
        painter.team_color_mask_variant_filename.set.assert_called_once_with("")
        painter.frame_team_color_mask_variant.pack_forget.assert_called_once_with()
        painter.frame_team_color_mask_variant.pack.assert_not_called()

    def test_selector_is_hidden_for_one_variant(self):
        variant = TeamColorMaskVariant(None, Path("marine_tem.dds"))
        painter = self.make_painter((variant,), variant)

        ArmyPainter.sync_team_color_mask_variant_selector(painter)

        painter.team_color_mask_variant_selector.configure.assert_called_once_with(
            values=("Default",)
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
            side="right", padx=6, pady=4
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


if __name__ == "__main__":
    unittest.main()
