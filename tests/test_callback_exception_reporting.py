import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter


class FakePainter:
    def __init__(self, log_path):
        self.application_log_path = log_path
        self._handling_callback_exception = False


def captured_exception_info():
    try:
        raise RuntimeError("sensitive diagnostic detail")
    except RuntimeError:
        return sys.exc_info()


class CallbackExceptionReportingTests(unittest.TestCase):
    @patch("src.frame_main.showerror")
    @patch("src.frame_main.LOGGER.error")
    def test_logs_supplied_traceback_and_shows_concise_log_path(
        self, log_error, showerror
    ):
        painter = FakePainter(Path("user-data") / "logs" / "application.log")
        exception_info = captured_exception_info()

        ArmyPainter.report_callback_exception(painter, *exception_info)

        log_error.assert_called_once_with(
            "Unhandled Tk callback exception",
            exc_info=exception_info,
        )
        showerror.assert_called_once()
        (title,) = showerror.call_args.args
        message = showerror.call_args.kwargs["message"]
        self.assertEqual(title, "Unexpected Error")
        self.assertIs(showerror.call_args.kwargs["parent"], painter)
        self.assertIn(str(painter.application_log_path), message)
        self.assertIn("The operation could not be completed", message)
        self.assertNotIn("Traceback", message)
        self.assertNotIn("sensitive diagnostic detail", message)
        self.assertFalse(painter._handling_callback_exception)

    @patch("src.frame_main.showerror")
    @patch("src.frame_main.LOGGER.error")
    def test_without_log_path_uses_fallback_text(self, log_error, showerror):
        painter = FakePainter(None)

        ArmyPainter.report_callback_exception(painter, *captured_exception_info())

        message = showerror.call_args.kwargs["message"]
        self.assertIn(
            "Technical details could not be written to the application log.",
            message,
        )
        self.assertNotIn("Technical details were written to:", message)

    @patch("src.frame_main.showerror")
    @patch("src.frame_main.LOGGER.error")
    def test_reentry_logs_without_opening_a_nested_dialog(self, log_error, showerror):
        painter = FakePainter(Path("application.log"))
        painter._handling_callback_exception = True
        exception_info = captured_exception_info()

        ArmyPainter.report_callback_exception(painter, *exception_info)

        log_error.assert_called_once_with(
            "Additional unhandled Tk callback exception while reporting an error",
            exc_info=exception_info,
        )
        showerror.assert_not_called()
        self.assertTrue(painter._handling_callback_exception)

    @patch("src.frame_main.LOGGER.exception")
    @patch("src.frame_main.LOGGER.error")
    @patch(
        "src.frame_main.showerror",
        side_effect=RuntimeError("dialog unavailable"),
    )
    def test_dialog_failure_is_logged_without_recursion(
        self, showerror, log_error, log_exception
    ):
        painter = FakePainter(Path("application.log"))

        ArmyPainter.report_callback_exception(painter, *captured_exception_info())

        showerror.assert_called_once()
        log_error.assert_called_once()
        log_exception.assert_called_once_with(
            "Could not display the unexpected-error dialog"
        )
        self.assertFalse(painter._handling_callback_exception)


if __name__ == "__main__":
    unittest.main()
