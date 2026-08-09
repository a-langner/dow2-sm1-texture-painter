from PIL import Image, ImageDraw
from src.constant import DEFAULT_IMG_SIZE

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


def load_diffuse_texture(filepath):
    """Load one validated diffuse image in the renderer's RGBA mode."""
    return _open_texture(filepath).convert("RGBA")


def load_team_colour_texture(filepath, diffuse_size):
    """Load and validate one RGB/RGBA team-colour image."""
    img = _open_texture(filepath)
    if img.size != diffuse_size:
        raise TextureValidationError(
            f'Team-colour texture "{filepath}" is '
            f"{img.size[0]}x{img.size[1]}, but the diffuse texture is "
            f"{diffuse_size[0]}x{diffuse_size[1]}. "
            "Team-colour and diffuse textures must have identical dimensions."
        )
    if img.mode == "RGB":
        empty_alpha = Image.new("L", img.size, 0)
        return Image.merge("RGBA", (*img.split(), empty_alpha))
    if img.mode != "RGBA":
        raise TextureValidationError(
            f'Team-colour texture "{filepath}" uses mode {img.mode}. '
            "An RGB or RGBA texture is required."
        )
    return img


def load_optional_texture(filepath, map_name, diffuse_size):
    """Load, validate, resize, and convert one optional companion map."""
    img = _open_texture(filepath)
    if not _same_aspect_ratio(img.size, diffuse_size):
        raise TextureValidationError(
            f'{map_name} texture "{filepath}" is '
            f"{img.size[0]}x{img.size[1]}, but the diffuse texture is "
            f"{diffuse_size[0]}x{diffuse_size[1]}. "
            "The textures must have the same aspect ratio."
        )
    if img.size != diffuse_size:
        img = img.resize(diffuse_size, Image.Resampling.LANCZOS)
    return img.convert("RGBA")


def create_placeholder_img(text="Image PlaceHolder", mode="RGBA"):
    img = Image.new(mode=mode, size=(DEFAULT_IMG_SIZE, DEFAULT_IMG_SIZE), color="gray")
    d1 = ImageDraw.Draw(img)
    d1.text(xy=(90, 128), fill="black", text=text)
    return img


def almostEquals(a, b, thres=5):
    return all(abs(a[i] - b[i]) < thres for i in range(len(a)))


def save_image(image: Image.Image, filepath) -> None:
    """Save an explicitly supplied rendered image using established behavior."""
    if str(filepath).endswith(".jpg"):
        image.convert("RGB").save(filepath)
    else:
        image.save(filepath)
