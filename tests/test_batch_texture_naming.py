import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.dow1_converter import team_color_output_path
from src.batch_processing_service import prepare_batch_workbench
from src.frame_main import ArmyPainter
from src.texture_naming import (
    DEFAULT_TEXTURE_NAMING,
    TextureKind,
    TextureNamingProfile,
    is_texture_kind,
    with_texture_kind,
)


class BatchTextureNamingTests(unittest.TestCase):
    def test_batch_detection_accepts_only_diffuse_files(self):
        painter = SimpleNamespace(texture_naming_profile=DEFAULT_TEXTURE_NAMING)

        self.assertTrue(
            ArmyPainter._check_diffuse_format(painter, "marine_dif.DDS", ["dds"])
        )
        for filename in (
            "marine_tem.dds",
            "marine_drt.dds",
            "marine_spc.dds",
            "marine.dds",
            "marine_dif.png",
        ):
            with self.subTest(filename=filename):
                self.assertFalse(
                    ArmyPainter._check_diffuse_format(painter, filename, ["dds"])
                )

    def test_batch_detection_supports_multiple_dots_and_custom_profile(self):
        profile = self._custom_profile()
        painter = SimpleNamespace(texture_naming_profile=profile)

        self.assertTrue(
            ArmyPainter._check_diffuse_format(
                painter, "marine.armour_BASE.TGA", ["tga"]
            )
        )
        self.assertFalse(
            ArmyPainter._check_diffuse_format(
                painter, "marine.armour_mask.tga", ["tga"]
            )
        )

    def test_team_color_output_uses_profile_and_removes_terminal_default_tag(self):
        destination = Path("output")

        self.assertEqual(
            team_color_output_path("marine.v2_default", destination, "DDS"),
            destination / "marine.v2_tem.DDS",
        )

    def test_team_color_output_never_duplicates_suffix(self):
        destination = Path("output")

        self.assertEqual(
            team_color_output_path("marine_tem", destination, "dds"),
            destination / "marine_tem.dds",
        )

    def test_team_color_output_supports_custom_profile(self):
        profile = self._custom_profile()

        self.assertEqual(
            team_color_output_path("marine_default", Path("output"), "tga", profile),
            Path("output") / "marine_mask.tga",
        )

    def test_invalid_output_names_are_rejected(self):
        self.assertIsNone(team_color_output_path("", Path("output"), "dds"))
        self.assertIsNone(team_color_output_path("marine", Path("output"), ""))

    def test_texture_classification_and_output_helpers_have_parity(self):
        source = Path("units") / "marine_dif.dds"
        output = with_texture_kind(source, TextureKind.TEAM_COLOR)

        self.assertTrue(is_texture_kind(source, TextureKind.DIFFUSE))
        self.assertTrue(is_texture_kind(output, TextureKind.TEAM_COLOR))
        self.assertEqual(output, Path("units") / "marine_tem.dds")

    @patch("src.batch_processing_service.ImageWorkbench")
    @patch("src.batch_processing_service.find_companion_texture")
    def test_batch_companion_discovery_receives_injected_profile(
        self, find_companion, workbench_type
    ):
        profile = self._custom_profile()
        workbench = workbench_type.return_value
        team_color_path = Path("marine_mask.dds")
        find_companion.side_effect = [team_color_path, None, None]

        prepare_batch_workbench(Path("marine_base.dds"), Mock(), profile)

        self.assertEqual(
            [call.args[1] for call in find_companion.call_args_list],
            [TextureKind.TEAM_COLOR, TextureKind.DIRT, TextureKind.SPECULAR],
        )
        self.assertTrue(
            all(call.args[2] is profile for call in find_companion.call_args_list)
        )
        workbench.load_team_colour_file.assert_called_once_with(team_color_path)

    def test_batch_detection_uses_no_filesystem_outside_temporary_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diffuse = root / "marine_dif.dds"
            diffuse.touch()

            self.assertTrue(is_texture_kind(diffuse, TextureKind.DIFFUSE))

    @staticmethod
    def _custom_profile():
        return TextureNamingProfile(
            name="Test Profile",
            diffuse_suffix="_base",
            team_color_suffix="_mask",
            dirt_suffix="_wear",
            specular_suffix="_shine",
        )


if __name__ == "__main__":
    unittest.main()
