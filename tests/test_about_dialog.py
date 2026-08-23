import unittest
from unittest.mock import Mock, patch

from src.app_identity import APP_NAME, APP_VERSION
from src.update_check import UpdateCheckResult, UpdateStatus
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
    def test_update_result_only_exposes_download_for_newer_release(self):
        dialog = object.__new__(AboutDialog)
        dialog.update_status_label = Mock()
        dialog.update_button = Mock()
        dialog.download_button = Mock()
        dialog.update_download_url = None
        dialog.update_check_in_progress = True

        dialog.show_update_result(
            UpdateCheckResult(UpdateStatus.LATEST, "You are using the latest version.")
        )
        self.assertIsNone(dialog.update_download_url)
        self.assertFalse(dialog.update_check_in_progress)
        dialog.update_button.configure.assert_called_once_with(state="normal")
        dialog.download_button.pack_forget.assert_called_once_with()

        dialog.download_button.reset_mock()
        result = UpdateCheckResult(
            UpdateStatus.NEWER,
            "Version 1.1 is available.",
            "https://github.com/example/releases/tag/v1.1",
        )
        dialog.show_update_result(result)
        self.assertEqual(dialog.update_download_url, result.download_url)
        dialog.update_status_label.configure.assert_called_with(text=result.message)
        dialog.download_button.pack.assert_called_once_with(pady=(8, 0))

    @patch.object(AboutDialog, "open_link")
    def test_open_download_page_uses_validated_result_url(self, open_link):
        dialog = object.__new__(AboutDialog)
        dialog.update_download_url = "https://github.com/example/releases/tag/v1.1"

        dialog.open_update_download_page()

        open_link.assert_called_once_with(dialog.update_download_url)

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
        dialog.update_check_in_progress = False
        dialog.update_button = Mock()
        dialog.update_status_label = Mock()
        dialog.download_button = Mock()
        dialog.update_download_url = "https://github.com/old"

        self.assertTrue(dialog.request_update_check())
        self.assertFalse(dialog.request_update_check())

        dialog.event_generate.assert_called_once_with("<<CheckForUpdates>>")
        dialog.update_button.configure.assert_called_once_with(state="disabled")
        dialog.update_status_label.configure.assert_called_once_with(
            text="Checking..."
        )
        dialog.download_button.pack_forget.assert_called_once_with()
        self.assertIsNone(dialog.update_download_url)

    def test_position_restores_with_clamping_and_saves_independently(self):
        dialog = object.__new__(AboutDialog)
        dialog.settings = Mock()
        dialog.settings.about_dialog_position = (1900, 1000)
        dialog.update_idletasks = Mock()
        dialog.winfo_width = Mock(return_value=440)
        dialog.winfo_height = Mock(return_value=360)
        dialog.winfo_vrootx = Mock(return_value=0)
        dialog.winfo_vrooty = Mock(return_value=0)
        dialog.winfo_vrootwidth = Mock(return_value=1920)
        dialog.winfo_vrootheight = Mock(return_value=1080)
        dialog.winfo_x = Mock(return_value=1480)
        dialog.winfo_y = Mock(return_value=720)
        dialog.geometry = Mock()

        dialog._restore_position()
        dialog._save_position()

        dialog.geometry.assert_called_once_with("+1480+720")
        dialog.settings.set_about_dialog_position.assert_called_once_with(
            (1480, 720)
        )


if __name__ == "__main__":
    unittest.main()
