"""Stable identities for the four positional team-colour slots."""

from enum import Enum


class ColorSlot(Enum):
    """Identify a team-colour slot independently of its current RGB value."""

    COLOR_1 = "color_1"
    COLOR_2 = "color_2"
    COLOR_3 = "color_3"
    COLOR_4 = "color_4"

    @property
    def index(self) -> int:
        return _COLOR_SLOT_INDEXES[self]

    @property
    def display_name(self) -> str:
        return f"Color {self.index + 1}"

    @classmethod
    def parse(cls, value: object) -> "ColorSlot":
        """Parse a stable ID, display name, or existing slot value."""
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError(f"Unknown color slot: {value!r}")
        normalized = value.strip().casefold()
        for slot in cls:
            if normalized in (slot.value.casefold(), slot.display_name.casefold()):
                return slot
        raise ValueError(f"Unknown color slot: {value!r}")

    @classmethod
    def from_index(cls, index: int) -> "ColorSlot":
        """Resolve one zero-based RGBA/team-colour channel index."""
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError("Color slot index must be an integer.")
        if not 0 <= index < 4:
            raise ValueError("Color slot index must be between 0 and 3.")
        return tuple(cls)[index]


_COLOR_SLOT_INDEXES = {slot: index for index, slot in enumerate(ColorSlot)}
DEFAULT_COLOR_SLOT = ColorSlot.COLOR_1
