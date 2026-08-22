"""Stable domain identities for unified Citadel and Custom Favorites."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias
from uuid import uuid4

from src.color_picker_visual import normalize_rgb_hex, rgb_hex_to_channels
from src.paint_catalog import PaintCatalog


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


@dataclass(frozen=True)
class FavoriteAddResult:
    """Report the resolved Favorite identity and whether it was newly stored."""

    favorite: FavoriteColor
    added: bool


@dataclass(frozen=True)
class FavoritePaletteColor:
    """Resolved palette presentation shared by both Favorite kinds."""

    id: str
    name: str
    r: int
    g: int
    b: int
    favorite: FavoriteColor


def resolve_exact_citadel_favorite(
    catalog: PaintCatalog,
    color: str,
    explicit_citadel_id: str | None = None,
) -> CitadelFavoriteColor | None:
    """Resolve an exact catalog identity, preferring a matching explicit ID."""
    channels = rgb_hex_to_channels(normalize_rgb_hex(color))
    if explicit_citadel_id is not None:
        explicit_paint = catalog.find_by_id(explicit_citadel_id)
        if explicit_paint is not None and (
            explicit_paint.r,
            explicit_paint.g,
            explicit_paint.b,
        ) == channels:
            return CitadelFavoriteColor(explicit_paint.id)

    canonical_paint = catalog.find_exact_rgb(channels)
    if canonical_paint is None:
        return None
    return CitadelFavoriteColor(canonical_paint.id)


class FavoriteColorLibrary:
    """Unified indexed collection with exact Custom RGB deduplication."""

    def __init__(
        self,
        catalog: PaintCatalog,
        favorites: tuple[FavoriteColor, ...] = (),
    ) -> None:
        self.catalog = catalog
        self._citadel_by_id: dict[str, CitadelFavoriteColor] = {}
        self._custom_by_id: dict[str, CustomFavoriteColor] = {}
        self._custom_by_color: dict[str, CustomFavoriteColor] = {}
        for favorite in favorites:
            self._store_existing(favorite)

    @property
    def favorites(self) -> tuple[FavoriteColor, ...]:
        """Return both Favorite kinds in stable insertion order."""
        return tuple(self._citadel_by_id.values()) + tuple(
            self._custom_by_id.values()
        )

    def palette_colors(self) -> tuple[FavoritePaletteColor, ...]:
        """Resolve unified Favorites into the existing RGB palette shape."""
        colors: list[FavoritePaletteColor] = []
        for favorite in self.favorites:
            if isinstance(favorite, CitadelFavoriteColor):
                paint = self.catalog.find_by_id(favorite.citadel_id)
                if paint is None:
                    continue
                colors.append(
                    FavoritePaletteColor(
                        paint.id,
                        paint.name,
                        paint.r,
                        paint.g,
                        paint.b,
                        favorite,
                    )
                )
            else:
                red, green, blue = rgb_hex_to_channels(favorite.color)
                colors.append(
                    FavoritePaletteColor(
                        f"custom:{favorite.id}",
                        favorite.name,
                        red,
                        green,
                        blue,
                        favorite,
                    )
                )
        return tuple(colors)

    def has_citadel(self, citadel_id: str) -> bool:
        """Return whether one exact catalog identity is a Favorite."""
        return citadel_id in self._citadel_by_id

    def remove_citadel(self, citadel_id: str) -> CitadelFavoriteColor | None:
        """Remove and return one Citadel Favorite, if present."""
        return self._citadel_by_id.pop(citadel_id, None)

    def custom_for_color(self, color: str) -> CustomFavoriteColor | None:
        """Return the Custom Favorite with one exact normalized RGB value."""
        return self._custom_by_color.get(normalize_rgb_hex(color))

    def remove_custom(self, favorite_id: str) -> CustomFavoriteColor | None:
        """Remove and return one Custom Favorite by stable identity."""
        favorite = self._custom_by_id.pop(favorite_id, None)
        if favorite is not None:
            self._custom_by_color.pop(favorite.color, None)
        return favorite

    def rename_custom(
        self,
        favorite_id: str,
        name: str,
    ) -> CustomFavoriteColor | None:
        """Replace only a Custom Favorite's display name."""
        existing = self._custom_by_id.get(favorite_id)
        if existing is None:
            return None
        renamed = CustomFavoriteColor(existing.id, name, existing.color)
        self._custom_by_id[favorite_id] = renamed
        self._custom_by_color[renamed.color] = renamed
        return renamed

    def _store_existing(self, favorite: FavoriteColor) -> bool:
        if isinstance(favorite, CitadelFavoriteColor):
            if (
                self.catalog.find_by_id(favorite.citadel_id) is None
                or favorite.citadel_id in self._citadel_by_id
            ):
                return False
            self._citadel_by_id[favorite.citadel_id] = favorite
            return True
        if (
            favorite.id in self._custom_by_id
            or favorite.color in self._custom_by_color
        ):
            return False
        self._custom_by_id[favorite.id] = favorite
        self._custom_by_color[favorite.color] = favorite
        return True

    def add_color(
        self,
        color: str,
        *,
        custom_name: str = "",
        explicit_citadel_id: str | None = None,
    ) -> FavoriteAddResult:
        """Add or resolve one exact current color through the unified rules."""
        citadel = resolve_exact_citadel_favorite(
            self.catalog,
            color,
            explicit_citadel_id,
        )
        if citadel is not None:
            existing = self._citadel_by_id.get(citadel.citadel_id)
            if existing is not None:
                return FavoriteAddResult(existing, False)
            self._citadel_by_id[citadel.citadel_id] = citadel
            return FavoriteAddResult(citadel, True)

        normalized_color = normalize_rgb_hex(color)
        existing_custom = self._custom_by_color.get(normalized_color)
        if existing_custom is not None:
            return FavoriteAddResult(existing_custom, False)
        custom = CustomFavoriteColor.create(custom_name, normalized_color)
        self._custom_by_id[custom.id] = custom
        self._custom_by_color[custom.color] = custom
        return FavoriteAddResult(custom, True)


def validate_favorite_colors(
    value: object,
    catalog: PaintCatalog,
) -> tuple[FavoriteColor, ...]:
    """Validate independent persisted entries and safely discard bad records."""
    if not isinstance(value, list):
        return ()

    candidates: list[FavoriteColor] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        favorite_type = entry.get("type")
        try:
            if favorite_type == FavoriteColorType.CITADEL.value:
                citadel_id = entry.get("citadel_id")
                if not isinstance(citadel_id, str):
                    continue
                candidates.append(CitadelFavoriteColor(citadel_id))
            elif favorite_type == FavoriteColorType.CUSTOM.value:
                favorite_id = entry.get("id")
                color = entry.get("color")
                name = entry.get("name", "")
                if not isinstance(favorite_id, str) or not isinstance(color, str):
                    continue
                candidates.append(
                    CustomFavoriteColor(
                        favorite_id,
                        name if isinstance(name, str) else "",
                        color,
                    )
                )
        except (TypeError, ValueError):
            continue
    return FavoriteColorLibrary(catalog, tuple(candidates)).favorites


def serialize_favorite_colors(
    favorites: tuple[FavoriteColor, ...],
) -> list[dict[str, str]]:
    """Serialize compact stable identities without duplicating catalog records."""
    serialized: list[dict[str, str]] = []
    for favorite in favorites:
        if isinstance(favorite, CitadelFavoriteColor):
            serialized.append(
                {
                    "type": favorite.type.value,
                    "citadel_id": favorite.citadel_id,
                }
            )
        else:
            serialized.append(
                {
                    "type": favorite.type.value,
                    "id": favorite.id,
                    "name": favorite.name,
                    "color": favorite.color,
                }
            )
    return serialized
