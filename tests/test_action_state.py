import inspect
import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.action_state import (
    PatternActionContext,
    PatternActionState,
    derive_pattern_action_state,
)


class PatternActionStatePolicyTests(unittest.TestCase):
    def derive(self, selected=False, user=False, dirty=False, users=False):
        return derive_pattern_action_state(
            PatternActionContext(selected, user, dirty, users)
        )

    def assert_actions(
        self,
        state,
        *,
        update,
        reset,
        rename,
        duplicate,
        delete,
        export_selected,
    ):
        self.assertIsInstance(state, PatternActionState)
        self.assertTrue(state.save_new_enabled)
        self.assertEqual(state.update_enabled, update)
        self.assertEqual(state.reset_enabled, reset)
        self.assertEqual(state.rename_enabled, rename)
        self.assertEqual(state.duplicate_enabled, duplicate)
        self.assertEqual(state.delete_enabled, delete)
        self.assertEqual(state.export_selected_enabled, export_selected)

    def test_no_selection(self):
        state = self.derive(dirty=True)
        self.assert_actions(
            state,
            update=False,
            reset=False,
            rename=False,
            duplicate=False,
            delete=False,
            export_selected=False,
        )
        self.assertFalse(state.modified_indicator_visible)

    def test_builtin_unchanged(self):
        self.assert_actions(
            self.derive(selected=True),
            update=False,
            reset=False,
            rename=False,
            duplicate=True,
            delete=False,
            export_selected=True,
        )

    def test_builtin_dirty(self):
        state = self.derive(selected=True, dirty=True)
        self.assert_actions(
            state,
            update=False,
            reset=True,
            rename=False,
            duplicate=True,
            delete=False,
            export_selected=True,
        )
        self.assertTrue(state.modified_indicator_visible)

    def test_user_unchanged(self):
        self.assert_actions(
            self.derive(selected=True, user=True),
            update=False,
            reset=False,
            rename=True,
            duplicate=True,
            delete=True,
            export_selected=True,
        )

    def test_user_dirty(self):
        self.assert_actions(
            self.derive(selected=True, user=True, dirty=True),
            update=True,
            reset=True,
            rename=True,
            duplicate=True,
            delete=True,
            export_selected=True,
        )

    def test_export_all_depends_only_on_user_pattern_presence(self):
        for selected, user, dirty in (
            (False, False, False),
            (True, False, False),
            (True, False, True),
            (True, True, False),
            (True, True, True),
        ):
            with self.subTest(selected=selected, user=user, dirty=dirty):
                self.assertFalse(
                    self.derive(selected, user, dirty, False).export_all_enabled
                )
                self.assertTrue(
                    self.derive(selected, user, dirty, True).export_all_enabled
                )

    def test_visible_marker_text_cannot_affect_policy(self):
        fields = PatternActionContext.__dataclass_fields__
        self.assertNotIn("name", fields)
        self.assertNotIn("marker", fields)
        self.assertNotIn("label", fields)

    def test_policy_module_has_no_tk_dependency(self):
        import src.action_state as module

        self.assertNotIn("tkinter", inspect.getsource(module))


if __name__ == "__main__":
    unittest.main()
