import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
import src.color_pattern_handler as pattern_handler
from src.color_pattern_handler import (
    BuiltinPatternModificationError,
    InvalidPatternError,
    PatternNotFoundError,
    UserPatternPersistenceError,
    load_user_patterns,
    update_user_pattern,
)


def colors(*values):
    if values:
        return list(values)
    return ["#112233", "#445566", "#778899", "#aabbcc"]


class UserPatternUpdateTests(unittest.TestCase):
    def setUp(self):
        self.original_users = OrderedDict(pattern_handler.user_color_patterns)
        self.original_all = OrderedDict(pattern_handler.army_color_pattern)
        pattern_handler.user_color_patterns.clear()
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(
            pattern_handler.builtin_color_patterns
        )

    def tearDown(self):
        pattern_handler.user_color_patterns.clear()
        pattern_handler.user_color_patterns.update(self.original_users)
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(self.original_all)

    def seed(self, name, values, path):
        pattern_handler.save(name, values, pattern_path=path)

    def test_updates_existing_pattern_and_all_four_colors(self):
        replacement = colors("#010203", "#141516", "#272829", "#3a3b3c")
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            self.seed("Update Me", colors(), pattern_path)

            with patch.object(
                pattern_handler,
                "_write_user_patterns",
                wraps=pattern_handler._write_user_patterns,
            ) as atomic_write:
                result = update_user_pattern(
                    "  Update Me  ", replacement, pattern_path=pattern_path
                )

            self.assertEqual(result, "Update Me")
            atomic_write.assert_called_once()
            expected = OrderedDict(zip(pattern_handler.color_key, replacement))
            self.assertEqual(pattern_handler.user_color_patterns["Update Me"], expected)
            self.assertEqual(pattern_handler.army_color_pattern["Update Me"], expected)
            self.assertEqual(load_user_patterns(pattern_path)["Update Me"], expected)

    def test_persists_for_a_freshly_loaded_handler_state(self):
        replacement = colors("#abcdef", "#123456", "#654321", "#fedcba")
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            self.seed("Persistent", colors(), pattern_path)
            update_user_pattern("Persistent", replacement, pattern_path)

            reloaded_users = load_user_patterns(pattern_path)
            fresh_all = pattern_handler.get_all_patterns(
                pattern_handler.builtin_color_patterns, reloaded_users
            )

            self.assertEqual(
                fresh_all["Persistent"],
                OrderedDict(zip(pattern_handler.color_key, replacement)),
            )

    def test_preserves_pattern_order(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            for name in ("First", "Second", "Third"):
                self.seed(name, colors(), pattern_path)

            update_user_pattern(
                "Second",
                colors("#abcdef", "#445566", "#778899", "#aabbcc"),
                pattern_path,
            )

            self.assertEqual(
                list(pattern_handler.user_color_patterns),
                ["First", "Second", "Third"],
            )
            self.assertEqual(
                list(load_user_patterns(pattern_path)), ["First", "Second", "Third"]
            )

    def test_rejects_builtin_pattern_without_writing(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            with self.assertRaisesRegex(
                BuiltinPatternModificationError, "cannot be updated"
            ):
                update_user_pattern(builtin_name, colors(), pattern_path)

            self.assertFalse(pattern_path.exists())

    def test_rejects_unknown_pattern_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            with self.assertRaisesRegex(PatternNotFoundError, "not found"):
                update_user_pattern("Unknown", colors(), pattern_path)

            self.assertFalse(pattern_path.exists())

    def test_rejects_invalid_pattern_names_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            for name in (None, "", "   ", 123):
                with self.subTest(name=name):
                    with self.assertRaises(InvalidPatternError):
                        update_user_pattern(name, colors(), pattern_path)

            self.assertFalse(pattern_path.exists())

    def test_rejects_invalid_color_count_and_hexadecimal_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            self.seed("Valid", colors(), pattern_path)
            contents_before = pattern_path.read_bytes()
            pattern_before = OrderedDict(pattern_handler.user_color_patterns["Valid"])

            for invalid_colors in (
                colors()[:3],
                colors() + ["#000000"],
                ["red"] + colors()[1:],
            ):
                with self.subTest(colors=invalid_colors):
                    with self.assertRaises(InvalidPatternError):
                        update_user_pattern("Valid", invalid_colors, pattern_path)
                    self.assertEqual(pattern_path.read_bytes(), contents_before)
                    self.assertEqual(
                        pattern_handler.user_color_patterns["Valid"], pattern_before
                    )

    def test_atomic_failure_preserves_file_and_in_memory_colors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            self.seed("Still Original", colors(), pattern_path)
            file_before = pattern_path.read_bytes()
            users_before = OrderedDict(
                (name, OrderedDict(pattern))
                for name, pattern in pattern_handler.user_color_patterns.items()
            )
            all_before = OrderedDict(
                (name, OrderedDict(pattern))
                for name, pattern in pattern_handler.army_color_pattern.items()
            )

            with patch(
                "src.color_pattern_handler.os.replace",
                side_effect=OSError("simulated failure"),
            ):
                with self.assertRaisesRegex(
                    UserPatternPersistenceError, "simulated failure"
                ):
                    update_user_pattern(
                        "Still Original",
                        colors("#abcdef", "#123456", "#654321", "#fedcba"),
                        pattern_path,
                    )

            self.assertEqual(pattern_path.read_bytes(), file_before)
            self.assertEqual(pattern_handler.user_color_patterns, users_before)
            self.assertEqual(pattern_handler.army_color_pattern, all_before)
            self.assertEqual(
                list(pattern_path.parent.glob(f".{pattern_path.name}.*.tmp")), []
            )

    def test_packaged_resources_remain_unchanged(self):
        packaged_before = pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes()
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            self.seed("External", colors(), pattern_path)

            update_user_pattern(
                "External",
                colors("#abcdef", "#123456", "#654321", "#fedcba"),
                pattern_path,
            )

        self.assertEqual(
            pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes(), packaged_before
        )


if __name__ == "__main__":
    unittest.main()
