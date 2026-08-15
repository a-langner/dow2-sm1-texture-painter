"""Authoritative blend-mode identities and presentation labels."""

from enum import Enum


class BlendMode(Enum):
    """Stable blend identifiers shared by rendering, UI, and persistence."""

    NORMAL = "normal"
    MULTIPLY = "multiply"
    SCREEN = "screen"
    OVERLAY = "overlay"
    SOFT_LIGHT = "soft_light"
    HARD_LIGHT = "hard_light"
    COLOR = "color"
    LINEAR_BURN = "linear_burn"
    LINEAR_DODGE = "linear_dodge"

    @property
    def display_name(self) -> str:
        return _BLEND_MODE_DISPLAY_NAMES[self]

    @classmethod
    def parse(cls, value: object) -> "BlendMode":
        """Parse a stable ID or a legacy/display name."""
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError(f"Unknown blend mode: {value!r}")
        normalized = value.strip().casefold()
        for mode in cls:
            if normalized in (mode.value.casefold(), mode.display_name.casefold()):
                return mode
        raise ValueError(f"Unknown blend mode: {value!r}")


_BLEND_MODE_DISPLAY_NAMES = {
    BlendMode.NORMAL: "Normal",
    BlendMode.MULTIPLY: "Multiply",
    BlendMode.SCREEN: "Screen",
    BlendMode.OVERLAY: "Overlay",
    BlendMode.SOFT_LIGHT: "Soft Light",
    BlendMode.HARD_LIGHT: "Hard Light",
    BlendMode.COLOR: "Color",
    BlendMode.LINEAR_BURN: "Linear Burn",
    BlendMode.LINEAR_DODGE: "Linear Dodge (Add)",
}

# Only these modes have pixel implementations before Jobs 3-8.
IMPLEMENTED_BLEND_MODES = (
    BlendMode.NORMAL,
    BlendMode.MULTIPLY,
    BlendMode.SCREEN,
    BlendMode.OVERLAY,
)
