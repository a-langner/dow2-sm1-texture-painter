"""Immutable parameters that determine texture-rendering pixels."""

from dataclasses import dataclass, field, replace
import re

from src.color_processing_settings import (
    DEFAULT_COLOR_PROCESSING_SETTINGS,
    MAX_BRIGHTNESS,
    MAX_CONTRAST,
    MIN_BRIGHTNESS,
    MIN_CONTRAST,
    ColorProcessingSettings,
    validate_processing_level,
)
from src.color_slot import ColorSlot
from src.constant import ColorOps
from src.processing_mode import ProcessingMode

DEFAULT_COLOR = "#808080"
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
PerColorProcessingSettings = tuple[
    ColorProcessingSettings,
    ColorProcessingSettings,
    ColorProcessingSettings,
    ColorProcessingSettings,
]


def _default_per_color_processing() -> PerColorProcessingSettings:
    return (DEFAULT_COLOR_PROCESSING_SETTINGS,) * 4


def _validate_color(value: str, field_name: str) -> None:
    if not isinstance(value, str) or _HEX_COLOR.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a #RRGGBB colour string.")


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
    processing_mode: ProcessingMode = ProcessingMode.GLOBAL
    active_color_slot: ColorSlot = ColorSlot.COLOR_1
    tem_selected: tuple[int, ...] = ()
    per_color_processing: PerColorProcessingSettings = field(
        default_factory=_default_per_color_processing
    )
    _per_color_processing_initialized: bool = field(
        default=False,
        repr=False,
    )

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
        if not isinstance(self.color_op, ColorOps):
            raise ValueError("color_op must be a ColorOps value.")
        if not isinstance(self.processing_mode, ProcessingMode):
            raise ValueError("processing_mode must be a ProcessingMode value.")
        if not isinstance(self.active_color_slot, ColorSlot):
            raise ValueError("active_color_slot must be a ColorSlot value.")
        if not isinstance(self.per_color_processing, tuple) or len(
            self.per_color_processing
        ) != 4:
            raise TypeError(
                "per_color_processing must be a tuple of four settings values."
            )
        if not all(
            isinstance(settings, ColorProcessingSettings)
            for settings in self.per_color_processing
        ):
            raise TypeError(
                "per_color_processing must contain ColorProcessingSettings values."
            )
        if not isinstance(self._per_color_processing_initialized, bool):
            raise TypeError(
                "_per_color_processing_initialized must be a boolean."
            )
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

    @property
    def global_processing(self) -> ColorProcessingSettings:
        """Return the structured form of the established global fields."""
        return ColorProcessingSettings(
            blend_mode=self.color_op,
            brightness=self.brightness,
            contrast=self.contrast,
        )

    @property
    def per_color_processing_initialized(self) -> bool:
        """Report whether the lazy per-colour values have been established."""
        return self._per_color_processing_initialized

    def initialize_per_color_processing(self) -> "RenderSettings":
        """Copy current Global values to all slots exactly once."""
        if self._per_color_processing_initialized:
            return self
        initial: PerColorProcessingSettings = (self.global_processing,) * 4
        return replace(
            self,
            per_color_processing=initial,
            _per_color_processing_initialized=True,
        )

    def with_processing_mode(self, mode: ProcessingMode) -> "RenderSettings":
        """Switch context without changing either retained settings set."""
        settings = self
        if mode is ProcessingMode.PER_COLOR:
            settings = settings.initialize_per_color_processing()
        return replace(settings, processing_mode=mode)

    def with_active_color_slot(self, slot: ColorSlot) -> "RenderSettings":
        """Select an editing slot without changing colours or processing."""
        if not isinstance(slot, ColorSlot):
            raise TypeError("slot must be a ColorSlot value.")
        return replace(self, active_color_slot=slot)

    def with_global_processing(
        self, settings: ColorProcessingSettings
    ) -> "RenderSettings":
        """Replace the global context while retaining all per-colour values."""
        if not isinstance(settings, ColorProcessingSettings):
            raise TypeError("settings must be a ColorProcessingSettings value.")
        return replace(
            self,
            color_op=settings.blend_mode,
            brightness=settings.brightness,
            contrast=settings.contrast,
        )

    def with_color_processing(
        self,
        slot_index: int,
        settings: ColorProcessingSettings,
    ) -> "RenderSettings":
        """Replace one zero-based colour context without touching the others."""
        if isinstance(slot_index, bool) or not isinstance(slot_index, int):
            raise TypeError("slot_index must be an integer.")
        if not 0 <= slot_index < 4:
            raise ValueError("slot_index must be between 0 and 3.")
        if not isinstance(settings, ColorProcessingSettings):
            raise TypeError("settings must be a ColorProcessingSettings value.")
        initialized = self.initialize_per_color_processing()
        per_color = list(initialized.per_color_processing)
        per_color[slot_index] = settings
        updated: PerColorProcessingSettings = (
            per_color[0],
            per_color[1],
            per_color[2],
            per_color[3],
        )
        return replace(
            initialized,
            per_color_processing=updated,
            _per_color_processing_initialized=True,
        )


DEFAULT_RENDER_SETTINGS = RenderSettings()
