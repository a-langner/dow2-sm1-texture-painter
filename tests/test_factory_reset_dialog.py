import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.widget import FactoryResetDialog, FactoryResetPatternDeletionDialog


class FactoryResetDialogTests(unittest.TestCase):
    def test_confirm_returns_current_delete_choice(self):
        dialog = SimpleNamespace(
            result=None,
            delete_user_patterns=Mock(get=Mock(return_value=True)),
            destroy=Mock(),
        )

        FactoryResetDialog.confirm(dialog)

        self.assertTrue(dialog.result)
        dialog.destroy.assert_called_once_with()

    def test_cancel_abandons_factory_reset(self):
        dialog = SimpleNamespace(result=True, _save_position=Mock(), destroy=Mock())

        FactoryResetDialog.cancel(dialog)

        self.assertIsNone(dialog.result)
        dialog._save_position.assert_called_once_with()
        dialog.destroy.assert_called_once_with()

    def test_position_restores_with_clamping_and_saves_on_cancel(self):
        dialog = object.__new__(FactoryResetDialog)
        dialog.settings = Mock()
        dialog.settings.factory_reset_dialog_position = (1900, 1000)
        dialog.update_idletasks = Mock()
        dialog.winfo_width = Mock(return_value=400)
        dialog.winfo_height = Mock(return_value=260)
        dialog.winfo_vrootx = Mock(return_value=0)
        dialog.winfo_vrooty = Mock(return_value=0)
        dialog.winfo_vrootwidth = Mock(return_value=1920)
        dialog.winfo_vrootheight = Mock(return_value=1080)
        dialog.winfo_x = Mock(return_value=1520)
        dialog.winfo_y = Mock(return_value=820)
        dialog.geometry = Mock()
        dialog.destroy = Mock()
        dialog.result = True

        dialog._restore_position()
        dialog.cancel()

        dialog.geometry.assert_called_once_with("+1520+820")
        dialog.settings.set_factory_reset_dialog_position.assert_called_once_with(
            (1520, 820)
        )
        self.assertIsNone(dialog.result)
        dialog.destroy.assert_called_once_with()

    def test_pattern_deletion_confirmation_is_explicit(self):
        dialog = SimpleNamespace(result=False, destroy=Mock())

        FactoryResetPatternDeletionDialog.confirm(dialog)

        self.assertTrue(dialog.result)
        dialog.destroy.assert_called_once_with()

    def test_pattern_deletion_cancel_is_false(self):
        dialog = SimpleNamespace(result=True, destroy=Mock())

        FactoryResetPatternDeletionDialog.cancel(dialog)

        self.assertFalse(dialog.result)
        dialog.destroy.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
