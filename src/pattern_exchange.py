import json
import logging
import os
from pathlib import Path
import tempfile
from typing import NamedTuple

from src.color_pattern_handler import (
    ARMY_PATTERN_RESOURCE,
    InvalidPatternError,
    PatternAlreadyExistsError,
    PatternNameConflictError,
    PatternNotFoundError,
    color_key,
    get_all_patterns,
    normalize_pattern_colors,
    normalize_pattern_name,
    save_imported_pattern,
)
from src.user_data import get_user_patterns_path

PATTERN_EXCHANGE_FORMAT = "sm1-dow2-texture-painter-pattern"
PATTERN_EXCHANGE_VERSION = 1
PATTERN_EXCHANGE_SUFFIX = ".pattern.json"
PATTERN_COLLECTION_EXCHANGE_FORMAT = "sm1-dow2-texture-painter-pattern-collection"
PATTERN_COLLECTION_EXCHANGE_VERSION = 1
PATTERN_COLLECTION_EXCHANGE_SUFFIX = ".pattern-collection.json"
LOGGER = logging.getLogger(__name__)


class PatternImportError(ValueError):
    """Base class for errors while reading an exchanged pattern."""


class InvalidPatternJsonError(PatternImportError):
    """Raised when imported text is not valid JSON."""


class InvalidPatternFileError(PatternImportError):
    """Raised when valid JSON does not contain a valid pattern document."""


class InvalidImportedPatternNameError(InvalidPatternFileError):
    """Raised when an imported pattern name is missing or invalid."""


class InvalidImportedPatternColorsError(InvalidPatternFileError):
    """Raised when imported pattern colors are missing or invalid."""


class UnsupportedPatternVersionError(PatternImportError):
    """Raised when a pattern document uses an unsupported version."""


class PatternExportError(OSError):
    """Raised when a pattern exchange file cannot be written safely."""


class PatternImportReadError(OSError):
    """Raised when a pattern exchange file cannot be read."""


class PatternFileNotFoundError(PatternImportReadError):
    """Raised when a selected pattern file no longer exists."""


class PatternPermissionDeniedError(PatternImportReadError):
    """Raised when a selected pattern file cannot be read due to permissions."""


class PatternExportPermissionDeniedError(PatternExportError):
    """Raised when an export destination cannot be written due to permissions."""


class BuiltinPatternImportConflictError(PatternImportError):
    """Raised when an import targets a built-in pattern name."""


class UserPatternImportConflictError(PatternImportError):
    """Raised when an import targets an existing user pattern name."""


class InvalidPatternImportNameError(PatternImportError):
    """Raised when an imported pattern's replacement name is invalid."""


class ImportedPattern(NamedTuple):
    name: str
    colors: dict


def create_pattern_exchange_entry(name, pattern):
    """Create the shared name-and-colors structure for one pattern."""
    return {
        "name": name,
        "colors": {key: pattern[key] for key in color_key},
    }


def create_pattern_exchange_document(name, pattern):
    """Create the versioned document for exchanging one color pattern."""
    return {
        "format": PATTERN_EXCHANGE_FORMAT,
        "version": PATTERN_EXCHANGE_VERSION,
        **create_pattern_exchange_entry(name, pattern),
    }


def create_pattern_collection_exchange_document(name, patterns):
    """Create a versioned collection document from ordered pattern pairs."""
    return {
        "format": PATTERN_COLLECTION_EXCHANGE_FORMAT,
        "version": PATTERN_COLLECTION_EXCHANGE_VERSION,
        "name": name,
        "patterns": [
            create_pattern_exchange_entry(pattern_name, pattern)
            for pattern_name, pattern in patterns
        ],
    }


def has_pattern_exchange_format(document):
    """Return whether a document declares the single-pattern format."""
    return (
        isinstance(document, dict) and document.get("format") == PATTERN_EXCHANGE_FORMAT
    )


def has_supported_pattern_exchange_version(document):
    """Return whether a document declares the supported exchange version."""
    return (
        isinstance(document, dict)
        and type(document.get("version")) is int
        and document["version"] == PATTERN_EXCHANGE_VERSION
    )


def validate_imported_pattern(data):
    """Validate a parsed exchange document and return its normalized form."""
    if not isinstance(data, dict):
        raise InvalidPatternFileError("Pattern file must contain a JSON object")
    if "format" not in data:
        raise InvalidPatternFileError("Pattern file is missing its format identifier")
    if not has_pattern_exchange_format(data):
        raise InvalidPatternFileError("Pattern file has an invalid format identifier")
    if "version" not in data:
        raise InvalidPatternFileError("Pattern file is missing its format version")
    if type(data["version"]) is not int:
        raise InvalidPatternFileError("Pattern file version must be an integer")
    if not has_supported_pattern_exchange_version(data):
        raise UnsupportedPatternVersionError(
            f"Unsupported pattern file version {data['version']!r}; "
            f"supported version is {PATTERN_EXCHANGE_VERSION}"
        )
    if "name" not in data:
        raise InvalidImportedPatternNameError("Pattern file is missing its name")
    if not isinstance(data["name"], str):
        raise InvalidImportedPatternNameError("Pattern file name must be a string")
    if "colors" not in data or not isinstance(data["colors"], dict):
        raise InvalidImportedPatternColorsError(
            "Pattern file must contain a colors object"
        )

    colors = data["colors"]
    missing_keys = [key for key in color_key if key not in colors]
    if missing_keys:
        raise InvalidImportedPatternColorsError(
            "Pattern file is missing required colors: " + ", ".join(missing_keys)
        )

    try:
        normalized_name = normalize_pattern_name(data["name"])
    except InvalidPatternError as exc:
        raise InvalidImportedPatternNameError(str(exc)) from exc
    try:
        normalized_colors = normalize_pattern_colors([colors[key] for key in color_key])
    except InvalidPatternError as exc:
        raise InvalidImportedPatternColorsError(str(exc)) from exc

    return create_pattern_exchange_document(
        normalized_name, dict(zip(color_key, normalized_colors))
    )


def parse_imported_pattern_json(json_text):
    """Parse JSON text separately from validating its pattern content."""
    try:
        data = json.loads(json_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise InvalidPatternJsonError("Pattern file contains invalid JSON") from exc
    return validate_imported_pattern(data)


def read_pattern_file(path):
    """Read and validate one pattern file without resolving name conflicts."""
    path = Path(path)
    try:
        json_text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidPatternJsonError("Pattern file is not valid UTF-8 text") from exc
    except FileNotFoundError as exc:
        raise PatternFileNotFoundError(f'Pattern file was not found: "{path}"') from exc
    except PermissionError as exc:
        raise PatternPermissionDeniedError(
            f'Permission was denied reading pattern file: "{path}"'
        ) from exc
    except OSError as exc:
        raise PatternImportReadError(
            f'Could not read pattern file "{path}": {exc}'
        ) from exc
    document = parse_imported_pattern_json(json_text)
    return ImportedPattern(document["name"], document["colors"])


def import_pattern(
    imported_pattern, target_name=None, overwrite=False, pattern_path=None
):
    """Persist a validated pattern after applying the requested conflict policy."""
    if not isinstance(imported_pattern, ImportedPattern):
        raise InvalidPatternFileError("Imported pattern has not been validated")

    requested_name = imported_pattern.name if target_name is None else target_name
    try:
        normalized_name = normalize_pattern_name(requested_name)
    except InvalidPatternError as exc:
        raise InvalidPatternImportNameError(str(exc)) from exc

    try:
        return save_imported_pattern(
            normalized_name,
            [imported_pattern.colors[key] for key in color_key],
            overwrite=overwrite,
            pattern_path=pattern_path,
        )
    except PatternNameConflictError as exc:
        raise BuiltinPatternImportConflictError(str(exc)) from exc
    except PatternAlreadyExistsError as exc:
        raise UserPatternImportConflictError(str(exc)) from exc


def export_pattern(name, destination):
    """Atomically export one built-in or user pattern to a JSON file."""
    pattern = get_all_patterns().get(name)
    if pattern is None:
        raise PatternNotFoundError(f"Pattern '{name}' does not exist")

    try:
        destination = Path(destination)
    except TypeError as exc:
        raise PatternExportError("Pattern export destination is invalid") from exc
    try:
        protected_destinations = {get_user_patterns_path().resolve()}
        try:
            protected_destinations.add(Path(ARMY_PATTERN_RESOURCE).resolve())
        except TypeError:
            pass
        if destination.resolve() in protected_destinations:
            raise PatternExportError(
                "Pattern source file cannot be used as an export destination: "
                f'"{destination}"'
            )
        if destination.exists() and not destination.is_file():
            raise PatternExportError(
                f'Pattern export destination is not a file: "{destination}"'
            )
        if not destination.parent.is_dir():
            raise PatternExportError(
                f'Pattern export directory does not exist: "{destination.parent}"'
            )
    except PermissionError as exc:
        raise PatternExportPermissionDeniedError(
            f'Permission was denied accessing export destination "{destination}"'
        ) from exc
    except PatternExportError:
        raise
    except OSError as exc:
        raise PatternExportError(
            f'Could not access pattern export destination "{destination}": {exc}'
        ) from exc

    document = create_pattern_exchange_document(name, pattern)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as fp:
            temporary_path = Path(fp.name)
            json.dump(document, fp, indent=2, ensure_ascii=False)
            fp.write("\n")
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
    except PermissionError as exc:
        raise PatternExportPermissionDeniedError(
            f'Permission was denied exporting pattern to "{destination}"'
        ) from exc
    except OSError as exc:
        raise PatternExportError(
            f'Could not export pattern to "{destination}": {exc}'
        ) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                LOGGER.warning(
                    "Could not remove failed Pattern export temporary file: %s",
                    temporary_path,
                    exc_info=True,
                )
