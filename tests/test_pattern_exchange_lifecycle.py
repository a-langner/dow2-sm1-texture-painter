import json
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
import src.color_pattern_handler as pattern_handler
from src.blend_mode import BlendMode
from src.color_processing_settings import ColorProcessingSettings
from src.processing_mode import ProcessingMode
from src.pattern_exchange import (
    PATTERN_EXCHANGE_FORMAT,
    PATTERN_EXCHANGE_VERSION,
    BuiltinPatternImportConflictError,
    ImportedPattern,
    InvalidImportedPatternColorsError,
    InvalidPatternFileError,
    InvalidPatternJsonError,
    PatternExportError,
    UnsupportedPatternVersionError,
    UserPatternImportConflictError,
    export_pattern,
    import_pattern,
    read_pattern_file,
)
from src.settings_handler import SETTINGS_FORMAT, SettingsHandler


def exchange_colors(primary="#112233"):
    return OrderedDict(
        zip(
            pattern_handler.color_key,
            (primary, "#445566", "#778899", "#aabbcc"),
        )
    )


class PatternExchangeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.original_users = OrderedDict(pattern_handler.user_color_patterns)
        self.original_all = OrderedDict(pattern_handler.army_color_pattern)
        pattern_handler.user_color_patterns.clear()
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(
            pattern_handler.builtin_color_patterns
        )

    def tearDown(self):
        pattern_handler.user_color_patterns.clear()
        pattern_handler.user_color_patterns.update(self.original_users)
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(self.original_all)

    def assert_exchange_document(self, path, expected_name, expected_colors):
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["format"], PATTERN_EXCHANGE_FORMAT)
        self.assertEqual(document["version"], PATTERN_EXCHANGE_VERSION)
        self.assertEqual(document["name"], expected_name)
        self.assertEqual(list(document["colors"]), pattern_handler.color_key)
        self.assertEqual(document["colors"], expected_colors)
        return document

    def test_complete_builtin_and_user_export_import_round_trip(self):
        builtin_before = pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes()
        builtin_name, builtin_colors = next(
            iter(pattern_handler.builtin_color_patterns.items())
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            user_path = root / "data" / "user_patterns.json"
            builtin_export = root / "exports" / "builtin.pattern.json"
            user_export = root / "exports" / "user.pattern.json"
            builtin_export.parent.mkdir()

            user_name = "User Pattern"
            user_colors = exchange_colors("#abcdef")
            processing = pattern_handler.PatternProcessingState(
                ProcessingMode.PER_COLOR,
                ColorProcessingSettings(BlendMode.SCREEN, 80, 110, 90, 135),
                (
                    ColorProcessingSettings(saturation=25),
                    ColorProcessingSettings(saturation=75),
                    ColorProcessingSettings(saturation=150),
                    ColorProcessingSettings(saturation=200),
                ),
            )
            import_pattern(
                ImportedPattern(user_name, user_colors, processing),
                pattern_path=user_path,
            )

            export_pattern(builtin_name, builtin_export)
            export_pattern(user_name, user_export)
            self.assert_exchange_document(builtin_export, builtin_name, builtin_colors)
            self.assert_exchange_document(user_export, user_name, user_colors)

            imported_builtin = read_pattern_file(builtin_export)
            imported_user = read_pattern_file(user_export)
            self.assertEqual(imported_user.processing, processing)
            import_pattern(
                imported_builtin,
                target_name="Imported Built-in",
                pattern_path=user_path,
            )
            import_pattern(
                imported_user,
                target_name="Imported User",
                pattern_path=user_path,
            )

            reloaded = pattern_handler.load_user_patterns(user_path)
            self.assertEqual(
                [reloaded["Imported Built-in"][key] for key in pattern_handler.color_key],
                list(builtin_colors.values()),
            )
            self.assertEqual(
                [reloaded["Imported User"][key] for key in pattern_handler.color_key],
                list(user_colors.values()),
            )
            self.assertEqual(
                pattern_handler.parse_pattern_processing_state(
                    reloaded["Imported User"]
                ),
                processing,
            )
            # Rebuild the module-backed handler state as application startup does.
            pattern_handler.user_color_patterns.clear()
            pattern_handler.user_color_patterns.update(reloaded)
            pattern_handler.army_color_pattern.clear()
            pattern_handler.army_color_pattern.update(
                pattern_handler.get_all_patterns(
                    pattern_handler.builtin_color_patterns,
                    pattern_handler.user_color_patterns,
                )
            )
            self.assertTrue(pattern_handler.is_user_pattern("Imported Built-in"))
            self.assertTrue(pattern_handler.is_user_pattern("Imported User"))

        self.assertEqual(
            pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes(), builtin_before
        )

    def test_unicode_and_unknown_optional_fields_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            user_path = root / "user_patterns.json"
            source = root / "unicode.pattern.json"
            unicode_name = "Élite Löwen_日本"
            colors = exchange_colors()
            import_pattern(
                ImportedPattern(unicode_name, colors), pattern_path=user_path
            )
            export_pattern(unicode_name, source)

            document = json.loads(source.read_text(encoding="utf-8"))
            document["description"] = "ignored optional field"
            document["colors"]["future_colour"] = "ignored"
            source.write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )

            imported = read_pattern_file(source)
            self.assertEqual(imported.name, unicode_name)
            self.assertEqual(imported.colors, colors)
            result = import_pattern(
                imported,
                target_name="Élite Löwen_日本 Copy",
                pattern_path=user_path,
            )
            self.assertEqual(result, "Élite Löwen_日本 Copy")
            reloaded = pattern_handler.load_user_patterns(user_path)[result]
            self.assertEqual(
                [reloaded[key] for key in pattern_handler.color_key],
                list(colors.values()),
            )

    def test_invalid_exchange_files_are_rejected_without_being_modified(self):
        valid = {
            "format": PATTERN_EXCHANGE_FORMAT,
            "version": PATTERN_EXCHANGE_VERSION,
            "name": "Example",
            "colors": exchange_colors(),
        }
        cases = (
            (b"{broken", InvalidPatternJsonError),
            (json.dumps({"unrelated": True}).encode(), InvalidPatternFileError),
            (
                json.dumps({**valid, "version": 2}).encode(),
                UnsupportedPatternVersionError,
            ),
            (
                json.dumps(
                    {
                        **valid,
                        "colors": {
                            key: value
                            for key, value in valid["colors"].items()
                            if key != "extra_colour_name"
                        },
                    }
                ).encode(),
                InvalidImportedPatternColorsError,
            ),
            (
                json.dumps(
                    {
                        **valid,
                        "colors": {**valid["colors"], "extra_colour_name": "bad"},
                    }
                ).encode(),
                InvalidImportedPatternColorsError,
            ),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for index, (contents, error_type) in enumerate(cases):
                with self.subTest(error_type=error_type.__name__):
                    source = root / f"invalid-{index}.json"
                    source.write_bytes(contents)
                    with self.assertRaises(error_type):
                        read_pattern_file(source)
                    self.assertEqual(source.read_bytes(), contents)

    def test_conflicts_overwrite_and_rename_follow_explicit_policy(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            with self.assertRaises(BuiltinPatternImportConflictError):
                import_pattern(
                    ImportedPattern(builtin_name, exchange_colors()),
                    overwrite=True,
                    pattern_path=user_path,
                )

            original = exchange_colors()
            replacement = exchange_colors("#abcdef")
            import_pattern(
                ImportedPattern("Existing", original), pattern_path=user_path
            )
            with self.assertRaises(UserPatternImportConflictError):
                import_pattern(
                    ImportedPattern("Existing", replacement),
                    pattern_path=user_path,
                )
            self.assertEqual(
                pattern_handler.load_user_patterns(user_path)["Existing"], original
            )

            import_pattern(
                ImportedPattern("Existing", replacement),
                overwrite=True,
                pattern_path=user_path,
            )
            renamed = import_pattern(
                ImportedPattern("Imported Name", original),
                target_name="  Renamed Pattern  ",
                pattern_path=user_path,
            )
            reloaded = pattern_handler.load_user_patterns(user_path)
            self.assertEqual(reloaded["Existing"], replacement)
            self.assertEqual(renamed, "Renamed Pattern")
            self.assertEqual(reloaded[renamed], original)

    def test_atomic_failures_preserve_export_and_user_pattern_files(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            destination = root / "existing.pattern.json"
            destination_before = b'{"existing": true}\n'
            destination.write_bytes(destination_before)
            with patch("src.pattern_exchange.os.replace", side_effect=OSError("disk")):
                with self.assertRaises(PatternExportError):
                    export_pattern(builtin_name, destination)
            self.assertEqual(destination.read_bytes(), destination_before)

            user_path = root / "user_patterns.json"
            import_pattern(
                ImportedPattern("Existing", exchange_colors()),
                pattern_path=user_path,
            )
            user_before = user_path.read_bytes()
            memory_before = OrderedDict(pattern_handler.user_color_patterns)
            with patch(
                "src.color_pattern_handler.os.replace",
                side_effect=OSError("disk"),
            ):
                with self.assertRaises(OSError):
                    import_pattern(
                        ImportedPattern("Existing", exchange_colors("#abcdef")),
                        overwrite=True,
                        pattern_path=user_path,
                    )
            self.assertEqual(user_path.read_bytes(), user_before)
            self.assertEqual(pattern_handler.user_color_patterns, memory_before)

    def test_version_one_settings_without_pattern_directories_remain_compatible(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "format": SETTINGS_FORMAT,
                        "version": 1,
                        "last_diffuse_directory": str(root),
                    }
                ),
                encoding="utf-8",
            )

            handler = SettingsHandler(settings_path, home_directory=root)

            self.assertEqual(handler.get_last_pattern_import_directory(), root)
            self.assertEqual(handler.get_last_pattern_export_directory(), root)


if __name__ == "__main__":
    unittest.main()
