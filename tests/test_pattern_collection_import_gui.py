import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from fake_dialog_gateway import make_dialog_gateway, make_file_selection_service
from src.file_selection_service import PATTERN_COLLECTION_FILETYPES
from src.frame_main import ArmyPainter, format_collection_import_result
from src.pattern_controller import collection_selection_was_overwritten
from src.pattern_exchange import (
    CollectionImportAnalysis,
    CollectionImportResult,
    DuplicatePatternNameInCollectionError,
    ImportedPattern,
    ImportedPatternCollection,
    InvalidPatternCollectionError,
    InvalidPatternCollectionFormatError,
    InvalidPatternJsonError,
    PatternFileNotFoundError,
    PatternImportReadError,
    PatternPermissionDeniedError,
    UnsupportedPatternCollectionVersionError,
)
from src.widget import PatternSelection


class FakeSettings:
    def __init__(self, import_directory):
        self.import_directory = import_directory
        self.saved_directories = []

    def get_last_pattern_import_directory(self):
        return self.import_directory

    def set_last_pattern_import_directory(self, directory):
        self.saved_directories.append(directory)


class FakePatternList:
    def __init__(self, selected_name="Selected"):
        self.selected_name = selected_name
        self.load_calls = []

    def get_selected_pattern(self):
        if self.selected_name is None:
            return None
        return PatternSelection(self.selected_name, True)

    def load_pattern_list(self, preferred_pattern_name=None):
        self.load_calls.append(preferred_pattern_name)


class FakePainter:
    def __init__(self, import_directory=Path("imports")):
        self.dialogs = make_dialog_gateway(self)
        self.settings = FakeSettings(import_directory)
        self.file_selection = make_file_selection_service(self)
        self.frame_army_pattern = FakePatternList()
        self.state_updates = 0
        self.selection_apply_count = 0

    def _show_pattern_import_error(self, title, error, message=None):
        ArmyPainter._show_pattern_import_error(self, title, error, message)

    def update_pattern_action_states(self, selection=None):
        self.state_updates += 1

    def on_pattern_select(self):
        self.selection_apply_count += 1


def collection_and_analysis(conflicts=False):
    pattern = ImportedPattern("New Pattern", {"color": "value"})
    collection = ImportedPatternCollection("My Collection", (pattern,))
    analysis = CollectionImportAnalysis(
        "My Collection",
        () if conflicts else (pattern,),
        (pattern,) if conflicts else (),
        (),
    )
    return collection, analysis


class PatternCollectionImportGuiTests(unittest.TestCase):
    @patch("src.frame_main.read_pattern_collection_file")
    @patch("src.dialog_gateway.filedialog.askopenfilename", return_value="")
    def test_cancel_does_nothing(self, open_dialog, read_collection):
        painter = FakePainter(Path("remembered"))

        ArmyPainter.import_pattern_collection(painter)

        read_collection.assert_not_called()
        self.assertEqual(painter.settings.saved_directories, [])
        self.assertEqual(
            open_dialog.call_args.kwargs["filetypes"], PATTERN_COLLECTION_FILETYPES
        )

    @patch("src.dialog_gateway.messagebox.showerror")
    @patch("src.dialog_gateway.filedialog.askopenfilename", return_value="bad.json")
    def test_invalid_files_have_distinct_errors_and_do_not_update_setting(
        self, open_dialog, showerror
    ):
        errors = (
            (PatternFileNotFoundError("missing"), "Collection File Not Found"),
            (PatternPermissionDeniedError("denied"), "Permission Denied"),
            (PatternImportReadError("unreadable"), "Unreadable Collection File"),
            (InvalidPatternJsonError("malformed"), "Malformed Collection JSON"),
            (
                InvalidPatternCollectionFormatError("wrong"),
                "Wrong Collection Format",
            ),
            (
                UnsupportedPatternCollectionVersionError("future"),
                "Unsupported Collection Version",
            ),
            (
                DuplicatePatternNameInCollectionError("duplicate"),
                "Duplicate Pattern Names",
            ),
            (InvalidPatternCollectionError("invalid"), "Invalid Pattern Collection"),
        )
        for error, title in errors:
            with self.subTest(error=type(error).__name__), patch(
                "src.frame_main.read_pattern_collection_file", side_effect=error
            ), self.assertLogs("src.frame_main", level="ERROR"):
                painter = FakePainter()
                ArmyPainter.import_pattern_collection(painter)
                self.assertEqual(showerror.call_args.args[0], title)
                self.assertEqual(painter.settings.saved_directories, [])
                showerror.reset_mock()

    @patch("src.frame_main.PatternCollectionConflictDialog")
    @patch("src.frame_main.import_analyzed_pattern_collection")
    @patch("src.frame_main.analyze_pattern_collection_import")
    @patch("src.frame_main.read_pattern_collection_file")
    @patch(
        "src.dialog_gateway.filedialog.askopenfilename",
        return_value="C:/collections/valid.pattern-collection.json",
    )
    def test_conflict_dialog_cancel_is_remembered_but_imports_nothing(
        self, open_dialog, read_collection, analyze, persist, conflict_dialog
    ):
        collection, analysis = collection_and_analysis(conflicts=True)
        read_collection.return_value = collection
        analyze.return_value = analysis
        conflict_dialog.return_value = SimpleNamespace(
            result=False, overwrite_user_conflicts=False
        )
        painter = FakePainter()

        ArmyPainter.import_pattern_collection(painter)

        persist.assert_not_called()
        self.assertEqual(painter.settings.saved_directories, [Path("C:/collections")])
        self.assertEqual(painter.frame_army_pattern.load_calls, [])

    @patch("src.dialog_gateway.messagebox.showinfo")
    @patch("src.frame_main.PatternCollectionConflictDialog")
    @patch(
        "src.frame_main.import_analyzed_pattern_collection",
        return_value=CollectionImportResult(0, 1, 0, 0),
    )
    @patch("src.frame_main.analyze_pattern_collection_import")
    @patch("src.frame_main.read_pattern_collection_file")
    @patch("src.dialog_gateway.filedialog.askopenfilename", return_value="valid.json")
    def test_conflict_strategy_is_passed_to_one_atomic_import(
        self,
        open_dialog,
        read_collection,
        analyze,
        persist,
        conflict_dialog,
        showinfo,
    ):
        collection, analysis = collection_and_analysis(conflicts=True)
        read_collection.return_value = collection
        analyze.return_value = analysis
        conflict_dialog.return_value = SimpleNamespace(
            result=True, overwrite_user_conflicts=True
        )
        painter = FakePainter()
        painter.frame_army_pattern.selected_name = "New Pattern"

        ArmyPainter.import_pattern_collection(painter)

        conflict_dialog.assert_called_once_with(painter, analysis)
        persist.assert_called_once_with(analysis, overwrite_user_conflicts=True)
        self.assertEqual(painter.frame_army_pattern.load_calls, ["New Pattern"])
        self.assertEqual(painter.selection_apply_count, 1)
        self.assertIn("1 user pattern overwritten", showinfo.call_args.args[1])

    @patch("src.dialog_gateway.messagebox.showinfo")
    @patch("src.frame_main.PatternCollectionConflictDialog")
    @patch(
        "src.frame_main.import_analyzed_pattern_collection",
        return_value=CollectionImportResult(0, 0, 1, 1),
    )
    @patch("src.frame_main.analyze_pattern_collection_import")
    @patch("src.frame_main.read_pattern_collection_file")
    @patch("src.dialog_gateway.filedialog.askopenfilename", return_value="valid.json")
    def test_skip_strategy_reports_no_change_and_refreshes_once(
        self,
        open_dialog,
        read_collection,
        analyze,
        persist,
        conflict_dialog,
        showinfo,
    ):
        collection, analysis = collection_and_analysis(conflicts=True)
        analysis = analysis._replace(
            builtin_conflicts=(ImportedPattern("Built-in", {}),)
        )
        read_collection.return_value = collection
        analyze.return_value = analysis
        conflict_dialog.return_value = SimpleNamespace(
            result=True, overwrite_user_conflicts=False
        )
        painter = FakePainter()
        painter.frame_army_pattern.selected_name = "New Pattern"

        ArmyPainter.import_pattern_collection(painter)

        persist.assert_called_once_with(analysis, overwrite_user_conflicts=False)
        self.assertEqual(painter.frame_army_pattern.load_calls, ["New Pattern"])
        self.assertEqual(painter.selection_apply_count, 0)
        self.assertIn("No Patterns were imported", showinfo.call_args.args[1])

    @patch("src.frame_main.PatternCollectionImportConfirmationDialog")
    @patch("src.frame_main.analyze_pattern_collection_import")
    @patch("src.frame_main.read_pattern_collection_file")
    @patch(
        "src.dialog_gateway.filedialog.askopenfilename",
        return_value="C:/collections/valid.pattern-collection.json",
    )
    def test_confirmation_cancel_preserves_state_after_remembering_valid_file(
        self, open_dialog, read_collection, analyze, confirmation
    ):
        collection, analysis = collection_and_analysis()
        read_collection.return_value = collection
        analyze.return_value = analysis
        confirmation.return_value = SimpleNamespace(result=False)
        painter = FakePainter()

        with patch("src.frame_main.import_analyzed_pattern_collection") as persist:
            ArmyPainter.import_pattern_collection(painter)

        persist.assert_not_called()
        self.assertEqual(painter.settings.saved_directories, [Path("C:/collections")])
        self.assertEqual(painter.frame_army_pattern.load_calls, [])

    @patch("src.dialog_gateway.messagebox.showinfo")
    @patch("src.frame_main.PatternCollectionImportConfirmationDialog")
    @patch(
        "src.frame_main.import_analyzed_pattern_collection",
        return_value=CollectionImportResult(1, 0, 0, 0),
    )
    @patch("src.frame_main.analyze_pattern_collection_import")
    @patch("src.frame_main.read_pattern_collection_file")
    @patch(
        "src.dialog_gateway.filedialog.askopenfilename",
        return_value="C:/collections/valid.pattern-collection.json",
    )
    def test_all_new_collection_imports_once_and_preserves_selection_and_colors(
        self,
        open_dialog,
        read_collection,
        analyze,
        persist,
        confirmation,
        showinfo,
    ):
        collection, analysis = collection_and_analysis()
        read_collection.return_value = collection
        analyze.return_value = analysis
        confirmation.return_value = SimpleNamespace(result=True)
        painter = FakePainter()
        painter.frame_color_chooser = SimpleNamespace(color_boxes=[{"bg": "#112233"}])

        ArmyPainter.import_pattern_collection(painter)

        persist.assert_called_once_with(analysis, overwrite_user_conflicts=False)
        confirmation.assert_called_once_with(painter, "My Collection", 1, 1)
        self.assertEqual(painter.frame_army_pattern.load_calls, ["Selected"])
        self.assertEqual(painter.frame_color_chooser.color_boxes[0]["bg"], "#112233")
        self.assertIn("1 new pattern imported", showinfo.call_args.args[1])

    @patch("src.dialog_gateway.messagebox.showerror")
    @patch("src.frame_main.PatternCollectionImportConfirmationDialog")
    @patch(
        "src.frame_main.import_analyzed_pattern_collection",
        side_effect=OSError("disk failure"),
    )
    @patch("src.frame_main.analyze_pattern_collection_import")
    @patch("src.frame_main.read_pattern_collection_file")
    @patch("src.dialog_gateway.filedialog.askopenfilename", return_value="valid.json")
    def test_persistence_failure_does_not_refresh(
        self,
        open_dialog,
        read_collection,
        analyze,
        persist,
        confirmation,
        showerror,
    ):
        collection, analysis = collection_and_analysis()
        read_collection.return_value = collection
        analyze.return_value = analysis
        confirmation.return_value = SimpleNamespace(result=True)
        painter = FakePainter()

        with self.assertLogs("src.frame_main", level="ERROR"):
            ArmyPainter.import_pattern_collection(painter)

        self.assertEqual(painter.frame_army_pattern.load_calls, [])
        self.assertIn("disk failure", showerror.call_args.args[1])
        self.assertEqual(painter.settings.saved_directories, [Path(".")])

    @patch(
        "src.frame_main.read_pattern_collection_file",
        side_effect=RuntimeError("programming bug"),
    )
    @patch("src.dialog_gateway.filedialog.askopenfilename", return_value="valid.json")
    def test_unexpected_collection_read_error_is_not_suppressed(
        self, open_dialog, read_collection
    ):
        with self.assertRaisesRegex(RuntimeError, "programming bug"):
            ArmyPainter.import_pattern_collection(FakePainter())

    @patch("src.dialog_gateway.messagebox.showerror")
    @patch("src.frame_main.PatternCollectionImportConfirmationDialog")
    @patch(
        "src.frame_main.import_analyzed_pattern_collection",
        side_effect=RuntimeError("programming bug"),
    )
    @patch("src.frame_main.analyze_pattern_collection_import")
    @patch("src.frame_main.read_pattern_collection_file")
    @patch("src.dialog_gateway.filedialog.askopenfilename", return_value="valid.json")
    def test_unexpected_persistence_error_is_not_suppressed(
        self,
        open_dialog,
        read_collection,
        analyze,
        persist,
        confirmation,
        showerror,
    ):
        collection, analysis = collection_and_analysis()
        read_collection.return_value = collection
        analyze.return_value = analysis
        confirmation.return_value = SimpleNamespace(result=True)

        with self.assertRaisesRegex(RuntimeError, "programming bug"):
            ArmyPainter.import_pattern_collection(FakePainter())

        showerror.assert_not_called()


class PatternCollectionResultSummaryTests(unittest.TestCase):
    def test_summary_includes_only_nonzero_result_lines(self):
        message = format_collection_import_result(CollectionImportResult(12, 3, 4, 2))

        self.assertEqual(
            message,
            "Collection imported.\n\n"
            "12 new patterns imported.\n"
            "3 user patterns overwritten.\n"
            "4 user conflicts skipped.\n"
            "2 built-in conflicts skipped.",
        )

    def test_no_change_summary_explains_skipped_conflicts(self):
        message = format_collection_import_result(CollectionImportResult(0, 0, 2, 1))

        self.assertIn("No Patterns were imported.", message)
        self.assertIn("2 user conflicts skipped.", message)
        self.assertIn("1 built-in conflict skipped.", message)


class PatternCollectionSelectionPolicyTests(unittest.TestCase):
    def test_reapplies_only_an_explicitly_overwritten_selected_user_pattern(self):
        _, analysis = collection_and_analysis(conflicts=True)

        self.assertTrue(
            collection_selection_was_overwritten("New Pattern", analysis, True)
        )
        self.assertFalse(
            collection_selection_was_overwritten("New Pattern", analysis, False)
        )
        self.assertFalse(
            collection_selection_was_overwritten("Another Pattern", analysis, True)
        )
        self.assertFalse(collection_selection_was_overwritten(None, analysis, True))


if __name__ == "__main__":
    unittest.main()
