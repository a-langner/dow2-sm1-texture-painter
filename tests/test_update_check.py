import io
import json
import unittest
from unittest.mock import patch

from src.update_check import (
    GITHUB_LATEST_RELEASE_API_URL,
    GITHUB_RELEASES_URL,
    GitHubRelease,
    fetch_latest_stable_release,
)


class UpdateCheckTests(unittest.TestCase):
    @patch("src.update_check.urlopen")
    def test_fetches_public_latest_stable_release_without_authentication(
        self,
        urlopen,
    ):
        response = io.BytesIO(
            json.dumps(
                {
                    "tag_name": "v1.2",
                    "html_url": "https://github.com/a-langner/"
                    "dow2-sm1-texture-painter/releases/tag/v1.2",
                }
            ).encode("utf-8")
        )
        urlopen.return_value = response

        release = fetch_latest_stable_release(timeout=3.5)

        self.assertEqual(
            release,
            GitHubRelease(
                "v1.2",
                "https://github.com/a-langner/"
                "dow2-sm1-texture-painter/releases/tag/v1.2",
            ),
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, GITHUB_LATEST_RELEASE_API_URL)
        self.assertEqual(urlopen.call_args.kwargs, {"timeout": 3.5})
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
        self.assertIn("1.0", request.get_header("User-agent"))

    def test_release_urls_target_the_configured_public_repository(self):
        self.assertEqual(
            GITHUB_LATEST_RELEASE_API_URL,
            "https://api.github.com/repos/a-langner/"
            "dow2-sm1-texture-painter/releases/latest",
        )
        self.assertEqual(
            GITHUB_RELEASES_URL,
            "https://github.com/a-langner/dow2-sm1-texture-painter/releases",
        )


if __name__ == "__main__":
    unittest.main()
