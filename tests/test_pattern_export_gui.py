import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import (
    PATTERN_EXCHANGE_SUFFIX,
    PATTERN_FILETYPES,
    ArmyPainter,
    suggested_pattern_filename,
)
from src.pattern_exchange import PatternExportError
from src.widget import PatternSelection


class FakePatternList:
    def __init__(self, selected_name):
        self.selected_name = selected_name

    def get_selected_pattern_name(self):
        return self.selected_name

    def get_selected_pattern(self):
        if self.selected_name is None:
            return None
        return PatternSelection(self.selected_name, False)


class FakeSettings:
    def __init__(self, initial_directory):
        self.initial_directory = initial_directory
        self.saved_directories = []

    def get_last_pattern_export_directory(self):
        return self.initial_directory

    def set_last_pattern_export_directory(self, directory):
        self.saved_directories.append(directory)


class FakePainter:
    def __init__(self, selected_name, initial_directory):
        self.frame_army_pattern = FakePatternList(selected_name)
        self.settings = FakeSettings(initial_directory)


class PatternFilenameTests(unittest.TestCase):
    def test_replaces_invalid_characters_and_removes_trailing_dots_and_spaces(self):
        result = suggested_pattern_filename('Bad<>:"/\\|?* Name. ')

        self.assertEqual(result, "Bad_________ Name.pattern.json")

    def test_preserves_spaces_unicode_and_existing_suffix(self):
        self.assertEqual(
            suggested_pattern_filename("Élite Löwen.pattern.json"),
            "Élite Löwen.pattern.json",
        )

    def test_avoids_reserved_windows_names_and_uses_fallback(self):
        self.assertEqual(suggested_pattern_filename("CON"), "_CON.pattern.json")
        self.assertEqual(
            suggested_pattern_filename("COM1 .variant"),
            "_COM1 .variant.pattern.json",
        )
        self.assertEqual(suggested_pattern_filename("..."), "pattern.pattern.json")


class PatternExportGuiTests(unittest.TestCase):
    @patch("src.frame_main.filedialog.asksaveasfilename")
    @patch("src.frame_main.export_pattern")
    def test_no_selection_does_nothing(self, export, save_dialog):
        painter = FakePainter(None, Path("home"))

        ArmyPainter.export_selected_pattern(painter)

        save_dialog.assert_not_called()
        export.assert_not_called()

    @patch("src.frame_main.filedialog.asksaveasfilename", return_value="")
    @patch("src.frame_main.export_pattern")
    def test_cancel_does_not_export_or_update_settings(self, export, save_dialog):
        painter = FakePainter("Selected", Path("exports"))

        ArmyPainter.export_selected_pattern(painter)

        export.assert_not_called()
        self.assertEqual(painter.settings.saved_directories, [])
        self.assertEqual(save_dialog.call_args.kwargs["filetypes"], PATTERN_FILETYPES)
        self.assertEqual(
            save_dialog.call_args.kwargs["defaultextension"],
            PATTERN_EXCHANGE_SUFFIX,
        )

    @patch("src.frame_main.export_pattern")
    @patch("src.frame_main.filedialog.asksaveasfilename")
    def test_success_exports_internal_name_then_remembers_directory(
        self, save_dialog, export
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            export_directory = Path(temporary_directory)
            destination = export_directory / "chosen.pattern.json"
            save_dialog.return_value = str(destination)
            painter = FakePainter("Internal Name", export_directory)

            ArmyPainter.export_selected_pattern(painter)

        export.assert_called_once_with("Internal Name", str(destination))
        self.assertEqual(painter.settings.saved_directories, [export_directory])
        self.assertEqual(
            save_dialog.call_args.kwargs["initialfile"],
            "Internal Name.pattern.json",
        )

    @patch("src.frame_main.showerror")
    @patch(
        "src.frame_main.export_pattern",
        side_effect=PatternExportError("permission denied"),
    )
    @patch(
        "src.frame_main.filedialog.asksaveasfilename",
        return_value="C:/exports/failed.pattern.json",
    )
    def test_export_failure_shows_concise_error_and_does_not_update_settings(
        self, save_dialog, export, showerror
    ):
        painter = FakePainter("Internal Name", Path("exports"))

        with self.assertLogs("src.frame_main", level="ERROR"):
            ArmyPainter.export_selected_pattern(painter)

        message = showerror.call_args.args[1]
        self.assertIn("Internal Name", message)
        self.assertIn("C:/exports/failed.pattern.json", message)
        self.assertIn("permission denied", message)
        self.assertEqual(painter.settings.saved_directories, [])


if __name__ == "__main__":
    unittest.main()
