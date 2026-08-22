"""Stable domain identities for unified Citadel and Custom Favorites."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias
from uuid import uuid4

from src.color_picker_visual import normalize_rgb_hex


class FavoriteColorType(Enum):
    """Stable persisted discriminator for one Favorite Color kind."""

    CITADEL = "citadel"
    CUSTOM = "custom"


@dataclass(frozen=True)
class CitadelFavoriteColor:
    """Reference one immutable catalog record by its stable identifier."""

    citadel_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.citadel_id, str) or not self.citadel_id.strip():
            raise ValueError("citadel_id must be a non-empty string")
        object.__setattr__(self, "citadel_id", self.citadel_id.strip())

    @property
    def type(self) -> FavoriteColorType:
        return FavoriteColorType.CITADEL


@dataclass(frozen=True)
class CustomFavoriteColor:
    """Store one named custom Favorite with authoritative normalized RGB hex."""

    id: str
    name: str
    color: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("id must be a non-empty string")
        if not isinstance(self.name, str):
            raise TypeError("name must be a string")
        if not isinstance(self.color, str):
            raise TypeError("color must be a string")

        normalized_color = normalize_rgb_hex(self.color)
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "name", self.name.strip() or normalized_color)
        object.__setattr__(self, "color", normalized_color)

    @classmethod
    def create(cls, name: str, color: str) -> CustomFavoriteColor:
        """Create a Custom Favorite with a new application-independent identity."""
        return cls(id=uuid4().hex, name=name, color=color)

    @property
    def type(self) -> FavoriteColorType:
        return FavoriteColorType.CUSTOM


FavoriteColor: TypeAlias = CitadelFavoriteColor | CustomFavoriteColor
