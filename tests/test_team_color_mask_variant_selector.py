import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

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
            frame_team_color_mask_variant=Mock(),
        )

    def test_selector_is_hidden_without_variants(self):
        painter = self.make_painter(())

        ArmyPainter.sync_team_color_mask_variant_selector(painter)

        painter.team_color_mask_variant_selector.configure.assert_called_once_with(
            values=()
        )
        painter.team_color_mask_variant_name.set.assert_called_once_with("")
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
        painter.frame_team_color_mask_variant.pack.assert_called_once_with(
            side="right", padx=6, pady=4
        )
        painter.frame_team_color_mask_variant.pack_forget.assert_not_called()


if __name__ == "__main__":
    unittest.main()
