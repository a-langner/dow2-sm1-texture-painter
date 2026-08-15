"""Stable processing-mode identities independent of presentation widgets."""

from enum import Enum


class ProcessingMode(Enum):
    """Choose one global processing context or four per-colour contexts."""

    GLOBAL = "global"
    PER_COLOR = "per_color"

    @property
    def display_name(self) -> str:
        return _PROCESSING_MODE_DISPLAY_NAMES[self]

    @classmethod
    def parse(cls, value: object) -> "ProcessingMode":
        """Parse a stable ID, display name, or existing enum value."""
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError(f"Unknown processing mode: {value!r}")
        normalized = value.strip().casefold()
        for mode in cls:
            if normalized in (mode.value.casefold(), mode.display_name.casefold()):
                return mode
        raise ValueError(f"Unknown processing mode: {value!r}")

    @classmethod
    def from_stored(cls, value: object | None) -> "ProcessingMode":
        """Resolve a missing legacy field to Global, otherwise parse it."""
        if value is None:
            return cls.GLOBAL
        return cls.parse(value)


_PROCESSING_MODE_DISPLAY_NAMES = {
    ProcessingMode.GLOBAL: "Global",
    ProcessingMode.PER_COLOR: "Per Color",
}

DEFAULT_PROCESSING_MODE = ProcessingMode.GLOBAL
