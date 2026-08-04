import json
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
import src.color_pattern_handler as pattern_handler
from src.color_pattern_handler import color_key, is_user_pattern, load_user_patterns
from src.pattern_exchange import (
    PATTERN_EXCHANGE_FORMAT,
    PATTERN_EXCHANGE_VERSION,
    BuiltinPatternImportConflictError,
    ImportedPattern,
    InvalidPatternImportNameError,
    UserPatternImportConflictError,
    import_pattern,
    read_pattern_file,
)


def colors(primary="#112233"):
    return OrderedDict(zip(color_key, (primary, "#445566", "#778899", "#aabbcc")))


class PatternImportTests(unittest.TestCase):
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

    def test_read_file_is_separate_from_import_and_imports_new_pattern(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            exchange_path = root / "new.pattern.json"
            user_path = root / "user_patterns.json"
            exchange_path.write_text(
                json.dumps(
                    {
                        "format": PATTERN_EXCHANGE_FORMAT,
                        "version": PATTERN_EXCHANGE_VERSION,
                        "name": "  Imported  ",
                        "colors": colors(),
                    }
                ),
                encoding="utf-8",
            )

            imported = read_pattern_file(exchange_path)
            self.assertEqual(imported.name, "Imported")
            self.assertFalse(user_path.exists())

            result = import_pattern(imported, pattern_path=user_path)

            self.assertEqual(result, "Imported")
            self.assertTrue(is_user_pattern("Imported"))
            self.assertEqual(load_user_patterns(user_path)["Imported"], colors())

    def test_import_persists_for_newly_loaded_collection(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            import_pattern(
                ImportedPattern("Persistent", colors()), pattern_path=user_path
            )

            reloaded_patterns = load_user_patterns(user_path)

            self.assertIn("Persistent", reloaded_patterns)

    def test_builtin_collision_is_distinct_even_with_overwrite(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        imported = ImportedPattern(builtin_name, colors())
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"

            for overwrite in (False, True):
                with self.subTest(overwrite=overwrite):
                    with self.assertRaises(BuiltinPatternImportConflictError):
                        import_pattern(
                            imported,
                            overwrite=overwrite,
                            pattern_path=user_path,
                        )

            self.assertFalse(user_path.exists())

    def test_user_collision_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            import_pattern(
                ImportedPattern("Existing", colors()), pattern_path=user_path
            )

            with self.assertRaises(UserPatternImportConflictError):
                import_pattern(
                    ImportedPattern("Existing", colors("#abcdef")),
                    pattern_path=user_path,
                )

            self.assertEqual(pattern_handler.user_color_patterns["Existing"], colors())

    def test_explicit_overwrite_replaces_existing_user_pattern(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            import_pattern(
                ImportedPattern("Existing", colors()), pattern_path=user_path
            )
            replacement = colors("#abcdef")

            import_pattern(
                ImportedPattern("Existing", replacement),
                overwrite=True,
                pattern_path=user_path,
            )

            self.assertEqual(
                pattern_handler.user_color_patterns["Existing"], replacement
            )
            self.assertEqual(load_user_patterns(user_path)["Existing"], replacement)

    def test_import_under_normalized_replacement_name(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"

            result = import_pattern(
                ImportedPattern("Original", colors()),
                target_name="  Renamed  ",
                pattern_path=user_path,
            )

            self.assertEqual(result, "Renamed")
            self.assertIn("Renamed", pattern_handler.user_color_patterns)
            self.assertNotIn("Original", pattern_handler.user_color_patterns)

    def test_invalid_replacement_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"

            with self.assertRaises(InvalidPatternImportNameError):
                import_pattern(
                    ImportedPattern("Original", colors()),
                    target_name="   ",
                    pattern_path=user_path,
                )

            self.assertFalse(user_path.exists())

    def test_failed_persistence_preserves_memory_and_previous_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            import_pattern(
                ImportedPattern("Existing", colors()), pattern_path=user_path
            )
            previous_file = user_path.read_bytes()
            previous_memory = OrderedDict(pattern_handler.user_color_patterns)

            with patch(
                "src.color_pattern_handler.os.replace",
                side_effect=OSError("disk"),
            ):
                with self.assertRaises(OSError):
                    import_pattern(
                        ImportedPattern("Existing", colors("#abcdef")),
                        overwrite=True,
                        pattern_path=user_path,
                    )

            self.assertEqual(user_path.read_bytes(), previous_file)
            self.assertEqual(pattern_handler.user_color_patterns, previous_memory)


if __name__ == "__main__":
    unittest.main()
