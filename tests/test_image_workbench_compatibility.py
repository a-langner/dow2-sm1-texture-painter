import inspect
import unittest

import test_support  # noqa: F401 - installs the user-data path redirect
from src.image_process import ImageWorkbench


class ImageWorkbenchCompatibilityBoundaryTests(unittest.TestCase):
    def test_public_surface_is_limited_to_texture_state_and_loading(self):
        public_methods = {
            name
            for name, member in inspect.getmembers(
                ImageWorkbench, predicate=inspect.isfunction
            )
            if not name.startswith("_")
        }

        self.assertEqual(
            public_methods,
            {
                "load_diffuse_file",
                "load_dirt_file",
                "load_specular_file",
                "load_team_colour_file",
                "set_placeholder_img",
            },
        )

    def test_instance_owns_only_the_authoritative_texture_set(self):
        workbench = ImageWorkbench()

        self.assertEqual(set(vars(workbench)), {"texture_set"})

    def test_removed_render_settings_and_alias_apis_stay_absent(self):
        removed_names = {
            "apply_render_settings",
            "get_render_settings",
            "img_dirt",
            "img_og_dif",
            "img_og_tem",
            "img_spec",
            "img_workspace",
            "process_coloring",
            "refresh_team_colour_img",
            "render_snapshot",
            "tem_channels",
        }
        workbench = ImageWorkbench()

        for name in removed_names:
            with self.subTest(name=name):
                self.assertFalse(hasattr(workbench, name))


if __name__ == "__main__":
    unittest.main()
