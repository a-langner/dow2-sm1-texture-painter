import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.image_process import ImageWorkbench, TextureValidationError
from src.texture_loading_service import (
    TextureDiscoveryError,
    TextureLoadingService,
    UnsupportedTextureError,
)
from src.texture_naming import TextureKind, TextureNamingProfile


def save_image(path, size=(8, 4), mode="RGBA", color=None):
    if color is None:
        color = (128, 128, 128, 255) if mode == "RGBA" else (128, 128, 128)
    Image.new(mode, size, color).save(path, format="PNG")


class TextureLoadingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.workbench = ImageWorkbench()
        self.service = TextureLoadingService(self.workbench)

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
        self.assertEqual(result.team_color_path, team)
        self.assertEqual(result.dirt_path, dirt)
        self.assertEqual(result.specular_path, specular)
        self.assertIsNone(result.team_color_error)
        self.assertEqual(result.warnings, ())
        self.assertEqual(len(self.workbench.tem_channels), 4)
        self.assertEqual(self.workbench.img_dirt.size, (8, 4))
        self.assertEqual(self.workbench.img_spec.size, (8, 4))

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

        self.assertIsNone(result.team_color_path)
        self.assertIsNone(result.team_color_error)
        self.assertEqual(self.workbench.tem_channels, [])

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

        self.assertIn("identical dimensions", result.team_color_error)
        self.assertEqual(
            [warning.kind for warning in result.warnings],
            [TextureKind.DIRT, TextureKind.SPECULAR],
        )
        self.assertEqual(self.workbench.img_og_dif.size, (8, 4))
        self.assertIsNone(self.workbench.img_dirt)
        self.assertIsNone(self.workbench.img_spec)

    def test_invalid_diffuse_preserves_previous_workbench_state(self):
        previous_diffuse = self.workbench.img_og_dif
        invalid = self.root / "broken_dif.png"
        invalid.write_bytes(b"not an image")

        with self.assertRaises(TextureValidationError):
            self.service.load_diffuse_and_companions(invalid)

        self.assertIs(self.workbench.img_og_dif, previous_diffuse)

    def test_unsupported_extension_is_rejected_before_workbench_mutation(self):
        previous_diffuse = self.workbench.img_og_dif
        unsupported = self.root / "marine_dif.gif"
        save_image(unsupported)

        with self.assertRaises(UnsupportedTextureError):
            self.service.load_diffuse_and_companions(unsupported)

        self.assertIs(self.workbench.img_og_dif, previous_diffuse)

    def test_separate_channel_loading_returns_dimensions(self):
        diffuse = self.root / "marine_dif.png"
        channel = self.root / "manual_tem.png"
        save_image(diffuse)
        save_image(channel)
        self.service.load_diffuse_and_companions(diffuse)

        result = self.service.load_channel_file(channel)

        self.assertEqual(result.channel_path, channel)
        self.assertEqual((result.width, result.height), (8, 4))

    def test_extension_and_companion_matching_are_case_insensitive(self):
        diffuse = self.root / "marine_DIF.PNG"
        team = self.root / "marine_TEM.png"
        save_image(diffuse)
        save_image(team)

        result = self.service.load_diffuse_and_companions(diffuse)

        self.assertEqual(result.team_color_path, team)

    def test_injected_naming_profile_controls_discovery(self):
        profile = TextureNamingProfile(
            name="Test",
            diffuse_suffix="_base",
            team_color_suffix="_mask",
            dirt_suffix="_wear",
            specular_suffix="_shine",
        )
        diffuse = self.root / "marine_base.png"
        team = self.root / "marine_mask.png"
        save_image(diffuse)
        save_image(team)

        result = TextureLoadingService(
            self.workbench, profile
        ).load_diffuse_and_companions(diffuse)

        self.assertEqual(result.team_color_path, team)

    def test_discovery_failure_restores_previous_source_state(self):
        previous_state = (
            self.workbench.img_og_dif,
            self.workbench.img_og_tem,
            self.workbench.tem_channels,
            self.workbench.img_dirt,
            self.workbench.img_spec,
        )
        diffuse = self.root / "marine_dif.png"
        save_image(diffuse)

        with patch(
            "src.texture_loading_service.Path.iterdir",
            side_effect=PermissionError("denied"),
        ):
            with self.assertRaises(TextureDiscoveryError):
                self.service.load_diffuse_and_companions(diffuse)

        self.assertEqual(
            (
                self.workbench.img_og_dif,
                self.workbench.img_og_tem,
                self.workbench.tem_channels,
                self.workbench.img_dirt,
                self.workbench.img_spec,
            ),
            previous_state,
        )

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
