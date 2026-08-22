"""Typed loading and validation for bundled paint catalogs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import resources
import json
import logging
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable


LOGGER = logging.getLogger(__name__)
RGBColor = tuple[int, int, int]
CITADEL_CATALOG_RESOURCE = (
    resources.files("src.resources").joinpath("paints").joinpath("citadel.json")
)


class PaintCatalogError(ValueError):
    """Raised when a paint catalog cannot be loaded or validated."""


@dataclass(frozen=True)
class PaintColor:
    id: str
    name: str
    r: int
    g: int
    b: int


@dataclass(frozen=True)
class PaintCatalog:
    paints: tuple[PaintColor, ...]
    _rgb_index: Mapping[RGBColor, PaintColor] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _id_index: Mapping[str, PaintColor] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        rgb_index: dict[RGBColor, PaintColor] = {}
        id_index: dict[str, PaintColor] = {}
        for paint in self.paints:
            # Catalog order is authoritative when multiple products share RGB.
            rgb_index.setdefault((paint.r, paint.g, paint.b), paint)
            id_index.setdefault(paint.id, paint)
        object.__setattr__(self, "_rgb_index", MappingProxyType(rgb_index))
        object.__setattr__(self, "_id_index", MappingProxyType(id_index))

    def find_exact_rgb(self, rgb: RGBColor) -> PaintColor | None:
        """Return the first catalog paint with exactly matching RGB channels."""
        return self._rgb_index.get(rgb)

    def find_by_id(self, paint_id: str) -> PaintColor | None:
        """Return the catalog paint with the exact stable identifier."""
        return self._id_index.get(paint_id)


def _required_string(entry: dict[str, object], field: str, index: int) -> str:
    value = entry.get(field)
    if not isinstance(value, str) or not value:
        raise PaintCatalogError(
            f"Paint entry {index} has an invalid or missing '{field}' field"
        )
    return value


def _required_rgb(rgb: dict[str, object], channel: str, index: int) -> int:
    value = rgb.get(channel)
    if type(value) is not int or not 0 <= value <= 255:
        raise PaintCatalogError(
            f"Paint entry {index} RGB channel '{channel}' must be an integer "
            "between 0 and 255"
        )
    return value


def _parse_catalog(document: object) -> PaintCatalog:
    if not isinstance(document, dict):
        raise PaintCatalogError("Paint catalog must contain a JSON object")

    paint_entries = document.get("paints")
    if not isinstance(paint_entries, list) or not paint_entries:
        raise PaintCatalogError("Paint catalog must contain a non-empty 'paints' list")

    paints: list[PaintColor] = []
    for index, candidate in enumerate(paint_entries, start=1):
        if not isinstance(candidate, dict):
            raise PaintCatalogError(f"Paint entry {index} must be a JSON object")

        rgb = candidate.get("rgb")
        if not isinstance(rgb, dict):
            raise PaintCatalogError(
                f"Paint entry {index} has an invalid or missing 'rgb' object"
            )

        paints.append(
            PaintColor(
                id=_required_string(candidate, "id", index),
                name=_required_string(candidate, "name", index),
                r=_required_rgb(rgb, "r", index),
                g=_required_rgb(rgb, "g", index),
                b=_required_rgb(rgb, "b", index),
            )
        )

    return PaintCatalog(paints=tuple(paints))


def load_citadel_catalog(
    catalog_resource: Traversable | None = None,
) -> PaintCatalog:
    """Load the bundled Citadel catalog, or raise a useful catalog error."""
    if catalog_resource is None:
        catalog_resource = CITADEL_CATALOG_RESOURCE

    try:
        with catalog_resource.open("r", encoding="utf-8") as catalog_file:
            document: object = json.load(catalog_file)
        return _parse_catalog(document)
    except json.JSONDecodeError as exc:
        error = PaintCatalogError(
            f"Citadel paint catalog contains invalid JSON at line {exc.lineno}"
        )
    except (OSError, UnicodeError) as exc:
        error = PaintCatalogError(f"Could not read Citadel paint catalog: {exc}")
    except PaintCatalogError as exc:
        error = exc

    LOGGER.error("Could not load Citadel paint catalog: %s", error)
    raise error
