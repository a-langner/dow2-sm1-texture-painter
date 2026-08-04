from src.color_pattern_handler import color_key

PATTERN_EXCHANGE_FORMAT = "sm1-dow2-texture-painter-pattern"
PATTERN_EXCHANGE_VERSION = 1
PATTERN_EXCHANGE_SUFFIX = ".pattern.json"


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
