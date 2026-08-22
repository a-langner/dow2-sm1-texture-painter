import unittest
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from src.color_slot import ColorSlot
from src.color_slot_state import CustomFavoriteIdentity
from src.color_pattern_handler import PatternMarkerColor
from src.favorite_color import FavoriteColorLibrary
from src.frame_main import ArmyPainter
from src.paint_catalog import PaintCatalog, PaintColor
from src.render_settings import DEFAULT_RENDER_SETTINGS
from src.widget import SelectedColor
from src.workspace_history import (
    UNDO_HISTORY_LIMIT,
    EditableWorkspaceState,
    WorkspaceHistory,
)


def state_with_brightness(brightness: float) -> EditableWorkspaceState:
    settings = replace(DEFAULT_RENDER_SETTINGS, brightness=brightness)
    return EditableWorkspaceState.from_render_settings(settings, None)


class WorkspaceHistoryTests(unittest.TestCase):
    def test_undo_and_redo_exchange_independent_snapshots(self):
        history = WorkspaceHistory()
        before = state_with_brightness(10)
        after = state_with_brightness(20)

        self.assertTrue(history.record_edit(before, after))
        self.assertEqual(history.undo(after), before)
        self.assertEqual(history.redo(before), after)

    def test_new_edit_after_undo_clears_redo(self):
        history = WorkspaceHistory()
        first = state_with_brightness(10)
        second = state_with_brightness(20)
        replacement = state_with_brightness(30)
        history.record_edit(first, second)
        history.undo(second)

        history.record_edit(first, replacement)

        self.assertFalse(history.can_redo)

    def test_no_op_after_undo_preserves_redo(self):
        history = WorkspaceHistory()
        first = state_with_brightness(10)
        second = state_with_brightness(20)
        history.record_edit(first, second)
        history.undo(second)

        self.assertFalse(history.record_edit(first, first))

        self.assertTrue(history.can_redo)
        self.assertEqual(history.redo(first), second)

    def test_history_discards_oldest_state_above_limit(self):
        history = WorkspaceHistory()
        states = [
            state_with_brightness(index)
            for index in range(UNDO_HISTORY_LIMIT + 2)
        ]
        for previous, current in zip(states, states[1:]):
            history.record_edit(previous, current)

        self.assertEqual(history.undo_count, UNDO_HISTORY_LIMIT)
        restored = None
        current = states[-1]
        while history.can_undo:
            restored = history.undo(current)
            current = restored
        self.assertEqual(restored, states[1])

    def test_no_op_is_not_recorded(self):
        history = WorkspaceHistory()
        state = state_with_brightness(10)

        self.assertFalse(history.record_edit(state, state))
        self.assertFalse(history.can_undo)

    def test_clear_discards_both_stacks(self):
        history = WorkspaceHistory()
        before = state_with_brightness(10)
        after = state_with_brightness(20)
        history.record_edit(before, after)
        history.undo(after)

        history.clear()

        self.assertFalse(history.can_undo)
        self.assertFalse(history.can_redo)

    def test_pattern_marker_and_reorder_leave_workspace_history_unchanged(self):
        history = WorkspaceHistory()
        first = state_with_brightness(10)
        second = state_with_brightness(20)
        history.record_edit(first, second)
        history.undo(second)
        before = (history.undo_count, history.redo_count)
        controller = Mock()
        controller.set_marker_color.return_value = SimpleNamespace(changed=True)
        controller.reorder_pattern.return_value = SimpleNamespace(changed=True)
        painter = SimpleNamespace(
            workspace_history=history,
            pattern_controller=controller,
            dialogs=Mock(),
        )

        marker_changed = ArmyPainter.set_pattern_marker_color(
            painter, "User", PatternMarkerColor.BLUE
        )
        reordered = ArmyPainter.reorder_user_pattern(painter, "User", 0)

        self.assertTrue(marker_changed)
        self.assertTrue(reordered)
        self.assertEqual((history.undo_count, history.redo_count), before)
        controller.set_marker_color.assert_called_once_with(
            "User", PatternMarkerColor.BLUE
        )
        controller.reorder_pattern.assert_called_once_with("User", 0)

    def test_capture_excludes_active_slot_focus(self):
        first = EditableWorkspaceState.from_render_settings(
            DEFAULT_RENDER_SETTINGS, None
        )
        second = EditableWorkspaceState.from_render_settings(
            DEFAULT_RENDER_SETTINGS.with_active_color_slot(
                ColorSlot.COLOR_2
            ),
            None,
        )

        self.assertEqual(first, second)

    def test_snapshot_contains_only_lightweight_editable_fields(self):
        self.assertEqual(
            {field.name for field in fields(EditableWorkspaceState)},
            {
                "color_slot_states",
                "global_processing",
                "processing_mode",
                "per_color_processing_initialized",
                "selected_channels",
                "apply_alpha",
                "apply_dirt",
                "apply_spec",
                "team_color_mask_variant",
                "selected_pattern_name",
            },
        )
        source = Path(__file__).resolve().parents[1] / "src" / "workspace_history.py"
        source_text = source.read_text(encoding="utf-8")
        self.assertNotIn("PIL", source_text)
        self.assertNotIn("TextureSet", source_text)

    def test_color_picker_edit_uses_central_history_boundary(self):
        history = WorkspaceHistory()
        painter = SimpleNamespace(
            render_settings=DEFAULT_RENDER_SETTINGS,
            active_team_color_mask_variant=None,
            workspace_history=history,
            _history_recording_suspended=False,
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )
        before = EditableWorkspaceState.from_render_settings(
            DEFAULT_RENDER_SETTINGS, None
        )

        ArmyPainter.on_color_changed(painter, 0, "#102030")

        after = EditableWorkspaceState.from_render_settings(
            painter.render_settings, None
        )
        self.assertEqual(history.undo(after), before)
        self.assertEqual(painter.render_settings.primary_color, "#102030")

    def test_favorite_library_management_does_not_enter_workspace_history(self):
        history = WorkspaceHistory()
        paint = PaintColor("citadel-blue", "Citadel Blue", 1, 2, 3)
        library = FavoriteColorLibrary(PaintCatalog((paint,)))

        library.add_color("#010203")
        library.remove_citadel(paint.id)
        added = library.add_color("#102030", custom_name="Armor Blue").favorite
        library.rename_custom(added.id, "Renamed Blue")
        library.remove_custom(added.id)

        self.assertEqual(history.undo_count, 0)
        self.assertEqual(history.redo_count, 0)

    def test_applying_named_custom_favorite_is_undoable_slot_edit(self):
        history = WorkspaceHistory()
        identity = CustomFavoriteIdentity("custom-1", "Armor Blue")
        painter = SimpleNamespace(
            render_settings=DEFAULT_RENDER_SETTINGS,
            active_team_color_mask_variant=None,
            workspace_history=history,
            _history_recording_suspended=False,
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )
        before = EditableWorkspaceState.from_render_settings(
            DEFAULT_RENDER_SETTINGS, None
        )

        ArmyPainter.on_color_changed(
            painter,
            0,
            SelectedColor("#102030", identity),
        )

        after = EditableWorkspaceState.from_render_settings(
            painter.render_settings, None
        )
        restored_before = history.undo(after)
        restored_after = history.redo(restored_before)
        self.assertEqual(restored_before, before)
        self.assertEqual(
            restored_after.color_slot_states[0].custom_favorite,
            identity,
        )

    def test_slider_drag_records_only_press_and_final_release_states(self):
        history = WorkspaceHistory()
        painter = SimpleNamespace(
            render_settings=DEFAULT_RENDER_SETTINGS,
            active_team_color_mask_variant=None,
            workspace_history=history,
            _history_recording_suspended=False,
            _processing_controls_refreshing=False,
            _slider_edit_start=None,
            request_workspace_preview=Mock(),
        )
        before = EditableWorkspaceState.from_render_settings(
            DEFAULT_RENDER_SETTINGS, None
        )

        ArmyPainter.begin_slider_edit(painter)
        for brightness in (72.0, 68.0, 54.0, 42.0):
            ArmyPainter.on_slider_update(
                painter, brightness, 100.0, 100.0, 100.0
            )
        self.assertEqual(history.undo_count, 0)
        ArmyPainter.end_slider_edit(painter)

        self.assertEqual(history.undo_count, 1)
        after = EditableWorkspaceState.from_render_settings(
            painter.render_settings, None
        )
        self.assertEqual(history.undo(after), before)
        self.assertEqual(history.redo(before), after)

    def test_resetting_an_already_default_slot_is_not_recorded(self):
        history = WorkspaceHistory()
        painter = SimpleNamespace(
            render_settings=DEFAULT_RENDER_SETTINGS,
            active_team_color_mask_variant=None,
            workspace_history=history,
            _history_recording_suspended=False,
            frame_color_chooser=SimpleNamespace(
                color_boxes=[{"bg": "#808080"} for _ in range(4)],
                draw_rgb_value=Mock(),
            ),
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )

        with patch.object(ArmyPainter, "sync_render_settings"):
            ArmyPainter.reset_color_slot(painter, 0)

        self.assertFalse(history.can_undo)
        painter.frame_color_chooser.draw_rgb_value.assert_not_called()
        painter.refresh_workspace.assert_not_called()

    def test_slider_press_and_release_without_change_is_not_recorded(self):
        history = WorkspaceHistory()
        painter = SimpleNamespace(
            render_settings=DEFAULT_RENDER_SETTINGS,
            active_team_color_mask_variant=None,
            workspace_history=history,
            _history_recording_suspended=False,
            _processing_controls_refreshing=False,
            _slider_edit_start=None,
        )

        ArmyPainter.begin_slider_edit(painter)
        ArmyPainter.end_slider_edit(painter)

        self.assertFalse(history.can_undo)

    def test_undo_restores_controls_and_refreshes_once(self):
        history = WorkspaceHistory()
        before_settings = replace(
            DEFAULT_RENDER_SETTINGS,
            primary_color="#102030",
            brightness=61.0,
            tem_selected=(0, 2),
            apply_alpha=True,
        )
        after_settings = replace(
            before_settings,
            primary_color="#405060",
            brightness=82.0,
            tem_selected=(1, 3),
            apply_alpha=False,
        )
        before = EditableWorkspaceState.from_render_settings(before_settings, None)
        after = EditableWorkspaceState.from_render_settings(after_settings, None)
        history.record_edit(before, after)
        listbox = Mock()
        painter = SimpleNamespace(
            render_settings=after_settings,
            active_team_color_mask_variant=None,
            workspace_history=history,
            _history_recording_suspended=False,
            frame_color_chooser=SimpleNamespace(
                color_boxes=[{"bg": color} for color in after_settings.colors],
                draw_rgb_value=Mock(),
            ),
            frame_channel_select=SimpleNamespace(
                lb=listbox,
                apply_alpha=SimpleNamespace(set=Mock()),
            ),
            frame_army_pattern=SimpleNamespace(
                get_selected_pattern_name=Mock(return_value=None),
                clear_selection=Mock(),
                select_pattern=Mock(return_value="pattern-item"),
            ),
            edit_menu=Mock(),
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )

        with patch.object(
            ArmyPainter, "refresh_processing_controls"
        ) as refresh, patch.object(
            ArmyPainter, "sync_team_color_mask_variant_selector"
        ):
            self.assertTrue(ArmyPainter.undo(painter))

        self.assertEqual(painter.render_settings, before_settings)
        self.assertEqual(
            [box["bg"] for box in painter.frame_color_chooser.color_boxes],
            list(before_settings.colors),
        )
        listbox.selection_clear.assert_called_once_with(0, "end")
        listbox.selection_set.assert_has_calls([call(0), call(2)])
        painter.frame_channel_select.apply_alpha.set.assert_called_once_with(True)
        refresh.assert_called_once_with(painter)
        painter.refresh_workspace.assert_called_once_with()
        painter.update_pattern_action_states.assert_called_once_with()
        self.assertTrue(history.can_redo)

        painter.frame_color_chooser.draw_rgb_value.reset_mock()
        listbox.reset_mock()
        painter.frame_channel_select.apply_alpha.set.reset_mock()
        painter.refresh_workspace.reset_mock()
        painter.update_pattern_action_states.reset_mock()
        with patch.object(
            ArmyPainter, "refresh_processing_controls"
        ) as redo_refresh, patch.object(
            ArmyPainter, "sync_team_color_mask_variant_selector"
        ):
            self.assertTrue(ArmyPainter.redo(painter))

        self.assertEqual(painter.render_settings, after_settings)
        self.assertEqual(
            [box["bg"] for box in painter.frame_color_chooser.color_boxes],
            list(after_settings.colors),
        )
        listbox.selection_clear.assert_called_once_with(0, "end")
        listbox.selection_set.assert_has_calls([call(1), call(3)])
        painter.frame_channel_select.apply_alpha.set.assert_called_once_with(False)
        redo_refresh.assert_called_once_with(painter)
        painter.refresh_workspace.assert_called_once_with()
        painter.update_pattern_action_states.assert_called_once_with()
        self.assertTrue(history.can_undo)
        self.assertFalse(history.can_redo)

    def test_workspace_boundary_clears_undo_redo_and_slider_gesture(self):
        history = WorkspaceHistory()
        first = state_with_brightness(10)
        second = state_with_brightness(20)
        history.record_edit(first, second)
        history.undo(second)
        painter = SimpleNamespace(
            workspace_history=history,
            _slider_edit_start=first,
            edit_menu=Mock(),
        )

        ArmyPainter.clear_workspace_history(painter)

        self.assertFalse(history.can_undo)
        self.assertFalse(history.can_redo)
        self.assertIsNone(painter._slider_edit_start)
        painter.edit_menu.entryconfigure.assert_has_calls(
            [
                call("Undo", state="disabled"),
                call("Redo", state="disabled"),
            ]
        )

    def test_undo_pattern_application_clears_selection_and_modified_state(self):
        history = WorkspaceHistory()
        selected_name = "Applied Pattern"
        pattern_panel = SimpleNamespace()
        pattern_panel.selected_name = selected_name
        pattern_panel.get_selected_pattern_name = lambda: pattern_panel.selected_name
        pattern_panel.get_selected_pattern = lambda: (
            SimpleNamespace(name=pattern_panel.selected_name, is_user=False)
            if pattern_panel.selected_name is not None
            else None
        )
        pattern_panel.clear_selection = lambda: setattr(
            pattern_panel, "selected_name", None
        )
        pattern_panel.select_pattern = lambda name: setattr(
            pattern_panel, "selected_name", name
        )
        listbox = Mock()
        listbox.curselection.return_value = ()
        painter = SimpleNamespace(
            render_settings=DEFAULT_RENDER_SETTINGS,
            active_team_color_mask_variant=None,
            workspace_history=history,
            _history_recording_suspended=False,
            _history_pattern_selection_name=None,
            frame_army_pattern=pattern_panel,
            frame_color_chooser=SimpleNamespace(
                color_boxes=[{"bg": "#808080"} for _ in range(4)],
                draw_rgb_value=Mock(),
            ),
            frame_channel_select=SimpleNamespace(
                lb=listbox,
                apply_alpha=SimpleNamespace(set=Mock()),
            ),
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )

        ArmyPainter._apply_pattern_colors(
            painter,
            ["#102030", "#405060", "#708090", "#a0b0c0"],
        )
        self.assertEqual(pattern_panel.selected_name, selected_name)
        with patch.object(ArmyPainter, "refresh_processing_controls"), patch.object(
            ArmyPainter, "sync_team_color_mask_variant_selector"
        ):
            self.assertTrue(ArmyPainter.undo(painter))

        self.assertIsNone(pattern_panel.selected_name)
        self.assertFalse(ArmyPainter.is_selected_pattern_dirty(painter))


if __name__ == "__main__":
    unittest.main()
