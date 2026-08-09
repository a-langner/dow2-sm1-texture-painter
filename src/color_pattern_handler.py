from collections import OrderedDict
from collections.abc import Iterable, Mapping
import json
from importlib import resources
from importlib.resources.abc import Traversable
import logging
import os
from pathlib import Path
import re
import tempfile
from typing import NamedTuple, cast

from src.user_data import get_user_patterns_path

RESOURCE_ROOT = resources.files("src.resources")
ARMY_PATTERN_RESOURCE = RESOURCE_ROOT.joinpath("army_pattern.json")
USER_PATTERN_FORMAT = "sm1-dow2-texture-painter-user-patterns"
USER_PATTERN_VERSION = 1

color_key = [
    "primary_colour_name",
    "secondary_colour_name",
    "tint_colour_name",
    "extra_colour_name",
]

COLOR_VALUE_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
LOGGER = logging.getLogger(__name__)

PatternColors = list[str]
StoredPattern = OrderedDict[str, str]
PatternCollection = OrderedDict[str, StoredPattern]
PatternInput = Mapping[str, str]


class PatternError(ValueError):
    """Base class for invalid pattern operations."""


class InvalidPatternError(PatternError):
    """Raised when a pattern name or its colors are invalid."""


class PatternNameConflictError(PatternError):
    """Raised when a user pattern conflicts with a built-in pattern."""


class PatternAlreadyExistsError(PatternError):
    """Raised when overwriting an existing user pattern is attempted."""


class BuiltinPatternDeletionError(PatternError):
    """Raised when deletion of a built-in pattern is attempted."""


class BuiltinPatternModificationError(PatternError):
    """Raised when modification of a built-in pattern is attempted."""


class PatternNotFoundError(PatternError):
    """Raised when an operation targets a pattern that does not exist."""


class UserPatternFileError(PatternError):
    """Base class for user-pattern file errors safe to show in the GUI."""


class InvalidUserPatternFileError(UserPatternFileError):
    """Raised when a user-pattern file has invalid JSON or structure."""


class UnsupportedUserPatternVersionError(UserPatternFileError):
    """Raised when a user-pattern file uses an unsupported future version."""


class UserPatternPersistenceError(UserPatternFileError):
    """Raised when user-pattern data cannot be persisted safely."""


class UserPatternLoadIssue(NamedTuple):
    path: Path
    error: Exception


def _load_pattern_file(pattern_file: Traversable) -> PatternCollection:
    with pattern_file.open("r", encoding="utf-8") as fp:
        patterns: object = json.load(fp, object_pairs_hook=OrderedDict)

    if not _is_valid_pattern_collection(patterns):
        raise ValueError("Pattern data must contain valid Patterns")

    return cast(PatternCollection, patterns)


def load_builtin_patterns(
    pattern_resource: Traversable | None = None,
) -> PatternCollection:
    """Load the ordered, read-only pattern collection bundled with the app."""
    if pattern_resource is None:
        pattern_resource = ARMY_PATTERN_RESOURCE
    return _load_pattern_file(pattern_resource)


def load_user_patterns(pattern_path: Path | None = None) -> PatternCollection:
    """Load ordered user patterns, or return an empty collection if absent."""
    if pattern_path is None:
        pattern_path = get_user_patterns_path()
    pattern_path = Path(pattern_path)

    try:
        pattern_path.stat()
    except FileNotFoundError:
        return OrderedDict()

    try:
        with pattern_path.open("r", encoding="utf-8") as fp:
            document: object = json.load(fp, object_pairs_hook=OrderedDict)
    except json.JSONDecodeError as exc:
        raise InvalidUserPatternFileError(
            f"User-pattern file contains invalid JSON at line {exc.lineno}"
        ) from exc

    if not isinstance(document, dict):
        raise InvalidUserPatternFileError(
            "User-pattern file must contain a JSON object"
        )

    # Explicit compatibility for files written before the versioned wrapper.
    if _is_valid_pattern_collection(document):
        return cast(PatternCollection, document)

    if document.get("format") != USER_PATTERN_FORMAT:
        raise InvalidUserPatternFileError(
            "User-pattern file has an invalid or missing format identifier"
        )

    if "version" not in document:
        raise InvalidUserPatternFileError(
            "User-pattern file is missing its format version"
        )
    if type(document["version"]) is not int:
        raise InvalidUserPatternFileError(
            "User-pattern file version must be an integer"
        )
    if document["version"] != USER_PATTERN_VERSION:
        raise UnsupportedUserPatternVersionError(
            "Unsupported user-pattern file version "
            f"{document['version']!r}; supported version is "
            f"{USER_PATTERN_VERSION}"
        )

    patterns = document.get("patterns")
    if not isinstance(patterns, dict):
        raise InvalidUserPatternFileError(
            "User-pattern file must contain a patterns object"
        )
    if not _is_valid_pattern_collection(patterns):
        raise InvalidUserPatternFileError(
            "User-pattern file contains an invalid pattern"
        )

    return cast(PatternCollection, patterns)


def load_user_patterns_for_startup(
    pattern_path: Path | None = None,
) -> tuple[PatternCollection, UserPatternLoadIssue | None]:
    """Load user patterns without preventing application startup on failure."""
    if pattern_path is None:
        pattern_path = get_user_patterns_path()
    pattern_path = Path(pattern_path).resolve()

    try:
        return load_user_patterns(pattern_path), None
    except (UserPatternFileError, OSError) as exc:
        LOGGER.exception("Could not load user-pattern file: %s", pattern_path)
        return OrderedDict(), UserPatternLoadIssue(pattern_path, exc)


def get_all_patterns(
    builtin_patterns: Mapping[str, StoredPattern] | None = None,
    user_patterns: Mapping[str, StoredPattern] | None = None,
) -> PatternCollection:
    """Return built-ins followed by users, rejecting name collisions."""
    if builtin_patterns is None:
        builtin_patterns = builtin_color_patterns
    if user_patterns is None:
        user_patterns = user_color_patterns

    duplicate_names = set(builtin_patterns).intersection(user_patterns)
    if duplicate_names:
        names = ", ".join(sorted(duplicate_names))
        raise PatternNameConflictError(
            f"User pattern names conflict with built-in patterns: {names}"
        )

    combined_patterns = OrderedDict(builtin_patterns)
    combined_patterns.update(user_patterns)
    return combined_patterns


def is_user_pattern(name: str) -> bool:
    return name in user_color_patterns


def has_user_patterns() -> bool:
    return bool(user_color_patterns)


def get_pattern_colors(name: str) -> PatternColors:
    """Return stored Pattern colors in the canonical persistence order."""
    normalized_name = normalize_pattern_name(name)
    pattern = get_all_patterns().get(normalized_name)
    if pattern is None:
        raise PatternNotFoundError(f"Pattern '{normalized_name}' was not found")
    try:
        colors = [pattern[key] for key in color_key]
    except (KeyError, TypeError) as exc:
        raise InvalidPatternError(
            f"Pattern '{normalized_name}' does not contain four ordered colors"
        ) from exc
    return normalize_pattern_colors(colors)


def pattern_colors_equal(
    first: Iterable[str],
    second: Iterable[str],
) -> bool:
    """Compare two valid color sets without hexadecimal case differences."""
    normalized_first = [
        color.casefold() for color in normalize_pattern_colors(first)
    ]
    normalized_second = [
        color.casefold() for color in normalize_pattern_colors(second)
    ]
    return normalized_first == normalized_second


def _is_valid_pattern_collection(patterns: object) -> bool:
    if not isinstance(patterns, dict):
        return False

    for name, pattern in patterns.items():
        if not isinstance(name, str) or not name.strip():
            return False
        if not isinstance(pattern, dict) or list(pattern) != color_key:
            return False
        if not all(
            isinstance(color, str) and COLOR_VALUE_PATTERN.fullmatch(color)
            for color in pattern.values()
        ):
            return False

    return True


def normalize_pattern_name(name: object) -> str:
    """Validate and trim a pattern name using persistence rules."""
    if name is None or not isinstance(name, str) or not name.strip():
        raise InvalidPatternError("Pattern name must not be empty")
    return name.strip()


def normalize_pattern_colors(colors: Iterable[object]) -> PatternColors:
    """Validate four color values using the persistent #RRGGBB format."""
    try:
        normalized_colors = list(colors)
    except TypeError as exc:
        raise InvalidPatternError("Exactly four colors are required") from exc

    if len(normalized_colors) != len(color_key):
        raise InvalidPatternError("Exactly four colors are required")
    if not all(
        isinstance(color, str) and COLOR_VALUE_PATTERN.fullmatch(color)
        for color in normalized_colors
    ):
        raise InvalidPatternError(
            "Colors must use the #RRGGBB hexadecimal format"
        )
    return [color for color in normalized_colors if isinstance(color, str)]


def _validate_new_pattern(
    name: str,
    colors: Iterable[object],
) -> tuple[str, PatternColors]:
    normalized_name = normalize_pattern_name(name)
    normalized_colors = normalize_pattern_colors(colors)

    if normalized_name in builtin_color_patterns:
        raise PatternNameConflictError(
            f"'{normalized_name}' is a built-in pattern name"
        )
    if normalized_name in user_color_patterns:
        raise PatternAlreadyExistsError(
            f"User pattern '{normalized_name}' already exists"
        )

    return normalized_name, normalized_colors


def _write_user_patterns(
    patterns: Mapping[str, StoredPattern],
    pattern_path: Path,
) -> None:
    pattern_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    document = OrderedDict(
        [
            ("format", USER_PATTERN_FORMAT),
            ("version", USER_PATTERN_VERSION),
            ("patterns", patterns),
        ]
    )

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=pattern_path.parent,
            prefix=f".{pattern_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as fp:
            temporary_path = Path(fp.name)
            json.dump(document, fp, indent=2, ensure_ascii=False)
            fp.write("\n")
            fp.flush()
            os.fsync(fp.fileno())

        os.replace(temporary_path, pattern_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                LOGGER.warning(
                    "Could not remove user-pattern temporary file: %s",
                    temporary_path,
                    exc_info=True,
                )


def _ensure_user_pattern_file_is_writable(pattern_path: Path) -> None:
    if (
        user_pattern_load_issue is not None
        and pattern_path.resolve() == user_pattern_load_issue.path
    ):
        raise UserPatternFileError(
            "The user-pattern file was not loaded successfully and cannot "
            "be safely updated."
        )


def save(
    name: str,
    colors: Iterable[object],
    pattern_path: Path | None = None,
) -> None:
    normalized_name, normalized_colors = _validate_new_pattern(name, colors)
    if pattern_path is None:
        pattern_path = get_user_patterns_path(create_parent=True)
    pattern_path = Path(pattern_path)
    _ensure_user_pattern_file_is_writable(pattern_path)

    pattern = OrderedDict(zip(color_key, normalized_colors))
    updated_user_patterns = OrderedDict(user_color_patterns)
    updated_user_patterns[normalized_name] = pattern

    _write_user_patterns(updated_user_patterns, pattern_path)

    user_color_patterns[normalized_name] = pattern
    army_color_pattern[normalized_name] = pattern


def save_imported_pattern(
    name: str,
    colors: Iterable[object],
    overwrite: bool = False,
    pattern_path: Path | None = None,
) -> str:
    """Persist an imported user pattern, optionally replacing that user name."""
    normalized_name = normalize_pattern_name(name)
    normalized_colors = normalize_pattern_colors(colors)
    if normalized_name in builtin_color_patterns:
        raise PatternNameConflictError(
            f"'{normalized_name}' is a built-in pattern name"
        )
    if normalized_name in user_color_patterns and not overwrite:
        raise PatternAlreadyExistsError(
            f"User pattern '{normalized_name}' already exists"
        )

    if pattern_path is None:
        pattern_path = get_user_patterns_path(create_parent=True)
    pattern_path = Path(pattern_path)
    _ensure_user_pattern_file_is_writable(pattern_path)

    pattern = OrderedDict(zip(color_key, normalized_colors))
    updated_user_patterns = OrderedDict(user_color_patterns)
    updated_user_patterns[normalized_name] = pattern
    _write_user_patterns(updated_user_patterns, pattern_path)

    user_color_patterns[normalized_name] = pattern
    army_color_pattern[normalized_name] = pattern
    return normalized_name


def update_user_pattern(
    name: str,
    colors: Iterable[object],
    pattern_path: Path | None = None,
) -> str:
    """Atomically replace the colors of one existing user-created Pattern."""
    normalized_name = normalize_pattern_name(name)
    if normalized_name in builtin_color_patterns:
        raise BuiltinPatternModificationError(
            f"Built-in pattern '{normalized_name}' cannot be updated"
        )
    if normalized_name not in user_color_patterns:
        raise PatternNotFoundError(
            f"Pattern '{normalized_name}' was not found"
        )
    normalized_colors = normalize_pattern_colors(colors)

    if pattern_path is None:
        pattern_path = get_user_patterns_path(create_parent=True)
    pattern_path = Path(pattern_path)
    _ensure_user_pattern_file_is_writable(pattern_path)

    updated_pattern = OrderedDict(zip(color_key, normalized_colors))
    updated_user_patterns = OrderedDict(user_color_patterns)
    updated_user_patterns[normalized_name] = updated_pattern
    try:
        _write_user_patterns(updated_user_patterns, pattern_path)
    except OSError as exc:
        raise UserPatternPersistenceError(
            f"Could not update user pattern '{normalized_name}': {exc}"
        ) from exc

    user_color_patterns[normalized_name] = updated_pattern
    army_color_pattern[normalized_name] = updated_pattern
    return normalized_name


def rename_user_pattern(
    old_name: str,
    new_name: str,
    pattern_path: Path | None = None,
) -> str:
    """Atomically rename one existing user-created Pattern in place."""
    normalized_old_name = normalize_pattern_name(old_name)
    normalized_new_name = normalize_pattern_name(new_name)

    if normalized_old_name in builtin_color_patterns:
        raise BuiltinPatternModificationError(
            f"Built-in pattern '{normalized_old_name}' cannot be renamed"
        )
    if normalized_old_name not in user_color_patterns:
        raise PatternNotFoundError(
            f"Pattern '{normalized_old_name}' was not found"
        )
    if normalized_new_name == normalized_old_name:
        return normalized_new_name
    if normalized_new_name in builtin_color_patterns:
        raise PatternNameConflictError(
            f"'{normalized_new_name}' is a built-in pattern name"
        )
    if normalized_new_name in user_color_patterns:
        raise PatternAlreadyExistsError(
            f"User pattern '{normalized_new_name}' already exists"
        )

    renamed_user_patterns = OrderedDict(
        (
            normalized_new_name if name == normalized_old_name else name,
            OrderedDict(pattern),
        )
        for name, pattern in user_color_patterns.items()
    )
    if pattern_path is None:
        pattern_path = get_user_patterns_path(create_parent=True)
    pattern_path = Path(pattern_path)
    _ensure_user_pattern_file_is_writable(pattern_path)
    try:
        _write_user_patterns(renamed_user_patterns, pattern_path)
    except OSError as exc:
        raise UserPatternPersistenceError(
            f"Could not rename user pattern '{normalized_old_name}': {exc}"
        ) from exc

    user_color_patterns.clear()
    user_color_patterns.update(renamed_user_patterns)
    army_color_pattern.clear()
    army_color_pattern.update(builtin_color_patterns)
    army_color_pattern.update(user_color_patterns)
    return normalized_new_name


def replace_user_patterns(
    patterns: Mapping[str, PatternInput],
    pattern_path: Path | None = None,
) -> None:
    """Atomically replace the complete user collection after batch validation."""
    normalized_patterns = OrderedDict()
    for name, pattern in patterns.items():
        normalized_name = normalize_pattern_name(name)
        if normalized_name in builtin_color_patterns:
            raise PatternNameConflictError(
                f"'{normalized_name}' is a built-in pattern name"
            )
        if normalized_name in normalized_patterns:
            raise PatternAlreadyExistsError(
                f"User pattern '{normalized_name}' already exists"
            )
        if not isinstance(pattern, dict):
            raise InvalidPatternError(
                f"User pattern '{normalized_name}' must contain four colors"
            )
        try:
            colors = [pattern[key] for key in color_key]
        except KeyError as exc:
            raise InvalidPatternError(
                f"User pattern '{normalized_name}' is missing color {exc.args[0]}"
            ) from exc
        normalized_colors = normalize_pattern_colors(colors)
        normalized_patterns[normalized_name] = OrderedDict(
            zip(color_key, normalized_colors)
        )

    if pattern_path is None:
        pattern_path = get_user_patterns_path(create_parent=True)
    pattern_path = Path(pattern_path)
    _ensure_user_pattern_file_is_writable(pattern_path)
    _write_user_patterns(normalized_patterns, pattern_path)

    user_color_patterns.clear()
    user_color_patterns.update(normalized_patterns)
    army_color_pattern.clear()
    army_color_pattern.update(builtin_color_patterns)
    army_color_pattern.update(user_color_patterns)


def delete(name: str, pattern_path: Path | None = None) -> None:
    normalized_name = name.strip() if isinstance(name, str) else name
    if normalized_name in builtin_color_patterns:
        raise BuiltinPatternDeletionError(
            f"Built-in pattern '{normalized_name}' cannot be deleted"
        )
    if normalized_name not in user_color_patterns:
        raise PatternNotFoundError(
            f"Pattern '{normalized_name}' was not found"
        )

    if pattern_path is None:
        pattern_path = get_user_patterns_path(create_parent=True)
    pattern_path = Path(pattern_path)
    _ensure_user_pattern_file_is_writable(pattern_path)

    updated_user_patterns = OrderedDict(user_color_patterns)
    del updated_user_patterns[normalized_name]

    _write_user_patterns(updated_user_patterns, pattern_path)

    del user_color_patterns[normalized_name]
    del army_color_pattern[normalized_name]


builtin_color_patterns = load_builtin_patterns()
user_color_patterns, user_pattern_load_issue = load_user_patterns_for_startup()

try:
    # Compatibility view used by the existing GUI until it adopts the new API.
    army_color_pattern = get_all_patterns()
except PatternNameConflictError as exc:
    user_pattern_path = Path(get_user_patterns_path()).resolve()
    LOGGER.exception(
        "User-pattern file conflicts with built-in patterns: %s",
        user_pattern_path,
    )
    user_pattern_load_issue = UserPatternLoadIssue(user_pattern_path, exc)
    user_color_patterns = OrderedDict()
    army_color_pattern = get_all_patterns()
