import copy
import unittest
from collections import OrderedDict

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_pattern_handler import color_key
from src.pattern_exchange import (
    PATTERN_COLLECTION_EXCHANGE_FORMAT,
    PATTERN_COLLECTION_EXCHANGE_VERSION,
    InvalidPatternCollectionError,
    analyze_pattern_collection_import,
    validate_imported_pattern_collection,
)


def pattern_colors(primary="#112233"):
    return OrderedDict(zip(color_key, (primary, "#445566", "#778899", "#aabbcc")))


def validated_collection(*names):
    return validate_imported_pattern_collection(
        {
            "format": PATTERN_COLLECTION_EXCHANGE_FORMAT,
            "version": PATTERN_COLLECTION_EXCHANGE_VERSION,
            "name": "Import Set",
            "patterns": [{"name": name, "colors": pattern_colors()} for name in names],
        }
    )


class PatternCollectionAnalysisTests(unittest.TestCase):
    def test_all_new_patterns_are_classified_in_source_order(self):
        collection = validated_collection("Third", "First", "Second")

        analysis = analyze_pattern_collection_import(
            collection, builtin_patterns={}, user_patterns={}
        )

        self.assertEqual(
            [pattern.name for pattern in analysis.new_patterns],
            ["Third", "First", "Second"],
        )
        self.assertEqual(analysis.collection_name, "Import Set")
        self.assertEqual(analysis.total_pattern_count, 3)
        self.assertEqual(analysis.new_pattern_count, 3)
        self.assertEqual(analysis.user_conflict_count, 0)
        self.assertEqual(analysis.builtin_conflict_count, 0)

    def test_builtin_conflicts_are_never_classified_as_user_conflicts(self):
        collection = validated_collection("Built-in")

        analysis = analyze_pattern_collection_import(
            collection,
            builtin_patterns={"Built-in": pattern_colors()},
            user_patterns={"Built-in": pattern_colors("#abcdef")},
        )

        self.assertEqual(
            [pattern.name for pattern in analysis.builtin_conflicts],
            ["Built-in"],
        )
        self.assertEqual(analysis.user_conflicts, ())
        self.assertEqual(analysis.new_patterns, ())

    def test_user_conflicts_are_classified_separately(self):
        collection = validated_collection("Existing User")

        analysis = analyze_pattern_collection_import(
            collection,
            builtin_patterns={},
            user_patterns={"Existing User": pattern_colors()},
        )

        self.assertEqual(
            [pattern.name for pattern in analysis.user_conflicts],
            ["Existing User"],
        )
        self.assertEqual(analysis.user_conflict_count, 1)

    def test_mixed_groups_each_preserve_collection_order(self):
        collection = validated_collection(
            "New B",
            "User B",
            "Built-in B",
            "New A",
            "Built-in A",
            "User A",
        )

        analysis = analyze_pattern_collection_import(
            collection,
            builtin_patterns={
                "Built-in A": pattern_colors(),
                "Built-in B": pattern_colors(),
            },
            user_patterns={
                "User A": pattern_colors(),
                "User B": pattern_colors(),
            },
        )

        self.assertEqual(
            [pattern.name for pattern in analysis.new_patterns],
            ["New B", "New A"],
        )
        self.assertEqual(
            [pattern.name for pattern in analysis.user_conflicts],
            ["User B", "User A"],
        )
        self.assertEqual(
            [pattern.name for pattern in analysis.builtin_conflicts],
            ["Built-in B", "Built-in A"],
        )
        self.assertEqual(analysis.total_pattern_count, 6)

    def test_analysis_does_not_mutate_collection_or_existing_patterns(self):
        collection = validated_collection("New", "Existing")
        builtins = OrderedDict([("Built-in", pattern_colors())])
        users = OrderedDict([("Existing", pattern_colors("#abcdef"))])
        collection_before = copy.deepcopy(collection)
        builtins_before = copy.deepcopy(builtins)
        users_before = copy.deepcopy(users)

        analyze_pattern_collection_import(collection, builtins, users)

        self.assertEqual(collection, collection_before)
        self.assertEqual(builtins, builtins_before)
        self.assertEqual(users, users_before)

    def test_raw_collection_data_is_rejected(self):
        with self.assertRaisesRegex(InvalidPatternCollectionError, "validated"):
            analyze_pattern_collection_import({"name": "Raw", "patterns": []}, {}, {})


if __name__ == "__main__":
    unittest.main()
