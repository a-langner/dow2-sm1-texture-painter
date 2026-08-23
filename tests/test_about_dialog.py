import unittest
from unittest.mock import Mock

from src.app_identity import APP_NAME, APP_VERSION
from src.widget import (
    ABOUT_CITADEL_ATTRIBUTION,
    ABOUT_DESCRIPTION,
    ABOUT_DISCLAIMER,
    ABOUT_MAINTAINER,
    ABOUT_ORIGINAL_AUTHOR,
    AboutDialog,
)


class AboutDialogTests(unittest.TestCase):
    def test_about_content_uses_release_identity_and_required_credits(self):
        self.assertEqual(APP_NAME, "Army Painter")
        self.assertEqual(APP_VERSION, "1.0")
        self.assertEqual(
            ABOUT_DESCRIPTION,
            "A GUI application for easily colorizing Dawn of War II and "
            "Warhammer 40,000: Space Marine textures.",
        )
        self.assertEqual(ABOUT_MAINTAINER, "a-langner (Andreas Langner)")
        self.assertEqual(ABOUT_ORIGINAL_AUTHOR, "Jaccouille (Marc Szilagyi)")
        self.assertEqual(
            ABOUT_CITADEL_ATTRIBUTION,
            "Arcturus5404/miniature-paints — MIT License",
        )
        self.assertIn("unofficial community tool", ABOUT_DISCLAIMER)
        self.assertIn("Games Workshop", ABOUT_DISCLAIMER)
        self.assertIn("Relic Entertainment", ABOUT_DISCLAIMER)

    def test_manual_update_action_has_dedicated_event_seam(self):
        dialog = object.__new__(AboutDialog)
        dialog.event_generate = Mock()

        dialog.request_update_check()

        dialog.event_generate.assert_called_once_with("<<CheckForUpdates>>")


if __name__ == "__main__":
    unittest.main()
