import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.texture_naming import DOW2_TEXTURE_NAMING, SM1_TEXTURE_NAMING


class GameProfileSelectionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
