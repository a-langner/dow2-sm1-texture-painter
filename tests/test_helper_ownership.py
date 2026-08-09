import ast
from pathlib import Path
import unittest

import test_support  # noqa: F401 - installs the user-data path redirect

SRC_DIRECTORY = Path(__file__).resolve().parents[1] / "src"


def top_level_definitions(module_name):
    source_path = SRC_DIRECTORY / module_name
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


class HelperOwnershipTests(unittest.TestCase):
    def test_moved_helpers_are_not_duplicated_in_frame_main(self):
        frame_definitions = top_level_definitions("frame_main.py")
        moved_helpers = {
            "batch_convert_worker",
            "calculate_diffuse_window_size",
            "calculate_initial_window_size",
            "clamp_window_position",
            "log_application_startup",
            "suggested_exchange_filename",
            "suggested_pattern_collection_filename",
            "suggested_pattern_filename",
        }

        self.assertTrue(frame_definitions.isdisjoint(moved_helpers))


if __name__ == "__main__":
    unittest.main()
