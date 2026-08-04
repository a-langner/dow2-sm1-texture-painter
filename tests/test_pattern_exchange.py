import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_pattern_handler import color_key
from src.pattern_exchange import (
    PATTERN_EXCHANGE_FORMAT,
    PATTERN_EXCHANGE_SUFFIX,
    PATTERN_EXCHANGE_VERSION,
    create_pattern_exchange_document,
    has_pattern_exchange_format,
    has_supported_pattern_exchange_version,
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


if __name__ == "__main__":
    unittest.main()
