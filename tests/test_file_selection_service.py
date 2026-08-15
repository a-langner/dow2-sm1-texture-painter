import tempfile
import unittest
from pathlib import Path

import test_support  # noqa: F401 - installs the user-data path redirect
from fake_dialog_gateway import FakeDialogGateway
from src.file_selection_service import (
    FileSelectionService,
    PATTERN_COLLECTION_FILETYPES,
    PATTERN_FILETYPES,
)
from src.settings_handler import SettingsHandler


class FileSelectionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.settings = SettingsHandler(
            settings_path=self.root / "data" / "settings.json",
            home_directory=self.home,
        )
        self.dialogs = FakeDialogGateway()
        self.service = FileSelectionService(
            self.settings, self.dialogs, home_directory=self.home
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_valid_remembered_directory_is_used(self):
        remembered = self.root / "textures"
        remembered.mkdir()
        self.settings.remember_diffuse_file(remembered / "unit_dif.png")

        self.service.choose_diffuse_file()

        self.assertEqual(
            self.dialogs.calls[-1][1]["initial_directory"], remembered.resolve()
        )

    def test_missing_remembered_directory_falls_back_to_home(self):
        self.settings.last_diffuse_directory = self.root / "missing"

        self.service.choose_diffuse_file()

        self.assertEqual(
            self.dialogs.calls[-1][1]["initial_directory"], self.home
        )

    def test_cancel_and_selection_do_not_remember_diffuse_before_success(self):
        self.assertIsNone(self.service.choose_diffuse_file())
        self.dialogs.open_file_result = self.root / "chosen" / "unit_dif.png"

        selected = self.service.choose_diffuse_file()

        self.assertEqual(selected, self.dialogs.open_file_result)
        self.assertIsNone(self.settings.last_diffuse_directory)

    def test_successful_diffuse_is_remembered_and_persisted(self):
        textures = self.root / "textures"
        textures.mkdir()
        selected = textures / "unit_dif.png"

        self.service.remember_successful_diffuse(selected)
        reloaded = SettingsHandler(self.settings.path, home_directory=self.home)

        self.assertEqual(reloaded.last_diffuse_directory, textures.resolve())

    def test_pattern_imports_share_directory_and_require_explicit_success(self):
        imports = self.root / "imports"
        imports.mkdir()
        source = imports / "patterns.pattern.json"
        self.dialogs.open_file_result = source

        self.service.choose_pattern_import_file()
        self.assertIsNone(self.settings.last_pattern_import_directory)
        self.service.remember_successful_pattern_import(source)
        self.service.choose_pattern_collection_import_file()

        self.assertEqual(
            self.dialogs.calls[-1][1]["initial_directory"], imports.resolve()
        )
        self.assertEqual(
            self.dialogs.calls[-1][1]["filetypes"], PATTERN_COLLECTION_FILETYPES
        )

    def test_pattern_exports_share_directory_and_remember_only_after_success(self):
        exports = self.root / "exports"
        exports.mkdir()
        destination = exports / "patterns.pattern.json"
        self.dialogs.save_file_result = destination

        self.service.choose_pattern_export_destination("patterns.pattern.json")
        self.assertIsNone(self.settings.last_pattern_export_directory)
        self.service.remember_successful_pattern_export(destination)
        self.service.choose_pattern_collection_export_destination(
            "patterns.pattern-collection.json"
        )

        self.assertEqual(
            self.dialogs.calls[-1][1]["initial_directory"], exports.resolve()
        )
        self.assertNotEqual(PATTERN_FILETYPES, PATTERN_COLLECTION_FILETYPES)

    def test_channel_selection_does_not_read_or_change_remembered_diffuse(self):
        remembered = self.root / "textures"
        remembered.mkdir()
        self.settings.remember_diffuse_file(remembered / "unit_dif.png")

        self.service.choose_channel_file()

        self.assertEqual(
            self.dialogs.calls[-1][1]["initial_directory"], self.home
        )
        self.assertEqual(
            self.dialogs.calls[-1][1]["title"], "Open Team Color Mask"
        )
        self.assertEqual(self.settings.last_diffuse_directory, remembered.resolve())


if __name__ == "__main__":
    unittest.main()
