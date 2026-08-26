# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
from shutil import copy2

from PyInstaller.utils.hooks import collect_data_files
from src.app_identity import BUILD_NAME


BUNDLE_NAME = BUILD_NAME
ONE_FILE = os.environ.get("TEXTURE_PAINTER_ONEFILE") == "1"
PROJECT_ROOT = Path(SPECPATH).resolve()
ENTRY_POINT = PROJECT_ROOT / "src" / "frame_main.py"
APP_ICON = PROJECT_ROOT / "src" / "resources" / "icon_64x64.ico"
LEGAL_FILES = (
    PROJECT_ROOT / "LICENSE",
    PROJECT_ROOT / "THIRD_PARTY_NOTICES.md",
)

# Keep immutable package resources at their importable package destination.
RESOURCE_DATA = collect_data_files("src.resources")

analysis = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=RESOURCE_DATA,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
python_archive = PYZ(analysis.pure)

if ONE_FILE:
    executable = EXE(
        python_archive,
        analysis.scripts,
        analysis.binaries,
        analysis.datas,
        [],
        name=BUNDLE_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        icon=str(APP_ICON),
    )
else:
    executable = EXE(
        python_archive,
        analysis.scripts,
        [],
        exclude_binaries=True,
        name=BUNDLE_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        icon=str(APP_ICON),
    )
    bundle = COLLECT(
        executable,
        analysis.binaries,
        analysis.datas,
        strip=False,
        upx=True,
        name=BUNDLE_NAME,
    )
    bundle_directory = Path(DISTPATH) / BUNDLE_NAME
    for legal_file in LEGAL_FILES:
        copy2(legal_file, bundle_directory / legal_file.name)
