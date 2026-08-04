import json
import os
from pathlib import Path
import tempfile

from src.color_pattern_handler import (
    ARMY_PATTERN_RESOURCE,
    InvalidPatternError,
    PatternNotFoundError,
    color_key,
    get_all_patterns,
    normalize_pattern_colors,
    normalize_pattern_name,
)
from src.user_data import get_user_patterns_path

PATTERN_EXCHANGE_FORMAT = "sm1-dow2-texture-painter-pattern"
PATTERN_EXCHANGE_VERSION = 1
PATTERN_EXCHANGE_SUFFIX = ".pattern.json"


class PatternImportError(ValueError):
    """Base class for errors while reading an exchanged pattern."""


class InvalidPatternJsonError(PatternImportError):
    """Raised when imported text is not valid JSON."""


class InvalidPatternFileError(PatternImportError):
    """Raised when valid JSON does not contain a valid pattern document."""


class UnsupportedPatternVersionError(PatternImportError):
    """Raised when a pattern document uses an unsupported version."""


class PatternExportError(OSError):
    """Raised when a pattern exchange file cannot be written safely."""


def create_pattern_exchange_document(name, pattern):
    """Create the versioned document for exchanging one color pattern."""
    return {
        "format": PATTERN_EXCHANGE_FORMAT,
        "version": PATTERN_EXCHANGE_VERSION,
        "name": name,
        "colors": {key: pattern[key] for key in color_key},
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
        raise InvalidPatternFileError("Pattern file is missing its name")
    if not isinstance(data["name"], str):
        raise InvalidPatternFileError("Pattern file name must be a string")
    if "colors" not in data or not isinstance(data["colors"], dict):
        raise InvalidPatternFileError("Pattern file must contain a colors object")

    colors = data["colors"]
    missing_keys = [key for key in color_key if key not in colors]
    if missing_keys:
        raise InvalidPatternFileError(
            "Pattern file is missing required colors: " + ", ".join(missing_keys)
        )

    try:
        normalized_name = normalize_pattern_name(data["name"])
        normalized_colors = normalize_pattern_colors([colors[key] for key in color_key])
    except InvalidPatternError as exc:
        raise InvalidPatternFileError(str(exc)) from exc

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


def export_pattern(name, destination):
    """Atomically export one built-in or user pattern to a JSON file."""
    pattern = get_all_patterns().get(name)
    if pattern is None:
        raise PatternNotFoundError(f"Pattern '{name}' does not exist")

    try:
        destination = Path(destination)
    except TypeError as exc:
        raise PatternExportError("Pattern export destination is invalid") from exc
    protected_destinations = {get_user_patterns_path().resolve()}
    try:
        protected_destinations.add(Path(ARMY_PATTERN_RESOURCE).resolve())
    except TypeError:
        pass
    if destination.resolve() in protected_destinations:
        raise PatternExportError(
            f'Pattern source file cannot be used as an export destination: "{destination}"'
        )
    if destination.exists() and not destination.is_file():
        raise PatternExportError(
            f'Pattern export destination is not a file: "{destination}"'
        )
    if not destination.parent.is_dir():
        raise PatternExportError(
            f'Pattern export directory does not exist: "{destination.parent}"'
        )

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
    except OSError as exc:
        raise PatternExportError(
            f'Could not export pattern to "{destination}": {exc}'
        ) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
