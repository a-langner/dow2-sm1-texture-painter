"""Reusable dialog fake for GUI-orchestration tests."""

from src.dialog_gateway import DialogGateway
from src.file_selection_service import FileSelectionService


class FakeDialogGateway:
    def __init__(self):
        self.open_file_result = None
        self.save_file_result = None
        self.text_result = None
        self.confirm_result = False
        self.calls = []

    def choose_open_file(self, **options):
        self.calls.append(("choose_open_file", options))
        return self.open_file_result

    def choose_save_file(self, **options):
        self.calls.append(("choose_save_file", options))
        return self.save_file_result

    def ask_text(self, **options):
        self.calls.append(("ask_text", options))
        return self.text_result

    def confirm(self, **options):
        self.calls.append(("confirm", options))
        return self.confirm_result

    def show_error(self, **options):
        self.calls.append(("show_error", options))

    def show_warning(self, **options):
        self.calls.append(("show_warning", options))

    def show_info(self, **options):
        self.calls.append(("show_info", options))


def make_dialog_gateway(parent):
    """Build the real gateway with its Tk calls patched by the current test."""
    return DialogGateway(parent)


def make_file_selection_service(painter):
    """Build file-selection coordination for a lightweight painter double."""
    settings = painter.settings
    home_directory = next(
        (
            value
            for value in (
                getattr(settings, "initial_directory", None),
                getattr(settings, "import_directory", None),
                getattr(settings, "export_directory", None),
            )
            if value is not None
        ),
        None,
    )
    return FileSelectionService(
        settings,
        painter.dialogs,
        home_directory=home_directory,
    )
