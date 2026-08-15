import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from src.texture_naming import (
    DEFAULT_TEXTURE_NAMING,
    DOW2_TEXTURE_NAMING,
    SM1_TEXTURE_NAMING,
    TextureKind,
    TextureNamingProfile,
    replace_texture_suffix,
)


class TextureNamingTests(unittest.TestCase):
    def test_default_profile_defines_all_four_canonical_suffixes(self):
        self.assertIs(DEFAULT_TEXTURE_NAMING, DOW2_TEXTURE_NAMING)
        self.assertEqual(DOW2_TEXTURE_NAMING.profile_id, "dow2")
        self.assertEqual(DOW2_TEXTURE_NAMING.display_name, "Dawn of War II")
        self.assertEqual(
            {
                kind: DEFAULT_TEXTURE_NAMING.suffix_for(kind)
                for kind in TextureKind
            },
            {
                TextureKind.DIFFUSE: "_dif",
                TextureKind.TEAM_COLOR: "_tem",
                TextureKind.DIRT: "_drt",
                TextureKind.SPECULAR: "_spc",
            },
        )

    def test_sm1_profile_uses_the_shared_model_with_pnt_team_color(self):
        self.assertEqual(SM1_TEXTURE_NAMING.profile_id, "sm1")
        self.assertEqual(SM1_TEXTURE_NAMING.display_name, "Space Marine 1")
        self.assertEqual(
            {kind: SM1_TEXTURE_NAMING.suffix_for(kind) for kind in TextureKind},
            {
                TextureKind.DIFFUSE: "_dif",
                TextureKind.TEAM_COLOR: "_pnt",
                TextureKind.DIRT: "_drt",
                TextureKind.SPECULAR: "_spc",
            },
        )

    def test_diffuse_suffix_replacements(self):
        source = Path("marine_dif.dds")

        self.assertEqual(
            replace_texture_suffix(
                source, TextureKind.DIFFUSE, TextureKind.TEAM_COLOR
            ),
            Path("marine_tem.dds"),
        )
        self.assertEqual(
            replace_texture_suffix(source, TextureKind.DIFFUSE, TextureKind.DIRT),
            Path("marine_drt.dds"),
        )
        self.assertEqual(
            replace_texture_suffix(
                source, TextureKind.DIFFUSE, TextureKind.SPECULAR
            ),
            Path("marine_spc.dds"),
        )

    def test_uppercase_extension_is_preserved(self):
        result = replace_texture_suffix(
            Path("marine_DIF.DDS"),
            TextureKind.DIFFUSE,
            TextureKind.TEAM_COLOR,
        )

        self.assertEqual(result, Path("marine_tem.DDS"))

    def test_multiple_dots_and_parent_directory_are_preserved(self):
        source = Path("textures") / "veteran.armour.v2_dif.tga"

        result = replace_texture_suffix(
            source, TextureKind.DIFFUSE, TextureKind.SPECULAR
        )

        self.assertEqual(result, Path("textures") / "veteran.armour.v2_spc.tga")
        self.assertEqual(result.parent, source.parent)

    def test_suffix_like_text_in_middle_is_not_replaced(self):
        self.assertIsNone(
            replace_texture_suffix(
                Path("marine_dif_variant.dds"),
                TextureKind.DIFFUSE,
                TextureKind.TEAM_COLOR,
            )
        )

    def test_missing_source_suffix_returns_none(self):
        self.assertIsNone(
            replace_texture_suffix(
                Path("marine.dds"),
                TextureKind.DIFFUSE,
                TextureKind.TEAM_COLOR,
            )
        )
        self.assertIsNone(
            replace_texture_suffix(
                Path("_dif.dds"),
                TextureKind.DIFFUSE,
                TextureKind.TEAM_COLOR,
            )
        )

    def test_unicode_path_round_trips(self):
        source = Path("纹理") / "élite_доспех_dif.png"

        result = replace_texture_suffix(
            source, TextureKind.DIFFUSE, TextureKind.DIRT
        )

        self.assertEqual(result, Path("纹理") / "élite_доспех_drt.png")

    def test_custom_profile_is_supported_without_filesystem_access(self):
        profile = TextureNamingProfile(
            profile_id="test",
            display_name="Test",
            diffuse_suffix="_base",
            team_color_mask_suffix="_mask",
            dirt_suffix="_wear",
            specular_suffix="_shine",
        )

        result = replace_texture_suffix(
            Path("unit_base.bin"),
            TextureKind.DIFFUSE,
            TextureKind.SPECULAR,
            profile,
        )

        self.assertEqual(result, Path("unit_shine.bin"))

    def test_profile_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            DEFAULT_TEXTURE_NAMING.diffuse_suffix = "_changed"

    def test_profile_rejects_noncanonical_suffixes(self):
        with self.assertRaisesRegex(ValueError, "leading underscore"):
            TextureNamingProfile(
                profile_id="invalid",
                display_name="Invalid",
                diffuse_suffix="dif",
                team_color_mask_suffix="_tem.dds",
                dirt_suffix="_drt",
                specular_suffix="_spc",
            )


if __name__ == "__main__":
    unittest.main()
