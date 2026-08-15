import ast
import unittest
from pathlib import Path

from src.color_slot import DEFAULT_COLOR_SLOT, ColorSlot


class ColorSlotTests(unittest.TestCase):
    def test_slots_have_stable_ids_indexes_and_display_names(self):
        self.assertEqual(
            [(slot.value, slot.index, slot.display_name) for slot in ColorSlot],
            [
                ("color_1", 0, "Color 1"),
                ("color_2", 1, "Color 2"),
                ("color_3", 2, "Color 3"),
                ("color_4", 3, "Color 4"),
            ],
        )
        self.assertIs(DEFAULT_COLOR_SLOT, ColorSlot.COLOR_1)

    def test_slots_parse_from_identity_id_name_and_index(self):
        for slot in ColorSlot:
            with self.subTest(slot=slot):
                self.assertIs(ColorSlot.parse(slot), slot)
                self.assertIs(ColorSlot.parse(slot.value), slot)
                self.assertIs(ColorSlot.parse(slot.display_name), slot)
                self.assertIs(ColorSlot.from_index(slot.index), slot)

    def test_invalid_slot_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown color slot"):
            ColorSlot.parse("primary")
        with self.assertRaisesRegex(ValueError, "between 0 and 3"):
            ColorSlot.from_index(4)
        with self.assertRaisesRegex(TypeError, "integer"):
            ColorSlot.from_index(True)

    def test_model_has_no_widget_profile_or_texture_dependency(self):
        source_path = Path(__file__).resolve().parents[1] / "src" / "color_slot.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }

        self.assertEqual(imports, {"enum"})


if __name__ == "__main__":
    unittest.main()
