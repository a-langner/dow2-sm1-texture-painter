"""Reusable dialog fake for GUI-orchestration tests."""

from src.dialog_gateway import DialogGateway


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
