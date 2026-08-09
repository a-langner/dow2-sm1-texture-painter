import os
import subprocess
import sys
import unittest
from pathlib import Path

import test_support

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class MinimumPythonCompatibilityTests(unittest.TestCase):
    def test_pattern_resources_do_not_import_resources_abc_at_runtime(self):
        script = """
import importlib.abc
import sys

class BlockResourcesAbc(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "importlib.resources.abc":
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockResourcesAbc())

from src.color_pattern_handler import load_builtin_patterns

patterns = load_builtin_patterns()
assert patterns
"""
        environment = os.environ.copy()
        environment["XDG_DATA_HOME"] = str(
            test_support.TEST_USER_DATA_DIRECTORY
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
