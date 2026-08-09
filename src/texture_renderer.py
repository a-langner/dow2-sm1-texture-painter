"""Stateless Pillow rendering for prepared texture sources and settings."""

from PIL import Image, ImageChops, ImageColor, ImageEnhance

from src.constant import ColorOps
from src.render_settings import RenderSettings
from src.texture_set import TextureSet


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
    for color, channel in zip(settings.colors, _team_channels(textures)):
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

        if settings.color_op is ColorOps.OVERLAY:
            new_img = ImageChops.overlay(gray_img, color_img)
        elif settings.color_op is ColorOps.MULTIPLY:
            new_img = ImageChops.multiply(gray_img, color_img)
        else:
            new_img = ImageChops.screen(gray_img, color_img)

        enhancer_contrast = ImageEnhance.Contrast(new_img)
        new_img = enhancer_contrast.enhance(settings.contrast / 100)
        enhancer_brightness = ImageEnhance.Brightness(new_img)
        new_img = enhancer_brightness.enhance(settings.brightness / 100)

        # Apply the team-colour channel exactly once.
        workspace.paste(new_img, mask=channel)
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
