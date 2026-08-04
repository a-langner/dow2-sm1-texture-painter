import json
import logging
import os
from pathlib import Path
import tempfile

from src.user_data import get_settings_path

SETTINGS_FORMAT = "sm1-dow2-texture-painter-settings"
SETTINGS_VERSION = 1
LOGGER = logging.getLogger(__name__)
DIRECTORY_FIELDS = (
    "last_diffuse_directory",
    "last_pattern_import_directory",
    "last_pattern_export_directory",
)


class SettingsFileError(OSError):
    """Raised when preserving an invalid settings file prevents an update."""


class SettingsHandler:
    """Load and persist the small application settings document."""

    def __init__(self, settings_path=None, home_directory=None):
        self.path = Path(settings_path or get_settings_path())
        self.home_directory = Path(home_directory or Path.home())
        self.last_diffuse_directory = None
        self.last_pattern_import_directory = None
        self.last_pattern_export_directory = None
        self.load_error = None
        self._load()

    def _load(self):
        try:
            with self.path.open("r", encoding="utf-8") as fp:
                document = json.load(fp)
            directories = self._validate(document)
            for field, directory in directories.items():
                setattr(self, field, directory)
        except FileNotFoundError:
            return
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            self.load_error = exc
            LOGGER.exception("Could not load settings file: %s", self.path)

    @staticmethod
    def _validate(document):
        if not isinstance(document, dict):
            raise ValueError("Settings file must contain a JSON object")
        if document.get("format") != SETTINGS_FORMAT:
            raise ValueError("Settings file has an unsupported format")
        if (
            type(document.get("version")) is not int
            or document["version"] != SETTINGS_VERSION
        ):
            raise ValueError("Settings file has an unsupported version")
        directories = {}
        for field in DIRECTORY_FIELDS:
            directory = document.get(field)
            if directory is not None and not isinstance(directory, str):
                raise ValueError(f"Settings field {field} must be a string")
            directories[field] = Path(directory) if directory else None
        return directories

    def _get_existing_directory(self, field):
        directory = getattr(self, field)
        if directory is not None and directory.is_dir():
            return directory
        return self.home_directory

    def get_diffuse_initial_directory(self):
        return self._get_existing_directory("last_diffuse_directory")

    def get_last_pattern_import_directory(self):
        return self._get_existing_directory("last_pattern_import_directory")

    def get_last_pattern_export_directory(self):
        return self._get_existing_directory("last_pattern_export_directory")

    def remember_diffuse_file(self, diffuse_file):
        self._set_directory(
            "last_diffuse_directory", Path(diffuse_file).resolve().parent
        )

    def set_last_pattern_import_directory(self, directory):
        self._set_directory("last_pattern_import_directory", directory)

    def set_last_pattern_export_directory(self, directory):
        self._set_directory("last_pattern_export_directory", directory)

    def _set_directory(self, field, directory):
        if self.load_error is not None and self.path.exists():
            raise SettingsFileError(
                f"Settings file is invalid and was not overwritten: {self.path}"
            ) from self.load_error

        directory = Path(directory).resolve()
        if not directory.is_dir():
            raise SettingsFileError(f"Settings directory does not exist: {directory}")
        values = {name: getattr(self, name) for name in DIRECTORY_FIELDS}
        values[field] = directory
        document = {
            "format": SETTINGS_FORMAT,
            "version": SETTINGS_VERSION,
        }
        document.update(
            {name: str(value) for name, value in values.items() if value is not None}
        )
        self._write_atomic(document)
        setattr(self, field, directory)
        self.load_error = None

    def _write_atomic(self, document):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
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
