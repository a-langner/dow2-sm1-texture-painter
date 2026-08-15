import tempfile
import unittest
from pathlib import Path

from src.texture_loading_service import (
    detect_texture_naming_profile,
    find_companion_texture,
)
from src.texture_naming import (
    DOW2_TEXTURE_NAMING,
    SM1_TEXTURE_NAMING,
    TextureKind,
    TextureNamingProfile,
)


class CompanionTextureDiscoveryTests(unittest.TestCase):
    def test_all_three_companion_kinds_resolve_in_same_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diffuse = root / "marine_dif.dds"
            companions = {
                TextureKind.TEAM_COLOR: root / "marine_tem.dds",
                TextureKind.DIRT: root / "marine_drt.dds",
                TextureKind.SPECULAR: root / "marine_spc.dds",
            }
            diffuse.touch()
            for companion in companions.values():
                companion.touch()

            for texture_kind, expected in companions.items():
                with self.subTest(texture_kind=texture_kind):
                    self.assertEqual(
                        find_companion_texture(diffuse, texture_kind), expected
                    )

    def test_missing_companion_returns_none(self):
        with tempfile.TemporaryDirectory() as directory:
            diffuse = Path(directory) / "marine_dif.dds"
            diffuse.touch()

            self.assertIsNone(find_companion_texture(diffuse, TextureKind.SPECULAR))

    def test_invalid_diffuse_name_returns_none(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "marine.dds"
            source.touch()

            self.assertIsNone(find_companion_texture(source, TextureKind.TEAM_COLOR))

    def test_extension_matching_remains_case_insensitive_but_not_broadened(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diffuse = root / "marine_DIF.DDS"
            expected = root / "marine_TEM.dds"
            unrelated = root / "marine_tem.png"
            for path in (diffuse, expected, unrelated):
                path.touch()

            self.assertEqual(
                find_companion_texture(diffuse, TextureKind.TEAM_COLOR),
                expected,
            )

    def test_custom_profile_controls_expected_companion_name(self):
        profile = TextureNamingProfile(
            profile_id="temporary-test",
            display_name="Temporary Test Profile",
            diffuse_suffix="_base",
            team_color_mask_suffix="_mask",
            dirt_suffix="_wear",
            specular_suffix="_shine",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diffuse = root / "marine_base.bin"
            expected = root / "marine_shine.bin"
            diffuse.touch()
            expected.touch()

            self.assertEqual(
                find_companion_texture(
                    diffuse,
                    TextureKind.SPECULAR,
                    profile,
                ),
                expected,
            )

    def test_string_suffixes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            diffuse = Path(directory) / "marine_dif.dds"
            diffuse.touch()

            with self.assertRaises(TypeError):
                find_companion_texture(diffuse, "tem")

    def test_game_profiles_select_only_their_team_color_mask_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diffuse = root / "sm_armour_mp_basic_arm1_dif.dds"
            tem = root / "sm_armour_mp_basic_arm1_tem.dds"
            pnt = root / "sm_armour_mp_basic_arm1_pnt.dds"
            for path in (diffuse, tem, pnt):
                path.touch()

            self.assertEqual(
                find_companion_texture(
                    diffuse, TextureKind.TEAM_COLOR, DOW2_TEXTURE_NAMING
                ),
                tem,
            )
            self.assertEqual(
                find_companion_texture(
                    diffuse, TextureKind.TEAM_COLOR, SM1_TEXTURE_NAMING
                ),
                pnt,
            )

    def test_suffix_text_in_parent_directory_is_never_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mod_dif_assets"
            root.mkdir()
            diffuse = root / "unit_dif.dds"
            expected = root / "unit_pnt.dds"
            diffuse.touch()
            expected.touch()

            result = find_companion_texture(
                diffuse, TextureKind.TEAM_COLOR, SM1_TEXTURE_NAMING
            )

            self.assertEqual(result, expected)
            self.assertEqual(result.parent, root)

    def test_detection_selects_profile_for_one_matching_mask(self):
        for mask_suffix, expected in (
            ("_tem", DOW2_TEXTURE_NAMING),
            ("_pnt", SM1_TEXTURE_NAMING),
        ):
            with self.subTest(mask_suffix=mask_suffix), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                diffuse = root / "unit_dif.dds"
                diffuse.touch()
                (root / f"unit{mask_suffix}.dds").touch()

                self.assertIs(detect_texture_naming_profile(diffuse), expected)

    def test_detection_refuses_both_or_neither_mask(self):
        for mask_suffixes in ((), ("_tem", "_pnt")):
            with self.subTest(mask_suffixes=mask_suffixes), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                diffuse = root / "unit_dif.dds"
                diffuse.touch()
                for mask_suffix in mask_suffixes:
                    (root / f"unit{mask_suffix}.dds").touch()

                self.assertIsNone(detect_texture_naming_profile(diffuse))

    def test_diffuse_is_not_a_companion_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            diffuse = Path(directory) / "marine_dif.dds"
            diffuse.touch()

            with self.assertRaisesRegex(ValueError, "cannot be diffuse"):
                find_companion_texture(diffuse, TextureKind.DIFFUSE)


if __name__ == "__main__":
    unittest.main()
