import json
import logging
import os
from pathlib import Path
import re
import tempfile
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from typing import NamedTuple, TypedDict, cast

from src.color_pattern_handler import (
    ARMY_PATTERN_RESOURCE,
    InvalidPatternError,
    PatternAlreadyExistsError,
    PatternNameConflictError,
    PatternNotFoundError,
    StoredPattern,
    builtin_color_patterns,
    color_key,
    get_all_patterns,
    is_user_pattern,
    normalize_pattern_colors,
    normalize_pattern_name,
    save_imported_pattern,
    replace_user_patterns,
    user_color_patterns,
)
from src.user_data import get_settings_path, get_user_patterns_path

PATTERN_EXCHANGE_FORMAT = "dow2-sm1-texture-painter-pattern"
PATTERN_EXCHANGE_VERSION = 1
PATTERN_EXCHANGE_SUFFIX = ".pattern.json"
PATTERN_COLLECTION_EXCHANGE_FORMAT = "dow2-sm1-texture-painter-pattern-collection"
PATTERN_COLLECTION_EXCHANGE_VERSION = 1
PATTERN_COLLECTION_EXCHANGE_SUFFIX = ".pattern-collection.json"
LOGGER = logging.getLogger(__name__)


class PatternExchangeDocument(TypedDict):
    format: str
    version: int
    name: str
    colors: dict[str, str]

WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def suggested_exchange_filename(
    name: str,
    suffix: str,
    fallback_name: str,
) -> str:
    """Return a portable exchange filename for the supplied canonical suffix."""
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    safe_name = safe_name.rstrip(" .")
    if not safe_name:
        safe_name = fallback_name
    windows_stem = safe_name.split(".", 1)[0].rstrip(" .").upper()
    if windows_stem in WINDOWS_RESERVED_FILENAMES:
        safe_name = f"_{safe_name}"
    if not safe_name.casefold().endswith(suffix.casefold()):
        safe_name += suffix
    return safe_name


def suggested_pattern_filename(pattern_name: str) -> str:
    """Return a portable filename while preserving the internal pattern name."""
    return suggested_exchange_filename(pattern_name, PATTERN_EXCHANGE_SUFFIX, "pattern")


def suggested_pattern_collection_filename(collection_name: str) -> str:
    """Return a portable filename for a Pattern Collection."""
    return suggested_exchange_filename(
        collection_name,
        PATTERN_COLLECTION_EXCHANGE_SUFFIX,
        "pattern-collection",
    )


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


class PatternCollectionImportError(PatternImportError):
    """Base class for invalid imported Pattern Collection data."""


class InvalidPatternCollectionError(PatternCollectionImportError):
    """Raised when a Pattern Collection has invalid content or structure."""


class InvalidPatternCollectionFormatError(InvalidPatternCollectionError):
    """Raised when JSON does not declare the Pattern Collection format."""


class UnsupportedPatternCollectionVersionError(PatternCollectionImportError):
    """Raised when a Pattern Collection uses an unsupported version."""


class DuplicatePatternNameInCollectionError(PatternCollectionImportError):
    """Raised when normalized names repeat within a Pattern Collection."""


class PatternCollectionExportError(PatternExportError):
    """Base class for errors while exporting a Pattern Collection."""


class InvalidPatternCollectionNameError(PatternCollectionExportError):
    """Raised when an exported Pattern Collection name is invalid."""


class EmptyUserPatternCollectionError(PatternCollectionExportError):
    """Raised when there are no user-created Patterns to export."""


class StalePatternCollectionAnalysisError(PatternCollectionImportError):
    """Raised when Pattern state changed after collection conflict analysis."""


class CollectionImportResult(NamedTuple):
    imported_count: int
    overwritten_count: int
    skipped_user_conflict_count: int
    skipped_builtin_conflict_count: int


class ImportedPattern(NamedTuple):
    name: str
    colors: dict[str, str]


class ImportedPatternCollection(NamedTuple):
    name: str
    patterns: tuple[ImportedPattern, ...]


class CollectionImportAnalysis(NamedTuple):
    collection_name: str
    new_patterns: tuple[ImportedPattern, ...]
    user_conflicts: tuple[ImportedPattern, ...]
    builtin_conflicts: tuple[ImportedPattern, ...]

    @property
    def total_pattern_count(self) -> int:
        return (
            len(self.new_patterns)
            + len(self.user_conflicts)
            + len(self.builtin_conflicts)
        )

    @property
    def new_pattern_count(self) -> int:
        return len(self.new_patterns)

    @property
    def user_conflict_count(self) -> int:
        return len(self.user_conflicts)

    @property
    def builtin_conflict_count(self) -> int:
        return len(self.builtin_conflicts)


def create_pattern_exchange_entry(
    name: str,
    pattern: Mapping[str, str],
) -> dict[str, object]:
    """Create the shared name-and-colors structure for one pattern."""
    return {
        "name": name,
        "colors": {key: pattern[key] for key in color_key},
    }


def create_pattern_exchange_document(
    name: str,
    pattern: Mapping[str, str],
) -> PatternExchangeDocument:
    """Create the versioned document for exchanging one color pattern."""
    return {
        "format": PATTERN_EXCHANGE_FORMAT,
        "version": PATTERN_EXCHANGE_VERSION,
        "name": name,
        "colors": {key: pattern[key] for key in color_key},
    }


def create_pattern_collection_exchange_document(
    name: str,
    patterns: Iterable[tuple[str, Mapping[str, str]]],
) -> dict[str, object]:
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


def validate_imported_pattern_collection(
    data: object,
) -> ImportedPatternCollection:
    """Validate a collection atomically and return its normalized document."""
    if not isinstance(data, dict):
        raise InvalidPatternCollectionError(
            "Pattern Collection file must contain a JSON object"
        )
    if data.get("format") != PATTERN_COLLECTION_EXCHANGE_FORMAT:
        raise InvalidPatternCollectionFormatError(
            "Pattern Collection has an invalid or missing format identifier"
        )
    if "version" not in data:
        raise InvalidPatternCollectionError(
            "Pattern Collection is missing its format version"
        )
    if type(data["version"]) is not int:
        raise InvalidPatternCollectionError(
            "Pattern Collection version must be an integer"
        )
    if data["version"] != PATTERN_COLLECTION_EXCHANGE_VERSION:
        raise UnsupportedPatternCollectionVersionError(
            f"Unsupported Pattern Collection version {data['version']!r}; "
            f"supported version is {PATTERN_COLLECTION_EXCHANGE_VERSION}"
        )
    if "name" not in data or not isinstance(data["name"], str):
        raise InvalidPatternCollectionError("Pattern Collection name must be a string")
    try:
        collection_name = normalize_pattern_name(data["name"])
    except InvalidPatternError as exc:
        raise InvalidPatternCollectionError(
            f"Invalid Pattern Collection name: {exc}"
        ) from exc

    if "patterns" not in data:
        raise InvalidPatternCollectionError(
            "Pattern Collection is missing its patterns array"
        )
    if not isinstance(data["patterns"], list):
        raise InvalidPatternCollectionError(
            "Pattern Collection patterns must be a JSON array"
        )
    if not data["patterns"]:
        raise InvalidPatternCollectionError(
            "Pattern Collection must contain at least one Pattern"
        )

    normalized_patterns: list[ImportedPattern] = []
    normalized_names: set[str] = set()
    for index, entry in enumerate(data["patterns"]):
        if not isinstance(entry, dict):
            raise InvalidPatternCollectionError(
                f"Pattern entry {index} must be a JSON object"
            )
        raw_name = entry.get("name")
        entry_description = f"Pattern entry {index}"
        if isinstance(raw_name, str):
            entry_description += f" ({raw_name!r})"
        try:
            normalized = validate_imported_pattern(
                {
                    "format": PATTERN_EXCHANGE_FORMAT,
                    "version": PATTERN_EXCHANGE_VERSION,
                    "name": raw_name,
                    "colors": entry.get("colors"),
                }
            )
        except PatternImportError as exc:
            raise InvalidPatternCollectionError(
                f"{entry_description} is invalid: {exc}"
            ) from exc

        pattern_name = normalized["name"]
        if pattern_name in normalized_names:
            raise DuplicatePatternNameInCollectionError(
                f"Duplicate Pattern name {pattern_name!r} at entry {index}"
            )
        normalized_names.add(pattern_name)
        normalized_patterns.append(ImportedPattern(pattern_name, normalized["colors"]))

    return ImportedPatternCollection(collection_name, tuple(normalized_patterns))


def parse_imported_pattern_collection_json(
    json_text: str,
) -> ImportedPatternCollection:
    """Parse and validate one Pattern Collection JSON document."""
    try:
        data: object = json.loads(json_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise InvalidPatternJsonError(
            "Pattern Collection file contains invalid JSON"
        ) from exc
    return validate_imported_pattern_collection(data)


def read_pattern_collection_file(path: Path) -> ImportedPatternCollection:
    """Read and validate one Pattern Collection without importing it."""
    path = Path(path)
    try:
        json_text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidPatternJsonError(
            "Pattern Collection file is not valid UTF-8 text"
        ) from exc
    except FileNotFoundError as exc:
        raise PatternFileNotFoundError(
            f'Pattern Collection file was not found: "{path}"'
        ) from exc
    except PermissionError as exc:
        raise PatternPermissionDeniedError(
            f'Permission was denied reading Pattern Collection file: "{path}"'
        ) from exc
    except OSError as exc:
        raise PatternImportReadError(
            f'Could not read Pattern Collection file "{path}": {exc}'
        ) from exc
    return parse_imported_pattern_collection_json(json_text)


def analyze_pattern_collection_import(
    collection: ImportedPatternCollection,
    builtin_patterns: Mapping[str, StoredPattern] | None = None,
    user_patterns: Mapping[str, StoredPattern] | None = None,
) -> CollectionImportAnalysis:
    """Classify a validated collection without selecting a conflict policy."""
    if not isinstance(collection, ImportedPatternCollection):
        raise InvalidPatternCollectionError(
            "Pattern Collection must be validated before conflict analysis"
        )
    if builtin_patterns is None:
        builtin_patterns = builtin_color_patterns
    if user_patterns is None:
        user_patterns = user_color_patterns

    new_patterns: list[ImportedPattern] = []
    user_conflicts: list[ImportedPattern] = []
    builtin_conflicts: list[ImportedPattern] = []
    for pattern in collection.patterns:
        if pattern.name in builtin_patterns:
            builtin_conflicts.append(pattern)
        elif pattern.name in user_patterns:
            user_conflicts.append(pattern)
        else:
            new_patterns.append(pattern)

    return CollectionImportAnalysis(
        collection.name,
        tuple(new_patterns),
        tuple(user_conflicts),
        tuple(builtin_conflicts),
    )


def import_analyzed_pattern_collection(
    analysis: CollectionImportAnalysis,
    overwrite_user_conflicts: bool = False,
    pattern_path: Path | None = None,
) -> CollectionImportResult:
    """Apply one analyzed collection through a single atomic user-data write."""
    if not isinstance(analysis, CollectionImportAnalysis):
        raise InvalidPatternCollectionError(
            "Pattern Collection must be analyzed before batch import"
        )
    if type(overwrite_user_conflicts) is not bool:
        raise InvalidPatternCollectionError(
            "overwrite_user_conflicts must be a boolean"
        )

    for pattern in analysis.new_patterns:
        if (
            pattern.name in builtin_color_patterns
            or pattern.name in user_color_patterns
        ):
            raise StalePatternCollectionAnalysisError(
                f"Pattern state changed after analysis for {pattern.name!r}"
            )
    for pattern in analysis.user_conflicts:
        if (
            pattern.name in builtin_color_patterns
            or pattern.name not in user_color_patterns
        ):
            raise StalePatternCollectionAnalysisError(
                f"Pattern state changed after analysis for {pattern.name!r}"
            )
    for pattern in analysis.builtin_conflicts:
        if pattern.name not in builtin_color_patterns:
            raise StalePatternCollectionAnalysisError(
                f"Pattern state changed after analysis for {pattern.name!r}"
            )

    final_patterns = OrderedDict(user_color_patterns)
    for pattern in analysis.new_patterns:
        final_patterns[pattern.name] = OrderedDict(pattern.colors)

    overwritten_count = 0
    skipped_user_conflict_count = len(analysis.user_conflicts)
    if overwrite_user_conflicts:
        for pattern in analysis.user_conflicts:
            final_patterns[pattern.name] = OrderedDict(pattern.colors)
        overwritten_count = len(analysis.user_conflicts)
        skipped_user_conflict_count = 0

    imported_count = len(analysis.new_patterns)
    result = CollectionImportResult(
        imported_count,
        overwritten_count,
        skipped_user_conflict_count,
        len(analysis.builtin_conflicts),
    )
    if imported_count == 0 and overwritten_count == 0:
        return result
    if final_patterns == user_color_patterns:
        return result

    replace_user_patterns(final_patterns, pattern_path=pattern_path)
    return result


def has_pattern_exchange_format(document: object) -> bool:
    """Return whether a document declares the single-pattern format."""
    return (
        isinstance(document, dict) and document.get("format") == PATTERN_EXCHANGE_FORMAT
    )


def has_supported_pattern_exchange_version(document: object) -> bool:
    """Return whether a document declares the supported exchange version."""
    return (
        isinstance(document, dict)
        and type(document.get("version")) is int
        and document["version"] == PATTERN_EXCHANGE_VERSION
    )


def validate_imported_pattern(data: object) -> PatternExchangeDocument:
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


def parse_imported_pattern_json(json_text: str) -> PatternExchangeDocument:
    """Parse JSON text separately from validating its pattern content."""
    try:
        data: object = json.loads(json_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise InvalidPatternJsonError("Pattern file contains invalid JSON") from exc
    return validate_imported_pattern(data)


def read_pattern_file(path: Path) -> ImportedPattern:
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
    imported_pattern: ImportedPattern,
    target_name: str | None = None,
    overwrite: bool = False,
    pattern_path: Path | None = None,
) -> str:
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


def export_pattern(name: str, destination: Path) -> None:
    """Atomically export one built-in or user pattern to a JSON file."""
    pattern = get_all_patterns().get(name)
    if pattern is None:
        raise PatternNotFoundError(f"Pattern '{name}' does not exist")

    colors = {key: cast(str, pattern[key]) for key in color_key}
    document = create_pattern_exchange_document(name, colors)
    _write_exchange_document(document, destination)


def export_user_pattern_collection(
    collection_name: str,
    destination: Path,
) -> None:
    """Atomically export every user-created Pattern in deterministic order."""
    try:
        normalized_collection_name = normalize_pattern_name(collection_name)
    except InvalidPatternError as exc:
        raise InvalidPatternCollectionNameError(str(exc)) from exc

    user_patterns = [
        (name, {key: cast(str, pattern[key]) for key in color_key})
        for name, pattern in get_all_patterns().items()
        if is_user_pattern(name)
    ]
    if not user_patterns:
        raise EmptyUserPatternCollectionError(
            "There are no user-created Patterns to export"
        )

    document = create_pattern_collection_exchange_document(
        normalized_collection_name, user_patterns
    )
    _write_exchange_document(document, destination)


def _validate_export_destination(destination: Path) -> Path:
    try:
        destination = Path(destination)
    except TypeError as exc:
        raise PatternExportError("Pattern export destination is invalid") from exc
    try:
        protected_destinations = {
            get_user_patterns_path().resolve(),
            get_settings_path().resolve(),
        }
        try:
            protected_destinations.add(
                # ``Traversable`` implementations are path-like for the
                # filesystem-backed packaged resource used at runtime.
                Path(ARMY_PATTERN_RESOURCE).resolve()  # type: ignore[arg-type]
            )
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
    return destination


def _write_exchange_document(
    document: Mapping[str, object],
    destination: Path,
) -> None:
    """Write an exchange document atomically without touching its sources."""
    destination = _validate_export_destination(destination)
    temporary_path: Path | None = None
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
