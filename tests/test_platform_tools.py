import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from fake_dialog_gateway import make_dialog_gateway
from src.frame_main import ArmyPainter
from src.platform_tools import open_directory_in_file_manager


class OpenDirectoryHelperTests(unittest.TestCase):
    @patch("src.platform_tools.platform.system", return_value="Windows")
    @patch("src.platform_tools.os.startfile", create=True)
    def test_windows_uses_startfile(self, startfile, system):
        directory = Path("C:/diagnostics/logs")

        open_directory_in_file_manager(directory)

        startfile.assert_called_once_with(str(directory))

    @patch("src.platform_tools.subprocess.Popen")
    @patch("src.platform_tools.platform.system", return_value="Darwin")
    def test_macos_uses_open_argument_sequence(self, system, popen):
        directory = Path("/Users/example/Library/Logs")

        open_directory_in_file_manager(directory)

        popen.assert_called_once_with(["open", str(directory)])

    @patch("src.platform_tools.subprocess.Popen")
    @patch("src.platform_tools.platform.system", return_value="Linux")
    def test_linux_uses_xdg_open_argument_sequence(self, system, popen):
        directory = Path("/home/example/.local/share/app/logs")

        open_directory_in_file_manager(directory)

        popen.assert_called_once_with(["xdg-open", str(directory)])

    @patch("src.platform_tools.subprocess.Popen")
    @patch("src.platform_tools.platform.system", return_value="UnknownOS")
    def test_unsupported_platform_does_not_launch(self, system, popen):
        with self.assertRaisesRegex(OSError, "unsupported"):
            open_directory_in_file_manager(Path("logs"))

        popen.assert_not_called()

    @patch(
        "src.platform_tools.subprocess.Popen", side_effect=FileNotFoundError("missing")
    )
    @patch("src.platform_tools.platform.system", return_value="Linux")
    def test_missing_opener_is_reported_as_launch_failure(self, system, popen):
        with self.assertRaisesRegex(FileNotFoundError, "missing"):
            open_directory_in_file_manager(Path("logs"))


class OpenLogFolderGuiTests(unittest.TestCase):
    @patch("src.frame_main.open_directory_in_file_manager")
    def test_opens_containing_directory_without_changing_geometry(self, open_directory):
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "logs" / "application.log"
            painter = SimpleNamespace(
                application_log_path=log_path,
                window_geometry="900x700+20+20",
            )

            ArmyPainter.open_log_folder(painter)

            self.assertTrue(log_path.parent.is_dir())
            open_directory.assert_called_once_with(log_path.parent)
            self.assertEqual(painter.window_geometry, "900x700+20+20")

    @patch("src.dialog_gateway.messagebox.showinfo")
    @patch("src.frame_main.open_directory_in_file_manager")
    def test_unavailable_log_shows_information_without_launching(
        self, open_directory, showinfo
    ):
        painter = SimpleNamespace(application_log_path=None)
        painter.dialogs = make_dialog_gateway(painter)

        ArmyPainter.open_log_folder(painter)

        open_directory.assert_not_called()
        showinfo.assert_called_once_with(
            "Application Log Unavailable",
            "A persistent application log is not available.",
            parent=painter,
        )

    @patch("src.dialog_gateway.messagebox.showerror")
    @patch("src.frame_main.LOGGER.exception")
    @patch(
        "src.frame_main.open_directory_in_file_manager",
        side_effect=OSError("launcher failed"),
    )
    def test_launch_failure_is_logged_and_shown_concisely(
        self, open_directory, log_exception, showerror
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "logs" / "application.log"
            painter = SimpleNamespace(application_log_path=log_path)
            painter.dialogs = make_dialog_gateway(painter)

            ArmyPainter.open_log_folder(painter)

        log_exception.assert_called_once()
        showerror.assert_called_once()
        message = showerror.call_args.args[1]
        self.assertIn(str(log_path.parent), message)
        self.assertIn("launcher failed", message)
        self.assertNotIn("Traceback", message)


if __name__ == "__main__":
    unittest.main()
