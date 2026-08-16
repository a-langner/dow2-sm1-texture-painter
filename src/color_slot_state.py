"""Complete movable state stored at one positional colour slot."""

from dataclasses import dataclass

from src.color_processing_settings import ColorProcessingSettings


@dataclass(frozen=True)
class ColorSlotState:
    """Pair one slot colour with all processing that moves with it."""

    color: str
    processing: ColorProcessingSettings

    def __post_init__(self) -> None:
        if not isinstance(self.color, str):
            raise TypeError("color must be a string.")
        if not isinstance(self.processing, ColorProcessingSettings):
            raise TypeError("processing must be ColorProcessingSettings.")


ColorSlotStates = tuple[
    ColorSlotState,
    ColorSlotState,
    ColorSlotState,
    ColorSlotState,
]
