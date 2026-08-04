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
    CollectionImportResult,
    StalePatternCollectionAnalysisError,
    analyze_pattern_collection_import,
    import_analyzed_pattern_collection,
    validate_imported_pattern_collection,
)


def colors(primary="#112233"):
    return OrderedDict(
        zip(
            pattern_handler.color_key,
            (primary, "#445566", "#778899", "#aabbcc"),
        )
    )


def collection(*entries, name="Collection Metadata Only"):
    return validate_imported_pattern_collection(
        {
            "format": PATTERN_COLLECTION_EXCHANGE_FORMAT,
            "version": PATTERN_COLLECTION_EXCHANGE_VERSION,
            "name": name,
            "patterns": [
                {"name": pattern_name, "colors": pattern_colors}
                for pattern_name, pattern_colors in entries
            ],
        }
    )


class PatternCollectionImportTests(unittest.TestCase):
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

    def seed_user(self, name, pattern_colors, user_path):
        pattern_handler.save_imported_pattern(
            name,
            list(pattern_colors.values()),
            pattern_path=user_path,
        )

    def analyze(self, imported_collection):
        return analyze_pattern_collection_import(
            imported_collection,
            pattern_handler.builtin_color_patterns,
            pattern_handler.user_color_patterns,
        )

    def test_imports_all_new_patterns_with_one_atomic_write(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            imported = collection(
                ("New B", colors("#112233")),
                ("New A", colors("#abcdef")),
            )
            analysis = self.analyze(imported)

            with patch(
                "src.pattern_exchange.replace_user_patterns",
                wraps=pattern_handler.replace_user_patterns,
            ) as persist, patch(
                "src.color_pattern_handler._write_user_patterns",
                wraps=pattern_handler._write_user_patterns,
            ) as atomic_write:
                result = import_analyzed_pattern_collection(
                    analysis, pattern_path=user_path
                )

            self.assertEqual(result, CollectionImportResult(2, 0, 0, 0))
            persist.assert_called_once()
            atomic_write.assert_called_once()
            reloaded = pattern_handler.load_user_patterns(user_path)
            self.assertEqual(list(reloaded), ["New B", "New A"])
            self.assertEqual(reloaded["New B"], colors("#112233"))
            self.assertEqual(reloaded["New A"], colors("#abcdef"))

    def test_user_conflicts_are_skipped_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            original = colors("#112233")
            self.seed_user("Existing", original, user_path)
            analysis = self.analyze(collection(("Existing", colors("#abcdef"))))
            file_before = user_path.read_bytes()

            with patch("src.pattern_exchange.replace_user_patterns") as persist:
                result = import_analyzed_pattern_collection(
                    analysis,
                    overwrite_user_conflicts=False,
                    pattern_path=user_path,
                )

            self.assertEqual(result, CollectionImportResult(0, 0, 1, 0))
            persist.assert_not_called()
            self.assertEqual(user_path.read_bytes(), file_before)
            self.assertEqual(pattern_handler.user_color_patterns["Existing"], original)

    def test_user_conflicts_are_overwritten_only_when_requested(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            replacement = colors("#abcdef")
            self.seed_user("Existing", colors("#112233"), user_path)
            analysis = self.analyze(collection(("Existing", replacement)))

            result = import_analyzed_pattern_collection(
                analysis,
                overwrite_user_conflicts=True,
                pattern_path=user_path,
            )

            self.assertEqual(result, CollectionImportResult(0, 1, 0, 0))
            self.assertEqual(
                pattern_handler.user_color_patterns["Existing"], replacement
            )
            self.assertEqual(
                pattern_handler.load_user_patterns(user_path)["Existing"], replacement
            )

    def test_builtin_conflicts_are_always_skipped(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        builtin_before = pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes()
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            analysis = self.analyze(collection((builtin_name, colors("#abcdef"))))

            for overwrite in (False, True):
                with self.subTest(overwrite=overwrite), patch(
                    "src.pattern_exchange.replace_user_patterns"
                ) as persist:
                    result = import_analyzed_pattern_collection(
                        analysis,
                        overwrite_user_conflicts=overwrite,
                        pattern_path=user_path,
                    )
                    self.assertEqual(result, CollectionImportResult(0, 0, 0, 1))
                    persist.assert_not_called()

            self.assertFalse(user_path.exists())
        self.assertEqual(
            pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes(), builtin_before
        )

    def test_mixed_collection_counts_and_persists_final_state_once(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            self.seed_user("Keep", colors("#010101"), user_path)
            self.seed_user("Replace", colors("#020202"), user_path)
            analysis = self.analyze(
                collection(
                    ("New", colors("#030303")),
                    ("Keep", colors("#040404")),
                    (builtin_name, colors("#050505")),
                    ("Replace", colors("#060606")),
                )
            )

            with patch(
                "src.pattern_exchange.replace_user_patterns",
                wraps=pattern_handler.replace_user_patterns,
            ) as persist:
                result = import_analyzed_pattern_collection(
                    analysis,
                    overwrite_user_conflicts=True,
                    pattern_path=user_path,
                )

            self.assertEqual(result, CollectionImportResult(1, 2, 0, 1))
            persist.assert_called_once()
            reloaded = pattern_handler.load_user_patterns(user_path)
            self.assertEqual(list(reloaded), ["Keep", "Replace", "New"])
            self.assertEqual(reloaded["Keep"], colors("#040404"))
            self.assertEqual(reloaded["Replace"], colors("#060606"))
            self.assertEqual(reloaded["New"], colors("#030303"))
            self.assertNotIn(builtin_name, reloaded)
            self.assertNotIn(
                "Collection Metadata Only",
                json.loads(user_path.read_text())["patterns"],
            )

    def test_write_failure_preserves_file_memory_and_all_or_nothing_state(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            self.seed_user("Existing", colors("#112233"), user_path)
            analysis = self.analyze(
                collection(
                    ("Existing", colors("#abcdef")),
                    ("New", colors("#010101")),
                )
            )
            file_before = user_path.read_bytes()
            users_before = copy_patterns(pattern_handler.user_color_patterns)
            all_before = copy_patterns(pattern_handler.army_color_pattern)

            with patch(
                "src.color_pattern_handler.os.replace",
                side_effect=OSError("disk"),
            ):
                with self.assertRaises(OSError):
                    import_analyzed_pattern_collection(
                        analysis,
                        overwrite_user_conflicts=True,
                        pattern_path=user_path,
                    )

            self.assertEqual(user_path.read_bytes(), file_before)
            self.assertEqual(pattern_handler.user_color_patterns, users_before)
            self.assertEqual(pattern_handler.army_color_pattern, all_before)
            self.assertNotIn("New", pattern_handler.user_color_patterns)

    def test_persistence_reloads_into_fresh_handler_state(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            analysis = self.analyze(collection(("Persistent", colors("#abcdef"))))
            import_analyzed_pattern_collection(analysis, pattern_path=user_path)

            reloaded = pattern_handler.load_user_patterns(user_path)
            pattern_handler.user_color_patterns.clear()
            pattern_handler.army_color_pattern.clear()
            pattern_handler.user_color_patterns.update(reloaded)
            pattern_handler.army_color_pattern.update(
                pattern_handler.get_all_patterns(
                    pattern_handler.builtin_color_patterns, reloaded
                )
            )

            self.assertTrue(pattern_handler.is_user_pattern("Persistent"))
            self.assertEqual(
                pattern_handler.user_color_patterns["Persistent"], colors("#abcdef")
            )

    def test_stale_analysis_cannot_overwrite_a_new_user_conflict(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            analysis = self.analyze(collection(("Initially New", colors("#abcdef"))))
            self.seed_user("Initially New", colors("#112233"), user_path)
            file_before = user_path.read_bytes()

            with self.assertRaises(StalePatternCollectionAnalysisError):
                import_analyzed_pattern_collection(
                    analysis,
                    overwrite_user_conflicts=False,
                    pattern_path=user_path,
                )

            self.assertEqual(user_path.read_bytes(), file_before)
            self.assertEqual(
                pattern_handler.user_color_patterns["Initially New"], colors("#112233")
            )


def copy_patterns(patterns):
    return OrderedDict(
        (name, OrderedDict(pattern)) for name, pattern in patterns.items()
    )


if __name__ == "__main__":
    unittest.main()
