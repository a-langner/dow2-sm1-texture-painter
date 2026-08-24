import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Literal, Mapping

from src.favorite_color import (
    FavoriteColor,
    serialize_favorite_colors,
    validate_favorite_colors,
)
from src.paint_catalog import load_citadel_catalog
from src.recent_colors import RecentColors, validate_recent_colors
from src.texture_naming import DEFAULT_TEXTURE_NAMING, texture_naming_profile_for_id
from src.user_data import get_settings_path

SETTINGS_FORMAT = "dow2-sm1-texture-painter-settings"
SETTINGS_VERSION = 1
LOGGER = logging.getLogger(__name__)
DIRECTORY_FIELDS = (
    "last_diffuse_directory",
    "last_image_export_directory",
    "last_pattern_import_directory",
    "last_pattern_export_directory",
)
DirectoryField = Literal[
    "last_diffuse_directory",
    "last_image_export_directory",
    "last_pattern_import_directory",
    "last_pattern_export_directory",
]
DirectoryValues = dict[str, Path | None]
SettingsDocument = dict[str, object]
COLOR_PICKER_GEOMETRY_FIELD = "ui_color_picker_geometry"
COLOR_PICKER_GROUP_FIELD = "ui_color_picker_group"
COLOR_PICKER_COLOR_SPACE_FIELD = "ui_color_picker_color_space"
COLOR_PICKER_SORT_MODE_FIELD = "ui_color_picker_sort_mode"
COLOR_PICKER_SASHES_FIELD = "ui_color_picker_sashes"
COLOR_PICKER_RECENT_COLORS_FIELD = "ui_color_picker_recent_colors"
# Application-owned data: workspace resets must preserve this field. A future
# Factory/Application Reset may intentionally clear it.
APPLICATION_COLOR_FAVORITES_FIELD = "color_favorites"
MAIN_WINDOW_POSITION_FIELD = "ui_main_window_position"
FAVORITE_SAVE_DIALOG_POSITION_FIELD = "ui_favorite_save_dialog_position"
FAVORITE_RENAME_DIALOG_POSITION_FIELD = "ui_favorite_rename_dialog_position"
CLOSEST_CITADEL_DIALOG_POSITION_FIELD = "ui_closest_citadel_dialog_position"
ABOUT_DIALOG_POSITION_FIELD = "ui_about_dialog_position"
BATCH_EDITOR_POSITION_FIELD = "ui_batch_editor_position"
GAME_PROFILE_FIELD = "game_profile_id"
ValidatedSettings = tuple[DirectoryValues, str | None]


class SettingsFileError(OSError):
    """Raised when preserving an invalid settings file prevents an update."""


class SettingsHandler:
    """Load and persist the small application settings document."""

    def __init__(
        self,
        settings_path: Path | None = None,
        home_directory: Path | None = None,
    ) -> None:
        self.path = Path(settings_path or get_settings_path())
        self.home_directory = Path(home_directory or Path.home())
        self._apply_authoritative_defaults()
        self._load()

    def _apply_authoritative_defaults(self) -> None:
        """Set the same in-memory values used by a clean first launch."""
        self.last_diffuse_directory: Path | None = None
        self.last_image_export_directory: Path | None = None
        self.last_pattern_import_directory: Path | None = None
        self.last_pattern_export_directory: Path | None = None
        self.color_picker_geometry: str | None = None
        self.color_picker_group: str | None = None
        self.color_picker_color_space: str | None = None
        self.color_picker_sort_mode: str | None = None
        self.color_picker_sashes: tuple[int, int] | None = None
        self.color_picker_recent_colors: RecentColors = ()
        self.favorite_colors: tuple[FavoriteColor, ...] = ()
        self.main_window_position: tuple[int, int] | None = None
        self.favorite_save_dialog_position: tuple[int, int] | None = None
        self.favorite_rename_dialog_position: tuple[int, int] | None = None
        self.closest_citadel_dialog_position: tuple[int, int] | None = None
        self.about_dialog_position: tuple[int, int] | None = None
        self.batch_editor_position: tuple[int, int] | None = None
        self.game_profile_id = DEFAULT_TEXTURE_NAMING.profile_id
        self.load_error: Exception | None = None
        self.factory_reset_pending_restart = False

    def restore_authoritative_defaults(self) -> None:
        """Atomically persist and adopt the clean-first-launch settings state."""
        document: SettingsDocument = {
            "format": SETTINGS_FORMAT,
            "version": SETTINGS_VERSION,
        }
        self._write_atomic(document)
        self._apply_authoritative_defaults()

    def restore_factory_defaults(self) -> None:
        """Reset preferences while retaining user-created and working-history data."""
        recent_colors = self.color_picker_recent_colors
        favorite_colors = self.favorite_colors
        document: SettingsDocument = {
            "format": SETTINGS_FORMAT,
            "version": SETTINGS_VERSION,
        }
        if recent_colors:
            document[COLOR_PICKER_RECENT_COLORS_FIELD] = [
                list(color) for color in recent_colors
            ]
        if favorite_colors:
            document[APPLICATION_COLOR_FAVORITES_FIELD] = serialize_favorite_colors(
                favorite_colors
            )
        self._write_atomic(document)
        self._apply_authoritative_defaults()
        self.color_picker_recent_colors = recent_colors
        self.favorite_colors = favorite_colors
        self.factory_reset_pending_restart = True

    def _load(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as fp:
                document: object = json.load(fp)
            directories, geometry = self._validate(document)
            assert isinstance(document, dict)
            for field, directory in directories.items():
                setattr(self, field, directory)
            self.color_picker_geometry = geometry
            self.color_picker_group = self._optional_ui_string(
                document, COLOR_PICKER_GROUP_FIELD
            )
            self.color_picker_color_space = self._optional_ui_string(
                document, COLOR_PICKER_COLOR_SPACE_FIELD
            )
            self.color_picker_sort_mode = self._optional_ui_string(
                document, COLOR_PICKER_SORT_MODE_FIELD
            )
            self.color_picker_sashes = self._optional_ui_pair(
                document, COLOR_PICKER_SASHES_FIELD
            )
            self.color_picker_recent_colors = validate_recent_colors(
                document.get(COLOR_PICKER_RECENT_COLORS_FIELD)
            )
            if APPLICATION_COLOR_FAVORITES_FIELD in document:
                self.favorite_colors = validate_favorite_colors(
                    document.get(APPLICATION_COLOR_FAVORITES_FIELD),
                    load_citadel_catalog(),
                )
            self.main_window_position = self._optional_ui_pair(
                document, MAIN_WINDOW_POSITION_FIELD
            )
            self.favorite_save_dialog_position = self._optional_ui_pair(
                document, FAVORITE_SAVE_DIALOG_POSITION_FIELD
            )
            self.favorite_rename_dialog_position = self._optional_ui_pair(
                document, FAVORITE_RENAME_DIALOG_POSITION_FIELD
            )
            self.closest_citadel_dialog_position = self._optional_ui_pair(
                document, CLOSEST_CITADEL_DIALOG_POSITION_FIELD
            )
            self.about_dialog_position = self._optional_ui_pair(
                document, ABOUT_DIALOG_POSITION_FIELD
            )
            self.batch_editor_position = self._optional_ui_pair(
                document, BATCH_EDITOR_POSITION_FIELD
            )
            profile_id = self._optional_ui_string(document, GAME_PROFILE_FIELD)
            if profile_id is not None:
                if texture_naming_profile_for_id(profile_id) is None:
                    LOGGER.warning("Ignoring unknown game profile ID %s", profile_id)
                else:
                    self.game_profile_id = profile_id
        except FileNotFoundError:
            return
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            self.load_error = exc
            LOGGER.exception("Could not load settings file: %s", self.path)

    @staticmethod
    def _validate(document: object) -> ValidatedSettings:
        if not isinstance(document, dict):
            raise ValueError("Settings file must contain a JSON object")
        if document.get("format") != SETTINGS_FORMAT:
            raise ValueError("Settings file has an unsupported format")
        if (
            type(document.get("version")) is not int
            or document["version"] != SETTINGS_VERSION
        ):
            raise ValueError("Settings file has an unsupported version")
        directories: DirectoryValues = {}
        for field in DIRECTORY_FIELDS:
            directory = document.get(field)
            if directory is not None and not isinstance(directory, str):
                raise ValueError(f"Settings field {field} must be a string")
            directories[field] = Path(directory) if directory else None
        geometry = SettingsHandler._optional_ui_string(
            document, COLOR_PICKER_GEOMETRY_FIELD
        )
        return directories, geometry

    def _get_existing_directory(self, field: DirectoryField) -> Path:
        if field == "last_diffuse_directory":
            directory = self.last_diffuse_directory
        elif field == "last_image_export_directory":
            directory = self.last_image_export_directory
        elif field == "last_pattern_import_directory":
            directory = self.last_pattern_import_directory
        else:
            directory = self.last_pattern_export_directory
        if directory is not None and directory.is_dir():
            return directory
        return self.home_directory

    def get_diffuse_initial_directory(self) -> Path:
        return self._get_existing_directory("last_diffuse_directory")

    def get_last_image_export_directory(self) -> Path:
        return self._get_existing_directory("last_image_export_directory")

    def get_last_pattern_import_directory(self) -> Path:
        return self._get_existing_directory("last_pattern_import_directory")

    def get_last_pattern_export_directory(self) -> Path:
        return self._get_existing_directory("last_pattern_export_directory")

    def remember_diffuse_file(self, diffuse_file: Path) -> None:
        self._set_directory(
            "last_diffuse_directory", Path(diffuse_file).resolve().parent
        )

    def set_last_image_export_directory(self, directory: Path) -> None:
        self._set_directory("last_image_export_directory", directory)

    def set_last_pattern_import_directory(self, directory: Path) -> None:
        self._set_directory("last_pattern_import_directory", directory)

    def set_last_pattern_export_directory(self, directory: Path) -> None:
        self._set_directory("last_pattern_export_directory", directory)

    def set_color_picker_geometry(self, geometry: str) -> None:
        if self.factory_reset_pending_restart:
            return
        self._update(COLOR_PICKER_GEOMETRY_FIELD, geometry)

    def set_color_picker_ui_state(
        self,
        geometry: str,
        group: str | None,
        color_space: str,
        sort_mode: str,
        sashes: tuple[int, int],
    ) -> None:
        if self.factory_reset_pending_restart:
            return
        values: dict[str, object] = {
            COLOR_PICKER_GEOMETRY_FIELD: geometry,
            COLOR_PICKER_GROUP_FIELD: group,
            COLOR_PICKER_COLOR_SPACE_FIELD: color_space,
            COLOR_PICKER_SORT_MODE_FIELD: sort_mode,
            COLOR_PICKER_SASHES_FIELD: list(sashes),
        }
        self._update_values(values)
        self.color_picker_geometry = geometry
        self.color_picker_group = group
        self.color_picker_color_space = color_space
        self.color_picker_sort_mode = sort_mode
        self.color_picker_sashes = sashes

    def set_main_window_position(self, position: tuple[int, int]) -> None:
        if self.factory_reset_pending_restart:
            return
        self._update_values({MAIN_WINDOW_POSITION_FIELD: list(position)})
        self.main_window_position = position

    def set_favorite_save_dialog_position(
        self, position: tuple[int, int]
    ) -> None:
        if self.factory_reset_pending_restart:
            return
        self._update_values({FAVORITE_SAVE_DIALOG_POSITION_FIELD: list(position)})
        self.favorite_save_dialog_position = position

    def set_favorite_rename_dialog_position(
        self, position: tuple[int, int]
    ) -> None:
        if self.factory_reset_pending_restart:
            return
        self._update_values({FAVORITE_RENAME_DIALOG_POSITION_FIELD: list(position)})
        self.favorite_rename_dialog_position = position

    def set_closest_citadel_dialog_position(
        self, position: tuple[int, int]
    ) -> None:
        if self.factory_reset_pending_restart:
            return
        self._update_values({CLOSEST_CITADEL_DIALOG_POSITION_FIELD: list(position)})
        self.closest_citadel_dialog_position = position

    def set_about_dialog_position(self, position: tuple[int, int]) -> None:
        if self.factory_reset_pending_restart:
            return
        self._update_values({ABOUT_DIALOG_POSITION_FIELD: list(position)})
        self.about_dialog_position = position

    def set_batch_editor_position(self, position: tuple[int, int]) -> None:
        if self.factory_reset_pending_restart:
            return
        self._update_values({BATCH_EDITOR_POSITION_FIELD: list(position)})
        self.batch_editor_position = position

    def set_game_profile_id(self, profile_id: str) -> None:
        if texture_naming_profile_for_id(profile_id) is None:
            raise ValueError(f"Unknown game profile ID: {profile_id}")
        self._update_values({GAME_PROFILE_FIELD: profile_id})
        self.game_profile_id = profile_id

    def set_color_picker_recent_colors(self, colors: RecentColors) -> None:
        validated = validate_recent_colors([list(color) for color in colors])
        serialized = [list(color) for color in validated]
        self._update_values({COLOR_PICKER_RECENT_COLORS_FIELD: serialized})
        self.color_picker_recent_colors = validated

    def set_favorite_colors(self, favorites: tuple[FavoriteColor, ...]) -> None:
        serialized = serialize_favorite_colors(favorites)
        validated = validate_favorite_colors(serialized, load_citadel_catalog())
        self._update_values(
            {
                APPLICATION_COLOR_FAVORITES_FIELD: serialize_favorite_colors(
                    validated
                )
            }
        )
        self.favorite_colors = validated

    @staticmethod
    def _optional_ui_string(
        document: dict[str, object], field: str
    ) -> str | None:
        value = document.get(field)
        if value is not None and not isinstance(value, str):
            LOGGER.warning("Ignoring invalid optional settings field %s", field)
            return None
        return value

    @staticmethod
    def _optional_ui_pair(
        document: dict[str, object], field: str
    ) -> tuple[int, int] | None:
        value = document.get(field)
        if value is None:
            return None
        if (
            not isinstance(value, list)
            or len(value) != 2
            or any(type(coordinate) is not int for coordinate in value)
        ):
            LOGGER.warning("Ignoring invalid optional settings field %s", field)
            return None
        return value[0], value[1]

    def _set_directory(self, field: DirectoryField, directory: Path) -> None:
        if self.load_error is not None and self.path.exists():
            raise SettingsFileError(
                f"Settings file is invalid and was not overwritten: {self.path}"
            ) from self.load_error

        directory = Path(directory).resolve()
        if not directory.is_dir():
            raise SettingsFileError(f"Settings directory does not exist: {directory}")
        self._update(field, directory)
        setattr(self, field, directory)

    def _update(self, field: str, value: object) -> None:
        self._update_values({field: value})
        if field == COLOR_PICKER_GEOMETRY_FIELD:
            self.color_picker_geometry = str(value)

    def _update_values(self, updates: Mapping[str, object]) -> None:
        if self.load_error is not None and self.path.exists():
            raise SettingsFileError(
                f"Settings file is invalid and was not overwritten: {self.path}"
            ) from self.load_error

        document: SettingsDocument = {
            "format": SETTINGS_FORMAT,
            "version": SETTINGS_VERSION,
        }
        for name in DIRECTORY_FIELDS:
            directory = updates.get(name, getattr(self, name))
            if directory is not None:
                document[name] = str(directory)
        persisted_ui: SettingsDocument = {
            COLOR_PICKER_GEOMETRY_FIELD: self.color_picker_geometry,
            COLOR_PICKER_GROUP_FIELD: self.color_picker_group,
            COLOR_PICKER_COLOR_SPACE_FIELD: self.color_picker_color_space,
            COLOR_PICKER_SORT_MODE_FIELD: self.color_picker_sort_mode,
            COLOR_PICKER_SASHES_FIELD: (
                list(self.color_picker_sashes) if self.color_picker_sashes else None
            ),
            COLOR_PICKER_RECENT_COLORS_FIELD: (
                [list(color) for color in self.color_picker_recent_colors]
                if self.color_picker_recent_colors
                else None
            ),
            APPLICATION_COLOR_FAVORITES_FIELD: (
                serialize_favorite_colors(self.favorite_colors)
                if self.favorite_colors
                else None
            ),
            MAIN_WINDOW_POSITION_FIELD: (
                list(self.main_window_position) if self.main_window_position else None
            ),
            FAVORITE_SAVE_DIALOG_POSITION_FIELD: (
                list(self.favorite_save_dialog_position)
                if self.favorite_save_dialog_position
                else None
            ),
            FAVORITE_RENAME_DIALOG_POSITION_FIELD: (
                list(self.favorite_rename_dialog_position)
                if self.favorite_rename_dialog_position
                else None
            ),
            CLOSEST_CITADEL_DIALOG_POSITION_FIELD: (
                list(self.closest_citadel_dialog_position)
                if self.closest_citadel_dialog_position
                else None
            ),
            ABOUT_DIALOG_POSITION_FIELD: (
                list(self.about_dialog_position)
                if self.about_dialog_position
                else None
            ),
            BATCH_EDITOR_POSITION_FIELD: (
                list(self.batch_editor_position)
                if self.batch_editor_position
                else None
            ),
            GAME_PROFILE_FIELD: self.game_profile_id,
        }
        persisted_ui.update(
            {
                name: value
                for name, value in updates.items()
                if name not in DIRECTORY_FIELDS
            }
        )
        document.update(
            {name: value for name, value in persisted_ui.items() if value is not None}
        )
        self._write_atomic(document)
        self.load_error = None

    def _write_atomic(self, document: SettingsDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as fp:
                temporary_path = Path(fp.name)
                json.dump(document, fp, indent=2, ensure_ascii=False)
                fp.write("\n")
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    LOGGER.exception(
                        "Could not remove temporary settings file: %s",
                        temporary_path,
                    )
