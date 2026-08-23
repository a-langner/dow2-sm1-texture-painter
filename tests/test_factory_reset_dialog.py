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
        dialog = SimpleNamespace(result=True, destroy=Mock())

        FactoryResetDialog.cancel(dialog)

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
