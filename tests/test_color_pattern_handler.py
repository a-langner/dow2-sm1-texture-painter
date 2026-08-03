import json
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import src.color_pattern_handler as pattern_handler
from src.color_pattern_handler import (
    BuiltinPatternDeletionError,
    InvalidPatternError,
    PatternAlreadyExistsError,
    PatternNameConflictError,
    PatternNotFoundError,
    color_key,
    get_all_patterns,
    load_builtin_patterns,
    load_user_patterns,
)


def pattern(primary="#111111"):
    return OrderedDict(
        zip(color_key, [primary, "#222222", "#333333", "#444444"])
    )


class ColorPatternLoadingTests(unittest.TestCase):
    def test_loads_builtin_patterns_from_packaged_resource(self):
        patterns = load_builtin_patterns()

        self.assertIsInstance(patterns, OrderedDict)
        self.assertIn("Blood Ravens", patterns)
        self.assertEqual(list(patterns["Blood Ravens"]), color_key)

    def test_missing_user_file_returns_empty_ordered_collection(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / "missing.json"

            patterns = load_user_patterns(missing_path)

        self.assertEqual(patterns, OrderedDict())

    def test_loads_valid_user_patterns_in_file_order(self):
        expected = OrderedDict(
            [("First", pattern()), ("Second", pattern("#aaaaaa"))]
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_path.write_text(json.dumps(expected), encoding="utf-8")

            patterns = load_user_patterns(pattern_path)

        self.assertEqual(patterns, expected)
        self.assertEqual(list(patterns), ["First", "Second"])

    def test_duplicate_builtin_and_user_names_are_rejected(self):
        builtins = OrderedDict([("Duplicate", pattern())])
        users = OrderedDict([("Duplicate", pattern("#aaaaaa"))])

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            get_all_patterns(builtins, users)

    def test_invalid_top_level_json_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "JSON object"):
                load_user_patterns(pattern_path)


class ColorPatternSavingTests(unittest.TestCase):
    def setUp(self):
        self.original_users = OrderedDict(
            pattern_handler.user_color_patterns
        )
        self.original_all = OrderedDict(pattern_handler.army_color_pattern)

    def tearDown(self):
        pattern_handler.user_color_patterns.clear()
        pattern_handler.user_color_patterns.update(self.original_users)
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(self.original_all)

    def colors(self):
        return list(pattern().values())

    def test_first_save_creates_directory_and_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = (
                Path(temporary_directory)
                / "new-directory"
                / "user_patterns.json"
            )
            with patch.object(
                pattern_handler,
                "get_user_patterns_path",
                return_value=pattern_path,
            ) as mocked_path:
                pattern_handler.save("  New Pattern  ", self.colors())

            mocked_path.assert_called_once_with(create_parent=True)
            self.assertTrue(pattern_path.is_file())
            saved = json.loads(pattern_path.read_text(encoding="utf-8"))
            self.assertEqual(list(saved), ["New Pattern"])
            self.assertIn("New Pattern", pattern_handler.user_color_patterns)

    def test_saved_pattern_can_be_loaded_from_disk(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            pattern_handler.save("Persistent", self.colors(), pattern_path)
            reloaded = load_user_patterns(pattern_path)

        self.assertEqual(reloaded["Persistent"], pattern())

    def test_duplicate_user_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Duplicate", self.colors(), pattern_path)

            with self.assertRaisesRegex(
                PatternAlreadyExistsError, "already exists"
            ):
                pattern_handler.save(" Duplicate ", self.colors(), pattern_path)

    def test_builtin_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            with self.assertRaisesRegex(
                PatternNameConflictError, "built-in"
            ):
                pattern_handler.save(
                    "Blood Ravens", self.colors(), pattern_path
                )

            self.assertFalse(pattern_path.exists())

    def test_invalid_names_color_counts_and_color_values_are_rejected(self):
        invalid_cases = [
            (None, self.colors()),
            ("", self.colors()),
            ("   ", self.colors()),
            ("Too few", self.colors()[:3]),
            ("Too many", self.colors() + ["#555555"]),
            ("Bad color", ["red"] + self.colors()[1:]),
        ]

        for name, colors in invalid_cases:
            with self.subTest(name=name, colors=colors):
                with self.assertRaises(InvalidPatternError):
                    pattern_handler.save(name, colors, Path("unused.json"))

    def test_write_failure_does_not_change_memory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            users_before = OrderedDict(pattern_handler.user_color_patterns)
            all_before = OrderedDict(pattern_handler.army_color_pattern)

            with patch(
                "src.color_pattern_handler.os.replace",
                side_effect=OSError("simulated failure"),
            ):
                with self.assertRaisesRegex(OSError, "simulated failure"):
                    pattern_handler.save(
                        "Not Saved", self.colors(), pattern_path
                    )

            self.assertEqual(pattern_handler.user_color_patterns, users_before)
            self.assertEqual(pattern_handler.army_color_pattern, all_before)
            self.assertFalse(pattern_path.exists())
            self.assertEqual(list(pattern_path.parent.glob("*.tmp")), [])

    def test_saving_does_not_modify_packaged_patterns(self):
        packaged_before = pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes()

        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("External", self.colors(), pattern_path)

        self.assertEqual(
            pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes(),
            packaged_before,
        )


class ColorPatternDeletionTests(unittest.TestCase):
    def setUp(self):
        self.original_users = OrderedDict(
            pattern_handler.user_color_patterns
        )
        self.original_all = OrderedDict(pattern_handler.army_color_pattern)

    def tearDown(self):
        pattern_handler.user_color_patterns.clear()
        pattern_handler.user_color_patterns.update(self.original_users)
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(self.original_all)

    def colors(self):
        return list(pattern().values())

    def test_deletes_user_pattern_and_keeps_other_patterns(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Delete Me", self.colors(), pattern_path)
            pattern_handler.save("Keep Me", self.colors(), pattern_path)

            pattern_handler.delete(" Delete Me ", pattern_path)

            saved = load_user_patterns(pattern_path)
            self.assertEqual(list(saved), ["Keep Me"])
            self.assertNotIn("Delete Me", pattern_handler.user_color_patterns)
            self.assertNotIn("Delete Me", pattern_handler.army_color_pattern)

    def test_builtin_pattern_cannot_be_deleted(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            with self.assertRaisesRegex(
                BuiltinPatternDeletionError, "cannot be deleted"
            ):
                pattern_handler.delete("Blood Ravens", pattern_path)

            self.assertFalse(pattern_path.exists())
            self.assertIn("Blood Ravens", pattern_handler.army_color_pattern)

    def test_unknown_pattern_does_not_change_user_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Known", self.colors(), pattern_path)
            contents_before = pattern_path.read_bytes()

            with self.assertRaisesRegex(PatternNotFoundError, "not found"):
                pattern_handler.delete("Unknown", pattern_path)

            self.assertEqual(pattern_path.read_bytes(), contents_before)
            self.assertIn("Known", pattern_handler.user_color_patterns)

    def test_deleting_last_user_pattern_writes_empty_json_object(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Last", self.colors(), pattern_path)

            pattern_handler.delete("Last", pattern_path)

            self.assertTrue(pattern_path.is_file())
            self.assertEqual(
                json.loads(pattern_path.read_text(encoding="utf-8")), {}
            )
            self.assertEqual(pattern_handler.user_color_patterns, {})

    def test_deletion_persists_when_patterns_are_reloaded(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Removed", self.colors(), pattern_path)
            pattern_handler.save("Remaining", self.colors(), pattern_path)

            pattern_handler.delete("Removed", pattern_path)
            reloaded = load_user_patterns(pattern_path)

            self.assertEqual(list(reloaded), ["Remaining"])

    def test_delete_write_failure_does_not_change_memory_or_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Still Here", self.colors(), pattern_path)
            contents_before = pattern_path.read_bytes()
            users_before = OrderedDict(pattern_handler.user_color_patterns)
            all_before = OrderedDict(pattern_handler.army_color_pattern)

            with patch(
                "src.color_pattern_handler.os.replace",
                side_effect=OSError("simulated failure"),
            ):
                with self.assertRaisesRegex(OSError, "simulated failure"):
                    pattern_handler.delete("Still Here", pattern_path)

            self.assertEqual(pattern_path.read_bytes(), contents_before)
            self.assertEqual(pattern_handler.user_color_patterns, users_before)
            self.assertEqual(pattern_handler.army_color_pattern, all_before)


if __name__ == "__main__":
    unittest.main()
