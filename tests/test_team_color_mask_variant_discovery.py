import tempfile
import unittest
from pathlib import Path

from src.texture_loading_service import (
    detect_texture_naming_profile,
    discover_team_color_mask_variants,
)
from src.texture_naming import DOW2_TEXTURE_NAMING, SM1_TEXTURE_NAMING


class TeamColorMaskVariantDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.diffuse = self.root / "unit_dif.dds"
        self.diffuse.touch()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def create_files(self, *filenames: str) -> None:
        for filename in filenames:
            (self.root / filename).touch()

    def test_dow2_variants_sort_default_first_then_numerically(self):
        self.create_files(
            "unit_tem_10.dds",
            "unit_tem_2.dds",
            "unit_tem.dds",
            "unit_tem_3.dds",
        )

        variants = discover_team_color_mask_variants(
            self.diffuse, DOW2_TEXTURE_NAMING
        )

        self.assertEqual(
            [variant.display_name for variant in variants],
            ["Default", "Variant 2", "Variant 3", "Variant 10"],
        )

    def test_sm1_uses_the_same_discovery_with_pnt_suffix(self):
        self.create_files("unit_pnt.dds", "unit_pnt_4.dds", "unit_tem_2.dds")

        variants = discover_team_color_mask_variants(
            self.diffuse, SM1_TEXTURE_NAMING
        )

        self.assertEqual(
            [variant.filename for variant in variants],
            ["unit_pnt.dds", "unit_pnt_4.dds"],
        )

    def test_numbered_variants_are_discovered_without_default(self):
        self.create_files("unit_tem_5.dds", "unit_tem_2.dds")

        variants = discover_team_color_mask_variants(self.diffuse)

        self.assertEqual(
            [variant.variant_index for variant in variants],
            [2, 5],
        )
        self.assertTrue(all(not variant.is_default for variant in variants))
        self.assertIs(
            detect_texture_naming_profile(self.diffuse),
            DOW2_TEXTURE_NAMING,
        )

    def test_invalid_lookalikes_and_other_extensions_are_ignored(self):
        self.create_files(
            "unit_tem_backup.dds",
            "unit_tem_test.dds",
            "unit_tem_2_backup.dds",
            "unit_alt_tem.dds",
            "unit2_tem.dds",
            "my_unit_tem.dds",
            "unit_tem_0.dds",
            "unit_tem_-2.dds",
            "unit_tem_2.png",
        )

        self.assertEqual(discover_team_color_mask_variants(self.diffuse), ())

    def test_matching_is_case_insensitive_and_preserves_real_filename(self):
        self.create_files("unit_TEM.DDS", "unit_TEM_2.DdS")

        variants = discover_team_color_mask_variants(self.diffuse)

        self.assertEqual(
            [variant.filename for variant in variants],
            ["unit_TEM.DDS", "unit_TEM_2.DdS"],
        )

    def test_unrelated_dif_name_returns_no_variants(self):
        self.create_files("unit_tem.dds")

        variants = discover_team_color_mask_variants(
            self.root / "unit_variant.dds"
        )

        self.assertEqual(variants, ())


if __name__ == "__main__":
    unittest.main()
