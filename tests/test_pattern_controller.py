import inspect
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import Mock

import test_support  # noqa: F401 - installs the user-data path redirect
import src.color_pattern_handler as pattern_handler
from src.color_pattern_handler import (
    BuiltinPatternModificationError,
    PatternAlreadyExistsError,
    PatternProcessingState,
)
from src.color_processing_settings import ColorProcessingSettings
from src.constant import ColorOps
from src.pattern_controller import PatternController, PatternOperationResult
from src.pattern_exchange import (
    ImportedPattern,
    ImportedPatternCollection,
    import_analyzed_pattern_collection,
    import_pattern,
)
from src.processing_mode import ProcessingMode

COLORS = ("#112233", "#445566", "#778899", "#aabbcc")
NEW_COLORS = ("#010203", "#141516", "#272829", "#3a3b3c")


def color_document(values=COLORS):
    return OrderedDict(zip(pattern_handler.color_key, values))


class PathStore:
    def __init__(self, path):
        self.path = path

    def save(self, name, colors, *, processing=None):
        return pattern_handler.save(
            name,
            colors,
            pattern_path=self.path,
            processing=processing,
        )

    def update_user_pattern(self, name, colors, *, processing=None):
        return pattern_handler.update_user_pattern(
            name,
            colors,
            pattern_path=self.path,
            processing=processing,
        )

    def rename_user_pattern(self, old_name, new_name):
        return pattern_handler.rename_user_pattern(
            old_name, new_name, pattern_path=self.path
        )

    def delete(self, name):
        return pattern_handler.delete(name, pattern_path=self.path)


class PatternControllerTests(unittest.TestCase):
    def setUp(self):
        self.original_users = OrderedDict(pattern_handler.user_color_patterns)
        self.original_all = OrderedDict(pattern_handler.army_color_pattern)
        pattern_handler.user_color_patterns.clear()
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(
            pattern_handler.builtin_color_patterns
        )
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.user_path = self.root / "user_patterns.json"
        self.store = PathStore(self.user_path)
        self.controller = PatternController(
            store=self.store,
            get_processing=pattern_handler.get_pattern_processing_state,
            persist_single_import=lambda pattern, **options: import_pattern(
                pattern, pattern_path=self.user_path, **options
            ),
            persist_collection=lambda analysis, **options: (
                import_analyzed_pattern_collection(
                    analysis, pattern_path=self.user_path, **options
                )
            ),
        )

    def tearDown(self):
        self.temporary_directory.cleanup()
        pattern_handler.user_color_patterns.clear()
        pattern_handler.user_color_patterns.update(self.original_users)
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(self.original_all)

    def save(self, name="User", values=COLORS):
        return self.controller.save_new_pattern(name, values)

    def test_save_duplicate_and_structured_results(self):
        saved = self.save("  User  ")
        duplicate = self.controller.duplicate_pattern("User", "User Copy")

        self.assertIsInstance(saved, PatternOperationResult)
        self.assertEqual(saved.selected_name, "User")
        self.assertTrue(saved.list_changed and saved.persisted and saved.changed)
        self.assertEqual(duplicate.colors_to_apply, COLORS)
        self.assertIn("User Copy", pattern_handler.user_color_patterns)

    def test_update_reports_unchanged_then_persists_changed_colors(self):
        self.save()
        unchanged = self.controller.update_pattern("User", COLORS)
        changed = self.controller.update_pattern("User", NEW_COLORS)

        self.assertFalse(unchanged.changed)
        self.assertFalse(unchanged.persisted)
        self.assertTrue(changed.changed and changed.persisted)
        self.assertEqual(
            tuple(pattern_handler.user_color_patterns["User"].values()),
            NEW_COLORS,
        )

    def test_per_color_save_update_restart_and_reload_preserve_all_slots(self):
        original = PatternProcessingState(
            ProcessingMode.PER_COLOR,
            ColorProcessingSettings(ColorOps.SCREEN, 80, 120),
            (
                ColorProcessingSettings(ColorOps.OVERLAY, 10, 20),
                ColorProcessingSettings(ColorOps.MULTIPLY, 30, 40),
                ColorProcessingSettings(ColorOps.COLOR, 50, 60),
                ColorProcessingSettings(ColorOps.HARD_LIGHT, 70, 80),
            ),
        )
        updated = PatternProcessingState(
            ProcessingMode.PER_COLOR,
            original.global_processing,
            (
                original.per_color_processing[0],
                ColorProcessingSettings(ColorOps.LINEAR_DODGE, 90, 100),
                original.per_color_processing[2],
                original.per_color_processing[3],
            ),
        )

        self.controller.save_new_pattern("Per Color", COLORS, original)
        self.controller.update_pattern("Per Color", NEW_COLORS, updated)

        reloaded = pattern_handler.load_user_patterns(self.user_path)
        pattern_handler.user_color_patterns.clear()
        pattern_handler.user_color_patterns.update(reloaded)
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(
            pattern_handler.builtin_color_patterns
        )
        pattern_handler.army_color_pattern.update(reloaded)

        self.assertEqual(
            pattern_handler.get_pattern_processing_state("Per Color"),
            updated,
        )
        self.assertEqual(
            pattern_handler.get_pattern_colors("Per Color"),
            list(NEW_COLORS),
        )

    def test_rename_preserves_full_processing_and_delete_still_removes_it(self):
        state = PatternProcessingState(
            ProcessingMode.PER_COLOR,
            ColorProcessingSettings(ColorOps.SCREEN, 80, 120),
            (ColorProcessingSettings(),) * 4,
        )
        self.controller.save_new_pattern("Original", COLORS, state)

        self.controller.rename_pattern("Original", "Renamed")

        self.assertEqual(
            pattern_handler.get_pattern_processing_state("Renamed"), state
        )
        self.controller.delete_pattern("Renamed")
        self.assertNotIn("Renamed", pattern_handler.user_color_patterns)

    def test_update_builtin_is_rejected(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        with self.assertRaises(BuiltinPatternModificationError):
            self.controller.update_pattern(builtin_name, NEW_COLORS)

    def test_rename_same_name_collision_and_success(self):
        self.save("First")
        self.save("Second")

        same = self.controller.rename_pattern("First", " First ")
        self.assertFalse(same.changed)
        with self.assertRaises(PatternAlreadyExistsError):
            self.controller.rename_pattern("First", "Second")
        renamed = self.controller.rename_pattern("First", "Renamed")
        self.assertEqual(renamed.selected_name, "Renamed")
        self.assertNotIn("First", pattern_handler.user_color_patterns)

    def test_delete_user_and_reject_builtin(self):
        self.save()
        result = self.controller.delete_pattern("User", "Fallback")
        self.assertEqual(result.selected_name, "Fallback")
        self.assertNotIn("User", pattern_handler.user_color_patterns)

        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        with self.assertRaises(pattern_handler.BuiltinPatternDeletionError):
            self.controller.delete_pattern(builtin_name)

    def test_reset_returns_stored_colors_without_persistence(self):
        self.save()
        before = self.user_path.read_bytes()
        result = self.controller.reset_pattern("User")

        self.assertEqual(result.colors_to_apply, COLORS)
        self.assertFalse(result.persisted)
        self.assertEqual(self.user_path.read_bytes(), before)

    def test_single_import_new_conflict_cancel_and_explicit_overwrite(self):
        imported = ImportedPattern("Imported", color_document())
        preparation = type("Preparation", (), {"imported_pattern": imported})()
        callbacks = {
            "choose_conflict": lambda kind, name: "cancel",
            "request_rename": Mock(),
            "report_invalid_name": Mock(),
        }
        added = self.controller.import_single(
            preparation, selected_name=None, **callbacks
        )
        self.assertEqual(added.selected_name, "Imported")
        self.assertEqual(added.colors_to_apply, COLORS)

        cancelled = self.controller.import_single(
            preparation, selected_name="Imported", **callbacks
        )
        self.assertFalse(cancelled.changed)

        replacement = ImportedPattern("Imported", color_document(NEW_COLORS))
        replacement_preparation = type(
            "Preparation", (), {"imported_pattern": replacement}
        )()
        overwritten = self.controller.import_single(
            replacement_preparation,
            selected_name="Imported",
            choose_conflict=lambda kind, name: "overwrite",
            request_rename=Mock(),
            report_invalid_name=Mock(),
        )
        self.assertEqual(overwritten.colors_to_apply, NEW_COLORS)

    def test_builtin_import_conflict_can_be_renamed_but_not_overwritten(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        imported = ImportedPattern(builtin_name, color_document())
        preparation = type("Preparation", (), {"imported_pattern": imported})()
        decisions = []

        result = self.controller.import_single(
            preparation,
            selected_name=None,
            choose_conflict=lambda kind, name: decisions.append(kind) or "rename",
            request_rename=lambda name: "Imported Builtin",
            report_invalid_name=Mock(),
        )

        self.assertEqual(decisions, ["builtin"])
        self.assertEqual(result.selected_name, "Imported Builtin")
        self.assertEqual(
            pattern_handler.army_color_pattern[builtin_name],
            pattern_handler.builtin_color_patterns[builtin_name],
        )

    def test_collection_skip_and_overwrite_return_correct_state(self):
        self.save("Existing")
        existing = ImportedPattern("Existing", color_document(NEW_COLORS))
        new = ImportedPattern("New", color_document())
        collection = ImportedPatternCollection("Collection", (existing, new))
        analysis = self.controller.analyze_collection(collection)
        preparation = type(
            "Preparation", (), {"analysis": analysis, "collection": collection}
        )()

        skipped_operation, skipped = self.controller.import_collection(
            preparation,
            selected_name="Existing",
            overwrite_user_conflicts=False,
        )
        self.assertEqual(skipped.imported_count, 1)
        self.assertEqual(skipped.skipped_user_conflict_count, 1)
        self.assertIsNone(skipped_operation.colors_to_apply)

        overwrite_collection = ImportedPatternCollection("Overwrite", (existing,))
        overwrite_preparation = type(
            "Preparation",
            (),
            {
                "analysis": self.controller.analyze_collection(overwrite_collection),
                "collection": overwrite_collection,
            },
        )()
        overwritten_operation, overwritten = self.controller.import_collection(
            overwrite_preparation,
            selected_name="Existing",
            overwrite_user_conflicts=True,
        )
        self.assertEqual(overwritten.overwritten_count, 1)
        self.assertTrue(overwritten_operation.selected_data_changed)
        self.assertEqual(overwritten_operation.colors_to_apply, NEW_COLORS)

    def test_failed_persistence_preserves_previous_state(self):
        self.save()
        before_file = self.user_path.read_bytes()
        before_memory = OrderedDict(pattern_handler.user_color_patterns)
        failing = PatternController(
            store=Mock(update_user_pattern=Mock(side_effect=OSError("disk full"))),
            get_colors=lambda name: COLORS,
        )

        with self.assertRaises(OSError):
            failing.update_pattern("User", NEW_COLORS)

        self.assertEqual(self.user_path.read_bytes(), before_file)
        self.assertEqual(pattern_handler.user_color_patterns, before_memory)

    def test_controller_has_no_tk_or_widget_dependency(self):
        import src.pattern_controller as module

        source = inspect.getsource(module)
        self.assertNotIn("tkinter", source)
        self.assertNotIn("src.widget", source)
        self.assertNotIn("ArmyPainter", source)

    def test_directory_remembering_occurs_only_after_success(self):
        selection = Mock()
        controller = PatternController(
            file_selection=selection,
            read_single=Mock(side_effect=ValueError("invalid")),
            export_single=Mock(side_effect=OSError("write failed")),
        )
        with self.assertRaises(ValueError):
            controller.prepare_single_import(self.root / "invalid.json")
        with self.assertRaises(OSError):
            controller.export_selected("Pattern", self.root / "out.json")

        selection.remember_successful_pattern_import.assert_not_called()
        selection.remember_successful_pattern_export.assert_not_called()


if __name__ == "__main__":
    unittest.main()
