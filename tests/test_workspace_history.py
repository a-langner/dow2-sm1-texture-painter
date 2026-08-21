import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from src.color_slot import ColorSlot
from src.frame_main import ArmyPainter
from src.render_settings import DEFAULT_RENDER_SETTINGS
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
        self.assertTrue(history.can_redo)

        painter.frame_color_chooser.draw_rgb_value.reset_mock()
        listbox.reset_mock()
        painter.frame_channel_select.apply_alpha.set.reset_mock()
        painter.refresh_workspace.reset_mock()
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
        self.assertTrue(history.can_undo)
        self.assertFalse(history.can_redo)


if __name__ == "__main__":
    unittest.main()
