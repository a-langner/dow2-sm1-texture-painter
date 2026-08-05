"""Typed, filesystem-independent texture naming conventions.

Profile suffixes include their leading underscore and never include a file
extension. Filename matching is case-insensitive; replacement preserves the
original parent directory and extension exactly.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class TextureKind(Enum):
    """Logical texture roles understood by the application."""

    DIFFUSE = "diffuse"
    TEAM_COLOR = "team_color"
    DIRT = "dirt"
    SPECULAR = "specular"


@dataclass(frozen=True)
class TextureNamingProfile:
    """Immutable mapping from texture roles to filename-stem suffixes."""

    name: str
    diffuse_suffix: str
    team_color_suffix: str
    dirt_suffix: str
    specular_suffix: str

    def __post_init__(self):
        suffixes = (
            self.diffuse_suffix,
            self.team_color_suffix,
            self.dirt_suffix,
            self.specular_suffix,
        )
        if not self.name.strip():
            raise ValueError("Texture naming profile name cannot be empty.")
        if any(
            not suffix.startswith("_") or "." in suffix or len(suffix) == 1
            for suffix in suffixes
        ):
            raise ValueError(
                "Texture suffixes must include a leading underscore and no extension."
            )
        if len({suffix.casefold() for suffix in suffixes}) != len(suffixes):
            raise ValueError("Texture suffixes must be unique.")

    def suffix_for(self, texture_kind: TextureKind) -> str:
        """Return the canonical filename-stem suffix for ``texture_kind``."""
        if not isinstance(texture_kind, TextureKind):
            raise TypeError("texture_kind must be a TextureKind value.")
        return {
            TextureKind.DIFFUSE: self.diffuse_suffix,
            TextureKind.TEAM_COLOR: self.team_color_suffix,
            TextureKind.DIRT: self.dirt_suffix,
            TextureKind.SPECULAR: self.specular_suffix,
        }[texture_kind]


DEFAULT_TEXTURE_NAMING = TextureNamingProfile(
    name="DoW2 / SM1",
    diffuse_suffix="_dif",
    team_color_suffix="_tem",
    dirt_suffix="_drt",
    specular_suffix="_spc",
)


def replace_texture_suffix(
    path: Path,
    source_kind: TextureKind,
    target_kind: TextureKind,
    profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
) -> Optional[Path]:
    """Return ``path`` with its terminal texture suffix replaced.

    Matching is case-insensitive. ``None`` is returned when the stem does not
    end with the expected source suffix or contains no base name before it.
    This function performs no filesystem access.
    """
    texture_path = Path(path)
    source_suffix = profile.suffix_for(source_kind)
    target_suffix = profile.suffix_for(target_kind)
    stem = texture_path.stem
    if not stem.casefold().endswith(source_suffix.casefold()):
        return None

    base_stem = stem[: -len(source_suffix)]
    if not base_stem:
        return None
    return texture_path.with_name(f"{base_stem}{target_suffix}{texture_path.suffix}")


def texture_kind_for(
    path: Path,
    profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
) -> Optional[TextureKind]:
    """Return the texture kind encoded at the end of ``path``'s stem."""
    texture_path = Path(path)
    for texture_kind in TextureKind:
        suffix = profile.suffix_for(texture_kind)
        if texture_path.stem.casefold().endswith(suffix.casefold()):
            if texture_path.stem[: -len(suffix)]:
                return texture_kind
    return None


def is_texture_kind(
    path: Path,
    texture_kind: TextureKind,
    profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
) -> bool:
    """Return whether ``path`` has the profile suffix for ``texture_kind``."""
    profile.suffix_for(texture_kind)
    return texture_kind_for(path, profile) is texture_kind


def with_texture_kind(
    path: Path,
    target_kind: TextureKind,
    profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
) -> Optional[Path]:
    """Return ``path`` with exactly one suffix for ``target_kind``.

    An existing recognized texture suffix is replaced. Otherwise the target
    suffix is appended to a nonempty stem. The extension is preserved.
    """
    texture_path = Path(path)
    current_kind = texture_kind_for(texture_path, profile)
    if current_kind is not None:
        if current_kind is target_kind:
            return texture_path
        return replace_texture_suffix(
            texture_path,
            current_kind,
            target_kind,
            profile,
        )
    if not texture_path.stem:
        return None
    target_suffix = profile.suffix_for(target_kind)
    return texture_path.with_name(
        f"{texture_path.stem}{target_suffix}{texture_path.suffix}"
    )
