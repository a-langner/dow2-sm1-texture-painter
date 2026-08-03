import json
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path

from src.color_pattern_handler import (
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


if __name__ == "__main__":
    unittest.main()
