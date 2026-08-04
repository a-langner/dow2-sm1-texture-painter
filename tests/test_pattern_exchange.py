import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_pattern_handler import color_key
from src.pattern_exchange import (
    InvalidImportedPatternColorsError,
    InvalidImportedPatternNameError,
    InvalidPatternFileError,
    InvalidPatternJsonError,
    PATTERN_EXCHANGE_FORMAT,
    PATTERN_EXCHANGE_SUFFIX,
    PATTERN_EXCHANGE_VERSION,
    UnsupportedPatternVersionError,
    create_pattern_exchange_document,
    has_pattern_exchange_format,
    has_supported_pattern_exchange_version,
    parse_imported_pattern_json,
    validate_imported_pattern,
)


class PatternExchangeFormatTests(unittest.TestCase):
    def setUp(self):
        self.colors = {
            "primary_colour_name": "#112233",
            "secondary_colour_name": "#445566",
            "tint_colour_name": "#778899",
            "extra_colour_name": "#aabbcc",
        }

    def test_generated_document_has_expected_structure(self):
        document = create_pattern_exchange_document("Example Pattern", self.colors)

        self.assertEqual(
            document,
            {
                "format": "sm1-dow2-texture-painter-pattern",
                "version": 1,
                "name": "Example Pattern",
                "colors": self.colors,
            },
        )
        self.assertEqual(list(document["colors"]), color_key)

    def test_constants_define_version_one_json_suffix(self):
        self.assertEqual(PATTERN_EXCHANGE_FORMAT, "sm1-dow2-texture-painter-pattern")
        self.assertEqual(PATTERN_EXCHANGE_VERSION, 1)
        self.assertEqual(PATTERN_EXCHANGE_SUFFIX, ".pattern.json")

    def test_format_recognition_ignores_additional_fields(self):
        document = {
            "format": PATTERN_EXCHANGE_FORMAT,
            "version": PATTERN_EXCHANGE_VERSION,
            "future_field": "ignored",
        }

        self.assertTrue(has_pattern_exchange_format(document))
        self.assertTrue(has_supported_pattern_exchange_version(document))

    def test_format_and_version_recognition_reject_mismatches(self):
        self.assertFalse(has_pattern_exchange_format({"format": "other"}))
        self.assertFalse(has_supported_pattern_exchange_version({"version": 2}))
        self.assertFalse(has_supported_pattern_exchange_version({"version": True}))


class PatternExchangeValidationTests(unittest.TestCase):
    def setUp(self):
        self.valid_document = {
            "format": PATTERN_EXCHANGE_FORMAT,
            "version": PATTERN_EXCHANGE_VERSION,
            "name": "Example Pattern",
            "colors": {
                "primary_colour_name": "#112233",
                "secondary_colour_name": "#445566",
                "tint_colour_name": "#778899",
                "extra_colour_name": "#aabbcc",
            },
        }

    def test_valid_version_one_data_is_normalized(self):
        result = validate_imported_pattern(self.valid_document)

        self.assertEqual(result, self.valid_document)

    def test_invalid_top_level_type_is_rejected(self):
        for value in (None, [], "pattern"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidPatternFileError):
                    validate_imported_pattern(value)

    def test_missing_or_wrong_format_is_rejected(self):
        missing = dict(self.valid_document)
        missing.pop("format")
        wrong = {**self.valid_document, "format": "other"}

        for value in (missing, wrong):
            with self.subTest(value=value):
                with self.assertRaises(InvalidPatternFileError):
                    validate_imported_pattern(value)

    def test_unsupported_version_has_distinct_error(self):
        document = {**self.valid_document, "version": 2}

        with self.assertRaises(UnsupportedPatternVersionError):
            validate_imported_pattern(document)

    def test_missing_noninteger_and_boolean_versions_are_invalid(self):
        missing = dict(self.valid_document)
        missing.pop("version")
        for document in (
            missing,
            {**self.valid_document, "version": "1"},
            {**self.valid_document, "version": True},
        ):
            with self.subTest(document=document):
                with self.assertRaises(InvalidPatternFileError):
                    validate_imported_pattern(document)

    def test_missing_empty_or_nonstring_name_is_rejected(self):
        missing = dict(self.valid_document)
        missing.pop("name")
        for document in (
            missing,
            {**self.valid_document, "name": "   "},
            {**self.valid_document, "name": 123},
        ):
            with self.subTest(document=document):
                with self.assertRaises(InvalidImportedPatternNameError):
                    validate_imported_pattern(document)

    def test_missing_or_nonobject_colors_are_rejected(self):
        missing = dict(self.valid_document)
        missing.pop("colors")
        for document in (missing, {**self.valid_document, "colors": []}):
            with self.subTest(document=document):
                with self.assertRaises(InvalidImportedPatternColorsError):
                    validate_imported_pattern(document)

    def test_each_missing_color_key_is_rejected(self):
        for key in color_key:
            colors = dict(self.valid_document["colors"])
            colors.pop(key)
            with self.subTest(key=key):
                with self.assertRaises(InvalidImportedPatternColorsError):
                    validate_imported_pattern({**self.valid_document, "colors": colors})

    def test_none_and_invalid_color_values_are_rejected(self):
        for value in (None, "112233", "#12345g", 112233):
            colors = dict(self.valid_document["colors"])
            colors["primary_colour_name"] = value
            with self.subTest(value=value):
                with self.assertRaises(InvalidImportedPatternColorsError):
                    validate_imported_pattern({**self.valid_document, "colors": colors})

    def test_unknown_fields_are_ignored(self):
        colors = {**self.valid_document["colors"], "future_color": "ignored"}
        document = {
            **self.valid_document,
            "future_field": "ignored",
            "colors": colors,
        }

        self.assertEqual(validate_imported_pattern(document), self.valid_document)

    def test_name_surrounding_whitespace_is_removed(self):
        document = {**self.valid_document, "name": "  Example Pattern  "}

        result = validate_imported_pattern(document)

        self.assertEqual(result["name"], "Example Pattern")

    def test_invalid_json_has_distinct_error(self):
        with self.assertRaises(InvalidPatternJsonError):
            parse_imported_pattern_json("{broken")


if __name__ == "__main__":
    unittest.main()
