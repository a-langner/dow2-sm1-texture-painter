import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.widget import (
    FramePatternList,
    calculate_pattern_separator_x,
    find_treeview_body_boundary,
    pattern_action_states,
)


class FakeTree:
    def __init__(self):
        self.scroll_calls = []
        self.region = "cell"
        self.cursor = None

    def yview_scroll(self, number, what):
        self.scroll_calls.append((number, what))

    def identify_region(self, x, y):
        return self.region

    def configure(self, cursor):
        self.cursor = cursor


class FakeEvent:
    x = 10
    y = 5


class FakeRegionTree:
    def __init__(self, boundary, body_region):
        self.boundary = boundary
        self.body_region = body_region

    def winfo_width(self):
        return 300

    def winfo_height(self):
        return 200

    def identify_region(self, x, y):
        return "heading" if y < self.boundary else self.body_region


class FakeSeparator:
    def __init__(self):
        self.placement = None
        self.lifted = False

    def winfo_reqheight(self):
        return 2

    def place(self, **kwargs):
        self.placement = kwargs

    def lift(self):
        self.lifted = True


class FakeActionFrame:
    def __init__(self):
        self.pack_options = None
        self.column_weights = {}

    def pack(self, **kwargs):
        self.pack_options = kwargs

    def grid_columnconfigure(self, column, weight):
        self.column_weights[column] = weight


class FakeButton:
    def __init__(self, parent, **kwargs):
        self.parent = parent
        self.options = kwargs
        self.grid_options = None

    def grid(self, **kwargs):
        self.grid_options = kwargs

    def config(self, **kwargs):
        self.options.update(kwargs)


class FakePositionTree:
    def __init__(self):
        self.idle_updates = 0
        self.unbound = []

    def winfo_x(self):
        return 6

    def winfo_y(self):
        return 4

    def winfo_width(self):
        return 300

    def winfo_exists(self):
        return True

    def update_idletasks(self):
        self.idle_updates += 1

    def unbind(self, sequence, binding_id):
        self.unbound.append((sequence, binding_id))


class PatternTreeviewLayoutTests(unittest.TestCase):
    @patch("src.widget.ttk.Label", side_effect=FakeButton)
    @patch("src.widget.tk.Button", side_effect=FakeButton)
    @patch("src.widget.tk.Frame", return_value=FakeActionFrame())
    def test_pattern_actions_use_balanced_two_by_two_grid(
        self, _frame_type, _button_type, _label_type
    ):
        frame = object.__new__(FramePatternList)
        frame._on_save_new = Mock()
        frame._on_update = Mock()
        frame._on_rename = Mock()
        frame._on_delete = Mock()

        frame._create_action_buttons()

        self.assertEqual(frame.action_frame.column_weights, {0: 1, 1: 1})
        self.assertEqual(
            [
                frame.save_new_button.options["text"],
                frame.update_button.options["text"],
                frame.rename_button.options["text"],
                frame.delete_button.options["text"],
            ],
            ["Save New", "Update", "Rename", "Delete"],
        )
        self.assertNotIn("state", frame.save_new_button.options)
        self.assertEqual(frame.modified_label.options["text"], "")
        self.assertEqual(frame.modified_label.grid_options["row"], 0)
        self.assertEqual(frame.modified_label.grid_options["columnspan"], 2)
        for button in (
            frame.update_button,
            frame.rename_button,
            frame.delete_button,
        ):
            self.assertEqual(button.options["state"], tk.DISABLED)
            self.assertEqual(button.grid_options["sticky"], tk.EW)
        self.assertEqual(frame.save_new_button.grid_options["row"], 1)
        self.assertEqual(frame.save_new_button.grid_options["column"], 0)
        self.assertEqual(frame.update_button.grid_options["row"], 1)
        self.assertEqual(frame.update_button.grid_options["column"], 1)
        self.assertEqual(frame.rename_button.grid_options["row"], 2)
        self.assertEqual(frame.rename_button.grid_options["column"], 0)
        self.assertEqual(frame.delete_button.grid_options["row"], 2)
        self.assertEqual(frame.delete_button.grid_options["column"], 1)

        for button, callback in (
            (frame.save_new_button, frame._on_save_new),
            (frame.update_button, frame._on_update),
            (frame.rename_button, frame._on_rename),
            (frame.delete_button, frame._on_delete),
        ):
            button.options["command"]()
            callback.assert_called_once_with()

        frame.set_pattern_action_states(
            pattern_action_states(
                type("Selection", (), {"is_user": False})(), modified=True
            )
        )
        self.assertEqual(frame.modified_label.options["text"], "Modified")

        frame.set_pattern_action_states(pattern_action_states(None, modified=True))
        self.assertEqual(frame.modified_label.options["text"], "")

    def test_selection_change_invokes_supplied_callback_without_event(self):
        frame = object.__new__(FramePatternList)
        frame._on_selection_changed = Mock()
        frame._external_callbacks_enabled = True

        frame._notify_selection_changed(object())

        frame._on_selection_changed.assert_called_once_with()

    def test_selection_change_callback_is_safely_optional(self):
        frame = object.__new__(FramePatternList)
        frame._on_selection_changed = None
        frame._external_callbacks_enabled = True

        frame._notify_selection_changed(object())

    def test_selection_change_is_suppressed_during_construction(self):
        frame = object.__new__(FramePatternList)
        frame._on_selection_changed = Mock()
        frame._external_callbacks_enabled = False

        frame._notify_selection_changed(object())

        frame._on_selection_changed.assert_not_called()

    def test_enabling_callbacks_binds_selection_once(self):
        frame = object.__new__(FramePatternList)
        frame.tree = SimpleNamespace(bind=Mock(return_value="binding"))
        frame._external_callbacks_enabled = False

        frame.enable_external_callbacks()
        frame.enable_external_callbacks()

        frame.tree.bind.assert_called_once_with(
            "<<TreeviewSelect>>", frame._notify_selection_changed, add="+"
        )
        self.assertTrue(frame._external_callbacks_enabled)

    def test_pattern_list_has_no_implicit_root_lookup(self):
        widget_source = (
            Path(__file__).resolve().parents[1] / "src" / "widget.py"
        ).read_text(encoding="utf-8")
        class_source = widget_source.split("class FramePatternList", 1)[1].split(
            "class PatternImportConflictDialog", 1
        )[0]

        self.assertNotIn("_root()", class_source)

    def test_header_boundary_uses_populated_tree_hit_testing(self):
        tree = FakeRegionTree(boundary=24, body_region="cell")

        self.assertEqual(find_treeview_body_boundary(tree), 24)

    def test_header_boundary_uses_empty_tree_hit_testing(self):
        tree = FakeRegionTree(boundary=27, body_region="nothing")

        self.assertEqual(find_treeview_body_boundary(tree), 27)

    @patch("src.widget.find_treeview_body_boundary", return_value=None)
    def test_header_separator_position_reports_layout_not_ready(self, boundary):
        frame = object.__new__(FramePatternList)
        frame.tree = FakePositionTree()
        frame.header_separator = FakeSeparator()

        self.assertFalse(frame._position_header_separator())
        self.assertIsNone(frame.header_separator.placement)

    @patch("src.widget.find_treeview_body_boundary", return_value=24)
    def test_header_separator_position_reports_success(self, boundary):
        frame = object.__new__(FramePatternList)
        frame.tree = FakePositionTree()
        frame.header_separator = FakeSeparator()

        self.assertTrue(frame._position_header_separator())
        self.assertEqual(
            frame.header_separator.placement,
            {"x": 6, "y": 26, "width": 300},
        )
        self.assertTrue(frame.header_separator.lifted)

    def test_startup_position_suppresses_duplicates_and_unbinds_after_success(self):
        frame = object.__new__(FramePatternList)
        frame.tree = FakePositionTree()
        frame.header_separator_startup_retries = 3
        frame.header_separator_startup_after_id = None
        frame.header_separator_map_binding_id = "map-binding"
        pending_callbacks = []
        frame.after_idle = lambda callback: pending_callbacks.append(callback) or "idle"
        frame._position_header_separator = lambda: True

        frame._schedule_initial_header_separator_position()
        frame._schedule_initial_header_separator_position()

        self.assertEqual(len(pending_callbacks), 1)
        pending_callbacks.pop()()
        self.assertEqual(frame.tree.idle_updates, 1)
        self.assertEqual(frame.tree.unbound, [("<Map>", "map-binding")])
        self.assertIsNone(frame.header_separator_map_binding_id)

    def test_startup_position_retries_are_bounded(self):
        frame = object.__new__(FramePatternList)
        frame.tree = FakePositionTree()
        frame.header_separator_startup_retries = 3
        frame.header_separator_startup_after_id = None
        frame.header_separator_map_binding_id = "map-binding"
        pending_callbacks = []
        frame.after_idle = lambda callback: pending_callbacks.append(callback) or "idle"
        frame._position_header_separator = lambda: False

        frame._schedule_initial_header_separator_position()
        attempts = 0
        while pending_callbacks:
            attempts += 1
            pending_callbacks.pop(0)()

        self.assertEqual(attempts, 3)
        self.assertEqual(frame.header_separator_startup_retries, 0)
        self.assertIsNone(frame.header_separator_startup_after_id)

    def test_separator_tracks_marker_boundary_when_tree_resizes(self):
        narrow = calculate_pattern_separator_x(0, 200, 28, 1)
        wide = calculate_pattern_separator_x(0, 500, 28, 1)

        self.assertEqual(narrow, 171)
        self.assertEqual(wide, 471)

    def test_separator_position_includes_tree_offset(self):
        result = calculate_pattern_separator_x(6, 300, 28, 1)

        self.assertEqual(result, 277)

    def test_x11_wheel_events_scroll_tree_through_separator(self):
        frame = object.__new__(FramePatternList)
        frame.tree = FakeTree()

        up_result = frame._scroll_tree_up_through_separator(None)
        down_result = frame._scroll_tree_down_through_separator(None)

        self.assertEqual(frame.tree.scroll_calls, [(-1, "units"), (1, "units")])
        self.assertEqual(up_result, "break")
        self.assertEqual(down_result, "break")

    def test_header_separator_press_drag_and_release_are_blocked(self):
        frame = object.__new__(FramePatternList)
        frame.tree = FakeTree()
        frame.tree.region = "separator"
        frame.header_separator_pressed = False
        event = FakeEvent()

        self.assertEqual(frame._block_header_separator_press(event), "break")
        frame.tree.region = "heading"
        self.assertEqual(frame._block_header_separator_drag(event), "break")
        self.assertEqual(frame._block_header_separator_release(event), "break")
        self.assertFalse(frame.header_separator_pressed)
        self.assertEqual(frame.tree.cursor, "arrow")

    def test_normal_tree_interactions_are_not_blocked(self):
        frame = object.__new__(FramePatternList)
        frame.tree = FakeTree()
        frame.header_separator_pressed = False
        event = FakeEvent()

        self.assertIsNone(frame._block_header_separator_press(event))
        self.assertIsNone(frame._block_header_separator_drag(event))
        self.assertIsNone(frame._block_header_separator_release(event))

    def test_cursor_is_local_and_restored_outside_separator(self):
        frame = object.__new__(FramePatternList)
        frame.tree = FakeTree()
        event = FakeEvent()
        frame.tree.region = "separator"

        self.assertEqual(frame._update_header_separator_cursor(event), "break")
        self.assertEqual(frame.tree.cursor, "arrow")

        frame.tree.region = "cell"
        self.assertIsNone(frame._update_header_separator_cursor(event))
        self.assertEqual(frame.tree.cursor, "")


if __name__ == "__main__":
    unittest.main()
