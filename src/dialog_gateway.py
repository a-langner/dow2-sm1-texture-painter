"""Narrow Tkinter dialog access for the application's GUI layer."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog


class DialogGateway:
    """Present simple application dialogs with one consistent Tk parent."""

    def __init__(self, parent: tk.Misc):
        self._parent = parent

    def choose_open_file(self, *, title=None, initial_directory=None, filetypes=()):
        options = {"parent": self._parent, "filetypes": filetypes}
        if title is not None:
            options["title"] = title
        if initial_directory is not None:
            options["initialdir"] = initial_directory
        selected = filedialog.askopenfilename(**options)
        return Path(selected) if selected else None

    def choose_save_file(
        self,
        *,
        title=None,
        initial_directory=None,
        initial_filename=None,
        default_extension=None,
        filetypes=(),
    ):
        options = {"parent": self._parent, "filetypes": filetypes}
        if title is not None:
            options["title"] = title
        if initial_directory is not None:
            options["initialdir"] = initial_directory
        if initial_filename is not None:
            options["initialfile"] = initial_filename
        if default_extension is not None:
            options["defaultextension"] = default_extension
        selected = filedialog.asksaveasfilename(**options)
        return Path(selected) if selected else None

    def ask_text(self, *, title, prompt, initial_value=None):
        options = {"parent": self._parent}
        if initial_value is not None:
            options["initialvalue"] = initial_value
        result = simpledialog.askstring(title, prompt, **options)
        return result

    def confirm(self, *, title, message, default="no"):
        return messagebox.askyesno(
            title,
            message,
            default=default,
            parent=self._parent,
        )

    def show_error(self, *, title, message):
        messagebox.showerror(title, message, parent=self._parent)

    def show_warning(self, *, title, message):
        messagebox.showwarning(title, message, parent=self._parent)

    def show_info(self, *, title, message):
        messagebox.showinfo(title, message, parent=self._parent)
