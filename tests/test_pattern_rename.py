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
    PatternAlreadyExistsError,
    PatternNameConflictError,
    PatternNotFoundError,
    UserPatternPersistenceError,
    load_user_patterns,
    rename_user_pattern,
)


def colors(primary="#112233"):
    return [primary, "#445566", "#778899", "#aabbcc"]


class UserPatternRenameTests(unittest.TestCase):
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

    def test_renames_pattern_preserving_colors_order_and_compatibility_view(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            self.seed("First", colors("#010101"), pattern_path)
            self.seed("Old Name", colors("#020202"), pattern_path)
            self.seed("Third", colors("#030303"), pattern_path)
            colors_before = OrderedDict(pattern_handler.user_color_patterns["Old Name"])

            with patch.object(
                pattern_handler,
                "_write_user_patterns",
                wraps=pattern_handler._write_user_patterns,
            ) as atomic_write:
                result = rename_user_pattern(
                    "  Old Name  ", "  New Name  ", pattern_path
                )

            self.assertEqual(result, "New Name")
            atomic_write.assert_called_once()
            self.assertEqual(
                list(pattern_handler.user_color_patterns),
                ["First", "New Name", "Third"],
            )
            self.assertEqual(
                pattern_handler.user_color_patterns["New Name"], colors_before
            )
            self.assertEqual(
                pattern_handler.army_color_pattern["New Name"], colors_before
            )
            self.assertNotIn("Old Name", pattern_handler.user_color_patterns)
            self.assertNotIn("Old Name", pattern_handler.army_color_pattern)

    def test_rename_persists_after_reload(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            self.seed("Before", colors("#abcdef"), pattern_path)

            rename_user_pattern("Before", "After", pattern_path)
            reloaded = load_user_patterns(pattern_path)

            self.assertEqual(list(reloaded), ["After"])
            self.assertEqual(
                reloaded["After"],
                OrderedDict(zip(pattern_handler.color_key, colors("#abcdef"))),
            )

    def test_rejects_builtin_and_unknown_old_names(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            with self.assertRaisesRegex(
                BuiltinPatternModificationError, "cannot be renamed"
            ):
                rename_user_pattern(builtin_name, "New", pattern_path)
            with self.assertRaisesRegex(PatternNotFoundError, "not found"):
                rename_user_pattern("Unknown", "New", pattern_path)

            self.assertFalse(pattern_path.exists())

    def test_rejects_builtin_and_user_name_collisions(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            self.seed("Rename Me", colors(), pattern_path)
            self.seed("Existing", colors("#abcdef"), pattern_path)
            file_before = pattern_path.read_bytes()

            with self.assertRaisesRegex(PatternNameConflictError, "built-in"):
                rename_user_pattern("Rename Me", builtin_name, pattern_path)
            with self.assertRaisesRegex(PatternAlreadyExistsError, "already exists"):
                rename_user_pattern("Rename Me", "Existing", pattern_path)

            self.assertEqual(pattern_path.read_bytes(), file_before)
            self.assertIn("Rename Me", pattern_handler.user_color_patterns)

    def test_rejects_invalid_new_names(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            self.seed("Original", colors(), pattern_path)
            file_before = pattern_path.read_bytes()

            for new_name in (None, "", "   ", 123):
                with self.subTest(new_name=new_name):
                    with self.assertRaises(InvalidPatternError):
                        rename_user_pattern("Original", new_name, pattern_path)

            self.assertEqual(pattern_path.read_bytes(), file_before)
            self.assertIn("Original", pattern_handler.user_color_patterns)

    def test_rejects_invalid_old_names(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            for old_name in (None, "", "   ", 123):
                with self.subTest(old_name=old_name):
                    with self.assertRaises(InvalidPatternError):
                        rename_user_pattern(old_name, "New Name", pattern_path)

            self.assertFalse(pattern_path.exists())

    def test_same_normalized_name_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            self.seed("Same Name", colors(), pattern_path)
            file_before = pattern_path.read_bytes()

            with patch.object(pattern_handler, "_write_user_patterns") as atomic_write:
                result = rename_user_pattern(
                    " Same Name ", "  Same Name  ", pattern_path
                )

            self.assertEqual(result, "Same Name")
            atomic_write.assert_not_called()
            self.assertEqual(pattern_path.read_bytes(), file_before)
            self.assertEqual(list(pattern_handler.user_color_patterns), ["Same Name"])

    def test_atomic_failure_preserves_file_names_and_memory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            self.seed("Before", colors(), pattern_path)
            self.seed("Keep", colors("#abcdef"), pattern_path)
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
                    rename_user_pattern("Before", "After", pattern_path)

            self.assertEqual(pattern_path.read_bytes(), file_before)
            self.assertEqual(pattern_handler.user_color_patterns, users_before)
            self.assertEqual(pattern_handler.army_color_pattern, all_before)
            self.assertIn("Before", pattern_handler.user_color_patterns)
            self.assertNotIn("After", pattern_handler.user_color_patterns)
            self.assertEqual(
                list(pattern_path.parent.glob(f".{pattern_path.name}.*.tmp")), []
            )


if __name__ == "__main__":
    unittest.main()
