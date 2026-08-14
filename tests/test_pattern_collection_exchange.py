import json
import tempfile
import unittest
from pathlib import Path

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_pattern_handler import color_key
from src.pattern_exchange import (
    DuplicatePatternNameInCollectionError,
    ImportedPattern,
    ImportedPatternCollection,
    InvalidPatternCollectionError,
    InvalidPatternJsonError,
    PATTERN_COLLECTION_EXCHANGE_FORMAT,
    PATTERN_COLLECTION_EXCHANGE_SUFFIX,
    PATTERN_COLLECTION_EXCHANGE_VERSION,
    PATTERN_EXCHANGE_FORMAT,
    PATTERN_EXCHANGE_SUFFIX,
    PATTERN_EXCHANGE_VERSION,
    create_pattern_exchange_document,
    UnsupportedPatternCollectionVersionError,
    create_pattern_collection_exchange_document,
    read_pattern_collection_file,
    validate_imported_pattern_collection,
)


class PatternCollectionExchangeFormatTests(unittest.TestCase):
    def test_reads_and_validates_collection_file_as_utf8_json(self):
        document = create_pattern_collection_exchange_document(
            "Löwen",
            [
                (
                    "Élite",
                    {
                        "primary_colour_name": "#112233",
                        "secondary_colour_name": "#445566",
                        "tint_colour_name": "#778899",
                        "extra_colour_name": "#aabbcc",
                    },
                )
            ],
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "collection.json"
            source.write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )

            collection = read_pattern_collection_file(source)

        self.assertEqual(collection.name, "Löwen")
        self.assertEqual(collection.patterns[0].name, "Élite")

    def test_malformed_collection_json_is_distinct_from_invalid_content(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "collection.json"
            source.write_text("{not json", encoding="utf-8")

            with self.assertRaises(InvalidPatternJsonError):
                read_pattern_collection_file(source)

    def test_single_pattern_exchange_file_is_rejected_as_wrong_collection_format(self):
        single_pattern = create_pattern_exchange_document(
            "Single",
            {
                "primary_colour_name": "#112233",
                "secondary_colour_name": "#445566",
                "tint_colour_name": "#778899",
                "extra_colour_name": "#aabbcc",
            },
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "single.pattern.json"
            source.write_text(json.dumps(single_pattern), encoding="utf-8")

            with self.assertRaises(InvalidPatternCollectionError):
                read_pattern_collection_file(source)

    def test_constructs_version_one_collection_with_pattern_array(self):
        first_colors = {
            "primary_colour_name": "#7f1919",
            "secondary_colour_name": "#d1b989",
            "tint_colour_name": "#242424",
            "extra_colour_name": "#ffffff",
        }
        second_colors = {
            "primary_colour_name": "#2454a6",
            "secondary_colour_name": "#c49b31",
            "tint_colour_name": "#1c1c1c",
            "extra_colour_name": "#b71c1c",
        }

        document = create_pattern_collection_exchange_document(
            "My Space Marine Patterns",
            [
                ("Blood Ravens Veteran", first_colors),
                ("Ultramarines Sergeant", second_colors),
            ],
        )

        self.assertEqual(
            document,
            {
                "format": "dow2-sm1-texture-painter-pattern-collection",
                "version": 1,
                "name": "My Space Marine Patterns",
                "patterns": [
                    {"name": "Blood Ravens Veteran", "colors": first_colors},
                    {"name": "Ultramarines Sergeant", "colors": second_colors},
                ],
            },
        )
        self.assertIsInstance(document["patterns"], list)
        self.assertEqual(
            [list(entry["colors"]) for entry in document["patterns"]],
            [color_key, color_key],
        )

    def test_collection_constants_do_not_change_single_pattern_constants(self):
        self.assertEqual(
            PATTERN_COLLECTION_EXCHANGE_FORMAT,
            "dow2-sm1-texture-painter-pattern-collection",
        )
        self.assertEqual(PATTERN_COLLECTION_EXCHANGE_VERSION, 1)
        self.assertEqual(PATTERN_COLLECTION_EXCHANGE_SUFFIX, ".pattern-collection.json")
        self.assertEqual(PATTERN_EXCHANGE_FORMAT, "dow2-sm1-texture-painter-pattern")
        self.assertEqual(PATTERN_EXCHANGE_VERSION, 1)
        self.assertEqual(PATTERN_EXCHANGE_SUFFIX, ".pattern.json")

    def test_collection_name_is_not_applied_to_pattern_names(self):
        colors = {key: "#112233" for key in color_key}

        document = create_pattern_collection_exchange_document(
            "Collection Name", [("Pattern Name", colors)]
        )

        self.assertEqual(document["name"], "Collection Name")
        self.assertEqual(document["patterns"][0]["name"], "Pattern Name")


class PatternCollectionValidationTests(unittest.TestCase):
    def setUp(self):
        self.colors = {
            "primary_colour_name": "#112233",
            "secondary_colour_name": "#445566",
            "tint_colour_name": "#778899",
            "extra_colour_name": "#aabbcc",
        }
        self.valid_document = {
            "format": PATTERN_COLLECTION_EXCHANGE_FORMAT,
            "version": PATTERN_COLLECTION_EXCHANGE_VERSION,
            "name": "Example Collection",
            "patterns": [{"name": "Example Pattern", "colors": self.colors}],
        }

    def test_valid_collection_is_normalized(self):
        document = {
            **self.valid_document,
            "name": "  Example Collection  ",
            "patterns": [{"name": "  Example Pattern  ", "colors": self.colors}],
        }

        result = validate_imported_pattern_collection(document)

        self.assertEqual(
            result,
            ImportedPatternCollection(
                "Example Collection",
                (ImportedPattern("Example Pattern", self.colors),),
            ),
        )

    def test_invalid_top_level_type_is_rejected(self):
        for value in (None, [], "collection"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidPatternCollectionError):
                    validate_imported_pattern_collection(value)

    def test_missing_or_wrong_format_is_rejected(self):
        missing = dict(self.valid_document)
        missing.pop("format")
        wrong = {**self.valid_document, "format": "other"}
        for document in (missing, wrong):
            with self.subTest(document=document):
                with self.assertRaises(InvalidPatternCollectionError):
                    validate_imported_pattern_collection(document)

    def test_missing_noninteger_and_unsupported_versions_are_distinct(self):
        missing = dict(self.valid_document)
        missing.pop("version")
        for document in (
            missing,
            {**self.valid_document, "version": "1"},
            {**self.valid_document, "version": True},
        ):
            with self.subTest(document=document):
                with self.assertRaises(InvalidPatternCollectionError):
                    validate_imported_pattern_collection(document)

        with self.assertRaises(UnsupportedPatternCollectionVersionError):
            validate_imported_pattern_collection({**self.valid_document, "version": 2})

    def test_missing_empty_and_nonstring_collection_names_are_rejected(self):
        missing = dict(self.valid_document)
        missing.pop("name")
        for document in (
            missing,
            {**self.valid_document, "name": "   "},
            {**self.valid_document, "name": 123},
        ):
            with self.subTest(document=document):
                with self.assertRaises(InvalidPatternCollectionError):
                    validate_imported_pattern_collection(document)

    def test_patterns_must_be_a_nonempty_array(self):
        missing = dict(self.valid_document)
        missing.pop("patterns")
        for document in (
            missing,
            {**self.valid_document, "patterns": {}},
            {**self.valid_document, "patterns": []},
        ):
            with self.subTest(document=document):
                with self.assertRaises(InvalidPatternCollectionError):
                    validate_imported_pattern_collection(document)

    def test_invalid_entry_type_reports_its_index(self):
        document = {**self.valid_document, "patterns": [None]}

        with self.assertRaisesRegex(InvalidPatternCollectionError, "Pattern entry 0"):
            validate_imported_pattern_collection(document)

    def test_missing_pattern_fields_report_index_and_available_name(self):
        for entry, expected_text in (
            ({"colors": self.colors}, "Pattern entry 0"),
            ({"name": "Named"}, "Pattern entry 0 \\('Named'\\)"),
        ):
            with self.subTest(entry=entry):
                document = {**self.valid_document, "patterns": [entry]}
                with self.assertRaisesRegex(
                    InvalidPatternCollectionError, expected_text
                ):
                    validate_imported_pattern_collection(document)

    def test_invalid_colors_reuse_single_pattern_validation(self):
        colors = {**self.colors, "primary_colour_name": "not-a-color"}
        document = {
            **self.valid_document,
            "patterns": [{"name": "Broken", "colors": colors}],
        }

        with self.assertRaisesRegex(
            InvalidPatternCollectionError,
            "Pattern entry 0 \\('Broken'\\).*#RRGGBB",
        ):
            validate_imported_pattern_collection(document)

    def test_missing_required_color_rejects_the_entire_collection(self):
        incomplete_colors = dict(self.colors)
        incomplete_colors.pop("extra_colour_name")
        document = {
            **self.valid_document,
            "patterns": [
                {"name": "Valid", "colors": self.colors},
                {"name": "Incomplete", "colors": incomplete_colors},
            ],
        }

        with self.assertRaisesRegex(
            InvalidPatternCollectionError,
            "Pattern entry 1 \\('Incomplete'\\).*extra_colour_name",
        ):
            validate_imported_pattern_collection(document)

    def test_invalid_middle_entry_returns_no_partial_collection(self):
        invalid_colors = dict(self.colors)
        invalid_colors["secondary_colour_name"] = "invalid"
        document = {
            **self.valid_document,
            "patterns": [
                {"name": "Valid Before", "colors": self.colors},
                {"name": "Invalid Middle", "colors": invalid_colors},
                {"name": "Valid After", "colors": self.colors},
            ],
        }

        with self.assertRaisesRegex(
            InvalidPatternCollectionError, "Pattern entry 1.*Invalid Middle"
        ):
            validate_imported_pattern_collection(document)

    def test_duplicate_normalized_names_are_rejected_case_sensitively(self):
        duplicate = {
            **self.valid_document,
            "patterns": [
                {"name": "Duplicate", "colors": self.colors},
                {"name": "  Duplicate  ", "colors": self.colors},
            ],
        }

        with self.assertRaisesRegex(DuplicatePatternNameInCollectionError, "Duplicate"):
            validate_imported_pattern_collection(duplicate)

        case_distinct = {
            **self.valid_document,
            "patterns": [
                {"name": "Pattern", "colors": self.colors},
                {"name": "pattern", "colors": self.colors},
            ],
        }
        result = validate_imported_pattern_collection(case_distinct)
        self.assertEqual(
            [entry.name for entry in result.patterns],
            ["Pattern", "pattern"],
        )

    def test_unknown_fields_are_tolerated_and_unicode_names_are_preserved(self):
        document = {
            **self.valid_document,
            "name": "  Sammlung_日本  ",
            "future": "ignored",
            "patterns": [
                {
                    "name": "  Élite Löwen  ",
                    "colors": {**self.colors, "future_color": "ignored"},
                    "future_entry": "ignored",
                }
            ],
        }

        result = validate_imported_pattern_collection(document)

        self.assertEqual(result.name, "Sammlung_日本")
        self.assertEqual(result.patterns[0].name, "Élite Löwen")
        self.assertEqual(result.patterns[0].colors, self.colors)


if __name__ == "__main__":
    unittest.main()
