import os
import platform
from pathlib import Path
import subprocess

UNIX_DESKTOP_SYSTEMS = {
    "Linux",
    "FreeBSD",
    "OpenBSD",
    "NetBSD",
    "SunOS",
}


def open_directory_in_file_manager(path: Path) -> None:
    """Open a directory with the current platform's native file manager."""
    directory = Path(path)
    system_name = platform.system()
    if system_name == "Windows":
        startfile = getattr(os, "startfile", None)
        if startfile is None:
            raise OSError("The Windows file-manager launcher is unavailable")
        startfile(str(directory))
        return
    if system_name == "Darwin":
        subprocess.Popen(["open", str(directory)])
        return
    if system_name in UNIX_DESKTOP_SYSTEMS:
        subprocess.Popen(["xdg-open", str(directory)])
        return
    raise OSError(
        f"Opening directories is unsupported on {system_name or 'this platform'}"
    )
