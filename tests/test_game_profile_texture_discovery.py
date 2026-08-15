import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.texture_loading_service import (
    TextureLoadingService,
    detect_texture_naming_profile,
)
from src.texture_naming import DOW2_TEXTURE_NAMING, SM1_TEXTURE_NAMING


def save_test_texture(path: Path) -> None:
    Image.new("RGBA", (8, 4), (128, 128, 128, 255)).save(path, format="PNG")


class GameProfileTextureDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def create_textures(self, *suffixes: str) -> dict[str, Path]:
        paths = {suffix: self.root / f"unit{suffix}.dds" for suffix in suffixes}
        for path in paths.values():
            save_test_texture(path)
        return paths

    def assert_profile_loads_expected_companions(
        self,
        mask_suffix: str,
        expected_profile,
    ) -> None:
        paths = self.create_textures("_dif", mask_suffix, "_drt", "_spc")
        diffuse = paths["_dif"]

        detected = detect_texture_naming_profile(diffuse)
        self.assertIs(detected, expected_profile)
        result = TextureLoadingService(detected).load_diffuse_and_companions(diffuse)

        self.assertEqual(result.team_color_mask_path, paths[mask_suffix])
        self.assertEqual(result.dirt_path, paths["_drt"])
        self.assertEqual(result.specular_path, paths["_spc"])
        self.assertIsNotNone(result.texture_set.team_color)
        self.assertIsNotNone(result.texture_set.dirt)
        self.assertIsNotNone(result.texture_set.specular)

    def test_dow2_profile_loads_tem_drt_and_spc(self):
        self.assert_profile_loads_expected_companions(
            "_tem",
            DOW2_TEXTURE_NAMING,
        )

    def test_sm1_profile_loads_pnt_drt_and_spc(self):
        self.assert_profile_loads_expected_companions(
            "_pnt",
            SM1_TEXTURE_NAMING,
        )

    def test_diffuse_loads_when_every_companion_is_missing(self):
        diffuse = self.create_textures("_dif")["_dif"]

        self.assertIsNone(detect_texture_naming_profile(diffuse))
        result = TextureLoadingService().load_diffuse_and_companions(diffuse)

        self.assertEqual(result.diffuse_path, diffuse)
        self.assertIsNone(result.team_color_mask_path)
        self.assertIsNone(result.dirt_path)
        self.assertIsNone(result.specular_path)
        self.assertIsNone(result.texture_set.team_color)
        self.assertIsNone(result.texture_set.dirt)
        self.assertIsNone(result.texture_set.specular)
        self.assertEqual(result.warnings, ())

    def test_tem_and_pnt_together_are_ambiguous(self):
        paths = self.create_textures("_dif", "_tem", "_pnt")

        self.assertIsNone(detect_texture_naming_profile(paths["_dif"]))


if __name__ == "__main__":
    unittest.main()
