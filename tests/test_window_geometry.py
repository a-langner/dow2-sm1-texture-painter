import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.constant import DEFAULT_IMG_SIZE, FRAME_TOOL_HEIGHT
from src.frame_main import ArmyPainter
from src.window_geometry import (
    PATTERN_LIST_DEFAULT_WIDTH,
    WINDOW_CONTENT_PADDING,
    WINDOW_INITIAL_SCALE,
    calculate_diffuse_window_size,
    calculate_initial_window_size,
    clamp_window_position,
    safe_window_geometry,
    safe_window_position,
)
from src.image_process import TextureValidationError
from src.texture_naming import DEFAULT_TEXTURE_NAMING


class FakeMaximizedPainter:
    _default_min_window_size = (678, 500)

    def __init__(self):
        self.minimum_calls = []

    def state(self):
        return "zoomed"

    def minsize(self, width, height):
        self.minimum_calls.append((width, height))

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def geometry(self, value):
        raise AssertionError("A maximized window must not be resized")


class FakeTextureLoading:
    def __init__(self, error=None):
        self.error = error

    def load_diffuse_and_companions(self, filepath):
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            texture_set=object(),
            available_team_color_mask_variants=(),
            active_team_color_mask_variant=None,
            width=512,
            height=256,
            team_color_mask_error=None,
            team_color_mask_path=None,
            warnings=(),
        )


class FakeLoadingPainter:
    def __init__(self, load_error=None):
        self.texture_loading = FakeTextureLoading(load_error)
        self.texture_naming_profile = DEFAULT_TEXTURE_NAMING
        self.resize_calls = []
        self.refresh_calls = 0
        self.preview_controller = Mock()
        self.active_texture_set = None

    def open_channel(self):
        pass

    def refresh_workspace(self):
        self.refresh_calls += 1

    def resize_for_diffuse(self, texture_size):
        self.resize_calls.append(texture_size)


class InitialWindowGeometryTests(unittest.TestCase):
    def test_scales_initial_size_when_screen_has_room(self):
        result = calculate_initial_window_size(800, 600, 2560, 1600)

        self.assertEqual(
            result,
            (
                round(800 * WINDOW_INITIAL_SCALE),
                round(600 * WINDOW_INITIAL_SCALE),
            ),
        )

    def test_clamps_initial_size_to_ninety_percent_of_screen(self):
        result = calculate_initial_window_size(1000, 800, 1200, 900)

        self.assertEqual(result, (1080, 810))

    def test_clamping_never_changes_existing_minimum_boundary(self):
        result = calculate_initial_window_size(1000, 800, 900, 700)

        self.assertEqual(result, (1000, 800))

    def test_saved_geometry_is_clamped_to_virtual_multi_monitor_desktop(self):
        self.assertEqual(
            safe_window_geometry(
                "1100x720-2500+100",
                900,
                600,
                -1920,
                0,
                3840,
                1080,
            ),
            "1100x720-1920+100",
        )

    def test_malformed_saved_geometry_is_rejected(self):
        self.assertIsNone(
            safe_window_geometry("not geometry", 900, 600, 0, 0, 1920, 1080)
        )

    def test_main_window_position_clamps_without_changing_startup_size(self):
        self.assertEqual(
            safe_window_position(
                (-2500, 900), 1100, 720, -1920, 0, 3840, 1080
            ),
            (-1920, 360),
        )

    def test_invalid_main_window_position_is_ignored(self):
        self.assertIsNone(
            safe_window_position(None, 1100, 720, 0, 0, 1920, 1080)
        )

    def test_main_window_restores_position_with_fresh_startup_size(self):
        painter = self._main_window_painter()
        settings = SimpleNamespace(main_window_position=(320, 180))

        with patch("src.frame_main.SettingsHandler", return_value=settings), patch(
            "src.frame_main.files"
        ) as resources, patch("src.frame_main.as_file") as as_file, patch(
            "src.frame_main.tk.PhotoImage", return_value="icon"
        ):
            resources.return_value.joinpath.return_value = "icon-resource"
            as_file.return_value.__enter__.return_value = "icon.png"
            ArmyPainter._configure_main_window(painter)

        expected_size = calculate_initial_window_size(
            678, DEFAULT_IMG_SIZE + FRAME_TOOL_HEIGHT, 1920, 1080
        )
        painter.geometry.assert_called_once_with(
            f"{expected_size[0]}x{expected_size[1]}+320+180"
        )
        self.assertIs(painter.settings, settings)

    def test_main_window_without_saved_position_uses_default_geometry(self):
        painter = self._main_window_painter()
        settings = SimpleNamespace(main_window_position=None)

        with patch("src.frame_main.SettingsHandler", return_value=settings), patch(
            "src.frame_main.files"
        ) as resources, patch("src.frame_main.as_file") as as_file, patch(
            "src.frame_main.tk.PhotoImage", return_value="icon"
        ):
            resources.return_value.joinpath.return_value = "icon-resource"
            as_file.return_value.__enter__.return_value = "icon.png"
            ArmyPainter._configure_main_window(painter)

        expected_size = calculate_initial_window_size(
            678, DEFAULT_IMG_SIZE + FRAME_TOOL_HEIGHT, 1920, 1080
        )
        painter.geometry.assert_called_once_with(
            f"{expected_size[0]}x{expected_size[1]}"
        )
        self.assertEqual(painter._default_min_window_size, expected_size)
        painter.minsize.assert_called_once_with(*expected_size)

    @staticmethod
    def _main_window_painter():
        return SimpleNamespace(
            winfo_screenwidth=Mock(return_value=1920),
            winfo_screenheight=Mock(return_value=1080),
            winfo_vrootx=Mock(return_value=0),
            winfo_vrooty=Mock(return_value=0),
            winfo_vrootwidth=Mock(return_value=1920),
            winfo_vrootheight=Mock(return_value=1080),
            geometry=Mock(),
            iconphoto=Mock(),
            minsize=Mock(),
            title=Mock(),
            protocol=Mock(),
            on_exit=Mock(),
        )


class DiffuseWindowGeometryTests(unittest.TestCase):
    def test_small_texture_is_clamped_to_minimum_size(self):
        result = calculate_diffuse_window_size(64, 64, 678, 500, 1920, 1080)

        self.assertEqual(result, (678, 500))

    def test_medium_texture_uses_texture_content_size(self):
        result = calculate_diffuse_window_size(400, 300, 678, 500, 1920, 1080)

        self.assertEqual(
            result,
            (
                400 * 2 + PATTERN_LIST_DEFAULT_WIDTH + WINDOW_CONTENT_PADDING,
                300 + FRAME_TOOL_HEIGHT + WINDOW_CONTENT_PADDING,
            ),
        )

    def test_large_texture_is_clamped_to_screen_allowance(self):
        result = calculate_diffuse_window_size(8192, 8192, 678, 500, 1920, 1080)

        self.assertEqual(result, (1728, 972))

    def test_screen_allowance_leaves_a_margin(self):
        width, height = calculate_diffuse_window_size(8192, 8192, 678, 500, 1600, 1000)

        self.assertLess(width, 1600)
        self.assertLess(height, 1000)

    def test_width_includes_two_previews_and_pattern_panel(self):
        width, _ = calculate_diffuse_window_size(300, 200, 500, 300, 2560, 1440)

        self.assertEqual(
            width,
            300 * 2 + PATTERN_LIST_DEFAULT_WIDTH + WINDOW_CONTENT_PADDING,
        )

    def test_position_is_preserved_or_clamped_to_visible_screen(self):
        self.assertEqual(
            clamp_window_position(100, 75, 800, 600, 1920, 1080),
            (100, 75),
        )
        self.assertEqual(
            clamp_window_position(1800, -20, 800, 600, 1920, 1080),
            (1120, 0),
        )

    def test_maximized_window_is_not_resized(self):
        painter = FakeMaximizedPainter()

        ArmyPainter.resize_for_diffuse(painter, (1024, 1024))

        self.assertEqual(painter.minimum_calls, [(1728, 972)])

    def test_loaded_minimum_can_decrease_but_not_below_startup_minimum(self):
        painter = SimpleNamespace(
            _default_min_window_size=(800, 600),
            winfo_screenwidth=Mock(return_value=1920),
            winfo_screenheight=Mock(return_value=1080),
            winfo_x=Mock(return_value=100),
            winfo_y=Mock(return_value=75),
            minsize=Mock(),
            geometry=Mock(),
            state=Mock(return_value="normal"),
            attributes=Mock(return_value=False),
        )

        ArmyPainter.resize_for_diffuse(painter, (600, 700))
        ArmyPainter.resize_for_diffuse(painter, (64, 64))

        self.assertEqual(
            painter.minsize.call_args_list,
            [
                call(
                    *calculate_diffuse_window_size(
                        600, 700, 800, 600, 1920, 1080
                    )
                ),
                call(800, 600),
            ],
        )

    def test_invalid_diffuse_does_not_reach_resize(self):
        painter = FakeLoadingPainter(TextureValidationError("invalid diffuse"))

        with self.assertRaises(TextureValidationError):
            ArmyPainter.load_file(painter, "invalid_dif.png")

        self.assertEqual(painter.resize_calls, [])

    def test_successful_diffuse_load_resizes_exactly_once(self):
        painter = FakeLoadingPainter()

        ArmyPainter.load_file(painter, "valid_dif.png")

        self.assertEqual(painter.refresh_calls, 1)
        self.assertEqual(painter.resize_calls, [(512, 256)])
        painter.preview_controller.invalidate.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
