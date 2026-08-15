"""Coordinate file dialogs with success-only remembered directories."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from src.constant import OPEN_FILETYPES, SAVE_FILETYPES
from src.pattern_exchange import (
    PATTERN_COLLECTION_EXCHANGE_SUFFIX,
    PATTERN_EXCHANGE_SUFFIX,
)
from src.settings_handler import SettingsHandler

FileTypePattern = str | tuple[str, ...]
FileTypes = Sequence[tuple[str, FileTypePattern]]


class FileDialogProvider(Protocol):
    def choose_open_file(
        self,
        *,
        title: str | None = None,
        initial_directory: Path | None = None,
        filetypes: FileTypes = (),
    ) -> Path | None: ...

    def choose_save_file(
        self,
        *,
        title: str | None = None,
        initial_directory: Path | None = None,
        initial_filename: str | None = None,
        default_extension: str | tuple[str, str] | None = None,
        filetypes: FileTypes = (),
    ) -> Path | None: ...

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

    def __init__(
        self,
        settings: SettingsHandler,
        dialogs: FileDialogProvider,
        home_directory: Path | None = None,
    ) -> None:
        self.settings = settings
        self.dialogs = dialogs
        self.home_directory = Path(home_directory or Path.home())

    def _initial_directory(
        self,
        remembered_directory: Path | None = None,
    ) -> Path:
        directory = Path(remembered_directory or self.home_directory)
        return directory if directory.is_dir() else self.home_directory

    def choose_diffuse_file(self) -> Path | None:
        return self.dialogs.choose_open_file(
            initial_directory=self._initial_directory(
                self.settings.get_diffuse_initial_directory()
            ),
            filetypes=OPEN_FILETYPES,
        )

    def remember_successful_diffuse(self, diffuse_path: Path) -> None:
        self.settings.remember_diffuse_file(diffuse_path)

    def choose_channel_file(self) -> Path | None:
        return self.dialogs.choose_open_file(
            initial_directory=self._initial_directory(),
            filetypes=OPEN_FILETYPES,
            title="Open Team Color Mask",
        )

    def choose_image_save_destination(
        self,
        initial_filename: str,
    ) -> Path | None:
        return self.dialogs.choose_save_file(
            initial_directory=self._initial_directory(),
            filetypes=SAVE_FILETYPES,
            default_extension=SAVE_FILETYPES[0],
            initial_filename=initial_filename,
        )

    def choose_pattern_import_file(self) -> Path | None:
        return self.dialogs.choose_open_file(
            initial_directory=self._pattern_import_directory(),
            filetypes=PATTERN_FILETYPES,
            title="Import Pattern",
        )

    def choose_pattern_collection_import_file(self) -> Path | None:
        return self.dialogs.choose_open_file(
            initial_directory=self._pattern_import_directory(),
            filetypes=PATTERN_COLLECTION_FILETYPES,
            title="Import Pattern Collection",
        )

    def remember_successful_pattern_import(self, source_path: Path) -> None:
        self.settings.set_last_pattern_import_directory(Path(source_path).parent)

    def choose_pattern_export_destination(
        self,
        initial_filename: str,
    ) -> Path | None:
        return self.dialogs.choose_save_file(
            initial_directory=self._pattern_export_directory(),
            initial_filename=initial_filename,
            filetypes=PATTERN_FILETYPES,
            default_extension=PATTERN_EXCHANGE_SUFFIX,
            title="Export Pattern",
        )

    def choose_pattern_collection_export_destination(
        self,
        initial_filename: str,
    ) -> Path | None:
        return self.dialogs.choose_save_file(
            initial_directory=self._pattern_export_directory(),
            initial_filename=initial_filename,
            filetypes=PATTERN_COLLECTION_FILETYPES,
            default_extension=PATTERN_COLLECTION_EXCHANGE_SUFFIX,
            title="Export Pattern Collection",
        )

    def remember_successful_pattern_export(
        self,
        destination_path: Path,
    ) -> None:
        self.settings.set_last_pattern_export_directory(
            Path(destination_path).parent
        )

    def _pattern_import_directory(self) -> Path:
        return self._initial_directory(
            self.settings.get_last_pattern_import_directory()
        )

    def _pattern_export_directory(self) -> Path:
        return self._initial_directory(
            self.settings.get_last_pattern_export_directory()
        )
