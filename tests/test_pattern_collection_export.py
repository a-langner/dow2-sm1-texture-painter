import json
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
import src.color_pattern_handler as pattern_handler
from src.pattern_exchange import (
    PATTERN_COLLECTION_EXCHANGE_FORMAT,
    PATTERN_COLLECTION_EXCHANGE_VERSION,
    EmptyUserPatternCollectionError,
    InvalidPatternCollectionNameError,
    PatternExportError,
    export_user_pattern_collection,
)


def colors(primary):
    return OrderedDict(
        zip(
            pattern_handler.color_key,
            (primary, "#445566", "#778899", "#aabbcc"),
        )
    )


class PatternCollectionExportTests(unittest.TestCase):
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

    def add_user_pattern(self, name, pattern_colors, user_path):
        pattern_handler.save_imported_pattern(
            name,
            list(pattern_colors.values()),
            pattern_path=user_path,
        )

    def test_exports_only_user_patterns_in_persistent_order(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            user_path = root / "user_patterns.json"
            destination = root / "collection.json"
            expected = [
                ("Zulu Veterans", colors("#112233")),
                ("Élite Löwen_日本", colors("#abcdef")),
            ]
            for name, pattern_colors in expected:
                self.add_user_pattern(name, pattern_colors, user_path)

            export_user_pattern_collection("  My Space Marine Patterns  ", destination)
            raw_json = destination.read_text(encoding="utf-8")
            document = json.loads(raw_json)

        self.assertEqual(document["format"], PATTERN_COLLECTION_EXCHANGE_FORMAT)
        self.assertEqual(document["version"], PATTERN_COLLECTION_EXCHANGE_VERSION)
        self.assertEqual(document["name"], "My Space Marine Patterns")
        self.assertEqual(
            [entry["name"] for entry in document["patterns"]],
            [name for name, _ in expected],
        )
        self.assertTrue(
            set(entry["name"] for entry in document["patterns"]).isdisjoint(
                pattern_handler.builtin_color_patterns
            )
        )
        self.assertNotIn("★", raw_json)
        self.assertIn("Élite Löwen_日本", raw_json)
        for entry, (_, expected_colors) in zip(document["patterns"], expected):
            self.assertEqual(list(entry["colors"]), pattern_handler.color_key)
            self.assertEqual(entry["colors"], expected_colors)

    def test_rejects_export_without_user_patterns(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "collection.json"

            with self.assertRaises(EmptyUserPatternCollectionError):
                export_user_pattern_collection("Collection", destination)

            self.assertFalse(destination.exists())

    def test_rejects_invalid_collection_names(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            destination = Path(temporary_directory) / "collection.json"
            self.add_user_pattern("User", colors("#112233"), user_path)

            for name in (None, "", "   ", 123):
                with self.subTest(name=name):
                    with self.assertRaises(InvalidPatternCollectionNameError):
                        export_user_pattern_collection(name, destination)

            self.assertFalse(destination.exists())

    def test_invalid_destination_is_rejected_without_creating_it(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            user_path = root / "user_patterns.json"
            destination = root / "missing" / "collection.any-suffix"
            self.add_user_pattern("User", colors("#112233"), user_path)

            with self.assertRaises(PatternExportError):
                export_user_pattern_collection("Collection", destination)

            self.assertFalse(destination.parent.exists())

    def test_atomic_failure_preserves_destination_and_all_sources(self):
        builtin_before = pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            user_path = root / "user_patterns.json"
            settings_path = root / "settings.json"
            destination = root / "existing.collection"
            self.add_user_pattern("User", colors("#112233"), user_path)
            settings_path.write_text('{"settings": true}\n', encoding="utf-8")
            destination.write_text('{"previous": true}\n', encoding="utf-8")
            user_before = user_path.read_bytes()
            settings_before = settings_path.read_bytes()
            destination_before = destination.read_bytes()
            memory_before = OrderedDict(pattern_handler.user_color_patterns)

            with patch(
                "src.pattern_exchange.get_user_patterns_path",
                return_value=user_path,
            ), patch(
                "src.pattern_exchange.get_settings_path",
                return_value=settings_path,
            ), patch(
                "src.pattern_exchange.os.replace", side_effect=OSError("disk")
            ):
                with self.assertRaises(PatternExportError):
                    export_user_pattern_collection("Collection", destination)

            self.assertEqual(destination.read_bytes(), destination_before)
            self.assertEqual(user_path.read_bytes(), user_before)
            self.assertEqual(settings_path.read_bytes(), settings_before)
            self.assertEqual(pattern_handler.user_color_patterns, memory_before)
            self.assertEqual(
                list(destination.parent.glob(f".{destination.name}.*.tmp")), []
            )

        self.assertEqual(
            pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes(), builtin_before
        )

    def test_user_patterns_and_settings_cannot_be_export_destinations(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            user_path = root / "user_patterns.json"
            settings_path = root / "settings.json"
            self.add_user_pattern("User", colors("#112233"), user_path)
            settings_path.write_text('{"settings": true}\n', encoding="utf-8")
            user_before = user_path.read_bytes()
            settings_before = settings_path.read_bytes()

            with patch(
                "src.pattern_exchange.get_user_patterns_path",
                return_value=user_path,
            ), patch(
                "src.pattern_exchange.get_settings_path",
                return_value=settings_path,
            ):
                for destination in (user_path, settings_path):
                    with self.subTest(destination=destination):
                        with self.assertRaises(PatternExportError):
                            export_user_pattern_collection("Collection", destination)

            self.assertEqual(user_path.read_bytes(), user_before)
            self.assertEqual(settings_path.read_bytes(), settings_before)


if __name__ == "__main__":
    unittest.main()
