import ast
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.constant import ColorOps
from src.color_processing_settings import ColorProcessingSettings
from src.color_slot import ColorSlot
from src.color_slot_state import ColorSlotState
from src.processing_mode import ProcessingMode
from src.render_settings import (
    DEFAULT_COLOR,
    DEFAULT_RENDER_SETTINGS,
    MAX_BRIGHTNESS,
    MAX_CONTRAST,
    MAX_SATURATION,
    MIN_BRIGHTNESS,
    MIN_CONTRAST,
    MIN_SATURATION,
    RenderSettings,
)

COLORS = ("#102030", "#405060", "#708090", "#a0b0c0")


class RenderSettingsTests(unittest.TestCase):
    def test_complete_defaults_match_application_behavior(self):
        settings = RenderSettings()

        self.assertEqual(settings.colors, (DEFAULT_COLOR,) * 4)
        self.assertEqual(settings.brightness, 75.0)
        self.assertEqual(settings.contrast, 100.0)
        self.assertEqual(settings.opacity, 100.0)
        self.assertEqual(settings.saturation, 100.0)
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

    def test_saturation_accepts_processing_range_boundaries(self):
        self.assertEqual(
            RenderSettings(saturation=MIN_SATURATION).saturation,
            MIN_SATURATION,
        )
        self.assertEqual(
            RenderSettings(saturation=MAX_SATURATION).saturation,
            MAX_SATURATION,
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
            saturation=135,
        )
        per_color = (
            ColorProcessingSettings(ColorOps.MULTIPLY, 65, 110, 100),
            ColorProcessingSettings(ColorOps.COLOR, 80, 95, 65),
            ColorProcessingSettings(ColorOps.SOFT_LIGHT, 70, 105, 40),
            ColorProcessingSettings(ColorOps.OVERLAY, 75, 100, 85),
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
        self.assertEqual(settings.global_processing.saturation, 135)
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
            72,
            145,
        )
        settings = RenderSettings().with_global_processing(global_processing)

        initialized = settings.with_processing_mode(ProcessingMode.PER_COLOR)

        self.assertEqual(
            initialized.per_color_processing,
            (global_processing,) * 4,
        )
        self.assertEqual(
            tuple(value.opacity for value in initialized.per_color_processing),
            (72, 72, 72, 72),
        )
        self.assertEqual(
            tuple(value.saturation for value in initialized.per_color_processing),
            (145, 145, 145, 145),
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
        color_one = ColorProcessingSettings(ColorOps.MULTIPLY, 60, 90, 25)
        color_two = ColorProcessingSettings(ColorOps.COLOR, 80, 110, 70)
        changed_color_one = ColorProcessingSettings(ColorOps.SCREEN, 65, 95, 45)
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
            {"saturation": MIN_SATURATION - 1},
            {"saturation": MAX_SATURATION + 1},
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

    def test_army_painter_swaps_complete_slot_state_only(self):
        from src.frame_main import ArmyPainter

        source_processing = ColorProcessingSettings(
            ColorOps.MULTIPLY, 65, 110, 25, 45
        )
        target_processing = ColorProcessingSettings(
            ColorOps.SOFT_LIGHT, 80, 95, 90, 175
        )
        global_processing = ColorProcessingSettings(
            ColorOps.SCREEN, 88, 123, 100, 130
        )
        per_color_processing = (
            source_processing,
            ColorProcessingSettings(),
            target_processing,
            ColorProcessingSettings(ColorOps.COLOR, 70, 105),
        )
        color_boxes = [{"bg": color} for color in COLORS]
        operation_var = SimpleNamespace(
            get=Mock(return_value=source_processing.blend_mode.display_name),
            set=Mock(),
        )
        brightness_slider = SimpleNamespace(
            get=Mock(return_value=source_processing.brightness),
            set=Mock(),
        )
        contrast_slider = SimpleNamespace(
            get=Mock(return_value=source_processing.contrast),
            set=Mock(),
        )
        opacity_slider = SimpleNamespace(
            get=Mock(return_value=source_processing.opacity),
            set=Mock(),
        )
        saturation_slider = SimpleNamespace(
            get=Mock(return_value=source_processing.saturation),
            set=Mock(),
        )
        painter = SimpleNamespace(
            render_settings=RenderSettings(
                primary_color=COLORS[0],
                secondary_color=COLORS[1],
                tint_color=COLORS[2],
                extra_color=COLORS[3],
                color_op=global_processing.blend_mode,
                brightness=global_processing.brightness,
                contrast=global_processing.contrast,
                saturation=global_processing.saturation,
                processing_mode=ProcessingMode.PER_COLOR,
                active_color_slot=ColorSlot.COLOR_1,
                per_color_processing=per_color_processing,
                _per_color_processing_initialized=True,
                apply_alpha=True,
                apply_dirt=True,
                tem_selected=(0, 2),
            ),
            get_current_pattern_colors=Mock(return_value=COLORS),
            frame_color_chooser=SimpleNamespace(
                color_boxes=color_boxes,
                draw_rgb_value=Mock(),
            ),
            frame_color_op_option=SimpleNamespace(
                var=operation_var,
                set_processing_context=Mock(),
            ),
            frame_sliders=SimpleNamespace(
                brightness_slider=brightness_slider,
                contrast_slider=contrast_slider,
                saturation_slider=saturation_slider,
                opacity_slider=opacity_slider,
            ),
            frame_channel_select=SimpleNamespace(
                lb=SimpleNamespace(curselection=Mock(return_value=(0, 2)))
            ),
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )

        changed = ArmyPainter.swap_color_slots(painter, 0, 2)

        self.assertTrue(changed)
        self.assertEqual(
            painter.render_settings.colors,
            (COLORS[2], COLORS[1], COLORS[0], COLORS[3]),
        )
        self.assertEqual(
            painter.render_settings.per_color_processing,
            (
                target_processing,
                per_color_processing[1],
                source_processing,
                per_color_processing[3],
            ),
        )
        self.assertEqual(painter.render_settings.global_processing, global_processing)
        self.assertEqual(
            tuple(
                processing.opacity
                for processing in painter.render_settings.per_color_processing
            ),
            (90, 100, 25, 100),
        )
        self.assertEqual(
            tuple(
                processing.saturation
                for processing in painter.render_settings.per_color_processing
            ),
            (175, 100, 45, 100),
        )
        self.assertIs(
            painter.render_settings.active_color_slot,
            ColorSlot.COLOR_1,
        )
        self.assertTrue(painter.render_settings.apply_alpha)
        self.assertTrue(painter.render_settings.apply_dirt)
        self.assertEqual(painter.render_settings.tem_selected, (0, 2))
        self.assertEqual(
            [color_box["bg"] for color_box in color_boxes],
            [COLORS[2], COLORS[1], COLORS[0], COLORS[3]],
        )
        painter.frame_color_chooser.draw_rgb_value.assert_called_once_with()
        painter.update_pattern_action_states.assert_called_once_with()
        painter.refresh_workspace.assert_called_once_with()

    def test_paste_color_preserves_target_processing_and_global_settings(self):
        from src.frame_main import ArmyPainter

        global_processing = ColorProcessingSettings(ColorOps.SCREEN, 85, 120, 95, 130)
        target_processing = ColorProcessingSettings(
            ColorOps.SOFT_LIGHT, 90, 95, 80, 120
        )
        per_color_processing = (
            ColorProcessingSettings(ColorOps.MULTIPLY, 70, 110, 60, 85),
            ColorProcessingSettings(),
            target_processing,
            ColorProcessingSettings(),
        )
        color_boxes = [{"bg": color} for color in COLORS]
        painter = SimpleNamespace(
            _color_slot_clipboard_color="#010203",
            render_settings=RenderSettings(
                primary_color=COLORS[0],
                secondary_color=COLORS[1],
                tint_color=COLORS[2],
                extra_color=COLORS[3],
                color_op=global_processing.blend_mode,
                brightness=global_processing.brightness,
                contrast=global_processing.contrast,
                opacity=global_processing.opacity,
                saturation=global_processing.saturation,
                per_color_processing=per_color_processing,
                _per_color_processing_initialized=True,
            ),
            frame_color_chooser=SimpleNamespace(
                color_boxes=color_boxes,
                draw_rgb_value=Mock(),
            ),
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )

        with patch.object(ArmyPainter, "sync_render_settings") as sync:
            changed = ArmyPainter.paste_color_slot(painter, 2)

        self.assertTrue(changed)
        sync.assert_called_once_with(painter)
        self.assertEqual(
            painter.render_settings.colors,
            (COLORS[0], COLORS[1], "#010203", COLORS[3]),
        )
        self.assertEqual(
            painter.render_settings.per_color_processing,
            per_color_processing,
        )
        self.assertEqual(painter.render_settings.global_processing, global_processing)
        self.assertEqual(
            [color_box["bg"] for color_box in color_boxes],
            [COLORS[0], COLORS[1], "#010203", COLORS[3]],
        )
        painter.frame_color_chooser.draw_rgb_value.assert_called_once_with()
        painter.update_pattern_action_states.assert_called_once_with()
        painter.refresh_workspace.assert_called_once_with()

    def test_copy_color_and_settings_captures_complete_slot_only(self):
        from src.frame_main import ArmyPainter

        copied_processing = ColorProcessingSettings(
            ColorOps.MULTIPLY, 70, 110, 60, 85
        )
        global_processing = ColorProcessingSettings(
            ColorOps.SCREEN, 85, 120, 95, 130
        )
        settings = RenderSettings(
            primary_color=COLORS[0],
            secondary_color=COLORS[1],
            tint_color=COLORS[2],
            extra_color=COLORS[3],
            color_op=global_processing.blend_mode,
            brightness=global_processing.brightness,
            contrast=global_processing.contrast,
            opacity=global_processing.opacity,
            saturation=global_processing.saturation,
            active_color_slot=ColorSlot.COLOR_4,
            per_color_processing=(
                ColorProcessingSettings(),
                copied_processing,
                ColorProcessingSettings(),
                ColorProcessingSettings(),
            ),
            _per_color_processing_initialized=True,
        )
        painter = SimpleNamespace(
            render_settings=settings,
            _color_slot_clipboard_state=None,
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )

        with patch.object(ArmyPainter, "sync_render_settings") as sync:
            ArmyPainter.copy_color_slot_with_settings(painter, 1)

        sync.assert_called_once_with(painter)
        copied = painter._color_slot_clipboard_state
        self.assertEqual(copied.color, COLORS[1])
        self.assertEqual(copied.processing, copied_processing)
        self.assertIs(painter.render_settings, settings)
        self.assertIs(painter.render_settings.active_color_slot, ColorSlot.COLOR_4)
        self.assertEqual(painter.render_settings.global_processing, global_processing)
        painter.update_pattern_action_states.assert_not_called()
        painter.refresh_workspace.assert_not_called()

    def test_paste_color_and_settings_replaces_complete_slot_in_both_modes(self):
        from src.frame_main import ArmyPainter

        copied = ColorSlotState(
            "#010203",
            ColorProcessingSettings(ColorOps.MULTIPLY, 70, 110, 60, 85),
        )
        global_processing = ColorProcessingSettings(
            ColorOps.SCREEN, 88, 123, 97, 130
        )
        original_per_color = (
            ColorProcessingSettings(),
            ColorProcessingSettings(ColorOps.SOFT_LIGHT, 90, 95, 80, 120),
            ColorProcessingSettings(ColorOps.COLOR, 65, 105, 75, 140),
            ColorProcessingSettings(),
        )

        for mode in (ProcessingMode.GLOBAL, ProcessingMode.PER_COLOR):
            with self.subTest(mode=mode):
                color_boxes = [{"bg": color} for color in COLORS]
                painter = SimpleNamespace(
                    _color_slot_clipboard_state=copied,
                    render_settings=RenderSettings(
                        primary_color=COLORS[0],
                        secondary_color=COLORS[1],
                        tint_color=COLORS[2],
                        extra_color=COLORS[3],
                        color_op=global_processing.blend_mode,
                        brightness=global_processing.brightness,
                        contrast=global_processing.contrast,
                        opacity=global_processing.opacity,
                        saturation=global_processing.saturation,
                        processing_mode=mode,
                        active_color_slot=ColorSlot.COLOR_2,
                        per_color_processing=original_per_color,
                        _per_color_processing_initialized=True,
                    ),
                    frame_color_chooser=SimpleNamespace(
                        color_boxes=color_boxes,
                        draw_rgb_value=Mock(),
                    ),
                    update_pattern_action_states=Mock(),
                    refresh_workspace=Mock(),
                )

                with patch.object(ArmyPainter, "sync_render_settings") as sync, patch.object(
                    ArmyPainter, "refresh_processing_controls"
                ) as refresh_controls:
                    changed = ArmyPainter.paste_color_slot_with_settings(painter, 1)

                self.assertTrue(changed)
                sync.assert_called_once_with(painter)
                self.assertIs(painter.render_settings.processing_mode, mode)
                self.assertEqual(
                    painter.render_settings.global_processing,
                    global_processing,
                )
                self.assertEqual(
                    painter.render_settings.colors,
                    (COLORS[0], copied.color, COLORS[2], COLORS[3]),
                )
                self.assertEqual(
                    painter.render_settings.per_color_processing,
                    (
                        original_per_color[0],
                        copied.processing,
                        original_per_color[2],
                        original_per_color[3],
                    ),
                )
                refresh_controls.assert_called_once_with(painter)
                painter.update_pattern_action_states.assert_called_once_with()
                painter.refresh_workspace.assert_called_once_with()

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
