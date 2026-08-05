import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
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
from src.widget import (
    FramePatternList,
    PatternSelection,
    pattern_action_states,
    pattern_name_to_restore,
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
    @patch("src.frame_main.tk.Menu", side_effect=FakeBuildMenu)
    def test_patterns_menu_layout_and_handlers(self, menu_type, boolean_var):
        handlers = {
            name: Mock(name=name)
            for name in (
                "open_diffuse",
                "open_channel",
                "save",
                "close",
                "on_exit",
                "reset_workspace",
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
            )
        }
        painter = SimpleNamespace(
            **handlers,
            config=Mock(),
            bind=Mock(),
            update_pattern_action_states=Mock(),
        )

        ArmyPainter.define_menu(painter)

        menubar = painter.config.call_args.kwargs["menu"]
        cascades = {
            options["label"]: options["menu"]
            for item_type, options in menubar.items
            if item_type == "cascade"
        }
        self.assertEqual(
            list(cascades), ["File", "Edit", "Patterns", "Tools", "Help"]
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
        no_selection = pattern_action_states(None)
        self.assertEqual(
            (
                no_selection.save_new,
                no_selection.update,
                no_selection.reset,
                no_selection.rename,
                no_selection.duplicate,
                no_selection.delete,
                no_selection.export_selected,
            ),
            (
                "normal",
                "disabled",
                "disabled",
                "disabled",
                "disabled",
                "disabled",
                "disabled",
            ),
        )

        builtin = pattern_action_states(PatternSelection("Built-in", False))
        self.assertEqual(
            (
                builtin.update,
                builtin.reset,
                builtin.rename,
                builtin.duplicate,
                builtin.delete,
                builtin.export_selected,
            ),
            (
                "disabled",
                "disabled",
                "disabled",
                "normal",
                "disabled",
                "normal",
            ),
        )

        user = pattern_action_states(PatternSelection("Custom", True))
        self.assertEqual(
            (user.update, user.rename, user.delete, user.export_selected),
            ("disabled", "normal", "normal", "normal"),
        )

        modified_user = pattern_action_states(
            PatternSelection("Custom", True), modified=True
        )
        self.assertEqual(modified_user.update, "normal")
        self.assertEqual(modified_user.reset, "normal")
        self.assertTrue(modified_user.modified)
        self.assertTrue(
            pattern_action_states(
                PatternSelection("Built-in", False), modified=True
            ).modified
        )
        self.assertFalse(pattern_action_states(None, modified=True).modified)

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
        self.assertEqual(painter.frame_army_pattern.action_states.delete, "disabled")

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
                    painter.frame_army_pattern.action_states.delete,
                    expected_delete,
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
                    painter.frame_army_pattern.action_states.update,
                    expected_update,
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
                    painter.frame_army_pattern.action_states.rename,
                )
                self.assertEqual(
                    painter.pattern_menu.states[PATTERN_DUPLICATE_MENU_LABEL],
                    painter.frame_army_pattern.action_states.duplicate,
                )
                self.assertEqual(
                    painter.pattern_menu.states[PATTERN_DELETE_MENU_LABEL],
                    painter.frame_army_pattern.action_states.delete,
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
        self.assertEqual(painter.frame_army_pattern.action_states.delete, "disabled")

    def test_export_all_state_depends_on_user_patterns_not_selection(self):
        for selected_name in (None, "Built-in"):
            with self.subTest(selected_name=selected_name), patch(
                "src.frame_main.src.color_pattern_handler.has_user_patterns",
                return_value=True,
            ):
                painter = FakePainter(selected_name)

                ArmyPainter.update_pattern_action_states(painter)

                self.assertEqual(
                    painter.pattern_menu.states[
                        PATTERN_COLLECTION_EXPORT_MENU_LABEL
                    ],
                    "normal",
                )

    def test_pattern_list_refresh_invokes_state_change_callback(self):
        tree = SimpleNamespace(clear_patterns=Mock(), insert_pattern=Mock())
        callback = Mock()
        frame = SimpleNamespace(
            tree=tree,
            state_change_callback=callback,
            get_selected_pattern=Mock(return_value=None),
        )

        with patch("src.widget.build_pattern_rows", return_value=[]):
            FramePatternList.load_pattern_list(frame)

        callback.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
