import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.image_process import TextureValidationError
from src.texture_loading_service import (
    TextureDiscoveryError,
    TextureLoadingService,
    UnsupportedTextureError,
)
from src.texture_naming import (
    SM1_TEXTURE_NAMING,
    TextureKind,
    TextureNamingProfile,
)


def save_image(path, size=(8, 4), mode="RGBA", color=None):
    if color is None:
        color = (128, 128, 128, 255) if mode == "RGBA" else (128, 128, 128)
    Image.new(mode, size, color).save(path, format="PNG")


class TextureLoadingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.service = TextureLoadingService()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_loads_diffuse_and_all_companions_with_dimensions_and_paths(self):
        diffuse = self.root / "marine_dif.png"
        team = self.root / "marine_tem.png"
        dirt = self.root / "marine_drt.png"
        specular = self.root / "marine_spc.png"
        for path in (diffuse, team, dirt, specular):
            save_image(path)

        result = self.service.load_diffuse_and_companions(diffuse)

        self.assertEqual((result.width, result.height), (8, 4))
        self.assertEqual(result.diffuse_path, diffuse)
        self.assertEqual(result.team_color_mask_path, team.resolve())
        self.assertEqual(
            [variant.filename for variant in result.available_team_color_mask_variants],
            ["marine_tem.png"],
        )
        self.assertIs(
            result.active_team_color_mask_variant,
            result.available_team_color_mask_variants[0],
        )
        self.assertTrue(result.active_team_color_mask_variant.is_default)
        self.assertEqual(result.dirt_path, dirt)
        self.assertEqual(result.specular_path, specular)
        self.assertIsNone(result.team_color_mask_error)
        self.assertEqual(result.warnings, ())
        self.assertEqual(result.texture_set.team_color.mode, "RGBA")
        self.assertEqual(result.texture_set.dirt.size, (8, 4))
        self.assertEqual(result.texture_set.specular.size, (8, 4))

    def test_missing_optional_companions_are_nonfatal(self):
        diffuse = self.root / "marine_dif.png"
        team = self.root / "marine_tem.png"
        save_image(diffuse)
        save_image(team)

        result = self.service.load_diffuse_and_companions(diffuse)

        self.assertIsNone(result.dirt_path)
        self.assertIsNone(result.specular_path)
        self.assertEqual(result.warnings, ())

    def test_missing_team_color_is_reported_as_recoverable(self):
        diffuse = self.root / "marine_dif.png"
        save_image(diffuse)

        result = self.service.load_diffuse_and_companions(diffuse)

        self.assertIsNone(result.team_color_mask_path)
        self.assertIsNone(result.team_color_mask_error)
        self.assertEqual(result.available_team_color_mask_variants, ())
        self.assertIsNone(result.active_team_color_mask_variant)
        self.assertIsNone(result.texture_set.team_color)

    def test_invalid_companions_return_structured_issues(self):
        diffuse = self.root / "marine_dif.png"
        team = self.root / "marine_tem.png"
        dirt = self.root / "marine_drt.png"
        specular = self.root / "marine_spc.png"
        save_image(diffuse, (8, 4))
        save_image(team, (4, 4))
        save_image(dirt, (3, 3))
        save_image(specular, (5, 5))

        with self.assertLogs("src.texture_loading_service", level="WARNING"):
            result = self.service.load_diffuse_and_companions(diffuse)

        self.assertIn("identical dimensions", result.team_color_mask_error)
        self.assertEqual(
            [warning.kind for warning in result.warnings],
            [TextureKind.DIRT, TextureKind.SPECULAR],
        )
        self.assertEqual(result.texture_set.diffuse.size, (8, 4))
        self.assertIsNone(result.texture_set.dirt)
        self.assertIsNone(result.texture_set.specular)

    def test_invalid_diffuse_returns_no_texture_set(self):
        invalid = self.root / "broken_dif.png"
        invalid.write_bytes(b"not an image")

        with self.assertRaises(TextureValidationError):
            self.service.load_diffuse_and_companions(invalid)

    def test_unsupported_extension_is_rejected_before_loading(self):
        unsupported = self.root / "marine_dif.gif"
        save_image(unsupported)

        with self.assertRaises(UnsupportedTextureError):
            self.service.load_diffuse_and_companions(unsupported)


    def test_separate_channel_loading_returns_dimensions(self):
        diffuse = self.root / "marine_dif.png"
        channel = self.root / "manual_tem.png"
        dirt = self.root / "marine_drt.png"
        specular = self.root / "marine_spc.png"
        save_image(diffuse)
        save_image(channel)
        save_image(dirt)
        save_image(specular)
        textures = self.service.load_diffuse_and_companions(diffuse).texture_set

        result = self.service.load_channel_file(textures, channel)

        self.assertEqual(result.channel_path, channel)
        self.assertEqual((result.width, result.height), (8, 4))
        self.assertIsNot(result.texture_set, textures)
        self.assertIs(result.texture_set.diffuse, textures.diffuse)
        self.assertIs(result.texture_set.dirt, textures.dirt)
        self.assertIs(result.texture_set.specular, textures.specular)

    def test_channel_loading_requires_an_active_diffuse(self):
        channel = self.root / "manual_tem.png"
        save_image(channel)

        with self.assertRaisesRegex(TextureValidationError, "Load a diffuse"):
            self.service.load_channel_file(None, channel)

    def test_extension_and_companion_matching_are_case_insensitive(self):
        diffuse = self.root / "marine_DIF.PNG"
        team = self.root / "marine_TEM.png"
        save_image(diffuse)
        save_image(team)

        result = self.service.load_diffuse_and_companions(diffuse)

        self.assertEqual(result.team_color_mask_path, team.resolve())

    def test_dds_diffuse_loads_png_team_color_mask(self):
        diffuse = self.root / "marine_dif.dds"
        team = self.root / "marine_tem.png"
        save_image(diffuse)
        save_image(team)

        result = self.service.load_diffuse_and_companions(diffuse)

        self.assertEqual(result.team_color_mask_path, team.resolve())
        self.assertIsNotNone(result.texture_set.team_color)

    def test_jpeg_and_tiff_are_supported_across_diffuse_and_mask_roles(self):
        for diffuse_extension, mask_extension in (
            (".jpeg", ".tif"),
            (".tif", ".jpeg"),
            (".tiff", ".png"),
        ):
            with self.subTest(
                diffuse_extension=diffuse_extension,
                mask_extension=mask_extension,
            ):
                diffuse = self.root / f"marine_dif{diffuse_extension}"
                team = self.root / f"marine_tem{mask_extension}"
                Image.new("RGB", (8, 4), (80, 120, 160)).save(diffuse)
                Image.new("RGB", (8, 4), (255, 0, 0)).save(team)

                result = self.service.load_diffuse_and_companions(diffuse)

                self.assertEqual(result.team_color_mask_path, team.resolve())
                self.assertIsNotNone(result.texture_set.team_color)
                diffuse.unlink()
                team.unlink()

    def test_injected_naming_profile_controls_discovery(self):
        profile = TextureNamingProfile(
            profile_id="test",
            display_name="Test",
            diffuse_suffix="_base",
            team_color_mask_suffix="_mask",
            dirt_suffix="_wear",
            specular_suffix="_shine",
        )
        diffuse = self.root / "marine_base.png"
        team = self.root / "marine_mask.png"
        save_image(diffuse)
        save_image(team)

        result = TextureLoadingService(profile).load_diffuse_and_companions(diffuse)

        self.assertEqual(result.team_color_mask_path, team.resolve())

    def test_sm1_profile_discovers_pnt_without_changing_other_companions(self):
        diffuse = self.root / "marine_dif.png"
        dow2_team = self.root / "marine_tem.png"
        sm1_team = self.root / "marine_pnt.png"
        dirt = self.root / "marine_drt.png"
        specular = self.root / "marine_spc.png"
        for path in (diffuse, dow2_team, sm1_team, dirt, specular):
            save_image(path)

        result = TextureLoadingService(
            SM1_TEXTURE_NAMING
        ).load_diffuse_and_companions(diffuse)

        self.assertEqual(result.team_color_mask_path, sm1_team.resolve())
        self.assertEqual(result.dirt_path, dirt)
        self.assertEqual(result.specular_path, specular)

    def test_lowest_numbered_variant_loads_when_default_is_absent(self):
        diffuse = self.root / "marine_dif.png"
        second = self.root / "marine_tem_2.png"
        fifth = self.root / "marine_tem_5.png"
        for path in (diffuse, fifth, second):
            save_image(path)

        result = self.service.load_diffuse_and_companions(diffuse)

        self.assertEqual(
            [variant.variant_index for variant in result.available_team_color_mask_variants],
            [2, 5],
        )
        self.assertEqual(result.active_team_color_mask_variant.variant_index, 2)
        self.assertEqual(result.team_color_mask_path, second.resolve())
        self.assertIsNotNone(result.texture_set.team_color)

    def test_new_diffuse_load_prefers_default_over_numbered_variants(self):
        diffuse = self.root / "marine_dif.png"
        default = self.root / "marine_tem.png"
        second = self.root / "marine_tem_2.png"
        save_image(diffuse)
        save_image(default, color=(10, 20, 30, 255))
        save_image(second, color=(40, 50, 60, 255))

        result = self.service.load_diffuse_and_companions(diffuse)

        self.assertTrue(result.active_team_color_mask_variant.is_default)
        self.assertEqual(result.team_color_mask_path, default.resolve())
        self.assertEqual(result.texture_set.team_color.getpixel((0, 0)), (10, 20, 30, 255))

    def test_discovery_failure_returns_no_partial_texture_set(self):
        diffuse = self.root / "marine_dif.png"
        save_image(diffuse)

        with patch(
            "src.texture_loading_service.Path.iterdir",
            side_effect=PermissionError("denied"),
        ):
            with self.assertRaises(TextureDiscoveryError):
                self.service.load_diffuse_and_companions(diffuse)

    def test_loaded_files_are_not_kept_open(self):
        diffuse = self.root / "marine_dif.png"
        team = self.root / "marine_tem.png"
        save_image(diffuse)
        save_image(team)
        self.service.load_diffuse_and_companions(diffuse)

        diffuse.unlink()
        team.unlink()

        self.assertFalse(diffuse.exists())
        self.assertFalse(team.exists())

    def test_service_has_no_tk_dialog_settings_or_armypainter_dependencies(self):
        import src.texture_loading_service as module

        source = inspect.getsource(module)
        self.assertNotIn("tkinter", source)
        self.assertNotIn("messagebox", source)
        self.assertNotIn("SettingsHandler", source)
        self.assertNotIn("ArmyPainter", source)


if __name__ == "__main__":
    unittest.main()
