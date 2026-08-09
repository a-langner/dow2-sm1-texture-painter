import unittest
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter
from src.preview_controller import PreviewResult


class FakeLabel:
    def __init__(self):
        self.image = None

    def config(self, image):
        self.image = image


class FakePainter:
    def __init__(self):
        self.label_img_dif = FakeLabel()
        self.label_img_tem = FakeLabel()

    def geometry(self, *args):
        raise AssertionError("Preview completion must not change geometry")


class PreviewGeometryTests(unittest.TestCase):
    @patch(
        "src.frame_main.ImageTk.PhotoImage",
        side_effect=lambda image: f"display:{image}",
    )
    def test_completed_preview_updates_labels_without_geometry_change(
        self, photo_image
    ):
        painter = FakePainter()

        ArmyPainter.apply_preview_result(
            painter,
            PreviewResult(4, "workspace-image", "team-colour-image"),
        )

        self.assertFalse(hasattr(painter, "preview_output"))
        self.assertFalse(hasattr(painter, "rendered_output"))
        self.assertEqual(
            painter.label_img_dif.image, "display:workspace-image"
        )
        self.assertEqual(
            painter.label_img_tem.image, "display:team-colour-image"
        )


if __name__ == "__main__":
    unittest.main()
