"""Coordinate file dialogs with success-only remembered directories."""

from pathlib import Path

from src.constant import OPEN_FILETYPES, SAVE_FILETYPES
from src.pattern_exchange import (
    PATTERN_COLLECTION_EXCHANGE_SUFFIX,
    PATTERN_EXCHANGE_SUFFIX,
)

PATTERN_FILETYPES = (
    ("Pattern files", f"*{PATTERN_EXCHANGE_SUFFIX}"),
    ("JSON files", "*.json"),
    ("All files", "*.*"),
)
PATTERN_COLLECTION_FILETYPES = (
    ("Pattern Collections", f"*{PATTERN_COLLECTION_EXCHANGE_SUFFIX}"),
    ("JSON files", "*.json"),
    ("All files", "*.*"),
)


class FileSelectionService:
    """Select files and remember their directories only after explicit success."""

    def __init__(self, settings, dialogs, home_directory=None):
        self.settings = settings
        self.dialogs = dialogs
        self.home_directory = Path(home_directory or Path.home())

    def _initial_directory(self, remembered_directory=None):
        directory = Path(remembered_directory or self.home_directory)
        return directory if directory.is_dir() else self.home_directory

    def choose_diffuse_file(self):
        return self.dialogs.choose_open_file(
            initial_directory=self._initial_directory(
                self.settings.get_diffuse_initial_directory()
            ),
            filetypes=OPEN_FILETYPES,
        )

    def remember_successful_diffuse(self, diffuse_path):
        self.settings.remember_diffuse_file(diffuse_path)

    def choose_channel_file(self):
        return self.dialogs.choose_open_file(
            initial_directory=self._initial_directory(),
            filetypes=OPEN_FILETYPES,
            title="Open channel file",
        )

    def choose_image_save_destination(self, initial_filename):
        return self.dialogs.choose_save_file(
            initial_directory=self._initial_directory(),
            filetypes=SAVE_FILETYPES,
            default_extension=SAVE_FILETYPES[0],
            initial_filename=initial_filename,
        )

    def choose_pattern_import_file(self):
        return self.dialogs.choose_open_file(
            initial_directory=self._pattern_import_directory(),
            filetypes=PATTERN_FILETYPES,
            title="Import Pattern",
        )

    def choose_pattern_collection_import_file(self):
        return self.dialogs.choose_open_file(
            initial_directory=self._pattern_import_directory(),
            filetypes=PATTERN_COLLECTION_FILETYPES,
            title="Import Pattern Collection",
        )

    def remember_successful_pattern_import(self, source_path):
        self.settings.set_last_pattern_import_directory(Path(source_path).parent)

    def choose_pattern_export_destination(self, initial_filename):
        return self.dialogs.choose_save_file(
            initial_directory=self._pattern_export_directory(),
            initial_filename=initial_filename,
            filetypes=PATTERN_FILETYPES,
            default_extension=PATTERN_EXCHANGE_SUFFIX,
            title="Export Pattern",
        )

    def choose_pattern_collection_export_destination(self, initial_filename):
        return self.dialogs.choose_save_file(
            initial_directory=self._pattern_export_directory(),
            initial_filename=initial_filename,
            filetypes=PATTERN_COLLECTION_FILETYPES,
            default_extension=PATTERN_COLLECTION_EXCHANGE_SUFFIX,
            title="Export Pattern Collection",
        )

    def remember_successful_pattern_export(self, destination_path):
        self.settings.set_last_pattern_export_directory(
            Path(destination_path).parent
        )

    def _pattern_import_directory(self):
        return self._initial_directory(
            self.settings.get_last_pattern_import_directory()
        )

    def _pattern_export_directory(self):
        return self._initial_directory(
            self.settings.get_last_pattern_export_directory()
        )
