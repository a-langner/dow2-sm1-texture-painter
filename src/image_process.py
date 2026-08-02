from PIL import (
    Image,
    ImageChops,
    ImageOps,
    ImageColor,
    ImageEnhance,
    ImageDraw,
)
from src.constant import DEFAULT_IMG_SIZE, ColorOps


MAX_TEXTURE_DIMENSION = 16 * 1024
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
            f'{MAX_TEXTURE_DIMENSION} pixels in either dimension.'
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
    img = Image.new(
        mode=mode, size=(DEFAULT_IMG_SIZE, DEFAULT_IMG_SIZE), color="gray"
    )
    d1 = ImageDraw.Draw(img)
    d1.text(xy=(90, 128), fill="black", text=text)
    return img


def almostEquals(a, b, thres=5):
    return all(abs(a[i] - b[i]) < thres for i in range(len(a)))


class ImageWorkbench:
    def __init__(self):
        self.tem_channels = []
        self.tem_selected = []
        self.colors = []
        self.brightness = 50
        self.contrast = 100
        self.apply_alpha = False
        self.apply_dirt = False
        self.apply_spec = False
        self.color_op = ColorOps.OVERLAY.value
        self.img_dirt = None
        self.img_spec = None
        self.set_placeholder_img()

    def set_placeholder_img(self):
        self.img_og_dif = create_placeholder_img("Select Diffuse Texture", "RGBA")
        self.img_og_tem = create_placeholder_img("Select Channel Texture", "L")
        self.img_workspace = self.img_og_dif.copy()
        self.tem_channels = []
        self.img_dirt = None
        self.img_spec = None

    def process_coloring(self):
        """Process image with current workspace setting"""
        # Creating a copied image to work on
        self.img_workspace = self.img_og_dif.copy()
        for color, channel in zip(self.colors, self.tem_channels):
            rgb = ImageColor.getrgb(color)

            # Ignore gray value as they are default
            #  TODO: is this neccessary?
            if rgb == (128, 128, 128):
                continue

            # Get grayscaled original img
            #  TODO: useless variable as it is not altered
            gray_img = self.img_og_dif.copy()
            channel.convert("L")

            # Colorize grayscale image using channel as mask
            new_img = ImageOps.colorize(channel, (0, 0, 0), color).convert(
                "RGBA"
            )

            # Add alpha using channel as mask
            new_img.putalpha(channel)

            if self.color_op == ColorOps.OVERLAY.value:
                new_img = ImageChops.overlay(gray_img, new_img)
            elif self.color_op == ColorOps.MULTIPLY.value:
                new_img = ImageChops.multiply(gray_img, new_img)
            else:
                new_img = ImageChops.screen(gray_img, new_img)

            enhancer_contrast = ImageEnhance.Contrast(new_img)
            new_img = enhancer_contrast.enhance(self.contrast / 100)
            enhancer_brightness = ImageEnhance.Brightness(new_img)
            new_img = enhancer_brightness.enhance(self.brightness / 100)

            # Paste processed image part on the workspace one
            self.img_workspace.paste(new_img, mask=channel)

    def refresh_workspace(self):
        """Refresh the workspace image with current settings"""
        self.process_coloring()
        # Add black background, hiding transparent pixel
        background = Image.new("RGBA", self.img_workspace.size, (0, 0, 0))
        self.img_workspace = Image.alpha_composite(
            background, self.img_workspace
        )

        if self.apply_alpha:
            tmp = self.refresh_team_colour_img()
            tmp = ImageChops.invert(tmp)
            self.img_workspace.putalpha(tmp)

        if self.apply_dirt and self.img_dirt is not None:
            self.img_workspace = Image.alpha_composite(
                self.img_workspace, self.img_dirt
            )
        if self.apply_spec and self.img_spec is not None:
            self.img_workspace = Image.alpha_composite(
                self.img_workspace, self.img_spec
            )
        return self.img_workspace

    def refresh_team_colour_img(self):
        new_img = Image.new("L", self.img_og_tem.size)
        if len(self.tem_channels) == 0:
            return self.img_og_tem
        for i in self.tem_selected:
            # TODO: think about clean implementation
            try:
                new_img.paste(self.tem_channels[i], mask=self.tem_channels[i])
            except IndexError:
                return
        return new_img

    def load_diffuse_file(self, filepath: str):
        """Load diffuse texture and set it as workspace image,

        :param filepath: path to file
        :type filepath: str
        """
        self.img_og_dif = _open_texture(filepath).convert("RGBA")
        self.img_og_tem = Image.new("L", self.img_og_dif.size, "gray")
        self.tem_channels = []
        self.img_dirt = None
        self.img_spec = None

    def load_team_colour_file(self, filepath: str):
        img = _open_texture(filepath)
        if img.size != self.img_og_dif.size:
            raise TextureValidationError(
                f'Team-colour texture "{filepath}" is '
                f'{img.size[0]}x{img.size[1]}, but the diffuse texture is '
                f'{self.img_og_dif.size[0]}x{self.img_og_dif.size[1]}. '
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
                f'{img.size[0]}x{img.size[1]}, but the diffuse texture is '
                f'{self.img_og_dif.size[0]}x{self.img_og_dif.size[1]}. '
                "The textures must have the same aspect ratio."
            )
        if img.size != self.img_og_dif.size:
            img = img.resize(self.img_og_dif.size, Image.Resampling.LANCZOS)
        return img.convert("RGBA")

    def load_dirt_file(self, filepath: str):
        self.img_dirt = self._prepare_optional_map(filepath, "Dirt")

    def load_specular_file(self, filepath: str):
        self.img_spec = self._prepare_optional_map(filepath, "Specular")

    def save(self, filepath: str):
        if filepath.endswith(".jpg"):
            self.img_workspace.convert("RGB").save(filepath)
        else:
            self.img_workspace.save(filepath)
