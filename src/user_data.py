from pathlib import Path

from platformdirs import user_data_path


APP_NAME = "SM1-DOW2 Texture Painter"
USER_PATTERNS_FILENAME = "user_patterns.json"


def get_user_patterns_path(data_directory=None, create_parent=False):
    """Return the user-pattern file path without creating it by default."""
    if data_directory is None:
        data_directory = user_data_path(APP_NAME, appauthor=False)

    pattern_path = Path(data_directory) / USER_PATTERNS_FILENAME
    if create_parent:
        pattern_path.parent.mkdir(parents=True, exist_ok=True)

    return pattern_path
