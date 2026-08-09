import ast
import unittest
from pathlib import Path

from PIL import Image

import test_support  # noqa: F401 - installs the user-data path redirect
from src.image_process import ImageWorkbench
from src.texture_set import TextureSet


class TextureSetTests(unittest.TestCase):
    def test_diffuse_only_texture_set(self):
        diffuse = Image.new("RGBA", (4, 2), "red")

        texture_set = TextureSet(diffuse)

        self.assertIs(texture_set.diffuse, diffuse)
        self.assertIsNone(texture_set.team_color)
        self.assertIsNone(texture_set.dirt)
        self.assertIsNone(texture_set.specular)

    def test_all_companions_are_retained_by_identity(self):
        diffuse = Image.new("RGBA", (2, 2))
        team_color = Image.new("RGBA", (2, 2))
        dirt = Image.new("RGBA", (2, 2))
        specular = Image.new("RGBA", (2, 2))

        texture_set = TextureSet(diffuse, team_color, dirt, specular)

        self.assertIs(texture_set.diffuse, diffuse)
        self.assertIs(texture_set.team_color, team_color)
        self.assertIs(texture_set.dirt, dirt)
        self.assertIs(texture_set.specular, specular)

    def test_dimensions_come_from_required_diffuse(self):
        texture_set = TextureSet(Image.new("RGB", (8, 4)))

        self.assertEqual(texture_set.dimensions, (8, 4))

    def test_diffuse_is_required(self):
        with self.assertRaisesRegex(ValueError, "requires a diffuse"):
            TextureSet(None)

    def test_companion_reference_can_be_replaced(self):
        first = Image.new("RGBA", (2, 2), "red")
        second = Image.new("RGBA", (2, 2), "blue")
        texture_set = TextureSet(Image.new("RGBA", (2, 2)), dirt=first)

        texture_set.dirt = second

        self.assertIs(texture_set.dirt, second)

    def test_render_copy_has_independent_container_and_shared_images(self):
        diffuse = Image.new("RGBA", (2, 2))
        team_color = Image.new("RGBA", (2, 2))
        texture_set = TextureSet(diffuse, team_color)

        render_copy = texture_set.copy_for_render()
        texture_set.team_color = None

        self.assertIsNot(render_copy, texture_set)
        self.assertIs(render_copy.diffuse, diffuse)
        self.assertIs(render_copy.team_color, team_color)
        self.assertIsNone(texture_set.team_color)

    def test_workbench_adapter_has_one_authoritative_source_state(self):
        workbench = ImageWorkbench()
        diffuse = Image.new("RGBA", (2, 2), "white")
        dirt = Image.new("RGBA", (2, 2), "red")

        workbench.img_og_dif = diffuse
        workbench.img_dirt = dirt

        self.assertIs(workbench.texture_set.diffuse, diffuse)
        self.assertIs(workbench.texture_set.dirt, dirt)
        self.assertIs(workbench.img_og_dif, workbench.texture_set.diffuse)
        self.assertIs(workbench.img_dirt, workbench.texture_set.dirt)

    def test_render_snapshot_consumes_texture_set_without_copying_images(self):
        workbench = ImageWorkbench()
        diffuse = workbench.texture_set.diffuse
        team_color = workbench.texture_set.team_color

        snapshot = workbench.render_snapshot()
        workbench.texture_set.team_color = None

        self.assertIsNot(snapshot.texture_set, workbench.texture_set)
        self.assertIs(snapshot.texture_set.diffuse, diffuse)
        self.assertIs(snapshot.texture_set.team_color, team_color)
        self.assertEqual(snapshot.refresh_workspace().size, diffuse.size)

    def test_model_has_no_gui_or_filesystem_dependencies(self):
        source_path = Path(__file__).resolve().parents[1] / "src" / "texture_set.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )

        self.assertNotIn("tkinter", imports)
        self.assertNotIn("pathlib", imports)
        self.assertNotIn("os", imports)
        self.assertNotIn("src.frame_main", imports)

    def test_model_stores_only_source_images(self):
        texture_set = TextureSet(Image.new("RGBA", (2, 2)))

        self.assertEqual(
            set(vars(texture_set)),
            {"diffuse", "team_color", "dirt", "specular"},
        )
        self.assertNotIn("workspace", vars(texture_set))
        self.assertNotIn("render_settings", vars(texture_set))


if __name__ == "__main__":
    unittest.main()
