from collections import OrderedDict
import json
from importlib import resources
from pathlib import Path

from src.user_data import get_user_patterns_path


RESOURCE_ROOT = resources.files("src.resources")
ARMY_PATTERN_RESOURCE = RESOURCE_ROOT.joinpath("army_pattern.json")

color_key = [
    "primary_colour_name",
    "secondary_colour_name",
    "tint_colour_name",
    "extra_colour_name",
]


def _load_pattern_file(pattern_file):
    with pattern_file.open("r", encoding="utf-8") as fp:
        patterns = json.load(fp, object_pairs_hook=OrderedDict)

    if not isinstance(patterns, dict):
        raise ValueError("Pattern data must be a JSON object")

    return OrderedDict(patterns)


def load_builtin_patterns(pattern_resource=None):
    """Load the ordered, read-only pattern collection bundled with the app."""
    if pattern_resource is None:
        pattern_resource = ARMY_PATTERN_RESOURCE
    return _load_pattern_file(pattern_resource)


def load_user_patterns(pattern_path=None):
    """Load ordered user patterns, or return an empty collection if absent."""
    if pattern_path is None:
        pattern_path = get_user_patterns_path()
    pattern_path = Path(pattern_path)

    if not pattern_path.is_file():
        return OrderedDict()

    return _load_pattern_file(pattern_path)


def get_all_patterns(builtin_patterns=None, user_patterns=None):
    """Return built-in patterns followed by user patterns without collisions."""
    if builtin_patterns is None:
        builtin_patterns = builtin_color_patterns
    if user_patterns is None:
        user_patterns = user_color_patterns

    duplicate_names = set(builtin_patterns).intersection(user_patterns)
    if duplicate_names:
        names = ", ".join(sorted(duplicate_names))
        raise ValueError(
            f"User pattern names conflict with built-in patterns: {names}"
        )

    combined_patterns = OrderedDict(builtin_patterns)
    combined_patterns.update(user_patterns)
    return combined_patterns


def is_user_pattern(name):
    return name in user_color_patterns


def save(name: str, colors: list):
    raise NotImplementedError("User-pattern saving is not implemented yet")


def delete(name: str):
    raise NotImplementedError("User-pattern deletion is not implemented yet")


builtin_color_patterns = load_builtin_patterns()
user_color_patterns = load_user_patterns()

# Compatibility view used by the existing GUI until it adopts the new API.
army_color_pattern = get_all_patterns()
