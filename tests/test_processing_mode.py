import ast
import unittest
from pathlib import Path

from src.processing_mode import DEFAULT_PROCESSING_MODE, ProcessingMode


class ProcessingModeTests(unittest.TestCase):
    def test_modes_have_stable_ids_and_display_names(self):
        self.assertEqual(
            {mode.value: mode.display_name for mode in ProcessingMode},
            {"global": "Global", "per_color": "Per Color"},
        )

    def test_parser_accepts_ids_display_names_and_enum_values(self):
        for mode in ProcessingMode:
            with self.subTest(mode=mode):
                self.assertIs(ProcessingMode.parse(mode), mode)
                self.assertIs(ProcessingMode.parse(mode.value), mode)
                self.assertIs(ProcessingMode.parse(mode.display_name), mode)
        self.assertIs(
            ProcessingMode.parse(" PER COLOR "),
            ProcessingMode.PER_COLOR,
        )

    def test_missing_stored_mode_and_default_resolve_to_global(self):
        self.assertIs(DEFAULT_PROCESSING_MODE, ProcessingMode.GLOBAL)
        self.assertIs(ProcessingMode.from_stored(None), ProcessingMode.GLOBAL)

    def test_invalid_explicit_values_are_rejected(self):
        for value in ("individual", "", 1, False):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Unknown processing mode"):
                    ProcessingMode.from_stored(value)

    def test_model_has_no_widget_profile_or_texture_dependency(self):
        source_path = (
            Path(__file__).resolve().parents[1] / "src" / "processing_mode.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }

        self.assertEqual(imports, {"enum"})


if __name__ == "__main__":
    unittest.main()
