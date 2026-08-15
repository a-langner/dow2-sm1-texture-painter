"""Game-agnostic metadata for one team-colour mask variant."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TeamColorMaskVariant:
    """Describe one default or positively numbered team-colour mask file."""

    variant_index: int | None
    path: Path

    def __post_init__(self) -> None:
        if self.variant_index is not None and (
            type(self.variant_index) is not int or self.variant_index <= 0
        ):
            raise ValueError("A numbered mask variant requires a positive integer.")
        if not isinstance(self.path, Path):
            raise TypeError("Mask variant path must be a Path.")
        object.__setattr__(self, "path", self.path.resolve())

    @property
    def display_name(self) -> str:
        return (
            "Default"
            if self.variant_index is None
            else f"Variant {self.variant_index}"
        )

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def is_default(self) -> bool:
        return self.variant_index is None

    @property
    def sort_key(self) -> tuple[int, int]:
        """Sort Default first, followed by numbered variants numerically."""
        if self.variant_index is None:
            return 0, 0
        return 1, self.variant_index
