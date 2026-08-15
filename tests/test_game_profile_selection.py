import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.texture_naming import DOW2_TEXTURE_NAMING, SM1_TEXTURE_NAMING


class GameProfileSelectionTests(unittest.TestCase):
    @staticmethod
    def _load_result():
        return SimpleNamespace(
            texture_set=object(),
            team_color_mask_error=None,
            team_color_mask_path=Path("unit_pnt.dds"),
            warnings=(),
            width=8,
            height=4,
        )

    def test_selecting_sm1_updates_persistence_and_texture_loading(self):
        settings = SimpleNamespace(
            path=Path("settings.json"),
            set_game_profile_id=Mock(),
        )
        painter = SimpleNamespace(
            settings=settings,
            texture_naming_profile=DOW2_TEXTURE_NAMING,
            texture_loading=Mock(),
            game_profile_id=Mock(),
        )

        ArmyPainter.select_game_profile(painter, "sm1")

        settings.set_game_profile_id.assert_called_once_with("sm1")
        self.assertIs(painter.texture_naming_profile, SM1_TEXTURE_NAMING)
        self.assertIs(
            painter.texture_loading.naming_profile,
            SM1_TEXTURE_NAMING,
        )
        painter.game_profile_id.set.assert_called_once_with("sm1")

    def test_unknown_profile_is_rejected_without_changing_state(self):
        settings = SimpleNamespace(
            path=Path("settings.json"),
            set_game_profile_id=Mock(),
        )
        original_loader = Mock()
        painter = SimpleNamespace(
            settings=settings,
            texture_naming_profile=DOW2_TEXTURE_NAMING,
            texture_loading=original_loader,
            game_profile_id=Mock(),
        )

        with self.assertRaisesRegex(ValueError, "Unknown game profile ID"):
            ArmyPainter.select_game_profile(painter, "unknown")

        settings.set_game_profile_id.assert_not_called()
        self.assertIs(painter.texture_naming_profile, DOW2_TEXTURE_NAMING)
        self.assertIs(painter.texture_loading, original_loader)

    def test_unambiguous_detection_switches_before_loading_companions(self):
        sm1_loader = Mock(
            load_diffuse_and_companions=Mock(return_value=self._load_result())
        )
        painter = SimpleNamespace(
            texture_naming_profile=DOW2_TEXTURE_NAMING,
            texture_loading=Mock(),
            select_game_profile=Mock(),
            preview_controller=Mock(),
            select_channel=Mock(),
            open_channel=Mock(),
            dialogs=Mock(),
            refresh_workspace=Mock(),
            resize_for_diffuse=Mock(),
        )

        def switch_profile(profile_id):
            self.assertEqual(profile_id, "sm1")
            painter.texture_naming_profile = SM1_TEXTURE_NAMING
            painter.texture_loading = sm1_loader

        painter.select_game_profile.side_effect = switch_profile
        with patch(
            "src.frame_main.detect_texture_naming_profile",
            return_value=SM1_TEXTURE_NAMING,
        ):
            ArmyPainter.load_file(painter, "unit_dif.dds")

        painter.select_game_profile.assert_called_once_with("sm1")
        sm1_loader.load_diffuse_and_companions.assert_called_once_with(
            Path("unit_dif.dds")
        )

    def test_ambiguous_detection_keeps_manual_profile(self):
        loader = Mock(
            load_diffuse_and_companions=Mock(return_value=self._load_result())
        )
        painter = SimpleNamespace(
            texture_naming_profile=DOW2_TEXTURE_NAMING,
            texture_loading=loader,
            select_game_profile=Mock(),
            preview_controller=Mock(),
            select_channel=Mock(),
            open_channel=Mock(),
            dialogs=Mock(),
            refresh_workspace=Mock(),
            resize_for_diffuse=Mock(),
        )

        with patch(
            "src.frame_main.detect_texture_naming_profile",
            return_value=None,
        ):
            ArmyPainter.load_file(painter, "unit_dif.dds")

        painter.select_game_profile.assert_not_called()
        self.assertIs(painter.texture_naming_profile, DOW2_TEXTURE_NAMING)
        loader.load_diffuse_and_companions.assert_called_once_with(
            Path("unit_dif.dds")
        )


if __name__ == "__main__":
    unittest.main()
