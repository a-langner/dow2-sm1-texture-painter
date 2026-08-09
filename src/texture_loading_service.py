"""Filesystem and active TextureSet coordination for texture loading."""

from dataclasses import dataclass
import logging
from pathlib import Path

from src.constant import OPEN_EXT_LIST
from src.image_process import TextureValidationError
from src.texture_naming import (
    DEFAULT_TEXTURE_NAMING,
    TextureKind,
    replace_texture_suffix,
)

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
    """Load one active texture set into an injected texture-state facade."""

    def __init__(self, workbench, naming_profile=DEFAULT_TEXTURE_NAMING):
        self.workbench = workbench
        self.naming_profile = naming_profile

    def load_diffuse_and_companions(self, diffuse_path):
        diffuse_path = validate_supported_texture_path(diffuse_path)
        previous_state = self._source_state()
        self.workbench.load_diffuse_file(diffuse_path)

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
            self._restore_source_state(previous_state)
            raise TextureDiscoveryError(
                f'Could not inspect companion textures for "{diffuse_path}": {exc}'
            ) from exc

        team_color_error = None
        team_color_path = companions[TextureKind.TEAM_COLOR]
        if team_color_path is not None:
            LOGGER.debug("Loading team-colour companion: %s", team_color_path)
            try:
                self.workbench.load_team_colour_file(team_color_path)
            except TextureValidationError as exc:
                team_color_error = str(exc)
                LOGGER.warning(
                    "Invalid team-colour companion %s: %s",
                    team_color_path,
                    exc,
                )

        warnings = []
        for kind, path, loader in (
            (
                TextureKind.DIRT,
                companions[TextureKind.DIRT],
                self.workbench.load_dirt_file,
            ),
            (
                TextureKind.SPECULAR,
                companions[TextureKind.SPECULAR],
                self.workbench.load_specular_file,
            ),
        ):
            if path is None:
                continue
            try:
                loader(path)
            except TextureValidationError as exc:
                warnings.append(TextureLoadWarning(kind, str(exc)))
                LOGGER.warning(
                    "Invalid optional %s companion %s: %s",
                    kind.value,
                    path,
                    exc,
                )

        width, height = self.workbench.texture_set.diffuse.size
        return TextureLoadResult(
            diffuse_path=diffuse_path,
            team_color_path=team_color_path,
            dirt_path=companions[TextureKind.DIRT],
            specular_path=companions[TextureKind.SPECULAR],
            width=width,
            height=height,
            team_color_error=team_color_error,
            warnings=tuple(warnings),
        )

    def load_channel_file(self, channel_path):
        channel_path = validate_supported_texture_path(channel_path)
        self.workbench.load_team_colour_file(channel_path)
        width, height = self.workbench.texture_set.team_color.size
        return ChannelLoadResult(channel_path, width, height)

    def _source_state(self):
        return self.workbench.texture_set

    def _restore_source_state(self, state):
        self.workbench.texture_set = state
