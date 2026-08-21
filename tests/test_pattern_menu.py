import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.action_state import PatternActionContext, derive_pattern_action_state
from src.frame_main import (
    PATTERN_COLLECTION_IMPORT_MENU_LABEL,
    PATTERN_COLLECTION_EXPORT_MENU_LABEL,
    PATTERN_DELETE_MENU_LABEL,
    PATTERN_DUPLICATE_MENU_LABEL,
    PATTERN_EXPORT_MENU_LABEL,
    PATTERN_IMPORT_MENU_LABEL,
    PATTERN_RENAME_MENU_LABEL,
    PATTERN_RESET_MENU_LABEL,
    PATTERN_SAVE_MENU_LABEL,
    PATTERN_UPDATE_MENU_LABEL,
    ArmyPainter,
)
from src.texture_naming import DOW2_TEXTURE_NAMING
from src.widget import (
    FramePatternList,
    PatternSelection,
    pattern_name_to_restore,
)


def derive_for_selection(selection, modified=False, has_users=False):
    return derive_pattern_action_state(
        PatternActionContext(
            selection is not None,
            bool(selection and selection.is_user),
            modified,
            has_users,
        )
    )


class FakePatternList:
    def __init__(self, selected_name=None):
        self.selected_name = selected_name

    def get_selected_pattern_name(self):
        return self.selected_name

    def get_selected_pattern(self):
        if self.selected_name is None:
            return None
        return PatternSelection(
            self.selected_name, self.selected_name == "User-created"
        )

    def set_pattern_action_states(self, states):
        self.action_states = states


class FakeMenu:
    def __init__(self):
        self.configurations = []
        self.states = {}

    def entryconfig(self, entry, **options):
        self.configurations.append((entry, options))
        self.states[entry] = options["state"]


class FakeBuildMenu:
    def __init__(self, parent=None, **options):
        self.parent = parent
        self.items = []

    def add_command(self, **options):
        self.items.append(("command", options))

    def add_separator(self):
        self.items.append(("separator", {}))

    def add_checkbutton(self, **options):
        self.items.append(("checkbutton", options))

    def add_radiobutton(self, **options):
        self.items.append(("radiobutton", options))

    def add_cascade(self, **options):
        self.items.append(("cascade", options))


class FakePainter:
    def __init__(self, selected_name=None, dirty=False):
        self.frame_army_pattern = FakePatternList(selected_name)
        self.pattern_menu = FakeMenu()
        self.dirty = dirty

    def is_selected_pattern_dirty(self, selection=None):
        return self.dirty


class PatternMenuStateTests(unittest.TestCase):
    @patch("src.frame_main.tk.BooleanVar", return_value=Mock())
    @patch("src.frame_main.tk.StringVar", return_value=Mock())
    @patch("src.frame_main.tk.Menu", side_effect=FakeBuildMenu)
    def test_patterns_menu_layout_and_handlers(
        self, menu_type, string_var, boolean_var
    ):
        handlers = {
            name: Mock(name=name)
            for name in (
                "open_diffuse",
                "open_channel",
                "save",
                "close",
                "on_exit",
                "reset_workspace",
                "undo",
                "redo",
                "on_dirt_toggle",
                "on_spec_toggle",
                "save_pattern",
                "update_selected_pattern",
                "reset_to_selected_pattern",
                "rename_selected_pattern",
                "duplicate_selected_pattern",
                "delete_pattern",
                "import_pattern",
                "export_selected_pattern",
                "import_pattern_collection",
                "export_all_user_patterns",
                "open_batch_edit_tools",
                "open_log_folder",
                "batch_edit",
                "select_game_profile",
            )
        }
        painter = SimpleNamespace(
            **handlers,
            config=Mock(),
            bind=Mock(),
            update_pattern_action_states=Mock(),
            texture_naming_profile=DOW2_TEXTURE_NAMING,
        )

        ArmyPainter.define_menu(painter)

        painter.bind.assert_has_calls(
            [
                call("<Control-z>", handlers["undo"]),
                call("<Control-y>", handlers["redo"]),
            ]
        )

        menubar = painter.config.call_args.kwargs["menu"]
        cascades = {
            options["label"]: options["menu"]
            for item_type, options in menubar.items
            if item_type == "cascade"
        }
        self.assertEqual(
            list(cascades), ["File", "Edit", "Game", "Patterns", "Tools", "Help"]
        )
        self.assertEqual(
            cascades["Edit"].items[:4],
            [
                (
                    "command",
                    {
                        "label": "Undo",
                        "command": handlers["undo"],
                        "accelerator": "Ctrl+Z",
                        "state": "disabled",
                    },
                ),
                (
                    "command",
                    {
                        "label": "Redo",
                        "command": handlers["redo"],
                        "accelerator": "Ctrl+Y",
                        "state": "disabled",
                    },
                ),
                ("separator", {}),
                (
                    "command",
                    {
                        "label": "Reset workspace",
                        "command": handlers["reset_workspace"],
                        "accelerator": "Ctrl+R",
                    },
                ),
            ],
        )
        self.assertEqual(
            [item[1]["label"] for item in cascades["Game"].items],
            ["Dawn of War II", "Space Marine 1"],
        )
        self.assertEqual(
            [item[1]["value"] for item in cascades["Game"].items],
            ["dow2", "sm1"],
        )
        self.assertEqual(
            [
                item[1]["label"]
                for item in cascades["File"].items
                if item[0] == "command"
            ][:2],
            ["Open diffuse", "Open Team Color Mask"],
        )
        self.assertEqual(
            cascades["Help"].items,
            [
                (
                    "command",
                    {
                        "label": "Open Log Folder",
                        "command": handlers["open_log_folder"],
                    },
                )
            ],
        )
        self.assertEqual(
            cascades["Tools"].items,
            [
                (
                    "command",
                    {
                        "label": "Batch Edit Tools",
                        "command": handlers["open_batch_edit_tools"],
                        "accelerator": "Ctrl+B",
                    },
                )
            ],
        )
        painter.bind.assert_any_call(
            "<Control-b>", handlers["open_batch_edit_tools"]
        )

        labels = [
            item[1].get("label") if item[0] == "command" else None
            for item in painter.pattern_menu.items
        ]
        self.assertEqual(
            labels,
            [
                PATTERN_SAVE_MENU_LABEL,
                PATTERN_UPDATE_MENU_LABEL,
                PATTERN_RESET_MENU_LABEL,
                PATTERN_RENAME_MENU_LABEL,
                PATTERN_DUPLICATE_MENU_LABEL,
                PATTERN_DELETE_MENU_LABEL,
                None,
                PATTERN_IMPORT_MENU_LABEL,
                PATTERN_EXPORT_MENU_LABEL,
                None,
                PATTERN_COLLECTION_IMPORT_MENU_LABEL,
                PATTERN_COLLECTION_EXPORT_MENU_LABEL,
            ],
        )
        commands = {
            options["label"]: options["command"]
            for item_type, options in painter.pattern_menu.items
            if item_type == "command"
        }
        self.assertIs(commands[PATTERN_SAVE_MENU_LABEL], handlers["save_pattern"])
        self.assertIs(
            commands[PATTERN_UPDATE_MENU_LABEL],
            handlers["update_selected_pattern"],
        )
        self.assertIs(
            commands[PATTERN_RESET_MENU_LABEL],
            handlers["reset_to_selected_pattern"],
        )
        self.assertIs(
            commands[PATTERN_RENAME_MENU_LABEL],
            handlers["rename_selected_pattern"],
        )
        self.assertIs(
            commands[PATTERN_DUPLICATE_MENU_LABEL],
            handlers["duplicate_selected_pattern"],
        )
        self.assertIs(commands[PATTERN_DELETE_MENU_LABEL], handlers["delete_pattern"])

    def test_command_policy_covers_no_builtin_and_user_selection(self):
        no_selection = derive_for_selection(None)
        self.assertEqual(
            (
                no_selection.save_new_enabled,
                no_selection.update_enabled,
                no_selection.reset_enabled,
                no_selection.rename_enabled,
                no_selection.duplicate_enabled,
                no_selection.delete_enabled,
                no_selection.export_selected_enabled,
            ),
            (
                True,
                False,
                False,
                False,
                False,
                False,
                False,
            ),
        )

        builtin = derive_for_selection(PatternSelection("Built-in", False))
        self.assertEqual(
            (
                builtin.update_enabled,
                builtin.reset_enabled,
                builtin.rename_enabled,
                builtin.duplicate_enabled,
                builtin.delete_enabled,
                builtin.export_selected_enabled,
            ),
            (
                False,
                False,
                False,
                True,
                False,
                True,
            ),
        )

        user = derive_for_selection(PatternSelection("Custom", True))
        self.assertEqual(
            (
                user.update_enabled,
                user.rename_enabled,
                user.delete_enabled,
                user.export_selected_enabled,
            ),
            (False, True, True, True),
        )

        modified_user = derive_for_selection(
            PatternSelection("Custom", True), modified=True
        )
        self.assertTrue(modified_user.update_enabled)
        self.assertTrue(modified_user.reset_enabled)
        self.assertTrue(modified_user.modified_indicator_visible)
        self.assertTrue(
            derive_for_selection(
                PatternSelection("Built-in", False), modified=True
            ).modified_indicator_visible
        )
        self.assertFalse(
            derive_for_selection(None, modified=True).modified_indicator_visible
        )

    def test_refresh_selection_uses_internal_name_and_handles_removal(self):
        names = {"Built-in", "Custom"}
        self.assertEqual(pattern_name_to_restore(None, "Built-in", names), "Built-in")
        self.assertEqual(pattern_name_to_restore("Custom", "Built-in", names), "Custom")
        self.assertIsNone(pattern_name_to_restore(None, "Deleted", names))

    def test_export_is_disabled_without_selection(self):
        painter = FakePainter()

        ArmyPainter.update_pattern_action_states(painter)

        self.assertEqual(
            painter.pattern_menu.states,
            {
                PATTERN_SAVE_MENU_LABEL: "normal",
                PATTERN_UPDATE_MENU_LABEL: "disabled",
                PATTERN_RESET_MENU_LABEL: "disabled",
                PATTERN_RENAME_MENU_LABEL: "disabled",
                PATTERN_DUPLICATE_MENU_LABEL: "disabled",
                PATTERN_DELETE_MENU_LABEL: "disabled",
                PATTERN_EXPORT_MENU_LABEL: "disabled",
                PATTERN_COLLECTION_EXPORT_MENU_LABEL: "disabled",
            },
        )
        self.assertFalse(painter.frame_army_pattern.action_states.delete_enabled)

    def test_export_is_enabled_for_any_internal_pattern_name(self):
        for pattern_name in ("Built-in", "User-created"):
            with self.subTest(pattern_name=pattern_name):
                painter = FakePainter(pattern_name)

                ArmyPainter.update_pattern_action_states(painter)

                self.assertEqual(
                    painter.pattern_menu.states[PATTERN_EXPORT_MENU_LABEL],
                    "normal",
                )
                expected_delete = (
                    "normal" if pattern_name == "User-created" else "disabled"
                )
                self.assertEqual(
                    painter.frame_army_pattern.action_states.delete_enabled,
                    expected_delete == "normal",
                )

    def test_only_dirty_user_selection_enables_update(self):
        for pattern_name, dirty, expected_update in (
            ("Built-in", True, "disabled"),
            ("User-created", False, "disabled"),
            ("User-created", True, "normal"),
        ):
            with self.subTest(pattern_name=pattern_name, dirty=dirty):
                painter = FakePainter(pattern_name, dirty=dirty)

                ArmyPainter.update_pattern_action_states(painter)

                self.assertEqual(
                    painter.frame_army_pattern.action_states.update_enabled,
                    expected_update == "normal",
                )
                self.assertEqual(
                    painter.pattern_menu.states[PATTERN_UPDATE_MENU_LABEL],
                    expected_update,
                )
                expected_reset = "normal" if dirty else "disabled"
                self.assertEqual(
                    painter.pattern_menu.states[PATTERN_RESET_MENU_LABEL],
                    expected_reset,
                )
                self.assertEqual(
                    painter.pattern_menu.states[PATTERN_RENAME_MENU_LABEL],
                    (
                        "normal"
                        if painter.frame_army_pattern.action_states.rename_enabled
                        else "disabled"
                    ),
                )
                self.assertEqual(
                    painter.pattern_menu.states[PATTERN_DUPLICATE_MENU_LABEL],
                    (
                        "normal"
                        if painter.frame_army_pattern.action_states.duplicate_enabled
                        else "disabled"
                    ),
                )
                self.assertEqual(
                    painter.pattern_menu.states[PATTERN_DELETE_MENU_LABEL],
                    (
                        "normal"
                        if painter.frame_army_pattern.action_states.delete_enabled
                        else "disabled"
                    ),
                )

    def test_export_returns_to_disabled_when_selection_is_cleared(self):
        painter = FakePainter("Selected")
        ArmyPainter.update_pattern_action_states(painter)
        painter.frame_army_pattern.selected_name = None

        ArmyPainter.update_pattern_action_states(painter)

        self.assertEqual(
            painter.pattern_menu.states[PATTERN_EXPORT_MENU_LABEL],
            "disabled",
        )
        self.assertFalse(painter.frame_army_pattern.action_states.delete_enabled)

    def test_export_all_state_depends_on_user_patterns_not_selection(self):
        for selected_name in (None, "Built-in"):
            with self.subTest(selected_name=selected_name), patch(
                "src.frame_main.src.color_pattern_handler.has_user_patterns",
                return_value=True,
            ):
                painter = FakePainter(selected_name)

                ArmyPainter.update_pattern_action_states(painter)

                self.assertEqual(
                    painter.pattern_menu.states[PATTERN_COLLECTION_EXPORT_MENU_LABEL],
                    "normal",
                )

    @patch(
        "src.frame_main.src.color_pattern_handler.has_user_patterns",
        side_effect=(False, True, False),
    )
    def test_first_save_and_last_delete_transition_export_all_state(
        self, has_user_patterns
    ):
        painter = FakePainter()

        ArmyPainter.update_pattern_action_states(painter)
        self.assertEqual(
            painter.pattern_menu.states[PATTERN_COLLECTION_EXPORT_MENU_LABEL],
            "disabled",
        )

        ArmyPainter.update_pattern_action_states(painter)
        self.assertEqual(
            painter.pattern_menu.states[PATTERN_COLLECTION_EXPORT_MENU_LABEL],
            "normal",
        )

        ArmyPainter.update_pattern_action_states(painter)
        self.assertEqual(
            painter.pattern_menu.states[PATTERN_COLLECTION_EXPORT_MENU_LABEL],
            "disabled",
        )

    def test_pattern_list_refresh_invokes_state_change_callback(self):
        tree = SimpleNamespace(clear_patterns=Mock(), insert_pattern=Mock())
        callback = Mock()
        frame = SimpleNamespace(
            tree=tree,
            _on_state_changed=callback,
            _external_callbacks_enabled=True,
            get_selected_pattern=Mock(return_value=None),
        )

        with patch("src.widget.build_pattern_rows", return_value=[]):
            FramePatternList.load_pattern_list(frame)

        callback.assert_called_once_with()

    def test_initial_pattern_population_does_not_notify_controller(self):
        tree = SimpleNamespace(clear_patterns=Mock(), insert_pattern=Mock())
        callback = Mock()
        frame = SimpleNamespace(
            tree=tree,
            _on_state_changed=callback,
            _external_callbacks_enabled=False,
            get_selected_pattern=Mock(return_value=None),
        )

        with patch("src.widget.build_pattern_rows", return_value=[]):
            FramePatternList.load_pattern_list(frame, notify_state=False)

        callback.assert_not_called()

    def test_pattern_callbacks_activate_and_synchronize_after_assignment(self):
        panel = SimpleNamespace(enable_external_callbacks=Mock())
        painter = SimpleNamespace(frame_army_pattern=panel)

        def assert_panel_is_assigned():
            self.assertIs(painter.frame_army_pattern, panel)

        panel.enable_external_callbacks.side_effect = assert_panel_is_assigned
        painter.update_pattern_action_states = Mock(
            side_effect=assert_panel_is_assigned
        )

        ArmyPainter.activate_pattern_panel_callbacks(painter)

        panel.enable_external_callbacks.assert_called_once_with()
        painter.update_pattern_action_states.assert_called_once_with()

    def test_startup_fix_does_not_use_frame_attribute_hasattr_workaround(self):
        source = (
            Path(__file__).resolve().parents[1] / "src" / "frame_main.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn('hasattr(self, "frame_army_pattern")', source)


if __name__ == "__main__":
    unittest.main()
