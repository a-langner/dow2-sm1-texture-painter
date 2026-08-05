import unittest
from pathlib import Path

import test_support  # noqa: F401 - installs the user-data path redirect
from fake_dialog_gateway import FakeDialogGateway, make_file_selection_service
from src.constant import OPEN_FILETYPES
from src.frame_main import ArmyPainter
from src.image_process import TextureValidationError


class FakeSettings:
    def __init__(self):
        self.initial_directory = Path("home")
        self.remembered = []
        self.path = Path("settings.json")

    def get_diffuse_initial_directory(self):
        return self.initial_directory

    def remember_diffuse_file(self, filepath):
        self.remembered.append(filepath)


class FakePainter:
    def __init__(self, load_error=None):
        self.settings = FakeSettings()
        self.dialogs = FakeDialogGateway()
        self.load_error = load_error
        self.loaded = []
        self.file_selection = make_file_selection_service(self)

    def load_file(self, filepath):
        self.loaded.append(filepath)
        if self.load_error is not None:
            raise self.load_error


class DiffuseDirectoryGuiTests(unittest.TestCase):
    def test_cancellation_does_not_update_setting(self):
        painter = FakePainter()

        ArmyPainter.open_diffuse(painter)

        self.assertEqual(painter.loaded, [])
        self.assertEqual(painter.settings.remembered, [])
        self.assertEqual(
            painter.dialogs.calls,
            [
                (
                    "choose_open_file",
                    {
                        "initial_directory": Path("home"),
                        "filetypes": OPEN_FILETYPES,
                    },
                )
            ],
        )

    def test_validation_failure_does_not_update_setting(self):
        painter = FakePainter(TextureValidationError("invalid"))
        painter.dialogs.open_file_result = Path("C:/invalid/unit_dif.png")

        ArmyPainter.open_diffuse(painter)

        self.assertEqual(painter.settings.remembered, [])
        self.assertEqual(painter.dialogs.calls[-1][0], "show_error")

    def test_successful_load_updates_setting(self):
        painter = FakePainter()
        painter.dialogs.open_file_result = Path("C:/textures/unit_dif.png")

        ArmyPainter.open_diffuse(painter)

        self.assertEqual(
            painter.settings.remembered, [Path("C:/textures/unit_dif.png")]
        )


if __name__ == "__main__":
    unittest.main()
