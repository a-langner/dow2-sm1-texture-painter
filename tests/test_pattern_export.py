import json
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_pattern_handler import (
    ARMY_PATTERN_RESOURCE,
    PatternNotFoundError,
    color_key,
    get_all_patterns,
)
from src.pattern_exchange import (
    PATTERN_EXCHANGE_FORMAT,
    PATTERN_EXCHANGE_VERSION,
    PatternExportError,
    PatternExportPermissionDeniedError,
    export_pattern,
)


class PatternExportTests(unittest.TestCase):
    def test_exports_builtin_pattern_with_internal_name_and_all_colors(self):
        pattern_name = next(iter(get_all_patterns()))
        expected_colors = get_all_patterns()[pattern_name]

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "builtin.pattern.json"
            export_pattern(pattern_name, destination)
            document = json.loads(destination.read_text(encoding="utf-8"))

        self.assertEqual(document["format"], PATTERN_EXCHANGE_FORMAT)
        self.assertEqual(document["version"], PATTERN_EXCHANGE_VERSION)
        self.assertEqual(document["name"], pattern_name)
        self.assertNotIn("★", document["name"])
        self.assertEqual(list(document["colors"]), color_key)
        self.assertEqual(document["colors"], expected_colors)

    def test_exports_user_pattern_with_unicode_name(self):
        pattern_name = "Élite Löwen"
        colors = OrderedDict(
            zip(color_key, ("#112233", "#445566", "#778899", "#aabbcc"))
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "custom.json"
            with patch(
                "src.pattern_exchange.get_all_patterns",
                return_value=OrderedDict([(pattern_name, colors)]),
            ):
                export_pattern(pattern_name, destination)

            raw_json = destination.read_text(encoding="utf-8")
            document = json.loads(raw_json)

        self.assertIn(pattern_name, raw_json)
        self.assertEqual(document["name"], pattern_name)
        self.assertEqual(document["colors"], colors)

    def test_unknown_pattern_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "unknown.pattern.json"

            with self.assertRaises(PatternNotFoundError):
                export_pattern("Does not exist", destination)

            self.assertFalse(destination.exists())

    def test_invalid_destination_is_rejected_without_creating_parent(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            destination = root / "missing" / "pattern.json"
            pattern_name = next(iter(get_all_patterns()))

            with self.assertRaises(PatternExportError):
                export_pattern(pattern_name, destination)

            self.assertFalse(destination.parent.exists())

    def test_atomic_replace_failure_preserves_previous_destination(self):
        pattern_name = next(iter(get_all_patterns()))
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "existing.pattern.json"
            original = '{"previous": true}\n'
            destination.write_text(original, encoding="utf-8")

            with patch("src.pattern_exchange.os.replace", side_effect=OSError("disk")):
                with self.assertRaises(PatternExportError):
                    export_pattern(pattern_name, destination)

            self.assertEqual(destination.read_text(encoding="utf-8"), original)
            self.assertEqual(
                list(destination.parent.glob(f".{destination.name}.*.tmp")), []
            )

    def test_permission_failure_preserves_destination_and_cleans_temporary_file(self):
        pattern_name = next(iter(get_all_patterns()))
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "existing.pattern.json"
            original = b'{"previous": true}\n'
            destination.write_bytes(original)

            with patch(
                "src.pattern_exchange.os.replace",
                side_effect=PermissionError("denied"),
            ):
                with self.assertRaises(PatternExportPermissionDeniedError):
                    export_pattern(pattern_name, destination)

            self.assertEqual(destination.read_bytes(), original)
            self.assertEqual(
                list(destination.parent.glob(f".{destination.name}.*.tmp")), []
            )

    def test_export_does_not_modify_source_persistence(self):
        pattern_name = next(iter(get_all_patterns()))
        builtin_before = ARMY_PATTERN_RESOURCE.read_bytes()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            user_patterns = root / "user_patterns.json"
            user_contents = '{"sentinel": true}\n'
            user_patterns.write_text(user_contents, encoding="utf-8")

            with patch(
                "src.pattern_exchange.get_user_patterns_path",
                return_value=user_patterns,
            ):
                with self.assertRaises(PatternExportError):
                    export_pattern(pattern_name, user_patterns)

            self.assertEqual(user_patterns.read_text(encoding="utf-8"), user_contents)
        self.assertEqual(ARMY_PATTERN_RESOURCE.read_bytes(), builtin_before)


if __name__ == "__main__":
    unittest.main()
