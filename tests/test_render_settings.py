import ast
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import test_support  # noqa: F401 - installs the user-data path redirect
from src.constant import ColorOps
from src.image_process import ImageWorkbench
from src.render_settings import (
    DEFAULT_COLOR,
    DEFAULT_RENDER_SETTINGS,
    MAX_BRIGHTNESS,
    MAX_CONTRAST,
    MIN_BRIGHTNESS,
    MIN_CONTRAST,
    RenderSettings,
)

COLORS = ("#102030", "#405060", "#708090", "#a0b0c0")


class RenderSettingsTests(unittest.TestCase):
    def test_complete_defaults_match_application_behavior(self):
        settings = RenderSettings()

        self.assertEqual(settings.colors, (DEFAULT_COLOR,) * 4)
        self.assertEqual(settings.brightness, 75.0)
        self.assertEqual(settings.contrast, 100.0)
        self.assertFalse(settings.apply_alpha)
        self.assertFalse(settings.apply_dirt)
        self.assertFalse(settings.apply_spec)
        self.assertIs(settings.color_op, ColorOps.OVERLAY)
        self.assertEqual(settings.tem_selected, ())
        self.assertEqual(settings, DEFAULT_RENDER_SETTINGS)

    def test_settings_are_immutable(self):
        settings = RenderSettings()

        with self.assertRaises(FrozenInstanceError):
            settings.brightness = 50

    def test_four_colors_have_canonical_order(self):
        settings = RenderSettings(
            primary_color=COLORS[0],
            secondary_color=COLORS[1],
            tint_color=COLORS[2],
            extra_color=COLORS[3],
        )

        self.assertEqual(settings.colors, COLORS)
        self.assertIsInstance(settings.colors, tuple)

    def test_brightness_accepts_gui_range_boundaries(self):
        self.assertEqual(
            RenderSettings(brightness=MIN_BRIGHTNESS).brightness,
            MIN_BRIGHTNESS,
        )
        self.assertEqual(
            RenderSettings(brightness=MAX_BRIGHTNESS).brightness,
            MAX_BRIGHTNESS,
        )

    def test_contrast_accepts_gui_range_boundaries(self):
        self.assertEqual(
            RenderSettings(contrast=MIN_CONTRAST).contrast,
            MIN_CONTRAST,
        )
        self.assertEqual(
            RenderSettings(contrast=MAX_CONTRAST).contrast,
            MAX_CONTRAST,
        )

    def test_all_supported_operation_modes_use_enum(self):
        for operation in ColorOps:
            with self.subTest(operation=operation):
                self.assertIs(
                    RenderSettings(color_op=operation).color_op,
                    operation,
                )

    def test_dirt_specular_and_alpha_settings(self):
        settings = RenderSettings(
            apply_alpha=True,
            apply_dirt=True,
            apply_spec=True,
        )

        self.assertTrue(settings.apply_alpha)
        self.assertTrue(settings.apply_dirt)
        self.assertTrue(settings.apply_spec)

    def test_equal_values_produce_equal_settings(self):
        self.assertEqual(RenderSettings(), RenderSettings())
        self.assertEqual(hash(RenderSettings()), hash(RenderSettings()))

    def test_replace_does_not_mutate_original(self):
        original = RenderSettings()

        changed = replace(original, brightness=25, primary_color=COLORS[0])

        self.assertEqual(original, DEFAULT_RENDER_SETTINGS)
        self.assertEqual(changed.brightness, 25)
        self.assertEqual(changed.primary_color, COLORS[0])

    def test_worker_snapshot_is_independent_of_later_workbench_settings(self):
        workbench = ImageWorkbench()
        workbench.colors = COLORS
        snapshot = workbench.render_snapshot()
        captured = snapshot.get_render_settings()

        workbench.brightness = 20
        workbench.colors = tuple(reversed(COLORS))

        self.assertIs(snapshot.get_render_settings(), captured)
        self.assertEqual(captured.colors, COLORS)
        self.assertEqual(captured.brightness, 75.0)
        self.assertNotEqual(captured, workbench.get_render_settings())

    def test_invalid_levels_are_rejected_without_clamping(self):
        invalid_values = (
            {"brightness": MIN_BRIGHTNESS - 1},
            {"brightness": MAX_BRIGHTNESS + 1},
            {"contrast": MIN_CONTRAST - 1},
            {"contrast": MAX_CONTRAST + 1},
        )
        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValueError, "must be between"):
                    RenderSettings(**values)

    def test_invalid_colors_operation_and_selection_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "#RRGGBB"):
            RenderSettings(primary_color="red")
        with self.assertRaisesRegex(ValueError, "ColorOps"):
            RenderSettings(color_op="Overlay")
        with self.assertRaisesRegex(TypeError, "tuple of integer"):
            RenderSettings(tem_selected=[0, 1])
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            RenderSettings(tem_selected=(-1,))

    def test_compatibility_properties_build_one_authoritative_settings_value(self):
        workbench = ImageWorkbench()

        workbench.colors = COLORS
        workbench.brightness = 125
        workbench.contrast = 175
        workbench.apply_alpha = True
        workbench.apply_dirt = True
        workbench.apply_spec = True
        workbench.color_op = ColorOps.MULTIPLY.value
        workbench.tem_selected = (0, 2)

        settings = workbench.get_render_settings()
        self.assertIs(settings, workbench.render_settings)
        self.assertEqual(settings.colors, COLORS)
        self.assertEqual(settings.brightness, 125)
        self.assertEqual(settings.contrast, 175)
        self.assertTrue(settings.apply_alpha)
        self.assertTrue(settings.apply_dirt)
        self.assertTrue(settings.apply_spec)
        self.assertIs(settings.color_op, ColorOps.MULTIPLY)
        self.assertEqual(settings.tem_selected, (0, 2))

    def test_apply_render_settings_replaces_the_authoritative_value(self):
        workbench = ImageWorkbench()
        settings = RenderSettings(primary_color=COLORS[0])

        workbench.apply_render_settings(settings)

        self.assertIs(workbench.render_settings, settings)
        self.assertIs(workbench.get_render_settings(), settings)
        self.assertEqual(workbench.colors, settings.colors)

    def test_model_has_no_tkinter_or_image_dependency(self):
        source_path = Path(__file__).resolve().parents[1] / "src" / "render_settings.py"
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

        self.assertNotIn("tkinter", imports)
        self.assertNotIn("PIL", imports)
        self.assertNotIn("src.frame_main", imports)


if __name__ == "__main__":
    unittest.main()
