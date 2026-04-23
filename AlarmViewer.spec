# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


# PyInstaller executes spec files without defining __file__.
# The repo scripts/workflows `cd` into the project root before invoking this spec.
ROOT = Path.cwd().resolve()
IS_MAC = sys.platform == "darwin"
ICON_PATH = ROOT / "assets" / ("app_icon.icns" if IS_MAC else "app_icon.ico")

datas = [
    (str(ROOT / "assets" / "app_icon.png"), "assets"),
    (str(ROOT / "VERSION"), "."),
]
datas += collect_data_files(
    "alarm_app.bdt.vendor_synthid",
    includes=["*.pkl"],
)

hiddenimports = [
    "pandas",
    "openpyxl",
    "xlrd",
    "pyarrow",
    "python_calamine",
    "duckdb",
    "sqlalchemy",
    "uvicorn",
    "fastapi",
    "requests",
    "imagehash",
    "cv2",
    "pywt",
    "sklearn",
    "scipy",
    "c2pa",
]
hiddenimports += collect_submodules("alarm_app.db.repos")
hiddenimports += collect_submodules("alarm_app.web")
hiddenimports += collect_submodules("alarm_app.bdt.vendor_synthid")


a = Analysis(
    ["scripts/pyinstaller_entry.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AlarmViewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ICON_PATH),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AlarmViewer",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="AlarmViewer.app",
        icon=str(ICON_PATH),
        bundle_identifier="com.orange.alarmviewer",
    )
