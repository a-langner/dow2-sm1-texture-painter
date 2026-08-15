import ast
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import test_support  # noqa: F401 - installs the user-data path redirect
from src.constant import ColorOps
from src.color_processing_settings import ColorProcessingSettings
from src.color_slot import ColorSlot
from src.processing_mode import ProcessingMode
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
        self.assertIs(settings.processing_mode, ProcessingMode.GLOBAL)
        self.assertIs(settings.active_color_slot, ColorSlot.COLOR_1)
        self.assertEqual(
            settings.per_color_processing,
            (ColorProcessingSettings(),) * 4,
        )
        self.assertEqual(settings.global_processing, ColorProcessingSettings())
        self.assertFalse(settings.per_color_processing_initialized)
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

    def test_active_slot_is_independent_of_actual_color_values(self):
        original = RenderSettings(
            primary_color=COLORS[0],
            secondary_color=COLORS[1],
            tint_color=COLORS[2],
            extra_color=COLORS[3],
        )

        changed = original.with_active_color_slot(ColorSlot.COLOR_3)

        self.assertIs(changed.active_color_slot, ColorSlot.COLOR_3)
        self.assertEqual(changed.colors, original.colors)
        self.assertEqual(changed.global_processing, original.global_processing)
        self.assertEqual(
            changed.per_color_processing,
            original.per_color_processing,
        )

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

    def test_worker_snapshot_is_independent_of_later_settings(self):
        captured = RenderSettings(
            primary_color=COLORS[0],
            secondary_color=COLORS[1],
            tint_color=COLORS[2],
            extra_color=COLORS[3],
        )
        later = replace(captured, brightness=20, primary_color=COLORS[3])

        self.assertEqual(captured.colors, COLORS)
        self.assertEqual(captured.brightness, 75.0)
        self.assertNotEqual(captured, later)

    def test_global_and_four_per_color_contexts_are_retained(self):
        global_processing = ColorProcessingSettings(
            blend_mode=ColorOps.OVERLAY,
            brightness=75,
            contrast=100,
        )
        per_color = (
            ColorProcessingSettings(ColorOps.MULTIPLY, 65, 110),
            ColorProcessingSettings(ColorOps.COLOR, 80, 95),
            ColorProcessingSettings(ColorOps.SOFT_LIGHT, 70, 105),
            ColorProcessingSettings(ColorOps.OVERLAY, 75, 100),
        )
        settings = RenderSettings().with_global_processing(global_processing)
        for index, processing in enumerate(per_color):
            settings = settings.with_color_processing(index, processing)

        for mode in (
            ProcessingMode.PER_COLOR,
            ProcessingMode.GLOBAL,
            ProcessingMode.PER_COLOR,
        ):
            settings = settings.with_processing_mode(mode)

        self.assertIs(settings.processing_mode, ProcessingMode.PER_COLOR)
        self.assertEqual(settings.global_processing, global_processing)
        self.assertEqual(settings.per_color_processing, per_color)
        self.assertTrue(settings.per_color_processing_initialized)

    def test_complete_processing_state_can_be_restored_atomically(self):
        global_processing = ColorProcessingSettings(ColorOps.SCREEN, 80, 120)
        per_color = (
            ColorProcessingSettings(ColorOps.OVERLAY, 10, 20),
            ColorProcessingSettings(ColorOps.MULTIPLY, 30, 40),
            ColorProcessingSettings(ColorOps.COLOR, 50, 60),
            ColorProcessingSettings(ColorOps.HARD_LIGHT, 70, 80),
        )

        restored = RenderSettings().with_processing_state(
            ProcessingMode.PER_COLOR, global_processing, per_color
        )

        self.assertIs(restored.processing_mode, ProcessingMode.PER_COLOR)
        self.assertEqual(restored.global_processing, global_processing)
        self.assertEqual(restored.per_color_processing, per_color)
        self.assertTrue(restored.per_color_processing_initialized)

    def test_first_per_color_use_copies_then_current_global_values(self):
        global_processing = ColorProcessingSettings(
            ColorOps.HARD_LIGHT,
            65,
            110,
        )
        settings = RenderSettings().with_global_processing(global_processing)

        initialized = settings.with_processing_mode(ProcessingMode.PER_COLOR)

        self.assertEqual(
            initialized.per_color_processing,
            (global_processing,) * 4,
        )
        self.assertTrue(initialized.per_color_processing_initialized)
        self.assertFalse(settings.per_color_processing_initialized)

    def test_later_mode_switches_do_not_reinitialize_individual_values(self):
        color_one = ColorProcessingSettings(ColorOps.MULTIPLY, 60, 90)
        settings = RenderSettings().with_processing_mode(ProcessingMode.PER_COLOR)
        settings = settings.with_color_processing(0, color_one)
        settings = settings.with_processing_mode(ProcessingMode.GLOBAL)
        settings = settings.with_global_processing(
            ColorProcessingSettings(ColorOps.COLOR, 80, 110)
        )

        restored = settings.with_processing_mode(ProcessingMode.PER_COLOR)

        self.assertEqual(restored.per_color_processing[0], color_one)
        self.assertEqual(
            restored.per_color_processing[1:],
            (ColorProcessingSettings(),) * 3,
        )

    def test_one_per_color_context_can_change_independently(self):
        original = RenderSettings()
        color_two = ColorProcessingSettings(ColorOps.COLOR, 80, 95)

        changed = original.with_color_processing(1, color_two)

        self.assertEqual(changed.per_color_processing[1], color_two)
        self.assertEqual(
            changed.per_color_processing[:1] + changed.per_color_processing[2:],
            original.per_color_processing[:1] + original.per_color_processing[2:],
        )
        self.assertEqual(changed.global_processing, original.global_processing)

    def test_distinct_slots_survive_per_color_global_per_color_switch(self):
        color_one = ColorProcessingSettings(ColorOps.MULTIPLY, 60, 90)
        color_two = ColorProcessingSettings(ColorOps.COLOR, 80, 110)
        changed_color_one = ColorProcessingSettings(ColorOps.SCREEN, 65, 95)
        settings = RenderSettings().with_processing_mode(
            ProcessingMode.PER_COLOR
        )
        settings = settings.with_color_processing(0, color_one)
        settings = settings.with_color_processing(1, color_two)

        settings = settings.with_color_processing(0, changed_color_one)
        settings = settings.with_processing_mode(ProcessingMode.GLOBAL)
        settings = settings.with_processing_mode(ProcessingMode.PER_COLOR)

        self.assertEqual(settings.per_color_processing[0], changed_color_one)
        self.assertEqual(settings.per_color_processing[1], color_two)
        self.assertEqual(
            settings.per_color_processing[2:],
            (ColorProcessingSettings(),) * 2,
        )

    def test_active_processing_routes_to_global_or_selected_slot(self):
        global_processing = ColorProcessingSettings(ColorOps.OVERLAY, 75, 100)
        color_three = ColorProcessingSettings(ColorOps.COLOR, 80, 95)
        settings = RenderSettings().with_global_processing(global_processing)

        global_changed = settings.with_active_processing(
            ColorProcessingSettings(ColorOps.MULTIPLY, 60, 90)
        )
        self.assertEqual(
            global_changed.active_processing,
            ColorProcessingSettings(ColorOps.MULTIPLY, 60, 90),
        )
        self.assertFalse(global_changed.per_color_processing_initialized)

        per_color = settings.with_processing_mode(ProcessingMode.PER_COLOR)
        per_color = per_color.with_active_color_slot(ColorSlot.COLOR_3)
        per_color = per_color.with_active_processing(color_three)

        self.assertEqual(per_color.active_processing, color_three)
        self.assertEqual(per_color.per_color_processing[2], color_three)
        self.assertEqual(per_color.global_processing, global_processing)

    def test_per_color_context_requires_exactly_four_typed_values(self):
        with self.assertRaisesRegex(TypeError, "tuple of four"):
            RenderSettings(per_color_processing=(ColorProcessingSettings(),))
        with self.assertRaisesRegex(TypeError, "ColorProcessingSettings"):
            RenderSettings(per_color_processing=(None, None, None, None))
        with self.assertRaisesRegex(ValueError, "between 0 and 3"):
            RenderSettings().with_color_processing(4, ColorProcessingSettings())

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
        with self.assertRaisesRegex(ValueError, "ProcessingMode"):
            RenderSettings(processing_mode="global")
        with self.assertRaisesRegex(ValueError, "ColorSlot"):
            RenderSettings(active_color_slot=0)
        with self.assertRaisesRegex(TypeError, "tuple of integer"):
            RenderSettings(tem_selected=[0, 1])
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            RenderSettings(tem_selected=(-1,))

    def test_army_painter_collects_one_authoritative_settings_value(self):
        from src.frame_main import ArmyPainter

        painter = SimpleNamespace(
            render_settings=RenderSettings(
                apply_alpha=True,
                apply_dirt=True,
                apply_spec=True,
                color_op=ColorOps.MULTIPLY,
            ),
            get_current_pattern_colors=Mock(return_value=COLORS),
            frame_sliders=SimpleNamespace(
                brightness_slider=SimpleNamespace(get=Mock(return_value=125)),
                contrast_slider=SimpleNamespace(get=Mock(return_value=175)),
            ),
            frame_channel_select=SimpleNamespace(
                lb=SimpleNamespace(curselection=Mock(return_value=(0, 2)))
            ),
        )

        ArmyPainter.sync_render_settings(painter)

        settings = painter.render_settings
        self.assertEqual(settings.colors, COLORS)
        self.assertEqual(settings.brightness, 125)
        self.assertEqual(settings.contrast, 175)
        self.assertTrue(settings.apply_alpha)
        self.assertTrue(settings.apply_dirt)
        self.assertTrue(settings.apply_spec)
        self.assertIs(settings.color_op, ColorOps.MULTIPLY)
        self.assertEqual(settings.tem_selected, (0, 2))

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
