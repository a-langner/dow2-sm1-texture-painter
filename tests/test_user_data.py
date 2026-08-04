import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.user_data import (
    APP_NAME,
    USER_PATTERNS_FILENAME,
    SETTINGS_FILENAME,
    get_settings_path,
    get_user_patterns_path,
)


class UserPatternsPathTests(unittest.TestCase):
    def test_uses_platform_user_data_directory(self):
        expected_directory = Path("platform-data") / "application"

        with patch(
            "src.user_data.user_data_path", return_value=expected_directory
        ) as mocked_user_data_path:
            result = get_user_patterns_path()

        mocked_user_data_path.assert_called_once_with(
            APP_NAME, appauthor=False
        )
        self.assertEqual(result, expected_directory / USER_PATTERNS_FILENAME)

    def test_override_does_not_create_parent_by_default(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory) / "not-created"

            result = get_user_patterns_path(data_directory=data_directory)

            self.assertEqual(result, data_directory / USER_PATTERNS_FILENAME)
            self.assertFalse(data_directory.exists())

    def test_parent_is_created_only_when_requested(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory) / "created"

            result = get_user_patterns_path(
                data_directory=data_directory, create_parent=True
            )

            self.assertTrue(data_directory.is_dir())
            self.assertFalse(result.exists())

    def test_settings_path_uses_same_application_data_directory(self):
        expected_directory = Path("platform-data") / "application"

        with patch(
            "src.user_data.user_data_path", return_value=expected_directory
        ):
            result = get_settings_path()

        self.assertEqual(result, expected_directory / SETTINGS_FILENAME)


if __name__ == "__main__":
    unittest.main()
