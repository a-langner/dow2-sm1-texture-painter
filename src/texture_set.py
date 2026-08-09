"""Source-image state used by texture rendering."""

from dataclasses import dataclass

from PIL import Image


@dataclass
class TextureSet:
    """One renderable set of source textures.

    Incoming Pillow images are retained directly rather than copied. Once a set
    is exposed as active or submitted for rendering, its image references and
    pixel data are treated as read-only; loading replaces the whole container.
    """

    diffuse: Image.Image
    team_color: Image.Image | None = None
    dirt: Image.Image | None = None
    specular: Image.Image | None = None

    def __post_init__(self) -> None:
        if self.diffuse is None:
            raise ValueError("TextureSet requires a diffuse image.")

    @property
    def dimensions(self) -> tuple[int, int]:
        return self.diffuse.size

    def copy_for_render(self) -> "TextureSet":
        """Copy the container while retaining its read-only image references."""
        return TextureSet(
            diffuse=self.diffuse,
            team_color=self.team_color,
            dirt=self.dirt,
            specular=self.specular,
        )
