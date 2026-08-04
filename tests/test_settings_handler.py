import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.settings_handler import (
    SETTINGS_FORMAT,
    SETTINGS_VERSION,
    SettingsHandler,
)


def settings_document(directory, **additional_directories):
    document = {
        "format": SETTINGS_FORMAT,
        "version": SETTINGS_VERSION,
        "last_diffuse_directory": str(directory),
    }
    document.update(
        {name: str(value) for name, value in additional_directories.items()}
    )
    return document


class SettingsHandlerTests(unittest.TestCase):
    def test_missing_file_uses_home_directory_without_creating_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "data" / "settings.json"
            handler = SettingsHandler(settings_path, home_directory=root)

            self.assertEqual(handler.get_diffuse_initial_directory(), root)
            self.assertFalse(settings_path.exists())
            self.assertIsNone(handler.load_error)

    def test_valid_remembered_directory_is_used(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            remembered = root / "textures"
            remembered.mkdir()
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(settings_document(remembered)), encoding="utf-8"
            )

            handler = SettingsHandler(settings_path, home_directory=root)

            self.assertEqual(handler.get_diffuse_initial_directory(), remembered)

    def test_older_version_one_file_uses_home_for_missing_pattern_directories(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(settings_document(root)), encoding="utf-8"
            )

            handler = SettingsHandler(settings_path, home_directory=root)

            self.assertEqual(handler.get_last_pattern_import_directory(), root)
            self.assertEqual(handler.get_last_pattern_export_directory(), root)

    def test_valid_import_and_export_directories_remain_separate(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            import_directory = root / "imports"
            export_directory = root / "exports"
            import_directory.mkdir()
            export_directory.mkdir()
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    settings_document(
                        root,
                        last_pattern_import_directory=import_directory,
                        last_pattern_export_directory=export_directory,
                    )
                ),
                encoding="utf-8",
            )

            handler = SettingsHandler(settings_path, home_directory=root)

            self.assertEqual(
                handler.get_last_pattern_import_directory(), import_directory
            )
            self.assertEqual(
                handler.get_last_pattern_export_directory(), export_directory
            )

    def test_nonexistent_pattern_directories_fall_back_to_home(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    settings_document(
                        root,
                        last_pattern_import_directory=root / "gone-import",
                        last_pattern_export_directory=root / "gone-export",
                    )
                ),
                encoding="utf-8",
            )

            handler = SettingsHandler(settings_path, home_directory=root)

            self.assertEqual(handler.get_last_pattern_import_directory(), root)
            self.assertEqual(handler.get_last_pattern_export_directory(), root)

    def test_missing_remembered_directory_falls_back_to_home(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(settings_document(root / "gone")), encoding="utf-8"
            )

            handler = SettingsHandler(settings_path, home_directory=root)

            self.assertEqual(handler.get_diffuse_initial_directory(), root)

    def test_malformed_json_is_nonfatal_and_preserved(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            original = "{broken"
            settings_path.write_text(original, encoding="utf-8")

            with self.assertLogs("src.settings_handler", level="ERROR"):
                handler = SettingsHandler(settings_path, home_directory=root)

            self.assertEqual(handler.get_diffuse_initial_directory(), root)
            self.assertIsNotNone(handler.load_error)
            self.assertEqual(settings_path.read_text(encoding="utf-8"), original)

            with self.assertRaises(OSError):
                handler.remember_diffuse_file(root / "unit_dif.png")

            self.assertEqual(settings_path.read_text(encoding="utf-8"), original)

    def test_inaccessible_file_is_nonfatal(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"

            with patch.object(Path, "open", side_effect=PermissionError("denied")):
                with self.assertLogs("src.settings_handler", level="ERROR"):
                    handler = SettingsHandler(settings_path, home_directory=root)

            self.assertEqual(handler.get_diffuse_initial_directory(), root)
            self.assertIsInstance(handler.load_error, PermissionError)

    def test_unsupported_format_and_version_are_nonfatal(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for document in (
                {**settings_document(root), "format": "other"},
                {**settings_document(root), "version": 2},
            ):
                settings_path = root / "settings.json"
                settings_path.write_text(json.dumps(document), encoding="utf-8")

                with self.assertLogs("src.settings_handler", level="ERROR"):
                    handler = SettingsHandler(settings_path, home_directory=root)

                self.assertEqual(handler.get_diffuse_initial_directory(), root)
                self.assertIsNotNone(handler.load_error)

    def test_setting_persists_through_new_handler_instance(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            texture_directory = root / "nested" / "textures"
            texture_directory.mkdir(parents=True)
            diffuse_file = texture_directory / "unit_dif.png"
            settings_path = root / "data" / "settings.json"

            SettingsHandler(settings_path, root).remember_diffuse_file(diffuse_file)
            reloaded = SettingsHandler(settings_path, root)

            self.assertEqual(
                reloaded.get_diffuse_initial_directory(),
                texture_directory.resolve(),
            )

    def test_pattern_directories_persist_through_new_handler_instance(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            import_directory = root / "imports"
            export_directory = root / "exports"
            import_directory.mkdir()
            export_directory.mkdir()
            settings_path = root / "data" / "settings.json"
            handler = SettingsHandler(settings_path, root)

            handler.set_last_pattern_import_directory(import_directory)
            handler.set_last_pattern_export_directory(export_directory)
            reloaded = SettingsHandler(settings_path, root)

            self.assertEqual(
                reloaded.get_last_pattern_import_directory(),
                import_directory.resolve(),
            )
            self.assertEqual(
                reloaded.get_last_pattern_export_directory(),
                export_directory.resolve(),
            )

    def test_atomic_write_failure_preserves_file_and_memory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            old_directory = root / "old"
            new_directory = root / "new"
            old_directory.mkdir()
            new_directory.mkdir()
            settings_path = root / "settings.json"
            original = json.dumps(settings_document(old_directory))
            settings_path.write_text(original, encoding="utf-8")
            handler = SettingsHandler(settings_path, root)

            with patch("src.settings_handler.os.replace", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    handler.remember_diffuse_file(new_directory / "unit_dif.png")

            self.assertEqual(settings_path.read_text(encoding="utf-8"), original)
            self.assertEqual(handler.last_diffuse_directory, old_directory)

    def test_failed_pattern_directory_write_preserves_file_and_memory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            old_directory = root / "old"
            new_directory = root / "new"
            old_directory.mkdir()
            new_directory.mkdir()
            settings_path = root / "settings.json"
            original = json.dumps(
                settings_document(root, last_pattern_import_directory=old_directory)
            )
            settings_path.write_text(original, encoding="utf-8")
            handler = SettingsHandler(settings_path, root)

            with patch("src.settings_handler.os.replace", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    handler.set_last_pattern_import_directory(new_directory)

            self.assertEqual(settings_path.read_text(encoding="utf-8"), original)
            self.assertEqual(handler.last_pattern_import_directory, old_directory)


if __name__ == "__main__":
    unittest.main()
