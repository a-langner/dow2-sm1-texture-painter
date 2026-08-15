import unittest

from PIL import Image

import test_support  # noqa: F401 - installs the user-data path redirect
from src.blend_mode import BlendMode
from src.render_settings import DEFAULT_COLOR, RenderSettings
from src.texture_renderer import TextureRenderer
from src.texture_set import TextureSet

BASE = (50, 100, 200)
BLEND = "#c85028"
EXPECTED_RGB = {
    BlendMode.NORMAL: (200, 80, 40),
    BlendMode.MULTIPLY: (39, 31, 31),
    BlendMode.SCREEN: (211, 149, 209),
    BlendMode.OVERLAY: (78, 62, 162),
    BlendMode.SOFT_LIGHT: (72, 76, 169),
    BlendMode.HARD_LIGHT: (167, 62, 62),
    BlendMode.COLOR: (184, 64, 24),
    BlendMode.LINEAR_BURN: (0, 0, 0),
    BlendMode.LINEAR_DODGE: (250, 180, 240),
}


def textures_for_channel(channel_index):
    diffuse = Image.new("RGBA", (1, 1), (*BASE, 255))
    channels = [Image.new("L", (1, 1), 0) for _ in range(4)]
    channels[channel_index] = Image.new("L", (1, 1), 255)
    return TextureSet(diffuse, Image.merge("RGBA", tuple(channels)))


def settings_for_channel(mode, channel_index, apply_alpha):
    colors = [DEFAULT_COLOR] * 4
    colors[channel_index] = BLEND
    return RenderSettings(
        primary_color=colors[0],
        secondary_color=colors[1],
        tint_color=colors[2],
        extra_color=colors[3],
        brightness=100,
        contrast=100,
        color_op=mode,
        apply_alpha=apply_alpha,
        tem_selected=(channel_index,),
    )


class BlendModeChannelAndAlphaTests(unittest.TestCase):
    def test_every_mode_uses_each_rgba_team_colour_channel(self):
        renderer = TextureRenderer()
        for mode, expected_rgb in EXPECTED_RGB.items():
            for channel_index in range(4):
                textures = textures_for_channel(channel_index)
                with self.subTest(mode=mode, channel=channel_index):
                    result = renderer.render(
                        textures,
                        settings_for_channel(mode, channel_index, False),
                    )
                    self.assertEqual(result.getpixel((0, 0)), (*expected_rgb, 255))

    def test_apply_alpha_only_replaces_alpha_for_every_mode_and_channel(self):
        renderer = TextureRenderer()
        for mode, expected_rgb in EXPECTED_RGB.items():
            for channel_index in range(4):
                textures = textures_for_channel(channel_index)
                without_alpha = renderer.render(
                    textures,
                    settings_for_channel(mode, channel_index, False),
                )
                with_alpha = renderer.render(
                    textures,
                    settings_for_channel(mode, channel_index, True),
                )
                with self.subTest(mode=mode, channel=channel_index):
                    self.assertEqual(without_alpha.getpixel((0, 0))[3], 255)
                    self.assertEqual(with_alpha.getpixel((0, 0))[3], 0)
                    self.assertEqual(
                        with_alpha.getpixel((0, 0))[:3],
                        without_alpha.getpixel((0, 0))[:3],
                    )
                    self.assertEqual(
                        renderer.render_team_colour(
                            textures,
                            settings_for_channel(mode, channel_index, True),
                        ).getpixel((0, 0)),
                        255,
                    )
