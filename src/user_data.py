from pathlib import Path

from platformdirs import user_data_path

APP_NAME = "SM1-DOW2 Texture Painter"
USER_PATTERNS_FILENAME = "user_patterns.json"
SETTINGS_FILENAME = "settings.json"


def get_user_data_file_path(
    filename: str,
    data_directory: Path | None = None,
    create_parent: bool = False,
) -> Path:
    """Return an application user-data file without creating it by default."""
    if data_directory is None:
        data_directory = user_data_path(APP_NAME, appauthor=False)

    file_path = Path(data_directory) / filename
    if create_parent:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    return file_path


def get_user_patterns_path(
    data_directory: Path | None = None,
    create_parent: bool = False,
) -> Path:
    """Return the user-pattern file path without creating it by default."""
    return get_user_data_file_path(
        USER_PATTERNS_FILENAME, data_directory, create_parent
    )


def get_settings_path(
    data_directory: Path | None = None,
    create_parent: bool = False,
) -> Path:
    """Return the settings file path without creating it by default."""
    return get_user_data_file_path(
        SETTINGS_FILENAME, data_directory, create_parent
    )
