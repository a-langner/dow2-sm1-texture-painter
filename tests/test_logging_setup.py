import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
import src.logging_setup as logging_setup


class ApplicationLoggingSetupTests(unittest.TestCase):
    def setUp(self):
        self.root_logger = logging.getLogger()
        self.original_level = self.root_logger.level
        self.original_capture_warnings = logging._warnings_showwarning is not None
        self._remove_application_handlers()

    def tearDown(self):
        self._remove_application_handlers()
        self.root_logger.setLevel(self.original_level)
        logging.captureWarnings(self.original_capture_warnings)

    def _remove_application_handlers(self):
        for handler in list(self.root_logger.handlers):
            if getattr(handler, logging_setup._APPLICATION_HANDLER_MARKER, False):
                self.root_logger.removeHandler(handler)
                handler.close()

    def test_creates_log_directory_file_and_writes_utf8_record(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory) / "user-data"

            log_path = logging_setup.configure_application_logging(data_directory)
            logging.getLogger("src.example").info("Unicode: Überprüfung ★")
            for handler in self.root_logger.handlers:
                handler.flush()

            expected_path = (
                data_directory
                / logging_setup.LOG_DIRECTORY_NAME
                / logging_setup.LOG_FILENAME
            ).resolve()
            self.assertEqual(log_path, expected_path)
            self.assertTrue(expected_path.parent.is_dir())
            self.assertTrue(expected_path.is_file())
            contents = expected_path.read_text(encoding="utf-8")
            self.assertIn("INFO src.example: Unicode: Überprüfung ★", contents)
            self._remove_application_handlers()

    def test_repeated_configuration_reuses_one_application_handler(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            first_path = logging_setup.configure_application_logging(
                temporary_directory
            )
            second_path = logging_setup.configure_application_logging(
                temporary_directory
            )

            application_handlers = [
                handler
                for handler in self.root_logger.handlers
                if getattr(
                    handler,
                    logging_setup._APPLICATION_HANDLER_MARKER,
                    False,
                )
            ]
            self.assertEqual(first_path, second_path)
            self.assertEqual(len(application_handlers), 1)
            self._remove_application_handlers()

    def test_file_handler_failure_falls_back_once_to_stderr(self):
        with tempfile.TemporaryDirectory() as temporary_directory, patch(
            "src.logging_setup.RotatingFileHandler",
            side_effect=PermissionError("simulated denial"),
        ):
            first_result = logging_setup.configure_application_logging(
                temporary_directory
            )
            second_result = logging_setup.configure_application_logging(
                temporary_directory
            )

        application_handlers = [
            handler
            for handler in self.root_logger.handlers
            if getattr(handler, logging_setup._APPLICATION_HANDLER_MARKER, False)
        ]
        self.assertIsNone(first_result)
        self.assertIsNone(second_result)
        self.assertEqual(len(application_handlers), 1)
        self.assertIs(type(application_handlers[0]), logging.StreamHandler)

    def test_uses_override_instead_of_real_user_data_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory, patch(
            "src.logging_setup.get_user_data_file_path",
            wraps=logging_setup.get_user_data_file_path,
        ) as get_user_data_file_path:
            data_directory = Path(temporary_directory) / "isolated-data"

            log_path = logging_setup.configure_application_logging(data_directory)
            self._remove_application_handlers()

        get_user_data_file_path.assert_called_once_with(
            Path("logs") / "application.log",
            data_directory=data_directory,
        )
        self.assertTrue(log_path.is_relative_to(data_directory.resolve()))
        self.assertNotEqual(
            data_directory.resolve(),
            test_support.TEST_USER_DATA_DIRECTORY.resolve(),
        )


if __name__ == "__main__":
    unittest.main()
