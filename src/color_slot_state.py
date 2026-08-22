"""Complete movable state stored at one positional colour slot."""

from dataclasses import dataclass

from src.color_processing_settings import ColorProcessingSettings


@dataclass(frozen=True)
class CustomFavoriteIdentity:
    """Stable display identity attached to a color copied from Favorites."""

    id: str
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("custom Favorite id must not be empty.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("custom Favorite name must not be empty.")


@dataclass(frozen=True)
class ColorSlotState:
    """Pair one slot colour with all processing that moves with it."""

    color: str
    processing: ColorProcessingSettings
    custom_favorite: CustomFavoriteIdentity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.color, str):
            raise TypeError("color must be a string.")
        if not isinstance(self.processing, ColorProcessingSettings):
            raise TypeError("processing must be ColorProcessingSettings.")
        if self.custom_favorite is not None and not isinstance(
            self.custom_favorite, CustomFavoriteIdentity
        ):
            raise TypeError("custom_favorite must be CustomFavoriteIdentity or None.")


ColorSlotStates = tuple[
    ColorSlotState,
    ColorSlotState,
    ColorSlotState,
    ColorSlotState,
]
