import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_pattern_handler import color_key
from src.pattern_exchange import (
    PATTERN_COLLECTION_EXCHANGE_FORMAT,
    PATTERN_COLLECTION_EXCHANGE_SUFFIX,
    PATTERN_COLLECTION_EXCHANGE_VERSION,
    PATTERN_EXCHANGE_FORMAT,
    PATTERN_EXCHANGE_SUFFIX,
    PATTERN_EXCHANGE_VERSION,
    create_pattern_collection_exchange_document,
)


class PatternCollectionExchangeFormatTests(unittest.TestCase):
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
                "format": "sm1-dow2-texture-painter-pattern-collection",
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
            "sm1-dow2-texture-painter-pattern-collection",
        )
        self.assertEqual(PATTERN_COLLECTION_EXCHANGE_VERSION, 1)
        self.assertEqual(PATTERN_COLLECTION_EXCHANGE_SUFFIX, ".pattern-collection.json")
        self.assertEqual(PATTERN_EXCHANGE_FORMAT, "sm1-dow2-texture-painter-pattern")
        self.assertEqual(PATTERN_EXCHANGE_VERSION, 1)
        self.assertEqual(PATTERN_EXCHANGE_SUFFIX, ".pattern.json")

    def test_collection_name_is_not_applied_to_pattern_names(self):
        colors = {key: "#112233" for key in color_key}

        document = create_pattern_collection_exchange_document(
            "Collection Name", [("Pattern Name", colors)]
        )

        self.assertEqual(document["name"], "Collection Name")
        self.assertEqual(document["patterns"][0]["name"], "Pattern Name")


if __name__ == "__main__":
    unittest.main()
