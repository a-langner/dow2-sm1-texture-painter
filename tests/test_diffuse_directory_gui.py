import unittest
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
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
        self.load_error = load_error
        self.loaded = []

    def load_file(self, filepath):
        self.loaded.append(filepath)
        if self.load_error is not None:
            raise self.load_error


class DiffuseDirectoryGuiTests(unittest.TestCase):
    @patch("src.frame_main.filedialog.askopenfilename", return_value="")
    def test_cancellation_does_not_update_setting(self, askopenfilename):
        painter = FakePainter()

        ArmyPainter.open_diffuse(painter)

        self.assertEqual(painter.loaded, [])
        self.assertEqual(painter.settings.remembered, [])
        self.assertEqual(askopenfilename.call_args.kwargs["initialdir"], Path("home"))

    @patch("src.frame_main.showerror")
    @patch(
        "src.frame_main.filedialog.askopenfilename",
        return_value="C:/invalid/unit_dif.png",
    )
    def test_validation_failure_does_not_update_setting(
        self, askopenfilename, showerror
    ):
        painter = FakePainter(TextureValidationError("invalid"))

        ArmyPainter.open_diffuse(painter)

        self.assertEqual(painter.settings.remembered, [])
        showerror.assert_called_once()

    @patch(
        "src.frame_main.filedialog.askopenfilename",
        return_value="C:/textures/unit_dif.png",
    )
    def test_successful_load_updates_setting(self, askopenfilename):
        painter = FakePainter()

        ArmyPainter.open_diffuse(painter)

        self.assertEqual(painter.settings.remembered, ["C:/textures/unit_dif.png"])


if __name__ == "__main__":
    unittest.main()
