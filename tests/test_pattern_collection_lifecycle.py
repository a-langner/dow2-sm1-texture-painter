import json
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import test_support
import src.color_pattern_handler as pattern_handler
from src.blend_mode import BlendMode
from src.color_processing_settings import ColorProcessingSettings
from src.processing_mode import ProcessingMode
from src.pattern_exchange import (
    PATTERN_COLLECTION_EXCHANGE_FORMAT,
    PATTERN_COLLECTION_EXCHANGE_VERSION,
    PATTERN_EXCHANGE_FORMAT,
    PATTERN_EXCHANGE_VERSION,
    CollectionImportResult,
    DuplicatePatternNameInCollectionError,
    InvalidPatternCollectionError,
    InvalidPatternCollectionFormatError,
    InvalidPatternJsonError,
    PatternExportError,
    UnsupportedPatternCollectionVersionError,
    analyze_pattern_collection_import,
    export_user_pattern_collection,
    import_analyzed_pattern_collection,
    read_pattern_collection_file,
    validate_imported_pattern_collection,
)
from src.settings_handler import SETTINGS_FORMAT, SettingsHandler


def colors(primary="#112233"):
    return OrderedDict(
        zip(
            pattern_handler.color_key,
            (primary, "#445566", "#778899", "#aabbcc"),
        )
    )


def collection_document(name, entries, **optional_fields):
    return {
        "format": PATTERN_COLLECTION_EXCHANGE_FORMAT,
        "version": PATTERN_COLLECTION_EXCHANGE_VERSION,
        "name": name,
        "patterns": [
            {"name": pattern_name, "colors": pattern_colors}
            for pattern_name, pattern_colors in entries
        ],
        **optional_fields,
    }


class PatternCollectionLifecycleTests(unittest.TestCase):
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

    def seed_user(
        self,
        name,
        pattern_colors,
        path,
        processing=None,
        marker_color=pattern_handler.PatternMarkerColor.DEFAULT,
    ):
        pattern_handler.save_imported_pattern(
            name,
            list(pattern_colors.values()),
            pattern_path=path,
            processing=processing,
            marker_color=marker_color,
        )

    def rebuild_handler_state(self, users):
        pattern_handler.user_color_patterns.clear()
        pattern_handler.user_color_patterns.update(users)
        pattern_handler.army_color_pattern.clear()
        pattern_handler.army_color_pattern.update(
            pattern_handler.get_all_patterns(
                pattern_handler.builtin_color_patterns, users
            )
        )

    def test_export_import_reload_complete_collection_lifecycle(self):
        builtin_before = pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes()
        self.assertFalse(test_support.TEST_USER_DATA_DIRECTORY.exists())
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_user_path = root / "source" / "user_patterns.json"
            imported_user_path = root / "imported" / "user_patterns.json"
            destination = root / "Éxports" / "Löwen.pattern-collection.json"
            destination.parent.mkdir()
            expected = [
                ("Zulu", colors("#123456")),
                ("Élite 日本語", colors("#abcdef")),
            ]
            saturation_state = pattern_handler.PatternProcessingState(
                ProcessingMode.PER_COLOR,
                ColorProcessingSettings(
                    blend_mode=BlendMode.COLOR_BURN,
                    saturation=140,
                ),
                tuple(
                    ColorProcessingSettings(blend_mode=mode, saturation=value)
                    for mode, value in zip(
                        (
                            BlendMode.DARKEN,
                            BlendMode.LIGHTEN,
                            BlendMode.COLOR_BURN,
                            BlendMode.OVERLAY,
                        ),
                        (20, 80, 150, 200),
                    )
                ),
            )
            self.seed_user(
                expected[0][0],
                expected[0][1],
                source_user_path,
                saturation_state,
                pattern_handler.PatternMarkerColor.GREEN,
            )
            self.seed_user(expected[1][0], expected[1][1], source_user_path)

            with patch(
                "src.pattern_exchange.get_user_patterns_path",
                return_value=source_user_path,
            ):
                export_user_pattern_collection("Löwen 日本語", destination)

            document = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(document["format"], PATTERN_COLLECTION_EXCHANGE_FORMAT)
            self.assertEqual(document["version"], 1)
            self.assertEqual(document["name"], "Löwen 日本語")
            self.assertEqual(
                [entry["name"] for entry in document["patterns"]],
                [name for name, _ in expected],
            )
            for entry, (expected_name, expected_colors) in zip(
                document["patterns"], expected
            ):
                self.assertEqual(entry["name"], expected_name)
                self.assertEqual(list(entry["colors"]), pattern_handler.color_key)
                self.assertEqual(entry["colors"], expected_colors)
            self.assertTrue(
                set(pattern_handler.builtin_color_patterns).isdisjoint(
                    entry["name"] for entry in document["patterns"]
                )
            )

            document["description"] = "ignored future field"
            document["patterns"][0]["description"] = "also ignored"
            destination.write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
            imported = read_pattern_collection_file(destination)
            self.rebuild_handler_state(OrderedDict())
            analysis = analyze_pattern_collection_import(imported)
            result = import_analyzed_pattern_collection(
                analysis, pattern_path=imported_user_path
            )

            self.assertEqual(result, CollectionImportResult(2, 0, 0, 0))
            reloaded = pattern_handler.load_user_patterns(imported_user_path)
            self.rebuild_handler_state(reloaded)
            self.assertEqual(list(reloaded), [name for name, _ in expected])
            for name, expected_colors in expected:
                self.assertEqual(
                    [reloaded[name][key] for key in pattern_handler.color_key],
                    list(expected_colors.values()),
                )
                self.assertTrue(pattern_handler.is_user_pattern(name))
            self.assertEqual(
                pattern_handler.parse_pattern_processing_state(reloaded["Zulu"]),
                saturation_state,
            )
            self.assertEqual(document["patterns"][0]["marker_color"], "green")
            self.assertIs(
                pattern_handler.get_pattern_marker_color("Zulu"),
                pattern_handler.PatternMarkerColor.GREEN,
            )

        self.assertEqual(
            pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes(), builtin_before
        )
        self.assertFalse(test_support.TEST_USER_DATA_DIRECTORY.exists())

    def test_skip_overwrite_builtin_and_no_change_policies(self):
        builtin_name = next(iter(pattern_handler.builtin_color_patterns))
        builtin_before = pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes()
        with tempfile.TemporaryDirectory() as temporary_directory:
            user_path = Path(temporary_directory) / "user_patterns.json"
            self.seed_user("Existing", colors("#111111"), user_path)
            imported = validate_imported_pattern_collection(
                collection_document(
                    "Conflicts",
                    [
                        ("New", colors("#222222")),
                        ("Existing", colors("#333333")),
                        (builtin_name, colors("#444444")),
                    ],
                )
            )

            skip_analysis = analyze_pattern_collection_import(imported)
            skip_result = import_analyzed_pattern_collection(
                skip_analysis,
                overwrite_user_conflicts=False,
                pattern_path=user_path,
            )
            self.assertEqual(skip_result, CollectionImportResult(1, 0, 1, 1))
            self.assertEqual(
                pattern_handler.user_color_patterns["Existing"], colors("#111111")
            )

            overwrite_analysis = analyze_pattern_collection_import(imported)
            overwrite_result = import_analyzed_pattern_collection(
                overwrite_analysis,
                overwrite_user_conflicts=True,
                pattern_path=user_path,
            )
            self.assertEqual(overwrite_result, CollectionImportResult(0, 2, 0, 1))
            self.assertEqual(
                [
                    pattern_handler.user_color_patterns["Existing"][key]
                    for key in pattern_handler.color_key
                ],
                list(colors("#333333").values()),
            )
            self.assertNotIn(builtin_name, pattern_handler.user_color_patterns)

            no_change_analysis = analyze_pattern_collection_import(imported)
            file_before = user_path.read_bytes()
            with patch("src.pattern_exchange.replace_user_patterns") as persist:
                no_change_result = import_analyzed_pattern_collection(
                    no_change_analysis,
                    overwrite_user_conflicts=False,
                    pattern_path=user_path,
                )
            self.assertEqual(no_change_result, CollectionImportResult(0, 0, 2, 1))
            persist.assert_not_called()
            self.assertEqual(user_path.read_bytes(), file_before)

        self.assertEqual(
            pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes(), builtin_before
        )

    def test_invalid_collection_files_are_rejected_without_user_changes(self):
        valid_entry = {"name": "Valid", "colors": colors()}
        invalid_colors = colors()
        invalid_colors["extra_colour_name"] = "invalid"
        single_pattern = {
            "format": PATTERN_EXCHANGE_FORMAT,
            "version": PATTERN_EXCHANGE_VERSION,
            "name": "Single",
            "colors": colors(),
        }
        cases = (
            ("{broken", InvalidPatternJsonError),
            (json.dumps(single_pattern), InvalidPatternCollectionFormatError),
            (
                json.dumps(
                    {
                        **collection_document("Future", [("Valid", colors())]),
                        "version": 2,
                    }
                ),
                UnsupportedPatternCollectionVersionError,
            ),
            (
                json.dumps(collection_document("Empty", [])),
                InvalidPatternCollectionError,
            ),
            (
                json.dumps(
                    collection_document(
                        "Invalid Middle",
                        [
                            ("Before", colors()),
                            ("Broken", invalid_colors),
                            ("After", colors()),
                        ],
                    )
                ),
                InvalidPatternCollectionError,
            ),
            (
                json.dumps(
                    {
                        **collection_document("Duplicate", []),
                        "patterns": [valid_entry, valid_entry],
                    }
                ),
                DuplicatePatternNameInCollectionError,
            ),
            (
                json.dumps(
                    collection_document(
                        "Whitespace Duplicate",
                        [("Same", colors()), ("  Same  ", colors())],
                    )
                ),
                DuplicatePatternNameInCollectionError,
            ),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            user_path = root / "user_patterns.json"
            self.seed_user("Existing", colors("#101010"), user_path)
            file_before = user_path.read_bytes()
            users_before = OrderedDict(pattern_handler.user_color_patterns)
            for index, (text, error_type) in enumerate(cases):
                with self.subTest(error=error_type.__name__, index=index):
                    source = root / f"invalid-{index}.json"
                    source.write_text(text, encoding="utf-8")
                    with self.assertRaises(error_type):
                        read_pattern_collection_file(source)
                    self.assertEqual(user_path.read_bytes(), file_before)
                    self.assertEqual(pattern_handler.user_color_patterns, users_before)

    def test_atomic_import_and_export_failures_preserve_previous_state(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            user_path = root / "user_patterns.json"
            destination = root / "existing.pattern-collection.json"
            self.seed_user("Existing", colors("#111111"), user_path)
            analysis = analyze_pattern_collection_import(
                validate_imported_pattern_collection(
                    collection_document(
                        "Failure",
                        [
                            ("Existing", colors("#222222")),
                            ("New", colors("#333333")),
                        ],
                    )
                )
            )
            user_before = user_path.read_bytes()
            memory_before = OrderedDict(
                (name, OrderedDict(pattern))
                for name, pattern in pattern_handler.user_color_patterns.items()
            )
            with patch(
                "src.color_pattern_handler.os.replace", side_effect=OSError("disk")
            ):
                with self.assertRaises(OSError):
                    import_analyzed_pattern_collection(
                        analysis,
                        overwrite_user_conflicts=True,
                        pattern_path=user_path,
                    )
            self.assertEqual(user_path.read_bytes(), user_before)
            self.assertEqual(pattern_handler.user_color_patterns, memory_before)

            destination_before = b'{"previous": true}\n'
            destination.write_bytes(destination_before)
            with patch(
                "src.pattern_exchange.get_user_patterns_path",
                return_value=user_path,
            ), patch("src.pattern_exchange.os.replace", side_effect=OSError("disk")):
                with self.assertRaises(PatternExportError):
                    export_user_pattern_collection("Failure", destination)
            self.assertEqual(destination.read_bytes(), destination_before)

    def test_version_one_settings_and_shared_directories_remain_compatible(self):
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

            settings = SettingsHandler(settings_path, home_directory=root)

            self.assertEqual(settings.get_last_pattern_import_directory(), root)
            self.assertEqual(settings.get_last_pattern_export_directory(), root)
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8"))["version"], 1
            )


if __name__ == "__main__":
    unittest.main()
