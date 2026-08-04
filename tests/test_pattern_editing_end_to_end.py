import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import test_support
import src.color_pattern_handler as pattern_handler
from src.frame_main import (
    collection_selection_was_overwritten,
    single_import_selection_policy,
)
from src.widget import PatternSelection, build_pattern_rows, pattern_action_states

ORIGINAL_COLORS = ["#112233", "#445566", "#778899", "#aabbcc"]
UPDATED_COLORS = ["#010203", "#141516", "#272829", "#3a3b3c"]


class PatternEditingEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.original_users = OrderedDict(pattern_handler.user_color_patterns)
        self.original_all = OrderedDict(pattern_handler.army_color_pattern)
        self.original_load_issue = pattern_handler.user_pattern_load_issue
        pattern_handler.user_color_patterns.clear()
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(
            pattern_handler.builtin_color_patterns
        )
        pattern_handler.user_pattern_load_issue = None

    def tearDown(self):
        pattern_handler.user_color_patterns.clear()
        pattern_handler.user_color_patterns.update(self.original_users)
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(self.original_all)
        pattern_handler.user_pattern_load_issue = self.original_load_issue

    def test_update_rename_duplicate_and_reload_lifecycle(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        builtin_colors = pattern_handler.get_pattern_colors(builtin_name)

        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Editable", ORIGINAL_COLORS, pattern_path)
            pattern_handler.update_user_pattern(
                "Editable", UPDATED_COLORS, pattern_path
            )
            renamed = pattern_handler.rename_user_pattern(
                "Editable", "  Renamed Pattern  ", pattern_path
            )
            pattern_handler.save("Built-in Copy", builtin_colors, pattern_path)
            pattern_handler.save(
                "User Copy",
                pattern_handler.get_pattern_colors(renamed),
                pattern_path,
            )

            reloaded = pattern_handler.load_user_patterns(pattern_path)

        self.assertEqual(renamed, "Renamed Pattern")
        self.assertNotIn("Editable", reloaded)
        self.assertEqual(list(reloaded["Renamed Pattern"].values()), UPDATED_COLORS)
        self.assertEqual(list(reloaded["Built-in Copy"].values()), builtin_colors)
        self.assertEqual(list(reloaded["User Copy"].values()), UPDATED_COLORS)
        self.assertEqual(
            list(reloaded), ["Renamed Pattern", "Built-in Copy", "User Copy"]
        )

    def test_action_states_follow_the_complete_dirty_state_cycle(self):
        builtin = PatternSelection("Built-in", False)
        user = PatternSelection("User", True)

        no_selection = pattern_action_states(None)
        builtin_state = pattern_action_states(builtin)
        clean_user = pattern_action_states(user, modified=False)
        dirty_user = pattern_action_states(user, modified=True)
        restored_user = pattern_action_states(
            user,
            modified=not pattern_handler.pattern_colors_equal(
                ORIGINAL_COLORS, ORIGINAL_COLORS
            ),
        )

        for state in (no_selection, builtin_state):
            self.assertEqual(state.update, "disabled")
            self.assertEqual(state.rename, "disabled")
            self.assertEqual(state.delete, "disabled")
        self.assertEqual(clean_user.update, "disabled")
        self.assertEqual(clean_user.rename, "normal")
        self.assertEqual(clean_user.delete, "normal")
        self.assertEqual(dirty_user.update, "normal")
        self.assertEqual(dirty_user.reset, "normal")
        self.assertEqual(restored_user.update, "disabled")
        self.assertEqual(restored_user.reset, "disabled")

        # Brightness and contrast are deliberately absent from color comparison.
        for brightness, contrast in ((0, 0), (75, 100), (200, 200)):
            with self.subTest(brightness=brightness, contrast=contrast):
                self.assertTrue(
                    pattern_handler.pattern_colors_equal(
                        ORIGINAL_COLORS, ORIGINAL_COLORS
                    )
                )

    def test_update_and_rename_clear_or_preserve_dirty_state_as_expected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Editable", ORIGINAL_COLORS, pattern_path)

            self.assertFalse(
                pattern_handler.pattern_colors_equal(
                    UPDATED_COLORS,
                    pattern_handler.get_pattern_colors("Editable"),
                )
            )
            pattern_handler.update_user_pattern(
                "Editable", UPDATED_COLORS, pattern_path
            )
            self.assertTrue(
                pattern_handler.pattern_colors_equal(
                    UPDATED_COLORS,
                    pattern_handler.get_pattern_colors("Editable"),
                )
            )

            dirty_colors = ORIGINAL_COLORS
            renamed = pattern_handler.rename_user_pattern(
                "Editable", "Renamed", pattern_path
            )
            self.assertFalse(
                pattern_handler.pattern_colors_equal(
                    dirty_colors,
                    pattern_handler.get_pattern_colors(renamed),
                )
            )

            reset_colors = pattern_handler.get_pattern_colors(renamed)
            self.assertTrue(
                pattern_handler.pattern_colors_equal(
                    reset_colors,
                    pattern_handler.get_pattern_colors(renamed),
                )
            )

    def test_overwrite_selection_policies_refresh_only_changed_selection(self):
        self.assertEqual(
            single_import_selection_policy("Selected", "Selected", True),
            ("Selected", True),
        )
        self.assertEqual(
            single_import_selection_policy("Selected", "Other", True),
            ("Selected", False),
        )

        analysis = type(
            "Analysis",
            (),
            {"user_conflicts": [type("Imported", (), {"name": "Selected"})()]},
        )()
        self.assertTrue(
            collection_selection_was_overwritten("Selected", analysis, True)
        )
        self.assertFalse(
            collection_selection_was_overwritten("Selected", analysis, False)
        )
        self.assertFalse(collection_selection_was_overwritten("Other", analysis, True))

    def test_internal_names_are_undecorated_and_real_user_data_is_not_used(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            with patch.object(
                pattern_handler,
                "get_user_patterns_path",
                side_effect=AssertionError("real user-data path was accessed"),
            ):
                pattern_handler.save("Undecorated", ORIGINAL_COLORS, pattern_path)
                pattern_handler.update_user_pattern(
                    "Undecorated", UPDATED_COLORS, pattern_path
                )
                pattern_handler.rename_user_pattern(
                    "Undecorated", "Still Undecorated", pattern_path
                )

            rows = {
                row["name"]: row
                for row in build_pattern_rows(pattern_handler.get_all_patterns())
            }

        internal_name = rows["Still Undecorated"]["name"]
        self.assertTrue(rows["Still Undecorated"]["is_user"])
        self.assertTrue(rows["Still Undecorated"]["marker"])
        self.assertNotIn("★", internal_name)
        self.assertNotIn("Modified", internal_name)
        self.assertNotIn("★", pattern_handler.user_color_patterns)
        self.assertNotIn("Modified", pattern_handler.user_color_patterns)
        self.assertNotEqual(test_support.TEST_USER_DATA_DIRECTORY, pattern_path.parent)


if __name__ == "__main__":
    unittest.main()
