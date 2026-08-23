import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from src.update_check import (
    GITHUB_LATEST_RELEASE_API_URL,
    GITHUB_RELEASES_URL,
    GitHubRelease,
    LATEST_VERSION_MESSAGE,
    NO_PUBLISHED_RELEASE_MESSAGE,
    UPDATE_FAILURE_MESSAGE,
    UpdateStatus,
    check_for_updates,
    compare_release_versions,
    fetch_latest_stable_release,
    parse_release_version,
    interpret_latest_release,
)


class UpdateCheckTests(unittest.TestCase):
    def test_interprets_latest_newer_and_no_release_states(self):
        latest = interpret_latest_release(GitHubRelease("v1.0", None), "1.0")
        newer = interpret_latest_release(
            GitHubRelease("v1.1", "https://github.com/example/releases/tag/v1.1"),
            "1.0",
        )
        no_release = interpret_latest_release(None, "1.0")

        self.assertEqual(latest.status, UpdateStatus.LATEST)
        self.assertEqual(latest.message, LATEST_VERSION_MESSAGE)
        self.assertIsNone(latest.download_url)
        self.assertEqual(newer.status, UpdateStatus.NEWER)
        self.assertEqual(newer.message, "Version 1.1 is available.")
        self.assertEqual(
            newer.download_url,
            "https://github.com/example/releases/tag/v1.1",
        )
        self.assertEqual(no_release.status, UpdateStatus.NO_RELEASE)
        self.assertEqual(no_release.message, NO_PUBLISHED_RELEASE_MESSAGE)

    def test_malformed_tag_and_network_failure_return_safe_message(self):
        malformed = interpret_latest_release(GitHubRelease("release-one", {}))
        self.assertEqual(malformed.status, UpdateStatus.FAILURE)
        self.assertEqual(malformed.message, UPDATE_FAILURE_MESSAGE)
        self.assertNotIn("release-one", malformed.message)

        with patch(
            "src.update_check.fetch_latest_stable_release",
            side_effect=OSError("private network detail"),
        ):
            failure = check_for_updates()

        self.assertEqual(failure.status, UpdateStatus.FAILURE)
        self.assertEqual(failure.message, UPDATE_FAILURE_MESSAGE)
        self.assertNotIn("private network detail", failure.message)

    def test_newer_release_with_unexpected_page_uses_safe_releases_page(self):
        result = interpret_latest_release(GitHubRelease("v2.0", None), "1.0")

        self.assertEqual(result.status, UpdateStatus.NEWER)
        self.assertEqual(result.download_url, GITHUB_RELEASES_URL)

    @patch("src.update_check.urlopen")
    def test_missing_latest_release_is_a_normal_empty_result(self, urlopen):
        urlopen.side_effect = HTTPError(
            GITHUB_LATEST_RELEASE_API_URL,
            404,
            "Not Found",
            hdrs=None,
            fp=None,
        )

        release = fetch_latest_stable_release()

        self.assertIsNone(release)
        self.assertEqual(
            NO_PUBLISHED_RELEASE_MESSAGE,
            "No published release is available yet.",
        )

    @patch("src.update_check.urlopen")
    def test_non_missing_http_failure_is_not_misreported_as_no_release(
        self,
        urlopen,
    ):
        failure = HTTPError(
            GITHUB_LATEST_RELEASE_API_URL,
            503,
            "Unavailable",
            hdrs=None,
            fp=None,
        )
        urlopen.side_effect = failure

        with self.assertRaises(HTTPError) as raised:
            fetch_latest_stable_release()

        self.assertIs(raised.exception, failure)

    def test_semantic_version_comparison_is_numeric_and_normalizes_v_prefix(self):
        self.assertEqual(compare_release_versions("1.0", "v1.0"), 0)
        self.assertGreater(compare_release_versions("1.1", "1.0"), 0)
        self.assertGreater(compare_release_versions("1.10", "1.9"), 0)
        self.assertGreater(compare_release_versions("2.0", "1.10"), 0)
        self.assertLess(compare_release_versions("1.0", "1.1"), 0)
        self.assertEqual(compare_release_versions("1.0.0", "1"), 0)

    def test_malformed_or_nonstable_versions_are_rejected(self):
        for value in ("", "v", "1.x", "1.0-beta", "1..0"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_release_version(value)

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
