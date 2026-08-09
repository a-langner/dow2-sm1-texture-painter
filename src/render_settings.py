"""Immutable parameters that determine texture-rendering pixels."""

from dataclasses import dataclass
import re

from src.constant import ColorOps

DEFAULT_COLOR = "#808080"
MIN_BRIGHTNESS = 0.0
MAX_BRIGHTNESS = 150.0
MIN_CONTRAST = 0.0
MAX_CONTRAST = 200.0
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")


def _validate_color(value: str, field_name: str) -> None:
    if not isinstance(value, str) or _HEX_COLOR.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a #RRGGBB colour string.")


def _validate_level(
    value: float,
    field_name: str,
    minimum: float,
    maximum: float,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number.")
    if not minimum <= value <= maximum:
        raise ValueError(f"{field_name} must be between {minimum:g} and {maximum:g}.")


@dataclass(frozen=True)
class RenderSettings:
    """Complete worker-safe description of pixel-affecting settings."""

    primary_color: str = DEFAULT_COLOR
    secondary_color: str = DEFAULT_COLOR
    tint_color: str = DEFAULT_COLOR
    extra_color: str = DEFAULT_COLOR
    brightness: float = 75.0
    contrast: float = 100.0
    apply_alpha: bool = False
    apply_dirt: bool = False
    apply_spec: bool = False
    color_op: ColorOps = ColorOps.OVERLAY
    tem_selected: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        for field_name, value in zip(
            (
                "primary_color",
                "secondary_color",
                "tint_color",
                "extra_color",
            ),
            self.colors,
        ):
            _validate_color(value, field_name)
        _validate_level(
            self.brightness,
            "brightness",
            MIN_BRIGHTNESS,
            MAX_BRIGHTNESS,
        )
        _validate_level(
            self.contrast,
            "contrast",
            MIN_CONTRAST,
            MAX_CONTRAST,
        )
        if not isinstance(self.color_op, ColorOps):
            raise ValueError("color_op must be a ColorOps value.")
        if not isinstance(self.tem_selected, tuple) or not all(
            isinstance(index, int) and not isinstance(index, bool)
            for index in self.tem_selected
        ):
            raise TypeError("tem_selected must be a tuple of integer indices.")
        if any(index < 0 for index in self.tem_selected):
            raise ValueError("tem_selected indices cannot be negative.")
        for field_name in ("apply_alpha", "apply_dirt", "apply_spec"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a boolean.")

    @property
    def colors(self) -> tuple[str, str, str, str]:
        return (
            self.primary_color,
            self.secondary_color,
            self.tint_color,
            self.extra_color,
        )


DEFAULT_RENDER_SETTINGS = RenderSettings()
