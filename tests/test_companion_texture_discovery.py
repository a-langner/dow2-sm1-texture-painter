import tempfile
import unittest
from pathlib import Path

from src.frame_main import find_companion_texture
from src.texture_naming import TextureKind, TextureNamingProfile


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

            self.assertIsNone(
                find_companion_texture(diffuse, TextureKind.SPECULAR)
            )

    def test_invalid_diffuse_name_returns_none(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "marine.dds"
            source.touch()

            self.assertIsNone(
                find_companion_texture(source, TextureKind.TEAM_COLOR)
            )

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
            name="Temporary Test Profile",
            diffuse_suffix="_base",
            team_color_suffix="_mask",
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

    def test_diffuse_is_not_a_companion_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            diffuse = Path(directory) / "marine_dif.dds"
            diffuse.touch()

            with self.assertRaisesRegex(ValueError, "cannot be diffuse"):
                find_companion_texture(diffuse, TextureKind.DIFFUSE)


if __name__ == "__main__":
    unittest.main()
