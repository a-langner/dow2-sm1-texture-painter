import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_pattern_handler import color_key
from src.frame_main import (
    PATTERN_FILETYPES,
    ArmyPainter,
    single_import_selection_policy,
)
from src.pattern_exchange import (
    ImportedPattern,
    InvalidImportedPatternColorsError,
    InvalidImportedPatternNameError,
    InvalidPatternFileError,
    InvalidPatternJsonError,
    PatternImportReadError,
    PatternFileNotFoundError,
    PatternPermissionDeniedError,
    UnsupportedPatternVersionError,
    UserPatternImportConflictError,
)
from src.widget import PatternSelection


class FakePatternList:
    def __init__(self):
        self.selected_name = None
        self.load_count = 0
        self.delete_state_updates = 0

    def load_pattern_list(self, preferred_pattern_name=None):
        self.load_count += 1
        if preferred_pattern_name is not None:
            self.select_pattern(preferred_pattern_name)

    def select_pattern(self, pattern_name):
        self.selected_name = pattern_name
        return "new-item"

    def get_selected_pattern_name(self):
        return self.selected_name

    def get_selected_pattern(self):
        if self.selected_name is None:
            return None
        return PatternSelection(self.selected_name, True)


class FakeColorChooser:
    def __init__(self):
        self.color_boxes = [{"bg": "#000000"} for _ in range(4)]
        self.draw_count = 0

    def draw_rgb_value(self):
        self.draw_count += 1


class FakeSettings:
    def __init__(self, initial_directory):
        self.initial_directory = initial_directory
        self.saved_directories = []

    def get_last_pattern_import_directory(self):
        return self.initial_directory

    def set_last_pattern_import_directory(self, directory):
        self.saved_directories.append(directory)


class FakePainter:
    def __init__(self, initial_directory):
        self.frame_army_pattern = FakePatternList()
        self.frame_color_chooser = FakeColorChooser()
        self.settings = FakeSettings(initial_directory)
        self.refresh_count = 0
        self.menu_state_updates = 0
        self.conflict_decisions = ["cancel"]
        self.replacement_names = []
        self.invalid_name_messages = []

    def refresh_workspace(self):
        self.refresh_count += 1

    def update_pattern_menu_state(self):
        self.menu_state_updates += 1

    def update_pattern_action_states(self, selection=None):
        self.frame_army_pattern.delete_state_updates += 1
        self.menu_state_updates += 1

    def on_pattern_select(self):
        ArmyPainter.on_pattern_select(self)

    def apply_selected_pattern_colors(self, selection=None):
        return ArmyPainter.apply_selected_pattern_colors(self, selection)

    def _show_pattern_import_error(self, title, error, message=None):
        ArmyPainter._show_pattern_import_error(self, title, error, message)

    def _choose_pattern_import_conflict(self, conflict_type, pattern_name):
        return self.conflict_decisions.pop(0)

    def _request_pattern_import_name(self, current_name):
        return self.replacement_names.pop(0)

    def _report_invalid_pattern_import_name(self, message):
        self.invalid_name_messages.append(message)


class PatternImportGuiTests(unittest.TestCase):
    def test_single_import_selection_policy_distinguishes_overwrite_target(self):
        self.assertEqual(
            single_import_selection_policy("Selected", "Selected", True),
            ("Selected", True),
        )
        self.assertEqual(
            single_import_selection_policy("Selected", "Other", True),
            ("Selected", False),
        )
        self.assertEqual(
            single_import_selection_policy("Selected", "New", False),
            ("New", True),
        )

    @patch("src.frame_main.filedialog.askopenfilename", return_value="")
    @patch("src.frame_main.read_pattern_file")
    def test_cancel_does_nothing(self, read_pattern, open_dialog):
        painter = FakePainter(Path("imports"))

        ArmyPainter.import_pattern(painter)

        read_pattern.assert_not_called()
        self.assertEqual(painter.settings.saved_directories, [])
        self.assertEqual(open_dialog.call_args.kwargs["filetypes"], PATTERN_FILETYPES)

    @patch("src.frame_main.showerror")
    @patch("src.frame_main.filedialog.askopenfilename", return_value="bad.json")
    def test_invalid_files_show_specific_errors_without_remembering_directory(
        self, open_dialog, showerror
    ):
        errors = (
            (PatternFileNotFoundError("missing"), "Pattern File Not Found"),
            (PatternPermissionDeniedError("denied"), "Permission Denied"),
            (PatternImportReadError("unreadable"), "Unreadable Pattern File"),
            (InvalidPatternJsonError("malformed"), "Malformed Pattern JSON"),
            (InvalidPatternFileError("wrong format"), "Wrong Pattern Format"),
            (InvalidImportedPatternNameError("bad name"), "Invalid Pattern Name"),
            (
                InvalidImportedPatternColorsError("bad colors"),
                "Invalid Pattern Colors",
            ),
            (
                UnsupportedPatternVersionError("future version"),
                "Unsupported Pattern Version",
            ),
        )
        for error, expected_title in errors:
            with self.subTest(error=type(error).__name__), patch(
                "src.frame_main.read_pattern_file", side_effect=error
            ), self.assertLogs("src.frame_main", level="ERROR"):
                painter = FakePainter(Path("imports"))

                ArmyPainter.import_pattern(painter)

                self.assertEqual(showerror.call_args.args[0], expected_title)
                self.assertEqual(painter.settings.saved_directories, [])
                showerror.reset_mock()

    @patch(
        "src.frame_main.persist_imported_pattern",
        side_effect=UserPatternImportConflictError("duplicate"),
    )
    @patch("src.frame_main.read_pattern_file")
    @patch(
        "src.frame_main.filedialog.askopenfilename",
        return_value="C:/patterns/duplicate.pattern.json",
    )
    def test_conflict_cancel_leaves_list_and_settings_unchanged(
        self, open_dialog, read_pattern, persist
    ):
        read_pattern.return_value = ImportedPattern("Duplicate", {})
        painter = FakePainter(Path("imports"))

        ArmyPainter.import_pattern(painter)

        self.assertEqual(painter.frame_army_pattern.load_count, 0)
        self.assertEqual(painter.settings.saved_directories, [])

    @patch("src.frame_main.showerror")
    @patch(
        "src.frame_main.persist_imported_pattern",
        side_effect=OSError("disk is read-only"),
    )
    @patch("src.frame_main.read_pattern_file")
    @patch(
        "src.frame_main.filedialog.askopenfilename",
        return_value="C:/patterns/import.pattern.json",
    )
    def test_persistence_failure_is_reported_without_refresh_or_setting_update(
        self, open_dialog, read_pattern, persist, showerror
    ):
        read_pattern.return_value = ImportedPattern("Imported", {})
        painter = FakePainter(Path("imports"))

        with self.assertLogs("src.frame_main", level="ERROR"):
            ArmyPainter.import_pattern(painter)

        showerror.assert_called_once_with(
            "Cannot Import Pattern",
            "The Pattern could not be saved:\ndisk is read-only",
        )
        self.assertEqual(painter.frame_army_pattern.load_count, 0)
        self.assertEqual(painter.settings.saved_directories, [])

    @patch("src.frame_main.showerror")
    @patch("src.frame_main.persist_imported_pattern", return_value="Imported")
    @patch("src.frame_main.read_pattern_file")
    @patch("src.frame_main.filedialog.askopenfilename")
    def test_success_imports_selects_applies_and_remembers_directory(
        self, open_dialog, read_pattern, persist, showerror
    ):
        colors = OrderedDict(
            zip(color_key, ("#112233", "#445566", "#778899", "#aabbcc"))
        )
        imported = ImportedPattern("Imported", colors)
        with tempfile.TemporaryDirectory() as temporary_directory:
            import_directory = Path(temporary_directory)
            source = import_directory / "imported.pattern.json"
            open_dialog.return_value = str(source)
            read_pattern.return_value = imported
            painter = FakePainter(import_directory)

            with patch(
                "src.frame_main.get_pattern_colors",
                return_value=list(colors.values()),
            ):
                ArmyPainter.import_pattern(painter)

        read_pattern.assert_called_once_with(str(source))
        persist.assert_called_once_with(imported, target_name=None, overwrite=False)
        self.assertEqual(painter.frame_army_pattern.load_count, 1)
        self.assertEqual(painter.frame_army_pattern.selected_name, "Imported")
        self.assertEqual(
            [box["bg"] for box in painter.frame_color_chooser.color_boxes],
            list(colors.values()),
        )
        self.assertEqual(painter.frame_color_chooser.draw_count, 1)
        self.assertEqual(painter.refresh_count, 1)
        self.assertEqual(painter.frame_army_pattern.delete_state_updates, 1)
        self.assertEqual(painter.menu_state_updates, 1)
        self.assertEqual(painter.settings.saved_directories, [import_directory])
        showerror.assert_not_called()

    @patch("src.frame_main.showerror")
    @patch("src.frame_main.persist_imported_pattern")
    @patch("src.frame_main.read_pattern_file")
    @patch("src.frame_main.filedialog.askopenfilename")
    def test_overwriting_selected_pattern_applies_new_stored_colors(
        self, open_dialog, read_pattern, persist, showerror
    ):
        colors = OrderedDict(
            zip(color_key, ("#112233", "#445566", "#778899", "#aabbcc"))
        )
        imported = ImportedPattern("Selected", colors)
        open_dialog.return_value = "selected.pattern.json"
        read_pattern.return_value = imported
        persist.side_effect = [
            UserPatternImportConflictError("exists"),
            "Selected",
        ]
        painter = FakePainter(Path("imports"))
        painter.frame_army_pattern.selected_name = "Selected"
        painter.conflict_decisions = ["overwrite"]

        with patch(
            "src.frame_main.get_pattern_colors",
            return_value=list(imported.colors.values()),
        ):
            ArmyPainter.import_pattern(painter)

        self.assertEqual(painter.frame_army_pattern.selected_name, "Selected")
        self.assertEqual(painter.refresh_count, 1)
        self.assertEqual(
            [box["bg"] for box in painter.frame_color_chooser.color_boxes],
            list(imported.colors.values()),
        )
        self.assertEqual(painter.frame_army_pattern.delete_state_updates, 1)
        showerror.assert_not_called()

    @patch("src.frame_main.showerror")
    @patch("src.frame_main.persist_imported_pattern")
    @patch("src.frame_main.read_pattern_file")
    @patch("src.frame_main.filedialog.askopenfilename")
    def test_overwriting_another_pattern_preserves_selection_and_current_colors(
        self, open_dialog, read_pattern, persist, showerror
    ):
        colors = OrderedDict(
            zip(color_key, ("#112233", "#445566", "#778899", "#aabbcc"))
        )
        imported = ImportedPattern("Other", colors)
        open_dialog.return_value = "other.pattern.json"
        read_pattern.return_value = imported
        persist.side_effect = [UserPatternImportConflictError("exists"), "Other"]
        painter = FakePainter(Path("imports"))
        painter.frame_army_pattern.selected_name = "Selected"
        painter.conflict_decisions = ["overwrite"]
        colors_before = [
            box["bg"] for box in painter.frame_color_chooser.color_boxes
        ]

        ArmyPainter.import_pattern(painter)

        self.assertEqual(painter.frame_army_pattern.selected_name, "Selected")
        self.assertEqual(
            [box["bg"] for box in painter.frame_color_chooser.color_boxes],
            colors_before,
        )
        self.assertEqual(painter.refresh_count, 0)
        self.assertEqual(painter.frame_army_pattern.delete_state_updates, 1)
        showerror.assert_not_called()

    @patch("src.frame_main.read_pattern_file", side_effect=RuntimeError("bug"))
    @patch("src.frame_main.filedialog.askopenfilename", return_value="pattern.json")
    def test_unexpected_import_error_is_not_suppressed(self, open_dialog, read_pattern):
        with self.assertRaisesRegex(RuntimeError, "bug"):
            ArmyPainter.import_pattern(FakePainter(Path("imports")))


if __name__ == "__main__":
    unittest.main()
