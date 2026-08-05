import unittest
from pathlib import Path
from unittest.mock import patch

from src.dialog_gateway import DialogGateway


class DialogGatewayTests(unittest.TestCase):
    def setUp(self):
        self.parent = object()
        self.dialogs = DialogGateway(self.parent)

    @patch("src.dialog_gateway.filedialog.askopenfilename")
    def test_open_file_returns_path_and_passes_parent(self, choose):
        choose.return_value = "C:/textures/unit_dif.png"

        result = self.dialogs.choose_open_file(
            title="Open diffuse",
            initial_directory=Path("C:/textures"),
            filetypes=(("Images", "*.png"),),
        )

        self.assertEqual(result, Path("C:/textures/unit_dif.png"))
        self.assertIs(choose.call_args.kwargs["parent"], self.parent)

    @patch("src.dialog_gateway.filedialog.askopenfilename", return_value="")
    def test_cancelled_open_file_returns_none(self, choose):
        self.assertIsNone(self.dialogs.choose_open_file())

    @patch("src.dialog_gateway.filedialog.asksaveasfilename")
    def test_save_file_returns_path_and_preserves_options(self, choose):
        choose.return_value = "C:/patterns/name.pattern.json"

        result = self.dialogs.choose_save_file(
            title="Export Pattern",
            initial_directory=Path("C:/patterns"),
            initial_filename="name.pattern.json",
            default_extension=".pattern.json",
            filetypes=(("Patterns", "*.pattern.json"),),
        )

        self.assertEqual(result, Path("C:/patterns/name.pattern.json"))
        self.assertIs(choose.call_args.kwargs["parent"], self.parent)
        self.assertEqual(choose.call_args.kwargs["title"], "Export Pattern")

    @patch("src.dialog_gateway.filedialog.asksaveasfilename", return_value="")
    def test_cancelled_save_file_returns_none(self, choose):
        self.assertIsNone(self.dialogs.choose_save_file())

    @patch("src.dialog_gateway.simpledialog.askstring", return_value=None)
    def test_text_cancellation_returns_none_and_passes_parent(self, ask):
        self.assertIsNone(self.dialogs.ask_text(title="Name", prompt="Name:"))
        self.assertIs(ask.call_args.kwargs["parent"], self.parent)

    @patch("src.dialog_gateway.messagebox.askyesno", return_value=True)
    def test_confirmation_uses_requested_safe_default(self, confirm):
        self.assertTrue(
            self.dialogs.confirm(
                title="Delete", message="Delete it?", default="no"
            )
        )
        confirm.assert_called_once_with(
            "Delete", "Delete it?", default="no", parent=self.parent
        )

    @patch("src.dialog_gateway.messagebox.showinfo")
    @patch("src.dialog_gateway.messagebox.showwarning")
    @patch("src.dialog_gateway.messagebox.showerror")
    def test_messages_preserve_content_and_parent(self, error, warning, info):
        self.dialogs.show_error(title="Error", message="bad")
        self.dialogs.show_warning(title="Warning", message="careful")
        self.dialogs.show_info(title="Info", message="done")

        error.assert_called_once_with("Error", "bad", parent=self.parent)
        warning.assert_called_once_with("Warning", "careful", parent=self.parent)
        info.assert_called_once_with("Info", "done", parent=self.parent)


if __name__ == "__main__":
    unittest.main()
