import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from fake_dialog_gateway import make_dialog_gateway
from src.frame_main import (
    PATTERN_COLLECTION_EXCHANGE_SUFFIX,
    PATTERN_COLLECTION_FILETYPES,
    ArmyPainter,
    suggested_pattern_collection_filename,
)
from src.pattern_exchange import PatternExportError


class FakeSettings:
    def __init__(self, export_directory):
        self.export_directory = export_directory
        self.saved_directories = []

    def get_last_pattern_export_directory(self):
        return self.export_directory

    def set_last_pattern_export_directory(self, directory):
        self.saved_directories.append(directory)


class FakePainter:
    def __init__(self, export_directory=Path("exports")):
        self.dialogs = make_dialog_gateway(self)
        self.settings = FakeSettings(export_directory)


class PatternCollectionFilenameTests(unittest.TestCase):
    def test_collection_filename_reuses_portable_sanitization(self):
        self.assertEqual(
            suggested_pattern_collection_filename('Bad<>:"/\\|?* Name. '),
            "Bad_________ Name.pattern-collection.json",
        )
        self.assertEqual(
            suggested_pattern_collection_filename("CON"),
            "_CON.pattern-collection.json",
        )

    def test_collection_filename_preserves_unicode_and_avoids_duplicate_suffix(self):
        name = "Élite Löwen.pattern-collection.json"
        self.assertEqual(suggested_pattern_collection_filename(name), name)


class PatternCollectionExportGuiTests(unittest.TestCase):
    @patch("src.frame_main.export_user_pattern_collection")
    @patch("src.dialog_gateway.filedialog.asksaveasfilename")
    @patch("src.dialog_gateway.simpledialog.askstring")
    @patch("src.dialog_gateway.messagebox.showinfo")
    @patch(
        "src.frame_main.src.color_pattern_handler.has_user_patterns",
        return_value=False,
    )
    def test_no_user_patterns_shows_information_and_stops(
        self, has_users, showinfo, ask_name, save_dialog, export
    ):
        painter = FakePainter()

        ArmyPainter.export_all_user_patterns(painter)

        showinfo.assert_called_once()
        ask_name.assert_not_called()
        save_dialog.assert_not_called()
        export.assert_not_called()
        self.assertEqual(painter.settings.saved_directories, [])

    @patch("src.dialog_gateway.filedialog.asksaveasfilename")
    @patch("src.dialog_gateway.simpledialog.askstring", return_value=None)
    @patch(
        "src.frame_main.src.color_pattern_handler.has_user_patterns",
        return_value=True,
    )
    def test_collection_name_cancel_stops(self, has_users, ask_name, save_dialog):
        painter = FakePainter()

        ArmyPainter.export_all_user_patterns(painter)

        save_dialog.assert_not_called()
        self.assertEqual(painter.settings.saved_directories, [])

    @patch("src.dialog_gateway.messagebox.showerror")
    @patch("src.dialog_gateway.filedialog.asksaveasfilename")
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="   ")
    @patch(
        "src.frame_main.src.color_pattern_handler.has_user_patterns",
        return_value=True,
    )
    def test_empty_collection_name_is_rejected(
        self, has_users, ask_name, save_dialog, showerror
    ):
        painter = FakePainter()

        ArmyPainter.export_all_user_patterns(painter)

        showerror.assert_called_once()
        save_dialog.assert_not_called()
        self.assertEqual(painter.settings.saved_directories, [])

    @patch("src.frame_main.export_user_pattern_collection")
    @patch("src.dialog_gateway.filedialog.asksaveasfilename", return_value="")
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="My Collection")
    @patch(
        "src.frame_main.src.color_pattern_handler.has_user_patterns",
        return_value=True,
    )
    def test_save_dialog_cancel_does_not_export_or_update_settings(
        self, has_users, ask_name, save_dialog, export
    ):
        painter = FakePainter(Path("remembered"))

        ArmyPainter.export_all_user_patterns(painter)

        export.assert_not_called()
        self.assertEqual(painter.settings.saved_directories, [])
        options = save_dialog.call_args.kwargs
        self.assertEqual(options["initialdir"], Path("remembered"))
        self.assertEqual(options["filetypes"], PATTERN_COLLECTION_FILETYPES)
        self.assertEqual(
            options["defaultextension"], PATTERN_COLLECTION_EXCHANGE_SUFFIX
        )

    @patch("src.frame_main.export_user_pattern_collection")
    @patch("src.dialog_gateway.filedialog.asksaveasfilename")
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="  Élite Collection  ")
    @patch(
        "src.frame_main.src.color_pattern_handler.has_user_patterns",
        return_value=True,
    )
    def test_success_exports_and_remembers_shared_directory(
        self, has_users, ask_name, save_dialog, export
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            export_directory = Path(temporary_directory)
            destination = export_directory / "chosen.pattern-collection.json"
            save_dialog.return_value = str(destination)
            painter = FakePainter(export_directory)

            ArmyPainter.export_all_user_patterns(painter)

        export.assert_called_once_with("Élite Collection", destination)
        self.assertEqual(painter.settings.saved_directories, [export_directory])
        self.assertEqual(
            save_dialog.call_args.kwargs["initialfile"],
            "Élite Collection.pattern-collection.json",
        )

    @patch("src.dialog_gateway.messagebox.showerror")
    @patch(
        "src.frame_main.export_user_pattern_collection",
        side_effect=PatternExportError("disk failure"),
    )
    @patch(
        "src.dialog_gateway.filedialog.asksaveasfilename",
        return_value="C:/exports/failed.pattern-collection.json",
    )
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="My Collection")
    @patch(
        "src.frame_main.src.color_pattern_handler.has_user_patterns",
        return_value=True,
    )
    def test_export_failure_reports_name_path_reason_and_keeps_setting(
        self, has_users, ask_name, save_dialog, export, showerror
    ):
        painter = FakePainter()

        with self.assertLogs("src.frame_main", level="ERROR"):
            ArmyPainter.export_all_user_patterns(painter)

        message = showerror.call_args.args[1]
        self.assertIn("My Collection", message)
        self.assertIn(
            str(Path("C:/exports/failed.pattern-collection.json")), message
        )
        self.assertIn("disk failure", message)
        self.assertEqual(painter.settings.saved_directories, [])

    @patch(
        "src.frame_main.export_user_pattern_collection",
        side_effect=RuntimeError("bug"),
    )
    @patch(
        "src.dialog_gateway.filedialog.asksaveasfilename",
        return_value="C:/exports/failed.pattern-collection.json",
    )
    @patch("src.dialog_gateway.simpledialog.askstring", return_value="My Collection")
    @patch(
        "src.frame_main.src.color_pattern_handler.has_user_patterns",
        return_value=True,
    )
    def test_unexpected_export_error_is_not_suppressed(
        self, has_users, ask_name, save_dialog, export
    ):
        with self.assertRaisesRegex(RuntimeError, "bug"):
            ArmyPainter.export_all_user_patterns(FakePainter())


if __name__ == "__main__":
    unittest.main()
