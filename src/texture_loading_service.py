"""Filesystem and active TextureSet coordination for texture loading."""

from dataclasses import dataclass
import logging
from pathlib import Path

from src.constant import OPEN_EXT_LIST
from src.image_process import (
    TextureValidationError,
    load_diffuse_texture,
    load_optional_texture,
    load_team_colour_texture,
)
from src.texture_naming import (
    DEFAULT_TEXTURE_NAMING,
    TextureKind,
    replace_texture_suffix,
)
from src.texture_set import TextureSet

LOGGER = logging.getLogger(__name__)
SUPPORTED_TEXTURE_EXTENSIONS = frozenset(
    f".{extension.casefold()}" for extension in OPEN_EXT_LIST
)


class UnsupportedTextureError(TextureValidationError):
    """Raised when a selected texture has an unsupported filename extension."""


class TextureDiscoveryError(TextureValidationError):
    """Raised when companion files cannot be inspected safely."""


@dataclass(frozen=True)
class TextureLoadWarning:
    kind: TextureKind
    message: str


@dataclass(frozen=True)
class TextureLoadResult:
    texture_set: TextureSet
    diffuse_path: Path
    team_color_path: Path | None
    dirt_path: Path | None
    specular_path: Path | None
    width: int
    height: int
    team_color_error: str | None
    warnings: tuple[TextureLoadWarning, ...]


@dataclass(frozen=True)
class ChannelLoadResult:
    texture_set: TextureSet
    channel_path: Path
    width: int
    height: int


def validate_supported_texture_path(texture_path):
    path = Path(texture_path)
    if path.suffix.casefold() not in SUPPORTED_TEXTURE_EXTENSIONS:
        raise UnsupportedTextureError(
            f'Unsupported texture file "{path}". Choose a DDS, PNG, JPG, '
            "BMP, TGA, or BLP file."
        )
    return path


def find_companion_texture(
    diffuse_filepath,
    target_kind,
    profile=DEFAULT_TEXTURE_NAMING,
):
    """Find a case-insensitive sibling derived from the naming profile."""
    diffuse_path = Path(diffuse_filepath)
    if target_kind is TextureKind.DIFFUSE:
        raise ValueError("A companion texture kind cannot be diffuse.")
    if not isinstance(target_kind, TextureKind):
        raise TypeError("target_kind must be a TextureKind")
    expected_path = replace_texture_suffix(
        diffuse_path,
        TextureKind.DIFFUSE,
        target_kind,
        profile,
    )
    if expected_path is None:
        LOGGER.debug(
            "Texture name does not match profile '%s': %s",
            profile.name,
            diffuse_path,
        )
        return None

    expected_name = expected_path.name.casefold()
    for candidate in diffuse_path.parent.iterdir():
        if candidate.is_file() and candidate.name.casefold() == expected_name:
            return candidate
    LOGGER.debug("Companion texture is absent: %s", expected_path)
    return None


class TextureLoadingService:
    """Build replacement TextureSets without owning active application state."""

    def __init__(self, naming_profile=DEFAULT_TEXTURE_NAMING):
        self.naming_profile = naming_profile

    def load_diffuse_and_companions(self, diffuse_path):
        diffuse_path = validate_supported_texture_path(diffuse_path)
        diffuse = load_diffuse_texture(diffuse_path)
        textures = TextureSet(diffuse=diffuse)

        try:
            companions = {
                kind: find_companion_texture(
                    diffuse_path, kind, self.naming_profile
                )
                for kind in (
                    TextureKind.TEAM_COLOR,
                    TextureKind.DIRT,
                    TextureKind.SPECULAR,
                )
            }
        except OSError as exc:
            raise TextureDiscoveryError(
                f'Could not inspect companion textures for "{diffuse_path}": {exc}'
            ) from exc

        team_color_error = None
        team_color_path = companions[TextureKind.TEAM_COLOR]
        if team_color_path is not None:
            LOGGER.debug("Loading team-colour companion: %s", team_color_path)
            try:
                textures.team_color = load_team_colour_texture(
                    team_color_path, diffuse.size
                )
            except TextureValidationError as exc:
                team_color_error = str(exc)
                LOGGER.warning(
                    "Invalid team-colour companion %s: %s",
                    team_color_path,
                    exc,
                )

        warnings = []
        for kind, path, attribute in (
            (
                TextureKind.DIRT,
                companions[TextureKind.DIRT],
                "dirt",
            ),
            (
                TextureKind.SPECULAR,
                companions[TextureKind.SPECULAR],
                "specular",
            ),
        ):
            if path is None:
                continue
            try:
                setattr(
                    textures,
                    attribute,
                    load_optional_texture(path, kind.value.title(), diffuse.size),
                )
            except TextureValidationError as exc:
                warnings.append(TextureLoadWarning(kind, str(exc)))
                LOGGER.warning(
                    "Invalid optional %s companion %s: %s",
                    kind.value,
                    path,
                    exc,
                )

        width, height = diffuse.size
        return TextureLoadResult(
            texture_set=textures,
            diffuse_path=diffuse_path,
            team_color_path=team_color_path,
            dirt_path=companions[TextureKind.DIRT],
            specular_path=companions[TextureKind.SPECULAR],
            width=width,
            height=height,
            team_color_error=team_color_error,
            warnings=tuple(warnings),
        )

    def load_channel_file(self, textures, channel_path):
        if textures is None:
            raise TextureValidationError(
                "Load a diffuse texture before loading a team-colour texture."
            )
        channel_path = validate_supported_texture_path(channel_path)
        team_color = load_team_colour_texture(channel_path, textures.diffuse.size)
        replacement = TextureSet(
            diffuse=textures.diffuse,
            team_color=team_color,
            dirt=textures.dirt,
            specular=textures.specular,
        )
        width, height = team_color.size
        return ChannelLoadResult(replacement, channel_path, width, height)
