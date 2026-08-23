import unittest
from unittest.mock import Mock, patch

from src.app_identity import APP_NAME, APP_VERSION
from src.widget import (
    ABOUT_CITADEL_ATTRIBUTION,
    ABOUT_DESCRIPTION,
    ABOUT_DISCLAIMER,
    ABOUT_MAINTAINER,
    ABOUT_MAINTAINER_URL,
    ABOUT_ORIGINAL_AUTHOR,
    ABOUT_ORIGINAL_AUTHOR_URL,
    ABOUT_CITADEL_DATA_URL,
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
        self.assertEqual(
            ABOUT_MAINTAINER_URL,
            "https://github.com/a-langner/dow2-sm1-texture-painter",
        )
        self.assertEqual(
            ABOUT_ORIGINAL_AUTHOR_URL,
            "https://github.com/Jaccouille/dow2-texture-painter",
        )
        self.assertEqual(
            ABOUT_CITADEL_DATA_URL,
            "https://github.com/Arcturus5404/miniature-paints",
        )

    @patch("src.widget.open_url_in_default_browser")
    def test_about_links_use_shared_default_browser_helper(self, open_url):
        AboutDialog.open_link(ABOUT_MAINTAINER_URL)
        AboutDialog.open_link(ABOUT_ORIGINAL_AUTHOR_URL)
        AboutDialog.open_link(ABOUT_CITADEL_DATA_URL)

        self.assertEqual(
            [call.args[0] for call in open_url.call_args_list],
            [
                ABOUT_MAINTAINER_URL,
                ABOUT_ORIGINAL_AUTHOR_URL,
                ABOUT_CITADEL_DATA_URL,
            ],
        )

    def test_manual_update_action_has_dedicated_event_seam(self):
        dialog = object.__new__(AboutDialog)
        dialog.event_generate = Mock()

        dialog.request_update_check()

        dialog.event_generate.assert_called_once_with("<<CheckForUpdates>>")


if __name__ == "__main__":
    unittest.main()
