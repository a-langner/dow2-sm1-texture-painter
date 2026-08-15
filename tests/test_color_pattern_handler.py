import json
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
import src.color_pattern_handler as pattern_handler
from src.color_pattern_handler import (
    BuiltinPatternDeletionError,
    InvalidPatternError,
    InvalidUserPatternFileError,
    PatternAlreadyExistsError,
    PatternNameConflictError,
    PatternNotFoundError,
    UnsupportedUserPatternVersionError,
    UserPatternLoadIssue,
    USER_PATTERN_FORMAT,
    USER_PATTERN_VERSION,
    DEFAULT_PATTERN_PROCESSING,
    PatternProcessing,
    PatternProcessingState,
    color_key,
    get_all_patterns,
    load_builtin_patterns,
    load_user_patterns,
    load_user_patterns_for_startup,
    get_pattern_processing,
    get_pattern_processing_state,
)
from src.blend_mode import BlendMode
from src.color_processing_settings import ColorProcessingSettings
from src.processing_mode import ProcessingMode


def pattern(primary="#111111"):
    return OrderedDict(
        zip(color_key, [primary, "#222222", "#333333", "#444444"])
    )


def user_pattern_document(patterns, version=USER_PATTERN_VERSION):
    return OrderedDict(
        [
            ("format", USER_PATTERN_FORMAT),
            ("version", version),
            ("patterns", patterns),
        ]
    )


class ColorPatternLoadingTests(unittest.TestCase):
    def test_loads_builtin_patterns_from_packaged_resource(self):
        patterns = load_builtin_patterns()

        self.assertIsInstance(patterns, OrderedDict)
        self.assertIn("Blood Ravens", patterns)
        self.assertEqual(list(patterns["Blood Ravens"]), color_key)

    def test_missing_user_file_returns_empty_ordered_collection(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / "missing.json"

            patterns = load_user_patterns(missing_path)

        self.assertEqual(patterns, OrderedDict())

    def test_loads_valid_user_patterns_in_file_order(self):
        expected = OrderedDict(
            [("First", pattern()), ("Second", pattern("#aaaaaa"))]
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_path.write_text(
                json.dumps(user_pattern_document(expected)), encoding="utf-8"
            )

            patterns = load_user_patterns(pattern_path)

        self.assertEqual(patterns, expected)
        self.assertEqual(list(patterns), ["First", "Second"])

    def test_duplicate_builtin_and_user_names_are_rejected(self):
        builtins = OrderedDict([("Duplicate", pattern())])
        users = OrderedDict([("Duplicate", pattern("#aaaaaa"))])

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            get_all_patterns(builtins, users)

    def test_invalid_top_level_json_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(
                InvalidUserPatternFileError, "JSON object"
            ):
                load_user_patterns(pattern_path)

    def test_loads_legacy_unwrapped_file_without_rewriting_it(self):
        expected = OrderedDict([("Legacy", pattern())])
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_path.write_text(json.dumps(expected), encoding="utf-8")
            contents_before = pattern_path.read_bytes()

            patterns = load_user_patterns(pattern_path)

            self.assertEqual(patterns, expected)
            self.assertEqual(pattern_path.read_bytes(), contents_before)

    def test_rejects_unsupported_future_version_without_rewriting_file(self):
        document = user_pattern_document(OrderedDict(), version=2)
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_path.write_text(json.dumps(document), encoding="utf-8")
            contents_before = pattern_path.read_bytes()

            with self.assertRaisesRegex(
                UnsupportedUserPatternVersionError, "version 2"
            ):
                load_user_patterns(pattern_path)

            self.assertEqual(pattern_path.read_bytes(), contents_before)

    def test_rejects_invalid_format_and_patterns_object(self):
        invalid_documents = [
            {"format": "wrong", "version": 1, "patterns": {}},
            {
                "format": USER_PATTERN_FORMAT,
                "version": 1,
                "patterns": [],
            },
            {
                "format": USER_PATTERN_FORMAT,
                "version": "1",
                "patterns": {},
            },
        ]

        for document in invalid_documents:
            with self.subTest(document=document):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    pattern_path = (
                        Path(temporary_directory) / "user_patterns.json"
                    )
                    pattern_path.write_text(
                        json.dumps(document), encoding="utf-8"
                    )
                    contents_before = pattern_path.read_bytes()
                    with self.assertRaises(InvalidUserPatternFileError):
                        load_user_patterns(pattern_path)
                    self.assertEqual(
                        pattern_path.read_bytes(), contents_before
                    )

    def test_startup_survives_malformed_json_without_changing_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_path.write_text('{"broken":', encoding="utf-8")
            contents_before = pattern_path.read_bytes()

            with self.assertLogs("src.color_pattern_handler", level="ERROR"):
                patterns, issue = load_user_patterns_for_startup(pattern_path)

            self.assertEqual(patterns, OrderedDict())
            self.assertIsInstance(issue, UserPatternLoadIssue)
            self.assertIsInstance(issue.error, InvalidUserPatternFileError)
            self.assertEqual(pattern_path.read_bytes(), contents_before)

    def test_startup_survives_unsupported_version(self):
        document = user_pattern_document(OrderedDict(), version=2)
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertLogs("src.color_pattern_handler", level="ERROR"):
                patterns, issue = load_user_patterns_for_startup(pattern_path)

            self.assertEqual(patterns, OrderedDict())
            self.assertIsInstance(
                issue.error, UnsupportedUserPatternVersionError
            )

    def test_startup_survives_permission_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_path.write_text("{}", encoding="utf-8")

            with patch.object(
                Path, "open", side_effect=PermissionError("access denied")
            ), self.assertLogs("src.color_pattern_handler", level="ERROR"):
                patterns, issue = load_user_patterns_for_startup(pattern_path)

            self.assertEqual(patterns, OrderedDict())
            self.assertIsInstance(issue.error, PermissionError)
            self.assertEqual(issue.path, pattern_path.resolve())


class ColorPatternSavingTests(unittest.TestCase):
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

    def colors(self):
        return list(pattern().values())

    def test_first_save_creates_directory_and_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = (
                Path(temporary_directory)
                / "new-directory"
                / "user_patterns.json"
            )
            with patch.object(
                pattern_handler,
                "get_user_patterns_path",
                return_value=pattern_path,
            ) as mocked_path:
                pattern_handler.save("  New Pattern  ", self.colors())

            mocked_path.assert_called_once_with(create_parent=True)
            self.assertTrue(pattern_path.is_file())
            saved = json.loads(pattern_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["format"], USER_PATTERN_FORMAT)
            self.assertEqual(saved["version"], USER_PATTERN_VERSION)
            self.assertEqual(list(saved["patterns"]), ["New Pattern"])
            self.assertIn("New Pattern", pattern_handler.user_color_patterns)

    def test_saved_pattern_can_be_loaded_from_disk(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            pattern_handler.save("Persistent", self.colors(), pattern_path)
            reloaded = load_user_patterns(pattern_path)

        self.assertEqual(reloaded["Persistent"], pattern())

    def test_next_save_migrates_legacy_file_to_versioned_format(self):
        legacy = OrderedDict([("Legacy", pattern())])
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_path.write_text(json.dumps(legacy), encoding="utf-8")
            pattern_handler.user_color_patterns.update(
                load_user_patterns(pattern_path)
            )
            pattern_handler.army_color_pattern.update(legacy)

            pattern_handler.save("New", self.colors(), pattern_path)
            saved = json.loads(pattern_path.read_text(encoding="utf-8"))

        self.assertEqual(saved["format"], USER_PATTERN_FORMAT)
        self.assertEqual(saved["version"], USER_PATTERN_VERSION)
        self.assertEqual(list(saved["patterns"]), ["Legacy", "New"])

    def test_duplicate_user_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Duplicate", self.colors(), pattern_path)

            with self.assertRaisesRegex(
                PatternAlreadyExistsError, "already exists"
            ):
                pattern_handler.save(
                    " Duplicate ", self.colors(), pattern_path
                )

    def test_builtin_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            with self.assertRaisesRegex(PatternNameConflictError, "built-in"):
                pattern_handler.save(
                    "Blood Ravens", self.colors(), pattern_path
                )

            self.assertFalse(pattern_path.exists())

    def test_invalid_names_color_counts_and_color_values_are_rejected(self):
        invalid_cases = [
            (None, self.colors()),
            ("", self.colors()),
            ("   ", self.colors()),
            ("Too few", self.colors()[:3]),
            ("Too many", self.colors() + ["#555555"]),
            ("Bad color", ["red"] + self.colors()[1:]),
        ]

        for name, colors in invalid_cases:
            with self.subTest(name=name, colors=colors):
                with self.assertRaises(InvalidPatternError):
                    pattern_handler.save(name, colors, Path("unused.json"))

    def test_write_failure_does_not_change_memory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            users_before = OrderedDict(pattern_handler.user_color_patterns)
            all_before = OrderedDict(pattern_handler.army_color_pattern)

            with patch(
                "src.color_pattern_handler.os.replace",
                side_effect=OSError("simulated failure"),
            ):
                with self.assertRaisesRegex(OSError, "simulated failure"):
                    pattern_handler.save(
                        "Not Saved", self.colors(), pattern_path
                    )

            self.assertEqual(pattern_handler.user_color_patterns, users_before)
            self.assertEqual(pattern_handler.army_color_pattern, all_before)
            self.assertFalse(pattern_path.exists())
            self.assertEqual(list(pattern_path.parent.glob("*.tmp")), [])

    def test_write_failure_preserves_previous_valid_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Existing", self.colors(), pattern_path)
            contents_before = pattern_path.read_bytes()

            with patch(
                "src.color_pattern_handler.os.replace",
                side_effect=OSError("simulated failure"),
            ):
                with self.assertRaisesRegex(OSError, "simulated failure"):
                    pattern_handler.save(
                        "Not Saved", self.colors(), pattern_path
                    )

            self.assertEqual(pattern_path.read_bytes(), contents_before)
            self.assertIn("Existing", pattern_handler.user_color_patterns)
            self.assertNotIn("Not Saved", pattern_handler.user_color_patterns)

    def test_startup_load_issue_blocks_overwriting_affected_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_path.write_text('{"broken":', encoding="utf-8")
            contents_before = pattern_path.read_bytes()
            issue = UserPatternLoadIssue(
                pattern_path.resolve(),
                InvalidUserPatternFileError("invalid JSON"),
            )

            with patch.object(
                pattern_handler, "user_pattern_load_issue", issue
            ):
                with self.assertRaisesRegex(
                    pattern_handler.UserPatternFileError,
                    "cannot be safely updated",
                ):
                    pattern_handler.save(
                        "Blocked", self.colors(), pattern_path
                    )

            self.assertEqual(pattern_path.read_bytes(), contents_before)
            self.assertNotIn("Blocked", pattern_handler.user_color_patterns)

    def test_saving_does_not_modify_packaged_patterns(self):
        packaged_before = pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes()

        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("External", self.colors(), pattern_path)

        self.assertEqual(
            pattern_handler.ARMY_PATTERN_RESOURCE.read_bytes(),
            packaged_before,
        )

    def test_all_blend_modes_and_global_levels_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            for index, mode in enumerate(BlendMode):
                processing = PatternProcessing(mode, 25.0 + index, 125.0 + index)
                name = f"Mode {index}"
                pattern_handler.save(
                    name,
                    self.colors(),
                    pattern_path,
                    processing=processing,
                )

            reloaded = load_user_patterns(pattern_path)
            with patch.object(pattern_handler, "user_color_patterns", reloaded), patch.object(
                pattern_handler,
                "army_color_pattern",
                OrderedDict(
                    (*pattern_handler.builtin_color_patterns.items(), *reloaded.items())
                ),
            ):
                for index, mode in enumerate(BlendMode):
                    self.assertEqual(
                        get_pattern_processing(f"Mode {index}"),
                        PatternProcessing(mode, 25.0 + index, 125.0 + index),
                    )

    def test_legacy_and_invalid_processing_use_safe_defaults(self):
        legacy = pattern()
        invalid = pattern("#aaaaaa")
        invalid.update(
            (("blend_mode", "Difference"), ("brightness", 75), ("contrast", 100))
        )
        patterns = OrderedDict((("Legacy", legacy), ("Invalid", invalid)))
        with patch.object(pattern_handler, "builtin_color_patterns", OrderedDict()), patch.object(
            pattern_handler, "user_color_patterns", patterns
        ):
            self.assertEqual(get_pattern_processing("Legacy"), DEFAULT_PATTERN_PROCESSING)
            with self.assertLogs(pattern_handler.LOGGER, level="WARNING"):
                self.assertEqual(
                    get_pattern_processing("Invalid"), DEFAULT_PATTERN_PROCESSING
                )

    def test_per_color_processing_state_round_trips_with_stable_ids(self):
        global_settings = ColorProcessingSettings(BlendMode.SCREEN, 80.0, 110.0)
        per_color = (
            ColorProcessingSettings(BlendMode.OVERLAY, 10.0, 20.0),
            ColorProcessingSettings(BlendMode.MULTIPLY, 30.0, 40.0),
            ColorProcessingSettings(BlendMode.HARD_LIGHT, 50.0, 60.0),
            ColorProcessingSettings(BlendMode.LINEAR_DODGE, 70.0, 80.0),
        )
        state = PatternProcessingState(
            ProcessingMode.PER_COLOR, global_settings, per_color
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save(
                "Per Color",
                self.colors(),
                pattern_path,
                processing=state,
            )
            document = json.loads(pattern_path.read_text(encoding="utf-8"))
            stored = document["patterns"]["Per Color"]
            self.assertEqual(stored["processing_mode"], "per_color")
            self.assertEqual(
                list(stored["per_color_processing"]),
                ["color_1", "color_2", "color_3", "color_4"],
            )
            self.assertNotIn("tem_selected", stored)

            reloaded = load_user_patterns(pattern_path)
            with patch.object(
                pattern_handler, "user_color_patterns", reloaded
            ), patch.object(
                pattern_handler, "builtin_color_patterns", OrderedDict()
            ):
                self.assertEqual(get_pattern_processing_state("Per Color"), state)

    def test_legacy_global_processing_seeds_all_per_color_slots(self):
        legacy = pattern()
        legacy.update(
            (("blend_mode", "screen"), ("brightness", 45), ("contrast", 125))
        )
        with patch.object(
            pattern_handler, "builtin_color_patterns", OrderedDict()
        ), patch.object(
            pattern_handler,
            "user_color_patterns",
            OrderedDict((("Legacy", legacy),)),
        ):
            state = get_pattern_processing_state("Legacy")

        expected = ColorProcessingSettings(BlendMode.SCREEN, 45.0, 125.0)
        self.assertIs(state.processing_mode, ProcessingMode.GLOBAL)
        self.assertEqual(state.global_processing, expected)
        self.assertEqual(state.per_color_processing, (expected,) * 4)


class ColorPatternDeletionTests(unittest.TestCase):
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

    def colors(self):
        return list(pattern().values())

    def test_deletes_user_pattern_and_keeps_other_patterns(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Delete Me", self.colors(), pattern_path)
            pattern_handler.save("Keep Me", self.colors(), pattern_path)

            pattern_handler.delete(" Delete Me ", pattern_path)

            saved = load_user_patterns(pattern_path)
            self.assertEqual(list(saved), ["Keep Me"])
            self.assertNotIn("Delete Me", pattern_handler.user_color_patterns)
            self.assertNotIn("Delete Me", pattern_handler.army_color_pattern)

    def test_builtin_pattern_cannot_be_deleted(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"

            with self.assertRaisesRegex(
                BuiltinPatternDeletionError, "cannot be deleted"
            ):
                pattern_handler.delete("Blood Ravens", pattern_path)

            self.assertFalse(pattern_path.exists())
            self.assertIn("Blood Ravens", pattern_handler.army_color_pattern)

    def test_unknown_pattern_does_not_change_user_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Known", self.colors(), pattern_path)
            contents_before = pattern_path.read_bytes()

            with self.assertRaisesRegex(PatternNotFoundError, "not found"):
                pattern_handler.delete("Unknown", pattern_path)

            self.assertEqual(pattern_path.read_bytes(), contents_before)
            self.assertIn("Known", pattern_handler.user_color_patterns)

    def test_deleting_last_user_pattern_writes_empty_json_object(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Last", self.colors(), pattern_path)

            pattern_handler.delete("Last", pattern_path)

            self.assertTrue(pattern_path.is_file())
            self.assertEqual(
                json.loads(pattern_path.read_text(encoding="utf-8"))[
                    "patterns"
                ],
                {},
            )
            self.assertEqual(pattern_handler.user_color_patterns, {})

    def test_deletion_persists_when_patterns_are_reloaded(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Removed", self.colors(), pattern_path)
            pattern_handler.save("Remaining", self.colors(), pattern_path)

            pattern_handler.delete("Removed", pattern_path)
            reloaded = load_user_patterns(pattern_path)

            self.assertEqual(list(reloaded), ["Remaining"])

    def test_delete_write_failure_does_not_change_memory_or_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            pattern_path = Path(temporary_directory) / "user_patterns.json"
            pattern_handler.save("Still Here", self.colors(), pattern_path)
            contents_before = pattern_path.read_bytes()
            users_before = OrderedDict(pattern_handler.user_color_patterns)
            all_before = OrderedDict(pattern_handler.army_color_pattern)

            with patch(
                "src.color_pattern_handler.os.replace",
                side_effect=OSError("simulated failure"),
            ):
                with self.assertRaisesRegex(OSError, "simulated failure"):
                    pattern_handler.delete("Still Here", pattern_path)

            self.assertEqual(pattern_path.read_bytes(), contents_before)
            self.assertEqual(pattern_handler.user_color_patterns, users_before)
            self.assertEqual(pattern_handler.army_color_pattern, all_before)


if __name__ == "__main__":
    unittest.main()
