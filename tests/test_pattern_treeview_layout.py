import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.action_state import PatternActionContext, derive_pattern_action_state
from src.color_pattern_handler import PatternMarkerColor
from src.widget import (
    FramePatternList,
    calculate_pattern_separator_x,
    clipped_pattern_marker_height,
    find_treeview_body_boundary,
    first_user_pattern_item,
    pattern_marker_display_color,
    pattern_item_has_marker,
    pattern_drop_destination,
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

    def place_forget(self):
        self.placement = None


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
    def test_initial_scroll_callback_precedes_separator_construction_safely(self):
        scrollbar = SimpleNamespace(set=Mock())
        frame = SimpleNamespace(scrollbar=scrollbar)

        FramePatternList._set_pattern_scroll(frame, "0.0", "1.0")

        scrollbar.set.assert_called_once_with("0.0", "1.0")

    def test_user_block_separator_spans_tree_above_first_user_row(self):
        tree = SimpleNamespace(
            get_children=Mock(
                return_value=("builtin", "first-user", "second-user")
            ),
            is_user_item=Mock(
                side_effect=lambda item: item.endswith("user")
            ),
            bbox=Mock(return_value=(0, 84, 300, 20)),
            winfo_x=Mock(return_value=6),
            winfo_y=Mock(return_value=4),
            winfo_width=Mock(return_value=300),
        )
        separator = FakeSeparator()
        frame = SimpleNamespace(tree=tree, user_block_separator=separator)

        result = FramePatternList._position_user_block_separator(frame)

        self.assertTrue(result)
        self.assertEqual(separator.placement, {"x": 6, "y": 87, "width": 300})
        self.assertTrue(separator.lifted)

    def test_user_block_separator_is_hidden_without_user_rows(self):
        tree = SimpleNamespace(
            get_children=Mock(return_value=("builtin",)),
            is_user_item=Mock(return_value=False),
        )
        separator = FakeSeparator()
        separator.placement = {"old": True}
        frame = SimpleNamespace(tree=tree, user_block_separator=separator)

        result = FramePatternList._position_user_block_separator(frame)

        self.assertFalse(result)
        self.assertIsNone(separator.placement)

    def test_first_user_item_uses_real_rows_without_separator_entry(self):
        items = ("builtin-a", "builtin-b", "user-a", "user-b")

        result = first_user_pattern_item(
            items, lambda item: item.startswith("user-")
        )

        self.assertEqual(result, "user-a")
        self.assertIsNone(first_user_pattern_item(items[:2], lambda item: False))

    def test_drop_destination_uses_before_and_after_half_rows(self):
        users = ["user-a", "user-b", "user-c"]
        bbox = (0, 40, 200, 20)

        self.assertEqual(
            pattern_drop_destination(users, "user-c", "user-a", 45, bbox),
            (0, 40),
        )
        self.assertEqual(
            pattern_drop_destination(users, "user-a", "user-c", 55, bbox),
            (2, 60),
        )
        self.assertIsNone(
            pattern_drop_destination(users, "user-a", "builtin", 45, bbox)
        )

    def test_user_separator_cannot_start_an_independent_drag(self):
        frame = object.__new__(FramePatternList)
        frame._drag_pattern_item = "user-a"
        frame._drag_pattern_start = (1, 1)
        frame._drag_pattern_target = "user-b"
        frame._drag_pattern_target_index = 1
        frame._pattern_drag_started = True
        frame.pattern_drop_indicator = SimpleNamespace(place_forget=Mock())

        result = FramePatternList._block_user_separator_drag_start(frame)

        self.assertEqual(result, "break")
        self.assertIsNone(frame._drag_pattern_item)
        self.assertIsNone(frame._drag_pattern_target_index)
        frame.pattern_drop_indicator.place_forget.assert_called_once_with()

    def test_drag_release_reorders_only_within_user_items_and_restores_name(self):
        frame = object.__new__(FramePatternList)
        frame._drag_pattern_item = "user-b"
        frame._drag_pattern_target = "user-a"
        frame._drag_pattern_target_index = 0
        frame._drag_pattern_start = (0, 0)
        frame._pattern_drag_started = True
        frame.pattern_drop_indicator = SimpleNamespace(place_forget=Mock())
        frame._on_pattern_reordered = Mock(return_value=True)
        frame.load_pattern_list = Mock()
        frame.tree = SimpleNamespace(
            get_pattern_name=Mock(return_value="User B"),
            get_children=Mock(return_value=("builtin", "user-a", "user-b")),
            is_user_item=Mock(side_effect=lambda item: item.startswith("user-")),
        )

        FramePatternList._on_pattern_drag_release(frame)

        frame._on_pattern_reordered.assert_called_once_with("User B", 0)
        frame.load_pattern_list.assert_called_once_with("User B")
        self.assertIsNone(frame._drag_pattern_item)
        frame.pattern_drop_indicator.place_forget.assert_called_once_with()

    def test_drag_press_ignores_builtin_pattern(self):
        frame = object.__new__(FramePatternList)
        frame._drag_pattern_item = "old"
        frame._drag_pattern_start = (1, 1)
        frame._drag_pattern_target = "old"
        frame._drag_pattern_target_index = 0
        frame._pattern_drag_started = True
        frame.tree = SimpleNamespace(
            identify_row=Mock(return_value="builtin"),
            is_user_item=Mock(return_value=False),
        )

        FramePatternList._on_pattern_drag_press(
            frame, SimpleNamespace(y=5, x_root=10, y_root=20)
        )

        self.assertIsNone(frame._drag_pattern_item)
        self.assertFalse(frame._pattern_drag_started)

    def test_marker_overlay_is_clipped_before_tree_bottom_border(self):
        self.assertEqual(clipped_pattern_marker_height(170, 20, 181, 1), 10)
        self.assertEqual(clipped_pattern_marker_height(120, 20, 181, 1), 20)
        self.assertEqual(clipped_pattern_marker_height(181, 20, 181, 1), 0)

    def test_only_user_pattern_rows_receive_marker_overlays(self):
        self.assertTrue(pattern_item_has_marker({"is_user": True}))
        self.assertFalse(pattern_item_has_marker({"is_user": False}))
        self.assertFalse(pattern_item_has_marker(None))

    def test_treeview_has_no_native_star_under_centered_marker_overlay(self):
        widget_source = (
            Path(__file__).resolve().parents[1] / "src" / "widget.py"
        ).read_text(encoding="utf-8")
        tree_source = widget_source.split("class PatternTreeview", 1)[1].split(
            "class FramePatternList", 1
        )[0]
        redraw_source = widget_source.split(
            "def _redraw_pattern_markers", 1
        )[1].split("def _tree_border_width", 1)[0]

        self.assertIn('values=(pattern_name, "")', tree_source)
        self.assertIn('x=self.tree.winfo_x() + x', redraw_source)
        self.assertIn("width=width", redraw_source)
        self.assertIn("self.column_separator.lift()", redraw_source)

    def test_assigned_marker_colors_remain_distinct_on_selected_rows(self):
        selected_colors = {
            pattern_marker_display_color(marker, True)
            for marker in PatternMarkerColor
            if marker is not PatternMarkerColor.DEFAULT
        }

        self.assertEqual(len(selected_colors), 5)
        self.assertNotIn(None, selected_colors)
        self.assertEqual(
            pattern_marker_display_color(
                PatternMarkerColor.DEFAULT, True
            ).casefold(),
            "#505050",
        )
        self.assertEqual(
            pattern_marker_display_color(
                PatternMarkerColor.DEFAULT, False
            ).casefold(),
            "#202020",
        )

    def test_marker_menu_is_flat_with_heading_and_star_accelerators(self):
        widget_source = (
            Path(__file__).resolve().parents[1] / "src" / "widget.py"
        ).read_text(encoding="utf-8")
        class_source = widget_source.split("class FramePatternList", 1)[1].split(
            "class PatternImportConflictDialog", 1
        )[0]

        self.assertIn('label="Marker Color", state=tk.DISABLED', class_source)
        self.assertIn('accelerator="★"', class_source)
        self.assertNotIn("marker_color_menu", class_source)

    def test_disabled_marker_heading_cannot_remain_active(self):
        menu = SimpleNamespace(
            index=Mock(return_value=0),
            activate=Mock(),
        )
        frame = SimpleNamespace(marker_menu=menu)

        FramePatternList._suppress_marker_menu_heading(frame)

        menu.activate.assert_called_once_with(tk.NONE)

    def test_context_menu_targets_right_clicked_user_pattern(self):
        tree = SimpleNamespace(
            identify_row=Mock(return_value="user-item"),
            is_user_item=Mock(return_value=True),
            selection_set=Mock(),
            focus=Mock(),
        )
        menu = SimpleNamespace(tk_popup=Mock())
        frame = SimpleNamespace(
            tree=tree,
            marker_menu=menu,
            _context_pattern_item=None,
        )
        event = SimpleNamespace(y=18, x_root=40, y_root=60)

        result = FramePatternList._show_pattern_context_menu(frame, event)

        self.assertEqual(result, "break")
        self.assertEqual(frame._context_pattern_item, "user-item")
        tree.selection_set.assert_called_once_with("user-item")
        menu.tk_popup.assert_called_once_with(40, 60)

    def test_context_marker_callback_uses_stable_name_and_updates_row(self):
        callback = Mock(return_value=True)
        tree = SimpleNamespace(
            is_user_item=Mock(return_value=True),
            get_pattern_name=Mock(return_value="Right Clicked"),
            set_pattern_marker=Mock(),
        )
        frame = SimpleNamespace(
            tree=tree,
            _context_pattern_item="user-item",
            _on_marker_changed=callback,
        )

        FramePatternList._assign_context_marker(
            frame, PatternMarkerColor.GREEN
        )

        callback.assert_called_once_with(
            "Right Clicked", PatternMarkerColor.GREEN
        )
        tree.set_pattern_marker.assert_called_once_with(
            "user-item", PatternMarkerColor.GREEN
        )
        self.assertIsNone(frame._context_pattern_item)

    def test_context_menu_is_not_shown_for_builtin_pattern(self):
        tree = SimpleNamespace(
            identify_row=Mock(return_value="builtin-item"),
            is_user_item=Mock(return_value=False),
        )
        frame = SimpleNamespace(
            tree=tree,
            marker_menu=SimpleNamespace(tk_popup=Mock()),
            _context_pattern_item="old-item",
        )

        result = FramePatternList._show_pattern_context_menu(
            frame, SimpleNamespace(y=4)
        )

        self.assertIsNone(result)
        self.assertIsNone(frame._context_pattern_item)
        frame.marker_menu.tk_popup.assert_not_called()

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
            derive_pattern_action_state(PatternActionContext(True, False, True, False))
        )
        self.assertEqual(frame.modified_label.options["text"], "Modified")

        frame.set_pattern_action_states(
            derive_pattern_action_state(PatternActionContext(False, False, True, False))
        )
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
