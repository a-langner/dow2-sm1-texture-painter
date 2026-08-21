import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

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


if __name__ == "__main__":
    unittest.main()
