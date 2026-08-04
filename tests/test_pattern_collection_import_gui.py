import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import PATTERN_COLLECTION_FILETYPES, ArmyPainter
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
        self.settings = FakeSettings(import_directory)
        self.frame_army_pattern = FakePatternList()
        self.state_updates = 0

    def _show_pattern_import_error(self, title, error, message=None):
        ArmyPainter._show_pattern_import_error(self, title, error, message)

    def update_pattern_command_states(self, selection=None):
        self.state_updates += 1


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
    @patch("src.frame_main.filedialog.askopenfilename", return_value="")
    def test_cancel_does_nothing(self, open_dialog, read_collection):
        painter = FakePainter(Path("remembered"))

        ArmyPainter.import_pattern_collection(painter)

        read_collection.assert_not_called()
        self.assertEqual(painter.settings.saved_directories, [])
        self.assertEqual(
            open_dialog.call_args.kwargs["filetypes"], PATTERN_COLLECTION_FILETYPES
        )

    @patch("src.frame_main.showerror")
    @patch("src.frame_main.filedialog.askopenfilename", return_value="bad.json")
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

    @patch("src.frame_main.showinfo")
    @patch("src.frame_main.analyze_pattern_collection_import")
    @patch("src.frame_main.read_pattern_collection_file")
    @patch(
        "src.frame_main.filedialog.askopenfilename",
        return_value="C:/collections/valid.pattern-collection.json",
    )
    def test_valid_conflicting_collection_is_remembered_but_not_imported(
        self, open_dialog, read_collection, analyze, showinfo
    ):
        collection, analysis = collection_and_analysis(conflicts=True)
        read_collection.return_value = collection
        analyze.return_value = analysis
        painter = FakePainter()

        with patch("src.frame_main.import_analyzed_pattern_collection") as persist:
            ArmyPainter.import_pattern_collection(painter)

        persist.assert_not_called()
        self.assertEqual(painter.settings.saved_directories, [Path("C:/collections")])
        self.assertIn("No Patterns were imported", showinfo.call_args.args[1])
        self.assertEqual(painter.frame_army_pattern.load_calls, [])

    @patch("src.frame_main.PatternCollectionImportConfirmationDialog")
    @patch("src.frame_main.analyze_pattern_collection_import")
    @patch("src.frame_main.read_pattern_collection_file")
    @patch(
        "src.frame_main.filedialog.askopenfilename",
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

    @patch("src.frame_main.showinfo")
    @patch("src.frame_main.PatternCollectionImportConfirmationDialog")
    @patch(
        "src.frame_main.import_analyzed_pattern_collection",
        return_value=CollectionImportResult(1, 0, 0, 0),
    )
    @patch("src.frame_main.analyze_pattern_collection_import")
    @patch("src.frame_main.read_pattern_collection_file")
    @patch(
        "src.frame_main.filedialog.askopenfilename",
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

        persist.assert_called_once_with(analysis)
        confirmation.assert_called_once_with(painter, "My Collection", 1, 1)
        self.assertEqual(painter.frame_army_pattern.load_calls, ["Selected"])
        self.assertEqual(painter.frame_color_chooser.color_boxes[0]["bg"], "#112233")
        self.assertIn("1 pattern imported", showinfo.call_args.args[1])

    @patch("src.frame_main.showerror")
    @patch("src.frame_main.PatternCollectionImportConfirmationDialog")
    @patch(
        "src.frame_main.import_analyzed_pattern_collection",
        side_effect=OSError("disk failure"),
    )
    @patch("src.frame_main.analyze_pattern_collection_import")
    @patch("src.frame_main.read_pattern_collection_file")
    @patch("src.frame_main.filedialog.askopenfilename", return_value="valid.json")
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


if __name__ == "__main__":
    unittest.main()
