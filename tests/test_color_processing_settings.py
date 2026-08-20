import ast
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from src.blend_mode import BlendMode
from src.color_processing_settings import (
    DEFAULT_COLOR_PROCESSING_SETTINGS,
    MAX_BRIGHTNESS,
    MAX_CONTRAST,
    MAX_OPACITY,
    MAX_SATURATION,
    MIN_BRIGHTNESS,
    MIN_CONTRAST,
    MIN_OPACITY,
    MIN_SATURATION,
    ColorProcessingSettings,
)


class ColorProcessingSettingsTests(unittest.TestCase):
    def test_defaults_match_established_global_processing(self):
        settings = ColorProcessingSettings()

        self.assertIs(settings.blend_mode, BlendMode.OVERLAY)
        self.assertEqual(settings.brightness, 75.0)
        self.assertEqual(settings.contrast, 100.0)
        self.assertEqual(settings.opacity, 100.0)
        self.assertEqual(settings.saturation, 100.0)
        self.assertEqual(settings, DEFAULT_COLOR_PROCESSING_SETTINGS)

    def test_every_blend_mode_and_level_boundary_is_supported(self):
        for mode in BlendMode:
            with self.subTest(mode=mode):
                self.assertIs(
                    ColorProcessingSettings(blend_mode=mode).blend_mode,
                    mode,
                )

        settings = ColorProcessingSettings(
            brightness=MIN_BRIGHTNESS,
            contrast=MAX_CONTRAST,
            opacity=MIN_OPACITY,
            saturation=MAX_SATURATION,
        )
        self.assertEqual(settings.brightness, MIN_BRIGHTNESS)
        self.assertEqual(settings.contrast, MAX_CONTRAST)
        self.assertEqual(settings.opacity, MIN_OPACITY)
        self.assertEqual(settings.saturation, MAX_SATURATION)
        self.assertEqual(
            ColorProcessingSettings(brightness=MAX_BRIGHTNESS).brightness,
            MAX_BRIGHTNESS,
        )
        self.assertEqual(
            ColorProcessingSettings(contrast=MIN_CONTRAST).contrast,
            MIN_CONTRAST,
        )
        self.assertEqual(
            ColorProcessingSettings(opacity=MAX_OPACITY).opacity,
            MAX_OPACITY,
        )
        self.assertEqual(
            ColorProcessingSettings(saturation=MIN_SATURATION).saturation,
            MIN_SATURATION,
        )

    def test_values_are_immutable_and_replaceable_per_context(self):
        global_settings = ColorProcessingSettings()
        color_one = replace(
            global_settings,
            blend_mode=BlendMode.MULTIPLY,
            brightness=60,
            contrast=90,
            opacity=65,
            saturation=140,
        )

        self.assertEqual(global_settings, DEFAULT_COLOR_PROCESSING_SETTINGS)
        self.assertNotEqual(color_one, global_settings)
        with self.assertRaises(FrozenInstanceError):
            global_settings.brightness = 50

    def test_invalid_mode_and_levels_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "BlendMode"):
            ColorProcessingSettings(blend_mode="overlay")
        with self.assertRaisesRegex(TypeError, "must be a number"):
            ColorProcessingSettings(brightness=True)
        for values in (
            {"brightness": MIN_BRIGHTNESS - 1},
            {"brightness": MAX_BRIGHTNESS + 1},
            {"contrast": MIN_CONTRAST - 1},
            {"contrast": MAX_CONTRAST + 1},
            {"opacity": MIN_OPACITY - 1},
            {"opacity": MAX_OPACITY + 1},
            {"saturation": MIN_SATURATION - 1},
            {"saturation": MAX_SATURATION + 1},
        ):
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValueError, "must be between"):
                    ColorProcessingSettings(**values)

    def test_model_has_no_profile_mask_gui_or_image_dependency(self):
        source_path = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "color_processing_settings.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )

        self.assertEqual(imports, {"dataclasses", "src.blend_mode"})


if __name__ == "__main__":
    unittest.main()
