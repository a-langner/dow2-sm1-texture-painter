"""Reusable processing values for one team-colour context."""

from dataclasses import dataclass

from src.blend_mode import BlendMode

MIN_BRIGHTNESS = 0.0
MAX_BRIGHTNESS = 150.0
MIN_CONTRAST = 0.0
MAX_CONTRAST = 200.0
MIN_OPACITY = 0.0
MAX_OPACITY = 100.0


def validate_processing_level(
    value: float,
    field_name: str,
    minimum: float,
    maximum: float,
) -> None:
    """Validate one numeric processing level without coercion or clamping."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number.")
    if not minimum <= value <= maximum:
        raise ValueError(
            f"{field_name} must be between {minimum:g} and {maximum:g}."
        )


@dataclass(frozen=True)
class ColorProcessingSettings:
    """Blend and level settings reusable for global or per-colour rendering."""

    blend_mode: BlendMode = BlendMode.OVERLAY
    brightness: float = 75.0
    contrast: float = 100.0
    opacity: float = 100.0

    def __post_init__(self) -> None:
        if not isinstance(self.blend_mode, BlendMode):
            raise ValueError("blend_mode must be a BlendMode value.")
        validate_processing_level(
            self.brightness,
            "brightness",
            MIN_BRIGHTNESS,
            MAX_BRIGHTNESS,
        )
        validate_processing_level(
            self.contrast,
            "contrast",
            MIN_CONTRAST,
            MAX_CONTRAST,
        )
        validate_processing_level(
            self.opacity,
            "opacity",
            MIN_OPACITY,
            MAX_OPACITY,
        )


DEFAULT_COLOR_PROCESSING_SETTINGS = ColorProcessingSettings()
