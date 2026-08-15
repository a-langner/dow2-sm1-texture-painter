"""Filesystem and active TextureSet coordination for texture loading."""

from dataclasses import dataclass
import logging
from pathlib import Path
import re

from src.constant import OPEN_EXT_LIST
from src.image_process import (
    TextureValidationError,
    load_diffuse_texture,
    load_optional_texture,
    load_team_colour_texture,
)
from src.team_color_mask_variant import TeamColorMaskVariant
from src.texture_naming import (
    DEFAULT_TEXTURE_NAMING,
    TEXTURE_NAMING_PROFILES,
    TextureKind,
    TextureNamingProfile,
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
    available_team_color_mask_variants: tuple[TeamColorMaskVariant, ...]
    active_team_color_mask_variant: TeamColorMaskVariant | None
    team_color_mask_path: Path | None
    dirt_path: Path | None
    specular_path: Path | None
    width: int
    height: int
    team_color_mask_error: str | None
    warnings: tuple[TextureLoadWarning, ...]


@dataclass(frozen=True)
class ChannelLoadResult:
    texture_set: TextureSet
    channel_path: Path
    width: int
    height: int


def validate_supported_texture_path(texture_path: Path) -> Path:
    if texture_path.suffix.casefold() not in SUPPORTED_TEXTURE_EXTENSIONS:
        raise UnsupportedTextureError(
            f'Unsupported texture file "{texture_path}". '
            "Choose a DDS, PNG, JPG, BMP, TGA, or BLP file."
        )
    return texture_path


def find_companion_texture(
    diffuse_filepath: Path,
    target_kind: TextureKind,
    profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
) -> Path | None:
    """Find a case-insensitive sibling derived from the naming profile."""
    diffuse_path = diffuse_filepath
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
            profile.display_name,
            diffuse_path,
        )
        return None

    expected_name = expected_path.name.casefold()
    for candidate in diffuse_path.parent.iterdir():
        if candidate.is_file() and candidate.name.casefold() == expected_name:
            return candidate
    LOGGER.debug("Companion texture is absent: %s", expected_path)
    return None


def discover_team_color_mask_variants(
    diffuse_filepath: Path,
    profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
) -> tuple[TeamColorMaskVariant, ...]:
    """Discover exact default and numbered mask siblings for one diffuse."""
    diffuse_path = diffuse_filepath
    default_path = replace_texture_suffix(
        diffuse_path,
        TextureKind.DIFFUSE,
        TextureKind.TEAM_COLOR,
        profile,
    )
    if default_path is None:
        return ()

    stem_pattern = re.compile(
        rf"^{re.escape(default_path.stem)}(?:_([1-9]\d*))?$",
        re.IGNORECASE,
    )
    extension = diffuse_path.suffix.casefold()
    variants: list[TeamColorMaskVariant] = []
    for candidate in diffuse_path.parent.iterdir():
        if not candidate.is_file() or candidate.suffix.casefold() != extension:
            continue
        match = stem_pattern.fullmatch(candidate.stem)
        if match is None:
            continue
        numbered_suffix = match.group(1)
        variants.append(
            TeamColorMaskVariant(
                int(numbered_suffix) if numbered_suffix is not None else None,
                candidate,
            )
        )
    return tuple(
        sorted(
            variants,
            key=lambda variant: (
                variant.sort_key,
                variant.filename.casefold(),
                variant.filename,
            ),
        )
    )


def detect_texture_naming_profile(
    diffuse_filepath: Path,
    profiles: tuple[TextureNamingProfile, ...] = TEXTURE_NAMING_PROFILES,
) -> TextureNamingProfile | None:
    """Detect one unambiguous profile from sibling team-colour masks."""
    matches = tuple(
        profile
        for profile in profiles
        if discover_team_color_mask_variants(diffuse_filepath, profile)
    )
    return matches[0] if len(matches) == 1 else None


class TextureLoadingService:
    """Build replacement TextureSets without owning active application state."""

    def __init__(
        self,
        naming_profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
    ) -> None:
        self.naming_profile = naming_profile

    def load_diffuse_and_companions(
        self,
        diffuse_path: Path,
    ) -> TextureLoadResult:
        diffuse_path = validate_supported_texture_path(diffuse_path)
        diffuse = load_diffuse_texture(diffuse_path)
        textures = TextureSet(diffuse=diffuse)

        try:
            available_variants = discover_team_color_mask_variants(
                diffuse_path, self.naming_profile
            )
            companions: dict[TextureKind, Path | None] = {
                kind: find_companion_texture(
                    diffuse_path, kind, self.naming_profile
                )
                for kind in (
                    TextureKind.DIRT,
                    TextureKind.SPECULAR,
                )
            }
        except OSError as exc:
            raise TextureDiscoveryError(
                f'Could not inspect companion textures for "{diffuse_path}": {exc}'
            ) from exc

        active_variant = available_variants[0] if available_variants else None
        team_color_mask_error: str | None = None
        team_color_mask_path = active_variant.path if active_variant else None
        if team_color_mask_path is not None:
            LOGGER.debug("Loading team-colour mask: %s", team_color_mask_path)
            try:
                textures.team_color = load_team_colour_texture(
                    team_color_mask_path, diffuse.size
                )
            except TextureValidationError as exc:
                team_color_mask_error = str(exc)
                LOGGER.warning(
                    "Invalid team-colour mask %s: %s",
                    team_color_mask_path,
                    exc,
                )

        warnings: list[TextureLoadWarning] = []
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
            available_team_color_mask_variants=available_variants,
            active_team_color_mask_variant=active_variant,
            team_color_mask_path=team_color_mask_path,
            dirt_path=companions[TextureKind.DIRT],
            specular_path=companions[TextureKind.SPECULAR],
            width=width,
            height=height,
            team_color_mask_error=team_color_mask_error,
            warnings=tuple(warnings),
        )

    def load_channel_file(
        self,
        textures: TextureSet | None,
        channel_path: Path,
    ) -> ChannelLoadResult:
        if textures is None:
            raise TextureValidationError(
                "Load a diffuse texture before loading a team-colour mask."
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
