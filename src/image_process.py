from PIL import Image, ImageDraw
from dataclasses import replace
from src.constant import DEFAULT_IMG_SIZE, ColorOps
from src.render_settings import (
    DEFAULT_COLOR,
    DEFAULT_RENDER_SETTINGS,
    RenderSettings,
)
from src.texture_renderer import TextureRenderer
from src.texture_set import TextureSet

MAX_TEXTURE_DIMENSION = 16 * 1024
# Pillow's default decompression-bomb threshold is lower than a valid 16K
# texture. Dimension validation below remains the authoritative limit.
Image.MAX_IMAGE_PIXELS = MAX_TEXTURE_DIMENSION * MAX_TEXTURE_DIMENSION


class TextureValidationError(ValueError):
    """Raised when a texture cannot safely be used by the workbench."""


def _validate_dimensions(img, filepath):
    width, height = img.size
    if width <= 0 or height <= 0:
        raise TextureValidationError(
            f'"{filepath}" has invalid dimensions {width}x{height}.'
        )
    if width > MAX_TEXTURE_DIMENSION or height > MAX_TEXTURE_DIMENSION:
        raise TextureValidationError(
            f'"{filepath}" is {width}x{height}. Textures may not exceed '
            f"{MAX_TEXTURE_DIMENSION} pixels in either dimension."
        )


def _open_texture(filepath):
    """Decode an image and return a copy independent of its file handle."""
    try:
        with Image.open(filepath) as img:
            _validate_dimensions(img, filepath)
            img.load()
            return img.copy()
    except TextureValidationError:
        raise
    except (OSError, ValueError) as exc:
        raise TextureValidationError(
            f'Could not load texture "{filepath}": {exc}'
        ) from exc


def _same_aspect_ratio(first_size, second_size):
    first_width, first_height = first_size
    second_width, second_height = second_size
    return first_width * second_height == first_height * second_width


def create_placeholder_img(text="Image PlaceHolder", mode="RGBA"):
    img = Image.new(mode=mode, size=(DEFAULT_IMG_SIZE, DEFAULT_IMG_SIZE), color="gray")
    d1 = ImageDraw.Draw(img)
    d1.text(xy=(90, 128), fill="black", text=text)
    return img


def almostEquals(a, b, thres=5):
    return all(abs(a[i] - b[i]) < thres for i in range(len(a)))


class ImageWorkbench:
    def __init__(self):
        self.tem_channels = []
        self.render_settings = DEFAULT_RENDER_SETTINGS
        self._renderer = TextureRenderer()
        self.set_placeholder_img()

    @property
    def colors(self):
        """Compatibility view of the four canonical Pattern colours."""
        return self.render_settings.colors

    @colors.setter
    def colors(self, values):
        values = tuple(values)
        if len(values) > 4:
            raise ValueError("Rendering supports at most four Pattern colours.")
        values += (DEFAULT_COLOR,) * (4 - len(values))
        self.render_settings = replace(
            self.render_settings,
            primary_color=values[0],
            secondary_color=values[1],
            tint_color=values[2],
            extra_color=values[3],
        )

    @property
    def brightness(self):
        return self.render_settings.brightness

    @brightness.setter
    def brightness(self, value):
        self.render_settings = replace(self.render_settings, brightness=value)

    @property
    def contrast(self):
        return self.render_settings.contrast

    @contrast.setter
    def contrast(self, value):
        self.render_settings = replace(self.render_settings, contrast=value)

    @property
    def apply_alpha(self):
        return self.render_settings.apply_alpha

    @apply_alpha.setter
    def apply_alpha(self, value):
        self.render_settings = replace(self.render_settings, apply_alpha=value)

    @property
    def apply_dirt(self):
        return self.render_settings.apply_dirt

    @apply_dirt.setter
    def apply_dirt(self, value):
        self.render_settings = replace(self.render_settings, apply_dirt=value)

    @property
    def apply_spec(self):
        return self.render_settings.apply_spec

    @apply_spec.setter
    def apply_spec(self, value):
        self.render_settings = replace(self.render_settings, apply_spec=value)

    @property
    def color_op(self):
        """Compatibility string for GUI operation values."""
        return self.render_settings.color_op.value

    @color_op.setter
    def color_op(self, value):
        try:
            operation = value if isinstance(value, ColorOps) else ColorOps(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unsupported color operation: {value!r}") from exc
        self.render_settings = replace(self.render_settings, color_op=operation)

    @property
    def tem_selected(self):
        return self.render_settings.tem_selected

    @tem_selected.setter
    def tem_selected(self, value):
        self.render_settings = replace(self.render_settings, tem_selected=tuple(value))

    @property
    def img_og_dif(self):
        """Compatibility name for the authoritative diffuse source."""
        return self.texture_set.diffuse

    @img_og_dif.setter
    def img_og_dif(self, image):
        self.texture_set.diffuse = image

    @property
    def img_og_tem(self):
        """Compatibility name for the authoritative team-colour source."""
        return self.texture_set.team_color

    @img_og_tem.setter
    def img_og_tem(self, image):
        self.texture_set.team_color = image

    @property
    def img_dirt(self):
        """Compatibility name for the authoritative dirt source."""
        return self.texture_set.dirt

    @img_dirt.setter
    def img_dirt(self, image):
        self.texture_set.dirt = image

    @property
    def img_spec(self):
        """Compatibility name for the authoritative specular source."""
        return self.texture_set.specular

    @img_spec.setter
    def img_spec(self, image):
        self.texture_set.specular = image

    def set_placeholder_img(self):
        diffuse = create_placeholder_img("Select Diffuse Texture", "RGBA")
        team_color = create_placeholder_img("Select Channel Texture", "L")
        self.texture_set = TextureSet(diffuse, team_color)
        self.tem_channels = []

    def get_render_settings(self):
        return self.render_settings

    def apply_render_settings(self, settings):
        if not isinstance(settings, RenderSettings):
            raise TypeError("settings must be a RenderSettings instance.")
        self.render_settings = settings

    def render_snapshot(self):
        """Compatibility snapshot; preview rendering no longer uses this API."""
        snapshot = object.__new__(ImageWorkbench)
        snapshot.texture_set = self.texture_set.copy_for_render()
        snapshot.tem_channels = tuple(self.tem_channels)
        snapshot.render_settings = self.render_settings
        snapshot._renderer = self._renderer
        return snapshot

    def process_coloring(self):
        """Process image with current workspace setting"""
        return self._renderer.render_team_colors(
            self.texture_set,
            self.render_settings,
        )

    def refresh_workspace(self):
        """Refresh the workspace image with current settings"""
        return self._renderer.render(
            self.texture_set,
            self.render_settings,
        )

    def refresh_team_colour_img(self):
        return self._renderer.render_team_colour(
            self.texture_set,
            self.render_settings,
        )

    def load_diffuse_file(self, filepath: str):
        """Load diffuse texture and set it as workspace image,

        :param filepath: path to file
        :type filepath: str
        """
        diffuse = _open_texture(filepath).convert("RGBA")
        # Companion maps belong to a particular diffuse. Do not accidentally
        # retain maps from the previously opened texture.
        self.texture_set = TextureSet(
            diffuse=diffuse,
            team_color=Image.new("L", diffuse.size, "gray"),
        )
        self.tem_channels = []

    def load_team_colour_file(self, filepath: str):
        img = _open_texture(filepath)
        if img.size != self.img_og_dif.size:
            raise TextureValidationError(
                f'Team-colour texture "{filepath}" is '
                f"{img.size[0]}x{img.size[1]}, but the diffuse texture is "
                f"{self.img_og_dif.size[0]}x{self.img_og_dif.size[1]}. "
                "Team-colour and diffuse textures must have identical dimensions."
            )
        if img.mode == "RGB":
            empty_alpha = Image.new("L", img.size, 0)
            img = Image.merge("RGBA", (*img.split(), empty_alpha))
        elif img.mode != "RGBA":
            raise TextureValidationError(
                f'Team-colour texture "{filepath}" uses mode {img.mode}. '
                "An RGB or RGBA texture is required."
            )
        self.img_og_tem = img
        self.tem_channels = [channel.convert("L") for channel in img.split()]

    def _prepare_optional_map(self, filepath: str, map_name: str):
        img = _open_texture(filepath)
        if not _same_aspect_ratio(img.size, self.img_og_dif.size):
            raise TextureValidationError(
                f'{map_name} texture "{filepath}" is '
                f"{img.size[0]}x{img.size[1]}, but the diffuse texture is "
                f"{self.img_og_dif.size[0]}x{self.img_og_dif.size[1]}. "
                "The textures must have the same aspect ratio."
            )
        if img.size != self.img_og_dif.size:
            img = img.resize(self.img_og_dif.size, Image.Resampling.LANCZOS)
        return img.convert("RGBA")

    def load_dirt_file(self, filepath: str):
        self.img_dirt = self._prepare_optional_map(filepath, "Dirt")

    def load_specular_file(self, filepath: str):
        self.img_spec = self._prepare_optional_map(filepath, "Specular")

def save_image(image: Image.Image, filepath) -> None:
    """Save an explicitly supplied rendered image using established behavior."""
    if str(filepath).endswith(".jpg"):
        image.convert("RGB").save(filepath)
    else:
        image.save(filepath)
