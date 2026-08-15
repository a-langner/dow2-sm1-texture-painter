import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from src.team_color_mask_variant import TeamColorMaskVariant


class TeamColorMaskVariantTests(unittest.TestCase):
    def test_default_variant_derives_neutral_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unit_tem.dds"

            variant = TeamColorMaskVariant(None, path)

            self.assertIsNone(variant.variant_index)
            self.assertEqual(variant.display_name, "Default")
            self.assertEqual(variant.path, path.resolve())
            self.assertEqual(variant.filename, "unit_tem.dds")
            self.assertTrue(variant.is_default)
            self.assertEqual(variant.sort_key, (0, 0))

    def test_numbered_tem_and_pnt_use_the_same_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            variants = (
                TeamColorMaskVariant(2, root / "unit_tem_2.dds"),
                TeamColorMaskVariant(3, root / "unit_pnt_3.dds"),
            )

            self.assertEqual(
                [variant.display_name for variant in variants],
                ["Variant 2", "Variant 3"],
            )
            self.assertEqual(
                [variant.filename for variant in variants],
                ["unit_tem_2.dds", "unit_pnt_3.dds"],
            )
            self.assertTrue(all(not variant.is_default for variant in variants))

    def test_sort_key_is_default_then_numeric(self):
        root = Path("textures")
        variants = (
            TeamColorMaskVariant(10, root / "unit_tem_10.dds"),
            TeamColorMaskVariant(2, root / "unit_tem_2.dds"),
            TeamColorMaskVariant(None, root / "unit_tem.dds"),
        )

        ordered = sorted(variants, key=lambda variant: variant.sort_key)

        self.assertEqual(
            [variant.display_name for variant in ordered],
            ["Default", "Variant 2", "Variant 10"],
        )

    def test_invalid_numbered_indices_are_rejected(self):
        for invalid_index in (0, -1, 1.5, True):
            with self.subTest(invalid_index=invalid_index):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    TeamColorMaskVariant(invalid_index, Path("unit_tem.dds"))

    def test_model_is_immutable(self):
        variant = TeamColorMaskVariant(None, Path("unit_tem.dds"))

        with self.assertRaises(FrozenInstanceError):
            variant.variant_index = 2


if __name__ == "__main__":
    unittest.main()
