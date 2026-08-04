import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import resolve_pattern_import_conflicts
from src.pattern_exchange import (
    BuiltinPatternImportConflictError,
    ImportedPattern,
    UserPatternImportConflictError,
)


class ConflictPersistence:
    def __init__(self, builtins=(), users=(), failure=None):
        self.builtins = set(builtins)
        self.users = set(users)
        self.failure = failure
        self.calls = []

    def __call__(self, imported, target_name=None, overwrite=False):
        name = target_name or imported.name
        self.calls.append((name, overwrite))
        if name in self.builtins:
            raise BuiltinPatternImportConflictError(name)
        if name in self.users and not overwrite:
            raise UserPatternImportConflictError(name)
        if self.failure is not None:
            raise self.failure
        return name


class PatternConflictResolutionTests(unittest.TestCase):
    def setUp(self):
        self.imported = ImportedPattern("Original", {})
        self.invalid_messages = []

    def resolve(self, persist, decisions, replacement_names=()):
        decisions = iter(decisions)
        replacement_names = iter(replacement_names)
        self.conflicts = []

        def choose(conflict_type, name):
            self.conflicts.append((conflict_type, name))
            return next(decisions)

        return resolve_pattern_import_conflicts(
            self.imported,
            persist,
            choose,
            lambda current_name: next(replacement_names),
            self.invalid_messages.append,
        )

    def test_builtin_conflict_can_be_renamed(self):
        persist = ConflictPersistence(builtins={"Original"})

        result = self.resolve(persist, ["rename"], ["  Renamed  "])

        self.assertEqual(result, "Renamed")
        self.assertEqual(self.conflicts, [("builtin", "Original")])
        self.assertEqual(persist.calls, [("Original", False), ("Renamed", False)])

    def test_builtin_conflict_cancel_changes_nothing(self):
        persist = ConflictPersistence(builtins={"Original"})

        result = self.resolve(persist, ["cancel"])

        self.assertIsNone(result)
        self.assertEqual(persist.calls, [("Original", False)])

    def test_user_conflict_requires_explicit_overwrite(self):
        persist = ConflictPersistence(users={"Original"})

        result = self.resolve(persist, ["overwrite"])

        self.assertEqual(result, "Original")
        self.assertEqual(self.conflicts, [("user", "Original")])
        self.assertEqual(persist.calls, [("Original", False), ("Original", True)])

    def test_user_conflict_can_be_renamed_or_cancelled(self):
        persist = ConflictPersistence(users={"Original"})
        renamed = self.resolve(persist, ["rename"], ["Renamed"])
        self.assertEqual(renamed, "Renamed")

        persist = ConflictPersistence(users={"Original"})
        cancelled = self.resolve(persist, ["cancel"])
        self.assertIsNone(cancelled)

    def test_rename_to_another_conflict_repeats_predictably(self):
        persist = ConflictPersistence(builtins={"Original"}, users={"Existing User"})

        result = self.resolve(
            persist,
            ["rename", "rename"],
            ["Existing User", "Fresh Name"],
        )

        self.assertEqual(result, "Fresh Name")
        self.assertEqual(
            self.conflicts,
            [("builtin", "Original"), ("user", "Existing User")],
        )

    def test_whitespace_replacement_is_rejected_before_retry(self):
        persist = ConflictPersistence(builtins={"Original"})

        result = self.resolve(persist, ["rename"], ["   ", "Valid Replacement"])

        self.assertEqual(result, "Valid Replacement")
        self.assertEqual(len(self.invalid_messages), 1)

    def test_persistence_failure_during_overwrite_propagates(self):
        persist = ConflictPersistence(
            users={"Original"}, failure=OSError("disk failure")
        )

        with self.assertRaisesRegex(OSError, "disk failure"):
            self.resolve(persist, ["overwrite"])


if __name__ == "__main__":
    unittest.main()
