import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.favorite_color import CitadelFavoriteColor, CustomFavoriteColor
from src.settings_handler import (
    APPLICATION_COLOR_FAVORITES_FIELD,
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
    def test_restore_authoritative_defaults_matches_clean_first_launch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            handler = SettingsHandler(settings_path, root)
            handler.last_diffuse_directory = root
            handler.last_pattern_import_directory = root
            handler.last_pattern_export_directory = root
            handler.color_picker_geometry = "900x700+20+30"
            handler.color_picker_group = "Favorites"
            handler.color_picker_color_space = "HSL"
            handler.color_picker_sort_mode = "Alphabetical"
            handler.color_picker_sashes = (200, 700)
            handler.color_picker_recent_colors = ((1, 2, 3),)
            handler.favorite_colors = (CitadelFavoriteColor("mephiston-red"),)
            handler.main_window_position = (20, 30)
            handler.favorite_save_dialog_position = (21, 31)
            handler.favorite_rename_dialog_position = (22, 32)
            handler.closest_citadel_dialog_position = (23, 33)
            handler.about_dialog_position = (24, 34)
            handler.batch_editor_position = (25, 35)
            handler.game_profile_id = "sm1"
            handler.load_error = ValueError("old invalid settings")

            handler.restore_authoritative_defaults()

            pristine = SettingsHandler(root / "never-created.json", root)
            self.assertEqual(handler.__dict__, {**pristine.__dict__, "path": settings_path})
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {"format": SETTINGS_FORMAT, "version": SETTINGS_VERSION},
            )

    def test_settings_without_favorites_loads_empty_collection(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(settings_document(root)), encoding="utf-8"
            )

            handler = SettingsHandler(settings_path, root)

            self.assertEqual(handler.favorite_colors, ())

    def test_citadel_and_custom_favorites_persist_through_restart(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            citadel = CitadelFavoriteColor("mephiston-red")
            custom = CustomFavoriteColor(
                "custom-1", "My Armor Blue", "#395C71"
            )
            handler = SettingsHandler(settings_path, root)

            handler.set_favorite_colors((citadel, custom))
            reloaded = SettingsHandler(settings_path, root)

            self.assertEqual(reloaded.favorite_colors, (citadel, custom))
            document = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(
                document[APPLICATION_COLOR_FAVORITES_FIELD],
                [
                    {"type": "citadel", "citadel_id": "mephiston-red"},
                    {
                        "type": "custom",
                        "id": "custom-1",
                        "name": "My Armor Blue",
                        "color": "#395C71",
                    },
                ],
            )
            self.assertEqual(
                APPLICATION_COLOR_FAVORITES_FIELD,
                "color_favorites",
            )

    def test_stale_citadel_and_malformed_custom_favorites_are_ignored(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            document = settings_document(root)
            document["color_favorites"] = [
                {"type": "citadel", "citadel_id": "missing-paint"},
                {"type": "custom", "id": "bad-color", "color": "#1234"},
                {"type": "custom", "id": "valid", "color": "#abcdef"},
                {"type": "custom", "id": "duplicate", "color": "ABCDEF"},
                {"type": "custom", "color": "#112233"},
                "bad",
            ]
            settings_path.write_text(json.dumps(document), encoding="utf-8")

            handler = SettingsHandler(settings_path, root)

            self.assertEqual(
                handler.favorite_colors,
                (CustomFavoriteColor("valid", "#ABCDEF", "#ABCDEF"),),
            )
            self.assertIsNone(handler.load_error)

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

    def test_color_picker_geometry_persists_with_existing_settings(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            handler = SettingsHandler(settings_path, root)
            handler.remember_diffuse_file(root / "unit_dif.png")

            handler.set_color_picker_geometry("1100x720+120+80")
            reloaded = SettingsHandler(settings_path, root)

            self.assertEqual(
                reloaded.color_picker_geometry,
                "1100x720+120+80",
            )
            self.assertEqual(reloaded.last_diffuse_directory, root.resolve())

    def test_color_picker_ui_state_persists_together(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            handler = SettingsHandler(settings_path, root)

            handler.set_color_picker_ui_state(
                "1100x720+120+80",
                "Browns",
                "HSV / HSB",
                "alphabetical",
                (140, 690),
            )
            reloaded = SettingsHandler(settings_path, root)

            self.assertEqual(reloaded.color_picker_group, "Browns")
            self.assertEqual(reloaded.color_picker_color_space, "HSV / HSB")
            self.assertEqual(reloaded.color_picker_sort_mode, "alphabetical")
            self.assertEqual(reloaded.color_picker_sashes, (140, 690))
            document = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(document["ui_color_picker_sort_mode"], "alphabetical")

    def test_main_window_position_persists_without_a_size(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            handler = SettingsHandler(settings_path, root)

            handler.set_main_window_position((-800, 120))
            reloaded = SettingsHandler(settings_path, root)

            self.assertEqual(reloaded.main_window_position, (-800, 120))
            document = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(document["ui_main_window_position"], [-800, 120])
            self.assertNotIn("ui_main_window_size", document)

    def test_secondary_window_positions_persist_independently(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            handler = SettingsHandler(settings_path, root)

            handler.set_favorite_save_dialog_position((100, 110))
            handler.set_favorite_rename_dialog_position((200, 210))
            handler.set_closest_citadel_dialog_position((300, 310))
            handler.set_about_dialog_position((-500, 320))
            handler.set_batch_editor_position((400, 410))
            reloaded = SettingsHandler(settings_path, root)

            self.assertEqual(reloaded.favorite_save_dialog_position, (100, 110))
            self.assertEqual(reloaded.favorite_rename_dialog_position, (200, 210))
            self.assertEqual(reloaded.closest_citadel_dialog_position, (300, 310))
            self.assertEqual(reloaded.about_dialog_position, (-500, 320))
            self.assertEqual(reloaded.batch_editor_position, (400, 410))

    def test_game_profile_defaults_to_dow2_and_persists_stable_sm1_id(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            handler = SettingsHandler(settings_path, root)

            self.assertEqual(handler.game_profile_id, "dow2")
            handler.set_game_profile_id("sm1")

            reloaded = SettingsHandler(settings_path, root)
            document = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(reloaded.game_profile_id, "sm1")
            self.assertEqual(document["game_profile_id"], "sm1")

    def test_unknown_persisted_game_profile_falls_back_to_dow2(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            document = settings_document(root)
            document["game_profile_id"] = "renamed-display-value"
            settings_path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertLogs("src.settings_handler", level="WARNING"):
                handler = SettingsHandler(settings_path, root)

            self.assertEqual(handler.game_profile_id, "dow2")
            self.assertIsNone(handler.load_error)

    def test_unknown_game_profile_cannot_be_persisted(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            handler = SettingsHandler(root / "settings.json", root)

            with self.assertRaisesRegex(ValueError, "Unknown game profile ID"):
                handler.set_game_profile_id("unknown")

    def test_confirmed_recent_colors_persist_as_ordered_rgb_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            handler = SettingsHandler(settings_path, root)

            handler.set_color_picker_recent_colors(
                ((150, 12, 9), (138, 31, 39))
            )
            reloaded = SettingsHandler(settings_path, root)

            self.assertEqual(
                reloaded.color_picker_recent_colors,
                ((150, 12, 9), (138, 31, 39)),
            )
            document = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(
                document["ui_color_picker_recent_colors"],
                [[150, 12, 9], [138, 31, 39]],
            )

    def test_recent_colors_load_ignores_bad_entries_and_preserves_valid_order(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            document = settings_document(root)
            document["ui_color_picker_recent_colors"] = [
                [138, 31, 39],
                [300, 0, 0],
                [150, 12, 9],
                [138, 31, 39],
                "bad",
            ]
            settings_path.write_text(json.dumps(document), encoding="utf-8")

            handler = SettingsHandler(settings_path, root)

            self.assertEqual(
                handler.color_picker_recent_colors,
                ((138, 31, 39), (150, 12, 9)),
            )
            self.assertIsNone(handler.load_error)

    def test_recent_color_setter_deduplicates_and_caps_before_persisting(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            handler = SettingsHandler(settings_path, root)
            colors = tuple((value, value, value) for value in range(15))

            handler.set_color_picker_recent_colors(colors + (colors[0],))
            reloaded = SettingsHandler(settings_path, root)

            self.assertEqual(reloaded.color_picker_recent_colors, colors[:12])

    def test_invalid_optional_ui_fields_fall_back_without_blocking_updates(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings_path = root / "settings.json"
            document = settings_document(root)
            document.update(
                {
                    "ui_color_picker_geometry": [1100, 720],
                    "ui_color_picker_group": 42,
                    "ui_color_picker_color_space": False,
                    "ui_color_picker_sort_mode": ["alphabetical"],
                    "ui_color_picker_sashes": [140, "bad"],
                    "ui_main_window_position": "offscreen",
                }
            )
            settings_path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertLogs("src.settings_handler", level="WARNING"):
                handler = SettingsHandler(settings_path, root)

            self.assertIsNone(handler.load_error)
            self.assertIsNone(handler.color_picker_geometry)
            self.assertIsNone(handler.color_picker_group)
            self.assertIsNone(handler.color_picker_color_space)
            self.assertIsNone(handler.color_picker_sort_mode)
            self.assertIsNone(handler.color_picker_sashes)
            self.assertIsNone(handler.main_window_position)

            handler.set_main_window_position((100, 80))
            reloaded = SettingsHandler(settings_path, root)
            self.assertEqual(reloaded.main_window_position, (100, 80))

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
