import unittest

from PIL import Image

import test_support  # noqa: F401 - installs the user-data path redirect
from src.blend_mode import BlendMode
from src.color_processing_settings import ColorProcessingSettings
from src.processing_mode import ProcessingMode
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

    def test_opacity_scales_only_the_team_color_mask_strength(self):
        textures = textures_for_channel(0)
        full_strength = settings_for_channel(BlendMode.NORMAL, 0, False)
        no_strength = RenderSettings(
            primary_color=full_strength.primary_color,
            brightness=full_strength.brightness,
            contrast=full_strength.contrast,
            opacity=0,
            color_op=full_strength.color_op,
        )
        half_strength = RenderSettings(
            primary_color=full_strength.primary_color,
            brightness=full_strength.brightness,
            contrast=full_strength.contrast,
            opacity=50,
            color_op=full_strength.color_op,
        )

        self.assertEqual(
            TextureRenderer().render(textures, full_strength).getpixel((0, 0)),
            (*EXPECTED_RGB[BlendMode.NORMAL], 255),
        )
        self.assertEqual(
            TextureRenderer().render(textures, no_strength).getpixel((0, 0)),
            (*BASE, 255),
        )
        self.assertEqual(
            TextureRenderer().render(textures, half_strength).getpixel((0, 0)),
            (125, 90, 120, 255),
        )

    def test_per_color_mode_maps_independent_processing_to_rgba_channels(self):
        diffuse = Image.new("RGBA", (4, 1), (*BASE, 255))
        channels = []
        for channel_index in range(4):
            channel = Image.new("L", (4, 1), 0)
            channel.putpixel((channel_index, 0), 255)
            channels.append(channel)
        textures = TextureSet(diffuse, Image.merge("RGBA", tuple(channels)))
        colors = ("#c85028", "#2878c8", "#d0b020", "#40b060")
        processing = (
            ColorProcessingSettings(BlendMode.MULTIPLY, 60, 110),
            ColorProcessingSettings(BlendMode.COLOR, 80, 95),
            ColorProcessingSettings(BlendMode.SOFT_LIGHT, 70, 105),
            ColorProcessingSettings(BlendMode.LINEAR_BURN, 65, 100),
        )
        common = dict(
            primary_color=colors[0],
            secondary_color=colors[1],
            tint_color=colors[2],
            extra_color=colors[3],
        )
        per_color_settings = RenderSettings(
            **common,
            processing_mode=ProcessingMode.PER_COLOR,
            per_color_processing=processing,
        )

        result = TextureRenderer().render(textures, per_color_settings)
        expected_pixels = []
        for channel_index, context in enumerate(processing):
            global_settings = RenderSettings(
                **common,
                color_op=context.blend_mode,
                brightness=context.brightness,
                contrast=context.contrast,
            )
            global_result = TextureRenderer().render(textures, global_settings)
            expected_pixels.append(global_result.getpixel((channel_index, 0)))

        self.assertEqual(
            [result.getpixel((index, 0)) for index in range(4)],
            expected_pixels,
        )
        self.assertEqual(len(set(expected_pixels)), 4)

    def test_global_mode_ignores_retained_per_color_values(self):
        textures = textures_for_channel(0)
        legacy_global = settings_for_channel(BlendMode.OVERLAY, 0, True)
        distinct_per_color = (
            ColorProcessingSettings(BlendMode.NORMAL, 20, 20),
            ColorProcessingSettings(BlendMode.SCREEN, 40, 60),
            ColorProcessingSettings(BlendMode.COLOR, 80, 120),
            ColorProcessingSettings(BlendMode.LINEAR_DODGE, 140, 180),
        )
        retained = RenderSettings(
            primary_color=legacy_global.primary_color,
            secondary_color=legacy_global.secondary_color,
            tint_color=legacy_global.tint_color,
            extra_color=legacy_global.extra_color,
            brightness=legacy_global.brightness,
            contrast=legacy_global.contrast,
            color_op=legacy_global.color_op,
            apply_alpha=legacy_global.apply_alpha,
            tem_selected=legacy_global.tem_selected,
            processing_mode=ProcessingMode.GLOBAL,
            per_color_processing=distinct_per_color,
        )

        self.assertEqual(
            TextureRenderer().render(textures, retained).tobytes(),
            TextureRenderer().render(textures, legacy_global).tobytes(),
        )
