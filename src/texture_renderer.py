"""Stateless Pillow rendering for prepared texture sources and settings."""

from PIL import Image, ImageChops, ImageColor, ImageEnhance

from src.color_processing_settings import ColorProcessingSettings
from src.constant import ColorOps
from src.processing_mode import ProcessingMode
from src.render_settings import RenderSettings
from src.texture_set import TextureSet


def _luminosity(color: tuple[float, float, float]) -> float:
    return 0.3 * color[0] + 0.59 * color[1] + 0.11 * color[2]


def _clip_color(color: tuple[float, float, float]) -> tuple[float, float, float]:
    luminosity = _luminosity(color)
    minimum = min(color)
    maximum = max(color)
    clipped: tuple[float, float, float] = color
    if minimum < 0.0:
        clipped = (
            luminosity
            + ((clipped[0] - luminosity) * luminosity) / (luminosity - minimum),
            luminosity
            + ((clipped[1] - luminosity) * luminosity) / (luminosity - minimum),
            luminosity
            + ((clipped[2] - luminosity) * luminosity) / (luminosity - minimum),
        )
    maximum = max(clipped)
    if maximum > 1.0:
        clipped = (
            luminosity
            + ((clipped[0] - luminosity) * (1.0 - luminosity))
            / (maximum - luminosity),
            luminosity
            + ((clipped[1] - luminosity) * (1.0 - luminosity))
            / (maximum - luminosity),
            luminosity
            + ((clipped[2] - luminosity) * (1.0 - luminosity))
            / (maximum - luminosity),
        )
    return (
        max(0.0, min(1.0, clipped[0])),
        max(0.0, min(1.0, clipped[1])),
        max(0.0, min(1.0, clipped[2])),
    )


def _set_luminosity(
    color: tuple[float, float, float],
    luminosity: float,
) -> tuple[float, float, float]:
    difference = luminosity - _luminosity(color)
    return _clip_color(
        (
            color[0] + difference,
            color[1] + difference,
            color[2] + difference,
        )
    )


def _color_blend(base: Image.Image, blend: tuple[int, int, int]) -> Image.Image:
    """Apply the standard non-separable Color blend to one solid colour."""
    normalized_blend = (
        blend[0] / 255.0,
        blend[1] / 255.0,
        blend[2] / 255.0,
    )
    output_by_luminosity = [
        _set_luminosity(normalized_blend, luminosity / 255.0)
        for luminosity in range(256)
    ]
    luminosity = base.convert("RGB").convert(
        "L",
        matrix=(0.3, 0.59, 0.11, 0.0),
    )
    channels = tuple(
        luminosity.point(
            [int(color[channel_index] * 255.0 + 0.5) for color in output_by_luminosity]
        )
        for channel_index in range(3)
    )
    alpha = base.getchannel("A")
    return Image.merge("RGBA", (*channels, alpha))


def _team_channels(textures: TextureSet) -> tuple[Image.Image, ...]:
    team_color = textures.team_color
    if team_color is None or team_color.mode not in ("RGB", "RGBA"):
        return ()
    return tuple(team_color.split())


def _apply_team_colors(
    textures: TextureSet,
    settings: RenderSettings,
) -> Image.Image:
    workspace = textures.diffuse.copy()
    processing_by_channel: tuple[ColorProcessingSettings, ...]
    if settings.processing_mode is ProcessingMode.PER_COLOR:
        processing_by_channel = settings.per_color_processing
    else:
        processing_by_channel = (settings.global_processing,) * 4
    for color, channel, processing in zip(
        settings.colors,
        _team_channels(textures),
        processing_by_channel,
    ):
        rgb = ImageColor.getrgb(color)

        # Neutral grey is the established no-colour sentinel.
        if rgb == (128, 128, 128):
            continue

        # Original implementation retained for reference. It applied the
        # channel when generating the color, as alpha, and as the paste mask,
        # which compounded the attenuation of soft mask values.
        #
        # gray_img = textures.diffuse.copy()
        # channel.convert("L")  # No effect unless the return value is used.
        # new_img = ImageOps.colorize(
        #     channel, (0, 0, 0), color
        # ).convert("RGBA")
        # new_img.putalpha(channel)
        # if settings.color_op is ColorOps.OVERLAY:
        #     new_img = ImageChops.overlay(gray_img, new_img)
        # elif settings.color_op is ColorOps.MULTIPLY:
        #     new_img = ImageChops.multiply(gray_img, new_img)
        # else:
        #     new_img = ImageChops.screen(gray_img, new_img)
        # enhancer_contrast = ImageEnhance.Contrast(new_img)
        # new_img = enhancer_contrast.enhance(settings.contrast / 100)
        # enhancer_brightness = ImageEnhance.Brightness(new_img)
        # new_img = enhancer_brightness.enhance(settings.brightness / 100)
        # workspace.paste(new_img, mask=channel)

        gray_img = textures.diffuse.copy()
        color_img = Image.new("RGBA", gray_img.size, color)

        if processing.blend_mode is ColorOps.NORMAL:
            new_img = color_img
        elif processing.blend_mode is ColorOps.OVERLAY:
            new_img = ImageChops.overlay(gray_img, color_img)
        elif processing.blend_mode is ColorOps.MULTIPLY:
            new_img = ImageChops.multiply(gray_img, color_img)
        elif processing.blend_mode is ColorOps.SCREEN:
            new_img = ImageChops.screen(gray_img, color_img)
        elif processing.blend_mode is ColorOps.SOFT_LIGHT:
            new_img = ImageChops.soft_light(gray_img, color_img)
        elif processing.blend_mode is ColorOps.HARD_LIGHT:
            new_img = ImageChops.hard_light(gray_img, color_img)
        elif processing.blend_mode is ColorOps.COLOR:
            new_img = _color_blend(gray_img, (rgb[0], rgb[1], rgb[2]))
        elif processing.blend_mode is ColorOps.LINEAR_BURN:
            new_img = ImageChops.add(gray_img, color_img, offset=-255)
        elif processing.blend_mode is ColorOps.LINEAR_DODGE:
            new_img = ImageChops.add(gray_img, color_img)
        elif processing.blend_mode is ColorOps.DARKEN:
            new_img = ImageChops.darker(gray_img, color_img)
        elif processing.blend_mode is ColorOps.LIGHTEN:
            new_img = ImageChops.lighter(gray_img, color_img)
        else:
            raise ValueError(
                "Blend mode is not implemented yet: "
                f"{processing.blend_mode.value}"
            )

        enhancer_contrast = ImageEnhance.Contrast(new_img)
        new_img = enhancer_contrast.enhance(processing.contrast / 100)
        enhancer_brightness = ImageEnhance.Brightness(new_img)
        new_img = enhancer_brightness.enhance(processing.brightness / 100)
        if processing.saturation != 100.0:
            enhancer_saturation = ImageEnhance.Color(new_img)
            new_img = enhancer_saturation.enhance(processing.saturation / 100)

        # Apply the team-colour channel exactly once, with opacity scaling its
        # effective strength rather than the blended RGB values.
        effective_channel = channel
        if processing.opacity != 100.0:
            opacity = processing.opacity / 100.0
            effective_channel = channel.point(lambda value: value * opacity)
        workspace.paste(new_img, mask=effective_channel)
    return workspace


def _selected_team_colour(
    textures: TextureSet,
    settings: RenderSettings,
) -> Image.Image | None:
    channels = _team_channels(textures)
    if not channels:
        if textures.team_color is not None:
            return textures.team_color
        return Image.new("L", textures.diffuse.size, "gray")

    team_color = textures.team_color
    if team_color is None:
        return Image.new("L", textures.diffuse.size, "gray")

    new_img = Image.new("L", team_color.size)
    for index in settings.tem_selected:
        try:
            channel = channels[index]
        except IndexError:
            return None
        new_img.paste(channel, mask=channel)
    return new_img


class TextureRenderer:
    """Render source textures without retaining request or result state."""

    def render(
        self,
        textures: TextureSet,
        settings: RenderSettings,
    ) -> Image.Image:
        workspace = _apply_team_colors(textures, settings)

        # Add black background, hiding transparent pixels.
        background = Image.new("RGBA", workspace.size, (0, 0, 0))
        workspace = Image.alpha_composite(background, workspace)

        if settings.apply_alpha:
            team_colour = _selected_team_colour(textures, settings)
            # Preserve the established runtime failure for an invalid channel
            # selection until that domain contract is tightened separately.
            # Pillow's stub excludes valid single-band images here.
            workspace.putalpha(
                ImageChops.invert(team_colour)  # type: ignore[arg-type]
            )

        if settings.apply_dirt and textures.dirt is not None:
            workspace = Image.alpha_composite(workspace, textures.dirt)
        if settings.apply_spec and textures.specular is not None:
            workspace = Image.alpha_composite(workspace, textures.specular)
        return workspace

    def render_team_colors(
        self,
        textures: TextureSet,
        settings: RenderSettings,
    ) -> Image.Image:
        """Return the pre-composite coloured diffuse for compatibility."""
        return _apply_team_colors(textures, settings)

    def render_team_colour(
        self,
        textures: TextureSet,
        settings: RenderSettings,
    ) -> Image.Image | None:
        """Return the selected-channel image used by the current preview."""
        return _selected_team_colour(textures, settings)
