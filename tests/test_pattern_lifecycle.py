import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import src.color_pattern_handler as pattern_handler
from src.color_pattern_handler import (
    BuiltinPatternDeletionError,
    PatternNameConflictError,
)
from src.widget import build_pattern_rows


COLORS = ["#112233", "#445566", "#778899", "#aabbcc"]


class PatternLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.original_users = OrderedDict(
            pattern_handler.user_color_patterns
        )
        self.original_all = OrderedDict(pattern_handler.army_color_pattern)
        self.original_load_issue = pattern_handler.user_pattern_load_issue
        pattern_handler.user_pattern_load_issue = None

    def tearDown(self):
        pattern_handler.user_color_patterns.clear()
        pattern_handler.user_color_patterns.update(self.original_users)
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(self.original_all)
        pattern_handler.user_pattern_load_issue = self.original_load_issue

    def test_builtins_load_without_accessing_user_data_directory(self):
        with patch.object(
            pattern_handler,
            "get_user_patterns_path",
            side_effect=PermissionError("application directory is read-only"),
        ):
            builtins = pattern_handler.load_builtin_patterns()

        self.assertIn("Blood Ravens", builtins)
        self.assertGreater(len(builtins), 0)

    def test_first_launch_without_user_file_does_not_create_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = (
                Path(temporary_directory)
                / "not-created"
                / "user_patterns.json"
            )

            users = pattern_handler.load_user_patterns(pattern_path)

            self.assertEqual(users, OrderedDict())
            self.assertFalse(pattern_path.parent.exists())

    def test_complete_save_reload_identify_display_and_delete_lifecycle(self):
        resources_directory = Path("src/resources")
        resources_before = {
            path.name: path.read_bytes()
            for path in resources_directory.iterdir()
            if path.is_file()
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            pattern_handler.save("Lifecycle Pattern", COLORS, pattern_path)
            self.assertTrue(pattern_path.is_file())

            # A fresh load represents the state a newly started handler sees.
            freshly_loaded_users = pattern_handler.load_user_patterns(
                pattern_path
            )
            freshly_combined = pattern_handler.get_all_patterns(
                pattern_handler.builtin_color_patterns,
                freshly_loaded_users,
            )
            self.assertIn("Lifecycle Pattern", freshly_loaded_users)
            self.assertIn("Lifecycle Pattern", freshly_combined)
            self.assertTrue(
                pattern_handler.is_user_pattern("Lifecycle Pattern")
            )

            rows = {
                row["name"]: row
                for row in build_pattern_rows(freshly_combined)
            }
            self.assertEqual(rows["Lifecycle Pattern"]["marker"], "★")
            self.assertTrue(rows["Lifecycle Pattern"]["is_user"])
            self.assertNotIn("★", rows["Lifecycle Pattern"]["name"])
            self.assertEqual(rows["Blood Ravens"]["marker"], "")
            self.assertFalse(rows["Blood Ravens"]["is_user"])

            with self.assertRaises(PatternNameConflictError):
                pattern_handler.save("Blood Ravens", COLORS, pattern_path)
            with self.assertRaises(BuiltinPatternDeletionError):
                pattern_handler.delete("Blood Ravens", pattern_path)

            pattern_handler.delete("Lifecycle Pattern", pattern_path)
            users_after_restart = pattern_handler.load_user_patterns(
                pattern_path
            )
            self.assertNotIn("Lifecycle Pattern", users_after_restart)

        resources_after = {
            path.name: path.read_bytes()
            for path in resources_directory.iterdir()
            if path.is_file()
        }
        self.assertEqual(resources_after, resources_before)


if __name__ == "__main__":
    unittest.main()
