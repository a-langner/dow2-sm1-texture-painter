import unittest
from unittest.mock import patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter


class CompletedPreview:
    def done(self):
        return True

    def cancelled(self):
        return False

    def result(self):
        return "workspace-image", "team-colour-image"


class FakeLabel:
    def __init__(self):
        self.image = None

    def config(self, image):
        self.image = image


class FakePainter:
    def __init__(self, future):
        self.closing = False
        self.preview_generation = 4
        self.preview_futures = {future}
        self.img_wbench = type("Workbench", (), {})()
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
        future = CompletedPreview()
        painter = FakePainter(future)

        ArmyPainter.poll_preview_result(painter, 4, future)

        self.assertEqual(painter.img_wbench.img_workspace, "workspace-image")
        self.assertEqual(
            painter.label_img_dif.image, "display:workspace-image"
        )
        self.assertEqual(
            painter.label_img_tem.image, "display:team-colour-image"
        )
        self.assertNotIn(future, painter.preview_futures)


if __name__ == "__main__":
    unittest.main()
