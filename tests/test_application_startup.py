import unittest
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
import src.frame_main as frame_main


class FakeArmyPainter:
    def __init__(self, events, application_log_path=None):
        self.events = events
        self.application_log_path = application_log_path
        self.events.append(("construct", application_log_path))

    def mainloop(self):
        self.events.append(("mainloop", self.application_log_path))


class ApplicationStartupTests(unittest.TestCase):
    def test_logging_is_configured_before_one_root_is_constructed(self):
        events = []
        log_path = Path("diagnostics") / "application.log"

        def configure_logging():
            events.append(("configure", log_path))
            return log_path

        def construct_painter(application_log_path=None):
            return FakeArmyPainter(events, application_log_path)

        with patch.object(
            frame_main,
            "configure_application_logging",
            side_effect=configure_logging,
        ) as configure, patch.object(
            frame_main, "ArmyPainter", side_effect=construct_painter
        ) as painter_type, patch.object(
            frame_main, "log_application_startup"
        ) as log_startup, self.assertLogs(
            frame_main.LOGGER, level="INFO"
        ) as captured:
            frame_main.main()

        self.assertEqual(
            events,
            [
                ("configure", log_path),
                ("construct", log_path),
                ("mainloop", log_path),
            ],
        )
        configure.assert_called_once_with()
        painter_type.assert_called_once_with(application_log_path=log_path)
        log_startup.assert_called_once_with(log_path)
        self.assertEqual(
            captured.output.count("INFO:src.frame_main:Clean application shutdown"),
            1,
        )

    def test_startup_metadata_is_logged_without_settings_or_pattern_data(self):
        log_path = Path("user-data") / "logs" / "application.log"
        with patch.object(
            frame_main.platform, "platform", return_value="TestOS"
        ), patch.object(frame_main.sys, "version", "3.test"), patch.object(
            frame_main.sys, "frozen", True, create=True
        ), self.assertLogs(
            frame_main.LOGGER, level="INFO"
        ) as captured:
            frame_main.log_application_startup(log_path)

        output = "\n".join(captured.output)
        self.assertIn("Application startup", output)
        self.assertIn(f"Application version: {frame_main.VERSION}", output)
        self.assertIn("Python version: 3.test", output)
        self.assertIn("Operating system/platform: TestOS", output)
        self.assertIn("Running from a PyInstaller bundle: True", output)
        self.assertIn(f"Application log path: {log_path}", output)
        self.assertNotIn("primary_colour_name", output)
        self.assertNotIn("last_diffuse_directory", output)

    def test_stderr_fallback_path_is_reported_clearly(self):
        with patch.object(
            frame_main.platform, "platform", return_value="TestOS"
        ), self.assertLogs(frame_main.LOGGER, level="INFO") as captured:
            frame_main.log_application_startup(None)

        self.assertIn(
            "Application log path: unavailable; using stderr fallback",
            "\n".join(captured.output),
        )


if __name__ == "__main__":
    unittest.main()
